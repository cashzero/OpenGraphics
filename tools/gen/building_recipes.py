"""建築配方（M3）：依模板的部件結構與「配方」參數，產生 tools/blender/models/ops.py 用的幾何指令（model.json）。

部件角色由模板自動判斷（tools/objinfo.py 的 heights／variations）：
  ground = 每個變化組合的第一個部件且高度 ≤ 2；roof = 變化組合的最後一個部件；其餘為樓層。
  樓層再分 base（緊接在地面後、不重複）、typical（會重複）、feature（不重複的中段樓層）。
  不共用部件的變化組合（例如 [0,1,2,3] 與 [0,4,5,6]）視為 A／B 兩種設計，B 套用配方的 "b" 覆寫參數。

座標：平面以「格」為單位（佔地中心為原點，-y 為正面），高度以遊戲 px 為單位；每個部件都從 z = 0 起建。

配方 kind：
  house  ：住宅（牆面、門、窗、山形／四坡／平屋頂、煙囪、陽台、半木構、花園）
  block  ：城市街屋／公寓（底層店面或大門、標準層、簷口、平頂／山形／孟莎式屋頂）
  office ：辦公大樓（大廳、帶狀／格狀／玻璃帷幕窗、平頂／退縮塔頂／金字塔頂／尖塔）
  special：個別函式（教堂、城堡遺跡、音樂廳、法院、燈塔、電波塔、公司總部、商店街）
"""
from __future__ import annotations

import os

import math

# ---------------------------------------------------------------- 部件角色

PRIO = {"floor": 0, "roof": 1, "ground": 2}


def analyse(heights, variations):
    n = len(heights)
    role = [None] * n
    pos_min = [99] * n
    repeat = [1] * n
    for var in variations:
        for pos, p in enumerate(var):
            pos_min[p] = min(pos_min[p], pos)
            repeat[p] = max(repeat[p], var.count(p))
            if pos == 0 and heights[p] <= 2:
                r = "ground"
            elif pos == len(var) - 1:
                r = "roof"
            else:
                r = "floor"
            if role[p] is None or PRIO[r] > PRIO[role[p]]:
                role[p] = r
    # 設計組：扣掉所有組合都有的部件（共用地面、共用店面），剩下的部件有交集的組合視為同一組
    common = set(variations[0]).intersection(*map(set, variations[1:])) if len(variations) > 1 else set()
    groups = []                                            # [(部件集合, [組合 index…])]
    for vi, var in enumerate(variations):
        sv = set(var) - common
        hit = [g for g in groups if g[0] & sv]
        merged = (set(sv), [vi])
        for g in hit:
            merged[0].update(g[0])
            merged[1].extend(g[1])
            groups.remove(g)
        groups.append(merged)
    groups.sort(key=lambda g: min(g[1]))
    family = [0] * n
    for fi, (parts_, _v) in enumerate(groups):
        for q in parts_:
            family[q] = fi
    # 共用底層：歸給第一組
    sub = []
    for p in range(n):
        if role[p] == "floor":
            if repeat[p] > 1:
                sub.append("typical")
            elif pos_min[p] == 1:
                sub.append("base")
            else:
                sub.append("feature")
        else:
            sub.append(role[p])
    # 樓層在建築中的順序（第幾層），給門與店面判斷
    level = [pos_min[p] for p in range(n)]
    return role, sub, family, level


# ---------------------------------------------------------------- 幾何小工具

class Ops(list):
    def box(self, c, s, m, r=0):
        self.append({"op": "box", "c": [round(v, 4) for v in c], "s": [round(v, 4) for v in s], "m": m, **({"r": r} if r else {})})

    def gable(self, c, s, m, a="x"):
        self.append({"op": "gable", "c": c, "s": s, "m": m, "a": a})

    def hip(self, c, s, m, k=0.4):
        self.append({"op": "hip", "c": c, "s": s, "m": m, "k": k})

    def cyl(self, c, r, h, m, v=16, rt=None):
        op = {"op": "cyl", "c": c, "r": r, "h": h, "m": m, "v": v}
        if rt is not None:
            op["rt"] = rt
        self.append(op)

    def lathe(self, c, p, m, seg=24):
        self.append({"op": "lathe", "c": c, "p": p, "m": m, "seg": seg})

    def seg(self, a, b, m, r=0.01):
        self.append({"op": "seg", "a": a, "b": b, "m": m, "r": r})

    def ground(self, tiles, m):
        self.append({"op": "ground", "tiles": tiles, "m": m})


FACE = 0.012          # 貼在牆面上的窗、門的厚度（格）


def face_box(o: Ops, cx, cy, sx, sy, side, t, w, z, h, m, out=FACE):
    """在長方體 (cx, cy, sx, sy) 的某一面、沿該面位置 t（-0.5..0.5）貼一個 w 寬、h 高的薄片。"""
    if side == "-y":
        o.box((cx + t * sx, cy - sy / 2 - out / 2, z), (w, out, h), m)
    elif side == "+y":
        o.box((cx + t * sx, cy + sy / 2 + out / 2, z), (w, out, h), m)
    elif side == "-x":
        o.box((cx - sx / 2 - out / 2, cy + t * sy, z), (out, w, h), m)
    else:
        o.box((cx + sx / 2 + out / 2, cy + t * sy, z), (out, w, h), m)


SIDES = ("-y", "+y", "-x", "+x")


def windows(o: Ops, cx, cy, sx, sy, z0, z1, rows, per, m="glass", wf=0.5, hf=0.55, sills=None, skip=None, sides=SIDES):
    """四面開窗：per 為長邊（x 向）每列窗數，短邊依比例。skip(side, k, n, row) 回傳 True 時略過。"""
    hh = (z1 - z0) / rows
    wh = hh * hf
    for side in sides:
        L = sx if side in ("-y", "+y") else sy
        n = per if side in ("-y", "+y") else max(1, round(per * sy / max(sx, 1e-6)))
        ww = L / n * wf
        for r in range(rows):
            z = z0 + (r + 0.5) * hh - wh / 2
            for k in range(n):
                if skip and skip(side, k, n, r):
                    continue
                t = (k + 0.5) / n - 0.5
                face_box(o, cx, cy, sx, sy, side, t, ww, z, wh, m)
                if sills:
                    face_box(o, cx, cy, sx, sy, side, t, ww * 1.25, z - 0.7, 0.7, sills, out=FACE * 2.2)


def ribbon(o: Ops, cx, cy, sx, sy, z, h, m="glass"):
    for side in SIDES:
        L = sx if side in ("-y", "+y") else sy
        face_box(o, cx, cy, sx, sy, side, 0, L * 0.94, z, h, m)


def mullions(o: Ops, cx, cy, sx, sy, z, h, n, m):
    for side in SIDES:
        L = sx if side in ("-y", "+y") else sy
        k_n = n if side in ("-y", "+y") else max(1, round(n * sy / sx))
        for k in range(k_n + 1):
            t = k / k_n - 0.5
            face_box(o, cx, cy, sx, sy, side, t * 0.97, 0.012, z, h, m, out=FACE * 1.8)


def parapet(o: Ops, cx, cy, sx, sy, z, h, m, t=0.035):
    o.box((cx, cy - sy / 2 + t / 2, z), (sx, t, h), m)
    o.box((cx, cy + sy / 2 - t / 2, z), (sx, t, h), m)
    o.box((cx - sx / 2 + t / 2, cy, z), (t, sy, h), m)
    o.box((cx + sx / 2 - t / 2, cy, z), (t, sy, h), m)


def band(o: Ops, cx, cy, sx, sy, z, h, m, grow=0.03):
    o.box((cx, cy, z), (sx + grow, sy + grow, h), m)


def chimney(o: Ops, x, y, z, h, m="brick"):
    o.box((x, y, z), (0.085, 0.085, h), m)
    o.box((x, y, z + h), (0.105, 0.105, 1.1), "limestone")
    o.cyl((x - 0.022, y, z + h + 1.1), 0.016, 1.5, "terracotta", v=6)
    o.cyl((x + 0.022, y, z + h + 1.1), 0.016, 1.5, "terracotta", v=6)


def roof(o: Ops, kind, cx, cy, sx, sy, h, m, over=0.04, chim=None, dormers=0, along=None, stepped=False, wall_mat="plaster"):
    """屋頂（從 z = 0 起）。kind：gable / gx / gy / hip / pyramid / flat / mansard。"""
    if kind in ("gable", "gx", "gy"):
        a = along or ("x" if kind != "gy" else "y")
        if kind == "gable":
            a = "x" if sx >= sy else "y"
        rh = h * 0.90
        o.gable((cx, cy, 0), (sx + 2 * over, sy + 2 * over, rh), m, a)
        if stepped:
            # 歐式／阿爾卑斯階梯山牆（crow-stepped gable）
            steps = 4
            for side in (-1, 1):
                for s in range(steps):
                    frac = 1.0 - s / steps
                    z0 = rh * (s / steps)
                    sh = rh / steps + 1.4
                    if a == "x":
                        o.box((cx + side * (sx / 2 + 0.01), cy, z0), (0.055, (sy + 0.04) * frac, sh), wall_mat)
                    else:
                        o.box((cx, cy + side * (sy / 2 + 0.01), z0), ((sx + 0.04) * frac, 0.055, sh), wall_mat)
        if dormers:
            for k in range(dormers):
                t = (k + 0.5) / dormers - 0.5
                if a == "x":
                    dx, dy, w = cx + t * sx * 0.72, cy - sy * 0.30, min(0.22, sx / dormers * 0.42)
                    o.box((dx, dy, rh * 0.14), (w, 0.14, rh * 0.44), "white")
                    o.gable((dx, dy, rh * 0.56), (w * 1.18, 0.18, rh * 0.24), m, "y")
                    face_box(o, dx, dy, w, 0.14, "-y", 0, w * 0.58, rh * 0.20, rh * 0.30, "glass")
                else:
                    dx, dy, w = cx - sx * 0.30, cy + t * sy * 0.72, min(0.22, sy / dormers * 0.42)
                    o.box((dx, dy, rh * 0.14), (0.14, w, rh * 0.44), "white")
                    o.gable((dx, dy, rh * 0.56), (0.18, w * 1.18, rh * 0.24), m, "x")
                    face_box(o, dx, dy, 0.14, w, "-x", 0, w * 0.58, rh * 0.20, rh * 0.30, "glass")
    elif kind in ("hip", "pyramid"):
        rh = h * 0.86
        o.hip((cx, cy, 0), (sx + 2 * over, sy + 2 * over, rh), m, k=0.0 if kind == "pyramid" else 0.46)
        if dormers:
            for k in range(dormers):
                t = (k + 0.5) / dormers - 0.5
                dx, dy, w = cx + t * sx * 0.65, cy - sy * 0.34, min(0.20, sx / dormers * 0.38)
                o.box((dx, dy, rh * 0.14), (w, 0.14, rh * 0.44), "white")
                o.gable((dx, dy, rh * 0.56), (w * 1.18, 0.18, rh * 0.24), m, "y")
                face_box(o, dx, dy, w, 0.14, "-y", 0, w * 0.58, rh * 0.20, rh * 0.30, "glass")
    elif kind == "flat":
        o.box((cx, cy, 0), (sx, sy, min(h * 0.25, 2.2)), "darkconcrete")
        parapet(o, cx, cy, sx, sy, 0, min(h * 0.55, 3.6), m, t=0.045)
        if h >= 8:
            o.box((cx + sx * 0.18, cy + sy * 0.14, 2.0), (sx * 0.30, sy * 0.26, min(h * 0.55, 7.5)), "stone")
            o.box((cx - sx * 0.20, cy - sy * 0.16, 2.0), (sx * 0.18, sy * 0.16, min(h * 0.30, 3.8)), "steel")
    elif kind == "mansard":
        o.box((cx, cy, 0), (sx + 0.04, sy + 0.04, 1.5), "limestone")
        o.hip((cx, cy, 1.3), (sx + 0.02, sy + 0.02, h * 0.72), m, k=0.80)
        o.box((cx, cy, h * 0.74), (sx * 0.76, sy * 0.62, 1.0), "darkconcrete")
        parapet(o, cx, cy, sx * 0.78, sy * 0.64, h * 0.72, 1.6, "steel", t=0.025)
        n = max(2, dormers or round(sx / 0.24))
        for k in range(n):
            t = (k + 0.5) / n - 0.5
            for side in ("-y", "+y"):
                yy = cy + (-1 if side == "-y" else 1) * sy * 0.43
                w = min(0.18, sx / n * 0.42)
                o.box((cx + t * sx * 0.78, yy, h * 0.18), (w, 0.09, h * 0.36), "limestone")
                o.gable((cx + t * sx * 0.78, yy, h * 0.52), (w * 1.15, 0.11, h * 0.16), m, "y")
                face_box(o, cx + t * sx * 0.78, yy, w, 0.09, side, 0, w * 0.56, h * 0.22, h * 0.24, "glass")
        n2 = max(1, round(sy / 0.30))
        for k in range(n2):
            t = (k + 0.5) / n2 - 0.5
            for side in ("-x", "+x"):
                xx = cx + (-1 if side == "-x" else 1) * sx * 0.43
                w = min(0.18, sy / n2 * 0.42)
                o.box((xx, cy + t * sy * 0.78, h * 0.18), (0.09, w, h * 0.36), "limestone")
                face_box(o, xx, cy + t * sy * 0.78, 0.09, w, side, 0, w * 0.56, h * 0.22, h * 0.24, "glass")
    if chim:
        for (x, y) in chim:
            chimney(o, cx + x * sx, cy + y * sy, h * 0.30, h * 0.62)


# ---------------------------------------------------------------- house（寫實住宅與山區小屋）

def _yard_details(o: Ops, tiles, sx, sy, cx, cy, P):
    """住宅庭院：石牆、白木柵欄、車道、灌木與小徑，讓每棟住宅都有生活感且不突兀。"""
    yard = P.get("yard", "suburban")
    e = tiles / 2 - 0.04
    if yard == "stonewall":
        # 英式鄉村矮石牆（三側＋正面入口兩側）＋碎石小徑＋角落灌木
        for wx, wy, wsx, wsy in (
            (0.0, e, tiles * 0.94, 0.055),
            (e, 0.0, 0.055, tiles * 0.94),
            (-e, 0.0, 0.055, tiles * 0.94),
            (-e * 0.62, -e, tiles * 0.34, 0.055),
            (e * 0.62, -e, tiles * 0.34, 0.055),
        ):
            o.box((wx, wy, 0), (wsx, wsy, 2.4), "limestone")
        o.box((cx, -e * 0.52, 0), (0.14 * tiles, tiles * 0.48, 0.30), "gravel")
        _shrub(o, -e + 0.12, e - 0.12, 0.075, 5.5)
        _shrub(o, e - 0.12, -e + 0.14, 0.065, 4.5)
    elif yard == "picket":
        # 美式白木圍欄＋正面步道（適配中性碎石／草地）
        for wx, wy, wsx, wsy in (
            (0.0, e, tiles * 0.94, 0.028),
            (e, 0.0, 0.028, tiles * 0.94),
            (-e, 0.0, 0.028, tiles * 0.94),
            (-e * 0.64, -e, tiles * 0.32, 0.028),
            (e * 0.64, -e, tiles * 0.32, 0.028),
        ):
            o.box((wx, wy, 0.5), (wsx, wsy, 1.5), "whitewood")
        for x in (-e, 0.0, e):
            o.box((x, e, 0), (0.04, 0.04, 2.6), "white")
        for y in (-e, 0.0, e):
            o.box((e, y, 0), (0.04, 0.04, 2.6), "white")
            o.box((-e, y, 0), (0.04, 0.04, 2.6), "white")
        o.box((cx, -e * 0.54, 0), (0.16 * tiles, tiles * 0.46, 0.30), "pavement")
    elif yard == "alpine":
        # 山區木欄＋碎石前院＋柴堆＋小松樹
        o.box((cx, -e * 0.50, 0), (sx * 0.92, tiles * 0.46, 0.28), "gravel")
        for wx, wy, wsx, wsy in ((0.0, e, tiles * 0.92, 0.03), (e, 0.0, 0.03, tiles * 0.92)):
            o.box((wx, wy, 0.8), (wsx, wsy, 1.3), "wood")
        o.box((-e + 0.12, e - 0.12, 0), (0.14, 0.09, 2.2), "logs")
        _shrub(o, e - 0.12, e - 0.12, 0.075, 6.8)
    elif yard == "terrace":
        # 連棟街屋／城鎮商宅：人行道鋪面＋後方矮磚牆
        o.box((0.0, e, 0), (tiles * 0.96, 0.05, 2.8), "brick")
    elif yard == "lodge":
        # 2×2 山區大旅館：寬闊碎石車道＋兩側花圃松柏
        o.box((0, -0.78, 0), (1.42, 0.34, 0.35), "pavement")
        for dx in (-0.78, 0.78):
            _shrub(o, dx, -0.74, 0.10, 10.5)
            _shrub(o, dx, 0.76, 0.10, 11.5)
    else:
        # 英美郊區獨棟／雙併住宅：樹籬、側邊車道與前院灌木
        o.box((0.0, e, 0), (tiles * 0.94, 0.055, 2.4), "hedge")
        o.box((e, 0.0, 0), (0.055, tiles * 0.94, 2.4), "hedge")
        o.box((-e + 0.12, -0.05, 0), (0.20 * tiles, tiles * 0.84, 0.28), "pavement")
        o.box((cx, -e * 0.54, 0), (0.14 * tiles, tiles * 0.44, 0.28), "pavement")
        _shrub(o, e - 0.12, -e + 0.14, 0.07, 5.2)


def house(part, sub, fam, level, h, P, large):
    o = Ops()
    sx, sy = P.get("fp", (0.64, 0.48))
    if os.environ.get("OG_RENDER_STYLE", "vanilla") == "vanilla":
        sx, sy = min(sx * 1.18, 0.90 if not large else 1.82), min(sy * 1.18, 0.88 if not large else 1.66)
    cx, cy = P.get("off", (0.0, 0.04))
    roofm = P.get("roofmat", "slate")
    if roofm == "company":
        roofm = "terracotta"
    wing = P.get("wing")   # None | "garage" | "ell" | "side" | "porch_wing"

    if sub == "ground":
        tiles = 2 if large else 1
        o.ground(tiles, P.get("ground", "grass"))
        _yard_details(o, tiles, sx, sy, cx, cy, P)
        return o

    if sub == "roof":
        rk = P.get("roof", "gable")
        if rk == "gable" and P.get("along"):
            rk = "g" + P["along"]
        chim = P.get("chimneys", [(0.28, 0.10)] if P.get("chimney", True) else None)
        roof(o, rk, cx, cy, sx, sy, h, roofm, over=P.get("over", 0.05), chim=chim,
             dormers=P.get("dormers", 0), stepped=P.get("stepped", False), wall_mat=P.get("upper", P.get("mat", "plaster")))
        if wing == "ell":
            # L 型交錯山牆副屋頂，立體輪廓倍增
            wx, wy = cx - sx * 0.24, cy - sy * 0.36
            wsx, wsy = sx * 0.48, sy * 0.42
            o.gable((wx, wy, 0), (wsx + 0.08, wsy + 0.08, h * 0.72), roofm, "y")
        return o

    # 牆體（底層與上層）
    first = level <= 1
    mat = P.get("mat", "plaster") if (first or "upper" not in P) else P["upper"]
    o.box((cx, cy, 0), (sx, sy, h), mat)
    # 基礎石台基（所有獨棟住宅底層加微凸石基，告別貼地紙盒感）
    if first:
        band(o, cx, cy, sx, sy, 0, min(2.0, h * 0.22), P.get("plinth", "stone"), grow=0.02)
    # 美式魚鱗板／古典住宅四角白木邊條
    if P.get("corners"):
        cm = P["corners"]
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.box((cx + dx * (sx / 2 - 0.005), cy + dy * (sy / 2 - 0.005), 0), (0.045, 0.045, h), cm)
    doors = P.get("doors", 1) if first else 0
    per = P.get("win", 2)
    door_at = [((k + 0.5) / doors - 0.5) for k in range(doors)]

    def skip(side, k, n, r):
        if side != "-y" or not doors:
            return False
        t = (k + 0.5) / n - 0.5
        return any(abs(t - d) < 0.5 / n for d in door_at)

    # 帶白框細緻窗戶（高度比例較克制真實，不變成巨黑塊）
    windows(o, cx, cy, sx, sy, h * 0.24, h * 0.88, 1, per + (doors if first else 0),
            wf=0.44, hf=0.62, sills=P.get("sills", "white"), skip=skip)
    # 歐式／山區百葉窗板
    if P.get("shutters"):
        sm = P["shutters"]
        for side in ("-y", "+y"):
            n = per + (doors if first else 0)
            for k in range(n):
                if skip(side, k, n, 0):
                    continue
                t = (k + 0.5) / n - 0.5
                off = 0.28 / n
                face_box(o, cx, cy, sx, sy, side, t - off, sx / n * 0.14, h * 0.28, h * 0.44, sm, out=FACE * 1.4)
                face_box(o, cx, cy, sx, sy, side, t + off, sx / n * 0.14, h * 0.28, h * 0.44, sm, out=FACE * 1.4)

    for d in door_at:
        face_box(o, cx, cy, sx, sy, "-y", d, min(0.11, sx / (per + doors) * 0.52), 0, h * 0.72, P.get("door", "darkwood"))
        if P.get("porch") and first and not P.get("veranda"):
            px = cx + d * sx
            py = cy - sy / 2 - 0.07
            o.box((px, py, 0), (0.20, 0.14, 1.0), "stone")
            o.gable((px, py, h * 0.72), (0.24, 0.18, 3.2), roofm, "y")
            for dx in (-0.08, 0.08):
                o.cyl((px + dx, py - 0.05, 1.0), 0.012, h * 0.72 - 1.0, "white", v=6)

    # 全寬帶柱門廊（美式住宅標配：地板＋白立柱＋斜雨遮）
    if P.get("veranda") and first:
        vy = cy - sy / 2 - 0.09
        vw = sx * 0.94
        o.box((cx, vy, 0), (vw, 0.18, 1.6), "lightwood")
        o.box((cx, vy - 0.08, 1.6), (vw, 0.02, 2.2), "white")
        for k in range(4):
            px = cx + (k / 3 - 0.5) * (vw - 0.06)
            o.box((px, vy - 0.075, 1.6), (0.028, 0.028, h * 0.78 - 1.6), "white")
        o.box((cx, vy, h * 0.78), (vw + 0.04, 0.21, 1.6), roofm)

    # 側翼／附屬車庫／L 型前凸翼（讓輪廓不再是單一矩形）
    if wing == "garage" and first:
        gx, gy = cx + sx / 2 + 0.11, cy + 0.04
        o.box((gx, gy, 0), (0.22, sy * 0.76, h * 0.88), mat)
        o.box((gx, gy, h * 0.88), (0.24, sy * 0.80, 1.4), "darkconcrete")
        face_box(o, gx, gy, 0.22, sy * 0.76, "-y", 0, 0.16, 0, h * 0.68, "whitewood")
    elif wing == "side" and first:
        gx, gy = cx + sx / 2 + 0.10, cy + 0.04
        o.box((gx, gy, 0), (0.20, sy * 0.70, h * 0.90), mat)
        o.gable((gx, gy, h * 0.90), (0.23, sy * 0.76, 4.2), roofm, "x")
        face_box(o, gx, gy, 0.20, sy * 0.70, "-y", 0, 0.10, h * 0.28, h * 0.42, "glass")
    elif wing == "ell":
        wx, wy = cx - sx * 0.24, cy - sy * 0.36
        wsx, wsy = sx * 0.48, sy * 0.42
        o.box((wx, wy, 0), (wsx, wsy, h), mat)
        face_box(o, wx, wy, wsx, wsy, "-y", 0, wsx * 0.48, h * 0.28, h * 0.48, "glass")
        face_box(o, wx, wy, wsx, wsy, "-y", 0, wsx * 0.56, h * 0.22, 0.7, "white", out=FACE * 2)

    if P.get("timber"):
        tm = "darkwood"
        for t in (-0.5, -0.17, 0.17, 0.5):
            for side in SIDES:
                face_box(o, cx, cy, sx, sy, side, t * 0.985, 0.018, 0, h, tm, out=FACE * 1.5)
        for z in (0, h * 0.5, h - 0.7):
            band(o, cx, cy, sx, sy, z, 0.7, tm, grow=0.015)

    if P.get("balcony") and not first:
        by = cy - sy / 2 - 0.075
        o.box((cx, by, 0.2), (sx * 0.94, 0.15, 0.9), "wood")
        o.box((cx, by - 0.068, 0.9), (sx * 0.94, 0.022, h * 0.36), "darkwood")
        o.box((cx, by - 0.075, h * 0.38), (sx * 0.96, 0.028, 0.65), "lightwood")
        # 陽台花槽綠葉點綴
        for fx in (-0.28, 0.0, 0.28):
            o.box((cx + fx * sx, by - 0.085, h * 0.35), (sx * 0.16, 0.035, 1.0), "hedge")

    if P.get("bay") and first:
        o.box((cx - sx * 0.24, cy - sy / 2 - 0.06, 0), (sx * 0.34, 0.12, h * 0.88), mat)
        o.hip((cx - sx * 0.24, cy - sy / 2 - 0.06, h * 0.88), (sx * 0.38, 0.15, 2.2), roofm, k=0.5)
        face_box(o, cx - sx * 0.24, cy - sy / 2 - 0.06, sx * 0.34, 0.12, "-y", 0, sx * 0.24, h * 0.26, h * 0.48, "glass")
        face_box(o, cx - sx * 0.24, cy - sy / 2 - 0.06, sx * 0.34, 0.12, "-y", 0, sx * 0.28, h * 0.22, 0.7, "white", out=FACE * 2)

    if "trim" in P:
        band(o, cx, cy, sx, sy, h - 0.9, 0.9, P["trim"], grow=0.025)
    return o


# ---------------------------------------------------------------- block（城市街屋、公寓）

def shopfront(o, cx, cy, sx, sy, h, P):
    """寫實街屋店面：櫥窗、深木／石材店框與真實布棚（不再強制使用鮮紅公司色）。"""
    m = P.get("shopmat", "darkwood")
    awning = P.get("awning", "terracotta")
    if awning == "company":
        awning = "terracotta"
    for side in SIDES:
        L = sx if side in ("-y", "+y") else sy
        n = max(2, round(L / 0.28))
        for k in range(n):
            t = (k + 0.5) / n - 0.5
            face_box(o, cx, cy, sx, sy, side, t, L / n * 0.74, h * 0.10, h * 0.62, "glass")
            face_box(o, cx, cy, sx, sy, side, t, L / n * 0.80, h * 0.72, h * 0.14, m, out=FACE * 1.5)
    o.box((cx, cy - sy / 2 - 0.055, h * 0.68), (sx * 0.96, 0.11, 1.0), awning)
    o.box((cx - sx / 2 - 0.055, cy, h * 0.68), (0.11, sy * 0.96, 1.0), awning)


def block(part, sub, fam, level, h, P, large):
    o = Ops()
    shape = P.get("shape", "rect")
    sx, sy = P.get("fp", (0.82, 0.72) if not large else (1.74, 1.54))
    cx, cy = P.get("off", (0.0, 0.0))
    mat = P.get("mat", "brick")
    roofm = P.get("roofmat", "slate")
    if roofm == "company":
        roofm = "terracotta"

    if sub == "ground":
        o.ground(2 if large else 1, P.get("ground", "pavement"))
        if large and shape == "L":
            # 轉角綠地小花園
            o.box((0.52, -0.52, 0), (0.56, 0.56, 0.35), "grass")
            _shrub(o, 0.62, -0.60, 0.08, 6.5)
        return o

    # ---- 圓柱型高層現代公寓（BLDCTY20）
    if shape == "cyl":
        R = P.get("r", 0.76)
        if sub == "base":
            o.cyl((0, 0, 0), R + 0.04, h, "stone", v=24)
            o.cyl((0, 0, 2.0), R + 0.05, h - 4.0, "glass", v=24)
            for k in range(12):
                a = 2 * math.pi * k / 12
                o.box(((R + 0.03) * math.cos(a), (R + 0.03) * math.sin(a), 0), (0.06, 0.06, h), "limestone")
            o.box((0, -R - 0.08, h * 0.68), (0.58, 0.18, 1.4), "darksteel")
            o.cyl((0, 0, h - 1.5), R + 0.06, 1.5, "limestone", v=24)
            return o
        if sub == "roof":
            o.cyl((0, 0, 0), R, 12.0, mat, v=24)
            o.cyl((0, 0, 11.5), R + 0.03, 2.8, "limestone", v=24)
            o.cyl((0, 0, 12.0), R * 0.92, 1.5, "darkconcrete", v=24)
            o.cyl((0, 0, 13.0), R * 0.52, min(h - 13.5, 9.5), "limestone", v=20)
            o.cyl((0, 0, 13.0 + min(h - 13.5, 9.5)), R * 0.44, 1.4, "blueglass", v=16)
            return o
        # typical（退縮陽台＋垂直白柱格柵）
        o.cyl((0, 0, 0), R - 0.04, h, "glass", v=24)
        o.cyl((0, 0, 0), R + 0.01, h * 0.34, mat, v=24)
        for k in range(16):
            a = 2 * math.pi * k / 16
            o.box((R * math.cos(a), R * math.sin(a), 0), (0.045, 0.045, h), "limestone")
        return o

    # ---- L 型現代住宅樓（BLDCTY17）
    if shape == "L":
        w1 = (cx - 0.02, cy + 0.34, 1.72, 0.86)
        w2 = (cx - 0.42, cy - 0.34, 0.92, 0.86)
        if sub == "roof":
            for wx, wy, wsx, wsy in (w1, w2):
                o.box((wx, wy, 0), (wsx, wsy, 2.0), "darkconcrete")
                parapet(o, wx, wy, wsx, wsy, 0, 3.8, "limestone", t=0.045)
            # 樓梯機房＋圓形白色屋頂水塔＋太陽能／散熱設備
            o.box((-0.34, 0.34, 2.0), (0.56, 0.48, min(h * 0.62, 12.0)), "stone")
            o.box((-0.34, 0.34, 2.0 + min(h * 0.62, 12.0)), (0.58, 0.50, 1.2), "darkconcrete")
            o.cyl((0.40, 0.36, 2.0), 0.16, 4.5, "darksteel", v=10)
            o.cyl((0.40, 0.36, 6.5), 0.20, 7.5, "whiteconcrete", v=14)
            o.cyl((0.40, 0.36, 14.0), 0.21, 3.0, "slate", v=14, rt=0.02)
            o.box((-0.44, -0.34, 2.0), (0.34, 0.32, 6.5), "stone")
            return o
        for wx, wy, wsx, wsy in (w1, w2):
            o.box((wx, wy, 0), (wsx, wsy, h), mat)
            windows(o, wx, wy, wsx, wsy, h * 0.14, h * 0.90, 1, max(3, round(wsx / 0.24)), sills="limestone")
        # 轉角通高玻璃樓梯間＋混凝土陽台
        o.box((0.06, -0.02, 0), (0.24, 0.24, h), "blueglass")
        if sub != "base":
            o.box((-0.42, -0.80, 0.2), (0.76, 0.12, h * 0.42), "limestone")
            o.box((0.36, -0.12, 0.2), (0.68, 0.12, h * 0.42), "limestone")
        else:
            band(o, w1[0], w1[1], w1[2], w1[3], 0, 2.2, "stone", grow=0.02)
            band(o, w2[0], w2[1], w2[2], w2[3], 0, 2.2, "stone", grow=0.02)
        return o

    # ---- 標準矩形街屋／公寓
    if sub == "roof":
        rk = P.get("roof", "flat")
        rh = h
        if P.get("attic") and h > 14:
            fh = P.get("floor_h", 10)
            o.box((cx, cy, 0), (sx, sy, fh), mat)
            windows(o, cx, cy, sx, sy, fh * 0.20, fh * 0.88, 1, P.get("win", 4), sills=P.get("sills"))
            if "trim" in P:
                band(o, cx, cy, sx, sy, fh - 1.0, 1.0, P["trim"], grow=0.03)
            sub_o = Ops()
            roof(sub_o, rk, cx, cy, sx, sy, rh - fh, roofm, over=0.02, chim=P.get("chimneys"),
                 dormers=P.get("dormers", 0), stepped=P.get("stepped", False), wall_mat=mat)
            for op in sub_o:
                op = dict(op)
                if "c" in op:
                    op["c"] = [op["c"][0], op["c"][1], op["c"][2] + fh]
                o.append(op)
            return o
        roof(o, rk, cx, cy, sx, sy, rh, roofm, over=0.02, chim=P.get("chimneys"),
             dormers=P.get("dormers", 0), stepped=P.get("stepped", False), wall_mat=mat)
        if rk == "flat" and P.get("tank"):
            o.box((cx - sx * 0.16, cy + sy * 0.14, 1.8), (sx * 0.36, sy * 0.30, min(h * 0.55, 11.5)), "stone")
            o.box((cx - sx * 0.16, cy + sy * 0.14, 1.8 + min(h * 0.55, 11.5)), (sx * 0.38, sy * 0.32, 1.2), "darkconcrete")
            o.cyl((cx + sx * 0.22, cy + sy * 0.14, 1.8), min(sx, sy) * 0.10, min(h * 0.22, 4.5), "darksteel", v=8)
            o.cyl((cx + sx * 0.22, cy + sy * 0.14, 1.8 + min(h * 0.22, 4.5)), min(sx, sy) * 0.12, min(h * 0.38, 8.5), "wood", v=12)
            o.cyl((cx + sx * 0.22, cy + sy * 0.14, 1.8 + min(h * 0.60, 13.0)), min(sx, sy) * 0.13, 3.0, "slate", v=12, rt=0.02)
            o.box((cx + sx * 0.18, cy - sy * 0.22, 1.8), (0.18, 0.14, min(h * 0.25, 4.5)), "steel")
        return o

    o.box((cx, cy, 0), (sx, sy, h), mat if sub != "feature" else P.get("feature_mat", mat))
    if sub == "base" and P.get("shops"):
        shopfront(o, cx, cy, sx, sy, h, P)
    elif sub == "base":
        def skip(side, k, n, r):
            return side == "-y" and abs((k + 0.5) / n - 0.5) < 0.5 / n
        windows(o, cx, cy, sx, sy, h * 0.22, h * 0.85, 1, P.get("win", 4), sills=P.get("sills"), skip=skip)
        face_box(o, cx, cy, sx, sy, "-y", 0, 0.12, 0, h * 0.74, P.get("door", "darkwood"))
        band(o, cx, cy, sx, sy, 0, h * 0.18, P.get("plinth", "stone"), grow=0.02)
    else:
        rows = max(1, round(h / P.get("floor_h", 10)))
        windows(o, cx, cy, sx, sy, h * 0.12, h * 0.92, rows, P.get("win", 4), sills=P.get("sills"),
                m=P.get("glass", "glass"))
        if P.get("balconies"):
            bmat = P.get("balcony_mat", "limestone")
            if bmat == "company":
                bmat = "limestone"
            for r in range(rows):
                z = r * h / rows + 0.1
                o.box((cx, cy - sy / 2 - 0.055, z), (sx * 0.86, 0.11, 0.7), bmat)
                o.box((cx, cy - sy / 2 - 0.10, z), (sx * 0.86, 0.018, h / rows * 0.36), bmat)
    if "trim" in P:
        band(o, cx, cy, sx, sy, h - 0.9, 0.9, P["trim"], grow=0.025)
    return o


# ---------------------------------------------------------------- office（城市辦公與摩天大樓）

def _prism_tower(o: Ops, pts, z0, z1, m):
    o.append({"op": "prism", "p": pts, "z": [round(z0, 3), round(z1, 3)], "m": m})


def office(part, sub, fam, level, h, P, large):
    o = Ops()
    shape = P.get("shape", "rect")
    sx, sy = P.get("fp", (1.72, 1.54) if large else (0.82, 0.72))
    cx, cy = P.get("off", (0.0, 0.0))
    mat = P.get("mat", "concrete")
    style = P.get("style", "grid")
    fh = P.get("floor_h", 12)
    canopy = P.get("canopy", "darksteel")
    if canopy == "company":
        canopy = "darksteel"

    if sub == "ground":
        o.ground(2 if large else 1, P.get("ground", "pavement"))
        if P.get("plaza") and large:
            for dx in (-0.82, 0.82):
                o.box((dx, -0.82, 0), (0.20, 0.20, 1.6), "limestone")
                o.box((dx, -0.82, 1.6), (0.14, 0.14, 1.8), "hedge")
        return o

    # ---- 圓柱現代摩天大樓（BLDCTY12）：寬石材裙樓＋白帶藍玻璃圓塔
    if shape == "cyl_tower":
        R = P.get("r", 0.56)
        if sub == "base":
            o.box((0, 0, 0), (1.76, 1.60, h), "limestone")
            ribbon(o, 0, 0, 1.76, 1.60, 1.8, h - 4.0, "blueglass")
            mullions(o, 0, 0, 1.76, 1.60, 0, h, 8, "limestone")
            o.box((0, -0.86, h * 0.64), (0.64, 0.18, 1.4), "darksteel")
            o.box((0, 0, h - 1.5), (1.78, 1.62, 1.5), "whiteconcrete")
            return o
        if sub == "feature":
            o.cyl((0, 0, 0), R + 0.04, h, "whiteconcrete", v=24)
            o.cyl((0, 0, 2.0), R + 0.05, h - 4.0, "blueglass", v=24)
            return o
        if sub == "typical":
            o.cyl((0, 0, 0), R, h, "blueglass", v=24)
            o.cyl((0, 0, 0), R + 0.025, h * 0.34, "whiteconcrete", v=24)
            for k in range(12):
                a = 2 * math.pi * k / 12
                o.box((R * math.cos(a), R * math.sin(a), 0), (0.032, 0.032, h), "steel")
            return o
        # roof
        o.cyl((0, 0, 0), R, 10.0, "whiteconcrete", v=24)
        o.cyl((0, 0, 2.0), R + 0.015, 5.5, "blueglass", v=24)
        o.cyl((0, 0, 10.0), R * 0.90, 1.6, "darkconcrete", v=24)
        o.cyl((0, 0, 11.2), R * 0.45, 7.5, "stone", v=16)
        o.seg((0, 0, 18.0), (0, 0, h), "silver", r=0.014)
        return o

    # ---- 熨斗型三角切角大樓（BLDCTY28）
    if shape == "wedge":
        pts = [(-0.78, -0.78), (0.78, -0.78), (0.78, 0.18), (0.14, 0.78), (-0.78, 0.78)]
        pts_in = [(-0.74, -0.74), (0.74, -0.74), (0.74, 0.15), (0.12, 0.74), (-0.74, 0.74)]
        if sub == "base":
            _prism_tower(o, pts, 0, h, "limestone")
            _prism_tower(o, pts_in, 1.5, h - 2.0, "glass")
            o.box((0, -0.82, h * 0.68), (0.62, 0.16, 1.4), "darksteel")
            return o
        if sub == "roof":
            _prism_tower(o, pts, 0, 16.0, mat)
            _prism_tower(o, pts_in, 2.5, 13.0, "glass")
            _prism_tower(o, pts, 15.0, 18.0, "limestone")
            _prism_tower(o, pts_in, 16.5, 19.2, "darkconcrete")
            o.box((-0.18, -0.18, 19.0), (0.62, 0.56, 11.5), "stone")
            o.box((-0.18, -0.18, 30.5), (0.65, 0.59, 1.4), "darkconcrete")
            o.cyl((0.28, -0.34, 19.0), 0.12, 7.5, "darksteel", v=10)
            o.seg((-0.18, -0.18, 31.5), (-0.18, -0.18, h), "silver", r=0.012)
            return o
        _prism_tower(o, pts, 0, h, mat)
        _prism_tower(o, pts_in, h * 0.24, h * 0.82, "glass")
        for (px, py) in pts:
            o.box((px * 0.96, py * 0.96, 0), (0.12, 0.12, h), "limestone")
        return o

    # ---- 八角切角現代高樓（BLDCTY19）
    if shape == "chamfer":
        c = 0.22
        hx, hy = sx / 2, sy / 2
        pts = [(-hx + c, -hy), (hx - c, -hy), (hx, -hy + c), (hx, hy - c),
               (hx - c, hy), (-hx + c, hy), (-hx, hy - c), (-hx, -hy + c)]
        pts_g = [(x * 1.006, y * 1.006) for x, y in pts]
        if sub == "base":
            _prism_tower(o, pts, 0, h, "darkstone")
            _prism_tower(o, pts_g, 1.4, h - 1.8, "glass")
            o.box((0, -hy - 0.06, h * 0.68), (0.66, 0.16, 1.4), "steel")
            return o
        if sub == "feature":
            _prism_tower(o, pts, 0, h, "darkconcrete")
            _prism_tower(o, pts_g, 2.5, h - 2.5, "darksteel")
            return o
        if sub == "roof":
            _prism_tower(o, pts, 0, 4.0, mat)
            _prism_tower(o, [(x * 0.94, y * 0.94) for x, y in pts], 1.5, 4.8, "darkconcrete")
            o.box((0, 0, 4.5), (sx * 0.48, sy * 0.42, min(h - 5.0, 9.5)), "stone")
            o.cyl((-0.34, 0.24, 4.5), 0.12, 6.0, "steel", v=10)
            o.cyl((0.34, -0.24, 4.5), 0.10, 5.5, "darksteel", v=10)
            return o
        _prism_tower(o, pts, 0, h, mat)
        _prism_tower(o, pts_g, h * 0.24, h * 0.80, "glass")
        for (px, py) in pts:
            o.box((px * 0.97, py * 0.97, 0), (0.08, 0.08, h), "limestone")
        return o

    # ---- 喬治亞古典穹頂辦公樓（BLDCTY15）
    if shape == "georgian_cupola":
        if sub == "base":
            o.box((0, 0, 0), (sx, sy, h), "limestone")
            windows(o, 0, 0, sx, sy, 3.0, h - 2.5, 1, 7, m="glass", wf=0.45, hf=0.76, sills="white")
            band(o, 0, 0, sx, sy, h - 1.6, 1.6, "whiteconcrete", grow=0.05)
            return o
        if sub in ("typical", "feature"):
            o.box((0, 0, 0), (sx, sy, h), "brick")
            windows(o, 0, 0, sx, sy, 2.0, h - 2.0, 1, 8, m="glass", wf=0.45, hf=0.74, sills="white")
            for dx in (-1, 1):
                for dy in (-1, 1):
                    o.box((dx * (sx / 2 - 0.01), dy * (sy / 2 - 0.01), 0), (0.10, 0.10, h), "limestone")
            return o
        # roof (h=85)：兩層閣樓＋白石古典欄杆＋陡石板四坡頂＋白石多層圓柱鐘樓＋金色圓頂！
        o.box((0, 0, 0), (sx, sy, 16.0), "brick")
        windows(o, 0, 0, sx, sy, 2.5, 13.5, 1, 8, m="glass", wf=0.45, hf=0.72, sills="white")
        band(o, 0, 0, sx, sy, 14.5, 2.0, "limestone", grow=0.06)
        parapet(o, 0, 0, sx + 0.04, sy + 0.04, 16.5, 3.2, "whiteconcrete", t=0.05)
        o.hip((0, 0, 17.0), (sx * 0.96, sy * 0.94, 18.0), "slate", k=0.58)
        for cx0, cy0 in ((-0.52, 0.36), (0.52, 0.36), (-0.52, -0.36), (0.52, -0.36)):
            chimney(o, cx0, cy0, 26.0, 11.0, "brick")
        # 白色古典鐘樓＋金色穹頂（z=34..84）
        o.box((0, 0, 34.0), (0.64, 0.64, 13.0), "whiteconcrete")
        o.cyl((0, 0, 47.0), 0.28, 14.0, "whiteconcrete", v=16)
        o.cyl((0, 0, 49.0), 0.29, 9.5, "glass", v=16)
        for k in range(8):
            a = 2 * math.pi * k / 8
            o.cyl((0.295 * math.cos(a), 0.295 * math.sin(a), 47.0), 0.024, 14.0, "white", v=8)
        o.lathe((0, 0, 61.0), [(0.28, 0), (0.25, 5.5), (0.16, 11.5), (0.06, 15.0), (0.0, 17.0)], "gold", seg=16)
        o.seg((0, 0, 77.5), (0, 0, 84.0), "gold", r=0.012)
        return o

    # ---- 標準辦公與摩天大樓（含轉角玻璃穹頂 rotunda、古典孟莎、退縮高塔、玻璃帷幕）
    def storeys(z0, height, sx_, sy_, m=mat):
        o.box((cx, cy, z0), (sx_, sy_, height), m)
        n = max(1, round(height / fh))
        if style == "ribbon":
            for r in range(n):
                ribbon(o, cx, cy, sx_, sy_, z0 + r * height / n + height / n * 0.26, height / n * 0.54, P.get("glass", "glass"))
            mullions(o, cx, cy, sx_, sy_, z0, height, max(4, round(sx_ / 0.22)), P.get("piers", m))
        elif style == "glass":
            ribbon(o, cx, cy, sx_, sy_, z0 + 0.3, height - 0.6, P.get("glass", "blueglass"))
            mullions(o, cx, cy, sx_, sy_, z0, height, max(4, round(sx_ / 0.14)), P.get("frame", "steel"))
            for r in range(1, n):
                band(o, cx, cy, sx_, sy_, z0 + r * height / n - 0.3, 0.6, P.get("frame", "steel"), grow=0.028)
            if P.get("endcores"):
                for dx in (-1, 1):
                    o.box((cx + dx * (sx_ / 2 - 0.14), cy, z0), (0.28, sy_ * 0.86, height), P["endcores"])
        else:
            windows(o, cx, cy, sx_, sy_, z0 + height * 0.08, z0 + height * 0.96, n, P.get("win", max(4, round(sx_ / 0.18))),
                    m=P.get("glass", "glass"), wf=P.get("wf", 0.54), hf=0.62, sills=P.get("sills"))
        if P.get("piers"):
            for t in (-0.5, 0.5):
                for side in SIDES:
                    face_box(o, cx, cy, sx_, sy_, side, t * 0.97, 0.07, z0, height, P["piers"], out=FACE * 2)
        if shape == "rotunda":
            # 轉角圓柱玻璃塔身（BLDCTY29）
            rx, ry = cx - sx_ * 0.44, cy - sy_ * 0.44
            o.cyl((rx, ry, z0), 0.26, height, "limestone", v=16)
            o.cyl((rx, ry, z0 + height * 0.14), 0.27, height * 0.72, "glass", v=16)

    if sub == "base":
        o.box((cx, cy, 0), (sx, sy, h), P.get("base_mat", mat))
        if P.get("shops"):
            shopfront(o, cx, cy, sx, sy, h, P)
        else:
            ribbon(o, cx, cy, sx * 0.999, sy * 0.999, h * 0.08, h * 0.72, P.get("lobby_glass", "glass"))
            n = max(3, round(sx / 0.24))
            for side in SIDES:
                k_n = n if side in ("-y", "+y") else max(2, round(n * sy / sx))
                for k in range(k_n + 1):
                    face_box(o, cx, cy, sx, sy, side, (k / k_n - 0.5) * 0.97, 0.04, 0, h * 0.84, P.get("piers", P.get("base_mat", mat)), out=FACE * 2)
            o.box((cx, cy - sy / 2 - 0.06, h * 0.74), (sx * 0.38, 0.14, 1.0), canopy)
        if shape == "rotunda":
            o.cyl((cx - sx * 0.44, cy - sy * 0.44, 0), 0.27, h, "limestone", v=16)
        band(o, cx, cy, sx, sy, h - 1.2, 1.2, P.get("trim", P.get("base_mat", mat)), grow=0.04)
        return o

    if sub in ("typical", "feature"):
        if sub == "feature" and P.get("feature") == "band":
            o.box((cx, cy, 0), (sx, sy, h), P.get("feature_mat", "darkconcrete"))
            ribbon(o, cx, cy, sx, sy, h * 0.22, h * 0.56, "darksteel")
        elif sub == "feature" and P.get("feature") == "setback":
            k = P.get("setback", 0.86)
            storeys(0, h, sx * k, sy * k)
            parapet(o, cx, cy, sx, sy, 0, 2.0, P.get("trim", mat))
        else:
            storeys(0, h, sx, sy, P.get("feature_mat", mat) if sub == "feature" else mat)
        if "trim" in P and P.get("cornices", True):
            band(o, cx, cy, sx, sy, h - 0.7, 0.7, P["trim"], grow=0.025)
        return o

    # roof / crown
    crown = P.get("crown", "flat")
    if crown == "mansard":
        # 古典歐式石板孟莎大屋頂＋老虎窗＋高磚煙囪（BLDCTY1, BLDCTY6, BLDCTY7, BLDCTY8, BLDCTY9）
        body_h = max(0.0, h - 22.0)
        z = 0.0
        if body_h >= 8.0:
            storeys(0, body_h, sx, sy)
            band(o, cx, cy, sx, sy, body_h - 1.2, 1.2, P.get("trim", "limestone"), grow=0.04)
            z = body_h
        sub_o = Ops()
        chim = [(-0.34, 0.26), (0.34, 0.26), (-0.34, -0.26), (0.34, -0.26)] if large else [(0.26, 0.20), (-0.26, 0.20)]
        roof(sub_o, "mansard", cx, cy, sx, sy, h - z, P.get("roofmat", "slate"), chim=chim, dormers=4 if large else 2)
        for op in sub_o:
            op = dict(op)
            if "c" in op:
                op["c"] = [op["c"][0], op["c"][1], op["c"][2] + z]
            o.append(op)
        return o

    if shape == "rotunda":
        # BLDCTY29：2 層古典高樓身＋深礫石屋頂＋轉角標誌性藍玻璃鋼骨穹頂
        body_h = 26.0
        storeys(0, body_h, sx, sy)
        band(o, cx, cy, sx, sy, body_h - 1.6, 1.6, "limestone", grow=0.05)
        o.box((cx, cy, body_h), (sx * 0.96, sy * 0.96, 1.8), "darkconcrete")
        parapet(o, cx, cy, sx, sy, body_h, 3.8, "limestone", t=0.05)
        o.box((cx + 0.22, cy + 0.22, body_h + 1.5), (0.52, 0.44, 6.5), "stone")
        rx, ry = cx - sx * 0.44, cy - sy * 0.44
        o.cyl((rx, ry, body_h), 0.30, 6.5, "limestone", v=18)
        o.lathe((rx, ry, body_h + 6.5), [(0.28, 0), (0.27, 6.0), (0.21, 13.5), (0.11, 19.5), (0.0, 23.0)], "blueglass", seg=18)
        for k in range(8):
            a = 2 * math.pi * k / 8
            o.seg((rx + 0.28 * math.cos(a), ry + 0.28 * math.sin(a), body_h + 6.5),
                  (rx, ry, body_h + 29.5), "whiteconcrete", r=0.012)
        o.seg((rx, ry, body_h + 29.5), (rx, ry, h), "silver", r=0.012)
        return o

    z = 0.0
    if crown == "flat" or h < 18:
        o.box((cx, cy, 0), (sx, sy, min(h, 2.2)), "darkconcrete")
        parapet(o, cx, cy, sx, sy, 0, min(h, 4.2), P.get("trim", mat), t=0.045)
        if h >= 8:
            o.box((cx + sx * 0.16, cy + sy * 0.12, 2.0), (sx * 0.36, sy * 0.30, min(h * 0.65, 11.0)), P.get("plant", "stone"))
            o.box((cx + sx * 0.16, cy + sy * 0.12, 2.0 + min(h * 0.65, 11.0)), (sx * 0.38, sy * 0.32, 1.2), "darkconcrete")
            o.cyl((cx - sx * 0.22, cy + sy * 0.18, 2.0), min(sx, sy) * 0.10, min(h * 0.55, 7.5), "darksteel", v=12)
            for k in range(max(2, P.get("units", 2))):
                o.box((cx - sx * 0.24 + k * 0.18, cy - sy * 0.20, 2.0), (0.13, 0.10, min(h * 0.45, 5.2)), "steel")
        return o

    cap = {"pyramid": 0.36, "spire": 0.45, "setback": 0.28, "antenna": 0.35, "deco": 0.48, "dome": 0.44,
           "clock": 0.50}.get(crown, 0.32) * h
    body = h - cap
    k = 1.0
    tiers = max(1, round(body / (fh * 2.2)))
    for t in range(tiers):
        th = body / tiers
        storeys(z, th, sx * k, sy * k)
        band(o, cx, cy, sx * k, sy * k, z + th - 0.9, 0.9, P.get("trim", mat), grow=0.03)
        z += th
        if crown in ("setback", "deco", "spire", "antenna"):
            k *= P.get("step", 0.84)
    if crown == "pyramid":
        o.hip((cx, cy, z), (sx * k + 0.04, sy * k + 0.04, cap), P.get("roofmat", "copper"), k=0.12)
    elif crown == "dome":
        o.box((cx, cy, z), (sx * k, sy * k, 1.5), "darkconcrete")
        parapet(o, cx, cy, sx * k, sy * k, z, 3.4, P.get("trim", mat), t=0.05)
        r = min(sx, sy) * k * 0.36
        o.cyl((cx, cy, z + 1.5), r * 1.08, cap * 0.30, "limestone", v=16)
        o.cyl((cx, cy, z + 1.5 + cap * 0.08), r * 1.10, cap * 0.16, "glass", v=16)
        o.lathe((cx, cy, z + 1.5 + cap * 0.30), [(r, 0), (r * 0.92, cap * 0.24), (r * 0.70, cap * 0.44), (r * 0.35, cap * 0.60),
                                                 (0.0, cap * 0.66)], P.get("roofmat", "copper"), seg=16)
        o.cyl((cx, cy, z + 1.5 + cap * 0.94), 0.018, cap * 0.08, "gold", v=6)
    elif crown == "clock":
        w = min(sx, sy) * k * 0.42
        o.box((cx, cy, z), (sx * k, sy * k, 1.6), "darkconcrete")
        parapet(o, cx, cy, sx * k, sy * k, z, 3.2, P.get("trim", mat), t=0.045)
        o.box((cx, cy, z), (w, w, cap * 0.56), mat)
        for side in SIDES:
            face_box(o, cx, cy, w, w, side, 0, w * 0.56, z + cap * 0.24, w * 0.56 * 20, "white")
        o.hip((cx, cy, z + cap * 0.56), (w * 1.12, w * 1.12, cap * 0.44), P.get("roofmat", "copper"), k=0.0)
    else:
        o.box((cx, cy, z), (sx * k, sy * k, 1.6), "darkconcrete")
        parapet(o, cx, cy, sx * k, sy * k, z, 3.4, P.get("trim", mat), t=0.045)
        if crown == "setback":
            o.box((cx, cy, z), (sx * k * 0.54, sy * k * 0.50, cap * 0.78), P.get("plant", "stone"))
            o.box((cx, cy, z + cap * 0.78), (sx * k * 0.56, sy * k * 0.52, 1.2), "darkconcrete")
        elif crown == "antenna":
            o.box((cx, cy, z), (sx * k * 0.42, sy * k * 0.38, cap * 0.34), "stone")
            o.seg((cx, cy, z + cap * 0.34), (cx, cy, z + cap), "silver", r=0.016)
            o.seg((cx + 0.06, cy, z + cap * 0.34), (cx + 0.06, cy, z + cap * 0.75), "red", r=0.011)
        elif crown == "spire":
            o.box((cx, cy, z), (sx * k * 0.48, sy * k * 0.48, cap * 0.28), mat)
            o.cyl((cx, cy, z + cap * 0.28), min(sx, sy) * k * 0.20, cap * 0.72, P.get("roofmat", "steel"), v=8, rt=0.01)
        elif crown == "deco":
            for i, f in enumerate((0.72, 0.50, 0.32)):
                o.box((cx, cy, z + i * cap * 0.20), (sx * k * f, sy * k * f, cap * 0.20), mat)
                band(o, cx, cy, sx * k * f, sy * k * f, z + (i + 1) * cap * 0.20 - 0.7, 0.7, P.get("trim", "gold"))
            o.cyl((cx, cy, z + cap * 0.60), 0.032, cap * 0.40, "gold", v=8, rt=0.008)
    return o


# ---------------------------------------------------------------- 特殊建築

def _shrub(o: Ops, x, y, r=0.075, h=7.5, m="hedge"):
    """小型庭院柏樹／灌木（供教堂、住宅、總部庭園點綴）。"""
    o.cyl((x, y, 0), r * 0.25, h * 0.25, "darkwood", v=6)
    o.lathe((x, y, h * 0.18), [(0.0, 0), (r, h * 0.22), (r * 0.85, h * 0.56), (r * 0.42, h * 0.84), (0.0, h)], m, seg=8)


def _church_ground(P):
    o = Ops()
    style = P["style"]
    if style == "colonial":
        # 美式教堂：中性溫暖碎石地坪（沙漠與草地城鎮皆自然），配白木矮欄與正面石板步道
        o.ground(2, "gravel")
        o.box((0.0, -0.78, 0), (0.28, 0.42, 0.35), "pavement")
        o.box((-0.44, -0.58, 0), (0.34, 0.72, 0.35), "pavement")
        # 側後白木圍欄
        for sx, sy, cx, cy in (
            (1.88, 0.03, 0.0, 0.93),
            (0.03, 1.84, 0.93, 0.0),
            (0.03, 1.84, -0.93, 0.0),
        ):
            o.box((cx, cy, 0.6), (sx, sy, 1.6), "whitewood")
        for x in (-0.93, -0.46, 0.0, 0.46, 0.93):
            o.box((x, 0.93, 0), (0.045, 0.045, 3.0), "white")
        for y in (-0.90, -0.45, 0.0, 0.45, 0.90):
            o.box((0.93, y, 0), (0.045, 0.045, 3.0), "white")
            o.box((-0.93, y, 0), (0.045, 0.045, 3.0), "white")
        return o
    # 英式鄉村教堂：石牆墓園、碎石步道、墓碑與角落柏樹
    o.ground(2, "grass")
    o.box((0.0, -0.62, 0), (0.22, 0.72, 0.32), "gravel")
    o.box((-0.18, -0.44, 0), (0.68, 0.18, 0.32), "gravel")
    # 矮石圍牆（前方留入口）
    for cx, cy, sx, sy in (
        (0.0, 0.92, 1.88, 0.07),
        (0.92, 0.0, 0.07, 1.88),
        (-0.92, 0.0, 0.07, 1.88),
        (-0.56, -0.92, 0.76, 0.07),
        (0.56, -0.92, 0.76, 0.07),
    ):
        o.box((cx, cy, 0), (sx, sy, 3.4), "limestone")
        o.box((cx, cy, 3.4), (sx + 0.02, sy + 0.02, 0.6), "stone")
    # 入口石柱
    for x in (-0.17, 0.17):
        o.box((x, -0.92, 0), (0.10, 0.10, 5.2), "limestone")
    # 墓碑排
    for gx, gy in ((-0.68, 0.56), (-0.42, 0.62), (-0.12, 0.64), (0.22, 0.62), (0.55, 0.58),
                   (-0.66, -0.58), (-0.42, -0.64), (0.45, -0.62), (0.68, -0.56)):
        o.box((gx, gy, 0), (0.035, 0.08, 3.2), "limestone")
    # 角落柏樹灌木
    for tx, ty, r, h in ((-0.76, 0.76, 0.09, 11), (0.76, 0.76, 0.085, 10), (0.76, -0.74, 0.08, 9)):
        _shrub(o, tx, ty, r, h)
    return o


def church(n_parts, heights, P, large):
    """三座寫實教堂：chapel（英式石禮拜堂）、spire（哥德尖塔教堂）、colonial（美式白木教堂）。"""
    H = heights[1]
    o = Ops()
    style = P["style"]
    wall = P.get("mat", "limestone")
    roofm = P.get("roofmat", "slate")

    if style == "colonial":
        # 美式殖民風白色木造教堂（BLDCRCH3）：亮白魚鱗板、紅木瓦陡頂、門廊、多層白尖塔
        nx, ny, nh = 1.08, 0.64, 24.0
        cx = 0.18
        # 石砌台基
        o.box((cx, 0, 0), (nx + 0.04, ny + 0.04, 3.0), "stone")
        # 主堂木牆與轉角白壁柱
        o.box((cx, 0, 3.0), (nx, ny, nh), wall)
        for dx in (-1, 1):
            for dy in (-1, 1):
                o.box((cx + dx * (nx / 2 - 0.01), dy * (ny / 2 - 0.01), 3.0), (0.06, 0.06, nh), "white")
        band(o, cx, 0, nx, ny, 3.0 + nh - 1.2, 1.2, "white", grow=0.04)
        # 側牆五扇細長格窗（帶白色窗框）
        windows(o, cx, 0, nx, ny, 7.5, 24.0, 1, 5, m="glass", wf=0.34, hf=0.82, sills="white", sides=("-y", "+y"))
        # 陡峭紅木瓦屋頂＋白山牆簷板＋後方紅磚煙囪
        o.gable((cx, 0, 3.0 + nh), (nx + 0.08, ny + 0.10, 19.5), roofm, "x")
        chimney(o, cx + nx * 0.36, 0.12, 3.0 + nh + 7.0, 14.0, "brick")
        # 正面（-x）山牆入口門廊與石階
        px = cx - nx / 2 - 0.12
        o.box((px, 0, 0), (0.28, 0.36, 3.0), "stone")
        o.box((px - 0.14, 0, 0), (0.12, 0.28, 1.5), "stone")
        o.box((px, 0, 3.0), (0.24, 0.34, 15.0), wall)
        o.gable((px, 0, 18.0), (0.28, 0.40, 7.5), roofm, "x")
        face_box(o, px, 0, 0.24, 0.34, "-x", 0, 0.14, 3.0, 10.5, "darkwood")
        # 西側多層美式白色尖塔（從屋脊前段升起，總高 ~90px）
        tx = cx - nx / 2 + 0.04
        tw = 0.38
        # 第一段方塔身（延伸至 z=48）
        o.box((tx, 0, 3.0), (tw, tw, 45.0), wall)
        for side in SIDES:
            face_box(o, tx, 0, tw, tw, side, 0, tw * 0.32, 31.0, 10.0, "glass")
        band(o, tx, 0, tw, tw, 47.0, 1.8, "white", grow=0.05)
        parapet(o, tx, 0, tw + 0.04, tw + 0.04, 48.5, 2.5, "white", t=0.03)
        # 第二段白色鐘樓（z=48.8..63）
        bw = 0.28
        o.box((tx, 0, 48.8), (bw, bw, 14.2), "white")
        for side in SIDES:
            face_box(o, tx, 0, bw, bw, side, 0, bw * 0.42, 52.5, 7.5, "darkstone")
        band(o, tx, 0, bw, bw, 62.5, 1.5, "white", grow=0.04)
        # 尖細八角紅木瓦尖頂（z=64..88）＋金十字架
        o.cyl((tx, 0, 64.0), bw * 0.56, 24.5, roofm, v=8, rt=0.015)
        o.seg((tx, 0, 88.0), (tx, 0, 91.5), "gold", r=0.008)
        o.seg((tx, -0.03, 90.2), (tx, 0.03, 90.2), "gold", r=0.006)
        return o

    if style == "chapel":
        # 英式鄉村石造禮拜堂（BLDCRCH1，H=39）
        nx, ny, nh = 1.06, 0.56, 17.5
        cx = 0.04
        o.box((cx, 0, 0), (nx + 0.04, ny + 0.04, 2.2), "stone")
        o.box((cx, 0, 0), (nx, ny, nh), wall)
        o.gable((cx, 0, nh), (nx + 0.08, ny + 0.10, 15.0), roofm, "x")
        # 側牆扶壁（每邊 4 根）＋尖頂花格窗
        for k in range(4):
            bx = cx + ((k + 0.5) / 4 - 0.5) * nx * 0.86
            for dy in (-1, 1):
                o.box((bx, dy * (ny / 2 + 0.035), 0), (0.07, 0.07, nh * 0.78), wall)
                o.box((bx, dy * (ny / 2 + 0.025), nh * 0.78), (0.07, 0.05, 1.8), "stone")
        windows(o, cx, 0, nx, ny, 5.0, 15.5, 1, 3, m="glass", wf=0.28, hf=0.88, sills="stone", sides=("-y", "+y"))
        # 東側聖壇後殿
        ax = cx + nx / 2 + 0.18
        o.box((ax, 0, 0), (0.38, 0.40, nh * 0.84), wall)
        o.gable((ax, 0, nh * 0.84), (0.42, 0.46, 11.0), roofm, "x")
        windows(o, ax, 0, 0.38, 0.40, 4.5, 12.5, 1, 1, m="glass", wf=0.32, hf=0.85, sides=("+x",))
        # 南側入口門廊
        o.box((cx - 0.18, -ny / 2 - 0.13, 0), (0.28, 0.26, 11.5), wall)
        o.gable((cx - 0.18, -ny / 2 - 0.13, 11.5), (0.32, 0.30, 6.5), roofm, "y")
        face_box(o, cx - 0.18, -ny / 2 - 0.13, 0.28, 0.26, "-y", 0, 0.11, 0, 8.5, "darkwood")
        # 西山牆鐘架（雙柱＋拱頂＋吊鐘）
        wx = cx - nx / 2 - 0.01
        o.box((wx, 0, 0), (0.12, ny + 0.04, nh), wall)
        o.box((wx, -0.09, nh + 7.5), (0.10, 0.06, 11.0), wall)
        o.box((wx, 0.09, nh + 7.5), (0.10, 0.06, 11.0), wall)
        o.cyl((wx, 0, nh + 12.0), 0.04, 4.0, "gold", v=10, rt=0.02)
        o.gable((wx, 0, nh + 18.0), (0.14, 0.28, 5.5), wall, "x")
        return o

    # 哥德尖塔教堂（BLDCRCH2，H=85）：石灰岩中殿、雙側廊、入口門廊、三段鐘塔＋高聳八角尖頂
    nx, ny, nh = 1.10, 0.52, 20.5
    cx = 0.24
    o.box((cx, 0, 0), (nx, ny, nh), wall)
    o.gable((cx, 0, nh), (nx + 0.06, ny + 0.08, 15.5), roofm, "x")
    windows(o, cx, 0, nx, ny, 13.5, 19.5, 1, 5, m="glass", wf=0.28, hf=0.80, sides=("-y", "+y"))
    # 南北矮側廊＋扶壁
    for dy in (-1, 1):
        ay = dy * (ny / 2 + 0.12)
        o.box((cx, ay, 0), (nx * 0.90, 0.24, 11.5), wall)
        o.hip((cx, ay, 11.5), (nx * 0.92, 0.26, 4.5), roofm, k=0.85)
        for k in range(4):
            bx = cx + ((k + 0.5) / 4 - 0.5) * nx * 0.80
            o.box((bx, dy * (ny / 2 + 0.26), 0), (0.06, 0.06, 10.5), wall)
    # 南側入口門廊
    o.box((cx - 0.12, -(ny / 2 + 0.30), 0), (0.28, 0.22, 11.0), wall)
    o.gable((cx - 0.12, -(ny / 2 + 0.30), 11.0), (0.32, 0.26, 6.0), roofm, "y")
    face_box(o, cx - 0.12, -(ny / 2 + 0.30), 0.28, 0.22, "-y", 0, 0.11, 0, 8.2, "darkwood")
    # 西側三段哥德方塔（z=0..46）
    tx = cx - nx / 2 - 0.18
    tw = 0.40
    th = 46.0
    o.box((tx, 0, 0), (tw, tw, th), wall)
    # 四角階梯式扶壁
    for dx in (-1, 1):
        for dy in (-1, 1):
            o.box((tx + dx * tw * 0.50, dy * tw * 0.50, 0), (0.08, 0.08, th * 0.65), wall)
            o.box((tx + dx * tw * 0.48, dy * tw * 0.48, th * 0.65), (0.06, 0.06, th * 0.28), wall)
    for zband in (16.0, 32.0, 44.5):
        band(o, tx, 0, tw, tw, zband, 1.2, "stone", grow=0.04)
    # 鐘面與百葉鐘窗
    for side in SIDES:
        face_box(o, tx, 0, tw, tw, side, 0, tw * 0.34, 21.0, 7.5, "white", out=FACE * 1.6)
        face_box(o, tx, 0, tw, tw, side, 0, tw * 0.18, 22.8, 4.0, "black", out=FACE * 2.2)
        face_box(o, tx, 0, tw, tw, side, -0.18, tw * 0.18, 35.0, 7.5, "black")
        face_box(o, tx, 0, tw, tw, side, 0.18, tw * 0.18, 35.0, 7.5, "black")
    face_box(o, tx, 0, tw, tw, "-x", 0, tw * 0.34, 0, 10.5, "darkwood")
    # 女兒牆＋四角小尖塔＋八角石板尖頂（至 z=84）
    parapet(o, tx, 0, tw + 0.04, tw + 0.04, th, 3.0, wall, t=0.04)
    for dx in (-1, 1):
        for dy in (-1, 1):
            o.cyl((tx + dx * tw * 0.46, dy * tw * 0.46, th + 2.5), 0.038, 8.0, wall, v=6, rt=0.0)
    o.cyl((tx, 0, th + 1.5), tw * 0.46, H - th - 3.5, roofm, v=8, rt=0.015)
    o.seg((tx, 0, H - 2.2), (tx, 0, H + 0.5), "gold", r=0.007)
    return o


def castle(heights, P):
    """中世紀古堡遺跡（BLDCASTL，2×2，H=40）：自然土石山丘＋青苔內院、四座殘破圓塔、拱門城門、殘垣與碎石。"""
    H = heights[0]
    o = Ops()
    # 自然土石基座（無突兀綠方塊），內院點綴青苔草皮
    o.ground(2, "gravel")
    o.box((0, 0, 0), (1.42, 1.36, 0.45), "grass")
    o.box((0.08, -0.10, 0.45), (0.85, 0.72, 0.35), "dirt")
    st, lm, dk = "stone", "limestone", "darkstone"
    # 四座高低殘破圓形角塔
    towers = [
        (-0.62, 0.56, 0.26, H * 0.94, lm),   # 主角塔（最高）
        (0.60, 0.56, 0.22, H * 0.64, st),    # 東北塔
        (0.62, -0.54, 0.21, H * 0.48, lm),   # 東南殘塔
        (-0.62, -0.54, 0.20, H * 0.58, st),  # 西南塔
    ]
    for tx, ty, tr, th, tm in towers:
        o.cyl((tx, ty, 0), tr * 1.08, 4.0, dk, v=14, rt=tr)
        o.cyl((tx, ty, 4.0), tr, th - 4.0, tm, v=14)
        # 殘缺垛口（每塔挑 4–5 塊高低不等的垛牆）
        for k in range(6):
            if (k + int(tx * 10)) % 3 == 0:
                continue
            a = 2 * math.pi * k / 6
            o.box((tx + (tr - 0.03) * math.cos(a), ty + (tr - 0.03) * math.sin(a), th), (0.08, 0.08, 3.2), tm)
        # 狹窄箭孔
        for ang in (0, 1.57, 3.14, 4.71):
            o.box((tx + tr * math.cos(ang), ty + tr * math.sin(ang), th * 0.55), (0.04, 0.04, 4.2), "black")
    # 雙塔拱門城門（南側 -y）
    for dx in (-0.18, 0.18):
        o.cyl((dx, -0.60, 0), 0.13, H * 0.56, lm, v=12)
    o.box((0.0, -0.60, H * 0.30), (0.28, 0.16, H * 0.22), lm)
    o.box((0.0, -0.60, 0), (0.16, 0.18, H * 0.28), "black")
    # 殘缺城牆（厚度足、高低錯落＋垛口）
    walls = [
        ((-0.62, 0.02), (0.14, 0.90), 17.0, st),
        ((0.0, 0.58), (1.02, 0.14), 21.0, lm),
        ((0.61, 0.08), (0.14, 0.72), 13.5, st),
        ((-0.40, -0.58), (0.34, 0.13), 12.0, st),
        ((0.40, -0.56), (0.32, 0.13), 9.5, lm),
    ]
    for (wx, wy), (sx, sy), wh, wm in walls:
        o.box((wx, wy, 0), (sx, sy, wh), wm)
        n = max(2, int(max(sx, sy) / 0.16))
        for k in range(n):
            if k % 2 == 0:
                t = (k + 0.5) / n - 0.5
                cx = wx + t * sx if sx > sy else wx
                cy = wy + t * sy if sy > sx else wy
                o.box((cx, cy, wh), (0.09 if sx > sy else sx, 0.09 if sy > sx else sy, 2.8), wm)
    # 內院殘壁與碎石堆＋灌木青苔
    o.box((-0.18, 0.16, 0), (0.36, 0.12, 11.0), st)
    o.box((-0.30, 0.04, 0), (0.12, 0.28, 8.5), lm)
    for rx, ry, rs, rh in ((0.24, -0.22, 0.22, 3.8), (-0.18, -0.26, 0.16, 2.8), (0.32, 0.26, 0.20, 3.5), (0.02, 0.34, 0.18, 3.0)):
        o.hip((rx, ry, 0.4), (rs, rs * 0.85, rh), dk, k=0.25)
    for bx, by in ((-0.40, 0.38), (0.44, -0.34), (-0.42, -0.32)):
        _shrub(o, bx, by, 0.07, 5.0)
    return o


def concert_hall(sub, h, P):
    """新古典交響音樂廳（BLDHALL1，2×2，h=[1, 20, 24]）：六柱白色柱廊、磚石古典外牆、三角楣與銅綠斜屋頂。"""
    o = Ops()
    sx, sy = 1.72, 1.48
    if sub == "ground":
        o.ground(2, "pavement")
        o.box((0, -0.80, 0), (1.36, 0.24, 1.0), "limestone")
        o.box((0, -0.88, 0), (1.22, 0.14, 0.5), "limestone")
        o.box((0, 0.02, 0), (sx + 0.08, sy + 0.08, 0.6), "stone")
        return o
    if sub == "base":
        # 磚石基座＋退縮柱廊門廳
        o.box((0, 0.10, 0), (sx, sy - 0.18, h), "brick")
        band(o, 0, 0.10, sx, sy - 0.18, 0, 3.2, "limestone", grow=0.03)
        band(o, 0, 0.10, sx, sy - 0.18, h - 2.4, 2.4, "limestone", grow=0.05)
        # 兩側高聳拱窗與白色壁柱
        windows(o, 0, 0.10, sx, sy - 0.18, 4.5, h - 3.0, 1, 6, m="glass", wf=0.45, hf=0.82, sills="limestone", sides=("-x", "+x", "+y"))
        mullions(o, 0, 0.10, sx, sy - 0.18, 3.0, h - 5.2, 6, "limestone")
        # 正面古典六柱柱廊（白石灰岩圓柱＋深色大門）
        py = -sy / 2 + 0.05
        o.box((0, py + 0.06, 0), (sx * 0.86, 0.20, 2.2), "limestone")
        for k in range(6):
            x = -0.62 + 1.24 * k / 5
            o.cyl((x, py, 2.2), 0.044, h - 4.4, "limestone", v=12)
        o.box((0, py + 0.04, h - 2.4), (sx * 0.90, 0.22, 2.4), "limestone")
        for dx in (-0.30, 0.0, 0.30):
            face_box(o, 0, 0.10, sx, sy - 0.18, "-y", dx / sx, 0.14, 2.2, 10.5, "darkwood")
        return o
    # 屋頂（h=24）：古典三角山牆楣＋銅綠斜屋頂＋天窗＋後方舞台塔
    o.box((0, 0.04, 0), (sx + 0.04, sy + 0.02, 2.4), "limestone")
    parapet(o, 0, 0.04, sx + 0.04, sy + 0.02, 2.4, 2.6, "limestone", t=0.06)
    # 主廳高側窗鼓座＋銅綠山形大屋頂（沿 y 方向貫穿）
    o.box((0, 0.08, 2.4), (sx * 0.78, sy * 0.78, 7.5), "limestone")
    windows(o, 0, 0.08, sx * 0.78, sy * 0.78, 3.5, 9.0, 1, 5, m="glass", wf=0.52, hf=0.72, sides=("-x", "+x"))
    o.gable((0, 0.04, 9.6), (sx * 0.84, sy * 0.90, 13.5), "copper", "y")
    # 正面白色古典三角楣（緊接柱廊上方）
    o.gable((0, -sy / 2 + 0.16, 2.4), (sx * 0.86, 0.32, 11.0), "limestone", "y")
    # 屋脊裝飾天窗帶
    o.box((0, 0.08, 21.0), (0.24, sy * 0.56, 2.4), "limestone")
    o.box((0, 0.08, 22.8), (0.28, sy * 0.58, 0.9), "copper")
    # 兩側矮銅屋頂（覆蓋側廳）
    for dx in (-1, 1):
        o.box((dx * sx * 0.44, 0.08, 2.4), (sx * 0.14, sy * 0.82, 2.2), "copper")
    return o


def lighthouse(part, heights, P):
    """海岸燈塔（BLDLIGHT，1×1，h=[0, 84, 28×32]）：白石紅帶砌石塔身滿高 84px＋觀景廊道＋緊貼塔頂的 32 格旋轉燈室。"""
    o = Ops()
    if part == 0:
        o.ground(1, "gravel")
        # 矮白石護牆
        for cx, cy, sx, sy in ((0, 0.45, 0.92, 0.06), (0.45, 0, 0.06, 0.92)):
            o.box((cx, cy, 0), (sx, sy, 2.6), "limestone")
        # 守燈人白牆小屋（石板斜屋頂＋煙囪）
        o.box((0.22, -0.08, 0), (0.30, 0.38, 10.5), "whitewash")
        o.gable((0.22, -0.08, 10.5), (0.35, 0.43, 6.0), "slate", "y")
        face_box(o, 0.22, -0.08, 0.30, 0.38, "-y", 0, 0.10, 0, 7.0, "darkwood")
        face_box(o, 0.22, -0.08, 0.30, 0.38, "+x", 0, 0.12, 3.5, 4.5, "glass")
        chimney(o, 0.28, 0.04, 13.0, 5.5, "brick")
        return o
    if part == 1:
        # 滿高 84px 砌石圓錐燈塔（與 part 2 無縫銜接）
        H = heights[1]
        tx, ty = -0.10, 0.04
        # 石砌基礎台座（z=0..8）
        o.cyl((tx, ty, 0), 0.28, 8.0, "stone", v=20, rt=0.25)
        # 紅白相間 5 段錐塔（z=8..77）
        segs = [(8.0, 22.0, "whitewash"), (22.0, 36.0, "red"), (36.0, 52.0, "whitewash"),
                (52.0, 66.0, "red"), (66.0, 77.5, "whitewash")]
        for z0, z1, col in segs:
            r0 = 0.25 - 0.11 * (z0 - 8.0) / 69.5
            r1 = 0.25 - 0.11 * (z1 - 8.0) / 69.5
            o.cyl((tx, ty, z0), r0, z1 - z0, col, v=20, rt=r1)
        # 螺旋梯小窗與底部門
        o.box((tx, ty - 0.25, 0), (0.09, 0.06, 9.0), "darkwood")
        for wz, ang in ((18, -1.2), (32, -0.4), (48, 0.5), (62, -1.0)):
            wr = 0.25 - 0.11 * (wz - 8.0) / 69.5
            o.box((tx + wr * math.cos(ang), ty + wr * math.sin(ang), wz), (0.045, 0.045, 3.8), "black")
        # 托架石砌觀景廊道（z=77.5..82）＋深鐵欄杆（z=82..84.5）
        o.cyl((tx, ty, 77.5), 0.145, 2.5, "stone", v=20, rt=0.20)
        o.cyl((tx, ty, 80.0), 0.205, 2.2, "limestone", v=20)
        for k in range(10):
            a = 2 * math.pi * k / 10
            o.seg((tx + 0.19 * math.cos(a), ty + 0.19 * math.sin(a), 82.0),
                  (tx + 0.19 * math.cos(a), ty + 0.19 * math.sin(a), 84.6), "darksteel", r=0.008)
        o.cyl((tx, ty, 84.0), 0.195, 0.6, "darksteel", v=16)
        return o
    # 燈室（part 2..33，座落於塔頂中心 (-0.10, 0.04, 0)）
    frame = part - 2
    tx, ty = -0.10, 0.04
    o.cyl((tx, ty, 0), 0.125, 2.2, "darksteel", v=16)
    o.cyl((tx, ty, 2.2), 0.105, 9.5, "lit", v=16)
    for k in range(8):
        a = 2 * math.pi * k / 8
        o.seg((tx + 0.112 * math.cos(a), ty + 0.112 * math.sin(a), 2.0),
              (tx + 0.112 * math.cos(a), ty + 0.112 * math.sin(a), 11.8), "darksteel", r=0.009)
    o.lathe((tx, ty, 11.6), [(0.135, 0), (0.12, 2.5), (0.075, 5.2), (0.025, 7.0), (0.0, 8.2)], "copper", seg=16)
    o.seg((tx, ty, 19.5), (tx, ty, 23.0), "gold", r=0.007)
    # 柔和短旋轉光束（單側較強＋對側微光，不顯死硬長棍）
    a = 2 * math.pi * frame / 32
    L = 0.42
    o.seg((tx, ty, 7.0), (tx + L * math.cos(a), ty + L * math.sin(a), 6.2), "glow", r=0.018)
    o.seg((tx, ty, 7.0), (tx - L * 0.7 * math.cos(a), ty - L * 0.7 * math.sin(a), 6.4), "lit", r=0.014)
    return o


def transmitter(heights, P):
    """廣播電視塔（BLDTRANS，1×1，H=109）：粗壯可辨識的拉線鋼骨桁架塔、雙層微波碟平台與紅白頂端天線。"""
    H = heights[0]
    o = Ops()
    o.ground(1, "gravel")
    # 設備機房與冷氣機
    o.box((0.28, 0.24, 0), (0.28, 0.24, 7.5), "concrete")
    o.box((0.28, 0.24, 7.5), (0.30, 0.26, 1.0), "darkconcrete")
    face_box(o, 0.28, 0.24, 0.28, 0.24, "-y", 0, 0.10, 0, 5.5, "darksteel")
    # 中央基礎混凝土墩＋四角鋼索錨座
    o.box((0, 0, 0), (0.28, 0.28, 3.0), "concrete")
    for dx, dy in ((-0.42, -0.42), (0.42, -0.42), (0.42, 0.42), (-0.42, 0.42)):
        o.box((dx, dy, 0), (0.09, 0.09, 2.2), "concrete")
    # 粗壯鋼骨四角桁架塔（z=3..92，桿徑加粗確保 1× 縮放依舊清晰立體）
    levels = 9
    w0_base, w1_top = 0.145, 0.065
    pts = [(w0_base + (w1_top - w0_base) * i / levels, 3.0 + 89.0 * i / levels) for i in range(levels + 1)]
    for i in range(levels):
        (wa, za), (wb, zb) = pts[i], pts[i + 1]
        col = "silver" if i % 2 == 0 else "steel"
        corners = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        for dx, dy in corners:
            o.seg((dx * wa, dy * wa, za), (dx * wb, dy * wb, zb), col, r=0.017)
        for k in range(4):
            ax, ay = corners[k]
            bx, by = corners[(k + 1) % 4]
            # 水平框＋雙交叉斜撐
            o.seg((ax * wb, ay * wb, zb), (bx * wb, by * wb, zb), "darksteel", r=0.010)
            o.seg((ax * wa, ay * wa, za), (bx * wb, by * wb, zb), "steel", r=0.010)
            o.seg((bx * wa, by * wa, za), (ax * wb, ay * wb, zb), "steel", r=0.010)
    # 4 向雙層鋼索拉線（從塔身 48px 與 80px 拉到四角錨墩）
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        o.seg((dx * 0.42, dy * 0.42, 2.0), (dx * 0.10, dy * 0.10, 48.0), "darksteel", r=0.008)
        o.seg((dx * 0.42, dy * 0.42, 2.0), (dx * 0.075, dy * 0.075, 80.0), "darksteel", r=0.009)
    # 雙層高空微波碟與天線平台（z=72 與 z=88）
    for pz, pr in ((72.0, 0.14), (88.0, 0.12)):
        o.cyl((0, 0, pz), pr, 1.8, "darksteel", v=12)
        o.cyl((0, 0, pz + 3.2), pr * 1.02, 0.5, "steel", v=12)
    # 4 面白色微波轉播碟
    for ang, pz in ((0.4, 75.5), (2.0, 75.5), (3.5, 91.0), (5.1, 91.0)):
        o.cyl((0.12 * math.cos(ang), 0.12 * math.sin(ang), pz), 0.065, 3.2, "white", v=10)
    # 頂端紅白航空警示天線（z=92..109）
    o.cyl((0, 0, 92.0), 0.036, 5.5, "red", v=10, rt=0.028)
    o.cyl((0, 0, 97.5), 0.028, 5.5, "white", v=10, rt=0.020)
    o.cyl((0, 0, 103.0), 0.020, 6.0, "red", v=8, rt=0.008)
    return o


def headquarters(part, sub, level_group, h, heights, P):
    """寫實企業總部（HQ1，5 階段）：真實建築材質為主，僅以約 6–10% 主公司色做旗幟、入口與頂部飾帶點綴。"""
    o = Ops()
    if sub == "ground":
        if level_group == 0:
            # 階段 1：碎石工務院子、矮木圍籬與公司旗桿
            o.ground(2, "gravel")
            o.box((0.35, -0.45, 0), (0.65, 0.65, 0.35), "pavement")
            for cx, cy, sx, sy in ((0, 0.90, 1.82, 0.04), (0.90, 0, 0.04, 1.82), (-0.90, 0, 0.04, 1.82)):
                o.box((cx, cy, 0), (sx, sy, 2.8), "wood")
            _shrub(o, -0.74, 0.74, 0.08, 8.0)
            _shrub(o, 0.74, 0.74, 0.08, 7.5)
        elif level_group == 1:
            # 階段 2：鋪石前院＋兩側草坪花圃
            o.ground(2, "pavement")
            o.box((-0.64, 0.56, 0), (0.52, 0.62, 0.35), "grass")
            o.box((0.64, 0.56, 0), (0.52, 0.62, 0.35), "grass")
            _shrub(o, -0.72, 0.72, 0.08, 7.5)
            _shrub(o, 0.72, 0.72, 0.08, 7.5)
        else:
            # 階段 3–5：花崗岩企業廣場＋花槽＋旗桿
            o.ground(2, "pavement")
            for dx in (-0.78, 0.78):
                o.box((dx, -0.78, 0), (0.24, 0.24, 1.4), "limestone")
                o.box((dx, -0.78, 1.4), (0.18, 0.18, 1.6), "hedge")
        # 全階段皆有醒目的公司旗桿＋公司色旗幟
        o.seg((-0.66, -0.82, 0), (-0.66, -0.82, 18.0), "silver", r=0.011)
        o.box((-0.56, -0.82, 13.5), (0.18, 0.02, 4.0), "company")
        return o

    # 階段 1（part 1, h=29）：溫馨小型磚木雙層工務所（斜屋頂＋入口雨遮＋小車庫）
    if level_group == 0:
        o.box((-0.18, 0.14, 0), (0.86, 0.64, 13.0), "brick")
        o.gable((-0.18, 0.14, 13.0), (0.94, 0.72, 10.5), "slate", "x")
        windows(o, -0.18, 0.14, 0.86, 0.64, 3.5, 11.2, 1, 3, m="glass", wf=0.45, hf=0.65, sills="white")
        face_box(o, -0.18, 0.14, 0.86, 0.64, "-y", 0, 0.14, 0, 8.5, "darkwood")
        o.box((-0.18, -0.22, 8.6), (0.28, 0.14, 1.1), "company")   # 公司色門廊招牌
        chimney(o, 0.12, 0.24, 18.0, 9.5, "brick")
        # 側邊小倉儲棚
        o.box((0.46, 0.22, 0), (0.44, 0.44, 8.5), "lightwood")
        o.gable((0.46, 0.22, 8.5), (0.48, 0.48, 5.0), "slate", "y")
        return o

    # 階段 2（part 3, h=29）：現代 2 層紅磚＋石灰岩地區總部
    if level_group == 1:
        sx, sy = 1.38, 1.04
        o.box((0, 0.06, 0), (sx, sy, 21.0), "brick")
        band(o, 0, 0.06, sx, sy, 0, 2.5, "limestone", grow=0.03)
        band(o, 0, 0.06, sx, sy, 10.2, 1.2, "limestone", grow=0.03)
        band(o, 0, 0.06, sx, sy, 19.6, 1.8, "limestone", grow=0.04)
        windows(o, 0, 0.06, sx, sy, 3.0, 19.2, 2, 6, m="blueglass", wf=0.58, hf=0.58, sills="limestone")
        # 入口門廳雨遮（公司色飾帶）
        o.box((0, -sy / 2 - 0.06, 9.4), (0.58, 0.22, 1.4), "limestone")
        o.box((0, -sy / 2 - 0.08, 10.4), (0.60, 0.24, 0.9), "company")
        o.box((0, 0.06, 21.0), (sx * 0.96, sy * 0.96, 1.4), "darkconcrete")
        parapet(o, 0, 0.06, sx, sy, 21.0, 2.6, "limestone", t=0.045)
        o.box((0.26, 0.16, 22.0), (0.42, 0.34, 6.2), "stone")
        return o

    # 階段 3（parts 5,6,7）：5 層裝飾藝術石灰岩中層總部
    if level_group == 2:
        sx, sy = 1.54, 1.34
        if sub == "base":
            o.box((0, 0, 0), (sx, sy, h), "limestone")
            ribbon(o, 0, 0, sx, sy, h * 0.12, h * 0.68, "blueglass")
            mullions(o, 0, 0, sx, sy, 0, h, 6, "limestone")
            o.box((0, -sy / 2 - 0.07, h * 0.74), (0.68, 0.18, 1.2), "company")
            band(o, 0, 0, sx, sy, h - 1.0, 1.0, "limestone", grow=0.04)
            return o
        if sub == "typical":
            o.box((0, 0, 0), (sx, sy, h), "limestone")
            windows(o, 0, 0, sx, sy, h * 0.12, h * 0.90, 1, 7, m="blueglass", wf=0.55, hf=0.68)
            for t in (-0.5, 0.5):
                for side in SIDES:
                    face_box(o, 0, 0, sx, sy, side, t * 0.97, 0.08, 0, h, "whiteconcrete", out=FACE * 2)
            return o
        # roof (h=30)：退縮兩層＋公司色頂帶＋樓梯機房
        o.box((0, 0, 0), (sx, sy, 14.0), "limestone")
        windows(o, 0, 0, sx, sy, 2.0, 12.5, 1, 7, m="blueglass", wf=0.55, hf=0.65)
        band(o, 0, 0, sx, sy, 12.8, 1.4, "company", grow=0.04)
        o.box((0, 0, 14.0), (sx * 0.94, sy * 0.94, 1.5), "darkconcrete")
        parapet(o, 0, 0, sx, sy, 14.0, 3.0, "limestone", t=0.05)
        o.box((0, 0, 15.0), (sx * 0.64, sy * 0.56, 11.5), "limestone")
        windows(o, 0, 0, sx * 0.64, sy * 0.56, 17.0, 24.5, 1, 4, m="blueglass", wf=0.52, hf=0.62)
        parapet(o, 0, 0, sx * 0.64, sy * 0.56, 26.5, 2.2, "whiteconcrete", t=0.04)
        return o

    # 階段 4（parts 9,10,11）：8 層現代花崗岩與藍玻璃企業高樓＋轉角圓塔
    if level_group == 3:
        sx, sy = 1.62, 1.40
        if sub == "base":
            o.box((0, 0, 0), (sx, sy, h), "stone")
            ribbon(o, 0, 0, sx, sy, 2.0, h - 4.0, "blueglass")
            mullions(o, 0, 0, sx, sy, 0, h, 8, "stone")
            o.cyl((-sx * 0.44, -sy * 0.42, 0), 0.24, h, "limestone", v=16)
            o.box((0.12, -sy / 2 - 0.08, h * 0.68), (0.76, 0.20, 1.6), "company")
            band(o, 0, 0, sx, sy, h - 1.4, 1.4, "limestone", grow=0.04)
            return o
        if sub == "typical":
            o.box((0, 0, 0), (sx, sy, h), "stone")
            ribbon(o, 0, 0, sx, sy, 1.8, h - 3.2, "blueglass")
            mullions(o, 0, 0, sx, sy, 0, h, 8, "limestone")
            o.cyl((-sx * 0.44, -sy * 0.42, 0), 0.23, h, "blueglass", v=16)
            o.cyl((-sx * 0.44, -sy * 0.42, h - 1.4), 0.24, 1.4, "limestone", v=16)
            return o
        # roof (h=44)：頂層＋公司色屋頂冠帶＋圓角玻璃穹頂塔
        o.box((0, 0, 0), (sx, sy, 14.0), "stone")
        ribbon(o, 0, 0, sx, sy, 2.2, 9.5, "blueglass")
        mullions(o, 0, 0, sx, sy, 0, 14.0, 8, "limestone")
        band(o, 0, 0, sx, sy, 13.0, 1.8, "company", grow=0.04)
        o.box((0, 0, 14.0), (sx * 0.94, sy * 0.94, 1.6), "darkconcrete")
        parapet(o, 0, 0, sx, sy, 14.0, 3.2, "limestone", t=0.05)
        o.box((0.14, 0.10, 15.0), (0.78, 0.68, 12.0), "stone")
        # 轉角圓塔冠頂＋公司色小穹頂
        o.cyl((-sx * 0.44, -sy * 0.42, 0), 0.23, 24.0, "limestone", v=16)
        o.cyl((-sx * 0.44, -sy * 0.42, 16.0), 0.24, 6.0, "blueglass", v=16)
        o.lathe((-sx * 0.44, -sy * 0.42, 24.0), [(0.23, 0), (0.20, 6.0), (0.12, 11.5), (0.0, 14.5)], "company", seg=16)
        o.seg((-sx * 0.44, -sy * 0.42, 38.0), (-sx * 0.44, -sy * 0.42, 44.0), "silver", r=0.012)
        return o

    # 階段 5（parts 13,14,15）：指標圓柱玻璃與白石摩天總部（含屋頂空中花園＋公司色冠環＋尖塔）
    R = 0.72
    if sub == "base":
        # 寬敞白石裙樓（1.74×1.54）＋圓形主塔基座＋公司色門廳雨遮
        o.box((0, 0, 0), (1.74, 1.54, h * 0.65), "limestone")
        ribbon(o, 0, 0, 1.74, 1.54, 1.6, h * 0.48, "blueglass")
        mullions(o, 0, 0, 1.74, 1.54, 0, h * 0.65, 9, "whiteconcrete")
        o.box((0, -0.84, h * 0.56), (0.88, 0.24, 1.8), "company")
        o.cyl((0, 0, 0), R, h, "blueglass", v=24)
        o.cyl((0, 0, h - 1.6), R + 0.03, 1.6, "whiteconcrete", v=24)
        return o
    if sub == "typical":
        # 現代圓柱玻璃帷幕塔身＋白色層間環梁＋12 根垂直白石肋柱
        o.cyl((0, 0, 0), R, h, "blueglass", v=24)
        o.cyl((0, 0, 0), R + 0.025, 2.2, "whiteconcrete", v=24)
        for k in range(12):
            a = 2 * math.pi * k / 12
            o.box((R * math.cos(a), R * math.sin(a), 0), (0.045, 0.045, h), "whiteconcrete")
        return o
    # roof (h=89)：兩層退縮玻璃塔＋屋頂空中花園＋公司色雙冠環＋摩天尖塔
    o.cyl((0, 0, 0), R, 24.0, "blueglass", v=24)
    for z in (0, 10.0, 20.0):
        o.cyl((0, 0, z), R + 0.025, 2.2, "whiteconcrete", v=24)
    o.cyl((0, 0, 22.5), R + 0.04, 2.6, "company", v=24)          # 公司色主冠帶
    o.cyl((0, 0, 24.0), R * 0.94, 2.0, "grass", v=24)           # 空中花園綠屋頂
    # 中段退縮圓柱觀景層（z=25..50）
    o.cyl((0, 0, 25.0), R * 0.66, 25.0, "blueglass", v=24)
    for z in (25.0, 35.0, 46.5):
        o.cyl((0, 0, z), R * 0.68, 2.2, "whiteconcrete", v=24)
    o.cyl((0, 0, 48.5), R * 0.70, 2.4, "company", v=24)         # 第二道公司色冠環
    # 圓穹頂＋鋼骨通訊尖塔（z=50..88）
    o.lathe((0, 0, 50.5), [(R * 0.56, 0), (R * 0.50, 7.0), (R * 0.32, 13.0), (R * 0.12, 17.5), (0.0, 19.5)], "steel", seg=20)
    o.cyl((0, 0, 69.0), 0.045, 10.0, "white", v=10, rt=0.022)
    o.cyl((0, 0, 79.0), 0.022, 9.5, "company", v=8, rt=0.008)
    return o


SHOP_MATS = ["brick", "yellowbrick", "plaster", "cream", "darkbrick", "sandstone", "pink", "sage", "limestone", "ochre",
             "whitewash", "brick", "cream", "yellowbrick", "plaster"]
SHOP_ROOFS = [("gx", "slate"), ("hip", "terracotta"), ("flat", "limestone"), ("gx", "redshingle"), ("mansard", "slate")]


def shops(part, sub, h, P):
    """商店街（BLDSHOP1）：寫實 4 種店面（無鮮紅公司色）、15 種樓層外牆、5 種屋頂，組合出 18 種高街商宅。"""
    o = Ops()
    sx, sy = 0.84, 0.74
    if sub == "ground":
        o.ground(1, "pavement")
        return o
    if 1 <= part <= 4:
        o.box((0, 0, 0), (sx, sy, h), ["darkwood", "brick", "darkstone", "limestone"][part - 1])
        shopfront(o, 0, 0, sx, sy, h, {"shopmat": ["lightwood", "white", "limestone", "darkwood"][part - 1],
                                         "awning": ["terracotta", "sage", "copper", "redwood"][part - 1]})
        return o
    if 5 <= part <= 19:
        m = SHOP_MATS[part - 5]
        o.box((0, 0, 0), (sx, sy, h), m)
        windows(o, 0, 0, sx, sy, h * 0.18, h * 0.88, 1, 3 + part % 3, sills="white" if part % 2 else "limestone")
        band(o, 0, 0, sx, sy, h - 0.8, 0.8, "limestone" if part % 3 else "darkstone", grow=0.02)
        return o
    rk, rm = SHOP_ROOFS[part - 20]
    roof(o, rk, 0, 0, sx, sy, h, rm, over=0.02, chim=[(0.30, 0.20)] if rk != "flat" else None)
    return o


def courthouse(part, sub, h, P):
    """古典石灰岩法院（BLDCTY21，2×2，h=[1, 4, 24, 16, 35]）：寬台階、八柱列柱廊、亮白古典辦公層、三角楣＋銅綠屋頂與圓頂。"""
    o = Ops()
    sx, sy = 1.72, 1.44
    if sub == "ground":
        o.ground(2, "pavement")
        o.box((0, -0.82, 0), (1.42, 0.24, 0.6), "limestone")
        return o
    if h <= 6:                                                   # 寬石階台座（part 1, h=4）
        o.box((0, 0.04, 0), (sx + 0.12, sy + 0.12, h), "limestone")
        o.box((0, -sy / 2 - 0.10, 0), (1.16, 0.20, h * 0.65), "limestone")
        o.box((0, -sy / 2 - 0.16, 0), (1.08, 0.12, h * 0.35), "limestone")
        return o
    if sub == "base":                                            # 八柱古典柱廊（part 2, h=24）
        o.box((0, 0.12, 0), (sx, sy - 0.16, h), "limestone")
        # 左右突出古典轉角角樓
        for dx in (-1, 1):
            o.box((dx * (sx / 2 - 0.16), -sy / 2 + 0.14, 0), (0.34, 0.28, h), "limestone")
        windows(o, 0, 0.12, sx, sy - 0.16, 4.0, h - 3.5, 1, 7, m="glass", wf=0.40, hf=0.80, sills="white", sides=("+y", "-x", "+x"))
        mullions(o, 0, 0.12, sx, sy - 0.16, 2.0, h - 4.0, 7, "whiteconcrete")
        # 正面 8 根白色古典圓柱＋門廳大門
        for k in range(8):
            x = -0.58 + 1.16 * k / 7
            o.cyl((x, -sy / 2 + 0.06, 0), 0.038, h - 2.2, "whiteconcrete", v=12)
        o.box((0, -sy / 2 + 0.06, h - 2.4), (1.36, 0.18, 2.4), "whiteconcrete")
        for dx in (-0.24, 0.0, 0.24):
            face_box(o, 0, 0.12, sx, sy - 0.16, "-y", dx / sx, 0.14, 0, h * 0.62, "darkwood")
        band(o, 0, 0.12, sx, sy - 0.16, h - 1.6, 1.6, "whiteconcrete", grow=0.05)
        return o
    if sub in ("typical", "feature"):                            # 兩層古典辦公室（part 3, h=16）
        o.box((0, 0.04, 0), (sx, sy, h), "limestone")
        windows(o, 0, 0.04, sx, sy, 2.2, h - 2.2, 1, 8, m="glass", wf=0.42, hf=0.78, sills="white")
        mullions(o, 0, 0.04, sx, sy, 0, h - 1.2, 8, "whiteconcrete")
        band(o, 0, 0.04, sx, sy, h - 1.5, 1.5, "whiteconcrete", grow=0.05)
        return o
    # 屋頂（part 4, h=35）：女兒牆＋古典三角楣＋氧化銅綠孟莎斜屋頂＋中央圓柱鼓座銅綠圓頂
    o.box((0, 0.04, 0), (sx + 0.04, sy + 0.04, 2.5), "whiteconcrete")
    parapet(o, 0, 0.04, sx + 0.04, sy + 0.04, 2.5, 2.8, "limestone", t=0.05)
    o.gable((0, -sy / 2 + 0.22, 2.5), (1.18, 0.36, 9.5), "whiteconcrete", "y")
    o.hip((0, 0.08, 2.5), (sx * 0.94, sy * 0.92, 9.5), "copper", k=0.62)
    chimney(o, -sx * 0.38, 0.32, 7.5, 9.5, "limestone")
    chimney(o, sx * 0.38, 0.32, 7.5, 9.5, "limestone")
    # 中央古典列柱圓鼓＋銅綠大圓頂＋金塔尖
    o.cyl((0, 0.08, 9.5), 0.36, 8.5, "limestone", v=24)
    o.cyl((0, 0.08, 11.5), 0.37, 4.5, "glass", v=24)
    for k in range(12):
        a = 2 * math.pi * k / 12
        o.cyl((0.375 * math.cos(a), 0.08 + 0.375 * math.sin(a), 9.5), 0.022, 8.5, "whiteconcrete", v=8)
    o.cyl((0, 0.08, 17.5), 0.385, 1.5, "whiteconcrete", v=24)
    o.lathe((0, 0.08, 18.8), [(0.36, 0), (0.33, 4.5), (0.24, 9.0), (0.11, 12.2), (0.0, 13.8)], "copper", seg=24)
    o.cyl((0, 0.08, 32.0), 0.045, 3.0, "gold", v=8, rt=0.01)
    return o


# ---------------------------------------------------------------- 入口

def make_model(info: dict, recipe: dict) -> dict:
    heights, variations = info["heights"], info["variations"]
    large = info["large"]
    role, sub, family, level = analyse(heights, variations)
    kind = recipe["kind"]
    parts = []
    for p, h in enumerate(heights):
        P = dict(recipe)
        if family[p] == 1 and "b" in recipe:
            P.update(recipe["b"])
        if family[p] == 2 and "c" in recipe:
            P.update(recipe["c"])
        if kind == "house":
            o = house(p, sub[p], family[p], level[p], h, P, large)
        elif kind == "block":
            o = block(p, sub[p], family[p], level[p], h, P, large)
        elif kind == "office":
            o = office(p, sub[p], family[p], level[p], h, P, large)
        elif kind == "church":
            o = _church_ground(P) if p == 0 else church(len(heights), heights, P, large)
        elif kind == "castle":
            o = castle(heights, P)
        elif kind == "hall":
            o = concert_hall(sub[p], h, P)
        elif kind == "lighthouse":
            o = lighthouse(p, heights, P)
        elif kind == "transmitter":
            o = transmitter(heights, P)
        elif kind == "hq":
            o = headquarters(p, sub[p], family[p], h, heights, P)
        elif kind == "shops":
            o = shops(p, sub[p], h, P)
        elif kind == "courthouse":
            o = courthouse(p, sub[p], h, P)
        else:
            raise SystemExit(f"未知配方 {kind}")
        parts.append({"role": sub[p], "family": family[p], "height": h, "ops": list(o)})
    return {"kind": kind, "parts": parts}
