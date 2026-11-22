# OG_SNDD9（fork 自製）
- 對應 vanilla：SNDD9（Sound）
- 內部名稱：OGSNDD9
- 遊戲內名稱：Diesel Engine Loop 9
- 設計概念：柴油引擎循環音：每秒約 48 次爆發，每次為機體共鳴（198 Hz）的衰減振盪加雜訊，再加低頻隆隆聲；爆發數在循環長度內為整數，循環無接縫。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py SNDD9`），產生器與參數記錄在該腳本中；以 vanilla SNDD9 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；headless 不播放音效，**尚未試聽**
