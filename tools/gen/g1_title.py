#!/usr/bin/env python3
"""g1 標題畫面主選單（ROADMAP M4）：地球旋轉／建造動畫、星光、磁片、學士帽。輸出 base/g1/title/（PNG + sprites.json）。

  .venv/bin/python tools/gen/g1_title.py [--sheet build/preview/g1_title.png]

主選單（OpenLoco Ui/Windows/TitleMenu.cpp）：4 顆 74×74 按鈕，各畫一個地球（45×44，偏移 (13, 17)）＋疊圖：
  新遊戲：地球 + title_menu_sparkle；載入：地球 + title_menu_save；教學：地球 + title_menu_lesson_l（依語言另有 a、p）；
  情境編輯器：title_menu_globe_construct_*（沒有滑鼠懸停時固定第 24 格）。滑鼠懸停時地球依 32 格動畫轉動。
地球是程序產生的星球（3D 雜訊大陸、極地冰帽、蘭伯特光照），不是真實地圖。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "title"
PAL = dat.load_palette()
ALLOWED = [i for i in range(10, 246) if not (0xCA <= i <= 0xD5) and i != 0xF5 and not (0xE3 <= i <= 0xEF)]
_cache: dict = {}


def q(rgb) -> int:
    """RGB → 最接近的調色盤 index（排除公司色、動畫色）。"""
    key = tuple(int(max(0, min(255, round(v)))) // 4 for v in rgb)
    if key not in _cache:
        r, g, b = (k * 4 + 2 for k in key)
        _cache[key] = min(ALLOWED, key=lambda i: (PAL[i][0] - r) ** 2 * 3 + (PAL[i][1] - g) ** 2 * 4 + (PAL[i][2] - b) ** 2 * 2)
    return _cache[key]


# ---------------------------------------------------------------- 3D 雜訊
def _hash(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def noise3(x, y, z, seed):
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    sx, sy, sz = (t * t * (3 - 2 * t) for t in (fx, fy, fz))
    v = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (sx if dx else 1 - sx) * (sy if dy else 1 - sy) * (sz if dz else 1 - sz)
                v += w * _hash(ix + dx, iy + dy, iz + dz, seed)
    return v


def fbm(p, seed, octaves=4):
    s, a, f = 0.0, 0.5, 1.6
    for o in range(octaves):
        s += a * noise3(p[0] * f, p[1] * f, p[2] * f, seed + o)
        a *= 0.5
        f *= 2.1
    return s


def rot_y(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


def rot_z(p, a):
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2])


LIGHT = (-0.55, -0.6, 0.6)


def globe_pixels(w, h, cx, cy, R, spin, seed=7):
    """回傳 {(x, y): 色號}：地球（畫面座標 y 向下，z 朝觀看者）。"""
    L = math.sqrt(sum(c * c for c in LIGHT))
    Lx, Ly, Lz = (c / L for c in LIGHT)
    out = {}
    for y in range(h):
        for x in range(w):
            nx, ny = (x + 0.5 - cx) / R, (y + 0.5 - cy) / R
            d = nx * nx + ny * ny
            if d > 1.0:
                continue
            nz = math.sqrt(1 - d)
            p = rot_z((nx, ny, nz), math.radians(-18))          # 地軸傾斜
            p = rot_y(p, spin)
            lat = math.asin(max(-1, min(1, -p[1])))
            n = fbm((p[0] * 1.7, p[1] * 1.7, p[2] * 1.7), seed)
            lam = max(0.0, nx * Lx + ny * Ly + nz * Lz)
            shade = 0.28 + 0.85 * lam
            if abs(lat) > math.radians(68) + (n - 0.5) * 0.25:
                rgb = (235, 240, 245)
            elif n > 0.53:
                hgt = (n - 0.53) / 0.2
                if abs(lat) < math.radians(22) and hgt < 0.5:
                    rgb = (170, 150, 80)                         # 赤道附近的乾燥地
                elif hgt > 0.7:
                    rgb = (120, 100, 70)                         # 山地
                else:
                    rgb = (70, 140, 55)
            else:
                depth = (0.53 - n) / 0.25
                rgb = (30, 80 - 30 * depth, 170 - 40 * depth)
                spec = max(0.0, (nx * Lx + ny * Ly + (nz + 1) * Lz) / math.sqrt(2 + 2 * Lz)) ** 24
                rgb = tuple(c + 120 * spec for c in rgb)
            rgb = tuple(c * shade for c in rgb)
            out[(x, y)] = q(rgb)
            if d > 0.86:                                         # 邊緣的大氣光暈
                out[(x, y)] = q(tuple(0.6 * c + 0.4 * t for c, t in zip(rgb, (90, 140, 220))))
    # 外框（深色一圈），讓地球在任何按鈕色上都清楚
    for (x, y) in list(out):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in out and 0 <= x + dx < w and 0 <= y + dy < h:
                out.setdefault(("o", x + dx, y + dy), None)
    edge = {(k[1], k[2]) for k in out if k[0] == "o"}
    res = {k: v for k, v in out.items() if k[0] != "o"}
    for k in edge:
        res[k] = 0x0A + 1
    return res


def to_frame(pix, w, h, x, y):
    px = bytearray(w * h)
    for (i, j), v in pix.items():
        if 0 <= i < w and 0 <= j < h:
            px[j * w + i] = v
    return (w, h, x, y, bytes(px))


# ---------------------------------------------------------------- 疊圖
def sparkle():
    """新遊戲：地球左上方的幾顆四角星光（38×46，偏移 (1, 1)）。"""
    pix = {}
    for (cx, cy, r) in ((9, 9, 7), (27, 5, 4), (5, 28, 3), (20, 17, 2)):
        for k in range(-r, r + 1):
            t = 1 - abs(k) / (r + 1)
            col = q((255, 250, 200)) if abs(k) <= r // 3 else q((255, 220, 80))
            for (x, y) in ((cx + k, cy), (cx, cy + k)):
                pix[(x, y)] = col if t > 0.2 else q((220, 170, 40))
        if r >= 4:
            for d in (1, 2):
                for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                    if d < r // 2:
                        pix[(cx + sx * d, cy + sy * d)] = q((255, 235, 140))
    return to_frame(pix, 38, 46, 1, 1)


def floppy():
    """載入遊戲：磁片（22×22，偏移 (3, 3)）。"""
    pix = {}
    for y in range(1, 19):
        for x in range(1, 19):
            pix[(x, y)] = q((50, 70, 120)) if not (x >= 15 and y <= 3) else None
    pix = {k: v for k, v in pix.items() if v is not None}
    for y in range(1, 7):                                       # 金屬擋板
        for x in range(5, 14):
            pix[(x, y)] = q((200, 205, 210)) if x not in (10, 11) or y < 2 or y > 5 else q((60, 60, 70))
    for y in range(10, 18):                                     # 標籤
        for x in range(3, 17):
            pix[(x, y)] = q((240, 235, 220)) if y not in (12, 14, 16) else q((150, 150, 170))
    edge = set()
    for (x, y) in pix:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in pix:
                edge.add((x + dx, y + dy))
    for k in edge:
        pix[k] = 0x0A
    for x in range(2, 21):                                      # 右下陰影
        pix.setdefault((x, 20), 0x0A + 2)
    for y in range(2, 21):
        pix.setdefault((20, y), 0x0A + 2)
    return to_frame(pix, 22, 22, 3, 3)


def mortarboard():
    """教學：戴在地球上的學士帽（37×41，偏移 (17, 6)；地球頂端在 y = 17）。"""
    pix = {}
    cx = 18
    for y in range(0, 9):                                       # 帽頂（等角菱形）
        half = 17 - abs(y - 4) * 4
        for x in range(cx - half, cx + half + 1):
            pix[(x, y)] = q((40, 40, 50)) if abs(y - 4) * 4 + abs(x - cx) < 16 else q((20, 20, 25))
    for y in range(6, 14):                                      # 帽身
        for x in range(cx - 8, cx + 9):
            pix.setdefault((x, y), q((30, 30, 40) if x < cx + 3 else (55, 55, 65)))
    pix[(cx, 4)] = q((255, 210, 60))
    for k in range(1, 10):                                      # 流蘇
        pix[(cx + k * 1.4 // 1, 4 + k // 3)] = q((255, 200, 40))
    for y in range(7, 16):
        pix[(cx + 13, y)] = q((255, 200, 40))
    for x in (cx + 12, cx + 13, cx + 14):
        pix[(x, 16)] = q((230, 170, 30))
        pix[(x, 17)] = q((230, 170, 30))
    pix = {(int(x), int(y)): v for (x, y), v in pix.items()}
    return to_frame(pix, 37, 41, 17, 6)


def crane_frame(f):
    """情境編輯器：地球 + 會轉動的塔式起重機（32 格；沒有懸停時顯示第 24 格）。"""
    W, H, ox, oy = 62, 66, 12, 1
    gx, gy = 23, 16 + 22                                       # 地球中心（影像座標；地球頂在 y = 17）
    pix = globe_pixels(W, H, gx, gy, 21.5, math.radians(40))
    # 起重機立在地球右上：塔身
    base = (gx + 3, gy - 21)
    top_y = 4
    yel, dark = q((240, 190, 40)), q((120, 80, 20))
    for y in range(top_y, base[1] + 1):
        pix[(base[0], y)] = yel
        pix[(base[0] + 2, y)] = yel
        if (y - top_y) % 3 == 0:
            pix[(base[0] + 1, y)] = dark
    # 吊臂（以塔頂為軸轉動；投影：水平 cos、垂直 sin × 0.5）
    a = 2 * math.pi * (f - 24) / 32 + math.radians(10)          # 第 24 格（靜止畫面）吊臂朝右側伸出
    L1, L2 = 17, 7
    tx, ty = base[0] + 1, top_y
    for k in range(-L2, L1 + 1):
        x = tx + k * math.cos(a)
        y = ty + k * math.sin(a) * 0.45
        pix[(round(x), round(y))] = yel if k > 0 else dark
    pix[(tx, ty - 1)] = q((220, 60, 40))
    # 吊鉤與正在吊起的方塊
    hx = round(tx + 13 * math.cos(a))
    hy = round(ty + 13 * math.sin(a) * 0.45)
    drop = 8 + round(4 * math.sin(a * 2))
    for y in range(hy + 1, hy + drop):
        pix[(hx, y)] = q((60, 60, 60))
    for y in range(hy + drop, hy + drop + 4):
        for x in range(hx - 2, hx + 3):
            pix[(x, y)] = q((200, 110, 60)) if x < hx + 2 else q((150, 80, 40))
    # 配重
    cx2 = round(tx - L2 * math.cos(a))
    cy2 = round(ty - L2 * math.sin(a) * 0.45)
    for y in range(cy2, cy2 + 3):
        for x in range(cx2 - 1, cx2 + 2):
            pix[(x, y)] = q((90, 90, 95))
    pix = {k: v for k, v in pix.items() if 0 <= k[0] < W and 0 <= k[1] < H}
    xs = [k[0] for k in pix]
    ys = [k[1] for k in pix]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    pix = {(x - x0, y - y0): v for (x, y), v in pix.items()}
    return to_frame(pix, w, h, ox + x0, oy + y0)


def build():
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e["i"] for e in cat["entries"] if e.get("name")}
    frames = []
    for k in range(32):
        g = globe_pixels(45, 44, 22.5, 22.0, 21.5, 2 * math.pi * k / 32)
        frames.append((ids[f"title_menu_globe_spin_{k}"], to_frame(g, 45, 44, 13, 17)))
        frames.append((ids[f"title_menu_globe_construct_{k}"], crane_frame(k)))
    frames.append((ids["title_menu_sparkle"], sparkle()))
    frames.append((ids["title_menu_save"], floppy()))
    cap = mortarboard()
    for n in ("l", "a", "p"):
        frames.append((ids[f"title_menu_lesson_{n}"], cap))
    return frames


def write(frames):
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    meta = []
    for idx, (w, h, x, y, px) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, w, h, px, bytes(255 if v else 0 for v in px), PAL)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")


def sheet(path, frames):
    """預覽：4 顆按鈕（灰色底）＋地球旋轉與建造動畫各 8 格。"""
    from PIL import Image
    fx = dict(frames)
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e["i"] for e in cat["entries"] if e.get("name")}

    def blit(im, f, x, y):
        w, h, ox, oy, px = f
        for j in range(h):
            for i in range(w):
                v = px[j * w + i]
                if v and 0 <= x + ox + i < im.width and 0 <= y + oy + j < im.height:
                    im.putpixel((x + ox + i, y + oy + j), PAL[v])
    im = Image.new("RGB", (74 * 4 + 8, 74 * 3 + 8), (40, 40, 40))
    for b in range(4):
        for j in range(74):
            for i in range(74):
                im.putpixel((b * 74 + i + 4, j + 4), (120, 130, 135) if 0 < i < 73 and 0 < j < 73 else (60, 65, 70))
    blit(im, fx[ids["title_menu_globe_spin_0"]], 4, 4)
    blit(im, fx[ids["title_menu_sparkle"]], 4, 4)
    blit(im, fx[ids["title_menu_globe_spin_0"]], 78, 4)
    blit(im, fx[ids["title_menu_save"]], 78, 4)
    blit(im, fx[ids["title_menu_globe_spin_0"]], 152, 4)
    blit(im, fx[ids["title_menu_lesson_l"]], 152, 4)
    blit(im, fx[ids["title_menu_globe_construct_24"]], 226, 4)
    for k in range(8):
        blit(im, fx[ids[f"title_menu_globe_spin_{k * 4}"]], 4 + k * 37 - 13, 80)
        blit(im, fx[ids[f"title_menu_globe_construct_{k * 4}"]], 4 + k * 37 - 13, 150)
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(REPO / "build" / "preview" / "g1_title.png"))
    args = ap.parse_args()
    frames = build()
    write(frames)
    sheet(args.sheet, frames)
    print(f"寫出 {len(frames)} 張 → {OUT}；預覽 {args.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
