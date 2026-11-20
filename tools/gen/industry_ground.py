#!/usr/bin/env python3
"""產業地面圖塊（industry 物件 fieldImageIds 的 21 張：19 種坡度地面 + 樹 + 積雪樹）。

坡度圖塊的輪廓與明暗取自上游 OG 地形物件 OG_GRASS1（image 285–303，與 vanilla 產業地面的尺寸／偏移完全相同），
再換成指定材質的色階。第 20、21 張（樹、積雪樹）沿用模板尺寸，輸出透明圖。

  python3 tools/gen/industry_ground.py --template <產業模板.DAT> --style coal|gravel|dirt --append-to <sprites 資料夾>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import common

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SHAPES = REPO / "objects" / "VanillaReplacements" / "Land" / "GRASS1" / "OG_GRASS1.dat"
SHAPE_START = 285
STYLES = {"coal": (0x0A, 0, 5), "gravel": (0x0A, 3, 8), "dirt": (0xD6, 2, 7)}   # (色階, 最暗, 最亮)


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", choices=STYLES, required=True)
    ap.add_argument("--append-to", required=True)
    args = ap.parse_args()

    tpl_entries = common.template_entries(args.template)
    fields = tpl_entries[-21:]
    shapes = dat.read_dat(SHAPES).image_table()
    ramp, lo, hi = STYLES[args.style]
    out = Path(args.append_to)
    meta = json.loads((out / "sprites.json").read_text())
    start = len(meta)
    for k, fe in enumerate(fields):
        if k < 19:
            w, h, x, y, px, al = dat.decode_sprite(shapes, SHAPE_START + k, True)
            if (w, h, x, y) != (fe.width, fe.height, fe.x_offset, fe.y_offset):
                raise SystemExit(f"坡度圖塊 {k} 尺寸不符：OG {w, h, x, y} 模板 {fe.width, fe.height, fe.x_offset, fe.y_offset}")
            ls = [lum(common.PALETTE[px[i]]) for i in range(w * h) if al[i]]
            mn, mx = (min(ls), max(ls)) if ls else (0, 1)
            pix = bytearray(w * h)
            for i in range(w * h):
                if al[i]:
                    t = (lum(common.PALETTE[px[i]]) - mn) / max(mx - mn, 1)
                    pix[i] = ramp + lo + round(t * (hi - lo))
        else:
            w, h, x, y = fe.width, fe.height, fe.x_offset, fe.y_offset
            pix = bytearray(w * h)
            al = bytearray(w * h)
        alpha = bytes(255 if v else 0 for v in pix)
        fn = f"{start + k}.png"
        dat.write_indexed_png(out / fn, w, h, bytes(pix), alpha, common.PALETTE)
        meta.append({"path": fn, "x": x, "y": y, "zoomOffset": 0, "flags": 0, "name": None})
    (out / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"加上 {len(fields)} 張地面圖塊（{args.style}）→ {out}（共 {len(meta)} 張）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
