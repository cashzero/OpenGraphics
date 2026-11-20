#!/usr/bin/env python3
"""平交道警示牌（levelCrossing 物件，4 個角落 × 4 組）。

模板的 16 張圖依序為 4 組 × 4 個角落；第 0、2 組警示牌正面朝向畫面（看得到 X 形牌），
第 1、3 組為側面（只看到牌子的厚度）。

  python3 tools/gen/lcross_signs.py --template <模板.DAT> -o <資料夾>
"""
from __future__ import annotations

import argparse

import common

POST = 0xD6 + 4      # brown4：木柱
POST_DARK = 0xD6 + 2
WHITE = 0x0A + 11    # 最亮的灰白
RED = 0xA6 + 7


def sign(w: int, h: int, face_on: bool) -> bytes:
    px = bytearray(w * h)
    post_x = w // 2 - (0 if w % 2 else 1)
    for y in range(4, h):
        px[y * w + post_x] = POST
        if post_x + 1 < w:
            px[y * w + post_x + 1] = POST_DARK
    if face_on:
        # 4×4 的 X 形牌：白底紅邊
        for k in range(min(w, 4)):
            for y, x in ((k, k), (k, 3 - k)):
                if 0 <= x < w and y < h:
                    px[y * w + x] = WHITE
        for y, x in ((0, 0), (0, 3), (3, 0), (3, 3)):
            if x < w and y < h:
                px[y * w + x] = RED
    else:
        for y in range(0, 4):
            px[y * w + post_x] = WHITE
            if post_x + 1 < w:
                px[y * w + post_x + 1] = RED
    return bytes(px)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    entries = common.template_entries(args.template)
    frames = []
    for i, e in enumerate(entries):
        face_on = (i // 4) % 2 == 0
        frames.append((e.width, e.height, e.x_offset, e.y_offset, sign(e.width, e.height, face_on)))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
