"""P1 渲染：以 .blend 內現有的 Loco 渲染 rig（相機、燈光、逐格動畫）headless 輸出 sprite 影格。

  blender -b <物件.blend> --python tools/blender/render_sprites.py -- \
      --out build/render/<NAME> [--frames 0-615 | --frames 0,4,8] [--samples 16] [--percentage 100]

適用於上游以 Loco Graphics Helper（新版）製作的 .blend：每個 sprite 角度烘焙成一格動畫，
影格順序 = image table 順序（例：OG_4F.blend 影格 0–615 = 616 張 sprite）。
- 找不到的貼圖會自動改指向 repo 的 textures/（依檔名）或 .blend 所在資料夾。
- 輸出 <out>/NNNN.png（RGBA，透明背景）與 render.json（每格的原點像素座標），交給 tools/quantize.py。
- 原點 = 世界座標 (0,0,0) 經作用中相機投影到影格上的位置，再加上 --origin-offset。
  預設 (0, 2)：以上游 OG_4F.blend 校正（7 類 sprite 與 DAT 比對，dx 恆為 0、dy 恆為 2）。
- 公司色遮罩：依材質名稱判斷（上游慣例）。"Company Color 1"／"Recolorable 1" = primary，
  "Company Color 2"／"Recolorable 2" = secondary。全部正常影格渲染完後，把材質換成純色發光
  （紅 = primary、綠 = secondary、黑 = 其他），色彩管理改 Standard，再渲染一輪輸出 NNNN_mask.png。
"""
import argparse
import json
import os
import re
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRIMARY_RE = re.compile(r"(company\s*colou?r|recolou?rable)\s*1", re.I)
SECONDARY_RE = re.compile(r"(company\s*colou?r|recolou?rable)\s*2", re.I)


def emission_material(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    em.inputs["Strength"].default_value = 1.0
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], outn.inputs["Surface"])
    return m


def apply_mask_materials():
    """把所有物件的材質換成遮罩用的純色發光材質；回傳是否有任何 remap 材質。"""
    mats = {"p": emission_material("__mask_primary", (1, 0, 0)),
            "s": emission_material("__mask_secondary", (0, 1, 0)),
            "n": emission_material("__mask_none", (0, 0, 0))}
    found = False
    for ob in bpy.data.objects:
        if not hasattr(ob, "material_slots"):
            continue
        for slot in ob.material_slots:
            name = slot.material.name if slot.material else ""
            if PRIMARY_RE.search(name):
                key = "p"
                found = True
            elif SECONDARY_RE.search(name):
                key = "s"
                found = True
            else:
                key = "n"
            slot.link = "OBJECT"   # 不改到共用的 mesh 資料
            slot.material = mats[key]
    return found


def parse_frames(spec: str, start: int, end: int):
    if not spec:
        return list(range(start, end))
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def fix_missing_images():
    blend_dir = os.path.dirname(bpy.data.filepath)
    fixed, missing = [], []
    for img in bpy.data.images:
        if img.source != "FILE" or not img.filepath or img.packed_file is not None:
            continue  # 已打包進 .blend 的貼圖不用處理
        path = bpy.path.abspath(img.filepath)
        if os.path.exists(path):
            continue
        name = os.path.basename(img.filepath.replace("\\", "/"))
        for cand in (os.path.join(REPO, "textures", name), os.path.join(blend_dir, name)):
            if os.path.exists(cand):
                img.filepath = cand
                img.reload()
                fixed.append(name)
                break
        else:
            missing.append(img.filepath)
    return sorted(set(fixed)), sorted(set(missing))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", default="")
    ap.add_argument("--samples", type=int, default=0, help="EEVEE 取樣數（0 = 沿用 .blend 設定）")
    ap.add_argument("--percentage", type=int, default=100)
    ap.add_argument("--origin-offset", type=float, nargs=2, default=[0.0, 2.0], metavar=("DX", "DY"))
    ap.add_argument("--no-mask", action="store_true", help="不輸出公司色遮罩")
    ap.add_argument("--mask-samples", type=int, default=16, help="遮罩 pass 的 EEVEE 取樣數（預設 16）")
    args = ap.parse_args(argv)

    scene = bpy.context.scene
    cam = scene.camera
    if cam is None:
        sys.exit("場景沒有作用中相機")
    fixed, missing = fix_missing_images()
    print(f"[render_sprites] 貼圖：修正 {fixed}，仍缺 {missing}")

    r = scene.render
    r.resolution_percentage = args.percentage
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    if args.samples and hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = args.samples

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    w = int(r.resolution_x * r.resolution_percentage / 100)
    h = int(r.resolution_y * r.resolution_percentage / 100)
    frames = parse_frames(args.frames, scene.frame_start, scene.frame_end)
    spec = {"source": bpy.data.filepath, "camera": cam.name, "size": [w, h], "frames": []}
    t0 = time.time()
    for n, f in enumerate(frames):
        scene.frame_set(f)
        co = world_to_camera_view(scene, cam, Vector((0.0, 0.0, 0.0)))
        origin = [co.x * w + args.origin_offset[0], (1.0 - co.y) * h + args.origin_offset[1]]
        fn = f"{f:04d}.png"
        r.filepath = os.path.join(out, fn)
        bpy.ops.render.render(write_still=True)
        spec["frames"].append({"file": fn, "frame": f, "origin": [round(origin[0], 3), round(origin[1], 3)]})
        print(f"[render_sprites] {n + 1}/{len(frames)} frame {f} ({time.time() - t0:.1f}s)")
    if not args.no_mask and apply_mask_materials():
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        if hasattr(scene, "eevee"):
            # 遮罩也要反鋸齒，邊緣像素才會和正常影格一樣是部分值（1 取樣會讓公司色邊緣變成一般紫色細線）
            scene.eevee.taa_render_samples = min(scene.eevee.taa_render_samples, args.mask_samples)
        for n, fr in enumerate(spec["frames"]):
            scene.frame_set(fr["frame"])
            fr["mask"] = fr["file"].replace(".png", "_mask.png")
            r.filepath = os.path.join(out, fr["mask"])
            bpy.ops.render.render(write_still=True)
        print(f"[render_sprites] 公司色遮罩 {len(spec['frames'])} 格完成（{time.time() - t0:.1f}s）")
    else:
        print("[render_sprites] 沒有公司色材質（或指定 --no-mask），不輸出遮罩")
    with open(os.path.join(out, "render.json"), "w") as fp:
        json.dump(spec, fp, indent=2)
    print(f"[render_sprites] 完成 {len(frames)} 格 → {out}（{time.time() - t0:.1f}s）")


main()
