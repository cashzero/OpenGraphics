#!/usr/bin/env python3
"""蒸汽／排氣／火花的煙團動畫（steam 物件）。依模板每格的尺寸產生一團由小變大、最後消散的煙。

  python3 tools/gen/steam.py --template <模板.DAT> --style exhaust|steam|spark --seed 1 -o <資料夾>
"""
from __future__ import annotations

import argparse
import math
import random

import common

STYLES = {
    # (色階起點, 可用的階數範圍, 基本密度)
    "exhaust": (0x0A, (2, 7), 0.80),   # 深灰柴油排氣
    "steam": (0x0A, (6, 11), 0.85),    # 淺灰白蒸汽
    "spark": (0x82, (7, 11), 0.22),    # 藍白電弧火花（稀疏亮點）
}


def blob(w: int, h: int, progress: float, style: str, rng: random.Random) -> bytes:
    base, (lo, hi), density = STYLES[style]
    if progress > 0.7:                      # 後段逐漸消散
        density *= max(0.15, 1.0 - (progress - 0.7) / 0.3 * 0.85)
    px = bytearray(w * h)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    rx, ry = max(w / 2, 0.5), max(h / 2, 0.5)
    for y in range(h):
        for x in range(w):
            d = math.hypot((x - cx) / rx, (y - cy) / ry)
            if d > 1.0:
                continue
            p = density * (1.0 - 0.55 * d)
            if rng.random() > p:
                continue
            # 上方較亮、下方較暗；邊緣較淡
            shade = hi - (y / max(h - 1, 1)) * (hi - lo) * 0.7 - d * 1.5 + rng.uniform(-1, 1)
            px[y * w + x] = base + int(max(lo, min(hi, round(shade))))
    if not any(px):                         # 很小的格子至少留一個點
        px[(h // 2) * w + w // 2] = base + hi
    return bytes(px)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", choices=STYLES, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    entries = common.template_entries(args.template)
    n = len(entries)
    frames = []
    for i, e in enumerate(entries):
        frames.append((e.width, e.height, e.x_offset, e.y_offset,
                       blob(e.width, e.height, i / max(n - 1, 1), args.style, rng)))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
