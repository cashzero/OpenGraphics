# OG_BLDHOUS9（fork 自製）
- 對應 vanilla：BLDHOUS9（Building）
- 內部名稱：OGBLDHO9
- 遊戲內名稱：Brick Cottage
- 設計概念：深色磚造小屋，公司色山形屋頂。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/building_table.py` 的配方 → `tools/gen/building_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_BLDHOUS9.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py BLDHOUS9`。以 vanilla BLDHOUS9 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/building-OGBLDHO9.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
- 2026-11-26 V1/V2（建物材質與光照升級）：`tools/blender/kit.py` 與 `static_rig.py` 修復垂直牆面 3D 磚紋映射、新增磚／切石／疊瓦／木板／茅草／灰泥／混凝土接縫＋3D Bump＋`AmbientOcclusion` 屋簷與窗框陰影，並以暖陽主光消除冷灰塑膠感；同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_02.png`、`cmp_04.png`、`cmp_05.png`）檢視通過。
- 2026-11-26 V1/V2：全 73 棟建築全面翻修為真實建築美學（移除非總部公司色屋頂與雨遮、修正燈塔斷頭與電波塔過細、升級三座教堂／古堡／音樂廳／法院／5 階段總部、住宅立體側翼門廊圍籬與中性砂土美式庭院、城市建築飽滿佔地與圓柱／熨斗／切角／圓頂天際線）；build/screenshots/building_compare_1..6.png 與 build/screenshots/title_compare/cmp_01..10.png 目測通過，lint 0 錯誤，0 切頂。
