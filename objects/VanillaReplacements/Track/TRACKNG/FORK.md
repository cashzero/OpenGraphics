# OG_TRACKNG（fork 自製）
- 對應 vanilla：TRACKNG（Track）
- 內部名稱：OGTRACKN
- 遊戲內名稱：Light Railway Track
- 設計概念：窄軌：灰色煤渣道碴、間距較寬的深色木枕、軌距較窄（約標準軌的 2/3）的鋼軌；可合併片段分成道碴／枕木／鋼軌三層，坡道類合成一張；工具列為 16 格旋轉圖示，另有拿起／放下車輛圖示。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py TRACKNG`），產生器與參數記錄在該腳本中；以 vanilla TRACKNG 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/track-OGTRACKN.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
