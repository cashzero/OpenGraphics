# OG_SIGS（fork 自製）
- 對應 vanilla：SIGS（TrainSignal）
- 內部名稱：OGSIGS
- 遊戲內名稱：Upper Arm Semaphore
- 設計概念：灰色號誌柱配紅色臂板（末端白條紋）與燈號；8 個視角，動畫逐格把臂板揚起（上象限式）。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py SIGS`），產生器與參數記錄在該腳本中；以 vanilla SIGS 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）；物件預覽 build/screenshots/m2/preview/OGSIGS.png 已檢視。未驗證：新遊戲沒有鐵路，號誌動畫尚未在地圖上看過
