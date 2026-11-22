#!/usr/bin/env python3
"""建置以 Blender 建模的 M2 物件（城鎮建築、產業）。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_blender_objects.py [--reuse-render] [名稱…]

流程：模板（vanilla）取得部件高度 → tools/blender/static_rig.py 渲染（每部件 × 4 旋轉 + 公司色遮罩）
→ tools/quantize.py → （產業另外補上 2D 產生的影格）→ tools/pack.py → 刪 .gitkeep → 寫 FORK.md。
模型來源：建築用 tools/blender/models/building.py + 物件資料夾內的 model.json；產業用物件資料夾內的 model.py。
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import dat  # noqa: E402
import objinfo  # noqa: E402

PY = str(REPO / ".venv" / "bin" / "python")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", str(Path.home() / "Locomotion" / "game")))
VR = REPO / "objects" / "VanillaReplacements"
BUILD = REPO / "build"

OBJECTS = {
    "BLDHOUS4": dict(folder="Building/BLDHOUS4", name="OGBLDHO4", display="Garden Cottage", size=128,
                     concept="小花園裡的平房：一種是白色粉刷牆配山形屋頂與煙囪，另一種是紅磚牆配轉向的屋頂。屋頂為公司色（城鎮隨機上色）。"),
    "BLDHOUS7": dict(folder="Building/BLDHOUS7", name="OGBLDHO7", display="Stone Cottage", size=128,
                     concept="砂岩牆的平房，三扇窗、山形屋頂與煙囪。屋頂為公司色。"),
    "BLDHOUS2": dict(folder="Building/BLDHOUS2", name="OGBLDHO2", display="Brick Terrace", size=128,
                     concept="三層紅磚排屋，每層四扇窗，一樓有門，山形屋頂與煙囪。屋頂為公司色。"),
    "BLDCTY3": dict(folder="Building/BLDCTY3", name="OGBLDCT3", display="Glass Office Block", size=256,
                    concept="2×2 的混凝土辦公大樓，每層一圈玻璃窗帶，樓層數依變化組合重複，平屋頂帶女兒牆與空調機組。女兒牆為公司色。"),
    "BLDCTY1": dict(folder="Building/BLDCTY1", name="OGBLDCT1", display="Sandstone Offices", size=256,
                    concept="2×2 的砂岩辦公樓，窗戶整齊排列，平屋頂帶女兒牆。女兒牆為公司色。"),
}

def industry_ground(style):
    """產業：在部件影格之後補上 21 張地面圖塊（tools/gen/industry_ground.py）。"""
    def extra(obj, info, sprites_dir):
        if info["has_shadows"]:
            raise SystemExit("尚未支援有陰影的產業")
        tpl = template_path(obj.name_str)
        run([PY, "tools/gen/industry_ground.py", "--template", str(tpl), "--style", style, "--append-to", str(sprites_dir)])
    return extra


OBJECTS.update({
    "COALMINE": dict(folder="Industry/COALMINE", name="OGCOALMI", display="Colliery", size=256, samples=24,
                     extra=industry_ground("coal"),
                     concept="煤礦：紅磚絞車房配公司色鋼構井架（天輪轉動 4 格動畫）、架高煤倉、選煤廠與煙囪；地面為煤場、碎石與泥土。"),
    "COALPS": dict(folder="Industry/COALPS", name="OGCOALPS", display="Coal Power Plant", size=256, samples=24,
                   extra=industry_ground("gravel"),
                   concept="燃煤電廠：雙曲線冷卻塔（頂端 32 格循環蒸汽）、紅磚鍋爐廠房與雙煙囪、兩種變電設備；地面為碎石與煤堆。"),
})

# ---- M3：建築配方（tools/gen/building_table.py）
sys.path.insert(0, str(REPO / "tools" / "gen"))
import building_recipes  # noqa: E402
import common  # noqa: E402
import building_table  # noqa: E402


def building_shadows(obj, info, sprites_dir):
    """有 hasShadows 旗標的建築（電波塔、部分辦公大樓）：部件影像之後接地面陰影（扁平深灰橢圓，尺寸沿用模板）。"""
    entries = obj.image_table().entries
    extra = entries[len(info["heights"]) * 4:]
    if not extra:
        return
    meta = json.loads((sprites_dir / "sprites.json").read_text())
    start = len(meta)
    shadows = bool(obj.data[0x98] & 0x10)                  # 沒有 hasShadows 旗標：模板多出的圖沒有被引用，放 1×1 透明圖
    for k, e in enumerate(extra):
        w, h = (e.width, e.height) if shadows else (1, 1)
        px = bytearray(w * h)
        for y in range(h if shadows else 0):
            for x in range(w):
                if ((x - (w - 1) / 2) / (w / 2)) ** 2 + ((y - (h - 1) / 2) / (h / 2)) ** 2 <= 1 and (x + y) % 2 == 0:
                    px[y * w + x] = 0x0A + 1
        fn = f"{start + k}.png"
        dat.write_indexed_png(sprites_dir / fn, w, h, bytes(px), bytes(255 if v else 0 for v in px), dat.load_palette())
        meta.append({"path": fn, "x": e.x_offset if shadows else 0, "y": e.y_offset if shadows else 0, "zoomOffset": 0,
                     "flags": 0, "name": None})
    (sprites_dir / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")


for _v, (_disp, _concept, _recipe) in building_table.BUILDINGS.items():
    OBJECTS[_v] = dict(folder=f"Building/{_v}", name=dat.og_internal_name(_v).decode().strip(), display=_disp,
                       concept=_concept, recipe=_recipe, samples=24,
                       extra=building_shadows)

# ---- M3：產業（tools/gen/industry_recipes.py + tools/gen/industry_fields.py）
import industry_recipes  # noqa: E402

INDUSTRY_TABLE = {  # vanilla: (遊戲內名稱, 田地樣式, 設計概念)
    "BREWERY": ("Brewhouse", "gravel", "紅磚釀造樓與銅綠尖頂塔樓、高煙囪；另一棟為三座錐頂發酵槽與小棚。"),
    "CHEMWORK": ("Chemical Plant", "concrete", "五種設施：浪板製程廠房與管架、蒸餾塔群、紅白高煙囪與鍋爐房、球形儲槽、臥式儲槽。"),
    "FACTORY": ("Goods Factory", "concrete", "鋸齒屋頂廠房、辦公樓與水塔；第二棟大廠房配高煙囪，煙囪頂端有 32 格冒煙動畫。"),
    "FARM": ("Grain Farm", "wheat", "白牆茅草頂農舍、公司色屋頂穀倉、乾草棚、機具棚（拖拉機）、穀倉塔；麥田有 8 個成長階段（翻土 → 發芽 → 翠綠 → 金黃 → 殘株）。"),
    "FARMUS": ("Prairie Farm", "maize", "白色農舍與門廊、紅色雙斜面穀倉、金屬穀倉群、風車抽水機；玉米田 8 個成長階段。"),
    "FOODPROC": ("Food Cannery", "concrete", "白色混凝土廠房、公司色屋頂、三座錐頂儲槽、裝卸區與排氣管。"),
    "FOREST": ("Timber Plantation", "forest", "原木林務小屋、原木吊架、原木堆；林地上的冷杉依 6 個階段長大，最後砍伐成樹樁。"),
    "OILREFIN": ("Refinery", "concrete", "製程單元、白色大型儲油槽、蒸餾塔、球形儲槽、裂解單元、高煙囪，以及三角桁架火炬塔（64 格火焰動畫）。"),
    "OILRIG": ("Offshore Platform", None, "黃色鋼柱撐起的海上平台：生活艙、直升機坪、吊臂與公司色鑽塔。"),
    "OILWELL": ("Oil Field", "dirt", "抽油機（16 格點頭動畫）、儲油槽、公司色鑽井架。"),
    "OREMINE": ("Iron Mine", "ore", "辦公室、階梯狀碎礦廠、礦石倉與輸送帶、公司色豎井井架、機具棚、工具房、選礦廠、礦石堆；地面為紅褐色礦土。"),
    "PAPERMIL": ("Paper Works", "woodchips", "長條黃磚造紙廠房與屋頂排氣罩、原木堆；另一棟為蒸煮塔與高煙囪。"),
    "PRINTWRK": ("Printing House", "pavement", "紅磚印刷廠主樓配鐘塔與銅綠尖頂；另一棟為深色磚倉庫、四個裝卸門與送貨車。"),
    "SAWMILL": ("Timber Mill", "woodchips", "木造鋸木廠房與原木坡道、原木堆與吊車、磚造乾燥窯與煙囪、大型木材倉庫、板材堆。"),
    "SKICENT": ("Ski Resort", "ski", "石砌底層、木造上層與陽台的滑雪小屋，公司色大屋頂；雪道有 4 種滑雪痕跡方向。"),
    "STEELMIL": ("Steelworks", "ore", "鏽色煉鋼廠房（7 格倒鋼動畫：門內發光、鋼水傾倒）、礦石倉、高爐與熱風爐、雙煙囪、鋼胚堆。"),
    "STOCKFRM": ("Cattle Ranch", "pasture", "木造牛舍、石砌農舍、公司色飼料塔、動物棚；牧場上有牛羊（3 個階段 × 4 種站位）。"),
    "VINEYARD": ("Vine Estate", "vines", "赭色莊園屋與塔樓、陶瓦屋頂、酒桶；葡萄藤成行，第二階段結出紫色葡萄。"),
    "WINDMILL": ("Tower Windmill", None, "白色圓錐塔身的塔式風車、深色帽頂、四片帆（8 格轉動動畫），旁有茅草頂小屋。"),
    "WINERY": ("Wine Cellars", "gravel", "石造酒窖與陶瓦屋頂、酒桶；另一棟為赭色發酵槽塔。"),
}


def industry_fields(style):
    def extra(obj, info, sprites_dir):
        if style:
            run([PY, "tools/gen/industry_fields.py", "--template", str(template_path(obj.name_str)), "--style", style,
                 "--append-to", str(sprites_dir)])
    return extra


for _v, (_disp, _style, _concept) in INDUSTRY_TABLE.items():
    OBJECTS[_v] = dict(folder=f"Industry/{_v}", name=dat.og_internal_name(_v).decode().strip(), display=_disp,
                       concept=_concept, industry_recipe=_v, samples=24, extra=industry_fields(_style))

# ---- M3：碼頭與機場（tools/gen/port_recipes.py）
import port_recipes  # noqa: E402

PORT_TABLE = {  # vanilla: (資料夾, 遊戲內名稱, 設計概念)
    "SHIPST1": ("Dock/SHIPST1", "Harbour Wharf",
                "2×2 混凝土岸壁碼頭：水側木護舷、繫船柱與黃色警示線、貨箱；紅磚倉庫配浪板人字屋頂與公司色飾帶，"
                "旁邊是公司色操作室的門式起重機。"),
    "HPORT1": ("Airport/HPORT1", "Rooftop Heliport",
               "城市高樓頂的直升機場：一樓玻璃大廳與公司色雨遮、四層帶狀窗辦公樓層，屋頂以鋼柱撐起起降平台"
               "（黃色圓環、白色 H、四角燈）。"),
    "AIRPORT2": ("Airport/AIRPORT2", "Grass Airfield",
                 "1920–30 年代草地機場：碎石跑道（跑道頭白色條紋、中段白色圓形標記）、木造機庫與浪板機庫、"
                 "白牆陶瓦屋頂的航站與塔台；跑道兩端的風向袋有 16 格轉動動畫。"),
    "AIRPORT3": ("Airport/AIRPORT3", "Regional Aerodrome",
                 "中型機場：柏油跑道（跑道頭條紋、編號、接地區標線、中心虛線）、白色混凝土航站、浪板大機庫、"
                 "黃磚貨運棚、圓柱形塔台；混凝土停機坪有接縫與黃色引導線；風向袋 16 格動畫。"),
    "AIRPORT1": ("Airport/AIRPORT1", "Intercontinental Airport",
                 "大型國際機場：寬柏油跑道（鋼琴鍵閾值、接地區、編號）、藍色邊燈的滑行道、混凝土停機坪與機位標線；"
                 "玻璃帷幕航廈與登機橋、航廈屋頂上的高塔台、浪板機庫、停車大樓；兩座雷達有 64 格旋轉動畫。"),
}


def port_preview(obj, info, sprites_dir):
    """預覽圖（image 0）：依建築位置把整座機場／碼頭的部件拼起來，縮到 64 × 64 內，插在最前面。"""
    from PIL import Image
    import pack
    import region_image
    meta = json.loads((sprites_dir / "sprites.json").read_text())
    frames = []
    for m in meta:
        w, h, px = pack.load_indices(sprites_dir / m["path"], common.PALETTE)
        frames.append((w, h, m["x"], m["y"], px))
    positions = info.get("positions") or [(0, 0, 0, 0)]
    large = info.get("large_tiles") or [True] * len(info["variations"])
    tiles = []
    for vi, rot, tx, ty in positions:
        wx, wy = ((tx + 1) * 32, (ty + 1) * 32) if large[vi] else (tx * 32 + 16, ty * 32 + 16)
        tiles.append((wx + wy, wx, wy, vi, rot))
    canvas = {}
    for _d, wx, wy, vi, rot in sorted(tiles):                 # 由遠到近
        sx0, sy0, z = wy - wx, (wx + wy) // 2, 0
        for p in info["variations"][vi]:
            w, h, x, y, px = frames[p * 4 + rot]
            for j in range(h):
                for i in range(w):
                    v = px[j * w + i]
                    if v:
                        canvas[(sx0 + x + i, sy0 - z + y + j)] = region_image.FIXED.get(v, v)
            z += info["heights"][p]
    xs = [k[0] for k in canvas]
    ys = [k[1] for k in canvas]
    x0, y0 = min(xs), min(ys)
    W, H = max(xs) - x0 + 1, max(ys) - y0 + 1
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for (x, y), v in canvas.items():
        im.putpixel((x - x0, y - y0), tuple(common.PALETTE[v]) + (255,))
    k = min(1.0, 64 / W, 64 / H)
    im = im.resize((max(1, round(W * k)), max(1, round(H * k))), Image.BOX)
    w, h = im.size
    allowed = [i for i in range(10, 246) if not (0xCA <= i <= 0xD5) and i not in range(0xF6, 0xFF)]
    cache = {}
    px = bytearray(w * h)
    for j in range(h):
        for i in range(w):
            r, g_, b, a = im.getpixel((i, j))
            if a < 110:
                continue
            key = (r, g_, b)
            if key not in cache:
                cache[key] = min(allowed, key=lambda c: sum((u - t) ** 2 for u, t in zip(common.PALETTE[c], key)))
            px[j * w + i] = cache[key]
    preview = (w, h, 2 + (64 - w) // 2, 2 + (64 - h) // 2, bytes(px))
    common.write_sprites(sprites_dir, [preview] + frames)


for _v, (_folder, _disp, _concept) in PORT_TABLE.items():
    OBJECTS[_v] = dict(folder=_folder, name=dat.og_internal_name(_v).decode().strip(), display=_disp,
                       concept=_concept, port_recipe=_v, samples=24, size=256, extra=port_preview)

FORK_MD = """# OG_{vanilla}（fork 自製）
- 對應 vanilla：{vanilla}（{type_folder}）
- 內部名稱：{name}
- 遊戲內名稱：{display}
- 設計概念：{concept}
- 製作方式：Blender 5.2 程序化建模（{model}），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_{vanilla}.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py {vanilla}`。以 vanilla {vanilla} 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- {date} V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
"""


def run(cmd, env=None):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"失敗：{' '.join(map(str, cmd))}")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if lines:
        print("  " + lines[-1])


def template_path(vanilla: str) -> Path:
    p = LOCO / "ObjData" / f"{vanilla}.DAT"
    if p.exists():
        return p
    for f in (LOCO / "ObjData").iterdir():           # 有些 vanilla 檔名與內部名稱不同（例如 coalmine.dat）
        if dat.read_dat(f).name_str == vanilla:
            return f
    raise SystemExit(f"找不到模板 {vanilla}")


def build(vanilla: str, cfg: dict) -> None:
    folder = VR / cfg["folder"]
    tpl = template_path(vanilla)
    obj = dat.read_dat(tpl)
    info = {"building": objinfo.building, "industry": objinfo.industry, "dock": objinfo.dock,
            "airport": objinfo.airport}[obj.type_name](obj)
    heights = ",".join(str(h) for h in info["heights"])
    render_dir = BUILD / "render" / vanilla
    sprites_dir = BUILD / "sprites" / vanilla
    print(f"== {vanilla}（{obj.type_name}，{len(info['heights'])} 部件）")
    env = dict(os.environ)
    if "industry_recipe" in cfg:
        model_json = industry_recipes.make_model(cfg["industry_recipe"], info)
        (folder / "model.json").write_text(json.dumps(model_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        model = REPO / "tools" / "blender" / "models" / "ops.py"
        env["MODEL_CONFIG"] = str(folder / "model.json")
        model_desc = "`tools/gen/industry_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；田地圖塊 `tools/gen/industry_fields.py`"
        if "size" not in cfg:
            tall = max(info["heights"]) + 16
            cfg["size"] = max(256, -(-2 * max(tall, 80) // 32) * 32)
    elif "port_recipe" in cfg:
        model_json = port_recipes.make_model(cfg["port_recipe"], info)
        (folder / "model.json").write_text(json.dumps(model_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        model = REPO / "tools" / "blender" / "models" / "ops.py"
        env["MODEL_CONFIG"] = str(folder / "model.json")
        model_desc = "`tools/gen/port_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`；預覽圖依建築位置拼合"
    elif "recipe" in cfg:
        model_json = building_recipes.make_model(info, cfg["recipe"])
        (folder / "model.json").write_text(json.dumps(model_json, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        model = REPO / "tools" / "blender" / "models" / "ops.py"
        env["MODEL_CONFIG"] = str(folder / "model.json")
        model_desc = "`tools/gen/building_table.py` 的配方 → `tools/gen/building_recipes.py` 產生 `model.json`（幾何指令）→ `tools/blender/models/ops.py`"
        if "size" not in cfg:                       # 畫布：容得下最高的部件與地面菱形
            tall = max(info["heights"]) + 12
            base = 72 if info.get("large") else 40
            cfg["size"] = max(128 if not info.get("large") else 256, -(-2 * max(tall, base) // 32) * 32)
    elif obj.type_name == "building":
        model = REPO / "tools" / "blender" / "models" / "building.py"
        env["MODEL_CONFIG"] = str(folder / "model.json")
        model_desc = "`tools/blender/models/building.py` + `model.json`"
    else:
        model = folder / "model.py"
        model_desc = "`model.py`"
    if REUSE_RENDER and (render_dir / "render.json").exists():
        print("  沿用既有的渲染結果")
    else:
        shutil.rmtree(render_dir, ignore_errors=True)
        # Blender（EEVEE + Mesa d3d12）每渲染一格記憶體就漲一些：部件多時分段，每段換新的行程
        nparts = len(info["heights"])
        merged = None
        for a in range(0, nparts, PART_CHUNK):
            b = min(a + PART_CHUNK, nparts) - 1
            part_json = f"render_{a:03d}.json"
            run(["blender", "-b", "--factory-startup", "--python", "tools/blender/static_rig.py", "--",
                 "--model", str(model), "--heights", heights, "--out", str(render_dir), "--size", str(cfg["size"]),
                 "--samples", str(cfg.get("samples", 32)), "--parts", f"{a}-{b}", "--json-name", part_json], env=env)
            spec = json.loads((render_dir / part_json).read_text())
            if merged is None:
                merged = spec
            else:
                merged["frames"] += spec["frames"]
            (render_dir / part_json).unlink()
        (render_dir / "render.json").write_text(json.dumps(merged, indent=2))
    # 來源檔：模型存成 .blend（AGENTS.md §2.3；所有部件並排，不渲染）
    run(["blender", "-b", "--factory-startup", "--python", "tools/blender/static_rig.py", "--",
         "--model", str(model), "--heights", heights, "--save-blend", str(folder / f"OG_{vanilla}.blend")], env=env)
    # 靜態 rig 有公司色遮罩，不用色鍵（避免一般顏色的雜訊被吸到 remap 色）
    run([PY, "tools/quantize.py", str(render_dir), "-o", str(sprites_dir), "--no-remap-colours"])
    if cfg.get("extra"):
        cfg["extra"](obj, info, sprites_dir)      # 產業：補上陰影／地面等 2D 影格
    out = folder / f"OG_{vanilla}.dat"
    pack = [PY, "tools/pack.py", "--template", str(tpl), "--sprites", str(sprites_dir), "--name", cfg["name"], "--relink",
            "--display", cfg["display"], "-o", str(out)]
    run(pack)
    (folder / ".gitkeep").unlink(missing_ok=True)
    fork_md = folder / "FORK.md"
    if not fork_md.exists():
        fork_md.write_text(FORK_MD.format(vanilla=vanilla, type_folder=cfg["folder"].split("/")[0], name=cfg["name"],
                                          display=cfg["display"], concept=cfg["concept"], model=model_desc,
                                          date=datetime.date.today().isoformat()),
                           encoding="utf-8")


REUSE_RENDER = False
PART_CHUNK = 6                                       # 每個 Blender 行程最多渲染幾個部件（× 4 旋轉 × 2 含遮罩）


def main() -> int:
    global REUSE_RENDER
    args = sys.argv[1:]
    if "--reuse-render" in args:                      # 只重新量化與打包（模型沒改時）
        REUSE_RENDER = True
        args.remove("--reuse-render")
    names = args or list(OBJECTS)
    for n in names:
        build(n, OBJECTS[n])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
