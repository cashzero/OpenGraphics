# OG_OREMINE（fork 自製）
- 對應 vanilla：OREMINE（Industry）
- 內部名稱：OGOREMIN
- 遊戲內名稱：Iron Mine
- 設計概念：辦公室、階梯狀碎礦廠、礦石倉與輸送帶、公司色豎井井架、機具棚、工具房、選礦廠、礦石堆；地面為紅褐色礦土。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/industry_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；田地圖塊 `tools/gen/industry_fields.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_OREMINE.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py OREMINE`。以 vanilla OREMINE 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/industry-OGOREMIN.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2：移除過量公司色，改為深鋼豎井井架、暗石板階梯碎礦廠與鏽鋼礦倉；build/preview/b2_oremine.p1.png、build/screenshots/polish3/obj_OGOREMIN.png 檢視通過
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
- 2026-11-26 V1/V2（建物材質與光照升級）：`tools/blender/kit.py` 與 `static_rig.py` 修復垂直牆面 3D 磚紋映射、新增磚／切石／疊瓦／木板／茅草／灰泥／混凝土接縫＋3D Bump＋`AmbientOcclusion` 屋簷與窗框陰影，並以暖陽主光消除冷灰塑膠感；同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_02.png`、`cmp_04.png`、`cmp_05.png`）檢視通過。
- 2026-11-26 V1/V2（重工業金屬材質與建築幾何全面升級）：`tools/blender/kit.py` 與 `ops.py` 修正高金屬度在黑背景 EEVEE 反射死黑問題並新增鉚接鋼板焊縫＋縱向鐵鏽流痕＋冷中性工業混凝土地坪；`industry_recipes.py` / `COALPS/model.py` 升級重型儲槽、螺旋階梯、管橋、反應塔與球槽細節；同步更新 `.blend` 與全部 22 座工業建物原版 vs OG 對照圖（`build/screenshots/industry_compare_1..4.png`）與 Title 1:1 截圖（`cmp_01/06/09/10.png`）檢視通過。
- 2026-11-26 V1/V2（全部 22 座工業建物移除公司色 remap 與第二輪品質精修）：全面移除工業建物誤用的 `company` 材質並於量化加入 `--no-remap-colours`，全部 22 座工業建物皆達 0% remap（與原版一致）；新建 `tools/gen/smoke_fx.py` 取代 `COALPS`／`FACTORY` 的 3D 球狀煙霧為 2D 半透明紊流蒸氣／黑煙；修復 `WINDMILL`／`FARM`／`VINEYARD`／`SKICENT` 異常底板並升級 `SKICENT` 厚雪斜頂、`VINEYARD` 絲柏樹、`OILRIG` 紅白鑽塔、`SAWMILL` 儲木棚與 `COALPS` 冷卻塔／變電站；全部 4 張原版 vs OG 比較圖（`build/screenshots/industry_compare_1..4.png`）與 Title 1:1 截圖檢視通過。
- 2026-11-26 V1/V2（重設全部 8 組採礦建築）：全面捨棄偏暗冷灰方塊，改以暖石磚、重木棧橋、鏽鐵與赤鐵礦堆重設 v0 篩分礦堆站、v1 碎礦廠與木構斜棧橋、v2 寬幅貯礦大廳、v3 雙紅磚焙燒煙囪、v4 肋骨暗鋼貯礦圓頂、v5 原礦堆、v6 選礦分級廠＋高架儲礦倉＋輸送橋、v7 木格滿礦漏斗；`lint.py` 0 錯誤、0% remap，於 `build/screenshots/industry_compare_2.png` 檢視通過。
