#!/usr/bin/env python3
"""標題畫面（ROADMAP M6）：base/title/ → OpenLoco 的 Data/title.dat 與 Data/title.yml。install 只用標準函式庫，CI 也能直接執行。

  python3 tools/title.py build                 # 重建 base/title/title.dat（需要 OpenLoco fork 與 --with-base 的測試環境）
  python3 tools/title.py install <Data 目錄>   # 例：build/openloco-env/data/base/Data

build 的步驟：
1. .venv/bin/python tools/gen/title_heightmap.py → base/title/heightmap.png（地形）
2. STANDALONE=1 tools/run_openloco.sh build-scene base/title/title.yml → base/title/title.dat
   （OpenLoco fork 的 SceneBuilder 依場景腳本建造城鎮、鐵路、車輛…，模擬後存檔；腳本格式見 base/title/README.md）
建造時用的是測試環境裡的物件（tools/install_test_env.py --with-placeholders --with-base），存檔只以內部名稱引用物件，
所以玩家安裝的 OpenGraphics 物件包要有同樣的物件。

install 會寫出：
- title.dat：標題畫面的地圖存檔（OpenLoco 啟動時載入；沒有這個檔時 fork 會自動生成地圖）
- title.yml：鏡頭清單（base/title/camera.yml；fork 的 Title.cpp 依序移動鏡頭，取代原版寫死的座標）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TITLE = REPO / "base" / "title"


def install(data_dir: Path) -> bool:
    """把 title.dat 與鏡頭清單裝進 Data/。沒有 title.dat（還沒 build）時不裝，回傳 False。"""
    src = TITLE / "title.dat"
    if not src.exists():
        print(f"沒有 {src}（先執行 python3 tools/title.py build）；OpenLoco fork 會改用自動生成的標題地圖")
        return False
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, data_dir / "title.dat")
    shutil.copyfile(TITLE / "camera.yml", data_dir / "title.yml")
    print(f"標題畫面：{data_dir / 'title.dat'}、{data_dir / 'title.yml'}")
    return True


def build() -> int:
    venv_python = REPO / ".venv" / "bin" / "python"
    subprocess.run([str(venv_python), str(REPO / "tools" / "gen" / "title_heightmap.py")], check=True)
    out = REPO / "build" / "title" / "title.SV5"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    log = REPO / "build" / "logs" / "title_build.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, STANDALONE="1", TIMEOUT=os.environ.get("TIMEOUT", "900"))
    with log.open("w") as f:
        r = subprocess.run([str(REPO / "tools" / "run_openloco.sh"), "build-scene", str(TITLE / "title.yml"), "-o", str(out)],
                           env=env, stdout=f, stderr=subprocess.STDOUT)
    lines = [ln for ln in log.read_text(errors="replace").splitlines() if "build-scene" in ln]
    for ln in lines[-3:]:
        print(ln)
    if r.returncode != 0 or not out.exists():
        print(f"build-scene 失敗（exit {r.returncode}），完整紀錄：{log}", file=sys.stderr)
        return 1
    shutil.copyfile(out, TITLE / "title.dat")
    print(f"→ {TITLE / 'title.dat'}（{(TITLE / 'title.dat').stat().st_size // 1024} KiB）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    p = sub.add_parser("install")
    p.add_argument("data_dir", type=Path)
    args = ap.parse_args()
    if args.cmd == "build":
        return build()
    install(args.data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
