#!/usr/bin/env python3
"""貨幣符號字形（currency 物件）。需要 .venv 的 Pillow（用 DejaVu 字型畫符號）。

OpenLoco（Graphics/Gfx.cpp `loadCurrency`）把這 5 張圖當成字型中的貨幣符號字元：
  0 = small、1 = medium normal、2 = medium bold、3 = large（物件選擇視窗的預覽也用這張），4 = 未使用（同 1）。
遊戲顯示金額時，字串裡的 £ 會換成這些字形；字寬 = 圖寬（± 1）。
像素用 text remap index 1（介面會換成文字顏色），與 g1 字型相同（tools/g1.py）。

  .venv/bin/python tools/gen/currency.py --template <模板.DAT> --symbol '$' -o <資料夾>
"""
from __future__ import annotations

import argparse

import common

TEXT = 1
FONTS = {"regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"}
WEIGHTS = ["regular", "regular", "bold", "bold", "regular"]


SCALE = 6

# small 字型（7 列）用的手繪像素字形：TrueType 縮到 5 列會糊掉。每字 7 列（第 0、6 列給 $ 的上下短豎線），
# 大寫高 5 列（第 1–5 列）。
PIXEL = {
    "$": [".#.", "###", "#..", "###", "..#", "###", ".#."],
    "D": ["...", "##.", "#.#", "#.#", "#.#", "##.", "..."],
    "M": [".....", "#...#", "##.##", "#.#.#", "#...#", "#...#", "....."],
    "€": ["....", ".###", "#...", "###.", "#...", ".###", "...."],
    "F": ["...", "###", "#..", "##.", "#..", "#..", "..."],
    "f": ["...", ".##", "#..", "###", "#..", "#..", "..."],
    "l": [".", "#", "#", "#", "#", "#", "."],
    "k": ["...", "#..", "#.#", "##.", "#.#", "#.#", "..."],
    "r": ["..", "..", "#.", "##", "#.", "#.", ".."],
    "L": ["...", "#..", "#..", "#..", "#..", "###", "..."],
    "N": ["....", "#..#", "##.#", "#.##", "#..#", "#..#", "...."],
    "T": ["...", "###", ".#.", ".#.", ".#.", ".#.", "..."],
    "£": ["....", ".##.", "#...", "###.", "#...", "####", "...."],
    "P": ["...", "##.", "#.#", "##.", "#..", "#..", "..."],
    "t": ["...", ".#.", "###", ".#.", ".#.", ".##", "..."],
    "s": ["...", "...", ".##", "#..", ".#.", "##.", "..."],
    "₩": [".....", "#...#", "#.#.#", "#####", "#.#.#", ".#.#.", "....."],
    "¥": ["...", "#.#", "#.#", "###", ".#.", "###", "..."],
    "z": ["...", "...", "###", "..#", ".#.", "###", "..."],
    "ł": ["..", "#.", "#.", "##", "#.", "#.", ".."],
}


def pixel_glyph(text: str, h: int) -> tuple[int, bytes] | None:
    if h != 7 or any(c not in PIXEL for c in text):
        return None
    rows = ["." .join(PIXEL[c][r] for c in text) for r in range(7)]   # 字間 1 px
    w = len(rows[0])
    return w, bytes(TEXT if ch == "#" else 0 for row in rows for ch in row)


def glyph(text: str, h: int, weight: str) -> tuple[int, bytes]:
    pix = pixel_glyph(text, h)
    if pix:
        return pix
    """回傳 (寬, 像素)：字形外框高度填滿 h - 1 列（底下留 1 列給字型的行距），寬度依文字而定。
    小字型直接用 TrueType 畫會糊成一團，所以先放大 SCALE 倍畫，再以 box filter 縮小後取閾值。"""
    from PIL import Image, ImageDraw, ImageFont
    target = max(h - 1, 4) * SCALE
    size = target
    while True:                                   # 找出外框高度不超過 target 的最大字級
        f = ImageFont.truetype(FONTS[weight], size)
        left, top, right, bottom = f.getbbox(text)
        if bottom - top <= target or size <= 4:
            break
        size -= 1
    big_w = right - left
    w = max(1, -(-big_w // SCALE))
    img = Image.new("L", (w * SCALE, h * SCALE), 0)
    ImageDraw.Draw(img).text((-left + (w * SCALE - big_w) // 2, -top), text, fill=255, font=f)
    small = img.resize((w, h), Image.BOX)
    cut = 96 if weight == "bold" else 80
    return w, bytes(TEXT if v >= cut else 0 for v in small.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    entries = common.template_entries(args.template)
    frames = []
    for i, e in enumerate(entries):
        w, px = glyph(args.symbol, e.height, WEIGHTS[i % len(WEIGHTS)])
        frames.append((w, e.height, 0, e.y_offset, px))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
