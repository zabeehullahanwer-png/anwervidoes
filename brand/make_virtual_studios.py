"""Virtual studio sets for green-screen recordings (Blender/Cycles via pip `bpy`).

Each set is rendered from one 16:9 camera as two plates:
  <set>_bg.png  the room behind the presenter (presenter not rendered)
  <set>_fg.png  transparent foreground: the anchor desk and what stands on it
The presenter (keyed green-screen footage, or a cut-out photo) goes between the two.

  python3 brand/make_virtual_studios.py [--preview] [--only library,broadcast,...]
Sets: library, broadcast, arches, brand, manuscript
"""
import argparse
import math
import os
import random
import sys

import bpy
import mathutils

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "scripts"))
OUT = os.path.join(HERE, "studio", "plates")
TEX = os.path.join(HERE, "studio", "tex")
CAM = (0.0, -2.8, 1.30)         # presenter at y=0, eye line 1.22 m (seated); camera a little above
PITCH = -4.0                    # degrees, looking slightly down onto the desk
LENS = 60
DESK_TOP = 0.90

NAVY = (0.012, 0.035, 0.085)
GOLD = (1.0, 0.72, 0.36)
IVORY = (0.92, 0.88, 0.80)


# ---------------------------------------------------------------- textures (PIL)
def textures():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    import graphics
    os.makedirs(TEX, exist_ok=True)
    # 1) Islamic lattice (white lines on black): emission / alpha mask
    T = 512
    tile = graphics.islamic_tile(T, line_w=7)
    m = np.frombuffer(graphics.tiled_mask(tile, T, 2048, 2048), dtype=np.uint8).reshape(2048, 2048)
    Image.fromarray(m).save(os.path.join(TEX, "lattice.png"))
    tf = graphics.islamic_tile(256, line_w=5)
    mf = np.frombuffer(graphics.tiled_mask(tf, 256, 2048, 2048), dtype=np.uint8).reshape(2048, 2048)
    Image.fromarray(mf).save(os.path.join(TEX, "lattice_fine.png"))
    # 2) mashrabiya screen: inverse lattice with thick bars (holes let light through)
    tile2 = graphics.islamic_tile(256, line_w=30)
    m2 = np.frombuffer(graphics.tiled_mask(tile2, 256, 2048, 2048), dtype=np.uint8).reshape(2048, 2048)
    Image.fromarray(m2).save(os.path.join(TEX, "mashrabiya.png"))
    # 3) rosette (big gold medallion)
    rs = np.frombuffer(graphics.rosette(2048, 16), dtype=np.uint8).reshape(2048, 2048) if hasattr(graphics, "rosette") else m
    Image.fromarray(rs).save(os.path.join(TEX, "rosette.png"))
    # 4) row of pointed arches (white = opening)
    W, H = 4096, 2048
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    n = 5
    pitch = W / n
    for i in range(n):
        cx = pitch * (i + 0.5)
        hw = pitch * 0.36
        spring = H * 0.42
        r = hw * 1.55
        pts = [(cx - hw, H), (cx - hw, spring)]
        lc = cx - hw + r
        t0 = math.acos((cx - lc) / r)
        pts += [(lc + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, t0, 60)]
        rc = cx + hw - r
        t1 = math.acos((cx - rc) / r)
        pts += [(rc + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(t1, 0, 60)]
        pts += [(cx + hw, spring), (cx + hw, H)]
        d.polygon(pts, fill=255)
    im.save(os.path.join(TEX, "arches.png"))
    # 5) single tall arched window
    im = Image.new("L", (1024, 2048), 0)
    d = ImageDraw.Draw(im)
    hw, spring = 420, 760
    r = hw * 1.5
    cx = 512
    pts = [(cx - hw, 2048), (cx - hw, spring)]
    lc = cx - hw + r
    pts += [(lc + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.pi, math.acos((cx - lc) / r), 60)]
    rc = cx + hw - r
    pts += [(rc + r * math.cos(t), spring - r * math.sin(t)) for t in np.linspace(math.acos((cx - rc) / r), 0, 60)]
    pts += [(cx + hw, spring), (cx + hw, 2048)]
    d.polygon(pts, fill=255)
    # window muntins in the lattice style
    lat = Image.open(os.path.join(TEX, "lattice.png")).resize((1024, 1024)).crop((0, 0, 1024, 1024))
    lat2 = Image.new("L", (1024, 2048), 0)
    lat2.paste(lat, (0, 0))
    lat2.paste(lat, (0, 1024))
    win = np.asarray(im).astype(np.float32) * (1 - np.asarray(lat2).astype(np.float32) / 255 * 0.85)
    Image.fromarray(win.astype(np.uint8)).save(os.path.join(TEX, "window.png"))


# ---------------------------------------------------------------- blender helpers
def mat(name, color, rough=0.5, metal=0.0, coat=0.0, emis=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emis:
        b.inputs["Emission Color"].default_value = (*emis[0], 1)
        b.inputs["Emission Strength"].default_value = emis[1]
    return m


def img_mat(name, path, base=(0, 0, 0), emit=None, strength=0.0, alpha=False, invert=False, rough=0.6,
            line_color=None):
    """material driven by a greyscale mask: mask -> emission (glow) and/or alpha (cut-outs),
    or mask -> base colour mix (inlay lines)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Roughness"].default_value = rough
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = bpy.data.images.load(path)
    tx.image.colorspace_settings.name = "Non-Color"
    out = tx.outputs["Color"]
    if invert:
        inv = nt.nodes.new("ShaderNodeInvert")
        nt.links.new(out, inv.inputs["Color"])
        out = inv.outputs["Color"]
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = strength
        nt.links.new(out, mul.inputs[0])
        nt.links.new(mul.outputs[0], b.inputs["Emission Strength"])
    if line_color:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = (*base, 1)
        mix.inputs["B"].default_value = (*line_color, 1)
        nt.links.new(out, mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        met = nt.nodes.new("ShaderNodeMath")
        met.operation = "MULTIPLY"
        met.inputs[1].default_value = 1.0
        nt.links.new(out, met.inputs[0])
        nt.links.new(met.outputs[0], b.inputs["Metallic"])
    if alpha:
        nt.links.new(out, b.inputs["Alpha"])
        try:
            m.blend_method = "HASHED"
        except Exception:
            pass
    return m


def _unit_cube():
    """one shared cube mesh: thousands of books as linked objects build in seconds, not minutes."""
    me = bpy.data.meshes.get("unitcube")
    if me is None:
        import bmesh
        me = bpy.data.meshes.new("unitcube")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(None)
    return me


def box(name, loc, size, m, rot=(0, 0, 0), bev=0.0):
    o = bpy.data.objects.new(name, _unit_cube())
    bpy.context.collection.objects.link(o)
    o.location, o.rotation_euler, o.scale = loc, rot, size
    o.material_slots[0].link = "OBJECT"
    o.material_slots[0].material = m
    if bev:
        md = o.modifiers.new("bev", "BEVEL")
        md.width, md.segments = bev, 3
    return o


def plane(name, loc, size, m, rot=(math.radians(90), 0, 0)):
    """vertical plane facing the camera by default (size = width, height)."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = (size[0], size[1], 1)
    o.data.materials.append(m)
    return o


def cyl(name, loc, r, depth, m, rot=(0, 0, 0), verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(m)
    return o


def light(kind, loc, energy, color, size=1.0, rot=(0, 0, 0), spot=None):
    ld = bpy.data.lights.new(f"l{len(bpy.data.lights)}", kind)
    ld.energy, ld.color = energy, color
    if kind == "AREA":
        ld.size = size
    elif kind in ("POINT", "SPOT"):
        ld.shadow_soft_size = size
    if spot:
        ld.spot_size, ld.spot_blend = spot
    o = bpy.data.objects.new(ld.name, ld)
    o.location, o.rotation_euler = loc, rot
    bpy.context.collection.objects.link(o)
    return o


def aim(o, target):
    v = mathutils.Vector(target) - o.location
    o.rotation_euler = v.to_track_quat("-Z", "Y").to_euler()


def setup(world_color=(0.02, 0.02, 0.025), world_strength=0.3, focus=None, fstop=4.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("cam")
    cd.lens, cd.sensor_width, cd.sensor_fit = LENS, 36, "HORIZONTAL"
    cd.dof.use_dof = True
    cd.dof.focus_distance = focus or -CAM[1]
    cd.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new("cam", cd)
    cam.location = CAM
    cam.rotation_euler = (math.radians(90 + PITCH), 0, 0)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (*world_color, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = world_strength
    sc.world = w
    # presenter key + fill (the same in every set, matching the face light in the footage)
    k = light("AREA", (-1.4, -1.6, 2.3), 90, (1.0, 0.9, 0.78), size=2.0)
    aim(k, (0, 0, 1.1))
    f = light("AREA", (1.6, -2.2, 1.6), 25, (0.85, 0.9, 1.0), size=2.5)
    aim(f, (0, 0, 1.1))
    return sc


def floor(m):
    plane("floor", (0, 1.5, 0), (14, 10), m, rot=(0, 0, 0))


# ---------------------------------------------------------------- shared furniture
def desk(style):
    """anchor desk in front of the presenter; returns its objects (foreground layer)."""
    objs = []
    if style in ("walnut", "walnut_matte"):
        top = mat("desk_top", (0.09, 0.045, 0.02), rough=0.42 if style == "walnut" else 0.75,
                  coat=0.25 if style == "walnut" else 0.0)
        body = img_mat("desk_body", os.path.join(TEX, "lattice.png"), base=(0.06, 0.03, 0.014), rough=0.35,
                       line_color=(0.30, 0.18, 0.08))
        trim = mat("desk_trim", GOLD, rough=0.25, metal=1.0)
    elif style == "navy":
        top = mat("desk_top", (0.015, 0.03, 0.06), rough=0.18, coat=0.8)
        body = img_mat("desk_body", os.path.join(TEX, "lattice.png"), base=(0.012, 0.03, 0.07), rough=0.35,
                       line_color=GOLD)
        trim = mat("desk_trim", GOLD, rough=0.22, metal=1.0, emis=(GOLD, 2.0))
    else:   # marble
        top = mat("desk_top", (0.86, 0.83, 0.78), rough=0.12, coat=0.5)
        body = mat("desk_body", (0.015, 0.035, 0.075), rough=0.35, coat=0.4)
        trim = mat("desk_trim", GOLD, rough=0.22, metal=1.0)
    y0, y1, w = -0.98, -0.30, 1.9
    objs.append(box("desktop", (0, (y0 + y1) / 2, DESK_TOP - 0.025), (w, y1 - y0, 0.05), top, bev=0.012))
    objs.append(box("deskfront", (0, y0 + 0.06, DESK_TOP / 2 - 0.03), (w - 0.08, 0.06, DESK_TOP - 0.06), body, bev=0.01))
    objs.append(box("trim", (0, y0 + 0.025, DESK_TOP - 0.065), (w - 0.06, 0.012, 0.012), trim))
    objs.append(box("trim2", (0, y0 + 0.025, 0.08), (w - 0.06, 0.012, 0.012), trim))
    return objs


def props(rnd, mic=False, lamp=True):
    """open book on a rehal, a small stack of books, optional brass lamp and podcast mic."""
    objs = []
    paper = mat("paper", (0.93, 0.89, 0.80), rough=0.7)
    cover = mat("cover", (0.30, 0.05, 0.04), rough=0.4, coat=0.3)
    gold = mat("gold", GOLD, rough=0.3, metal=1.0)
    # an open book lying on the desk, front-left, slightly turned
    cx, cy = -0.40, -0.55
    rz = math.radians(8)
    objs.append(box("cover", (cx, cy, DESK_TOP + 0.006), (0.32, 0.22, 0.012), cover, rot=(0, 0, rz), bev=0.003))
    for s_ in (-1, 1):
        objs.append(box("pages", (cx + s_ * 0.078 * math.cos(rz), cy + s_ * 0.078 * math.sin(rz), DESK_TOP + 0.02),
                        (0.148, 0.20, 0.018), paper, rot=(0, math.radians(-s_ * 4), rz), bev=0.004))
    # stack of books, front-right
    x, y, z = 0.40, -0.48, DESK_TOP
    for i in range(3):
        t = rnd.uniform(0.035, 0.055)
        c = mat(f"stack{i}", rnd.choice([(0.05, 0.10, 0.07), (0.25, 0.05, 0.04), (0.04, 0.05, 0.12)]), rough=0.45, coat=0.2)
        objs.append(box("bk", (x, y, z + t / 2), (0.20 - i * 0.02, 0.14 - i * 0.01, t), c,
                        rot=(0, 0, math.radians(rnd.uniform(-8, 8))), bev=0.003))
        objs.append(box("bkband", (x - 0.085 + i * 0.01, y, z + t / 2), (0.008, 0.142 - i * 0.01, t * 0.9), gold,
                        rot=(0, 0, 0)))
        z += t
    if lamp:
        brass = mat("brass", (0.9, 0.62, 0.3), rough=0.25, metal=1.0)
        objs.append(cyl("lampbase", (0.62, -0.32, DESK_TOP + 0.01), 0.07, 0.02, brass))
        objs.append(cyl("lampstem", (0.62, -0.32, DESK_TOP + 0.2), 0.008, 0.38, brass))
        shade = mat("shade", (0.45, 0.32, 0.2), rough=0.7, emis=((1.0, 0.70, 0.40), 0.9))
        bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.085, radius2=0.045, depth=0.11,
                                        location=(0.62, -0.32, DESK_TOP + 0.42))
        o = bpy.context.active_object
        o.data.materials.append(shade)
        objs.append(o)
        light("POINT", (0.62, -0.32, DESK_TOP + 0.38), 10, (1.0, 0.75, 0.45), size=0.05)
    if mic:
        black = mat("mic", (0.008, 0.008, 0.009), rough=0.4, coat=0.2)
        metal = mat("micarm", (0.04, 0.04, 0.045), rough=0.3, metal=0.8)
        head = mathutils.Vector((0.22, -0.40, 1.10))
        mouth = mathutils.Vector((0.0, 0.0, 1.10))
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.032, depth=0.17, location=head)
        b = bpy.context.active_object
        b.rotation_euler = (mouth - head).to_track_quat("Z", "Y").to_euler()
        b.data.materials.append(black)
        objs.append(b)
        base = mathutils.Vector((0.35, -0.55, DESK_TOP))
        mid = mathutils.Vector((0.36, -0.5, 1.02))
        for a_, c_ in ((base, mid), (mid, head)):
            d_ = c_ - a_
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.01, depth=d_.length, location=(a_ + c_) / 2)
            t = bpy.context.active_object
            t.rotation_euler = d_.to_track_quat("Z", "Y").to_euler()
            t.data.materials.append(metal)
            objs.append(t)
    return objs


def bookshelf_wall(rnd, x0, x1, y, h=2.9, z0=0.0, depth=0.32, rows=6):
    walnut = mat("walnut", (0.10, 0.05, 0.022), rough=0.4, coat=0.3)
    back = mat("back", (0.05, 0.03, 0.018), rough=0.6)
    leather = [(0.12, 0.025, 0.02), (0.03, 0.06, 0.045), (0.02, 0.035, 0.07), (0.11, 0.06, 0.03),
               (0.18, 0.12, 0.07), (0.06, 0.03, 0.02), (0.30, 0.25, 0.18), (0.08, 0.02, 0.03)]
    bms = [mat(f"b{i}", c, rough=rnd.uniform(0.35, 0.6), coat=0.15) for i, c in enumerate(leather)]
    gold = mat("gilt", GOLD, rough=0.28, metal=1.0)
    W = x1 - x0
    cx = (x0 + x1) / 2
    box("shback", (cx, y + depth, z0 + h / 2), (W, 0.03, h), back)
    zs = [z0 + 0.1 + i * (h - 0.2) / rows for i in range(rows)]
    for z in zs + [z0 + h - 0.02]:
        box("shelf", (cx, y + depth / 2, z - 0.02), (W, depth, 0.035), walnut, bev=0.004)
    nb = max(2, int(W / 1.1))
    for i in range(nb + 1):
        box("side", (x0 + W * i / nb, y + depth / 2, z0 + h / 2), (0.04, depth, h), walnut, bev=0.004)
    for z in zs[:-1] if rows > 3 else zs:
        x = x0 + 0.03
        while x < x1 - 0.05:
            if rnd.random() < 0.05:
                x += rnd.uniform(0.05, 0.12)
                continue
            t = rnd.uniform(0.022, 0.055)
            hh = rnd.uniform(0.22, (h - 0.2) / rows - 0.05)
            dd = rnd.uniform(0.17, 0.24)
            box("book", (x + t / 2, y + 0.02 + dd / 2, z + hh / 2), (t, dd, hh), rnd.choice(bms))
            if rnd.random() < 0.6:
                for fr in rnd.choice([(0.18, 0.82), (0.5,), (0.15, 0.85)]):
                    box("band", (x + t / 2, y + 0.018, z + hh * fr), (t * 0.9, 0.004, 0.006), gold)
            x += t + rnd.uniform(0, 0.004)


# ---------------------------------------------------------------- the five sets
def set_library(rnd):
    """grand scholar's library: floor-to-ceiling walnut shelves, a lit arched niche with a lattice
    screen behind the presenter, warm practical lamps."""
    sc = setup(world_color=(0.03, 0.02, 0.015), world_strength=0.2, fstop=1.8)
    floor(mat("floor", (0.05, 0.03, 0.02), rough=0.3, coat=0.4))
    Y = 2.3
    bookshelf_wall(rnd, -3.4, -0.75, Y, h=3.1)
    bookshelf_wall(rnd, 0.75, 3.4, Y, h=3.1)
    # arched niche in the middle: dark recess + glowing lattice
    niche = img_mat("niche", os.path.join(TEX, "arches.png"), base=(0.06, 0.035, 0.02), alpha=False)
    wall = mat("wall", (0.08, 0.05, 0.03), rough=0.6)
    box("pillarL", (-0.72, Y + 0.15, 1.55), (0.12, 0.35, 3.1), wall)
    box("pillarR", (0.72, Y + 0.15, 1.55), (0.12, 0.35, 3.1), wall)
    glow = img_mat("glowscreen", os.path.join(TEX, "mashrabiya.png"), base=(0.04, 0.022, 0.01),
                   emit=(1.0, 0.62, 0.30), strength=0.35, invert=True)
    plane("screen", (0, Y + 0.45, 1.6), (1.35, 3.0), glow)
    light("AREA", (0, Y + 0.2, 3.0), 120, (1.0, 0.75, 0.45), size=1.2, rot=(0, 0, 0))
    for x in (-2.0, 2.0):
        light("POINT", (x, Y - 0.3, 2.4), 60, (1.0, 0.72, 0.42), size=0.1)
    return sc, "walnut", dict(mic=False, lamp=True)


def set_broadcast(rnd):
    """modern broadcast / podcast studio (Al Jazeera, Thmanyah style): navy acoustic walls, vertical
    wood slats, a large backlit geometric wall, LED lines, podcast mic on the desk."""
    sc = setup(world_color=(0.01, 0.015, 0.03), world_strength=0.25, fstop=1.8)
    floor(mat("floor", (0.01, 0.012, 0.02), rough=0.15, coat=0.6))
    Y = 2.6
    navy = mat("navy", NAVY, rough=0.7)
    box("backwall", (0, Y + 0.3, 1.8), (9, 0.1, 3.6), navy)
    panel = img_mat("panel", os.path.join(TEX, "lattice_fine.png"), base=(0.01, 0.02, 0.05),
                    emit=(0.35, 0.55, 0.95), strength=1.6)
    plane("geo", (0, Y + 0.24, 1.75), (2.6, 2.6), panel)
    wood = mat("slat", (0.18, 0.10, 0.05), rough=0.45, coat=0.2)
    for i in range(16):
        for s in (-1, 1):
            box("slat", (s * (1.65 + i * 0.12), Y + 0.15, 1.8), (0.05, 0.08, 3.6), wood)
    led = mat("led", (1, 1, 1), emis=(GOLD, 12.0))
    for s in (-1, 1):
        box("ledv", (s * 1.42, Y + 0.2, 1.75), (0.018, 0.02, 2.7), led)
    box("ledh", (0, Y + 0.2, 3.15), (2.86, 0.02, 0.018), led)
    box("ledh2", (0, Y + 0.2, 0.36), (2.86, 0.02, 0.018), led)
    return sc, "navy", dict(mic=True, lamp=False)


def set_arches(rnd):
    """Andalusian arcade: a row of pointed arches with warm light behind, columns, marble floor."""
    sc = setup(world_color=(0.9, 0.7, 0.45), world_strength=0.12, fstop=1.8)
    sc["exposure"] = -1.3
    floor(mat("marble", (0.55, 0.50, 0.45), rough=0.15, coat=0.6))
    Y = 2.4
    wallm = img_mat("arcade", os.path.join(TEX, "arches.png"), base=(0.42, 0.33, 0.24), alpha=True,
                    invert=True, rough=0.7)
    plane("arcade", (0, Y, 0.95), (6.0, 1.9), wallm)
    plane("arcade_top", (0, Y, 2.6), (6.0, 1.4), img_mat("lintel", os.path.join(TEX, "lattice_fine.png"),
          base=(0.40, 0.31, 0.22), rough=0.7, line_color=(0.62, 0.46, 0.26)))
    plane("arcade2", (0.75, Y + 1.8, 1.15), (7.4, 2.3), wallm)
    # light beyond the arches (courtyard sun)
    glow = mat("courtyard", (1, 1, 1), emis=((1.0, 0.74, 0.45), 0.55))
    plane("sky", (0, Y + 4.0, 2.2), (14, 6), glow)
    light("SUN", (0, 10, 6), 2.0, (1.0, 0.85, 0.65), rot=(math.radians(-60), 0, 0))
    for x in (-1.8, -0.6, 0.6, 1.8):
        cyl("col", (x, Y - 0.12, 0.62), 0.05, 1.24, mat("colm", (0.85, 0.82, 0.76), rough=0.2, coat=0.4))
    return sc, "marble", dict(mic=False, lamp=False)


def set_brand(rnd):
    """minimal brand studio: navy wall with a large backlit gold rosette, short shelves either side."""
    sc = setup(world_color=(0.01, 0.015, 0.03), world_strength=0.2, fstop=1.8)
    floor(mat("floor", (0.012, 0.02, 0.04), rough=0.2, coat=0.5))
    Y = 2.4
    box("wall", (0, Y + 0.3, 1.8), (9, 0.1, 3.6), mat("navywall", NAVY, rough=0.75))
    ros = img_mat("rosette", os.path.join(TEX, "rosette.png"), base=NAVY, emit=(1.0, 0.62, 0.22), strength=0.55)
    plane("rosette", (0, Y + 0.24, 1.75), (2.4, 2.4), ros)
    bookshelf_wall(rnd, -3.3, -1.7, Y - 0.1, h=2.2, rows=4)
    bookshelf_wall(rnd, 1.7, 3.3, Y - 0.1, h=2.2, rows=4)
    light("AREA", (0, Y - 0.6, 3.2), 80, GOLD, size=3.0, rot=(math.radians(20), 0, 0))
    return sc, "marble", dict(mic=False, lamp=True)


def set_manuscript(rnd):
    """old scholar's study: tall arched window with daylight and a lattice, wooden shelves with
    manuscripts, a hanging lantern."""
    sc = setup(world_color=(0.04, 0.03, 0.02), world_strength=0.2, fstop=1.8)
    floor(mat("floor", (0.07, 0.045, 0.025), rough=0.35, coat=0.3))
    Y = 2.3
    plaster = mat("plaster", (0.55, 0.45, 0.33), rough=0.85)
    win = img_mat("window", os.path.join(TEX, "window.png"), base=(0.5, 0.42, 0.32), emit=(1.0, 0.80, 0.55),
                  strength=0.9)
    box("wall", (0, Y + 0.32, 1.9), (9, 0.1, 3.8), plaster)
    plane("win", (0, Y + 0.26, 1.75), (1.3, 2.6), win)
    light("AREA", (0, Y + 0.1, 1.9), 110, (1.0, 0.86, 0.66), size=1.2, rot=(math.radians(-90), 0, 0))
    bookshelf_wall(rnd, -3.4, -1.0, Y - 0.05, h=2.8, rows=5)
    bookshelf_wall(rnd, 1.0, 3.4, Y - 0.05, h=2.8, rows=5)
    brass = mat("lantern", (0.9, 0.6, 0.28), rough=0.3, metal=1.0, emis=((1.0, 0.7, 0.35), 3.0))
    for x in (-1.6, 1.6):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.09, depth=0.28, location=(x, Y - 0.5, 2.35))
        bpy.context.active_object.data.materials.append(brass)
        light("POINT", (x, Y - 0.5, 2.35), 35, (1.0, 0.7, 0.35), size=0.06)
    return sc, "walnut_matte", dict(mic=False, lamp=False)


SETS = {"library": set_library, "broadcast": set_broadcast, "arches": set_arches,
        "brand": set_brand, "manuscript": set_manuscript}


def render(sc, path, preview, transparent):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16 if preview else 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = 50 if preview else 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = sc.get("exposure", -0.9)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("wrote", path)


def build(name, with_fg_only):
    rnd = random.Random(11)
    sc, style, pr = SETS[name](rnd)
    room = set(bpy.data.objects)
    fg = desk(style) + props(random.Random(5), **pr)
    if with_fg_only:
        for o in room:
            if o.type == "MESH":
                o.visible_camera = False
    else:
        for o in fg:
            o.hide_render = True
    return sc


def save_meta(sc, name):
    """where the presenter's eyes land and how many pixels a metre is at the presenter (for compositing)."""
    import json
    from bpy_extras.object_utils import world_to_camera_view
    cam = sc.camera
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
    def px(p):
        v = world_to_camera_view(sc, cam, mathutils.Vector(p))
        return v.x * 1920, (1 - v.y) * 1080
    eye = px((0, 0, 1.22))
    one = px((1.0, 0, 1.22))
    desk_back = px((0, -0.30, DESK_TOP))
    meta = {"eye_x": eye[0], "eye_y": eye[1], "ppm": one[0] - eye[0], "desk_back_y": desk_back[1]}
    with open(os.path.join(OUT, f"{name}_meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(name, meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--only", default=",".join(SETS))
    a = ap.parse_args(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    textures()
    for name in a.only.split(","):
        sc = build(name, False)
        save_meta(sc, name)
        render(sc, os.path.join(OUT, f"{name}_bg.png"), a.preview, False)
        sc = build(name, True)
        render(sc, os.path.join(OUT, f"{name}_fg.png"), a.preview, True)


if __name__ == "__main__":
    main()
