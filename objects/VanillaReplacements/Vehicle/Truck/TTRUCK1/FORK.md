# OG_TTRUCK1（fork 自製）
- 對應 vanilla：TTRUCK1（Vehicle/Truck）
- 內部名稱：OGTTRUC1
- 遊戲內名稱：Brimmer Tank Lorry
- 設計概念：早期開放式駕駛座，後方為銀色圓筒油槽。
- 製作方式：程序化建模（`tools/gen/vehicle_table.py` 的配方 → `tools/gen/vehicle_recipes.py` 產生各狀態的幾何指令），
  `tools/blender/vehicle_rig.py` 依模板結構逐張渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_TTRUCK1.blend`（所有狀態並排）；建置指令 `tools/gen/build_vehicles.py TTRUCK1`。
  以 vanilla TTRUCK1 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 結構、張數與車身長度比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/vehicle-OGTTRUC1.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
