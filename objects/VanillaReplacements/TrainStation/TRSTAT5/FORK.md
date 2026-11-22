# OG_TRSTAT5（fork 自製）
- 對應 vanilla：TRSTAT5（TrainStation）
- 內部名稱：OGTRSTA5
- 遊戲內名稱：Country Halt
- 設計概念：鄉間小站：磚砌月台基座上鋪木板，木柱撐起人字瓦頂雨棚、簷口飾板為公司色；後側月台有一間木造候車亭；沒有雨棚的月台段有煤氣路燈與木長椅。
- 製作方式：`tools/gen/build_stations.py TRSTAT5` 以幾何指令建模（`OG_TRSTAT5.blend` 為各影像的模型並排），
  `tools/blender/vehicle_rig.py`（unit = tile，原點 = 圖塊角落）渲染 → `tools/quantize.py` → 依 OpenLoco 影像表重組
  （半透明玻璃由 `tools/gen/iso.py` 投影產生）→ `tools/pack.py`（以 vanilla TRSTAT5 為結構模板，只沿用結構、屬性與其他字串）
- AI 工具：Claude（撰寫建模指令與產生器程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/trainStation-OGTRSTA5.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
