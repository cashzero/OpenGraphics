#!/usr/bin/env bash
# 在隔離測試環境中執行 OpenLoco（docs/PIPELINE.md V2）。參數原樣傳給 OpenLoco。
#   tools/run_openloco.sh simulate <存檔絕對路徑> 500 -o out.sv5
#   tools/run_openloco.sh screenshot <存檔絕對路徑> 200 -o <png 絕對路徑> --size 1024x640
# 環境變數（可覆寫）：LOCO_DATA_DIR、OPENLOCO_BIN、OPENLOCO_ENV、TIMEOUT
#   STANDALONE=1：不使用 Locomotion（需要 install_test_env.py --with-base），對應 OpenLoco fork 的 OPENLOCO_STANDALONE
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
: "${LOCO_DATA_DIR:=$HOME/Locomotion/game}"
: "${OPENLOCO_BIN:=$REPO/../OpenLoco/build/posix/Release/OpenLoco}"
: "${OPENLOCO_ENV:=$REPO/build/openloco-env}"
: "${TIMEOUT:=300}"

if [ ! -d "$OPENLOCO_ENV/data/objects" ]; then
  echo "測試環境不存在：先執行 python3 tools/install_test_env.py --with-placeholders --relink" >&2
  exit 2
fi
export XDG_CONFIG_HOME="$OPENLOCO_ENV" OPENLOCO_DATA_DIR="$OPENLOCO_ENV/data"
export SDL_VIDEO_DRIVER=offscreen SDL_AUDIO_DRIVER=dummy ALSOFT_DRIVERS=null
# Linux 版會在目前目錄建立 OpenLoco.lock，所以一定要在環境目錄裡執行
cd "$OPENLOCO_ENV"
if [ "${STANDALONE:-0}" = "1" ]; then
  # 不使用 Locomotion：OpenLoco fork 改用 $OPENLOCO_DATA_DIR/base（install_test_env.py --with-base）
  export OPENLOCO_STANDALONE=1
  exec timeout "$TIMEOUT" "$OPENLOCO_BIN" "$@"
fi
exec timeout "$TIMEOUT" "$OPENLOCO_BIN" --locomotion_path "$LOCO_DATA_DIR" "$@"
