#!/usr/bin/env python3
"""建置 M3 車輛（卡車、巴士、船、飛機、火車）。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_vehicles.py [--reuse-render] [--only 0,8,16] [名稱…]
  … build_vehicles.py --repack 名稱…   只用既有 sprite 重新打包（不開 Blender）

流程：模板（vanilla）取得車身／轉向架 sprite 結構 → 依結構列出每張影像的方向（yaw）、坡度（pitch）與狀態
（動畫格、貨物圖、煞車燈、飛機影子）→ tools/gen/vehicle_recipes.py 產生各狀態的幾何指令 →
tools/blender/vehicle_rig.py 渲染 → tools/quantize.py → tools/pack.py → 刪 .gitkeep → 寫 FORK.md。

影像順序（OpenLoco Objects/VehicleObject.cpp、Vehicles/VehicleDraw.cpp）：每個車身 sprite 依序為
  平地 N 向（對稱時 N/2）→ [緩坡] 過渡 4 向上、4 向下 → 緩坡 Ns 向上、Ns 向下 → [陡坡] 同上（對稱時只有「上」）；
  每個方向 numFramesPerRotation 張 = 動畫格 + 貨物圖 × 動畫格數，最後一張為煞車燈（有的話）。
之後是轉向架 sprite：平地 32 向（對稱 16）→ [緩坡] 32 向上、32 向下（對稱只有上）。飛機的轉向架 sprite 是地面影子。
方向：yaw = -(360 / 方向數) × k（度，與上游 rig 相同）；坡度：過渡 5.625°、緩坡 11.25°、陡坡過渡 16.875°、陡坡 22.5°。
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "gen"))
import dat  # noqa: E402
import vehicle_recipes as vr  # noqa: E402
from vehicle_table import VEHICLES  # noqa: E402

PY = str(REPO / ".venv" / "bin" / "python")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", str(Path.home() / "Locomotion" / "game")))
VR = REPO / "objects" / "VanillaReplacements" / "Vehicle"
BUILD = REPO / "build"
CATS = {1: "grain", 2: "coal", 3: "ironOre", 4: "liquids", 5: "paper", 6: "steel", 7: "timber", 8: "goods", 9: "foods",
        11: "livestock", 12: "passengers", 13: "mail"}

# 繪製原點的垂直校正（px，加在相機投影的原點上）：以 vanilla／上游 sprite 的底部位置對齊
ORIGIN_DY = {"truck": -1, "bus": -1}
CHUNK = 24                         # 每個 Blender 行程最多渲染幾格（見 build() 的分段渲染）

FORK_MD = """# OG_{vanilla}（fork 自製）
- 對應 vanilla：{vanilla}（Vehicle/{sub}）
- 內部名稱：{name}
- 遊戲內名稱：{display}
- 設計概念：{concept}
- 製作方式：程序化建模（`tools/gen/vehicle_table.py` 的配方 → `tools/gen/vehicle_recipes.py` 產生各狀態的幾何指令），
  `tools/blender/vehicle_rig.py` 依模板結構逐張渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_{vanilla}.blend`（所有狀態並排）；建置指令 `tools/gen/build_vehicles.py {vanilla}`。
  以 vanilla {vanilla} 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 結構、張數與車身長度比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
"""


def template_path(vanilla: str) -> Path:
    p = LOCO / "ObjData" / f"{vanilla}.DAT"
    if p.exists():
        return p
    for f in (LOCO / "ObjData").iterdir():
        try:
            if dat.read_dat(f).name_str == vanilla:
                return f
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(f"找不到模板 {vanilla}")


def structure(o: dat.DatObject) -> dict:
    d = o.data
    bodies, bogies = [], []
    for i in range(4):
        b = d[0x3C + i * 0x1E: 0x3C + (i + 1) * 0x1E]
        if b[7] & 1:
            bodies.append(dict(flat=b[0], sloped=b[1], anim=b[2], cload=b[3], cargo=b[4], roll=b[5], half=b[6], flags=b[7]))
    for i in range(2):
        b = d[0xB4 + i * 0x12: 0xB4 + (i + 1) * 0x12]
        if b[1] & 1:
            bogies.append(dict(anim=b[0], flags=b[1]))
    # 貨物：cargo frame c（1..）對應的貨種
    _e, p = dat.parse_string_table(d, 0x15E)
    flags = struct.unpack_from("<H", d, 0xE0)[0]
    if not (flags & 0x200) and d[2] in (0, 1):
        p += 16
    p += 16 * d[6]
    cargo_by_offset = {}
    for _i in range(2):
        mx = d[p]
        p += 1
        if mx == 0:
            continue
        while struct.unpack_from("<H", d, p)[0] != 0xFFFF:
            c = struct.unpack_from("<H", d, p)[0]
            off = d[p + 2]
            p += 3
            cargo_by_offset.setdefault(off, CATS.get(c, str(c)))
        p += 2
    return {"mode": d[2], "bodies": bodies, "bogies": bogies, "cargo_by_offset": cargo_by_offset}


def body_images(bi, b, cargo_names):
    """回傳 [(state dict, yaw, pitch)]。"""
    sym = bool(b["flags"] & 2)
    brake = bool(b["flags"] & 0x20)
    A, C = b["anim"], b["cargo"]
    fpr = A * C * b["roll"] + (1 if brake else 0)
    slots = []
    N, Ns = b["flat"], b["sloped"]
    for k in range(N // 2 if sym else N):
        slots.append((-(360 / N) * k, 0.0))

    def slope_group(trans, full):
        for sign in ((1,) if sym else (1, -1)):
            for k in range(4):
                slots.append((-90.0 * k, sign * trans))
        for sign in ((1,) if sym else (1, -1)):
            for k in range(Ns):
                slots.append((-(360 / Ns) * k, sign * full))
    if b["flags"] & 0x08:
        slope_group(5.625, 11.25)
    if b["flags"] & 0x10:
        slope_group(16.875, 22.5)
    out = []
    for yaw, pitch in slots:
        for f in range(fpr):
            if brake and f == fpr - 1:
                st = {"body": bi, "anim": 0, "anims": A, "cargo": None, "brake": True}
            else:
                a = f % A
                c = (f // A) % C
                st = {"body": bi, "anim": a, "anims": A, "cargo": cargo_names.get(c), "brake": False}
            out.append((st, yaw, pitch))
    return out


def bogie_images(gi, g, shadow):
    sym = bool(g["flags"] & 2)
    A = g["anim"]
    slots = [(-(360 / 32) * k, 0.0) for k in range(16 if sym else 32)]
    for bit, ang in ((0x04, 11.25), (0x08, 22.5)):
        if g["flags"] & bit:
            for sign in ((1,) if sym else (1, -1)):
                for k in range(32):
                    slots.append((-(360 / 32) * k, sign * ang))
    out = []
    for yaw, pitch in slots:
        for a in range(A):
            st = {"part": "bogie", "anim": a, "anims": A, "body": 0, "cargo": None, "brake": False, "shadow": shadow}
            out.append((st, yaw, pitch))
    return out


def state_key(st):
    return "_".join(f"{k}{v}" for k, v in sorted(st.items()) if k not in ("shadow",))


def brake_overlays(sprites_dir: Path, images) -> int:
    """煞車燈格只保留「與同方向第一格不同」的像素（vanilla 也是疊在車身上的小圖）；完全看不到時為 1×1 透明。"""
    import pack
    meta = json.loads((sprites_dir / "sprites.json").read_text())
    pal = dat.load_palette()
    n = 0
    for i, (st, _yaw, _pitch) in enumerate(images):
        if not st.get("brake"):
            continue
        A = st["anims"]
        fpr_rest = None
        j = i - 1
        while j >= 0 and images[j][0].get("brake") is False and images[j][1:] == images[i][1:]:
            fpr_rest = j
            j -= 1
        if fpr_rest is None:
            continue
        a_m, b_m = meta[fpr_rest], meta[i]

        def grid(path, m):
            w, h, px = pack.load_indices(path, pal)
            return {(i % w + m["x"], i // w + m["y"]): v for i, v in enumerate(px) if v}
        ga, gb = grid(sprites_dir / a_m['path'], a_m), grid(sprites_dir / b_m['path'], b_m)
        diff = {k: v for k, v in gb.items() if ga.get(k) != v and v in range(0xA6, 0xB2)}
        if diff:
            xs = [k[0] for k in diff]
            ys = [k[1] for k in diff]
            x0, y0 = min(xs), min(ys)
            w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
            px = bytearray(w * h)
            for (x, y), v in diff.items():
                px[(y - y0) * w + (x - x0)] = v
        else:
            x0, y0, w, h, px = 0, 0, 1, 1, bytearray(1)
        dat.write_indexed_png(sprites_dir / b_m["path"], w, h, bytes(px), bytes(255 if v else 0 for v in px), pal)
        b_m["x"], b_m["y"] = x0, y0
        n += 1
    (sprites_dir / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    return n


def run(cmd, env=None):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"失敗：{' '.join(map(str, cmd))}")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if lines:
        print("  " + lines[-1])


def build(vanilla: str, cfg: dict, reuse: bool, only: str) -> None:
    sub, name, display, concept, R = cfg["sub"], cfg["name"], cfg["display"], cfg["concept"], cfg["recipe"]
    folder = VR / sub / vanilla
    tpl = template_path(vanilla)
    obj = dat.read_dat(tpl)
    s = structure(obj)
    cargo_names = {0: None}
    for off, cname in s["cargo_by_offset"].items():
        cargo_names[1 + off] = cname
    images = []
    for bi, b in enumerate(s["bodies"]):
        images += body_images(bi, b, cargo_names)
    shadow = R["cat"] == "air"
    for gi, g in enumerate(s["bogies"]):
        images += bogie_images(gi, g, shadow)
    n_tpl = len(obj.image_table().entries)
    if len(images) != n_tpl:
        raise SystemExit(f"{vanilla}：依結構算出 {len(images)} 張，模板有 {n_tpl} 張")
    # 每個車身的長度
    lengths = [2 * b["half"] * vr.SCALE for b in s["bodies"]]
    states, spec_images = {}, []
    for st, yaw, pitch in images:
        key = state_key(st)
        if key not in states:
            L = lengths[min(st.get("body", 0), len(lengths) - 1)]
            if shadow and st.get("part") == "bogie":
                st2 = dict(st, part="body", anim=0)
                states[key] = list(vr.model(R, lengths[0], st2))
            else:
                states[key] = list(vr.model(R, L, st))
        spec_images.append({"state": key, "yaw": yaw, "pitch": pitch, "shadow": bool(st.get("shadow"))})
    Lmax = max(lengths)
    size = max(64, -(-int(Lmax * 4.42 * 1.25 + 48) // 32) * 32)
    render_dir = BUILD / "render" / vanilla
    sprites_dir = BUILD / "sprites" / vanilla
    print(f"== {vanilla}（{len(images)} 張、{len(states)} 個狀態、畫布 {size}）")
    if not (reuse and (render_dir / "render.json").exists()):
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True)
        spec = {"size": size, "states": states, "images": spec_images}
        (render_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        cmd = ["blender", "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--",
               "--spec", str(render_dir / "spec.json"), "--out", str(render_dir), "--samples", str(cfg.get("samples", 12)), "--mask-samples", "6",
               "--origin-offset", "0", str(ORIGIN_DY.get(R["cat"], 2))]
        if only:
            run(cmd + ["--only", only])
            return
        # Blender（EEVEE + Mesa d3d12）每渲染一格記憶體就漲一些、不會釋放：分段渲染，每段換新的行程
        frames = []
        for a in range(0, len(spec_images), CHUNK):
            b = min(a + CHUNK, len(spec_images)) - 1
            part = f"render_{a:04d}.json"
            run(cmd + ["--only", f"{a}-{b}", "--json-name", part])
            frames += json.loads((render_dir / part).read_text())["frames"]
            (render_dir / part).unlink()
        (render_dir / "render.json").write_text(json.dumps({"size": [size, size], "frames": frames}, indent=1))
    folder.mkdir(parents=True, exist_ok=True)
    (render_dir / "spec.json").exists() and run(
        ["blender", "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--", "--spec",
         str(render_dir / "spec.json"), "--save-blend", str(folder / f"OG_{vanilla}.blend")])
    run([PY, "tools/quantize.py", str(render_dir), "-o", str(sprites_dir), "--no-remap-colours"])
    nb = brake_overlays(sprites_dir, images)
    if nb:
        print(f"  煞車燈疊加圖 {nb} 張")
    out = folder / f"OG_{vanilla}.dat"
    run([PY, "tools/pack.py", "--template", str(tpl), "--sprites", str(sprites_dir), "--name", name, "--relink",
         "--display", display, "-o", str(out)])
    (folder / ".gitkeep").unlink(missing_ok=True)
    fm = folder / "FORK.md"
    if not fm.exists():
        fm.write_text(FORK_MD.format(vanilla=vanilla, sub=sub, name=name, display=display, concept=concept), encoding="utf-8")


def repack(vanilla: str, cfg: dict) -> None:
    """只用 build/sprites/<名稱> 現有的 sprite 重新打包（不渲染、不開 Blender），例如 relink 規則改變之後。"""
    folder = VR / cfg["sub"] / vanilla
    out = folder / f"OG_{vanilla}.dat"
    run([PY, "tools/pack.py", "--template", str(template_path(vanilla)), "--sprites", str(BUILD / "sprites" / vanilla),
         "--name", cfg["name"], "--relink", "--display", cfg["display"], "-o", str(out)])


def main() -> int:
    args = sys.argv[1:]
    if "--repack" in args:
        args.remove("--repack")
        for n in args:
            cfg = dict(VEHICLES[n])
            cfg.setdefault("name", dat.og_internal_name(n).decode().strip())
            repack(n, cfg)
        return 0
    reuse = "--reuse-render" in args
    if reuse:
        args.remove("--reuse-render")
    only = ""
    if "--only" in args:
        i = args.index("--only")
        only = args[i + 1]
        del args[i:i + 2]
    for n in args or list(VEHICLES):
        cfg = dict(VEHICLES[n])
        cfg.setdefault("name", dat.og_internal_name(n).decode().strip())
        build(n, cfg, reuse, only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
