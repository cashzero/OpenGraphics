# OG_YEW（fork 自製）
- 對應 vanilla：YEW（Tree）
- 內部名稱：OGYEW
- 遊戲內名稱：Churchyard Yew
- 設計概念：低矮樹幹、寬大濃密的常綠圓頂紫杉，橄欖深綠。含陰影。
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py YEW`），產生器與參數記錄在該腳本中；以 vanilla YEW 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/tree-OGYEW.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2：全面升級 tree3d.py（對齊原版纖細樹幹、低分叉、通透羽狀葉冠、高對比暖陽光影、落葉針葉樹秋紅與冬枯、連續幾何雪帽、沙漠植物特化）；build/screenshots/title_compare/compare_sheet_1.png 與 compare_sheet_2.png 1:1 檢視通過
- 2026-11-25 V1/V2（全樹木暖陽光照與色帶調校）：修正 `tree3d.py` AO 雙重乘算壓暗並對齊 Locomotion 暖陽橄欖綠／森林綠色帶；V1 與 V2 Title 1:1（`compare_sheet_1.png`、`compare_sheet_2.png`）檢視通過。
- 2026-11-27 V1/V2：依建築比例將樹木高度、樹冠、陰影與淨空高度同步縮減至 0.45×（沙漠低矮仙人掌／絲蘭 0.62×、約書亞樹 0.50×）；39 個樹木 DAT 通過 tools/lint.py（0 錯誤）與 tools/v2_smoke.sh 及 title_compare 實機截圖檢視。
