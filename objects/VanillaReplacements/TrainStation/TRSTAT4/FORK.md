# OG_TRSTAT4（fork 自製）
- 對應 vanilla：TRSTAT4（TrainStation）
- 內部名稱：OGTRSTA4
- 遊戲內名稱：Concourse Terminal
- 設計概念：現代都會銀鋼圓拱玻璃車站：深灰混凝土基座與鋪石月台、標誌性公司色 V 型斜鋼骨支撐桁架、銀色空間桁架大圓拱與半透明玻璃穹頂（約 5% 優雅公司色點綴）。
- 製作方式：`tools/gen/build_stations.py TRSTAT4` 以幾何指令建模（`OG_TRSTAT4.blend` 為各影像的模型並排），
  `tools/blender/vehicle_rig.py`（unit = tile，原點 = 圖塊角落）渲染 → `tools/quantize.py` → 依 OpenLoco 影像表重組
  （半透明玻璃由 `tools/gen/iso.py` 投影產生）→ `tools/pack.py`（以 vanilla TRSTAT4 為結構模板，只沿用結構、屬性與其他字串）
- AI 工具：Claude（撰寫建模指令與產生器程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-26 V1/V2：依真實鐵道建築全面重製（維多利亞鍛鐵圓拱、現代 V 型斜撐玻璃圓拱、古典雙弧銅綠雨棚與寫實月台設施）；`tools/lint.py` 0 錯誤，V1 與 V2 遊戲內截圖目測通過。
