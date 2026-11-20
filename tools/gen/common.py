"""產生器共用函式。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

PALETTE = dat.load_palette()


def template_entries(template: str) -> list[dat.G1Entry]:
    o = dat.read_dat(template)
    t = o.image_table()
    if t is None:
        raise SystemExit(f"{template} 沒有 image table")
    return t.entries


def write_sprites(out_dir: str | Path, frames: list[tuple[int, int, int, int, bytes]], flags: list[int] | None = None,
                  zoom: list[int] | None = None) -> None:
    """frames：[(w, h, x_offset, y_offset, pixels)]，pixels 為調色盤 index（0 = 透明）。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("*.png")) + list(out.glob("sprites.json")):
        old.unlink()
    meta = []
    for i, (w, h, x, y, px) in enumerate(frames):
        alpha = bytes(255 if v else 0 for v in px)
        dat.write_indexed_png(out / f"{i}.png", w, h, px, alpha, PALETTE)
        meta.append({"path": f"{i}.png", "x": x, "y": y,
                     "zoomOffset": (zoom[i] if zoom else 0), "flags": (flags[i] if flags else 0), "name": None})
    (out / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"寫出 {len(frames)} 張 sprite → {out}")
