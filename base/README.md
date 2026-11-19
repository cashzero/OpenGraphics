# base/ — 物件以外的基礎素材（fork 專屬）

依 `docs/ROADMAP.md` 決策 D3（2026-11-19 採用），讓 OpenLoco 不需要 vanilla `Data/` 的素材都放在這裡。
上游 OpenGraphics 沒有這個目錄；若上游日後也做了同類素材，依「上游優先」政策處理。

| 子目錄 | 取代的 vanilla 檔案 | 里程碑 |
|---|---|---|
| `g1/` | `Data/g1.DAT`（基礎圖形 4122 張：UI、字型、圖示…） | M1（placeholder）、M4（正式） |
| `sfx/` | `Data/CSS1.DAT`（音效）、`CSS2–4.DAT`（環境音） | M5 |
| `music/` | 29 首背景音樂與標題音樂 `CSS5.DAT` | M5 |
| `title/` | `Data/title.dat`（標題畫面背景存檔） | M6 |
| `scenarios/` | `Scenarios/*.SC5`（只用 OG 物件的情境） | M6 |

規則：
- 與 `objects/` 相同：來源檔要進 repo、允許 AI 素材、不可複製 vanilla 或真實品牌。
- 子目錄在有內容時才建立。
- 打包：之後由 CI 與 `objects.zip` 一起發行（M1 時調整 `.github/workflows/`）。
