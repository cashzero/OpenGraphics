# OG_AIRPORT1（fork 自製）
- 對應 vanilla：AIRPORT1（Airport）
- 內部名稱：OGAIRPO1
- 遊戲內名稱：Intercontinental Airport
- 設計概念：大型國際機場：寬柏油跑道（鋼琴鍵閾值、接地區、編號）、藍色邊燈的滑行道、混凝土停機坪與機位標線；具結構立柱、天窗採光頂、拱形玻璃中庭與玻璃空橋的現代航廈、帶肋塔身與外傾多邊形觀景室／雷達罩的高塔台、拱形圓筒屋頂與鋼構拱肋／四片滑動大門的機庫（背面附工作間）、露天頂樓停放車輛與角落玻璃電梯塔的立體停車大樓；兩座雷達有 64 格旋轉動畫。
- 製作方式：Blender 5.2 程序化建模（`tools/gen/port_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；預覽圖依建築位置拼合），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_AIRPORT1.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py AIRPORT1`。以 vanilla AIRPORT1 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude／Gemini（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-22 V2：`tools/newgame_check.sh`（standalone，`OG_REGUK`／`OG_REGALP`）開新遊戲 → 模擬一年不崩潰、存檔物件全部來自 repo；物件選擇預覽 `build/screenshots/m3/preview/airport-OGAIRPO1.png` 已檢視。**未驗證**：尚未看過放在地圖上的樣子（需要含此物件的測試存檔）
- 2026-11-25 V1／V2：重塑航廈（立面結構柱、天窗、拱形玻璃中庭、空橋）、塔台（肋條塔身、外傾窗框、陽台欄杆、球形雷達罩）、機庫（圓筒拱頂、鋼拱肋、四片滑門、背面工作間）與立體停車大樓（露天頂樓車位與車輛、電梯塔、中空公司色飾條）。V1 檢視 `build/preview/check_air1_new.p1..2.png`、`check_air1_p27.png`（發現並修正停車大樓頂樓飾條實心覆蓋柏油面的問題）；V2 檢視標題場景地圖截圖 `build/screenshots/polish/shot4_air1_r0.png`、`shot4_air1_r2.png` 與物件預覽 `obj_OGAIRPO1.png`，多角度堆疊、比例與公司色皆正常
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
- 2026-11-26 V1/V2（滑行道與跑道銜接修正）：`port_recipes.py` 於跑道 `part 13`、`part 24` 補上無縫柏油 T 字銜接段、喇叭口倒角、黃色導引線與雙道等待線，同步更新 `.blend` 並於 `cmp_07.png`、`og_own_title_grid.png`（OG 04）驗證通過。
