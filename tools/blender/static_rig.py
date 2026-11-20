"""P1 渲染（靜態物件：建築、產業）：在空白場景建立與上游相同的相機與燈光，依模型腳本逐部件、
逐旋轉渲染，輸出 tools/quantize.py 可讀的 render.json。

  blender -b --factory-startup --python tools/blender/static_rig.py -- \
      --model objects/…/model.py --heights 1,10,16 --out build/render/<NAME> [--size 256] [--samples 32]

模型腳本需定義 make_part(kit, index)：在原點（佔地中心、z = 0）建立該部件的物件（kit 見 tools/blender/kit.py）。
可選 PART_FRAMES = {index: callable(kit, objs, frame)} 之類的延伸，目前只需 make_part。
- 每個部件都在 z = 0 渲染（偏移與絕對高度無關）；--heights（遊戲 px，與模板的 part heights 相同）提供給模型，
  模型以環境變數 PART_HEIGHT_PX 取得目前部件的高度。
- 影像順序：部件 × 4 旋轉（image = part * 4 + rotation），與 OpenLoco 的建築／產業相同。
- 原點 = 世界 (0, 0, z_p) 經相機投影 + --origin-offset。
- 公司色遮罩：材質名稱含 "Company Color 1"／"2"（同 render_sprites.py）。

  … static_rig.py -- --model … --heights … --save-blend objects/…/OG_<NAME>.blend
      不渲染：把所有部件沿 X 軸並排建好（含相機與燈光），存成 .blend 作為可在 Blender 中檢視的來源檔
      （AGENTS.md §2.3）。材質全是程序化節點，沒有外部貼圖。
"""
import argparse
import importlib.util
import json
import math
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import kit  # noqa: E402
import render_sprites as rs  # noqa: E402  共用遮罩材質邏輯

LIGHTS = [  # (名稱, 強度, 旋轉角度) — 取自上游 OG_4F.blend
    ("Light Primary", 4.75, (30.0, 0.0, 135.0)),
    ("Light Left", 2.75, (60.0, 0.0, 35.4)),
    ("Light Back", 2.0, (60.0, 0.0, -90.0)),
    ("Light Upper Highlights", 1.4, (50.0, 0.0, 120.0)),
]


def setup_scene(size, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = samples
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("World")
    world.color = (0.05, 0.05, 0.05)
    scene.world = world

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = size / kit.PX_PER_UNIT
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    rot = (math.radians(60.718), 0.0, math.radians(45.0))
    cam.rotation_euler = rot
    direction = Vector((0, 0, 1))
    direction.rotate(cam.rotation_euler)
    cam.location = direction * 60.0
    cam_data.clip_end = 500
    scene.camera = cam

    for name, energy, (rx, ry, rz) in LIGHTS:
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        scene.collection.objects.link(lo)
    return scene, cam


def load_model(path):
    spec = importlib.util.spec_from_file_location("model", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--heights", required=True, help="各部件高度（遊戲 px），逗號分隔")
    ap.add_argument("--out", help="渲染輸出資料夾（渲染時必填）")
    ap.add_argument("--save-blend", help="不渲染，所有部件並排存成這個 .blend")
    ap.add_argument("--parts", default="", help="只渲染這些部件，例如 0-3,6")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--mask-samples", type=int, default=16)
    ap.add_argument("--origin-offset", type=float, nargs=2, default=[0.0, 1.0], metavar=("DX", "DY"),
                    help="預設 (0, 1)：以 1×1 地面板對 vanilla 校正（64×32、偏移 -32,-17）")
    ap.add_argument("--rotation-sign", type=float, default=-1.0, help="旋轉方向；-1 以 vanilla BLDCTY12 校正（畫面上順時針：右→下→左→上）")
    ap.add_argument("--no-mask", action="store_true")
    args = ap.parse_args(argv)

    heights = [int(h) for h in args.heights.split(",")]
    parts = list(range(len(heights)))
    if args.parts:
        parts = []
        for seg in args.parts.split(","):
            a, _, b = seg.partition("-")
            parts += list(range(int(a), int(b or a) + 1))
    scene, cam = setup_scene(args.size, args.samples)
    model = load_model(args.model)
    if args.save_blend:
        for k, p in enumerate(parts):
            root = bpy.data.objects.new(f"part{p}", None)
            scene.collection.objects.link(root)
            before = set(bpy.data.objects)
            os.environ["PART_HEIGHT_PX"] = str(heights[p])
            model.make_part(kit, p)
            for o in bpy.data.objects:
                if o not in before and o is not root and o.parent is None:
                    o.parent = root
            root.location = (k * 3 * kit.TILE, 0, 0)
        path = os.path.abspath(args.save_blend)
        bpy.context.preferences.filepaths.save_version = 0      # 不產生 .blend1 備份
        bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True, compress=True)
        print(f"[static_rig] 存成 {path}（{len(parts)} 個部件並排）")
        return
    if not args.out:
        ap.error("渲染時必須指定 --out")
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    spec = {"model": os.path.abspath(args.model), "size": [args.size, args.size], "frames": []}
    t0 = time.time()

    for p in parts:
        # 每個部件都在 z = 0 渲染：正交投影下 sprite 相對原點的偏移與絕對高度無關，
        # 而部件實際堆疊順序由變化組合決定（不是 index 順序），放高反而可能超出畫布
        z_cum = 0.0
        root = bpy.data.objects.new(f"part{p}", None)
        scene.collection.objects.link(root)
        before = set(bpy.data.objects)
        os.environ["PART_HEIGHT_PX"] = str(heights[p])
        model.make_part(kit, p)
        objs = [o for o in bpy.data.objects if o not in before and o is not root]
        for o in objs:
            if o.parent is None:
                o.parent = root
        root.location = (0, 0, z_cum)
        co = world_to_camera_view(scene, cam, Vector((0.0, 0.0, z_cum)))
        origin = [co.x * args.size + args.origin_offset[0], (1.0 - co.y) * args.size + args.origin_offset[1]]
        for r in range(4):
            root.rotation_euler[2] = math.radians(90.0 * r * args.rotation_sign)
            fn = f"{p:03d}_{r}.png"
            scene.render.filepath = os.path.join(out, fn)
            bpy.ops.render.render(write_still=True)
            spec["frames"].append({"file": fn, "part": p, "rotation": r,
                                   "origin": [round(origin[0], 3), round(origin[1], 3)]})
        if not args.no_mask:
            vt, look, samples = scene.view_settings.view_transform, scene.view_settings.look, scene.eevee.taa_render_samples
            if rs.apply_mask_materials():
                scene.view_settings.view_transform = "Standard"
                scene.view_settings.look = "None"
                scene.eevee.taa_render_samples = min(samples, args.mask_samples)
                for r in range(4):
                    root.rotation_euler[2] = math.radians(90.0 * r * args.rotation_sign)
                    fn = f"{p:03d}_{r}_mask.png"
                    scene.render.filepath = os.path.join(out, fn)
                    bpy.ops.render.render(write_still=True)
                    spec["frames"][-4 + r]["mask"] = fn
            scene.view_settings.view_transform, scene.view_settings.look = vt, look
            scene.eevee.taa_render_samples = samples
        for o in objs + [root]:
            bpy.data.objects.remove(o, do_unlink=True)
        print(f"[static_rig] part {p} 完成（{time.time() - t0:.1f}s）")

    with open(os.path.join(out, "render.json"), "w") as fp:
        json.dump(spec, fp, indent=2)
    print(f"[static_rig] 完成 {len(spec['frames'])} 格 → {out}（{time.time() - t0:.1f}s）")


main()
