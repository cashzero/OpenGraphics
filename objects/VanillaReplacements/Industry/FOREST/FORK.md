# OG_FOREST（fork 自製）
- 對應 vanilla：FOREST（Industry）
- 內部名稱：OGFOREST
- 遊戲內名稱：Timber Plantation
- 設計概念：原木林務小屋、原木吊架、原木堆；林地上的冷杉依 6 個階段長大，最後砍伐成樹樁。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/industry_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；田地圖塊 `tools/gen/industry_fields.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_FOREST.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py FOREST`。以 vanilla FOREST 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude／Gemini（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/industry-OGFOREST.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1／V2：林場田地人工林改用 `tools/gen/tree3d.py` 點雲冷杉（深針葉綠，與地圖樹木一致），並修正階段 6 樹樁繪製原點；`tools/lint.py` 0 錯誤；V1 已檢視 `build/preview/check_forest_new.png`，V2 已檢視標題場景截圖 `build/screenshots/polish/shot8_forest.png`，人工林色調已與周圍針葉林自然融合、砍伐區可見樹樁
