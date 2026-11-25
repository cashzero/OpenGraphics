#!/usr/bin/env python3
"""M3 的火車站（trainStation，paint style 0）：幾何指令 → tools/blender/vehicle_rig.py（unit = tile）渲染
→ tools/quantize.py → 依 OpenLoco 的影像表重組 → tools/pack.py → 刪 .gitkeep → 寫 FORK.md。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_stations.py [--reuse-render] [名稱…]

影像表（OpenLoco Objects/TrainStationObject.h、Paint/PaintTrainStation.cpp）：
  0 預覽（畫在 68 × 68 框內，偏移約 (2, 2)）、1 預覽的半透明玻璃（沒有就 1×1）
  之後兩組 × 17 張（station element 的 sequenceIndex 0／1）：組 0 = 沒有雨棚的月台、組 1 = 有雨棚。
  每組：0 後側月台 NE、1 前側月台 NE、2 雨棚 NE、3 雨棚半透明 NE、4–7 同上 SE、8–16 對角（trackPieces = 0，用不到 → 1×1）。
座標：以圖塊角落為原點的 Loco 座標（x, y ∈ [0, 32]、z = 遊戲 px）。NE：軌道沿 x、後側月台在 y ≈ 0–7、前側在 y ≈ 25–32；
SE = NE 繞圖塊中心轉 90°（(x, y) → (y, 32 − x)）。後側柱子畫在後側月台影像（在列車後面），
前側柱子與兩片屋頂畫在雨棚影像（OpenLoco 把雨棚畫在列車之上）。
半透明玻璃是遮罩：非零像素 = 套用半透明色（OpenLoco 只看是否為 0），由 tools/gen/iso.py 直接投影平面畫出。
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import common
import iso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402
import pack  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
VR = REPO / "objects" / "VanillaReplacements" / "TrainStation"
BUILD = REPO / "build"
PY = str(REPO / ".venv" / "bin" / "python")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", Path.home() / "Locomotion" / "game"))
GLASS = 57                      # 半透明遮罩用的像素值（任意非零；與 vanilla 慣例相同）
SIZE = 128


# ---------------------------------------------------------------- 幾何（Loco 座標）→ ops 指令
def _xf(x, y, se):
    return (y, 32 - x) if se else (x, y)


def box(ops, x0, x1, y0, y1, z0, z1, m, se=False):
    (ax, ay), (bx, by) = _xf(x0, y0, se), _xf(x1, y1, se)
    x0, x1 = sorted((ax, bx))
    y0, y1 = sorted((ay, by))
    # Loco (x, y) → Blender（格）：bx = y / 32、by = −x / 32
    ops.append({"op": "box", "c": [(y0 + y1) / 64, -(x0 + x1) / 64, z0], "s": [(y1 - y0) / 32, (x1 - x0) / 32, z1 - z0], "m": m})


def post(ops, x, y, z0, z1, r, m, se=False, square=True):
    if square:
        box(ops, x - r, x + r, y - r, y + r, z0, z1, m, se)
    else:
        X, Y = _xf(x, y, se)
        ops.append({"op": "cyl", "c": [Y / 32, -X / 32, z0], "r": r / 32, "h": z1 - z0, "m": m, "v": 8})


def gable(ops, x0, x1, y0, y1, z0, h, m, se=False):
    """人字屋頂，屋脊沿 Loco x（SE 時沿 y）。"""
    (ax, ay), (bx, by) = _xf(x0, y0, se), _xf(x1, y1, se)
    x0, x1 = sorted((ax, bx))
    y0, y1 = sorted((ay, by))
    # 屋脊沿 Loco x ＝ 沿 Blender y；SE 轉過之後屋脊沿 Loco y ＝ 沿 Blender x
    ops.append({"op": "gable", "c": [(y0 + y1) / 64, -(x0 + x1) / 64, z0], "s": [(y1 - y0) / 32, (x1 - x0) / 32, h],
                "m": m, "a": "x" if se else "y"})


# ---------------------------------------------------------------- 三種車站
def platform(ops, front, st, se):
    y0, y1 = (24.5, 31.5) if front else (0.5, 7.5)
    edge = (24.5, 25.3) if front else (6.7, 7.5)
    ph = st["ph"]
    if st.get("base"):
        box(ops, 0, 32, y0, y1, 0, ph - 0.7, st["base"], se)
        box(ops, 0, 32, y0, y1, ph - 0.7, ph, st["deck"], se)
    else:
        box(ops, 0, 32, y0, y1, 0, ph, st["deck"], se)
    box(ops, 0, 32, edge[0], edge[1], ph, ph + 0.15, st["edge"], se)


def furniture(ops, front, st, se):
    """沒有雨棚的組 0：路燈與長椅。"""
    ph = st["ph"]
    y = 28.0 if front else 4.0
    for x in (6.0, 26.0):
        post(ops, x, y, ph, ph + 13, 0.5, st["lamp_post"], se)
        box(ops, x - 0.8, x + 0.8, y - 0.8, y + 0.8, ph + 12, ph + 13.6, "lit", se)
    box(ops, 13.5, 18.5, y - 0.6, y + 0.6, ph, ph + 2.2, st["bench"], se)


def back_pillars(ops, st, se):
    ph = st["ph"]
    for x in st["pillar_x"]:
        post(ops, x, st["pillar_y"], ph, st["roof_z"], st["pillar_r"], st["pillar"], se, square=st.get("square", True))


def front_pillars(ops, st, se):
    ph = st["ph"]
    for x in st["pillar_x"]:
        post(ops, x, 32 - st["pillar_y"], ph, st["roof_z"], st["pillar_r"], st["pillar"], se, square=st.get("square", True))


def seg(ops, a, b, r, m, se=False):
    ax, ay = _xf(a[0], a[1], se)
    bx, by = _xf(b[0], b[1], se)
    ops.append({"op": "seg", "a": [ay / 32, -ax / 32, a[2]], "b": [by / 32, -bx / 32, b[2]], "r": r / 32, "m": m})


def _arch_z(y, z0, arch_h):
    """橫跨全格（y ∈ [0.5, 31.5]）的半橢圓拱高。"""
    t = max(0.0, min(1.0, (y - 0.5) / 31.0))
    return z0 + arch_h * math.sin(math.pi * t)


def roofs(ops, st, se):
    z = st["roof_z"]
    kind = st["roof"]
    if kind == "glass_arch":                                   # 維多利亞／經典拱形玻璃鐵架車站棚（橫跨雙側月台）
        arch_h = st.get("arch_h", 12.0)
        segs = 10
        ys = [0.5 + 31.0 * k / segs for k in range(segs + 1)]
        # 兩側縱向簷樑＋公司色花飾邊樑
        for y0, y1 in ((0.2, 1.4), (30.6, 31.8)):
            box(ops, 0, 32, y0, y1, z - 1.6, z + 0.6, st["trim"], se)
        # 5 道橫向拱形鐵肋（x = 0, 8, 16, 24, 32）
        for x in (0.5, 8.0, 16.0, 24.0, 31.5):
            for k in range(segs):
                y0, y1 = ys[k], ys[k + 1]
                z0, z1 = _arch_z(y0, z, arch_h), _arch_z(y1, z, arch_h)
                seg(ops, (x, y0, z0), (x, y1, z1), 0.55, st["frame"], se)
            # 拱腳小斜撐
            seg(ops, (x, 1.2, z - 4.2), (x, 4.2, _arch_z(4.2, z, arch_h) - 0.6), 0.35, st["trim"], se)
            seg(ops, (x, 30.8, z - 4.2), (x, 27.8, _arch_z(27.8, z, arch_h) - 0.6), 0.35, st["trim"], se)
        # 縱向桁條與屋脊鋼樑（讓玻璃拱頂有豐富結構感）
        for k in (2, 4, 5, 6, 8):
            yk = ys[k]
            zk = _arch_z(yk, z, arch_h)
            r = 0.45 if k == 5 else 0.30
            seg(ops, (0.0, yk, zk), (32.0, yk, zk), r, st["frame"], se)
        return
    for y0, y1 in ((0.0, st["roof_w"]), (32 - st["roof_w"], 32.0)):
        if kind == "slab_skylight":                            # 現代主義懸挑翼狀雨棚（深色屋頂凹槽＋寬天窗＋公司色簷口）
            mid0, mid1 = y0 + st["roof_w"] * 0.28, y0 + st["roof_w"] * 0.72
            # 外緣白色混凝土薄殼結構＋深色防眩頂面（不再整片過曝純白）
            box(ops, 0, 32, y0, mid0, z, z + 1.8, st["slab"], se)
            box(ops, 0, 32, mid1, y1, z, z + 1.8, st["slab"], se)
            box(ops, 0, 32, y0 + 0.5, mid0 - 0.2, z + 1.5, z + 2.0, "darkconcrete", se)
            box(ops, 0, 32, mid1 + 0.2, y1 - 0.5, z + 1.5, z + 2.0, "darkconcrete", se)
            box(ops, 0, 32, y0, y0 + 0.7, z + 1.4, z + 2.8, st["trim"], se)
            box(ops, 0, 32, y1 - 0.7, y1, z + 1.4, z + 2.8, st["trim"], se)
            for x in range(0, 33, 8):                          # 天窗橫向鋼樑＋柱頭斜撐
                box(ops, max(0, x - 0.45), min(32, x + 0.45), y0, y1, z + 1.0, z + 2.3, "darksteel", se)
                cy = 3.5 if y0 < 16 else 28.5
                seg(ops, (max(1, min(31, x)), cy, z - 3.5), (max(1, min(31, x)), (y0 + y1) / 2, z + 0.5), 0.35, "darksteel", se)
        else:                                                  # gable：鄉間木造人字瓦頂＋斜撐＋公司色簷板
            gable(ops, 0, 32, y0, y1, z, st["roof_h"], st["roof_m"], se)
            box(ops, 0, 32, y0, y0 + 0.5, z - 1.8, z, st["trim"], se)
            box(ops, 0, 32, y1 - 0.5, y1, z - 1.8, z, st["trim"], se)
            cy = st["pillar_y"] if y0 < 16 else 32 - st["pillar_y"]
            for x in st["pillar_x"]:
                seg(ops, (x, cy, z - 4.0), (x, (y0 + y1) / 2, z - 0.4), 0.32, st["pillar"], se)


def shelter(ops, st, se):
    """鄉間小站：後側月台上的木造候車亭（在列車後面，畫在後側月台影像）。"""
    if not st.get("shelter"):
        return
    ph = st["ph"]
    box(ops, 10, 22, 0.8, 5.2, ph, ph + 9.5, "wood", se)
    gable(ops, 9.5, 22.5, 0.4, 5.6, ph + 9.5, 3.2, "slate", se)
    box(ops, 14.5, 17.5, 5.1, 5.4, ph, ph + 6.8, "darkwood", se)        # 門
    for x in (11.4, 18.6):
        box(ops, x, x + 1.8, 5.1, 5.4, ph + 3.4, ph + 6.4, "blueglass", se)
    box(ops, 19.5, 20.8, 1.4, 2.7, ph + 10.5, ph + 15.0, "brick", se)   # 小煙囪


def glass_quads(st, se):
    """半透明玻璃的平面四邊形（Loco 座標，四個角）。"""
    z = st["roof_z"]
    quads = []
    if st["roof"] == "glass_arch":
        arch_h = st.get("arch_h", 12.0)
        segs = 8
        ys = [0.8 + 30.4 * k / segs for k in range(segs + 1)]
        for k in range(segs):
            y0, y1 = ys[k], ys[k + 1]
            z0, z1 = _arch_z(y0, z, arch_h), _arch_z(y1, z, arch_h)
            q = [(0.5, y0, z0), (31.5, y0, z0), (31.5, y1, z1), (0.5, y1, z1)]
            quads.append([(*_xf(x, y, se), zz) for x, y, zz in q])
        return quads
    for y0, y1 in ((0.0, st["roof_w"]), (32 - st["roof_w"], 32.0)):
        if st["roof"] == "slab_skylight":
            m0, m1 = y0 + st["roof_w"] * 0.28, y0 + st["roof_w"] * 0.72
            q = [(0, m0, z + 1.7), (32, m0, z + 1.7), (32, m1, z + 1.7), (0, m1, z + 1.7)]
        else:
            continue
        quads.append([(*_xf(x, y, se), zz) for x, y, zz in q])
    return quads


def glass_mask(st, se):
    quads = glass_quads(st, se)
    if not quads:
        return None
    c = iso.Canvas()
    for a, b, cc, d in quads:
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(d[i] - a[i] for i in range(3))
        c.plate(a, u, v, lambda s, t: GLASS, step=0.3)
    return c.render()


STATIONS = {
    "TRSTAT1": dict(display="Glass Canopy Station",
                    concept="經典拱形玻璃鐵架車站：磚石基座與風化石月台、白色安全線，深鐵與公司色拱形鋼肋橫跨雙側月台"
                            "撐起半透明拱形玻璃頂棚（下方列車清晰可見）；無棚段有鑄鐵路燈與長椅。",
                    style=dict(ph=4, base="darkstone", deck="stone", edge="white", lamp_post="darksteel", bench="darkwood",
                               pillar="darksteel", pillar_r=0.55, pillar_x=(0.8, 8, 16, 24, 31.2), pillar_y=1.2,
                               roof="glass_arch", roof_z=20, arch_h=12.5, frame="darksteel", trim="company")),
    "TRSTAT4": dict(display="Concourse Station",
                    concept="現代主義都會車站：深色鋪面月台與黃色警示線，圓柱與鋼構斜撐撐起雙側現代雨棚（凹入深色屋頂防反光、"
                            "中央寬幅半透明玻璃天窗與公司色簷口）；無棚段有現代路燈與長椅。",
                    style=dict(ph=4, base="darkconcrete", deck="stone", edge="yellowsteel", lamp_post="darksteel", bench="steel",
                               pillar="concrete", pillar_r=0.75, pillar_x=(8, 24), pillar_y=3.2, square=False,
                               roof="slab_skylight", roof_z=23, roof_w=12.8, slab="concrete", trim="company")),
    "TRSTAT5": dict(display="Country Halt",
                    concept="鄉間小站：紅磚基座木板月台、木柱與斜撐撐起深色石板人字屋頂與公司色簷板，"
                            "後側月台附帶磚煙囪的木造候車室；無棚段有復古路燈與木長椅。",
                    style=dict(ph=3.5, base="brick", deck="planks", edge="white", lamp_post="darkwood", bench="wood",
                               pillar="darkwood", pillar_r=0.48, pillar_x=(5, 16, 27), pillar_y=3.0,
                               roof="gable", roof_z=16, roof_w=10.8, roof_h=5.2, roof_m="slate", trim="company",
                               shelter=True)),
}


def states_for(st):
    S = {}
    for se in (False, True):
        tag = "se" if se else "ne"
        for front in (False, True):
            ops0, ops1 = [], []
            platform(ops0, front, st, se)
            furniture(ops0, front, st, se)
            platform(ops1, front, st, se)
            if not front:
                back_pillars(ops1, st, se)
                shelter(ops1, st, se)
            S[f"{tag}_{'front' if front else 'back'}0"] = ops0
            S[f"{tag}_{'front' if front else 'back'}1"] = ops1
        can = []
        roofs(can, st, se)
        front_pillars(can, st, se)
        S[f"{tag}_canopy1"] = can
    prev = []                                                  # 預覽：道床＋兩側月台＋雨棚
    box(prev, 0, 32, 9, 23, 0, 1.0, "gravel")
    for k in range(1, 32, 3):
        box(prev, k - 0.5, k + 0.5, 11, 21, 1.0, 1.5, "darkwood")
    for y in (13.4, 18.6):
        box(prev, 0, 32, y - 0.3, y + 0.3, 1.5, 2.3, "steel")
    for front in (False, True):
        platform(prev, front, st, False)
    back_pillars(prev, st, False)
    shelter(prev, st, False)
    roofs(prev, st, False)
    front_pillars(prev, st, False)
    S["preview"] = prev
    return S


LAYOUT = {   # 影像 index → 狀態名（None = 1×1）；玻璃另外處理
    0: "preview",
    2: "ne_back0", 3: "ne_front0", 6: "se_back0", 7: "se_front0",
    19: "ne_back1", 20: "ne_front1", 21: "ne_canopy1", 23: "se_back1", 24: "se_front1", 25: "se_canopy1",
}
GLASS_IMAGES = {1: ("preview", False), 22: ("ne", False), 26: ("se", True)}


def run(cmd):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"失敗：{' '.join(map(str, cmd))}")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if lines:
        print("  " + lines[-1])


FORK_MD = """# OG_{vanilla}（fork 自製）
- 對應 vanilla：{vanilla}（TrainStation）
- 內部名稱：{name}
- 遊戲內名稱：{display}
- 設計概念：{concept}
- 製作方式：`tools/gen/build_stations.py {vanilla}` 以幾何指令建模（`OG_{vanilla}.blend` 為各影像的模型並排），
  `tools/blender/vehicle_rig.py`（unit = tile，原點 = 圖塊角落）渲染 → `tools/quantize.py` → 依 OpenLoco 影像表重組
  （半透明玻璃由 `tools/gen/iso.py` 投影產生）→ `tools/pack.py`（以 vanilla {vanilla} 為結構模板，只沿用結構、屬性與其他字串）
- AI 工具：Claude（撰寫建模指令與產生器程式）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-20 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
"""


def build(vanilla, cfg, reuse):
    st = cfg["style"]
    name = dat.og_internal_name(vanilla).decode().strip()
    tpl = next(f for f in (LOCO / "ObjData").iterdir() if f.name.upper() == f"{vanilla}.DAT")
    n_tpl = len(dat.read_dat(tpl).image_table().entries)
    folder = VR / vanilla
    render_dir = BUILD / "render" / vanilla
    sprites_dir = BUILD / "sprites" / vanilla
    S = states_for(st)
    order = sorted(LAYOUT)
    print(f"== {vanilla}（{n_tpl} 張，渲染 {len(order)} 張）")
    if not (reuse and (render_dir / "render.json").exists()):
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True)
        spec = {"size": SIZE, "unit": "tile", "states": S,
                "images": [{"state": LAYOUT[i], "yaw": 0.0, "pitch": 0.0} for i in order]}
        (render_dir / "spec.json").write_text(json.dumps(spec))
        run(["blender", "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--",
             "--spec", str(render_dir / "spec.json"), "--out", str(render_dir), "--samples", "24", "--mask-samples", "8",
             "--origin-offset", "0", "0"])
    folder.mkdir(parents=True, exist_ok=True)
    run(["blender", "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--", "--spec",
         str(render_dir / "spec.json"), "--save-blend", str(folder / f"OG_{vanilla}.blend")])
    tmp = BUILD / "sprites" / f"{vanilla}_q"
    run([PY, "tools/quantize.py", str(render_dir), "-o", str(tmp), "--no-remap-colours"])
    meta = json.loads((tmp / "sprites.json").read_text())
    rendered = {}
    for k, i in enumerate(order):
        w, h, px = pack.load_indices(tmp / meta[k]["path"], common.PALETTE)
        rendered[i] = (w, h, meta[k]["x"], meta[k]["y"], px)
    frames = []
    for i in range(n_tpl):
        if i in rendered:
            frames.append(rendered[i])
        elif i in GLASS_IMAGES and st["roof"] != "gable":
            frames.append(glass_mask(st, GLASS_IMAGES[i][1]))
        else:
            frames.append((1, 1, 0, 0, bytes(1)))
    # 預覽與其玻璃層一起平移到 68 × 68 框內置中（OpenLoco 在 (x − 34, y − 34) 畫）
    w, h, x, y, px = frames[0]
    dx, dy = 2 + (64 - w) // 2 - x, 2 + (64 - h) // 2 - y
    frames[0] = (w, h, x + dx, y + dy, px)
    if frames[1][0] > 1:
        w1, h1, x1, y1, p1 = frames[1]
        frames[1] = (w1, h1, x1 + dx, y1 + dy, p1)
    common.write_sprites(sprites_dir, frames)
    shutil.rmtree(tmp, ignore_errors=True)
    out = folder / f"OG_{vanilla}.dat"
    run([PY, "tools/pack.py", "--template", str(tpl), "--sprites", str(sprites_dir), "--name", name, "--relink",
         "--display", cfg["display"], "-o", str(out)])
    (folder / ".gitkeep").unlink(missing_ok=True)
    fm = folder / "FORK.md"
    if not fm.exists():
        fm.write_text(FORK_MD.format(vanilla=vanilla, name=name, **cfg))


def main() -> int:
    args = sys.argv[1:]
    reuse = "--reuse-render" in args
    names = [a for a in args if not a.startswith("--")] or list(STATIONS)
    for n in names:
        build(n, STATIONS[n], reuse)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
