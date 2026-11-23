#!/usr/bin/env python3
"""g1 的 logo（ROADMAP M4）：標題畫面的「OpenLoco」字標、About 視窗與開場畫面的字標。

  .venv/bin/python tools/gen/g1_logo.py [--reuse-render]

tools/blender/logo_rig.py 渲染（立體字 + M3 的 4-6-0 蒸汽機車與煤水車，幾何取自 tools/gen/vehicle_recipes.py）
→ 量化成 Loco 調色盤 → base/g1/logo/（PNG + sprites.json）。
取代的 vanilla 影像：locomotion_logo（標題視窗，270×162）、chris_sawyer_logo_small（About 視窗，216×53）、
atari_logo_intro_left／right 與 chris_sawyer_logo_intro_left／right（開場畫面，左右兩半）。
字型：DejaVu Sans Bold（系統字型，只用來渲染字形；字標的立體造型、配色與構圖為原創）。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import g1_title  # noqa: E402  （共用調色盤量化 q()）
import vehicle_recipes as vr  # noqa: E402
import vehicle_table  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "logo"
RENDER = REPO / "build" / "render" / "g1_logo"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def train_ops():
    R = vehicle_table.VEHICLES["JUBILEE"]["recipe"]
    loco = list(vr.model(R, 13.0, {"body": 0, "anim": 1, "anims": 4, "cargo": None, "brake": False}))
    tender = list(vr.model(R, 8.0, {"body": 1, "anim": 0, "anims": 1, "cargo": None, "brake": False}))
    return [loco, tender]


SHOTS = [  # (名稱, 尺寸, 參數)
    ("title", (270, 162), dict(text="OpenLoco", text_size=0.86, text_z=0.38, train=True, ortho=3.6, tilt=10,
                               rail_z=-0.62, train_x=0.38, train_gap=0.95, train_scale=0.09)),
    ("about", (216, 53), dict(text="OpenGraphics", text_size=0.5, text_z=0.0, ortho=3.9, tilt=6, extrude=0.08)),
    ("intro_a", (432, 108), dict(text="OpenLoco", text_size=0.74, text_z=0.14, sub="powered by OpenGraphics", sub_z=-0.4,
                                 sub_size=0.2, ortho=4.6, tilt=8)),
    ("intro_b", (500, 116), dict(text="OpenGraphics", text_size=0.66, text_z=0.14, sub="original art for OpenLoco",
                                 sub_z=-0.4, sub_size=0.2, ortho=5.2, tilt=8)),
]


def render(reuse: bool):
    if reuse and all((RENDER / f"{n}.png").exists() for n, _s, _p in SHOTS):
        return
    RENDER.mkdir(parents=True, exist_ok=True)
    tr = train_ops()
    spec = {"font": FONT, "shots": []}
    for name, size, p in SHOTS:
        s = dict(p, name=name, size=list(size))
        s["train"] = tr if p.get("train") else None
        spec["shots"].append(s)
    (RENDER / "spec.json").write_text(json.dumps(spec))
    r = subprocess.run(["blender", "-b", "--factory-startup", "--python", "tools/blender/logo_rig.py", "--",
                        "--spec", str(RENDER / "spec.json"), "--out", str(RENDER)], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit("logo 渲染失敗")


def quantize(path: Path):
    """RGBA → (w, h, pixels)：alpha < 128 透明，其餘取最接近的調色盤色（排除公司色與動畫色）。"""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            r, g, b, a = im.getpixel((x, y))
            if a >= 128:
                px[y * w + x] = g1_title.q((r, g, b))
    return w, h, bytes(px)


def crop(w, h, px):
    xs = [i % w for i, v in enumerate(px) if v]
    ys = [i // w for i, v in enumerate(px) if v]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(cw * ch)
    for y in range(ch):
        out[y * cw:(y + 1) * cw] = px[(y + y0) * w + x0:(y + y0) * w + x1 + 1]
    return cw, ch, x0, y0, bytes(out)


def split(w, h, px, left_w):
    a = bytearray(left_w * h)
    b = bytearray((w - left_w) * h)
    for y in range(h):
        a[y * left_w:(y + 1) * left_w] = px[y * w:y * w + left_w]
        b[y * (w - left_w):(y + 1) * (w - left_w)] = px[y * w + left_w:(y + 1) * w]
    return (left_w, h, bytes(a)), (w - left_w, h, bytes(b))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reuse-render", action="store_true")
    args = ap.parse_args()
    render(args.reuse_render)
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e for e in cat["entries"] if e.get("name")}
    frames = []
    # 標題 logo：視窗 298×170，vanilla 影像偏移 (16, 5)；裁切後保留在同一區域內
    w, h, px = quantize(RENDER / "title.png")
    cw, ch, x0, y0, cpx = crop(w, h, px)
    frames.append((ids["locomotion_logo"]["i"], (cw, ch, 16 + x0, 5 + y0, cpx)))
    w, h, px = quantize(RENDER / "about.png")
    frames.append((ids["chris_sawyer_logo_small"]["i"], (w, h, 0, 0, px)))
    for name, left, right in (("intro_a", "atari_logo_intro_left", "atari_logo_intro_right"),
                              ("intro_b", "chris_sawyer_logo_intro_left", "chris_sawyer_logo_intro_right")):
        w, h, px = quantize(RENDER / f"{name}.png")
        (lw, lh, lpx), (rw, rh, rpx) = split(w, h, px, ids[left]["w"])
        frames.append((ids[left]["i"], (lw, lh, 0, 0, lpx)))
        frames.append((ids[right]["i"], (rw, rh, 0, 0, rpx)))
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    pal = dat.load_palette()
    meta = []
    for idx, (fw, fh, fx, fy, fpx) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, fw, fh, fpx, bytes(255 if v else 0 for v in fpx), pal)
        meta.append({"index": idx, "path": fn, "x": fx, "y": fy})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"寫出 {len(frames)} 張 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
