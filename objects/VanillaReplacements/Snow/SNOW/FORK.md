# OG_SNOW（fork 覆寫上游版）
- 對應 vanilla：SNOW（Snow）
- 內部名稱：OGSNOW
- 遊戲內名稱：Snow
- 設計概念：柔和的風吹雪丘與淡冰藍斜坡陰影（覆寫原上游版 `OG_SNOW`，修正斜坡誤用 index 253–254 造成遊戲內黑點及雜訊過重的問題；經使用者於 2026-11-25 明確同意覆寫）。
- 製作方式：程序化產生器 `tools/gen/snow.py`，從 `OG_GRASS1` 萃取 19 種坡度明暗場，疊加低頻柔和風吹雪丘紋理，全部嚴格限定於 Locomotion 調色盤冰藍—雪白色階（index 16–21、129），保留原始非 RLE 旗標與 `zoom_offset`。
- AI 工具：Antigravity（撰寫 `tools/gen/snow.py`）
- 參考資料：無外部素材；僅檢視原版雪地色階分布與斜坡明暗比例
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-25 V1：`tools/lint.py` 0 錯誤；`build/preview/check_snow_new.png` 已檢視，0 個超出色盤 index（無黑點）。
- 2026-11-25 V2：build/screenshots/title_compare/cmp_09.png 與 og_own_title_grid.png（OG 07）檢視通過，雪坡柔和平滑無黑點
