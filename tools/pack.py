#!/usr/bin/env python3
"""P3 打包：以模板 DAT 為基礎，換上新的 sprite 與名稱，產生 OG 物件 DAT（需要 .venv 的 Pillow）。

  .venv/bin/python tools/pack.py --template <模板.dat> --sprites <sprites 資料夾> \\
      --name OGXXXXXX [--display "遊戲內名稱"] -o build/dat/<NAME>/OG_<NAME>.dat

- 模板提供物件結構、屬性與其他字串（可以是 vanilla、上游 OG 或自己的物件）。
- <sprites 資料夾> 內有 sprites.json（格式同 ObjectEditor／tools/dat.py extract）與 PNG：
  索引色 PNG 直接使用調色盤 index；RGBA PNG 必須只含 Loco 調色盤中的顏色（先用 tools/quantize.py）。
  index 0 或 alpha < 128 視為透明。
- sprite 一律以 RLE 編碼（G1 flags = hasTransparency | isRLECompressed），保留 sprites.json 中的
  hasZoomSprites / noZoomDraw / duplicatePrevious 旗標與 zoomOffset。
- 預設 sprite 數量必須與模板相同（--allow-count-change 可放寬，例如車輛屬性改變時）。
- 寫出後會重新讀取驗證：checksum、解碼後像素與輸入一致。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("需要 Pillow：請用 .venv/bin/python 執行")

KEEP_FLAGS = dat.G1_HAS_ZOOM | dat.G1_NO_ZOOM_DRAW | dat.G1_DUPLICATE_PREVIOUS


def load_indices(path: Path, palette: list[tuple[int, int, int]]) -> tuple[int, int, bytes]:
    """回傳 (w, h, pixels)，透明為 index 0。"""
    im = Image.open(path)
    w, h = im.size
    if im.mode == "P":
        px = bytearray(im.tobytes())
        trns = im.info.get("transparency")
        if isinstance(trns, int):
            px = bytearray(0 if v == trns else v for v in px)
        elif isinstance(trns, (bytes, bytearray)):
            px = bytearray(0 if (v < len(trns) and trns[v] < 128) else v for v in px)
        return w, h, bytes(px)
    rgba = im.convert("RGBA")
    lookup = {c: i for i, c in enumerate(palette) if 10 <= i <= 0xFE}
    out = bytearray(w * h)
    raw = rgba.tobytes()
    for k in range(w * h):
        r, g, b, a = raw[4 * k:4 * k + 4]
        if a < 128:
            continue
        idx = lookup.get((r, g, b))
        if idx is None:
            raise ValueError(f"{path}: 像素 ({k % w},{k // w}) 顏色 {(r, g, b)} 不在 Loco 調色盤中（先用 tools/quantize.py）")
        out[k] = idx
    return w, h, bytes(out)


def encode_rle(w: int, h: int, px: bytes) -> bytes:
    """G1 RLE：每列一個 u16 offset，之後每列為若干 [長度|列尾旗標][起始 x][像素…]。"""
    rows = []
    for y in range(h):
        row = px[y * w:(y + 1) * w]
        runs = []
        x = 0
        while x < w:
            if row[x] == 0:
                x += 1
                continue
            start = x
            while x < w and row[x] != 0 and x - start < 127:
                x += 1
            runs.append((start, row[start:x]))
        if not runs:
            rows.append(bytes([0x80, 0]))
            continue
        b = bytearray()
        for i, (start, pixels) in enumerate(runs):
            last = 0x80 if i == len(runs) - 1 else 0
            b += bytes([len(pixels) | last, start]) + pixels
        rows.append(bytes(b))
    offsets = bytearray()
    pos = 2 * h
    for r in rows:
        offsets += struct.pack("<H", pos)
        pos += len(r)
    data = bytes(offsets) + b"".join(rows)
    if pos > 0xFFFF:
        raise ValueError("sprite 太大，RLE offset 超過 16 bit")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--sprites", required=True)
    ap.add_argument("--name", required=True, help="8 字元以內的內部名稱，例如 OGCTRUC1")
    ap.add_argument("--display", help="遊戲內名稱（所有語言都改成這個）；不指定則沿用模板")
    ap.add_argument("--allow-count-change", action="store_true")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args(argv)

    tpl = dat.read_dat(args.template)
    table = tpl.image_table()
    if table is None:
        sys.exit(f"模板 {args.template} 沒有 image table")
    sprites_dir = Path(args.sprites)
    meta = json.loads((sprites_dir / "sprites.json").read_text())
    if len(meta) != len(table.entries) and not args.allow_count_change:
        sys.exit(f"sprite 數量 {len(meta)} 與模板 {len(table.entries)} 不同（確定要改請加 --allow-count-change）")

    palette = dat.load_palette()
    entries: list[dat.G1Entry] = []
    image_data = bytearray()
    expected: list[tuple[int, int, bytes] | None] = []
    for i, m in enumerate(meta):
        flags = int(m.get("flags", 0)) & KEEP_FLAGS
        if flags & dat.G1_DUPLICATE_PREVIOUS:
            entries.append(dat.G1Entry(0, 0, 0, int(m["x"]), int(m["y"]), flags, int(m.get("zoomOffset", 0))))
            expected.append(None)
            continue
        w, h, px = load_indices(sprites_dir / m["path"], palette)
        enc = encode_rle(w, h, px) if w and h else b""
        entries.append(dat.G1Entry(len(image_data), w, h, int(m["x"]), int(m["y"]),
                                   flags | dat.G1_HAS_TRANSPARENCY | dat.G1_IS_RLE, int(m.get("zoomOffset", 0))))
        image_data += enc
        expected.append((w, h, px))

    data = tpl.data
    if args.display:
        text = args.display.encode("latin1")
        data = dat.replace_first_string_table(tpl, lambda _s: text)
        obj = dat.DatObject(None, tpl.flags, tpl.name, 0, tpl.encoding, data)
        table = dat.find_image_table(data, obj.strings_offset() or 0)
    data = dat.replace_image_table(data, table.offset, entries, bytes(image_data))

    name = args.name.encode("latin1")
    if len(name) > 8:
        sys.exit("內部名稱最多 8 字元")
    flags = (tpl.flags & ~0xC0) | (3 << 6)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    dat.write_dat(out, flags, name.ljust(8), data, dat.ENC_RLE_SINGLE)

    # 驗證
    chk = dat.read_dat(out)
    assert chk.checksum_ok(), "checksum 驗證失敗"
    ct = chk.image_table()
    assert ct is not None and len(ct.entries) == len(entries)
    for i, exp in enumerate(expected):
        w, h, _x, _y, px, al = dat.decode_sprite(ct, i)
        if exp is None:
            continue
        ew, eh, epx = exp
        got = bytes(px[k] if al[k] else 0 for k in range(w * h))
        if (w, h) != (ew, eh) or got != epx:
            sys.exit(f"驗證失敗：sprite #{i} 解碼後與輸入不同")
    print(f"寫出 {out}：{chk.type_name} {chk.name_str!r} display={chk.display_name()!r} "
          f"sprites={len(entries)} checksum OK，解碼驗證通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
