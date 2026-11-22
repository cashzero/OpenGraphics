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
    o.box((x, y, z), (0.07, 0.07, h), m)
    o.box((x, y, z + h), (0.085, 0.085, 1.0), "darkstone")


def roof(o: Ops, kind, cx, cy, sx, sy, h, m, over=0.04, chim=None, dormers=0, along=None):
    """屋頂（從 z = 0 起）。kind：gable / gx / gy / hip / pyramid / flat / mansard。"""
    if kind in ("gable", "gx", "gy"):
        a = along or ("x" if kind != "gy" else "y")
        if kind == "gable":
            a = "x" if sx >= sy else "y"
        o.gable((cx, cy, 0), (sx + 2 * over, sy + 2 * over, h * 0.9), m, a)
        if dormers:
            for k in range(dormers):
                t = (k + 0.5) / dormers - 0.5
                if a == "x":
                    dx, dy, w = cx + t * sx * 0.8, cy - sy * 0.28, sx / dormers * 0.35
                    o.box((dx, dy, h * 0.15), (w, 0.1, h * 0.35), "white")
                    o.gable((dx, dy, h * 0.5), (w * 1.2, 0.12, h * 0.18), m, "y")
                    face_box(o, dx, dy, w, 0.1, "-y", 0, w * 0.55, h * 0.2, h * 0.22, "glass")
                else:
                    dx, dy, w = cx - sx * 0.28, cy + t * sy * 0.8, sy / dormers * 0.35
                    o.box((dx, dy, h * 0.15), (0.1, w, h * 0.35), "white")
                    o.gable((dx, dy, h * 0.5), (0.12, w * 1.2, h * 0.18), m, "x")
                    face_box(o, dx, dy, 0.1, w, "-x", 0, w * 0.55, h * 0.2, h * 0.22, "glass")
    elif kind in ("hip", "pyramid"):
        o.hip((cx, cy, 0), (sx + 2 * over, sy + 2 * over, h * 0.85), m, k=0.0 if kind == "pyramid" else 0.45)
    elif kind == "flat":
        o.box((cx, cy, 0), (sx, sy, h * 0.25), m)
        parapet(o, cx, cy, sx, sy, 0, h * 0.45, m)
    elif kind == "mansard":
        o.box((cx, cy, 0), (sx + 0.02, sy + 0.02, 1.2), "white")
        o.hip((cx, cy, 1.0), (sx, sy, h * 0.7), m, k=0.85)
        o.box((cx, cy, h * 0.7), (sx * 0.75, sy * 0.6, h * 0.06), m)
        n = max(1, dormers or round(sx / 0.22))
        for k in range(n):
            t = (k + 0.5) / n - 0.5
            for side in ("-y", "+y"):
                yy = cy + (-1 if side == "-y" else 1) * sy * 0.42
                o.box((cx + t * sx * 0.85, yy, h * 0.2), (sx / n * 0.35, 0.06, h * 0.3), "white")
                face_box(o, cx + t * sx * 0.85, yy, sx / n * 0.35, 0.06, side, 0, sx / n * 0.2, h * 0.24, h * 0.18, "glass")
    if chim:
        for (x, y) in chim:
            chimney(o, cx + x * sx, cy + y * sy, h * 0.3, h * 0.75)


# ---------------------------------------------------------------- house

def house(part, sub, fam, level, h, P, large):
    o = Ops()
    sx, sy = P.get("fp", (0.6, 0.45))
    cx, cy = P.get("off", (0.0, 0.05))
    if sub == "ground":
        tiles = 2 if large else 1
        o.ground(tiles, P.get("ground", "grass"))
        if P.get("path", True):
            o.box((cx + P.get("path_x", 0) * sx, cy - sy / 2 - (tiles / 2 - sy / 2 - cy) / 2 - 0.01, 0),
                  (0.08 * tiles, max(0.02, tiles / 2 - sy / 2 + cy), 0.25), "pavement")
        if P.get("hedge", True):
            e = tiles / 2 - 0.035
            o.box((0, e, 0), (tiles * 0.96, 0.05, 2.2), "hedge")
            o.box((e, 0, 0), (0.05, tiles * 0.96, 2.2), "hedge")
            if P.get("fence"):
                o.box((-e, -0.25 * tiles, 0), (0.02, tiles * 0.45, 1.6), "white")
        return o
    if sub == "roof":
        rk = P.get("roof", "gable")
        if rk == "gable" and P.get("along"):
            rk = "g" + P["along"]
        chim = P.get("chimneys", [(0.3, 0.1)] if P.get("chimney", True) else None)
        roof(o, rk, cx, cy, sx, sy, h, P.get("roofmat", "company"), over=P.get("over", 0.04), chim=chim,
             dormers=P.get("dormers", 0))
        return o
    # 牆
    first = level <= 1
    mat = P.get("mat", "plaster") if (first or "upper" not in P) else P["upper"]
    o.box((cx, cy, 0), (sx, sy, h), mat)
    if P.get("plinth") and first:
        band(o, cx, cy, sx, sy, 0, min(2.0, h * 0.2), P["plinth"], grow=0.02)
    doors = P.get("doors", 1) if first else 0
    per = P.get("win", 2)
    door_at = [((k + 0.5) / doors - 0.5) for k in range(doors)]

    def skip(side, k, n, r):
        if side != "-y" or not doors:
            return False
        t = (k + 0.5) / n - 0.5
        return any(abs(t - d) < 0.5 / n for d in door_at)
    windows(o, cx, cy, sx, sy, h * 0.28, h * 0.92, 1, per + (doors if first else 0), sills=P.get("sills", "white"), skip=skip)
    for d in door_at:
        face_box(o, cx, cy, sx, sy, "-y", d, min(0.1, sx / (per + doors) * 0.55), 0, h * 0.68, P.get("door", "darkwood"))
        if P.get("porch") and first:
            o.box((cx + d * sx, cy - sy / 2 - 0.05, h * 0.68), (0.16, 0.1, 0.8), P.get("roofmat", "company"))
    if P.get("timber"):
        tm = "darkwood"
        for t in (-0.5, -0.17, 0.17, 0.5):
            for side in SIDES:
                face_box(o, cx, cy, sx, sy, side, t * 0.985, 0.014, 0, h, tm, out=FACE * 1.5)
        for z in (0, h - 0.6):
            band(o, cx, cy, sx, sy, z, 0.6, tm, grow=0.01)
    if P.get("balcony") and not first:
        o.box((cx, cy - sy / 2 - 0.06, h * 0.05), (sx * 0.9, 0.12, 0.7), "lightwood")
        o.box((cx, cy - sy / 2 - 0.115, h * 0.05), (sx * 0.9, 0.012, h * 0.32), "darkwood")
    if P.get("bay") and first:
        o.box((cx - sx * 0.25, cy - sy / 2 - 0.05, 0), (sx * 0.3, 0.1, h * 0.85), mat)
        face_box(o, cx - sx * 0.25, cy - sy / 2 - 0.05, sx * 0.3, 0.1, "-y", 0, sx * 0.22, h * 0.3, h * 0.45, "glass")
    if "trim" in P:
        band(o, cx, cy, sx, sy, h - 0.8, 0.8, P["trim"], grow=0.02)
    return o


# ---------------------------------------------------------------- block（城市街屋、公寓）

def shopfront(o, cx, cy, sx, sy, h, P):
    m = P.get("shopmat", "darkwood")
    for side in SIDES:
        L = sx if side in ("-y", "+y") else sy
        n = max(1, round(L / 0.3))
        for k in range(n):
            t = (k + 0.5) / n - 0.5
            face_box(o, cx, cy, sx, sy, side, t, L / n * 0.72, h * 0.1, h * 0.62, "glass")
            face_box(o, cx, cy, sx, sy, side, t, L / n * 0.78, h * 0.72, h * 0.14, m, out=FACE * 1.5)   # 招牌
    # 遮陽棚（公司色）：正面與左側
    o.box((cx, cy - sy / 2 - 0.05, h * 0.68), (sx * 0.96, 0.1, 0.9), P.get("awning", "company"))
    o.box((cx - sx / 2 - 0.05, cy, h * 0.68), (0.1, sy * 0.96, 0.9), P.get("awning", "company"))


def block(part, sub, fam, level, h, P, large):
    o = Ops()
    sx, sy = P.get("fp", (0.7, 0.6) if not large else (1.6, 1.4))
    cx, cy = P.get("off", (0.0, 0.0))
    mat = P.get("mat", "brick")
    if sub == "ground":
        o.ground(2 if large else 1, P.get("ground", "pavement"))
        return o
    if sub == "roof":
        rk = P.get("roof", "flat")
        rh = h
        if P.get("attic") and h > 14:                        # 屋頂部件較高：先加一層閣樓樓層
            fh = P.get("floor_h", 10)
            o.box((cx, cy, 0), (sx, sy, fh), mat)
            windows(o, cx, cy, sx, sy, fh * 0.25, fh * 0.9, 1, P.get("win", 4), sills=P.get("sills"))
            if "trim" in P:
                band(o, cx, cy, sx, sy, fh - 1.0, 1.0, P["trim"])
            sub_o = Ops()
            roof(sub_o, rk, cx, cy, sx, sy, rh - fh, P.get("roofmat", "slate"), over=0.02,
                 chim=P.get("chimneys"), dormers=P.get("dormers", 0))
            for op in sub_o:
                op = dict(op)
                if "c" in op:
                    op["c"] = [op["c"][0], op["c"][1], op["c"][2] + fh]
                o.append(op)
            return o
        roof(o, rk, cx, cy, sx, sy, rh, P.get("roofmat", "slate"), over=0.02, chim=P.get("chimneys"),
             dormers=P.get("dormers", 0))
        if rk == "flat" and P.get("tank"):
            o.box((cx + sx * 0.2, cy + sy * 0.15, 0), (0.12, 0.12, h * 0.9), "darkwood")
        return o
    o.box((cx, cy, 0), (sx, sy, h), mat if sub != "feature" else P.get("feature_mat", mat))
    if sub == "base" and P.get("shops"):
        shopfront(o, cx, cy, sx, sy, h, P)
    elif sub == "base":
        doors = P.get("doors", 1)

        def skip(side, k, n, r):
            return side == "-y" and abs((k + 0.5) / n - 0.5) < 0.5 / n
        windows(o, cx, cy, sx, sy, h * 0.25, h * 0.85, 1, P.get("win", 4), sills=P.get("sills"), skip=skip)
        face_box(o, cx, cy, sx, sy, "-y", 0, 0.1, 0, h * 0.75, P.get("door", "darkwood"))
        band(o, cx, cy, sx, sy, 0, h * 0.15, P.get("plinth", "darkstone"), grow=0.015)
    else:
        rows = max(1, round(h / P.get("floor_h", 10)))
        windows(o, cx, cy, sx, sy, h * 0.12, h * 0.95, rows, P.get("win", 4), sills=P.get("sills"),
                m=P.get("glass", "glass"))
        if P.get("balconies"):
            for r in range(rows):
                z = r * h / rows + 0.1
                o.box((cx, cy - sy / 2 - 0.05, z), (sx * 0.85, 0.1, 0.6), P.get("balcony_mat", "white"))
                o.box((cx, cy - sy / 2 - 0.095, z), (sx * 0.85, 0.012, h / rows * 0.35), P.get("balcony_mat", "white"))
    if "trim" in P:
        band(o, cx, cy, sx, sy, h - 0.9, 0.9, P["trim"])
    return o


# ---------------------------------------------------------------- office

def office(part, sub, fam, level, h, P, large):
    o = Ops()
    sx, sy = P.get("fp", (1.5, 1.4) if large else (0.7, 0.62))
    cx, cy = P.get("off", (0.0, 0.0))
    mat = P.get("mat", "concrete")
    style = P.get("style", "grid")
    fh = P.get("floor_h", 12)
    if sub == "ground":
        o.ground(2 if large else 1, P.get("ground", "pavement"))
        if P.get("plaza") and large:
            o.box((cx - 0.75, cy - 0.75, 0), (0.18, 0.18, 2.0), "hedge")
            o.box((cx + 0.75, cy - 0.75, 0), (0.18, 0.18, 2.0), "hedge")
        return o

    def storeys(z0, height, sx_, sy_, m=mat):
        o.box((cx, cy, z0), (sx_, sy_, height), m)
        n = max(1, round(height / fh))
        if style == "ribbon":
            for r in range(n):
                ribbon(o, cx, cy, sx_, sy_, z0 + r * height / n + height / n * 0.3, height / n * 0.5, P.get("glass", "glass"))
        elif style == "glass":
            ribbon(o, cx, cy, sx_, sy_, z0 + 0.3, height - 0.6, P.get("glass", "blueglass"))
            mullions(o, cx, cy, sx_, sy_, z0, height, max(3, round(sx_ / 0.12)), P.get("frame", "steel"))
            for r in range(1, n):
                band(o, cx, cy, sx_, sy_, z0 + r * height / n - 0.25, 0.5, P.get("frame", "steel"), grow=0.028)
        else:
            windows(o, cx, cy, sx_, sy_, z0 + height * 0.06, z0 + height * 0.98, n, P.get("win", round(sx_ / 0.12)),
                    m=P.get("glass", "glass"), wf=P.get("wf", 0.55), hf=0.6)
        if P.get("piers"):
            for t in (-0.5, 0.5):
                for side in SIDES:
                    face_box(o, cx, cy, sx_, sy_, side, t * 0.97, 0.05, z0, height, P["piers"], out=FACE * 2)

    if sub == "base":
        o.box((cx, cy, 0), (sx, sy, h), P.get("base_mat", mat))
        if P.get("shops"):
            shopfront(o, cx, cy, sx, sy, h, P)
        else:
            ribbon(o, cx, cy, sx * 0.999, sy * 0.999, h * 0.08, h * 0.7, P.get("lobby_glass", "glass"))
            n = max(2, round(sx / 0.25))
            for side in SIDES:
                L = sx if side in ("-y", "+y") else sy
                k_n = n if side in ("-y", "+y") else max(2, round(n * sy / sx))
                for k in range(k_n + 1):
                    face_box(o, cx, cy, sx, sy, side, (k / k_n - 0.5) * 0.97, 0.03, 0, h * 0.8, P.get("piers", mat), out=FACE * 2)
            o.box((cx, cy - sy / 2 - 0.06, h * 0.75), (sx * 0.4, 0.12, 0.8), P.get("canopy", "company"))
        band(o, cx, cy, sx, sy, h - 1.0, 1.0, P.get("trim", P.get("base_mat", mat)), grow=0.03)
        return o
    if sub in ("typical", "feature"):
        if sub == "feature" and P.get("feature") == "band":
            o.box((cx, cy, 0), (sx, sy, h), P.get("feature_mat", "darkconcrete"))
            ribbon(o, cx, cy, sx, sy, h * 0.25, h * 0.5, "darksteel")
        elif sub == "feature" and P.get("feature") == "setback":
            k = P.get("setback", 0.85)
            storeys(0, h, sx * k, sy * k)
            parapet(o, cx, cy, sx, sy, 0, 1.6, P.get("trim", mat))
        else:
            storeys(0, h, sx, sy, P.get("feature_mat", mat) if sub == "feature" else mat)
        if "trim" in P and P.get("cornices", True):
            band(o, cx, cy, sx, sy, h - 0.6, 0.6, P["trim"], grow=0.02)
        return o
    # roof / crown
    crown = P.get("crown", "flat")
    z = 0.0
    if crown == "flat" or h < 18:
        o.box((cx, cy, 0), (sx, sy, min(h, 3.0)), mat)
        parapet(o, cx, cy, sx, sy, 0, min(h, 4.0), P.get("trim", mat))
        if h >= 8:
            o.box((cx + sx * 0.15, cy + sy * 0.1, 0), (sx * 0.35, sy * 0.3, h * 0.75), P.get("plant", "darkconcrete"))
            for k in range(P.get("units", 2)):
                o.box((cx - sx * 0.25 + k * 0.12, cy - sy * 0.2, 0), (0.08, 0.06, min(h, 6.0)), "steel")
        return o
    # 高塔頂：先蓋幾層樓（逐級退縮），再加頂飾
    cap = {"pyramid": 0.38, "spire": 0.45, "setback": 0.25, "antenna": 0.35, "deco": 0.5, "dome": 0.4,
           "clock": 0.5}.get(crown, 0.3) * h
    body = h - cap
    k = 1.0
    tiers = max(1, round(body / (fh * 2.2)))
    for t in range(tiers):
        th = body / tiers
        storeys(z, th, sx * k, sy * k)
        band(o, cx, cy, sx * k, sy * k, z + th - 0.8, 0.8, P.get("trim", mat), grow=0.02)
        z += th
        if crown in ("setback", "deco", "spire", "antenna"):
            k *= P.get("step", 0.82)
    if crown == "pyramid":
        o.hip((cx, cy, z), (sx * k + 0.04, sy * k + 0.04, cap), P.get("roofmat", "copper"), k=0.0)
    elif crown == "dome":
        r = min(sx, sy) * k * 0.38
        o.cyl((cx, cy, z), r * 1.05, cap * 0.3, mat, v=24)
        o.lathe((cx, cy, z + cap * 0.3), [(r, 0), (r * 0.92, cap * 0.25), (r * 0.7, cap * 0.45), (r * 0.35, cap * 0.62),
                                          (0.0, cap * 0.68)], P.get("roofmat", "copper"))
        o.cyl((cx, cy, z + cap * 0.95), 0.012, cap * 0.05, "gold", v=6)
    elif crown == "clock":
        w = min(sx, sy) * k * 0.4
        o.box((cx, cy, z), (sx * k, sy * k, 1.5), P.get("trim", mat))
        o.box((cx, cy, z), (w, w, cap * 0.55), mat)
        for side in SIDES:
            face_box(o, cx, cy, w, w, side, 0, w * 0.6, cap * 0.28, w * 0.6 * 22, "white")
        o.hip((cx, cy, z + cap * 0.55), (w * 1.1, w * 1.1, cap * 0.45), P.get("roofmat", "copper"), k=0.0)
    else:                                                     # setback / antenna / spire / deco
        o.box((cx, cy, z), (sx * k, sy * k, 2.0), P.get("trim", mat))
        if crown == "setback":
            o.box((cx, cy, z), (sx * k * 0.5, sy * k * 0.5, cap * 0.8), P.get("plant", "darkconcrete"))
        elif crown == "antenna":
            o.box((cx, cy, z), (sx * k * 0.35, sy * k * 0.35, cap * 0.3), "darkconcrete")
            o.seg((cx, cy, z + cap * 0.3), (cx, cy, z + cap), "red", r=0.012)
            o.seg((cx + 0.04, cy, z + cap * 0.3), (cx + 0.04, cy, z + cap * 0.75), "steel", r=0.008)
        elif crown == "spire":
            o.box((cx, cy, z), (sx * k * 0.45, sy * k * 0.45, cap * 0.25), mat)
            o.cyl((cx, cy, z + cap * 0.25), min(sx, sy) * k * 0.2, cap * 0.75, P.get("roofmat", "steel"), v=8, rt=0.0)
        elif crown == "deco":
            for i, f in enumerate((0.7, 0.5, 0.32)):
                o.box((cx, cy, z + i * cap * 0.2), (sx * k * f, sy * k * f, cap * 0.2), mat)
                band(o, cx, cy, sx * k * f, sy * k * f, z + (i + 1) * cap * 0.2 - 0.6, 0.6, P.get("trim", "gold"))
            o.cyl((cx, cy, z + cap * 0.6), 0.03, cap * 0.4, "gold", v=8, rt=0.0)
    return o


# ---------------------------------------------------------------- 特殊建築

def church(n_parts, heights, P, large):
    """教堂：part 0 地面、part 1 整座教堂。"""
    H = heights[1]
    o = Ops()
    style = P["style"]
    wall = P.get("mat", "stone")
    roofm = P.get("roofmat", "slate")
    if style == "chapel":           # 小禮拜堂：中殿 + 鐘架
        nx, ny, nh = 1.0, 0.5, H * 0.38
        o.box((0.1, 0, 0), (nx, ny, nh), wall)
        o.gable((0.1, 0, nh), (nx + 0.06, ny + 0.08, H * 0.3), roofm, "x")
        windows(o, 0.1, 0, nx, ny, nh * 0.3, nh * 0.9, 1, 4, wf=0.25, hf=0.85, sides=("-y", "+y"))
        o.box((-0.5, 0, 0), (0.12, 0.3, H * 0.62), wall)                       # 山牆上的鐘架
        o.box((-0.5, 0, H * 0.62), (0.13, 0.12, H * 0.12), wall)
        o.gable((-0.5, 0, H * 0.74), (0.16, 0.16, H * 0.22), roofm, "y")
        o.box((0.62, 0, 0), (0.3, 0.36, nh * 0.85), wall)                       # 半圓後殿（簡化成方形）
        o.hip((0.62, 0, nh * 0.85), (0.34, 0.4, H * 0.18), roofm, k=0.2)
        face_box(o, -0.4, 0, 0.0, 0.3, "-x", 0, 0.08, 0, nh * 0.6, "darkwood")
        return o
    # 尖塔教堂：中殿 + 側廊 + 西塔 + 尖塔
    nx, ny = (1.15, 0.5) if style == "spire" else (1.3, 0.62)
    nh = 18 if style == "spire" else 22
    o.box((0.25, 0, 0), (nx, ny, nh), wall)
    o.gable((0.25, 0, nh), (nx + 0.06, ny + 0.08, 14 if style == "spire" else 18), roofm, "x")
    windows(o, 0.25, 0, nx, ny, nh * 0.25, nh * 0.9, 1, 5, wf=0.25, hf=0.85, sides=("-y", "+y"))
    if style == "minster":           # 側廊與十字翼
        for s in (-1, 1):
            o.box((0.25, s * (ny / 2 + 0.12), 0), (nx * 0.9, 0.24, nh * 0.55), wall)
            o.hip((0.25, s * (ny / 2 + 0.12), nh * 0.55), (nx * 0.9, 0.26, 6), roofm, k=0.8)
        o.box((0.55, 0, 0), (0.36, ny + 0.6, nh * 0.95), wall)
        o.gable((0.55, 0, nh * 0.95), (0.42, ny + 0.66, 16), roofm, "y")
        windows(o, 0.55, 0, 0.36, ny + 0.6, nh * 0.3, nh * 0.85, 1, 1, wf=0.4, hf=0.8, sides=("-x", "+x"))
    tx = 0.25 - nx / 2 - 0.15
    tw = 0.34 if style == "spire" else 0.42
    th = H * (0.45 if style == "spire" else 0.55)
    o.box((tx, 0, 0), (tw, tw, th), wall)
    band(o, tx, 0, tw, tw, th * 0.5, 1.0, "darkstone", grow=0.02)
    for side in SIDES:
        face_box(o, tx, 0, tw, tw, side, 0, tw * 0.25, th * 0.72, th * 0.18, "black")   # 鐘樓窗
    face_box(o, tx, 0, tw, tw, "-x", 0, tw * 0.3, 0, th * 0.22, "darkwood")
    o.box((tx, 0, th), (tw + 0.03, tw + 0.03, 1.5), "darkstone")
    if style == "spire":
        o.cyl((tx, 0, th + 1.5), tw * 0.52, H - th - 1.5, roofm, v=8, rt=0.0)
    else:
        for dx in (-1, 1):                                                       # 四角小尖塔 + 中央尖塔
            for dy in (-1, 1):
                o.cyl((tx + dx * tw * 0.42, dy * tw * 0.42, th + 1.5), 0.035, 9, "darkstone", v=6, rt=0.0)
        o.cyl((tx, 0, th + 1.5), tw * 0.42, H - th - 1.5, roofm, v=8, rt=0.0)
    return o


def castle(heights, P):
    """城堡遺跡（單一部件，含地面）：殘破的城牆、兩座塔、碎石。"""
    H = heights[0]
    o = Ops()
    o.ground(2, "grass")
    st, dk = "stone", "darkstone"
    o.box((0, 0, 0), (1.6, 1.4, 0.5), "dirt")
    # 城牆（高低不一 = 殘破）
    segs = [((-0.75, -0.2), (0.1, 0.9), 14), ((-0.4, 0.62), (0.8, 0.1), 18), ((0.35, 0.62), (0.5, 0.1), 9),
            ((0.72, 0.1), (0.1, 0.9), 12), ((0.1, -0.62), (0.6, 0.1), 7)]
    for (x, y), (sx, sy), hh in segs:
        o.box((x, y, 0), (sx, sy, hh), st)
        n = int(max(sx, sy) / 0.12)
        for k in range(n):                                   # 垛口
            if k % 2 == 0:
                t = (k + 0.5) / n - 0.5
                o.box((x + t * sx if sx > sy else x, y + t * sy if sy > sx else y, hh), (min(sx, 0.08) if sx > sy else sx, min(sy, 0.08) if sy > sx else sy, 2.5), st)
    # 主塔（保存較好）與半毀的角塔
    o.box((-0.55, 0.45, 0), (0.42, 0.42, H * 0.92), st)
    for side in SIDES:
        face_box(o, -0.55, 0.45, 0.42, 0.42, side, 0, 0.06, H * 0.55, 4, "black")
        face_box(o, -0.55, 0.45, 0.42, 0.42, side, -0.25, 0.05, H * 0.3, 3, "black")
    for k in range(4):
        dx, dy = [(-1, -1), (-1, 1), (1, -1), (1, 1)][k]
        o.box((-0.55 + dx * 0.17, 0.45 + dy * 0.17, H * 0.92), (0.08, 0.08, 3), st)
    o.cyl((0.65, -0.5, 0), 0.2, H * 0.55, st, v=12)
    o.box((0.62, -0.42, H * 0.55), (0.16, 0.2, 4), st)
    # 碎石堆
    for (x, y, s) in ((0.25, -0.3, 0.18), (-0.2, -0.45, 0.12), (0.45, 0.35, 0.15), (0.0, 0.1, 0.1)):
        o.hip((x, y, 0.5), (s, s * 0.8, 3), dk, k=0.3)
    return o


def concert_hall(sub, h, P):
    o = Ops()
    if sub == "ground":
        o.ground(2, "pavement")
        o.box((0, -0.82, 0), (1.4, 0.2, 0.6), "whiteconcrete")
        return o
    if sub == "base":
        o.box((0, 0.05, 0), (1.5, 1.3, h), "whiteconcrete")
        ribbon(o, 0, 0.05, 1.5, 1.3, h * 0.1, h * 0.8, "blueglass")
        mullions(o, 0, 0.05, 1.5, 1.3, 0, h, 10, "white")
        o.box((0, -0.65, h * 0.85), (1.2, 0.2, 1.0), "company")
        return o
    # 波浪形大屋頂（兩片弧形殼）+ 舞台塔
    o.box((0.3, 0.2, 0), (0.6, 0.6, h * 0.95), "whiteconcrete")
    for k, (x, w) in enumerate(((-0.3, 0.8), (0.25, 0.9))):
        prof = [(w * 0.5, 0), (w * 0.47, h * 0.25), (w * 0.38, h * 0.5), (w * 0.22, h * 0.68), (0.0, h * 0.72)]
        o.lathe((x, 0.05, 0), prof, "copper" if k == 0 else "company", seg=28)
    return o


def lighthouse(part, heights, P):
    o = Ops()
    if part == 0:
        o.ground(1, "grass")
        o.box((0, 0, 0), (0.7, 0.7, 0.6), "stone")
        o.box((0.22, -0.05, 0), (0.24, 0.32, 9), "whitewash")                  # 守燈人小屋
        o.gable((0.22, -0.05, 9), (0.28, 0.36, 5), "company", "y")
        return o
    if part == 1:                                                                # 塔身：紅白相間的圓錐塔
        H = heights[1]
        for k in range(4):
            z0, z1 = H * k / 4, H * (k + 1) / 4
            r0 = 0.17 - 0.06 * z0 / H
            r1 = 0.17 - 0.06 * z1 / H
            o.cyl((0, 0, z0), r0, z1 - z0, "white" if k % 2 == 0 else "red", v=20, rt=r1)
        o.cyl((0, 0, H - 1.2), 0.15, 1.2, "darksteel", v=20)                    # 走廊
        return o
    # 燈室：玻璃 + 圓頂 + 旋轉光束（32 格）
    frame = part - 2
    o.cyl((0, 0, 0), 0.085, 9, "lit", v=16)
    for k in range(8):
        a = 2 * math.pi * k / 8
        o.seg((0.085 * math.cos(a), 0.085 * math.sin(a), 0), (0.085 * math.cos(a), 0.085 * math.sin(a), 9), "darksteel", r=0.006)
    o.lathe((0, 0, 9), [(0.1, 0), (0.08, 3), (0.04, 5), (0.0, 6)], "darksteel", seg=16)
    a = 2 * math.pi * frame / 32
    L = 0.75
    for s in (-1, 1):                                                            # 前後兩道光束
        x, y = s * L * math.cos(a), s * L * math.sin(a)
        o.seg((0, 0, 4.5), (x, y, 3.0), "lit", r=0.02)
    return o


def transmitter(heights, P):
    """電波塔：四角桁架鐵塔（紅白），頂端天線。"""
    H = heights[0]
    o = Ops()
    o.ground(1, "gravel")
    o.box((0.28, 0.28, 0), (0.18, 0.14, 5), "darkconcrete")
    levels = 10
    base, topw = 0.3, 0.05
    pts = []
    for i in range(levels + 1):
        z = H * 0.88 * i / levels
        w = base + (topw - base) * i / levels
        pts.append((w, z))
    for i in range(levels):
        (w0, z0), (w1, z1) = pts[i], pts[i + 1]
        col = "red" if i % 2 == 0 else "white"
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            o.seg((dx * w0, dy * w0, z0), (dx * w1, dy * w1, z1), col, r=0.012)
        for (ax, ay), (bx, by) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)), ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            o.seg((ax * w0, ay * w0, z0), (bx * w1, by * w1, z1), "steel", r=0.006)
    o.seg((0, 0, H * 0.88), (0, 0, H), "red", r=0.012)
    return o


def headquarters(part, sub, level_group, h, heights, P):
    """公司總部：5 個等級，玻璃與裝飾帶用公司色。"""
    o = Ops()
    if sub == "ground":
        o.ground(2, "pavement")
        o.box((-0.7, -0.7, 0), (0.2, 0.2, 2), "hedge")
        o.box((0.7, -0.7, 0), (0.2, 0.2, 2), "hedge")
        o.seg((-0.55, -0.85, 0), (-0.55, -0.85, 14), "white", r=0.008)        # 旗桿
        o.box((-0.5, -0.85, 11), (0.1, 0.01, 3), "company")
        return o
    P2 = dict(P)
    sizes = {0: (0.9, 0.7), 1: (1.2, 0.9), 2: (1.4, 1.1), 3: (1.5, 1.3), 4: (1.6, 1.4)}
    sx, sy = sizes[level_group]
    P2.update({"fp": (sx, sy), "mat": "whiteconcrete" if level_group < 3 else "darkconcrete", "style": "ribbon" if level_group < 2 else "glass",
               "glass": "company", "frame": "white", "canopy": "company2", "trim": "company2", "floor_h": 10,
               "crown": {0: "flat", 1: "flat", 2: "setback", 3: "antenna", 4: "spire"}[level_group], "roofmat": "steel"})
    if sub == "roof" and h < 35 and level_group < 2:         # 等級 1、2：整棟一個部件
        o.box((0, 0, 0), (sx, sy, h * 0.82), P2["mat"])
        for r in range(2):
            ribbon(o, 0, 0, sx, sy, h * (0.1 + 0.4 * r), h * 0.25, "company")
        o.box((0, -sy / 2 - 0.06, h * 0.3), (sx * 0.4, 0.12, 0.8), "company2")
        parapet(o, 0, 0, sx, sy, h * 0.82, 2.0, "company2")
        o.box((0.2, 0.1, h * 0.82), (sx * 0.3, sy * 0.3, h * 0.15), "darkconcrete")
        return o
    return office(part, sub, 0, 0, h, P2, True)


SHOP_MATS = ["brick", "yellowbrick", "plaster", "cream", "darkbrick", "sandstone", "pink", "sage", "stone", "ochre",
             "whitewash", "brick", "cream", "yellowbrick", "plaster"]
SHOP_ROOFS = [("gx", "slate"), ("hip", "terracotta"), ("flat", "stone"), ("gx", "company"), ("mansard", "slate")]


def shops(part, sub, h, P):
    """商店街（BLDSHOP1）：部件 1–4 為四種店面、5–19 為十五種樓層、20–24 為五種屋頂，由變化組合拼出不同外觀。"""
    o = Ops()
    sx, sy = 0.78, 0.66
    if sub == "ground":
        o.ground(1, "pavement")
        return o
    if 1 <= part <= 4:
        o.box((0, 0, 0), (sx, sy, h), ["darkwood", "company", "darkstone", "white"][part - 1])
        shopfront(o, 0, 0, sx, sy, h, {"shopmat": ["lightwood", "white", "company", "darkwood"][part - 1],
                                         "awning": ["company", "company2", "company", "company2"][part - 1]})
        return o
    if 5 <= part <= 19:
        m = SHOP_MATS[part - 5]
        o.box((0, 0, 0), (sx, sy, h), m)
        windows(o, 0, 0, sx, sy, h * 0.2, h * 0.9, 1, 3 + part % 3, sills="white" if part % 2 else None)
        band(o, 0, 0, sx, sy, h - 0.7, 0.7, "white" if part % 4 else "darkstone")
        return o
    rk, rm = SHOP_ROOFS[part - 20]
    roof(o, rk, 0, 0, sx, sy, h, rm, over=0.02, chim=[(0.3, 0.2)] if rk != "flat" else None)
    return o


def courthouse(part, sub, h, P):
    o = Ops()
    sx, sy = 1.5, 1.1
    if sub == "ground":
        o.ground(2, "pavement")
        return o
    if h <= 6:                                                   # 台階
        o.box((0, 0.05, 0), (sx + 0.1, sy + 0.1, h), "whiteconcrete")
        o.box((0, -sy / 2 - 0.12, 0), (0.7, 0.2, h * 0.6), "whiteconcrete")
        return o
    if sub == "base":                                            # 柱廊
        o.box((0, 0.12, 0), (sx, sy - 0.15, h), "sandstone")
        windows(o, 0, 0.12, sx, sy - 0.15, h * 0.2, h * 0.8, 1, 7, wf=0.35, sides=("+y", "-x", "+x"))
        for k in range(8):
            x = -0.6 + 1.2 * k / 7
            o.cyl((x, -sy / 2 + 0.06, 0), 0.035, h, "whiteconcrete", v=10)
        o.box((0, -sy / 2 + 0.06, h - 1.6), (1.35, 0.14, 1.6), "whiteconcrete")
        face_box(o, 0, 0.12, sx, sy - 0.15, "-y", 0, 0.14, 0, h * 0.6, "darkwood")
        return o
    if sub in ("typical", "feature"):
        o.box((0, 0.05, 0), (sx, sy, h), "sandstone")
        windows(o, 0, 0.05, sx, sy, h * 0.2, h * 0.85, 1, 8, wf=0.35, sills="white")
        band(o, 0, 0.05, sx, sy, h - 0.8, 0.8, "whiteconcrete")
        return o
    # 屋頂：三角楣 + 中央圓頂
    o.box((0, 0.05, 0), (sx, sy, 2), "whiteconcrete")
    o.gable((0, -sy / 2 + 0.2, 2), (0.9, 0.42, 7), "whiteconcrete", "y")
    o.hip((0, 0.05, 2), (sx * 0.98, sy * 0.98, 6), "lead", k=0.6)
    o.cyl((0, 0.15, 6), 0.26, 6, "sandstone", v=24)
    o.lathe((0, 0.15, 12), [(0.27, 0), (0.25, 6), (0.18, 11), (0.08, 14), (0.0, 15)], "copper")
    o.cyl((0, 0.15, 27), 0.03, h - 27, "gold", v=6, rt=0.0)
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
            o = Ops()
            if p == 0:
                o.ground(2, "grass")
                o.box((0.25, -0.75, 0), (0.12, 0.5, 0.3), "gravel")
            else:
                o = church(len(heights), heights, P, large)
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
