#!/usr/bin/env python3
"""建築／產業的合成預覽：依模板的變化組合把部件 sprite 疊起來（與遊戲相同：image = part × 4 + 旋轉，
部件高度累加），每個變化組合 × 4 個旋轉畫在一張圖上。需要 .venv 的 Pillow。

  .venv/bin/python tools/stack_preview.py <OG_X.dat>… -o build/preview/<名稱>.png [--max-var 3] [--rot 0,1,2,3]

公司色以紅（primary）／黃（secondary）示意。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import objinfo  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

PRIMARY = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
SECONDARY = list(range(0xCA, 0xD6))


def colour_lut(pal):
    lut = list(pal)
    for k, i in enumerate(PRIMARY):
        lut[i] = pal[0xA6 + k]
    for k, i in enumerate(SECONDARY):
        lut[i] = pal[0x2E + k]
    return lut


def sprite(table, idx, lut):
    w, h, x, y, px, al = dat.decode_sprite(table, idx)
    im = Image.new("RGBA", (max(w, 1), max(h, 1)))
    im.putdata([(*lut[px[i]], 255) if al[i] else (0, 0, 0, 0) for i in range(w * h)] or [(0, 0, 0, 0)])
    return im, x, y


def compose(path, max_var, rots, lut):
    o = dat.read_dat(path)
    t = o.image_table()
    if o.type_name == "building":
        info = objinfo.building(o)
        base = 0
    else:
        info = objinfo.industry(o)
        base = info["first_part_image"]
    cells = []
    for vi, var in enumerate(info["variations"][:max_var]):
        for r in rots:
            layers, z = [], 0
            for p in var:
                layers.append((sprite(t, base + p * 4 + r, lut), z))
                z += info["heights"][p]
            cells.append((vi, r, layers))
    return o, cells


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--max-var", type=int, default=3)
    ap.add_argument("--rot", default="0,1,2,3")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()
    lut = colour_lut(dat.load_palette())
    rots = [int(r) for r in args.rot.split(",")]
    rows = []
    for f in args.files:
        o, cells = compose(f, args.max_var, rots, lut)
        # 每格大小
        boxes = []
        for _vi, _r, layers in cells:
            xs, ys = [], []
            for (im, x, y), z in layers:
                xs += [x, x + im.width]
                ys += [y - z, y - z + im.height]
            boxes.append((min(xs), max(xs), min(ys), max(ys)))
        W = max(b[1] - b[0] for b in boxes) + 8
        H = max(b[3] - b[2] for b in boxes) + 8
        top = min(b[2] for b in boxes)
        left = min(b[0] for b in boxes)
        row = Image.new("RGB", (W * len(cells), H + 14), (96, 120, 80))
        d = ImageDraw.Draw(row)
        d.text((2, 1), f"{Path(f).stem}  {o.display_name()}", fill="white")
        for k, (_vi, _r, layers) in enumerate(cells):
            for (im, x, y), z in layers:
                row.paste(im, (k * W + 4 + x - left, 14 + 4 + y - z - top), im)
        rows.append(row)
    W = max(r.width for r in rows)
    out = Image.new("RGB", (W, sum(r.height for r in rows)), (60, 60, 60))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    if args.scale > 1:
        out = out.resize((out.width * args.scale, out.height * args.scale), Image.NEAREST)
    out.save(args.output)
    print(f"寫出 {args.output}（{out.width}×{out.height}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
