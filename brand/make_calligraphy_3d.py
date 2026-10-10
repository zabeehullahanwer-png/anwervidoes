"""3D teardrop calligraphy logo: polished gold letters mounted off a dark marble wall,
lit by a top spotlight (Blender/Cycles via pip `bpy`).

  python3 brand/make_calligraphy_3d.py [--preview] [--view angled|front] [--out PATH]
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calligraphy_layout import composition  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def principled(name, color, metallic=0.0, rough=0.4):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    return m


def marble():
    m = bpy.data.materials.new("marble")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.32
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.9
    noise.inputs["Detail"].default_value = 12
    noise.inputs["Distortion"].default_value = 3.5
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 0.22
    wave.inputs["Distortion"].default_value = 9.0
    wave.inputs["Detail"].default_value = 8
    wave.inputs["Detail Roughness"].default_value = 0.7
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.13, 0.13, 0.135, 1)   # thin grey veins
    ramp.color_ramp.elements[1].position = 0.025
    ramp.color_ramp.elements[1].color = (0.018, 0.018, 0.020, 1)  # near-black stone
    mix_n = nt.nodes.new("ShaderNodeMix")
    mix_n.data_type = "VECTOR"
    mix_n.inputs["Factor"].default_value = 0.35
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], mix_n.inputs[4])
    nt.links.new(noise.outputs["Color"], mix_n.inputs[5])
    nt.links.new(mix_n.outputs[1], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def extrude(name, contours, depth, bevel, mat, z):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = 5
    for c in contours:
        sp = cu.splines.new("POLY")
        sp.points.add(len(c) - 1)
        for i, (x, y) in enumerate(c):
            sp.points[i].co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    ob.location.z = z
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def build(view):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    gold = principled("gold", (1.0, 0.62, 0.20), metallic=1.0, rough=0.16)

    # wall
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(marble())

    # letters: each element separately so overlaps stay solid; 12 cm stand-off from the wall
    for name, cs in composition().items():
        thin = name.startswith("swoosh") or name.startswith("dot")
        extrude(name, cs, 0.045 if thin else 0.06, 0.006, gold, 0.16)

    # lighting: top spotlight (visible pool + downward shadows), soft fill, reflection cards
    sp = bpy.data.lights.new("spot", "SPOT")
    sp.energy = 1700
    sp.spot_size = math.radians(70)
    sp.spot_blend = 0.75
    sp.shadow_soft_size = 0.35
    sp.color = (1.0, 0.93, 0.82)
    so = bpy.data.objects.new("spot", sp)
    so.location = (0.0, 3.6, 5.2)
    bpy.context.collection.objects.link(so)
    tgt = bpy.data.objects.new("target", None)
    tgt.location = (0, 0.1, 0)
    bpy.context.collection.objects.link(tgt)
    c = so.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"

    fill = bpy.data.lights.new("fill", "AREA")
    fill.size, fill.energy, fill.color = 6, 90, (0.85, 0.9, 1.0)
    fo = bpy.data.objects.new("fill", fill)
    fo.location = (-3, -4, 6)
    fo.rotation_euler = (math.radians(35), math.radians(-25), 0)
    bpy.context.collection.objects.link(fo)

    for nm, loc, rot, sx, sy, st in [("card_top", (0, 3, 7), (math.radians(-25), 0, 0), 6, 1.5, 8.0),
                                     ("card_left", (-5, 0.5, 4), (0, math.radians(-55), 0), 1.5, 5, 3.0),
                                     ("card_right", (5, 0.5, 4), (0, math.radians(55), 0), 1.5, 5, 2.0),
                                     ("card_front", (-1.0, 1.2, 15), (0, 0, 0), 9, 9, 1.6)]:
        bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
        ob = bpy.context.active_object
        ob.scale = (sx, sy, 1)
        m = bpy.data.materials.new(nm)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.95, 0.88, 1)
        bsdf.inputs["Emission Strength"].default_value = st
        ob.data.materials.append(m)
        ob.visible_camera = False
        ob.visible_shadow = False
        ob.visible_diffuse = False  # only shows up in the gold's reflections, never lights the wall

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.01, 0.012, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.3
    sc.world = world

    cd = bpy.data.cameras.new("cam")
    cd.lens = 60
    cam = bpy.data.objects.new("cam", cd)
    if view == "angled":   # seen from the left, like a sign photographed on a wall
        cam.location = (-2.75, 0.25, 8.3)
        cam.rotation_euler = (0, math.radians(-18.3), 0)
    else:
        cam.location = (0.0, 0.25, 8.7)
        cam.rotation_euler = (0, 0, 0)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    return sc


def render(sc, out, preview):
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if preview else 128
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 2000
    sc.render.resolution_percentage = 40 if preview else 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - High Contrast"
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--view", choices=["angled", "front"], default="angled")
    ap.add_argument("--out", default=os.path.join(HERE, "logo", "logo_calligraphy_3d.png"))
    a = ap.parse_args(sys.argv[1:])
    render(build(a.view), os.path.abspath(a.out), a.preview)
