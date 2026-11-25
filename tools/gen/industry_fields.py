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
import numpy as np
import tree3d

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
    u = (Y if a == 0 else X) % 4.0                            # 壟：每 4 單位一條清晰立體耕壟
    v_along = (X if a == 0 else Y)
    # 立體壟面光影：向陽坡（u ≈ 0.8）最亮、壟溝（u ≈ 3.1）深陰影，對照原版農田的清晰條紋質感
    ridge_wave = math.sin((u / 4.0) * 2.0 * math.pi + 0.35)   # +1 壟脊、-1 壟溝
    furrow = u >= 2.55                                        # 壟溝底帶
    light = 2.4 * (t - 0.5)
    # 沿壟方向微幅斑駁，避免完全機械的直線
    patch = 0.45 * math.sin(v_along * 0.55 + (X + Y) * 0.22)
    if style in ("wheat", "maize"):
        soil_v = 3.2 + light + 1.55 * ridge_wave + patch * 0.5 + rng.uniform(-0.55, 0.55)
        soil = shade(BROWN, soil_v)
        if g == 0:                                            # 剛翻的土：立體明暗土壟
            return shade(BROWN, 3.0 + light + 1.75 * ridge_wave + rng.uniform(-0.55, 0.55))
        if g == 7:                                            # 收割後的殘株：乾草褐黃＋深壟溝
            if furrow and rng.random() < 0.72:
                return shade(BROWN, 2.2 + light + rng.uniform(-0.5, 0.5))
            ramp = DKYEL if rng.random() < 0.7 else BROWN
            return shade(ramp, 4.4 + light + 1.45 * ridge_wave + rng.uniform(-0.7, 0.7))
        # 作物覆蓋隨成長階段從壟脊往壟溝擴張，壟溝始終保留陰影深度
        dens = {1: 0.36, 2: 0.68, 3: 0.90, 4: 0.97, 5: 0.98, 6: 0.98}[g]
        if furrow and g <= 3:
            if rng.random() > (0.12 if g == 1 else 0.25 if g == 2 else 0.45):
                return shade(BROWN, 1.8 + light + rng.uniform(-0.4, 0.4))
        elif furrow and rng.random() < 0.30:
            return shade(BROWN, 1.6 + light + rng.uniform(-0.4, 0.4))
        if rng.random() > dens:
            return soil
        if style == "wheat":
            if g == 1:
                ramp, base = OLIVE, 4.2
            elif g == 2:
                ramp, base = (OLIVE if rng.random() < 0.5 else GRASS), 4.0
            elif g == 3:
                ramp, base = GRASS, 4.0
            elif g == 4:
                ramp, base = (GRASS if rng.random() < 0.75 else OLIVE), 4.3
            elif g == 5:                                      # 抽穗轉黃：橄欖黃＋暗黃交錯
                ramp, base = (DKYEL if rng.random() < 0.55 else OLIVE), 5.0
            else:                                             # 成熟金黃麥田：溫潤暗黃與稻草棕（避免螢光黃）
                r = rng.random()
                ramp, base = (DKYEL, 6.2) if r < 0.68 else ((BROWN, 6.2) if r < 0.88 else (YELLOW, 5.2))
        else:
            if g in (1, 2):
                ramp, base = OLIVE, 4.0
            elif g in (3, 4):
                ramp, base = GRASS, 4.2
            elif g == 5:
                ramp, base = (GRASS if rng.random() < 0.6 else OLIVE), 3.8
            else:                                             # 成熟玉米：深橄欖與金褐交錯
                ramp, base = (DKYEL if rng.random() < 0.65 else BROWN), 5.5
        return shade(ramp, base + light + 1.55 * ridge_wave + patch + rng.uniform(-0.85, 0.85))
    if style == "vines":
        if not furrow and rng.random() < 0.86 and (math.sin(v_along * 1.45) > -0.35):
            if g == 1 and rng.random() < 0.20:
                return shade(MPURPLE, 3.0 + light * 0.6 + rng.uniform(-0.8, 0.8))
            return shade(GRASS, 3.8 + light + 1.3 * ridge_wave + rng.uniform(-0.9, 0.9))
        return shade(BROWN, 3.0 + light + 1.2 * ridge_wave + rng.uniform(-0.55, 0.55))
    if style == "pasture":
        ramp = GRASS if (g < 2 or rng.random() < 0.55) else OLIVE
        return shade(ramp, 4.0 + light + 0.5 * patch + rng.uniform(-1.0, 1.0))
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
    """林場的樹：階段 0–5 為成長中的冷杉（使用 tree3d 點雲算圖，與地圖上的針葉樹色調一致），階段 6 為砍伐後的樹樁。"""
    w, h = e.width, e.height
    rng = random.Random(seed)
    if g >= 6 or h < 20:
        px = bytearray(w * h)
        cx, cy = w / 2.0, h / 2.0
        for y in range(h):
            for x in range(w):
                dx, dy = (x - cx) / 2.8, (y - cy) / 2.0
                if dx * dx + dy * dy <= 1.0:
                    if snow and y <= cy:
                        px[y * w + x] = BLACK + (10 if x < cx else 9)
                    elif y < cy:
                        px[y * w + x] = BROWN + (7 if x < cx else 6)  # 樹樁切面
                    else:
                        px[y * w + x] = BROWN + (4 if x < cx else 2)  # 樹皮側面
        for _ in range(3):                                            # 散落的木屑與針葉
            x, y = rng.randrange(w), rng.randrange(h // 2, h)
            if not px[y * w + x]:
                px[y * w + x] = BROWN + 4 if rng.random() < 0.5 else OLIVE + 3
        return bytes(px)
    # 樹幹底部放在圖塊中央（sy ≈ +14，對應 h - 4；與原版林場圖塊與階段 6 樹樁位置一致）
    ox = -e.x_offset
    oy = max(-e.y_offset, h - 4)
    H = max(14.0, (h - 6) * (0.64 + 0.32 * g / 5))
    cfg = dict(tree3d.SPECIES["grandfir"], whorls=9 + 2 * (g >= 2) + 2 * (g >= 4), width=0.84 + 0.04 * g)
    cloud = tree3d.make_cloud(cfg, 3, H, seed, snow)
    p, *_ = cloud.arrays()
    if len(p):
        sx, sy = tree3d.project(p)
        half = max(3.0, min(ox, w - ox) - 1.5)
        fx = min(1.0, half / max(float(np.abs(sx).max()), 1e-6))
        top_room = max(6.0, oy - 1.5)
        fz = min(1.0, top_room / max(float(-sy.min()), 1e-6))
        if fx < 1.0 or fz < 1.0:
            cloud = tree3d.scale_cloud(cloud, fx, fz)
    return tree3d.render(cloud, w, h, ox, oy).tobytes()


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
