# OG_AIRPORT2（fork 自製）
- 對應 vanilla：AIRPORT2（Airport）
- 內部名稱：OGAIRPO2
- 遊戲內名稱：Grass Airfield
- 設計概念：1920–30 年代草地機場：碎石跑道（跑道頭白色條紋、中段白色圓形標記）、外露木樑與工具棚／油桶的木造機庫、拱形浪板鋼肋機庫、白牆石基座會館式航站（門廊柱、煙囪、懸挑木陽台觀景塔台）；跑道兩端的風向袋有 16 格轉動動畫。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/port_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；預覽圖依建築位置拼合），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_AIRPORT2.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py AIRPORT2`。以 vanilla AIRPORT2 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude／Gemini（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/airport-OGAIRPO2.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1／V2：重塑木造機庫、拱形浪板機庫與 1930 年代會館式航站＋木陽台塔台；`tools/lint.py` 0 錯誤；已檢視 `build/preview/check_air2_new.p1.png` 與物件預覽 `build/screenshots/polish/obj_OGAIRPO2.png`（**未驗證**：尚未在地圖上放置檢視）
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
