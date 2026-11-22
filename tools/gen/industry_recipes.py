"""產業模型（M3）：每種產業一個函式，回傳每個部件的幾何指令（tools/blender/models/ops.py）。
部件編號、高度、哪些部件是動畫格，都與該產業模板的結構一致（tools/objinfo.py industry()）。

座標：平面以「格」為單位（佔地中心為原點），高度以遊戲 px 為單位；1×1 佔地為 ±0.5、2×2 為 ±1。
動畫（OpenLoco Paint/PaintIndustry.cpp）：
  - 部件的 animation numFrames > 0：畫的是 part + (tick & (numFrames-1))，也就是連續 numFrames 個部件為動畫格。
  - numFrames = 0 且產業有 animation sequence：畫 part + sequence[tick]（煉鋼廠）。
"""
from __future__ import annotations

import math
import random

from building_recipes import Ops, SIDES, band, face_box, parapet, ribbon, roof, windows

TZ = 39.5   # 1 格的水平長度換算成高度 px（kit：TILE / (1 / PX_PER_Z)）；傾斜或旋轉的構件用來換算


# ---------------------------------------------------------------- 共用構件

def ground(o, tiles, m):
    o.ground(tiles, m)


def shed(o, c, sx, sy, h, wall="corrugated", roofm="company", kind="gable", along="x", win=0, rows=1, door=True):
    x, y = c
    o.box((x, y, 0), (sx, sy, h), wall)
    if win:
        windows(o, x, y, sx, sy, h * 0.15, h * 0.9, rows, win, wf=0.45)
    if door:
        face_box(o, x, y, sx, sy, "-y", 0.2, min(0.3, sx * 0.3), 0, h * 0.7, "darksteel")
    sub = Ops()
    if kind == "saw":                                         # 鋸齒屋頂
        n = max(2, round(sx / 0.3))
        for k in range(n):
            xx = x - sx / 2 + (k + 0.5) * sx / n
            sub.hip((xx, y, 0), (sx / n, sy, h * 0.3), roofm, k=0.95)
            face_box(sub, xx, y, sx / n, sy, "-x", 0, sy * 0.9, h * 0.02, h * 0.22, "glass")
    elif kind == "flat":
        sub.box((x, y, 0), (sx, sy, 1.0), roofm)
        parapet(sub, x, y, sx, sy, 0, 2.0, wall)
    else:
        roof(sub, "g" + along, x, y, sx, sy, max(6, min(h * 0.45, 14)), roofm, over=0.02)
    for op in sub:
        op = dict(op)
        if "c" in op:
            op["c"] = [op["c"][0], op["c"][1], op["c"][2] + h]
        o.append(op)


def tank(o, c, r, h, m="silver", top="dome", z=0):
    x, y = c
    o.cyl((x, y, z), r, h, m, v=20)
    if top == "dome":
        o.lathe((x, y, z + h), [(r, 0), (r * 0.8, r * TZ * 0.6), (0.0, r * TZ * 0.9)], m, seg=20)
    elif top == "cone":
        o.cyl((x, y, z + h), r, r * TZ * 0.8, m, v=20, rt=0.02)
    elif top == "flat":
        o.cyl((x, y, z + h), r * 1.02, 1.0, "darksteel", v=20)


def sphere_tank(o, c, r, z):
    x, y = c
    for a in range(4):                                         # 支柱
        ang = math.pi / 4 + a * math.pi / 2
        o.seg((x + r * 0.8 * math.cos(ang), y + r * 0.8 * math.sin(ang), 0),
              (x + r * 0.8 * math.cos(ang), y + r * 0.8 * math.sin(ang), z), "darksteel", r=0.015)
    prof = [(0.0, -r * TZ), (r * 0.7, -r * TZ * 0.7), (r, 0), (r * 0.7, r * TZ * 0.7), (0.0, r * TZ)]
    o.lathe((x, y, z + r * TZ), prof, "white", seg=20)


def chimney(o, c, r, h, m="brick", top="darkstone", z=0, bands=None):
    x, y = c
    o.cyl((x, y, z), r, h, m, v=14, rt=r * 0.75)
    o.cyl((x, y, z + h - 2), r * 0.82, 2, top, v=14)
    if bands:
        for k in range(3):
            o.cyl((x, y, z + h * (0.55 + 0.15 * k)), r * (0.9 - 0.08 * k), h * 0.06, bands, v=14)


def pipe(o, a, b, m="steel", r=0.018):
    o.seg(a, b, m, r=r)


def column(o, c, r, h, m="silver", platforms=3):
    x, y = c
    o.cyl((x, y, 0), r, h, m, v=14)
    o.lathe((x, y, h), [(r, 0), (r * 0.5, r * 20), (0.0, r * 26)], m, seg=14)
    for k in range(1, platforms + 1):
        o.cyl((x, y, h * k / (platforms + 1)), r * 1.5, 0.6, "darksteel", v=14)


def logs(o, c, n, length, r, z=0, along="x", m="logs"):
    x, y = c
    for k in range(n):
        off = (k - (n - 1) / 2) * r * 2.1
        zz = z + r * TZ
        if along == "x":
            o.seg((x - length / 2, y + off, zz), (x + length / 2, y + off, zz), m, r=r)
        else:
            o.seg((x + off, y - length / 2, zz), (x + off, y + length / 2, zz), m, r=r)


def log_pile(o, c, rows, n, length, r, along="x"):
    for row in range(rows):
        logs(o, (c[0], c[1]), n - row, length, r, z=row * r * 80, along=along)


def smoke_puffs(o, c, z0, frame, frames, n=5, rise=60, size=0.12, m="smoke"):
    """煙囪頂的煙：n 團逐格上升、變大、飄向 +x；frame/frames 為循環位置。"""
    x, y = c
    for k in range(n):
        t = ((k + frame / frames) / n) % 1.0
        r = size * (0.5 + t * 1.2)
        o.lathe((x + t * 0.35, y + t * 0.1, z0 + t * rise), [(0.0, 0), (r * 0.8, r * 18), (r, r * 40), (r * 0.6, r * 62), (0.0, r * 70)],
                m, seg=10)


def fence(o, cx, cy, sx, sy, h=2.0, m="wood"):
    for side in SIDES:
        L = sx if side in ("-y", "+y") else sy
        face_box(o, cx, cy, sx, sy, side, 0, L, h * 0.6, h * 0.25, m, out=0.012)
        n = max(2, int(L / 0.12))
        for k in range(n + 1):
            face_box(o, cx, cy, sx, sy, side, k / n - 0.5, 0.012, 0, h, m, out=0.012)


def house(o, c, sx, sy, h, wall="plaster", roofm="company", along="x", win=3):
    x, y = c
    o.box((x, y, 0), (sx, sy, h), wall)
    windows(o, x, y, sx, sy, h * 0.25, h * 0.9, max(1, round(h / 12)), win, sills="white")
    face_box(o, x, y, sx, sy, "-y", 0, 0.08, 0, min(h * 0.6, 7), "darkwood")
    sub = Ops()
    roof(sub, "g" + along, x, y, sx, sy, max(8, sx * 14), roofm, over=0.03, chim=[(0.3, 0.0)])
    for op in sub:
        op = dict(op)
        if "c" in op:
            op["c"] = [op["c"][0], op["c"][1], op["c"][2] + h]
        o.append(op)


# ---------------------------------------------------------------- 各產業

def brewery(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "gravel")
    elif p == 2:
        ground(o, 1, "pavement")
    elif p == 1:                                              # 釀造樓：紅磚主樓 + 塔樓 + 高煙囪
        o.box((-0.15, 0.1, 0), (1.3, 1.0, 50), "brick")
        windows(o, -0.15, 0.1, 1.3, 1.0, 5, 48, 4, 6, sills="white")
        o2 = Ops()
        roof(o2, "gx", -0.15, 0.1, 1.3, 1.0, 16, "slate", over=0.03)
        for op in o2:
            op = dict(op)
            op["c"] = [op["c"][0], op["c"][1], op["c"][2] + 50]
            o.append(op)
        o.box((0.35, -0.35, 0), (0.42, 0.42, 92), "brick")
        windows(o, 0.35, -0.35, 0.42, 0.42, 55, 90, 2, 2, sills="white")
        o.hip((0.35, -0.35, 92), (0.48, 0.48, 18), "copper", k=0.0)
        o.box((0.35, -0.35, 92), (0.46, 0.46, 1.5), "white")
        chimney(o, (-0.7, 0.6), 0.09, h, bands="darkbrick")
        for k in range(4):                                    # 木桶
            o.cyl((0.75 + (k % 2) * 0.1, -0.85 + (k // 2) * 0.12, 0), 0.04, 4, "wood", v=10)
    elif p == 3:                                              # 發酵槽
        o.box((0, 0, 0), (0.9, 0.9, 1.0), "concrete")
        for (x, y) in ((-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2)):
            tank(o, (x, y), 0.15, h * 0.62, "silver", top="cone", z=1)
            o.box((x, y, h * 0.2), (0.32, 0.03, 0.8), "company")
        shed(o, (0.25, 0.25), 0.36, 0.3, 12, wall="brick", roofm="slate")
    return o


def chemworks(p, h, info):
    o = Ops()
    if p in (0, 2, 4):
        ground(o, 2, "concrete")
    elif p in (6, 8):
        ground(o, 1, "concrete")
    elif p == 1:                                              # 製程廠房 + 管架
        shed(o, (-0.3, 0.2), 1.0, 0.9, h * 0.45, wall="corrugated", roofm="company", kind="flat", win=5)
        for k in range(3):
            chimney(o, (0.55, -0.6 + k * 0.3), 0.05, h, m="silver", top="darksteel")
        for y in (-0.6, -0.3, 0.0):
            pipe(o, (-0.8, y - 0.2, 12), (0.6, y - 0.2, 12), "company", r=0.02)
        for x in (-0.6, -0.1, 0.4):
            o.seg((x, -0.8, 0), (x, -0.8, 12), "darksteel", r=0.012)
    elif p == 3:                                              # 蒸餾塔
        for (x, y, hh) in ((-0.4, -0.3, h), (0.0, -0.4, h * 0.8), (0.35, -0.2, h * 0.9), (-0.2, 0.3, h * 0.6)):
            column(o, (x, y), 0.1, hh * 0.85, "silver")
        for (a, b) in (((-0.4, -0.3), (0.0, -0.4)), ((0.0, -0.4), (0.35, -0.2)), ((0.35, -0.2), (-0.2, 0.3))):
            pipe(o, (a[0], a[1], h * 0.5), (b[0], b[1], h * 0.45), "company")
        shed(o, (0.5, 0.55), 0.6, 0.5, 14, wall="concrete", roofm="corrugated", kind="flat", win=3)
    elif p == 5:                                              # 高煙囪 + 鍋爐房
        shed(o, (-0.3, 0.3), 0.9, 0.8, 26, wall="brick", roofm="slate", win=4)
        chimney(o, (0.4, -0.4), 0.14, h, m="concrete", top="red", bands="red")
    elif p == 7:                                              # 球形儲槽
        o.box((0, 0, 0), (0.85, 0.85, 0.6), "concrete")
        sphere_tank(o, (-0.15, -0.15), 0.2, 12)
        sphere_tank(o, (0.22, 0.22), 0.15, 10)
    elif p == 9:                                              # 臥式儲槽
        o.box((0, 0, 0), (0.85, 0.85, 0.6), "concrete")
        for k in range(3):
            y = -0.25 + k * 0.25
            for x in (-0.3, 0.3):
                o.box((x, y, 0), (0.05, 0.12, 4), "concrete")
            o.seg((-0.38, y, 9), (0.38, y, 9), "white", r=0.1)
    return o


def factory(p, h, info, frame=0):
    o = Ops()
    if p in (0, 2):
        ground(o, 2, "concrete")
    elif p == 1:                                              # 鋸齒屋頂廠房 + 辦公樓 + 水塔
        shed(o, (-0.15, 0.15), 1.4, 1.2, 28, wall="brick", roofm="slate", kind="saw", win=7)
        o.box((0.55, -0.7, 0), (0.7, 0.4, 24), "yellowbrick")
        windows(o, 0.55, -0.7, 0.7, 0.4, 2, 23, 2, 5, sills="white")
        o.box((0.55, -0.7, 24), (0.72, 0.42, 1.5), "white")
        for a in range(4):
            ang = math.pi / 4 + a * math.pi / 2
            o.seg((-0.7 + 0.1 * math.cos(ang), -0.7 + 0.1 * math.sin(ang), 0), (-0.7 + 0.08 * math.cos(ang), -0.7 + 0.08 * math.sin(ang), h * 0.72), "darksteel", r=0.01)
        tank(o, (-0.7, -0.7), 0.13, h * 0.2, "company", top="cone", z=h * 0.72)
    elif p == 3:                                              # 大廠房 + 煙囪下段
        shed(o, (-0.2, 0.15), 1.4, 1.3, 44, wall="darkbrick", roofm="company", kind="saw", win=8, rows=2)
        chimney(o, (0.65, -0.6), 0.15, h, bands=None)
    else:                                                     # 煙囪上段 + 32 格煙（疊在 part 3 上方）
        k = p - 4
        o.cyl((0.65, -0.6, 0), 0.12, 55, "brick", v=14, rt=0.1)
        o.cyl((0.65, -0.6, 53), 0.11, 2, "darkstone", v=14)
        smoke_puffs(o, (0.65, -0.6), 57, k, 32, n=5, rise=36, size=0.11)
    return o


def farm(p, h, info, us=False):
    o = Ops()
    grounds = {0: (2, "dirt"), 2: (2, "dirt"), 4: (2, "gravel"), 7: (1, "dirt")}
    if p in grounds:
        ground(o, *grounds[p])
        if p == 0:
            fence(o, 0, 0, 1.9, 1.9, h=2.5)
        return o
    if not us:
        if p == 1:                                            # 農舍
            house(o, (-0.3, 0.2), 0.8, 0.55, 14, wall="whitewash", roofm="thatch")
            o.box((0.55, -0.4, 0), (0.4, 0.3, 8), "stone")
            o.gable((0.55, -0.4, 8), (0.44, 0.34, 6), "slate", "x")
        elif p == 3:                                          # 穀倉
            o.box((0, 0, 0), (1.3, 0.8, 12), "wood")
            o.gable((0, 0, 12), (1.36, 0.86, 12), "company", "x")
            face_box(o, 0, 0, 1.3, 0.8, "-y", 0, 0.35, 0, 10, "darkwood")
        elif p == 5:                                          # 乾草棚
            for x in (-0.5, 0.0, 0.5):
                for y in (-0.35, 0.35):
                    o.box((x, y, 0), (0.05, 0.05, 18), "wood")
            o.gable((0, 0, 18), (1.2, 0.85, 10), "corrugated", "x")
            for k in range(6):
                o.box((-0.4 + (k % 3) * 0.4, -0.15 + (k // 3) * 0.3, 0), (0.3, 0.22, 6 + (k % 2) * 4), "hay")
        elif p == 6:                                          # 機具棚 + 拖拉機
            shed(o, (0.1, 0.2), 1.1, 0.7, 16, wall="wood", roofm="corrugated", door=False)
            o.box((-0.4, -0.5, 1.5), (0.18, 0.12, 3), "red")
            o.box((-0.33, -0.5, 4.5), (0.08, 0.1, 3), "red")
            for dx in (-0.47, -0.33):
                o.seg((dx, -0.57, 2), (dx, -0.43, 2), "black", r=0.04)
        elif p == 8:                                          # 穀倉塔（1×1）
            tank(o, (-0.12, 0.05), 0.17, h * 0.75, "concrete", top="dome")
            tank(o, (0.2, -0.18), 0.12, h * 0.6, "concrete", top="dome")
            o.box((0.15, 0.25, 0), (0.25, 0.2, 10), "wood")
    else:
        if p == 1:                                            # 白色農舍 + 門廊
            house(o, (-0.2, 0.2), 0.9, 0.6, 16, wall="white", roofm="slate", win=4)
            o.box((-0.2, -0.16, 0), (0.9, 0.14, 0.8), "wood")
            o.box((-0.2, -0.16, 8), (0.92, 0.16, 0.8), "slate")
            for x in (-0.6, -0.2, 0.2):
                o.box((x, -0.22, 0), (0.025, 0.025, 8), "white")
        elif p == 3:                                          # 紅色穀倉（雙斜面）
            o.box((0, 0, 0), (0.7, 0.55, 14), "red")
            o.hip((0, 0, 14), (0.74, 0.6, 9), "slate", k=1.0)
            o.gable((0, 0, 20), (0.74, 0.3, 8), "slate", "x")
            face_box(o, 0, 0, 0.7, 0.55, "-y", 0, 0.2, 0, 10, "white")
        elif p in (5, 6):                                     # 金屬穀倉群
            n = 3 if p == 5 else 2
            for k in range(n):
                ang = k * 2 * math.pi / n
                tank(o, (0.18 * math.cos(ang), 0.18 * math.sin(ang)), 0.14 if p == 5 else 0.18, h * 0.65, "silver", top="cone")
        elif p == 8:                                          # 風車抽水機
            for a in range(4):
                ang = math.pi / 4 + a * math.pi / 2
                o.seg((0.12 * math.cos(ang), 0.12 * math.sin(ang), 0), (0.02 * math.cos(ang), 0.02 * math.sin(ang), h * 0.75), "darksteel", r=0.008)
            for k in range(12):
                a = 2 * math.pi * k / 12
                o.seg((0, -0.03, h * 0.82), (0.16 * math.cos(a), -0.03, h * 0.82 + 0.16 * math.sin(a) * TZ), "silver", r=0.012)
            o.cyl((0.25, 0.2, 0), 0.15, 6, "wood", v=16)
    return o


def foodproc(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "concrete")
        return o
    shed(o, (-0.2, 0.15), 1.3, 1.1, 28, wall="whiteconcrete", roofm="company", kind="flat", win=6, rows=2)
    for k in range(3):
        tank(o, (0.65, -0.6 + k * 0.3), 0.12, h * 0.75, "silver", top="cone")
    o.box((-0.2, -0.65, 0), (0.6, 0.25, 8), "white")
    face_box(o, -0.2, -0.65, 0.6, 0.25, "-y", 0, 0.5, 0, 6, "darksteel")
    chimney(o, (-0.7, 0.65), 0.06, h * 0.7, m="silver", top="darksteel")
    return o


def forest(p, h, info):
    o = Ops()
    if p in (0, 2, 4):
        ground(o, 1, "dirt")
    elif p == 1:                                              # 林務小屋
        o.box((0, 0.1, 0), (0.5, 0.36, 10), "logs")
        o.gable((0, 0.1, 10), (0.56, 0.42, 9), "shingle", "x")
        face_box(o, 0, 0.1, 0.5, 0.36, "-y", 0, 0.08, 0, 7, "darkwood")
        chimney(o, (0.15, 0.15), 0.035, 22, m="stone")
        log_pile(o, (0.0, -0.32), 2, 3, 0.5, 0.025)
    elif p == 3:                                              # 原木吊架
        for x in (-0.35, 0.35):
            o.seg((x, -0.3, 0), (x, 0, h * 0.85), "wood", r=0.02)
            o.seg((x, 0.3, 0), (x, 0, h * 0.85), "wood", r=0.02)
        o.seg((-0.4, 0, h * 0.85), (0.4, 0, h * 0.85), "wood", r=0.025)
        log_pile(o, (0, 0), 3, 4, 0.7, 0.03)
    elif p == 5:                                              # 原木堆
        log_pile(o, (-0.15, -0.1), 2, 4, 0.55, 0.035, along="y")
        log_pile(o, (0.25, 0.2), 2, 3, 0.45, 0.03)
    return o


def oilrefinery(p, h, info, frame=0):
    o = Ops()
    g2, g1 = {0, 2, 6, 8, 12}, {4, 10}
    if p in g2:
        ground(o, 2, "concrete")
    elif p in g1:
        ground(o, 1, "concrete")
    elif p == 1:                                              # 製程單元
        for (x, y) in ((-0.5, -0.4), (-0.1, -0.5), (0.3, -0.3)):
            column(o, (x, y), 0.09, h * 0.9, "silver")
        shed(o, (0.2, 0.5), 0.9, 0.5, 12, wall="concrete", roofm="corrugated", kind="flat", win=4)
        for y in (0.0, 0.15):
            pipe(o, (-0.9, y, 10), (0.9, y, 10), "company", r=0.02)
    elif p == 3:                                              # 大型儲油槽
        tank(o, (-0.4, -0.4), 0.42, h * 0.55, "white", top="flat")
        tank(o, (0.45, 0.4), 0.38, h * 0.5, "white", top="flat")
        o.box((-0.4, -0.4, h * 0.25), (0.86, 0.02, 2), "company")
    elif p == 5:                                              # 蒸餾塔群（1×1）
        column(o, (-0.15, -0.1), 0.1, h * 0.92, "silver")
        column(o, (0.2, 0.15), 0.08, h * 0.7, "silver")
        pipe(o, (-0.15, -0.1, h * 0.6), (0.2, 0.15, h * 0.5), "company")
    elif p == 7:                                              # 球形儲槽
        sphere_tank(o, (-0.4, -0.3), 0.3, 10)
        sphere_tank(o, (0.45, 0.35), 0.26, 9)
    elif p == 9:                                              # 裂解單元 + 加熱爐煙囪
        shed(o, (-0.3, 0.2), 1.0, 0.8, 22, wall="corrugated", roofm="company", kind="flat", win=4)
        for k in range(2):
            chimney(o, (0.5 + k * 0.25, -0.5), 0.08, h * 0.95, m="concrete", top="red", bands="red")
        column(o, (-0.6, -0.6), 0.1, h * 0.8, "silver")
    elif p == 11:                                             # 高煙囪（1×1）
        chimney(o, (0, 0), 0.13, h, m="concrete", top="red", bands="red")
        o.box((0.25, 0.25, 0), (0.3, 0.3, 8), "brick")
    elif p == 13:                                             # 火炬塔
        for a in range(3):
            ang = a * 2 * math.pi / 3
            o.seg((0.35 * math.cos(ang), 0.35 * math.sin(ang), 0), (0.04 * math.cos(ang), 0.04 * math.sin(ang), h), "company", r=0.012)
        for k in range(1, 8):
            z = h * k / 8
            r = 0.35 - 0.31 * k / 8
            for a in range(3):
                a0, a1 = a * 2 * math.pi / 3, (a + 1) * 2 * math.pi / 3
                o.seg((r * math.cos(a0), r * math.sin(a0), z), (r * math.cos(a1), r * math.sin(a1), z), "white", r=0.007)
        o.cyl((0, 0, 0), 0.04, h, "darksteel", v=8)
    else:                                                     # 火焰（64 格，疊在火炬塔頂）
        k = p - 14
        rng = random.Random(1000 + k)
        flick = 0.75 + 0.25 * math.sin(2 * math.pi * k / 64 * 3) + rng.uniform(-0.08, 0.08)
        lean = 0.06 * math.sin(2 * math.pi * k / 64)
        fh = h * 0.55 * flick
        o.cyl((0, 0, 0), 0.03, 3, "darksteel", v=8)
        o.lathe((lean * 0.3, 0, 3), [(0.0, 0), (0.07, fh * 0.15), (0.09, fh * 0.35), (0.06, fh * 0.65), (0.0, fh)], "flame", seg=10)
        o.lathe((lean * 0.2, 0, 3), [(0.0, 0), (0.04, fh * 0.15), (0.04, fh * 0.35), (0.0, fh * 0.55)], "glow", seg=8)
        smoke_puffs(o, (lean, 0), 3 + fh, k, 64, n=2, rise=h - fh - 4, size=0.06, m="smoke")
    return o


def oilrig(p, h, info):
    o = Ops()
    deck = 42
    for x in (-0.6, 0.6):
        for y in (-0.6, 0.6):
            o.cyl((x, y, 0), 0.09, deck, "yellowsteel", v=12)
            o.cyl((x, y, 0), 0.12, 4, "darksteel", v=12)
    for (a, b) in (((-0.6, -0.6), (0.6, -0.6)), ((0.6, -0.6), (0.6, 0.6)), ((0.6, 0.6), (-0.6, 0.6)), ((-0.6, 0.6), (-0.6, -0.6))):
        o.seg((a[0], a[1], 8), (b[0], b[1], deck - 8), "yellowsteel", r=0.02)
    o.box((0, 0, deck), (1.6, 1.6, 4), "darksteel")
    shed(o, (-0.4, 0.4), 0.7, 0.6, 16, wall="white", roofm="company", kind="flat", win=3, door=False)
    o.box((0.55, 0.5, deck + 4), (0.5, 0.5, 1), "darksteel")
    o.cyl((0.55, 0.5, deck + 5), 0.22, 0.3, "yellowsteel", v=20)                   # 直升機坪
    # 鑽塔
    base = deck + 4
    top = h
    for dx in (-1, 1):
        for dy in (-1, 1):
            o.seg((0.25 + dx * 0.2, -0.35 + dy * 0.2, base), (0.25 + dx * 0.04, -0.35 + dy * 0.04, top), "company", r=0.012)
    for k in range(1, 7):
        z = base + (top - base) * k / 7
        w = 0.2 - 0.16 * k / 7
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            o.seg((0.25 + a[0] * w, -0.35 + a[1] * w, z), (0.25 + b[0] * w, -0.35 + b[1] * w, z), "white", r=0.006)
    o.seg((-0.7, -0.3, deck + 4), (-0.2, -0.75, deck + 34), "yellowsteel", r=0.02)        # 吊臂
    o.seg((-0.7, -0.75, base), (-0.7, -0.75, base + 20), "white", r=0.02)
    return o


def oilwell(p, h, info):
    o = Ops()
    if p in (0, 19):
        ground(o, 1, "dirt")
    elif p == 17:
        ground(o, 2, "gravel")
    elif 1 <= p <= 16:                                        # 抽油機（16 格）
        k = p - 1
        ang = math.radians(16) * math.sin(2 * math.pi * k / 16)
        o.box((0, 0, 0), (0.7, 0.25, 1.5), "concrete")
        for dy in (-0.07, 0.07):
            o.seg((0.0, dy, 1.5), (0.0, dy * 0.4, 30), "darksteel", r=0.014)
            o.seg((-0.12, dy, 1.5), (0.0, dy * 0.4, 30), "darksteel", r=0.012)
        L1, L2 = 0.38, 0.25
        piv = (0.0, 0.0, 31)
        head = (piv[0] + L1 * math.cos(ang), 0, piv[2] + L1 * TZ * math.sin(ang))
        tail = (piv[0] - L2 * math.cos(ang), 0, piv[2] - L2 * TZ * math.sin(ang))
        o.seg(tail, head, "company", r=0.03)
        o.lathe((head[0], 0, head[2] - 6), [(0.0, 0), (0.06, 2), (0.07, 6), (0.06, 10), (0.0, 12)], "company", seg=10)  # 驢頭
        o.seg((head[0] + 0.05, 0, head[2] - 6), (0.43, 0, 2), "black", r=0.004)
        o.cyl((0.43, 0, 0), 0.04, 4, "darksteel", v=8)
        o.box((-0.25, 0, 1.5), (0.16, 0.18, 6), "darksteel")                            # 曲柄配重
        o.seg((tail[0], 0, tail[2]), (-0.25, 0, 7.5 + 3 * math.sin(ang * 3)), "darksteel", r=0.012)
    elif p == 18:                                             # 儲油槽
        tank(o, (-0.4, -0.3), 0.36, h * 0.6, "silver", top="flat")
        tank(o, (0.45, 0.4), 0.3, h * 0.55, "silver", top="flat")
        o.box((-0.4, -0.3, h * 0.35), (0.74, 0.02, 2), "company")
        pipe(o, (-0.4, -0.3, 3), (0.45, 0.4, 3), "darksteel")
    elif p == 20:                                             # 鑽井架
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.seg((dx * 0.25, dy * 0.25, 0), (dx * 0.04, dy * 0.04, h), "company", r=0.012)
        for k in range(1, 10):
            z = h * k / 10
            w = 0.25 - 0.21 * k / 10
            for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                o.seg((a[0] * w, a[1] * w, z), (b[0] * w, b[1] * w, z), "steel", r=0.006)
        o.box((0, 0, 0), (0.6, 0.6, 2), "wood")
        o.box((0.35, 0.3, 0), (0.2, 0.15, 6), "darksteel")
    return o


def oremine(p, h, info):
    o = Ops()
    sizes = {0: 2, 2: 2, 4: 2, 6: 1, 8: 2, 10: 1, 12: 2, 14: 1}
    if p in sizes:
        ground(o, sizes[p], "ore")
        return o
    if p == 1:                                                # 辦公室與更衣室
        shed(o, (-0.2, 0.2), 1.1, 0.7, 20, wall="brick", roofm="slate", win=5, rows=1)
        o.box((0.6, -0.6, 0), (0.4, 0.3, 10), "corrugated")
    elif p == 3:                                              # 碎礦廠（階梯狀廠房）
        for k in range(3):
            o.box((-0.5 + k * 0.5, 0.1, 0), (0.55, 1.1, h * (0.95 - 0.25 * k)), "corrugated")
            o.box((-0.5 + k * 0.5, 0.1, h * (0.95 - 0.25 * k)), (0.57, 1.12, 1.2), "company")
        o.seg((0.9, -0.8, 2), (0.0, -0.2, h * 0.7), "darksteel", r=0.04)
    elif p == 5:                                              # 礦石倉 + 輸送帶
        o.box((0, 0, 0), (0.6, 0.6, 18), "darksteel")
        o.box((0, 0, 18), (0.9, 0.9, 24), "company")
        o.cyl((0, 0, 12), 0.25, 6, "darksteel", v=4, rt=0.4)
        o.seg((0.5, 0.5, 30), (1.0, 1.0, 4), "darksteel", r=0.035)
    elif p == 7:                                              # 豎井井架（1×1）
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.seg((dx * 0.22, dy * 0.22, 0), (dx * 0.1, dy * 0.1, h * 0.85), "company", r=0.018)
        for k in range(1, 6):
            z = h * 0.85 * k / 6
            w = 0.22 - 0.12 * k / 6
            for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                o.seg((a[0] * w, a[1] * w, z), (b[0] * w, b[1] * w, z), "company", r=0.01)
        for s in (-0.06, 0.06):                               # 天輪
            o.lathe((0, s, h * 0.9), [(0.12, -2), (0.13, 0), (0.12, 2)], "darksteel", seg=16)
        o.seg((-0.3, 0.0, h * 0.4), (0.0, 0.0, h * 0.9), "darksteel", r=0.02)
        o.box((-0.3, 0.3, 0), (0.3, 0.3, 14), "brick")
    elif p == 9:                                              # 機具棚
        shed(o, (0, 0), 1.2, 0.9, 18, wall="corrugated", roofm="company", win=4)
    elif p == 11:                                             # 小工具房（1×1）
        shed(o, (0, 0), 0.5, 0.4, 12, wall="brick", roofm="slate", win=2)
    elif p == 13:                                             # 選礦廠 + 水槽
        shed(o, (-0.2, 0.2), 1.1, 0.9, 36, wall="corrugated", roofm="company", win=5, rows=2)
        tank(o, (0.65, -0.6), 0.2, 16, "concrete", top="flat")
    elif p == 15:                                             # 礦石堆（1×1）
        o.hip((0, 0, 0), (0.8, 0.7, h * 0.6), "ore", k=0.3)
        o.seg((0.45, 0.45, 2), (0.0, 0.0, h * 0.7), "darksteel", r=0.03)
    return o


def papermill(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "concrete")
    elif p == 2:
        ground(o, 1, "concrete")
    elif p == 1:                                              # 長條造紙機廠房
        shed(o, (0, 0.15), 1.6, 0.8, 26, wall="yellowbrick", roofm="company", win=8, rows=2)
        for x in (-0.5, 0.0, 0.5):
            o.box((x, 0.15, 36), (0.12, 0.3, 6), "corrugated")                     # 屋頂排氣罩
        log_pile(o, (-0.3, -0.7), 2, 4, 0.8, 0.03)
    elif p == 3:                                              # 蒸煮塔 + 煙囪（1×1）
        tank(o, (-0.15, 0.1), 0.18, h * 0.5, "concrete", top="dome")
        chimney(o, (0.22, -0.2), 0.09, h, bands="darkbrick")
    return o


def printworks(p, h, info):
    o = Ops()
    ground(o, 2, "pavement")
    if p == 0:                                                # 印刷廠主樓（紅磚、鐘塔）
        o.box((0, 0.15, 0), (1.5, 1.0, 40), "brick")
        windows(o, 0, 0.15, 1.5, 1.0, 4, 38, 3, 8, sills="white")
        band(o, 0, 0.15, 1.5, 1.0, 39, 1.5, "white")
        o.hip((0, 0.15, 40), (1.52, 1.02, 14), "slate", k=0.5)
        o.box((0, -0.45, 0), (0.3, 0.3, 64), "brick")
        for side in SIDES:
            face_box(o, 0, -0.45, 0.3, 0.3, side, 0, 0.2, 50, 9, "white")
        o.hip((0, -0.45, 64), (0.34, 0.34, h - 64), "copper", k=0.0)
    else:                                                     # 倉庫與裝卸台
        shed(o, (0, 0.2), 1.6, 0.9, 30, wall="darkbrick", roofm="company", win=8)
        for k in range(4):
            face_box(o, 0, 0.2, 1.6, 0.9, "-y", -0.35 + k * 0.23, 0.18, 0, 10, "darksteel")
        o.box((0, -0.32, 0), (1.5, 0.12, 3), "concrete")
        for k in range(3):
            o.box((-0.5 + k * 0.5, -0.7, 0), (0.25, 0.16, 7), "white")                    # 送貨車
    return o


def sawmill(p, h, info):
    o = Ops()
    if p in (0, 2, 4, 6, 8):
        ground(o, 2, "dirt")
    elif p == 1:                                              # 鋸木廠房 + 原木坡道
        shed(o, (-0.2, 0.2), 1.3, 0.8, 22, wall="wood", roofm="corrugated", win=5)
        o.seg((0.9, -0.6, 1), (0.3, -0.1, 14), "wood", r=0.05)
        log_pile(o, (0.5, -0.65), 2, 4, 0.7, 0.03)
    elif p == 3:                                              # 原木堆 + 吊車
        log_pile(o, (-0.3, 0.2), 3, 5, 1.1, 0.035)
        log_pile(o, (0.4, -0.5), 2, 4, 0.8, 0.03, along="y")
        o.seg((0.7, 0.6, 0), (0.7, 0.6, h * 0.9), "company", r=0.02)
        o.seg((0.7, 0.6, h * 0.9), (-0.1, 0.2, h * 0.7), "company", r=0.015)
    elif p == 5:                                              # 乾燥窯 + 煙囪
        for k in range(3):
            o.box((-0.4 + k * 0.4, 0.2, 0), (0.35, 1.0, 16), "brick")
            o.gable((-0.4 + k * 0.4, 0.2, 16), (0.37, 1.02, 7), "slate", "y")
        chimney(o, (0.6, -0.65), 0.08, h)
    elif p == 7:                                              # 大型木材倉庫
        shed(o, (0, 0.1), 1.6, 1.1, 34, wall="lightwood", roofm="company", win=6, rows=2)
    elif p == 9:                                              # 板材堆
        for k in range(6):
            x, y = -0.6 + (k % 3) * 0.6, -0.4 + (k // 3) * 0.7
            for L in range(5):
                o.box((x, y, L * 3), (0.45, 0.3, 2.6), "planks" if L % 2 == 0 else "lightwood")
    return o


def skicentre(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "snow")
        o.box((0.5, -0.5, 0), (0.6, 0.5, 0.5), "pavement")
    elif p in (1, 2):                                         # 兩層木造樓層與陽台
        o.box((-0.2, 0.2, 0), (1.2, 0.9, h), "lightwood" if p == 2 else "stone")
        windows(o, -0.2, 0.2, 1.2, 0.9, h * 0.2, h * 0.9, 1, 6, sills="white")
        if p == 2:
            o.box((-0.2, 0.2 - 0.5, 0.3), (1.1, 0.1, 0.6), "darkwood")
        if p == 1:
            face_box(o, -0.2, 0.2, 1.2, 0.9, "-y", 0, 0.2, 0, 7, "darkwood")
            for k in range(5):                                # 雪板架
                o.box((0.6, -0.6 + k * 0.05, 0), (0.01, 0.01, 5), "company")
    else:                                                     # 出簷很深的山形屋頂
        o.gable((-0.2, 0.2, 0), (1.4, 1.1, h * 0.9), "company", "x")
        chimney(o, (0.2, 0.3), 0.06, h * 0.8, m="stone")
    return o


def steelmill(p, h, info):
    o = Ops()
    if p in (0, 4):
        ground(o, 2, "ore")
        return o
    if p in (2, 6, 9):
        ground(o, 1, "ore")
        return o
    if p == 1 or 10 <= p <= 16:                               # 煉鋼廠房；10–16 為倒鋼動畫格
        k = 0 if p == 1 else p - 9
        shed(o, (0, 0.1), 1.5, 1.1, 46, wall="rust", roofm="corrugated", win=0)
        o.box((0, 0.1, 60), (0.3, 0.9, 6), "rust")                                       # 屋頂通風樓
        for x in (-0.45, 0.45):
            chimney(o, (x, 0.5), 0.07, h * 0.98, m="darkconcrete", top="darkstone")
        door_glow = "glow" if k else "black"
        face_box(o, 0, 0.1, 1.5, 1.1, "-y", -0.15, 0.4, 0, 30, door_glow)
        face_box(o, 0, 0.1, 1.5, 1.1, "-x", 0.1, 0.4, 0, 30, door_glow)
        if k:
            tilt = min(k, 6) / 6
            o.lathe((-0.3, -0.55, 18), [(0.0, 0), (0.12, 1), (0.14, 8), (0.12, 12)], "darksteel", seg=12)
            o.seg((-0.3 + 0.1 * tilt, -0.55, 28), (-0.3 + 0.2 * tilt, -0.6, 4), "flame", r=0.02 + 0.02 * tilt)
            o.cyl((-0.15, -0.6, 0), 0.08 + 0.05 * tilt, 1.5, "glow", v=12)
    elif p == 3:                                              # 礦石倉（1×1）
        o.box((0, 0, 0), (0.7, 0.7, 14), "darksteel")
        o.box((0, 0, 14), (0.8, 0.8, 18), "rust")
        o.cyl((0, 0, 8), 0.18, 6, "darksteel", v=4, rt=0.4)
    elif p == 5:                                              # 高爐（2×2）
        o.cyl((0, 0, 0), 0.35, h * 0.2, "darksteel", v=20)
        o.cyl((0, 0, h * 0.2), 0.3, h * 0.55, "rust", v=20, rt=0.22)
        o.cyl((0, 0, h * 0.75), 0.18, h * 0.15, "darksteel", v=16)
        for k in range(3):                                    # 熱風爐
            tank(o, (0.65, -0.6 + k * 0.3), 0.13, h * 0.5, "darkconcrete", top="dome")
        pipe(o, (0, 0, h * 0.85), (0.6, 0.6, h * 0.95), "rust", r=0.04)
        pipe(o, (0.6, 0.6, h * 0.95), (0.7, 0.7, 2), "rust", r=0.04)
        o.seg((-0.9, -0.9, 2), (-0.1, -0.1, h * 0.8), "darksteel", r=0.035)            # 裝料斜橋
    elif p == 7:                                              # 雙煙囪（1×1）
        chimney(o, (-0.15, -0.15), 0.1, h, m="darkbrick", top="darkstone", bands="darkstone")
        chimney(o, (0.2, 0.2), 0.08, h * 0.85, m="darkbrick", top="darkstone")
    elif p == 8:                                              # 鋼胚堆（1×1）
        for k in range(8):
            x, y = -0.25 + (k % 4) * 0.17, -0.15 + (k // 4) * 0.3
            o.box((x, y, (k // 4) * 3), (0.12, 0.25, 3), "darksteel")
        o.hip((0.2, 0.25, 0), (0.4, 0.3, h * 0.6), "darkstone", k=0.3)
    return o


def stockfarm(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "dirt")
        fence(o, 0, 0, 1.9, 1.9, h=2.5)
    elif p == 2:
        ground(o, 1, "dirt")
    elif p == 1:                                              # 牛舍 + 農舍
        o.box((0.2, 0.2, 0), (1.2, 0.6, 12), "wood")
        o.gable((0.2, 0.2, 12), (1.26, 0.66, 10), "corrugated", "x")
        for k in range(5):
            face_box(o, 0.2, 0.2, 1.2, 0.6, "-y", -0.4 + k * 0.2, 0.08, 4, 3, "black")
        house(o, (-0.6, -0.5), 0.5, 0.4, 12, wall="stone", roofm="slate", win=2)
        tank(o, (0.75, -0.55), 0.13, 20, "company", top="dome")
    elif p == 3:                                              # 動物棚（1×1）
        for x in (-0.3, 0.3):
            for y in (-0.2, 0.2):
                o.box((x, y, 0), (0.04, 0.04, 10), "wood")
        o.gable((0, 0, 10), (0.75, 0.55, 6), "corrugated", "x")
        o.box((0, 0.22, 0), (0.7, 0.04, 6), "wood")
        o.box((0, 0, 0), (0.5, 0.3, 2), "hay")
    return o


def vineyard(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "gravel")
        return o
    o.box((-0.15, 0.2, 0), (1.2, 0.8, 20), "ochre")                                    # 莊園屋
    windows(o, -0.15, 0.2, 1.2, 0.8, 4, 19, 2, 6, sills="white")
    o.hip((-0.15, 0.2, 20), (1.28, 0.88, 11), "terracotta", k=0.5)
    o.box((0.55, -0.45, 0), (0.3, 0.3, 30), "ochre")                                   # 塔樓
    o.hip((0.55, -0.45, 30), (0.36, 0.36, h - 30), "terracotta", k=0.0)
    for k in range(5):                                        # 酒桶
        o.seg((-0.7 + k * 0.12, -0.6, 2), (-0.7 + k * 0.12, -0.45, 2), "wood", r=0.04)
    o.box((-0.2, -0.55, 0), (0.12, 0.12, 6), "hedge")
    return o


def windmill(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "grass")
        o.box((0.5, -0.5, 0), (0.4, 0.3, 8), "plaster")
        o.gable((0.5, -0.5, 8), (0.44, 0.34, 6), "thatch", "x")
        return o
    k = p - 1                                                 # 8 格：風帆轉動（四葉，每格 11.25°）
    body = h * 0.62
    o.cyl((0, 0, 0), 0.32, body, "whitewash", v=16, rt=0.22)
    o.box((0, 0, body * 0.15), (0.68, 0.68, 1.5), "darkwood")                         # 環台
    windows(o, 0, 0, 0.42, 0.42, body * 0.3, body * 0.85, 2, 1, wf=0.3, sides=("-y", "-x"))
    o.lathe((0, 0, body), [(0.24, 0), (0.22, 6), (0.12, 14), (0.0, 18)], "darkwood", seg=16)   # 帽頂
    hub = (0.0, -0.27, body + 6)
    for s in range(4):
        a = math.radians(45 + s * 90 + k * 11.25)
        L = 0.55
        tip = (hub[0] + L * math.cos(a), hub[1], hub[2] + L * TZ * math.sin(a))
        o.seg(hub, tip, "darkwood", r=0.014)
        # 帆面：沿葉片的一片白色帆布
        nx, nz = -math.sin(a), math.cos(a)
        o.append({"op": "box", "c": [hub[0] + 0.32 * math.cos(a) + 0.045 * nx, hub[1] - 0.01, hub[2] + 0.32 * TZ * math.sin(a) - 1.5],
                  "s": [0.06, 0.012, 3], "m": "white"})
        for t in (0.25, 0.45, 0.65, 0.85):
            px = hub[0] + L * t * math.cos(a)
            pz = hub[2] + L * TZ * t * math.sin(a)
            o.seg((px, hub[1] - 0.01, pz), (px + 0.09 * nx, hub[1] - 0.01, pz + 0.09 * TZ * nz), "white", r=0.012)
    return o


def winery(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "gravel")
    elif p == 2:
        ground(o, 1, "gravel")
    elif p == 1:                                              # 石造酒窖
        o.box((0, 0.2, 0), (1.4, 0.8, 18), "stone")
        windows(o, 0, 0.2, 1.4, 0.8, 4, 16, 1, 6, wf=0.3)
        o.gable((0, 0.2, 18), (1.46, 0.86, 10), "terracotta", "x")
        face_box(o, 0, 0.2, 1.4, 0.8, "-y", 0, 0.25, 0, 12, "darkwood")
        for k in range(6):
            o.seg((-0.6 + k * 0.15, -0.55, 2.5), (-0.6 + k * 0.15, -0.38, 2.5), "wood", r=0.045)
    elif p == 3:                                              # 發酵槽塔（1×1）
        o.box((0, 0.1, 0), (0.6, 0.5, 22), "ochre")
        o.hip((0, 0.1, 22), (0.66, 0.56, 9), "terracotta", k=0.4)
        for k in range(2):
            tank(o, (-0.2 + k * 0.4, -0.3), 0.1, 14, "silver", top="cone")
    return o


INDUSTRIES = {
    "BREWERY": brewery, "CHEMWORK": chemworks, "FACTORY": factory, "FARM": farm, "FARMUS": lambda p, h, i: farm(p, h, i, us=True),
    "FOODPROC": foodproc, "FOREST": forest, "OILREFIN": oilrefinery, "OILRIG": oilrig, "OILWELL": oilwell, "OREMINE": oremine,
    "PAPERMIL": papermill, "PRINTWRK": printworks, "SAWMILL": sawmill, "SKICENT": skicentre, "STEELMIL": steelmill,
    "STOCKFRM": stockfarm, "VINEYARD": vineyard, "WINDMILL": windmill, "WINERY": winery,
}


def make_model(name: str, info: dict) -> dict:
    fn = INDUSTRIES[name]
    parts = []
    for p, h in enumerate(info["heights"]):
        parts.append({"height": h, "ops": list(fn(p, h, info))})
    return {"kind": "industry", "parts": parts}
