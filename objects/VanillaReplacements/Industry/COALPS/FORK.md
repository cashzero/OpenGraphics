# OG_COALPS（fork 自製）
- 對應 vanilla：COALPS（Industry）
- 內部名稱：OGCOALPS
- 遊戲內名稱：Coal Power Plant
- 設計概念：燃煤電廠：雙曲線冷卻塔（頂端 32 格循環蒸汽）、紅磚鍋爐廠房與雙煙囪、兩種變電設備；地面為碎石與煤堆。
- 製作方式：Blender 5.2 程序化建模（`model.py`），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_COALPS.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py COALPS`。以 vanilla COALPS 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無（已用 `tools/pack.py --relink` 改指向 OG 物件）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
- 2026-11-19 V2：`tools/newgame_check.sh` 通過（standalone 新遊戲物件選擇驗證、模擬一年不崩潰、存檔物件 placeholder 只剩音效等 24 個）；地圖截圖 build/screenshots/newgame/industry_*.png 已檢視：建築、動畫部件、地面圖塊與公司色正常
- 2026-11-25 V1/V2：鍋爐廠房改為暗色凹入屋頂＋採光氣樓＋公司色細簷口，變電站改為鋼製散熱片變壓器與匯流排門架；build/preview/b2_coalps_fix.p1.png、build/screenshots/polish3/shot5_coalps.png 檢視通過
- 2026-11-25 V1/V2（建物地表材質升級）：`tools/blender/kit.py` 新增多尺度程序化地表著色器（泥土／碎石／草地／人行道磚縫／混凝土伸縮縫／停機坪／礦土／煤場／雪地＋3D Bump），重算地面部件並同步更新 `.blend`，V1 與 V2 Title 1:1（`cmp_01.png`、`cmp_05.png`、`cmp_07.png`）檢視通過。
