# OG_CLIM6（fork 自製）
- 對應 vanilla：CLIM6（Climate）
- 內部名稱：OGCLIM6
- 遊戲內名稱：Snowless Climate
- 設計概念：無雪氣候：季節長度與 OG_CLIM3 相近，雪線設為最高（不會下雪）。季節長度 60/79/99/79（總和與模板相同）。沒有圖片。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py CLIM6`），產生器與參數記錄在該腳本中；以 vanilla CLIM6 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/climate-OGCLIM6.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
