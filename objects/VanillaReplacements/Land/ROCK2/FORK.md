# OG_ROCK2（fork 覆寫上游）
- 對應 vanilla：ROCK2（Land）
- 內部名稱：OGROCK2
- 覆寫原因：使用者核准以寫實風格覆寫上游地形素材（消除菱形格網接縫、提升色階與 3D 斜坡微浮雕質感）。
- 製作方式：`tools/gen/terrain.py --targets ROCK2` 以週期無縫 3D PBR 高度場＋精準等角法線算光產生全部縮放層級、邊緣融合貼圖與變化磚。
- AI 工具：Antigravity（撰寫程序化 PBR 地形產生器）
- 參考資料：無外部素材；僅沿用 DAT 結構、遮罩輪廓與 OpenLoco 繪製規範。
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-26 V1/V2：`tools/lint.py` 0 錯誤；`build/screenshots/title_compare/cmp_01..10.png` 遊戲內實機對照目測通過。
