#!/usr/bin/env python3
"""軌道類物件的程序化等角像素圖：窄軌（track）、第三軌／齒軌（trackExtra）、電車軌（road style 1）。

每張 sprite 對應「片段 × 格（sequence）× 方向（× 圖層）」，影像名稱表、片段的圖塊配置與中心線
都來自 tools/gen/data/track_geometry.json（由 tools/gen/extract_track_geometry.py 從 OpenLoco 原始碼抽出）。
做法：沿中心線在世界座標中取樣出道碴、枕木、鋼軌等表面，只保留落在該格圖塊（32 × 32）內的點，
以 OpenLoco 的投影（tools/gen/iso.py）畫成像素；圖塊原點 = sprite 的繪製原點。

  python3 tools/gen/track_iso.py --template <模板.DAT> --style narrow|thirdrail|rack|tram -o <sprites 資料夾>

樣式：
- narrow：窄軌（track，412 張）：道碴、枕木、鋼軌三層（可合併的片段分開畫，坡道類合成一張）＋ UI 圖示
- thirdrail：第三軌（trackExtra style 0）：軌道外側架在絕緣座上的導電軌＋ 8 格分頁圖示
- rack：齒軌（trackExtra style 0）：兩鋼軌中間的雙片齒條＋ 8 格分頁圖示（齒輪）
- tram：電車軌（road style 1）：每條車道一組軌道，鋪石路面＋ UI 圖示
模板中用不到的影像（例如模板比 style 0 影像表多出來的部分）輸出 1×1 透明。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

import common
import iso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

GEOM = json.loads((Path(__file__).resolve().parent / "data" / "track_geometry.json").read_text())
TRACK_IDS = ["Straight", "Diagonal", "LeftCurveVerySmall", "RightCurveVerySmall", "LeftCurveSmall", "RightCurveSmall",
             "LeftCurve", "RightCurve", "LeftCurveLarge", "RightCurveLarge", "DiagonalLeftCurveLarge",
             "DiagonalRightCurveLarge", "SBendLeft", "SBendRight", "StraightSlopeUp", "StraightSlopeDown",
             "StraightSteepSlopeUp", "StraightSteepSlopeDown", "LeftCurveSmallSlopeUp", "RightCurveSmallSlopeUp",
             "LeftCurveSmallSlopeDown", "RightCurveSmallSlopeDown", "LeftCurveSmallSteepSlopeUp",
             "RightCurveSmallSteepSlopeUp", "LeftCurveSmallSteepSlopeDown", "RightCurveSmallSteepSlopeDown"]
ROAD_IDS = ["Straight", "LeftCurveVerySmall", "RightCurveVerySmall", "LeftCurveSmall", "RightCurveSmall",
            "StraightSlopeUp", "StraightSlopeDown", "StraightSteepSlopeUp", "StraightSteepSlopeDown", "Turnaround"]
DIRS = {"NE": 0, "SE": 1, "SW": 2, "NW": 3, "E": 0, "S": 1}
NAME_RE = re.compile(r"^k([A-Za-z]+?)(\d+)(Ballast|Sleeper|Rail)?(NE|SE|SW|NW|E|S)$")

GREY, OLIVE, DKYEL, AVOCADO, MORANGE, BROWN, YELLOW, RED = 0x0A, 0x16, 0x22, 0x52, 0x6A, 0xD6, 0x2E, 0xA6
PRIMARY = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))   # 公司主色 remap（12 階）
LIGHT = (0.42, 0.12, 0.90)


def rot(x, y, r):
    return [(x, y), (y, -x), (-x, -y), (-y, x)][r]


def unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def lit(normal) -> float:
    """法向量的明暗偏移（色階格數）：平面 0，朝 +x 稍暗，朝 +y 更暗。"""
    L = unit(LIGHT)
    n = unit(normal)
    return (sum(a * b for a, b in zip(n, L)) - L[2]) * 6.0


def shade(ramp, v):
    return ramp + int(max(0, min(11, round(v))))


# ---------------------------------------------------------------- 中心線
class Path3:
    """平滑後的中心線：等距取樣點，每點有位置、切線（3D）與水平左法線。"""

    def __init__(self, pts, step=0.25, extend=3.0):
        P = [tuple(map(float, p)) for p in pts]
        # 1 單位整數格點 → 5 點移動平均（端點以直線外插補齊，避免縮短）
        def ext(a, b, k):
            return tuple(a[i] + (a[i] - b[i]) * k for i in range(3))
        if len(P) >= 3:
            head = [ext(P[0], P[2], k / 2) for k in (4, 3, 2, 1)]
            tail = [ext(P[-1], P[-3], k / 2) for k in (1, 2, 3, 4)]
            Q = head + P + tail
            S = []
            for i in range(2, len(Q) - 2):
                S.append(tuple(sum(Q[j][c] for j in range(i - 2, i + 3)) / 5 for c in range(3)))
            P = S
        # 兩端各延伸 extend 單位，確保鋪滿到圖塊邊緣（之後會被圖塊裁切）
        if len(P) >= 2:
            d0 = unit(tuple(P[0][i] - P[1][i] for i in range(3)))
            d1 = unit(tuple(P[-1][i] - P[-2][i] for i in range(3)))
            P = [tuple(P[0][i] + d0[i] * extend for i in range(3))] + P + [tuple(P[-1][i] + d1[i] * extend for i in range(3))]
        # 等距重新取樣
        seg = [math.dist(P[i], P[i + 1]) for i in range(len(P) - 1)]
        total = sum(seg)
        self.samples = []   # (s, pos, tangent, left)
        n = max(2, int(total / step))
        k, acc = 0, 0.0
        for j in range(n + 1):
            s = total * j / n
            while k < len(seg) - 1 and acc + seg[k] < s:
                acc += seg[k]
                k += 1
            t = (s - acc) / seg[k] if seg[k] else 0.0
            pos = tuple(P[k][i] + (P[k + 1][i] - P[k][i]) * t for i in range(3))
            tan = unit(tuple(P[k + 1][i] - P[k][i] for i in range(3)))
            left = unit((-tan[1], tan[0], 0.0))
            self.samples.append((s, pos, tan, left))
        self.length = total

    def at(self, s):
        """弧長 s 處的 (pos, tan, left)。"""
        i = min(len(self.samples) - 1, max(0, int(round(s / self.length * (len(self.samples) - 1)))))
        return self.samples[i][1:]


# ---------------------------------------------------------------- 樣式參數
STYLES = {
    # 道碴：頂面半寬、底面半寬、高；枕木：半長、厚（沿軌道方向）、高、間距；鋼軌：半軌距、高
    "narrow": dict(ballast=(5.6, 8.6, 1.2), sleeper=(4.3, 0.7, 0.5, 4.0), gauge=2.9, rail_h=0.8,
                   ballast_mix=[((GREY, 5), 30), ((GREY, 6), 22), ((BROWN, 5), 18), ((GREY, 4), 12), ((BROWN, 6), 10),
                                ((GREY, 7), 5), ((OLIVE, 5), 3)],
                   sleeper_mix=[((BROWN, 1), 65), ((BROWN, 2), 25), ((BROWN, 0), 10)]),
    "tram": dict(ballast=(14.6, 14.6, 0.0), sleeper=(0.0, 0.0, 0.0, 0.0), gauge=3.1, rail_h=0.25,
                 ballast_mix=[((GREY, 5), 30), ((GREY, 6), 26), ((GREY, 4), 16), ((BROWN, 6), 14), ((BROWN, 5), 10),
                              ((GREY, 7), 4)]),
}


def texel(mix, key, rng_seed=0):
    """依世界座標（四捨五入到 1 單位）挑選材質色：相同座標永遠同色，看起來是一顆顆的石頭。"""
    h = (key[0] * 73856093) ^ (key[1] * 19349663) ^ (key[2] * 83492791) ^ rng_seed
    r = random.Random(h).random() * sum(w for _, w in mix)
    for v, w in mix:
        r -= w
        if r <= 0:
            return v
    return mix[-1][0]


class Tile:
    """單一格的畫布：只接受落在 [tx, tx+32) × [ty, ty+32) 的點，座標轉成以該格原點為準。"""

    def __init__(self, tx, ty, tz, clip=True):
        self.c = iso.Canvas()
        self.tx, self.ty, self.tz, self.clip = tx, ty, tz, clip

    def plot(self, p, colour, bias=0.0):
        x, y, z = p
        if self.clip and not (self.tx <= x < self.tx + 32 and self.ty <= y < self.ty + 32):
            return
        self.c.plot(x - self.tx, y - self.ty, z - self.tz, colour, bias)


# ---------------------------------------------------------------- 圖層
def draw_ballast(tile, path, st, seed=0):
    wt, wb, hb = st["ballast"]
    mix = st["ballast_mix"]
    step_v = 0.3
    for s, pos, tan, left in path.samples:
        v = -wb
        while v <= wb + 1e-6:
            av = abs(v)
            if av <= wt or wb <= wt:
                z, nrm = hb, (-tan[2] * tan[0], -tan[2] * tan[1], 1.0)
            else:
                k = (wb - av) / (wb - wt)
                z = hb * k
                side = 1 if v > 0 else -1
                nrm = (left[0] * side * hb, left[1] * side * hb, (wb - wt))
            p = (pos[0] + left[0] * v, pos[1] + left[1] * v, pos[2] + z)
            ramp, base = texel(mix, (round(p[0]), round(p[1]), round(p[2] * 2)), seed)
            tile.plot(p, shade(ramp, base + lit(nrm) + (0.6 if av <= wt else 0)))
            v += step_v


def sleeper_positions(path, spacing):
    n = int(path.length / spacing)
    off = (path.length - n * spacing) / 2
    return [off + spacing * (k + 0.5) for k in range(n)]


def draw_sleepers(tile, path, st, seed=0):
    """枕木：細長木條（只畫頂面＋朝相機的一道深色邊），顏色只在同一色階內小幅變化。"""
    hl, th, hs, spacing = st["sleeper"]
    hb = st["ballast"][2]
    mix = st["sleeper_mix"]
    for k, s0 in enumerate(sleeper_positions(path, spacing)):
        pos, tan, left = path.at(s0)
        ramp, base = texel(mix, (k, seed, 7))
        z0 = pos[2] + hb + hs
        b = -hl
        while b <= hl + 1e-6:
            for a in (-th / 2, 0.0, th / 2):
                p = (pos[0] + tan[0] * a + left[0] * b, pos[1] + tan[1] * a + left[1] * b, z0 + tan[2] * a)
                tile.plot(p, shade(ramp, base + (1 if abs(b) < hl - 0.4 else 0)))
            for sgn in (-1, 1):                                 # 朝相機那一側的邊
                nrm = (tan[0] * sgn, tan[1] * sgn, 0.0)
                if iso.facing_camera(nrm):
                    a = th / 2 * sgn
                    p = (pos[0] + tan[0] * a + left[0] * b, pos[1] + tan[1] * a + left[1] * b, z0 - hs * 0.8 + tan[2] * a)
                    tile.plot(p, shade(ramp, base - 1))
            b += 0.25


def draw_bar(tile, path, offset, z_bottom, z_top, half_w, top_col, side_col, step=0.2, bias=0.0, every=None):
    """沿中心線、側移 offset 的長條（鋼軌／導電軌／齒條）。top_col/side_col 可為 callable(s) → 色號。"""
    for s, pos, tan, left in path.samples[::max(1, int(step / 0.25))] if step >= 0.25 else path.samples:
        if every and not every(s):
            continue
        cx, cy = pos[0] + left[0] * offset, pos[1] + left[1] * offset
        tc = top_col(s) if callable(top_col) else top_col
        for w in (-half_w, 0.0, half_w):
            tile.plot((cx + left[0] * w, cy + left[1] * w, pos[2] + z_top), tc, bias)
        for sgn in (-1, 1):
            nrm = (left[0] * sgn, left[1] * sgn, 0.0)
            if not iso.facing_camera(nrm):
                continue
            sc = side_col(s, nrm) if callable(side_col) else side_col
            z = z_bottom
            while z < z_top - 1e-6:
                tile.plot((cx + left[0] * half_w * sgn, cy + left[1] * half_w * sgn, pos[2] + z), sc, bias)
                z += 0.35


def draw_rails(tile, path, st, z_base=None):
    hb = st["ballast"][2]
    hs = st["sleeper"][2]
    z0 = (hb + hs) if z_base is None else z_base
    g = st["gauge"]
    for off in (-g, g):
        draw_bar(tile, path, off, z0, z0 + st["rail_h"], 0.2, GREY + 6,
                 lambda s, n: shade(GREY, 3 + lit(n) * 0.5), bias=0.3)


# ---------------------------------------------------------------- 物件類型
def track_image(name, idx, style, st):
    """track style 0 的一張影像。回傳 (w, h, x, y, px) 或 None（不認得的名稱）。"""
    m = NAME_RE.match(name)
    if not m:
        return None
    piece, seq, layer, d = m.group(1), int(m.group(2)), m.group(3), DIRS[m.group(4)]
    tid = TRACK_IDS.index(piece)
    tiles = GEOM["track"]["pieces"][str(tid)]
    _i, x, y, z = tiles[seq]
    tx, ty = rot(x, y, d)
    path = Path3(GEOM["track"]["paths"][str(tid)][d])
    tile = Tile(tx, ty, z)
    seed = tid * 31 + seq * 7 + d
    if layer in (None, "Ballast"):
        draw_ballast(tile, path, st, seed)
    if layer in (None, "Sleeper"):
        draw_sleepers(tile, path, st, seed)
    if layer in (None, "Rail"):
        draw_rails(tile, path, st)
    return tile.c.render()


def extra_image(name, style, track_st):
    """trackExtra style 0 的一張影像（第三軌／齒軌），疊在軌道上。"""
    m = NAME_RE.match(name)
    if not m:
        return None
    piece, seq, d = m.group(1), int(m.group(2)), DIRS[m.group(4)]
    tid = TRACK_IDS.index(piece)
    _i, x, y, z = GEOM["track"]["pieces"][str(tid)][seq]
    tx, ty = rot(x, y, d)
    path = Path3(GEOM["track"]["paths"][str(tid)][d])
    tile = Tile(tx, ty, z)
    z0 = 1.8                                                  # 枕木頂面附近（標準軌道碴 + 枕木）
    if style == "thirdrail":
        off = -7.2                                            # 行進方向右側
        for s0 in sleeper_positions(path, 6.0):               # 絕緣座（每隔幾根枕木一個）
            pos, tan, left = path.at(s0)
            c = (pos[0] + left[0] * off, pos[1] + left[1] * off, pos[2] + z0)
            for h in (0.0, 0.4, 0.8):
                tile.plot((c[0], c[1], c[2] + h), YELLOW + 6 if h < 0.8 else YELLOW + 8)
                tile.plot((c[0] + tan[0] * 0.4, c[1] + tan[1] * 0.4, c[2] + h), YELLOW + 5)
        draw_bar(tile, path, off, z0 + 0.9, z0 + 1.6, 0.3, GREY + 8,
                 lambda s, n: shade(GREY, 4 + lit(n) * 0.6), bias=0.4)
    else:                                                     # rack：中間雙片齒條
        for off in (-0.45, 0.45):
            draw_bar(tile, path, off, z0, z0 + 0.9, 0.15,
                     lambda s: GREY + (5 if int(s / 0.6) % 2 else 1),
                     lambda s, n: shade(GREY, 1 + lit(n) * 0.4), bias=0.5)
    return tile.c.render()


def road_image(name, style, st):
    m = NAME_RE.match(name)
    if not m:
        return None
    piece, seq, layer, d = m.group(1), int(m.group(2)), m.group(3), DIRS[m.group(4)]
    rid = ROAD_IDS.index(piece)
    _i, x, y, z = GEOM["road"]["pieces"][str(rid)][seq]
    tx, ty = rot(x, y, d)
    lanes = [Path3(p) for p in GEOM["road"]["paths"][str(rid)][d]]
    tile = Tile(tx, ty, z)
    seed = rid * 31 + seq * 7 + d
    if layer in (None, "Ballast"):                            # 鋪石路面：兩條車道各自的帶狀，內側較寬以蓋住中線
        for k, lane in enumerate(lanes):
            draw_pavement(tile, lane, st, seed + k)
    if layer in (None, "Sleeper"):                            # 嵌入路面的軌道沒有外露枕木：軌間鋪較深的石塊
        for lane in lanes:
            for s, pos, tan, left in lane.samples:
                for v in (-1.8, -0.9, 0.0, 0.9, 1.8):
                    p = (pos[0] + left[0] * v, pos[1] + left[1] * v, pos[2])
                    key = (math.floor(p[0] / 1.6), math.floor(p[1] / 1.6), 9)
                    ramp, base = texel(st["ballast_mix"], key, seed)
                    tile.plot(p, shade(ramp, base - 1), bias=-0.1)
    if layer in (None, "Rail"):                               # 槽型軌：深色軌槽＋亮色軌頂
        for lane in lanes:
            for off in (-st["gauge"], st["gauge"]):
                out = 1 if off > 0 else -1                    # 軌槽在內側、軌頂在外側，相隔 1 單位才不會擠在同一像素
                draw_bar(tile, lane, off - 0.5 * out, 0.0, 0.1, 0.0, GREY + 1, GREY + 1, bias=0.25)
                draw_bar(tile, lane, off + 0.5 * out, 0.0, 0.12, 0.0, GREY + 8, GREY + 6, bias=0.3)
    return tile.c.render()


def draw_pavement(tile, lane, st, seed):
    mix = st["ballast_mix"]
    for s, pos, tan, left in lane.samples:
        v = -8.6
        while v <= 6.6:
            p = (pos[0] + left[0] * v, pos[1] + left[1] * v, pos[2])
            # 石塊：每 1.6 × 1.1 單位一塊，接縫較暗
            key = (math.floor(p[0] / 1.6), math.floor(p[1] / 1.6), round(p[2]))
            ramp, base = texel(mix, key, seed)
            joint = (p[0] % 1.6 < 0.3) or (p[1] % 1.6 < 0.3)
            nrm = (-tan[2] * tan[0], -tan[2] * tan[1], 1.0)
            tile.plot(p, shade(ramp, base + lit(nrm) - (1.5 if joint else 0)), bias=-0.2)
            v += 0.3
        _ = seed


# ---------------------------------------------------------------- UI 圖示
def icon_track(frame, frames, st, kind="narrow", primary=True):
    """工具列動畫圖示：一小段軌道放在公司色底板上，隨影格旋轉。"""
    c = iso.Canvas()
    ang = 2 * math.pi * frame / frames
    R = 11.0
    # 底板（公司主色）
    if primary:
        for i in range(-24, 25):
            for j in range(-24, 25):
                u, v = i * 0.5, j * 0.5
                if abs(u) <= R and abs(v) <= R:
                    edge = abs(u) > R - 0.6 or abs(v) > R - 0.6
                    c.plot(u, v, -1.0, PRIMARY[5 if edge else 8])
    pts = []
    for k in range(-16, 17):
        x, y = k * 0.75, 0.0
        cx, cy = x * math.cos(ang) - y * math.sin(ang), x * math.sin(ang) + y * math.cos(ang)
        pts.append((cx, cy, 0.0))
    path = Path3(pts, extend=0.0)
    tile = Tile(0, 0, 0, clip=False)
    tile.c = c
    if kind == "tram":
        for lane_off in (-5.0, 5.0):
            lane = Path3([(p[0] - math.sin(ang) * lane_off, p[1] + math.cos(ang) * lane_off, 0.0) for p in pts], extend=0.0)
            draw_pavement(tile, lane, dict(st, ballast_mix=st["ballast_mix"]), 3)
        for lane_off in (-5.0, 5.0):
            lane = Path3([(p[0] - math.sin(ang) * lane_off, p[1] + math.cos(ang) * lane_off, 0.0) for p in pts], extend=0.0)
            for off in (-2.2, 2.2):
                draw_bar(tile, lane, off, 0.0, 0.3, 0.25, GREY + 10, GREY + 6, bias=0.3)
    else:
        sst = dict(st, ballast=(4.6, 7.0, 1.0), sleeper=(3.6, 1.0, 0.5, 3.2), gauge=2.5)
        draw_ballast(tile, path, sst, 5)
        draw_sleepers(tile, path, sst, 5)
        draw_rails(tile, path, sst)
    return c.render()


def icon_pickup(st, up: bool, kind="narrow"):
    """拿起／放下車輛的按鈕圖示：一小段軌道＋黃色箭頭（上 = 拿起，下 = 放下）。"""
    w, h, x0, y0, px = icon_track(0, 16, st, kind, primary=False)
    W, H = 20, 19
    out = bytearray(W * H)
    ox, oy = (W - w) // 2, H - h - 1
    for j in range(h):
        for i in range(w):
            v = px[j * w + i]
            if v and 0 <= j + oy < H and 0 <= i + ox < W:
                out[(j + oy) * W + i + ox] = v
    ax = W // 2
    rows = list(range(1, 11))
    for k, r in enumerate(rows):                              # 箭頭：三角形頭 + 方形桿
        head = k < 5 if up else k >= 5
        half = (k if up else 9 - k) if head else 1
        for i in range(ax - half - 1, ax + half + 1):
            if 0 <= i < W:
                out[r * W + i] = YELLOW + (9 if i < ax else 7)
        if head:
            out[r * W + max(0, ax - half - 2)] = GREY + 1
            out[r * W + min(W - 1, ax + half + 1)] = GREY + 1
    return W, H, 2, 2, bytes(out)


def icon_spark(frame):
    """第三軌分頁圖示（8 格）：一小段導電軌＋閃爍的電弧。"""
    W = H = 16
    out = bytearray(W * H)
    for i in range(1, 15):                                    # 導電軌（斜放）
        j = 11 - i // 2
        out[j * W + i] = GREY + 9
        out[(j + 1) * W + i] = GREY + 5
        if i % 5 == 2:
            out[(j + 2) * W + i] = YELLOW + 6
    rng = random.Random(frame * 7 + 1)
    x, y = 8, 7
    for _ in range(6 + frame % 3):                            # 鋸齒電弧
        x = max(1, min(14, x + rng.choice((-1, 1))))
        y = max(0, y - 1)
        out[y * W + x] = (YELLOW + 10) if (frame + y) % 2 else (0x82 + 10)
    if frame % 2 == 0:
        out[(y) * W + x] = GREY + 11
    return W, H, 0, 0, bytes(out)


def icon_cog(frame):
    """齒軌分頁圖示（8 格）：轉動的齒輪。"""
    W = H = 16
    out = bytearray(W * H)
    cx = cy = 7.5
    teeth = 8
    for j in range(H):
        for i in range(W):
            dx, dy = i - cx, j - cy
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx) - frame * (2 * math.pi / teeth) / 8
            tooth = (math.cos(a * teeth) > 0.2)
            rim = 5.2 + (1.8 if tooth else 0.0)
            if r <= rim:
                if r < 1.6:
                    continue                                  # 軸孔
                light = 9 if (dx + dy) < 0 else 6
                if r < 3.2:
                    light -= 2
                out[j * W + i] = GREY + light
    return W, H, 12 - 12, 8 - 8, bytes(out)


# ---------------------------------------------------------------- 主程式
def build(style, template):
    entries = common.template_entries(template)
    n = len(entries)
    frames: list = [None] * n
    names = {}
    if style == "narrow":
        st = STYLES["narrow"]
        for k, v in GEOM["images"]["track"]["Style0"].items():
            names[v] = k
        for i in range(n):
            if i < 16:
                frames[i] = icon_track(i, 16, st)
            elif i in (16, 17):
                frames[i] = icon_pickup(st, up=(i == 16))
            elif i in names:
                frames[i] = track_image(names[i], i, style, st)
    elif style in ("thirdrail", "rack"):
        for k, v in GEOM["images"]["trackExtra"]["Style0"].items():
            names[v + 8] = k
        for i in range(n):
            if i < 8:
                frames[i] = icon_spark(i) if style == "thirdrail" else icon_cog(i)
            elif i in names:
                frames[i] = extra_image(names[i], style, None)
    elif style == "tram":
        st = STYLES["tram"]
        for k, v in GEOM["images"]["road"]["Style1"].items():
            names[v] = k
        for i in range(n):
            if i < 32:
                frames[i] = icon_track(i, 32, st, kind="tram")
            elif i in (32, 33):
                frames[i] = icon_pickup(st, up=(i == 32), kind="tram")
            elif i in names:
                frames[i] = road_image(names[i], style, st)
    else:
        raise SystemExit(f"未知樣式 {style}")
    unused = 0
    for i in range(n):
        if frames[i] is None:
            frames[i] = (1, 1, 0, 0, bytes(1))
            unused += 1
    return frames, unused


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", required=True, choices=["narrow", "thirdrail", "rack", "tram"])
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--only", default="", help="只輸出這些 index（除錯用，其餘為 1×1）")
    args = ap.parse_args()
    frames, unused = build(args.style, args.template)
    common.write_sprites(args.out, frames)
    print(f"{args.style}：{len(frames)} 張（{unused} 張用不到、輸出 1×1）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
