"""Scholar's study plates for portrait compositing (Blender/Cycles via pip `bpy`).

Renders, from one portrait camera (135 mm, f/2, focused on the sitter at 3 m):
  study_bg.png   walnut bookshelves full of leather/cloth-bound books with gilded spines,
                 warm lamp light, strong natural lens blur (subject itself not rendered)
  study_mic.png  transparent foreground layer: broadcast dynamic mic on a boom arm

  python3 brand/make_study_scene.py [--preview]
"""
import argparse
import math
import os
import random
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "profile", "plates")
CAM_Z = 1.17          # camera height (subject eye line ≈ 1.25 m, seated)
SUBJECT_DIST = 3.0    # focus distance


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


def box(name, loc, size, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    o.data.materials.append(m)
    return o


def bevel(o, w=0.004):
    mod = o.modifiers.new("bev", "BEVEL")
    mod.width = w
    mod.segments = 2


def shelves(rnd):
    walnut = mat("walnut", (0.11, 0.055, 0.025), rough=0.42, coat=0.3)
    back = mat("backboard", (0.06, 0.035, 0.02), rough=0.6)
    leather = [(0.23, 0.04, 0.03), (0.05, 0.12, 0.08), (0.04, 0.06, 0.13), (0.20, 0.11, 0.05),
               (0.32, 0.22, 0.12), (0.10, 0.05, 0.03), (0.55, 0.47, 0.34), (0.14, 0.03, 0.05),
               (0.03, 0.09, 0.07), (0.40, 0.30, 0.18)]
    book_mats = [mat(f"book{i}", c, rough=rnd.uniform(0.35, 0.65), coat=0.15) for i, c in enumerate(leather)]
    gold = mat("gilt", (1.0, 0.70, 0.32), rough=0.28, metal=1.0)
    Y = 1.85                      # shelf front face (subject at y=0, camera at y=-3)
    W, H, D = 3.6, 2.6, 0.34
    box("back", (0, Y + D, H / 2), (W + 0.4, 0.04, H + 0.2), back)
    rows = [0.18, 0.62, 1.06, 1.50, 1.94, 2.38]
    for z in rows + [H]:
        b = box(f"shelf{z}", (0, Y + D / 2, z - 0.02), (W, D, 0.035), walnut)
        bevel(b)
    for x in (-W / 2, -0.6, 0.6, W / 2):
        b = box(f"side{x}", (x, Y + D / 2, H / 2), (0.045, D, H), walnut)
        bevel(b)
    # books
    for zi, z in enumerate(rows):
        for bay in ((-W / 2 + 0.03, -0.63), (-0.57, 0.57), (0.63, W / 2 - 0.03)):
            x = bay[0]
            while x < bay[1] - 0.03:
                if rnd.random() < 0.06:          # a small gap or a horizontal stack
                    if rnd.random() < 0.5:
                        x += rnd.uniform(0.04, 0.10)
                        continue
                    sw, sh = rnd.uniform(0.18, 0.24), 0.0
                    for k in range(rnd.randint(2, 5)):
                        t = rnd.uniform(0.025, 0.05)
                        box("hb", (x + sw / 2, Y + 0.12, z + sh + t / 2), (sw, rnd.uniform(0.16, 0.22), t),
                            rnd.choice(book_mats))
                        sh += t
                    x += sw + 0.01
                    continue
                t = rnd.uniform(0.022, 0.06)
                h = rnd.uniform(0.24, 0.36) if zi < 5 else rnd.uniform(0.22, 0.30)
                d = rnd.uniform(0.17, 0.24)
                lean = math.radians(rnd.uniform(-2, 2)) if rnd.random() < 0.15 else 0
                bm = rnd.choice(book_mats)
                bk = box("book", (x + t / 2, Y + 0.02 + d / 2, z + h / 2), (t, d, h), bm, rot=(0, lean, 0))
                bevel(bk, 0.002)
                # gilded bands on the spine (classic Arabic/Urdu kitab bindings)
                if rnd.random() < 0.65:
                    for frac in rnd.choice([(0.18, 0.82), (0.15, 0.3, 0.7, 0.85), (0.5,), (0.2, 0.8)]):
                        box("band", (x + t / 2, Y + 0.02 - 0.0015, z + h * frac), (t * 0.92, 0.004, 0.006), gold,
                            rot=(0, lean, 0))
                x += t + rnd.uniform(0.0, 0.004)
    # a warm desk lamp glow at the side of the shelf
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=(1.25, Y - 0.35, 1.30))
    lamp = bpy.context.active_object
    lamp.data.materials.append(mat("lampshade", (1, 0.8, 0.5), emis=((1.0, 0.72, 0.38), 25)))
    pl = bpy.data.lights.new("lamp", "POINT")
    pl.energy, pl.color, pl.shadow_soft_size = 90, (1.0, 0.68, 0.38), 0.15
    po = bpy.data.objects.new("lamp", pl)
    po.location = (1.25, Y - 0.35, 1.30)
    bpy.context.collection.objects.link(po)


def microphone():
    """broadcast dynamic mic (SM7B-like silhouette) on a boom arm, aimed at the mouth."""
    black = mat("mic_black", (0.006, 0.006, 0.007), rough=0.45, coat=0.25)
    foam = mat("foam", (0.004, 0.004, 0.005), rough=1.0)
    metal = mat("arm", (0.03, 0.03, 0.035), rough=0.3, metal=0.8)
    chrome = mat("chrome", (0.6, 0.6, 0.62), rough=0.18, metal=1.0)
    mouth = (0.0, 0.0, 1.08)
    head = (0.17, -0.22, 0.93)
    coll = bpy.data.collections.new("mic")
    bpy.context.scene.collection.children.link(coll)
    objs = []
    # body: rounded cylinder + foam windscreen in front
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.031, depth=0.15)
    body = bpy.context.active_object
    body.data.materials.append(black)
    bevel(body, 0.008)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.036)
    fs = bpy.context.active_object
    fs.scale = (1, 1, 1.35)
    fs.location = (0, 0, 0.095)
    fs.data.materials.append(foam)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.032, minor_radius=0.003, location=(0, 0, 0.055))
    ring = bpy.context.active_object
    ring.data.materials.append(chrome)
    # yoke
    bpy.ops.mesh.primitive_torus_add(major_radius=0.045, minor_radius=0.006, location=(0, 0, -0.02),
                                     rotation=(0, math.radians(90), 0))
    yoke = bpy.context.active_object
    yoke.scale = (1, 1, 0.6)
    yoke.data.materials.append(metal)
    parts = [body, fs, ring, yoke]
    for p in parts:
        for c in p.users_collection:
            c.objects.unlink(p)
        coll.objects.link(p)
    piv = bpy.data.objects.new("mic_pivot", None)
    coll.objects.link(piv)
    for p in parts:
        p.parent = piv
    piv.location = head
    # aim the mic's +Z axis at the mouth
    import mathutils
    v = mathutils.Vector(mouth) - mathutils.Vector(head)
    piv.rotation_euler = v.to_track_quat("Z", "Y").to_euler()
    # boom arm: two tubes out of frame to the lower right
    def tube(a, b, r):
        a, b = mathutils.Vector(a), mathutils.Vector(b)
        d = b - a
        bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=r, depth=d.length, location=(a + b) / 2)
        t = bpy.context.active_object
        t.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        t.data.materials.append(metal)
        for c in t.users_collection:
            c.objects.unlink(t)
        coll.objects.link(t)
        return t
    back_pt = (head[0] + 0.03, head[1] + 0.05, head[2] - 0.08)
    elbow = (0.62, -0.05, 0.55)
    tube(back_pt, elbow, 0.011)
    tube(elbow, (1.4, 0.3, 0.9), 0.011)
    tube((back_pt[0] + 0.01, back_pt[1], back_pt[2]), (elbow[0] + 0.01, elbow[1], elbow[2] + 0.02), 0.004)
    objs.append(coll)
    return coll


def camera_and_world():
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("cam")
    cd.lens = 135
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.dof.focus_distance = SUBJECT_DIST
    cd.dof.aperture_fstop = 1.6
    cam = bpy.data.objects.new("cam", cd)
    cam.location = (0, -SUBJECT_DIST, CAM_Z)
    cam.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.035, 0.025, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.15
    sc.world = w
    # soft warm key from front-left (matches the face lighting in the portrait)
    key = bpy.data.lights.new("key", "AREA")
    key.size, key.energy, key.color = 2.5, 260, (1.0, 0.85, 0.66)
    ko = bpy.data.objects.new("key", key)
    ko.location = (-1.6, -1.2, 2.6)
    ko.rotation_euler = (math.radians(50), math.radians(-35), 0)
    bpy.context.collection.objects.link(ko)
    fill = bpy.data.lights.new("fill", "AREA")
    fill.size, fill.energy, fill.color = 3, 50, (0.85, 0.9, 1.0)
    fo = bpy.data.objects.new("fill", fill)
    fo.location = (1.8, -2.5, 1.8)
    fo.rotation_euler = (math.radians(75), math.radians(40), 0)
    bpy.context.collection.objects.link(fo)
    return sc


def render(sc, path, preview, transparent):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if preview else 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 1800
    sc.render.resolution_percentage = 40 if preview else 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = -0.6
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args(sys.argv[1:])
    os.makedirs(OUT, exist_ok=True)
    rnd = random.Random(7)

    # 1) background plate
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = camera_and_world()
    shelves(rnd)
    render(sc, os.path.join(OUT, "study_bg.png"), a.preview, False)

    # 2) microphone layer (same camera & lights, transparent; shelves hidden but kept for reflections)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = camera_and_world()
    shelves(random.Random(7))
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.visible_camera = False
    microphone()
    for o in bpy.data.collections["mic"].all_objects:
        o.visible_camera = True
    render(sc, os.path.join(OUT, "study_mic.png"), a.preview, True)


if __name__ == "__main__":
    main()
