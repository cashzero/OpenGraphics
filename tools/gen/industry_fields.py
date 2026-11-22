#!/usr/bin/env python3
"""產業的田地／地面圖塊（industry 物件 fieldImageIds 之後的影像），接在部件影像後面。

影像順序（OpenLoco Paint/PaintSurface.cpp）：成長階段 g × 角度 a × 21 張；21 張 = 19 種坡度地面 + 樹 + 積雪樹。
  image = fieldImageIds + g × (角度數 × 21) + a × 21 + 坡度（0–18）；19／20 每個產業圖塊都會畫（只有林場是真的樹）。
坡度圖塊的輪廓與明暗取自上游 OG 地形物件 OG_GRASS1（image 285–303，尺寸／偏移與 vanilla 相同），再疊上材質紋理。
紋理座標：畫面 (sx, sy) 以平地近似換回世界座標 X = sy - sx/2、Y = sy + sx/2（坡地會有輕微變形）。

  python3 tools/gen/industry_fields.py --template <產業模板.DAT> --style <樣式> --append-to <sprites 資料夾>

樣式：wheat、maize（8 階段作物）、pasture（牧草 + 牲畜）、vines（葡萄藤）、ski（滑雪道）、forest（林地 + 成長中的樹）、
以及單純地面 concrete、pavement、gravel、dirt、ore、coal、grass、snow、woodchips。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

import common
import tree

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SHAPES = REPO / "objects" / "VanillaReplacements" / "Land" / "GRASS1" / "OG_GRASS1.dat"
SHAPE_START = 285
BLACK, OLIVE, DKYEL, YELLOW, GRASS, AVOCADO, GREEN = 0x0A, 0x16, 0x22, 0x2E, 0x46, 0x52, 0x5E
MORANGE, MPURPLE, BLUE, RED, ORANGE, BROWN = 0x6A, 0x76, 0x82, 0xA6, 0xB2, 0xD6
PLAIN = {  # 樣式: (色階, 最暗, 最亮, 雜點機率)
    "concrete": (BLACK, 4, 8, 0.05), "pavement": (BLACK, 5, 9, 0.04), "gravel": (BLACK, 3, 8, 0.25),
    "dirt": (BROWN, 2, 7, 0.2), "ore": (MORANGE, 1, 5, 0.25), "coal": (BLACK, 0, 5, 0.25), "grass": (GRASS, 3, 8, 0.15),
    "snow": (BLACK, 8, 11, 0.03), "woodchips": (BROWN, 4, 9, 0.3),
}


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def shade(ramp, v):
    return ramp + int(max(0, min(11, round(v))))


def crop_pixel(style, g, a, X, Y, t, rng):
    """回傳單一像素色號。t = 坡面明暗（0 暗 – 1 亮），X/Y = 世界座標（0–32）。"""
    u = (Y if a == 0 else X) % 4.0                            # 壟：每 4 單位一行
    row = u < 2.2
    light = 2.5 * (t - 0.5)
    if style in ("wheat", "maize"):
        soil = shade(BROWN, 3 + light + (1.2 if not row else 0) + rng.uniform(-0.6, 0.6))
        if g == 0:                                            # 剛翻的土
            return shade(BROWN, (2.5 if row else 4.5) + light + rng.uniform(-0.6, 0.6))
        if g == 7:                                            # 收割後的殘株
            return shade(DKYEL, (5 if row else 3.5) + light + rng.uniform(-0.8, 0.8))
        dens = {1: 0.25, 2: 0.55, 3: 0.85, 4: 1.0, 5: 1.0, 6: 1.0}[g]
        cover = row or g >= 4
        if not cover or rng.random() > dens:
            return soil
        if style == "wheat":
            ramp = {1: GREEN, 2: GREEN, 3: GREEN, 4: GRASS, 5: AVOCADO, 6: YELLOW}[g]
            base = {1: 6, 2: 6, 3: 5, 4: 6, 5: 7, 6: 7}[g]
        else:
            ramp = {1: GREEN, 2: GREEN, 3: GRASS, 4: GRASS, 5: GRASS, 6: DKYEL}[g]
            base = {1: 6, 2: 6, 3: 6, 4: 5, 5: 4, 6: 6}[g]
        return shade(ramp, base + light + (0.8 if row else -0.8) + rng.uniform(-1, 1))
    if style == "vines":
        if row and rng.random() < 0.85 and (math.sin((X if a == 0 else Y) * 1.6) > -0.3):
            if g == 1 and rng.random() < 0.18:
                return shade(MPURPLE, 3 + rng.uniform(-1, 1))
            return shade(GRASS, 4.5 + light + rng.uniform(-1, 1))
        return shade(BROWN, 4 + light + rng.uniform(-0.6, 0.6))
    if style == "pasture":
        ramp = GRASS if g < 2 else AVOCADO
        return shade(ramp, 5 + light + rng.uniform(-1.2, 1.2))
    if style == "ski":
        trail = abs(((X + Y * (0.6 if a % 2 else -0.6)) + a * 7) % 10 - 5) < 0.6
        return shade(BLACK, (9 if trail else 10.5) + light * 0.6 + rng.uniform(-0.4, 0.4))
    if style == "forest":
        if rng.random() < 0.25:
            return shade(BROWN, 3 + light + rng.uniform(-1, 1))
        return shade(GRASS, 2.5 + light + rng.uniform(-1, 1))
    ramp, lo, hi, speck = PLAIN[style]
    v = lo + t * (hi - lo) + rng.uniform(-0.5, 0.5)
    if rng.random() < speck:
        v += rng.choice((-2, 2))
    return shade(ramp, max(lo - 1, min(hi + 1, v)))


ANIMALS = {0: [("cow", 7, 9), ("cow", 22, 14)], 1: [("cow", 8, 20), ("sheep", 18, 8), ("cow", 24, 24), ("sheep", 12, 12)],
           2: [("sheep", 10, 18), ("cow", 20, 10), ("sheep", 25, 22)]}


def draw_animals(px, w, h, xo, yo, g, a):
    """牧場：在平面上畫幾隻小牲畜（3–4 px）＋影子；角度 a 改變站位。"""
    for kind, X, Y in ANIMALS[g]:
        X, Y = (X + a * 6) % 28 + 2, (Y + a * 9) % 28 + 2
        sx, sy = Y - X, (X + Y) / 2
        i, j = int(round(sx - xo)), int(round(sy - yo))
        body = [(0, 0), (1, 0), (2, 0), (0, -1), (1, -1), (2, -1)] if kind == "cow" else [(0, 0), (1, 0), (0, -1), (1, -1)]
        col = (BLACK + 11, BLACK + 1) if kind == "cow" else (BLACK + 10, BLACK + 9)
        for k, (di, dj) in enumerate([(d[0] + 1, d[1] + 1) for d in body]):
            if 0 <= i + di < w and 0 <= j + dj < h and px[(j + dj) * w + i + di]:
                px[(j + dj) * w + i + di] = GRASS + 1                  # 影子
        for k, (di, dj) in enumerate(body):
            if 0 <= i + di < w and 0 <= j + dj < h and px[(j + dj) * w + i + di]:
                px[(j + dj) * w + i + di] = col[1] if (kind == "cow" and k in (2, 3)) else col[0]
        hi, hj = i - 1, j - 1                                          # 頭
        if 0 <= hi < w and 0 <= hj < h and px[hj * w + hi]:
            px[hj * w + hi] = BLACK + 2 if kind == "sheep" else BLACK + 10


def forest_tree(e, g, snow, seed):
    """林場的樹：階段 0–5 為成長中的冷杉，階段 6 為砍伐後的樹樁。"""
    w, h, ox, oy = e.width, e.height, -e.x_offset, -e.y_offset
    rng = random.Random(seed)
    if g >= 6 or h < 20:
        px = bytearray(w * h)
        for y in range(h):
            for x in range(w):
                if ((x - ox) / 2.5) ** 2 + ((y - oy + 1) / 1.6) ** 2 <= 1:
                    px[y * w + x] = BROWN + (7 if y < oy - 1 else 4)
        for k in range(3):                                            # 散落的枝葉
            x, y = rng.randrange(w), rng.randrange(h // 2, h)
            px[y * w + x] = GRASS + 3
        return bytes(px)
    return tree.draw_preset(tree.PRESETS["grandfir"], w, h, ox, oy, 3, rng, snow)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", required=True)
    ap.add_argument("--append-to", required=True)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    obj = dat.read_dat(args.template)
    sys.path.insert(0, str(REPO / "tools"))
    import objinfo
    info = objinfo.industry(obj)
    entries = obj.image_table().entries
    start = info["first_part_image"] + len(info["heights"]) * 4
    fields = entries[start:]
    angles = obj.data[0xE9]
    if not fields:
        print("這個產業沒有田地圖塊")
        return 0
    stages = len(fields) // (21 * angles)
    if stages * 21 * angles != len(fields):
        raise SystemExit(f"田地圖塊數 {len(fields)} 不是 21 × 角度 {angles} 的倍數")
    shapes = dat.read_dat(SHAPES).image_table()
    out = Path(args.append_to)
    meta = json.loads((out / "sprites.json").read_text())
    base_n = len(meta)
    rng = random.Random(args.seed)
    for k, fe in enumerate(fields):
        g, rest = divmod(k, 21 * angles)
        a, s = divmod(rest, 21)
        if s < 19:
            w, h, x, y, spx, al = dat.decode_sprite(shapes, SHAPE_START + s, True)
            ls = [lum(common.PALETTE[spx[i]]) for i in range(w * h) if al[i]]
            mn, mx = (min(ls), max(ls)) if ls else (0, 1)
            px = bytearray(w * h)
            for j in range(h):
                for i in range(w):
                    if not al[j * w + i]:
                        continue
                    t = (lum(common.PALETTE[spx[j * w + i]]) - mn) / max(mx - mn, 1)
                    sx, sy = i + x, j + y
                    X, Y = sy - sx / 2, sy + sx / 2
                    px[j * w + i] = crop_pixel(args.style, g, a, X, Y, t, rng)
            if args.style == "pasture":
                draw_animals(px, w, h, x, y, g, a)
        elif args.style == "forest":
            w, h, x, y = fe.width, fe.height, fe.x_offset, fe.y_offset
            px = bytearray(forest_tree(fe, g, s == 20, args.seed * 100 + g))
        else:
            w, h, x, y = fe.width, fe.height, fe.x_offset, fe.y_offset
            px = bytearray(w * h)
        fn = f"{base_n + k}.png"
        dat.write_indexed_png(out / fn, w, h, bytes(px), bytes(255 if v else 0 for v in px), common.PALETTE)
        meta.append({"path": fn, "x": x, "y": y, "zoomOffset": 0, "flags": 0, "name": None})
    (out / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"加上 {len(fields)} 張田地圖塊（{args.style}，{stages} 階段 × {angles} 角度）→ {out}（共 {len(meta)} 張）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
