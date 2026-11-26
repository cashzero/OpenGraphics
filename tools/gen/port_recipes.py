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

    def lathe(self, x, y, z0, prof, m, seg=16):
        self.ops.append({"op": "lathe", "c": [y, -x, z0], "p": [[r, h] for r, h in prof], "m": m, "seg": seg})

    def vault(self, x0, x1, y0, y1, z0, h, m, ridge="y", segs=10):
        """拱形圓筒屋頂：ridge='y' 沿局部 y 擠出（跨度在 x），ridge='x' 沿局部 x 擠出（跨度在 y）。"""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if ridge == "y":
            pts = [[-(x0 + (x1 - x0) * k / segs), z0 + h * math.sin(math.pi * k / segs)] for k in range(segs + 1)]
            self.ops.append({"op": "finx", "p": pts, "x": [y0, y1], "m": m})
        else:
            pts = [[y0 + (y1 - y0) * k / segs, z0 + h * math.sin(math.pi * k / segs)] for k in range(segs + 1)]
            self.ops.append({"op": "finy", "p": pts, "y": [-x1, -x0], "m": m})

    def wedge(self, x0, x1, y0, y1, z_a, z_b, m, slope="x", base=None):
        """單坡斜屋頂（現代航廈翼狀屋頂）：slope='x' 時高度由 x0 的 z_a 漸變到 x1 的 z_b；slope='y' 由 y0 到 y1。"""
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        zb = min(z_a, z_b) if base is None else base
        if slope == "x":
            pts = [[-x0, zb], [-x1, zb], [-x1, z_b], [-x0, z_a]]
            self.ops.append({"op": "finx", "p": pts, "x": [y0, y1], "m": m})
        else:
            pts = [[y0, zb], [y1, zb], [y1, z_b], [y0, z_a]]
            self.ops.append({"op": "finy", "p": pts, "y": [-x1, -x0], "m": m})

    def sphere(self, x, y, z0, r, m, seg=14, rings=6):
        """球體（雷達罩等）。z0 = 底部高度，r 以格為單位（高度自動換算成 px）。"""
        r_px = r * 39.5
        prof = []
        for k in range(rings + 1):
            a = -math.pi / 2 + math.pi * k / rings
            prof.append((max(0.002, r * math.cos(a)), r_px * (1.0 + math.sin(a))))
        self.lathe(x, y, z0, prof, m, seg=seg)

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
    if part == 0:                                             # 碼頭平台（h8）：風化暗石岸壁、木樁護舷、石鋪面、貨箱與軌道
        g.box(-1.0, 1.0, -1.0, 1.0, 0, 6.2, "darkstone")
        g.box(-0.98, 0.98, -0.98, 0.98, 6.2, 7.5, "stone")    # 風化石鋪面（不再過曝成純白）
        g.box(0.86, 1.00, -1.0, 1.0, 7.2, 7.7, "darkwood")    # 岸緣防撞護木
        # 水側（局部 +x）重型木樁護舷與橫木
        for y in (-0.84, -0.42, 0.0, 0.42, 0.84):
            g.cyl(1.01, y, 0.5, 7.4, 0.045, "darkwood", v=8)
        g.box(0.98, 1.03, -0.92, 0.92, 4.8, 5.5, "wood")
        g.box(0.98, 1.03, -0.92, 0.92, 2.2, 2.9, "wood")
        # 繫船鐵柱與起重機軌道
        for y in (-0.72, 0.0, 0.72):
            g.cyl(0.88, y, 7.5, 1.8, 0.04, "darksteel", v=8)
            g.cyl(0.88, y, 9.1, 0.4, 0.055, "darksteel", v=8)
        for x in (0.28, 0.76):
            g.mark(x - 0.015, x + 0.015, -0.94, 0.94, "darksteel", z=7.5)
        g.mark(-0.96, 0.96, 0.90, 0.95, "yellowsteel", z=7.5)
        # 碼頭貨箱與集裝箱堆
        for (x, y, sx, sy, h, m) in ((0.44, 0.58, 0.24, 0.16, 4.2, "company"),
                                     (0.44, 0.76, 0.24, 0.16, 4.2, "red"),
                                     (0.44, 0.67, 0.22, 0.15, 3.6, "planks"),
                                     (0.10, 0.68, 0.18, 0.18, 3.2, "wood")):
            g.box(x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, 7.5, 7.5 + h, m)
    else:                                                     # 紅磚倉庫（暗石板屋頂＋天窗）＋桁架門式起重機（h40）
        g.box(-0.96, -0.10, -0.90, 0.90, 0, 21.0, "brick")
        for y in (-0.90, -0.30, 0.30, 0.90):
            g.box(-0.98, -0.08, y - 0.03, y + 0.03, 0, 21.0, "darkbrick")
        g.gable(-0.99, -0.07, -0.94, 0.94, 21.0, 10.5, "slate", ridge="y")
        g.box(-0.62, -0.44, -0.68, 0.68, 29.0, 32.0, "blueglass")
        g.gable(-0.65, -0.41, -0.71, 0.71, 32.0, 2.2, "darksteel", ridge="y")
        for y in (-0.56, 0.0, 0.56):                          # 朝水側的裝卸大門與雨遮
            g.box(-0.11, -0.08, y - 0.18, y + 0.18, 0, 13.0, "darksteel")
            g.box(-0.10, -0.07, y - 0.15, y + 0.15, 0, 12.2, "darkwood")
        g.wedge(-0.10, 0.10, -0.86, 0.86, 15.2, 13.5, "slate", slope="x", base=13.3)
        g.band(-0.96, -0.10, -0.90, 0.90, 17.5, 19.2, "company", out=0.015)
        # 桁架門式港口起重機（四腳收分桁架＋旋轉玻璃駕駛室＋配重箱＋桁架吊臂＋吊鉤）
        for y in (-0.44, 0.24):
            g.seg((0.28, y, 0), (0.36, y, 24.0), 0.022, "darksteel")
            g.seg((0.76, y, 0), (0.68, y, 24.0), 0.022, "darksteel")
            g.seg((0.28, y, 10.0), (0.72, y, 23.0), 0.010, "yellowsteel")
            g.seg((0.76, y, 10.0), (0.32, y, 23.0), 0.010, "yellowsteel")
            g.seg((0.32, y, 11.0), (0.72, y, 11.0), 0.014, "darksteel")
        for x in (0.36, 0.68):
            g.seg((x, -0.44, 16.0), (x, 0.24, 23.5), 0.010, "yellowsteel")
            g.seg((x, 0.24, 16.0), (x, -0.44, 23.5), 0.010, "yellowsteel")
        g.box(0.30, 0.74, -0.48, 0.28, 23.5, 25.6, "darksteel")        # 門架平台
        # 旋轉機房＋玻璃操作室＋後方配重
        g.box(0.32, 0.66, -0.34, 0.14, 25.6, 32.0, "company")
        g.box(0.64, 0.72, -0.26, 0.06, 27.2, 31.2, "blueglass")        # 朝水側觀景窗
        g.box(0.24, 0.34, -0.30, 0.10, 26.2, 30.2, "darkconcrete")     # 配重箱
        # A 型塔架與桁架吊臂
        g.seg((0.46, -0.24, 32.0), (0.56, -0.10, 39.5), 0.014, "yellowsteel")
        g.seg((0.46, 0.04, 32.0), (0.56, -0.10, 39.5), 0.014, "yellowsteel")
        for dy in (-0.08, 0.08):
            g.seg((0.58, -0.10 + dy, 31.5), (1.30, -0.10 + dy * 0.4, 37.0), 0.013, "yellowsteel")
        g.seg((0.56, -0.10, 39.5), (1.30, -0.10, 37.0), 0.008, "darksteel")   # 拉索
        g.seg((1.28, -0.10, 37.0), (1.28, -0.10, 15.0), 0.005, "darksteel")   # 吊索
        g.box(1.22, 1.34, -0.16, -0.04, 13.5, 15.2, "yellowsteel")            # 吊鉤塊
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


def runway_junction(g, jx, rw_width, side=-1, tw_width=0.42):
    """跑道與滑行道 T 字銜接段：從圖塊邊界（side*1.0）無縫連到跑道邊緣，附喇叭口倒角、黃色導引線與等待線。"""
    y_edge = side * 1.03
    y_rw = side * (rw_width / 2 - 0.04)
    y0, y1 = min(y_edge, y_rw), max(y_edge, y_rw)
    # 主銜接柏油段（略高於跑道白邊線 z=1.005 以自然切斷跑道邊線）
    g.box(jx - tw_width / 2, jx + tw_width / 2, y0, y1, 0, 1.005, "asphalt")
    # 跑道入口處喇叭口加寬倒角，讓飛機轉彎更自然
    fy0, fy1 = sorted((side * (rw_width / 2 + 0.18), y_rw))
    g.box(jx - tw_width / 2 - 0.14, jx + tw_width / 2 + 0.14, fy0, fy1, 0, 1.005, "asphalt")
    # 黃色滑行中心線延伸進跑道（轉彎導入）
    cy0, cy1 = sorted((side * 1.02, side * 0.12))
    g.mark(jx - 0.012, jx + 0.012, cy0, cy1, "yellowsteel", z=1.01)
    # 雙道黃色跑道等待線（hold-short bar）
    hy = side * (rw_width / 2 + 0.22)
    g.mark(jx - tw_width / 2 + 0.03, jx + tw_width / 2 - 0.03, hy - 0.015, hy + 0.015, "yellowsteel", z=1.01)
    g.mark(jx - tw_width / 2 + 0.03, jx + tw_width / 2 - 0.03, hy + side * 0.045 - 0.012, hy + side * 0.045 + 0.012, "yellowsteel", z=1.01)


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


def sliding_doors(g, span0, span1, face, z0, z1, axis="x", leaves=4, mat="company", frame="darksteel"):
    """多片滑動機庫大門：門框＋均分門扇＋門縫與門楣滑軌。"""
    s = 1 if face >= 0 else -1
    w = (span1 - span0) / leaves
    gap = 0.022
    if axis == "x":
        g.box(face - 0.015, face + 0.015, span0 - 0.03, span1 + 0.03, z0, z1 + 1.4, frame)
        for k in range(leaves):
            a, b = span0 + k * w + gap, span0 + (k + 1) * w - gap
            g.box(face - 0.005, face + s * 0.024, a, b, z0, z1, mat)
        g.box(face - 0.02, face + s * 0.055, span0 - 0.04, span1 + 0.04, z1, z1 + 1.6, frame)
    else:
        g.box(span0 - 0.03, span1 + 0.03, face - 0.015, face + 0.015, z0, z1 + 1.4, frame)
        for k in range(leaves):
            a, b = span0 + k * w + gap, span0 + (k + 1) * w - gap
            g.box(a, b, face - 0.005, face + s * 0.024, z0, z1, mat)
        g.box(span0 - 0.04, span1 + 0.04, face - 0.02, face + s * 0.055, z1, z1 + 1.6, frame)


def arched_hangar(g, half_x, half_y, wall, arch_h, front, mat="corrugated", roof="lead", doors="company", ribs=5, annex=True):
    """拱形圓筒屋頂機庫：外露鋼構拱肋、屋脊採光天窗、多片滑動大門與側面工作間。"""
    g.box(-half_x, half_x, -half_y, half_y, 0, wall, mat)
    ridge = "x" if front in ("+x", "-x") else "y"
    g.vault(-half_x - 0.02, half_x + 0.02, -half_y - 0.02, half_y + 0.02, wall, arch_h, roof, ridge=ridge, segs=10)
    # 外露鋼構拱肋與側牆立柱
    if ridge == "x":
        for k in range(ribs):
            x = -half_x + (2 * half_x) * k / max(ribs - 1, 1)
            g.vault(x - 0.025, x + 0.025, -half_y - 0.04, half_y + 0.04, wall, arch_h + 0.9, "darksteel", ridge="x", segs=10)
            for sy in (-1, 1):
                g.box(x - 0.03, x + 0.03, sy * half_y - 0.02, sy * half_y + 0.02, 0, wall, "darksteel")
        # 屋脊採光天窗
        g.box(-half_x * 0.85, half_x * 0.85, -0.18, 0.18, wall + arch_h - 1.5, wall + arch_h + 2.2, "blueglass")
        g.box(-half_x * 0.88, half_x * 0.88, -0.21, 0.21, wall + arch_h + 2.2, wall + arch_h + 3.0, "darksteel")
        # 側牆高窗
        for sy in (-1, 1):
            g.box(-half_x * 0.72, half_x * 0.72, sy * (half_y + 0.008) - 0.012, sy * (half_y + 0.008) + 0.012, wall * 0.62, wall * 0.82, "blueglass")
        # 前後山牆半圓採光窗
        for sx in (-1, 1):
            g.vault(sx * half_x - 0.02, sx * half_x + 0.02, -half_y * 0.48, half_y * 0.48, wall + 1.5, arch_h * 0.55, "blueglass", ridge="x", segs=8)
        s = 1 if front[0] == "+" else -1
        sliding_doors(g, -half_y * 0.80, half_y * 0.80, s * half_x, 0, wall * 0.84, axis="x", leaves=4, mat=doors)
        if annex:
            g.box(-half_x * 0.55, half_x * 0.45, -half_y - 0.15, -half_y, 0, wall * 0.48, "whiteconcrete")
            g.box(-half_x * 0.58, half_x * 0.48, -half_y - 0.17, -half_y, wall * 0.48, wall * 0.54, "darksteel")
            g.box(-half_x * 0.42, half_x * 0.32, -half_y - 0.16, -half_y - 0.14, wall * 0.22, wall * 0.38, "blueglass")
    else:
        for k in range(ribs):
            y = -half_y + (2 * half_y) * k / max(ribs - 1, 1)
            g.vault(-half_x - 0.04, half_x + 0.04, y - 0.025, y + 0.025, wall, arch_h + 0.9, "darksteel", ridge="y", segs=10)
            for sx in (-1, 1):
                g.box(sx * half_x - 0.02, sx * half_x + 0.02, y - 0.03, y + 0.03, 0, wall, "darksteel")
        g.box(-0.18, 0.18, -half_y * 0.85, half_y * 0.85, wall + arch_h - 1.5, wall + arch_h + 2.2, "blueglass")
        g.box(-0.21, 0.21, -half_y * 0.88, half_y * 0.88, wall + arch_h + 2.2, wall + arch_h + 3.0, "darksteel")
        s = 1 if front[0] == "+" else -1
        sliding_doors(g, -half_x * 0.80, half_x * 0.80, s * half_y, 0, wall * 0.84, axis="y", leaves=4, mat=doors)


def facade_piers(g, x0, x1, y0, y1, z0, z1, xs=(), ys=(), mat="whiteconcrete", t=0.032, out=0.024):
    """立面垂直結構柱（切割玻璃帷幕，避免整片窗帶太單調）。"""
    for x in xs:
        g.box(x - t, x + t, y0 - out, y0 + out, z0, z1, mat)
        g.box(x - t, x + t, y1 - out, y1 + out, z0, z1, mat)
    for y in ys:
        g.box(x0 - out, x0 + out, y - t, y + t, z0, z1, mat)
        g.box(x1 - out, x1 + out, y - t, y + t, z0, z1, mat)


def atc_cab(g, cx, cy, z_base, r_bot, r_top, cab_h, fascia="company", mullions=8):
    """外傾多邊形航管塔台觀景室：斜窗格、環繞陽台欄杆、屋頂雷達罩與天線陣列。"""
    # 環繞式走道與欄杆
    g.cyl(cx, cy, z_base - 1.0, 1.2, r_bot + 0.07, "concrete", v=12)
    for k in range(mullions):
        a = 2 * math.pi * k / mullions
        rx, ry = cx + math.cos(a) * (r_bot + 0.06), cy + math.sin(a) * (r_bot + 0.06)
        g.seg((rx, ry, z_base + 0.2), (rx, ry, z_base + 2.4), 0.008, "darksteel")
        a2 = 2 * math.pi * (k + 1) / mullions
        rx2, ry2 = cx + math.cos(a2) * (r_bot + 0.06), cy + math.sin(a2) * (r_bot + 0.06)
        g.seg((rx, ry, z_base + 2.3), (rx2, ry2, z_base + 2.3), 0.007, "darksteel")
    # 外傾玻璃窗室＋暗色斜窗框
    g.cyl(cx, cy, z_base, cab_h, r_bot, "blueglass", v=12, rt=r_top)
    for k in range(mullions):
        a = 2 * math.pi * k / mullions
        p0 = (cx + math.cos(a) * (r_bot + 0.008), cy + math.sin(a) * (r_bot + 0.008), z_base)
        p1 = (cx + math.cos(a) * (r_top + 0.008), cy + math.sin(a) * (r_top + 0.008), z_base + cab_h)
        g.seg(p0, p1, 0.011, "darksteel")
    # 階梯狀屋頂與公司色飾邊
    z_roof = z_base + cab_h
    g.cyl(cx, cy, z_roof, 1.4, r_top + 0.04, "whiteconcrete", v=12)
    g.cyl(cx, cy, z_roof + 1.4, 1.4, r_top + 0.05, fascia, v=12)
    g.cyl(cx, cy, z_roof + 2.8, 1.0, r_top - 0.02, "darkconcrete", v=12)
    # 雷達球罩、通訊天線與航空警示燈
    g.cyl(cx + 0.09, cy + 0.09, z_roof + 3.6, 1.2, 0.045, "darksteel", v=8)
    g.sphere(cx + 0.09, cy + 0.09, z_roof + 4.4, 0.065, "white", seg=12, rings=5)
    g.seg((cx - 0.07, cy - 0.07, z_roof + 3.6), (cx - 0.07, cy - 0.07, z_roof + 12.5), 0.010, "darksteel")
    g.seg((cx - 0.14, cy - 0.07, z_roof + 9.5), (cx, cy - 0.07, z_roof + 9.5), 0.007, "white")
    g.seg((cx - 0.07, cy - 0.14, z_roof + 10.8), (cx - 0.07, cy, z_roof + 10.8), 0.007, "white")
    g.cyl(cx - 0.07, cy - 0.07, z_roof + 12.3, 1.2, 0.018, "red", v=6)


# ---------------------------------------------------------------- AIRPORT2：1919–1940 小型草地機場
def airport2(part):
    g = M()
    if part == 0:                                             # 跑道頭（旋轉 0 在西端 → 跑道頭在局部 −x）
        runway(g, 1.0, 0.75, "gravel", end=-1, edges=False)
    elif part == 1:                                           # 跑道中段（旋轉 1 → 跑道沿局部 y）
        runway(g, 1.0, 0.75, "gravel", edges=False, along="y")
        g.cyl(0.6, 0, 1.0, 0.1, 0.25, "white", v=24)          # 草地上的白色圓形標記
        g.cyl(0.6, 0, 1.0, 0.14, 0.2, "grass", v=24)
    elif part == 2:                                           # 木造機庫（旋轉 3 → 正面朝局部 +x）
        g.box(-0.78, 0.72, -0.72, 0.72, 0, 20, "lightwood")
        g.gable(-0.84, 0.78, -0.78, 0.78, 20, 15, "lead", ridge="x")
        # 外露木樑、側牆高窗與滑動大門
        for x in (-0.78, -0.28, 0.22, 0.72):
            for sy in (-0.72, 0.72):
                g.box(x - 0.03, x + 0.03, sy - 0.025, sy + 0.025, 0, 20, "darkwood")
        for sy in (-0.73, 0.73):
            g.box(-0.62, 0.56, sy - 0.01, sy + 0.01, 13, 17, "glass")
        sliding_doors(g, -0.58, 0.58, 0.72, 0, 17, axis="x", leaves=4, mat="company", frame="darkwood")
        g.box(0.70, 0.75, -0.25, 0.25, 22, 27, "glass")       # 山牆採光窗
        # 側邊小工具棚與油桶
        g.box(-0.45, 0.35, -0.92, -0.72, 0, 10, "wood")
        g.wedge(-0.48, 0.38, -0.95, -0.72, 10, 13, "terracotta", slope="y", base=10)
        for dx, m in ((0.55, "red"), (0.68, "yellowsteel")):
            g.cyl(dx, -0.84, 0, 4.2, 0.055, m, v=8)
    elif part == 3:                                           # 1930 年代會館式航站＋木構觀景塔台（h64）
        g.box(-0.72, 0.28, -0.72, 0.72, 0, 2.5, "stone")      # 石砌基座
        g.box(-0.70, 0.26, -0.70, 0.70, 2.5, 16.5, "whitewash")
        g.band(-0.70, 0.26, -0.70, 0.70, 6.5, 12.0, "glass")
        facade_piers(g, -0.70, 0.26, -0.70, 0.70, 2.5, 16.5, xs=(-0.50, -0.22, 0.06), ys=(-0.45, 0.0, 0.45), mat="whitewash", t=0.03, out=0.02)
        g.hip(-0.78, 0.34, -0.78, 0.78, 16.5, 9.5, "terracotta", k=0.45)
        g.box(-0.55, -0.40, 0.35, 0.50, 20, 29, "brick")      # 煙囪
        # 正面有柱門廊雨遮
        g.box(0.26, 0.48, -0.58, 0.58, 9.5, 11.2, "company")
        g.wedge(0.26, 0.50, -0.60, 0.60, 13.0, 11.2, "terracotta", slope="x", base=11.0)
        for y in (-0.52, -0.18, 0.18, 0.52):
            g.box(0.43, 0.47, y - 0.022, y + 0.022, 0, 9.5, "whitewash")
        # 方形塔台＋懸挑觀景陽台＋尖頂
        g.box(0.30, 0.78, -0.28, 0.28, 0, 10, "brick")
        g.box(0.32, 0.76, -0.26, 0.26, 10, 38, "whitewash")
        for z in (16, 24, 32):
            g.box(0.75, 0.78, -0.07, 0.07, z, z + 3.5, "glass")
        # 懸挑木陽台與欄杆
        g.box(0.24, 0.84, -0.34, 0.34, 37.5, 39.2, "darkwood")
        for x in (0.25, 0.54, 0.83):
            for y in (-0.33, 0.33):
                g.seg((x, y, 39.2), (x, y, 42.0), 0.009, "darkwood")
        g.box(0.30, 0.78, -0.28, 0.28, 39.2, 47.0, "blueglass")
        for x in (0.30, 0.54, 0.78):
            for y in (-0.28, 0.28):
                g.box(x - 0.018, x + 0.018, y - 0.018, y + 0.018, 39.2, 47.0, "whitewash")
        g.box(0.26, 0.82, -0.32, 0.32, 47.0, 49.0, "company")
        g.hip(0.24, 0.84, -0.34, 0.34, 49.0, 7.5, "terracotta")
        g.seg((0.54, 0.0, 56.5), (0.54, 0.0, 63.0), 0.010, "darksteel")
        g.seg((0.46, 0.0, 61.5), (0.62, 0.0, 61.5), 0.008, "white")
    elif part == 4:                                           # 第二座機庫（拱形浪板機庫，h48）
        arched_hangar(g, 0.76, 0.86, 17, 16, "+x", mat="corrugated", roof="lead", doors="darkwood", ribs=5, annex=False)
        g.box(0.75, 0.81, -0.82, 0.82, 15.2, 17.0, "company") # 正面公司色飾帶
    elif part == 5:
        return []                                             # 草地跑道：空白（顯示地形）
    else:
        windsock(g, part - 6)
    return g.ops


# ---------------------------------------------------------------- AIRPORT3：1935–1975 中型機場
def airport3(part):
    g = M()
    if part in (0, 1, 2, 3):                                  # 跑道：0 西端、3 東端、1/2 中段（1 有跑道編號；1/2 接停機坪出口）
        runway(g, 1.0, 0.8, end={0: -1, 3: 1}.get(part), number=(part == 1), touchdown=(part == 2))
        if part == 1:                                         # x=-1..0, y=2..3：x=0 側（local +0.5）接停機坪 t14 (x=0, y=1)
            runway_junction(g, 0.5, 0.8, side=-1, tw_width=0.52)
        elif part == 2:                                       # x=1..2, y=2..3：x=1 側（local -0.5）接停機坪 t16 (x=1, y=1)
            runway_junction(g, -0.5, 0.8, side=-1, tw_width=0.52)
    elif part == 4:                                           # 現代主義中型航站（旋轉 3 → 正面朝局部 +x）
        g.box(-0.66, 0.56, -0.90, 0.90, 0, 2.0, "darkconcrete")
        g.box(-0.64, 0.54, -0.88, 0.88, 2.0, 26.0, "whiteconcrete")
        for z in (3.0, 13.5):
            g.band(-0.64, 0.54, -0.88, 0.88, z, z + 7.0, "blueglass")
        g.box(0.53, 0.56, -0.45, 0.45, 2.5, 8.5, "lit")       # 入口大廳室內暖光
        facade_piers(g, -0.64, 0.54, -0.88, 0.88, 2.0, 26.0, xs=(-0.38, 0.0, 0.34), ys=(-0.62, -0.22, 0.22, 0.62), mat="whiteconcrete", t=0.032)
        g.band(-0.64, 0.54, -0.88, 0.88, 24.5, 26.0, "company", out=0.02)
        # 朝停機坪上揚的翼狀懸挑屋頂＋中央採光天窗室
        g.wedge(-0.72, 0.74, -0.94, 0.94, 26.2, 31.0, "whiteconcrete", slope="x", base=26.0)
        g.box(-0.45, 0.25, -0.68, 0.68, 28.0, 32.5, "blueglass")
        g.box(-0.48, 0.28, -0.71, 0.71, 32.5, 34.0, "apron")
        g.box(-0.55, -0.25, -0.25, 0.25, 26.5, 29.5, "darkconcrete")   # 屋頂空調機組
        # 正面斜撐雨遮入口
        g.box(0.54, 0.86, -0.58, 0.58, 10.0, 11.6, "company")
        for y in (-0.50, 0.0, 0.50):
            g.seg((0.54, y, 4.0), (0.82, y, 10.2), 0.014, "darksteel")
    elif part == 5:                                           # 拱形大型機庫
        arched_hangar(g, 0.84, 0.88, 20, 18, "+x", mat="corrugated", roof="lead", doors="company", ribs=5, annex=True)
    elif part == 6:                                           # 貨運棚：裝卸月台＋屋脊採光氣窗＋貨箱
        g.box(-0.60, 0.46, -0.90, 0.90, 0, 18, "yellowbrick")
        g.gable(-0.64, 0.50, -0.94, 0.94, 18, 9.5, "lead", ridge="y")
        # 屋脊氣窗帶
        g.box(-0.16, 0.16, -0.72, 0.72, 24.5, 28.5, "blueglass")
        g.gable(-0.19, 0.19, -0.75, 0.75, 28.5, 2.8, "darksteel", ridge="y")
        # 裝卸混凝土月台＋遮雨棚＋三組捲門
        g.box(0.46, 0.76, -0.88, 0.88, 0, 3.2, "concrete")
        g.wedge(0.46, 0.80, -0.90, 0.90, 14.5, 12.6, "corrugated", slope="x", base=12.4)
        for y in (-0.54, 0.0, 0.54):
            g.box(0.45, 0.49, y - 0.18, y + 0.18, 3.2, 12.5, "darksteel")
            g.box(0.46, 0.50, y - 0.15, y + 0.15, 3.2, 11.8, "company")
        for (y, m) in ((-0.74, "planks"), (-0.64, "logs"), (0.72, "planks")):
            g.box(0.56, 0.68, y - 0.05, y + 0.05, 3.2, 6.4, m)
    elif part == 7:                                           # 塔台（偏佔地的一角）
        cx, cy = 0.58, 0.58
        g.box(0.18, 0.92, 0.18, 0.92, 0, 12, "whiteconcrete")
        g.band(0.18, 0.92, 0.18, 0.92, 3.5, 9.0, "blueglass")
        facade_piers(g, 0.18, 0.92, 0.18, 0.92, 0, 12, xs=(0.40, 0.72), ys=(0.40, 0.72), mat="whiteconcrete", t=0.025)
        g.box(0.16, 0.94, 0.16, 0.94, 12, 13.4, "apron")
        # 帶肋圓柱塔身
        g.cyl(cx, cy, 13.4, 22.5, 0.16, "whiteconcrete", v=12, rt=0.13)
        for dx, dy in ((0.14, 0), (-0.14, 0), (0, 0.14), (0, -0.14)):
            g.box(cx + dx - 0.025, cx + dx + 0.025, cy + dy - 0.025, cy + dy + 0.025, 13.4, 35.5, "concrete")
        g.cyl(cx, cy, 35.5, 3.0, 0.16, "darkconcrete", v=12, rt=0.25)
        atc_cab(g, cx, cy, 38.5, 0.25, 0.31, 7.5, fascia="company", mullions=8)
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
    if part in (0, 1, 13, 24):                                # 2×2 跑道：0 跑道頭、1 編號段、13/24 接地區＋滑行道銜接
        runway(g, 1.0, 0.92, end=1 if part == 0 else None, number=(part == 1), touchdown=(part in (13, 24)))
        if part == 13:                                        # x=-2..-1, y=4..5：x=-2 側（local -0.5）接滑行道 t9r1 (x=-2, y=3)
            runway_junction(g, -0.5, 0.92, side=-1, tw_width=0.42)
        elif part == 24:                                      # x=2..3, y=4..5：x=3 側（local +0.5）接滑行道 t9r1 (x=3, y=3)
            runway_junction(g, 0.5, 0.92, side=-1, tw_width=0.42)
    elif part in (2, 5, 9, 25):                               # 建築底下的混凝土地坪（h0）
        g.slab(1.0, "apron", z1=0.6)
    elif part == 3:                                           # 角落航廈底層（旋轉 1 → 正面朝局部 −x、+y 接主航廈）
        g.box(-0.78, 0.82, -0.88, 1.0, 0, 1.2, "darkconcrete")
        g.box(-0.76, 0.80, -0.86, 1.0, 1.2, 8.0, "whiteconcrete")
        g.band(-0.76, 0.80, -0.86, 0.98, 1.4, 7.2, "blueglass")
        g.box(-0.77, -0.74, -0.55, 0.55, 1.6, 5.2, "lit")     # 室內候機大廳暖光
        facade_piers(g, -0.76, 0.80, -0.86, 0.98, 1.0, 8.0, xs=(-0.45, 0.0, 0.45), ys=(-0.55, -0.05, 0.45), mat="whiteconcrete", t=0.035)
        # 停機坪側（−x）懸挑雨遮＋鋼柱
        g.box(-0.96, -0.76, -0.82, 0.96, 5.8, 7.0, "company")
        for y in (-0.70, -0.20, 0.30, 0.80):
            g.box(-0.94, -0.90, y - 0.02, y + 0.02, 0, 5.8, "darksteel")
        # 陸側（+x）下客門廊雨遮
        g.box(0.80, 0.96, -0.60, 0.65, 5.6, 6.8, "apron")
        for y in (-0.52, 0.02, 0.56):
            g.box(0.92, 0.95, y - 0.02, y + 0.02, 0, 5.6, "darksteel")
    elif part == 4:                                           # 角落航廈上層＋拱形玻璃採光中庭（頂部部件）
        g.box(-0.78, 0.82, -0.88, 1.0, 0, 12.2, "whiteconcrete")
        g.band(-0.78, 0.82, -0.88, 0.98, 1.2, 5.4, "blueglass")
        g.band(-0.78, 0.82, -0.88, 0.98, 6.6, 10.8, "blueglass")
        facade_piers(g, -0.78, 0.82, -0.88, 0.98, 0, 12.2, xs=(-0.45, 0.0, 0.45), ys=(-0.55, -0.05, 0.45), mat="whiteconcrete", t=0.036)
        # 挑簷與公司色飾帶＋凹入屋頂女兒牆
        g.box(-0.84, 0.86, -0.92, 1.0, 11.4, 12.6, "company")
        g.box(-0.86, 0.88, -0.94, 1.0, 12.6, 13.8, "whiteconcrete")
        g.box(-0.74, 0.76, -0.82, 0.96, 12.6, 14.0, "darkconcrete")    # 凹入屋頂面
        # 屋頂中庭玻璃採光拱頂＋鋼肋
        g.box(-0.52, 0.50, -0.58, 0.62, 13.8, 16.4, "blueglass")
        g.vault(-0.54, 0.52, -0.60, 0.64, 16.4, 4.6, "blueglass", ridge="y", segs=8)
        for y in (-0.58, -0.18, 0.22, 0.62):
            g.vault(-0.56, 0.54, y - 0.025, y + 0.025, 16.4, 5.0, "whiteconcrete", ridge="y", segs=8)
        # 屋頂空調機箱
        g.box(0.56, 0.74, -0.74, -0.32, 13.8, 16.2, "apron")
        g.box(0.56, 0.74, 0.30, 0.72, 13.8, 16.0, "apron")
    elif part == 6:                                           # 航廈主體底層（旋轉 1 → 正面朝局部 −x）＋兩座空橋
        g.box(-0.58, 0.82, -1.0, 1.0, 0, 1.2, "darkconcrete")
        g.box(-0.56, 0.80, -1.0, 1.0, 1.2, 8.0, "whiteconcrete")
        g.band(-0.56, 0.80, -0.98, 0.98, 1.4, 7.2, "blueglass")
        for y in (-0.75, 0.0, 0.75):
            g.box(-0.57, -0.54, y - 0.16, y + 0.16, 1.6, 5.0, "lit")
        facade_piers(g, -0.56, 0.80, -1.0, 1.0, 1.0, 8.0, ys=(-0.82, -0.34, 0.16, 0.66), mat="whiteconcrete", t=0.036)
        # 陸側連續雨遮
        g.box(0.80, 0.96, -1.0, 1.0, 5.6, 6.8, "apron")
        for y in (-0.75, -0.25, 0.25, 0.75):
            g.box(0.92, 0.95, y - 0.02, y + 0.02, 0, 5.6, "darksteel")
        # 登機空橋（圓柱接頭＋玻璃鋼構橋身＋支撐腳＋接機防雨罩）
        for y in (-0.50, 0.50):
            g.cyl(-0.60, y, 0, 7.6, 0.11, "whiteconcrete", v=10)
            g.box(-0.96, -0.60, y - 0.08, y + 0.08, 4.2, 7.4, "silver")
            g.box(-0.94, -0.62, y - 0.085, y + 0.085, 5.2, 6.6, "blueglass")
            g.box(-0.88, -0.82, y - 0.03, y + 0.03, 0, 4.2, "darksteel")
            g.box(-1.00, -0.95, y - 0.095, y + 0.095, 4.0, 7.6, "darkconcrete")
    elif part == 7:                                           # 航廈主體上層（中央留 z=12 平台承接塔台 part 8）
        g.box(-0.60, 0.82, -1.0, 1.0, 0, 10.6, "whiteconcrete")
        g.band(-0.60, 0.82, -0.98, 0.98, 1.2, 4.8, "blueglass")
        g.band(-0.60, 0.82, -0.98, 0.98, 5.8, 9.6, "blueglass")
        facade_piers(g, -0.60, 0.82, -1.0, 1.0, 0, 10.6, ys=(-0.82, -0.34, 0.16, 0.66), mat="whiteconcrete", t=0.038)
        # 翼狀懸挑簷口＋公司色飾帶＋凹入屋頂面（中央 -0.34..0.34 維持 z=12 平整）
        g.box(-0.66, 0.84, -1.0, 1.0, 9.6, 10.6, "company")
        g.box(-0.76, 0.86, -1.0, 1.0, 10.6, 12.0, "whiteconcrete")
        g.box(-0.54, 0.74, -1.0, 1.0, 11.4, 12.05, "darkconcrete")
        # 兩側縱向採光天窗＋屋頂鋼構拱肋（避開中央塔台區 y in [-0.34, 0.34]）
        for y0, y1 in ((-0.96, -0.40), (0.40, 0.96)):
            g.box(-0.34, 0.50, y0, y1, 12.0, 14.2, "blueglass")
            g.gable(-0.37, 0.53, y0 - 0.02, y1 + 0.02, 14.2, 2.6, "whiteconcrete", ridge="y")
        for y in (-0.94, -0.42, 0.42, 0.94):
            g.box(-0.74, 0.84, y - 0.025, y + 0.025, 11.8, 13.0, "whiteconcrete")
        g.box(0.56, 0.74, -0.24, 0.24, 12.0, 14.0, "apron")   # 屋頂機械箱
    elif part == 8:                                           # 航廈屋頂上的現代化高塔台（h66）
        g.box(-0.28, 0.28, -0.28, 0.28, 0, 5.5, "concrete")
        g.band(-0.28, 0.28, -0.28, 0.28, 1.5, 4.2, "darkconcrete", out=0.01)
        g.box(-0.30, 0.30, -0.30, 0.30, 5.2, 6.2, "whiteconcrete")
        # 帶 4 道結構肋與電梯核心的收分塔身
        g.cyl(0, 0, 6.0, 38.0, 0.145, "whiteconcrete", v=12, rt=0.115)
        for dx, dy in ((0.13, 0), (-0.13, 0), (0, 0.13), (0, -0.13)):
            g.box(dx - 0.026, dx + 0.026, dy - 0.026, dy + 0.026, 6.0, 44.0, "concrete")
        g.box(0.08, 0.19, -0.06, 0.06, 6.0, 44.0, "whiteconcrete")
        g.box(0.18, 0.205, -0.035, 0.035, 9.0, 42.0, "blueglass")      # 電梯景觀細窗
        # 設備層擴口與外傾玻璃航管室
        g.cyl(0, 0, 44.0, 3.2, 0.15, "concrete", v=12, rt=0.26)
        g.cyl(0, 0, 47.0, 2.5, 0.26, "darkconcrete", v=12, rt=0.27)
        atc_cab(g, 0, 0, 49.5, 0.26, 0.34, 9.5, fascia="company", mullions=8)
    elif part == 10:                                          # 機庫底層（正面朝局部 +y，背面朝 −y 含工作間與窗戶）
        g.box(-0.94, 0.94, -0.78, 0.78, 0, 8.0, "corrugated")
        for x in (-0.94, -0.47, 0.0, 0.47, 0.94):
            g.box(x - 0.03, x + 0.03, -0.80, -0.76, 0, 8.0, "darksteel")
        for y in (-0.78, -0.26, 0.26, 0.78):
            for sx in (-0.94, 0.94):
                g.box(sx - 0.025, sx + 0.025, y - 0.03, y + 0.03, 0, 8.0, "darksteel")
        # 背面工作間附屬樓（讓面向城鎮的機庫背面也有建築細節）
        g.box(-0.72, 0.72, -0.92, -0.78, 0, 7.6, "whiteconcrete")
        g.box(-0.62, 0.62, -0.935, -0.915, 3.5, 6.2, "blueglass")
        for x in (-0.42, 0.0, 0.42):
            g.box(x - 0.025, x + 0.025, -0.94, -0.90, 0, 7.6, "whiteconcrete")
        # 正面四片滑動大門下段
        sliding_doors(g, -0.82, 0.82, 0.78, 0, 8.0, axis="y", leaves=4, mat="company", frame="darksteel")
    elif part == 11:                                          # 機庫上層＋拱形圓筒屋頂與天窗（頂部部件）
        g.box(-0.94, 0.94, -0.78, 0.78, 0, 6.2, "corrugated")
        g.box(-0.74, 0.74, -0.94, -0.78, 0, 1.0, "darksteel") # 背面工作間屋頂收邊
        sliding_doors(g, -0.82, 0.82, 0.78, 0, 5.2, axis="y", leaves=4, mat="company", frame="darksteel")
        g.box(-0.88, 0.88, 0.76, 0.88, 5.2, 6.6, "whiteconcrete")      # 門楣招牌樑
        # 圓筒拱頂＋5 道外露鋼構拱肋＋屋脊玻璃天窗＋山牆半圓窗
        g.vault(-0.96, 0.96, -0.82, 0.82, 6.2, 10.2, "lead", ridge="y", segs=10)
        for y in (-0.80, -0.40, 0.0, 0.40, 0.80):
            g.vault(-0.98, 0.98, y - 0.026, y + 0.026, 6.2, 10.9, "darksteel", ridge="y", segs=10)
        g.box(-0.22, 0.22, -0.74, 0.74, 15.0, 17.8, "blueglass")
        g.box(-0.25, 0.25, -0.77, 0.77, 17.8, 18.6, "darksteel")
        for sy in (-0.80, 0.80):
            g.vault(-0.56, 0.56, sy - 0.02, sy + 0.02, 7.2, 5.8, "blueglass", ridge="y", segs=8)
        for y in (-0.55, 0.55):
            g.cyl(0.55, y, 13.0, 2.6, 0.06, "silver", v=8)    # 屋頂排風帽
    elif part in (12, 23):                                    # 2×2 停機坪（機位）
        apron(g, 1.0, stands=[(-0.5, -0.4), (0.5, -0.4)] if part == 12 else [(-0.4, -0.5), (-0.4, 0.5)],
              lines=[(-1, 1, 0.39, 0.41)] if part == 12 else [(0.39, 0.41, -1, 1)])
    elif part == 14:                                          # 滑行道端點（1×1，較小）
        taxiway(g, 0.42, along="x", ends=(True, False))
    elif part == 15:                                          # 滑行道直線
        taxiway(g, 0.5, along="x", ends=(False, False))
    elif part == 16:                                          # 滑行道 T 字（往跑道接出）
        taxiway(g, 0.5, along="x", ends=(False, False), lights=False)
        g.box(-0.21, 0.21, 0.0, 0.54, 0, 1.0, "asphalt")
        g.mark(-0.012, 0.012, 0.0, 0.54, "yellowsteel")
    elif part in (17, 18, 20, 21, 28):                        # 1×1 停機坪
        apron(g, 0.5, stands=[(0, 0)] if part in (17, 21) else [],
              lines=[(-0.5, 0.5, -0.01, 0.01)] if part in (18, 20) else [(-0.01, 0.01, -0.5, 0.5)] if part == 28 else [])
    elif part in (19, 22):                                    # 滑行道接停機坪（往 −y 接出）
        taxiway(g, 0.5, along="x", ends=(False, False), lights=False)
        g.box(-0.21, 0.21, -0.54, 0.0, 0, 1.0, "apron")
        g.mark(-0.012, 0.012, -0.54, 0.0, "yellowsteel")
    elif part == 26:                                          # 立體停車大樓底層（旋轉 0，正面朝 +y、左面朝城鎮）
        g.box(-0.82, 0.82, -0.82, 0.82, 0, 8.0, "darkconcrete")
        for z in (0.0, 3.6, 7.0):
            g.box(-0.86, 0.86, -0.86, 0.86, z, min(8.0, z + 1.4), "whiteconcrete")
        facade_piers(g, -0.86, 0.86, -0.86, 0.86, 0, 8.0, xs=(-0.82, -0.40, 0.02, 0.44, 0.82),
                     ys=(-0.82, -0.40, 0.02, 0.44, 0.82), mat="concrete", t=0.032, out=0.012)
        # 角落玻璃電梯樓梯間核心
        g.box(-0.88, -0.44, -0.88, -0.44, 0, 8.0, "whiteconcrete")
        g.band(-0.88, -0.44, -0.88, -0.44, 1.0, 7.6, "blueglass", out=0.012)
        # 入口雨遮與公司色標誌
        g.box(-0.25, 0.25, 0.86, 0.96, 3.4, 4.4, "company")
    elif part == 27:                                          # 立體停車大樓上層＋露天頂樓停車場與停放車輛（頂部部件）
        g.box(-0.82, 0.82, -0.82, 0.82, 0, 9.4, "darkconcrete")
        for z in (0.0, 3.2, 6.4, 9.0):
            g.box(-0.86, 0.86, -0.86, 0.86, z, z + 1.3, "whiteconcrete")
        facade_piers(g, -0.86, 0.86, -0.86, 0.86, 0, 10.6, xs=(-0.82, -0.40, 0.02, 0.44, 0.82),
                     ys=(-0.82, -0.40, 0.02, 0.44, 0.82), mat="concrete", t=0.032, out=0.012)
        # 屋頂四周矮護牆＋外緣公司色飾條（中空四邊，不遮蓋露天柏油甲板）
        for (x0, x1, y0, y1) in ((-0.87, 0.87, -0.87, -0.78), (-0.87, 0.87, 0.78, 0.87),
                                 (-0.87, -0.78, -0.78, 0.78), (0.78, 0.87, -0.78, 0.78)):
            g.box(x0, x1, y0, y1, 9.8, 11.4, "whiteconcrete")
        for (x0, x1, y0, y1) in ((-0.885, 0.885, -0.885, -0.865), (-0.885, 0.885, 0.865, 0.885),
                                 (-0.885, -0.865, -0.865, 0.865), (0.865, 0.885, -0.865, 0.865)):
            g.box(x0, x1, y0, y1, 10.2, 11.0, "company")
        # 露天柏油停車甲板與白色車位格線
        g.box(-0.78, 0.78, -0.78, 0.78, 9.4, 9.9, "asphalt")
        for x in (-0.52, -0.26, 0.0, 0.26, 0.52):
            g.mark(x - 0.008, x + 0.008, -0.74, -0.32, "white", z=9.9)
            g.mark(x - 0.008, x + 0.008, 0.32, 0.74, "white", z=9.9)
        g.mark(-0.74, 0.74, -0.012, 0.012, "yellowsteel", z=9.9)
        # 頂樓迷你停放車輛
        cars = [(-0.13, -0.54, "red"), (0.13, -0.54, "white"), (0.39, -0.54, "blueglass"),
                (0.65, -0.54, "yellowsteel"), (-0.65, 0.54, "silver"), (-0.39, 0.54, "company2"),
                (0.13, 0.54, "white"), (0.65, 0.54, "darksteel")]
        for cx, cy, cm in cars:
            g.box(cx - 0.065, cx + 0.065, cy - 0.13, cy + 0.13, 9.9, 11.1, cm)
            g.box(cx - 0.052, cx + 0.052, cy - 0.06, cy + 0.06, 11.1, 11.9, "blueglass")
        # 角落電梯樓梯間突出屋頂的玻璃塔樓
        g.box(-0.88, -0.44, -0.88, -0.44, 0, 16.2, "whiteconcrete")
        g.band(-0.88, -0.44, -0.88, -0.44, 1.0, 15.0, "blueglass", out=0.012)
        g.box(-0.90, -0.42, -0.90, -0.42, 16.0, 17.0, "company")
        g.box(-0.86, -0.46, -0.86, -0.46, 17.0, 17.6, "apron")
        # 頂樓照明燈柱
        for (lx, ly) in ((0.68, -0.02), (-0.68, 0.02)):
            g.seg((lx, ly, 9.9), (lx, ly, 16.0), 0.012, "darksteel")
            g.box(lx - 0.04, lx + 0.04, ly - 0.04, ly + 0.04, 15.8, 16.4, "lit")
    elif 29 <= part <= 92:
        radar(g, part - 29)
    else:
        return []                                             # 93：空白
    return g.ops


MAKERS = {"SHIPST1": dock, "HPORT1": heliport, "AIRPORT1": airport1, "AIRPORT2": airport2, "AIRPORT3": airport3}


def make_model(name, info):
    return {"parts": [{"ops": MAKERS[name](p)} for p in range(len(info["heights"]))]}
