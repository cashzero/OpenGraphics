"""g1 的標題 logo（ROADMAP M4）：立體字 + 選用的蒸汽機車與鐵軌，正面略俯視的透視相機，透明背景。

  blender -b --factory-startup --python tools/blender/logo_rig.py -- --spec build/render/g1_logo/spec.json --out build/render/g1_logo

spec.json（由 tools/gen/g1_logo.py 產生）：
  {"font": 字型檔, "shots": [{"name": 檔名, "size": [w, h], "text": 字, "sub": 副標或 null, "text_z": 字的高度,
                              "train": [[幾何指令…], [幾何指令…]] 或 null, "ortho": 相機正交寬度}]}
幾何指令同 tools/blender/models/ops.py（unit = m）。
"""
import argparse
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "models"))
import kit  # noqa: E402
import ops  # noqa: E402


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._materials.clear()                                    # 重設場景後舊材質已失效


def text_obj(body, font, size, z, mats, extrude=0.12, name="text"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = font
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = 0.018
    cu.bevel_resolution = 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (math.radians(90), 0, 0)              # 字面朝 −Y（相機在 −Y）
    ob.location = (0, 0, z)
    for m in mats:
        ob.data.materials.append(m)
    return ob


def shot(spec, s, out):
    clear()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    w, h = s["size"]
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("World")
    world.color = (0.08, 0.08, 0.09)
    scene.world = world
    font = bpy.data.fonts.load(spec["font"])

    face = kit.material("logo_face", (0.95, 0.55, 0.06), rough=0.35, metal=0.3)
    text_obj(s["text"], font, s.get("text_size", 1.0), s.get("text_z", 0.6), [face], extrude=s.get("extrude", 0.14))
    if s.get("sub"):
        subm = kit.material("logo_sub", (0.85, 0.86, 0.88), rough=0.5)
        text_obj(s["sub"], font, s.get("sub_size", 0.32), s.get("sub_z", 0.0), [subm], extrude=0.04, name="sub")

    if s.get("train"):
        # logo 不會套公司色：公司色材質換成固定的深綠車身與暗紅飾帶
        ops.MATS["company"] = ((0.03, 0.16, 0.07), 0.45, 0.1, 0.1)
        ops.MATS["company2"] = ((0.35, 0.04, 0.03), 0.5, 0.1, 0.1)
        rail = kit.material("rail", (0.35, 0.36, 0.38), rough=0.4, metal=0.8)
        tie = kit.material("tie", (0.18, 0.11, 0.06), rough=0.8)
        ballast = kit.material("ballast", (0.30, 0.27, 0.23), rough=0.95)
        y0 = s.get("rail_y", -0.3)
        zr = s.get("rail_z", -0.62)
        kit.box(3.6, 0.42, 0.06, (0, y0, zr - 0.06), ballast)
        for k in range(-17, 18):
            kit.box(0.05, 0.32, 0.025, (k * 0.1, y0, zr), tie)
        for dy in (-0.09, 0.09):
            kit.box(3.6, 0.018, 0.03, (0, y0 + dy, zr + 0.025), rail)
        sc = s.get("train_scale", 0.075)
        x = s.get("train_x", -0.15)
        for k, op_list in enumerate(s["train"]):
            root = bpy.data.objects.new(f"veh{k}", None)
            scene.collection.objects.link(root)
            before = set(bpy.data.objects)
            for op in op_list:
                ops.run_op(kit, op, T=1.0, Z=lambda v: v)
            for o in bpy.data.objects:
                if o not in before and o is not root and o.parent is None:
                    o.parent = root
            root.scale = (sc, sc, sc)
            root.rotation_euler = (0, 0, math.radians(-90))  # 車頭（模型 +Y）朝右（+X）
            root.location = (x, y0, zr + 0.055)
            x -= s.get("train_gap", 1.02)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = s.get("ortho", 3.6)
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    tilt = math.radians(s.get("tilt", 12))
    cam.rotation_euler = (math.radians(90) - tilt, 0, 0)
    cam.location = (0, -10 * math.cos(tilt), 10 * math.sin(tilt) + s.get("cam_z", 0.15))
    scene.camera = cam
    for name, energy, rot in (("key", 3.2, (35, 0, -30)), ("fill", 1.2, (60, 0, 60)), ("top", 1.5, (5, 0, 0))):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = tuple(math.radians(v) for v in rot)
        scene.collection.objects.link(lo)
    scene.render.filepath = os.path.join(out, s["name"] + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    spec = json.load(open(args.spec))
    os.makedirs(args.out, exist_ok=True)
    for s in spec["shots"]:
        shot(spec, s, os.path.abspath(args.out))
        print(f"[logo_rig] {s['name']}")


main()
