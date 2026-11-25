# 標題畫面（ROADMAP M6）

OpenLoco 啟動時載入 `Data/title.dat`（一張地圖存檔），再依鏡頭清單在地圖上移動。本資料夾是這兩者的來源：

| 檔案 | 內容 |
|---|---|
| `title.yml` | 場景腳本：地形、物件、要建造的城鎮／鐵路／車輛…（OpenLoco fork 的 `build-scene` 讀取） |
| `heightmap.png` | 地形高度圖，由 `tools/gen/title_heightmap.py` 產生（不要手改） |
| `title.dat` | 建好的地圖存檔（產物，但要 commit：建造需要 OpenLoco fork，CI 不重建） |
| `camera.yml` | 鏡頭清單，安裝成 `Data/title.yml` |

```bash
python3 tools/install_test_env.py --with-placeholders --with-base   # 建造用的測試環境（物件 + standalone base）
python3 tools/title.py build                                        # 高度圖 → build-scene → base/title/title.dat
python3 tools/title.py install build/openloco-env/data/base/Data    # install_test_env --with-base 也會自動做
```

場景是 10 個設計好的小場景（「vignette」），鏡頭依序停在各場景：

| # | 場景 | 重點 |
|---|---|---|
| 1 | 秋季河谷 | 磚造高架橋跨河、山脊隧道，蒸汽快車 |
| 2 | 河港城鎮 | 吊橋連接兩岸，公車過橋，渡輪在橋下往返兩座碼頭 |
| 3 | 市中心 | 先蓋車站再讓城市長大，通勤列車開往郊區 |
| 4 | 機場 | 洲際機場與區域機場之間的客機 |
| 5 | 礦業線 | 煤礦 → 發電廠的運煤列車 |
| 6 | 農村 | 農場 → 食品加工廠的卡車 |
| 7 | 阿爾卑斯雪村 | 窄軌齒軌鐵道切穿山脊爬上雪村 |
| 8 | 林場 | 森林 → 鋸木廠的運材卡車 |
| 9 | 海岸鐵路 | 海崖上的單線鐵路、岬角燈塔 |
| 10 | 郊區 | 通勤線的郊區車站 |

## 場景腳本格式（`title.yml`）

座標一律是**格**（tile），高度是**級**（1 級 = 16 世界單位 = 一段坡道的落差；海平面 4 級）。
方向 `dir`：0 = −x、1 = +y、2 = +x、3 = −y（rotation 0 的畫面上，+x 往左下、+y 往右下）。

頂層：

| 鍵 | 說明 |
|---|---|
| `year`、`seed` | 開始年份、地圖生成的亂數種子 |
| `heightmap`、`sea_level` | 高度圖 PNG（相對於腳本）、海平面 |
| `trees` | `{forests, random, radius, density, altitude}`：地圖生成時的樹林（altitude 單位是 smallZ，1 級 = 4） |
| `remove_generated_industries` | 移除地圖生成時的產業，只留 ops 放的 |
| `freeze_industries` | 禁止產業自行開張／倒閉 |
| `company_colours` | `[主色, 副色]`（`Graphics/Colour.h` 的名稱，例如 `red`、`grey`）；不設定時每次重建隨機選色 |
| `objects` | 要載入的物件（內部名稱）；氣候要放在 region 之前 |
| `ops` | 依序執行的建造指令（下表） |
| `date`、`simulate` | 最後把日期設成 `[年, 月, 日]`，再模擬 N tick 才存檔（樹木的季節才會正確） |

ops（每個是單鍵 map，例如 `- town: {at: [231, 300], size: 8}`）：

| op | 參數 |
|---|---|
| `town` | `at`、`size`（1–8） |
| `industry` | `type`、`at` |
| `building` | `type`、`at`、`rot`、`variation` |
| `track` | `object`、`start`、`z`、`dir`、`path`；選填 `station`、`bridge`、`signal`、`mods`（trackExtra，例如齒軌 `OGTREXRA`、架空線 `OGTREXCA`） |
| `road` | `object`、`start`、`z`、`dir`、`path`；選填 `station`、`bridge` |
| `airport`、`dock` | `type`、`at`、`rot`（碼頭可用 `auto`：自動找面向水的方向）、`label` |
| `vehicle`（`train`） | `vehicles`（車頭在前）、`at`（標籤）、`orders`（標籤清單）、`reverse`（列車放在最後一格月台時用） |
| `trees` | `types`、`area: [x0, y0, x1, y1]`、`count` |
| `clear`、`land` | `area`；`land` 另有 `type`（地表物件）。`clear` 之後地面是裸土，要再 `land` 鋪回草地 |
| `raise`、`lower` | `area`、`steps`：整塊抬高／壓低（隧道口需要 ≥ 2 級的崖面） |
| `simulate` | tick 數（例如讓城鎮長大、讓第一台車先開走） |
| `probe` | `area`：除錯用，把區域內容印成文字地圖（`~` 水、`R` 道路、`T` 軌道、`S` 車站、`B` 建築、`I` 產業、`t` 樹、數字 = 地面高度的個位數） |

`path` 是空白分隔的片段：`S` 直線、`ST` 月台／車站、`F` 順著地形的直線（自動用陡坡上下）、`L1`–`L4`／`R1`–`R4` 左右彎、
`SBL`／`SBR` S 彎、`SIG` 號誌；後綴 `+`／`-` 緩坡（2 格 1 級）、`++`／`--` 陡坡；`:名稱` 標籤（重複時記在最後一段）、`*N` 重複。

### 經驗法則
- 車站需要地圖上已經有城鎮（任何一個）。要讓城鎮圍著車站長，先蓋鐵路與車站、再放城鎮、最後長時間 `simulate`。
- 道路、軌道不能蓋在側坡上；需要平地的地方在 `tools/gen/title_heightmap.py` 的 `FLATS`／`PROFILES` 加區塊。
- 列車放在最後一格月台並 `reverse: true`；公車放在路中間的標籤，不要放在盡頭的站。同一格要放第二台車時，先 `simulate` 幾百 tick。
- 建造失敗時會存下 `<輸出>.failed.SV5`，可以用 `tools/run_openloco.sh screenshot` 看現場；`probe` 可以看哪裡被擋住。

## 鏡頭清單（`camera.yml`）

```yaml
zoom: 0                     # 預設縮放（0 = 最近）
camera:
  - [206, 182, 0, 400]      # [格 x, 格 y, rotation 0–3, 停留 tick 數, 縮放（選填）]
```

播完最後一個鏡頭後重新載入 `title.dat`，從頭開始。
