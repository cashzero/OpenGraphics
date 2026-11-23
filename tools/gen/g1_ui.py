#!/usr/bin/env python3
"""g1 的 UI 圖（ROADMAP M4）：視窗元件、分頁、工具列與功能圖示、進度條、新聞紙背景等。輸出 base/g1/ui/。

  .venv/bin/python tools/gen/g1_ui.py [--sheet build/preview/g1_ui.png]

原則：每張圖沿用 vanilla 同名影像的畫布尺寸與偏移（docs/g1-catalog.json），讓圖示在按鈕／分頁裡的位置與原版版面一致；
畫風為原創的像素圖（決策：沿用 Locomotion 版面）。換色規則（OpenLoco Ui/Widgets/*.cpp）：
- 按鈕圖示（ImageButton）：primary remap 換成視窗顏色；停用時整個剪影以兩個色階實心畫出 → 圖示要有清楚的外形。
- 分頁 tab／selected_tab（= tab + 1）、wide_tab／+1：以視窗顏色換色；未選中的分頁再疊一層 tab 形狀的半透明（unk33）。
- 視窗框背景（800 × 44，橫向重複）、縮放把手、色票、滑桿：以視窗顏色換色 → 全用 primary remap 色號。
- 進度條（ProgressBar.cpp）：鐵軌 + 火車（recolour2：primary = 海綠、secondary = 暗紅），4 格車輪動畫。
- 站名標籤兩端（curved_border_*，Station.cpp）以 unk34 半透明疊加 → 遮罩。
另外三張沒有名稱但會用到的圖：wide_tab + 1（選中的寬分頁）、decrease／increase_tool_area + 1（按下時，ImageButtonAlt）。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import g1_title  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "ui"
PAL = dat.load_palette()
PRIMARY = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
SECONDARY = list(range(0xCA, 0xD6))


def G(k):  # 灰（調色盤的 black 色階，偏青灰）
    return 0x0A + max(0, min(11, k))


def Y(k):
    return 0x2E + max(0, min(11, k))


def RD(k):
    return 0xA6 + max(0, min(11, k))


def GN(k):
    return 0x5E + max(0, min(11, k))


def BL(k):
    return 0x82 + max(0, min(11, k))


def BR(k):
    return 0xD6 + max(0, min(11, k))


def OR(k):
    return 0xB2 + max(0, min(11, k))


def P(k):  # primary remap（視窗／公司色）
    return PRIMARY[max(0, min(11, k))]


def S(k):
    return SECONDARY[max(0, min(11, k))]


class C:
    """像素畫布（以 vanilla 影像的寬高與偏移建立）。"""

    def __init__(self, w, h, x=0, y=0):
        self.w, self.h, self.x, self.y = w, h, x, y
        self.px = {}

    def set(self, x, y, c):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            if c == 0:
                self.px.pop((x, y), None)
            else:
                self.px[(x, y)] = c

    def get(self, x, y):
        return self.px.get((x, y), 0)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(int(y0), int(y1) + 1):
            for x in range(int(x0), int(x1) + 1):
                self.set(x, y, c)

    def frame(self, x0, y0, x1, y1, c, c2=None):
        """外框；c2 = 右下的顏色（立體感）。"""
        for x in range(x0, x1 + 1):
            self.set(x, y0, c)
            self.set(x, y1, c2 or c)
        for y in range(y0, y1 + 1):
            self.set(x0, y, c)
            self.set(x1, y, c2 or c)

    def line(self, x0, y0, x1, y1, c, width=1):
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for k in range(int(n * 2) + 1):
            t = k / (n * 2)
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for dx in range(width):
                self.set(x + dx - (width - 1) / 2, y, c)

    def circle(self, cx, cy, r, c, fill=True, ring=None):
        for y in range(int(cy - r) - 1, int(cy + r) + 2):
            for x in range(int(cx - r) - 1, int(cx + r) + 2):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if d <= r:
                    if ring is not None and d > r - 1:
                        self.set(x, y, ring)
                    elif fill:
                        self.set(x, y, c)

    def poly(self, pts, c):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        for y in range(math.floor(min(ys)), math.ceil(max(ys)) + 1):
            for x in range(math.floor(min(xs)), math.ceil(max(xs)) + 1):
                inside = False
                for i in range(len(pts)):
                    (x1, y1), (x2, y2) = pts[i], pts[i - 1]
                    if (y1 > y + 0.5) != (y2 > y + 0.5) and x + 0.5 < (x2 - x1) * (y + 0.5 - y1) / (y2 - y1) + x1:
                        inside = not inside
                if inside:
                    self.set(x, y, c)

    def outline(self, c, diag=False):
        """在現有像素外圍加一圈外框。"""
        nb = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diag else [])
        add = set()
        for (x, y) in self.px:
            for dx, dy in nb:
                if (x + dx, y + dy) not in self.px:
                    add.add((x + dx, y + dy))
        for (x, y) in add:
            self.set(x, y, c)

    def shadow(self, c, dx=1, dy=1):
        for (x, y) in list(self.px):
            if (x + dx, y + dy) not in self.px:
                self.set(x + dx, y + dy, c)

    def blit(self, other, ox, oy):
        for (x, y), v in other.px.items():
            self.set(x + ox, y + oy, v)

    def frame_out(self):
        px = bytearray(self.w * self.h)
        for (x, y), v in self.px.items():
            px[y * self.w + x] = v
        return (self.w, self.h, self.x, self.y, bytes(px))


def from_text(rows, colours):
    """小圖用文字描述：每個字元對應 colours[字元]，'.' 或空白 = 透明。"""
    c = C(max(len(r) for r in rows), len(rows))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch not in ". ":
                c.set(x, y, colours[ch])
    return c


# ================================================================ 視窗元件
def window_resize_handle(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    for k in range(3):                                         # 右下角三道斜紋
        d = 3 + k * 3
        c.line(e["w"] - 1, e["h"] - 1 - d, e["w"] - 1 - d, e["h"] - 1, P(10))
        c.line(e["w"] - 1, e["h"] - d, e["w"] - d, e["h"] - 1, P(3))
    return c


def close_button(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    for k in range(e["w"]):
        c.set(k, k, G(1))
        c.set(e["w"] - 1 - k, k, G(1))
    return c


def frame_background(e, alt):
    """視窗上方 41 px 的背景（橫向重複、以視窗顏色換色）：由亮到暗的漸層＋淡淡的斜紋，左邊一條邊線。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    rng = random.Random(5 if alt else 3)
    for y in range(e["h"]):
        base = (10 if not alt else 9) - y * 4 / e["h"]
        for x in range(e["w"]):
            v = base + (0.6 if ((x + y * 2) // 3) % 6 == 0 else 0) + rng.uniform(-0.35, 0.35)
            c.set(x, y, P(int(round(v))))
    for y in range(e["h"]):
        c.set(0, y, P(3))
    return c


def tab_shape(w, h, selected, top=0):
    """分頁外形：上方圓角、左上亮邊、右邊暗邊；選中的分頁多一列（與內容區相連）。"""
    c = C(w, h)
    bottom = h - 1
    for y in range(top, bottom + 1):
        for x in range(w):
            if y == top and x in (0, w - 1):
                continue
            if y == top + 1 and x in (0, w - 1) and False:
                continue
            edge_l = x == 0 or (y == top and x == 1)
            edge_t = y == top or (y == top + 1 and x in (0, w - 1))
            edge_r = x == w - 1
            if edge_t or edge_l:
                col = P(11)
            elif edge_r:
                col = P(3)
            else:
                col = P(9 if selected else 7)
            c.set(x, y, col)
    if not selected:
        for x in range(w):
            c.set(x, bottom, P(11))
    return c


def tab(e, selected):
    c = tab_shape(e["w"], e["h"], selected)
    c.x, c.y = e["x"], e["y"]
    return c


def colour_swatch(e, style):
    c = C(e["w"], e["h"], e["x"], e["y"])
    c.rect(1, 1, e["w"] - 2, e["h"] - 2, P(7))
    if style == "raised":
        c.frame(0, 0, e["w"] - 1, e["h"] - 1, P(10), P(3))
    elif style == "pressed":
        c.frame(0, 0, e["w"] - 1, e["h"] - 1, P(3), P(10))
        c.rect(1, 1, e["w"] - 2, e["h"] - 2, P(6))
    else:
        c.frame(0, 0, e["w"] - 1, e["h"] - 1, P(5))
    return c


def curved_border(e, side):
    """站名標籤的半圓端（以 unk34 半透明疊加 → 遮罩）。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    r = e["h"] / 2
    for y in range(e["h"]):
        for x in range(e["w"]):
            xx = (e["w"] - x - 0.5) if side == "left" else (x + 0.5)
            if math.hypot(xx * (r / e["w"]), y + 0.5 - r) <= r:
                c.set(x, y, G(1))
    return c


def slider_track(e, vertical):
    c = C(e["w"], e["h"], e["x"], e["y"])
    if vertical:
        cx = e["w"] // 2
        c.rect(cx - 1, 2, cx + 1, e["h"] - 3, P(4))
        c.line(cx - 1, 2, cx - 1, e["h"] - 3, P(2))
        c.line(cx + 1, 2, cx + 1, e["h"] - 3, P(10))
        for k in range(5):
            y = 4 + k * (e["h"] - 9) // 4
            c.line(cx - 6, y, cx - 4, y, P(3))
            c.line(cx + 4, y, cx + 6, y, P(3))
    else:
        cy = e["h"] // 2
        c.rect(2, cy - 1, e["w"] - 3, cy + 1, P(4))
        c.line(2, cy - 1, e["w"] - 3, cy - 1, P(2))
        c.line(2, cy + 1, e["w"] - 3, cy + 1, P(10))
        for k in range(11):
            x = 4 + k * (e["w"] - 9) // 10
            c.line(x, cy + 4, x, cy + 6 if k % 5 == 0 else cy + 5, P(3))
    return c


def slider_thumb(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    c.rect(0, 0, e["w"] - 1, e["h"] - 1, P(8))
    c.frame(0, 0, e["w"] - 1, e["h"] - 1, P(11), P(2))
    if e["h"] > e["w"]:
        for y in range(e["h"] // 2 - 3, e["h"] // 2 + 4, 2):
            c.line(2, y, e["w"] - 3, y, P(4))
    else:
        for x in range(e["w"] // 2 - 3, e["w"] // 2 + 4, 2):
            c.line(x, 2, x, e["h"] - 3, P(4))
    return c


def news_background(e, old, half):
    """新聞紙背景（左右兩半）：old = 泛黃舊報紙，new = 白色新報紙；紙張纖維雜點＋淡淡的欄線與摺痕。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    rng = random.Random((7 if old else 9) + half)
    for y in range(e["h"]):
        for x in range(e["w"]):
            n = rng.random()
            if old:
                v = (BR(9) if n < 0.55 else BR(10) if n < 0.85 else Y(6))
            else:
                v = (G(10) if n < 0.6 else G(11) if n < 0.9 else G(9))
            gx = x + half * e["w"]
            if gx == 2 * e["w"] - 1 or gx == 0 or y in (0, e["h"] - 1):
                v = BR(6) if old else G(7)
            c.set(x, y, v)
    if old:                                                    # 舊報紙的斑點
        for _ in range(18):
            cx, cy, r = rng.uniform(0, e["w"]), rng.uniform(0, e["h"]), rng.uniform(1, 4)
            for y in range(int(cy - r), int(cy + r) + 1):
                for x in range(int(cx - r), int(cx + r) + 1):
                    if math.hypot(x - cx, y - cy) < r and rng.random() < 0.6:
                        c.set(x, y, BR(8))
    return c


def progress_track(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    for x in range(0, e["w"], 5):                              # 枕木
        c.rect(x, e["h"] - 6, x + 2, e["h"] - 2, BR(3))
    for y, col in ((e["h"] - 6, G(8)), (e["h"] - 3, G(8))):
        c.line(0, y, e["w"] - 1, y, col)
        c.line(0, y + 1, e["w"] - 1, y + 1, G(4))
    return c


def progress_train(e, frame, style):
    """進度條上的火車：style 0 = 蒸汽機車 + 客車；style 1 = 流線型柴油動車組。primary / secondary 由程式換色。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    H = e["h"]
    base = H - 4                                               # 輪子中心
    x = e["w"] - 1

    def wheel(cx, r, k):
        c.circle(cx, base, r, G(2), ring=G(1))
        a = (frame + k) * math.pi / 4
        c.set(cx + round(math.cos(a) * (r - 1)), base + round(math.sin(a) * (r - 1)), G(8))
    if style == 0:
        # 機車（朝右）
        c.rect(x - 34, base - 11, x - 6, base - 3, P(6))       # 鍋爐
        c.rect(x - 34, base - 11, x - 6, base - 10, P(9))
        c.rect(x - 7, base - 10, x - 3, base - 3, G(2))        # 煙箱
        c.rect(x - 9, base - 16, x - 7, base - 11, G(1))       # 煙囪
        c.rect(x - 40, base - 16, x - 30, base - 3, P(5))      # 駕駛室
        c.rect(x - 38, base - 14, x - 33, base - 11, G(10))
        c.rect(x - 42, base - 17, x - 28, base - 16, G(2))
        for k, cx in enumerate((x - 12, x - 20, x - 28)):
            wheel(cx, 3.5, k)
        c.line(x - 28, base, x - 12, base, S(7))               # 連桿
        x -= 46
        while x > 30:                                          # 客車
            c.rect(x - 36, base - 13, x, base - 3, S(6))
            c.rect(x - 36, base - 13, x, base - 12, S(9))
            for wx in range(x - 33, x - 2, 6):
                c.rect(wx, base - 10, wx + 3, base - 7, G(10))
            wheel(x - 6, 2.5, 0)
            wheel(x - 30, 2.5, 1)
            x -= 40
    else:
        nose = [(x, base - 3), (x - 4, base - 12), (x - 14, base - 15), (x - 14, base - 3)]
        c.poly(nose, P(7))
        c.line(x - 4, base - 12, x - 14, base - 15, P(10))
        c.rect(x - 9, base - 12, x - 6, base - 9, G(10))
        while x > 30:
            c.rect(x - 56, base - 15, x - 14, base - 3, P(6))
            c.rect(x - 56, base - 15, x - 14, base - 14, P(9))
            c.rect(x - 56, base - 8, x - 14, base - 7, S(7))   # 飾帶
            for wx in range(x - 53, x - 16, 6):
                c.rect(wx, base - 12, wx + 3, base - 10, G(10))
            wheel(x - 20, 2.5, 0)
            wheel(x - 26, 2.5, 1)
            wheel(x - 44, 2.5, 2)
            wheel(x - 50, 2.5, 3)
            x -= 44
    return c


def tick_big(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    pts = [(1, 9), (4, 6), (8, 10), (17, 1), (19, 4), (8, 16)]
    c.poly(pts, GN(8))
    c.line(4, 6, 8, 10, GN(11))
    c.line(8, 10, 17, 1, GN(10))
    c.outline(GN(2))
    return c


def owner_jailed(e):
    """入獄：疊在頭像上的鐵窗（5 根直條 + 上下橫條）。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    for x in range(2, e["w"] - 2, 10):
        c.rect(x, 0, x + 2, e["h"] - 1, G(3))
        c.line(x, 0, x, e["h"] - 1, G(7))
    for y in (6, e["h"] - 8):
        c.rect(0, y, e["w"] - 1, y + 2, G(3))
        c.line(0, y, e["w"] - 1, y, G(7))
    return c


def random_map_watermark(e):
    """隨機地圖浮水印（以視窗第二色換色）：兩顆骰子 + 起伏的山形。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    for x in range(e["w"]):                                    # 山形
        top = int(60 + 10 * math.sin(x / 9) + 6 * math.sin(x / 4 + 1))
        for y in range(top, e["h"]):
            c.set(x, y, P(5 if (x + y) % 2 else 4))
    for (x0, y0, dots) in ((10, 12, (1, 5, 9)), (36, 28, (1, 3, 5, 7, 9))):
        c.rect(x0, y0, x0 + 24, y0 + 24, P(9))
        c.frame(x0, y0, x0 + 24, y0 + 24, P(11), P(4))
        pos = {1: (5, 5), 3: (19, 5), 5: (12, 12), 7: (5, 19), 9: (19, 19)}
        for d in dots:
            px, py = pos[d]
            c.circle(x0 + px + 0.5, y0 + py + 0.5, 2.2, P(3))
    return c


def compass(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    cx, cy = e["w"] / 2, e["h"] / 2
    c.circle(cx, cy, 9.5, G(10), ring=G(2))
    c.poly([(cx, 2), (cx + 3, cy), (cx, cy + 1), (cx - 3, cy)], RD(7))
    c.poly([(cx, e["h"] - 2), (cx + 3, cy), (cx, cy - 1), (cx - 3, cy)], G(4))
    return c


def tool_area(e):
    """地形工具的範圍示意：一格菱形（數字由程式疊上）。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    cx, cy = e["w"] / 2, e["h"] / 2
    c.poly([(cx, 0), (e["w"], cy), (cx, e["h"]), (0, cy)], GN(5))
    for (x, y) in list(c.px):
        if (x + y) % 2 == 0:
            c.set(x, y, GN(6))
    c.outline(G(1))
    return c


def plus_minus(e, plus, pressed):
    c = C(e["w"], e["h"], e["x"], e["y"])
    c.rect(1, 1, e["w"] - 2, e["h"] - 2, P(6 if pressed else 8))
    c.frame(1, 1, e["w"] - 2, e["h"] - 2, P(3) if pressed else P(11), P(11) if pressed else P(3))
    m = e["w"] // 2
    o = 1 if pressed else 0
    c.rect(4 + o, m - 1 + o, e["w"] - 5 + o, m + o, G(1))
    if plus:
        c.rect(m - 1 + o, 4 + o, m + o, e["h"] - 5 + o, G(1))
    return c


# ================================================================ 小圖示（工具、路線、音樂…）
def icon(e, rows, colours, outline=G(1)):
    c = C(e["w"], e["h"], e["x"], e["y"])
    art = from_text(rows, colours)
    if outline is not None:
        art.outline(outline)
    ox = (e["w"] - art.w) // 2
    oy = (e["h"] - art.h) // 2
    c.blit(art, ox, oy)
    return c


def triangle_arrow(e, up, colour, light):
    c = C(e["w"], e["h"], e["x"], e["y"])
    w, h = e["w"], e["h"]
    if up:
        c.poly([(w / 2, 0.5), (w - 1, h - 1), (1, h - 1)], colour)
        c.line(w / 2, 1, 2, h - 2, light)
    else:
        c.poly([(1, 0.5), (w - 1, 0.5), (w / 2, h - 1)], colour)
        c.line(2, 1, w - 3, 1, light)
    c.outline(G(1))
    return c


def speed(e, kind, active):
    """時間控制：暫停 ||、正常 ▶、快轉 ▶▶、超快 ▶▶▶；active = 目前選取（亮色）。"""
    c = C(e["w"], e["h"], e["x"], e["y"])
    col = Y(10) if active else G(9)
    edge = G(1)
    h = e["h"]
    if kind == "pause":
        c.rect(1, 1, 2, h - 2, col)
        c.rect(5, 1, 6, h - 2, col)
    else:
        n = {"normal": 1, "fast": 2, "extra": 3}[kind]
        for k in range(n):
            x0 = 1 + k * 4
            c.poly([(x0, 1), (x0 + 5, h / 2), (x0, h - 1)], col)
    c.outline(edge)
    return c


def flag(e, colour):
    c = C(e["w"], e["h"], e["x"], e["y"])
    c.rect(3, 1, 3, e["h"] - 1, BR(3))                         # 旗桿
    for y in range(2, 10):
        for x in range(4, e["w"] - 2):
            wave = round(math.sin((x - 4) / 3) * 1.2)
            if 2 <= y + wave <= 10:
                c.set(x, y + wave, colour(7 if (x // 3) % 2 == 0 else 9))
    c.outline(G(1))
    c.circle(3.5, 1, 1.2, Y(9))
    return c


def tree_icon(e, random_tree):
    c = C(e["w"], e["h"], e["x"], e["y"])
    if random_tree:
        for (cx, cy, r, col) in ((7, 9, 5, GN(5)), (14, 7, 5.5, GN(7)), (11, 13, 4.5, GN(6))):
            c.circle(cx, cy, r, col)
        c.rect(10, 15, 11, 20, BR(3))
        c.circle(16, 4, 3, Y(9))                               # 「隨機」記號
        c.set(16, 3, G(1))
        c.set(16, 5, G(1))
    else:
        c.poly([(11, 1), (19, 14), (3, 14)], GN(6))
        c.poly([(11, 1), (19, 14), (11, 14)], GN(4))
        c.rect(10, 15, 12, 20, BR(3))
    c.outline(G(1))
    return c


def houses(e):
    c = C(e["w"], e["h"], e["x"], e["y"])
    for (x0, y0, w, h) in ((2, 10, 8, 9), (11, 6, 9, 13)):
        c.rect(x0, y0, x0 + w, y0 + h, G(10))
        c.poly([(x0 - 1, y0), (x0 + w / 2, y0 - 5), (x0 + w + 1, y0)], RD(6))
        c.rect(x0 + 2, y0 + 3, x0 + 3, y0 + 5, BL(6))
    c.outline(G(1))
    for k in range(3):                                         # 往外擴張的箭頭
        c.set(20 - k, 2 + k, Y(10))
        c.set(18, 2, Y(10))
        c.set(20, 4, Y(10))
    return c


def music(e, kind):
    c = C(e["w"], e["h"], e["x"], e["y"])
    w, h = e["w"], e["h"]
    if kind == "stop":
        c.rect(2, 2, w - 3, h - 3, G(9))
    elif kind == "play":
        c.poly([(3, 1), (w - 2, h / 2), (3, h - 1)], G(9))
    else:
        c.poly([(1, 2), (w / 2, h / 2), (1, h - 2)], G(9))
        c.poly([(w / 2 - 1, 2), (w - 3, h / 2), (w / 2 - 1, h - 2)], G(9))
        c.rect(w - 3, 2, w - 2, h - 3, G(9))
    c.outline(G(1))
    return c


# ================================================================ 建造視窗的軌道片段圖示（俯視；坡道為側視）
def track_path(c, pts, gauge=2.0):
    """沿中心線畫雙軌 + 枕木（深色，最後由呼叫者加外框）。pts：由下往上（行進方向）的點列。"""
    dense = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) * 3))
        for k in range(n):
            t = k / n
            dense.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    dense.append(pts[-1])
    frames = []
    for i in range(1, len(dense) - 1):
        (xa, ya), (xb, yb) = dense[i - 1], dense[i + 1]
        tx, ty = xb - xa, yb - ya
        n = math.hypot(tx, ty) or 1
        frames.append((dense[i], (-ty / n, tx / n)))
    acc = 0.0
    for k, ((x, y), (nx, ny)) in enumerate(frames):
        if k:
            acc += math.hypot(x - frames[k - 1][0][0], y - frames[k - 1][0][1])
        if acc >= 2.6 or k == 0:
            acc = 0.0
            s = -gauge - 1.2
            while s <= gauge + 1.2:
                c.set(x + nx * s, y + ny * s, BR(5))
                s += 0.4
    for (x, y), (nx, ny) in frames:
        for sg in (-gauge, gauge):
            c.set(x + nx * sg, y + ny * sg, G(3))


def arc_points(cx, cy, r, a0, a1, n=32):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def construction_icon(e, kind):
    c = C(e["w"], e["h"], e["x"], e["y"])
    w, h = e["w"], e["h"]
    m = 3.5                                                   # 軌道半寬（含枕木）＋外框的邊距
    if kind == "straight":
        track_path(c, [(w / 2, h), (w / 2, -1)])
    elif kind in ("left_turnaround", "right_turnaround"):
        sgn = -1 if kind.startswith("left") else 1
        r = (w - 2 * m) / 2
        xs, xe = w / 2 - sgn * r, w / 2 + sgn * r
        top = m + r
        pts = [(xs, h)] + arc_points(w / 2, top, r, math.pi if sgn > 0 else 0, 2 * math.pi if sgn > 0 else -math.pi)[::] + [(xe, h)]
        pts = [(xs, h), (xs, top)] + [p for p in arc_points(w / 2, top, r, math.pi, 2 * math.pi)][:: (1 if sgn > 0 else -1)] + [(xe, top), (xe, h)]
        if sgn < 0:
            pts = [(xe, h), (xe, top)] + arc_points(w / 2, top, r, 2 * math.pi, math.pi) + [(xs, top), (xs, h)]
        track_path(c, pts, gauge=1.6)
    elif kind.startswith(("left", "right")):
        size = kind.split("_", 1)[1]
        sgn = -1 if kind.startswith("left") else 1
        if size == "large":                                   # 45° 緩彎
            R = h * 1.6
            x0 = w / 2 - sgn * 2.5
            cx = x0 + sgn * R
            pts = arc_points(cx, h, R, math.pi if sgn > 0 else 0, (math.pi * 1.25) if sgn > 0 else -math.pi * 0.25)
            pts = [(px, py) for px, py in pts if py > -2]
        else:                                                 # 90° 彎：底部出發、轉向側邊
            x0 = m if sgn > 0 else w - m
            R = min(abs((w - m) - x0) if sgn > 0 else x0 - m, h - m) * {"very_small": 0.75, "small": 0.85, "curve": 1.0}[size]
            R = max(R, 4)
            cx = x0 + sgn * R
            pts = [(x0, h)] + arc_points(cx, h - 1, R, math.pi if sgn > 0 else 0, 1.5 * math.pi if sgn > 0 else -0.5 * math.pi) \
                + [(cx + sgn * (w + 2), h - 1 - R)]
        track_path(c, pts)
    elif kind.startswith("s_bend"):
        sgn = -1 if kind.endswith("left") else 1
        if kind.startswith("s_bend_dual"):
            for off in (-3.5, 3.5):
                pts = [(w / 2 + off - sgn * 1.5 + sgn * 3 * (0.5 - 0.5 * math.cos(math.pi * k / 20)), h - (h + 1) * k / 20) for k in range(21)]
                track_path(c, pts, gauge=1.2)
        elif kind.startswith("s_bend_to_single"):
            for off in (-3.5, 3.5):
                pts = [(w / 2 + off * (0.5 + 0.5 * math.cos(math.pi * k / 20)), h - (h + 1) * k / 20) for k in range(21)]
                track_path(c, pts, gauge=1.2)
        else:
            amp = (w - 2 * m) / 2
            pts = [(w / 2 - sgn * amp + 2 * sgn * amp * (0.5 - 0.5 * math.cos(math.pi * k / 20)), h - (h + 1) * k / 20) for k in range(21)]
            track_path(c, pts)
    elif kind in ("level", "slope_up", "slope_down", "steep_slope_up", "steep_slope_down"):
        rise = {"level": 0, "slope_up": 4, "slope_down": -4, "steep_slope_up": 8, "steep_slope_down": -8}[kind]
        rise = max(-(h - 5), min(h - 5, rise))
        y0 = h - 3 if rise >= 0 else h - 3 + rise
        for x in range(w):
            y = round(y0 - rise * x / (w - 1))
            for yy in range(y + 2, h):
                c.set(x, yy, GN(5) if (x + yy) % 2 else GN(4))
            c.set(x, y, G(10))
            c.set(x, y + 1, G(3))
            if x % 3 == 0:
                c.set(x, y + 1, BR(4))
    elif kind == "remove":
        track_path(c, [(w / 2, h), (w / 2, -1)])
        c.outline(G(1))
        for k in range(-6, 7):
            for d in (0, 1):
                c.set(w / 2 + k + d, h / 2 + k * 0.8, RD(9))
                c.set(w / 2 + k + d, h / 2 - k * 0.8, RD(9))
        return c
    elif kind == "new_position":
        c.circle(w / 2, h / 2, 7.5, 0, ring=G(2))
        c.line(w / 2, 0, w / 2, h - 1, G(2))
        c.line(0, h / 2, w - 1, h / 2, G(2))
        c.circle(w / 2, h / 2, 2.5, Y(10))
        c.outline(G(9))
        return c
    c.outline(G(1))
    return c


# ================================================================ 各種功能圖示
def misc_icon(e, name):
    c = C(e["w"], e["h"], e["x"], e["y"])
    w, h = e["w"], e["h"]
    cx, cy = w / 2, h / 2
    if name == "rubbish_bin":
        c.rect(2, 4, w - 3, h - 1, G(7))
        for x in range(4, w - 4, 3):
            c.line(x, 6, x, h - 3, G(4))
        c.rect(1, 2, w - 2, 3, G(9))
        c.rect(cx - 2, 0, cx + 1, 1, G(9))
    elif name == "centre_viewport":
        c.circle(cx, cy, 7.5, 0, ring=G(10))
        c.circle(cx, cy, 4.5, 0, ring=G(10))
        c.line(cx, 0, cx, h - 1, G(10))
        c.line(0, cy, w - 1, cy, G(10))
        c.circle(cx, cy, 1.5, RD(8))
    elif name == "rotate_object":
        for k in range(40):
            a = math.radians(30 + k * 7.5)
            c.set(cx + 7 * math.cos(a), cy + 7 * math.sin(a), G(10))
            c.set(cx + 6 * math.cos(a), cy + 6 * math.sin(a), G(10))
        c.poly([(cx + 7, cy - 6), (cx + 11, cy - 1), (cx + 3, cy - 1)], G(10))
    elif name == "photo_camera":
        c.rect(1, 3, w - 2, h - 1, G(3))
        c.rect(3, 1, 7, 2, G(3))
        c.circle(cx + 1, cy + 1.5, 4, G(9), ring=G(10))
        c.circle(cx + 1, cy + 1.5, 2, BL(5))
        c.set(w - 4, 4, Y(10))
    elif name == "paintbrush":
        c.line(3, h - 3, w - 6, 4, BR(6), width=2)
        c.poly([(w - 7, 1), (w - 1, 1), (w - 1, 7), (w - 5, 5)], G(9))
        c.poly([(1, h - 1), (6, h - 4), (4, h - 6)], RD(8))
    elif name == "stopwatch":
        c.circle(cx, cy + 1, 8, G(10), ring=G(2))
        c.rect(cx - 1, 0, cx, 2, G(3))
        c.line(cx, cy + 1, cx, cy - 4, G(1))
        c.line(cx, cy + 1, cx + 3, cy + 2, RD(8))
    elif name in ("pickupFromAirport", "placeOnAirport"):
        plane = [(cx, 3), (cx + 1, 6), (cx + 8, 10), (cx + 8, 11), (cx + 1, 9), (cx + 1, 14), (cx + 3, 16), (cx - 3, 16),
                 (cx - 1, 14), (cx - 1, 9), (cx - 8, 11), (cx - 8, 10), (cx - 1, 6)]
        c.poly(plane, G(10))
        up = name.startswith("pickup")
        ax = 3
        if up:
            c.poly([(ax, 1), (ax + 3, 5), (ax - 3, 5)], Y(10))
            c.rect(ax - 1, 5, ax, 9, Y(10))
        else:
            c.poly([(ax, h - 2), (ax + 3, h - 6), (ax - 3, h - 6)], Y(10))
            c.rect(ax - 1, h - 10, ax, h - 6, Y(10))
    elif name == "pass_signal":
        c.rect(cx - 1, 6, cx, h - 1, G(3))
        c.rect(cx - 4, 0, cx + 3, 6, G(2))
        c.circle(cx - 0.5, 2, 1.6, GN(9))
        c.circle(cx - 0.5, 5, 1.6, RD(4))
        c.poly([(1, 12), (6, 9), (6, 15)], GN(9))
    elif name == "route_delete":
        for k in range(w - 2):
            for d in (0, 1):
                c.set(1 + k + d, 1 + k * (h - 3) / (w - 3), RD(8))
                c.set(w - 2 - k + d - 1, 1 + k * (h - 3) / (w - 3), RD(8))
    elif name == "route_skip":
        c.circle(5, cy + 3, 2.5, G(9))
        for k in range(20):
            a = math.pi + k * math.pi / 19
            c.set(cx + 6 * math.cos(a), cy + 2 + 5 * math.sin(a), Y(10))
        c.poly([(w - 2, cy + 2), (w - 6, cy), (w - 6, cy + 5)], Y(10))
    elif name == "route_wait":
        c.poly([(cx - 5, 1), (cx + 5, 1), (cx, cy), (cx + 5, h - 2), (cx - 5, h - 2), (cx, cy)], Y(8))
        c.rect(cx - 6, 0, cx + 6, 0, BR(4))
        c.rect(cx - 6, h - 1, cx + 6, h - 1, BR(4))
        c.rect(cx - 2, h - 4, cx + 2, h - 3, BR(6))
    elif name == "route_force_unload":
        c.rect(3, 6, w - 4, h - 1, BR(6))
        c.frame(3, 6, w - 4, h - 1, BR(3))
        c.poly([(cx, 5), (cx - 4, 0), (cx + 4, 0)], Y(10))
    elif name == "show_station_catchment":
        for k in range(0, w, 2):
            c.set(k, 0, P(8))
            c.set(k, h - 1, P(8))
            c.set(0, k, P(8))
            c.set(w - 1, k, P(8))
        c.rect(cx - 4, cy - 3, cx + 3, cy + 3, G(9))
        c.rect(cx - 5, cy - 5, cx + 4, cy - 4, RD(6))
    elif name == "refit_cargo_button":
        c.rect(5, 6, w - 6, h - 5, BR(6))
        c.frame(5, 6, w - 6, h - 5, BR(3))
        for k in range(14):
            a = math.radians(200 + k * 10)
            c.set(cx + 9 * math.cos(a), cy + 9 * math.sin(a), Y(10))
            a = math.radians(20 + k * 10)
            c.set(cx + 9 * math.cos(a), cy + 9 * math.sin(a), Y(10))
    elif name in ("step_back", "step_forward"):
        sgn = 1 if name == "step_forward" else -1
        for k in (0, 1):
            x0 = cx + sgn * (-6 + k * 6)
            c.poly([(x0, 2), (x0 + sgn * 6, cy), (x0, h - 2)], G(10))
        bx = cx + sgn * 7
        c.rect(bx, 2, bx + 1, h - 3, G(10))
    elif name == "icon_folder":
        c.rect(0, 2, w - 1, h - 1, Y(8))
        c.rect(0, 0, 4, 1, Y(8))
        c.line(0, 3, w - 1, 3, Y(10))
    elif name == "icon_parent_folder":
        c.rect(0, 4, w - 5, h - 1, Y(8))
        c.rect(0, 2, 4, 3, Y(8))
        c.poly([(w - 3, 0), (w, 4), (w - 6, 4)], GN(8))
        c.rect(w - 4, 4, w - 3, 9, GN(8))
    elif name == "company_list_dropdown_icon":
        for k, hh in enumerate((10, 16, 7, 13)):
            c.rect(3 + k * 6, h - 2 - hh, 7 + k * 6, h - 2, P(7) if k % 2 else S(7))
        c.line(1, h - 1, w - 2, h - 1, G(2))
    if name not in ("show_station_catchment", "icon_folder"):
        c.outline(G(1))
    return c


# ================================================================ 分頁圖示
def gear(c, cx, cy, r, teeth, col, hole=None):
    for y in range(int(cy - r - 3), int(cy + r + 4)):
        for x in range(int(cx - r - 3), int(cx + r + 4)):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            a = math.atan2(dy, dx)
            rim = r + (2.2 if math.cos(a * teeth) > 0.3 else 0)
            if d <= rim and (hole is None or d > hole):
                c.set(x, y, col)


def tab_icon(e, name, frame=0):
    c = C(e["w"], e["h"], e["x"], e["y"])
    w, h = e["w"], e["h"]
    cx, cy = w / 2, h / 2
    if name == "tab_display":                                  # 螢幕
        c.rect(1, 1, w - 2, h - 6, G(2))
        c.rect(3, 3, w - 4, h - 8, BL(6))
        c.line(4, 4, 8, 4, BL(9))
        c.rect(cx - 2, h - 5, cx + 1, h - 3, G(4))
        c.rect(cx - 6, h - 2, cx + 5, h - 1, G(4))
    elif name == "tab_control":                                # 滑鼠＋鍵盤
        c.rect(1, h - 10, w - 10, h - 2, G(8))
        for x in range(3, w - 11, 3):
            for y in (h - 8, h - 5):
                c.set(x, y, G(3))
        c.circle(w - 5, 8, 4.5, G(10))
        c.line(w - 5, 3, w - 5, 8, G(3))
        c.line(w - 5, 3, w - 9, h - 12, G(3))
    elif name == "tab_sound":                                  # 喇叭
        c.rect(1, cy - 3, 5, cy + 3, G(8))
        c.poly([(5, cy - 3), (w - 6, 2), (w - 6, h - 2), (5, cy + 3)], G(8))
        for r in (3, 6):
            for k in range(-5, 6):
                a = k / 6
                c.set(w - 5 + r * math.cos(a) - 2, cy + r * math.sin(a) * 1.6, Y(9))
    elif name == "tab_miscellaneous":                          # 齒輪＋扳手
        gear(c, 9, cy, 4.5, 8, G(9), hole=1.8)
        c.line(w - 14, h - 3, w - 3, 3, G(8), width=2)
        c.circle(w - 3, 3, 2.5, G(8))
    elif name.startswith("tab_globe"):
        g = g1_title.globe_pixels(w, h, w / 2, h / 2, min(w, h) / 2 - 1, 2 * math.pi * frame / 32)
        for (x, y), v in g.items():
            c.set(x, y, v)
        return c
    elif name.startswith("tab_music"):                         # 音符上下跳動
        for k, (x0, base) in enumerate(((4, 12), (13, 9), (21, 13))):
            y = base - round(3 * abs(math.sin(math.pi * (frame + k * 5) / 16)))
            c.circle(x0, y + 5, 2.4, G(1))
            c.rect(x0 + 1, y - 4, x0 + 2, y + 5, G(1))
            c.rect(x0 + 2, y - 4, x0 + 4, y - 3, G(1))
        return c
    else:
        obj = name.replace("tab_object_", "")
        draw_object_tab(c, obj, w, h)
    c.outline(G(1))
    return c


def draw_object_tab(c, obj, w, h):
    cx, cy = w / 2, h / 2
    if obj == "settings":
        gear(c, cx, cy, 6, 8, G(9), hole=2.5)
    elif obj == "audio":
        c.rect(2, cy - 3, 6, cy + 3, G(8))
        c.poly([(6, cy - 3), (12, cy - 8), (12, cy + 8), (6, cy + 3)], G(8))
        c.line(15, cy - 4, 15, cy + 4, Y(9))
        c.line(18, cy - 7, 18, cy + 7, Y(9))
    elif obj == "currency":
        for k in range(4):
            c.rect(3 + k, h - 4 - k * 3, w - 10 + k, h - 2 - k * 3, Y(7 + (k % 2) * 2))
        c.circle(w - 6, cy - 2, 5, Y(9), ring=Y(6))
    elif obj in ("smoke",):
        for (x, y, r) in ((6, h - 5, 3), (10, h - 10, 4), (15, h - 15, 5)):
            c.circle(x, y, r, G(9))
    elif obj == "cliff":
        c.poly([(0, h - 1), (0, 8), (8, 4), (14, 9), (14, h - 1)], BR(5))
        c.poly([(14, h - 1), (14, 9), (w - 1, 14), (w - 1, h - 1)], GN(5))
        for y in range(8, h, 4):
            c.line(1, y, 12, y + 1, BR(3))
    elif obj == "water":
        for y0 in (4, 10, 16):
            for x in range(w):
                c.set(x, y0 + round(1.5 * math.sin(x / 2.5 + y0)), BL(8))
                c.set(x, y0 + 1 + round(1.5 * math.sin(x / 2.5 + y0)), BL(5))
    elif obj == "landscape":
        for x in range(w):
            top = int(h - 4 - 7 * abs(math.sin(x / 7)) - 3 * math.sin(x / 3))
            for y in range(top, h):
                c.set(x, y, GN(6) if y < top + 2 else GN(4))
    elif obj == "town_names":
        c.rect(cx - 1, 5, cx, h - 1, BR(3))
        c.rect(1, 2, w - 2, 9, BR(8))
        c.line(3, 5, w - 4, 5, BR(3))
        c.line(3, 7, w - 7, 7, BR(3))
    elif obj == "cargo":
        c.rect(2, 6, w - 3, h - 1, BR(6))
        c.frame(2, 6, w - 3, h - 1, BR(3))
        c.line(2, 6, w - 3, h - 1, BR(4))
        c.line(w - 3, 6, 2, h - 1, BR(4))
    elif obj == "walls":
        for y in range(4, h, 4):
            off = 0 if (y // 4) % 2 else 4
            for x in range(-off, w, 8):
                c.rect(max(0, x), y, min(w - 1, x + 6), y + 2, RD(5))
    elif obj == "signals":
        c.rect(cx - 1, 2, cx, h - 1, G(3))
        c.rect(cx + 1, 4, w - 3, 7, RD(8))
        c.rect(w - 4, 4, w - 3, 7, G(10))
    elif obj == "level_crossings":
        c.line(3, 3, w - 4, h - 6, G(10), width=2)
        c.line(w - 4, 3, 3, h - 6, G(10), width=2)
        c.rect(cx - 1, cy, cx, h - 1, G(3))
        c.set(5, 4, RD(8))
        c.set(w - 6, 4, RD(8))
    elif obj == "streetlights":
        c.rect(cx - 1, 4, cx, h - 1, G(3))
        c.rect(cx - 1, 3, cx + 5, 4, G(3))
        c.rect(cx + 3, 5, cx + 6, 6, Y(10))
    elif obj == "tunnels":
        c.rect(0, 2, w - 1, h - 1, G(6))
        c.circle(cx, cy + 4, 7, G(0))
        c.rect(cx - 7, cy + 4, cx + 6, h - 1, G(0))
    elif obj == "bridges":
        c.rect(0, 5, w - 1, 7, G(8))
        for k in range(w):
            y = 8 + int(8 * (1 - ((k - cx) / cx) ** 2))
            c.set(k, y, G(7))
        for x in (3, w - 4):
            c.rect(x, 8, x + 1, h - 1, G(6))
        c.rect(0, h - 3, w - 1, h - 1, BL(6))
    elif obj == "track_stations":
        c.rect(1, h - 7, w - 2, h - 4, G(9))
        c.rect(2, 4, 3, h - 7, G(3))
        c.rect(w - 4, 4, w - 3, h - 7, G(3))
        c.rect(0, 2, w - 1, 4, RD(6))
        c.line(0, h - 2, w - 1, h - 2, G(6))
    elif obj == "track_mods":
        c.rect(3, 2, 4, h - 1, G(3))
        c.line(4, 4, w - 1, 4, G(3))
        c.line(6, 7, w - 1, 7, Y(8))
    elif obj == "track":
        track_path(c, [(cx, h - 0.5), (cx, 0.5)], gauge=3.0)
    elif obj == "road_stations":
        c.rect(cx - 1, 6, cx, h - 1, G(3))
        c.circle(cx - 0.5, 5, 4.5, Y(9), ring=G(2))
        c.rect(cx - 2, 4, cx + 1, 5, GN(5))
    elif obj == "road_mods":
        c.line(0, 2, w - 1, 2, G(3))
        c.line(0, 6, w - 1, 6, Y(8))
        for x in (3, w - 4):
            c.rect(x, 0, x + 1, h - 1, G(3))
    elif obj == "road":
        c.rect(3, 0, w - 4, h - 1, G(4))
        for y in range(1, h, 5):
            c.rect(cx - 1, y, cx, y + 2, G(11))
    elif obj == "airports":
        plane = [(cx, 1), (cx + 1, 6), (cx + 10, 11), (cx + 10, 13), (cx + 1, 10), (cx + 1, 17), (cx + 4, 20), (cx - 4, 20),
                 (cx - 1, 17), (cx - 1, 10), (cx - 10, 13), (cx - 10, 11), (cx - 1, 6)]
        c.poly(plane, G(10))
    elif obj == "docks":
        c.poly([(2, h - 9), (w - 3, h - 9), (w - 6, h - 3), (5, h - 3)], RD(6))
        c.rect(cx - 4, h - 15, cx + 3, h - 10, G(10))
        c.rect(cx - 1, 3, cx, h - 15, G(3))
        c.line(0, h - 1, w - 1, h - 1, BL(6))
    elif obj == "vehicles":
        c.rect(2, 8, w - 9, h - 6, GN(6))
        c.rect(w - 9, 4, w - 3, h - 6, GN(5))
        c.rect(w - 8, 6, w - 4, 9, G(10))
        c.rect(4, 4, 6, 8, G(2))
        for x in (5, 11, w - 6):
            c.circle(x, h - 4, 2.5, G(2))
    elif obj == "trees":
        c.circle(cx, cy - 2, 8, GN(6))
        c.circle(cx - 3, cy - 4, 4, GN(8))
        c.rect(cx - 1, cy + 5, cx + 1, h - 1, BR(3))
    elif obj == "snow":
        for a in range(3):
            ang = a * math.pi / 3
            c.line(cx - 8 * math.cos(ang), cy - 8 * math.sin(ang), cx + 8 * math.cos(ang), cy + 8 * math.sin(ang), G(11))
    elif obj == "climate":
        c.circle(8, cy, 5, Y(10))
        for k in range(8):
            a = k * math.pi / 4
            c.set(8 + 8 * math.cos(a), cy + 8 * math.sin(a), Y(9))
        c.rect(w - 6, 2, w - 4, h - 5, G(10))
        c.circle(w - 4.5, h - 4, 3, RD(8))
        c.rect(w - 5, 8, w - 5, h - 5, RD(8))
    elif obj == "map":
        c.poly([(1, 3), (9, 1), (17, 3), (w - 2, 1), (w - 2, h - 3), (17, h - 1), (9, h - 3), (1, h - 1)], Y(7))
        c.line(9, 1, 9, h - 3, BR(6))
        c.line(17, 3, 17, h - 1, BR(6))
        c.line(3, 10, 14, 8, BL(7))
    elif obj == "buildings":
        c.rect(4, 10, w - 5, h - 1, G(10))
        c.poly([(1, 11), (cx, 1), (w - 2, 11)], RD(6))
        c.rect(cx - 2, h - 7, cx + 1, h - 1, BR(4))
        c.rect(7, 13, 9, 15, BL(6))
        c.rect(w - 10, 13, w - 8, 15, BL(6))
    elif obj == "construction":
        c.rect(5, 2, 6, h - 1, Y(9))
        c.line(5, 3, w - 2, 3, Y(9))
        c.line(w - 4, 3, w - 4, 12, G(2))
        c.rect(w - 6, 12, w - 3, 15, BR(6))
        c.rect(1, h - 2, 10, h - 1, G(4))
    elif obj == "industries":
        c.rect(1, 10, w - 2, h - 1, BR(5))
        for k in range(3):
            c.poly([(1 + k * 7, 10), (1 + k * 7, 5), (8 + k * 7, 10)], BR(5))
        c.rect(w - 6, 1, w - 3, 10, RD(5))
        c.circle(w - 4, 0, 2, G(9))
    elif obj == "world":
        g = g1_title.globe_pixels(w, h, w / 2, h / 2, min(w, h) / 2 - 1.5, 0.7)
        for (x, y), v in g.items():
            c.set(x, y, v)
    elif obj == "companies":
        c.rect(2, 8, w - 3, h - 1, BR(4))
        c.rect(cx - 3, 4, cx + 2, 8, BR(3))
        c.rect(2, 13, w - 3, 13, BR(2))
        c.rect(cx - 1, 12, cx, 14, Y(9))
    elif obj == "scenarios":
        c.rect(3, 2, w - 4, h - 3, Y(10))
        c.rect(1, 1, w - 2, 3, BR(6))
        c.rect(1, h - 4, w - 2, h - 2, BR(6))
        for y in range(6, h - 5, 3):
            c.line(5, y, w - 7, y, BR(4))


# ================================================================ 名稱 → 產生函式
def build():
    cat = json.loads(CATALOG.read_text())
    E = {e["name"]: e for e in cat["entries"] if e.get("name")}
    by_index = {e["i"]: e for e in cat["entries"]}
    frames = []

    def add(name, canvas):
        frames.append((E[name]["i"], canvas.frame_out()))

    add("window_resize_handle", window_resize_handle(E["window_resize_handle"]))
    add("close_button", close_button(E["close_button"]))
    add("frame_background_image", frame_background(E["frame_background_image"], False))
    add("frame_background_image_alt", frame_background(E["frame_background_image_alt"], True))
    add("tab", tab(E["tab"], False))
    add("selected_tab", tab(E["selected_tab"], True))
    add("wide_tab", tab(E["wide_tab"], False))
    frames.append((E["wide_tab"]["i"] + 1, tab(by_index[E["wide_tab"]["i"] + 1], True).frame_out()))
    add("colour_swatch_recolourable", colour_swatch(E["colour_swatch_recolourable"], "flat"))
    add("colour_swatch_recolourable_raised", colour_swatch(E["colour_swatch_recolourable_raised"], "raised"))
    add("colour_swatch_recolourable_pressed", colour_swatch(E["colour_swatch_recolourable_pressed"], "pressed"))
    for size in ("medium", "medium_bold", "small"):
        for side in ("left", "right"):
            n = f"curved_border_{side}_{size}"
            add(n, curved_border(E[n], side))
    add("volume_slider_track", slider_track(E["volume_slider_track"], False))
    add("volume_slider_thumb", slider_thumb(E["volume_slider_thumb"]))
    add("speed_control_track", slider_track(E["speed_control_track"], True))
    add("speed_control_thumb", slider_thumb(E["speed_control_thumb"]))
    for old in (True, False):
        for half, side in enumerate(("left", "right")):
            n = f"news_background_{'old' if old else 'new'}_{side}"
            add(n, news_background(E[n], old, half))
    add("progressbar_track", progress_track(E["progressbar_track"]))
    for style in (0, 1):
        for f in range(4):
            n = f"progressbar_style{style}_frame{f}"
            add(n, progress_train(E[n], f, style))
    add("scenario_completed_tick", tick_big(E["scenario_completed_tick"]))
    add("owner_jailed", owner_jailed(E["owner_jailed"]))
    add("random_map_watermark", random_map_watermark(E["random_map_watermark"]))
    add("height_map_compass", compass(E["height_map_compass"]))
    add("tool_area", tool_area(E["tool_area"]))
    for plus, n in ((False, "decrease_tool_area"), (True, "increase_tool_area")):
        add(n, plus_minus(E[n], plus, False))
        frames.append((E[n]["i"] + 1, plus_minus(by_index[E[n]["i"] + 1], plus, True).frame_out()))
    add("inline_green_up_arrow", triangle_arrow(E["inline_green_up_arrow"], True, GN(8), GN(11)))
    add("inline_red_down_arrow", triangle_arrow(E["inline_red_down_arrow"], False, RD(8), RD(11)))
    add("red_arrow_up", triangle_arrow(E["red_arrow_up"], True, RD(8), RD(11)))
    add("red_arrow_down", triangle_arrow(E["red_arrow_down"], False, RD(8), RD(11)))
    for kind in ("pause", "normal", "fast_forward", "extra_fast_forward"):
        k = {"pause": "pause", "normal": "normal", "fast_forward": "fast", "extra_fast_forward": "extra"}[kind]
        add(f"speed_{kind}", speed(E[f"speed_{kind}"], k, False))
        add(f"speed_{kind}_active", speed(E[f"speed_{kind}_active"], k, True))
    add("red_flag", flag(E["red_flag"], RD))
    add("green_flag", flag(E["green_flag"], GN))
    add("yellow_flag", flag(E["yellow_flag"], Y))
    add("plant_cluster_selected_tree", tree_icon(E["plant_cluster_selected_tree"], False))
    add("plant_cluster_random_tree", tree_icon(E["plant_cluster_random_tree"], True))
    add("town_expand", houses(E["town_expand"]))
    for kind in ("stop", "play", "next"):
        add(f"music_controls_{kind}", music(E[f"music_controls_{kind}"], kind))
    for n, e in E.items():
        if n.startswith("construction_") and n not in ("construction_straight",) and not n.startswith("construction_arrow") \
                and not n.startswith(("constructionSelection", "constructionCatchment")):
            kind = n.replace("construction_", "").replace("_hand_curve", "")
            kind = {"left": "left_curve", "right": "right_curve"}.get(kind, kind)   # 其餘：left_small、right_large、left_turnaround…
            add(n, construction_icon(e, kind))
    add("construction_straight", construction_icon(E["construction_straight"], "straight"))
    for n in ("rubbish_bin", "centre_viewport", "rotate_object", "photo_camera", "paintbrush", "stopwatch",
              "pickupFromAirport", "placeOnAirport", "pass_signal", "route_delete", "route_skip", "route_wait",
              "route_force_unload", "show_station_catchment", "refit_cargo_button", "step_back", "step_forward",
              "icon_folder", "icon_parent_folder", "company_list_dropdown_icon"):
        add(n, misc_icon(E[n], n))
    for n, e in E.items():
        if n.startswith("tab_object_") or n in ("tab_display", "tab_control", "tab_sound", "tab_miscellaneous"):
            add(n, tab_icon(e, n))
        elif n.startswith("tab_globe_") or n.startswith("tab_music_"):
            add(n, tab_icon(e, n, int(n.rsplit("_", 1)[1])))
    return frames


def sheet(path, frames):
    from PIL import Image, ImageDraw
    cat = json.loads(CATALOG.read_text())
    names = {e["i"]: e.get("name") or f"#{e['i']}" for e in cat["entries"]}
    win = {p: 0x82 + k for k, p in enumerate(PRIMARY)}        # 預覽：視窗色用藍色
    win.update({s: 0xA6 + k for k, s in enumerate(SECONDARY)})
    cells = [(names[i], f) for i, f in sorted(frames) if f[0] <= 120 and f[1] <= 60]
    cols = 10
    rows = (len(cells) + cols - 1) // cols
    im = Image.new("RGB", (cols * 72, rows * 76), (70, 75, 80))
    d = ImageDraw.Draw(im)
    for k, (n, (w, h, x, y, px)) in enumerate(cells):
        ox, oy = (k % cols) * 72 + 4, (k // cols) * 76 + 12
        d.text((ox, oy - 11), n[-13:], fill=(255, 255, 0))
        for j in range(h):
            for i in range(w):
                v = px[j * w + i]
                if v and i < 66 and j < 62:
                    im.putpixel((ox + i, oy + j), PAL[win.get(v, v)])
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    im.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(REPO / "build" / "preview" / "g1_ui.png"))
    args = ap.parse_args()
    frames = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    meta = []
    for idx, (w, h, x, y, px) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, w, h, px, bytes(255 if v else 0 for v in px), PAL)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")
    sheet(args.sheet, frames)
    print(f"寫出 {len(frames)} 張 → {OUT}；預覽 {args.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
