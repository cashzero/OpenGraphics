# PIPELINE — 素材製作與驗證管線

> 標示說明：**✅ 已實測**＝指令已在本機跑過；**🛠 M0 待建**＝工具或功能尚未實作，介面是預定規格，實作後要把本檔改成實際用法。
> 里程碑與進度見 [`ROADMAP.md`](ROADMAP.md)；agent 工作規範見 [`../AGENTS.md`](../AGENTS.md)。

## 原則

1. **驗證要獨立於製作**。V1 一律從**最終 DAT** 解出 sprite 來檢查，不拿來源 PNG 充數；V2 一律在真正 build 出來的 OpenLoco 裡載入。
2. **agent 必須親自看圖**。用能讀圖片的工具（Claude Code 的 Read、Codex 的圖片檢視）打開產生的 PNG，把觀察結果寫進該物件 `FORK.md` 的「驗證紀錄」。沒看過圖不可以標記通過。
3. **全程 headless**。每一步都要能在沒有顯示器、沒有人操作的情況下執行。WSLg（`DISPLAY=:0`）只給人工互動測試用。
4. **缺什麼就用 placeholder 補**，讓遊戲隨時都能端到端跑起來（見 §6）。
5. **產物一律放 `build/`**（gitignored），不放進 `objects/`；只有最終 DAT 與來源檔會 commit。

## 管線總覽

```
來源檔（.blend / bpy 腳本 / 像素圖）
  │ P1 渲染（Blender headless）
  ▼
build/render/<NAME>/        RGBA PNG + remap 遮罩
  │ P2 量化（Loco 調色盤 + remap）
  ▼
build/sprites/<NAME>/       0.png…N.png + sprites.json
  │ P3 打包
  ▼
OG_<NAME>.dat ──────────────┬─ V1 素材驗證：lint + 解碼 DAT → contact sheet → agent 看圖
                            └─ V2 遊戲驗證：測試環境（正式物件 + placeholder）
                                 → OpenLoco simulate（冒煙測試）
                                 → OpenLoco headless 預覽／截圖 → agent 看圖
```

## `build/` 目錄配置

```
build/
  render/<NAME>/             P1 輸出（含 turntable 預覽）
  sprites/<NAME>/            P2 輸出
  dat/<NAME>/                P3 輸出（驗證通過後才複製到 objects/…）
  preview/<NAME>.png         V1 contact sheet
  placeholders/objects/      placeholder 物件 DAT
  placeholders/g1.dat        placeholder 基礎圖形（M1）
  openloco-env/OpenLoco/     V2 隔離環境（XDG_CONFIG_HOME 指向 build/openloco-env）
  screenshots/<NAME>/        V2 截圖
```

---

## P1 渲染（Blender）

Blender 5.2.3 位於 `~/.local/bin/blender`，以 `blender -b <file> --python <script> -- <args>` 執行 headless 作業。

**sprite 渲染**（✅ 2026-11-19：`tools/blender/render_sprites.py`）
```bash
blender -b objects/…/OG_X.blend --python tools/blender/render_sprites.py -- \
  --out build/render/OG_X [--frames 0-7 | --frames 0,40,100] [--samples 16] [--no-mask]
```
- **使用 `.blend` 內現成的 rig**：上游近期的 `.blend` 是用 Loco Graphics Helper 的新版（物件帶有 `loco_graphics_helper_*` 屬性）製作，每個 sprite 角度烘焙成一格動畫，**影格順序 = image table 順序**（例：`OG_4F.blend` 影格 0–615 = 616 張 sprite）。相機為正交 `Camera Medium Curve`（`ortho_scale` 19、俯仰 60.718°／方位 45°），4 盞 SUN 燈（`Light Primary`／`Back`／`Left`／`Upper Highlights`），EEVEE、AgX、透明背景，影格 84×84。
- **WSL2 可 headless 用 EEVEE**（Mesa 軟體 GL，`libEGL warning` 可忽略）：第一格約 28 秒（含 shader 編譯），之後每格約 1.1 秒；遮罩 pass 另計。`OG_4F` 全部 616 格 + 遮罩實測 16.6 分鐘（遮罩 1 取樣時；改成 16 取樣後會再久一些）。
- **找不到的貼圖**（例如路徑寫成 `//C1Noisemap.png` 或 `D:\…`）自動改指向 repo 的 `textures/`；已打包進 `.blend` 的貼圖不動。
- **原點**：世界原點經相機投影的位置，加上 `--origin-offset`（預設 `0 2`）。這個值是以 `OG_4F.blend` 校正的：7 類 sprite 與上游 DAT 比對，dx 恆為 0、dy 恆為 2。
- **公司色遮罩**（預設開啟）：依材質名稱判斷（上游慣例）：`Company Color 1`／`Recolorable 1` = primary，`Company Color 2`／`Recolorable 2` = secondary。正常影格渲染完後，材質換成純色發光、色彩管理改 Standard，再渲染一輪輸出 `NNNN_mask.png`。**沒有遮罩時，光影會讓公司色區域被量化成一般顏色，公司色就失效**（實測）。遮罩 pass 也要反鋸齒（`--mask-samples`，預設 16）：只用 1 取樣時，公司色邊緣會留下一般紫色細線（`OG_4F` #200–207 實測 48 個像素 → 16 取樣後 0 個，與上游原檔相同）。
- 輸出：`NNNN.png`（RGBA）、`NNNN_mask.png`、`render.json`（每格原點）。
- 驗證紀錄（2026-11-19，M0 端到端驗收）：`OG_4F.blend` 全部 616 格經 P1→P2→P3 打包成 `OGR4F`，lint 0 錯誤；616 張 sprite 的尺寸與偏移和上游 DAT 相差都不超過 1 像素；contact sheet 的公司色變體正確；在 OpenLoco 中的物件預覽與上游原檔幾乎相同（`build/screenshots/preview/e2e_compare.png`）。

**新建模型**：沒有現成 rig 的新 `.blend`，先從上游近期的 `.blend` 複製相機、燈光與渲染設定（或直接以上游檔案為起點修改），再依物件類型設定逐格動畫。各物件類型的影格／sprite 排列規則待 M3 依類型整理。

🛠 之後再做：`tools/blender/turntable.py`（較高解析度輸出 8 個角度，給 agent 在正式渲染前檢查造型）。

### 靜態物件與程序化物件（✅ 2026-11-19，M2）

**建築與產業（Blender 靜態 rig）**：`tools/gen/build_blender_objects.py`
```bash
LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_blender_objects.py [--reuse-render] [BLDHOUS2 COALMINE …]
```
- 每個物件的設定（模板、內部名稱、顯示名稱、模型）寫在腳本的 `OBJECTS`。模型可以是物件資料夾裡的 `model.json`（交給 `tools/blender/models/building.py` 參數化建模：ground／walls／storey／gable／flatroof 部件），也可以是 `model.py`（自由 bpy 腳本，例如 `Industry/COALMINE/model.py`）。共用的尺寸常數與建模函式在 `tools/blender/kit.py`（`TILE` = 10.236 單位、`PX_PER_Z`、材質、box／cylinder／lathe／gable_roof／ground_plate…）。
- `tools/blender/static_rig.py` 建立乾淨場景、上游同款相機與燈光，**每個部件都在 z=0 渲染**（OpenLoco 依模板的部件高度往上疊），4 個旋轉（畫面上順時針），影格順序 = `part*4 + rot`；公司色遮罩 pass 同 P1。
- 部件高度、部件數、變化組合由 `tools/objinfo.py` 從模板讀出，產業另外加上 21 張地面圖塊（`tools/gen/industry_ground.py`，坡形取 `OG_GRASS1` 的 19 種坡形）。
- 量化用 `--no-remap-colours`：靜態 rig 有遮罩，不需要色鍵（色鍵會把一般顏色的雜訊吸成公司色）。
- `--reuse-render`：模型沒改時只重新量化與打包（渲染 2×2 建築約 3 分鐘、電廠約 7 分鐘）。
- 每次建置都會用 `static_rig.py --save-blend` 把模型存成物件資料夾裡的 `OG_<NAME>.blend`（所有部件沿 X 軸並排、不渲染、壓縮、不產生 `.blend1`），滿足 AGENTS.md §2.3「3D 物件必須 commit `.blend`」。材質全是程序化節點，沒有外部貼圖路徑。

**程序化物件**：`tools/gen/build_simple_objects.py`
```bash
LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_simple_objects.py [CURRDOLL OAK …]
```
- 產生器在 `tools/gen/`：`currency.py`（貨幣圖示，text remap 色）、`steam.py`（蒸汽／排氣／火花）、`lcross_signs.py`（平交道警示牌）、`signal.py`（臂板號誌，8 視角 × 動畫格）、`tree.py`（闊葉、針葉、棕櫚、仙人掌；四季、積雪、枯萎與陰影）、`sound.py`（22050 Hz 16-bit mono 合成音）、`region_image.py`（region 預覽圖，由 repo 內 OG 物件的 sprite 拼成）。
- 產生的 PNG／`sprites.json`／WAV 放在物件資料夾（commit），再以 `pack.py --relink` 打包；`FORK.md` 只在不存在時寫入。

### M3 新增的產生器（2026-11-20）

所有 3D 物件都改用「幾何指令」：配方模組產生 JSON 指令（box／cyl／gable／hip／lathe／seg／loft／tube…），由 `tools/blender/models/ops.py` 在 Blender 端畫出（材質表 `MATS`，`company`／`company2` = 公司色）。

| 類別 | 建置指令 | 配方／產生器 | rig |
|---|---|---|---|
| 建築 | `build_blender_objects.py BLDxxx` | `building_table.py`（名稱、概念、配方）→ `building_recipes.py`（依部件高度與變化組合分析角色：地面／底層／標準層／特色層／屋頂） | `static_rig.py` |
| 產業 | `build_blender_objects.py COALMINE …` | `industry_recipes.py`（每個產業一個函式，含動畫部件）、`industry_fields.py`（田地／地面 21 張 × 階段 × 角度） | `static_rig.py` |
| 碼頭、機場 | `build_blender_objects.py SHIPST1 AIRPORT1 …` | `port_recipes.py`（依建築位置與移動節點推得跑道方向與建築正面）；預覽圖依建築位置把整座機場拼起來縮小 | `static_rig.py` |
| 車輛 | `build_vehicles.py CTRUCK1 …` | `vehicle_table.py`（名稱、概念、配方）→ `vehicle_recipes.py`（卡車、公車、船、飛機、蒸汽機車…）；影像清單依模板的 body／bogie 結構（旋轉數、坡度、動畫、貨物、煞車燈）產生 | `vehicle_rig.py` |
| 火車站 | `build_stations.py TRSTAT1 …` | 檔內設計；半透明玻璃遮罩由 `iso.py` 投影 | `vehicle_rig.py`（`unit = tile`，原點 = 圖塊角落） |
| 軌道、第三軌／齒軌、電車軌 | `build_simple_objects.py TRACKNG …` | `track_iso.py`：依 `data/track_geometry.json`（`extract_track_geometry.py` 從 OpenLoco 原始碼抽出的片段圖塊、中心線、影像編號）逐格繪製道碴／枕木／鋼軌 | 無（像素繪製） |
| 號誌、平交道 | `build_simple_objects.py SIGxxx LCROSSx` | `signal_iso.py`、`lcross_iso.py`（共用 `iso.py` 的等角像素畫布） | 無 |
| 競爭者頭像、貨幣、樹、音效 | `build_simple_objects.py COMPx …` | `portrait.py`、`currency.py`（字形）、`tree.py --preset`、`sound.py`（螺旋槳、噴射、蒸汽、柴油、喇叭…） | 無 |

- `vehicle_rig.py` 以**動畫模式**渲染：每張影像一個影格，各狀態（車身、貨物、動畫格）的根物件以關鍵影格切換位置與方向，比逐張呼叫 `render()` 快約 3.6 倍。
- **記憶體**：Blender（EEVEE + Mesa d3d12）每渲染一格約多佔 20 MB 且不會釋放，所以 `build_vehicles.py` 每 24 格、`build_blender_objects.py` 每 6 個部件換一個新的 Blender 行程（每個行程峰值約 1.3 GB）。**一次只跑一個 Blender**（批次要依序排隊，不要平行；16 GB 的機器同時開多個會耗盡記憶體）。
- 雙 GPU：Mesa d3d12 無法指定第二張卡（兩張同名，只有名稱比對的環境變數），而且瓶頸是每格的 CPU 開銷，不是 GPU。
- 檢查工具：`tools/stack_preview.py`（建築／產業依變化組合堆疊的預覽，含公司色）。

### g1 基礎圖形（M4，2026-11-22）

```bash
.venv/bin/python tools/gen/g1_fonts.py      # 4 套點陣字型（medium 一般／粗體、small、large）
.venv/bin/python tools/gen/g1_title.py      # 主選單：程序星球（旋轉、建造動畫）、星光／磁片／學士帽
.venv/bin/python tools/gen/g1_logo.py       # 標題 logo（Blender：tools/blender/logo_rig.py，一次一個 Blender）
.venv/bin/python tools/gen/g1_overlays.py   # 施工選取框、集貨範圍、格線、橋影（× 19 坡形）
.venv/bin/python tools/gen/g1_markers.py    # 高度標記、路線編號圓圈
.venv/bin/python tools/gen/g1_arrows.py     # 施工箭頭、單行道箭頭、地圖外空格
.venv/bin/python tools/gen/g1_effects.py    # 煙、爆炸、火球、水花、撞車碎片
.venv/bin/python tools/gen/g1_ui.py         # 視窗元件、分頁與工具圖示、進度條、新聞紙背景
.venv/bin/python tools/g1.py build -o build/placeholders/base/Data/g1.DAT   # 組出 g1.DAT（預設讀 base/g1）
```
- 每個產生器輸出 `base/g1/<類別>/`（PNG + `sprites.json`），並在 `build/preview/` 產生預覽圖。
- 換色規則（字形的三個色號、按鈕／分頁／視窗框以視窗色換色、選取框的標記色號 + `paletteMapUnk21–2B`）寫在各產生器開頭與 `tools/g1.py`。
- **UI 截圖**（OpenLoco fork `og/window-capture`）：`--open-window` 在截圖前 30 個畫面開啟指定視窗：
  ```bash
  STANDALONE=1 tools/run_openloco.sh "$PWD/build/tests/newgame/after.SV5" --exit-after-frames 200 \
    --open-window objects,options -o "$PWD/build/screenshots/m4/ui.png"
  ```
  可用名稱：options、audio、objects、company、finances、companies、towns、industries、stations、trains、terraform、trees、
  map、music、messages、about、shortcuts、landscape、construction、roadconstruction（見 OpenLoco.cpp `openWindowsByName`）。

## P2 量化

✅ 2026-11-19：`tools/quantize.py`（需要 `.venv` 裡的 Pillow）
```bash
.venv/bin/python tools/quantize.py build/render/OG_X -o build/sprites/OG_X [--no-remap-colours]
```
- 調色盤：`palettes/locopal.act`。OpenLoco 可繪製的顏色是 index 10–245（`Graphics/Gfx.cpp` 的 `updatePalette(…, 10, 236)`）；0 = 透明。
- 一般像素：最接近的顏色（redmean 加權距離），候選為 10–245，排除 secondary remap `0xCA–0xD5` 與未使用的 `0xF5`；預設另加入 remap 色（色鍵）。
- 遮罩區域（通道值 >= `--mask-threshold`，預設 48，讓反鋸齒邊緣也算進去）：依亮度對應到 remap 色階（兩組色階在調色盤中都是由暗到亮）：primary `0x07–0x09`、`0xF6–0xFE`；secondary `0xCA–0xD5`。
- 每格裁切到不透明範圍，並把原點換算成 G1 的 `xOffset`／`yOffset`。輸出 `0.png…N.png`（索引色）與 `sprites.json`。

## P3 打包

✅ 2026-11-19 定案：**路線 B**，`tools/pack.py`（不需要 ObjectEditor）。
```bash
.venv/bin/python tools/pack.py --template <模板.dat> --sprites build/sprites/OG_X \
  --name OGXXXXXX [--display "遊戲內名稱"] [--allow-count-change] -o build/dat/OG_X/OG_X.dat
```
- 模板提供結構、屬性與其他字串（vanilla、上游 OG 或自己的物件都可以）；sprite 以 RLE 重新編碼（G1 flags 5），保留 zoom／duplicate 旗標。
- 預設 sprite 數量必須與模板相同；寫出後自動重新讀取，驗證 checksum 與每張 sprite 的像素。
- 驗證紀錄：把 `OG_4F` 全部 616 張 sprite 解出再打包，OpenLoco 中的物件預覽與原檔**逐像素相同**。
- 產物先放 `build/dat/<NAME>/`，通過 V1 後才複製到 `objects/…/<NAME>/`。
- 其他選項（2026-11-19，M2）：
  - `--set u8@3=60`：修改固定結構中的數值（可重複；型別 u8/i8/u16/i16/u32/i32）。
  - `--wav <檔案>`：音效物件換成新的 PCM。
  - `--relink`：模板中引用的 vanilla 物件改指向 repo 裡**已有**的 OG 物件（AGENTS.md §2.2.1）；沒有 OG 版的保留原名，由別名層處理，並列在輸出中。
  - `--og-only-will-load`（region 專用，需搭配 `--relink`）：willLoad 清單只保留 OG 物件。region 被選取時，willLoad 裡的物件會一併被選取，留著 vanilla 名稱就會連帶選進 placeholder。

---

## V1 素材驗證

### 自動檢查

✅ 2026-11-19 實作：`tools/lint.py`（只用標準函式庫）
```bash
python3 tools/lint.py objects/…/OG_X.dat     # 單檔（repo 層級的重複檢查仍會執行）
python3 tools/lint.py --quiet-vanilla        # 整個 repo（約 30 秒）
```
- **錯誤**（exit 1）：checksum 不符、type 與資料夾不符、source 不是 openLoco、內部名稱不符 `OG*`／`EX*`、`(type, 名稱)` 重複、同 Category 檔名重複、sprite 無法解碼、該有 image table 卻沒有。
- **警告**：引用 vanilla 物件、有內容卻殘留 `.gitkeep`、`*.blend1`、`FORK.md` 缺欄位。`--strict` 會把警告也當成失敗。
- 2026-11-19 對上游全部 243 個 DAT 執行：0 個錯誤；1 個警告（上游 `C56` 殘留 `.gitkeep`）；188 個 DAT 引用 vanilla。

其他工具：
- `python3 tools/dat.py info|verify|extract`：檔頭資訊、checksum 與編碼往返驗證、匯出 sprite PNG + `sprites.json`。✅ 已對 repo 243 個與 vanilla 545 個 DAT 驗證 checksum 全部通過，並解碼全部 99,115 張 sprite 沒有錯誤。
- `python3 tools/deps.py [--per-file] [--alias-json build/alias.json]`：相依引用稽核，以及產生 vanilla → OG 對照表（ROADMAP D1-A 用）。
- `python3 tools/inventory.py [--list placeholder]`：盤點。

### 目視檢查（agent 必做）

✅ 2026-11-19 實作：`tools/preview.py`（需要 `.venv` 的 Pillow）
```bash
.venv/bin/python tools/preview.py objects/…/OG_X.dat -o build/preview/OG_X.png \
  --remap --height-lines 18 22 --compare "$LOCO_DATA_DIR/ObjData/X.DAT" [--range 0:48]
```
contact sheet 內容：
- 從**最終 DAT** 解出 sprite，最近鄰放大（`--scale`，預設 2×），每格標上 `#index 寬x高 f<G1 flags>`。
- 棋盤格背景看透明區域；紅色十字是繪製原點（檢查偏移）；`--height-lines` 在原點上方畫高度參考線（藍線，單位像素）。
- `--remap`：再畫 3 組公司色變體（primary／secondary = 紅／黃、藍／橘、綠／紅）。remap 區域沒有變色就表示公司色沒做好。
- `--compare`：以相同比例畫出對照物件（上游 OG 或 vanilla）。
- sprite 多時用 `--range` 只畫一部分，或讓工具自動分頁（`<out>.p1.png`…）。
- index 0 預設視為透明，因為 OpenLoco 以公司色 remap 繪製（車輛等）時，不論 flag 都把 index 0 當透明（`Graphics/DrawSprite.cpp`）。要依 flag 判斷時加 `--strict-flags`。

看圖檢查清單：
- [ ] sprite 數量與順序正確，旋轉方向連續、沒有跳格（數量依物件屬性而定，不一定等於 vanilla）
- [ ] 沒有裁切、雜點、殘留背景
- [ ] 偏移一致：連續角度之間物件不會跳動（紅色十字相對位置一致）
- [ ] 公司色區域明顯且合理
- [ ] 尺寸與對照物協調，符合高度表
- [ ] 與 vanilla 版本有明顯差異；沒有真實品牌標誌或文字

---

## V2 遊戲內驗證

### Build OpenLoco

依「優先使用現成套件」原則（`AGENTS.md` §3），本機開發用 `posix` preset 搭配系統套件。✅ 2026-11-19 實測成功，耗時約 3 分 25 秒（12 執行緒）。

一次安裝全部相依套件（需要 sudo）：
```bash
sudo apt-get install -y build-essential ninja-build pkg-config git \
  libsdl3-dev libpng-dev libopenal-dev libyaml-cpp-dev libtbb-dev libgtest-dev
```
- **不要**安裝 `libfmt-dev`：Ubuntu 的 fmt 是 10.1，OpenLoco 指定 11.1.4；系統沒有 fmt 時，CMake 會自己用 `FetchContent` 抓正確版本。
- 需要 CMake 4.x（本機在 `~/.local/bin/cmake`）。

```bash
cd ../OpenLoco
cmake --preset posix
cmake --build --preset posix-release
```
- 執行檔：`../OpenLoco/build/posix/Release/OpenLoco`
- CMake 會用 `FetchContent` 下載上游 OpenGraphics `v0.1.12` 的 `objects.zip`，放到 `../OpenLoco/build/posix/Release/data/objects/`（198 個 DAT）。
- OpenLoco fork（D2）：`../OpenLoco` 切到 `og-main`（`git switch og-main && git pull`）後執行同樣的指令。V2 流程需要 fork 的功能（`screenshot` 命令、別名層）。

**靜態連結發佈版**（之後要發佈時才用；需要從原始碼編譯所有相依套件，`linux-vcpkg-static` preset）：2026-11-19 嘗試過三次都沒有完成。依序遇到缺 `zip`／`unzip`、缺 autotools（vcpkg 的 `alsa`）、缺 `libxtst-dev`（vcpkg 的 `sdl3`），之後改走上面的 `posix` 路線。若要再試，先補齊下列套件，並在重試前 `rm -rf build/linux-vcpkg-static`：
```bash
sudo apt-get install -y zip unzip autoconf autoconf-archive automake libtool libxtst-dev libxft-dev
```

### 執行 OpenLoco 的注意事項

- **一律加上 `--locomotion_path <dir>` 並使用隔離環境**。OpenLoco 在處理任何命令列動作（包含 `--version`、`simulate`）之前，會先解析 Locomotion 路徑；找不到就會跳出資料夾選擇視窗並卡住。
- 無視窗、無聲音執行：`SDL_VIDEO_DRIVER=offscreen SDL_AUDIO_DRIVER=dummy ALSOFT_DRIVERS=null`（✅ `simulate` 已實測不會開視窗）。
- 每次執行都要包在 `timeout` 裡，避免卡住的程序留在背景。

### vanilla 資料（開發期量測用）

`LOCO_DATA_DIR=$HOME/Locomotion/game`（✅ 2026-11-19 從使用者提供的 `$HOME/Atari-ChrisSawyersLocomotion.iso` 解出）。這個目錄在所有 git repo 之外，**絕不 commit**。

重建步驟（需要 `sudo apt-get install -y unshield`；`uv` 用來執行現成的 PyPI 套件 `pycdlib`）：
1. 解開 ISO：`bsdtar` 讀不到這個 ISO 的目錄（列出 0 個檔案），改用 `pycdlib` 透過 Joliet 解到 `~/Locomotion/iso/`。
2. 解開 InstallShield 安裝包：`unshield -g "Default File Group" -d ~/Locomotion/cab x ~/Locomotion/iso/data1.cab`
3. 組成安裝目錄（hard link，不額外占空間）：
   ```bash
   L=~/Locomotion; mkdir -p $L/game/Data
   cp -al $L/iso/Data/. $L/game/Data/
   cp -al $L/cab/Default_File_Group/Data/. $L/game/Data/
   cp -al $L/cab/Default_File_Group/ObjData $L/cab/Default_File_Group/Scenarios $L/game/
   ```
4. 刪掉中間產物：`rm -r $L/iso $L/cab`（`game/` 是 hard link，不受影響；2026-11-19 已清理，`~/Locomotion` 只剩 `game/`，約 513 MB）
內容：`Data/`（58 個檔：g1、CSS1–5、29 首音樂、title、教學）、`ObjData/`（545 個 vanilla 物件）、`Scenarios/`（含 `Landscapes/`）。OpenLoco 的 vanilla 清單有 549 個；`AIRPORT4`、`HPORT2`、`SHINKT0`、`SHINKF0` 不在這張 CD 上，也不在本專案範圍內（見 `ROADMAP.md`）。

### 組測試環境

✅ 2026-11-19 實作：`tools/install_test_env.py`
```bash
LOCO_DATA_DIR=$HOME/Locomotion/game python3 tools/make_placeholders.py   # 產生 placeholder 與 alias.json
python3 tools/install_test_env.py --with-placeholders --relink
```
產生的隔離環境（`build/openloco-env/`）：
- `data/objects/`：本 repo 的 243 個物件 + 367 個 placeholder。OpenLoco 用環境變數 `OPENLOCO_DATA_DIR` 指向 `build/openloco-env/data`，**取代** build 內建的上游 v0.1.12 物件，不會產生重複（不需要改 OpenLoco）。
- `data/language`：symlink 到 OpenLoco build 的語言檔。
- `OpenLoco/`：使用者目錄（`XDG_CONFIG_HOME=build/openloco-env`），每次重建時刪除物件索引快取 `plugin.dat`。fork 另支援 `OPENLOCO_USER_DIR` 直接指定使用者目錄（Linux 已測；Windows／macOS 用同樣的程式碼但未測）。
- `--relink`：**只在測試副本中**依 `build/placeholders/alias.json` 把 vanilla 引用改指向 OG 名稱（2026-11-19：861 處），repo 內的檔案不變。脫離 vanilla 物件測試時必須加；理由見下方「已知問題」。

`tools/run_openloco.sh <OpenLoco 參數…>` 會自動設好上述環境變數與無視窗設定，並在環境目錄裡執行（避免 `OpenLoco.lock` 落在 repo）。存檔路徑請用**絕對路徑**，否則 OpenLoco 會當成相對於 `Scenarios` 資料夾。

### 只用 OG 物件的測試存檔

✅ 2026-11-19 實作：`tools/s5.py`
```bash
python3 tools/s5.py info "$LOCO_DATA_DIR/Scenarios/Boulder Breakers.SC5" -v       # 列出必要物件
python3 tools/s5.py relink "$LOCO_DATA_DIR/Scenarios/Boulder Breakers.SC5" \
  -o build/tests/og_boulder.SC5 --alias build/placeholders/alias.json            # vanilla → OG
```
存檔的地圖資料以 slot index 引用物件，所以只換必要物件清單裡的 header，就能讓 vanilla 情境改用 OG 物件與 placeholder。`--types`／`--exclude-types`／`--names` 可只換部分物件，用來二分搜尋問題物件。

### 端到端冒煙測試（一個指令）

✅ 2026-11-19：`tools/v2_smoke.sh ["<情境>.SC5"]`（約 8 秒；需要 OpenLoco fork 的 `og-main`）
依序：產生 placeholder（若還沒有）→ 組測試環境（含 `aliases.yml`）→ 建立**沒有 `ObjData`** 的 Locomotion 目錄 `build/loco-noobjdata/`（只 symlink `Data`、`Scenarios`）→ 以**原版情境**執行 `simulate` 500 ticks（檢查有跑滿、有載入別名表）→ `screenshot` → `build/screenshots/v2_smoke/<情境>.png`。失敗時以非 0 結束。**PASS 之後仍要親自看截圖。**

這等於在「完全沒有 vanilla 物件」的條件下驗證：所有物件都經由別名層換成 OG 或 placeholder。

### 別名層（fork `og-main`）

- OpenLoco 讀取 `<objects 目錄>/aliases.yml`（每列 `[ObjectType 數值, vanilla 名稱, OG 名稱]`）。找不到 vanilla 物件時，改用對應的 OG 物件；物件之間的引用（例如車輛引用軌道）也一樣。
- 產生：`python3 tools/deps.py --aliases-yml <path>`（只含 repo 已有的 OG 物件）；`tools/make_placeholders.py` 會另外產生含 placeholder 的版本；`install_test_env.py` 會自動放進測試環境。
- `OPENLOCO_PREFER_OPENGRAPHICS=1`：即使裝了 vanilla 物件也優先使用 OG（預設行為不變，仍優先 vanilla）。
- 因為有別名層，`install_test_env.py --relink` 與 `s5.py relink` 已不是必要步驟，只在測試上游版 OpenLoco 時使用。

### Standalone（不使用 Locomotion）測試

✅ 2026-11-19（fork `og-main`）：
```bash
.venv/bin/python tools/g1.py build -o build/placeholders/base/Data/g1.DAT    # placeholder g1（只需 docs/g1-catalog.json）
python3 tools/install_test_env.py --with-placeholders --with-base             # 放進 build/openloco-env/data/base
STANDALONE=1 tools/run_openloco.sh --exit-after-frames 300 -o "$PWD/build/screenshots/m1/standalone.png"
```
- `--exit-after-frames N -o <png>`：照正常流程執行遊戲（標題畫面、主選單），畫完 N 個畫面後把**整個螢幕（含 UI）**存成 PNG 並結束。這是檢查主選單、視窗等 UI 的方法。
- `STANDALONE=1`：`run_openloco.sh` 不傳 `--locomotion_path`，改設 `OPENLOCO_STANDALONE=1`，OpenLoco 使用 `$OPENLOCO_DATA_DIR/base`。不設定時，找不到 Locomotion 也會自動改用 base（已實測，且不會把 base 路徑寫進設定檔）。
- 沒有 `title.dat` 時，標題地圖由引擎依已安裝的物件生成（預設物件 + 每種必選類型各一 + 全部地形／樹／建築／圍牆／道路，積雪最少的氣候、平緩丘陵、夏天）。
- 只要驗證「發行內容」時，`install_test_env.py` 不加 `--with-placeholders`。

### 開新遊戲驗收（ROADMAP M2）

✅ 2026-11-19（fork `og/new-game`）：一個指令跑完 M2 驗收，約 20 秒。
```bash
tools/newgame_check.sh                         # 預設：OG_REGUK + M2 核心物件
SELECT=OGREGUK,OGCOALMI MAX_PLACEHOLDERS=30 tools/newgame_check.sh
```
1. 重建 placeholder g1、組測試環境（`--with-placeholders --with-base`），之後全部以 standalone 模式執行（沒有任何 Locomotion 檔案）。
2. `new-game 0 -o new.SV5 --select <名稱,…>`：照正常開新遊戲的流程（`EditorController` 預設地形 → `Scenario::start`），亂數種子固定，同樣的物件會產生同一張地圖。指定物件時**不預先選取預設物件**（否則 OpenLoco 會先選 `OGREGUS`，region 只能選一個），先選指定的物件，其餘必選類型自動各補一個；log 必須有 `Object selection valid`，不能有 `could not be selected`。
3. `simulate` 35,100 ticks（一個遊戲年，1 日 ≈ 96 ticks）。
4. `python3 tools/s5.py info after.SV5 --origin --max-placeholders N`：依類型統計存檔用到的物件來自 repo 還是 placeholder；有來源不明的物件，或 placeholder 超過 N 個就失敗。
5. 截圖 `industry:OGCOALMI industry:OGCOALPS town:0 town:3`（`SHOTS` 可改），輸出到 `build/screenshots/newgame/`，**agent 必須親自看圖**：核心物件不可以是橘色格紋的 placeholder。

地圖上看不到的物件（號誌、平交道：新遊戲沒有鐵路；蒸汽：沒有車輛運行）用物件預覽（`screenshot --object`）補看，並在 `FORK.md` 註明哪些部分還沒驗證。

### 截圖對照的注意事項

- **部分情境開局時才隨機生成地形**（沒有「地形已生成」旗標，例如 Aerophobia），同一個情境每次載入的地形都不同，不能拿來對照。Boulder Breakers 的地形是預先做好的，可以直接對照。
- 固定地圖的方法：`tools/run_openloco.sh simulate <情境> 1 -o build/tests/<名稱>.SV5` 先輸出存檔，之後 vanilla 與 OG 兩種模式都載入這份存檔，並用相同的 `--centre`／`--zoom` 截圖對照。
- 對照圖可用 Pillow 左右拼接（例子見 2026-11-19 的 `build/screenshots/v2_smoke/aerofix_compare.png`：用這個方法發現了 `OGSNOW` 的雜點問題）。

### 冒煙測試（OpenLoco 現有功能）

✅ 2026-11-19 實測（vanilla 情境、500 ticks、約 0.9 秒、exit 0）：
```bash
# 在 OpenGraphics repo 根目錄執行
export LOCO_DATA_DIR=$HOME/Locomotion/game
export OPENLOCO_BIN=$HOME/OpenLoco/build/posix/Release/OpenLoco
export XDG_CONFIG_HOME="$PWD/build/openloco-env" SDL_VIDEO_DRIVER=offscreen SDL_AUDIO_DRIVER=dummy ALSOFT_DRIVERS=null
mkdir -p build/openloco-env
(cd build/openloco-env && timeout 180 "$OPENLOCO_BIN" --locomotion_path "$LOCO_DATA_DIR" \
  simulate "$LOCO_DATA_DIR/Scenarios/Boulder Breakers.SC5" 500 -o smoke.sv5)
```
- **必須 `cd` 進 `build/openloco-env` 再執行**：Linux 版會在當前工作目錄建立單一執行個體鎖檔 `OpenLoco.lock`（`Platform.Posix.cpp`），在 repo 根目錄執行會留下垃圾檔。
- 語法：`simulate <存檔或情境> <ticks> [比對用存檔] -o <輸出存檔>`。第三個位置參數是**比對用**的存檔，不是輸出。
- 上游的 `simulate` 在載入失敗時 exit code 仍是 0；fork 已修正為回傳 1（`og/headless-screenshot` 分支）。用上游版本時務必檢查 `scenario ticks` 是否等於指定值。
- 通過條件：exit code 為 0、輸出 `scenario ticks` 等於指定的 ticks，而且 log（`$XDG_CONFIG_HOME/OpenLoco/logs/`）中沒有 `Mismatch between installed object header`、`Data could not be read` 這類物件載入錯誤。
- 已知（上游問題）：載入物件索引時出現 `Object EXLRC1/EXLRC2 has too few images for bogie sprites!`，是上游 `NorthAmericanExpansion` 的 `OGE_LRC1`／`OGE_LRC2`。依「上游優先」政策不修改。（錯誤訊息帶出物件名稱是 fork 的改善，見 `og/headless-screenshot` 分支。）
- `$XDG_CONFIG_HOME/OpenLoco/plugin.dat` 是物件索引快取；要強制重建索引時刪掉它即可。
- **OG 物件引用 vanilla 物件時，拿掉 vanilla 就會 crash**（2026-11-19 實測，segmentation fault）：只換 `TRACKST` → `OGTRACKS` 時，仍引用 `TRACKST` 的車輛會讓遊戲崩潰；反之亦然。上游有 136 個 OG 車輛引用 vanilla `TRACKST`。已由 fork 的別名層解決（D1-A，`og-main`）；上游版 OpenLoco 則需用 `--relink`。
- 上游截圖程式只寫 246 色調色盤，畫面含有未套 remap 的 index（例如 placeholder）時 libpng 會報 `PNG ERROR`；fork 已改為寫入完整 256 色。
- 測試存檔（只使用 OG 物件與 placeholder）在 M2 建立後放在 `tests/saves/`。

### Headless 截圖（OpenLoco fork 新功能）

✅ 2026-11-19 實作於 fork 分支 `og/headless-screenshot`，已合併進 `og-main`（https://github.com/cashzero/OpenLoco ）。新增命令列動作 `screenshot`：載入存檔或情境、可先模擬 N ticks，再把指定視角畫到記憶體並存成 PNG，不開視窗。
```bash
# 環境變數同冒煙測試；在 build/openloco-env 裡執行
(cd build/openloco-env && timeout 180 "$OPENLOCO_BIN" --locomotion_path "$LOCO_DATA_DIR" \
  screenshot "$LOCO_DATA_DIR/Scenarios/Boulder Breakers.SC5" 200 -o ../screenshots/smoke/view.png --size 1024x640)
(cd build/openloco-env && timeout 180 "$OPENLOCO_BIN" --locomotion_path "$LOCO_DATA_DIR" \
  screenshot "$LOCO_DATA_DIR/Scenarios/Boulder Breakers.SC5" 0 -o ../screenshots/smoke/giant.png --giant --zoom 3)
```
- 語法：`screenshot <存檔或情境> [ticks] -o <png> [--size WxH] [--zoom 0-3] [--rotation 0-3] [--centre x,y|town:N|industry:名稱] [--giant]`
- `--centre` 可以是**格子座標**、`town:N`（第 N 個城鎮）或 `industry:<內部名稱>`（第一個使用該物件的產業，例如 `industry:OGCOALMI`，2026-11-19）；未指定時用存檔記錄的主視角，再不行用地圖中心。`--rotation` 依序檢查四個方向。
- 輸出為 8-bit 索引色 PNG，可直接用看圖工具檢視。
- 實作：`Ui::saveScreenshotToFile`（`src/OpenLoco/src/Ui/Screenshot.cpp`，改寫自 giant screenshot 與 `Scenario/ScenarioPreview.cpp`）、`OpenLoco::screenshotGame`（`OpenLoco.cpp`）、命令列解析（`CommandLine.cpp`、`App/src/Main.cpp`）。

**單一物件預覽**（✅ 2026-11-19，fork `og/object-preview`，已合併進 `og-main`）：`screenshot` 加上 `--object <內部名稱>`，改為輸出該物件在物件選擇視窗裡的預覽圖（114×114，與遊戲內相同的繪製程式碼）。物件必須已安裝在測試環境裡（`install_test_env.py`；手動放進 `build/openloco-env/data/objects/` 時要刪掉 `plugin.dat` 讓索引重建）。
```bash
LOCO_DATA_DIR="$PWD/build/loco-noobjdata" tools/run_openloco.sh screenshot "$HOME/Locomotion/game/Scenarios/Boulder Breakers.SC5" 0 \
  -o "$PWD/build/screenshots/preview/OG4F.png" --object OG4F
```
要看物件**放在地圖上**的樣子，仍需要含有該物件的測試存檔（M2 的 `tests/saves/`）。

在 fork 功能涵蓋不到的情況，可人工透過 WSLg 執行遊戲，截圖會存到 `$XDG_CONFIG_HOME/OpenLoco/screenshots/`，agent 再讀取這些 PNG。

看圖檢查清單：
- [ ] 物件出現在物件選擇視窗，名稱與預覽圖正確
- [ ] 放到地圖上的位置正確（在軌道／道路／格子上，沒有浮空或陷入地面）
- [ ] 四個旋轉方向都正確，轉向時沒有偏移跳動
- [ ] 公司色有套用
- [ ] 與周圍物件比例協調
- [ ] 沒有調色盤錯色
- [ ] log 沒有錯誤

---

## §6 Placeholder

用途：在正式素材完成前，讓遊戲能端到端運行，同時讓整條管線有東西可以測。

🛠 M0 待建：`tools/make_placeholders.py`
```bash
python3 tools/make_placeholders.py --out build/placeholders [--loco-data "$LOCO_DATA_DIR"]
```
規格：
- 只產生在 `build/placeholders/`，**絕不 commit 進 `objects/`**（`objects/` 的 placeholder 資料夾保持只有 `.gitkeep`）。
- 內部名稱與日後的正式 OG 物件**相同**，換成正式版時對遊戲與存檔都是透明的。
- 外觀一眼可辨識：洋紅／棋盤格底色，加上類型縮寫與 index。但 sprite 數量、尺寸、偏移都與模板一致，排版錯誤才看得出來。
- 遊戲內名稱加上前綴 `[PH] `，在遊戲裡就看得出是 placeholder。
- 屬性數值取自模板（D4）。相依引用一律指向 OG 名稱。
- g1 placeholder（M1）：依 `docs/g1-catalog.json` 的尺寸與偏移產生 4122 張圖，夠大的圖上畫出 index。
- g1 中**不是美術、而是資料**的圖，依調色盤或幾何計算（M2，2026-11-19，`tools/g1.py`）。這些圖做錯時，整張地圖都會壞掉：
  - `paletteMap*`（公司色、半透明對照表）與 `text_palette`：沒有它們時，所有公司色與陰影都變成深灰色剪影。
  - 地形遮罩 `surfaceSmooth*`（相鄰地塊貼圖的過渡帶）、`cliffEdge*Mask*`（懸崖面各段）、`snowMaskCoverage*`（部分積雪）。OpenLoco 以「g1 圖 AND 貼圖」繪製（`drawMaskedZoom`），所以必須是 0xFF／0 的未壓縮 bitmap；做成實心方塊時，相鄰地塊的岩石貼圖會整塊蓋上去。邊的編號（rotation 0）：0 左下、1 右下、2 左上、3 右上；坡形取 `OG_GRASS1`。驗證方式：同一個存檔分別用 vanilla g1 與 placeholder g1 截圖對照，除了雜點之外地形應該一致。
- 音訊 placeholder：靜音，或由 fork 在缺檔時略過。

---

## 文件維護規則

- 工具或 fork 功能實作完成時，把對應的「🛠 M0 待建」改成實際用法，並標上「✅ 已實測」與日期。
- 指令執行失敗時，把錯誤訊息重點與解法記在對應小節，下一個 agent 才不會重蹈覆轍。
