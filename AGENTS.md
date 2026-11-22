# AGENTS.md — OpenGraphics（cashzero fork）

給 AI agent（Claude、GPT/Codex 等）與維護者的工作手冊。開始任何工作前先讀完本檔。
`README.md` 是上游的貢獻規範；**本檔與 README 衝突時，以本檔為準**。

---

## 0. Fork 政策（最重要）

| 項目 | 規定 |
|---|---|
| 最終目標 | **讓 OpenLoco 完全不需要 vanilla Locomotion 素材就能正常運行**。範圍包含物件、`g1.DAT` 基礎圖形、音訊、標題畫面與情境，以及必要的 OpenLoco 引擎修改。完整計畫見 [`docs/ROADMAP.md`](docs/ROADMAP.md)。 |
| 定位 | `cashzero/OpenGraphics`，fork 自 `OpenLoco/OpenGraphics`。**不向上游提 PR**。 |
| 上游同步 | 上游的變更會定期 merge 進來（見 §6）。 |
| 上游優先 | 上游一旦完成某個物件，**整個物件資料夾以上游版本覆蓋 fork 版本**，不保留、不合併。 |
| AI 素材 | **允許** AI 生成／輔助（模型、bpy 腳本、貼圖、像素圖、名稱、數值、音效）。上游 README 的禁令在本 fork 不適用。 |
| 仍然有效的規定 | README「Requirements」其餘全部照舊：不可複製真實產品／品牌／塗裝／名稱、不可 1:1 複製 vanilla、尺寸與調色盤與 vanilla 一致、命名規則、來源檔必須進 repo。 |

### AI 素材的額外紅線
- 不可把 vanilla Locomotion 的 sprite／圖檔當作 img2img、style reference、LoRA 訓練等輸入。vanilla 只能拿來**量尺寸、比輪廓、數 sprite 數量**。
- 不可在 prompt 中要求重現特定真實車型、品牌、商標或塗裝（可以用「混合多個時代特徵」的描述）。
- 每個 fork 自製物件都必須在 `FORK.md` 記錄來源（見 §2.3）。

---

## 1. Repo 結構

```
objects/<Pack>/<ObjectType>/[<VehicleSubtype>/]<ObjectFolder>/
palettes/     Locomotion 調色盤（locopal.act = 256×RGB，權威來源）
textures/     共用貼圖（C1Noisemap.png、CorrugatedMetal.png）
.github/workflows/  CI：打包 objects.zip、tag 時發 release
```

- **Pack**：`VanillaReplacements`（vanilla 替代品，待上游重整）、`Common`（跨區域共用）、`NorthAmericanExpansion`、`GreatBritainExpansion`（區域擴充包）。
- **ObjectType** 資料夾名稱對應 OpenLoco 的 `ObjectType` enum（`Vehicle`、`Building`、`Tree`…）。
- **物件資料夾的三種狀態**：

| 狀態 | 判斷方式 | 意義 |
|---|---|---|
| placeholder | 只有 `.gitkeep` | 待製作，**fork 的主要工作目標** |
| 上游完成 | 有 `OG_*.dat`／`OGE_*.dat`，沒有 `FORK.md` | 上游作品，**不要修改**（會造成 sync 衝突） |
| fork 自製 | 有 `FORK.md` | 本 fork 作品，上游完成同一物件時會被覆蓋 |

- 少數資料夾只有 `.dat` 是正常的：純文字物件（TownNames 等），或與其他物件共用 `.blend`（資料夾內會有 README 說明，例如 `ESTAR2` → `ESTAR1`）。

### 1.1 盤點

```bash
python3 tools/inventory.py                    # 依類型列出 已完成／fork 自製／placeholder
python3 tools/inventory.py --list placeholder # 列出待做清單
```

2026-11-22 快照（M3 完成後）：CD 版 vanilla 物件 545 個（不含範圍外的 4 個）中，上游完成 178、fork 自製 322、placeholder 45（全部是 ScenarioText，M6）。全部 placeholder 都在 `VanillaReplacements/` 底下。另有擴充包資料夾 53 個。

### 1.2 CI 打包規則（會影響命名）

`.github/workflows/` 會把 `objects/<Pack>/<Category>/**/*.dat` 全部**攤平**複製到 `objects.zip` 內的 `<Category>/<檔名>`（`cp -f`）。因此：
- 只有 `.dat` 會進入發行包；`.blend`、PNG、`FORK.md` 都不會。
- 同一 Category 底下，不同 Pack 若有同檔名的 `.dat`，**後者會靜默覆蓋前者**。檔名在同 Category 內必須唯一。
- 推 tag 會建立 GitHub Release（附 `objects.zip` 與 SHA256）。OpenLoco 透過 `../OpenLoco/CMakeLists.txt` 的 `FetchContent_Declare(openloco_objects URL ... URL_HASH ...)` 取用；要讓 OpenLoco 使用本 fork，就改這兩個值。

---

## 2. 物件規範

### 2.1 命名
- 檔名：`OG_<VANILLA名稱>.dat`，例如 `CTRUCK1` → `OG_CTRUCK1.dat`。直接填入該 placeholder 資料夾，並刪除 `.gitkeep`。
- DAT 內部名稱（header 的 8 字元，不足補空白）：
  - 以 `OG` 開頭；超過 8 字元就從尾端前面刪字，但**保留結尾的數字**以免撞名。
  - 範例（上游既有）：`LIVESTCK→OGLIVEST`、`CATTLE1→OGCATTL1`、`TRSTAT2→OGTRSTA2`、`BLDALP11→OGBLDA11`。
  - 結尾是「數字＋字母」時整段保留，避免撞名：`SNDCH1A→OGSNDC1A`、`SNDCH1AS→OGSND1AS`、`TREX3RL→OGTRE3RL`（`tools/dat.py og_internal_name`）。
  - 依本 fork 政策，**刻意與上游未來會用的名稱相同**，好讓上游版本自然取代。
- 遊戲內顯示名稱：原創或諧仿（parody），不可與 vanilla 或真實產品同名。參考 OpenTTD 的命名風格。
- 非 vanilla 的新物件（擴充包）：沿用上游慣例，檔名 `OGE_*`、內部名稱 `EX*`，放在對應 Pack 資料夾。

### 2.2 DAT header 必須符合
- `flags & 0x3F` = 該資料夾的 `ObjectType`（例如 Vehicle = 23、Tree = 24、Building = 28）。
- source = `(flags >> 6) & 3` = **3（openLoco）**，與上游所有物件一致。
- checksum 正確（OpenLoco 載入時會驗證，不符就拒絕載入；`tools/dat.py verify` 會檢查）。演算法見 `../OpenLoco/src/OpenLoco/src/Objects/ObjectManager.cpp` 的 `computeObjectChecksum`：seed `0xF369A75B`，依序處理 flags 的第 1 個 byte、8 bytes 名稱、解碼後的資料 chunk，每個 byte 做 `c = rotl32(c ^ b, 11)`。
- 整個 repo 內 `(type, 內部名稱)` 不可重複；同 Category 內檔名不可重複（`tools/lint.py` 會檢查）。

### 2.2.1 相依引用（攸關最終目標）
DAT 內會以 16-byte header 引用其他物件（車輛 → 軌道、蒸汽、音效；Region → 建築、產業、樹木；軌道 → 號誌、橋、車站…）。**只要引用到 vanilla 物件，就無法脫離 vanilla 運行。**
- fork 自製物件的相依引用，**一律指向 OG／EX 版本**（例如軌道用 `OGTRACKS` 而不是 `TRACKST`）。
- 需要的 OG 相依物件還不存在時，先暫時引用 vanilla，並在 `FORK.md` 列出「待改指向」清單。
- 上游物件裡的 vanilla 引用**不要直接改 DAT**：已由 OpenLoco fork 的別名層處理（`docs/ROADMAP.md` D1-A），只要別名表 `aliases.yml` 有對應即可。

### 2.3 資料夾內容

| 物件類型 | 必須 commit | 選擇性 |
|---|---|---|
| 3D 渲染（車輛、建築、產業…） | `OG_X.dat`、`OG_X.blend`、`FORK.md` | 產生 `.blend` 的 bpy 腳本（建議，方便 AI 迭代）、手修過的 PNG |
| 手繪／像素圖 | `OG_X.dat`、`0.png…N.png`、`sprites.json`、`FORK.md` | 繪製用的腳本 |
| 純文字／數值 | `OG_X.dat`、`FORK.md` | — |
| 音效 | `OG_X.dat`、原始音檔（`.wav`/`.ogg`）、`FORK.md` | — |

- `.blend` 引用的貼圖必須用相對路徑指向 repo 內的檔案（共用貼圖放 `/textures`）。不可有 `C:/Users/...` 這類絕對路徑。
- 不要 commit：Blender 的 `*.blend1` 備份、渲染與預覽產物（一律輸出到 `build/`，除非是手修過的最終 PNG 來源）、任何 vanilla 檔案。
- `sprites.json` 格式（ObjectEditor 匯出格式）：陣列，每個元素 `{path, x, y, zoomOffset, flags, name}`，`x`/`y` 是繪製偏移。可參考 `objects/Common/Land/OG_VOID/sprites.json`。

`FORK.md` 範本：

```markdown
# OG_CTRUCK1（fork 自製）
- 對應 vanilla：CTRUCK1（Vehicle/Truck）
- 內部名稱：OGCTRUC1
- 遊戲內名稱：<名稱>
- 設計概念：looks like it was based on ... / has elements from ... and ...
- 製作方式：<例如 bpy 腳本由 Claude 產生 + 手動調整 / 像素圖由 GPT 產生後量化>
- AI 工具：<模型名稱與用途>
- 參考資料：<公開領域或自製來源；不可列 vanilla sprite 作為生成輸入>
- 狀態：draft | dat-built | v1-passed | in-game-tested
- 待改指向的 vanilla 引用：<無 / 清單>

## 驗證紀錄
- YYYY-MM-DD V1：build/preview/OG_CTRUCK1.png — <看到什麼、修了什麼>
- YYYY-MM-DD V2：build/screenshots/OG_CTRUCK1/ — <看到什麼、修了什麼>
```

### 2.4 美術規範
- **調色盤**：最終 sprite 必須落在 Locomotion 256 色調色盤內（`palettes/locopal.act`）。index 0 = 透明。
- **公司色 remap**（車輛、部分建築必須正確使用，否則玩家選的公司色不會生效）：
  - primary remap：index `0x07–0x09`、`0xF6–0xFE`
  - secondary remap：index `0xCA–0xD5`
  - 定義來源：`../OpenLoco/src/OpenLoco/include/OpenLoco/Graphics/Colour.h`
- **尺寸**：與 vanilla 原物件大致相同。火車高度依 README 的「Train sprite scaling」表；地面車輛約 10 m = 1 tile。
- **視覺辨識度**：必須能與 vanilla 版本並存時一眼分辨，但輪廓與用途要對得上。
- **sprite 數量與順序**：必須與**該物件自己的屬性設定**一致（旋轉角度數、坡度、動畫格數等決定 OpenLoco 需要幾張圖），不一定等於 vanilla。例如上游 `OG_4F` 有 616 張，vanilla `4F` 只有 392 張。用 `tools/dat.py info` 與 `tools/preview.py --compare <vanilla DAT>` 對照 `LOCO_DATA_DIR` 中的 vanilla 物件。

---

## 3. 工具鏈與環境

| 工具 | 狀態／位置 | 用途 |
|---|---|---|
| Blender 5.2.3 | `~/.local/bin/blender`（本機已安裝） | 建模與渲染。可 headless：`blender -b <file>.blend --python <script>.py` |
| Blender MCP | Claude Code session 內可用 | 互動式檢查／修改正在開啟的 Blender 場景 |
| OpenLoco Graphics Helper add-on | 未安裝（官方版只支援 Blender 2.79；上游近期的 `.blend` 是用新版移植製作的） | 不需要：`tools/blender/render_sprites.py` 直接渲染 `.blend` 內已烘焙好的 rig（相機、燈光、逐格動畫） |
| `tools/`（本 repo） | ✅ P1 `blender/render_sprites.py`、P2 `quantize.py`、P3 `pack.py`；V1 `lint.py`、`preview.py`、`dat.py`、`deps.py`、`inventory.py`；V2 `install_test_env.py`、`run_openloco.sh`、`v2_smoke.sh`、`newgame_check.sh`、`s5.py`；製作 `blender/static_rig.py`（建築／產業／碼頭／機場）、`blender/vehicle_rig.py`（車輛、火車站）、`blender/models/ops.py`（幾何指令）、`gen/`（`build_simple_objects.py`、`build_blender_objects.py`、`build_vehicles.py`、`build_stations.py` 與各產生器、配方，見 `docs/PIPELINE.md`）；檢查 `stack_preview.py`；`make_placeholders.py`；g1 `g1.py`（catalog／placeholder） | 整條製作與驗證管線。用法見各檔開頭說明與 `docs/PIPELINE.md` |
| OpenLoco ObjectEditor | 未安裝；**不需要**（P3 已定案用 `tools/pack.py`） | 只在需要互動式檢視或編輯物件屬性時參考 |
| Python 3 | `/usr/bin/python3`；`.venv/`（Pillow，以 `uv venv .venv && uv pip install --python .venv/bin/python pillow` 建立） | `tools/` 中只有 `preview.py` 需要 Pillow（用 `.venv/bin/python` 執行），其餘只用標準函式庫 |
| OpenLoco 原始碼 | `../OpenLoco`：fork https://github.com/cashzero/OpenLoco （`origin`），官方為 `upstream`；工作分支 `og-main` | 格式權威參考（見下表），也是 V2 遊戲內驗證要 build 的對象 |
| OpenLoco build | ✅ `../OpenLoco/build/posix/Release/OpenLoco`（`posix` preset + 系統套件，build 自 `og-main`：headless `screenshot`／`--object`／`--centre town:N`／`industry:名稱`、`new-game`、`--exit-after-frames`、vanilla→OG 別名層、standalone 模式） | V2 遊戲內驗證。執行時一律加 `--locomotion_path`、用隔離環境與無視窗設定，否則會跳出視窗卡住（見 `docs/PIPELINE.md` V2） |
| vanilla Locomotion 資料 | `LOCO_DATA_DIR=$HOME/Locomotion/game`（從使用者的 ISO 解出）；版權素材 | 開發期量測用（尺寸、sprite 數量、結構模板），以及 M1 之前執行 OpenLoco。**絕不 commit**、不可複製進任何 repo，最終成品也不能依賴它 |

**相依套件原則**：工具與函式庫一律**優先使用現成的**（apt 套件、官方 release 執行檔）。只有在有明確理由時才自己從原始碼 build（例如需要的版本沒有現成的、要做靜態連結的發佈版、需要打 patch），並且事先說明理由。需要 sudo 時，一次列出完整的安裝指令給使用者，不要一個一個試錯。

**OpenLoco fork 政策**：引擎修改一律放在 fork（`docs/ROADMAP.md` D1、D2），不要在本 repo 裡 workaround 引擎的限制。分支：`master` 追上游，每個功能開 `og/<功能>` 分支，完成並驗證後合併進 `og-main`。commit 結尾加上 AI 協作標記；推到 fork 前先在本機 build 並跑過 `tools/v2_smoke.sh`。

OpenLoco 原始碼參考點（路徑相對於 `../OpenLoco/src/`）：
- `OpenLoco/include/OpenLoco/Objects/Object.h`：`ObjectType` enum、`ObjectHeader`、`SourceGame`
- `OpenLoco/src/Objects/<Type>Object.cpp`：各類物件的資料結構與 image table 用法
- `OpenLoco/src/Objects/Object.cpp`：`_vanillaObjects`（全部 vanilla 物件名稱清單）
- `OpenLoco/src/Objects/ObjectManager.cpp`：checksum
- `OpenLoco/include/OpenLoco/S5/SawyerStream.h`：DAT chunk 編碼（0 = none、1 = RLE single、2 = RLE multi、3 = rotate）

遊戲內測試一律透過 `tools/run_openloco.sh`（或 `tools/v2_smoke.sh`）在隔離環境 `build/openloco-env/` 執行，不要動到使用者自己的 `~/.config/OpenLoco`。細節見 `docs/PIPELINE.md` V2。

---

## 4. 單一物件製作流程

每個物件依序走完以下步驟。**一個物件 = 一個 commit**（訊息格式：`Add OG_<NAME> (fork)`／`Update OG_<NAME> (fork)`）。

1. **選題**：用 §1.1 盤點，挑一個 placeholder。依 `docs/ROADMAP.md` 目前里程碑的優先順序挑選。確認上游最新版本還沒做這個物件（先 `git fetch upstream`）。
2. **研究 vanilla**：類型、大小、sprite 數量與排列、旋轉／坡度／動畫格數、屬性數值（年份、速度、容量、價格）。記下來。
3. **設計 brief**：寫進 `FORK.md` 草稿——名稱、設計概念（混合哪些時代特徵）、與 vanilla 的差異點、預計的屬性數值。**名稱與概念先給使用者確認再動工**。
4. **製作來源檔**：
   - 3D：寫 bpy 腳本產生模型 → 存 `OG_<NAME>.blend`（相對路徑貼圖）→ turntable 預覽，**看過圖、修好造型**再往下走。
   - 像素圖：產生 PNG → 量化到 Loco 調色盤 → 檢查 remap 區域。
5. **渲染與量化**：`docs/PIPELINE.md` P1、P2（`blender -b … --python tools/blender/render_sprites.py -- --out build/render/<NAME>` → `.venv/bin/python tools/quantize.py`）。影格順序 = sprite 順序。
6. **打包 DAT**：`docs/PIPELINE.md` P3（`.venv/bin/python tools/pack.py --template … --sprites … --name OG… --display …`）。模板提供結構與屬性；內部名稱、source = 3、checksum 自動處理。
7. **V1 素材驗證**：`docs/PIPELINE.md` V1。lint 全部通過，並**親自看過**從最終 DAT 解出的 contact sheet。`FORK.md` 狀態改為 `v1-passed`，寫下驗證紀錄。
8. **V2 遊戲內驗證**：`docs/PIPELINE.md` V2。重新組測試環境後跑 `tools/v2_smoke.sh`（確認物件能載入、模擬不崩潰），再用 `tools/run_openloco.sh screenshot` 拍出含有該物件的畫面並**親自看過**。`FORK.md` 狀態改為 `in-game-tested`。
9. **Commit**：刪除 `.gitkeep`，只 commit 該物件資料夾。

管線工具還沒建好（`docs/ROADMAP.md` M0）之前，步驟 5–8 中做不到的部分要在 `FORK.md` 註明「未驗證：原因」，**不可以宣稱已通過**。

### Agent 與使用者的分工
- **Agent 自己做（包含驗證）**：盤點、研究 OpenLoco 原始碼、開發 `tools/` 與 OpenLoco fork 功能、寫 bpy 腳本並 headless 渲染、產生與量化像素圖、打包 DAT、V1 與 V2 驗證（包含 build 並執行 OpenLoco、看截圖）、產生 placeholder、撰寫名稱與數值草稿、整理 commit。
- **需要使用者**：確認名稱與設計概念、需要 sudo 的系統套件安裝、提供 vanilla 資料路徑、建立 GitHub fork、最終驗收、push 與發 release。
- **未經使用者同意不要做**：修改上游完成的物件、改動 CI、push 到任何遠端、刪除任何非 placeholder 的資料夾。

---

## 5. 驗證

完整的驗證管線（V1 素材驗證、V2 遊戲內驗證、placeholder）定義在 [`docs/PIPELINE.md`](docs/PIPELINE.md)，必須照做。最低要求：

```bash
python3 tools/lint.py <你的 DAT>                 # 自動檢查；必須 0 個錯誤
python3 tools/dat.py info <你的 DAT>             # 檔頭、名稱、checksum、image 數
.venv/bin/python tools/preview.py <你的 DAT> -o build/preview/<NAME>.png --remap   # 產生後必須親自看圖
python3 tools/deps.py <你的 DAT> --per-file      # 相依引用，vanilla 引用要記進 FORK.md
```

另外人工確認：`.blend` 沒有絕對路徑貼圖、資料夾內有 `FORK.md`、`.gitkeep` 已刪除。

---

## 6. 上游同步流程

前置（只需一次）：

```bash
git remote add upstream https://github.com/OpenLoco/OpenGraphics.git
```

每次同步：

```bash
git fetch upstream
git switch -c sync/upstream-$(date +%Y%m%d) main
BASE=$(git merge-base HEAD upstream/main)

# 找出：上游這次有變動、而且 fork 在該資料夾有 FORK.md 的物件 → 將被上游取代
mkdir -p build
git diff --name-only "$BASE" upstream/main -- objects/ | xargs -r -n1 dirname | sort -u \
  | while read d; do [ -f "$d/FORK.md" ] && echo "$d"; done > build/superseded.txt
cat build/superseded.txt

git merge --no-ff upstream/main   # 可能出現衝突，先不要急著解

# 被取代的資料夾：整個換成上游版本（fork 的 .blend、FORK.md 等一併移除）
while read d; do
  git rm -rq --ignore-unmatch "$d"
  git checkout upstream/main -- "$d"
done < build/superseded.txt
```

接著：
1. 解決其餘衝突：`README.md` 保留 fork 對 AI 規定的修改，其餘採用上游；`AGENTS.md`、`CLAUDE.md` 是 fork 專屬檔案，以 fork 為準。
2. 檢查**路徑搬移**：上游計畫把 `VanillaReplacements` 重整到各 Pack。對每個含 `FORK.md` 的資料夾，確認上游還有同路徑（`git ls-tree upstream/main -- <path>`）；若上游已搬走該 placeholder，把 fork 資料夾搬到新位置。
3. 檢查**換位置的同名物件**：上游可能把同一物件做在別的 Pack。跑 §5 的重複檢查；若 fork 物件與上游物件 `(type, 名稱)` 重複，刪除 fork 的。
4. 驗證全部通過後 commit，交給使用者確認再 merge 回 `main`。

已知影響：使用 fork 版物件的存檔，在上游版本取代後仍能載入（OpenLoco 對 source = openLoco 的物件只比對 type + 名稱），但外觀與數值會變成上游版本。

---

## 7. 路線圖與文件

- 路線圖、里程碑、待決策事項：[`docs/ROADMAP.md`](docs/ROADMAP.md)。完成路線圖上的項目時，在同一個 commit 裡勾選並更新該檔。
- 非物件素材（`g1`、音訊、標題、情境）放在 `base/`（ROADMAP 決策 D3），規則見 `base/README.md`。不要在 repo 根目錄另開其他素材資料夾。
- 新的研究結果（檔案格式、OpenLoco 行為）寫在 `docs/` 底下，並從 ROADMAP 連結過去。
