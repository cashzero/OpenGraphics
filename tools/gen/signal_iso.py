#!/usr/bin/env python3
"""號誌（trackSignal 物件，M3）：以 tools/gen/iso.py 依實際 3D 幾何畫出每個視角。

  python3 tools/gen/signal_iso.py --template <模板.DAT> --style <樣式> -o <資料夾>

樣式：uq（上象限臂板）、lq（下象限臂板）、uqd／lqd（主臂 + 預告臂）、us3（三位式 90° 臂板）、
disc（圓頭臂板）、light（直立燈號，2–4 燈，依格數決定）、twin（左右兩燈）、search（探照燈式單燈）。

影像（OpenLoco Paint/PaintSignal.cpp）：image + frame × 8 + 視角 k（k = ((軌道旋轉 & 3) << 1) | 斜向）。
有 hasLights 旗標時，80／88／96／104 起各 8 張為紅燈、紅燈 2、綠燈、綠燈 2 的光暈（疊在號誌上）。
frame = min(狀態 × 3, 格數 - 1)：0 = 停止、3 = 注意、6 = 第二注意（或通行）、9 = 通行。

幾何（由 PaintSignal.cpp 的位移表推得）：視角 k 的 d = k >> 1，左側號誌「朝外」方向
d = 0..3 依序為 +y、+x、-y、-x，斜向取 d 與 d+1 的平均；右側號誌（無 isLeft）朝外方向相反。
號誌正面朝向迎面駛來的列車：facing = (朝外左.y, -朝外左.x)。臂板由柱子伸向朝外方向。
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

import common
import iso

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

BLACK, GREY_RAMP, RED, YELLOW, GREEN, WHITE = 0x0A, 0x0A, 0xA6, 0x2E, 0x5E, 0x0A + 11
OUT_LEFT = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0)]


def norm(v):
    L = math.hypot(*v)
    return (v[0] / L, v[1] / L)


def view(k: int, is_left: bool):
    d, diag = k >> 1, k & 1
    o = OUT_LEFT[d]
    if diag:
        o = norm((o[0] + OUT_LEFT[(d + 1) % 4][0], o[1] + OUT_LEFT[(d + 1) % 4][1]))
    facing = (o[1], -o[0])
    out = o if is_left else (-o[0], -o[1])
    return out, facing


def post(c, H, ramp=GREY_RAMP, base=7, r=0.45):
    c.box((-r, -r, 0), (r, r, H), ramp, base)
    c.box((-0.9, -0.9, 0), (0.9, 0.9, 0.6), BLACK, 3)          # 基座
    c.box((-0.6, -0.6, H), (0.6, 0.6, H + 0.6), BLACK, 3)      # 柱頂


def arm(c, out, facing, z, angle, length, kind):
    """臂板：樞軸在柱前方，沿 out 方向伸出，往上轉 angle（弧度，負值 = 往下）。"""
    front = iso.facing_camera(facing)
    piv = (facing[0] * 0.7, facing[1] * 0.7, z)
    d = (out[0] * math.cos(angle), out[1] * math.cos(angle), math.sin(angle))
    p = (-out[0] * math.sin(angle), -out[1] * math.sin(angle), math.cos(angle))   # 板面內垂直方向
    width = 1.3

    def colour(s, t):
        if kind == "home":
            if front:
                return WHITE if 0.72 < s < 0.84 else RED + 8
            return BLACK + 2 if 0.72 < s < 0.84 else WHITE - 1
        if kind == "distant":
            if front:
                chevron = abs((s - 0.85) * 4 - abs(t - 0.5)) < 0.25 and s > 0.7
                return BLACK + 1 if chevron else YELLOW + 9
            return WHITE - 1
        if kind == "disc":
            if s > 0.78:                                        # 圓頭
                return WHITE if front else WHITE - 2
            return RED + 8 if front and int(s * 6) % 2 == 0 else (WHITE - 1 if front else WHITE - 2)
        return RED + 8
    origin = (piv[0] - p[0] * width / 2, piv[1] - p[1] * width / 2, piv[2] - p[2] * width / 2)
    if kind == "disc":
        length *= 0.85
    c.plate(origin, (d[0] * length, d[1] * length, d[2] * length), (p[0] * width, p[1] * width, p[2] * width), colour)
    if kind == "disc":                                          # 臂端的圓牌
        cx, cy, cz = (piv[0] + d[0] * length, piv[1] + d[1] * length, piv[2] + d[2] * length)
        for a in range(0, 360, 20):
            for r in (0.4, 0.9, 1.3):
                q = (cx + p[0] * math.sin(math.radians(a)) * r + d[0] * math.cos(math.radians(a)) * r,
                     cy + p[1] * math.sin(math.radians(a)) * r + d[1] * math.cos(math.radians(a)) * r,
                     cz + p[2] * math.sin(math.radians(a)) * r + d[2] * math.cos(math.radians(a)) * r)
                c.plot(*q, (RED + 8 if r > 1 else WHITE) if front else WHITE - 2)
    # 燈（眼鏡框）：在樞軸旁
    lamp = (piv[0] + facing[0] * 0.2, piv[1] + facing[1] * 0.2, z - 1.4)
    c.dot(lamp, (RED + 9 if angle == 0 else GREEN + 9) if front else BLACK + 1)


def semaphore(k, frame, frames, style, is_left):
    out, facing = view(k, is_left)
    c = iso.Canvas()
    H = 24
    post(c, H, base=8)
    if style in ("uq", "lq", "disc"):
        sgn = -1 if style == "lq" else 1
        ang = sgn * math.radians(45) * frame / max(frames - 1, 1)
        arm(c, out, facing, H - 2, ang, 6.5, "disc" if style == "disc" else "home")
    elif style in ("uqd", "lqd"):
        sgn = -1 if style == "lqd" else 1
        home = min(frame, 3) / 3
        dist = max(0, frame - 3) / 3
        arm(c, out, facing, H - 2, sgn * math.radians(45) * home, 6.5, "home")
        arm(c, out, facing, H - 9, sgn * math.radians(45) * dist, 5.5, "distant")
    elif style == "us3":
        ang = math.radians(90) * frame / max(frames - 1, 1)
        arm(c, out, facing, H - 2, ang, 7, "home")
    return c.render()


LAMP_SETS = {2: ["green", "red"], 3: ["green", "yellow", "red"], 4: ["yellow", "green", "yellow", "red"]}
LAMP_COL = {"red": RED + 9, "yellow": YELLOW + 10, "green": GREEN + 10}


def lit_lamps(aspects: int, frame: int, frames: int):
    """回傳這一格點亮的燈（燈號索引集合）。只有 3 的倍數（或最後一格）是穩定狀態，其餘為切換中（全暗）。"""
    if frame % 3 and frame != frames - 1:
        return set()
    state = frame // 3 if frame != frames - 1 else (frames - 1 + 2) // 3
    lamps = LAMP_SETS[aspects]
    if state == 0:
        return {lamps.index("red")}
    if aspects == 2:
        return {lamps.index("green")}
    if aspects == 3:
        return {lamps.index("yellow")} if state == 1 else {lamps.index("green")}
    # 4 燈（上黃、綠、下黃、紅）：1 = 下黃、2 = 雙黃、3 = 綠
    return {2} if state == 1 else ({0, 2} if state == 2 else {1})


def head_geometry(k, is_left, style, aspects):
    out, facing = view(k, is_left)
    side = (-facing[1], facing[0])
    if style == "twin":
        lamps = [(side[0] * s, side[1] * s, 0.0) for s in (-1.4, 1.4)]
        size = (5.0, 3.0)
    elif style == "search":
        lamps = [(0, 0, 0.0)]
        size = (4.0, 4.0)
    else:
        lamps = [(0, 0, -2.4 * i) for i in range(aspects)]
        size = (3.2, 2.4 * aspects + 0.8)
    return out, facing, side, lamps, size


def colour_light(k, frame, frames, style, is_left, overlay=None):
    aspects = {4: 2, 7: 3, 10: 4}.get(frames, 3)
    if style in ("twin",):
        aspects = 2
    out, facing, side, lamps, (hw, hh) = head_geometry(k, is_left, style, aspects)
    front = iso.facing_camera(facing)
    c = iso.Canvas()
    H = 18 if style != "search" else 22
    top = H + hh
    # 頭部中心：在柱子朝外側一點（像懸臂），正面朝 facing
    cx, cy = out[0] * 0.6, out[1] * 0.6
    if overlay is None:
        post(c, H, base=7)
        # 燈頭：以 plate 畫正面與背面（厚度 0.8）
        for depth, col in ((0.4, BLACK + 2), (-0.4, BLACK + 3)):
            o = (cx + facing[0] * depth - side[0] * hw / 2, cy + facing[1] * depth - side[1] * hw / 2, H + 0.3)
            if style == "search":
                def disc(s, t, col=col):
                    return col if (s - 0.5) ** 2 + (t - 0.5) ** 2 <= 0.25 else None
                c.plate(o, (side[0] * hw, side[1] * hw, 0), (0, 0, hh), disc)
            else:
                c.plate(o, (side[0] * hw, side[1] * hw, 0), (0, 0, hh), lambda s, t, col=col: col)
        if style == "light":                                    # 遮光罩（白邊背板）
            o = (cx - facing[0] * 0.5 - side[0] * (hw / 2 + 0.6), cy - facing[1] * 0.5 - side[1] * (hw / 2 + 0.6), H)
            c.plate(o, (side[0] * (hw + 1.2), side[1] * (hw + 1.2), 0), (0, 0, hh + 0.6),
                    lambda s, t: WHITE - 1 if (s < 0.12 or s > 0.88 or t > 0.93) else BLACK + 1)
    lit = lit_lamps(aspects, frame, frames) if overlay is None else None
    if not front:
        return c.render() if overlay is None else (1, 1, 0, 0, bytes(1))
    names = LAMP_SETS[aspects] if style != "search" else ["red"]
    for i, (lx, ly, lz) in enumerate(lamps):
        p = (cx + facing[0] * 0.55 + lx, cy + facing[1] * 0.55 + ly, top - 0.8 + lz if style != "search" else H + hh / 2 + 0.3)
        if overlay is None:
            if style == "search":
                state = frame // 3 if frame % 3 == 0 or frame == frames - 1 else -1
                col = {0: RED + 9, 1: YELLOW + 10, 2: YELLOW + 10, 3: GREEN + 10}.get(state, BLACK + 4)
            else:
                col = LAMP_COL[names[i]] if i in lit else BLACK + 4
            for dx, dz in ((0, 0), (0.7, 0), (0, -0.7), (0.7, -0.7)):     # 2×2 px 的燈
                c.dot((p[0] + side[0] * dx, p[1] + side[1] * dx, p[2] + dz), col - (0 if (dx, dz) == (0, 0) else 1))
        else:
            want = overlay[0]
            if style != "search" and names[i] != want:
                continue
            col = LAMP_COL[want]
            for dx, dz in ((0, 0), (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6)):
                c.dot((p[0] + side[0] * dx, p[1] + side[1] * dx, p[2] + dz), col - (0 if (dx, dz) == (0, 0) else 2), bias=1.0)
            if style == "search":
                break
            if overlay[1] == 1:                                 # 「2」號光暈：第二盞同色燈（4 燈式的雙黃以外，畫成同一盞的較大光暈）
                for dx, dz in ((0.6, 0.6), (-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6)):
                    c.dot((p[0] + side[0] * dx, p[1] + side[1] * dx, p[2] + dz), col - 3, bias=1.0)
    return c.render()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--style", required=True, choices=["uq", "lq", "uqd", "lqd", "us3", "disc", "light", "twin", "search"])
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    obj = dat.read_dat(args.template)
    d = obj.data
    flags = struct.unpack_from("<H", d, 2)[0]
    frames = d[5]
    is_left, has_lights = bool(flags & 1), bool(flags & 2)
    n = len(obj.image_table().entries)
    out = []
    for i in range(n):
        f, k = divmod(i, 8)
        if args.style in ("light", "twin", "search"):
            if has_lights and i >= 80:
                kind = (i - 80) // 8                            # 0 紅、1 紅2、2 綠、3 綠2
                ov = ("red" if kind < 2 else "green", kind % 2)
                out.append(colour_light(k, 0, frames, args.style, is_left, overlay=ov))
            elif f < frames:
                out.append(colour_light(k, f, frames, args.style, is_left))
            else:
                out.append((1, 1, 0, 0, bytes(1)))             # 未使用的格
        else:
            out.append(semaphore(k, min(f, frames - 1), frames, args.style, is_left))
    common.write_sprites(args.output, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
