#!/usr/bin/env python3
"""碼頭（SHIPST1）與機場（HPORT1、AIRPORT1–3）的幾何指令（給 tools/blender/models/ops.py + static_rig.py）。

每個 sprite set（部件）一份指令，單獨在 z = 0 渲染 × 4 旋轉；遊戲依「圖塊種類（variation）」把部件疊起來。
座標以 Loco 的「部件區域局部座標」撰寫（格為單位、佔地中心為原點；1×1 佔 [−0.5, 0.5]、2×2 佔 [−1, 1]，
高度為遊戲 px），輸出時轉成 Blender（bx = ly、by = −lx，與 static_rig 的相機一致）。
各圖塊的角色由模板的建築位置（tools/objinfo.py airport()["positions"]）與移動節點推得：
跑道沿世界 x、建築正面朝停機坪（世界 +y）。旋轉 r 的局部方向 d 在世界中為 rotate(d, r)
（r = 1：(x, y) → (y, −x)），所以：r = 1 的建築正面朝局部 −x、r = 3 朝局部 +x、r = 0 朝局部 +y。
"""
from __future__ import annotations

import math


class M:
    """以 Loco 局部座標收集 ops 指令。"""

    def __init__(self):
        self.ops = []

    def box(self, x0, x1, y0, y1, z0, z1, m):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if z1 - z0 <= 0 or x1 - x0 <= 0 or y1 - y0 <= 0:
            return
        self.ops.append({"op": "box", "c": [(y0 + y1) / 2, -(x0 + x1) / 2, z0], "s": [y1 - y0, x1 - x0, z1 - z0], "m": m})

    def cyl(self, x, y, z0, h, r, m, v=12, rt=None):
        op = {"op": "cyl", "c": [y, -x, z0], "r": r, "h": h, "m": m, "v": v}
        if rt is not None:
            op["rt"] = rt
        self.ops.append(op)

    def seg(self, a, b, r, m):
        self.ops.append({"op": "seg", "a": [a[1], -a[0], a[2]], "b": [b[1], -b[0], b[2]], "r": r, "m": m})

    def gable(self, x0, x1, y0, y1, z, h, m, ridge="x"):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        self.ops.append({"op": "gable", "c": [(y0 + y1) / 2, -(x0 + x1) / 2, z], "s": [y1 - y0, x1 - x0, h], "m": m,
                         "a": "y" if ridge == "x" else "x"})

    def hip(self, x0, x1, y0, y1, z, h, m, k=0.0):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        self.ops.append({"op": "hip", "c": [(y0 + y1) / 2, -(x0 + x1) / 2, z], "s": [y1 - y0, x1 - x0, h], "m": m, "k": k})

    def mark(self, x0, x1, y0, y1, m="white", z=1.0):
        self.box(x0, x1, y0, y1, z, z + 0.12, m)

    # ---- 常用組合
    def slab(self, half, m="concrete", z1=1.0):
        self.box(-half, half, -half, half, 0, z1, m)

    def band(self, x0, x1, y0, y1, z0, z1, m="blueglass", out=0.012):
        """窗帶：比牆稍大一圈的扁盒，四面都看得到。"""
        self.box(x0 - out, x1 + out, y0 - out, y1 + out, z0, z1, m)


# ---------------------------------------------------------------- 碼頭
def dock(part):
    g = M()
    if part == 0:                                             # 碼頭平台（h8）：混凝土岸壁、木護舷、繫船柱、貨箱
        g.box(-1, 1, -1, 1, 0, 6.5, "darkstone")
        g.box(-0.98, 0.98, -0.98, 0.98, 6.5, 7.5, "quay")
        for y in (-0.8, -0.4, 0.0, 0.4, 0.8):                 # 水側（局部 +x）的護舷木
            g.box(0.98, 1.02, y - 0.06, y + 0.06, 1.0, 7.0, "darkwood")
        for y in (-0.7, 0.0, 0.7):
            g.cyl(0.9, y, 7.5, 1.6, 0.035, "darksteel", v=8)
        g.mark(-0.98, 0.98, 0.93, 0.97, "yellowsteel", z=7.5)
        for (x, y, m) in ((0.35, 0.55, "company"), (0.55, 0.55, "planks"), (0.45, 0.75, "company2")):
            g.box(x - 0.08, x + 0.08, y - 0.08, y + 0.08, 7.5, 10.5, m)
    else:                                                     # 倉庫（局部 −x 半邊）＋門式起重機（h40）
        g.box(-0.95, -0.1, -0.9, 0.9, 0, 22, "brick")
        g.gable(-0.97, -0.08, -0.92, 0.92, 22, 10, "corrugated", ridge="y")
        for y in (-0.55, 0.0, 0.55):                          # 朝水側的大門
            g.box(-0.1, -0.08, y - 0.17, y + 0.17, 0, 13, "darkwood")
        g.band(-0.95, -0.1, -0.9, 0.9, 15, 17, "company", out=0.01)
        # 起重機：兩支腳 + 橫樑 + 吊臂
        for y in (-0.45, 0.25):
            for x in (0.33, 0.8):
                g.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0, 30, "yellowsteel")
            g.seg((0.33, y, 2), (0.8, y, 28), 0.008, "yellowsteel")                 # 斜撐
            g.seg((0.8, y, 2), (0.33, y, 28), 0.008, "yellowsteel")
        g.box(0.28, 0.85, -0.5, 0.3, 30, 33, "company")
        g.box(0.4, 0.6, -0.15, 0.05, 33, 37, "company")       # 操作室
        g.seg((0.5, -0.05, 34), (1.25, -0.05, 31), 0.012, "yellowsteel")
        g.seg((1.15, -0.05, 31), (1.15, -0.05, 14), 0.004, "darksteel")
    return g.ops


# ---------------------------------------------------------------- 直升機場
def heliport(part):
    g = M()
    if part == 0:                                             # 地面：人行鋪面
        g.slab(0.5, "pavement")
        g.mark(-0.5, 0.5, -0.5, -0.46, "darkconcrete")
    elif part == 1:                                           # 一樓大廳：玻璃＋入口雨遮
        g.box(-0.4, 0.4, -0.4, 0.4, 0, 9, "whiteconcrete")
        g.band(-0.4, 0.4, -0.4, 0.4, 1, 7.5, "blueglass")
        g.box(0.4, 0.5, -0.15, 0.15, 6.5, 7.5, "company")
    elif part == 2:                                           # 辦公樓層（疊 4 層）
        g.box(-0.4, 0.4, -0.4, 0.4, 0, 9, "whiteconcrete")
        g.band(-0.4, 0.4, -0.4, 0.4, 2.5, 7.5, "blueglass")
    else:                                                     # 屋頂：鋼柱撐起的起降平台（頂面在 z = 18，與移動節點一致）
        g.box(-0.4, 0.4, -0.4, 0.4, 0, 2, "concrete")
        g.box(-0.15, 0.15, -0.15, 0.15, 2, 7, "whiteconcrete")              # 樓梯間
        for x in (-0.35, 0.35):
            for y in (-0.35, 0.35):
                g.seg((x, y, 2), (x * 1.2, y * 1.2, 16), 0.012, "darksteel")
        g.box(-0.46, 0.46, -0.46, 0.46, 16, 17.6, "darkconcrete")
        g.cyl(0, 0, 17.6, 0.12, 0.30, "yellowsteel", v=32)                  # 黃色圓環
        g.cyl(0, 0, 17.6, 0.16, 0.26, "darkconcrete", v=32)
        g.mark(-0.12, 0.12, -0.13, -0.08, "white", z=17.6)                  # H
        g.mark(-0.12, 0.12, 0.08, 0.13, "white", z=17.6)
        g.mark(-0.025, 0.025, -0.1, 0.1, "white", z=17.6)
        for x, y in ((0.44, 0.44), (-0.44, 0.44), (0.44, -0.44), (-0.44, -0.44)):
            g.cyl(x, y, 17.6, 0.6, 0.02, "lit", v=6)
    return g.ops


# ---------------------------------------------------------------- 機場共用
def runway(g, half, width, mat="asphalt", end=None, number=False, touchdown=False, edges=True, along="x"):
    """跑道段：沿局部 along 軸；end = +1/−1 表示該側是跑道頭（閾值條紋）。"""
    def R(a0, a1, b0, b1, m, z=1.0):                          # a = 沿跑道、b = 橫向
        if along == "x":
            g.mark(a0, a1, b0, b1, m, z)
        else:
            g.mark(b0, b1, a0, a1, m, z)
    if along == "x":
        g.box(-half, half, -width / 2, width / 2, 0, 1.0, mat)
    else:
        g.box(-width / 2, width / 2, -half, half, 0, 1.0, mat)
    if edges:
        R(-half, half, width / 2 - 0.04, width / 2 - 0.015, "white")
        R(-half, half, -width / 2 + 0.015, -width / 2 + 0.04, "white")
    stop = half
    if end:
        e = end * half
        n = 6 if width > 0.6 else 4
        for k in range(n):                                    # 閾值條紋（鋼琴鍵）
            b = -width / 2 + width * (k + 0.5) / n
            R(e - end * 0.30, e - end * 0.06, b - width / (n * 4.5), b + width / (n * 4.5), "white")
        stop = half - 0.45
    if number:
        R(-0.12, 0.12, -0.06, 0.06, "white")
        R(-0.18, -0.14, -0.12, 0.12, "white")
    if touchdown:
        for s in (-0.55, 0.55):
            for b in (-width * 0.25, width * 0.25):
                R(s - 0.12, s + 0.12, b - 0.035, b + 0.035, "white")
    a = -half + 0.08
    while a + 0.2 < half:                                     # 中心線虛線
        if not end or (end > 0 and a + 0.2 < stop) or (end < 0 and a > -stop):
            R(a, a + 0.2, -0.012, 0.012, "white")
        a += 0.36


def taxiway(g, half_len, width=0.42, along="x", ends=(True, True), lights=True):
    h0 = -half_len if ends[0] else -half_len - 0.1
    h1 = half_len if ends[1] else half_len + 0.1
    if along == "x":
        g.box(h0, h1, -width / 2, width / 2, 0, 1.0, "asphalt")
        g.mark(h0, h1, -0.012, 0.012, "yellowsteel")
    else:
        g.box(-width / 2, width / 2, h0, h1, 0, 1.0, "asphalt")
        g.mark(-0.012, 0.012, h0, h1, "yellowsteel")
    if lights:
        for t in (-0.3, 0.0, 0.3):
            for s in (-1, 1):
                p = (t, s * (width / 2 + 0.03)) if along == "x" else (s * (width / 2 + 0.03), t)
                g.cyl(p[0], p[1], 1.0, 0.8, 0.015, "blueglass", v=6)


def apron(g, half, stands=(), lines=()):
    g.box(-half, half, -half, half, 0, 1.0, "apron")
    k = -half + 0.25
    while k < half:                                           # 混凝土板的接縫
        g.mark(k - 0.006, k + 0.006, -half, half, "darkconcrete")
        g.mark(-half, half, k - 0.006, k + 0.006, "darkconcrete")
        k += 0.25
    for (x0, x1, y0, y1) in lines:                            # 黃色滑行引導線
        g.mark(x0, x1, y0, y1, "yellowsteel")
    for (x, y) in stands:                                     # 機位：T 字標線
        g.mark(x - 0.15, x + 0.15, y - 0.012, y + 0.012, "yellowsteel")
        g.mark(x - 0.012, x + 0.012, y - 0.15, y + 0.15, "yellowsteel")


def windsock(g, frame, frames=16):
    g.cyl(0, 0, 0, 1.0, 0.06, "concrete", v=8)
    g.seg((0, 0, 1), (0, 0, 27), 0.012, "white")
    g.seg((0, 0, 12), (0, 0, 16), 0.014, "red")
    a = 2 * math.pi * frame / frames                          # 風向緩慢轉動＋擺動
    wob = math.sin(4 * a) * 0.03
    d = (math.cos(a), math.sin(a))
    for k, m in enumerate(("company", "white", "company", "white")):
        t0, t1 = 0.02 + k * 0.055, 0.02 + (k + 1) * 0.055
        p0 = (d[0] * t0, d[1] * t0 + wob * k, 26.5 - k * 0.5)
        p1 = (d[0] * t1, d[1] * t1 + wob * (k + 1), 26.5 - (k + 1) * 0.5)
        g.seg(p0, p1, 0.022 - k * 0.003, m)


def radar(g, frame, frames=64):
    g.box(-0.12, 0.12, -0.12, 0.12, 0, 3, "whiteconcrete")
    g.seg((0, 0, 3), (0, 0, 13), 0.03, "darksteel")
    a = 2 * math.pi * frame / frames
    d = (math.cos(a), math.sin(a))
    n = (-d[1], d[0])
    for s in (-1, 1):                                         # 長條形天線（略向前傾的拋物面）
        g.seg((n[0] * 0.02 * s, n[1] * 0.02 * s, 13), (n[0] * 0.24 * s + d[0] * 0.05, n[1] * 0.24 * s + d[1] * 0.05, 16), 0.022, "white")
        g.seg((n[0] * 0.02 * s, n[1] * 0.02 * s, 17), (n[0] * 0.24 * s + d[0] * 0.05, n[1] * 0.24 * s + d[1] * 0.05, 16), 0.022, "white")
    g.seg((0, 0, 13), (0, 0, 18), 0.02, "company")


def hangar(g, half_x, half_y, wall, roof_h, front, mat="corrugated", doors="company"):
    """機庫：front = 局部正面方向（'+x'、'-x'、'+y'、'-y'），正面是大門。"""
    g.box(-half_x, half_x, -half_y, half_y, 0, wall, mat)
    ridge = "y" if front in ("+x", "-x") else "x"
    g.gable(-half_x - 0.02, half_x + 0.02, -half_y - 0.02, half_y + 0.02, wall, roof_h, "lead", ridge=ridge)
    s = 1 if front[0] == "+" else -1
    if front[1] == "x":
        g.box(s * half_x - 0.01, s * half_x + 0.01, -half_y * 0.8, half_y * 0.8, 0, wall * 0.85, doors)
    else:
        g.box(-half_x * 0.8, half_x * 0.8, s * half_y - 0.01, s * half_y + 0.01, 0, wall * 0.85, doors)


# ---------------------------------------------------------------- AIRPORT2：1919–1940 小型草地機場
def airport2(part):
    g = M()
    if part == 0:                                             # 跑道頭（旋轉 0 在西端 → 跑道頭在局部 −x）
        runway(g, 1.0, 0.75, "gravel", end=-1, edges=False)
    elif part == 1:                                           # 跑道中段（旋轉 1 → 跑道沿局部 y）
        runway(g, 1.0, 0.75, "gravel", edges=False, along="y")
        g.cyl(0.6, 0, 1.0, 0.1, 0.25, "white", v=24)          # 草地上的白色圓形標記
        g.cyl(0.6, 0, 1.0, 0.14, 0.2, "grass", v=24)
    elif part == 2:                                           # 機庫（旋轉 3 → 正面朝局部 +x）
        hangar(g, 0.8, 0.75, 22, 16, "+x", mat="lightwood", doors="company")
    elif part == 3:                                           # 航站＋塔台（h64）
        g.box(-0.7, 0.3, -0.7, 0.7, 0, 16, "whitewash")
        g.band(-0.7, 0.3, -0.7, 0.7, 6, 11, "glass")
        g.hip(-0.75, 0.35, -0.75, 0.75, 16, 8, "terracotta", k=0.5)
        g.box(0.35, 0.75, -0.25, 0.25, 0, 40, "whitewash")    # 塔台
        g.band(0.35, 0.75, -0.25, 0.25, 40, 47, "blueglass")
        g.box(0.33, 0.77, -0.27, 0.27, 47, 49, "company")
        g.hip(0.33, 0.77, -0.27, 0.27, 49, 6, "terracotta")
        g.box(0.3, 0.32, -0.6, 0.6, 0, 10, "company")         # 正面的公司色雨遮
    elif part == 4:                                           # 第二座機庫（較寬，h48）
        hangar(g, 0.75, 0.95, 24, 14, "+x", mat="corrugated", doors="darkwood")
        g.band(-0.75, 0.75, -0.95, 0.95, 18, 20, "company", out=0.01)
    elif part == 5:
        return []                                             # 草地跑道：空白（顯示地形）
    else:
        windsock(g, part - 6)
    return g.ops


# ---------------------------------------------------------------- AIRPORT3：1935–1975 中型機場
def terminal_block(g, x0, x1, y0, y1, h, front, glass="blueglass", roof="apron", stripe="company"):
    g.box(x0, x1, y0, y1, 0, h, "whiteconcrete")
    for z in range(3, int(h) - 3, 9):
        g.band(x0, x1, y0, y1, z, z + 4.5, glass)
    g.box(x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, h, h + 1.5, roof)
    g.band(x0, x1, y0, y1, h - 2, h - 0.5, stripe, out=0.015)


def airport3(part):
    g = M()
    if part in (0, 1, 2, 3):                                  # 跑道：0 西端、3 東端、1/2 中段（1 有跑道編號）
        runway(g, 1.0, 0.8, end={0: -1, 3: 1}.get(part), number=(part == 1), touchdown=(part == 2))
    elif part == 4:                                           # 航站（旋轉 3 → 正面朝局部 +x）
        terminal_block(g, -0.6, 0.6, -0.9, 0.9, 30, "+x")
        g.box(0.6, 0.85, -0.5, 0.5, 9, 10.5, "company")       # 正面雨遮
    elif part == 5:                                           # 大機庫
        hangar(g, 0.85, 0.95, 26, 18, "+x", mat="corrugated", doors="company")
    elif part == 6:                                           # 貨運棚
        g.box(-0.5, 0.5, -0.9, 0.9, 0, 18, "yellowbrick")
        g.gable(-0.52, 0.52, -0.92, 0.92, 18, 9, "lead", ridge="y")
        for y in (-0.5, 0.0, 0.5):
            g.box(0.5, 0.52, y - 0.15, y + 0.15, 0, 12, "company")
    elif part == 7:                                           # 塔台（偏佔地的一角）
        g.box(0.3, 0.9, 0.3, 0.9, 0, 12, "whiteconcrete")
        g.cyl(0.6, 0.6, 12, 26, 0.17, "whiteconcrete", v=16)
        g.cyl(0.6, 0.6, 38, 7, 0.27, "blueglass", v=16, rt=0.3)
        g.cyl(0.6, 0.6, 45, 1.5, 0.31, "company", v=16)
        g.seg((0.6, 0.6, 46.5), (0.6, 0.6, 54), 0.01, "darksteel")
    elif part == 8:
        return []                                             # 草地：空白
    elif 9 <= part <= 24:
        windsock(g, part - 9)
    elif part in (25, 26, 27, 32, 33):                        # 2×2 停機坪
        apron(g, 1.0, stands=[(-0.5, -0.5), (0.5, 0.5)] if part in (26, 33) else [(0.5, -0.5)],
              lines=[(-1, 1, -0.01, 0.01)] if part in (25, 32) else [(-0.01, 0.01, -1, 1)])
    else:                                                     # 1×1 停機坪（28–31）
        apron(g, 0.5, stands=[(0.0, 0.0)] if part in (28, 31) else [],
              lines=[(-0.5, 0.5, -0.01, 0.01)] if part in (29, 30) else [])
    return g.ops


# ---------------------------------------------------------------- AIRPORT1：1970 年後的大型國際機場
def airport1(part):
    g = M()
    if part in (0, 1, 13, 24):                                # 2×2 跑道：0 跑道頭（局部 +x）、1 中段有編號、13/24 接地區
        runway(g, 1.0, 0.92, end=1 if part == 0 else None, number=(part == 1), touchdown=(part in (13, 24)))
    elif part in (2, 5, 9, 25):                               # 建築底下的混凝土地坪（h0）
        g.slab(1.0, "apron", z1=0.6)
    elif part in (3, 4):                                      # 角落航廈（旋轉 1 → 正面朝局部 −x）：兩層
        h = 8 if part == 3 else 13
        g.box(-0.85, 0.85, -0.85, 0.85, 0, h, "whiteconcrete")
        g.band(-0.85, 0.85, -0.85, 0.85, 1.5 if part == 3 else 2, h - 1.5, "blueglass")
        if part == 4:
            g.box(-0.87, 0.87, -0.87, 0.87, h, h + 1.5, "apron")
            g.box(-0.3, 0.3, -0.3, 0.3, h + 1.5, h + 4, "darkconcrete")          # 屋頂機房
            g.band(-0.85, 0.85, -0.85, 0.85, h - 1, h, "company")
        else:
            g.box(-1.0, -0.85, -0.7, 0.7, 6, 7, "company")                       # 正面雨遮
    elif part in (6, 7):                                      # 航廈主體（旋轉 1，正面朝局部 −x），玻璃帷幕
        h = 8 if part == 6 else 12
        g.box(-0.6, 0.85, -1.0, 1.0, 0, h, "whiteconcrete")
        g.band(-0.6, 0.85, -1.0, 1.0, 1.5, h - 1.2, "blueglass")
        if part == 7:
            g.box(-0.62, 0.87, -1.0, 1.0, h, h + 1.5, "apron")
            g.band(-0.6, 0.85, -1.0, 1.0, h - 1, h, "company")
        else:                                                 # 登機橋（朝停機坪伸出）
            for y in (-0.5, 0.5):
                g.box(-1.0, -0.6, y - 0.07, y + 0.07, 4, 7, "steel")
    elif part == 8:                                           # 航廈屋頂上的塔台（h66）
        g.box(-0.2, 0.2, -0.2, 0.2, 0, 4, "concrete")
        g.cyl(0, 0, 4, 44, 0.12, "whiteconcrete", v=16)
        g.cyl(0, 0, 48, 3, 0.16, "concrete", v=16, rt=0.26)
        g.cyl(0, 0, 51, 9, 0.27, "blueglass", v=16, rt=0.31)
        g.cyl(0, 0, 60, 2, 0.32, "company", v=16)
        g.seg((0, 0, 62), (0, 0, 72), 0.01, "darksteel")
        g.cyl(0.12, 0.12, 62, 3, 0.05, "white", v=10)        # 小雷達罩
    elif part in (10, 11):                                    # 機庫（正面朝局部 +y）
        if part == 10:
            g.box(-0.95, 0.95, -0.8, 0.8, 0, 8, "corrugated")
            g.box(-0.85, 0.85, 0.8, 0.82, 0, 7.5, "company")
        else:
            g.box(-0.95, 0.95, -0.8, 0.8, 0, 8, "corrugated")
            g.box(-0.97, 0.97, -0.82, 0.82, 8, 9.5, "lead")
            g.box(-0.85, 0.85, 0.8, 0.82, 0, 6, "company")
            g.mark(-0.6, 0.6, 0.83, 0.85, "white", z=7)
    elif part in (12, 23):                                    # 2×2 停機坪（機位）
        apron(g, 1.0, stands=[(-0.5, -0.4), (0.5, -0.4)] if part == 12 else [(-0.4, -0.5), (-0.4, 0.5)],
              lines=[(-1, 1, 0.39, 0.41)] if part == 12 else [(0.39, 0.41, -1, 1)])
    elif part == 14:                                          # 滑行道端點（1×1，較小）
        taxiway(g, 0.42, along="x", ends=(True, False))
    elif part == 15:                                          # 滑行道直線
        taxiway(g, 0.5, along="x", ends=(False, False))
    elif part == 16:                                          # 滑行道 T 字（往跑道接出）
        taxiway(g, 0.5, along="x", ends=(False, False), lights=False)
        g.box(-0.21, 0.21, 0.0, 0.5, 0, 1.0, "asphalt")
        g.mark(-0.012, 0.012, 0.0, 0.5, "yellowsteel")
    elif part in (17, 18, 20, 21, 28):                        # 1×1 停機坪
        apron(g, 0.5, stands=[(0, 0)] if part in (17, 21) else [],
              lines=[(-0.5, 0.5, -0.01, 0.01)] if part in (18, 20) else [(-0.01, 0.01, -0.5, 0.5)] if part == 28 else [])
    elif part in (19, 22):                                    # 滑行道接停機坪（往 −y 接出）
        taxiway(g, 0.5, along="x", ends=(False, False), lights=False)
        g.box(-0.21, 0.21, -0.5, 0.0, 0, 1.0, "apron")
        g.mark(-0.012, 0.012, -0.5, 0.0, "yellowsteel")
    elif part in (26, 27):                                    # 停車大樓（旋轉 0，正面朝局部 +y）
        h = 8 if part == 26 else 12
        g.box(-0.85, 0.85, -0.85, 0.85, 0, h, "apron")
        for z in (2.5, 6.5, 10.5):
            if z < h - 1:
                g.band(-0.85, 0.85, -0.85, 0.85, z, z + 1.6, "darkconcrete")
        if part == 27:
            g.box(-0.87, 0.87, -0.87, 0.87, h, h + 1.2, "company")
    elif 29 <= part <= 92:
        radar(g, part - 29)
    else:
        return []                                             # 93：空白
    return g.ops


MAKERS = {"SHIPST1": dock, "HPORT1": heliport, "AIRPORT1": airport1, "AIRPORT2": airport2, "AIRPORT3": airport3}


def make_model(name, info):
    return {"parts": [{"ops": MAKERS[name](p)} for p in range(len(info["heights"]))]}
