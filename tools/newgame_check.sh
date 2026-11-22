#!/usr/bin/env bash
# 開新遊戲驗收（ROADMAP M2）：standalone 模式（沒有任何 Locomotion 檔案）只用 repo 物件 + placeholder
#   1. new-game：依正常的開新遊戲流程選物件（指定的 region 與物件優先，其餘必選類型自動補齊）→ 物件選擇驗證
#   2. simulate 一個遊戲年（35,100 ticks）不崩潰
#   3. 統計存檔用到的物件來自 repo 還是 placeholder（tools/s5.py info --origin）
#   4. 截圖：產業與城鎮各數張，輸出到 build/screenshots/newgame/（**必須親自看圖**）
#
#   tools/newgame_check.sh                    預設物件清單（M2 的 OG_REGUK + 核心物件）
#   SELECT=OGREGUK,OGCOALMI tools/newgame_check.sh
#   MAX_PLACEHOLDERS=30 tools/newgame_check.sh   placeholder 超過此數量就失敗（預設 30）
#
# 需要 OpenLoco fork 的 og-main（new-game、screenshot --centre town:N／industry:NAME、standalone 模式）。
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

: "${SELECT:=OGREGUK,OGCOALMI,OGCOALPS,OGLCROS4,OGSIGS,OGBLDHO4,OGBLDHO7,OGBLDHO2,OGBLDCT3,OGBLDCT1,OGOAK,OGBEECH,OGBIRCH,OGSCPINE,OGRFIR}"
: "${TICKS:=35100}"
: "${MAX_PLACEHOLDERS:=30}"
: "${SHOTS:=industry:OGCOALMI industry:OGCOALPS town:0 town:3}"
OUT="$REPO/build/tests/newgame"
SHOT_DIR="$REPO/build/screenshots/newgame"
mkdir -p "$OUT" "$SHOT_DIR"
export STANDALONE=1

[ -f build/placeholders/manifest.json ] || python3 tools/make_placeholders.py
.venv/bin/python tools/g1.py build -o build/placeholders/base/Data/g1.DAT
python3 tools/install_test_env.py --with-placeholders --with-base

LOG="$OUT/newgame.log"
tools/run_openloco.sh new-game 0 -o "$OUT/new.SV5" --select "$SELECT" >"$LOG" 2>&1 \
  || { cat "$LOG"; echo "FAIL：new-game（物件選擇沒有通過驗證或建立失敗）" >&2; exit 1; }
grep -q "Object selection valid" "$LOG" || { cat "$LOG"; echo "FAIL：物件選擇沒有通過驗證" >&2; exit 1; }
if grep -q "could not be selected" "$LOG"; then
  grep "could not be selected" "$LOG"; echo "FAIL：有指定的物件選不進去" >&2; exit 1
fi

tools/run_openloco.sh simulate "$OUT/new.SV5" "$TICKS" -o "$OUT/after.SV5" >"$LOG" 2>&1 \
  || { cat "$LOG"; echo "FAIL：simulate" >&2; exit 1; }
grep -q "scenario ticks: $TICKS" "$LOG" || { cat "$LOG"; echo "FAIL：模擬沒有跑滿 $TICKS ticks" >&2; exit 1; }

python3 tools/s5.py info "$OUT/after.SV5" --origin --max-placeholders "$MAX_PLACEHOLDERS" \
  || { echo "FAIL：placeholder 超過 $MAX_PLACEHOLDERS 個或有來源不明的物件" >&2; exit 1; }

for target in $SHOTS; do
  png="$SHOT_DIR/${target/:/_}.png"
  tools/run_openloco.sh screenshot "$OUT/after.SV5" 0 -o "$png" --size 640x400 --centre "$target" >"$LOG" 2>&1 \
    || { cat "$LOG"; echo "FAIL：screenshot $target" >&2; exit 1; }
done
rm -f "$LOG"
echo "PASS：截圖在 $SHOT_DIR（請用看圖工具檢視：核心物件不可以是 placeholder 的橘色格紋）"
