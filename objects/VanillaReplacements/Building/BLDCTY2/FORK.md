# OG_BLDCTY2（fork 自製）
- 對應 vanilla：BLDCTY2（Building）
- 內部名稱：OGBLDCT2
- 遊戲內名稱：Concrete Office Block
- 設計概念：2×2 的混凝土辦公大樓，帶狀窗，頂部兩級退縮與天線。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/building_table.py` 的配方 → `tools/gen/building_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_BLDCTY2.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py BLDCTY2`。以 vanilla BLDCTY2 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/building-OGBLDCT2.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2：改為凹入深色屋頂甲板＋屋頂機房／水塔／冷卻機組，帶狀窗補上立面直柱；build/screenshots/polish3/shot3_city.png 檢視通過
