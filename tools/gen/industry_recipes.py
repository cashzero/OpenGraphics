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


def spiral_stair(o, cx, cy, r, z0, z1, turns=1.35, steps=18, m="darksteel"):
    """繞在圓柱儲槽或高塔外壁的 3D 螺旋階梯與護欄支柱。"""
    pts = []
    for k in range(steps + 1):
        t = k / steps
        ang = t * turns * 2.0 * math.pi + 0.4
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang), z0 + (z1 - z0) * t))
    for k in range(steps):
        p0, p1 = pts[k], pts[k + 1]
        o.seg(p0, p1, m, r=0.016)
        o.seg((p0[0], p0[1], p0[2] + 3.2), (p1[0], p1[1], p1[2] + 3.2), m, r=0.010)
        if k % 2 == 0:
            o.seg(p0, (p0[0], p0[1], p0[2] + 3.2), m, r=0.009)


def pipe_bridge(o, a, b, z_top, r=0.055, m="rust"):
    """粗大高架拱形製程管橋（垂直上升 → 水平跨越 → 垂直下降，附法蘭接環）。"""
    ax, ay, az = a
    bx, by, bz = b
    o.seg((ax, ay, az), (ax, ay, z_top), m, r=r)
    o.seg((ax, ay, z_top), (bx, by, z_top), m, r=r)
    o.seg((bx, by, z_top), (bx, by, bz), m, r=r)
    o.cyl((ax, ay, z_top - 1.0), r * 1.28, 2.0, "darksteel", v=12)
    o.cyl((bx, by, z_top - 1.0), r * 1.28, 2.0, "darksteel", v=12)


def riveted_tank(o, c, r, h, m="steel", stair=True, z=0, band_m="darksteel"):
    """大型重工業鉚接鋼製儲槽：混凝土環基、加強肋環、微拱鋼頂＋放射肋＋頂緣護欄＋外壁螺旋梯。"""
    x, y = c
    o.cyl((x, y, z), r * 1.03, 2.2, "darkconcrete", v=24)
    o.cyl((x, y, z + 2.0), r, h - 2.0, m, v=24)
    # 水平補強肋環
    for frac in (0.28, 0.56, 0.84):
        o.cyl((x, y, z + h * frac), r * 1.022, 0.9, band_m, v=24)
    # 微拱頂蓋＋放射狀強化樑＋中央透氣閥座
    o.lathe((x, y, z + h), [(r, 0), (r * 0.72, 2.2), (r * 0.35, 3.6), (0.0, 4.2)], m, seg=24)
    o.cyl((x, y, z + h + 3.6), r * 0.14, 2.6, "darksteel", v=12)
    # 屋頂外緣安全護欄（環柱＋雙圈扶手）
    for k in range(12):
        a0 = k * 2.0 * math.pi / 12
        a1 = (k + 1) * 2.0 * math.pi / 12
        px0, py0 = x + r * 0.96 * math.cos(a0), y + r * 0.96 * math.sin(a0)
        px1, py1 = x + r * 0.96 * math.cos(a1), y + r * 0.96 * math.sin(a1)
        o.seg((px0, py0, z + h), (px0, py0, z + h + 3.2), "darksteel", r=0.010)
        o.seg((px0, py0, z + h + 3.0), (px1, py1, z + h + 3.0), "darksteel", r=0.010)
    if stair:
        spiral_stair(o, x, y, r * 1.045, z + 2.0, z + h + 1.0, turns=0.85, steps=16)


def heavy_vessel(o, c, r, h, m="steel", cap_m="silver", platforms=3, stair=True, z=0):
    """階梯狀重工業反應塔／分餾塔：寬裙座 → 縮徑主筒 → 壓力半球頂＋多層格柵平台與螺旋檢修梯。"""
    x, y = c
    o.cyl((x, y, z), r * 1.08, 3.0, "darkconcrete", v=20)
    h1 = h * 0.44
    h2 = h * 0.38
    h3 = max(6.0, h - h1 - h2 - r * 14)
    o.cyl((x, y, z + 3.0), r, h1, m, v=20)
    o.cyl((x, y, z + 3.0 + h1), r, 4.5, "darksteel", v=20, rt=r * 0.78)
    o.cyl((x, y, z + 7.5 + h1), r * 0.78, h2, cap_m, v=20)
    o.cyl((x, y, z + 7.5 + h1 + h2), r * 0.78, 3.5, "darksteel", v=18, rt=r * 0.56)
    o.cyl((x, y, z + 11.0 + h1 + h2), r * 0.56, h3, m, v=18)
    zt = z + 11.0 + h1 + h2 + h3
    o.lathe((x, y, zt), [(r * 0.56, 0), (r * 0.44, r * 10), (0.0, r * 15)], cap_m, seg=18)
    # 多層環形檢修平台＋護欄環
    for k in range(1, platforms + 1):
        zp = z + (h * 0.88) * k / (platforms + 1)
        rp = (r if zp < z + h1 + 5 else r * 0.78) * 1.28
        o.cyl((x, y, zp), rp, 1.0, "darksteel", v=16)
        o.cyl((x, y, zp + 2.6), rp * 0.99, 0.55, "steel", v=16)
    if stair:
        spiral_stair(o, x, y, r * 1.06, z + 3.0, z + h1 + h2 * 0.75, turns=1.1, steps=16)


def heavy_sphere(o, c, r, z, m="silver"):
    """大型霍頓球形高壓儲槽：6 根斜撐鋼柱＋X 字交叉拉桿＋赤道檢修環＋頂部閥座與旋梯。"""
    x, y = c
    zc = z + r * TZ
    leg_pts_b, leg_pts_t = [], []
    for a in range(6):
        ang = a * math.pi / 3
        pb = (x + r * 0.92 * math.cos(ang), y + r * 0.92 * math.sin(ang), 0)
        pt = (x + r * 0.88 * math.cos(ang), y + r * 0.88 * math.sin(ang), zc)
        leg_pts_b.append(pb)
        leg_pts_t.append(pt)
        o.seg(pb, pt, "darksteel", r=0.022)
    # 柱間交叉鋼構拉桿
    for a in range(6):
        a2 = (a + 1) % 6
        pm0 = tuple((leg_pts_b[a][i] + leg_pts_t[a][i]) * 0.5 for i in range(3))
        pm1 = tuple((leg_pts_b[a2][i] + leg_pts_t[a2][i]) * 0.5 for i in range(3))
        o.seg(leg_pts_b[a], pm1, "darksteel", r=0.011)
        o.seg(leg_pts_b[a2], pm0, "darksteel", r=0.011)
    # 高細分球體（8 段剖面，圓潤飽滿）
    prof = []
    for s in range(9):
        th = -math.pi / 2 + math.pi * s / 8
        prof.append((max(0.0, r * math.cos(th)), r * TZ * math.sin(th)))
    o.lathe((x, y, zc), prof, m, seg=24)
    # 赤道焊環＋檢修平台＋頂部壓力閥台＋攀登梯
    o.cyl((x, y, zc - 0.8), r * 1.04, 1.6, "darksteel", v=24)
    o.cyl((x, y, zc + r * TZ - 0.5), r * 0.28, 2.2, "darksteel", v=14)
    o.cyl((x, y, zc + r * TZ + 1.7), r * 0.34, 0.7, "steel", v=14)
    spiral_stair(o, x, y, r * 1.05, 0, zc + r * TZ * 0.55, turns=0.55, steps=12)


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
        ground(o, 2, "pavement")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
    elif p == 2:
        ground(o, 1, "pavement")
    elif p == 1:                                              # 維多利亞紅磚釀造主樓＋銅頂麥芽塔＋高煙囪＋銅管橋
        o.box((-0.18, 0.12, 0), (1.36, 1.06, 5.0), "stone")
        o.box((-0.18, 0.12, 5.0), (1.34, 1.04, 46.0), "brick")
        windows(o, -0.18, 0.12, 1.34, 1.04, 7, 48, 4, 6, sills="stone")
        band(o, -0.18, 0.12, 1.34, 1.04, 49.5, 1.6, "stone", grow=0.04)
        o2 = Ops()
        roof(o2, "gx", -0.18, 0.12, 1.34, 1.04, 16, "slate", over=0.04)
        for op in o2:
            op = dict(op)
            if "c" in op:
                op["c"] = [op["c"][0], op["c"][1], op["c"][2] + 51]
            o.append(op)
        # 屋脊銅綠糖化釜排氣圓頂
        o.cyl((-0.34, 0.12, 62), 0.18, 6.0, "copper", v=16)
        o.lathe((-0.34, 0.12, 68), [(0.18, 0), (0.14, 4), (0.0, 7)], "copper", seg=16)
        # 高聳麥芽烘乾塔樓＋石砌簷口＋銅綠尖頂
        o.box((0.40, -0.36, 0), (0.48, 0.48, 92), "brick")
        windows(o, 0.40, -0.36, 0.48, 0.48, 54, 90, 2, 2, sills="stone")
        band(o, 0.40, -0.36, 0.48, 0.48, 90.5, 2.0, "stone", grow=0.05)
        o.hip((0.40, -0.36, 92), (0.54, 0.54, 20), "copper", k=0.0)
        # 重型紅磚主煙囪＋外部銅製釀造管橋
        chimney(o, (-0.72, 0.64), 0.12, h, m="darkbrick", top="darkstone", bands="stone")
        pipe_bridge(o, (0.40, -0.36, 36), (-0.18, 0.12, 36), 46, r=0.042, m="copper")
        # 裝卸雨遮與堆疊橡木酒桶
        o.box((-0.18, -0.50, 11.0), (0.90, 0.24, 1.2), "slate")
        for k in range(6):
            o.cyl((0.68 + (k % 2) * 0.12, -0.82 + (k // 2) * 0.12, 0), 0.05, 5.5, "wood", v=10)
    elif p == 3:                                              # 1×1 不鏽鋼發酵槽群＋銅頂＋高架管匯
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.2, "stone", t=0.04)
        for (x, y) in ((-0.20, -0.18), (0.20, -0.18), (-0.20, 0.20)):
            riveted_tank(o, (x, y), 0.18, h * 0.66, m="silver", stair=False, z=0.5)
            o.cyl((x, y, h * 0.42), 0.185, 1.4, "company", v=18)
        pipe_bridge(o, (-0.20, -0.18, h * 0.54), (0.20, -0.18, h * 0.54), h * 0.66, r=0.032, m="copper")
        shed(o, (0.24, 0.24), 0.38, 0.34, 14, wall="brick", roofm="slate", win=2)
    return o


def chemworks(p, h, info):
    """重型化工廠（對齊原版 Shot 06 / Shot 10 的厚重工業體量與密度）：
    混凝土硬化地坪無縫銜接圍籬區，搭配巨型階梯反應塔、粗大拱形鏽鋼管橋、大型球形儲槽與深藍化學儲罐。
    """
    o = Ops()
    if p in (0, 2, 4):
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.4), "darkconcrete")
        return o
    if p in (6, 8):
        ground(o, 1, "concrete")
        o.box((0, 0, 0), (0.92, 0.92, 0.4), "darkconcrete")
        return o
    if p == 1:                                                # 2×2 重型反應器廠房＋巨型雙反應塔＋深藍化學罐＋粗大管橋
        # 佔地 85% 飽滿佈局：厚重浪板製程廠房＋高聳階梯鋼製反應塔
        shed(o, (-0.36, 0.36), 1.12, 0.98, 28, wall="corrugated", roofm="darkconcrete", kind="saw", win=5)
        band(o, -0.36, 0.36, 1.12, 0.98, 26.5, 1.4, "company", grow=0.04)
        heavy_vessel(o, (0.48, -0.40), 0.32, h * 0.86, m="steel", cap_m="silver", platforms=3, stair=True)
        heavy_vessel(o, (-0.42, -0.46), 0.25, h * 0.72, m="rust", cap_m="steel", platforms=2, stair=False)
        # 粗大拱形鏽鋼製程管橋串聯反應塔與廠房
        pipe_bridge(o, (0.48, -0.40, h * 0.56), (-0.42, -0.46, h * 0.50), h * 0.68, r=0.056, m="rust")
        pipe_bridge(o, (0.48, -0.40, 24), (-0.36, 0.36, 24), 34, r=0.052, m="steel")
        # 兩座鮮明工業深藍化學原料槽
        riveted_tank(o, (0.58, 0.44), 0.24, 34, m="chemblue", stair=False)
        riveted_tank(o, (0.14, 0.62), 0.16, 26, m="chemblue", stair=False)
    elif p == 3:                                              # 2×2 巨型合成蒸餾群＋球形高壓槽＋深藍壓力塔
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        heavy_vessel(o, (-0.42, -0.36), 0.34, h * 0.92, m="steel", cap_m="silver", platforms=4, stair=True)
        heavy_vessel(o, (0.42, -0.32), 0.28, h * 0.78, m="steel", cap_m="rust", platforms=3, stair=False)
        heavy_sphere(o, (-0.36, 0.44), 0.34, 8.0, m="silver")
        # 高聳深藍化學洗滌塔（立體螺旋鋼框）
        o.cyl((0.46, 0.44, 0), 0.22, h * 0.82, "chemblue", v=20)
        o.cyl((0.46, 0.44, h * 0.82), 0.22, 6.0, "darksteel", v=18, rt=0.14)
        spiral_stair(o, 0.46, 0.44, 0.24, 2.0, h * 0.78, turns=1.6, steps=18)
        # 粗大拱形管橋連接三座主設備
        pipe_bridge(o, (-0.42, -0.36, h * 0.62), (0.42, -0.32, h * 0.56), h * 0.74, r=0.062, m="rust")
        pipe_bridge(o, (0.42, -0.32, h * 0.48), (0.46, 0.44, h * 0.48), h * 0.60, r=0.054, m="rust")
        pipe_bridge(o, (-0.42, -0.36, 26), (-0.36, 0.44, 26), 34, r=0.048, m="steel")
    elif p == 5:                                              # 2×2 重型鍋爐與洗滌廠房＋巨型高煙囪＋雙藍儲槽
        shed(o, (-0.32, 0.32), 1.18, 1.02, 32, wall="brick", roofm="corrugated", kind="gable", win=5, rows=2)
        band(o, -0.32, 0.32, 1.18, 1.02, 29.5, 1.6, "company", grow=0.04)
        # 主重型工業煙囪＋鋼構檢修環台
        chimney(o, (0.50, -0.46), 0.17, h, m="darkbrick", top="darksteel", bands="steel")
        for zf in (0.35, 0.65):
            o.cyl((0.50, -0.46, h * zf), 0.23, 1.2, "darksteel", v=16)
        # 巨型鋼製洗滌反應罐＋粗大排氣管直通煙囪與鍋爐房
        heavy_vessel(o, (-0.42, -0.48), 0.30, 68, m="steel", cap_m="silver", platforms=3, stair=True)
        pipe_bridge(o, (-0.42, -0.48, 42), (0.50, -0.46, 42), 54, r=0.064, m="rust")
        pipe_bridge(o, (-0.42, -0.48, 22), (-0.32, 0.32, 22), 34, r=0.052, m="steel")
        riveted_tank(o, (0.54, 0.48), 0.24, 38, m="chemblue", stair=False)
    elif p == 7:                                              # 1×1 巨型霍頓球形高壓儲槽（填滿 1×1 圍堰）
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.8, "stone", t=0.05)
        heavy_sphere(o, (0.0, 0.0), 0.36, 9.0, m="silver")
        pipe(o, (-0.42, -0.34, 4.5), (0.42, -0.34, 4.5), "rust", r=0.032)
    elif p == 9:                                              # 1×1 重型雙臥式壓力槽＋深藍化學立罐
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.4, "stone", t=0.045)
        for y in (-0.22, 0.16):
            for x in (-0.26, 0.26):
                o.box((x, y, 0), (0.08, 0.18, 6.0), "stone")
            o.seg((-0.40, y, 12.5), (0.40, y, 12.5), "silver", r=0.145)
            o.cyl((0.0, y, 16.5), 0.08, 2.6, "darksteel", v=12)
        riveted_tank(o, (0.24, 0.34), 0.16, 26, m="chemblue", stair=False)
        pipe_bridge(o, (-0.34, -0.22, 12.5), (-0.34, 0.16, 12.5), 22, r=0.036, m="rust")
    return o


def factory(p, h, info, frame=0):
    o = Ops()
    if p in (0, 2):
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
    elif p == 1:                                              # 鋸齒屋頂主廠房＋辦公樓＋重型鉚接高架水塔＋除塵旋風筒
        shed(o, (-0.14, 0.16), 1.46, 1.24, 30, wall="brick", roofm="slate", kind="saw", win=7)
        band(o, -0.14, 0.16, 1.46, 1.24, 28.5, 1.5, "stone", grow=0.04)
        o.box((0.54, -0.68, 0), (0.76, 0.44, 26), "yellowbrick")
        windows(o, 0.54, -0.68, 0.76, 0.44, 3, 24, 2, 5, sills="stone")
        o.box((0.54, -0.68, 25.4), (0.70, 0.38, 1.0), "darkconcrete")
        parapet(o, 0.54, -0.68, 0.78, 0.46, 25.4, 2.2, "stone", t=0.04)
        # 重型交叉斜撐鋼構高架水塔（鉚接鋼槽）
        wx, wy = -0.68, -0.66
        zt = h * 0.66
        for dx in (-0.14, 0.14):
            for dy in (-0.14, 0.14):
                o.seg((wx + dx, wy + dy, 0), (wx + dx * 0.78, wy + dy * 0.78, zt), "darksteel", r=0.016)
        o.seg((wx - 0.14, wy - 0.14, 6), (wx + 0.14, wy - 0.14, zt - 6), "darksteel", r=0.009)
        o.seg((wx + 0.14, wy - 0.14, 6), (wx - 0.14, wy - 0.14, zt - 6), "darksteel", r=0.009)
        o.cyl((wx, wy, 0), 0.045, zt, "steel", v=10)          # 中央立管
        riveted_tank(o, (wx, wy), 0.19, h * 0.24, m="steel", stair=False, z=zt)
        o.cyl((wx, wy, zt + h * 0.10), 0.196, 1.6, "company", v=20)
        # 側邊工業除塵旋風筒與管線
        o.cyl((0.70, 0.30, 12), 0.14, 16, "silver", v=14)
        o.cyl((0.70, 0.30, 4), 0.05, 8, "rust", v=14, rt=0.14)
        pipe_bridge(o, (0.70, 0.30, 24), (0.40, 0.30, 24), 30, r=0.036, m="steel")
    elif p == 3:                                              # 巨型重工業裝配大廠房＋外部扶壁＋高煙囪下段
        shed(o, (-0.18, 0.16), 1.48, 1.32, 46, wall="darkbrick", roofm="slate", kind="saw", win=8, rows=2)
        band(o, -0.18, 0.16, 1.48, 1.32, 44.2, 1.8, "company", grow=0.04)
        for dx in (-0.72, -0.36, 0.0, 0.36):
            o.box((dx, -0.51, 0), (0.06, 0.06, 45), "stone")
        # 裝卸遮雨棚與捲門
        o.box((-0.18, -0.60, 12.0), (1.10, 0.24, 1.4), "darksteel")
        for dx in (-0.50, -0.18, 0.14):
            face_box(o, -0.18, 0.16, 1.48, 1.32, "-y", dx * 0.5, 0.22, 0, 11.0, "darksteel")
        o.box((0.66, -0.60, 0), (0.38, 0.38, 14.0), "stone")  # 煙囪石砌基座
        chimney(o, (0.66, -0.60), 0.17, h, m="brick", bands="darkstone")
    else:                                                     # 煙囪上段 + 32 格煙（疊在 part 3 上方）
        k = p - 4
        o.cyl((0.66, -0.60, 0), 0.13, 55, "brick", v=14, rt=0.10)
        o.cyl((0.66, -0.60, 53), 0.12, 2.5, "darkstone", v=14)
        smoke_puffs(o, (0.66, -0.60), 57, k, 32, n=5, rise=36, size=0.11)
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
        elif p in (5, 6):                                     # 鍍鋅鉚接金屬穀倉群＋架空穀物輸送管橋
            n = 3 if p == 5 else 2
            pts = []
            for k in range(n):
                ang = k * 2 * math.pi / n + 0.3
                r_c = 0.24 if p == 5 else 0.26
                cx, cy = r_c * math.cos(ang), r_c * math.sin(ang)
                pts.append((cx, cy))
                riveted_tank(o, (cx, cy), 0.20 if p == 5 else 0.24, h * 0.68, m="silver", stair=(k == 0))
            if len(pts) >= 2:
                pipe_bridge(o, (pts[0][0], pts[0][1], h * 0.64), (pts[1][0], pts[1][1], h * 0.64), h * 0.78, r=0.028, m="steel")
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
        o.box((0, 0, 0), (1.84, 1.84, 0.35), "darkconcrete")
        return o
    # 紅磚＋米色混凝土罐頭廠房（凹入深色屋頂＋雙排採光天窗＋屋頂冷卻機組）
    o.box((-0.24, 0.14, 0), (1.28, 1.10, 6.5), "brick")
    o.box((-0.24, 0.14, 6.5), (1.26, 1.08, 22.5), "cream")
    windows(o, -0.24, 0.14, 1.26, 1.08, 8.5, 27.0, 2, 6, sills="stone")
    for x in (-0.84, -0.44, -0.04, 0.36):
        o.box((x, -0.41, 0), (0.045, 0.045, 29.0), "stone")
        o.box((x, 0.69, 0), (0.045, 0.045, 29.0), "stone")
    band(o, -0.24, 0.14, 1.26, 1.08, 27.6, 1.4, "company", grow=0.04)
    parapet(o, -0.24, 0.14, 1.28, 1.10, 29.0, 2.2, "stone", t=0.05)
    o.box((-0.24, 0.14, 28.6), (1.18, 1.00, 0.9), "darkconcrete")
    for y in (-0.12, 0.36):
        o.box((-0.24, y, 29.5), (0.96, 0.24, 2.4), "blueglass")
        o.gable((-0.24, y, 31.9), (0.98, 0.28, 2.2), "slate", "x")
    riveted_tank(o, (-0.64, 0.44), 0.15, 7.5, m="steel", stair=False, z=29.5)
    # 三座厚重不鏽鋼鉚接原料筒倉＋架空輸送管橋與螺旋梯
    for k in range(3):
        sy = -0.60 + k * 0.40
        riveted_tank(o, (0.64, sy), 0.17, h * 0.72, m="silver", stair=(k == 1))
        o.cyl((0.64, sy, h * 0.44), 0.176, 1.2, "company", v=18)
        pipe_bridge(o, (0.40, sy, 26), (0.64, sy, h * 0.66), h * 0.76, r=0.032, m="steel")
    # 裝卸月台與遮雨棚
    o.box((-0.24, -0.58, 0), (0.90, 0.36, 10.0), "brick")
    o.box((-0.24, -0.60, 10.0), (0.94, 0.40, 1.4), "slate")
    for dx in (-0.30, 0.0, 0.30):
        face_box(o, -0.24, -0.58, 0.90, 0.36, "-y", dx, 0.20, 0, 7.6, "darksteel")
    chimney(o, (-0.74, 0.64), 0.09, h * 0.84, m="brick", top="darkstone", bands="company")
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
    """重型煉油廠（對齊原版 Shot 09 的巨型鉚接原油儲槽與高密度階梯催化裂解塔群）。"""
    o = Ops()
    g2, g1 = {0, 2, 6, 8, 12}, {4, 10}
    if p in g2:
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.4), "darkconcrete")
        return o
    if p in g1:
        ground(o, 1, "concrete")
        o.box((0, 0, 0), (0.92, 0.92, 0.4), "darkconcrete")
        return o
    if p == 1:                                                # 2×2 加氫脫硫與分餾製程群
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        heavy_vessel(o, (-0.46, -0.38), 0.28, h * 0.96, m="steel", cap_m="silver", platforms=3, stair=True)
        heavy_vessel(o, (0.38, -0.42), 0.24, h * 0.84, m="rust", cap_m="steel", platforms=3, stair=False)
        pipe_bridge(o, (-0.46, -0.38, h * 0.62), (0.38, -0.42, h * 0.58), h * 0.74, r=0.052, m="rust")
        # 臥式熱交換器滾筒＋紅磚控制泵房
        for k in range(2):
            o.seg((-0.70, 0.56 - k * 0.26, 9.5), (0.06, 0.56 - k * 0.26, 9.5), "silver", r=0.115)
            for xx in (-0.54, -0.08):
                o.box((xx, 0.56 - k * 0.26, 0), (0.08, 0.18, 6.0), "stone")
        shed(o, (0.48, 0.44), 0.78, 0.66, 20, wall="brick", roofm="darkconcrete", kind="flat", win=4)
        band(o, 0.48, 0.44, 0.78, 0.66, 18.6, 1.2, "company", grow=0.04)
        pipe_bridge(o, (-0.46, -0.38, 18), (0.48, 0.44, 18), 28, r=0.046, m="steel")
    elif p == 3:                                              # 2×2 巨型風化鉚接原油儲槽（Shot 09 主體大儲槽！）
        parapet(o, 0, 0, 1.90, 1.90, 0, 3.0, "stone", t=0.055)
        # 單座超巨型鉚接風化鋼製儲槽（r=0.72 填滿圍堰＋外壁螺旋梯＋頂緣護欄）＋側邊泵閥間與粗集油管
        riveted_tank(o, (-0.06, -0.06), 0.72, h * 0.84, m="steel", stair=True)
        o.box((0.68, 0.66, 0), (0.40, 0.34, 13.0), "brick")
        o.box((0.68, 0.66, 13.0), (0.42, 0.36, 1.2), "darkconcrete")
        pipe_bridge(o, (0.68, 0.66, 10), (0.38, 0.38, 10), 16, r=0.046, m="rust")
        pipe(o, (-0.82, 0.62, 5.0), (0.56, 0.62, 5.0), "darksteel", r=0.038)
    elif p == 5:                                              # 1×1 重型雙塔分餾單元
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.2, "stone", t=0.045)
        heavy_vessel(o, (-0.16, -0.14), 0.22, h * 0.92, m="steel", cap_m="silver", platforms=3, stair=True)
        heavy_vessel(o, (0.22, 0.18), 0.17, h * 0.76, m="rust", cap_m="steel", platforms=2, stair=False)
        pipe_bridge(o, (-0.16, -0.14, h * 0.62), (0.22, 0.18, h * 0.56), h * 0.74, r=0.042, m="rust")
    elif p == 7:                                              # 2×2 巨型高壓液化氣球形儲槽區
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.055)
        heavy_sphere(o, (-0.40, -0.34), 0.42, 10.0, m="silver")
        heavy_sphere(o, (0.44, 0.34), 0.38, 9.0, m="steel")
        pipe_bridge(o, (-0.40, -0.34, 16), (0.44, 0.34, 16), 24, r=0.046, m="rust")
        o.box((-0.56, 0.56, 0), (0.46, 0.38, 14.0), "brick")
        o.box((-0.56, 0.56, 14.0), (0.48, 0.40, 1.4), "darkconcrete")
    elif p == 9:                                              # 2×2 熱裂解加熱爐＋巨型塔器＋雙煙囪
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        shed(o, (-0.30, 0.26), 1.12, 0.92, 30, wall="rust", roofm="darkconcrete", kind="flat", win=4)
        band(o, -0.30, 0.26, 1.12, 0.92, 28.2, 1.5, "company", grow=0.04)
        for k in range(2):
            chimney(o, (0.50 + k * 0.28, -0.48), 0.11, h * 0.96, m="steel", top="darksteel", bands="rust")
        heavy_vessel(o, (-0.54, -0.52), 0.24, h * 0.88, m="steel", cap_m="silver", platforms=3, stair=True)
        pipe_bridge(o, (-0.54, -0.52, 30), (-0.30, 0.26, 30), 42, r=0.052, m="rust")
    elif p == 11:                                             # 1×1 主重型煙道高煙囪＋紅磚鍋爐間
        chimney(o, (-0.10, -0.10), 0.20, h, m="stone", top="darksteel", bands="darkbrick")
        o.box((0.24, 0.24, 0), (0.42, 0.40, 18), "brick")
        o.gable((0.24, 0.24, 18), (0.46, 0.44, 6), "slate", "x")
        pipe_bridge(o, (0.24, 0.24, 14), (-0.10, -0.10, 18), 24, r=0.056, m="rust")
    elif p == 13:                                             # 2×2 核心巨型催化裂解塔群＋高聳火炬塔（h=155，頂端接 2D 火焰）
        o.box((0, 0, 0), (1.84, 1.84, 3.2), "darkconcrete")
        parapet(o, 0, 0, 1.88, 1.88, 0, 4.4, "stone", t=0.05)
        # 中央巨型階梯式催化裂解主塔＋螺旋階梯＋直上 z=155 火炬燃燒口
        o.cyl((0, 0, 3), 0.34, 34, "steel", v=22)
        o.cyl((0, 0, 37), 0.34, 6.0, "darksteel", v=22, rt=0.26)
        o.cyl((0, 0, 43), 0.26, 54, "silver", v=22, rt=0.22)
        o.cyl((0, 0, 97), 0.22, 24, "rust", v=20, rt=0.13)
        o.cyl((0, 0, 121), 0.10, h - 121, "darksteel", v=16, rt=0.075)        # 火炬立管頂到 z=155
        o.cyl((0, 0, h - 4.5), 0.12, 4.5, "rust", v=16)                       # 火炬燃燒口
        # 重型四柱鋼構桁架＋5 層寬檢修平台＋螺旋階梯
        for dx in (-0.38, 0.38):
            for dy in (-0.38, 0.38):
                o.seg((dx, dy, 3), (dx * 0.72, dy * 0.72, 120), "darksteel", r=0.024)
        for z_plat, r_plat in ((32, 0.44), (58, 0.40), (84, 0.36), (106, 0.30), (130, 0.20)):
            o.cyl((0, 0, z_plat), r_plat, 1.4, "darksteel", v=18)
            o.cyl((0, 0, z_plat + 3.0), r_plat * 0.99, 0.65, "steel", v=18)
        spiral_stair(o, 0, 0, 0.36, 4.0, 96.0, turns=1.4, steps=22)
        # 三座厚重環繞副塔（大幅加粗體量）＋粗大拱形高架鋼管
        flank = ((-0.54, -0.40, 114, 0.25, "steel", "silver"),
                 (0.54, -0.36, 98, 0.22, "rust", "steel"),
                 (-0.40, 0.52, 86, 0.21, "steel", "rust"))
        for fx, fy, fh, fr, fmat, fcap in flank:
            heavy_vessel(o, (fx, fy), fr, fh, m=fmat, cap_m=fcap, platforms=3, stair=False, z=3)
            zm = fh * 0.70
            pipe_bridge(o, (fx, fy, zm), (0, 0, zm), zm + 14, r=0.052, m="rust" if fmat != "rust" else "steel")
            pipe(o, (fx, fy, zm * 0.44), (0, 0, zm * 0.44), "darksteel", r=0.042)
        # 紅磚壓縮機房＋粗大臥式冷凝器
        pipe_bridge(o, (-0.54, -0.40, 52), (0.54, -0.36, 52), 62, r=0.044, m="steel")
        o.box((0.48, 0.50, 3), (0.68, 0.58, 26), "brick")
        o.box((0.48, 0.50, 29), (0.70, 0.60, 1.4), "darkconcrete")
        parapet(o, 0.48, 0.50, 0.70, 0.60, 28.8, 2.2, "stone", t=0.045)
        for k in range(2):
            o.seg((-0.38, -0.70 + k * 0.20, 13), (0.36, -0.70 + k * 0.20, 13), "silver", r=0.095)
    else:                                                     # 火焰 part 14..77 由 tools/gen/fire_fx.py 2D 流體模擬覆寫
        k = p - 14
        o.cyl((0, 0, 0), 0.06, 3.0, "darksteel", v=10)
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
    riveted_tank(o, (-0.48, -0.34), 0.17, 14.0, m="silver", z=base)
    riveted_tank(o, (-0.16, -0.46), 0.14, 11.5, m="steel", z=base)
    pipe_bridge(o, (-0.48, -0.34, base + 9), (-0.16, -0.46, base + 9), base + 15, r=0.024, m="rust")
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
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
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
    elif p == 18:                                             # 2×2 重型鉚接原油儲槽群＋圍堰＋螺旋梯＋泵房
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.05)
        riveted_tank(o, (-0.36, -0.34), 0.46, h * 0.72, m="steel", stair=True)
        riveted_tank(o, (0.42, 0.36), 0.38, h * 0.62, m="silver", stair=True)
        o.cyl((-0.36, -0.34, h * 0.42), 0.468, 1.8, "company", v=24)
        pipe_bridge(o, (-0.36, -0.34, 8), (0.42, 0.36, 8), 14, r=0.042, m="rust")
        o.box((-0.62, 0.56, 0), (0.42, 0.34, 12.0), "corrugated")
        o.gable((-0.62, 0.56, 12.0), (0.46, 0.38, 4.5), "slate", "x")
    elif p == 20:                                             # 1×1 重型鑽井架＋泥漿泵屋＋鑽桿架
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.seg((dx * 0.27, dy * 0.27, 2), (dx * 0.055, dy * 0.055, h - 2), "darksteel", r=0.016)
        for k in range(1, 10):
            z = 2 + (h - 4) * k / 10
            w = 0.27 - 0.215 * k / 10
            for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                o.seg((a[0] * w, a[1] * w, z), (b[0] * w, b[1] * w, z), "steel", r=0.009)
        o.box((0, 0, h - 4), (0.14, 0.14, 4.0), "company")    # 天車頭
        o.box((0, 0, 0), (0.68, 0.68, 2.5), "wood")
        o.box((0.32, 0.30, 0), (0.28, 0.24, 9.0), "corrugated")
        o.gable((0.32, 0.30, 9.0), (0.30, 0.26, 3.0), "slate", "x")
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
    elif p == 13:                                             # 選礦廠（暗石板屋頂＋氣樓＋巨型濃縮槽＋漿料管橋）
        shed(o, (-0.24, 0.22), 1.16, 0.94, 38, wall="corrugated", roofm="slate", win=5, rows=2)
        o.box((-0.24, 0.22, 48), (0.80, 0.26, 4.5), "darksteel")
        o.gable((-0.24, 0.22, 52.5), (0.84, 0.30, 3.8), "slate", "x")
        band(o, -0.24, 0.22, 1.16, 0.94, 36.2, 1.6, "company", grow=0.04)
        riveted_tank(o, (0.58, -0.52), 0.32, 22, m="steel", stair=True)
        pipe_bridge(o, (-0.24, 0.22, 26), (0.58, -0.52, 20), 34, r=0.042, m="rust")
    elif p == 15:                                             # 礦石堆（1×1）
        o.hip((0, 0, 0), (0.8, 0.7, h * 0.6), "ore", k=0.3)
        o.seg((0.45, 0.45, 2), (0.0, 0.0, h * 0.7), "darksteel", r=0.03)
    return o


def papermill(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
    elif p == 2:
        ground(o, 1, "concrete")
        o.box((0, 0, 0), (0.92, 0.92, 0.35), "darkconcrete")
    elif p == 1:                                              # 2×2 巨型造紙機廠房＋大型紙漿儲槽＋蒸氣管橋＋原木堆場
        shed(o, (-0.12, 0.24), 1.60, 0.96, 30, wall="yellowbrick", roofm="slate", kind="gable", win=8, rows=2)
        band(o, -0.12, 0.24, 1.60, 0.96, 28.4, 1.6, "company", grow=0.04)
        for x in (-0.64, -0.12, 0.40):
            o.box((x, 0.24, 40), (0.18, 0.36, 7.0), "corrugated")
            o.cyl((x, 0.24, 47), 0.06, 4.0, "steel", v=10)
        # 側邊大型鉚接紙漿儲槽＋粗蒸氣管橋
        riveted_tank(o, (0.64, -0.56), 0.28, 34, m="steel", stair=True)
        pipe_bridge(o, (0.64, -0.56, 24), (0.36, 0.24, 24), 34, r=0.046, m="rust")
        log_pile(o, (-0.34, -0.62), 3, 5, 0.94, 0.036)
    elif p == 3:                                              # 1×1 重型階梯紙漿蒸煮塔＋高煙囪＋管橋
        heavy_vessel(o, (-0.18, 0.14), 0.23, h * 0.72, m="steel", cap_m="silver", platforms=3, stair=True)
        chimney(o, (0.24, -0.22), 0.12, h, m="brick", top="darkstone", bands="darkbrick")
        pipe_bridge(o, (-0.18, 0.14, h * 0.44), (0.24, -0.22, h * 0.44), h * 0.54, r=0.042, m="rust")
    return o


def printworks(p, h, info):
    o = Ops()
    ground(o, 2, "pavement")
    if p == 0:                                                # 紅磚維多利亞印刷主樓＋石砌基座＋鐘塔＋採光天窗
        o.box((0, 0.15, 0), (1.56, 1.06, 5.0), "stone")
        o.box((0, 0.15, 5.0), (1.52, 1.02, 37.0), "brick")
        windows(o, 0, 0.15, 1.52, 1.02, 7, 40, 3, 8, sills="stone")
        band(o, 0, 0.15, 1.52, 1.02, 40.5, 1.8, "stone", grow=0.04)
        o.hip((0, 0.15, 42), (1.56, 1.06, 14), "slate", k=0.52)
        o.box((0, 0.15, 53), (0.76, 0.28, 4.0), "blueglass")
        o.gable((0, 0.15, 57), (0.80, 0.32, 3.0), "slate", "x")
        o.box((0, -0.46, 0), (0.36, 0.36, 66), "brick")
        band(o, 0, -0.46, 0.36, 0.36, 64.5, 2.0, "stone", grow=0.05)
        for side in SIDES:
            face_box(o, 0, -0.46, 0.36, 0.36, side, 0, 0.22, 50, 10, "cream")
        o.hip((0, -0.46, 66), (0.40, 0.40, h - 66), "copper", k=0.0)
    else:                                                     # 深紅磚裝卸倉庫＋鋼構遮雨棚＋紙捲棧板與貨車
        shed(o, (0, 0.22), 1.62, 0.94, 32, wall="darkbrick", roofm="slate", win=8, rows=2)
        band(o, 0, 0.22, 1.62, 0.94, 30.2, 1.6, "company", grow=0.04)
        o.box((0, -0.34, 11.5), (1.54, 0.28, 1.2), "darksteel")
        for k in range(4):
            face_box(o, 0, 0.22, 1.62, 0.94, "-y", -0.35 + k * 0.23, 0.18, 0, 10.5, "darksteel")
        o.box((0, -0.32, 0), (1.56, 0.16, 3.2), "stone")
        for k in range(3):
            tx = -0.52 + k * 0.52
            o.box((tx, -0.68, 1.2), (0.26, 0.18, 6.8), "cream")
            o.box((tx, -0.82, 1.2), (0.22, 0.10, 5.2), "company")
    return o


def sawmill(p, h, info):
    o = Ops()
    if p in (0, 2, 4, 6, 8):
        ground(o, 2, "dirt")
    elif p == 1:                                              # 鋸木廠房（暗石板屋頂＋氣樓＋原木坡道＋木屑旋風筒倉＋鍋爐煙囪）
        shed(o, (-0.22, 0.22), 1.28, 0.84, 23, wall="wood", roofm="slate", win=5)
        o.box((-0.22, 0.22, 31), (0.86, 0.22, 4.0), "darkwood")
        o.gable((-0.22, 0.22, 35), (0.90, 0.26, 3.5), "slate", "x")
        o.box((-0.22, 0.22, 21.8), (1.30, 0.86, 1.1), "company")
        o.seg((0.88, -0.58, 1), (0.28, -0.08, 13), "darkwood", r=0.055)
        log_pile(o, (0.50, -0.64), 2, 4, 0.72, 0.032)
        riveted_tank(o, (0.64, 0.54), 0.20, 28, m="silver", stair=False)
        pipe_bridge(o, (0.28, 0.24, 24), (0.64, 0.54, 24), 32, r=0.034, m="steel")
        chimney(o, (-0.78, 0.64), 0.065, 44, m="darksteel", top="darksteel")
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
    if p == 1 or 10 <= p <= 16:                               # 2×2 重型轉爐煉鋼廠房；10–16 為倒鋼動畫格
        k = 0 if p == 1 else p - 9
        shed(o, (0, 0.12), 1.58, 1.18, 48, wall="rust", roofm="corrugated", win=0)
        # 外露重型鋼構扶壁柱與公司色簷口帶
        for dx in (-0.76, -0.38, 0.0, 0.38, 0.76):
            o.box((dx, -0.48, 0), (0.06, 0.06, 47), "darksteel")
            o.box((dx, 0.72, 0), (0.06, 0.06, 47), "darksteel")
        band(o, 0, 0.12, 1.58, 1.18, 45.8, 1.8, "company", grow=0.04)
        o.box((0, 0.12, 62), (1.16, 0.34, 7.5), "darksteel")  # 貫穿式屋頂排煙氣樓
        o.gable((0, 0.12, 69.5), (1.20, 0.38, 4.5), "rust", "x")
        for x in (-0.48, 0.48):
            chimney(o, (x, 0.56), 0.095, h * 0.98, m="steel", top="darksteel", bands="rust")
        door_glow = "glow" if k else "black"
        face_box(o, 0, 0.12, 1.58, 1.18, "-y", -0.15, 0.44, 0, 32, door_glow)
        face_box(o, 0, 0.12, 1.58, 1.18, "-x", 0.10, 0.44, 0, 32, door_glow)
        if k:
            tilt = min(k, 6) / 6
            o.lathe((-0.30, -0.58, 18), [(0.0, 0), (0.14, 1.5), (0.16, 9), (0.14, 14)], "darksteel", seg=14)
            o.seg((-0.30 + 0.1 * tilt, -0.58, 30), (-0.30 + 0.2 * tilt, -0.64, 4), "flame", r=0.025 + 0.025 * tilt)
            o.cyl((-0.14, -0.64, 0), 0.10 + 0.06 * tilt, 2.0, "glow", v=14)
    elif p == 3:                                              # 1×1 重型鋼構礦石倉＋漏斗＋輸送廊道
        for dx in (-0.30, 0.30):
            for dy in (-0.30, 0.30):
                o.box((dx, dy, 0), (0.08, 0.08, 16), "darksteel")
        o.box((0, 0, 15), (0.84, 0.84, 20), "rust")
        band(o, 0, 0, 0.84, 0.84, 33.5, 1.6, "company", grow=0.04)
        o.gable((0, 0, 35), (0.88, 0.88, 6.0), "corrugated", "x")
        o.cyl((0, 0, 7), 0.18, 8, "darksteel", v=4, rt=0.42)
    elif p == 5:                                              # 2×2 巨型高爐＋三座鉚接熱風爐＋粗大下降管橋＋螺旋梯＋裝料斜橋
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.05)
        heavy_vessel(o, (-0.12, -0.06), 0.40, h * 0.92, m="rust", cap_m="steel", platforms=4, stair=True)
        # 三座巨型鉚接熱風爐（Cowper stoves）＋相連粗大熱風導管
        for k in range(3):
            sy = -0.58 + k * 0.38
            riveted_tank(o, (0.64, sy), 0.19, h * 0.56, m="steel", stair=(k == 1))
            pipe_bridge(o, (-0.12, -0.06, h * 0.62), (0.64, sy, h * 0.50), h * 0.72, r=0.048, m="rust")
        # 高爐頂部粗大煤氣下降管（downcomer）＋除塵器
        riveted_tank(o, (-0.64, 0.58), 0.22, h * 0.48, m="darksteel", stair=False)
        pipe_bridge(o, (-0.12, -0.06, h * 0.82), (-0.64, 0.58, h * 0.46), h * 0.94, r=0.058, m="rust")
        # 雙軌桁架裝料斜橋
        for off in (-0.06, 0.06):
            o.seg((-0.90 + off, -0.90 - off, 2), (-0.14 + off, -0.14 - off, h * 0.82), "darksteel", r=0.032)
    elif p == 7:                                              # 1×1 重型雙煙囪＋石砌煙道基座
        o.box((0, 0, 0), (0.76, 0.76, 10.0), "stone")
        chimney(o, (-0.16, -0.16), 0.13, h, m="darkbrick", top="darkstone", bands="steel")
        chimney(o, (0.20, 0.20), 0.11, h * 0.88, m="brick", top="darkstone", bands="darkstone")
    elif p == 8:                                              # 1×1 鋼胚堆＋重型門架吊具
        for k in range(8):
            x, y = -0.26 + (k % 4) * 0.17, -0.16 + (k // 4) * 0.32
            o.box((x, y, (k // 4) * 3.2), (0.13, 0.26, 3.2), "steel")
        o.hip((0.20, 0.26, 0), (0.42, 0.32, h * 0.58), "darkstone", k=0.3)
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
    elif p == 1:                                              # 石造酒窖＋扶壁＋拱門遮棚＋橡木酒桶堆
        o.box((0, 0.22, 0), (1.48, 0.86, 20), "stone")
        windows(o, 0, 0.22, 1.48, 0.86, 5, 18, 1, 6, wf=0.3, sills="darkstone")
        o.gable((0, 0.22, 20), (1.56, 0.94, 11), "terracotta", "x")
        face_box(o, 0, 0.22, 1.48, 0.86, "-y", 0, 0.28, 0, 12, "darkwood")
        o.box((0, -0.30, 11.5), (0.58, 0.24, 1.4), "darkwood")
        for x in (-0.68, -0.34, 0.34, 0.68):
            o.box((x, -0.22, 0), (0.09, 0.10, 19), "darkstone")
        for k in range(6):
            o.seg((-0.62 + k * 0.15, -0.58, 2.8), (-0.62 + k * 0.15, -0.38, 2.8), "wood", r=0.052)
        for k in range(5):
            o.seg((-0.54 + k * 0.15, -0.58, 6.2), (-0.54 + k * 0.15, -0.38, 6.2), "wood", r=0.050)
    elif p == 3:                                              # 發酵槽塔（1×1：雙鉚接不鏽鋼發酵桶＋銅管橋＋石砌塔屋）
        o.box((0, 0.14, 0), (0.64, 0.52, 24), "ochre")
        o.hip((0, 0.14, 24), (0.70, 0.58, 9), "terracotta", k=0.4)
        windows(o, 0, 0.14, 0.64, 0.52, 6, 22, 2, 2, wf=0.32, sills="stone")
        riveted_tank(o, (-0.22, -0.30), 0.15, 18, m="silver")
        riveted_tank(o, (0.22, -0.30), 0.15, 18, m="silver")
        pipe_bridge(o, (-0.22, -0.30, 13), (0.22, -0.30, 13), 20, r=0.024, m="copper")
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
