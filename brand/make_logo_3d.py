"""Real 3D logo for Zabeehullah Leghari, rendered with Blender (pip `bpy`) + Cycles.

Urdu text is shaped with HarfBuzz (proper Nastaliq joining), its glyph outlines are
extruded into bevelled gold metal; the emblem is an Islamic 8-point star medallion.

  python3 brand/make_logo_3d.py [--preview] [--transparent] [--out PATH]
"""
import argparse
import math
import os
import sys

import bpy
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", ".claude", "skills", "dai-video-editor", "assets", "fonts")
NASTALIQ = os.path.join(FONTS, "NotoNastaliqUrdu-Bold.ttf")
AMIRI = os.path.join(FONTS, "Amiri-Bold.ttf")
POPPINS = os.path.join(FONTS, "Poppins-SemiBold.ttf")

UR = "ذبیح اللہ لغاری"
EN = "ZABEEHULLAH  LEGHARI"


# --------------------------------------------------------------------------- text -> contours
class FlatPen(BasePen):
    """Collects glyph outlines as flattened polylines."""

    def __init__(self, glyphset, dx, dy, steps=10):
        super().__init__(glyphset)
        self.dx, self.dy, self.steps = dx, dy, steps
        self.contours, self.cur = [], []

    def _p(self, pt):
        return (pt[0] + self.dx, pt[1] + self.dy)

    def _moveTo(self, pt):
        self.cur = [self._p(pt)]

    def _lineTo(self, pt):
        self.cur.append(self._p(pt))

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        a, b, c = self._p(p1), self._p(p2), self._p(p3)
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * a[0] + 3 * mt * t * t * b[0] + t ** 3 * c[0],
                             mt ** 3 * p0[1] + 3 * mt * mt * t * a[1] + 3 * mt * t * t * b[1] + t ** 3 * c[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        a, b = self._p(p1), self._p(p2)
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * a[0] + t * t * b[0],
                             mt * mt * p0[1] + 2 * mt * t * a[1] + t * t * b[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def shaped_contours(text, font_path, letter_spacing=0):
    blob = hb.Blob.from_file_path(font_path)
    font = hb.Font(hb.Face(blob))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    tt = TTFont(font_path)
    gs, order = tt.getGlyphSet(), tt.getGlyphOrder()
    upem = tt["head"].unitsPerEm
    x, contours = 0, []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = FlatPen(gs, x + pos.x_offset, pos.y_offset)
        gs[order[info.codepoint]].draw(pen)
        contours += pen.contours
        x += pos.x_advance + letter_spacing
    return [[(px / upem, py / upem) for px, py in c] for c in contours]


# --------------------------------------------------------------------------- blender helpers
def material(name, color, metallic=0.0, rough=0.4, emission=None, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = (*emission[0], 1)
        b.inputs["Emission Strength"].default_value = emission[1]
    return m


def curve_from_contours(name, contours, depth, bevel, mat, width=None, height=None, center=(0, 0), z=0.0):
    xs = [p[0] for c in contours for p in c]
    ys = [p[1] for c in contours for p in c]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    s = 1.0
    if width:
        s = width / (maxx - minx)
    if height:
        s = min(s, height / (maxy - miny)) if width else height / (maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    for c in contours:
        sp = cu.splines.new("POLY")
        sp.points.add(len(c) - 1)
        for i, (px, py) in enumerate(c):
            sp.points[i].co = ((px - cx) * s + center[0], (py - cy) * s + center[1], 0, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    ob.location.z = z
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob, (maxx - minx) * s, (maxy - miny) * s


def star_points(r_out, n=8, inner_ratio=0.765, rot=math.pi / 2):
    pts = []
    for i in range(2 * n):
        ang = rot + i * math.pi / n
        r = r_out if i % 2 == 0 else r_out * inner_ratio
        pts.append((r * math.cos(ang), r * math.sin(ang)))
    return pts


def circle_pts(r, n=180):
    return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def tube(name, pts, radius, mat, z=0.0, cyclic=True):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, (x, y) in enumerate(pts):
        sp.points[i].co = (x, y, 0, 1)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    ob.location.z = z
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def area_light(name, loc, rot, size, energy, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = energy
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.collection.objects.link(ob)
    return ob


def softbox(name, loc, rot, sx, sy, strength):
    """visible-to-reflections emissive card (gives gold its bright streaks)"""
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (sx, sy, 1)
    m = material(name + "_m", (0, 0, 0), emission=((1.0, 0.95, 0.85), strength))
    ob.data.materials.append(m)
    ob.visible_camera = False
    return ob


# --------------------------------------------------------------------------- scene
def build(transparent):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene

    gold = material("gold", (1.0, 0.60, 0.16), metallic=1.0, rough=0.20)
    gold_brushed = material("gold_soft", (0.95, 0.58, 0.18), metallic=1.0, rough=0.34)
    cream = material("cream", (1.0, 0.80, 0.50), metallic=1.0, rough=0.28)
    navy = material("navy", (0.001, 0.006, 0.013), metallic=0.0, rough=0.55)
    back = material("backdrop", (0.0025, 0.008, 0.013), rough=0.8)

    # --- medallion
    EY = 1.15  # emblem centre height
    bpy.ops.mesh.primitive_cylinder_add(vertices=256, radius=1.0, depth=0.10, location=(0, EY, -0.05))
    disc = bpy.context.active_object
    disc.data.materials.append(navy)
    bpy.ops.object.shade_smooth()
    tube("ring_outer", [(x, y + EY) for x, y in circle_pts(1.0)], 0.045, gold, z=0.0)
    tube("ring_inner", [(x, y + EY) for x, y in circle_pts(0.90)], 0.012, gold_brushed, z=0.01)
    for i in range(48):
        a = 2 * math.pi * i / 48
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=(0.95 * math.cos(a), EY + 0.95 * math.sin(a), 0.01))
        bpy.context.active_object.data.materials.append(gold)
    # 16-fold rosette (thin gold lines)
    R = 0.84
    pts = [(R * math.cos(2 * math.pi * i / 16 + math.pi / 2), R * math.sin(2 * math.pi * i / 16 + math.pi / 2)) for i in range(16)]
    for i in range(16):
        a, b = pts[i], pts[(i + 5) % 16]
        tube(f"ros{i}", [(a[0], a[1] + EY), (b[0], b[1] + EY)], 0.004, gold_brushed, z=0.0, cyclic=False)
    # raised 8-point star frame (outer star minus inner star) + inner navy star
    outer = [(x, y + EY) for x, y in star_points(0.80)]
    inner = [(x, y + EY) for x, y in star_points(0.70)]
    curve_from_contours("star_frame", [outer, inner[::-1]], 0.05, 0.012, gold, width=1.60, center=(0, EY), z=0.04)
    curve_from_contours("star_fill", [inner], 0.02, 0.0, navy, width=1.40 * 1.0, center=(0, EY), z=0.03)
    tube("star_inner_line", [(x, y + EY) for x, y in star_points(0.62)], 0.006, gold_brushed, z=0.06)
    tube("centre_ring", [(x, y + EY) for x, y in circle_pts(0.46)], 0.007, gold_brushed, z=0.06)
    # monogram ذ
    mono = shaped_contours("ذ", AMIRI)
    curve_from_contours("monogram", mono, 0.06, 0.010, gold, height=0.55, center=(0, EY + 0.02), z=0.08)

    # --- names
    ur = shaped_contours(UR, NASTALIQ)
    curve_from_contours("name_ur", ur, 0.09, 0.012, gold, width=2.55, center=(0, -0.62), z=0.0)
    # thin rule with diamond
    tube("rule_l", [(-1.25, -1.30), (-0.10, -1.30)], 0.006, gold_brushed, cyclic=False)
    tube("rule_r", [(0.10, -1.30), (1.25, -1.30)], 0.006, gold_brushed, cyclic=False)
    curve_from_contours("diamond", [[(0, 0.07), (0.07, 0), (0, -0.07), (-0.07, 0)]], 0.02, 0.004, gold,
                        width=0.14, center=(0, -1.30), z=0.0)
    en = shaped_contours(EN, POPPINS, letter_spacing=180)
    curve_from_contours("name_en", en, 0.035, 0.005, cream, width=2.45, center=(0, -1.62), z=0.0)

    # --- backdrop, lights, camera
    if not transparent:
        bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.35))
        bd = bpy.context.active_object
        # unlit radial navy gradient, brighter teal-navy behind the medallion
        mt = bpy.data.materials.new("bg_grad")
        mt.use_nodes = True
        nt = mt.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (0, -1.15 * 0.2, 0)
        mp.inputs["Scale"].default_value = (0.2, 0.2, 1)
        gr = nt.nodes.new("ShaderNodeTexGradient")
        gr.gradient_type = "SPHERICAL"
        cr = nt.nodes.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (0.002, 0.007, 0.012, 1)
        cr.color_ramp.elements[1].color = (0.016, 0.085, 0.120, 1)
        cr.color_ramp.elements[1].position = 0.9
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], gr.inputs["Vector"])
        nt.links.new(gr.outputs["Color"], cr.inputs["Fac"])
        nt.links.new(cr.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        bd.data.materials.append(mt)
    area_light("key", (-3.5, 3.5, 5.0), (math.radians(-35), math.radians(-35), 0), 4.0, 650, (1.0, 0.90, 0.75))
    area_light("fill", (4.0, -1.0, 4.0), (math.radians(15), math.radians(40), 0), 5.0, 160, (0.85, 0.92, 1.0))
    area_light("rim", (0, 4.5, 1.2), (math.radians(-75), 0, 0), 6.0, 500, (1.0, 0.88, 0.70))
    # soft teal halo on the backdrop behind the medallion
    pl = bpy.data.lights.new("halo", "POINT")
    pl.energy, pl.color, pl.shadow_soft_size = 120, (0.20, 0.55, 0.62), 1.5
    po = bpy.data.objects.new("halo", pl)
    po.location = (0, 1.15, -0.22)
    bpy.context.collection.objects.link(po)
    softbox("sb_top", (0, 2.0, 6.0), (math.radians(-15), 0, 0), 9, 3, 6.0)
    softbox("sb_left", (-6, 0, 3), (0, math.radians(-60), 0), 3, 8, 4.0)
    softbox("sb_right", (6, 0, 3), (0, math.radians(60), 0), 3, 8, 3.0)
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.035, 0.045, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.12
    sc.world = world

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 85
    cam = bpy.data.objects.new("cam", cam_d)
    cam.location = (0, -2.2, 14.0)
    cam.rotation_euler = (math.radians(9.5), 0, 0)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    return sc


def render(sc, out, preview, transparent):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if preview else 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 2000
    sc.render.resolution_percentage = 40 if preview else 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - High Contrast"
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--transparent", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "logo", "logo_3d.png"))
    a = ap.parse_args(sys.argv[1:])
    s = build(a.transparent)
    render(s, os.path.abspath(a.out), a.preview, a.transparent)
