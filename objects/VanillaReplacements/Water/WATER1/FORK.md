# OG_WATER1（fork 覆寫上游）
- 對應 vanilla：WATER1（Water）
- 內部名稱：OGWATER1
- 覆寫原因：使用者核准以寫實風格覆寫上游地形素材（消除菱形格網接縫、提升色階與 3D 斜坡微浮雕質感）。
- 製作方式：`tools/gen/terrain.py --targets WATER1` 以高通濾波各向異性水平風浪場（∂H/∂y 微坡面反光）、物理透射＋菲涅耳反射海洋藍綠表（192..199）與 1px 波峰脊線動態閃光層重建全縮放層級。
- AI 工具：Antigravity（撰寫程序化水面產生器）
- 參考資料：無外部素材；僅沿用 DAT 結構、遮罩輪廓與 OpenLoco 繪製規範。
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-26 V1/V2：`tools/lint.py` 0 錯誤；`tools/v2_smoke.sh` PASS；`build/screenshots/zoom_water_08.png`、`zoom_river_04.png`、`zoom_desert_water_03.png` 及 `title_compare/cmp_03,04,08.png` 遊戲內實機對照目測通過（水平風浪連貫無雜訊／無斜條紋／無 64×32 重複亮斑，深海與淺灘透光層次清晰）。
