#!/usr/bin/env python3
"""P2 量化：把渲染出的 RGBA 影格轉成 Loco 調色盤的 sprite（需要 .venv 的 Pillow）。

  .venv/bin/python tools/quantize.py <render 資料夾> -o <sprites 資料夾>

輸入（tools/blender/render_sprites.py 的輸出格式）：
  render.json：{"frames": [{"file": "0000.png", "mask": "0000_mask.png"（可省略）,
                            "origin": [ox, oy], "flags": 0, "zoomOffset": 0}, ...]}
  每個 PNG 為 RGBA；origin 是物件原點在影格中的像素座標。
  mask 為 RGB：R >= 門檻（預設 48）= primary remap（主公司色）區域，G >= 門檻 = secondary remap 區域。
輸出：0.png…N.png（索引色）與 sprites.json，可直接給 tools/pack.py。

規則（依 OpenLoco Graphics/Gfx.cpp：可繪製顏色為 index 10–245）：
- alpha < 128 → 透明（index 0）。
- 一般像素 → 最接近的顏色，候選為 10–245（排除 secondary remap 0xCA–0xD5 與未使用的 0xF5），
  預設再加上 primary／secondary remap 色（色鍵模式，對應上游 rig 用紫／粉紅材質標示公司色）；
  --no-remap-colours 可關閉（只靠 mask 指定 remap 區域）。
- mask 區域 → 依亮度對應到 remap 色階（primary：0x07–0x09、0xF6–0xFE；secondary：0xCA–0xD5）。
- 影格會裁切到不透明像素的範圍，並把 origin 換算成 G1 的 xOffset／yOffset。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：請用 .venv/bin/python 執行")

PRIMARY = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
SECONDARY = list(range(0xCA, 0xD6))
ALLOWED = [i for i in range(10, 246) if not (0xCA <= i <= 0xD5) and i != 0xF5]


def lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


class Quantizer:
    def __init__(self, palette, remap_colours: bool = True):
        self.palette = palette
        # 色鍵模式：上游 Loco Graphics Helper 的材質直接用 remap 色（紫／粉紅）標示公司色區域，
        # 所以 remap 色也列入最近色候選，量化後自然落在 remap index。
        self.candidates = ALLOWED + (PRIMARY + SECONDARY if remap_colours else [])
        self.cache: dict[tuple[int, int, int], int] = {}
        self.ramps = {
            "primary": [(lum(palette[i]), i) for i in PRIMARY],
            "secondary": [(lum(palette[i]), i) for i in SECONDARY],
        }

    def nearest(self, rgb: tuple[int, int, int]) -> int:
        hit = self.cache.get(rgb)
        if hit is not None:
            return hit
        r, g, b = rgb
        best, best_d = self.candidates[0], 1 << 30
        for i in self.candidates:
            pr, pg, pb = self.palette[i]
            rm = (r + pr) / 2
            # "redmean" 加權距離，比純 RGB 距離更接近人眼
            d = (2 + rm / 256) * (r - pr) ** 2 + 4 * (g - pg) ** 2 + (2 + (255 - rm) / 256) * (b - pb) ** 2
            if d < best_d:
                best, best_d = i, d
        self.cache[rgb] = best
        return best

    def remap(self, rgb, ramp: str) -> int:
        l = lum(rgb)
        return min(self.ramps[ramp], key=lambda t: abs(t[0] - l))[1]


def quantize_frame(q: Quantizer, img: Image.Image, mask: Image.Image | None, threshold: int = 48):
    rgba = img.convert("RGBA")
    w, h = rgba.size
    m = mask.convert("RGB").load() if mask is not None else None
    src = rgba.load()
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            r, g, b, a = src[x, y]
            if a < 128:
                continue
            if m is not None:
                mr, mg, _mb = m[x, y]
                # 反鋸齒邊緣的遮罩值只有部分，門檻放低才不會在交界留下一般顏色的細線
                if mr >= threshold and mr >= mg:
                    px[y * w + x] = q.remap((r, g, b), "primary")
                    continue
                if mg >= threshold:
                    px[y * w + x] = q.remap((r, g, b), "secondary")
                    continue
            px[y * w + x] = q.nearest((r, g, b))
    # 裁切到不透明範圍
    xs = [k % w for k in range(w * h) if px[k]]
    ys = [k // w for k in range(w * h) if px[k]]
    if not xs:
        return 1, 1, 0, 0, bytes(1)
    left, right, top, bottom = min(xs), max(xs) + 1, min(ys), max(ys) + 1
    cw, ch = right - left, bottom - top
    out = bytearray(cw * ch)
    for y in range(ch):
        out[y * cw:(y + 1) * cw] = px[(top + y) * w + left:(top + y) * w + right]
    return cw, ch, left, top, bytes(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("render_dir")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--no-remap-colours", action="store_true", help="一般像素不使用 remap 色（只靠 mask）")
    ap.add_argument("--mask-threshold", type=int, default=48, help="遮罩通道值 >= 此值即視為公司色區域（預設 48）")
    args = ap.parse_args(argv)

    src = Path(args.render_dir)
    spec = json.loads((src / "render.json").read_text())
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    palette = dat.load_palette()
    q = Quantizer(palette, remap_colours=not args.no_remap_colours)
    meta = []
    for i, fr in enumerate(spec["frames"]):
        img = Image.open(src / fr["file"])
        mask = Image.open(src / fr["mask"]) if fr.get("mask") else None
        w, h, left, top, px = quantize_frame(q, img, mask, args.mask_threshold)
        ox, oy = fr["origin"]
        alpha = bytes(255 if v else 0 for v in px)
        dat.write_indexed_png(out / f"{i}.png", w, h, px, alpha, palette)
        meta.append({"path": f"{i}.png", "x": left - int(round(ox)), "y": top - int(round(oy)),
                     "zoomOffset": int(fr.get("zoomOffset", 0)), "flags": int(fr.get("flags", 0)), "name": fr.get("name")})
    (out / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"量化 {len(meta)} 張影格 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
