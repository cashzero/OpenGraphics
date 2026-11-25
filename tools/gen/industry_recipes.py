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


def sphere_tank(o, c, r, z, m="silver"):
    x, y = c
    for a in range(6):                                         # 支柱
        ang = a * math.pi / 3
        o.seg((x + r * 0.85 * math.cos(ang), y + r * 0.85 * math.sin(ang), 0),
              (x + r * 0.85 * math.cos(ang), y + r * 0.85 * math.sin(ang), z + r * TZ * 0.55), "darksteel", r=0.014)
    prof = [(0.0, -r * TZ), (r * 0.68, -r * TZ * 0.72), (r, 0), (r * 0.68, r * TZ * 0.72), (0.0, r * TZ)]
    o.lathe((x, y, z + r * TZ), prof, m, seg=20)
    o.cyl((x, y, z + r * TZ - 0.6), r * 1.03, 1.2, "darksteel", v=20)      # 赤道檢修環帶
    o.cyl((x, y, z + r * TZ * 1.98), r * 0.25, 1.4, "darksteel", v=12)     # 頂部閥座
    o.seg((x + r * 0.9, y, 0), (x + r * 0.9, y, z + r * TZ * 1.4), "darksteel", r=0.008)


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
        ground(o, 2, "gravel")
    elif p in (6, 8):
        ground(o, 1, "gravel")
    elif p == 1:                                              # 製程廠房 + 管架 + 冷凝器
        shed(o, (-0.30, 0.22), 1.06, 0.92, h * 0.44, wall="corrugated", roofm="darkconcrete", kind="flat", win=5)
        band(o, -0.30, 0.22, 1.06, 0.92, h * 0.44 - 1.2, 1.2, "company", grow=0.04)
        o.box((-0.30, 0.22, h * 0.44 + 1.0), (0.70, 0.30, 4.5), "darksteel")
        for k in range(3):
            chimney(o, (0.56, -0.58 + k * 0.30), 0.055, h * (0.95 - k * 0.08), m="steel", top="darksteel")
        for y in (-0.60, -0.36, -0.12):
            pipe(o, (-0.84, y - 0.14, 14), (0.64, y - 0.14, 14), "steel", r=0.022)
        pipe(o, (-0.84, -0.48, 17), (0.64, -0.48, 17), "company", r=0.024)
        for x in (-0.64, -0.12, 0.40):
            o.seg((x, -0.78, 0), (x, -0.78, 18), "darksteel", r=0.015)
            o.seg((x, -0.22, 0), (x, -0.22, 18), "darksteel", r=0.015)
            o.seg((x, -0.78, 14), (x, -0.22, 14), "darksteel", r=0.014)
    elif p == 3:                                              # 蒸餾塔群 + 拱形管橋
        cols = ((-0.42, -0.32, h), (0.02, -0.42, h * 0.82), (0.36, -0.20, h * 0.90), (-0.22, 0.30, h * 0.64))
        for x, y, hh in cols:
            column(o, (x, y), 0.11, hh * 0.85, "silver", platforms=3)
            o.cyl((x, y, hh * 0.45), 0.12, 1.4, "company", v=14)
        for (ax, ay, ah), (bx, by, bh) in ((cols[0], cols[1]), (cols[1], cols[2]), (cols[2], cols[3])):
            zm = min(ah, bh) * 0.65
            pipe(o, (ax, ay, zm), (ax, ay, zm + 8), "steel", r=0.02)
            pipe(o, (ax, ay, zm + 8), (bx, by, zm + 8), "steel", r=0.02)
            pipe(o, (bx, by, zm + 8), (bx, by, zm - 4), "steel", r=0.02)
        shed(o, (0.52, 0.56), 0.62, 0.50, 14, wall="brick", roofm="darkconcrete", kind="flat", win=3)
    elif p == 5:                                              # 高煙囪 + 鍋爐房
        shed(o, (-0.3, 0.3), 0.9, 0.8, 26, wall="brick", roofm="slate", win=4)
        chimney(o, (0.4, -0.4), 0.14, h, m="concrete", top="red", bands="red")
    elif p == 7:                                              # 球形儲槽（金屬銀色＋圍堰）
        o.box((0, 0, 0), (0.88, 0.88, 0.8), "darkconcrete")
        parapet(o, 0, 0, 0.88, 0.88, 0, 2.2, "stone", t=0.04)
        sphere_tank(o, (-0.16, -0.16), 0.21, 11, "silver")
        sphere_tank(o, (0.22, 0.22), 0.16, 9, "steel")
    elif p == 9:                                              # 臥式儲槽（金屬銀色＋管匯）
        o.box((0, 0, 0), (0.88, 0.88, 0.8), "darkconcrete")
        for k in range(3):
            y = -0.26 + k * 0.26
            for x in (-0.28, 0.28):
                o.box((x, y, 0), (0.06, 0.14, 4.5), "stone")
            o.seg((-0.38, y, 9.5), (0.38, y, 9.5), "silver", r=0.105)
            o.box((0, y, 12.5), (0.08, 0.08, 2.0), "company")
        pipe(o, (-0.42, -0.26, 6.0), (-0.42, 0.26, 6.0), "darksteel", r=0.018)
    return o


def factory(p, h, info, frame=0):
    o = Ops()
    if p in (0, 2):
        ground(o, 2, "gravel")
    elif p == 1:                                              # 鋸齒屋頂廠房 + 辦公樓 + 水塔
        shed(o, (-0.15, 0.15), 1.4, 1.2, 28, wall="brick", roofm="slate", kind="saw", win=7)
        o.box((0.55, -0.7, 0), (0.7, 0.4, 24), "yellowbrick")
        windows(o, 0.55, -0.7, 0.7, 0.4, 2, 23, 2, 5, sills="stone")
        o.box((0.55, -0.7, 23.6), (0.64, 0.34, 0.9), "darkconcrete")
        parapet(o, 0.55, -0.7, 0.72, 0.42, 23.5, 2.2, "stone", t=0.04)
        for a in range(4):
            ang = math.pi / 4 + a * math.pi / 2
            o.seg((-0.7 + 0.1 * math.cos(ang), -0.7 + 0.1 * math.sin(ang), 0), (-0.7 + 0.08 * math.cos(ang), -0.7 + 0.08 * math.sin(ang), h * 0.72), "darksteel", r=0.01)
        tank(o, (-0.7, -0.7), 0.13, h * 0.2, "company", top="cone", z=h * 0.72)
    elif p == 3:                                              # 大廠房（暗石板鋸齒頂＋公司色簷口）+ 煙囪下段
        shed(o, (-0.2, 0.15), 1.4, 1.3, 44, wall="darkbrick", roofm="slate", kind="saw", win=8, rows=2)
        band(o, -0.2, 0.15, 1.4, 1.3, 42.5, 1.8, "company", grow=0.04)
        chimney(o, (0.65, -0.6), 0.15, h, bands="darkstone")
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
        ground(o, 2, "gravel")
        o.box((0, 0, 0), (1.75, 1.65, 0.3), "darkconcrete")
        return o
    # 紅磚＋米色混凝土罐頭廠房（凹入深色屋頂＋雙排採光天窗，避免整片白頂過曝）
    o.box((-0.22, 0.14, 0), (1.28, 1.08, 6.0), "brick")
    o.box((-0.22, 0.14, 6.0), (1.26, 1.06, 22.0), "cream")
    windows(o, -0.22, 0.14, 1.26, 1.06, 8.0, 26.0, 2, 6, sills="stone")
    for x in (-0.82, -0.42, -0.02, 0.38):
        o.box((x, -0.40, 0), (0.04, 0.04, 28.0), "stone")
        o.box((x, 0.68, 0), (0.04, 0.04, 28.0), "stone")
    # 女兒牆＋公司色簷口細條＋深色屋頂甲板＋雙排採光天窗＋屋頂水塔
    band(o, -0.22, 0.14, 1.26, 1.06, 26.8, 1.2, "company", grow=0.04)
    parapet(o, -0.22, 0.14, 1.28, 1.08, 28.0, 2.2, "stone", t=0.05)
    o.box((-0.22, 0.14, 27.6), (1.18, 0.98, 0.9), "darkconcrete")
    for y in (-0.12, 0.36):
        o.box((-0.22, y, 28.5), (0.96, 0.24, 2.4), "blueglass")
        o.gable((-0.22, y, 30.9), (0.98, 0.28, 2.2), "slate", "x")
    tank(o, (-0.64, 0.44), 0.12, 5.0, "darksteel", top="cone", z=28.5)
    # 三座不鏽鋼原料筒倉＋架空輸送管橋
    for k in range(3):
        sy = -0.58 + k * 0.34
        tank(o, (0.64, sy), 0.13, h * 0.68, "silver", top="cone")
        o.cyl((0.64, sy, h * 0.42), 0.14, 0.9, "company", v=16)
        pipe(o, (0.40, sy, h * 0.56), (0.64, sy, h * 0.62), "darksteel", r=0.022)
    # 裝卸月台與遮雨棚
    o.box((-0.22, -0.56, 0), (0.86, 0.34, 9.5), "brick")
    o.box((-0.22, -0.58, 9.5), (0.90, 0.38, 1.2), "slate")
    for dx in (-0.28, 0.0, 0.28):
        face_box(o, -0.22, -0.56, 0.86, 0.34, "-y", dx, 0.18, 0, 7.2, "darksteel")
    chimney(o, (-0.72, 0.62), 0.07, h * 0.78, m="brick", top="darkstone", bands="company")
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
        ground(o, 2, "gravel")
        o.box((0, 0, 0), (1.84, 1.84, 0.35), "darkconcrete")
        return o
    if p in g1:
        ground(o, 1, "gravel")
        o.box((0, 0, 0), (0.90, 0.90, 0.35), "darkconcrete")
        return o
    if p == 1:                                                # 製程與加氫脫硫單元（密集塔群＋多層拱形管橋＋熱交換器）
        cols = ((-0.54, -0.42, h * 0.96, 0.13, "steel"),
                (-0.14, -0.52, h * 0.84, 0.11, "silver"),
                (0.28, -0.40, h * 0.92, 0.12, "rust"),
                (-0.48, 0.12, h * 0.72, 0.10, "silver"))
        for x, y, hh, r, mat in cols:
            column(o, (x, y), r, hh, mat, platforms=3)
            o.seg((x + r * 1.1, y, 0), (x + r * 1.1, y, hh), "darksteel", r=0.012)
        for (ax, ay, ah, *_), (bx, by, bh, *_) in ((cols[0], cols[1]), (cols[1], cols[2]), (cols[0], cols[3])):
            zm = min(ah, bh) * 0.68
            pipe(o, (ax, ay, zm), (ax, ay, zm + 7), "rust", r=0.028)
            pipe(o, (ax, ay, zm + 7), (bx, by, zm + 7), "rust", r=0.028)
            pipe(o, (bx, by, zm + 7), (bx, by, zm - 3), "rust", r=0.028)
        # 臥式熱交換器滾筒＋控制泵房＋管架
        for k in range(2):
            o.seg((-0.68, 0.56 - k * 0.22, 8), (0.04, 0.56 - k * 0.22, 8), "steel", r=0.085)
            for xx in (-0.54, -0.10):
                o.box((xx, 0.56 - k * 0.22, 0), (0.06, 0.14, 5.5), "darkconcrete")
        shed(o, (0.44, 0.46), 0.74, 0.62, 16, wall="brick", roofm="darkconcrete", kind="flat", win=4)
        band(o, 0.44, 0.46, 0.74, 0.62, 14.8, 1.1, "company", grow=0.04)
        for y in (-0.06, 0.08):
            pipe(o, (-0.88, y, 13), (0.88, y, 13), "steel" if y < 0 else "company", r=0.024)
        for x in (-0.70, -0.15, 0.45):
            o.seg((x, -0.08, 0), (x, -0.08, 14), "darksteel", r=0.016)
            o.seg((x, 0.10, 0), (x, 0.10, 14), "darksteel", r=0.016)
            o.seg((x, -0.08, 13), (x, 0.10, 13), "darksteel", r=0.014)
    elif p == 3:                                              # 巨型風化鋼製原油儲槽（填滿 2×2 圍堰＋補強環＋盤梯＋集油管匯）
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.055)
        for (x, y, r, th, mat) in ((-0.38, -0.36, 0.49, h * 0.74, "steel"),
                                   (0.42, 0.38, 0.44, h * 0.66, "rust")):
            tank(o, (x, y), r, th, mat, top="flat")
            # 水平焊縫加強肋環＋頂部浮頂護欄與暗色浮頂蓋
            for frac in (0.28, 0.56, 0.82):
                o.cyl((x, y, th * frac), r * 1.025, 0.9, "darksteel", v=24)
            o.cyl((x, y, th * 0.66), r * 1.03, 1.6, "company", v=24)
            o.cyl((x, y, th + 0.4), r * 0.94, 1.0, "darkconcrete", v=24)
            o.cyl((x, y, th + 1.0), r * 1.01, 1.8, "darksteel", v=24)
            # 外壁攀登斜梯與頂部集油管
            o.seg((x + r * 1.03, y - 0.14, 0), (x + r * 1.03, y + 0.18, th + 1.5), "darksteel", r=0.016)
            o.seg((x + r * 0.95, y - 0.14, 0), (x + r * 0.95, y + 0.18, th + 1.5), "darksteel", r=0.012)
        pipe(o, (-0.38, -0.36, 4.0), (0.42, 0.38, 4.0), "darksteel", r=0.032)
        o.box((-0.62, 0.54, 0), (0.36, 0.30, 10.0), "darksteel")              # 泵浦閥組箱
    elif p == 5:                                              # 雙塔分餾單元（1×1）
        column(o, (-0.18, -0.14), 0.12, h * 0.94, "steel", platforms=4)
        column(o, (0.20, 0.16), 0.10, h * 0.78, "rust", platforms=3)
        pipe(o, (-0.18, -0.14, h * 0.66), (-0.18, -0.14, h * 0.76), "steel", r=0.026)
        pipe(o, (-0.18, -0.14, h * 0.76), (0.20, 0.16, h * 0.76), "steel", r=0.026)
        pipe(o, (0.20, 0.16, h * 0.76), (0.20, 0.16, h * 0.60), "steel", r=0.026)
        o.seg((-0.34, 0.22, 6), (0.24, 0.22, 6), "darksteel", r=0.055)
    elif p == 7:                                              # 高壓液化氣球形儲槽區（2×2）
        parapet(o, 0, 0, 1.84, 1.84, 0, 2.4, "stone", t=0.05)
        sphere_tank(o, (-0.42, -0.32), 0.32, 9, "silver")
        sphere_tank(o, (0.44, 0.34), 0.29, 8, "steel")
        pipe(o, (-0.42, -0.32, 4.0), (0.44, 0.34, 4.0), "darksteel", r=0.028)
        o.box((-0.50, 0.54, 0), (0.42, 0.32, 11.0), "brick")
        o.box((-0.50, 0.54, 11.0), (0.44, 0.34, 1.2), "darkconcrete")
    elif p == 9:                                              # 熱裂解爐＋雙煙囪＋塔器（2×2）
        shed(o, (-0.32, 0.22), 1.08, 0.88, 26, wall="rust", roofm="darkconcrete", kind="flat", win=4)
        band(o, -0.32, 0.22, 1.08, 0.88, 24.4, 1.4, "company", grow=0.04)
        for k in range(2):
            chimney(o, (0.50 + k * 0.26, -0.46), 0.095, h * 0.96, m="steel", top="darksteel", bands="red")
        column(o, (-0.60, -0.58), 0.13, h * 0.88, "silver", platforms=3)
        pipe(o, (-0.60, -0.58, 28), (-0.60, -0.58, 36), "rust", r=0.030)
        pipe(o, (-0.60, -0.58, 36), (-0.32, 0.22, 36), "rust", r=0.030)
        pipe(o, (-0.32, 0.22, 36), (-0.32, 0.22, 24), "rust", r=0.030)
    elif p == 11:                                             # 主煙道高煙囪＋鍋爐間（1×1）
        chimney(o, (-0.06, -0.06), 0.16, h, m="stone", top="darksteel", bands="red")
        o.box((0.24, 0.24, 0), (0.38, 0.36, 14), "brick")
        o.gable((0.24, 0.24, 14), (0.42, 0.40, 5), "slate", "x")
        pipe(o, (0.16, 0.16, 12), (-0.06, -0.06, 18), "darksteel", r=0.05)
    elif p == 13:                                             # 核心巨型催化裂解塔群＋高聳火炬塔（2×2，h=155，原版 Shot 09 主視覺！）
        # 重型混凝土與鋼構設備基座
        o.box((0, 0, 0), (1.74, 1.74, 3.0), "darkconcrete")
        parapet(o, 0, 0, 1.78, 1.78, 0, 4.2, "stone", t=0.045)
        # 中央巨型催化裂解主塔（鋼構骨架包覆＋多層圓形走道＋鏽鋼反應器）＋直上 z=155 火炬煙道
        o.cyl((0, 0, 3), 0.26, 26, "darksteel", v=20)
        o.cyl((0, 0, 29), 0.22, 64, "steel", v=20, rt=0.18)
        o.cyl((0, 0, 93), 0.18, 26, "rust", v=20, rt=0.12)
        o.cyl((0, 0, 119), 0.085, h - 119, "darksteel", v=14, rt=0.065)       # 火炬立管頂到 z=155
        o.cyl((0, 0, h - 4), 0.11, 4.0, "rust", v=14)                         # 火炬燃燒口
        # 圍繞主塔的四柱鋼構桁架與 5 層檢修平台
        for dx in (-0.30, 0.30):
            for dy in (-0.30, 0.30):
                o.seg((dx, dy, 3), (dx * 0.72, dy * 0.72, 118), "darksteel", r=0.018)
        for z_plat, r_plat in ((28, 0.36), (52, 0.34), (76, 0.32), (100, 0.28), (126, 0.20)):
            o.cyl((0, 0, z_plat), r_plat, 1.2, "darksteel", v=16)
            o.cyl((0, 0, z_plat + 2.8), r_plat * 0.98, 0.6, "steel", v=16)
        o.cyl((0, 0, 62), 0.23, 2.4, "company", v=20)
        # 三座環繞主塔的分餾／再生副塔（不同高度與材質，營造濃密工業剪影）
        flank = ((-0.52, -0.38, 108, 0.17, "rust"),
                 (0.54, -0.34, 92, 0.15, "silver"),
                 (-0.36, 0.50, 80, 0.14, "steel"))
        for fx, fy, fh, fr, fmat in flank:
            column(o, (fx, fy), fr, fh, fmat, platforms=4)
            # 粗大拱形高架鋼管直連中央主塔
            zm = fh * 0.74
            pipe(o, (fx, fy, zm), (fx, fy, zm + 11), "rust" if fmat != "rust" else "steel", r=0.036)
            pipe(o, (fx, fy, zm + 11), (0, 0, zm + 11), "rust" if fmat != "rust" else "steel", r=0.036)
            pipe(o, (fx, fy, zm * 0.45), (0, 0, zm * 0.45), "darksteel", r=0.030)
        # 副塔間互連管線＋紅磚壓縮機房＋臥式冷凝器
        pipe(o, (-0.52, -0.38, 48), (0.54, -0.34, 48), "steel", r=0.028)
        o.box((0.46, 0.48, 3), (0.62, 0.54, 24), "brick")
        o.box((0.46, 0.48, 27), (0.64, 0.56, 1.4), "darkconcrete")
        parapet(o, 0.46, 0.48, 0.64, 0.56, 26.8, 2.2, "stone", t=0.04)
        for k in range(2):
            o.seg((-0.36, -0.68 + k * 0.16, 11), (0.34, -0.68 + k * 0.16, 11), "silver", r=0.075)
    else:                                                     # 劇烈橘紅火炬火焰＋黑煙（64 格，疊在火炬口 z=155 上方）
        k = p - 14
        rng = random.Random(2000 + k)
        ang = 2 * math.pi * k / 64
        flick = 0.78 + 0.22 * math.sin(ang * 3) + rng.uniform(-0.07, 0.07)
        lean = 0.11 * math.sin(ang * 2) + 0.05
        fh = h * 0.62 * flick
        o.cyl((0, 0, 0), 0.06, 3.5, "darksteel", v=10)
        # 外層大橘紅火焰＋內層亮黃火芯＋上方躍動火舌
        o.lathe((lean * 0.35, 0, 3),
                [(0.0, 0), (0.11, fh * 0.14), (0.14, fh * 0.34), (0.10, fh * 0.66), (0.04, fh * 0.88), (0.0, fh)],
                "flame", seg=12)
        o.lathe((lean * 0.25, 0, 3),
                [(0.0, 0), (0.07, fh * 0.14), (0.075, fh * 0.38), (0.03, fh * 0.62), (0.0, fh * 0.72)],
                "glow", seg=10)
        # 躍動分離火舌（增加動態燃燒感）
        t_tongue = ((k / 64 * 4) % 1.0)
        o.lathe((lean * (0.6 + t_tongue * 0.5), 0.03 * math.cos(ang * 4), 3 + fh * (0.78 + 0.32 * t_tongue)),
                [(0.0, 0), (0.07 * (1 - 0.5 * t_tongue), 4), (0.05 * (1 - 0.5 * t_tongue), 10), (0.0, 15)],
                "flame", seg=8)
        smoke_puffs(o, (lean * 0.9, 0), 4 + fh * 0.92, k, 64, n=3, rise=max(14, h - fh * 0.92 - 2), size=0.09, m="darksteel")
    return o


def oilrig(p, h, info):
    o = Ops()
    deck = 42
    base = deck + 4
    # 四根鋼管支柱與斜撐（黃黑工業塗裝）
    for x in (-0.62, 0.62):
        for y in (-0.62, 0.62):
            o.cyl((x, y, 0), 0.10, deck, "yellowsteel", v=14)
            o.cyl((x, y, 0), 0.13, 5, "darksteel", v=14)
            o.cyl((x, y, deck - 4), 0.13, 4, "darksteel", v=14)
    for (a, b) in (((-0.62, -0.62), (0.62, -0.62)), ((0.62, -0.62), (0.62, 0.62)),
                   ((0.62, 0.62), (-0.62, 0.62)), ((-0.62, 0.62), (-0.62, -0.62))):
        o.seg((a[0], a[1], 8), (b[0], b[1], deck - 6), "yellowsteel", r=0.022)
        o.seg((b[0], b[1], 8), (a[0], a[1], deck - 6), "yellowsteel", r=0.022)
        o.seg((a[0], a[1], 22), (b[0], b[1], 22), "darksteel", r=0.022)
    # 主甲板（深色鋼板＋周圍安全欄杆）
    o.box((0, 0, deck), (1.68, 1.68, 4.0), "darksteel")
    o.box((0, 0, deck + 3.6), (1.60, 1.60, 0.6), "asphalt")
    for s in (-0.82, 0.82):
        o.seg((-0.82, s, base + 2.4), (0.82, s, base + 2.4), "yellowsteel", r=0.008)
        o.seg((s, -0.82, base + 2.4), (s, 0.82, base + 2.4), "yellowsteel", r=0.008)
    # 兩層生活艙與控制室（修正：建在主甲板上方 z = base，不再沉在水下！）
    o.box((-0.42, 0.38, base), (0.72, 0.62, 16.0), "stone")
    windows(o, -0.42, 0.38, 0.72, 0.62, base + 2.5, base + 14.5, 2, 4, m="blueglass", wf=0.55)
    o.box((-0.42, 0.38, base + 14.6), (0.74, 0.64, 1.4), "company")
    o.box((-0.42, 0.38, base + 16.0), (0.68, 0.58, 1.0), "darkconcrete")
    parapet(o, -0.42, 0.38, 0.72, 0.62, base + 16.0, 1.8, "steel", t=0.03)
    # 懸挑直升機坪（八角鋼盤＋黃圈＋白色 H 標線）
    o.box((0.56, 0.54, base + 2.0), (0.58, 0.58, 1.4), "darksteel")
    o.seg((0.40, 0.40, deck + 1), (0.76, 0.76, base + 2), "yellowsteel", r=0.02)
    o.cyl((0.56, 0.54, base + 3.4), 0.25, 0.35, "yellowsteel", v=20)
    o.cyl((0.56, 0.54, base + 3.7), 0.21, 0.25, "asphalt", v=20)
    o.box((0.50, 0.54, base + 3.9), (0.035, 0.22, 0.2), "white")
    o.box((0.62, 0.54, base + 3.9), (0.035, 0.22, 0.2), "white")
    o.box((0.56, 0.54, base + 3.9), (0.14, 0.035, 0.2), "white")
    # 甲板製程儲槽與集油管
    tank(o, (-0.48, -0.34), 0.14, 12.0, "silver", top="dome", z=base)
    tank(o, (-0.18, -0.46), 0.11, 10.0, "steel", top="dome", z=base)
    # 桁架鑽塔（深鋼主柱＋交叉拉桿＋天車頭＋公司色識別帶）
    top = h
    dx0, dy0 = 0.24, -0.30
    o.box((dx0, dy0, base), (0.48, 0.48, 4.0), "darksteel")
    for dx in (-1, 1):
        for dy in (-1, 1):
            o.seg((dx0 + dx * 0.21, dy0 + dy * 0.21, base + 4), (dx0 + dx * 0.055, dy0 + dy * 0.055, top - 4), "darksteel", r=0.016)
    for k in range(1, 7):
        z0 = base + 4 + (top - base - 8) * (k - 1) / 6
        z1 = base + 4 + (top - base - 8) * k / 6
        w0 = 0.21 - 0.155 * (k - 1) / 6
        w1 = 0.21 - 0.155 * k / 6
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            o.seg((dx0 + a[0] * w1, dy0 + a[1] * w1, z1), (dx0 + b[0] * w1, dy0 + b[1] * w1, z1), "steel", r=0.008)
            o.seg((dx0 + a[0] * w0, dy0 + a[1] * w0, z0), (dx0 + b[0] * w1, dy0 + b[1] * w1, z1), "steel", r=0.006)
    o.box((dx0, dy0, top - 4.5), (0.15, 0.15, 4.5), "company")
    # 甲板起重機（旋轉駕駛室＋斜桁吊臂）＋火炬臂
    o.cyl((-0.68, -0.58, base), 0.08, 6.0, "yellowsteel", v=10)
    o.box((-0.68, -0.58, base + 6.0), (0.20, 0.20, 6.0), "company")
    o.seg((-0.68, -0.58, base + 9.0), (-0.12, -0.78, base + 32.0), "yellowsteel", r=0.022)
    o.seg((-0.12, -0.78, base + 32.0), (-0.12, -0.78, base + 14.0), "black", r=0.006)
    o.seg((0.72, -0.62, base + 2), (1.02, -0.88, base + 22), "darksteel", r=0.016)
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
    elif p == 3:                                              # 碎礦廠（階梯狀工業廠房＋暗石板屋頂＋密閉輸送廊道）
        for k in range(3):
            hh = h * (0.90 - 0.23 * k)
            o.box((-0.48 + k * 0.48, 0.10, 0), (0.52, 1.08, hh), "corrugated" if k != 1 else "rust")
            windows(o, -0.48 + k * 0.48, 0.10, 0.52, 1.08, hh * 0.25, hh * 0.85, max(1, 3 - k), 2, m="glass")
            o.gable((-0.48 + k * 0.48, 0.10, hh), (0.56, 1.12, 5.5), "slate", "y")
            band(o, -0.48 + k * 0.48, 0.10, 0.52, 1.08, hh - 1.4, 1.2, "company", grow=0.04)
        o.seg((0.90, -0.78, 2), (0.04, -0.16, h * 0.66), "darksteel", r=0.048)
        o.seg((0.50, -0.48, 0), (0.50, -0.48, h * 0.34), "darksteel", r=0.018)
    elif p == 5:                                              # 礦石倉（深色鋼架＋漏斗＋鏽色倉體＋公司色飾帶）
        for dx in (-0.34, 0.34):
            for dy in (-0.34, 0.34):
                o.box((dx, dy, 0), (0.08, 0.08, 19), "darksteel")
        o.box((0, 0, 18), (0.94, 0.94, 22), "rust")
        band(o, 0, 0, 0.94, 0.94, 37.5, 2.0, "company", grow=0.04)
        o.gable((0, 0, 40), (0.98, 0.98, 7.0), "slate", "x")
        o.cyl((0, 0, 10), 0.28, 8, "darksteel", v=4, rt=0.45)
        o.seg((0.46, 0.46, 30), (0.96, 0.96, 4), "darksteel", r=0.042)
    elif p == 7:                                              # 豎井井架（1×1：深鋼桁架＋斜撐＋紅磚絞車房）
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.seg((dx * 0.21, dy * 0.21, 0), (dx * 0.09, dy * 0.09, h * 0.84), "darksteel", r=0.018)
        for k in range(1, 6):
            z = h * 0.84 * k / 6
            w = 0.21 - 0.12 * k / 6
            for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                o.seg((a[0] * w, a[1] * w, z), (b[0] * w, b[1] * w, z), "steel", r=0.010)
        o.box((0, 0, h * 0.82), (0.24, 0.24, 2.5), "company")
        for s in (-0.06, 0.06):                               # 天輪
            o.lathe((0, s, h * 0.90), [(0.13, -2), (0.14, 0), (0.13, 2)], "darksteel", seg=16)
        for dy in (-0.08, 0.08):
            o.seg((-0.34, dy, 12), (-0.06, dy, h * 0.84), "darksteel", r=0.016)
        o.box((-0.32, 0.24, 0), (0.34, 0.34, 14), "brick")
        o.gable((-0.32, 0.24, 14), (0.38, 0.38, 6), "slate", "x")
    elif p == 9:                                              # 機具棚（暗石板屋頂＋公司色簷口）
        shed(o, (0, 0), 1.2, 0.9, 18, wall="corrugated", roofm="slate", win=4)
        band(o, 0, 0, 1.2, 0.9, 16.8, 1.2, "company", grow=0.04)
    elif p == 11:                                             # 小工具房（1×1）
        shed(o, (0, 0), 0.5, 0.4, 12, wall="brick", roofm="slate", win=2)
    elif p == 13:                                             # 選礦廠（暗石板屋頂＋氣樓＋公司色簷口）+ 水槽
        shed(o, (-0.2, 0.2), 1.1, 0.9, 36, wall="corrugated", roofm="slate", win=5, rows=2)
        o.box((-0.2, 0.2, 46), (0.76, 0.24, 4.0), "darksteel")
        o.gable((-0.2, 0.2, 50), (0.80, 0.28, 3.5), "slate", "x")
        band(o, -0.2, 0.2, 1.1, 0.9, 34.4, 1.6, "company", grow=0.04)
        tank(o, (0.65, -0.6), 0.2, 16, "steel", top="flat")
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
    elif p == 1:                                              # 鋸木廠房（暗石板屋頂＋氣樓＋原木坡道＋鍋爐煙囪）
        shed(o, (-0.22, 0.22), 1.28, 0.82, 22, wall="wood", roofm="slate", win=5)
        o.box((-0.22, 0.22, 30), (0.86, 0.22, 4.0), "darkwood")
        o.gable((-0.22, 0.22, 34), (0.90, 0.26, 3.5), "slate", "x")
        o.box((-0.22, 0.22, 20.8), (1.30, 0.84, 1.1), "company")
        o.seg((0.88, -0.58, 1), (0.28, -0.08, 13), "darkwood", r=0.055)
        log_pile(o, (0.50, -0.64), 2, 4, 0.72, 0.032)
        chimney(o, (-0.78, 0.64), 0.055, 42, m="darksteel", top="darksteel")
    elif p == 3:                                              # 原木堆 + 鋼構吊車
        log_pile(o, (-0.30, 0.22), 3, 5, 1.12, 0.036)
        log_pile(o, (0.40, -0.48), 2, 4, 0.82, 0.032, along="y")
        o.box((0.68, 0.58, 0), (0.26, 0.26, 8.0), "darkwood")
        o.box((0.68, 0.58, 8.0), (0.22, 0.22, 5.5), "company")
        o.seg((0.68, 0.58, 13), (0.68, 0.58, h * 0.88), "darksteel", r=0.022)
        o.seg((0.68, 0.58, h * 0.88), (-0.12, 0.22, h * 0.68), "darksteel", r=0.018)
        o.seg((-0.12, 0.22, h * 0.68), (-0.12, 0.22, 16), "black", r=0.006)
    elif p == 5:                                              # 紅磚乾燥窯 + 雙排煙囪
        for k in range(3):
            o.box((-0.40 + k * 0.40, 0.20, 0), (0.35, 1.02, 16), "brick")
            o.gable((-0.40 + k * 0.40, 0.20, 16), (0.38, 1.06, 7), "slate", "y")
            face_box(o, -0.40 + k * 0.40, 0.20, 0.35, 1.02, "-y", 0, 0.22, 0, 11, "darksteel")
        chimney(o, (0.62, -0.62), 0.085, h, m="brick", top="darkstone", bands="company")
    elif p == 7:                                              # 大型木材倉庫（木瓦人字頂＋側遮雨棚，避免公司色白頂）
        shed(o, (0, 0.14), 1.56, 1.04, 30, wall="wood", roofm="shingle", win=6, rows=2)
        o.box((0, 0.14, 41), (1.0, 0.24, 3.6), "darkwood")
        o.gable((0, 0.14, 44.6), (1.04, 0.28, 3.0), "slate", "x")
        o.box((0, 0.14, 28.8), (1.58, 1.06, 1.2), "company")
        o.box((0, -0.52, 12.0), (1.36, 0.32, 1.2), "slate")   # 前側裝車遮雨棚
        for x in (-0.60, 0.0, 0.60):
            o.box((x, -0.64, 0), (0.04, 0.04, 12.0), "darkwood")
    elif p == 9:                                              # 板材堆＋防雨木棚
        for k in range(6):
            x, y = -0.58 + (k % 3) * 0.58, -0.38 + (k // 3) * 0.72
            for L in range(5):
                o.box((x, y, L * 2.8), (0.44, 0.28, 2.4), "planks" if L % 2 == 0 else "lightwood")
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
        o.cyl((0, 0, 0), 0.62, 0.4, "dirt", v=16)                                       # 磨坊周邊土路院場
        o.box((0.54, -0.48, 0), (0.44, 0.34, 9.5), "plaster")
        windows(o, 0.54, -0.48, 0.44, 0.34, 3, 8.5, 1, 2, m="glass")
        o.gable((0.54, -0.48, 9.5), (0.50, 0.40, 7.0), "thatch", "x")
        chimney(o, (0.68, -0.48), 0.032, 19.0, m="brick")
        for sx, sy in ((-0.46, -0.46), (-0.34, -0.54), (-0.52, -0.34)):                 # 穀物麻袋堆
            o.box((sx, sy, 0), (0.11, 0.08, 3.2), "hay")
        return o
    k = p - 1                                                 # 8 格：風帆轉動（四葉木格帆，每格 11.25°）
    body = h * 0.60
    o.cyl((0, 0, 0), 0.36, body * 0.24, "stone", v=16, rt=0.33)                         # 石砌基座
    o.cyl((0, 0, body * 0.24), 0.33, body * 0.76, "plaster", v=16, rt=0.22)             # 灰泥塔身
    # 八角形木造環台＋護欄
    gz = body * 0.24
    o.cyl((0, 0, gz), 0.44, 1.8, "darkwood", v=8)
    for a in range(8):
        a0, a1 = a * math.pi / 4, (a + 1) * math.pi / 4
        o.seg((0.42 * math.cos(a0), 0.42 * math.sin(a0), gz + 1.8), (0.42 * math.cos(a0), 0.42 * math.sin(a0), gz + 5.0), "wood", r=0.014)
        o.seg((0.42 * math.cos(a0), 0.42 * math.sin(a0), gz + 4.8), (0.42 * math.cos(a1), 0.42 * math.sin(a1), gz + 4.8), "wood", r=0.014)
    face_box(o, 0, 0, 0.66, 0.66, "-y", 0, 0.14, 0, 10, "darkwood")
    windows(o, 0, 0, 0.46, 0.46, body * 0.36, body * 0.88, 2, 1, wf=0.28, sides=("-y", "-x", "+x"))
    # 深木船形帽頂＋轉向尾桿
    o.lathe((0, 0, body), [(0.25, 0), (0.24, 5), (0.18, 12), (0.09, 17), (0.0, 20)], "darkwood", seg=16)
    o.seg((0.0, 0.22, body + 6), (0.0, 0.48, body - 14), "wood", r=0.016)
    # 轉軸與四片寬木格帆架（含帆布條與縱橫木條，確保清晰辨識）
    hub = (0.0, -0.29, body + 7)
    o.seg((0.0, -0.20, body + 7), (0.0, -0.34, body + 7), "darkwood", r=0.036)
    for s in range(4):
        a = math.radians(45 + s * 90 + k * 11.25)
        L = 0.64
        ca, sa = math.cos(a), math.sin(a)
        nx, nz = -sa, ca
        tip = (hub[0] + L * ca, hub[1], hub[2] + L * TZ * sa)
        o.seg(hub, tip, "darkwood", r=0.018)                                            # 主帆桁
        w_sail = 0.145
        p0 = (hub[0] + 0.14 * ca + w_sail * nx, hub[1] - 0.015, hub[2] + (0.14 * sa + w_sail * nz) * TZ)
        p1 = (hub[0] + L * ca + w_sail * nx, hub[1] - 0.015, hub[2] + (L * sa + w_sail * nz) * TZ)
        o.seg(p0, p1, "wood", r=0.012)
        for idx in range(6):
            t = 0.18 + idx * 0.155
            bx = hub[0] + L * t * ca
            bz = hub[2] + L * t * TZ * sa
            o.seg((bx, hub[1] - 0.012, bz), (bx + w_sail * nx, hub[1] - 0.012, bz + w_sail * TZ * nz), "wood", r=0.011)
            mx = bx + 0.05 * L * ca
            mz = bz + 0.05 * L * TZ * sa
            o.seg((mx + 0.02 * nx, hub[1] - 0.018, mz + 0.02 * TZ * nz),
                  (mx + (w_sail - 0.01) * nx, hub[1] - 0.018, mz + (w_sail - 0.01) * TZ * nz), "cream", r=0.024)
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
