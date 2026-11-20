#!/usr/bin/env python3
"""貨幣圖示（currency 物件）：前幾張為硬幣堆，後面為貨幣符號。像素使用 text remap index 1–3，
介面繪製時會換成文字顏色。需要 .venv 的 Pillow（用 DejaVu 字型畫符號）。

  .venv/bin/python tools/gen/currency.py --template <模板.DAT> --symbol '$' --coins 3 -o <資料夾>
"""
from __future__ import annotations

import argparse

import common

BODY, EDGE, SHINE = 1, 3, 2   # textRemap：1 = 主色、2/3 = 明暗


def coins(w: int, h: int, count: int) -> bytes:
    px = bytearray(w * h)
    coin_h = max(3, min(5, w // 2))
    for c in range(count):
        top = h - coin_h - c * 2
        if top < 0:
            break
        for y in range(coin_h):
            for x in range(w):
                ex = (x - (w - 1) / 2) / (w / 2)
                ey = (y - (coin_h - 1) / 2) / (coin_h / 2)
                if ex * ex + ey * ey <= 1.0:
                    v = EDGE if (y == coin_h - 1 or ex * ex + ey * ey > 0.6) else BODY
                    if y == 0 and abs(ex) < 0.4:
                        v = SHINE
                    px[(top + y) * w + x] = v
    return bytes(px)


def symbol(w: int, h: int, text: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", h + 1)
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    l, t, r, b = font.getbbox(text)
    d.text(((w - (r - l)) // 2 - l, (h - (b - t)) // 2 - t), text, fill=255, font=font)
    return bytes(BODY if v >= 128 else (EDGE if v >= 50 else 0) for v in img.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--coins", type=int, default=3, help="前幾張畫硬幣堆（其餘畫符號）")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    entries = common.template_entries(args.template)
    frames = []
    for i, e in enumerate(entries):
        px = coins(e.width, e.height, i + 1) if i < args.coins else symbol(e.width, e.height, args.symbol)
        frames.append((e.width, e.height, e.x_offset, e.y_offset, px))
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
