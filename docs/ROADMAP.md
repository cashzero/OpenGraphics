# ROADMAP — 讓 OpenLoco 不依賴 vanilla 素材運行

> 本檔由 agent 與維護者共同維護。完成項目時，在同一個 commit 裡勾選並附上日期。
> 製作與驗證的實際操作步驟見 [`PIPELINE.md`](PIPELINE.md)；agent 工作規範見 [`../AGENTS.md`](../AGENTS.md)。

## 最終目標與完成定義

**目標**：在沒有安裝 Locomotion 的電腦上，OpenLoco（本專案 fork 版）能正常啟動、建立新遊戲並遊玩，所有圖形、物件、音訊都來自 OpenGraphics。

完成定義（全部達成才算完成）：
1. 沒有 Locomotion 的隔離環境中，OpenLoco 能啟動並進入主選單。
2. 只啟用 OG／EX 物件，就能通過 OpenLoco 的物件選擇驗證，並生成地圖、鋪軌、運行車輛、讓城鎮成長、讓產業運作。
3. CD 版的 545 個 vanilla 物件都有 OG 對應，而且任何 OG 物件都不引用 vanilla 物件。
4. `g1.DAT`（基礎圖形）、音效、環境音、音樂都有替代品，或在缺少時能正常靜音運行。
5. （延伸）標題畫面、情境、教學都有 OG 版本。

**開發原則**：未完成的部分一律先用 **placeholder**（自動產生、外觀一眼可辨識、但尺寸／數量／偏移正確）填補，讓遊戲隨時都能端到端跑起來；之後再逐一換成正式素材。每一項成果都必須通過 `PIPELINE.md` 的 V1（素材驗證）與 V2（遊戲內驗證），而且 V2 要由 agent 自己 build 並執行 OpenLoco、親自檢視截圖。

---

## 現況快照（2026-11-19）

### 物件覆蓋（對照 OpenLoco `_vanillaObjects`，共 549 個）

| 狀態 | 數量 |
|---|---|
| 已有 OG 版本（上游完成） | 178 |
| placeholder 資料夾（待製作） | 367 |
| 不在範圍內 | 4（`AIRPORT4`、`HPORT2`、`SHINKT0`、`SHINKF0`，見下方說明） |

尚未完成的類型（已完成 / placeholder）：

| 類型 | 完成 | 待做 | 類型 | 完成 | 待做 |
|---|---|---|---|---|---|
| vehicle | 106 | 59 (+2 缺資料夾) | scenarioText | 0 | 45 |
| building | 3 | 73 | sound | 3 | 39 |
| tree | 0 | 39 | competitor | 0 | 38 |
| industry | 0 | 22 | currency | 0 | 13 |
| trackSignal | 0 | 10 | climate | 0 | 6 |
| steam | 0 | 5 | airport | 0 | 4 (+2 缺資料夾) |
| levelCrossing | 0 | 4 | trainStation | 2 | 3 |
| region | 1 | 2 | trackExtra | 1 | 2 |
| track | 1 | 1 | road | 5 | 1 |
| dock | 0 | 1 | | | |

**不在範圍內的 4 個物件**：OpenLoco 的 `_vanillaObjects` 清單有 549 個，其中 `SHINKT0`／`SHINKF0`（新幹線 0 系，Chris Sawyer 官方免費下載的情境 `Shinkansen.SC5`）與 `AIRPORT4`／`HPORT2`（International Airport／Large Heliport，可查到的來源是玩家製作的 Enhanced Airport Pack）不在基本遊戲 CD 上。CD 上的物件與情境都沒有引用它們。OpenLoco 只在兩個地方用到這份清單：存檔時判斷要不要把物件嵌入存檔（`S5.cpp`），以及物件選擇視窗的 vanilla 標記（`ObjectSelectionWindow.cpp`）。啟動和開新遊戲都不需要它們，因此不列入目標（2026-11-19 確認）。

已全部完成：bridge、cargo、cliffEdge、hillShapes、interfaceSkin、land、roadExtra、roadStation、scaffolding、snow、streetLight、townNames、tunnel、wall、water。

### 物件選擇驗證的必選類型（OpenLoco `ObjectIndex.cpp` 的 `kValidateTypeAndErrorMessage`）

| 必選類型 | OG 狀態 |
|---|---|
| region、scaffolding、interfaceSkin、vehicle、land、water、townNames、streetLight、snow、hillShapes、road（雙向通用道路） | ✅ 已有 |
| building | ⚠️ 只有 3 個（噴泉、公園、電塔），通過驗證但城鎮無法正常成長 |
| **currency、climate、levelCrossing、industry** | ❌ 沒有 → **M2 的硬性阻擋項** |

### 相依引用稽核（`python3 tools/deps.py`）

解碼全部 243 個 OG／EX DAT，搜尋內嵌的物件 header：
- 共引用了 **222 個不同的 vanilla 物件**。只有 70 個 DAT 有引用 OG／EX 物件（多為音效與車站）。
- 熱點（括號為引用它的 DAT 數）：`TRACKST`(136)、`SNDTR1`(89)、`SPARK1`(48)、`TRACKNG`(35)、`TREXCAT1`(30)、`SNDE1`(25)、`EXH1`(24)、`ROADTRAM`(22)、`STEAM`(18)、`SNDS1`(17)、`SNDW7`/`SNDW8`(16)、`ROADONE`/`ROADTMC`/`ROADUS1`/`ROADUS2`(13)。
- 其中很多已經有 OG 版本（例如 `OGTRACKS`、`OGROADON`），只是上游物件仍指向 vanilla 名稱。
- `OG_REGUS` 引用大量 vanilla 建築、產業、樹木與車輛。

→ 光是補齊物件還不夠，**必須處理引用**（見決策 D1）。

### 已知的上游問題

- `OGE_LRC1`／`OGE_LRC2`（`EXLRC1`／`EXLRC2`）：bogie sprite 數量不足，OpenLoco 載入時報錯，但仍會繼續載入。依「上游優先」政策不修改。
- `OG_SNOW`（`OGSNOW`）：在遊戲中雪地呈現大量黑色雜點，vanilla `SNOW` 沒有（2026-11-19，以同一份固定存檔對照截圖發現）。兩者 sprite 數量與旗標相同，原因待查（可能與雪地的 noise mask 混合有關）。

### 物件以外的 vanilla 依賴（OpenLoco 端）

| 檔案 | 內容 | 啟動是否必要 | OpenLoco 程式位置（`../OpenLoco/src/OpenLoco/src/`） |
|---|---|---|---|
| `Data/g1.DAT` | 基礎圖形 0x101A = 4122 張（UI、字型、圖示等；`ImageIds.h` 約 2720 個常數） | **是**：安裝路徑驗證就是檢查它是否存在 | `Environment.cpp` `validateLocoInstallPath`、`Graphics/Gfx.cpp` `loadG1` |
| `ObjData/` | vanilla 物件 | 目前是 | `Objects/ObjectIndex.cpp` |
| `Data/CSS1.DAT` | 音效 bank | 啟動時載入 | `Audio/Audio.cpp` |
| `Data/CSS2–4.DAT` | 環境音 | 否 | `Audio/AmbientAudio.cpp` |
| `Data/CSS5.DAT` | 標題音樂 | 否 | `Title.cpp`、`Jukebox.cpp` |
| `Data/*.DAT`（29 首） | 背景音樂 | 否 | `Jukebox.cpp` |
| `Data/title.dat` | 標題畫面背景存檔 | 標題畫面需要 | `Title.cpp` |
| `Scenarios/*.SC5` | 內建情境 | 否 | `Scenario/ScenarioManager.cpp` |
| `Scenarios/Boulder Breakers.SC5`、`Data/TUT*.DAT` | 教學 | 否 | `Tutorial.cpp` |
| 硬編碼預設物件 `REGUS` | 新遊戲預設 region | 是 | `Objects/ObjectIndex.cpp`（`kDefaultObjects`） |

語言字串由 OpenLoco 的 `data/language/*.yml` 提供，不依賴 vanilla。

OpenLoco 現有命令列只有 `simulate <save> <ticks> <out>`（無頭模擬）與 `compare`，**沒有無頭截圖**；遊戲內有 giant screenshot（`Ui/Screenshot.cpp`）可供改寫。

### 開發環境現況

| 項目 | 狀態 |
|---|---|
| Blender 5.2.3 | ✅ `~/.local/bin/blender` |
| cmake 4.4.3、ninja、g++ 15.2、OpenLoco 相依的系統套件（libsdl3-dev 等） | ✅ |
| OpenLoco build（`posix` preset + 系統套件） | ✅ 2026-11-19，約 3.5 分鐘；執行檔 `../OpenLoco/build/posix/Release/OpenLoco` |
| OpenLoco `simulate` 冒煙測試（隔離環境、無視窗） | ✅ 2026-11-19，vanilla 情境 500 ticks |
| OpenLoco 靜態發佈版（`linux-vcpkg-static`） | ⏸ 暫緩，發佈時再處理（見 `PIPELINE.md` V2） |
| `.NET`（ObjectEditor） | ❌ 未安裝 |
| Pillow | ❌ 未安裝（應裝在 `.venv`） |
| Locomotion 正版資料 | ✅ 2026-11-19 從使用者的 ISO 解到 `$HOME/Locomotion/game`（`LOCO_DATA_DIR`） |
| WSLg 顯示（`DISPLAY=:0`） | ✅ 可供人工互動測試 |

---

## 前置需求（需要使用者處理）

- [x] 安裝 vcpkg 需要的 `zip`、`unzip`（2026-11-19，以 `apt-get download` + `dpkg-deb -x` 裝到 `~/.local`，不需 sudo；見 `PIPELINE.md` V2）
- [x] 安裝 vcpkg 的 `alsa` 套件需要的 autotools（2026-11-19，使用者以 sudo 安裝）
- [x] 改走 `posix` preset，以系統套件安裝 OpenLoco 相依函式庫（2026-11-19；vcpkg 靜態 build 暫緩）
- [x] 提供 Locomotion 正版資料（2026-11-19，使用者提供 ISO，解到 `$HOME/Locomotion/game`，設為 `LOCO_DATA_DIR`）。**只用於開發期量測**（g1 圖片尺寸、物件結構模板、sprite 數量），任何 vanilla 內容都不會 commit，最終成品也不需要它。
- [ ] 在 GitHub 建立 OpenLoco 的 fork（決策 D2），並告知 repo 名稱

---

## 決策紀錄

| # | 議題 | 狀態 | 內容 |
|---|---|---|---|
| D1 | vanilla 引用怎麼處理 | **已決定 A**（2026-11-19）；已實作於 fork `og/vanilla-alias`，並合併進 `og-main`。實測：OG 物件引用 vanilla 時，拿掉 vanilla 就會 crash；加上別名層後，原版情境在沒有 `ObjData` 的環境下能正常載入 | **A**：在 OpenLoco fork 加入「vanilla → OG 別名層」：找不到 vanilla 物件時，依對照表改載入 OG 物件。對照表由本 repo 自動產生。優點：不需要改上游 DAT（不與 sync 衝突），同時解決情境檔、title.dat、舊存檔引用 vanilla 的問題。**B**：寫工具改寫 DAT 內的引用，每次 sync 後重跑。缺點：修改上游物件、sync 時衝突、情境檔仍然引用 vanilla。 |
| D2 | OpenLoco 引擎修改 | **已決定**（2026-11-19） | fork：https://github.com/cashzero/OpenLoco 。`../OpenLoco` 的 remote：`origin` = fork、`upstream` = 官方。分支：`master` 追上游，功能開在 `og/*`，整合在 `og-main`（目前含 `og/headless-screenshot`、`og/vanilla-alias`）。 |
| D3 | 非物件素材（g1、音訊、標題、情境）放在哪 | **已決定**（2026-11-19，採用建議；已建立 `base/README.md`） | 建議本 repo 新增頂層 `base/`（`base/g1/`、`base/sfx/`、`base/music/`、`base/title/`、`base/scenarios/`），與 `objects/` 一起由 CI 打包。上游沒有這些資料夾，sync 衝突風險低。 |
| D4 | placeholder 怎麼產生 | **已依建議實作，待確認**（2026-11-19：`tools/make_placeholders.py`） | 建議先以本機 vanilla 資料作為「結構與尺寸模板」產生（不 commit 產物，只 commit 產生工具）；長期改為直接依 OpenLoco 原始碼的結構定義產生，讓 CI 也能產生。 |
| D5 | 發行方式 | 待決定 | 建議：本 repo 推 tag 發布 `objects.zip`（之後加上 `base.zip`），OpenLoco fork 的 `CMakeLists.txt` 改指向本 fork 的 release URL 與 SHA256。 |

---

## 里程碑

### M0 — 驗證管線與工具（所有後續工作的前提）✅ 2026-11-19 完成

目標：agent 可以不靠人，從來源檔一路做到「在 OpenLoco 裡看到截圖」。

環境
- [x] build 上游 OpenLoco（`posix` preset），指令與耗時已寫入 `PIPELINE.md`（2026-11-19）
- [x] 隔離環境 + 無視窗執行 `simulate` 冒煙測試（2026-11-19）
- [x] `.venv` + Pillow（2026-11-19，以 `uv` 安裝現成 wheel）
- [x] `.gitignore` 加入 `build/`、`*.blend1`、`.venv/`（2026-11-19）

OpenLoco fork（D2）
- [x] 在 GitHub 建立 fork（2026-11-19，https://github.com/cashzero/OpenLoco ）；`og/headless-screenshot`、`og/vanilla-alias` 已推上 fork 並合併進 `og-main`
- [x] 單一物件預覽：`screenshot --object <名稱>` 輸出物件選擇視窗用的預覽圖 PNG（2026-11-19，`og/object-preview`）
- [x] 命令列 `screenshot`：載入存檔，依指定視角／縮放／旋轉輸出 PNG（可選 giant 全圖）（2026-11-19，本機分支；以 vanilla 情境實測）
- [x] 不建立視窗、不需要顯示器即可執行：`SDL_VIDEO_DRIVER=offscreen SDL_AUDIO_DRIVER=dummy ALSOFT_DRIVERS=null` 即可，不需要改 drawing engine（2026-11-19）
- [x] 隔離環境：Linux 用 `XDG_CONFIG_HOME`；fork 加上 `OPENLOCO_USER_DIR` 環境變數（2026-11-19；Linux 已測，Windows／macOS 未測）
- [x] ~~CMake 選項：物件來源可指向本機資料夾~~ → 不需要：OpenLoco 原本就支援 `OPENLOCO_DATA_DIR` 環境變數（2026-11-19）
- [x] `simulate` 載入失敗時回傳非 0（上游會回傳 0）（2026-11-19，本機分支）
- [x] 截圖寫入完整 256 色調色盤（上游只寫 246 色，遇到 placeholder 會 PNG ERROR）（2026-11-19，本機分支）
- [x] 物件載入錯誤的 log 帶出物件名稱（2026-11-19，本機分支；查出是上游 `EXLRC1`／`EXLRC2`）

本 repo 工具（`tools/`）
- [x] `dat.py`：DAT 讀寫（chunk 編碼 0/1/2/3、checksum、header、字串表、G1 image table）（2026-11-19；788 個 DAT checksum 全過、99,115 張 sprite 解碼無誤）
- [x] `lint.py`：AGENTS.md §2 規則 + checksum + 相依引用報告（2026-11-19；上游 243 個 DAT 0 錯誤）
- [x] `inventory.py`：物件狀態總表（2026-11-19）
- [x] `deps.py`：相依引用稽核 + vanilla → OG 對照表產生（2026-11-19）
- [x] `preview.py`：從**最終 DAT** 解出 sprite，產生 contact sheet（含 remap 上色、高度線、對照物）（2026-11-19，以 `OG_4F` 對照 vanilla `4F` 驗證）
- [x] `make_placeholders.py`：為所有缺少的物件產生 placeholder DAT（D4 建議做法；2026-11-19，367 個，所有 vanilla 引用都改指向 OG）
- [x] `install_test_env.py`：組出 OpenLoco 測試環境（正式物件優先，缺的用 placeholder；以 `OPENLOCO_DATA_DIR` 取代內建物件）（2026-11-19）
- [x] `s5.py`：情境／存檔的必要物件 relink（vanilla → OG）（2026-11-19）
- [x] `run_openloco.sh`、`v2_smoke.sh`：一個指令跑完 V2 冒煙測試（2026-11-19）
- [x] Blender 5.x 渲染（`tools/blender/render_sprites.py`）：直接使用上游近期 `.blend` 內的 rig（Loco Graphics Helper 新版，逐格動畫 = sprite 順序）；WSL2 headless EEVEE 可用；原點偏移以 `OG_4F` 校正；依材質名稱產生公司色遮罩（2026-11-19）
- [x] 調色盤量化與 remap 遮罩處理（`tools/quantize.py`，2026-11-19）
- [x] DAT 打包路線定案：**`tools/pack.py`**（自行打包，不需要 ObjectEditor）；`OG_4F` 解出再打包後，遊戲內預覽逐像素相同（2026-11-19）

端到端驗收
- [x] 拿一個上游物件走完 V1 + V2，截圖可由 agent 檢視（2026-11-19：`OG_4F.blend` 全部 616 格 渲染 → 量化 → 打包 → lint → contact sheet → OpenLoco 物件預覽，與上游原檔幾乎相同）
  - 2026-11-19：V1 已完成（`OG_4F` contact sheet 含 remap 與 vanilla 對照）；V2 的 `screenshot` 已能拍 vanilla 情境，還缺含指定物件的測試存檔
- [x] 拿 placeholder 走完 V1 + V2：`OG_CTRUCK1` contact sheet；vanilla 情境 Boulder Breakers 改用 OG + placeholder 後模擬 500 ticks 並截圖成功（2026-11-19）

### M1 — 可啟動（standalone boot）

- [ ] 從本機 vanilla `g1.DAT` 匯出**純 metadata**（每張圖的寬、高、偏移、flags，不含像素）存成 `docs/g1-catalog.json`，並依 `ImageIds.h` 分類用途
- [ ] g1 placeholder 產生器：4122 張圖，尺寸／偏移正確，內容為可辨識的佔位圖
- [ ] OpenLoco fork：沒有 Locomotion 時改用 OpenGraphics 的 g1；缺少 CSS、音樂、title、教學檔時安靜略過
- [x] OpenLoco fork：別名層（D1-A）（2026-11-19）。讀取 `<objects 目錄>/aliases.yml`，由 `deps.py --aliases-yml`（只含 repo 物件）或 `make_placeholders.py`（含 placeholder）產生；`OPENLOCO_PREFER_OPENGRAPHICS=1` 可在有 vanilla 時強制使用 OG
- [ ] CI：發行包含 `aliases.yml`（與 `objects.zip` 一起）
- [ ] OpenLoco fork：預設 region 改為 `OGREGUS`
- [ ] 驗收：隔離環境、無 Locomotion，headless 截圖到主選單

### M2 — 可玩的 sandbox（只用 OG 物件 + placeholder）

硬性阻擋項（先做正式版）
- [ ] currency ×1 以上（建議先做 `CURRDOLL`，`OG_REGUS` 有引用）
- [ ] climate ×1 以上（建議先做 `CLIM3`，`OG_REGUS` 有引用）
- [ ] levelCrossing ×1 以上（`LCROSS2`、`LCROSS4` 被引用）
- [ ] industry：至少一條完整產業鏈（例如煤礦 → 發電廠，或農場 → 食品廠）

可玩性
- [ ] 城鎮建築：住宅與商業各數種
- [ ] steam：`EXH1`、`EXH2`、`SPARK1`、`STEAM`（大量車輛引用）
- [ ] trackSignal ×1 以上、tree：每種 climate 數種
- [ ] 高引用音效物件：`SNDTR1`、`SNDE1`、`SNDS1`、`SNDW7`、`SNDW8`

驗收
- [ ] 只啟用 OG 物件（缺的用 placeholder）建立新遊戲，通過物件選擇驗證
- [ ] `simulate` 跑一個遊戲年不崩潰；截圖中核心物件不是 placeholder

### M3 — 物件全面覆蓋

依類別分批，每批一個分支：
- [ ] Vehicle：Truck 24、Aircraft 19、Ship 10、Bus 3、Train 3
- [ ] Building 剩餘、Industry 剩餘
- [ ] Tree 剩餘、TrainSignal 剩餘、Track／TrackExtra／Road 剩餘
- [ ] Airport 4、Dock 1、TrainStation 3
- [ ] Competitor 38、Currency 剩餘、Climate 剩餘、Region 2
- [ ] 驗收：`deps.py` 報告中沒有任何 vanilla 引用（或全部由別名層涵蓋）

### M4 — 正式 g1 基礎圖形

- [ ] 依 `docs/g1-catalog.json` 的分類，逐類以正式美術取代 placeholder（介面框線與按鈕、工具圖示、字型、游標、地圖元素等）
- [ ] 字型需要特別規劃（多語系字元範圍、像素字型）

### M5 — 音訊

- [ ] 研究 CSS 格式（`Audio.cpp` 的 `loadSoundsFromCSS`）
- [ ] 音效 bank（CSS1）、Sound 物件 39 個、環境音（CSS2–4）
- [ ] 音樂 29 首 + 標題音樂（CSS5）

### M6 — 內容

- [ ] 標題畫面存檔（只用 OG 物件）
- [ ] OG 版情境 + ScenarioText 45 個
- [ ] 教學：重製或在 fork 中停用

---

## 建議執行順序

```
M0 ──┬─> M1（引擎 + g1 placeholder）──┐
     └─> M2（必選物件）───────────────┴─> M3 ─> M4 ─> M5 ─> M6
```

M1 與 M2 可以平行：M1 以 OpenLoco fork 的程式碼為主，M2 以本 repo 的素材為主。
