# OG_BLDHOUS4（fork 自製）
- 對應 vanilla：BLDHOUS4（Building）
- 內部名稱：OGBLDHO4
- 遊戲內名稱：Garden Cottage
- 設計概念：小花園裡的平房：一種是白色粉刷牆配山形屋頂與煙囪，另一種是紅磚牆配轉向的屋頂。屋頂為公司色（城鎮隨機上色）。
- 製作方式：Blender 5.2 程序化建模（`tools/blender/models/building.py` + `model.json`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_BLDHOUS4.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py BLDHOUS4`。以 vanilla BLDHOUS4 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）；城鎮截圖 build/screenshots/newgame/town_*.png 與物件預覽 build/screenshots/m2/preview/ 已檢視
