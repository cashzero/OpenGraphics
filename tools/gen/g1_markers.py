#!/usr/bin/env python3
"""g1 的地圖標記（ROADMAP M4）：高度標記 3 套 × 256 個、車輛路線的編號圓圈 64 個。輸出 base/g1/markers/。

  .venv/bin/python tools/gen/g1_markers.py

- 高度標記（Paint/PaintTileDecorations.cpp getHeightMarkerImage）：index = 相對海平面的高度 + 128（−128…127）；
  三套依設定顯示：_u = 高度單位（N）、_i = 英尺（N × 16）、_m = 公尺（N × 5）（Localisation/Formatting.cpp 的換算）。
  軌道／道路上以 Colour::blue、地面上以 mutedAvocadoGreen 換色 → 底框用 primary remap 色號，數字用固定的白色。
- 編號圓圈（Ui/Windows/Vehicle.cpp）：以 Colour::white 換色 → 圓用 primary remap，數字用深色。
數字字形取自 tools/gen/g1_fonts.py 的 small 字型（3 × 5 點陣）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import g1_fonts  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "markers"
REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
WHITE, DARK = 0x0A + 11, 0x0A + 1


def glyph_cells(text):
    """文字 → 墨水點 {(x, y)}（small 字型，每字間隔 1 px）與總寬。"""
    pts, x = set(), 0
    for ch in text:
        top, rows = g1_fonts.SMALL[ch]
        w = max(len(r) for r in rows)
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                if v == "#":
                    pts.add((x + c, top + r))
        x += w + 1
    return pts, x - 1


def height_marker(value):
    pts, tw = glyph_cells(str(value))
    w, h = tw + 4, 7
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            corner = (x in (0, w - 1)) and (y in (0, h - 1))
            if corner:
                continue
            border = x in (0, w - 1) or y in (0, h - 1)
            px[y * w + x] = REMAP[2] if border else REMAP[7]
    for (x, y) in pts:
        px[(y + 1) * w + x + 2] = WHITE
    return (w, h, -(w // 2), -3, bytes(px))


def number_circle(n):
    pts, tw = glyph_cells(str(n))
    w = h = 9
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            d = (x - 4) ** 2 + (y - 4) ** 2
            if d <= 19:
                px[y * w + x] = REMAP[7] if d > 14 else REMAP[11]     # 淺色外圈＋更淺的底，深色數字才清楚
    ox = (w - tw) // 2
    for (x, y) in pts:
        px[(y + 2) * w + x + ox] = DARK
    return (w, h, 0, 0, bytes(px))


def build():
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e["i"] for e in cat["entries"] if e.get("name")}
    frames = []
    for n in range(-128, 128):
        key = f"neg_{-n}" if n < 0 else str(n)
        for suffix, factor in (("u", 1), ("i", 16), ("m", 5)):
            frames.append((ids[f"height_marker_{key}_{suffix}"], height_marker(n * factor)))
    for k in range(64):                                       # number_circle_NN 顯示 NN（kNumberCircle 從 _01 開始，_00 沒用到）
        frames.append((ids[f"number_circle_{k:02d}"], number_circle(k)))
    return frames


def main() -> int:
    frames = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    pal = dat.load_palette()
    meta = []
    for idx, (w, h, x, y, px) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, w, h, px, bytes(255 if v else 0 for v in px), pal)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"寫出 {len(frames)} 張 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
