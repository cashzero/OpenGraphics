# base/music — 背景音樂（ROADMAP M5）

OpenLoco 的 29 首背景音樂與標題曲，改用 **OpenMSX** 的 MIDI（OpenTTD 的免費音樂集），由 OpenLoco fork 以 SoundFont 即時合成。

## 授權

本資料夾的檔案**不是** MIT 授權（與 repo 其他部分不同），而是 **GNU GPL v2**，全文見 [`COPYING`](COPYING)：

| 檔案 | 來源 | 著作權 | 授權 |
|---|---|---|---|
| `midi/*.mid` | [OpenMSX](https://github.com/OpenTTD/OpenMSX) 0.4.2（取自 Debian 套件 `openttd-openmsx` 0.4.2-2，md5 與 OpenMSX 的 `openmsx.obm` 相符） | © 2010–2021 OpenMSX Authors（作者見下表） | GPL v2 |
| `TimGM6mb.sf2` | TimGM6mb 1.3（取自 Debian 套件 `timgm6mb-soundfont`） | © 2004 Tim Brechbill、2010 David Bolton | GPL v2 |

MIDI 檔本身就是樂曲的原始檔，沒有修改。OpenMSX 的協調者是 Ingo von Borstel（planetmaker），音樂顧問 kamnet。
`Careless Love` 是公有領域的傳統曲（Jim Redfarn 編曲）；`Moo Moo Boogie` 的靈感來自 Cow Cow Boogie。

## 曲目分配（`tracks.json`）

slot = OpenLoco 預期的檔名（`Data/<slot>.DAT`，見 OpenLoco `Environment.cpp`）。依 `Jukebox.cpp` 的播放年代挑風格接近的曲子：
拉格泰姆與 20 年代時段用 Jim Redfarn 的鋼琴／布吉曲，40–70 年代用爵士、薩克斯風、電鋼琴類，80–90 年代用合成器曲。
OpenMSX 31 首中只有 `wood_whistles.mid`（Wood Whistles）沒有用到。

| slot | 年代 | 曲名 | 作者 | 檔案 |
|---|---|---|---|---|
| `CSS5` | 標題曲 | OpenTTD Journey | -lucas- | `tttheme2.mid` |
| `Eugenia` | –1908 | Careless Love | Jim Redfarn（傳統曲） | `careless_perc_redfarn.mid` |
| `Chrysanthemum` | –1911 | Slow and Easy | Jim Redfarn | `slow_neasy_redfarn.mid` |
| `Rag1` | –1914 | Mosey Along | Jim Redfarn | `mosey_along_redfarn.mid` |
| `Rag2` | 1909–1917 | Moo Moo Boogie | Jim Redfarn | `moo_redfarn.mid` |
| `rag3` | 1912–1920 | City Blues | Jim Redfarn | `city_blues_redfarn.mid` |
| `20s5` | 1918–1926 | No Work Song | Jim Redfarn | `no_work_song_redfarn.mid` |
| `20s6` | 1921–1929 | The Hobo | Jim Redfarn | `the_hobo_redfarn.mid` |
| `20s1` | 1925–1933 | Boogie Marabi | Jim Redfarn | `boogi_marabi_redfarn.mid` |
| `20s2` | 1927–1935 | Be Sharp Boogie | Jim Redfarn | `be_sharp_bw_redfarn.mid` |
| `20s3` | 1929–1937 | Say What | Jim Redfarn | `say_what_redfarn.mid` |
| `20s4` | 1932–1940 | 5 4 3 2 .. Gone | Jim Redfarn | `5432gone_redfarn.mid` |
| `40s1` | 1940–1948 | Keep on Rolling | Trolley Trev | `keep_on_rolling.mid` |
| `40s2` | 1943–1951 | Coconut Run 2 | Tistou Blomberg | `coconut_run2.mid` |
| `40s3` | 1946–1954 | Busy Schedule | mimm | `busy_schedule.mid` |
| `50s3` | 1950–1958 | The Fast Route | mimm | `the_fast_route.mid` |
| `50s2` | 1953–1961 | Excitement! Run for Your Life | Tistou Blomberg | `run_for_your_life.mid` |
| `50s1` | 1956–1964 | Train Filled with Cash | imuh3 | `train_filled_with_cash.mid` |
| `60s1` | 1960–1968 | Harp Harmony 'n Humor | Tistou Blomberg | `harp_harmony.mid` |
| `60s2` | 1963–1971 | Plain Simple Relax Song | Tistou Blomberg | `relax_song.mid` |
| `60s3` | 1966–1974 | Deep Down Chemistry Lab | Tistou Blomberg | `chemistry_lab.mid` |
| `70s3` | 1970–1978 | Midnight Snow Run | Tistou Blomberg | `midnight_snow_run.mid` |
| `70s2` | 1973–1981 | Downtown Cab Ride | imuh3 | `ttsong_iv_imuh3.mid` |
| `70s1` | 1976–1984 | Linn's Basket of Treats | Tistou Blomberg | `linns_basket.mid` |
| `80s2` | 1980–1988 | Modern Motion | Kyle Timmerman (Mr.Ksoft) | `modern_motion.mid` |
| `80s3` | 1983–1991 | Mighty Giant Run | Tistou Blomberg | `mighty_giant_run.mid` |
| `80s4` | 1986–1994 | Ultimate Run | Tistou Blomberg | `ultimate_run.mid` |
| `80s1` | 1990– | Skydive | imuh3 | `ttsong_iii_imuh3.mid` |
| `90s1` | 1993– | Unidentified Flying Scotsman | imuh3 | `flying_scotsman.mid` |
| `90s2` | 1996– | Chugga Chugga Cha-ching | imuh3 | `chuggachugga.mid` |

## 安裝與運作

```bash
python3 tools/music.py check
python3 tools/music.py install <Data 目錄>   # 寫出 <slot>.mid、TimGM6mb.sf2、music.yml、COPYING-music
```

OpenLoco fork（`Audio.cpp`、`Jukebox.cpp`）：找不到 `Data/<slot>.DAT` 時改讀同名的 `.mid`（不分大小寫），以同資料夾的第一個 `.sf2`
在背景執行緒合成（TinySoundFont，22050 Hz 立體聲，響度正規化到 vanilla 音樂的 RMS 0.16，約 0.5–1 秒）；`music.yml` 的曲名會取代點唱機顯示的曲名。
vanilla 的 WAV 音樂照常可用。
