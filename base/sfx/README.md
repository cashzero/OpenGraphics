# base/sfx — 音效與環境音（ROADMAP M5）

`Data/CSS1.DAT`（32 個介面／事件音效）與環境音 `CSS2.DAT`、`CSS4.DAT`，素材來自 **OpenSFX**（OpenTTD 的免費音效集）。

## 授權

本資料夾的檔案**不是** MIT 授權（與 repo 其他部分不同）：OpenSFX 整體為 **CC BY-SA 3.0**
（https://creativecommons.org/licenses/by-sa/3.0/），個別檔案為 CC BY 3.0、CC BY-SA 3.0 或 CC0，作者與原始出處如下
（文字取自 OpenSFX 1.0.3 `opensfx.cat` 內每個音效的名稱欄位；Debian 套件 `openttd-opensfx` 1.0.3-3build1）。
`tools/sfx.py install` 會把這份清單寫成 `Data/COPYING-sfx.txt` 一起發佈。

| 檔案 | 出處與授權 |
|---|---|
| `00_good_year.wav` | "Good Year". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `01_bad_year.wav` | "Bad Year". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `02_splat_building_docks_canals_.wav` | "Splat (building docks/canals/river)". Original "splattt.mp3" by "SlykMrByches". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |
| `15_road_vehicle_breakdown.wav` | "Road vehicle breakdown". Original "Dropping a large gun.wav" by "Leady". Edited by Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `16_train_ship_breakdown.wav` | "Train/ship breakdown". Original "Dumpster_Diving.wav" by "1sticky8". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |
| `17_crash.wav` | "Crash". Original "crash.wav" by "sagetyrtle". Edited by Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `19_big_crash.wav` | "Big crash". Original "crash.wav" by "sagetyrtle". Edited by Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `20_cash_till.wav` | "Cash till". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `21_beep.wav` | "Beep". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `22_morse.wav` | "Morse". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `23_plane_wheels_touching_ground.wav` | "Plane wheels touching ground". Original "CarStartSkidCrash.wav" by "musicmasta1". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |
| `29_applause.wav` | "Applause". Original "Approx 850 - Enthusiast Audience.wav" by "lonemonk". Edited by "Wuzzy". License: Creative Commons Attribution 3.0 Unported. |
| `30_oooh_sound.wav` | "Oooh sound". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `31_splat_terraform_non_rail_bui.wav` | "Splat (terraform/non-rail builds". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `32_splat_rail_builds.wav` | "Splat (rail builds)". Original "kick_1.wav" by "jascha". Edited by "Wuzzy". License: Creative Commons Attribution 3.0 Unported. |
| `47_bubble_plop.wav` | "Toyland: Bubble plop". By Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `52_wind.wav` | "Wind". Original "wind1.wav" by "Anton". Edited by Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `54_crashing_tree.wav` | "Lumber mill: Crashing tree". Original "A Tree Falling Down.wav" by "ecfike". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |
| `57_heavy_wind.wav` | "Heavy wind". Original "wind1.wav" by "Anton". Edited by Janis Lukss. License: Creative Commons Attribution 3.0 Unported. |
| `66_bird_1.wav` | "Tropical: Bird (1)". Original "Bird Noise - 1.wav" by "SpaceJoe". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |
| `72_bird_2.wav` | "Tropical: Bird (2)". Original "Bird Noise - 12.wav" by "SpaceJoe". Edited by "Wuzzy". License: Creative Commons Zero 1.0. |

## 對應（`sounds.json`）

CSS1：OpenLoco `SoundId` 0–31 → 素材。增益依 vanilla 同一音效的 RMS 量出（只用數值，最多放大 2 倍）。
`clickUp` 在 vanilla 只有 0.01 秒、幾乎無聲，所以用靜音，避免一次點擊響兩聲。breakdown1–6、splash1、applause1、
multiplayer 兩個目前 OpenLoco 沒有用到，仍依用途填入。

| SoundId | 名稱 | 素材 | 增益 |
|---|---|---|---|
| 0 | `clickDown` | `21_beep.wav` | 0.12 |
| 1 | `clickUp` | 靜音 |  |
| 2 | `clickPress` | `21_beep.wav` | 0.12 |
| 3 | `construct` | `32_splat_rail_builds.wav` | 1.08 |
| 4 | `demolish` | `31_splat_terraform_non_rail_bui.wav` | 0.98 |
| 5 | `income` | `20_cash_till.wav` | 0.9 |
| 6 | `crash` | `19_big_crash.wav` | 0.61 |
| 7 | `water` | `02_splat_building_docks_canals_.wav` | 1.26 |
| 8 | `splash1` | `02_splat_building_docks_canals_.wav` | 0.91 |
| 9 | `splash2` | `02_splat_building_docks_canals_.wav` | 0.6 |
| 10 | `waypoint` | `21_beep.wav` | 0.28 |
| 11 | `notification` | `22_morse.wav` | 2.0 |
| 12 | `openWindow` | `47_bubble_plop.wav` | 0.68 |
| 13 | `applause1` | `29_applause.wav` | 0.68 |
| 14 | `error` | `01_bad_year.wav` | 1.95 |
| 15 | `multiplayerConnected` | `00_good_year.wav` | 2.0 |
| 16 | `multiplayerDisconnected` | `01_bad_year.wav` | 1.95 |
| 17 | `demolishTree` | `54_crashing_tree.wav` | 0.29 |
| 18 | `demolishBuilding` | `17_crash.wav` | 0.69 |
| 19 | `vehiclePlace` | `23_plane_wheels_touching_ground.wav` | 1.19 |
| 20 | `vehiclePickup` | `32_splat_rail_builds.wav` | 0.85 |
| 21 | `constructShip` | `02_splat_building_docks_canals_.wav` | 0.96 |
| 22 | `ticker` | `21_beep.wav` | 0.17 |
| 23 | `applause2` | `29_applause.wav` | 0.46 |
| 24 | `newsOooh` | `30_oooh_sound.wav` | 1.89 |
| 25 | `newsAwww` | `01_bad_year.wav` | 1.18 |
| 26 | `breakdown1` | `15_road_vehicle_breakdown.wav` | 0.68 |
| 27 | `breakdown2` | `16_train_ship_breakdown.wav` | 0.72 |
| 28 | `breakdown3` | `15_road_vehicle_breakdown.wav` | 0.97 |
| 29 | `breakdown4` | `16_train_ship_breakdown.wav` | 0.86 |
| 30 | `breakdown5` | `15_road_vehicle_breakdown.wav` | 0.75 |
| 31 | `breakdown6` | `16_train_ship_breakdown.wav` | 0.81 |

環境音（`AmbientAudio.cpp` 依周圍地形選擇，循環播放；9 秒，頭尾等功率交叉淡化，響度調到 vanilla 同一檔案的 RMS）：

| 檔案 | 用途 | 素材 |
|---|---|---|
| `CSS2.DAT` | 荒野／山地（AmbientAudio.cpp：附近山地多） | `57_heavy_wind.wav`（循環底音）、`52_wind.wav`（循環底音） |
| `CSS4.DAT` | 森林（附近樹木多） | `52_wind.wav`（循環底音）、`66_bird_1.wav`（0.8 秒）、`72_bird_2.wav`（5.2 秒） |
| `CSS3.DAT` | 海邊（附近水多） | **缺**：OpenSFX 沒有海浪聲，暫時靜音 |

## 產生

```bash
python3 tools/sfx.py check
python3 tools/sfx.py install <Data 目錄>   # CSS1.DAT、CSS2.DAT、CSS4.DAT、COPYING-sfx.txt
```
