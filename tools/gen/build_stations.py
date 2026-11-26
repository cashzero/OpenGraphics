#!/usr/bin/env python3
"""M3 的火車站（trainStation，paint style 0）：幾何指令 → tools/blender/vehicle_rig.py（unit = tile）渲染
→ tools/quantize.py → 依 OpenLoco 的影像表重組 → tools/pack.py → 刪 .gitkeep → 寫 FORK.md。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_stations.py [--reuse-render] [名稱…]

影像表（OpenLoco Objects/TrainStationObject.h、Paint/PaintTrainStation.cpp）：
  0 預覽（畫在 68 × 68 框內，偏移約 (2, 2)）、1 預覽的半透明玻璃（沒有就 1×1）
  之後兩組 × 17 張（station element 的 sequenceIndex 0／1）：組 0 = 沒有雨棚的月台、組 1 = 有雨棚。
  每組：0 後側月台 NE、1 前側月台 NE、2 雨棚 NE、3 雨棚半透明 NE、4–7 同上 SE、8–16 對角（trackPieces = 0，用不到 → 1×1）。
座標：以圖塊角落為原點的 Loco 座標（x, y ∈ [0, 32]、z = 遊戲 px）。NE：軌道沿 x、後側月台在 y ≈ 0–7、前側在 y ≈ 25–32；
SE = NE 繞圖塊中心轉 90°（(x, y) → (y, 32 − x)）。後側柱子／斜撐畫在後側月台影像（在列車後面），
前側柱子／斜撐與屋頂畫在雨棚影像（OpenLoco 把雨棚畫在列車之上）。
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
BLENDER = shutil.which("blender") or str(Path.home() / ".local" / "bin" / "blender")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", Path.home() / "Locomotion" / "game"))
GLASS = 57                      # 半透明遮罩用的像素值（任意非零；與 vanilla 慣例相同）
SIZE = 160                      # 留足高度給 35px 高拱頂，不切頂


# ---------------------------------------------------------------- 幾何（Loco 座標）→ ops 指令
def _xf(x, y, se):
    return (y, 32 - x) if se else (x, y)


def box(ops, x0, x1, y0, y1, z0, z1, m, se=False):
    (ax, ay), (bx, by) = _xf(x0, y0, se), _xf(x1, y1, se)
    x0, x1 = sorted((ax, bx))
    y0, y1 = sorted((ay, by))
    ops.append({"op": "box", "c": [(y0 + y1) / 64, -(x0 + x1) / 64, z0],
                "s": [(y1 - y0) / 32, (x1 - x0) / 32, z1 - z0], "m": m})


def post(ops, x, y, z0, z1, r, m, se=False, square=True):
    if square:
        box(ops, x - r, x + r, y - r, y + r, z0, z1, m, se)
    else:
        X, Y = _xf(x, y, se)
        ops.append({"op": "cyl", "c": [Y / 32, -X / 32, z0], "r": r / 32, "h": z1 - z0, "m": m, "v": 8})


def gable(ops, x0, x1, y0, y1, z0, h, m, se=False):
    (ax, ay), (bx, by) = _xf(x0, y0, se), _xf(x1, y1, se)
    x0, x1 = sorted((ax, bx))
    y0, y1 = sorted((ay, by))
    ops.append({"op": "gable", "c": [(y0 + y1) / 64, -(x0 + x1) / 64, z0],
                "s": [(y1 - y0) / 32, (x1 - x0) / 32, h], "m": m, "a": "x" if se else "y"})


def seg(ops, a, b, r, m, se=False):
    ax, ay = _xf(a[0], a[1], se)
    bx, by = _xf(b[0], b[1], se)
    ops.append({"op": "seg", "a": [ay / 32, -ax / 32, a[2]], "b": [by / 32, -bx / 32, b[2]], "r": r / 32, "m": m})


def _arch_z(y, z0, arch_h, y_min=0.5, y_max=31.5):
    """橫跨 [y_min, y_max] 的平滑圓拱高。"""
    t = max(0.0, min(1.0, (y - y_min) / (y_max - y_min)))
    return z0 + arch_h * math.sin(math.pi * t)


# ---------------------------------------------------------------- 月台與設施
def platform(ops, front, st, se):
    y0, y1 = (24.2, 31.8) if front else (0.2, 7.8)
    edge = (24.2, 25.0) if front else (7.0, 7.8)
    ph = st["ph"]
    # 磚／石牆基座＋鋪石月台面＋低調安全石條
    box(ops, 0, 32, y0, y1, 0, ph - 0.9, st["base"], se)
    box(ops, 0, 32, y0, y1, ph - 0.9, ph, st["deck"], se)
    box(ops, 0, 32, edge[0], edge[1], ph - 0.1, ph + 0.18, st["edge"], se)
    # 背面外緣矮擋牆／欄杆（讓月台更有實體厚度）
    outer = (31.1, 31.8) if front else (0.2, 0.9)
    if st.get("low_wall"):
        box(ops, 0, 32, outer[0], outer[1], ph, ph + 2.2, st["low_wall"], se)
        box(ops, 0, 32, outer[0] - 0.1, outer[1] + 0.1, ph + 2.2, ph + 2.6, "limestone", se)


def furniture(ops, front, st, se):
    """無雨棚段（組 0）：修長典雅車站燈柱、木／鐵長椅與時刻牌（告別粗大黃棒棒糖）。"""
    ph = st["ph"]
    y = 29.2 if front else 2.8
    # 兩支細長站燈（低調小燈頭）
    for x in (6.5, 25.5):
        post(ops, x, y, ph, ph + 9.2, 0.28, st["lamp_post"], se, square=False)
        box(ops, x - 0.45, x + 0.45, y - 0.45, y + 0.45, ph + 9.0, ph + 9.8, "white", se)
        box(ops, x - 0.55, x + 0.55, y - 0.55, y + 0.55, ph + 9.8, ph + 10.2, st["lamp_post"], se)
    # 帶靠背長椅
    by = 28.6 if front else 3.4
    box(ops, 12.0, 20.0, by - 0.7, by + 0.7, ph, ph + 1.5, st["bench"], se)
    back_y0, back_y1 = (by + 0.45, by + 0.85) if front else (by - 0.85, by - 0.45)
    box(ops, 12.0, 20.0, back_y0, back_y1, ph + 1.4, ph + 3.0, st["bench"], se)
    # 站名小牌（後側月台）
    if not front:
        post(ops, 16.0, 1.5, ph, ph + 6.5, 0.22, st["lamp_post"], se)
        box(ops, 12.2, 19.8, 1.2, 1.8, ph + 4.8, ph + 6.8, st.get("sign_m", "whiteconcrete"), se)


def _side_supports(ops, y_side, st, se):
    """單側（後側或前側）結構柱與支撐桁架。"""
    ph = st["ph"]
    z = st["roof_z"]
    kind = st["roof"]
    if kind == "modern_arch":
        # TRSTAT4 標誌性高鐵／都會車站：公司色 V 型／W 型斜鋼骨支撐桁架（優雅 ~5% 公司色）
        # 水平底部連接樑與頂部承重鋼樑
        box(ops, 0, 32, y_side - 0.55, y_side + 0.55, z - 1.2, z + 0.6, "steel", se)
        xs = (0.8, 8.0, 16.0, 24.0, 31.2)
        for i in range(len(xs) - 1):
            xa, xb = xs[i], xs[i + 1]
            xm = (xa + xb) / 2
            # 粗壯 V 字公司色鋼骨（底端落於 xm，兩臂斜撐至 xa、xb 頂端）
            post(ops, xm, y_side, ph, ph + 1.8, 0.72, "darkconcrete", se)
            seg(ops, (xm, y_side, ph + 1.4), (xa, y_side, z - 0.6), 0.56, "company", se)
            seg(ops, (xm, y_side, ph + 1.4), (xb, y_side, z - 0.6), 0.56, "company", se)
        # 兩端輔助直柱確保與鄰格接縫俐落
        for xe in (0.8, 31.2):
            seg(ops, (xe, y_side, ph), (xe, y_side, z - 0.4), 0.42, "steel", se)
    elif kind == "victorian_arch":
        # TRSTAT1：古典維多利亞鑄鐵柱＋柱頭托座＋外緣飾條（0% 公司色）
        for x in (0.8, 8.0, 16.0, 24.0, 31.2):
            post(ops, x, y_side, ph, ph + 2.4, 0.72, "stone", se)
            post(ops, x, y_side, ph + 2.4, z, 0.48, "darksteel", se, square=False)
            post(ops, x, y_side, z - 1.8, z, 0.68, "steel", se)
        # 縱向鑄鐵簷樑＋裝飾格柵帶
        box(ops, 0, 32, y_side - 0.45, y_side + 0.45, z - 2.2, z + 0.4, "darksteel", se)
        box(ops, 0, 32, y_side - 0.55, y_side + 0.55, z - 0.5, z + 0.5, "steel", se)
    else:
        # TRSTAT5：經典歐式雙弧頂月台鑄鐵柱＋花紋斜撐
        cy = 3.2 if y_side < 16 else 28.8
        for x in (2.0, 11.3, 20.7, 30.0):
            post(ops, x, cy, ph, ph + 1.8, 0.62, "stone", se)
            post(ops, x, cy, ph + 1.8, z, 0.42, "darksteel", se, square=False)
            # 雙向斜撐支撐弧形雨棚
            seg(ops, (x, cy, z - 3.8), (x, cy - 2.4, z - 0.3), 0.28, "darksteel", se)
            seg(ops, (x, cy, z - 3.8), (x, cy + 2.4, z - 0.3), 0.28, "darksteel", se)


def back_pillars(ops, st, se):
    _side_supports(ops, 1.3, st, se)


def front_pillars(ops, st, se):
    _side_supports(ops, 30.7, st, se)


def shelter(ops, st, se):
    """TRSTAT5 後側月台上的古典紅磚＋石灰岩候車小屋（在列車後方）。"""
    if not st.get("shelter"):
        return
    ph = st["ph"]
    box(ops, 9.5, 22.5, 0.5, 4.6, ph, ph + 1.6, "stone", se)
    box(ops, 9.8, 22.2, 0.6, 4.5, ph + 1.6, ph + 10.0, "brick", se)
    gable(ops, 9.3, 22.7, 0.2, 4.9, ph + 10.0, 3.6, "slate", se)
    box(ops, 14.5, 17.5, 4.4, 4.7, ph, ph + 7.2, "darkwood", se)
    for x in (11.0, 18.8):
        box(ops, x, x + 2.2, 4.4, 4.7, ph + 3.2, ph + 6.8, "glass", se)
        box(ops, x - 0.2, x + 2.4, 4.4, 4.8, ph + 2.8, ph + 3.3, "limestone", se)
    box(ops, 19.6, 21.0, 1.2, 2.6, ph + 10.5, ph + 15.2, "brick", se)


def roofs(ops, st, se):
    z = st["roof_z"]
    kind = st["roof"]

    if kind == "victorian_arch":
        # TRSTAT1：宏偉維多利亞雙弦鍛鐵玻璃圓拱大棚（類似聖潘克拉斯／帕丁頓車站，全鐵石色無鮮紅條）
        arch_h = st["arch_h"]
        segs = 12
        ys = [0.8 + 30.4 * k / segs for k in range(segs + 1)]
        # 5 道雙弦桁架圓拱（外弦＋內弦＋徑向腹桿，像素級建築細節！）
        for x in (0.8, 8.0, 16.0, 24.0, 31.2):
            for k in range(segs):
                y0, y1 = ys[k], ys[k + 1]
                z0, z1 = _arch_z(y0, z, arch_h, 0.8, 31.2), _arch_z(y1, z, arch_h, 0.8, 31.2)
                seg(ops, (x, y0, z0), (x, y1, z1), 0.52, "darksteel", se)
                # 內弦拱肋（往下退縮 1.6px 做出古典鐵桁架厚度）
                seg(ops, (x, y0, z0 - 1.5), (x, y1, z1 - 1.5), 0.34, "steel", se)
                if k % 2 == 1:
                    seg(ops, (x, y0, z0), (x, y0, z0 - 1.5), 0.26, "darksteel", se)
            # 拱腳古典斜撐
            seg(ops, (x, 1.3, z - 4.8), (x, 4.5, _arch_z(4.5, z, arch_h, 0.8, 31.2) - 1.5), 0.38, "darksteel", se)
            seg(ops, (x, 30.7, z - 4.8), (x, 27.5, _arch_z(27.5, z, arch_h, 0.8, 31.2) - 1.5), 0.38, "darksteel", se)
        # 7 道縱向玻璃窗欞鋼桁條＋頂部通氣天窗脊（極具原版大車站的細密玻璃格網感）
        for k in (1, 3, 5, 6, 7, 9, 11):
            yk = ys[k]
            zk = _arch_z(yk, z, arch_h, 0.8, 31.2)
            r = 0.44 if k == 6 else 0.28
            seg(ops, (0.0, yk, zk + (0.6 if k == 6 else 0.0)),
                (32.0, yk, zk + (0.6 if k == 6 else 0.0)), r, "steel" if k != 6 else "darksteel", se)
        # 屋脊中央加高排煙天窗條
        top_z = z + arch_h
        box(ops, 0, 32, 14.4, 17.6, top_z + 0.2, top_z + 1.4, "darksteel", se)
        box(ops, 0, 32, 14.8, 17.2, top_z + 1.4, top_z + 2.0, "steel", se)
        return

    if kind == "modern_arch":
        # TRSTAT4：現代都會銀鋼圓拱玻璃車站大棚（配下方公司色 V 型鋼骨支撐）
        arch_h = st["arch_h"]
        segs = 12
        ys = [0.8 + 30.4 * k / segs for k in range(segs + 1)]
        # 5 道亮銀鋼管圓拱肋（現代空間桁架感）
        for x in (0.8, 8.0, 16.0, 24.0, 31.2):
            for k in range(segs):
                y0, y1 = ys[k], ys[k + 1]
                z0, z1 = _arch_z(y0, z, arch_h, 0.8, 31.2), _arch_z(y1, z, arch_h, 0.8, 31.2)
                seg(ops, (x, y0, z0), (x, y1, z1), 0.56, "silver", se)
                seg(ops, (x, y0, z0 - 1.3), (x, y1, z1 - 1.3), 0.32, "darksteel", se)
        # 7 道細緻縱向玻璃窗欞鋼樑＋銀色屋脊主樑
        for k in (1, 3, 5, 6, 7, 9, 11):
            yk = ys[k]
            zk = _arch_z(yk, z, arch_h, 0.8, 31.2)
            r = 0.48 if k == 6 else 0.28
            seg(ops, (0.0, yk, zk), (32.0, yk, zk), r, "silver" if k % 2 == 0 else "steel", se)
        # 兩側簷口細銀樑＋微幅公司色細飾線
        for y0, y1 in ((0.4, 1.5), (30.5, 31.6)):
            box(ops, 0, 32, y0, y1, z - 0.8, z + 0.8, "silver", se)
        return

    # TRSTAT5：雙側歐式弧形銅綠／鋅鐵拱頂月台雨棚（中央留空給鐵軌天空，氣質優雅！）
    rw = st["roof_w"]
    arch_h = st["arch_h"]
    segs = 6
    for y_start, y_end in ((0.2, rw), (32.0 - rw, 31.8)):
        ys = [y_start + (y_end - y_start) * k / segs for k in range(segs + 1)]
        # 弧形屋頂板（以分段薄板拼出平滑曲面屋頂，外層氧化銅綠／石板灰）
        for k in range(segs):
            ya, yb = ys[k], ys[k + 1]
            za = _arch_z(ya, z, arch_h, y_start, y_end)
            zb = _arch_z(yb, z, arch_h, y_start, y_end)
            zm = (za + zb) / 2
            box(ops, 0, 32, ya, yb, zm - 0.65, zm + 0.65, st["roof_m"], se)
        # 4 道深鐵弧形加強肋（x = 2, 11.3, 20.7, 30）
        for x in (2.0, 11.3, 20.7, 30.0):
            for k in range(segs):
                ya, yb = ys[k], ys[k + 1]
                za = _arch_z(ya, z, arch_h, y_start, y_end) + 0.35
                zb = _arch_z(yb, z, arch_h, y_start, y_end) + 0.35
                seg(ops, (x, ya, za), (x, yb, zb), 0.36, "darksteel", se)
        # 雙側簷口垂飾板＋微幅 1% 公司色細線（典雅復古）
        box(ops, 0, 32, y_start, y_start + 0.55, z - 1.5, z + 0.3, "darksteel", se)
        box(ops, 0, 32, y_end - 0.55, y_end, z - 1.5, z + 0.3, "darksteel", se)
        inner_y0, inner_y1 = (y_end - 0.45, y_end + 0.05) if y_start < 16 else (y_start - 0.05, y_start + 0.45)
        box(ops, 0, 32, inner_y0, inner_y1, z - 1.4, z - 0.5, "company", se)


def glass_quads(st, se):
    """半透明玻璃的平面四邊形（Loco 座標，四個角）。"""
    if st["roof"] not in ("victorian_arch", "modern_arch"):
        return []
    z = st["roof_z"]
    arch_h = st["arch_h"]
    segs = 10
    ys = [1.0 + 30.0 * k / segs for k in range(segs + 1)]
    quads = []
    for k in range(segs):
        y0, y1 = ys[k], ys[k + 1]
        z0 = _arch_z(y0, z, arch_h, 0.8, 31.2)
        z1 = _arch_z(y1, z, arch_h, 0.8, 31.2)
        q = [(0.4, y0, z0), (31.6, y0, z0), (31.6, y1, z1), (0.4, y1, z1)]
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
    "TRSTAT1": dict(
        display="Grand Vault Station",
        concept="19 世紀維多利亞鍛鐵玻璃圓拱總站：紅磚與石板月台、細緻雙弦鍛鐵圓拱桁架、"
                "七道玻璃窗欞鋼樑與屋脊通氣天窗，撐起半透明大跨距玻璃圓拱（0% 鮮紅公司色條）。",
        style=dict(ph=4.2, base="brick", deck="pavement", edge="limestone", low_wall="brick",
                   lamp_post="darksteel", bench="darkwood", sign_m="limestone",
                   roof="victorian_arch", roof_z=18.5, arch_h=15.0),
    ),
    "TRSTAT4": dict(
        display="Concourse Terminal",
        concept="現代都會銀鋼圓拱玻璃車站：深灰混凝土基座與鋪石月台、標誌性公司色 V 型斜鋼骨支撐桁架、"
                "銀色空間桁架大圓拱與半透明玻璃穹頂（約 5% 優雅公司色點綴）。",
        style=dict(ph=4.2, base="darkconcrete", deck="pavement", edge="sandstone", low_wall="darkconcrete",
                   lamp_post="steel", bench="steel", sign_m="whiteconcrete",
                   roof="modern_arch", roof_z=19.0, arch_h=15.0),
    ),
    "TRSTAT5": dict(
        display="Heritage Canopy Station",
        concept="古典歐式雙弧頂月台車站：紅磚砌石月台、鑄鐵花撐柱、雙側弧形氧化銅綠拱頂雨棚"
                "（微幅公司色簷線點綴）與後側紅磚石灰岩候車小屋。",
        style=dict(ph=4.0, base="brick", deck="pavement", edge="limestone", low_wall="stone",
                   lamp_post="darksteel", bench="wood", sign_m="limestone",
                   roof="twin_vault", roof_z=17.5, roof_w=10.6, arch_h=4.6, roof_m="copper",
                   shelter=True),
    ),
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
    box(prev, 0, 32, 8.5, 23.5, 0, 1.0, "gravel")
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
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-26 V1/V2：依真實鐵道建築全面重製（維多利亞鍛鐵圓拱、現代 V 型斜撐玻璃圓拱、古典雙弧銅綠雨棚與寫實月台設施）；`tools/lint.py` 0 錯誤，V1 與 V2 遊戲內截圖目測通過。
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
    print(f"== {vanilla}（{n_tpl} 張，渲染 {len(order)} 張）", flush=True)
    if not (reuse and (render_dir / "render.json").exists()):
        shutil.rmtree(render_dir, ignore_errors=True)
        render_dir.mkdir(parents=True)
        spec = {"size": SIZE, "unit": "tile", "states": S,
                "images": [{"state": LAYOUT[i], "yaw": 0.0, "pitch": 0.0} for i in order]}
        (render_dir / "spec.json").write_text(json.dumps(spec))
        run([BLENDER, "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--",
             "--spec", str(render_dir / "spec.json"), "--out", str(render_dir), "--samples", "24", "--mask-samples", "8",
             "--origin-offset", "0", "0"])
    folder.mkdir(parents=True, exist_ok=True)
    run([BLENDER, "-b", "--factory-startup", "--python", "tools/blender/vehicle_rig.py", "--", "--spec",
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
        elif i in GLASS_IMAGES and st["roof"] in ("victorian_arch", "modern_arch"):
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
