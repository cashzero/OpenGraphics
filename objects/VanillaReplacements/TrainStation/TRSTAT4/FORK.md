# OG_TRSTAT4（fork 自製）
- 對應 vanilla：TRSTAT4（TrainStation）
- 內部名稱：OGTRSTA4
- 遊戲內名稱：Concourse Station
- 設計概念：1960 年代中期城市站：深色鋪面月台與黃色警示線，白色混凝土圓柱撐起厚實的平頂混凝土雨棚，屋頂中央一道玻璃天窗（半透明），簷口為公司色。
- 製作方式：`tools/gen/build_stations.py TRSTAT4` 以幾何指令建模（`OG_TRSTAT4.blend` 為各影像的模型並排），
  `tools/blender/vehicle_rig.py`（unit = tile，原點 = 圖塊角落）渲染 → `tools/quantize.py` → 依 OpenLoco 影像表重組
  （半透明玻璃由 `tools/gen/iso.py` 投影產生）→ `tools/pack.py`（以 vanilla TRSTAT4 為結構模板，只沿用結構、屬性與其他字串）
- AI 工具：Claude（撰寫建模指令與產生器程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/trainStation-OGTRSTA4.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2：改為現代雙月台天窗雨棚與公司色簷口；build/preview/check_trstat4_new.png、build/screenshots/polish3/shot3_city.png 檢視通過
