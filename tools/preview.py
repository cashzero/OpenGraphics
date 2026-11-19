#!/usr/bin/env python3
"""V1 目視驗證：從「最終 DAT」解出所有 sprite，產生 contact sheet（需要 .venv 的 Pillow）。

  .venv/bin/python tools/preview.py <file.dat> -o build/preview/<NAME>.png [options]

每張 sprite 一格：棋盤格背景（看透明）、2× 最近鄰放大、左上角 index、
紅色十字 = 繪製原點（xOffset/yOffset 的基準），可選擇畫出高度參考線。
格子標籤：#index 寬x高 f<G1 flags>。index 0 預設視為透明（--strict-flags 改為依 flag）。
--remap 會額外輸出公司色變體（primary/secondary remap 換成範例色階）。
--compare 會在同一張圖下方以相同比例畫出對照物件。
sprite 太多時自動分頁：<out>.p1.png、<out>.p2.png…
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：請用 .venv/bin/python 執行（uv venv .venv && uv pip install --python .venv/bin/python pillow）")

PRIMARY_REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))   # 12 階
SECONDARY_REMAP = list(range(0xCA, 0xD6))                       # 12 階
RAMPS = {"yellow": 0x2E, "green": 0x5E, "blue": 0x82, "red": 0xA6, "orange": 0xB2}
# (primary, secondary) 範例組合
REMAP_SCHEMES = [("red", "yellow"), ("blue", "orange"), ("green", "red")]

MAX_PAGE_W = 1800
MAX_PAGE_H = 1800
PAD = 6
LABEL_H = 12


def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def remap_table(scheme: tuple[str, str] | None) -> list[int]:
    t = list(range(256))
    if scheme:
        p0, s0 = RAMPS[scheme[0]], RAMPS[scheme[1]]
        for k, idx in enumerate(PRIMARY_REMAP):
            t[idx] = p0 + k
        for k, idx in enumerate(SECONDARY_REMAP):
            t[idx] = s0 + k
    return t


def sprite_image(table: dat.ImageTable, i: int, palette, remap: list[int], strict: bool) -> tuple[Image.Image, int, int]:
    w, h, xo, yo, px, al = dat.decode_sprite(table, i, None if strict else True)
    img = Image.new("RGBA", (max(w, 1), max(h, 1)), (0, 0, 0, 0))
    if w and h:
        data = []
        for k in range(w * h):
            if al[k]:
                r, g, b = palette[remap[px[k]]]
                data.append((r, g, b, 255))
            else:
                data.append((0, 0, 0, 0))
        img.putdata(data)
    return img, xo, yo


def checker(w: int, h: int, s: int = 4) -> Image.Image:
    bg = Image.new("RGB", (w, h), (205, 205, 205))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, s):
        for x in range((y // s % 2) * s, w, 2 * s):
            d.rectangle([x, y, x + s - 1, y + s - 1], fill=(170, 170, 170))
    return bg


def build_cells(obj: dat.DatObject, palette, scale: int, scheme, height_lines: list[int], indices, strict: bool = False):
    table = obj.image_table()
    font = _font(10)
    remap = remap_table(scheme)
    cells = []
    for i in indices:
        img, xo, yo = sprite_image(table, i, palette, remap, strict)
        flags = table.entries[i].flags
        w, h = img.size
        # 原點在 sprite 座標中的位置為 (-xo, -yo)；格子要同時包含 sprite 與原點
        ox, oy = -xo, -yo
        left, top = min(0, ox), min(0, oy)
        right, bottom = max(w, ox + 1), max(h, oy + 1)
        for hl in height_lines:
            top = min(top, oy - hl)
        cw, ch = (right - left) * scale + 2 * PAD, (bottom - top) * scale + 2 * PAD + LABEL_H
        cell = checker(cw, ch)
        sx, sy = PAD + (0 - left) * scale, PAD + LABEL_H + (0 - top) * scale
        big = img.resize((w * scale, h * scale), Image.NEAREST)
        cell.paste(big, (sx, sy), big)
        d = ImageDraw.Draw(cell)
        cx, cy = PAD + (ox - left) * scale + scale // 2, PAD + LABEL_H + (oy - top) * scale + scale // 2
        for hl in height_lines:
            yl = cy - hl * scale
            d.line([(PAD, yl), (cw - PAD, yl)], fill=(0, 120, 255), width=1)
            d.text((cw - PAD - 22, yl - 11), f"{hl}", fill=(0, 90, 200), font=font)
        d.line([(cx - 4, cy), (cx + 4, cy)], fill=(255, 0, 0), width=1)
        d.line([(cx, cy - 4), (cx, cy + 4)], fill=(255, 0, 0), width=1)
        d.text((PAD, 1), f"#{i} {img.size[0]}x{img.size[1]} f{flags}", fill=(0, 0, 0), font=font)
        d.rectangle([0, 0, cw - 1, ch - 1], outline=(120, 120, 120))
        cells.append(cell)
    return cells


def layout(sections: list[tuple[str, list[Image.Image]]]) -> list[Image.Image]:
    """把多個區段（標題 + 格子）排成一頁或多頁。"""
    font = _font(14)
    pages: list[Image.Image] = []
    placements = []  # (page_no, x, y, image)
    page, x, y, row_h, page_w = 0, 0, 0, 0, 0

    def newline():
        nonlocal x, y, row_h
        x, y, row_h = 0, y + row_h, 0

    for title, cells in sections:
        if x:
            newline()
        if y + 22 > MAX_PAGE_H:
            page, x, y, row_h = page + 1, 0, 0, 0
        placements.append((page, 0, y, title))
        y += 22
        for c in cells:
            cw, ch = c.size
            if x and x + cw > MAX_PAGE_W:
                newline()
            if y + ch > MAX_PAGE_H and y > 0:
                page, x, y, row_h = page + 1, 0, 0, 0
            placements.append((page, x, y, c))
            x += cw
            page_w = max(page_w, x)
            row_h = max(row_h, ch)
    n_pages = page + 1
    heights = [0] * n_pages
    widths = [0] * n_pages
    for p, px, py, item in placements:
        if isinstance(item, str):
            heights[p] = max(heights[p], py + 22)
            widths[p] = max(widths[p], 400)
        else:
            heights[p] = max(heights[p], py + item.size[1])
            widths[p] = max(widths[p], px + item.size[0])
    for p in range(n_pages):
        pages.append(Image.new("RGB", (max(widths[p], 1), max(heights[p], 1)), (255, 255, 255)))
    for p, px, py, item in placements:
        if isinstance(item, str):
            ImageDraw.Draw(pages[p]).text((4, py + 3), item, fill=(0, 0, 0), font=font)
        else:
            pages[p].paste(item, (px, py))
    return pages


def parse_range(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        if ":" in part:
            a, b = part.split(":")
            out += list(range(int(a or 0), min(int(b or n), n)))
        else:
            out.append(int(part))
    return [i for i in out if 0 <= i < n]


def describe(obj: dat.DatObject) -> str:
    t = obj.image_table()
    return (f"{obj.path.name}  type={obj.type_name} name={obj.name_str!r} "
            f"display={obj.display_name()!r} images={len(t.entries) if t else 0} "
            f"checksum={'OK' if obj.checksum_ok() else 'MISMATCH'} source={obj.source_name}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--range", help="只畫部分 sprite，例如 0:32 或 0,4,8")
    ap.add_argument("--remap", action="store_true", help="加畫公司色變體")
    ap.add_argument("--height-lines", type=int, nargs="*", default=[], help="在原點上方畫出高度參考線（像素）")
    ap.add_argument("--compare", help="對照用的 DAT，以相同比例畫在下方")
    ap.add_argument("--strict-flags", action="store_true",
                    help="依 hasTransparency flag 決定 index 0 是否透明（預設一律透明，等同遊戲中以公司色繪製）")
    args = ap.parse_args(argv)

    palette = dat.load_palette()
    obj = dat.read_dat(args.file)
    table = obj.image_table()
    if not table:
        print(f"{describe(obj)}\n此物件沒有 image table")
        return 0
    idx = parse_range(args.range, len(table.entries))
    sections = [(describe(obj), build_cells(obj, palette, args.scale, None, args.height_lines, idx, args.strict_flags))]
    if args.remap:
        for sch in REMAP_SCHEMES:
            sections.append((f"remap primary={sch[0]} secondary={sch[1]}",
                             build_cells(obj, palette, args.scale, sch, args.height_lines, idx, args.strict_flags)))
    if args.compare:
        cmp_obj = dat.read_dat(args.compare)
        ct = cmp_obj.image_table()
        if ct:
            cidx = parse_range(args.range, len(ct.entries))
            sections.append(("COMPARE  " + describe(cmp_obj),
                             build_cells(cmp_obj, palette, args.scale, None, args.height_lines, cidx, args.strict_flags)))

    pages = layout(sections)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(pages) == 1:
        pages[0].save(out)
        print(out)
    else:
        for n, pg in enumerate(pages, 1):
            p = out.with_name(f"{out.stem}.p{n}{out.suffix}")
            pg.save(p)
            print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
