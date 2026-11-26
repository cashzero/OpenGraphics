# OG_OILREFIN（fork 自製）
- 對應 vanilla：OILREFIN（Industry）
- 內部名稱：OGOILREF
- 遊戲內名稱：Refinery
- 設計概念：製程單元、白色大型儲油槽、蒸餾塔、球形儲槽、裂解單元、高煙囪，以及三角桁架火炬塔（64 格火焰動畫）。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/industry_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；田地圖塊 `tools/gen/industry_fields.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_OILREFIN.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py OILREFIN`。以 vanilla OILREFIN 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/industry-OGOILREF.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1/V2：地坪改為風化碎石、金屬浮頂儲油槽＋圍堰、銀灰球槽與拱形管橋；build/preview/b2_oilrefin.p1.png、build/screenshots/polish3/obj_OGOILREF.png 檢視通過
- 2026-11-25 V1/V2：核心催化裂解塔群（part 13）重製為四塔高密管橋＋64 格橘紅大火炬，原油儲槽改為風化鋼／鏽鋼加強環與盤梯；build/preview/check_oilrefin_v3.p1.png、build/screenshots/title_compare/cmp_09.png 檢視通過
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
- 2026-11-26 V1/V2（建物材質與光照升級）：`tools/blender/kit.py` 與 `static_rig.py` 修復垂直牆面 3D 磚紋映射、新增磚／切石／疊瓦／木板／茅草／灰泥／混凝土接縫＋3D Bump＋`AmbientOcclusion` 屋簷與窗框陰影，並以暖陽主光消除冷灰塑膠感；同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_02.png`、`cmp_04.png`、`cmp_05.png`）檢視通過。
- 2026-11-26 V1/V2（2D 流體紊流火炬火焰重製）：以 `tools/gen/fire_fx.py` 取代原本 3D 錐體建模，改產 64 格無縫循環 2D 白熱核心＋橘紅躍動火舌＋上升黑煙精靈（對齊原版 2D billboard 做法）；V1（`check_oilrefin_fire_v2.png`）與 V2 Title 1:1（`cmp_09.png`）檢視通過。
- 2026-11-26 V1/V2（重工業金屬材質與建築幾何全面升級）：`tools/blender/kit.py` 與 `ops.py` 修正高金屬度在黑背景 EEVEE 反射死黑問題並新增鉚接鋼板焊縫＋縱向鐵鏽流痕＋冷中性工業混凝土地坪；`industry_recipes.py` / `COALPS/model.py` 升級重型儲槽、螺旋階梯、管橋、反應塔與球槽細節；同步更新 `.blend` 與全部 22 座工業建物原版 vs OG 對照圖（`build/screenshots/industry_compare_1..4.png`）與 Title 1:1 截圖（`cmp_01/06/09/10.png`）檢視通過。
