#!/usr/bin/env python3
"""g1 的特效動畫（ROADMAP M4）：煙團、爆炸煙、爆炸雲、火球、水花、撞車碎片。輸出 base/g1/effects/。

  .venv/bin/python tools/gen/g1_effects.py [--sheet build/preview/g1_effects.png]

繪製（OpenLoco Paint/PaintEffectEntity.cpp）：各動畫依 particle->frame / 256 逐格取圖，原點 = 粒子位置。
- smoke（12 格）：灰色煙團逐漸變大、變淡（抖色淡出）。
- explosion_smoke（10 格）：深灰色大團濃煙，向上翻騰。
- explosion_cloud（18 格）：亮黃→橘紅的火球迅速擴大，之後轉為貼地擴散的灰煙。
- fireball（31 格）：火球升空（最高約 70 px），先變大再縮成火星。
- splash（28 格）：車輛落水的水柱：先往上衝高，再向外散開落下。
- vehicle_crash_0–4（各 12 格）：撞車時飛散、翻滾的碎片（以車輛的公司色換色 → primary／secondary remap 色號）。
road_hit_test_*：OpenLoco 沒有引用 → 1×1 透明。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import g1_title  # noqa: E402  （調色盤量化 q()）

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "effects"
q = g1_title.q
PRIMARY = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
SECONDARY = list(range(0xCA, 0xD6))
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]


def puffs(blobs, colour_at, density=1.0):
    """blobs：[(cx, cy, r)]（畫面座標）；colour_at(nx, ny, t) → RGB，t = 0（中心）–1（邊緣），nx/ny = 法線（光照）。
    density < 1 時以 Bayer 抖色讓部分像素透明（煙逐漸消散）。"""
    pix = {}
    for (cx, cy, r) in blobs:
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                d = math.hypot(dx, dy)
                if d > r:
                    continue
                if density < 1 and (BAYER[(y % 4) * 4 + (x % 4)] + 0.5) / 16 > density:
                    continue
                t = d / max(r, 0.01)
                nz = math.sqrt(max(0.0, 1 - t * t))
                pix[(x, y)] = colour_at(dx / max(r, 0.01), dy / max(r, 0.01), nz)
    return pix


def lit(base, nx, ny, nz, amb=0.45):
    l = max(0.0, -0.5 * nx - 0.6 * ny + 0.62 * nz)
    k = amb + (1 - amb) * l
    return q(tuple(c * k for c in base))


def frame(pix):
    if not pix:
        return (1, 1, 0, 0, bytes(1))
    xs = [k[0] for k in pix]
    ys = [k[1] for k in pix]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    px = bytearray(w * h)
    for (x, y), v in pix.items():
        px[(y - y0) * w + x - x0] = v
    return (w, h, x0, y0, bytes(px))


def smoke(k, n=12):
    t = k / (n - 1)
    r = 1.6 + 8.5 * t
    rng = random.Random(11)
    blobs = [(0, -r * 0.3, r)] + [(rng.uniform(-r, r) * 0.6, -r * 0.3 + rng.uniform(-r, r) * 0.4, r * 0.6) for _ in range(int(2 + 3 * t))]
    grey = 210 - 40 * t
    return frame(puffs(blobs, lambda nx, ny, nz: lit((grey, grey, grey + 5), nx, ny, nz, 0.6), density=1.0 - 0.6 * t))


def explosion_smoke(k, n=10):
    t = k / (n - 1)
    rng = random.Random(23)
    blobs = []
    for b in range(9):
        a = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(0, 12) * (0.4 + t)
        blobs.append((math.cos(a) * dist, -8 - 14 * t + math.sin(a) * dist * 0.6 - b * 1.2 * t, 7 + 9 * t * rng.uniform(0.7, 1.2)))
    return frame(puffs(blobs, lambda nx, ny, nz: lit((70 + 50 * t, 68 + 50 * t, 66 + 50 * t), nx, ny, nz, 0.5),
                       density=1.0 - 0.55 * max(0, t - 0.3)))


def explosion_cloud(k, n=18):
    t = k / (n - 1)
    rng = random.Random(37)
    R = 6 + 34 * (1 - (1 - t) ** 2)
    blobs = []
    for b in range(12):
        a = rng.uniform(0, 2 * math.pi)
        d = rng.uniform(0.2, 0.75) * R
        blobs.append((math.cos(a) * d, math.sin(a) * d * 0.55 - 4 * t, R * rng.uniform(0.35, 0.55)))
    hot = max(0.0, 1 - t * 1.4)                                 # 前段是火焰，後段轉為煙（中間幾格內核仍有火光）

    fire = [0xA6 + 6, 0xB2 + 6, 0xB2 + 8, 0x2E + 8, 0x2E + 10, 0x2E + 11]   # 由外到內：紅、橘、黃、亮黃（自發光，不打光）

    smoke_from = max(0.0, min(1.0, (0.6 - hot) / 0.6))          # 熱度降低時，煙從外緣往中心擴大

    def col(nx, ny, nz):
        if nz > smoke_from:
            heat = nz * (0.4 + 0.6 * hot) + 0.15 * (-nx - ny)
            k = max(0, min(len(fire) - 1, int(heat * len(fire))))
            return fire[k]
        return lit((95, 92, 90), nx, ny, nz, 0.5)
    return frame(puffs(blobs, col, density=1.0 - 0.5 * max(0, t - 0.55) / 0.45))


def fireball(k, n=31):
    t = k / (n - 1)
    rise = 72 * (1 - (1 - t) ** 1.6)
    size = 4 + 12 * math.sin(math.pi * min(1, t * 1.6)) if t < 0.62 else max(0.6, 5 * (1 - t) / 0.38)
    rng = random.Random(41 + k)
    blobs = [(0, -rise, size)] + [(rng.uniform(-1, 1) * size * 0.5, -rise + rng.uniform(-1, 1) * size * 0.4, size * 0.55)
                                  for _ in range(3 if size > 3 else 0)]
    heat = 1 - t

    def col(nx, ny, nz):
        return q((255, 140 + 110 * nz * heat, 30 + 160 * nz * heat * heat))
    pix = puffs(blobs, col)
    if t > 0.3:                                                 # 拖曳的煙
        for j in range(4):
            yy = -rise + size + 3 + j * 4
            pix.update(puffs([(rng.uniform(-1, 1), yy, 1.5 + j * 0.6)], lambda nx, ny, nz: lit((120, 115, 110), nx, ny, nz), 0.6))
    return frame(pix)


def splash(k, n=28):
    t = k / (n - 1)
    rng = random.Random(53)
    pix = {}
    up = 46 * math.sin(math.pi * min(1.0, t / 0.6)) if t < 0.6 else 46 * max(0.0, 1 - (t - 0.6) / 0.4) * 0.5
    spread = 4 + 26 * t
    drops = []
    for b in range(40):
        a = rng.uniform(-1, 1)
        hgt = up * rng.uniform(0.3, 1.0) * (1 - abs(a) * 0.5)
        drops.append((a * spread, -hgt, rng.uniform(1.2, 3.2) * (1 - 0.4 * t)))
    for b in range(10):                                         # 水面的波紋
        a = b / 10 * 2 * math.pi
        drops.append((math.cos(a) * spread * 0.9, math.sin(a) * spread * 0.35, 1.5))
    return frame(puffs(drops, lambda nx, ny, nz: lit((215, 235, 250), nx, ny, nz, 0.7), density=1.0 - 0.5 * max(0, t - 0.6) / 0.4))


def debris(kind, k):
    """撞車碎片：形狀依 kind，隨 k 翻滾（2D 旋轉 + 透視壓扁）。"""
    a = 2 * math.pi * k / 12
    c, s = math.cos(a), math.sin(a)
    squash = 0.55 + 0.45 * abs(math.cos(a * 0.5 + kind))
    shapes = {
        0: ([(-3, -2), (3, -2), (3, 2), (-3, 2)], PRIMARY[7], PRIMARY[4]),          # 車身板
        1: ([(-4, -1), (4, -1), (4, 1), (-4, 1)], SECONDARY[7], SECONDARY[4]),       # 長條飾板
        2: (None, 0x0A + 2, 0x0A + 6),                                               # 車輪
        3: ([(-5, -0.8), (5, -0.8), (5, 0.8), (-5, 0.8)], 0x0A + 7, 0x0A + 3),       # 金屬桿
        4: ([(-3, -3), (2, -3), (3, 1), (0, 3), (-3, 1)], PRIMARY[5], 0x0A + 2),     # 碎塊
    }
    poly, fill, edge = shapes[kind]
    pix = {}
    if poly is None:
        rx, ry = 3.6 * abs(c) + 1.2, 3.6
        for y in range(-5, 6):
            for x in range(-5, 6):
                d = (x / rx) ** 2 + (y / ry) ** 2
                if d <= 1:
                    pix[(x, y)] = edge if d > 0.45 else fill
        return frame(pix)
    pts = [(x * c - y * s, (x * s + y * c) * squash) for x, y in poly]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for y in range(math.floor(min(ys)) - 1, math.ceil(max(ys)) + 1):
        for x in range(math.floor(min(xs)) - 1, math.ceil(max(xs)) + 1):
            inside = False
            for i in range(len(pts)):
                (x1, y1), (x2, y2) = pts[i], pts[i - 1]
                if (y1 > y + 0.5) != (y2 > y + 0.5) and x + 0.5 < (x2 - x1) * (y + 0.5 - y1) / (y2 - y1) + x1:
                    inside = not inside
            if inside:
                pix[(x, y)] = fill
    for (x, y) in list(pix):
        if any((x + a, y + b) not in pix for a, b in ((1, 0), (0, 1))):
            pix[(x, y)] = edge
    return frame(pix)


def build():
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e["i"] for e in cat["entries"] if e.get("name")}
    frames = []
    for k in range(12):
        frames.append((ids[f"smoke_{k:02d}"], smoke(k)))
        for kind in range(5):
            frames.append((ids[f"vehicle_crash_{kind}_{k:02d}"], debris(kind, k)))
    for k in range(10):
        frames.append((ids[f"explosion_smoke_{k:02d}"], explosion_smoke(k)))
    for k in range(18):
        frames.append((ids[f"explosion_cloud_{k:02d}"], explosion_cloud(k)))
    for k in range(31):
        frames.append((ids[f"fireball_{k:02d}"], fireball(k)))
    for k in range(28):
        frames.append((ids[f"splash_{k:02d}"], splash(k)))
    for e in cat["entries"]:
        if (e.get("name") or "").startswith("road_hit_test"):
            frames.append((e["i"], (1, 1, 0, 0, bytes(1))))
    return frames


def sheet(path, frames):
    from PIL import Image
    pal = dat.load_palette()
    cat = json.loads(CATALOG.read_text())
    names = {e["i"]: e.get("name") or "" for e in cat["entries"]}
    rows = {}
    for idx, f in sorted(frames):
        key = names[idx].rsplit("_", 1)[0]
        rows.setdefault(key, []).append(f)
    im = Image.new("RGB", (32 * 82, len(rows) * 100), (70, 100, 80))
    for r, (key, fs) in enumerate(rows.items()):
        for k, (w, h, x, y, px) in enumerate(fs):
            ox, oy = k * 82 + 41, r * 100 + (88 if key in ("fireball", "splash") else 55)
            for j in range(h):
                for i in range(w):
                    v = px[j * w + i]
                    if v and 0 <= ox + x + i < im.width and 0 <= oy + y + j < im.height:
                        im.putpixel((ox + x + i, oy + y + j), pal[v])
    im.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(REPO / "build" / "preview" / "g1_effects.png"))
    args = ap.parse_args()
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
    sheet(args.sheet, frames)
    print(f"寫出 {len(frames)} 張 → {OUT}；預覽 {args.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
