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


def shed(o, c, sx, sy, h, wall="corrugated", roofm="slate", kind="gable", along="x", win=0, rows=1, door=True):
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


def distill_column(o, c, r, h, m="silver", frame_m="darksteel", z=0):
    """寫實化工廠直筒式蒸餾／分餾塔（告別外星錐體造型）：
    等徑光滑銀灰／鋼製圓筒塔體＋球面頂蓋＋外圍四柱開放式鋼構鷹架、方型檢修走道與側邊回流立管。
    """
    x, y = c
    o.cyl((x, y, z), r * 1.24, 3.5, "stone", v=18)
    o.cyl((x, y, z + 3.5), r * 1.06, 5.0, frame_m, v=20)
    body_h = max(14.0, h - 12.0)
    o.cyl((x, y, z + 8.5), r, body_h, m, v=22)
    z_cap = z + 8.5 + body_h
    o.lathe((x, y, z_cap), [(r, 0), (r * 0.92, 2.2), (r * 0.70, 4.2), (r * 0.35, 5.5), (0.0, 6.0)], m, seg=20)
    o.cyl((x, y, z_cap + 5.5), r * 0.16, 4.0, frame_m, v=10)
    n_rings = max(2, int(body_h // 16))
    for k in range(1, n_rings + 1):
        zr = z + 8.5 + body_h * k / (n_rings + 1)
        o.cyl((x, y, zr), r * 1.03, 0.9, frame_m, v=20)
    fw = r * 1.32
    f_top = z + 8.5 + body_h * 0.92
    for dx in (-fw, fw):
        for dy in (-fw, fw):
            o.seg((x + dx, y + dy, z), (x + dx, y + dy, f_top), frame_m, r=0.015)
    n_decks = max(2, int(body_h // 22))
    for k in range(1, n_decks + 1):
        zd = z + 8.5 + body_h * (k / (n_decks + 0.6))
        o.box((x, y, zd), (fw * 2.15, fw * 2.15, 1.0), frame_m)
        for s in (-fw * 1.04, fw * 1.04):
            o.seg((x - fw * 1.04, y + s, zd + 3.0), (x + fw * 1.04, y + s, zd + 3.0), "steel", r=0.008)
            o.seg((x + s, y - fw * 1.04, zd + 3.0), (x + s, y + fw * 1.04, zd + 3.0), "steel", r=0.008)
    o.seg((x + r * 1.12, y, z + 10.0), (x + r * 1.12, y, z_cap + 2.0), "steel", r=0.022)
    o.seg((x + r * 1.12, y, z_cap + 2.0), (x, y, z_cap + 3.5), "steel", r=0.022)


def pipe_rack(o, p1, p2, z_h, mats=("silver", "steel", "rust")):
    """寫實化工廠高架鋼構管廊（H 型鋼門架＋3 根平行水平製程管線）。"""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-4:
        return
    nx, ny = -dy / L, dx / L
    n_bents = 3 if L > 0.7 else 2
    for i in range(n_bents):
        t = i / (n_bents - 1)
        bx, by = x1 + dx * t, y1 + dy * t
        for side in (-0.09, 0.09):
            o.seg((bx + nx * side, by + ny * side, 0), (bx + nx * side, by + ny * side, z_h + 1.5), "darksteel", r=0.015)
        o.seg((bx - nx * 0.11, by - ny * 0.11, z_h), (bx + nx * 0.11, by + ny * 0.11, z_h), "darksteel", r=0.016)
    for k, pm in enumerate(mats):
        off = (k - (len(mats) - 1) / 2.0) * 0.055
        o.seg((x1 + nx * off, y1 + ny * off, z_h + 1.4), (x2 + nx * off, y2 + ny * off, z_h + 1.4), pm, r=0.024)


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


def house(o, c, sx, sy, h, wall="plaster", roofm="slate", along="x", win=3):
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
            o.cyl((x, y, h * 0.42), 0.185, 1.4, "darksteel", v=18)
        pipe_bridge(o, (-0.20, -0.18, h * 0.54), (0.20, -0.18, h * 0.54), h * 0.66, r=0.032, m="copper")
        shed(o, (0.24, 0.24), 0.38, 0.34, 14, wall="brick", roofm="slate", win=2)
    return o


def chemworks(p, h, info):
    """寫實現代重型化工廠（銀白保溫鋁板＋風化鋼構鷹架＋高架平行管廊＋紅磚／混凝土廠房，
    全面捨棄怪異紫色與外星錐體儲槽，呈現真實石化／精細化工廠風貌）。
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
    if p == 1:                                                # 2×2 化工製程廠房＋直筒蒸餾塔＋潔白銀灰原料儲槽＋高架管廊
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.2, "stone", t=0.045)
        # 左後方：混凝土與深鋼框架化工反應廠房＋屋頂大型冷卻風扇箱
        o.box((-0.34, 0.36, 0), (1.14, 0.94, 6.0), "stone")
        o.box((-0.34, 0.36, 6.0), (1.10, 0.90, 23.0), "whiteconcrete")
        windows(o, -0.34, 0.36, 1.10, 0.90, 9.0, 26.5, 2, 5, m="blueglass", sills="stone")
        parapet(o, -0.34, 0.36, 1.14, 0.94, 29.0, 2.0, "darksteel", t=0.04)
        o.box((-0.34, 0.36, 28.8), (1.06, 0.86, 0.8), "darkconcrete")
        for fx in (-0.64, -0.34, -0.04):
            o.box((fx, 0.36, 29.6), (0.22, 0.38, 4.5), "steel")
            o.cyl((fx, 0.36, 34.1), 0.08, 1.8, "darksteel", v=12)
        # 右前方：直筒不鏽鋼蒸餾塔（附四柱鋼構鷹架與三層方型走道）
        distill_column(o, (0.50, -0.38), 0.17, h * 0.88, m="silver")
        # 側邊兩座乾淨平頂銀白／灰鋼化學原料儲槽（零紫色！）＋安全黃閥門管線
        riveted_tank(o, (0.54, 0.44), 0.25, 32.0, m="white", stair=True)
        riveted_tank(o, (-0.48, -0.48), 0.24, 26.0, m="silver", stair=False)
        # 三管平行高架管廊串聯廠房、儲槽與蒸餾塔
        pipe_rack(o, (-0.34, 0.02), (0.50, -0.38), 18.0, mats=("silver", "steel", "yellowsteel"))
        pipe_rack(o, (-0.48, -0.48), (0.50, -0.38), 14.0, mats=("silver", "rust", "steel"))
    elif p == 3:                                              # 2×2 多塔分餾精煉區＋高架管廊＋銀白霍頓球槽＋熱交換器群
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        # 三座錯落高度的標準直筒不鏽鋼／工業鋼分餾塔（附開放式結構鋼框與高空聯絡天橋）
        distill_column(o, (-0.44, -0.34), 0.18, h * 0.92, m="silver")
        distill_column(o, (0.42, -0.34), 0.16, h * 0.78, m="steel")
        distill_column(o, (0.44, 0.42), 0.14, h * 0.66, m="white")
        # 高空鋼構聯絡走道橋＋平行製程管廊
        pipe_rack(o, (-0.44, -0.34), (0.42, -0.34), 38.0, mats=("silver", "steel", "rust"))
        pipe_rack(o, (0.42, -0.34), (0.44, 0.42), 26.0, mats=("silver", "yellowsteel", "steel"))
        # 左後方大型銀白霍頓球形高壓槽
        heavy_sphere(o, (-0.42, 0.42), 0.34, 8.0, m="white")
        # 前緣雙排臥式銀灰管殼熱交換器組
        for k in range(2):
            o.seg((-0.34, -0.74 + k * 0.16, 7.5), (0.28, -0.74 + k * 0.16, 7.5), "silver", r=0.068)
            for xx in (-0.22, 0.16):
                o.box((xx, -0.74 + k * 0.16, 0), (0.06, 0.12, 5.0), "stone")
    elif p == 5:                                              # 2×2 紅磚化驗控制中心＋高聳混凝土主煙囪＋氣體洗滌塔＋銀白儲罐
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.2, "stone", t=0.045)
        # 左後方：兩層紅磚＋切石飾帶化工控制與化驗中心
        o.box((-0.30, 0.34, 0), (1.22, 0.98, 6.0), "stone")
        o.box((-0.30, 0.34, 6.0), (1.18, 0.94, 26.0), "brick")
        windows(o, -0.30, 0.34, 1.18, 0.94, 9.0, 29.5, 2, 6, m="blueglass", sills="stone")
        band(o, -0.30, 0.34, 1.18, 0.94, 30.2, 1.6, "stone", grow=0.04)
        parapet(o, -0.30, 0.34, 1.22, 0.98, 32.0, 2.0, "stone", t=0.045)
        o.box((-0.30, 0.34, 31.6), (1.12, 0.88, 0.8), "darkconcrete")
        o.box((-0.52, 0.34, 32.4), (0.46, 0.42, 4.5), "silver")
        # 右前方：高聳淺灰混凝土工業排氣煙囪（附暗鋼檢修環與紅白航空警示環）
        chimney(o, (0.50, -0.46), 0.16, h, m="whiteconcrete", top="darksteel", bands="rust")
        for zf in (0.38, 0.68):
            o.cyl((0.50, -0.46, h * zf), 0.22, 1.3, "darksteel", v=16)
        # 前左方直筒鋼製氣體洗滌塔＋粗排氣導管通往主煙囪
        distill_column(o, (-0.44, -0.46), 0.16, 68.0, m="steel")
        pipe_bridge(o, (-0.44, -0.46, 44.0), (0.50, -0.46, 44.0), 54.0, r=0.058, m="silver")
        # 右後方銀白平頂化學儲槽＋管廊
        riveted_tank(o, (0.56, 0.44), 0.24, 34.0, m="white", stair=False)
        pipe_rack(o, (0.56, 0.44), (0.14, 0.34), 18.0, mats=("silver", "steel", "yellowsteel"))
    elif p == 7:                                              # 1×1 潔白銀灰霍頓球形高壓儲槽（填滿 1×1 混凝土圍堰）
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.8, "stone", t=0.05)
        heavy_sphere(o, (0.0, 0.0), 0.36, 9.0, m="white")
        pipe(o, (-0.42, -0.34, 4.5), (0.42, -0.34, 4.5), "yellowsteel", r=0.028)
        pipe(o, (-0.42, -0.24, 4.5), (0.42, -0.24, 4.5), "silver", r=0.028)
    elif p == 9:                                              # 1×1 雙臥式銀白高壓子彈儲槽＋鋼構管匯門架（零紫色！）
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.4, "stone", t=0.045)
        for y in (-0.22, 0.18):
            for x in (-0.26, 0.26):
                o.box((x, y, 0), (0.08, 0.18, 6.0), "stone")
            o.seg((-0.38, y, 12.5), (0.38, y, 12.5), "white", r=0.145)
            o.cyl((-0.14, y, 16.5), 0.055, 3.0, "darksteel", v=10)
            o.cyl((0.14, y, 16.5), 0.055, 3.0, "yellowsteel", v=10)
        # 端側小型不鏽鋼計量泵房與高架匯流管架
        pipe_rack(o, (-0.34, -0.24), (-0.34, 0.20), 22.0, mats=("silver", "yellowsteel", "steel"))
        o.box((0.26, -0.02, 0), (0.28, 0.24, 8.5), "steel")
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
        o.cyl((wx, wy, zt + h * 0.10), 0.196, 1.6, "rust", v=20)
        # 側邊工業除塵旋風筒與管線
        o.cyl((0.70, 0.30, 12), 0.14, 16, "silver", v=14)
        o.cyl((0.70, 0.30, 4), 0.05, 8, "rust", v=14, rt=0.14)
        pipe_bridge(o, (0.70, 0.30, 24), (0.40, 0.30, 24), 30, r=0.036, m="steel")
    elif p == 3:                                              # 巨型重工業裝配大廠房＋外部扶壁＋雙重型紅磚高煙囪（煙霧由 smoke_fx.py 2D 覆寫）
        shed(o, (-0.18, 0.16), 1.48, 1.32, 46, wall="darkbrick", roofm="slate", kind="saw", win=8, rows=2)
        band(o, -0.18, 0.16, 1.48, 1.32, 44.2, 1.8, "stone", grow=0.04)
        for dx in (-0.72, -0.36, 0.0, 0.36):
            o.box((dx, -0.51, 0), (0.06, 0.06, 45), "stone")
        # 裝卸遮雨棚與捲門
        o.box((-0.18, -0.60, 12.0), (1.10, 0.24, 1.4), "darksteel")
        for dx in (-0.50, -0.18, 0.14):
            face_box(o, -0.18, 0.16, 1.48, 1.32, "-y", dx * 0.5, 0.22, 0, 11.0, "darksteel")
        # 雙重型紅磚主／副煙囪（主煙囪高度 126，頂部銜接 2D 黑煙）
        o.box((0.66, -0.58, 0), (0.38, 0.38, 16.0), "stone")
        chimney(o, (0.66, -0.58), 0.16, h * 1.18, m="brick", top="darkstone", bands="darkstone")
        o.box((0.66, -0.16, 0), (0.32, 0.32, 14.0), "stone")
        chimney(o, (0.66, -0.16), 0.13, h * 0.98, m="darkbrick", top="darkstone", bands="stone")
    else:                                                     # part 4..35 由 tools/gen/smoke_fx.py 2D 流體黑煙覆寫
        o.cyl((0.66, -0.58, 0), 0.06, 2.0, "darksteel", v=8)
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
        if p == 1:                                            # 2×2 滿格 L 型石砌白牆農莊主屋＋庭院石矮牆＋副屋（h=32）
            house(o, (-0.18, 0.34), 1.32, 0.68, 17, wall="whitewash", roofm="slate", along="x", win=5)
            house(o, (0.48, -0.26), 0.64, 0.88, 15, wall="stone", roofm="thatch", along="y", win=3)
            # 庭院低矮石牆圍合＋門廊與草堆
            o.box((-0.44, -0.78, 0), (0.94, 0.08, 4.0), "stone")
            o.box((-0.86, -0.34, 0), (0.08, 0.94, 4.0), "stone")
            o.box((-0.56, -0.44, 0), (0.34, 0.24, 5.5), "hay")
        elif p == 3:                                          # 2×2 滿格寬大木石雙坡大穀倉＋側披屋＋乾草堆（h=24）
            o.box((0, 0.06, 0), (1.68, 1.14, 5.0), "stone")
            o.box((0, 0.06, 5.0), (1.64, 1.10, 11.0), "wood")
            o.gable((0, 0.06, 16.0), (1.74, 1.22, 13.0), "terracotta", "x")
            face_box(o, 0, 0.06, 1.64, 1.10, "-y", 0, 0.42, 0, 13.0, "darkwood")
            for dx in (-0.78, -0.39, 0.39, 0.78):
                o.box((dx, -0.50, 0), (0.06, 0.06, 15.5), "darkwood")
            o.box((-0.58, -0.72, 0), (0.44, 0.28, 6.0), "hay")
            o.box((0.56, -0.72, 0), (0.42, 0.26, 8.0), "lightwood")
        elif p == 5:                                          # 2×2 滿格開放式重木乾草大棚＋滿棚金黃乾草垛（h=33）
            for x in (-0.76, -0.25, 0.25, 0.76):
                for y in (-0.52, 0.52):
                    o.box((x, y, 0), (0.065, 0.065, 20.0), "darkwood")
                    o.seg((x, y, 13.0), (x, y * 0.62, 20.0), "darkwood", r=0.018)
            o.gable((0, 0, 20.0), (1.72, 1.26, 12.5), "corrugated", "x")
            for k in range(6):
                hx = -0.50 + (k % 3) * 0.50
                hy = -0.24 + (k // 3) * 0.48
                o.box((hx, hy, 0), (0.42, 0.38, 10.0 + (k % 2) * 4.5), "hay")
        elif p == 6:                                          # 2×2 滿格農機具棚＋拖拉機＋農用拖車（h=33）
            o.box((0.04, 0.20, 0), (1.62, 1.06, 18.0), "wood")
            o.gable((0.04, 0.20, 18.0), (1.70, 1.14, 12.0), "corrugated", "x")
            windows(o, 0.04, 0.20, 1.62, 1.06, 7, 16, 1, 5, sills="darkwood", sides=("+x", "-x", "+y"))
            for k in range(3):
                face_box(o, 0.04, 0.20, 1.62, 1.06, "-y", -0.30 + k * 0.30, 0.24, 0, 13.0, "darkwood")
            # 前方紅色農用拖拉機與木載車
            o.box((-0.44, -0.62, 2.0), (0.28, 0.16, 4.5), "red")
            o.box((-0.34, -0.62, 6.5), (0.14, 0.14, 4.5), "red")
            for dx in (-0.54, -0.34):
                o.seg((dx, -0.71, 2.5), (dx, -0.53, 2.5), "black", r=0.055)
            o.box((0.26, -0.62, 2.0), (0.48, 0.26, 4.5), "lightwood")
            o.box((0.26, -0.62, 6.5), (0.44, 0.22, 3.5), "hay")
        elif p == 8:                                          # 1×1 粗壯石磚混凝土圓筒大穀倉塔＋銀圓頂＋卸料槽（h=92）
            o.cyl((-0.04, 0.04, 0), 0.35, h * 0.80, "stone", v=22)
            for zf in (0.18, 0.36, 0.54, 0.72):
                o.cyl((-0.04, 0.04, h * zf), 0.362, 1.3, "darksteel", v=22)
            o.lathe((-0.04, 0.04, h * 0.80), [(0.36, 0), (0.34, 5), (0.25, 10), (0.11, 14), (0.0, 16)], "silver", seg=22)
            o.box((0.30, 0.04, 0), (0.14, 0.14, h * 0.78), "wood")
            o.box((0.26, -0.30, 0), (0.36, 0.28, 12.0), "wood")
            o.gable((0.26, -0.30, 12.0), (0.40, 0.32, 5.0), "slate", "x")
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
    band(o, -0.24, 0.14, 1.26, 1.08, 27.6, 1.4, "darkbrick", grow=0.04)
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
        o.cyl((0.64, sy, h * 0.44), 0.176, 1.2, "darksteel", v=18)
        pipe_bridge(o, (0.40, sy, 26), (0.64, sy, h * 0.66), h * 0.76, r=0.032, m="steel")
    # 裝卸月台與遮雨棚
    o.box((-0.24, -0.58, 0), (0.90, 0.36, 10.0), "brick")
    o.box((-0.24, -0.60, 10.0), (0.94, 0.40, 1.4), "slate")
    for dx in (-0.30, 0.0, 0.30):
        face_box(o, -0.24, -0.58, 0.90, 0.36, "-y", dx, 0.20, 0, 7.6, "darksteel")
    chimney(o, (-0.74, 0.64), 0.09, h * 0.84, m="brick", top="darkstone", bands="darkstone")
    return o


def forest(p, h, info):
    o = Ops()
    if p in (0, 2, 4):
        ground(o, 1, "dirt")
    elif p == 1:                                              # 1×1 滿格原木林務管理小屋＋前廊＋石煙囪＋木柴堆（h=26）
        o.box((0.0, 0.08, 0), (0.76, 0.56, 12.5), "logs")
        o.gable((0.0, 0.08, 12.5), (0.86, 0.68, 10.5), "shingle", "x")
        windows(o, 0.0, 0.08, 0.76, 0.56, 4.5, 10.5, 1, 3, sills="darkwood")
        face_box(o, 0.0, 0.08, 0.76, 0.56, "-y", 0, 0.16, 0, 8.5, "darkwood")
        o.box((0.0, -0.26, 8.0), (0.76, 0.18, 1.0), "darkwood")
        for dx in (-0.34, 0.0, 0.34):
            o.box((dx, -0.32, 0), (0.04, 0.04, 8.0), "darkwood")
        chimney(o, (0.24, 0.20), 0.055, 25.0, m="stone", top="darkstone")
        log_pile(o, (0.0, -0.40), 2, 4, 0.68, 0.028)
    elif p == 3:                                              # 1×1 重型原木裝車龍門吊架＋吊掛原木束＋儲木架（h=43）
        # 四柱斜撐重型木鋼龍門框架
        for x in (-0.36, 0.36):
            for y in (-0.28, 0.28):
                o.seg((x, y, 0), (x * 0.88, y * 0.78, 32.0), "darkwood", r=0.032)
            o.seg((x, -0.28, 4.0), (x, 0.28, 30.0), "darkwood", r=0.018)
            o.seg((x, 0.28, 4.0), (x, -0.28, 30.0), "darkwood", r=0.018)
        o.box((0, 0, 32.0), (0.86, 0.58, 2.2), "darksteel")
        o.box((0, 0, 34.2), (0.88, 0.24, 3.0), "yellowsteel")  # 頂部電動葫蘆主樑
        o.box((0.04, 0, 31.0), (0.18, 0.20, 4.5), "darksteel") # 吊車滑車
        for dx in (-0.12, 0.12):
            o.seg((dx, 0, 31.0), (dx, 0, 17.0), "black", r=0.008)
        # 懸吊中的原木束與地面整齊原木垛
        logs(o, (0, 0), 2, 0.62, 0.038, z=14.0, along="x")
        log_pile(o, (0, 0.04), 2, 4, 0.72, 0.034)
    elif p == 5:                                              # 1×1 木圍籬針葉樹苗圃（四排育苗床＋16 株翠綠雲杉幼苗，h=14）
        fence(o, 0, 0, 0.90, 0.90, h=3.2, m="wood")
        for iy in range(4):
            by = -0.30 + iy * 0.20
            o.box((0, by, 0), (0.76, 0.13, 1.5), "darkwood")
            for ix in range(4):
                bx = -0.27 + ix * 0.18
                sh = 7.5 + ((ix + iy) % 3) * 1.8
                o.cyl((bx, by, 1.5), 0.018, 2.0, "darkwood", v=6)
                o.cyl((bx, by, 3.0), 0.068, sh, "hedge", v=8, rt=0.008)
    return o


def oilrefinery(p, h, info, frame=0):
    """寫實現代重型煉油廠（標準等徑直筒分餾塔＋開放鋼構鷹架＋水平高架多管廊＋巨型鉚接原油儲槽，
    全面淘汰外星堆疊錐體造型，並維持 part 13 火炬噴口精準位於 (0,0,155) 銜接 2D 紊流火焰）。
    """
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
    if p == 1:                                                # 2×2 加氫脫硫與直筒分餾單元＋三管高架管廊＋紅磚泵房
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        distill_column(o, (-0.46, -0.38), 0.17, h * 0.96, m="silver")
        distill_column(o, (0.36, -0.42), 0.15, h * 0.82, m="steel")
        pipe_rack(o, (-0.46, -0.38), (0.36, -0.42), 24.0, mats=("silver", "steel", "rust"))
        # 臥式管殼熱交換器組＋紅磚控制泵房
        for k in range(2):
            o.seg((-0.70, 0.56 - k * 0.26, 9.5), (0.04, 0.56 - k * 0.26, 9.5), "silver", r=0.105)
            for xx in (-0.54, -0.08):
                o.box((xx, 0.56 - k * 0.26, 0), (0.08, 0.18, 6.0), "stone")
        shed(o, (0.48, 0.44), 0.78, 0.66, 20, wall="brick", roofm="darkconcrete", kind="flat", win=4)
        band(o, 0.48, 0.44, 0.78, 0.66, 18.6, 1.2, "stone", grow=0.04)
        pipe_rack(o, (-0.46, -0.10), (0.48, 0.44), 16.0, mats=("silver", "rust", "steel"))
    elif p == 3:                                              # 2×2 巨型風化鉚接原油儲槽（Shot 09 主體大儲槽！）
        parapet(o, 0, 0, 1.90, 1.90, 0, 3.0, "stone", t=0.055)
        riveted_tank(o, (-0.06, -0.06), 0.72, h * 0.84, m="steel", stair=True)
        o.box((0.68, 0.66, 0), (0.40, 0.34, 13.0), "brick")
        o.box((0.68, 0.66, 13.0), (0.42, 0.36, 1.2), "darkconcrete")
        pipe_bridge(o, (0.68, 0.66, 10), (0.38, 0.38, 10), 16, r=0.046, m="rust")
        pipe(o, (-0.82, 0.62, 5.0), (0.56, 0.62, 5.0), "darksteel", r=0.038)
    elif p == 5:                                              # 1×1 直筒真空分餾塔＋開放鋼構鷹架＋側邊再沸器
        parapet(o, 0, 0, 0.92, 0.92, 0, 2.2, "stone", t=0.045)
        distill_column(o, (-0.10, -0.08), 0.17, h * 0.94, m="silver")
        o.seg((0.18, 0.24, 9.0), (0.38, 0.24, 9.0), "steel", r=0.075)
        pipe_bridge(o, (-0.10, -0.08, 32), (0.28, 0.24, 14), 38, r=0.036, m="rust")
    elif p == 7:                                              # 2×2 巨型高壓液化氣霍頓球形儲槽區
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.055)
        heavy_sphere(o, (-0.40, -0.34), 0.42, 10.0, m="white")
        heavy_sphere(o, (0.44, 0.34), 0.38, 9.0, m="silver")
        pipe_rack(o, (-0.40, -0.34), (0.44, 0.34), 16.0, mats=("silver", "yellowsteel", "steel"))
        o.box((-0.56, 0.56, 0), (0.46, 0.38, 14.0), "brick")
        o.box((-0.56, 0.56, 14.0), (0.48, 0.40, 1.4), "darkconcrete")
    elif p == 9:                                              # 2×2 箱式管狀加熱爐＋雙排氣鋼煙囪＋直筒汽提塔＋高架管廊
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.6, "stone", t=0.05)
        # 典型煉油廠箱式管狀加熱爐（耐火磚鋼框爐體＋梯形集煙罩＋雙鋼煙囪）
        o.box((-0.26, 0.26, 0), (1.16, 0.88, 28.0), "steel")
        for dx in (-0.82, -0.45, -0.08, 0.28):
            o.box((dx, -0.19, 0), (0.06, 0.06, 28.0), "darksteel")
            o.box((dx, 0.71, 0), (0.06, 0.06, 28.0), "darksteel")
        o.hip((-0.26, 0.26, 28.0), (1.12, 0.84, 8.0), "darksteel", k=0.4)
        for k in range(2):
            chimney(o, (-0.54 + k * 0.56, 0.26), 0.11, h * 0.98, m="steel", top="darksteel", bands="rust")
        distill_column(o, (-0.50, -0.48), 0.16, h * 0.86, m="silver")
        pipe_rack(o, (-0.50, -0.48), (0.46, -0.44), 22.0, mats=("silver", "rust", "steel"))
        riveted_tank(o, (0.56, -0.46), 0.22, 28.0, m="steel", stair=False)
    elif p == 11:                                             # 1×1 主重型煙道高煙囪＋紅磚鍋爐間
        chimney(o, (-0.10, -0.10), 0.20, h, m="stone", top="darksteel", bands="darkbrick")
        o.box((0.24, 0.24, 0), (0.42, 0.40, 18), "brick")
        o.gable((0.24, 0.24, 18), (0.46, 0.44, 6), "slate", "x")
        pipe_bridge(o, (0.24, 0.24, 14), (-0.10, -0.10, 18), 24, r=0.056, m="rust")
    elif p == 13:                                             # 2×2 寫實流體催化裂解塔群＋中央鋼桁架火炬塔（頂端 (0,0,155) 接 2D 火焰）
        o.box((0, 0, 0), (1.84, 1.84, 3.2), "darkconcrete")
        parapet(o, 0, 0, 1.88, 1.88, 0, 4.4, "stone", t=0.05)
        # 中央標準等徑火炬立管＋四柱鋼桁架火炬塔（直達 z=155 火炬燃燒口，無外星錐體！）
        o.cyl((0, 0, 3), 0.11, h - 7.5, "darksteel", v=16, rt=0.085)
        o.cyl((0, 0, h - 4.5), 0.125, 4.5, "rust", v=16)                      # 火炬燃燒口 z=155
        for dx in (-0.22, 0.22):
            for dy in (-0.22, 0.22):
                o.seg((dx, dy, 3), (dx * 0.65, dy * 0.65, h - 12), "darksteel", r=0.020)
        for z_plat, pw in ((30, 0.48), (62, 0.42), (94, 0.36), (124, 0.30)):
            o.box((0, 0, z_plat), (pw, pw, 1.4), "darksteel")
            o.box((0, 0, z_plat + 3.0), (pw, pw, 0.5), "steel")
        # 三座真實直筒式裂解／再生／分餾主塔（配開放式結構鋼框）＋高空平行管廊
        distill_column(o, (-0.54, -0.40), 0.19, 114.0, m="silver", z=3)
        distill_column(o, (0.52, -0.38), 0.17, 98.0, m="steel", z=3)
        distill_column(o, (-0.42, 0.50), 0.16, 86.0, m="white", z=3)
        pipe_rack(o, (-0.54, -0.40), (0.52, -0.38), 54.0, mats=("silver", "rust", "steel"))
        pipe_rack(o, (-0.54, -0.40), (-0.42, 0.50), 40.0, mats=("silver", "steel", "rust"))
        pipe_bridge(o, (-0.54, -0.40, 78), (0, 0, 78), 88, r=0.048, m="rust")
        pipe_bridge(o, (0.52, -0.38, 66), (0, 0, 66), 76, r=0.044, m="steel")
        # 紅磚壓縮機房＋臥式冷凝分離鼓
        o.box((0.48, 0.50, 3), (0.68, 0.58, 26), "brick")
        o.box((0.48, 0.50, 29), (0.70, 0.60, 1.4), "darkconcrete")
        parapet(o, 0.48, 0.50, 0.70, 0.60, 28.8, 2.2, "stone", t=0.045)
        for k in range(2):
            o.seg((-0.36, -0.72 + k * 0.18, 12.5), (0.36, -0.72 + k * 0.18, 12.5), "silver", r=0.088)
    else:                                                     # 火焰 part 14..77 由 tools/gen/fire_fx.py 2D 流體模擬覆寫
        o.cyl((0, 0, 0), 0.06, 3.0, "darksteel", v=10)
    return o


def oilrig(p, h, info):
    o = Ops()
    deck = 36
    base = deck + 6
    # 四根粗大海上鋼構半潛主柱＋底浮筒＋密集斜交叉拉撐
    for x in (-0.64, 0.64):
        for y in (-0.64, 0.64):
            o.cyl((x, y, 0), 0.16, deck, "steel", v=16)
            o.cyl((x, y, 0), 0.20, 6.0, "darksteel", v=16)
            o.cyl((x, y, deck - 4), 0.19, 4.5, "darksteel", v=16)
    for (a, b) in (((-0.64, -0.64), (0.64, -0.64)), ((0.64, -0.64), (0.64, 0.64)),
                   ((0.64, 0.64), (-0.64, 0.64)), ((-0.64, 0.64), (-0.64, -0.64))):
        o.seg((a[0], a[1], 6), (b[0], b[1], deck - 4), "darksteel", r=0.032)
        o.seg((b[0], b[1], 6), (a[0], a[1], deck - 4), "darksteel", r=0.032)
        o.seg((a[0], a[1], 18), (b[0], b[1], 18), "steel", r=0.030)
        o.seg((a[0], a[1], deck - 2), (b[0], b[1], deck - 2), "darksteel", r=0.040)
    # 雙層厚重主甲板（格柵鋼底＋柏油工作甲板＋安全護欄）
    o.box((0, 0, deck), (1.76, 1.76, 5.5), "darksteel")
    o.box((0, 0, deck + 5.2), (1.68, 1.68, 0.8), "asphalt")
    for s in (-0.84, 0.84):
        o.seg((-0.84, s, base + 2.8), (0.84, s, base + 2.8), "silver", r=0.010)
        o.seg((s, -0.84, base + 2.8), (s, 0.84, base + 2.8), "silver", r=0.010)
    # 多層白色生活艙與控制中心（無公司色，使用白／淺灰鋼板＋深藍舷窗）
    o.box((-0.44, 0.36, base), (0.76, 0.72, 22.0), "white")
    windows(o, -0.44, 0.36, 0.76, 0.72, base + 3.0, base + 20.0, 3, 4, m="blueglass", wf=0.55)
    band(o, -0.44, 0.36, 0.76, 0.72, base + 20.5, 1.4, "darksteel", grow=0.03)
    o.box((-0.44, 0.36, base + 22.0), (0.72, 0.68, 1.2), "darkconcrete")
    # 懸挑八角直升機坪（白色 H 標線＋黃環）
    o.box((0.56, 0.56, base + 4.0), (0.62, 0.62, 1.8), "darksteel")
    o.seg((0.36, 0.36, deck + 2), (0.78, 0.78, base + 4.0), "steel", r=0.026)
    o.cyl((0.56, 0.56, base + 5.8), 0.27, 0.4, "yellowsteel", v=20)
    o.cyl((0.56, 0.56, base + 6.2), 0.23, 0.3, "asphalt", v=20)
    o.box((0.50, 0.56, base + 6.5), (0.035, 0.22, 0.25), "white")
    o.box((0.62, 0.56, base + 6.5), (0.035, 0.22, 0.25), "white")
    o.box((0.56, 0.56, base + 6.5), (0.14, 0.035, 0.25), "white")
    # 密集甲板製程區：雙大型鉚接油氣分離儲槽＋臥式冷凝器＋多條高壓管匯＋發電機房
    riveted_tank(o, (-0.54, -0.40), 0.21, 18.0, m="silver", z=base)
    riveted_tank(o, (-0.18, -0.54), 0.17, 15.0, m="steel", z=base)
    pipe_bridge(o, (-0.54, -0.40, base + 12), (-0.18, -0.54, base + 12), base + 20, r=0.032, m="rust")
    pipe_bridge(o, (-0.18, -0.54, base + 10), (0.20, -0.18, base + 14), base + 22, r=0.036, m="steel")
    o.box((0.56, -0.48, base), (0.44, 0.36, 14.0), "corrugated")
    o.box((0.56, -0.48, base + 14.0), (0.46, 0.38, 1.2), "darksteel")
    # 經典紅白相間重型鋼構鑽井塔（固定紅／白警示漆，非公司色！）＋寬鑽井平台＋天車
    top = h
    dx0, dy0 = 0.18, -0.14
    o.box((dx0, dy0, base), (0.64, 0.64, 8.0), "steel")
    o.box((dx0, dy0, base + 8.0), (0.68, 0.68, 1.6), "darksteel")
    d_bot = base + 9.5
    d_h = top - d_bot - 5.0
    nseg = 8
    for k in range(nseg):
        f0, f1 = k / nseg, (k + 1) / nseg
        z0, z1 = d_bot + d_h * f0, d_bot + d_h * f1
        w0 = 0.28 - 0.19 * f0
        w1 = 0.28 - 0.19 * f1
        cm = "red" if k % 2 == 0 else "white"
        for sx in (-1, 1):
            for sy in (-1, 1):
                o.seg((dx0 + sx * w0, dy0 + sy * w0, z0), (dx0 + sx * w1, dy0 + sy * w1, z1), cm, r=0.024)
        for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            o.seg((dx0 + a[0] * w1, dy0 + a[1] * w1, z1), (dx0 + b[0] * w1, dy0 + b[1] * w1, z1), cm, r=0.015)
            o.seg((dx0 + a[0] * w0, dy0 + a[1] * w0, z0), (dx0 + b[0] * w1, dy0 + b[1] * w1, z1), cm, r=0.012)
    o.box((dx0, dy0, top - 6.0), (0.24, 0.24, 2.0), "darksteel")
    o.box((dx0, dy0, top - 4.0), (0.18, 0.18, 4.0), "red")
    # 甲板重型格子吊臂起重機（警示黃＋深鋼）＋斜伸火炬臂
    o.cyl((-0.72, -0.66, base), 0.10, 8.0, "darksteel", v=12)
    o.box((-0.72, -0.66, base + 8.0), (0.24, 0.24, 7.0), "yellowsteel")
    o.seg((-0.72, -0.66, base + 11.0), (-0.06, -0.86, base + 42.0), "yellowsteel", r=0.028)
    o.seg((-0.06, -0.86, base + 42.0), (-0.06, -0.86, base + 18.0), "black", r=0.008)
    o.seg((0.76, -0.68, base + 4), (1.12, -0.96, base + 28), "rust", r=0.022)
    return o


def oilwell(p, h, info):
    o = Ops()
    if p in (0, 19):
        ground(o, 1, "dirt")
    elif p == 17:
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
    elif 1 <= p <= 16:                                        # 1×1 重型清晰磕頭抽油機（16 格，厚實 A 型架＋黃鋼遊梁驢頭＋圍欄基座）
        k = p - 1
        ang = math.radians(17) * math.sin(2 * math.pi * k / 16)
        o.box((0, 0, 0), (0.84, 0.44, 2.2), "concrete")
        fence(o, 0, 0, 0.90, 0.90, h=2.6, m="darksteel")
        # 粗壯 A 型支撐三腳鋼架（Samson Post）
        for dy in (-0.10, 0.10):
            o.seg((0.02, dy, 2.2), (0.0, dy * 0.35, 34.0), "darksteel", r=0.026)
            o.seg((-0.18, dy, 2.2), (0.0, dy * 0.35, 34.0), "darksteel", r=0.022)
        o.box((0.0, 0.0, 32.5), (0.14, 0.14, 3.0), "steel")
        # 厚重工業黃鋼遊梁（Walking Beam）＋弧形驢頭（Horsehead）
        L1, L2 = 0.42, 0.30
        piv = (0.0, 0.0, 35.0)
        head = (piv[0] + L1 * math.cos(ang), 0, piv[2] + L1 * TZ * math.sin(ang))
        tail = (piv[0] - L2 * math.cos(ang), 0, piv[2] - L2 * TZ * math.sin(ang))
        o.seg(tail, head, "yellowsteel", r=0.044)
        o.lathe((head[0], 0, head[2] - 8.5), [(0.0, 0), (0.08, 3), (0.10, 8), (0.08, 13), (0.0, 16)], "yellowsteel", seg=12)
        o.seg((head[0] + 0.06, 0, head[2] - 7), (0.44, 0, 3), "black", r=0.008)
        o.cyl((0.44, 0, 2.0), 0.07, 6.0, "darksteel", v=10)   # 井口採油樹
        # 旋轉大配重曲柄與馬達箱
        o.box((-0.28, 0, 2.2), (0.24, 0.26, 9.5), "darksteel")
        o.box((-0.44, 0, 2.2), (0.16, 0.18, 6.0), "steel")
        o.seg((tail[0], 0, tail[2]), (-0.28, 0, 11.0 + 4.0 * math.sin(ang * 3)), "steel", r=0.020)
    elif p == 18:                                             # 2×2 重型鉚接原油儲槽群＋圍堰＋螺旋梯＋泵房
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.05)
        riveted_tank(o, (-0.36, -0.34), 0.46, h * 0.72, m="steel", stair=True)
        riveted_tank(o, (0.42, 0.36), 0.38, h * 0.62, m="silver", stair=True)
        o.cyl((-0.36, -0.34, h * 0.42), 0.468, 1.8, "darksteel", v=24)
        pipe_bridge(o, (-0.36, -0.34, 8), (0.42, 0.36, 8), 14, r=0.042, m="rust")
        o.box((-0.62, 0.56, 0), (0.42, 0.34, 12.0), "corrugated")
        o.gable((-0.62, 0.56, 12.0), (0.46, 0.38, 4.5), "slate", "x")
    elif p == 20:                                             # 1×1 重型鋼構石油鑽井架＋高架黃鋼鑽台＋泥漿泵屋（h=133）
        # 高架鋼構鑽井底座平台
        o.box((0, 0, 0), (0.82, 0.82, 9.0), "darksteel")
        o.box((0, 0, 9.0), (0.86, 0.86, 1.8), "wood")
        # 粗壯四柱交叉桁架鑽塔（清楚可辨，不再細若蛛絲！）
        n_lvl = 9
        for k in range(n_lvl):
            f0, f1 = k / n_lvl, (k + 1) / n_lvl
            z0 = 10.5 + (h - 16.5) * f0
            z1 = 10.5 + (h - 16.5) * f1
            w0 = 0.32 - 0.22 * f0
            w1 = 0.32 - 0.22 * f1
            for sx in (-1, 1):
                for sy in (-1, 1):
                    o.seg((sx * w0, sy * w0, z0), (sx * w1, sy * w1, z1), "darksteel", r=0.026)
            for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
                o.seg((a[0] * w1, a[1] * w1, z1), (b[0] * w1, b[1] * w1, z1), "steel", r=0.015)
                o.seg((a[0] * w0, a[1] * w0, z0), (b[0] * w1, b[1] * w1, z1), "steel", r=0.012)
        # 中段醒目安全黃二層立管作業台（Monkeyboard）＋頂部天車架
        o.box((0, 0, h * 0.52), (0.44, 0.44, 14.0), "yellowsteel")
        o.box((0, 0, h - 7.0), (0.24, 0.24, 7.0), "yellowsteel")
        o.box((0.34, 0.32, 0), (0.30, 0.26, 11.0), "corrugated")
        o.gable((0.34, 0.32, 11.0), (0.34, 0.30, 4.0), "slate", "x")
    return o


def oremine(p, h, info):
    o = Ops()
    sizes = {0: 2, 2: 2, 4: 2, 6: 1, 8: 2, 10: 1, 12: 2, 14: 1}
    if p in sizes:
        if p in (8, 12):
            ground(o, sizes[p], "concrete")
            o.box((0, 0, 0), (1.86, 1.86, 0.35), "darkconcrete")
        else:
            ground(o, sizes[p], "ore")
        return o
    if p == 1:                                                # 2×2 選礦篩分站＋巨型赤鐵礦堆＋高架漏斗＋石磚管理房（h=38）
        # 前方巨型赤鐵礦堆（多峰層疊＋木枕擋土矮牆）
        o.cyl((-0.30, -0.32, 0), 0.56, 15.0, "ore", v=12, rt=0.14)
        o.cyl((0.18, -0.44, 0), 0.38, 10.5, "ore", v=10, rt=0.10)
        o.box((-0.30, -0.84, 0), (1.10, 0.08, 3.2), "darkwood")
        o.box((-0.84, -0.30, 0), (0.08, 0.96, 3.2), "darkwood")
        # 篩分高架鋼構漏斗（將礦石傾瀉到礦堆上）
        for dx in (-0.18, 0.18):
            for dy in (-0.18, 0.18):
                o.box((-0.26 + dx, -0.20 + dy, 0), (0.06, 0.06, 22.0), "darksteel")
        o.cyl((-0.26, -0.20, 16.0), 0.14, 7.0, "darksteel", v=4, rt=0.30)
        o.box((-0.26, -0.20, 23.0), (0.50, 0.50, 7.5), "rust")
        o.cyl((-0.26, -0.20, 30.5), 0.22, 3.5, "ore", v=8, rt=0.05)
        # 後方石磚篩分廠房＋鏽鐵屋頂＋斜輸送帶＋側邊木屋
        o.box((0.28, 0.42, 0), (1.06, 0.72, 20.0), "stone")
        windows(o, 0.28, 0.42, 1.06, 0.72, 5, 18, 1, 5, sills="darkstone")
        o.gable((0.28, 0.42, 20.0), (1.14, 0.80, 10.5), "rust", "x")
        chimney(o, (0.72, 0.66), 0.075, 36.0, m="brick", top="darkstone")
        o.seg((0.10, 0.36, 22.0), (-0.26, -0.20, 29.0), "darksteel", r=0.068)
        o.box((-0.62, 0.52, 0), (0.48, 0.44, 13.0), "wood")
        o.gable((-0.62, 0.52, 13.0), (0.52, 0.48, 6.0), "corrugated", "y")
    elif p == 3:                                              # 2×2 重型階梯碎礦廠＋木構斜棧橋＋粗輸送廊道（h=57）
        # 石砌基座＋階梯式木構／鏽鐵碎礦主樓（暖木＋鏽浪板＋石基座）
        o.box((-0.26, 0.22, 0), (1.26, 0.96, 12.0), "stone")
        o.box((-0.44, 0.22, 12.0), (0.72, 0.92, 32.0), "rust")
        o.gable((-0.44, 0.22, 44.0), (0.78, 0.98, 10.5), "corrugated", "y")
        windows(o, -0.44, 0.22, 0.72, 0.92, 15, 42, 2, 3, m="glass")
        o.box((0.18, 0.22, 12.0), (0.58, 0.92, 19.0), "wood")
        o.gable((0.18, 0.22, 31.0), (0.64, 0.98, 9.0), "rust", "y")
        windows(o, 0.18, 0.22, 0.58, 0.92, 15, 29, 1, 3, m="glass")
        # 側翼重型交叉木構斜棧橋＋高架礦車運道＋底部碎礦堆
        for k in range(4):
            bx = -0.18 + k * 0.32
            bh = 24.0 - k * 5.2
            o.box((bx, -0.48, 0), (0.06, 0.06, bh), "darkwood")
            o.box((bx, -0.76, 0), (0.06, 0.06, bh), "darkwood")
            o.seg((bx, -0.48, 1.5), (bx, -0.76, bh - 1.0), "darkwood", r=0.016)
            o.seg((bx, -0.76, 1.5), (bx, -0.48, bh - 1.0), "darkwood", r=0.016)
        o.seg((-0.34, -0.62, 27.0), (0.86, -0.62, 6.0), "wood", r=0.095)
        o.seg((-0.34, -0.26, 36.0), (0.78, -0.42, 10.0), "darksteel", r=0.065)
        o.cyl((0.68, -0.52, 0), 0.34, 8.5, "ore", v=10, rt=0.08)
    elif p == 5:                                              # 2×2 巨型寬幅礦石貯存大廠房＋雙排通風天窗＋外部扶壁（h=53）
        # 填滿 2×2 場地的宏偉木石貯礦大廳（暖赭石基座＋風化木牆＋寬大鏽鐵人字屋頂）
        o.box((0, 0.04, 0), (1.72, 1.32, 10.0), "stone")
        o.box((0, 0.04, 10.0), (1.66, 1.26, 20.0), "wood")
        windows(o, 0, 0.04, 1.66, 1.26, 13, 28, 1, 7, sills="darkwood")
        for dx in (-0.82, -0.41, 0.0, 0.41, 0.82):
            o.box((dx, -0.61, 0), (0.07, 0.08, 29.0), "darkwood")
            o.box((dx, 0.69, 0), (0.07, 0.08, 29.0), "darkwood")
        o.gable((0, 0.04, 30.0), (1.78, 1.38, 18.0), "rust", "x")
        o.box((0, 0.04, 45.0), (1.26, 0.30, 4.5), "darkwood")
        o.gable((0, 0.04, 49.5), (1.30, 0.34, 3.5), "corrugated", "x")
        # 前側裝車木棚與溢出礦堆
        o.box((-0.24, -0.74, 0), (0.64, 0.24, 11.0), "darkwood")
        o.cyl((0.52, -0.74, 0), 0.28, 7.0, "ore", v=10, rt=0.06)
    elif p == 7:                                              # 1×1 雙座重型紅磚焙燒高煙囪＋石砌煙道基座＋鋼構井口架（h=106）
        o.box((0, 0, 0), (0.82, 0.82, 14.0), "stone")
        o.box((0, 0, 14.0), (0.86, 0.86, 2.0), "darkstone")
        chimney(o, (-0.18, 0.16), 0.16, h, m="brick", top="darkstone", bands="darksteel")
        chimney(o, (0.20, -0.18), 0.14, h * 0.90, m="darkbrick", top="darkstone", bands="darksteel")
        pipe_bridge(o, (-0.18, 0.16, 36), (0.20, -0.18, 36), 44, r=0.055, m="rust")
        # 側邊小磚鍋爐間
        o.box((-0.20, -0.22, 14.0), (0.36, 0.34, 14.0), "brick")
        o.gable((-0.20, -0.22, 28.0), (0.40, 0.38, 5.5), "slate", "x")
    elif p == 9:                                              # 2×2 巨型肋骨暗鋼貯礦圓頂倉＋進料輸送橋＋地磅房（h=32）
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.4, "stone", t=0.045)
        # 巨型深鋼半球貯礦圓頂（佔滿 2×2 中央）＋放射狀外部加強鋼肋＋頂部進料塔
        cx, cy = -0.06, 0.06
        o.cyl((cx, cy, 0), 0.72, 4.0, "stone", v=24)
        prof = [
            (0.71, 4.0), (0.68, 9.0), (0.60, 15.0), (0.47, 20.5),
            (0.30, 25.0), (0.14, 27.5), (0.0, 28.5),
        ]
        o.lathe((cx, cy, 0), prof, "darksteel", seg=24)
        for k in range(8):
            a = k * math.pi / 4
            o.seg((cx + 0.71 * math.cos(a), cy + 0.71 * math.sin(a), 4.0),
                  (cx + 0.14 * math.cos(a), cy + 0.14 * math.sin(a), 27.5), "steel", r=0.022)
        o.cyl((cx, cy, 27.0), 0.18, 4.5, "rust", v=16)
        # 側邊進料緩衝筒倉＋傾斜輸送帶＋石造地磅室
        riveted_tank(o, (0.68, -0.58), 0.20, 18.0, m="rust", stair=False)
        o.seg((0.68, -0.58, 15.0), (cx, cy, 29.0), "steel", r=0.052)
        o.box((-0.66, -0.62, 0), (0.44, 0.36, 12.0), "stone")
        o.gable((-0.66, -0.62, 12.0), (0.48, 0.40, 5.0), "rust", "x")
    elif p == 11:                                             # 1×1 赤鐵礦原礦堆場＋木枕圍邊＋卸礦槽（h=21）
        o.cyl((0.0, 0.0, 0), 0.44, h * 0.90, "ore", v=12, rt=0.08)
        o.cyl((0.20, -0.18, 0), 0.24, h * 0.55, "ore", v=10, rt=0.05)
        o.box((0.0, -0.44, 0), (0.86, 0.06, 3.0), "darkwood")
        o.box((-0.44, 0.0, 0), (0.06, 0.86, 3.0), "darkwood")
        o.seg((-0.42, 0.36, 2.0), (-0.06, 0.04, h * 0.88), "darksteel", r=0.036)
    elif p == 13:                                             # 2×2 巨型選礦分級廠＋高架重型木鋼儲礦倉＋高空封閉輸送橋（h=61）
        # 左後方：赭石磚牆選礦主廠房（雙層＋氣樓＋高窗）
        o.box((-0.42, 0.34, 0), (0.98, 0.98, 34.0), "ochre")
        o.box((-0.42, 0.34, 0), (1.02, 1.02, 6.0), "stone")
        windows(o, -0.42, 0.34, 0.98, 0.98, 9, 31, 2, 4, sills="darkstone")
        o.gable((-0.42, 0.34, 34.0), (1.06, 1.06, 13.0), "rust", "x")
        o.box((-0.42, 0.34, 44.0), (0.64, 0.26, 4.5), "darkwood")
        o.gable((-0.42, 0.34, 48.5), (0.68, 0.30, 3.5), "corrugated", "x")
        # 右前方：高聳架空巨型木鋼裝車儲礦倉（重型交叉木柱＋四漏斗＋滿倉赤鐵礦）
        hx, hy = 0.46, -0.36
        for dx in (-0.34, 0.0, 0.34):
            for dy in (-0.34, 0.34):
                o.box((hx + dx, hy + dy, 0), (0.08, 0.08, 25.0), "darkwood")
        for dy in (-0.34, 0.34):
            o.seg((hx - 0.34, hy + dy, 1.5), (hx, hy + dy, 24.0), "darkwood", r=0.022)
            o.seg((hx + 0.34, hy + dy, 1.5), (hx, hy + dy, 24.0), "darkwood", r=0.022)
        o.cyl((hx, hy, 15.0), 0.22, 10.0, "darksteel", v=4, rt=0.44)
        o.box((hx, hy, 25.0), (0.86, 0.84, 24.0), "wood")
        for zb in (27.0, 33.0, 39.0, 45.0):
            band(o, hx, hy, 0.86, 0.84, zb, 1.2, "darksteel", grow=0.035)
        o.gable((hx, hy, 49.0), (0.92, 0.90, 9.5), "rust", "x")
        o.cyl((hx, hy, 0), 0.32, 6.5, "ore", v=10, rt=0.08)
        # 高空封閉式鋼構輸送廊道（連接選礦主廠房與高架儲礦倉）＋中間支撐鋼架
        o.seg((-0.34, 0.30, 36.0), (hx, hy, 42.0), "corrugated", r=0.145)
        o.seg((-0.34, 0.30, 32.5), (hx, hy, 38.5), "darksteel", r=0.036)
        o.box((0.04, -0.04, 0), (0.08, 0.08, 36.0), "darksteel")
        # 左前附屬石砌壓縮機房
        o.box((-0.56, -0.58, 0), (0.56, 0.44, 16.0), "stone")
        o.gable((-0.56, -0.58, 16.0), (0.60, 0.48, 6.5), "slate", "x")
    elif p == 15:                                             # 1×1 重型木格圍框高架裝礦漏斗倉（裝滿赤鐵礦，h=37）
        # 四角重木支柱＋X 型斜撐
        for dx in (-0.34, 0.34):
            for dy in (-0.34, 0.34):
                o.box((dx, dy, 0), (0.08, 0.08, 17.0), "darkwood")
        for s in (-0.34, 0.34):
            o.seg((-0.34, s, 1.5), (0.34, s, 16.0), "darkwood", r=0.020)
            o.seg((0.34, s, 1.5), (-0.34, s, 16.0), "darkwood", r=0.020)
            o.seg((s, -0.34, 1.5), (s, 0.34, 16.0), "darkwood", r=0.020)
            o.seg((s, 0.34, 1.5), (s, -0.34, 16.0), "darkwood", r=0.020)
        # 底部鋼製錐形下料口＋地面散落礦堆
        o.cyl((0, 0, 8.0), 0.16, 9.0, "darksteel", v=4, rt=0.38)
        o.cyl((0, 0, 0), 0.24, 4.5, "ore", v=10, rt=0.06)
        # 開放式木格裝礦斗（外部水平重木加固條＋四角鐵箍＋滿溢赤鐵礦堆）
        o.box((0, 0, 17.0), (0.82, 0.82, 13.0), "wood")
        for zb in (18.5, 22.5, 26.5, 29.2):
            band(o, 0, 0, 0.82, 0.82, zb, 1.1, "darkwood", grow=0.035)
        for dx in (-0.42, 0.42):
            for dy in (-0.42, 0.42):
                o.box((dx, dy, 17.0), (0.06, 0.06, 13.5), "darksteel")
        o.hip((0, 0, 29.5), (0.74, 0.74, 7.0), "ore", k=0.25)
    return o


def papermill(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "concrete")
        o.box((0, 0, 0), (1.88, 1.88, 0.35), "darkconcrete")
    elif p == 2:
        ground(o, 1, "concrete")
        o.box((0, 0, 0), (0.92, 0.92, 0.35), "darkconcrete")
    elif p == 1:                                              # 2×2 現代化大型造紙主廠房＋屋頂蒸氣排風罩＋雙不鏽鋼漂白塔＋巨捲原紙與原木堆（h=53）
        # 填滿場地的寬大淺灰混凝土＋紅磚基座造紙機廠房
        o.box((-0.06, 0.22, 0), (1.74, 1.02, 7.0), "stone")
        o.box((-0.06, 0.22, 7.0), (1.70, 0.98, 25.0), "whiteconcrete")
        windows(o, -0.06, 0.22, 1.70, 0.98, 10.0, 29.0, 2, 8, m="blueglass", sills="stone")
        for dx in (-0.84, -0.42, 0.0, 0.42, 0.78):
            o.box((dx - 0.04, -0.28, 0), (0.06, 0.06, 32.0), "stone")
            o.box((dx - 0.04, 0.72, 0), (0.06, 0.06, 32.0), "stone")
        parapet(o, -0.06, 0.22, 1.74, 1.02, 32.0, 2.4, "stone", t=0.05)
        o.box((-0.06, 0.22, 31.8), (1.64, 0.92, 1.0), "darkconcrete")
        # 屋頂 4 座大型不鏽鋼造紙乾燥排氣罩與連接風管
        for x in (-0.64, -0.24, 0.16, 0.56):
            o.box((x, 0.22, 33.0), (0.24, 0.44, 6.5), "silver")
            o.cyl((x, 0.22, 39.5), 0.075, 5.5, "steel", v=12)
        pipe(o, (-0.64, 0.42, 37.5), (0.56, 0.42, 37.5), "steel", r=0.042)
        # 前方銅綠斜雨遮裝卸月台＋巨型白色捲筒原紙棧板
        o.box((-0.26, -0.38, 10.5), (1.26, 0.28, 1.4), "copper")
        o.box((-0.26, -0.38, 0), (1.26, 0.26, 3.0), "stone")
        for k in range(4):
            rx = -0.70 + k * 0.24
            o.cyl((rx, -0.58, 0), 0.085, 6.5, "white", v=12)
            o.cyl((rx + 0.08, -0.74, 0), 0.08, 6.0, "cream", v=12)
        # 右前方雙座鉚接不鏽鋼紙漿漂白塔＋高架蒸氣管橋＋原木堆
        riveted_tank(o, (0.64, -0.56), 0.22, 42.0, m="silver", stair=True)
        riveted_tank(o, (0.22, -0.62), 0.16, 32.0, m="steel", stair=False)
        pipe_bridge(o, (0.64, -0.56, 30.0), (0.34, 0.22, 30.0), 40.0, r=0.048, m="silver")
        pipe_bridge(o, (0.64, -0.56, 24.0), (0.22, -0.62, 24.0), 34.0, r=0.036, m="rust")
        log_pile(o, (-0.54, -0.78), 2, 4, 0.72, 0.032)
    elif p == 3:                                              # 1×1 重型鍋爐動力間＋高聳磚混主煙囪＋不鏽鋼蒸煮吹放槽（h=92）
        # 填滿 1×1 基座的淺灰混凝土／紅磚鍋爐房
        o.box((-0.06, 0.08, 0), (0.82, 0.74, 24.0), "whiteconcrete")
        o.box((-0.06, 0.08, 0), (0.86, 0.78, 5.5), "stone")
        windows(o, -0.06, 0.08, 0.82, 0.74, 8, 22, 2, 3, m="blueglass", sills="stone")
        parapet(o, -0.06, 0.08, 0.84, 0.76, 24.0, 2.0, "stone", t=0.04)
        o.box((-0.06, 0.08, 23.6), (0.76, 0.68, 0.8), "darkconcrete")
        # 粗大磚混主煙囪（高度滿 h=92）＋不鏽鋼鉚接紙漿蒸煮塔＋粗蒸氣管橋
        chimney(o, (0.24, -0.22), 0.16, h, m="brick", top="darkstone", bands="stone")
        heavy_vessel(o, (-0.22, -0.22), 0.19, 54.0, m="silver", cap_m="steel", platforms=2, stair=False)
        pipe_bridge(o, (-0.22, -0.22, 34.0), (0.24, -0.22, 34.0), 44.0, r=0.044, m="rust")
    return o


def printworks(p, h, info):
    o = Ops()
    ground(o, 2, "pavement")
    if p == 0:                                                # 2×2 宏偉四層滿格古典石造印刷總部大樓＋孟薩爾石板頂＋天窗＋銅圓頂鐘樓（h=86）
        # 佔地 95% 滿格四層新古典切石／米白大樓（對齊原版厚重氣勢）
        o.box((0, 0, 0), (1.84, 1.78, 12.0), "stone")                                    # 一樓粗石基座
        o.box((0, 0, 12.0), (1.80, 1.74, 34.0), "cream")                                 # 二至四樓米白石牆
        # 三層密集多格窗戶＋層間石雕腰線＋外凸古典壁柱
        windows(o, 0, 0, 1.84, 1.78, 2.5, 10.5, 1, 8, m="darkstone", sills="stone")
        windows(o, 0, 0, 1.80, 1.74, 14.5, 44.0, 3, 8, m="glass", sills="stone")
        for zb in (11.5, 23.5, 34.5, 45.0):
            band(o, 0, 0, 1.82, 1.76, zb, 1.5, "stone", grow=0.04)
        for dx in (-0.88, -0.44, 0.0, 0.44, 0.88):
            o.box((dx, -0.88, 12.0), (0.08, 0.06, 34.0), "stone")
            o.box((dx, 0.88, 12.0), (0.08, 0.06, 34.0), "stone")
        for dy in (-0.44, 0.0, 0.44):
            o.box((-0.91, dy, 12.0), (0.06, 0.08, 34.0), "stone")
            o.box((0.91, dy, 12.0), (0.06, 0.08, 34.0), "stone")
        # 孟薩爾石板斜屋頂＋四周女兒牆＋雙排採光老虎天窗＋石磚雙煙囪
        parapet(o, 0, 0, 1.84, 1.78, 46.0, 2.6, "stone", t=0.05)
        o.hip((0, 0, 46.0), (1.78, 1.72, 14.0), "slate", k=0.62)
        for dy in (-0.34, 0.34):
            o.box((0, dy, 56.5), (1.10, 0.24, 4.2), "blueglass")
            o.gable((0, dy, 60.7), (1.14, 0.28, 3.0), "slate", "x")
        for dx in (-0.64, 0.64):
            chimney(o, (dx, 0.54), 0.09, 72.0, m="brick", top="stone")
        # 前方八角古典鐘塔＋銅綠圓頂（高度達 h=86）
        o.box((0, -0.68, 46.0), (0.44, 0.44, 22.0), "stone")
        band(o, 0, -0.68, 0.44, 0.44, 66.5, 1.8, "cream", grow=0.04)
        for side in SIDES:
            face_box(o, 0, -0.68, 0.44, 0.44, side, 0, 0.24, 52.0, 11.0, "white")
        o.lathe((0, -0.68, 68.0), [(0.24, 0), (0.23, 5), (0.18, 11), (0.08, 15), (0.0, 18)], "copper", seg=12)
    else:                                                     # 2×2 滿格兩層大型輪轉機印刷廠房＋三排採光天窗＋紙捲裝卸區（h=60）
        o.box((0, 0.04, 0), (1.84, 1.66, 9.0), "stone")
        o.box((0, 0.04, 9.0), (1.80, 1.62, 23.0), "ochre")
        windows(o, 0, 0.04, 1.80, 1.62, 11.5, 30.0, 2, 8, m="glass", sills="stone")
        for zb in (8.5, 20.5, 31.0):
            band(o, 0, 0.04, 1.82, 1.64, zb, 1.5, "stone", grow=0.04)
        for dx in (-0.88, -0.44, 0.0, 0.44, 0.88):
            o.box((dx, -0.78, 9.0), (0.07, 0.06, 23.0), "stone")
            o.box((dx, 0.86, 9.0), (0.07, 0.06, 23.0), "stone")
        # 寬大孟薩爾石板屋頂＋三排鋸齒／氣樓採光天窗（印刷車間必備採光）
        parapet(o, 0, 0.04, 1.84, 1.66, 32.0, 2.4, "stone", t=0.05)
        o.hip((0, 0.04, 32.0), (1.78, 1.60, 11.5), "slate", k=0.72)
        for dy in (-0.42, 0.04, 0.50):
            o.box((0, dy, 40.5), (1.28, 0.22, 4.2), "blueglass")
            o.gable((0, dy, 44.7), (1.32, 0.26, 2.8), "slate", "x")
        # 前側裝卸大門、遮雨棚與新聞紙捲＋配送貨車
        for k in range(3):
            face_box(o, 0, 0.04, 1.84, 1.66, "-y", -0.30 + k * 0.30, 0.22, 0, 8.2, "darksteel")
        o.box((0, -0.84, 8.8), (1.42, 0.18, 1.2), "darksteel")
        for k in range(3):
            o.cyl((-0.74 + k * 0.16, -0.88, 0), 0.065, 5.2, "white", v=10)
    return o


def sawmill(p, h, info):
    o = Ops()
    if p in (0, 2, 4, 6, 8):
        ground(o, 2, "dirt")
    elif p == 1:                                              # 2×2 明亮木板主鋸木廠房＋原木斜坡道＋巨型原木堆＋鍍鋅木屑筒倉（h=54）
        # 石砌基座＋明亮新裁原木板牆（lightwood／planks，告別暗褐色方塊）＋外露深木構架
        o.box((-0.18, 0.24, 0), (1.50, 0.96, 6.0), "stone")
        o.box((-0.18, 0.24, 6.0), (1.46, 0.92, 22.0), "lightwood")
        windows(o, -0.18, 0.24, 1.46, 0.92, 10, 26, 1, 6, sills="darkwood")
        for dx in (-0.88, -0.42, 0.04, 0.50):
            o.box((dx, -0.23, 0), (0.06, 0.06, 28.0), "darkwood")
            o.box((dx, 0.71, 0), (0.06, 0.06, 28.0), "darkwood")
        o.gable((-0.18, 0.24, 28.0), (1.58, 1.04, 14.0), "slate", "x")
        o.box((-0.18, 0.24, 39.0), (1.06, 0.28, 4.2), "planks")
        o.gable((-0.18, 0.24, 43.2), (1.10, 0.32, 3.2), "slate", "x")
        # 前側原木上料斜坡道＋大型整齊原木堆（鮮明木色對比）
        for dy in (-0.12, 0.12):
            o.seg((0.88, -0.56 + dy, 1.5), (0.28, -0.16 + dy, 16.0), "darkwood", r=0.042)
        o.seg((0.84, -0.56, 3.0), (0.30, -0.16, 17.5), "logs", r=0.065)
        log_pile(o, (-0.16, -0.62), 3, 5, 1.10, 0.040)
        # 側邊鍍鋅鉚接木屑旋風筒倉＋架空吸塵管＋鍋爐黑煙囪
        riveted_tank(o, (0.68, 0.56), 0.22, 34.0, m="silver", stair=False)
        pipe_bridge(o, (0.32, 0.26, 28.0), (0.68, 0.56, 30.0), 38.0, r=0.042, m="silver")
        chimney(o, (-0.78, 0.68), 0.08, 52.0, m="darksteel", top="darksteel")
    elif p == 3:                                              # 2×2 巨型開放式原木分選棚架＋堆疊鮮明板材原木＋重型黃鋼吊車（h=50）
        # 佔滿 85% 場地的大型開放木構棚架（深木立柱＋斜撐＋寬大波浪鐵頂）
        for x in (-0.78, -0.26, 0.26, 0.78):
            for y in (-0.42, 0.56):
                o.box((x, y, 0), (0.07, 0.07, 23.0), "darkwood")
                o.seg((x, y, 16.0), (x, y * 0.60, 23.0), "darkwood", r=0.020)
        o.gable((0.0, 0.07, 23.0), (1.72, 1.18, 12.5), "corrugated", "x")
        # 棚架內外堆滿明亮裁切板材與原木堆
        log_pile(o, (-0.36, 0.08), 3, 5, 0.88, 0.042)
        for k in range(4):
            px, py = 0.20 + (k % 2) * 0.42, -0.14 + (k // 2) * 0.42
            for L in range(5):
                o.box((px, py, L * 3.0), (0.36, 0.34, 2.5), "planks" if L % 2 == 0 else "lightwood")
        # 前方重型黃鋼旋臂吊木機
        o.box((0.68, -0.66, 0), (0.28, 0.28, 8.0), "stone")
        o.box((0.68, -0.66, 8.0), (0.24, 0.24, 6.0), "yellowsteel")
        o.seg((0.68, -0.66, 14.0), (0.68, -0.66, h * 0.88), "darksteel", r=0.026)
        o.seg((0.68, -0.66, h * 0.88), (-0.18, -0.46, h * 0.68), "yellowsteel", r=0.022)
        o.seg((-0.18, -0.46, h * 0.68), (-0.18, -0.46, 16.0), "black", r=0.008)
    elif p == 5:                                              # 2×2 明亮木板刨木車間＋屋頂雙鍍鋅旋風集塵塔＋紅磚鍋爐高煙囪（h=84）
        o.box((-0.14, 0.16, 0), (1.54, 1.16, 6.0), "stone")
        o.box((-0.14, 0.16, 6.0), (1.50, 1.12, 22.0), "planks")
        windows(o, -0.14, 0.16, 1.50, 1.12, 10, 25, 1, 6, sills="darkwood")
        o.gable((-0.14, 0.16, 28.0), (1.60, 1.22, 13.5), "slate", "x")
        # 屋頂雙座高架鍍鋅旋風集塵器＋吸塵風管（經典鋸木廠識別造型）
        for cx, cy, zc in ((-0.46, 0.16, 40.0), (0.04, 0.16, 44.0)):
            for dx in (-0.12, 0.12):
                for dy in (-0.12, 0.12):
                    o.seg((cx + dx, cy + dy, 32.0), (cx + dx * 0.8, cy + dy * 0.8, zc + 12.0), "darksteel", r=0.015)
            o.cyl((cx, cy, zc + 4.0), 0.05, 8.0, "silver", v=14, rt=0.17)
            o.cyl((cx, cy, zc + 12.0), 0.17, 13.0, "silver", v=16)
            o.cyl((cx, cy, zc + 25.0), 0.18, 2.5, "steel", v=16, rt=0.06)
        pipe_bridge(o, (-0.46, 0.16, 56.0), (0.04, 0.16, 58.0), 66.0, r=0.040, m="silver")
        # 側邊紅磚鍋爐房＋高聳紅磚煙囪（滿 h=84）＋前側木門雨遮
        o.box((0.64, -0.52, 0), (0.48, 0.44, 16.0), "brick")
        o.gable((0.64, -0.52, 16.0), (0.52, 0.48, 6.0), "slate", "x")
        chimney(o, (0.64, -0.62), 0.105, h, m="brick", top="darkstone", bands="stone")
        o.box((-0.24, -0.54, 11.0), (0.86, 0.28, 1.4), "darkwood")
    elif p == 7:                                              # 2×2 雙層開放式木板倉貯大穀倉（正面雙層可見滿滿金黃板材堆，h=66）
        o.box((0, 0.10, 0), (1.64, 1.24, 5.0), "stone")
        o.box((0, 0.10, 5.0), (1.60, 1.20, 34.0), "lightwood")
        windows(o, 0, 0.10, 1.60, 1.20, 10, 36, 2, 6, sills="darkwood", sides=("+x", "-x", "+y"))
        # 正面雙層開放式儲木貨格（深色內襯＋兩層金黃板材堆＋重木框架柱）
        face_box(o, 0, 0.10, 1.60, 1.20, "-y", 0, 1.40, 5.5, 31.0, "darkwood")
        for floor_z in (6.5, 22.0):
            o.box((0, -0.54, floor_z - 1.2), (1.56, 0.22, 1.6), "darkwood")
            for k in range(3):
                bx = -0.48 + k * 0.48
                for L in range(4):
                    o.box((bx, -0.54, floor_z + L * 2.9), (0.38, 0.26, 2.4), "planks" if L % 2 == 0 else "cream")
        for dx in (-0.78, -0.26, 0.26, 0.78):
            o.box((dx, -0.56, 5.0), (0.07, 0.08, 34.0), "darkwood")
        o.gable((0, 0.10, 39.0), (1.72, 1.34, 17.5), "slate", "x")
        o.box((0, 0.10, 53.0), (1.16, 0.30, 4.5), "darkwood")
        o.gable((0, 0.10, 57.5), (1.20, 0.34, 4.0), "slate", "x")
    elif p == 9:                                              # 2×2 重型斜撐外扶壁乾燥長木棚（經典斜木支撐＋滿棚金黃板材堆，h=46）
        # 兩側 10 根醒目外斜木扶壁支撐（對齊傳統重型乾燥棚建築特徵）
        for x in (-0.76, -0.38, 0.0, 0.38, 0.76):
            for sy in (-1, 1):
                o.box((x, sy * 0.52, 0), (0.065, 0.065, 24.0), "darkwood")
                o.seg((x, sy * 0.78, 0), (x, sy * 0.52, 23.0), "lightwood", r=0.028)
        o.gable((0, 0, 24.0), (1.76, 1.34, 14.0), "slate", "x")
        o.box((0, 0, 35.5), (1.42, 0.24, 3.2), "darkwood")
        o.gable((0, 0, 38.7), (1.46, 0.28, 2.6), "corrugated", "x")
        # 棚內整齊堆滿 3×2 六大疊鮮亮裁切木板
        for k in range(6):
            x, y = -0.52 + (k % 3) * 0.52, -0.24 + (k // 3) * 0.48
            for L in range(6):
                o.box((x, y, L * 3.1), (0.44, 0.36, 2.6), "planks" if L % 2 == 0 else "lightwood")
    return o


def skicentre(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "snow")
        o.box((0.42, -0.46, 0), (0.76, 0.58, 0.45), "pavement")
    elif p in (1, 2):                                         # 兩層阿爾卑斯木石滑雪小屋與環繞木陽台
        o.box((-0.14, 0.14, 0), (1.36, 1.02, h), "lightwood" if p == 2 else "stone")
        windows(o, -0.14, 0.14, 1.36, 1.02, h * 0.2, h * 0.88, 1, 6, sills="darkwood")
        if p == 2:
            o.box((-0.14, 0.14 - 0.56, 0.3), (1.32, 0.14, 0.9), "darkwood")
            o.box((-0.14, 0.14 - 0.60, 2.4), (1.32, 0.06, 1.4), "wood")
        if p == 1:
            face_box(o, -0.14, 0.14, 1.36, 1.02, "-y", 0, 0.24, 0, 8, "darkwood")
            for k in range(6):                                # 彩色滑雪板架（固定漆色，非公司色）
                o.box((0.58, -0.62 + k * 0.06, 0), (0.018, 0.018, 5.5), "red" if k % 2 == 0 else "chemblue")
    else:                                                     # 厚積雪深出簷阿爾卑斯山形斜屋頂（深木簷底＋厚雪被）
        o.gable((-0.14, 0.14, 0), (1.64, 1.28, h * 0.88), "darkwood", "x")
        o.gable((-0.14, 0.14, 1.8), (1.66, 1.30, h * 0.90), "snow", "x")
        chimney(o, (0.22, 0.26), 0.075, h * 0.95, m="stone", top="darkstone")
    return o


def steelmill(p, h, info):
    o = Ops()
    if p in (0, 4):
        ground(o, 2, "ore")
        return o
    if p in (2, 6, 9):
        ground(o, 1, "ore")
        return o
    if p == 1 or 10 <= p <= 16:                               # 2×2 滿格重型雙跨轉爐煉鋼大廠房；10–16 為倒鋼動畫格（h=86）
        k = 0 if p == 1 else p - 9
        # 滿格重鋼主跨（高天車廠房）＋側跨出鋼間
        o.box((-0.06, 0.16, 0), (1.76, 1.18, 52.0), "rust")
        o.box((-0.06, -0.58, 0), (1.76, 0.38, 30.0), "darksteel")
        o.gable((-0.06, 0.16, 52.0), (1.84, 1.26, 14.0), "corrugated", "x")
        o.box((-0.06, -0.58, 30.0), (1.80, 0.42, 2.0), "corrugated")
        # 密集外露重型 H 鋼扶壁柱＋貫穿式百葉排煙氣樓
        for dx in (-0.88, -0.44, 0.0, 0.44, 0.80):
            o.box((dx, -0.44, 0), (0.07, 0.07, 52.0), "darksteel")
            o.box((dx, 0.76, 0), (0.07, 0.07, 52.0), "darksteel")
        band(o, -0.06, 0.16, 1.76, 1.18, 50.0, 2.0, "darksteel", grow=0.04)
        o.box((-0.06, 0.16, 64.0), (1.44, 0.38, 9.0), "darksteel")
        o.gable((-0.06, 0.16, 73.0), (1.50, 0.44, 5.5), "rust", "x")
        for x in (-0.54, 0.42):
            chimney(o, (x, 0.58), 0.11, h * 0.98, m="steel", top="darksteel", bands="rust")
        door_glow = "glow" if k else "black"
        face_box(o, -0.06, -0.58, 1.76, 0.38, "-y", -0.15, 0.50, 0, 26, door_glow)
        face_box(o, -0.06, 0.16, 1.76, 1.18, "-x", 0.10, 0.48, 0, 34, door_glow)
        if k:
            tilt = min(k, 6) / 6
            o.lathe((-0.34, -0.78, 18), [(0.0, 0), (0.14, 1.5), (0.16, 9), (0.14, 14)], "darksteel", seg=14)
            o.seg((-0.34 + 0.1 * tilt, -0.78, 30), (-0.34 + 0.2 * tilt, -0.84, 4), "flame", r=0.028 + 0.026 * tilt)
            o.cyl((-0.18, -0.84, 0), 0.12 + 0.06 * tilt, 2.2, "glow", v=14)
    elif p == 3:                                              # 1×1 滿格重型鋼構礦石與助熔劑大儲倉（h=33）
        for dx in (-0.36, 0.36):
            for dy in (-0.36, 0.36):
                o.box((dx, dy, 0), (0.09, 0.09, 15.0), "darksteel")
        o.box((0, 0, 14.0), (0.90, 0.90, 14.0), "rust")
        band(o, 0, 0, 0.90, 0.90, 26.5, 1.8, "darksteel", grow=0.04)
        o.gable((0, 0, 28.0), (0.94, 0.94, 5.5), "corrugated", "x")
        o.cyl((0, 0, 6.0), 0.20, 8.0, "darksteel", v=4, rt=0.45)
    elif p == 5:                                              # 2×2 寫實直筒煉鐵高爐＋四柱重鋼頂架＋三座熱風爐＋下降管＋裝料斜橋（h=129）
        parapet(o, 0, 0, 1.88, 1.88, 0, 2.8, "stone", t=0.05)
        # 真實直筒／微收高爐本體（爐缸＋風口帶＋爐身＋四柱鋼構爐頂框架＋雙高爐放散管，告別外星錐體！）
        bx, by = -0.14, -0.06
        o.cyl((bx, by, 0), 0.38, 22.0, "darksteel", v=24)
        o.cyl((bx, by, 22.0), 0.36, 64.0, "rust", v=24, rt=0.28)
        o.cyl((bx, by, 86.0), 0.24, 18.0, "steel", v=20)
        # 四柱重型高爐外框鋼結構與 4 層方形檢修平台＋頂部天車架＋放散立管
        fw = 0.42
        for dx in (-fw, fw):
            for dy in (-fw, fw):
                o.seg((bx + dx, by + dy, 0), (bx + dx * 0.78, by + dy * 0.78, 108.0), "darksteel", r=0.026)
        for z_pl, pw in ((26, 0.90), (54, 0.84), (82, 0.76), (104, 0.68)):
            o.box((bx, by, z_pl), (pw, pw, 2.0), "darksteel")
            o.box((bx, by, z_pl + 3.5), (pw, pw, 0.7), "steel")
        o.box((bx, by, 106.0), (0.64, 0.64, 4.0), "darksteel")
        for sx in (-0.12, 0.12):
            o.cyl((bx + sx, by, 108.0), 0.055, 19.0, "steel", v=12)                   # 雙高爐頂部放散管
        # 三座巨型鉚接熱風爐（Cowper stoves）＋相連粗大熱風導管
        for k in range(3):
            sy = -0.58 + k * 0.38
            riveted_tank(o, (0.64, sy), 0.19, h * 0.56, m="steel", stair=(k == 1))
            pipe_bridge(o, (bx, by, h * 0.58), (0.64, sy, h * 0.50), h * 0.68, r=0.048, m="rust")
        # 粗大煤氣下降管（downcomer）＋旋風除塵器
        riveted_tank(o, (-0.64, 0.58), 0.22, h * 0.48, m="darksteel", stair=False)
        pipe_bridge(o, (bx, by, 98.0), (-0.64, 0.58, h * 0.46), 114.0, r=0.058, m="rust")
        # 雙軌桁架裝料斜橋（Skip Hoist Bridge）
        for off in (-0.06, 0.06):
            o.seg((-0.90 + off, -0.90 - off, 2), (bx + off, by - off, 102.0), "darksteel", r=0.032)
    elif p == 7:                                              # 1×1 重型雙煙囪＋石砌煙道基座（h=150）
        o.box((0, 0, 0), (0.80, 0.80, 12.0), "stone")
        chimney(o, (-0.16, -0.16), 0.15, h, m="darkbrick", top="darkstone", bands="steel")
        chimney(o, (0.20, 0.20), 0.13, h * 0.88, m="brick", top="darkstone", bands="darkstone")
    elif p == 8:                                              # 1×1 鋼捲與鋼胚料場＋跨軌黃鋼龍門吊車（h=20）
        # 雙側軌道梁與門型天車架
        for sy in (-0.38, 0.38):
            o.box((0, sy, 0), (0.88, 0.06, 1.5), "darksteel")
        for sx in (-0.34, 0.34):
            for sy in (-0.36, 0.36):
                o.box((sx, sy, 1.5), (0.05, 0.05, 16.0), "darksteel")
            o.box((sx, 0, 16.5), (0.07, 0.78, 2.2), "yellowsteel")
        o.box((0, 0, 17.5), (0.76, 0.16, 2.2), "yellowsteel")                         # 跨軌橋式主梁
        # 場內堆滿發亮銀灰鋼捲與厚鋼胚
        for k in range(3):
            o.seg((-0.26 + k * 0.24, -0.18, 4.5), (-0.26 + k * 0.24, -0.02, 4.5), "silver", r=0.085)
        for k in range(4):
            o.box((-0.24 + k * 0.16, 0.18, 0), (0.13, 0.24, 5.5), "steel")
    return o


def stockfarm(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "dirt")
        fence(o, 0, 0, 1.9, 1.9, h=2.8)
    elif p == 2:
        ground(o, 1, "dirt")
    elif p == 1:                                              # 2×2 滿格大型牧場牛舍＋石砌牧場農舍＋高聳青貯筒倉＋木圍欄（h=37）
        # 大型通風木造牛舍（填滿後半格）
        o.box((0.06, 0.34, 0), (1.66, 0.84, 15.0), "wood")
        o.gable((0.06, 0.34, 15.0), (1.74, 0.92, 12.0), "corrugated", "x")
        o.box((0.06, 0.34, 24.5), (1.10, 0.22, 3.5), "darkwood")
        o.gable((0.06, 0.34, 28.0), (1.14, 0.26, 2.8), "corrugated", "x")
        for k in range(6):
            face_box(o, 0.06, 0.34, 1.66, 0.84, "-y", -0.40 + k * 0.16, 0.10, 5.0, 4.0, "black")
        # 前左方寬大石砌牧場主屋＋前右方鍍鋅鉚接青貯筒倉＋草垛
        house(o, (-0.42, -0.46), 0.84, 0.58, 15, wall="stone", roofm="slate", win=3)
        riveted_tank(o, (0.64, -0.46), 0.22, 34.0, m="silver", stair=False)
        o.box((0.20, -0.58, 0), (0.36, 0.26, 6.0), "hay")
    elif p == 3:                                              # 1×1 木圍欄畜欄＋遮雨乾草飼料棚＋飲水槽（h=17）
        fence(o, 0, 0, 0.90, 0.90, h=3.2, m="wood")
        for x in (-0.34, 0.0, 0.34):
            for y in (-0.12, 0.32):
                o.box((x, y, 0), (0.05, 0.05, 11.0), "darkwood")
        o.gable((0, 0.10, 11.0), (0.82, 0.56, 6.0), "corrugated", "x")
        o.box((0, 0.34, 0), (0.76, 0.05, 8.0), "wood")
        o.box((0, 0.10, 0), (0.58, 0.30, 4.5), "hay")
        o.box((0, -0.28, 0), (0.48, 0.12, 2.8), "stone")                              # 石製飲水槽
    return o


def vineyard(p, h, info):
    o = Ops()
    if p == 0:
        ground(o, 2, "gravel")
        return o
    # 托斯卡尼赭石莊園別墅＋紅瓦屋頂＋鐘塔＋地中海絲柏樹列＋木酒桶
    o.box((-0.14, 0.22, 0), (1.28, 0.84, 21), "ochre")
    windows(o, -0.14, 0.22, 1.28, 0.84, 4, 19, 2, 6, sills="stone")
    o.hip((-0.14, 0.22, 21), (1.36, 0.92, 11.5), "terracotta", k=0.5)
    o.box((0.56, -0.42, 0), (0.34, 0.34, 31), "ochre")
    windows(o, 0.56, -0.42, 0.34, 0.34, 20, 29, 1, 1, sills="stone")
    o.hip((0.56, -0.42, 31), (0.40, 0.40, h - 31), "terracotta", k=0.0)
    # 庭院地中海絲柏樹列（尖錐深綠樹冠＋樹幹）
    for cx, cy, ch in ((-0.76, -0.42, 24), (-0.42, -0.58, 20), (-0.06, -0.64, 22), (0.28, -0.68, 18), (-0.80, 0.26, 22)):
        o.cyl((cx, cy, 0), 0.025, 4.0, "darkwood", v=8)
        o.cyl((cx, cy, 3.0), 0.095, ch * 0.45, "hedge", v=10, rt=0.08)
        o.cyl((cx, cy, 3.0 + ch * 0.45), 0.08, ch * 0.55, "hedge", v=10, rt=0.01)
    for k in range(5):
        o.seg((-0.66 + k * 0.13, -0.34, 2.4), (-0.66 + k * 0.13, -0.20, 2.4), "wood", r=0.044)
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
    elif p == 1:                                              # 2×2 滿格歐式石砌酒窖＋綠藤葡萄棚架＋雙層橡木酒桶堆（h=32）
        o.box((0, 0.26, 0), (1.66, 0.96, 20.0), "stone")
        windows(o, 0, 0.26, 1.66, 0.96, 5, 18, 1, 7, wf=0.32, sills="darkstone")
        o.gable((0, 0.26, 20.0), (1.76, 1.06, 11.5), "terracotta", "x")
        face_box(o, 0, 0.26, 1.66, 0.96, "-y", 0, 0.34, 0, 13.0, "darkwood")
        for x in (-0.78, -0.40, 0.40, 0.78):
            o.box((x, -0.24, 0), (0.09, 0.10, 19.5), "darkstone")
        # 前方覆滿翠綠葡萄藤的木造棚架＋雙層橡木桶陳列
        for x in (-0.70, -0.24, 0.24, 0.70):
            o.box((x, -0.74, 0), (0.05, 0.05, 12.0), "darkwood")
        o.box((0, -0.50, 12.0), (1.50, 0.56, 1.0), "darkwood")
        o.box((0, -0.50, 13.0), (1.54, 0.60, 2.2), "hedge")                           # 綠藤葡萄棚頂
        for k in range(7):
            o.seg((-0.66 + k * 0.16, -0.64, 3.0), (-0.66 + k * 0.16, -0.42, 3.0), "wood", r=0.056)
        for k in range(5):
            o.seg((-0.50 + k * 0.16, -0.64, 6.8), (-0.50 + k * 0.16, -0.42, 6.8), "wood", r=0.054)
    elif p == 3:                                              # 1×1 赭石釀造發酵室＋三座發亮不鏽鋼釀酒槽＋銅質壓榨管匯（h=40）
        o.box((0, 0.16, 0), (0.72, 0.54, 26.0), "ochre")
        o.hip((0, 0.16, 26.0), (0.80, 0.62, 10.0), "terracotta", k=0.45)
        windows(o, 0, 0.16, 0.72, 0.54, 6, 23, 2, 3, wf=0.34, sills="stone")
        riveted_tank(o, (-0.26, -0.28), 0.16, 22.0, m="silver")
        riveted_tank(o, (0.04, -0.32), 0.15, 20.0, m="silver")
        riveted_tank(o, (0.30, -0.26), 0.14, 18.0, m="copper")
        pipe_bridge(o, (-0.26, -0.28, 16), (0.30, -0.26, 16), 24, r=0.028, m="copper")
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
