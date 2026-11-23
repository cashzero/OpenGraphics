#!/usr/bin/env python3
"""g1 的地圖箭頭（ROADMAP M4）：施工箭頭 16 個、單行道箭頭 20 個、地圖邊界外的空格 blank_tile。輸出 base/g1/arrows/。

  .venv/bin/python tools/gen/g1_arrows.py

- 施工箭頭（Paint/PaintTile.cpp paintConstructionArrow）：依建造方向選圖（0–3 = north／east／south／west，
  4–7、8–11 = 同方向的另兩個位置，12–15 = 斜向），以 Colour::yellow 換色 → 用 primary remap 色號 + 深色外框。
- 單行道箭頭（Paint/PaintRoad.cpp、PaintSignal.cpp）：以 mutedAvocadoGreen 等換色，畫法同上（較小）。
- 方向（rotation 0 的世界座標）：north = −x、east = +y、south = +x、west = −y（與軌道方向 0–3 的行進方向相同）。
  箭頭畫在地面平面上再投影；中心放在 vanilla 同名影像的位置（catalog 的偏移與尺寸），與 OpenLoco 的繪製位置一致。
- blank_tile（PaintTile.cpp）：地圖邊界外的空格 → 深色菱形。
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "arrows"
REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
DIRS = {"north": (-1, 0), "east": (0, 1), "south": (1, 0), "west": (0, -1),
        "north_east": (-1, 1), "south_east": (1, 1), "south_west": (1, -1), "north_west": (-1, -1)}


def direction(name):
    core = re.sub(r"^(construction_arrow_|one_way_direction_arrow_)", "", name)
    core = re.sub(r"^(left_lane_|right_lane_)", "", core)
    core = re.sub(r"(_?\d)$", "", core)
    return DIRS[core]


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def arrow(e, length):
    dx, dy = direction(e["name"])
    n = math.hypot(dx, dy)
    v = (dx / n, dy / n)
    p = (-v[1], v[0])
    L = length
    world = [(-0.5 * L, -0.12 * L), (0.1 * L, -0.12 * L), (0.1 * L, -0.32 * L), (0.5 * L, 0.0),
             (0.1 * L, 0.32 * L), (0.1 * L, 0.12 * L), (-0.5 * L, 0.12 * L)]
    pts = []
    for a, b in world:                                        # (沿 v, 沿 p) → 世界 (x, y) → 畫面
        x, y = a * v[0] + b * p[0], a * v[1] + b * p[1]
        pts.append((y - x, (x + y) / 2))
    cx, cy = e["x"] + e["w"] / 2, e["y"] + e["h"] / 2
    poly = [(sx + cx, sy + cy) for sx, sy in pts]
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    x0, y0 = math.floor(min(xs)) - 1, math.floor(min(ys)) - 1
    x1, y1 = math.ceil(max(xs)) + 1, math.ceil(max(ys)) + 1
    fill = {(i, j) for j in range(y0, y1 + 1) for i in range(x0, x1 + 1) if inside((i + 0.5, j + 0.5), poly)}
    pix = {}
    for (i, j) in fill:
        edge = any((i + a, j + b) not in fill for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        pix[(i, j)] = REMAP[3] if edge else REMAP[9]
    ring = {(i + a, j + b) for (i, j) in fill for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1))} - fill
    for q in ring:
        pix[q] = 0x0A + 1
    return frame(pix)


def frame(pix):
    xs = [k[0] for k in pix]
    ys = [k[1] for k in pix]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    px = bytearray(w * h)
    for (x, y), v in pix.items():
        px[(y - y0) * w + x - x0] = v
    return (w, h, x0, y0, bytes(px))


def blank_tile():
    pix = {}
    for j in range(31):
        half = 32 - abs(j * 2 - 30)
        for i in range(-half, half):
            pix[(i, j)] = 0x0A
    return frame(pix)


def build():
    cat = json.loads(CATALOG.read_text())
    frames = []
    for e in cat["entries"]:
        n = e.get("name") or ""
        if n.startswith("construction_arrow"):
            frames.append((e["i"], arrow(e, 16)))
        elif n.startswith("one_way_direction_arrow"):
            frames.append((e["i"], arrow(e, 11)))
        elif n == "blank_tile":
            frames.append((e["i"], blank_tile()))
    return frames


def main() -> int:
    frames = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    pal = dat.load_palette()
    meta = []
    for idx, (w, h, x, y, px) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, w, h, px, bytes(255 if v else 0 for v in px), pal)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"寫出 {len(frames)} 張 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
