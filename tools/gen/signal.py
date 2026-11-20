#!/usr/bin/env python3
"""臂板號誌（trackSignal 物件）。影像 = 8 個視角 + 動畫格 × 8（OpenLoco Paint/PaintSignal.cpp）。
每張：號誌柱立在繪製原點，頂端的臂板依可用寬度伸向左或右；動畫格 0→N 臂板逐格上揚（上象限式，揚起 = 通行）。

  python3 tools/gen/signal.py --template <模板.DAT> -o <資料夾>
"""
from __future__ import annotations

import argparse
import math

import common

POST, POST_DARK, BASE = 0x0A + 5, 0x0A + 3, 0x0A + 1
ARM, STRIPE, LAMP = 0xA6 + 8, 0x0A + 11, 0x2E + 9


def draw(w, h, ox, oy, frame, frames):
    px = bytearray(w * h)

    def put(x, y, c):
        if 0 <= x < w and 0 <= y < h:
            px[y * w + x] = c
    top = 2
    for y in range(top, oy + 1):
        put(ox, y, POST)
        put(ox + 1 if ox + 1 < w else ox - 1, y, POST_DARK)
    for dx in (-1, 0, 1, 2):
        put(ox + dx, oy, BASE)
    right = ox < w / 2
    room = (w - 1 - ox) if right else ox
    length = max(2, min(7, room))
    ang = math.radians(35 * frame / max(frames - 1, 1))      # 上象限：逐格上揚
    for s in range(length + 1):
        x = ox + (s if right else -s)
        y = round(top + 1 - s * math.sin(ang))
        c = STRIPE if s == length - 1 else ARM
        put(x, y, c)
        put(x, y + 1, c)
    put(ox, top + 3, LAMP)
    return bytes(px)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    entries = common.template_entries(args.template)
    frames = len(entries) // 8
    out = []
    for i, e in enumerate(entries):
        out.append((e.width, e.height, e.x_offset, e.y_offset,
                    draw(e.width, e.height, -e.x_offset, -e.y_offset, i // 8, frames)))
    common.write_sprites(args.output, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
