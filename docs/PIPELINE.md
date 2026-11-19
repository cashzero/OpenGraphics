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

**建模迭代預覽**（🛠 M0 待建：`tools/blender/turntable.py`）
```bash
blender -b objects/…/OG_X.blend --python tools/blender/turntable.py -- --out build/render/OG_X/turntable
```
以較高解析度輸出 8 個角度，給 agent 判斷造型、比例與細節，**在正式渲染 sprite 之前**先修好模型。

**sprite 渲染**（🛠 M0 待建：`tools/blender/render_sprites.py`）
```bash
blender -b objects/…/OG_X.blend --python tools/blender/render_sprites.py -- --type vehicle --out build/render/OG_X
```
渲染 rig 規格：
- 正交相機、Locomotion 的等角視角、旋轉數依物件類型與 vanilla 模板決定。
- 參考上游近期的 `.blend`（例如 `objects/GreatBritainExpansion/Vehicle/Train/OG_MK4/OG_MK4.blend`：EEVEE、`Camera Medium Curve`、`Light Primary`／`Light Back`／`Light Left`／`Light Upper Highlights`）逆向出相機角度、燈光與解析度。官方 add-on 只支援 Blender 2.79，不使用。
- 輸出 RGBA（透明背景）＋ remap 遮罩 pass（標記 primary／secondary 公司色區域）。
- WSL2 下 EEVEE 背景渲染可能需要 GPU／GL；不可行時改用 Cycles（CPU），並在本節記錄結論。

## P2 量化

🛠 M0 待建：`tools/quantize.py`（需要 `.venv` 裡的 Pillow）
```bash
.venv/bin/python tools/quantize.py build/render/OG_X -o build/sprites/OG_X
```
- 調色盤：`palettes/locopal.act`（256×RGB）。index 0 = 透明。（`tools/dat.py` 的 `write_indexed_png` 可直接寫出索引色 PNG。）
- 遮罩內的像素依亮度對應到 remap index：primary `0x07–0x09`、`0xF6–0xFE`；secondary `0xCA–0xD5`。遮罩外的像素**不得**落在 remap index 上。
- 輸出 `0.png…N.png` 與 `sprites.json`（格式見 `objects/Common/Land/OG_VOID/sprites.json`）。

## P3 打包

DAT 打包路線在 M0 定案，二選一：
- **A**：OpenLoco ObjectEditor（.NET，5.12.0 起有基本 CLI，本機尚未安裝 .NET）。
- **B**：🛠 `tools/dat.py build`：以模板物件（結構、屬性、字串）＋ `build/sprites/<NAME>/` 產生 DAT，自動填入內部名稱、source = 3 與 checksum。

產物先放 `build/dat/<NAME>/`，通過 V1 後才複製到 `objects/…/<NAME>/`。

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
- `OpenLoco/`：使用者目錄（`XDG_CONFIG_HOME=build/openloco-env`），每次重建時刪除物件索引快取 `plugin.dat`。
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
- 語法：`screenshot <存檔或情境> [ticks] -o <png> [--size WxH] [--zoom 0-3] [--rotation 0-3] [--centre x,y] [--giant]`
- `--centre` 是**格子座標**；未指定時用存檔記錄的主視角，再不行用地圖中心。`--rotation` 依序檢查四個方向。
- 輸出為 8-bit 索引色 PNG，可直接用看圖工具檢視。
- 實作：`Ui::saveScreenshotToFile`（`src/OpenLoco/src/Ui/Screenshot.cpp`，改寫自 giant screenshot 與 `Scenario/ScenarioPreview.cpp`）、`OpenLoco::screenshotGame`（`OpenLoco.cpp`）、命令列解析（`CommandLine.cpp`、`App/src/Main.cpp`）。

🛠 待建：`headless-preview`，輸出單一物件在物件選擇視窗裡的預覽圖。在那之前，要看物件在遊戲中的樣子，需先做一個含有該物件的測試存檔（M2 的 `tests/saves/`），再用 `screenshot` 拍。

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
- 音訊 placeholder：靜音，或由 fork 在缺檔時略過。

---

## 文件維護規則

- 工具或 fork 功能實作完成時，把對應的「🛠 M0 待建」改成實際用法，並標上「✅ 已實測」與日期。
- 指令執行失敗時，把錯誤訊息重點與解法記在對應小節，下一個 agent 才不會重蹈覆轍。
