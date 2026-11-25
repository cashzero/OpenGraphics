#!/usr/bin/env python3
"""把 base/music/ 的音樂裝進 OpenLoco 的 Data/ 目錄（ROADMAP M5）。只用標準函式庫，CI 也能直接執行。

  python3 tools/music.py install <Data 目錄>   # 例：build/placeholders/base/Data、artifacts/base/Data
  python3 tools/music.py check                 # 檢查 tracks.json 與檔案是否一致

base/music/tracks.json 列出 OpenLoco 每個音樂時段（slot = OpenLoco 預期的檔名主檔名，例如 20s1、Rag2、CSS5）
要用哪一首 OpenMSX MIDI。install 會寫出：
- <slot>.mid：OpenLoco fork 找不到 <slot>.DAT 時會改讀同名的 .mid，並以同資料夾的 SoundFont 合成
- TimGM6mb.sf2：合成 MIDI 用的 GM SoundFont
- music.yml：slot → 曲名，fork 會用它替換點唱機顯示的曲名（Jukebox::applyMusicTitles）
- COPYING：GPL v2（OpenMSX 與 TimGM6mb 的授權）
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MUSIC = REPO / "base" / "music"

# OpenLoco Jukebox.cpp kMusicInfo 用到的 29 首 + 標題曲（Environment.cpp 的檔名，不含 Data/ 與 .DAT）
SLOTS = ["20s1", "20s2", "20s4", "50s1", "50s2", "70s1", "70s2", "70s3", "80s1", "90s1", "90s2", "rag3", "Chrysanthemum",
         "Eugenia", "Rag2", "Rag1", "20s3", "40s1", "40s2", "50s3", "40s3", "80s2", "60s1", "80s3", "60s2", "60s3", "80s4",
         "20s5", "20s6", "CSS5"]


def load() -> dict:
    return json.loads((MUSIC / "tracks.json").read_text())


def check(tracks: dict) -> list[str]:
    errors = []
    slots = [t["slot"] for t in tracks["tracks"]]
    if sorted(slots) != sorted(SLOTS):
        errors.append(f"tracks.json 的 slot 與 OpenLoco 不符：缺 {sorted(set(SLOTS) - set(slots))}，多 {sorted(set(slots) - set(SLOTS))}")
    for t in tracks["tracks"]:
        if not (MUSIC / "midi" / t["file"]).is_file():
            errors.append(f"找不到 base/music/midi/{t['file']}")
        if not t.get("title"):
            errors.append(f"{t['slot']} 沒有曲名")
    if not (MUSIC / tracks["soundfont"]).is_file():
        errors.append(f"找不到 base/music/{tracks['soundfont']}")
    return errors


def install(data_dir: Path, tracks: dict) -> int:
    data_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# 由 tools/music.py 依 base/music/tracks.json 產生：音樂檔名（slot）→ 點唱機顯示的曲名", f"# {tracks['source']}"]
    for t in tracks["tracks"]:
        shutil.copyfile(MUSIC / "midi" / t["file"], data_dir / f"{t['slot']}.mid")
        lines.append(f"{t['slot']}: {json.dumps(t['title'], ensure_ascii=False)}")
    (data_dir / "music.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.copyfile(MUSIC / tracks["soundfont"], data_dir / tracks["soundfont"])
    shutil.copyfile(MUSIC / "COPYING", data_dir / "COPYING-music")
    return len(tracks["tracks"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install")
    p.add_argument("data_dir", type=Path)
    sub.add_parser("check")
    args = ap.parse_args(argv)
    tracks = load()
    errors = check(tracks)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.cmd == "install":
        n = install(args.data_dir, tracks)
        print(f"音樂：{n} 首 MIDI + {tracks['soundfont']} + music.yml → {args.data_dir}")
    else:
        print(f"OK：{len(tracks['tracks'])} 首")
    return 0


if __name__ == "__main__":
    sys.exit(main())
