"""車輛模型（M3）：依車種配方與狀態（動畫格、貨物圖、煞車燈）產生幾何指令（tools/blender/models/ops.py，unit = m）。
慣例：車頭朝 +Y、輪底（或水線、軌面）在 z = 0、轉軸在原點；長度 L 由模板的 halfLength 換算（L = 2 × half × 0.078）。

model(recipe, L, state) → [指令…]；state = {"anim": a, "anims": A, "cargo": 貨物名稱或 None, "brake": bool, "body": 第幾個車身}
"""
from __future__ import annotations

import math

from building_recipes import Ops

SCALE = 0.078   # halfLength 單位 → Blender 單位（由上游 OG_4F.blend 與 vanilla sprite 寬度量得）


# ---------------------------------------------------------------- 小構件

def box(o, c, s, m):
    o.box(c, s, m)


def wheel(o, x, y, r, w=0.25, m="black", hub="silver", z=None):
    o.append({"op": "cylx", "c": [x, y, r if z is None else z], "r": r, "w": w, "m": m, "v": 14})
    o.append({"op": "cylx", "c": [x + (w / 2 + 0.01) * (1 if x > 0 else -1), y, r if z is None else z], "r": r * 0.5, "w": 0.02,
              "m": hub, "v": 10})


def axle_pair(o, y, r, half_w, w=0.28, hub="silver"):
    for s in (-1, 1):
        wheel(o, s * (half_w - w / 2), y, r, w, hub=hub)


def side_profile(o, pts, half_w, m):
    """側面輪廓（YZ 平面）沿 X 擠出成整個車寬。"""
    o.append({"op": "finx", "p": [list(p) for p in pts], "x": [-half_w, half_w], "m": m})


def windows_side(o, y0, y1, z0, z1, half_w, n, m="glass", gap=0.25):
    """兩側的一排窗（薄片）。"""
    L = (y1 - y0) / n
    for k in range(n):
        yc = y0 + (k + 0.5) * L
        for s in (-1, 1):
            o.box((s * (half_w + 0.01), yc, z0), (0.02, L * (1 - gap), z1 - z0), m)


def lights(o, y, z, half_w, front, brake=False, s=0.14):
    m = "glow" if front else ("red" if brake else "darkwood")
    for sgn in (-1, 1):
        o.box((sgn * (half_w - s), y + (0.01 if front else -0.01), z), (s * 1.2, 0.04, s), m)


def tube(o, sections, m, seg=12):
    o.append({"op": "tube", "s": [list(s) for s in sections], "m": m, "seg": seg})


def loft(o, sections, m):
    o.append({"op": "loft", "s": [list(s) for s in sections], "m": m})


def prism(o, pts, z0, z1, m):
    o.append({"op": "prism", "p": [list(p) for p in pts], "z": [z0, z1], "m": m})


def fin(o, pts, x0, x1, m):
    o.append({"op": "finx", "p": [list(p) for p in pts], "x": [x0, x1], "m": m})


def cyly(o, c, r, length, m, rt=None, v=14):
    op = {"op": "cyly", "c": list(c), "r": r, "l": length, "m": m, "v": v}
    if rt is not None:
        op["rt"] = rt
    o.append(op)


# ---------------------------------------------------------------- 卡車

def truck(R, L, st):
    o = Ops()
    era = R.get("era", 1950)
    W = min(2.5, max(1.7, L * 0.3))
    hw = W / 2
    r = 0.36 + 0.025 * L
    if era < 1915:
        r *= 1.15
    front, rear = L / 2, -L / 2
    cab_over = era >= 1965
    trailer = R.get("trailer", False)
    chassis_z = r * 0.85
    # 前後軸
    fa = front - (0.16 * L if cab_over else 0.13 * L)
    ra = [rear + 0.2 * L] if L < 8 else [rear + 0.16 * L, rear + 0.27 * L]
    if trailer:
        fa = None
        ra = [rear + 0.25 * L, rear + 0.38 * L] if L > 5 else [rear + 0.3 * L]
    for y in ([fa] if fa is not None else []) + ra:
        axle_pair(o, y, r, hw, w=0.26 if era > 1915 else 0.14, hub="silver" if era > 1930 else "red")
    o.box((0, (rear + 0.05 + front - 0.1) / 2, chassis_z), (W * 0.7, front - rear - 0.15, r * 0.35), "darksteel")
    cab_c = R.get("cab", "company")
    if trailer:                                                   # 拖車：前方牽引桿
        o.seg((0, front - 0.6, chassis_z + 0.1), (0, front, chassis_z), "darksteel", r=0.06)
        body_front = front - 0.7
    elif cab_over:                                                # 平頭（駕駛室在引擎上方）
        cl = 0.2 * L
        cz0, cz1 = chassis_z + r * 0.3, chassis_z + 2.3
        side_profile(o, [(front - cl, cz0), (front, cz0), (front, cz1 - 0.5), (front - 0.15, cz1), (front - cl, cz1)], hw, cab_c)
        o.box((0, front + 0.01, cz0 + 0.9), (W * 0.86, 0.04, 0.85), "glass")                  # 擋風玻璃
        windows_side(o, front - cl + 0.15, front - 0.15, cz0 + 0.95, cz1 - 0.15, hw, 1)
        o.box((0, front + 0.02, cz0 + 0.1), (W * 0.6, 0.04, 0.45), "darksteel")              # 水箱罩
        lights(o, front + 0.02, cz0 + 0.15, hw, True)
        body_front = front - cl - 0.15
    else:
        bl = (0.16 if era >= 1930 else 0.13) * L                  # 引擎蓋
        cl = 0.17 * L
        ez0 = chassis_z + r * 0.3
        eh = 1.1 if era >= 1930 else 0.85
        if era >= 1940:                                           # 圓弧引擎蓋
            loft(o, [(front - bl, W * 0.32, ez0, ez0 + eh), (front - 0.1, W * 0.3, ez0, ez0 + eh * 0.92), (front, W * 0.26, ez0, ez0 + eh * 0.8)], cab_c)
            for s in (-1, 1):                                     # 前葉子板
                o.box((s * (hw - 0.15), fa, chassis_z + r * 0.35), (0.32, r * 2.4, r * 0.45), cab_c)
        else:
            o.box((0, front - bl / 2, ez0), (W * 0.55, bl, eh), "darksteel" if era < 1915 else cab_c)
        o.box((0, front - 0.02, ez0 + 0.05), (W * (0.45 if era < 1940 else 0.5), 0.05, eh * 0.8), "silver" if era >= 1930 else "darkwood")  # 水箱護罩
        lights(o, front, ez0 + eh * 0.5, W * 0.35, True, s=0.12)
        cy1 = front - bl
        cy0 = cy1 - cl
        cz0, cz1 = chassis_z + r * 0.3, chassis_z + (2.1 if era >= 1930 else 1.9)
        if era < 1915:                                            # 早期：開放式駕駛座 + 頂篷
            o.box((0, (cy0 + cy1) / 2, cz0), (W * 0.9, cl, 0.6), "wood")
            o.box((0, cy0 + 0.1, cz0), (W * 0.9, 0.12, 1.0), "wood")
            for yy in (cy0 + 0.05, cy1 - 0.05):
                for s in (-1, 1):
                    o.box((s * W * 0.42, yy, cz0), (0.06, 0.06, cz1 - cz0), "darkwood")
            o.box((0, (cy0 + cy1) / 2, cz1), (W * 0.95, cl + 0.2, 0.1), cab_c)
        else:
            side_profile(o, [(cy0, cz0), (cy1, cz0), (cy1, cz1 - 0.35), (cy1 - 0.25, cz1), (cy0, cz1)], hw * 0.95, cab_c)
            o.box((0, cy1 - 0.08, cz0 + 0.95), (W * 0.8, 0.04, cz1 - cz0 - 1.3), "glass")
            windows_side(o, cy0 + 0.15, cy1 - 0.3, cz0 + 0.9, cz1 - 0.2, hw * 0.95, 1)
            o.box((0, (cy0 + cy1) / 2, cz1), (W * 0.97, cl + 0.05, 0.08), "darksteel")
        body_front = cy0 - 0.12
    body_rear = rear
    blen = body_front - body_rear
    bc = (body_front + body_rear) / 2
    bz = chassis_z + r * 0.35
    kind = R["body"]
    b2 = R.get("body_col", "company2")
    if kind == "cattle":
        o.box((0, bc, bz), (W, blen, 0.15), "wood")
        for k in range(4):                                        # 條狀圍欄（中間留縫）
            z = bz + 0.25 + k * 0.42
            for s in (-1, 1):
                o.box((s * (hw - 0.04), bc, z), (0.08, blen, 0.22), "lightwood")
            o.box((0, body_rear + 0.04, z), (W, 0.08, 0.22), "lightwood")
        n = max(3, int(blen / 0.9))
        for k in range(n + 1):
            y = body_rear + k * blen / n
            for s in (-1, 1):
                o.box((s * (hw - 0.03), y, bz), (0.1, 0.1, 1.85), b2)
    elif kind == "flatbed":
        o.box((0, bc, bz), (W, blen, 0.2), "planks")
        o.box((0, body_front - 0.05, bz), (W, 0.1, 1.0), b2)                                # 前擋板
        cg = st.get("cargo")
        top = bz + 0.2
        if cg == "paper":                                         # 紙捲（白色圓柱）
            n = max(2, int(blen / 1.1))
            for k in range(n):
                y = body_rear + (k + 0.5) * blen / n
                o.append({"op": "cylx", "c": [0, y, top + 0.45], "r": 0.45, "w": W * 0.85, "m": "white", "v": 12})
        elif cg == "steel":                                       # 鋼材（灰色長條堆）
            for layer in range(3):
                for k in range(3):
                    o.box(((k - 1) * W * 0.28, bc, top + layer * 0.22), (W * 0.24, blen * 0.92, 0.2), "steel" if (k + layer) % 2 else "darksteel")
        elif cg == "timber":                                      # 原木
            for layer, n in ((0, 4), (1, 3), (2, 2)):
                for k in range(n):
                    x = (k - (n - 1) / 2) * W * 0.24
                    cyly(o, (x, bc, top + 0.2 + layer * 0.32), 0.2, blen * 0.95, "logs", v=8)
    elif kind in ("box", "mail"):
        h = 2.0 if kind == "box" else 1.7
        o.box((0, bc, bz), (W, blen, h), b2)
        o.box((0, bc, bz + h), (W * 1.02, blen * 1.01, 0.08), "white")
        if kind == "mail":
            for s in (-1, 1):
                o.box((s * (hw + 0.01), bc, bz + h * 0.4), (0.02, blen * 0.9, 0.25), "red")
        o.box((0, body_rear - 0.01, bz + 0.1), (W * 0.9, 0.03, h - 0.2), "darksteel")      # 後門
    elif kind == "hopper":
        top = bz + 1.2
        loft(o, [(body_rear, hw, bz, top), (body_front, hw, bz, top)], b2)
        o.box((0, bc, top - 0.05), (W * 0.9, blen * 0.95, 0.08), "black")                    # 斗內（空）
        cg = st.get("cargo")
        if cg:
            m = {"coal": "coal", "grain": "hay", "ironOre": "ore"}[cg]
            o.hip((0, bc, top), (W * 0.9, blen * 0.92, 0.55), m, k=0.6)
    elif kind == "tanker":
        cyly(o, (0, bc, bz + 0.85), 0.85 * W / 2, blen * 0.95, R.get("tank_col", "silver"), v=16)
        for y in (body_rear + blen * 0.3, body_rear + blen * 0.7):
            o.box((0, y, bz + 1.7), (0.4, 0.4, 0.15), "darksteel")
        o.box((0, bc, bz), (W * 0.5, blen * 0.9, 0.3), "darksteel")
    lights(o, rear, bz + 0.1, hw, False, brake=st.get("brake"))
    return o


# ---------------------------------------------------------------- 巴士

def bus(R, L, st):
    o = Ops()
    W = 2.5
    hw = W / 2
    r = 0.5
    front, rear = L / 2, -L / 2
    decks = R.get("decks", 1)
    H = 3.0 if decks == 1 else 4.3
    z0 = 0.35
    col, col2 = "company", R.get("trim", "company2")
    for y in (front - 0.17 * L, rear + 0.22 * L):
        axle_pair(o, y, r, hw * 0.98, w=0.3)
    style = R.get("style")
    if style == "halfcab":                                       # 半駕駛室雙層巴士（前置引擎、後開放平台）
        bl = 0.12 * L
        o.box((0, (front - bl + rear) / 2, z0), (W, L - bl, H), col)
        o.box((W * 0.25, front - bl / 2, z0), (W * 0.45, bl, 1.3), col)                     # 引擎蓋
        o.box((W * 0.25, front - 0.01, z0 + 0.2), (W * 0.35, 0.04, 0.9), "silver")
        o.box((-W * 0.25, front - bl / 2, z0), (W * 0.48, bl, 2.1), col)                    # 駕駛室
        o.box((-W * 0.25, front - 0.01, z0 + 1.2), (W * 0.4, 0.04, 0.7), "glass")
        o.box((0, rear + 0.5, z0), (W * 0.98, 1.0, 1.8), "black")                           # 後平台開口
        windows_side(o, rear + 1.1, front - bl - 0.2, z0 + 1.2, z0 + 2.0, hw, 5)
        windows_side(o, rear + 0.3, front - bl - 0.2, z0 + 2.7, z0 + 3.6, hw, 6)
        o.box((0, (front - bl + rear) / 2, z0 + 2.2), (W * 1.01, L - bl, 0.25), col2)
        loft(o, [(rear, hw, z0 + H, z0 + H + 0.25), (front - bl, hw, z0 + H, z0 + H + 0.25)], col)
        o.box((0, front - bl, z0 + 2.7), (W, 0.04, 0.9), "glass")
    else:
        rake = 0.5 if style == "coach" else 0.15
        prof = [(rear, z0), (front, z0), (front, z0 + H * 0.4), (front - rake, z0 + H), (rear + 0.1, z0 + H)]
        side_profile(o, prof, hw, col)
        o.box((0, front - rake / 2, z0 + H * 0.42), (W * 0.9, 0.05, H * 0.5), "glass")
        if decks == 2:
            windows_side(o, rear + 0.4, front - 0.6, z0 + 1.0, z0 + 1.9, hw, 6)
            windows_side(o, rear + 0.4, front - 0.4, z0 + 2.6, z0 + 3.6, hw, 6)
            o.box((0, 0, z0 + 2.1), (W * 1.01, L * 0.98, 0.3), col2)
            o.box((0, front - 0.02, z0 + 2.65), (W * 0.85, 0.04, 0.9), "glass")
        else:
            windows_side(o, rear + 0.5, front - rake - 0.3, z0 + 1.2, z0 + H - 0.3, hw, 7, gap=0.12)
            o.box((0, 0, z0 + 0.5), (W * 1.01, L * 0.95, 0.35), col2)
            o.box((0, rear + 0.6, z0 + H), (W * 0.6, 1.0, 0.25), "silver")                 # 車頂行李架／空調
        o.box((0, front + 0.01, z0 + 0.25), (W * 0.6, 0.04, 0.3), "silver")
    lights(o, front + 0.02, z0 + 0.3, hw, True)
    lights(o, rear - 0.02, z0 + 0.5, hw, False, brake=st.get("brake"))
    return o


# ---------------------------------------------------------------- 船

def hull(o, L, beam, free, m="black", deck="planks", bow=0.25, stern=0.08, waterline="red"):
    """船殼（水線以上）：船首尖、船尾略收窄；水線色帶。"""
    hb = beam / 2
    secs = [(-L / 2, hb * 0.75, 0, free * 0.95), (-L / 2 + stern * L, hb, 0, free), (L / 2 - bow * L, hb, 0, free),
            (L / 2 - bow * L * 0.4, hb * 0.6, 0, free * 1.05), (L / 2, 0.05, 0.3, free * 1.15)]
    loft(o, secs, m)
    loft(o, [(s[0], s[1] + 0.01, 0, 0.35) for s in secs[:-1]] + [(L / 2 - 0.05, 0.08, 0.3, 0.4)], waterline)
    loft(o, [(s[0], s[1] * 0.96, s[3] - 0.05, s[3]) for s in secs[:-1]] + [(L / 2 - 0.3, 0.15, free * 1.05, free * 1.1)], deck)


def funnel(o, y, z, r, h, band="company", m="black", x=0.0, rake=0.0):
    cyly_up(o, (x, y, z), r, h, band, rt=r * 0.95)
    cyly_up(o, (x, y, z + h * 0.75), r * 1.01, h * 0.25, m)


def cyly_up(o, c, r, h, m, rt=None):
    o.cyl(list(c), r, h, m, v=14, **({"rt": rt} if rt is not None else {}))


def superstructure(o, y0, y1, hw, z0, levels, lh=1.0, m="white", win=True):
    for k in range(levels):
        shrink = k * 0.08 * (y1 - y0)
        a, b = y0 + shrink * 0.3, y1 - shrink * 0.7
        o.box((0, (a + b) / 2, z0 + k * lh), (hw * 2 * (1 - 0.06 * k), b - a, lh), m)
        if win:
            windows_side(o, a + 0.2, b - 0.2, z0 + k * lh + 0.35, z0 + k * lh + 0.7, hw * (1 - 0.06 * k), max(2, int((b - a) / 0.8)), gap=0.4)
    return z0 + levels * lh


def mast(o, y, z, h, m="darkwood", r=0.08):
    o.cyl([0, y, z], r, h, m, v=8, rt=r * 0.6)


def ship(R, L, st):
    o = Ops()
    kind = R["kind"]
    a = st.get("anim", 0)
    if kind == "cargo":                                           # 貨輪：前方貨艙與吊桿、後方船橋
        beam, free = L * 0.16, 1.6
        hull(o, L, beam, free, m=R.get("hull", "black"))
        hw = beam / 2
        aft = R.get("bridge", "aft")
        by = -L * 0.3 if aft == "aft" else 0.0
        top = superstructure(o, by - L * 0.08, by + L * 0.08, hw * 0.8, free, 3, 0.9)
        o.box((0, by + L * 0.07, top), (hw * 1.9, 0.6, 0.3), "white")                     # 駕駛台兩翼
        funnel(o, by - L * 0.06, top, 0.45, 1.6)
        for k, y in enumerate((L * 0.32, L * 0.15, -L * 0.02) if aft == "aft" else (L * 0.3, L * 0.15, -L * 0.18, -L * 0.32)):
            o.box((0, y, free), (hw * 1.2, L * 0.1, 0.5), R.get("hatch", "company2"))
        for y in ((L * 0.235, L * 0.06) if aft == "aft" else (L * 0.23, -L * 0.25)):
            mast(o, y, free, 4.0, "steel")
            o.seg((0, y, free + 3.6), (0, y + 2.0, free + 0.6), "steel", r=0.05)
            o.seg((0, y, free + 3.6), (0, y - 2.0, free + 0.6), "steel", r=0.05)
    elif kind == "bulk":
        beam, free = L * 0.15, 1.3
        hull(o, L, beam, free, m=R.get("hull", "darkstone"), deck="rust")
        hw = beam / 2
        for k in range(6):
            o.box((0, L * 0.33 - k * L * 0.1, free), (hw * 1.3, L * 0.08, 0.35), "company2")
        top = superstructure(o, -L * 0.48, -L * 0.36, hw * 0.9, free, 4, 0.8)
        funnel(o, -L * 0.45, top, 0.4, 1.2)
    elif kind == "tanker":
        beam, free = L * 0.15, 1.1
        hull(o, L, beam, free, m=R.get("hull", "darksteel"), deck="rust")
        hw = beam / 2
        o.seg((0, -L * 0.3, free + 0.4), (0, L * 0.35, free + 0.4), "steel", r=0.12)        # 甲板管線
        for y in (L * 0.25, 0.0, -L * 0.2):
            o.box((0, y, free), (hw * 0.6, 0.4, 0.5), "darksteel")
        superstructure(o, -0.02 * L, 0.08 * L, hw * 0.75, free, 2, 0.9)                    # 船中船橋
        top = superstructure(o, -L * 0.48, -L * 0.36, hw * 0.85, free, 2, 0.9)
        funnel(o, -L * 0.44, top, 0.4, 1.4)
    elif kind == "ferry":
        beam, free = L * 0.2, 1.4
        hull(o, L, beam, free, m=R.get("hull", "white"), waterline="company2", deck="planks")
        hw = beam / 2
        top = superstructure(o, -L * 0.35, L * 0.25, hw * 0.95, free, R.get("decks", 2), 1.0, m="white")
        if R.get("paddles"):                                       # 明輪蒸汽渡輪：兩側明輪箱、雙高煙囪
            for s in (-1, 1):
                o.append({"op": "cylx", "c": [s * (hw + 0.3), 0, free], "r": 1.4, "w": 0.6, "m": "company", "v": 16})
            for y in (L * 0.06, -L * 0.12):
                funnel(o, y, top, 0.4, 2.6, band="black", m="company")
            mast(o, L * 0.32, free, 5.0)
        else:
            funnel(o, -L * 0.1, top, 0.55, 1.4)
            o.box((0, L * 0.15, top), (hw * 1.2, L * 0.12, 0.8), "white")                  # 駕駛台
            o.box((0, L * 0.21, top + 0.3), (hw * 1.2, 0.04, 0.35), "glass")
    elif kind == "clipper":                                       # 三桅帆船
        beam, free = L * 0.15, 1.3
        hull(o, L * 0.8, beam, free, m="black", deck="planks", bow=0.3, waterline="company2")
        o.seg((0, L * 0.38, free + 0.5), (0, L * 0.52, free + 1.8), "darkwood", r=0.08)    # 船首斜桅
        for y, h in ((L * 0.2, 9.0), (0.0, 10.0), (-L * 0.2, 8.0)):
            mast(o, y, free, h)
            for k, (zz, w) in enumerate(((0.3, 3.4), (0.55, 2.8), (0.78, 2.1))):         # 橫帆（白色薄板，正面朝前）
                o.box((0, y + 0.05, free + h * zz - 1.1 + 0.1), (w, 0.06, 2.0 if k < 2 else 1.5), "white")
                o.box((0, y + 0.1, free + h * zz + 0.9), (w * 1.05, 0.08, 0.08), "darkwood")
        o.box((0, -L * 0.33, free), (beam * 0.6, L * 0.08, 0.8), "darkwood")               # 船尾艙
    elif kind == "hovercraft":
        beam = L * 0.45
        loft(o, [(-L / 2, beam / 2, 0, 1.0), (L / 2 - 1.5, beam / 2, 0, 1.0), (L / 2, beam / 2 * 0.7, 0.2, 1.0)], "black")   # 氣墊裙
        o.box((0, 0, 1.0), (beam * 0.92, L * 0.9, 0.5), "white")
        superstructure(o, -L * 0.35, L * 0.3, beam * 0.38, 1.5, 1, 1.4, m="white")
        o.box((0, L * 0.3, 2.3), (beam * 0.5, 0.8, 0.8), "white")
        o.box((0, L * 0.34, 2.5), (beam * 0.45, 0.04, 0.4), "glass")
        for x, y in ((-beam * 0.3, -L * 0.32), (beam * 0.3, -L * 0.32)):                   # 螺旋槳（2 格動畫）
            o.cyl([x, y, 2.9], 0.15, 2.2, "darksteel", v=8)
            for k in range(4):
                ang = math.radians(45 * a + 90 * k + 20)
                o.seg((x, y + 0.2, 5.1), (x + 1.5 * math.cos(ang), y + 0.2, 5.1 + 1.5 * math.sin(ang)), "darksteel", r=0.12)
            fin(o, [(y - 1.2, 2.5), (y - 0.4, 2.5), (y - 0.6, 5.5), (y - 1.2, 5.5)], x - 0.05, x + 0.05, "company")
    elif kind in ("hydrofoil", "jetfoil"):                       # 速度動畫：0 慢速（船身在水面）→ 3 高速（船身升起，水翼露出）
        lift = a / max(st.get("anims", 4) - 1, 1)
        rise = 1.6 * lift
        beam = L * 0.18
        for y in (L * 0.3, -L * 0.3):                                                        # 水翼支柱
            for s in (-1, 1):
                o.box((s * beam * 0.45, y, 0), (0.12, 0.3, rise + 0.5), "darksteel")
            o.box((0, y, max(0.0, rise - 1.2)), (beam * 1.1, 0.5, 0.12), "darksteel")
        hm = "company" if kind == "jetfoil" else "white"
        loft(o, [(-L / 2, beam / 2 * 0.9, rise, rise + 1.3), (L / 2 - 2.0, beam / 2, rise, rise + 1.4), (L / 2, 0.2, rise + 0.5, rise + 1.5)], hm)
        top = superstructure(o, -L * 0.4, L * 0.25, beam * 0.45, rise + 1.4, 1 if kind == "hydrofoil" else 2, 1.0, m="white")
        o.box((0, L * 0.2, top - 1.0), (beam * 0.8, 0.04, 0.5), "glass")
        if lift > 0.3:                                                                       # 水花
            for s in (-1, 1):
                o.hip((s * beam * 0.6, -L * 0.35, 0), (0.8, 2.0 * lift, 0.6 * lift), "white", k=0.6)
    return o


# ---------------------------------------------------------------- 飛機

def fuselage(o, L, r, nose=0.12, tail=0.25, m="white", zc=None, hump=0.0):
    zc = r * 1.6 if zc is None else zc
    secs = [(-L / 2, r * 0.12, zc + r * 0.55), (-L / 2 + tail * L * 0.4, r * 0.5, zc + r * 0.35), (-L / 2 + tail * L, r, zc),
            (L / 2 - nose * L, r, zc), (L / 2 - nose * L * 0.4, r * 0.75, zc - r * 0.08), (L / 2, r * 0.15, zc - r * 0.25)]
    tube(o, secs, m, seg=12)
    if hump:
        tube(o, [(L / 2 - nose * L - hump * L, r * 0.3, zc + r * 0.75), (L / 2 - nose * L - hump * L * 0.5, r * 0.6, zc + r * 0.55),
                 (L / 2 - nose * L * 0.6, r * 0.55, zc + r * 0.45), (L / 2 - nose * L * 0.3, r * 0.2, zc + r * 0.3)], m, seg=10)
    return zc


def wing(o, root_y, span, chord, sweep, z, thick=0.18, m="white", dihedral=0.0, taper=0.4):
    """左右對稱的機翼：root_y = 翼根前緣位置；sweep = 翼尖前緣往後的距離。"""
    for s in (-1, 1):
        pts = [(0.0, root_y), (s * span / 2, root_y - sweep), (s * span / 2, root_y - sweep - chord * taper), (0.0, root_y - chord)]
        if s < 0:
            pts = pts[::-1]
        prism(o, pts, z, z + thick, m)


def engine_pod(o, x, y, z, r, length, m="silver"):
    cyly(o, (x, y, z), r, length, m, rt=r * 0.85, v=12)
    o.cyl([x, y - length * 0.1, z + r * 0.8], 0.06, 0.5, "darksteel", v=6)


def prop(o, x, y, z, r, frame, blades=3, m="darksteel"):
    """螺旋槳：快速轉動時畫成半透明感的槳葉（依動畫格轉角）。"""
    for k in range(blades):
        ang = math.radians(frame * 37 + k * 360 / blades)
        o.seg((x, y, z), (x + r * math.cos(ang), y, z + r * math.sin(ang)), m, r=0.07)
    o.cyl([x, y - 0.1, z - 0.15], 0.12, 0.3, "silver", v=8)


def tail(o, y_tail, H, chord, z0, span_h, m="white", t_tail=False, fin_col="company"):
    fin(o, [(y_tail, z0), (y_tail + chord, z0), (y_tail + chord * 0.35, z0 + H), (y_tail + chord * 0.05, z0 + H)], -0.08, 0.08, fin_col)
    zt = z0 + H * 0.95 if t_tail else z0 + 0.1
    for s in (-1, 1):
        pts = [(0, y_tail + chord * (0.75 if t_tail else 0.8)), (s * span_h / 2, y_tail + chord * 0.3), (s * span_h / 2, y_tail + chord * 0.05), (0, y_tail)]
        if s < 0:
            pts = pts[::-1]
        prism(o, pts, zt, zt + 0.1, m)


def gear(o, y, x, z_belly, r=0.35):
    o.seg((x, y, z_belly), (x, y, r), "darksteel", r=0.06)
    wheel(o, x, y, r, w=0.2, hub="silver")


def aircraft(R, L, st):
    o = Ops()
    a = st.get("anim", 0)
    kind = R["kind"]
    col, col2 = "white", "company"
    if kind == "jet":
        n_eng = R.get("engines", 2)
        r = L * R.get("width", 0.055)
        zc = fuselage(o, L, r, m=col, hump=R.get("hump", 0.0))
        span = L * R.get("span", 0.95)
        chord = L * 0.18
        wy = L * R.get("wing_pos", 0.08)
        wz = zc - r * (0.55 if not R.get("high") else -0.7)
        wing(o, wy, span, chord, span * 0.28, wz, m=col)
        o.box((0, 0, zc + r * 0.05), (r * 2.02, L * 0.7, r * 0.18), col2)                   # 公司色腰線
        windows_side(o, -L * 0.3, L * 0.32, zc + r * 0.15, zc + r * 0.35, r * 0.98, 16, gap=0.5)
        if R.get("decks2"):
            windows_side(o, -L * 0.25, L * 0.3, zc + r * 0.6, zc + r * 0.78, r * 0.85, 14, gap=0.5)
        tail(o, -L / 2 + 0.2, r * 3.2, L * 0.16, zc + r * 0.4, span * 0.36, t_tail=R.get("t_tail", False))
        if R.get("rear_engines"):
            for s in (-1, 1):
                engine_pod(o, s * r * 1.5, -L * 0.33, zc + r * 0.4, r * 0.45, L * 0.12)
        else:
            pos = [0.32] if n_eng == 2 else [0.22, 0.4]
            for p in pos:
                for s in (-1, 1):
                    x = s * span / 2 * p
                    y = wy - chord * 0.1 - span * 0.28 * p + L * 0.05
                    engine_pod(o, x, y, wz - r * 0.55, r * 0.42, L * 0.11)
        gear(o, L * 0.36, 0, zc - r, r=0.3)
        for s in (-1, 1):
            gear(o, wy - chord * 0.6, s * r * 1.4, wz, r=0.38)
    elif kind == "sst":
        r = L * 0.035
        zc = fuselage(o, L, r, nose=0.18, m=col)
        for s in (-1, 1):
            pts = [(0, L * 0.18), (s * L * 0.2, -L * 0.36), (0, -L * 0.36)]
            if s < 0:
                pts = pts[::-1]
            prism(o, pts, zc - r * 0.8, zc - r * 0.6, col)
            for k in (0.08, 0.13):
                engine_pod(o, s * L * k, -L * 0.25, zc - r * 1.3, r * 0.45, L * 0.14, m="silver")
        fin(o, [(-L * 0.46, zc + r * 0.3), (-L * 0.28, zc + r * 0.3), (-L * 0.4, zc + r * 4.5), (-L * 0.46, zc + r * 4.5)], -0.08, 0.08, col2)
        o.box((0, 0, zc), (r * 2.02, L * 0.6, r * 0.15), col2)
        windows_side(o, -L * 0.2, L * 0.25, zc + r * 0.1, zc + r * 0.4, r * 0.98, 14, gap=0.55)
        gear(o, L * 0.3, 0, zc - r)
        for s in (-1, 1):
            gear(o, -L * 0.12, s * r * 2, zc - r, r=0.4)
    elif kind in ("prop", "turboprop", "biplane", "trimotor"):
        r = L * R.get("width", 0.06)
        tail_down = R.get("taildragger", False)
        zc = fuselage(o, L, r, nose=0.1, tail=0.3, m=R.get("body", col))
        span = L * R.get("span", 1.25)
        chord = L * 0.16
        high = R.get("high", False)
        wy = L * 0.12
        wz = zc + r * 0.85 if high else zc - r * 0.6
        wmat = R.get("wing_mat", col)
        wing(o, wy, span, chord, 0.0 if kind != "turboprop" else span * 0.04, wz, m=wmat, taper=0.6)
        if kind == "biplane":                                    # 上下兩層翼 + 支柱
            wing(o, wy + 0.2, span, chord, 0.0, zc + r * 1.6, m=wmat, taper=0.9)
            for s in (-1, 1):
                for yy in (wy - 0.2, wy - chord + 0.3):
                    o.seg((s * span * 0.3, yy, wz), (s * span * 0.3, yy + 0.2, zc + r * 1.6), "darkwood", r=0.04)
        o.box((0, 0, zc + r * 0.1), (r * 2.02, L * 0.6, r * 0.2), col2)
        windows_side(o, -L * 0.2, L * 0.28, zc + r * 0.2, zc + r * 0.5, r * 0.98, 8, gap=0.45)
        tail(o, -L / 2 + 0.1, r * 3.4, L * 0.15, zc + r * 0.3, span * 0.35, m=wmat)
        n = R.get("engines", 2)
        xs = []
        if n in (1, 3):
            xs.append(0.0)
        if n >= 2:
            xs += [-span * 0.18, span * 0.18]
        if n == 4:
            xs += [-span * 0.34, span * 0.34]
        for x in xs:
            if x == 0.0:
                y = L / 2 + 0.05
                zz = zc - r * 0.2
            else:
                y = wy + 0.35
                zz = wz + (0.1 if high else 0.05)
                cyly(o, (x, wy - 0.6, zz), r * 0.42, 1.3, "silver", rt=r * 0.3)             # 引擎艙
            prop(o, x, y + 0.75, zz, L * 0.075, a, blades=4 if kind == "turboprop" else 3)
        gy = wy - chord * 0.4
        for s in (-1, 1):
            gear(o, gy, s * (span * 0.18 if n >= 2 else r * 1.8), wz if not high else zc - r, r=0.35)
        if tail_down:
            wheel(o, 0, -L * 0.42, 0.18, w=0.12)
        else:
            gear(o, L * 0.36, 0, zc - r, r=0.28)
        if R.get("ramp"):
            o.box((0, -L * 0.3, zc - r), (r * 1.6, L * 0.12, r * 0.5), col)
    elif kind == "heli":
        L = L * 1.3                                              # 模板的車長只算機身；放大讓整體（含旋翼盤）接近 vanilla 尺寸
        r = L * 0.09
        zc = 1.1
        tube(o, [(-L * 0.12, r * 0.6, zc + r * 0.2), (0.0, r, zc), (L * 0.25, r * 0.9, zc - r * 0.05), (L * 0.4, r * 0.3, zc - r * 0.3)], col2, seg=12)
        tube(o, [(-L * 0.45, r * 0.12, zc + r * 0.5), (-L * 0.12, r * 0.35, zc + r * 0.3)], col2, seg=8)  # 尾桁
        fin(o, [(-L * 0.47, zc + r * 0.4), (-L * 0.4, zc + r * 0.4), (-L * 0.44, zc + r * 1.8), (-L * 0.48, zc + r * 1.8)], -0.05, 0.05, col2)
        o.box((0, L * 0.3, zc - r * 0.3), (r * 1.6, 0.04, r * 0.9), "glass")
        windows_side(o, -L * 0.05, L * 0.25, zc, zc + r * 0.5, r * 0.98, 3, gap=0.3)
        for s in (-1, 1):                                        # 滑橇
            o.seg((s * r * 0.9, -L * 0.12, 0.08), (s * r * 0.9, L * 0.25, 0.08), "darksteel", r=0.06)
            o.seg((s * r * 0.9, 0, 0.08), (s * r * 0.6, 0, zc - r * 0.8), "darksteel", r=0.04)
        hub_z = zc + r * 1.25
        o.cyl([0, 0, zc + r * 0.8], 0.12, r * 0.5, "darksteel", v=8)
        blades = R.get("blades", 4)
        for k in range(blades):
            ang = math.radians(a * 45 / 2 + k * 360 / blades + 10)
            o.seg((0, 0, hub_z), (L * 0.6 * math.cos(ang), L * 0.6 * math.sin(ang), hub_z + 0.05), "darksteel", r=0.22)
        for k in range(2):
            ang = math.radians(a * 60 + k * 90)
            o.seg((0.12, -L * 0.46, zc + r * 1.2), (0.12, -L * 0.46 + 1.1 * math.cos(ang), zc + r * 1.2 + 1.1 * math.sin(ang)), "darksteel", r=0.12)
    return o


# ---------------------------------------------------------------- 火車

def bogie_model(R, L, st):
    """貨車轉向架（單獨的 bogie sprite）：兩軸、側架。"""
    o = Ops()
    r = 0.45
    for y in (-0.9, 0.9):
        axle_pair(o, y, r, 0.75, w=0.12, hub="darksteel")
    for s in (-1, 1):
        o.box((s * 0.78, 0, r * 0.6), (0.1, 2.6, 0.45), "darksteel")
    o.box((0, 0, r * 1.2), (1.6, 0.6, 0.25), "darksteel")
    return o


def boxcar_body(R, L, st):
    o = Ops()
    W = 2.8
    z0 = 1.1
    o.box((0, 0, z0 - 0.3), (W * 0.9, L, 0.3), "darksteel")
    o.box((0, 0, z0), (W, L * 0.97, 2.6), R.get("col", "company"))
    o.hip((0, 0, z0 + 2.6), (W * 1.02, L * 0.98, 0.35), "darksteel", k=0.95)
    for s in (-1, 1):
        o.box((s * (W / 2 + 0.02), 0, z0 + 0.1), (0.04, L * 0.25, 2.3), "darkwood")       # 滑門
        for y in (-L * 0.3, L * 0.3):
            o.box((s * (W / 2 + 0.02), y, z0), (0.05, 0.12, 2.6), "darksteel")
    for y in (-L / 2, L / 2):
        o.box((0, y, z0 - 0.1), (0.4, 0.3, 0.3), "darksteel")                               # 連結器
    return o


def steam_loco(R, L, st):
    """蒸汽機車（車身內含車輪；4 格動畫 = 動輪轉動與連桿）。"""
    o = Ops()
    a = st.get("anim", 0)
    phase = 2 * math.pi * a / max(st.get("anims", 4), 1)
    W = 2.7
    streamlined = R.get("streamlined", False)
    drivers = 3
    dr = 0.95
    front, rear = L / 2, -L / 2
    # 動輪與導輪、從輪
    dys = [rear + 0.22 * L + k * 2.05 for k in range(drivers)]
    lead = [front - 0.13 * L, front - 0.13 * L - 1.4]
    trail = [rear + 0.06 * L] if R.get("trailing") else []
    for y in dys:
        axle_pair(o, y, dr, 1.45, w=0.16, hub="red" if not streamlined else "silver")
    for y in lead + trail:
        axle_pair(o, y, 0.5, 1.4, w=0.14, hub="darksteel")
    # 連桿
    for s in (-1, 1):
        x = s * 1.58
        py = [y + 0.45 * math.cos(phase) for y in dys]
        pz = [dr + 0.45 * math.sin(phase) for _ in dys]
        o.seg((x, py[0], pz[0]), (x, py[-1], pz[-1]), "silver", r=0.06)
        o.seg((x, py[-1], pz[-1]), (x, lead[0] - 1.3, 1.3), "silver", r=0.06)
    o.box((0, (front + rear) / 2, 1.15), (W * 0.75, L * 0.95, 0.4), "black")                  # 車架
    for s in (-1, 1):
        o.box((s * 1.25, (front + rear) / 2 + 0.3, 1.9), (0.35, L * 0.75, 0.12), R.get("col", "company"))   # 踏板
    by0, by1 = rear + 0.2 * L, front - 0.05 * L
    if streamlined:                                              # 流線型外殼：子彈頭
        tube(o, [(rear + 0.2 * L, 1.5, 2.6), (front - 0.3 * L, 1.5, 2.6), (front - 0.12 * L, 1.35, 2.45), (front - 0.03 * L, 0.9, 2.2), (front, 0.3, 1.9)],
             R.get("col", "company"), seg=14)
        o.box((0, (by0 + front) / 2, 1.3), (W * 0.98, front - by0, 1.2), R.get("col", "company"))
        for s in (-1, 1):
            o.box((s * (W / 2 + 0.01), (by0 + front) / 2, 2.0), (0.02, front - by0, 0.18), R.get("stripe", "company2"))
            o.box((s * (W / 2 + 0.01), (by0 + front) / 2, 1.6), (0.02, front - by0, 0.08), R.get("stripe", "company2"))
        cab_m = R.get("col", "company")
    else:
        cyly(o, (0, (by0 + by1) / 2, 2.55), 0.95, by1 - by0, R.get("boiler", "company"), v=16)
        o.cyl([0, by1 - 0.25, 1.6], 0.98, 0.0001, "black", v=16)
        cyly(o, (0, by1 + 0.05, 2.55), 0.97, 0.1, "black", v=16)                             # 煙箱門
        o.cyl([0, by1 - 0.6, 3.4], 0.28, 1.0, "black", v=10, rt=0.3)                          # 煙囪
        o.cyl([0, (by0 + by1) / 2 + 0.3, 3.4], 0.35, 0.5, "gold", v=10, rt=0.25)               # 汽包
        for k in range(3):                                        # 鍋爐束環
            cyly(o, (0, by0 + (by1 - by0) * (0.2 + 0.3 * k), 2.55), 0.97, 0.12, "gold", v=16)
        for s in (-1, 1):
            o.box((s * 1.2, lead[0] - 0.3, 0.9), (0.35, 1.4, 0.75), "black")                 # 汽缸
        cab_m = R.get("cab", "company")
    # 駕駛室
    cy0, cy1 = rear, rear + 0.2 * L
    side_profile(o, [(cy0, 1.3), (cy1, 1.3), (cy1, 3.9), (cy0 + 0.3, 4.1), (cy0, 4.0)], 1.35, cab_m)
    windows_side(o, cy0 + 0.4, cy1 - 0.3, 2.9, 3.6, 1.35, 1)
    o.box((0, cy1 + 0.01, 3.0), (2.0, 0.04, 0.6), "glass")
    o.box((0, (cy0 + cy1) / 2, 4.05), (2.9, cy1 - cy0 + 0.3, 0.12), "black")
    lights(o, front + 0.02, 1.6, 1.0, True, s=0.15)
    return o


def tender(R, L, st):
    o = Ops()
    W = 2.7
    n = 3
    for k in range(n):
        axle_pair(o, -L * 0.3 + k * L * 0.3, 0.55, 1.4, w=0.14, hub="darksteel")
    o.box((0, 0, 1.0), (W * 0.8, L * 0.95, 0.4), "black")
    m = R.get("col", "company")
    if R.get("streamlined"):
        loft(o, [(-L / 2, W / 2, 1.3, 3.6), (L / 2 - 0.3, W / 2, 1.3, 3.6), (L / 2, W / 2 * 0.95, 1.3, 3.8)], m)
        for s in (-1, 1):
            o.box((s * (W / 2 + 0.01), 0, 2.0), (0.02, L * 0.95, 0.18), R.get("stripe", "company2"))
    else:
        o.box((0, 0, 1.3), (W, L * 0.95, 2.2), m)
        o.hip((0, L * 0.15, 3.5), (W * 0.85, L * 0.5, 0.6), "coal", k=0.5)
        o.box((0, 0, 3.4), (W * 1.01, L * 0.96, 0.15), "black")
    return o


# ---------------------------------------------------------------- 入口

def model(R, L, st):
    cat = R["cat"]
    if cat == "truck":
        return truck(R, L, st)
    if cat == "bus":
        return bus(R, L, st)
    if cat == "ship":
        return ship(R, L, st)
    if cat == "air":
        return aircraft(R, L, st)
    if cat == "train":
        part = st.get("part", "body")
        if R["kind"] == "boxcar":
            return bogie_model(R, L, st) if part == "bogie" else boxcar_body(R, L, st)
        if st.get("body", 0) == 0:
            return steam_loco(R, L, st)
        return tender(R, L, st)
    raise SystemExit(f"未知車種 {cat}")
