#!/usr/bin/env python3
"""程序化樹木（tree 物件）。依模板的結構（旋轉數、成長階段、季節組、積雪、陰影）與每張 sprite 的尺寸／偏移，
畫出新的像素樹。

  python3 tools/gen/tree.py --template <模板.DAT> --style deciduous|conifer|palm|cactus \\
      [--leaf green|darkgreen|birch] --seed 1 -o <資料夾>

影像順序（OpenLoco Objects/TreeObject.cpp）：季節組（var_3C 的位元：0 秋、1 冬（光禿）、2 春、3 夏、4 枯萎）
→ 每組 成長階段 × 旋轉數；有積雪旗標時接一份積雪版；有陰影旗標時再接全部影像的陰影。
樹幹底部位於繪製原點（-xOffset, -yOffset）。
"""
from __future__ import annotations

import argparse
import math
import random
import struct
import sys
from pathlib import Path

import common

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

# 調色盤色階起點（Graphics/Colour.h）
GREEN, DARKGREEN, AVOCADO, OLIVE = 0x5E, 0x46, 0x52, 0x16
ORANGE, RED, YELLOW, BROWN, GREY = 0xB2, 0xA6, 0x2E, 0xD6, 0x0A
LEAF = {
    "green": GREEN, "darkgreen": DARKGREEN, "birch": AVOCADO,
}
SEASON_COLOURS = {  # 季節位元 → (葉色階, 葉量)
    0: (ORANGE, 0.85),   # 秋
    1: (None, 0.0),      # 冬：光禿
    2: (None, 0.55),     # 春：較淡較疏（用 avocado）
    3: (None, 1.0),      # 夏：滿葉
    4: (None, 0.0),      # 枯萎：光禿、偏灰
}


def put(px, w, h, x, y, c):
    if 0 <= x < w and 0 <= y < h:
        px[y * w + x] = c


def trunk(px, w, h, ox, oy, top, rng, colour=BROWN):
    width = 1 if w < 30 else 2
    for y in range(max(top, 0), min(oy + 1, h)):
        for k in range(width):
            put(px, w, h, ox + k, y, colour + (3 if k == 0 else 5))


def branches(px, w, h, x, y, ang, length, depth, rng, colour):
    if depth == 0 or length < 2:
        return
    x2 = x + math.cos(ang) * length
    y2 = y - math.sin(ang) * length
    steps = int(max(abs(x2 - x), abs(y2 - y))) + 1
    for s in range(steps + 1):
        t = s / max(steps, 1)
        put(px, w, h, int(round(x + (x2 - x) * t)), int(round(y + (y2 - y) * t)), colour + (2 if depth > 2 else 4))
    for _ in range(2):
        branches(px, w, h, x2, y2, ang + rng.uniform(-0.7, 0.7), length * rng.uniform(0.55, 0.75), depth - 1, rng, colour)


def crown_blob(px, w, h, cx, cy, rx, ry, ramp, density, rng):
    """以多個小圓團組成樹冠，光源在左上。"""
    blobs = [(cx + rng.uniform(-0.55, 0.55) * rx, cy + rng.uniform(-0.55, 0.55) * ry, rng.uniform(0.45, 0.7))
             for _ in range(9)]
    for y in range(h):
        for x in range(w):
            inside = False
            for bx, by, r in blobs:
                if ((x - bx) / (rx * r)) ** 2 + ((y - by) / (ry * r)) ** 2 <= 1:
                    inside = True
                    break
            if not inside or rng.random() > density:
                continue
            light = -((x - cx) / rx) * 0.35 - ((y - cy) / ry) * 0.55
            shade = 6 + light * 5 + rng.uniform(-1.6, 1.6)
            r = ramp
            if ramp == ORANGE:                      # 秋葉：橘、紅、黃混色
                r = rng.choice((ORANGE, ORANGE, RED, YELLOW))
            px[y * w + x] = r + int(max(1, min(11, round(shade))))


TRUNK = BROWN


def draw_tree(style, w, h, ox, oy, season, leaf, rng, snow=False):
    px = bytearray(w * h)
    if style == "cactus":
        col = GREEN
        top = max(0, oy - int(h * 0.95))
        half = max(1, w // 6)                             # 主幹寬度依 sprite 寬度
        for y in range(top, oy + 1):
            for k in range(-half, half + 1):
                put(px, w, h, ox + k, y, col + int(6 - 3 * k / max(half, 1)))
        for side in (-1, 1):
            arm_y = oy - int(h * rng.uniform(0.35, 0.6))
            arm_x = ox + side * max(2, w // 3)
            for x in range(min(ox, arm_x), max(ox, arm_x) + 1):
                put(px, w, h, x, arm_y, col + 5)
                put(px, w, h, x, arm_y + 1, col + 4)
            for y in range(arm_y - int(h * 0.3), arm_y + 1):
                put(px, w, h, arm_x, y, col + 7)
                put(px, w, h, arm_x + side, y, col + 5)
        return bytes(px)
    if style == "palm":
        top = max(0, oy - int(h * 0.75))
        for i, y in enumerate(range(top, oy + 1)):
            put(px, w, h, ox + int(math.sin(i / 6) * 1.5), y, BROWN + 5)
            put(px, w, h, ox + int(math.sin(i / 6) * 1.5) + 1, y, BROWN + 3)
        for k in range(7):
            ang = math.pi * (0.1 + 0.8 * k / 6) + rng.uniform(-0.1, 0.1)
            length = w * rng.uniform(0.35, 0.5)
            for s in range(int(length)):
                fx = ox + math.cos(ang) * s
                fy = top + 2 - math.sin(ang) * s * 0.5 + (s / length) ** 2 * h * 0.12
                width = max(1, int(3 * (1 - s / length)) + 1)     # 葉片根部較寬、末端較細
                for k in range(width):
                    put(px, w, h, int(fx), int(fy) + k, DARKGREEN + (rng.randint(6, 9) if k == 0 else rng.randint(3, 6)))
        return bytes(px)

    ramp_season, density = SEASON_COLOURS.get(season, (None, 1.0))
    bare = density == 0.0
    if style == "conifer":
        if bare:
            col = GREY if season == 4 else BROWN
            trunk(px, w, h, ox, oy, max(0, oy - h + 2), rng, col)
            for k in range(6):                      # 枯枝沿樹幹向兩側伸出
                by = oy - h * (0.3 + 0.1 * k)
                for side in (-1, 1):
                    branches(px, w, h, ox, by, math.pi / 2 + side * rng.uniform(0.9, 1.3), w * 0.18 * (1 - k / 8), 2, rng, col)
            return bytes(px)
        ramp = LEAF.get(leaf, DARKGREEN)
        trunk(px, w, h, ox, oy, oy - int(h * 0.25), rng)
        layers = 5
        for L in range(layers):
            frac = L / layers
            ly = int(oy - h * 0.18 - frac * h * 0.78)
            half = (w / 2) * (1 - frac * 0.8)
            for y in range(int(ly - h * 0.2), ly + 1):
                t = (ly - y) / (h * 0.2 + 1e-6)
                span = half * (1 - t)
                for x in range(int(ox - span), int(ox + span) + 1):
                    if rng.random() > 0.9:
                        continue
                    light = -((x - ox) / max(half, 1)) * 0.4 - t * 0.4
                    put(px, w, h, x, y, ramp + int(max(1, min(10, round(5 + light * 4 + rng.uniform(-1.2, 1.2))))))
        if snow:
            add_snow(px, w, h, rng)
        return bytes(px)

    # deciduous
    trunk_top = oy - int(h * 0.45)
    colour = GREY if season == 4 else TRUNK
    trunk(px, w, h, ox, oy, trunk_top, rng, colour)
    if bare:
        for k in range(4):
            branches(px, w, h, ox, trunk_top + 2, math.pi / 2 + rng.uniform(-0.8, 0.8), h * 0.28, 4, rng, colour)
    else:
        ramp = ramp_season or (AVOCADO if season == 2 else LEAF.get(leaf, GREEN))
        cx, cy = ox, oy - h * 0.58
        crown_blob(px, w, h, cx, cy, w * 0.48, h * 0.42, ramp, density, rng)
    if snow:
        add_snow(px, w, h, rng)
    return bytes(px)


# ---------------------------------------------------------------- M3：樹種 preset
# 其他色階（Graphics/Colour.h）
MUTED_DARK_RED, MUTED_DARK_YELLOW, MUTED_ORANGE = 0x3A, 0x22, 0x6A
MUTED_PURPLE, MUTED_SEA_GREEN, MUTED_TEAL = 0x76, 0x8E, 0xBE
RAMPS = {"green": GREEN, "darkgreen": DARKGREEN, "avocado": AVOCADO, "olive": OLIVE, "gold": YELLOW,
         "golden": MUTED_DARK_YELLOW, "copper": MUTED_DARK_RED, "seagreen": MUTED_SEA_GREEN, "teal": MUTED_TEAL}
AUTUMN = {"orange": (ORANGE, ORANGE, RED, YELLOW), "red": (RED, RED, ORANGE, MUTED_DARK_RED),
          "yellow": (YELLOW, YELLOW, MUTED_DARK_YELLOW, ORANGE), "rust": (ORANGE, MUTED_ORANGE, BROWN, MUTED_ORANGE),
          "copper": (MUTED_DARK_RED, BROWN, ORANGE, MUTED_DARK_RED)}
FLOWERS = {"white": (GREY, 10, 11), "pink": (MUTED_PURPLE, 8, 10), "red": (RED, 7, 9), "cream": (YELLOW, 9, 11)}

# preset：樹形 + 參數。crown = (寬占比, 高占比, 中心高度占比)；blobs = 樹冠圓團數；density = 葉量
PRESETS = {
    "chestnut": dict(shape="crown", leaf="darkgreen", crown=(0.50, 0.46, 0.60), blobs=12, autumn="orange", flowers="cream"),
    "elm": dict(shape="crown", leaf="green", crown=(0.44, 0.52, 0.58), blobs=11, autumn="yellow", trunk_h=0.5),
    "copperbeech": dict(shape="crown", leaf="copper", crown=(0.50, 0.44, 0.58), blobs=12, autumn="copper", spring="copper", bias=-2.5),
    "frisia": dict(shape="crown", leaf="gold", crown=(0.46, 0.46, 0.58), blobs=10, autumn="yellow", spring="gold", airy=0.85),
    "ash": dict(shape="crown", leaf="avocado", crown=(0.46, 0.44, 0.62), blobs=14, blob_r=(0.30, 0.48), autumn="yellow", airy=0.72),
    "robinia": dict(shape="crown", leaf="green", crown=(0.48, 0.42, 0.62), blobs=14, blob_r=(0.30, 0.50), autumn="yellow",
                    airy=0.78, flowers="white"),
    "maple": dict(shape="crown", leaf="green", crown=(0.50, 0.46, 0.57), blobs=12, autumn="orange"),
    "sugarmaple": dict(shape="crown", leaf="darkgreen", crown=(0.48, 0.48, 0.58), blobs=12, autumn="red"),
    "crab": dict(shape="crown", leaf="green", crown=(0.48, 0.40, 0.52), blobs=10, autumn="red", flowers="pink", trunk_h=0.35),
    "snowbell": dict(shape="crown", leaf="avocado", crown=(0.50, 0.42, 0.55), blobs=10, autumn="yellow", flowers="white", trunk_h=0.38),
    "birch2": dict(shape="crown", leaf="avocado", crown=(0.36, 0.50, 0.62), blobs=10, blob_r=(0.32, 0.5), autumn="yellow",
                   airy=0.75, trunk="light"),
    "strawberry": dict(shape="crown", leaf="darkgreen", crown=(0.50, 0.50, 0.50), blobs=12, evergreen=True, fruit=RED, trunk_h=0.25),
    "yew": dict(shape="crown", leaf="darkgreen", crown=(0.50, 0.55, 0.50), blobs=14, evergreen=True, trunk_h=0.2, bias=-1.5),
    "redwood": dict(shape="cone", leaf="green", autumn="rust", width=0.95),
    "pondcypress": dict(shape="cone", leaf="avocado", autumn="rust", width=0.8),
    "swampcypress": dict(shape="cone", leaf="green", autumn="rust", width=1.0, airy=0.85),
    "willow": dict(shape="weeping", leaf="avocado", autumn="yellow"),
    "bluespruce": dict(shape="conifer", leaf="seagreen", layers=6, width=1.0),
    "grandfir": dict(shape="conifer", leaf="darkgreen", layers=5, width=1.0),
    "borisfir": dict(shape="conifer", leaf="green", layers=7, width=0.9),
    "redcedar": dict(shape="conifer", leaf="darkgreen", layers=8, width=0.75, trunk="red"),
    "silverpine": dict(shape="pine", leaf="darkgreen"),
    "cedar": dict(shape="tiered", leaf="darkgreen"),
    "italiancypress": dict(shape="column", leaf="darkgreen", width=0.55),
    "irishyew": dict(shape="column", leaf="darkgreen", width=0.8, bias=-1.5),
    "hinoki": dict(shape="column", leaf="avocado", width=0.9, spring="gold"),
    "silverpalm": dict(shape="palm", leaf="seagreen"),
    "joshua": dict(shape="joshua", leaf="olive"),
    "yucca": dict(shape="yucca", leaf="seagreen"),
    "barrel": dict(shape="barrel", leaf="green"),
    "pricklypear": dict(shape="pear", leaf="avocado"),
}


def shade(ramp, value):
    return ramp + int(max(1, min(11, round(value))))


def blobs_crown(px, w, h, cx, cy, rx, ry, colour_of, density, rng, n=9, blob_r=(0.45, 0.7)):
    """多個圓團組成的樹冠；colour_of(x, y, light) 回傳像素色（或 0 = 不畫）。
    整個樹冠限制在畫布內的橢圓外框裡（避免碰到畫布邊緣被切成方形）。"""
    rx = min(rx, w / 2 - 1.0)
    top = cy - ry
    if top < 1:                                       # 往下移／壓扁，讓頂端留 1 px
        ry = max(2.0, ry - (1 - top) / 2)
        cy = 1 + ry
    blobs = [(cx + rng.uniform(-0.45, 0.45) * rx, cy + rng.uniform(-0.45, 0.45) * ry, rng.uniform(*blob_r)) for _ in range(n)]
    for y in range(max(0, int(cy - ry) - 1), min(h, int(cy + ry) + 2)):
        for x in range(max(0, int(cx - rx) - 1), min(w, int(cx + rx) + 2)):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 > 1.0 + rng.uniform(-0.08, 0.04):
                continue
            best = None
            for bx, by, r in blobs:
                d = ((x - bx) / (rx * r)) ** 2 + ((y - by) / (ry * r)) ** 2
                if d <= 1 and (best is None or d < best[0]):
                    best = (d, bx, by)
            if best is None or rng.random() > density:
                continue
            d, bx, by = best
            # 整體光源左上 + 每個圓團自己的立體感
            light = -((x - cx) / rx) * 0.30 - ((y - cy) / ry) * 0.45 - ((x - bx) / rx + (y - by) / ry) * 0.6 + (0.5 - d) * 0.6
            c = colour_of(x, y, 6 + light * 4 + rng.uniform(-1.3, 1.3))
            if c:
                px[y * w + x] = c


def line(px, w, h, x0, y0, x1, y1, c, width=1):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for s in range(steps + 1):
        t = s / max(steps, 1)
        x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        for k in range(width):
            put(px, w, h, int(round(x)) + k, int(round(y)), c)


def season_look(cfg, season):
    """回傳 (葉色函式產生器需要的資訊)：ramp 或 autumn 混色、葉量、是否開花。"""
    leaf = RAMPS[cfg.get("leaf", "green")]
    if season == 4:
        return None, 0.0, False
    if cfg.get("evergreen"):
        return ([leaf], 1.0 if season != 1 else 0.92, False)
    if season == 1:
        return None, 0.0, False
    if season == 0:
        return (list(AUTUMN[cfg.get("autumn", "orange")]), 0.82, False)
    if season == 2:
        spring = RAMPS[cfg["spring"]] if "spring" in cfg else AVOCADO
        return ([spring], 0.6, bool(cfg.get("flowers")))
    return ([leaf], 1.0, False)


def draw_preset(cfg, w, h, ox, oy, season, rng, snow=False):
    px = bytearray(w * h)
    shape = cfg["shape"]
    look = season_look(cfg, season)
    ramps, density, flowering = look
    airy = cfg.get("airy", 1.0)
    trunk_col = {"brown": BROWN, "light": GREY + 4, "red": MUTED_DARK_RED, "dark": BROWN - 0}[cfg.get("trunk", "brown")]
    if season == 4:
        trunk_col = GREY

    bias = cfg.get("bias", 0.0)

    def leaf_colour(x, y, v):
        r = rng.choice(ramps) if len(ramps) > 1 else ramps[0]
        return shade(r, v + (bias if r == RAMPS[cfg.get("leaf", "green")] or season == 2 else 0))

    if shape == "crown":
        cw, ch, ccy = cfg["crown"]
        th = cfg.get("trunk_h", 0.45)
        trunk_top = oy - int(h * th)
        trunk(px, w, h, ox, oy, trunk_top, rng, trunk_col)
        if ramps is None:                              # 光禿：分枝
            for k in range(5):
                branches(px, w, h, ox, trunk_top + 2, math.pi / 2 + rng.uniform(-0.9, 0.9), h * 0.26, 4, rng, trunk_col)
        else:
            blobs_crown(px, w, h, ox, oy - h * ccy, w * cw, h * ch, leaf_colour, density * airy, rng,
                        n=cfg.get("blobs", 9), blob_r=cfg.get("blob_r", (0.45, 0.7)))
            if flowering:
                fr, lo, hi = FLOWERS[cfg["flowers"]]
                for i in range(w * h):
                    if px[i] and rng.random() < 0.35:
                        px[i] = fr + rng.randint(lo, hi)
            if cfg.get("fruit") and season in (0, 1):
                for i in range(w * h):
                    if px[i] and rng.random() < 0.06:
                        px[i] = cfg["fruit"] + rng.randint(7, 9)
    elif shape == "cone":                               # 落葉針葉樹：窄圓錐，秋天轉褐、冬天光禿
        width = cfg.get("width", 1.0)
        trunk(px, w, h, ox, oy, max(0, oy - h + 2), rng, trunk_col)
        if ramps is None:
            for k in range(8):
                by = oy - h * (0.2 + 0.09 * k)
                for side in (-1, 1):
                    branches(px, w, h, ox, by, math.pi / 2 + side * rng.uniform(1.0, 1.35), w * 0.32 * (1 - k / 9), 2, rng, trunk_col)
        else:
            top, base = 1, oy - h * 0.12
            phase = rng.uniform(0, 6.3)
            for y in range(max(0, int(top)), int(base) + 1):
                t = (y - top) / max(base - top, 1)
                tuft = 0.78 + 0.22 * abs(math.sin(y * 0.55 + phase)) + rng.uniform(-0.06, 0.06)   # 一簇簇的羽狀枝
                half = min(w / 2 - 1, (w / 2) * width * (0.08 + 0.92 * t ** 0.85) * tuft)
                for x in range(int(ox - half), int(ox + half) + 1):
                    if rng.random() > density * airy * (0.75 + 0.25 * math.sin(y * 1.7 + x * 0.3) ** 2):
                        continue
                    light = -((x - ox) / max(half, 1)) * 0.5 - (1 - t) * 0.3
                    put(px, w, h, x, y, leaf_colour(x, y, 5.5 + light * 4 + rng.uniform(-1.2, 1.2)))
    elif shape == "weeping":                            # 垂柳：圓頂 + 下垂枝條
        trunk_top = oy - int(h * 0.55)
        trunk(px, w, h, ox, oy, trunk_top, rng, trunk_col)
        cx, cy = ox, oy - h * 0.66
        strands = max(14, int(w * 0.75))
        for k in range(strands):
            sx = cx + (k / (strands - 1) - 0.5) * w * 0.92
            top = cy - h * 0.30 * math.cos((k / (strands - 1) - 0.5) * math.pi) + rng.uniform(-2, 2)
            bottom = oy - h * rng.uniform(0.05, 0.25)
            col_bare = trunk_col
            for y in range(int(top), int(bottom)):
                sway = math.sin(y * 0.15 + k) * 0.6
                x = int(round(sx + sway + (sx - cx) * 0.08 * (y - top) / max(bottom - top, 1)))
                if ramps is None:
                    if rng.random() < 0.7:
                        put(px, w, h, x, y, col_bare + 4)
                elif rng.random() < density * 0.95:
                    t = (y - top) / max(bottom - top, 1)
                    put(px, w, h, x, y, leaf_colour(x, y, 7 - t * 3 - (x - cx) / w * 3 + rng.uniform(-1, 1)))
                    if rng.random() < 0.5:
                        put(px, w, h, x + 1, y, leaf_colour(x, y, 5 - t * 3 + rng.uniform(-1, 1)))
        if ramps is not None:
            blobs_crown(px, w, h, cx, cy - h * 0.06, w * 0.42, h * 0.20, leaf_colour, density, rng, n=8)
    elif shape in ("conifer", "column", "pine", "tiered"):
        ramp = RAMPS[cfg.get("leaf", "darkgreen")]
        if ramps is None:                               # 枯萎
            trunk(px, w, h, ox, oy, max(0, oy - h + 2), rng, GREY)
            for k in range(6):
                by = oy - h * (0.3 + 0.1 * k)
                for side in (-1, 1):
                    branches(px, w, h, ox, by, math.pi / 2 + side * rng.uniform(0.9, 1.3), w * 0.18 * (1 - k / 8), 2, rng, GREY)
            return bytes(px)
        if shape == "conifer":
            layers, width = cfg.get("layers", 5), cfg.get("width", 1.0)
            trunk(px, w, h, ox, oy, oy - int(h * 0.22), rng, trunk_col)
            for L in range(layers):
                frac = L / layers
                ly = int(oy - h * 0.14 - frac * h * 0.84)
                half = (w / 2) * width * (1 - frac * 0.82)
                lh = h * 0.84 / layers * 1.5
                for y in range(int(ly - lh), ly + 1):
                    t = (ly - y) / (lh + 1e-6)
                    span = half * max(0.0, 1 - t) ** 0.9
                    for x in range(int(ox - span), int(ox + span) + 1):
                        if rng.random() > 0.92:
                            continue
                        light = -((x - ox) / max(half, 1)) * 0.45 - t * 0.5 + (0.3 if y == ly else 0)
                        put(px, w, h, x, y, shade(ramp, 5 + light * 4 + rng.uniform(-1.1, 1.1)))
        elif shape == "column":                        # 柱狀（義大利柏、愛爾蘭紫杉）
            width = cfg.get("width", 0.7)
            trunk(px, w, h, ox, oy, oy - int(h * 0.08), rng, trunk_col)
            top, base = 1, oy - h * 0.05
            for y in range(max(0, top), int(base) + 1):
                t = (y - top) / max(base - top, 1)
                half = (w / 2) * width * math.sin(math.pi * min(1.0, 0.12 + t * 0.95)) ** 0.7
                for x in range(int(ox - half), int(ox + half) + 1):
                    if rng.random() > 0.93:
                        continue
                    light = -((x - ox) / max(half, 1)) * 0.6 - (1 - t) * 0.2
                    col = ramps[0] if season == 2 and cfg.get("spring") else ramp
                    put(px, w, h, x, y, shade(col, 5.5 + cfg.get("bias", 0) + light * 4 + rng.uniform(-1.3, 1.3)))
        elif shape == "pine":                          # 高松：長樹幹、上方不規則的團狀樹冠
            trunk(px, w, h, ox, oy, oy - int(h * 0.75), rng, BROWN)
            for k in range(4):
                by = oy - h * (0.45 + 0.1 * k)
                for side in (-1, 1):
                    ex = ox + side * w * rng.uniform(0.15, 0.35)
                    line(px, w, h, ox, by, ex, by - h * 0.06, BROWN + 3)
            blobs_crown(px, w, h, ox, oy - h * 0.76, w * 0.48, h * 0.17, lambda x, y, v: shade(ramp, v - 1.0), 0.93, rng,
                        n=10, blob_r=(0.35, 0.6))
        else:                                          # 黎巴嫩雪松：水平層狀
            trunk(px, w, h, ox, oy, oy - int(h * 0.85), rng, trunk_col)
            tiers = 4
            for k in range(tiers):
                cy = oy - h * (0.30 + 0.18 * k)
                rx = w * (0.48 - 0.08 * k)
                ry = h * 0.07
                for y in range(int(cy - ry * 1.6), int(cy + ry) + 1):
                    for x in range(int(ox - rx), int(ox + rx) + 1):
                        d = ((x - ox) / rx) ** 2 + ((y - cy) / (ry * (1.6 if y < cy else 1.0))) ** 2
                        if d > 1 or rng.random() > 0.9:
                            continue
                        light = -(x - ox) / rx * 0.4 - (y - cy) / ry * 0.5
                        put(px, w, h, x, y, shade(ramp, 5.5 + light * 3 + rng.uniform(-1.2, 1.2)))
        if snow:
            add_snow(px, w, h, rng)
    elif shape == "palm":
        ramp = RAMPS[cfg.get("leaf", "seagreen")]
        if ramps is None:
            ramp = BROWN
        top = max(0, oy - int(h * 0.72))
        bend = rng.uniform(-2.5, 2.5)
        for i, y in enumerate(range(top, oy + 1)):
            t = 1 - i / max(oy - top, 1)
            x = ox + int(bend * t * t)
            put(px, w, h, x, y, BROWN + (6 if i % 3 else 4))
            put(px, w, h, x + 1, y, BROWN + 3)
        hx = ox + int(bend)
        for k in range(9):                              # 扇形葉：從頂端放射
            ang = rng.uniform(0, 2 * math.pi)
            length = w * rng.uniform(0.28, 0.45)
            for s_ in range(int(length)):
                f = s_ / length
                fx = hx + math.cos(ang) * s_
                fy = top + 1 + math.sin(ang) * s_ * 0.45 + f * f * h * 0.10
                for k2 in range(max(1, int(3 * (1 - f)) + 1)):
                    put(px, w, h, int(fx), int(fy) + k2, shade(ramp, (8 if k2 == 0 else 5) + rng.uniform(-1, 1)))
    elif shape == "joshua":                             # 約書亞樹：分叉的枝幹，末端是刺狀葉叢
        ramp = RAMPS[cfg.get("leaf", "olive")]
        def arm(x, y, ang, length, depth):
            x2, y2 = x + math.cos(ang) * length, y - math.sin(ang) * length
            line(px, w, h, x, y, x2, y2, BROWN + (5 if depth % 2 else 3), width=2 if depth > 1 else 1)
            if depth == 0 or length < 3:
                for k in range(10):                     # 刺狀葉叢
                    a = rng.uniform(0, 2 * math.pi)
                    L = rng.uniform(1.5, 3.5) * max(1, w / 30)
                    line(px, w, h, x2, y2, x2 + math.cos(a) * L, y2 - math.sin(a) * L * 0.9, shade(ramp, rng.uniform(5, 9)))
                return
            for side in (-1, 1):
                arm(x2, y2, ang + side * rng.uniform(0.35, 0.7), length * rng.uniform(0.6, 0.8), depth - 1)
        arm(ox, oy, math.pi / 2, h * 0.38, 2 if h > 20 else 1)
    elif shape == "yucca":                              # 絲蘭：地面放射的劍形葉，成樹有花莖
        ramp = RAMPS[cfg.get("leaf", "seagreen")]
        cx, cy = ox, oy - max(1, h * 0.12)
        n = max(8, w)
        for k in range(n):
            a = math.pi * (0.05 + 0.9 * k / (n - 1)) + rng.uniform(-0.08, 0.08)
            L = h * rng.uniform(0.35, 0.55)
            line(px, w, h, cx, cy, cx + math.cos(a) * L * (w / h) * 1.1, cy - math.sin(a) * L, shade(ramp, 4 + 4 * math.sin(a) + rng.uniform(-1, 1)))
        if h > 20:
            line(px, w, h, cx, cy, cx, 1, BROWN + 6)
            for y in range(1, int(h * 0.35)):
                if rng.random() < 0.7:
                    put(px, w, h, cx + rng.choice((-1, 1)), y, GREY + rng.randint(9, 11))
    elif shape == "barrel":                             # 圓桶仙人掌（成群）
        ramp = RAMPS[cfg.get("leaf", "green")]
        for k in range(1 if w < 10 else 2):
            bx = ox + (k * 3 - 1 if k else 0)
            rx = max(2.0, w * (0.42 - 0.12 * k))
            ry = max(2.0, min(h * (0.48 - 0.15 * k), rx * 1.8))
            cy = oy - ry
            for y in range(int(cy - ry), int(cy + ry) + 1):
                for x in range(int(bx - rx), int(bx + rx) + 1):
                    d = ((x - bx) / rx) ** 2 + ((y - cy) / ry) ** 2
                    if d > 1:
                        continue
                    rib = 1.2 if (x - int(bx)) % 2 == 0 else 0
                    put(px, w, h, x, y, shade(ramp, 6 - (x - bx) / rx * 2.5 - (y - cy) / ry * 1.5 + rib))
            if h > 12:
                put(px, w, h, int(bx), int(cy - ry), RED + 8)
                put(px, w, h, int(bx) + 1, int(cy - ry), YELLOW + 9)
    elif shape == "pear":                               # 仙人掌（扁平的掌狀莖節）
        ramp = RAMPS[cfg.get("leaf", "avocado")]
        pads = [(ox, oy - h * 0.28, w * 0.36, h * 0.28)]
        if h > 10:
            pads += [(ox - w * 0.22, oy - h * 0.62, w * 0.24, h * 0.2), (ox + w * 0.2, oy - h * 0.70, w * 0.22, h * 0.2)]
        if h > 22:
            pads += [(ox + w * 0.02, oy - h * 0.86, w * 0.18, h * 0.14)]
        for cx, cy, rx, ry in pads:
            for y in range(int(cy - ry), int(cy + ry) + 1):
                for x in range(int(cx - rx), int(cx + rx) + 1):
                    d = ((x - cx) / max(rx, 1)) ** 2 + ((y - cy) / max(ry, 1)) ** 2
                    if d <= 1:
                        dot = 2 if (x * 3 + y * 5) % 11 == 0 else 0
                        put(px, w, h, x, y, shade(ramp, 6.5 - (x - cx) / max(rx, 1) * 2 - (y - cy) / max(ry, 1) + dot))
    else:
        raise SystemExit(f"未知樹形 {shape}")
    if snow and shape not in ("conifer", "column", "pine", "tiered"):
        add_snow(px, w, h, rng)
    return bytes(px)


def add_snow(px, w, h, rng):
    """每個上方是空白的像素（枝葉的上緣）蓋上白雪。"""
    src = bytes(px)
    for y in range(h):
        for x in range(w):
            if not src[y * w + x]:
                continue
            above_empty = y == 0 or not src[(y - 1) * w + x]
            if above_empty and rng.random() < 0.9:
                px[y * w + x] = GREY + 11
                if y + 1 < h and src[(y + 1) * w + x] and rng.random() < 0.6:
                    px[(y + 1) * w + x] = GREY + 10


def shadow(w, h, rng):
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if ((x - (w - 1) / 2) / (w / 2)) ** 2 + ((y - (h - 1) / 2) / (h / 2)) ** 2 <= 1 and rng.random() < 0.8:
                px[y * w + x] = GREY + 1
    return bytes(px)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", choices=["deciduous", "conifer", "palm", "cactus"])
    ap.add_argument("--preset", help="M3 樹種 preset（見 PRESETS）；與 --style 二選一")
    ap.add_argument("--leaf", choices=list(LEAF), default="green")
    ap.add_argument("--trunk", choices=["brown", "light"], default="brown", help="light = 白樺的淺色樹幹")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    global TRUNK
    TRUNK = BROWN if args.trunk == "brown" else GREY + 5
    obj = dat.read_dat(args.template)
    d = obj.data
    rot, growth = d[6], d[7]
    flags = struct.unpack_from("<H", d, 8)[0]
    seasons = [b for b in range(6) if d[0x3C] >> b & 1]
    has_snow, has_shadow = bool(flags & 1), bool(flags & 0x80)
    entries = obj.image_table().entries
    plan = []  # (season, growth, rotation, snow)
    for s in seasons:
        for g in range(growth):
            for r in range(rot):
                plan.append((s, g, r, False))
    if has_snow:
        plan += [(s, g, r, True) for (s, g, r, _) in plan]
    n_main = len(plan)
    expected = n_main * (2 if has_shadow else 1)
    if expected != len(entries):
        raise SystemExit(f"影像數不符：依結構計算 {expected}，模板有 {len(entries)}")

    frames = []
    for i, e in enumerate(entries):
        if i < n_main:
            s, g, r, snow = plan[i]
            rng = random.Random(args.seed * 1000 + r * 10 + g)   # 同一棵樹各季節形狀一致
            if args.preset:
                px = draw_preset(PRESETS[args.preset], e.width, e.height, -e.x_offset, -e.y_offset, s, rng, snow)
            else:
                px = draw_tree(args.style, e.width, e.height, -e.x_offset, -e.y_offset, s, args.leaf, rng, snow)
        else:
            px = shadow(e.width, e.height, random.Random(args.seed + i))
        frames.append((e.width, e.height, e.x_offset, e.y_offset, px))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
