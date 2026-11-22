#!/usr/bin/env python3
"""平交道（levelCrossing 物件，M3）：以 tools/gen/iso.py 依 3D 幾何畫出 4 個角落 × 2 種道路方向 × 每一格動畫。

  python3 tools/gen/lcross_iso.py --template <模板.DAT> --style barrier|lights|gates -o <資料夾>

影像（OpenLoco Paint/PaintRoad.cpp `paintLevelCrossing`）：image + (旋轉 & 1) × 4 + frame × 8 + 角落 k。
角落 k 的位置（圖塊內世界座標）：0 = (2, 2)、1 = (2, 30)、2 = (30, 2)、3 = (30, 30)；sprite 原點是圖塊原點。
frame：0 = 開放、1..transition = 關閉中、transition+1.. = 關閉後的循環動畫（閃燈），共 1 + transition + closed 格。
道路方向：旋轉偶數時道路沿 x 軸（柵欄沿 y 軸橫過道路），奇數時相反（由 vanilla 的 sprite 範圍量得）。

樣式：
- barrier：紅白條紋的半柵欄（升起 → 放下）+ 黑底白框的雙閃燈。
- lights：只有雙閃燈與白底紅邊 X 牌。
- gates：白色木造平開柵門（中央紅色圓牌），開放時橫擋鐵路、關閉時轉 90° 擋住道路。
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import common
import iso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

CORNERS = [(2, 2), (2, 30), (30, 2), (30, 30)]
BLACK, RED, WHITE, YELLOW = 0x0A, 0xA6, 0x0A + 11, 0x2E


def toward_centre(cx, cy):
    return (1 if cx < 16 else -1), (1 if cy < 16 else -1)


def lamp_pair(c, cx, cy, z, across, lit):
    """黑色背板上左右兩個紅燈；lit = 0 全暗、1 左亮、2 右亮。背板面向道路來車（法向量 = 道路方向朝外）。"""
    ux, uy = across                                       # 背板的水平方向（沿柵欄方向）
    for s in (-1.2, 1.2):
        p = (cx + ux * s, cy + uy * s, z)
        on = (s < 0 and lit == 1) or (s > 0 and lit == 2)
        c.box((p[0] - 0.7, p[1] - 0.7, z - 0.8), (p[0] + 0.7, p[1] + 0.7, z + 0.8), BLACK, 2)
        col = RED + 10 if on else RED + 3
        c.dot((p[0] + 0.7, p[1] + 0.7, z), col, bias=0.8)
        c.dot((p[0] + 0.7, p[1] + 0.7, z + 0.6), col - (1 if on else 0), bias=0.8)
    c.box((cx - 0.3, cy - 0.3, z - 0.3), (cx + 0.3, cy + 0.3, z + 0.3), BLACK, 4)   # 橫桿


def crossbuck(c, cx, cy, z, across):
    ux, uy = across
    for sgn in (-1, 1):
        for t in range(-6, 7):
            s = t / 6 * 2.2
            p = (cx + ux * s, cy + uy * s, z + sgn * s * 0.55)
            col = RED + 8 if abs(t) > 4 else WHITE
            c.plot(*p, col)
            c.plot(p[0], p[1], p[2] + 0.4, col)


def corner(style, k, parity, frame, trans, closed_cnt):
    cx, cy = CORNERS[k]
    tx, ty = toward_centre(cx, cy)
    c = iso.Canvas()
    # 柵欄方向：橫過道路
    across = (0, ty) if parity == 0 else (tx, 0)
    along = (tx, 0) if parity == 0 else (0, ty)          # 沿道路邊（擋鐵路的方向）
    closed_phase = frame > trans
    if style in ("barrier", "lights"):
        H = 11
        c.box((cx - 0.5, cy - 0.5, 0), (cx + 0.5, cy + 0.5, H), BLACK, 8)          # 灰白柱
        c.box((cx - 1, cy - 1, 0), (cx + 1, cy + 1, 0.8), BLACK, 3)
        lit = 0
        if frame > 0:
            lit = 1 + (frame % 2)
        lamp_pair(c, cx, cy, H - 3.5, across, lit)
        if style == "lights":
            crossbuck(c, cx, cy, H + 1.2, across)
        else:
            # 柵欄臂：樞軸在柱上 z = 4，開放時幾乎垂直（85°），關閉時水平
            t = min(frame, trans) / trans if trans else (1.0 if frame else 0.0)
            ang = math.radians(85 * (1 - t))
            L = 13.0
            piv = (cx + along[0] * 0.8, cy + along[1] * 0.8, 4.0)
            d = (across[0] * math.cos(ang), across[1] * math.cos(ang), math.sin(ang))
            c.segment(piv, (piv[0] + d[0] * L, piv[1] + d[1] * L, piv[2] + d[2] * L),
                      lambda s: RED + 8 if int(s * 7) % 2 else WHITE, r=0.35)
            c.box((cx - 0.8, cy - 0.8, 2.5), (cx + 0.8, cy + 0.8, 5), BLACK, 5)     # 機箱
            if closed_phase or t >= 1:                                               # 臂端的紅燈
                tip = (piv[0] + d[0] * L, piv[1] + d[1] * L, piv[2] + d[2] * L + 0.6)
                c.dot(tip, RED + 10 if lit else RED + 4)
    else:                                                  # gates
        H = 9
        c.box((cx - 0.7, cy - 0.7, 0), (cx + 0.7, cy + 0.7, H), BLACK, 9)
        c.box((cx - 0.9, cy - 0.9, H), (cx + 0.9, cy + 0.9, H + 0.6), BLACK, 6)
        t = min(frame, trans) / trans if trans else (1.0 if frame else 0.0)
        # 從 along（擋鐵路）轉到 across（擋道路），經過圖塊內側
        a0 = math.atan2(along[1], along[0])
        a1 = math.atan2(across[1], across[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        a = a0 + da * t
        d = (math.cos(a), math.sin(a))
        L = 13.5
        o = (cx + d[0] * 0.8, cy + d[1] * 0.8, 1.2)

        def gate(s, u):
            # 外框 + 斜撐 + 中央紅色圓牌
            if s < 0.04 or s > 0.96 or u < 0.12 or u > 0.88:
                return WHITE
            if abs(u - (0.12 + 0.76 * s)) < 0.07:
                return WHITE - 1
            if (s - 0.55) ** 2 * 9 + (u - 0.5) ** 2 < 0.06:
                return RED + 8
            if abs(u - 0.5) < 0.06:
                return WHITE - 1
            return None
        c.plate(o, (d[0] * L, d[1] * L, 0), (0, 0, 6.0), gate)
    return c.render()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", required=True, choices=["barrier", "lights", "gates"])
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    obj = dat.read_dat(args.template)
    d = obj.data
    closed_cnt, trans = d[8], d[9]
    n = len(obj.image_table().entries)
    if n != (1 + trans + closed_cnt) * 8:
        raise SystemExit(f"影像數 {n} 與格數（1 + {trans} + {closed_cnt}）× 8 不符")
    out = []
    for i in range(n):
        frame, r = divmod(i, 8)
        parity, k = divmod(r, 4)
        out.append(corner(args.style, k, parity, frame, trans, closed_cnt))
    common.write_sprites(args.output, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
