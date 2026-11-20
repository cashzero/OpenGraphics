# OG_SNDS1（fork 自製）
- 對應 vanilla：SNDS1（Sound）
- 內部名稱：OGSNDS1
- 遊戲內名稱：Steam Idle Hiss
- 設計概念：蒸汽洩壓的嘶嘶聲，緩慢起伏，循環音效。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py SNDS1`），產生器與參數記錄在該腳本中；以 vanilla SNDS1 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）。未驗證：headless 執行不播放音效，需要人工試聽
