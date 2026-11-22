"""P1 渲染（車輛）：與 tools/blender/static_rig.py 相同的相機與燈光，依「影像清單」逐張設定模型的方向與狀態後渲染。

  blender -b --factory-startup --python tools/blender/vehicle_rig.py -- --spec build/render/<NAME>/spec.json \\
      --out build/render/<NAME> [--samples 24] [--save-blend objects/…/OG_<NAME>.blend]

spec.json（由 tools/gen/build_vehicles.py 依模板結構產生）：
  {"size": 畫布, "unit": "m"|"tile", "states": {狀態名: [幾何指令…]}, "images": [{"state": 名, "yaw": 度, "pitch": 度, "shadow": bool}, …]}
幾何指令同 tools/blender/models/ops.py。unit = m（預設，車輛）：單位約等於公尺，模型車頭朝 +Y、輪底在 z = 0、轉軸在原點；
unit = tile（車站，tools/gen/build_stations.py）：平面以格、高度以遊戲 px 為單位，原點 = 圖塊角落。
角度慣例取自上游 Loco Graphics Helper 的 rig（OG_VULCAN.blend）：先繞模型 X 軸俯仰（正值 = 車頭抬起），再繞 Z 軸偏航。
shadow = true：把模型壓扁在地面（z 縮成 0.1%）並全部換成深色，作為飛機的地面影子。
"""
import argparse
import json
import math
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "models"))
import kit  # noqa: E402
import ops  # noqa: E402
import render_sprites as rs  # noqa: E402
import static_rig  # noqa: E402


def build_state(name, op_list, unit="m"):
    """unit = "m"：座標直接是 Blender 單位（車輛）；"tile"：平面以格、高度以遊戲 px 為單位（車站等，同建築）。"""
    root = bpy.data.objects.new(f"state_{name}", None)
    bpy.context.scene.collection.objects.link(root)
    before = set(bpy.data.objects)
    for op in op_list:
        if unit == "tile":
            ops.run_op(kit, op)
        else:
            ops.run_op(kit, op, T=1.0, Z=lambda v: v)
    objs = [o for o in bpy.data.objects if o not in before and o is not root]
    for o in objs:
        if o.parent is None:
            o.parent = root
    return root, objs


def set_visible(root, objs, vis):
    for o in [root] + objs:
        o.hide_render = not vis
        o.hide_viewport = not vis


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--mask-samples", type=int, default=12)
    ap.add_argument("--origin-offset", type=float, nargs=2, default=[0.0, 1.0])
    ap.add_argument("--save-blend")
    ap.add_argument("--only", default="", help="只渲染這些影像 index（逗號分隔，可用 a-b 範圍）")
    ap.add_argument("--json-name", default="render.json", help="影格清單檔名（分段渲染時每段各寫一個）")
    args = ap.parse_args(argv)
    spec = json.load(open(args.spec, encoding="utf-8"))
    size = spec["size"]
    scene, cam = static_rig.setup_scene(size, args.samples)
    states = {}
    for name, op_list in spec["states"].items():
        states[name] = build_state(name, op_list, spec.get("unit", "m"))
        set_visible(*states[name], False)

    if args.save_blend:                                   # 來源檔：每個狀態並排
        for k, (name, (root, objs)) in enumerate(states.items()):
            set_visible(root, objs, True)
            root.location = ((k % 8) * 12.0, (k // 8) * 12.0, 0)
        path = os.path.abspath(args.save_blend)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True, compress=True)
        print(f"[vehicle_rig] 存成 {path}（{len(states)} 個狀態）")
        return

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    co = world_to_camera_view(scene, cam, Vector((0.0, 0.0, 0.0)))
    origin = [co.x * size + args.origin_offset[0], (1.0 - co.y) * size + args.origin_offset[1]]
    images = spec["images"]
    only = None
    if args.only:
        only = set()
        for v in filter(None, args.only.split(",")):
            a, _, b = v.partition("-")
            only.update(range(int(a), int(b or a) + 1))
    t0 = time.time()

    # 影子狀態：固定換成深色材質
    shadow_mat = rs.emission_material("__shadow", (0.02, 0.02, 0.02))
    shadow_states = {img["state"] for img in images if img.get("shadow")}
    for name in shadow_states:
        for o in states[name][1]:
            if hasattr(o, "material_slots"):
                for sl in o.material_slots:
                    sl.link = "OBJECT"
                    sl.material = shadow_mat

    # 每張影像 = 一個影格：作用中的狀態放在原點並設定方向，其他狀態移到畫面外（只對根物件打關鍵影格）
    FAR = (10000.0, 10000.0, 0.0)
    for name, (root, objs) in states.items():
        set_visible(root, objs, True)
        root.rotation_mode = "XYZ"
    sel = [i for i in range(len(images)) if only is None or i in only]
    prev = {}
    for f, i in enumerate(sel):
        img = images[i]
        for name, (root, _objs) in states.items():
            active = name == img["state"]
            if active:
                root.location = (0.0, 0.0, 0.0)
                root.rotation_euler = (math.radians(img.get("pitch", 0.0)), 0.0, math.radians(img.get("yaw", 0.0)))
                root.scale = (1, 1, 0.001) if img.get("shadow") else (1, 1, 1)
                root.keyframe_insert("location", frame=f)
                root.keyframe_insert("rotation_euler", frame=f)
                root.keyframe_insert("scale", frame=f)
            elif prev.get(name, True):
                root.location = FAR
                root.keyframe_insert("location", frame=f)
            prev[name] = active
    for root, _objs in states.values():                   # 一律不內插（每格各自獨立）
        ad = root.animation_data
        if ad and ad.action:
            for fc in _fcurves(ad):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"
    scene.frame_start, scene.frame_end = 0, len(sel) - 1
    scene.render.filepath = os.path.join(out, "f####")
    bpy.ops.render.render(animation=True)
    frames = []
    for f, i in enumerate(sel):
        src, dst = os.path.join(out, f"f{f:04d}.png"), os.path.join(out, f"{i:04d}.png")
        os.replace(src, dst)
        frames.append({"file": f"{i:04d}.png", "index": i, "origin": [round(origin[0], 3), round(origin[1], 3)]})
    print(f"[vehicle_rig] 一般影格 {len(sel)} 張（{time.time() - t0:.0f}s）")

    # 公司色遮罩：換成純色發光材質後再渲染一輪
    if rs.apply_mask_materials():
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.eevee.taa_render_samples = args.mask_samples
        scene.render.filepath = os.path.join(out, "m####")
        bpy.ops.render.render(animation=True)
        for f, i in enumerate(sel):
            src = os.path.join(out, f"m{f:04d}.png")
            if images[i].get("shadow"):
                os.remove(src)
                continue
            os.replace(src, os.path.join(out, f"{i:04d}_mask.png"))
            frames[f]["mask"] = f"{i:04d}_mask.png"
    with open(os.path.join(out, args.json_name), "w") as fp:
        json.dump({"size": [size, size], "frames": frames}, fp, indent=1)
    print(f"[vehicle_rig] 完成 {len(frames)} 張 → {out}（{time.time() - t0:.0f}s）")


def _fcurves(ad):
    """Blender 5：動作是分層的（layers → strips → channelbags）；舊版直接有 fcurves。"""
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


main()
