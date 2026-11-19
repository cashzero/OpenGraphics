#!/usr/bin/env bash
# V2 端到端冒煙測試：在「沒有 vanilla 物件」的環境中，用原版情境載入 OG 物件（+ placeholder）→ 模擬 → 截圖。
#   tools/v2_smoke.sh ["<情境名稱>.SC5"]      預設 "Boulder Breakers.SC5"
# 需要 OpenLoco fork 的 og-main（別名層 + screenshot 命令）。
# 產出：build/screenshots/v2_smoke/<情境>.png；任何一步失敗就以非 0 結束。
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
: "${LOCO_DATA_DIR:=$HOME/Locomotion/game}"
export LOCO_DATA_DIR
SCENARIO="${1:-Boulder Breakers.SC5}"
STEM="${SCENARIO%.*}"
OUT_PNG="$REPO/build/screenshots/v2_smoke/${STEM// /_}.png"
mkdir -p "$(dirname "$OUT_PNG")"

[ -f build/placeholders/manifest.json ] || python3 tools/make_placeholders.py
python3 tools/install_test_env.py --with-placeholders

# 只有 Data 與 Scenarios、沒有 ObjData 的 Locomotion 目錄：vanilla 物件一律不可用，只能靠別名層
NOOBJ="$REPO/build/loco-noobjdata"
mkdir -p "$NOOBJ"
ln -sfn "$LOCO_DATA_DIR/Data" "$NOOBJ/Data"
ln -sfn "$LOCO_DATA_DIR/Scenarios" "$NOOBJ/Scenarios"

LOG="$(mktemp)"
if ! LOCO_DATA_DIR="$NOOBJ" tools/run_openloco.sh simulate "$LOCO_DATA_DIR/Scenarios/$SCENARIO" 500 \
      -o "$REPO/build/openloco-env/v2_smoke.sv5" >"$LOG" 2>&1; then
  cat "$LOG"; echo "FAIL：simulate" >&2; exit 1
fi
grep -q "scenario ticks: 500" "$LOG" || { cat "$LOG"; echo "FAIL：模擬沒有跑滿 500 ticks" >&2; exit 1; }
grep -q "object aliases" "$LOG" || { cat "$LOG"; echo "FAIL：沒有載入別名表（OpenLoco 不是 fork 的 og-main？）" >&2; exit 1; }
grep -E "\[ERR\]" "$LOG" | grep -v "could not be found" || true
LOCO_DATA_DIR="$NOOBJ" tools/run_openloco.sh screenshot "$LOCO_DATA_DIR/Scenarios/$SCENARIO" 200 -o "$OUT_PNG" --size 1024x640 >"$LOG" 2>&1 \
  || { cat "$LOG"; echo "FAIL：screenshot" >&2; exit 1; }
rm -f "$LOG"
echo "PASS：$OUT_PNG（請用看圖工具檢視）"
