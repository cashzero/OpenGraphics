# OG_COALMINE（fork 自製）
- 對應 vanilla：COALMINE（Industry）
- 內部名稱：OGCOALMI
- 遊戲內名稱：Colliery
- 設計概念：煤礦：紅磚絞車房配公司色鋼構井架（天輪轉動 4 格動畫）、架高煤倉、選煤廠與煙囪；地面為煤場、碎石與泥土。
- 製作方式：Blender 5.2 程序化建模（`model.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_COALMINE.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py COALMINE`。以 vanilla COALMINE 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）；地圖截圖 build/screenshots/newgame/industry_*.png 已檢視：建築、動畫部件、地面圖塊與公司色正常
