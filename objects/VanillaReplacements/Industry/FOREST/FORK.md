# OG_FOREST（fork 自製）
- 對應 vanilla：FOREST（Industry）
- 內部名稱：OGFOREST
- 遊戲內名稱：Timber Plantation
- 設計概念：原木林務小屋、原木吊架、原木堆；林地上的冷杉依 6 個階段長大，最後砍伐成樹樁。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/industry_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；田地圖塊 `tools/gen/industry_fields.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_FOREST.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py FOREST`。以 vanilla FOREST 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude／Gemini（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/industry-OGFOREST.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1／V2：林場田地人工林改用 `tools/gen/tree3d.py` 點雲冷杉（深針葉綠，與地圖樹木一致），並修正階段 6 樹樁繪製原點；`tools/lint.py` 0 錯誤；V1 已檢視 `build/preview/check_forest_new.png`，V2 已檢視標題場景截圖 `build/screenshots/polish/shot8_forest.png`，人工林色調已與周圍針葉林自然融合、砍伐區可見樹樁
- 2026-11-25 V1/V2：配合新版 tree3d.py 重建人工林冷杉圖塊；build/screenshots/title_compare/og_own_title_grid.png 檢視通過
- 2026-11-25 V1/V2（隨樹木暖陽光照重編）：依新版 `tree3d.py` 暖陽色帶重產林場冷杉並驗證 `og_own_title_grid.png`（OG 08）通過。
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
- 2026-11-26 V1/V2（建物材質與光照升級）：`tools/blender/kit.py` 與 `static_rig.py` 修復垂直牆面 3D 磚紋映射、新增磚／切石／疊瓦／木板／茅草／灰泥／混凝土接縫＋3D Bump＋`AmbientOcclusion` 屋簷與窗框陰影，並以暖陽主光消除冷灰塑膠感；同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_02.png`、`cmp_04.png`、`cmp_05.png`）檢視通過。
- 2026-11-26 V1/V2（全部 22 座工業建物移除公司色 remap 與第二輪品質精修）：全面移除工業建物誤用的 `company` 材質並於量化加入 `--no-remap-colours`，全部 22 座工業建物皆達 0% remap（與原版一致）；新建 `tools/gen/smoke_fx.py` 取代 `COALPS`／`FACTORY` 的 3D 球狀煙霧為 2D 半透明紊流蒸氣／黑煙；修復 `WINDMILL`／`FARM`／`VINEYARD`／`SKICENT` 異常底板並升級 `SKICENT` 厚雪斜頂、`VINEYARD` 絲柏樹、`OILRIG` 紅白鑽塔、`SAWMILL` 儲木棚與 `COALPS` 冷卻塔／變電站；全部 4 張原版 vs OG 比較圖（`build/screenshots/industry_compare_1..4.png`）與 Title 1:1 截圖檢視通過。
