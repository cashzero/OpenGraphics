# OG_COMP26（fork 自製）
- 對應 vanilla：COMP26（Competitor）
- 內部名稱：OGCOMP26
- 遊戲內名稱：Agatha Axlegrease
- 設計概念：原創角色 Agatha Axlegrease（與 vanilla 第 26 位對手無關，只沿用其 AI 屬性）：女性、捲髮、眼鏡。卡通風格頭像，9 種表情 × 大小兩種尺寸，背景為公司色漸層。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py COMP26`），產生器與參數記錄在該腳本中；以 vanilla COMP26 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/competitor-OGCOMP26.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
