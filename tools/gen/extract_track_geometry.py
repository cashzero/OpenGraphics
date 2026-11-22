#!/usr/bin/env python3
"""從 OpenLoco 原始碼抽出軌道／道路片段的幾何資料，存成 tools/gen/data/track_geometry.json。

軌道類物件（track、trackExtra、road）的每張 sprite 都對應「某個片段、某一格（sequence）、某個方向」，
程序化繪製（tools/gen/track_iso.py）需要知道每個片段在世界座標中的中心線與佔用的圖塊。
這些是遊戲的幾何資料（列車行進路徑、圖塊配置、影像編號表），不是圖像素材；來源為 OpenLoco（MIT）：

- src/Map/Track/TrackData.cpp      trackPiece{N}／roadPiece{N}：每格 (index, x, y, z)，方向 0
- src/Map/Track/SubpositionData.cpp _4D9724（軌道）、_4D9DE4（道路，左側通行表）：每個片段 × 方向的中心線
- include/OpenLoco/Objects/{Track,TrackExtra,Road}Object.h ImageIds：影像名稱 → 編號

  python3 tools/gen/extract_track_geometry.py [--openloco ../OpenLoco]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tools" / "gen" / "data" / "track_geometry.json"


def parse_pieces(src: str, prefix: str) -> dict[int, list[list[int]]]:
    out = {}
    for m in re.finditer(rf"const std::array<PreviewTrack, \d+> {prefix}(\d+) = \{{(.*?)\n    \}};", src, re.S):
        tiles = []
        for t in re.finditer(r"PreviewTrack\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)", m.group(2)):
            tiles.append([int(v) for v in t.groups()])
        out[int(m.group(1))] = tiles
    return out


def parse_moveinfo(src: str) -> dict[str, list[list[int]]]:
    out = {}
    for m in re.finditer(r"static constexpr auto (moveInfo\w+) = std::to_array<MoveInfo>\(\s*\{(.*?)\}\);", src, re.S):
        pts = [[int(a), int(b), int(c)] for a, b, c in re.findall(r"\{\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}", m.group(2))]
        out[m.group(1)] = pts
    return out


def table_names(src: str, name: str) -> list[str]:
    m = re.search(rf"{name} = (.*?)\}}\);|{name} = (.*?)\n    \}};", src, re.S)
    body = m.group(1) or m.group(2)
    return re.findall(r"\b(moveInfo\w+)\b", body)


def parse_image_ids(src: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    ns = None
    for line in src.splitlines():
        m = re.match(r"\s*namespace (\w+)", line)
        if m:
            ns = m.group(1)
        m = re.match(r"\s*constexpr uint32_t (k\w+) = (\d+);", line)
        if m:
            out.setdefault(ns, {})[m.group(1)] = int(m.group(2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--openloco", default=str(REPO.parent / "OpenLoco"))
    args = ap.parse_args()
    base = Path(args.openloco) / "src" / "OpenLoco"
    td = (base / "src/Map/Track/TrackData.cpp").read_text()
    sp = (base / "src/Map/Track/SubpositionData.cpp").read_text()
    moves = parse_moveinfo(sp)

    track_tbl = table_names(sp, "_4D9724")
    track_paths = {}
    for tid in range(len(track_tbl) // 8):
        track_paths[tid] = [moves[track_tbl[tid * 8 + d]] for d in range(4)]
    # 道路：_4D9DE4[0][lane][roadId * 8 + dir]（只取不變換車道的 A0；L0／L1 = 兩條車道）
    road_tbl = table_names(sp, "_4D9DE4")                 # 依序：A0L0、A0L1、A1L0、A1L1，各 80 個
    road_paths = {}
    for rid in range(10):
        road_paths[rid] = [[moves[road_tbl[lane * 80 + rid * 8 + d]] for lane in (0, 1)] for d in range(4)]

    images = {}
    for key, fn in (("track", "TrackObject.h"), ("trackExtra", "TrackExtraObject.h"), ("road", "RoadObject.h")):
        images[key] = parse_image_ids((base / "include/OpenLoco/Objects" / fn).read_text())

    data = {
        "source": "OpenLoco src/Map/Track/{TrackData,SubpositionData}.cpp, include/OpenLoco/Objects/*Object.h",
        "track": {"pieces": parse_pieces(td, "trackPiece"), "paths": track_paths},
        "road": {"pieces": parse_pieces(td, "roadPiece"), "paths": road_paths},
        "images": images,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"軌道片段 {len(data['track']['pieces'])}、軌道路徑 {len(track_paths)}、道路片段 {len(data['road']['pieces'])} → {OUT}"
          f"（{OUT.stat().st_size // 1024} KB）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
