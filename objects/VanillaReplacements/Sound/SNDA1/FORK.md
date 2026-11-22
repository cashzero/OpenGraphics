# OG_SNDA1（fork 自製）
- 對應 vanilla：SNDA1（Sound）
- 內部名稱：OGSNDA1
- 遊戲內名稱：Piston Airliner Drone
- 設計概念：活塞螺旋槳引擎：點火基頻與 8 個泛音、慢速起伏與氣流雜音，循環無接縫。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py SNDA1`），產生器與參數記錄在該腳本中；以 vanilla SNDA1 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；headless 不播放音效，**尚未試聽**
