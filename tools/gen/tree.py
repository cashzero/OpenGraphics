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
    ap.add_argument("--style", choices=["deciduous", "conifer", "palm", "cactus"], required=True)
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
            px = draw_tree(args.style, e.width, e.height, -e.x_offset, -e.y_offset, s, args.leaf, rng, snow)
        else:
            px = shadow(e.width, e.height, random.Random(args.seed + i))
        frames.append((e.width, e.height, e.x_offset, e.y_offset, px))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
