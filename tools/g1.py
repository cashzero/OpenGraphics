#!/usr/bin/env python3
"""g1（基礎圖形）工具。

  python3 tools/g1.py catalog "$LOCO_DATA_DIR/Data/g1.DAT" -o docs/g1-catalog.json
      從 vanilla g1.DAT 匯出**純 metadata**（每張圖的寬、高、偏移、flags、zoomOffset，不含像素），
      並依 OpenLoco 的 ImageIds.h 標上名稱與分組。只需要做一次，結果 commit 進 repo。

  .venv/bin/python tools/g1.py build -o build/placeholders/base/Data/g1.DAT [--catalog docs/g1-catalog.json]
      依 catalog 產生 placeholder g1（不需要 vanilla 檔案，CI 也能跑）：
      - 調色盤圖（flags 含 isR8G8B8Palette）：以 palettes/locopal.act 填入。
      - 調色盤對照表（paletteMap*，256 bytes）與文字顏色表（text_palette）：依調色盤**計算**（不是美術，也不複製
        vanilla 資料）。公司色對照表把 primary remap 換成該顏色的 12 階；半透明對照表把每個顏色與色調混合後取最近色；
        用途不明的 Unk* 用恆等對照（不改色）。
      - 地形遮罩：surfaceSmooth*（相鄰地塊貼圖的過渡帶）、cliffEdge*Mask*（懸崖面各段的形狀）與
        snowMaskCoverage*（部分積雪）。OpenLoco 以
        「g1 圖 AND 貼圖」繪製（SoftwareDrawingContext drawMaskedZoom），所以這些圖必須是 0xFF／0 的遮罩；
        依地塊幾何計算（坡形取 repo 內 OG_GRASS1 的 19 種坡形 alpha，邊的編號與高度依 OpenLoco PaintSurface.cpp）。
      - 字型字形（characters_*）：用 DejaVu 字型畫出對應字元，像素用 text remap index 1（遊戲會換成文字顏色）。
      - 其他圖：深色外框 + 灰色底的方塊，尺寸、偏移、flags 與 vanilla 相同。
      - base/g1/**/sprites.json 列出的 index 以正式美術取代（M4；PNG 由 tools/gen/g1_*.py 產生）。

g1 檔案格式（OpenLoco Graphics/Gfx.cpp loadG1）：G1Header{numEntries, totalSize} + G1Element32 × N + 圖像資料。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO / "docs" / "g1-catalog.json"
IMAGE_IDS_H = REPO.parent / "OpenLoco" / "src" / "OpenLoco" / "include" / "OpenLoco" / "Graphics" / "ImageIds.h"
FONT_PATHS = {
    "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}
FONT_GROUPS = {  # ImageIds.h 中各字型第一個字元（空白）的名稱 → (字重)
    "characters_medium_normal": "regular",
    "characters_medium_bold": "bold",
    "characters_small": "regular",
    "characters_large": "bold",
}
C_BORDER = 0x0C   # black2
C_FILL = 0x12     # 中灰
C_TEXT = 0x01     # textRemap0：遊戲繪製文字時換成文字顏色


# 31 種公司色（OpenLoco Colour enum 順序）→（調色盤色階起點, 明暗位移）；沒有專屬色階的顏色用最接近的色階加減幾階
RAMPS = {"black": 0x0A, "mutedOliveGreen": 0x16, "mutedDarkYellow": 0x22, "yellow": 0x2E, "mutedDarkRed": 0x3A,
         "mutedGrassGreen": 0x46, "mutedAvocadoGreen": 0x52, "green": 0x5E, "mutedOrange": 0x6A, "mutedPurple": 0x76,
         "blue": 0x82, "mutedSeaGreen": 0x8E, "purple": 0x9A, "red": 0xA6, "orange": 0xB2, "mutedDarkTeal": 0xBE,
         "pink": 0xCA, "brown": 0xD6}
COLOURS = [  # (名稱, 色階, 位移)
    ("black", "black", -3), ("grey", "black", 0), ("white", "black", 3), ("mutedDarkPurple", "mutedPurple", -2),
    ("mutedPurple", "mutedPurple", 0), ("purple", "purple", 0), ("darkBlue", "blue", -2), ("blue", "blue", 0),
    ("mutedDarkTeal", "mutedDarkTeal", 0), ("mutedTeal", "mutedDarkTeal", 2), ("darkGreen", "green", -3),
    ("mutedSeaGreen", "mutedSeaGreen", 0), ("mutedGrassGreen", "mutedGrassGreen", 0), ("green", "green", 0),
    ("mutedAvocadoGreen", "mutedAvocadoGreen", 0), ("mutedOliveGreen", "mutedOliveGreen", 0), ("yellow", "yellow", 0),
    ("darkYellow", "yellow", -2), ("orange", "orange", 0), ("amber", "mutedDarkYellow", 1), ("darkOrange", "orange", -2),
    ("mutedDarkYellow", "mutedDarkYellow", 0), ("mutedYellow", "mutedDarkYellow", 2), ("brown", "brown", 0),
    ("mutedOrange", "mutedOrange", 0), ("mutedDarkRed", "mutedDarkRed", 0), ("darkRed", "red", -2), ("red", "red", 0),
    ("darkPink", "pink", -2), ("pink", "pink", 0), ("mutedRed", "mutedDarkRed", 2),
]
PRIMARY_REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
DRAWABLE = [i for i in range(10, 246) if i != 0xF5]


def colour_shade(name: str, shade: int) -> int:
    for n, ramp, shift in COLOURS:
        if n.lower() == name.lower():
            return RAMPS[ramp] + max(0, min(11, shade + shift))
    raise KeyError(name)


def nearest(palette, rgb) -> int:
    r, g, b = rgb
    return min(DRAWABLE, key=lambda i: (palette[i][0] - r) ** 2 + (palette[i][1] - g) ** 2 + (palette[i][2] - b) ** 2)


def palette_map(name: str, palette) -> bytes:
    """依名稱計算 256 bytes 的調色盤對照表。"""
    m = list(range(256))
    base = name[len("paletteMap"):]
    if base.startswith("Translucent") and base[-1] in "012":
        colour, variant = base[len("Translucent"):-1], int(base[-1])
        tint = palette[colour_shade(colour, 6)]
        alpha, light = [(0.45, 0.75), (0.5, 1.0), (0.4, 1.2)][variant]
        cache = {}
        for i in range(256):
            src = palette[i]
            key = src
            if key not in cache:
                cache[key] = nearest(palette, tuple(min(255, (src[k] * (1 - alpha) + tint[k] * alpha) * light) for k in range(3)))
            m[i] = cache[key]
        return bytes(m)
    if base in SELECTION_MAPS or base in EFFECT_MAPS:
        return special_map(base, palette)
    try:
        for k, idx in enumerate(PRIMARY_REMAP):
            m[idx] = colour_shade(base, k)
    except KeyError:
        pass                                   # 其餘 Unk*／Clear：恆等對照
    return bytes(m)


# ---- 用途已查明的 Unk 對照表（OpenLoco Paint/PaintSurface.cpp、Gfx.cpp、Station.cpp、Widget.cpp）---------
# 地圖選取框（PaintSurface.cpp paintSurface*Selection）以 ImageId(圖, ExtColour) 繪製：像素 = 對照表[來源]，0 = 不畫。
# 選取框圖（tools/gen/g1_overlays.py）用 12 個「標記色號」（primary remap 的 12 階）把圖塊分區：
#   角／全格（constructionSelectionCorners）C0–C3、邊（Edges）E0–E3、四分之一（Quads）Q0–Q3；
# 每張對照表只讓被選中的那一區顯示成亮色，其餘標記變成 0（不畫）。
# 這幾張表也可能被產業陰影（Colours::getShadow(產業顏色)，半透明 dst 模式）用到，所以其他色號一律做成變暗。
MARK_C = PRIMARY_REMAP[0:4]
MARK_E = PRIMARY_REMAP[4:8]
MARK_Q = PRIMARY_REMAP[8:12]
SELECTION_MAPS = {  # 名稱: (顯示的標記, 顏色)
    "Unk21": ([MARK_C[0]], "yellow"), "Unk22": ([MARK_C[1], MARK_E[0]], "yellow"),
    "Unk23": ([MARK_C[2], MARK_E[1]], "yellow"), "Unk24": ([MARK_C[3], MARK_E[2]], "yellow"),
    "Unk25": (MARK_C + [MARK_E[3]], "yellow"),             # 也是整格選取（paintSurfaceFullTileSelection）
    "Unk26": (MARK_C, "blue"),                              # 水面整格選取
    "Unk2B": (MARK_C, "orange"),
    "Unk27": ([MARK_Q[0]], "yellow"), "Unk28": ([MARK_Q[1]], "yellow"),
    "Unk29": ([MARK_Q[2]], "yellow"), "Unk2A": ([MARK_Q[3]], "yellow"),
}
# 其他效果：(模式, 參數)；src = 改寫來源色（ImageId(圖, ExtColour)），dst = 半透明疊在畫面上（withTranslucency）
EFFECT_MAPS = {
    "Unk2C": ("ghost", None),                  # 施工預覽（src）：淡藍灰
    "Unk31": ("tint", ((150, 185, 235), 0.5, 1.05)),   # 施工預覽（設定 constructionMarker，dst）
    "Unk2E": ("tint", ((140, 200, 215), 0.30, 1.08)),  # translucentGlass1（車站玻璃，不可換色時）
    "Unk2F": ("tint", ((120, 175, 200), 0.45, 1.05)),  # translucentGlass2
    "Unk30": ("tint", ((170, 215, 225), 0.22, 1.12)),  # translucentGlass0（地圖格線）
    "Unk32": ("tint", ((20, 25, 40), 0.42, 1.0)),      # 建築／產業陰影
    "Unk33": ("tint", ((0, 0, 0), 0.2, 1.0)),          # 半透明分頁
    "Unk34": ("tint", ((10, 10, 20), 0.5, 1.0)),       # 半透明視窗底（主選單按鈕等）
    "Unk74": ("burnt", None),                  # 特殊狀態車輛（src）：偏暗、去飽和
}


def special_map(base: str, palette) -> bytes:
    m = list(range(256))
    cache = {}

    def mapped(i, f):
        key = palette[i]
        if key not in cache:
            cache[key] = nearest(palette, tuple(max(0, min(255, v)) for v in f(key)))
        return cache[key]
    if base in SELECTION_MAPS:
        show, colour = SELECTION_MAPS[base]
        cache.clear()
        for i in range(1, 256):
            m[i] = mapped(i, lambda c: tuple(v * 0.62 for v in c))
        for mk in MARK_C + MARK_E + MARK_Q:
            m[mk] = 0
        for mk in show:
            m[mk] = colour_shade(colour, 9)
        m[0] = 0
        return bytes(m)
    mode, arg = EFFECT_MAPS[base]
    for i in range(1, 256):
        if mode == "ghost":
            lum = 0.3 * palette[i][0] + 0.59 * palette[i][1] + 0.11 * palette[i][2]
            m[i] = mapped(i, lambda c, lum=lum: (95 + 0.55 * lum, 120 + 0.55 * lum, 160 + 0.45 * lum))
            cache.clear()
        elif mode == "burnt":
            lum = 0.3 * palette[i][0] + 0.59 * palette[i][1] + 0.11 * palette[i][2]
            m[i] = mapped(i, lambda c, lum=lum: (0.55 * lum + 8, 0.5 * lum + 6, 0.48 * lum + 6))
            cache.clear()
        else:
            tint, alpha, light = arg
            m[i] = mapped(i, lambda c: tuple((c[k] * (1 - alpha) + tint[k] * alpha) * light for k in range(3)))
    m[0] = 0
    return bytes(m)


def text_palette(n: int) -> bytes:
    """文字顏色表：每種顏色 4 bytes（主色、兩個外框／陰影色、保留）。"""
    out = bytearray()
    for c in range(n):
        name = COLOURS[c % len(COLOURS)][0]
        # 主色、外框（字形 index 2）、外框／右下陰影（index 3）；兩個外框都用深色，地圖上的城鎮名才清楚
        out += bytes([colour_shade(name, 6), colour_shade(name, 1), colour_shade(name, 0), 0])
    return bytes(out)


# ---- 地形遮罩（PaintSurface.cpp）----------------------------------------------------------------
# displaySlope → 四角高度（T, R, B, L），由 kSlopeToDisplaySlope 與 kCornerHeights 推得
SLOPE_CORNERS = {0: (0, 0, 0, 0), 1: (0, 0, 0, 1), 2: (0, 0, 1, 0), 3: (0, 0, 1, 1), 4: (0, 1, 0, 0), 5: (0, 1, 0, 1),
                 6: (0, 1, 1, 0), 7: (0, 1, 1, 1), 8: (1, 0, 0, 0), 9: (1, 0, 0, 1), 10: (1, 0, 1, 0), 11: (1, 0, 1, 1),
                 12: (1, 1, 0, 0), 13: (1, 1, 0, 1), 14: (1, 1, 1, 0), 15: (2, 1, 0, 1), 16: (0, 1, 2, 1),
                 17: (1, 0, 1, 2), 18: (1, 2, 1, 0)}
# 過渡邊（rotation 0 的畫面方向）：0 = 左下（L–B）、1 = 右下（B–R）、2 = 左上（T–L）、3 = 右上（T–R）
SMOOTH_EDGES = {0: ("L", "B"), 1: ("B", "R"), 2: ("T", "L"), 3: ("T", "R")}
SMOOTH_WIDTH = 10.0                    # 過渡帶寬度（垂直像素）
BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
MASK_ON = 0xFF
_slope_alpha_cache: dict | None = None


def slope_alpha() -> dict:
    """displaySlope → (x_offset, y_offset, w, h, alpha bytes)，取自 OG_GRASS1 的坡形圖（image 285 + slope）。"""
    global _slope_alpha_cache
    if _slope_alpha_cache is None:
        obj = dat.read_dat(Path(__file__).resolve().parents[1] / "objects/VanillaReplacements/Land/GRASS1/OG_GRASS1.dat")
        table = obj.image_table()
        _slope_alpha_cache = {}
        for d in range(19):
            w, h, x, y, _px, al = dat.decode_sprite(table, 285 + d)
            _slope_alpha_cache[d] = (x, y, w, h, bytes(al))
    return _slope_alpha_cache


def corners(slope: int) -> dict:
    t, r, b, l = SLOPE_CORNERS[slope]
    return {"T": (0.0, 0.0 - 16 * t), "R": (32.0, 16.0 - 16 * r), "B": (0.0, 32.0 - 16 * b), "L": (-32.0, 16.0 - 16 * l)}


def surface_smooth_mask(edge: int, slope: int, e: dict) -> bytes:
    """相鄰地塊貼圖過渡遮罩：
    - 背面退化的水平邊（slope 2/10 的 e0/e1、slope 5/7 的 e2/e3、以及空坡 slope 16）完全留空（0 像素），
      消除草地與沙地斜坡交界的亮三角 glitch。
    - 其餘邊使用約 3.4px 寬的有機點描（非機械式 Bayer 棋盤格），常規邊約 36–44 像素、陡邊約 22–26 像素，
      讓相鄰地形交界柔順自然。
    """
    w, h = e["w"], e["h"]
    out = bytearray(w * h)
    if slope == 16:
        return bytes(out)
    t_h, r_h, b_h, l_h = SLOPE_CORNERS[slope]
    # 背面退化的雙水平邊不畫過渡帶（對應原版為 0 像素的 8 個坡面邊）
    if edge in (0, 1) and b_h > l_h and b_h > r_h:
        return bytes(out)
    if edge in (2, 3) and t_h < l_h and t_h < r_h:
        return bytes(out)

    ax, ay, aw, ah, alpha = slope_alpha()[slope]
    # 像素中心對齊 64×31 地塊菱形邊界（避免 B=32 偏離實際底邊 1.5px 導致 e0/e1 過窄）
    c = {
        "T": (0.0, 0.5 - 16 * t_h),
        "R": (31.5, 15.5 - 16 * r_h),
        "B": (0.0, 30.5 - 16 * b_h),
        "L": (-31.5, 15.5 - 16 * l_h),
    }
    (px, py), (qx, qy) = sorted((c[SMOOTH_EDGES[edge][0]], c[SMOOTH_EDGES[edge][1]]))
    dx, dy = qx - px, qy - py
    elen = math.hypot(dx, dy)
    # 沿邊線朝圖塊內部的單位法向量（由圖塊重心決定方向）
    mid_x = sum(v[0] for v in c.values()) / 4.0
    mid_y = sum(v[1] for v in c.values()) / 4.0
    nx, ny = -dy / elen, dx / elen
    if (mid_x - (px + qx) / 2.0) * nx + (mid_y - (py + qy) / 2.0) * ny < 0:
        nx, ny = -nx, -ny

    # 單邊水平（如 slope 1 e2）或陡邊略窄（~24px），標準 2:1 斜邊 ~38–42px
    band_w = 2.6 if (abs(dy) < 1e-6 or abs(dy) > 18.0) else 3.6
    seed_base = edge * 97 + slope * 13 + 31

    for j in range(h):
        for i in range(w):
            sx, sy = e["x"] + i, e["y"] + j
            u, v = sx - ax, sy - ay
            if not (0 <= u < aw and 0 <= v < ah and alpha[v * aw + u]):
                continue
            cx, cy = sx + 0.5, sy + 0.5
            t = ((cx - px) * dx + (cy - py) * dy) / (elen * elen)
            if t < -0.02 or t > 1.02:
                continue
            d_in = (cx - px) * nx + (cy - py) * ny
            if d_in < -0.5 or d_in > band_w + 1.0:
                continue
            end_taper = min(1.0, min(t, 1.0 - t) / 0.14) if 0.0 < t < 1.0 else 0.35
            local_w = band_w * (0.60 + 0.40 * end_taper)
            # 零均值高頻有機微擾，讓四條邊像素數均勻自然（~36–44 px）
            wobble = (_hash01(sx // 2, sy // 2, seed_base) - 0.5) * 1.1
            eff_d = max(0.0, d_in + wobble)
            prob = max(0.0, 1.0 - eff_d / local_w) ** 1.25 * 0.72
            jitter = 0.72 * _hash01(sx, sy, seed_base + 7) + 0.28 * (((sx ^ sy) & 1) * 0.5 + 0.25)
            if prob > jitter:
                out[j * w + i] = MASK_ON
    return bytes(out)


# 懸崖面遮罩：[0] 整段；[1]/[2] 頂端三角形（end0／end1 較高）；[3]/[4] 底端被鄰格斜坡蓋住（鄰格 end0／end1 較高）
# 每項為（頂端高度 end0, end1）、（底端高度 end0, end1），單位為一段（16 px）
CLIFF_PROFILES = [((1, 1), (0, 0)), ((1, 0), (0, 0)), ((0, 1), (0, 0)), ((1, 1), (1, 0)), ((1, 1), (0, 1))]


def cliff_edge_mask(family: int, variant: int, e: dict) -> bytes:
    """family 0：由左上往右下的面（edge 0／3，end0 在左）；family 1：由左下往右上的面（edge 1／2，end0 在右）。"""
    w, h = e["w"], e["h"]
    (t0, t1), (b0, b1) = CLIFF_PROFILES[variant]
    out = bytearray(w * h)
    for i in range(w):
        f = (i + 0.5) / w                              # 0 = 左端、1 = 右端
        if family == 0:
            base = 15.0 + (i + 0.5) / 2                # 高度 0 時該欄的下緣
            top_h, bot_h = t0 + (t1 - t0) * f, b0 + (b1 - b0) * f
        else:
            base = 15.0 + (w - i - 0.5) / 2
            top_h, bot_h = t1 + (t0 - t1) * f, b1 + (b0 - b1) * f
        y_top, y_bot = base - 16 * top_h, base - 16 * bot_h
        for j in range(h):
            if y_top <= j + 0.5 <= y_bot + 0.5:
                out[j * w + i] = MASK_ON
    return bytes(out)


def _hash01(x: int, y: int, seed: int) -> float:
    h = (x * 374761393 + y * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 0xFFFF


def _value_noise(x: float, y: float, cell: float, seed: int) -> float:
    gx, gy = x / cell, y / cell
    x0, y0 = int(gx // 1), int(gy // 1)
    fx, fy = gx - x0, gy - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash01(x0, y0, seed), _hash01(x0 + 1, y0, seed)
    c, d = _hash01(x0, y0 + 1, seed), _hash01(x0 + 1, y0 + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def snow_mask(coverage: int, slope: int, e: dict) -> bytes:
    """部分積雪遮罩（coverage 1–4）：依坡面四角實際高度線性插值局部高程 z_local ∈ [0, 2]，
    計算相對於雪線的有效積雪高度 eff_h = (coverage - 2.0) + z_local：
    - coverage 1（低於雪線 2 階）：平地與一般單階斜坡完全無雪（0 像素，徹底消除農田上的異常白點），
      只有雙階陡角（slope 15/17/18）最高尖角微微覆雪。
    - coverage 2（低於雪線 1 階）：平地 0 像素，斜坡較高側自然積雪。
    - coverage 3（雪線平地）：平地約 32% 細緻薄雪，斜坡隨高度漸濃。
    - coverage 4（雪線以上 1 階）：平地約 68% 積雪，高坡接近全覆蓋。
    """
    w, h = e["w"], e["h"]
    out = bytearray(w * h)
    if slope == 16:
        return bytes(out)
    t_h, r_h, b_h, l_h = SLOPE_CORNERS[slope]
    # 若整個坡面最高角仍低於雪線（eff_h <= 0），直接回傳全透明 0 像素
    if (coverage - 2) + max(t_h, r_h, b_h, l_h) <= 0:
        return bytes(out)

    ax, ay, aw, ah, alpha = slope_alpha()[slope]
    yT = 0.5 - 16.0 * t_h
    yR = 15.5 - 16.0 * r_h
    yB = 30.5 - 16.0 * b_h
    yL = 15.5 - 16.0 * l_h

    for j in range(h):
        for i in range(w):
            sx, sy = e["x"] + i, e["y"] + j
            u, v = sx - ax, sy - ay
            if not (0 <= u < aw and 0 <= v < ah and alpha[v * aw + u]):
                continue
            cx, cy = sx + 0.5, sy + 0.5
            if cx <= 0.0:
                f = max(0.0, min(1.0, (cx + 31.5) / 31.5))
                y_top = (1.0 - f) * yL + f * yT
                y_bot = (1.0 - f) * yL + f * yB
                h_top = (1.0 - f) * l_h + f * t_h
                h_bot = (1.0 - f) * l_h + f * b_h
            else:
                f = max(0.0, min(1.0, cx / 31.5))
                y_top = (1.0 - f) * yT + f * yR
                y_bot = (1.0 - f) * yB + f * yR
                h_top = (1.0 - f) * t_h + f * r_h
                h_bot = (1.0 - f) * b_h + f * r_h
            gv = max(0.0, min(1.0, (cy - y_top) / max(y_bot - y_top, 1e-4)))
            z_local = (1.0 - gv) * h_top + gv * h_bot

            eff_h = (coverage - 2.0) + z_local
            if eff_h <= 0.04:
                continue
            if eff_h <= 1.0:
                prob = 0.32 * (eff_h ** 1.35)
            elif eff_h <= 2.0:
                prob = 0.32 + 0.36 * (eff_h - 1.0)
            else:
                prob = min(0.97, 0.68 + 0.29 * (eff_h - 2.0))

            # 細緻有機雪粉＋小尺度雪堆雜訊，避免重複大塊白斑
            n = 0.44 * _value_noise(sx, sy * 2.0, 5.5, 7 + slope * 17) + 0.56 * _hash01(sx, sy, 11 + coverage * 31)
            if n < prob:
                out[j * w + i] = MASK_ON
    return bytes(out)


def terrain_mask(name: str, e: dict) -> bytes | None:
    m = re.fullmatch(r"snowMaskCoverage(\d)Slope(\d+)", name)
    if m:
        return snow_mask(int(m.group(1)), int(m.group(2)), e)
    m = re.fullmatch(r"surfaceSmooth(\d)Slope(\d+)", name)
    if m:
        return surface_smooth_mask(int(m.group(1)), int(m.group(2)), e)
    m = re.fullmatch(r"cliffEdge(\d)(?:Underground)?MaskSlope(\d)", name)
    if m:
        return cliff_edge_mask(int(m.group(1)), int(m.group(2)), e)
    return None


def group_of(name: str) -> str:
    for g in FONT_GROUPS:
        if name.startswith(g + "_"):
            return g
    return re.sub(r"\d+$", "", name)


def cmd_catalog(args) -> int:
    raw = Path(args.g1).read_bytes()
    n, total = struct.unpack_from("<II", raw, 0)
    names: dict[int, list[str]] = {}
    if IMAGE_IDS_H.exists():
        for nm, v in re.findall(r"constexpr uint32_t (\w+) = (\d+);", IMAGE_IDS_H.read_text()):
            names.setdefault(int(v), []).append(nm)
    font_base: dict[str, int] = {}
    for idx, nms in names.items():
        for nm in nms:
            for g in FONT_GROUPS:
                if nm == g + "_space":
                    font_base[g] = idx
    entries = []
    group = ""
    for i in range(n):
        _off, w, h, x, y, f, z = struct.unpack_from("<IhhhhHh", raw, 8 + 16 * i)
        e = {"i": i, "w": w, "h": h, "x": x, "y": y, "f": f, "z": z}
        if i in names:
            e["name"] = names[i][0]
            if len(names[i]) > 1:
                e["alias"] = names[i][1:]
            group = group_of(names[i][0])
        for g, b in font_base.items():
            if b <= i < b + 224:
                group = g
                e["char"] = 32 + (i - b)
        e["group"] = group or "unnamed"
        entries.append(e)
    out = {
        "source": "Chris Sawyer's Locomotion Data/g1.DAT（只含 metadata，不含任何像素資料）",
        "count": n,
        "fonts": {g: {"base": b, "weight": FONT_GROUPS[g]} for g, b in sorted(font_base.items(), key=lambda t: t[1])},
        "entries": entries,
    }
    lines = [json.dumps({k: v for k, v in out.items() if k != "entries"}, ensure_ascii=False)[:-1] + ', "entries": [']
    lines += [json.dumps(e, ensure_ascii=False) + ("," if k < len(entries) - 1 else "") for k, e in enumerate(entries)]
    lines.append("]}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    groups = sorted({e["group"] for e in entries})
    print(f"寫出 {args.output}：{n} 張圖、{len(names)} 個具名 index、{len(groups)} 個分組、字型 {list(font_base)}")
    return 0


def box_pixels(w: int, h: int) -> bytes:
    px = bytearray(w * h)
    for yy in range(h):
        for xx in range(w):
            edge = w < 3 or h < 3 or xx in (0, w - 1) or yy in (0, h - 1)
            px[yy * w + xx] = C_BORDER if edge else C_FILL
    return bytes(px)


class GlyphRenderer:
    def __init__(self):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            sys.exit("需要 Pillow：請用 .venv/bin/python 執行")
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.cache = {}

    def font(self, weight: str, px: int):
        key = (weight, px)
        if key not in self.cache:
            self.cache[key] = self.ImageFont.truetype(FONT_PATHS[weight], px)
        return self.cache[key]

    def render(self, ch: int, w: int, h: int, weight: str) -> bytes:
        if w <= 0 or h <= 0:
            return b""
        try:
            text = bytes([ch]).decode("latin1")
        except Exception:  # noqa: BLE001
            text = "?"
        if not text.isprintable() or text == " ":
            return bytes(w * h)
        img = self.Image.new("L", (w, h), 0)
        draw = self.ImageDraw.Draw(img)
        size = max(h - 1, 6)
        f = self.font(weight, size)
        left, top, right, bottom = f.getbbox(text)
        # 以字形高度置中，水平靠左（字寬由 g1 metadata 決定）
        ox = -left
        oy = (h - (bottom - top)) // 2 - top
        draw.text((ox, oy), text, fill=255, font=f)
        data = img.tobytes()
        return bytes(C_TEXT if v >= 110 else 0 for v in data)


BASE_G1 = REPO / "base" / "g1"


def load_overrides(root: Path) -> dict[int, tuple[int, int, int, int, bytes]]:
    """base/g1/**/sprites.json（[{index, path, x, y}]，PNG 為調色盤索引、0 = 透明）→ {index: (w, h, x, y, pixels)}。"""
    import pack  # 需要 Pillow
    palette = dat.load_palette()
    out = {}
    for meta in sorted(root.glob("**/sprites.json")):
        for m in json.loads(meta.read_text(encoding="utf-8")):
            w, h, px = pack.load_indices(meta.parent / m["path"], palette)
            if m["index"] in out:
                sys.exit(f"g1 index {m['index']} 重複：{meta}")
            out[m["index"]] = (w, h, m["x"], m["y"], px)
    return out


def cmd_build(args) -> int:
    cat = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    palette = dat.load_palette()
    glyphs = GlyphRenderer()
    overrides = load_overrides(Path(args.base)) if args.base else {}
    entries = []
    blob = bytearray()
    cache: dict[tuple, int] = {}
    for e in cat["entries"]:
        w, h, f = e["w"], e["h"], e["f"]
        if f & dat.G1_IS_PALETTE:
            start = e["x"]
            data = bytes(c for k in range(start, start + w) for c in reversed(palette[k]))  # BGR
            entries.append(dat.G1Entry(len(blob), w, h, e["x"], e["y"], f, e["z"]))
            blob += data
            continue
        name = e.get("name", "")
        if name.startswith("paletteMap") or name == "text_palette":
            # 資料表：原樣存放（不加透明旗標），內容依調色盤計算
            data = palette_map(name, palette) if name.startswith("paletteMap") else text_palette(e["h"])
            data = data[: w * h].ljust(w * h, b"\x00")
            entries.append(dat.G1Entry(len(blob), w, h, e["x"], e["y"], f, e["z"]))
            blob += data
            continue
        mask = terrain_mask(name, e)
        if mask is not None:
            # 遮罩：未壓縮 bitmap（drawMaskedZoom 不支援 RLE）。不提供縮小版（去掉 hasZoomSprites），
            # 縮小顯示時 OpenLoco 直接以全尺寸遮罩跳格取樣，與貼圖保持對齊
            entries.append(dat.G1Entry(len(blob), w, h, e["x"], e["y"], f & ~(dat.G1_IS_RLE | dat.G1_HAS_ZOOM), 0))
            blob += mask
            continue
        keep = f & (dat.G1_HAS_ZOOM | dat.G1_NO_ZOOM_DRAW | dat.G1_DUPLICATE_PREVIOUS)
        if not name and e["i"] not in overrides and args.base:
            # 沒有名稱的影像：OpenLoco 的 ImageIds.h 沒有引用（vanilla 遺留的圖、第 5 套字型、各種尺寸變體…），
            # 縮小版（0–303）在正式版也不再使用 → 1×1 透明（M4）
            entries.append(dat.G1Entry(len(blob), 1, 1, 0, 0, dat.G1_HAS_TRANSPARENCY, 0))
            blob += b"\x00"
            continue
        if e["i"] in overrides:                            # 正式美術（base/g1）
            ow, oh, ox, oy, data = overrides[e["i"]]
            # 不提供縮小版：縮小顯示時由 OpenLoco 直接跳格取樣（同地形遮罩）
            entries.append(dat.G1Entry(len(blob), ow, oh, ox, oy, (keep & ~dat.G1_HAS_ZOOM) | dat.G1_HAS_TRANSPARENCY, 0))
            blob += data
            continue
        if "char" in e:
            data = glyphs.render(e["char"], w, h, cat["fonts"][e["group"]]["weight"])
            key = None
        else:
            key = (w, h)
            data = None
        if key is not None and key in cache:
            off = cache[key]
        else:
            if data is None:
                data = box_pixels(max(w, 0), max(h, 0))
            off = len(blob)
            blob += data
            if key is not None:
                cache[key] = off
        entries.append(dat.G1Entry(off, w, h, e["x"], e["y"], keep | dat.G1_HAS_TRANSPARENCY, e["z"]))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = struct.pack("<II", len(entries), len(blob))
    body += b"".join(struct.pack("<IhhhhHh", x.offset, x.width, x.height, x.x_offset, x.y_offset, x.flags, x.zoom_offset) for x in entries)
    out.write_bytes(body + bytes(blob))
    print(f"寫出 placeholder g1：{out}（{len(entries)} 張圖，{len(body) + len(blob)} bytes）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("catalog")
    p.add_argument("g1")
    p.add_argument("-o", "--output", default=str(DEFAULT_CATALOG))
    p.set_defaults(func=cmd_catalog)
    p = sub.add_parser("build")
    p.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--base", default=str(BASE_G1), help="正式美術目錄（base/g1）；空字串 = 全部用 placeholder")
    p.set_defaults(func=cmd_build)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
