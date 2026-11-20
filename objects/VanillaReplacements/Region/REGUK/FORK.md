# OG_REGUK（fork 自製）
- 對應 vanilla：REGUK（Region）
- 內部名稱：OGREGUK
- 遊戲內名稱：British Isles
- 設計概念：英國地區：沿用 vanilla REGUK 的結構與 cargo 設定，但選取時一併載入的物件（willLoad）只保留已有 OG 版本的項目，開新遊戲不會帶進 placeholder。預覽圖由本 repo 的 OG 房屋、樹與礦井 sprite 拼成。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py REGUK`），產生器與參數記錄在該腳本中；以 vanilla REGUK 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）；本物件即新遊戲使用的 region，物件預覽 build/screenshots/m2/preview/OGREGUK.png 已檢視
