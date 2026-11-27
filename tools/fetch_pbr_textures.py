#!/usr/bin/env python3
"""下載並整理 Poly Haven（CC0 1.0）真實實拍 PBR 材質紋理庫至 textures/pbr/。

用法：
  .venv/bin/python tools/fetch_pbr_textures.py [--size 512] [--force] [--contact-sheet build/preview/pbr_library.png]

每組材質輸出至 textures/pbr/<slot>/：
  - albedo.jpg  （sRGB 基礎色貼圖，512×512）
  - normal.jpg  （OpenGL 切線空間法線貼圖，512×512，供 Blender Non-Color 讀取）
  - rough.jpg   （灰階粗糙度貼圖，512×512，供 Blender Non-Color 讀取）
同時產生 textures/pbr/CREDITS.md 紀錄每張貼圖的 Poly Haven ID、網址與 CC0 1.0 授權。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "textures" / "pbr"
UA = {"User-Agent": "OpenGraphics-PBR-Fetcher/1.0 (https://github.com/cashzero/OpenGraphics)"}

# 19 組精選實拍 CC0 建築／屋頂／工業／地表 PBR 材質（slot -> (polyhaven_id, 用途說明)）
CATALOG: dict[str, tuple[str, str]] = {
    "brick_red":       ("red_brick",              "紅磚外牆（brick）"),
    "brick_dark":      ("brick_wall_001",         "深色古舊焦磚外牆（darkbrick）"),
    "brick_yellow":    ("yellow_brick",           "暖黃磚外牆（yellowbrick）"),
    "stone_ashlar":    ("sandstone_blocks_04",    "砂岩／石灰岩切石塊（sandstone, limestone, stone）"),
    "stone_rustic":    ("old_stone_wall",         "古舊粗砌石牆（darkstone, 風車／農舍石基）"),
    "plaster":         ("painted_plaster_wall",   "風化灰泥粉刷牆（plaster, whitewash, cream, ochre, pink）"),
    "wood_siding":     ("wood_plank_wall",        "木造雨淋板與木板（wood, darkwood, lightwood, whitewood, redwood, sage, planks, logs）"),
    "concrete_wall":   ("concrete_wall_004",      "建築澆置混凝土外牆（concrete, darkconcrete, whiteconcrete）"),
    "roof_terracotta": ("clay_roof_tiles_02",     "歐式陶土屋瓦（terracotta, redshingle）"),
    "roof_slate":      ("roof_slates_02",         "威爾斯深灰藍板岩屋瓦（slate, shingle）"),
    "roof_corrugated": ("worn_corrugated_iron",   "風化浪板金屬屋頂（corrugated, copper）"),
    "roof_thatch":     ("thatch_roof_angled",     "自然茅草屋頂（thatch, hay）"),
    "metal_steel":     ("metal_plate_02",         "工業平滑風化鋼板與儲槽（steel, darksteel, silver, lead, yellowsteel, chemblue）"),
    "metal_rust":      ("rusty_metal_02",         "鏽蝕舊鐵（rust）"),
    "ground_asphalt":  ("asphalt_02",             "裂縫風化柏油路面與跑道（asphalt）"),
    "ground_apron":    ("hangar_concrete_floor",  "油漬伸縮縫機場停機坪／碼頭水泥板（apron, quay）"),
    "ground_pavement": ("precast_stone_paving",   "人行道與廣場鋪石板（pavement）"),
    "ground_dirt":     ("farm_soil",              "真實翻耕農田泥土與土塊（dirt, farmland）"),
    "ground_gravel":   ("gravel_concrete",        "碎石庭院與工業礦場地坪（gravel, ore, coal）"),
    "ground_rock":     ("rocks_ground_05",        "實拍高山花崗岩塊與碎石岩地（ROCK1 地形）"),
}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_image(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return Image.open(io.BytesIO(r.read()))


def pick_url(files_info: dict, keys: tuple[str, ...]) -> tuple[str | None, str | None]:
    """從 Poly Haven files JSON 選出最適合的 1k（或 2k）jpg/png 網址。"""
    for k in keys:
        node = files_info.get(k)
        if not isinstance(node, dict):
            continue
        for res in ("1k", "2k"):
            rnode = node.get(res)
            if not isinstance(rnode, dict):
                continue
            for fmt in ("jpg", "png"):
                fnode = rnode.get(fmt)
                if isinstance(fnode, dict) and "url" in fnode:
                    return k, fnode["url"]
    return None, None


def download_slot(slot: str, asset_id: str, size: int, force: bool) -> tuple[str, str]:
    d = OUT_DIR / slot
    d.mkdir(parents=True, exist_ok=True)
    p_alb, p_nrm, p_rgh = d / "albedo.jpg", d / "normal.jpg", d / "rough.jpg"
    if not force and p_alb.exists() and p_nrm.exists() and p_rgh.exists():
        return slot, "cached"

    info = fetch_json(f"https://api.polyhaven.com/files/{asset_id}")
    _, alb_url = pick_url(info, ("Diffuse", "col", "albedo"))
    _, nrm_url = pick_url(info, ("nor_gl", "Normal", "nor_dx"))
    rgh_key, rgh_url = pick_url(info, ("Rough", "roughness", "arm"))

    if not alb_url:
        raise RuntimeError(f"{slot} ({asset_id}): 找不到 Diffuse 貼圖，可用鍵：{list(info.keys())}")

    im_alb = fetch_image(alb_url).convert("RGB").resize((size, size), Image.LANCZOS)
    im_alb.save(p_alb, format="JPEG", quality=92, subsampling=0)

    if nrm_url:
        im_nrm = fetch_image(nrm_url).convert("RGB").resize((size, size), Image.LANCZOS)
        im_nrm.save(p_nrm, format="JPEG", quality=94, subsampling=0)
    else:
        Image.new("RGB", (size, size), (128, 128, 255)).save(p_nrm, format="JPEG", quality=94)

    if rgh_url:
        im_r = fetch_image(rgh_url)
        if rgh_key == "arm":
            # ARM 貼圖的 G 通道即 Roughness
            im_r = im_r.convert("RGB").split()[1]
        else:
            im_r = im_r.convert("L")
        im_r = im_r.resize((size, size), Image.LANCZOS)
        im_r.save(p_rgh, format="JPEG", quality=90)
    else:
        Image.new("L", (size, size), 185).save(p_rgh, format="JPEG", quality=90)

    kb = sum(p.stat().st_size for p in (p_alb, p_nrm, p_rgh)) // 1024
    return slot, f"OK ({asset_id}, {kb} KB)"


def write_credits() -> None:
    lines = [
        "# OpenGraphics PBR 紋理庫來源與授權（`textures/pbr/`）",
        "",
        "本資料夾收錄供 Blender Cycles 渲染使用之無縫 PBR 紋理（統一縮放至 512×512），皆可由 `tools/fetch_pbr_textures.py` 重建。",
        "",
        "## Poly Haven CC0 1.0 實拍 PBR 材質",
        "",
        "| 資料夾（Slot） | Poly Haven ID | 授權 | 用途 |",
        "|---|---|---|---|",
    ]
    for slot, (aid, desc) in CATALOG.items():
        lines.append(f"| `{slot}` | [{aid}](https://polyhaven.com/a/{aid}) | CC0 1.0 Public Domain | {desc} |")
    win_dir = OUT_DIR / "window_facade"
    if win_dir.exists():
        lines += [
            "",
            "## AI 生成客製遊戲紋理（依 `AGENTS.md §0` 紀錄）",
            "",
            "| 資料夾（Slot） | 來源工具 | 用途 |",
            "|---|---|---|",
            "| `window_facade` | Nano Banana (`image-generator`)，無外部/vanilla 輸入 | 建築窗戶深色室內與窗格微反射貼圖 |",
        ]
    (OUT_DIR / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_contact_sheet(out_path: Path) -> None:
    slots = [s for s in CATALOG if (OUT_DIR / s / "albedo.jpg").exists()]
    if (OUT_DIR / "window_facade" / "albedo.jpg").exists():
        slots.append("window_facade")
    tile = 128
    cols = 3  # 每列 3 組材質，每組顯示 Albedo + Normal + Rough
    rows = (len(slots) + cols - 1) // cols
    pad = 8
    cell_w = tile * 3 + pad * 2
    cell_h = tile + 22
    sheet = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), (28, 30, 34))
    draw = ImageDraw.Draw(sheet)
    for idx, slot in enumerate(slots):
        r, c = divmod(idx, cols)
        x0 = pad + c * cell_w
        y0 = pad + r * cell_h
        d = OUT_DIR / slot
        draw.text((x0 + 2, y0 + 2), slot, fill=(230, 235, 240))
        for k, fn in enumerate(("albedo.jpg", "normal.jpg", "rough.jpg")):
            p = d / fn
            if p.exists():
                im = Image.open(p).convert("RGB").resize((tile, tile), Image.LANCZOS)
                sheet.paste(im, (x0 + k * tile, y0 + 18))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"Contact sheet → {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--contact-sheet", default=str(REPO / "build" / "preview" / "pbr_library.png"))
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(download_slot, s, aid, args.size, args.force) for s, (aid, _) in CATALOG.items()]
        for f in futs:
            slot, msg = f.result()
            print(f"  [{slot:16s}] {msg}")
    write_credits()
    total_kb = sum(p.stat().st_size for p in OUT_DIR.rglob("*.jpg")) // 1024
    print(f"總計 {len(CATALOG)} 組 PBR 材質，共 {total_kb} KB ({total_kb / 1024:.2f} MB)")
    if args.contact_sheet:
        build_contact_sheet(Path(args.contact_sheet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
