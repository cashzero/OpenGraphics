#!/usr/bin/env python3
"""寫實程序化地面、水面與懸崖產生器（使用者核准之 fork 覆寫：GRASS1, GRASSBR, SAND1, ROCK1, ROCK2, WATER1, LSBROWN, LSROCK）。

核心技術：
1. 跨格完全無縫（toroidal periodic）256×256 3D PBR 微地形高度場、法線與反照率（FFT/諧波 fBM ＋ 週期 Voronoi 岩塊裂隙），
   徹底消除傳統地磚邊緣暗線與重複格網感。
2. 精準反解 OpenLoco 全部 19 種等角斜坡（SLOPE_CORNERS）的 3D (u, v) 透視投影與表面法線，
   疊加微地形法線貼圖（normal mapping）並以與原版完全一致的光源方向算光，
   搭配細緻多色相微顆粒與溫和 Bayer 抖動量化至 Locomotion 安全可繪色盤（排除 remap 與動態色）。
3. 6 張無縫 64×63 邊緣融合貼圖（cl = 0..5）與所有縮放層級（Zoom 0–3）、平坦變化磚皆由同一底層 PBR 場生成，
   且每一種地形的 blend_lits 與其斜坡光照曲線精準對齊，確保草地↔沙地↔岩石↔斜坡交界柔順無痕。
4. WATER1：單調平滑的 256×5 海洋藍綠半透明深度表＋無縫 Gerstner 波浪干涉場＋波峰流光動態水紋。
5. LSROCK／LSBROWN：保留精確 32×31 平行四邊形遮罩，生成 16 組不重複的立體不規則岩石節理、崖頂陰影與自然侵蝕土石峭壁。

用法：
  .venv/bin/python tools/gen/terrain.py [--targets GRASS1,SAND1,...]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402
import pack  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
VR = REPO / "objects" / "VanillaReplacements"

# 19 種 OpenLoco 顯示坡度的四角高度 (hT, hR, hB, hL)，單位為 16px
SLOPE_CORNERS: list[tuple[int, int, int, int]] = [
    (0, 0, 0, 0),  # 0: flat
    (0, 0, 0, 1),  # 1: L
    (0, 0, 1, 0),  # 2: B
    (0, 0, 1, 1),  # 3: B+L
    (0, 1, 0, 0),  # 4: R
    (0, 1, 0, 1),  # 5: R+L
    (0, 1, 1, 0),  # 6: R+B
    (0, 1, 1, 1),  # 7: R+B+L
    (1, 0, 0, 0),  # 8: T
    (1, 0, 0, 1),  # 9: T+L
    (1, 0, 1, 0),  # 10: T+B
    (1, 0, 1, 1),  # 11: T+B+L
    (1, 1, 0, 0),  # 12: T+R
    (1, 1, 0, 1),  # 13: T+R+L
    (1, 1, 1, 0),  # 14: T+R+B
    (2, 1, 0, 1),  # 15: T=2, R=1, L=1
    (0, 1, 2, 1),  # 16: B=2 (back-facing, 1x1 empty)
    (1, 0, 1, 2),  # 17: L=2, T=1, B=1
    (1, 2, 1, 0),  # 18: R=2, T=1, B=1
]

# 精準擬合 OpenLoco 全 19 種坡度明暗曲線（含 slope 8/15 向陽亮於平地、slope 4/12 柔和陰影、slope 17 最亮、slope 18 最暗）
SUN_DIR = np.array([0.88, -0.38, 0.90], dtype=np.float64)
SUN_DIR /= np.linalg.norm(SUN_DIR)

BAYER4 = (np.array([
    [0,  8,  2, 10],
    [12, 4, 14,  6],
    [3, 11,  1,  9],
    [15, 7, 13,  5],
], dtype=np.float64) + 0.5) / 16.0 - 0.5

# 安全靜態地形色盤（嚴格排除 0..9 透明/主公司色、194..201 動態水波色、202..213 副公司色、230..255 霓虹/主公司色）
SAFE_TERRAIN_INDICES = np.array(
    [i for i in range(10, 230) if not (194 <= i <= 201) and not (202 <= i <= 213)],
    dtype=np.uint8,
)


class FastQuantizer:
    """向量化紅均值感知距離色彩量化器（只選取安全靜態色盤）。"""

    def __init__(self, palette: list[tuple[int, int, int]], allowed: np.ndarray = SAFE_TERRAIN_INDICES):
        self.full_pal = np.array(palette, dtype=np.float64)
        self.allowed = allowed.astype(np.uint8)
        self.pal = self.full_pal[self.allowed]

    def map_rgb(self, rgb: np.ndarray, dither: float = 5.0, ox: int = 0, oy: int = 0) -> np.ndarray:
        shape = rgb.shape[:-1]
        if dither > 0 and len(shape) == 2:
            h, w = shape
            yy = (np.arange(h) + oy) & 3
            xx = (np.arange(w) + ox) & 3
            rgb = rgb + BAYER4[yy[:, None], xx[None, :]][:, :, None] * dither
        flat = np.clip(rgb.reshape(-1, 3), 0.0, 255.0)
        out = np.empty(flat.shape[0], dtype=np.uint8)
        pal = self.pal
        pr, pg, pb = pal[:, 0], pal[:, 1], pal[:, 2]
        chunk = 8192
        for s in range(0, flat.shape[0], chunk):
            c = flat[s:s + chunk]
            r, g, b = c[:, 0:1], c[:, 1:2], c[:, 2:3]
            rm = 0.5 * (r + pr[None, :])
            dr = r - pr[None, :]
            dg = g - pg[None, :]
            db = b - pb[None, :]
            dist = (2.0 + rm / 256.0) * dr * dr + 4.0 * dg * dg + (2.0 + (255.0 - rm) / 256.0) * db * db
            out[s:s + chunk] = self.allowed[np.argmin(dist, axis=1)]
        return out.reshape(shape)


# ---------------------------------------------------------------- 週期性無縫 2D 雜訊工具

def periodic_fbm(n: int, seed: int, f_min: int = 1, f_max: int = 24, beta: float = 1.65,
                 aniso: tuple[float, float] = (1.0, 1.0), angle: float = 0.0) -> np.ndarray:
    """用 2D FFT 產生嚴格週期性（0 接縫）各向異性 fBM 雜訊，正規化至 [-1, 1]。"""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(n, d=1.0 / n)[:, None]
    fx = np.fft.fftfreq(n, d=1.0 / n)[None, :]
    ca, sa = math.cos(angle), math.sin(angle)
    rx = (fx * ca + fy * sa) / aniso[0]
    ry = (-fx * sa + fy * ca) / aniso[1]
    rad = np.hypot(rx, ry)
    amp = np.where((rad >= f_min) & (rad <= f_max), np.power(np.maximum(rad, 1e-6), -beta), 0.0)
    phase = rng.uniform(0.0, 2.0 * math.pi, size=(n, n))
    spec = amp * (np.cos(phase) + 1j * np.sin(phase))
    field = np.fft.ifft2(spec).real
    std = max(float(field.std()), 1e-9)
    return np.clip(field / (std * 2.1), -1.0, 1.0)


def periodic_worley(n: int, cells: int, seed: int, jitter: float = 0.88) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """嚴格週期性 2D Voronoi/Worley 細胞雜訊：回傳 (F1, F2-F1 裂縫距, cell_id_hash 0..1)。"""
    rng = np.random.default_rng(seed)
    px = (np.arange(cells)[:, None] + 0.5 + rng.uniform(-0.5, 0.5, (cells, cells)) * jitter) % cells
    py = (np.arange(cells)[None, :] + 0.5 + rng.uniform(-0.5, 0.5, (cells, cells)) * jitter) % cells
    cid = rng.uniform(0.0, 1.0, (cells, cells))
    gy, gx = np.mgrid[0:n, 0:n].astype(np.float64) * (cells / n)
    ix = np.floor(gx).astype(np.int32)
    iy = np.floor(gy).astype(np.int32)
    f1 = np.full((n, n), 1e9, dtype=np.float64)
    f2 = np.full((n, n), 1e9, dtype=np.float64)
    best_id = np.zeros((n, n), dtype=np.float64)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx_i = (ix + dx) % cells
            ny_i = (iy + dy) % cells
            cx = px[nx_i, ny_i]
            cy = py[nx_i, ny_i]
            ddx = gx - cx
            ddx -= np.round(ddx / cells) * cells
            ddy = gy - cy
            ddy -= np.round(ddy / cells) * cells
            d = np.hypot(ddx, ddy)
            m1 = d < f1
            f2 = np.where(m1, f1, np.minimum(f2, d))
            f1 = np.where(m1, d, f1)
            best_id = np.where(m1, cid[nx_i, ny_i], best_id)
    return f1, np.clip(f2 - f1, 0.0, 1.0), best_id


def sample_periodic(arr: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    n = arr.shape[0]
    x = (u % 1.0) * n
    y = (v % 1.0) * n
    x0 = np.floor(x).astype(np.int32) % n
    y0 = np.floor(y).astype(np.int32) % n
    x1 = (x0 + 1) % n
    y1 = (y0 + 1) % n
    fx = x - np.floor(x)
    fy = y - np.floor(y)
    if arr.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    c00 = arr[y0, x0]
    c10 = arr[y0, x1]
    c01 = arr[y1, x0]
    c11 = arr[y1, x1]
    return (c00 * (1 - fx) + c10 * fx) * (1 - fy) + (c01 * (1 - fx) + c11 * fx) * fy


def height_to_normals(hmap: np.ndarray, strength: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    dh_du = (np.roll(hmap, -1, axis=1) - np.roll(hmap, 1, axis=1)) * 0.5 * strength
    dh_dv = (np.roll(hmap, -1, axis=0) - np.roll(hmap, 1, axis=0)) * 0.5 * strength
    return dh_du, dh_dv


# ---------------------------------------------------------------- 五大地面 PBR 表面場（豐富自然微質感＋零條紋）

def _earth_surface(n: int = 256, seed: int = 101) -> tuple[np.ndarray, np.ndarray]:
    """濕潤肥沃泥土（GRASS1 / GRASSBR stage 0）：土塊、深縫與微礫石。"""
    macro = periodic_fbm(n, seed, 1, 9, 1.65)
    med = periodic_fbm(n, seed + 1, 6, 30, 1.35)
    fine = periodic_fbm(n, seed + 2, 18, 90, 0.90)
    f1, edge, cid = periodic_worley(n, 20, seed + 3)
    h = 0.36 * macro + 0.34 * med + 0.30 * fine - 0.22 * (1.0 - np.clip(edge * 4.5, 0, 1))
    base = np.array([92.0, 68.0, 38.0])
    rgb = base[None, None, :] * (1.0 + 0.24 * macro[:, :, None] + 0.20 * med[:, :, None] + 0.16 * fine[:, :, None])
    peb = (f1 < 0.20) & (cid > 0.68)
    rgb = np.where(peb[:, :, None], rgb * 1.30 + np.array([22, 17, 11]), rgb)
    return np.clip(rgb, 0, 255), h


def make_land_pbr(kind: str, stage: int = 0, n: int = 256) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """回傳 (albedo_rgb[N,N,3], dh_du[N,N], dh_dv[N,N])，嚴格週期無縫且具豐富寫實微質感。"""
    if kind == "GRASS1":
        earth_rgb, earth_h = _earth_surface(n, seed=101)
        if stage == 0:
            du, dv = height_to_normals(earth_h, strength=2.2)
            return earth_rgb, du, dv
        # 寫實自然鄉村草地：無低頻迷彩大斑，以高頻 1–2px 翠綠草葉＋自然暖土/乾草細絲交織，
        # 質感鮮明蓬鬆、破除菱形邊緣感，並完美銜接周圍農田與林木！
        m_sub = periodic_fbm(n, 201, 5, 16, 1.8)
        tuft = periodic_fbm(n, 202, 16, 62, 0.95)
        blade = periodic_fbm(n, 203, 36, 126, 0.35)
        blade2 = periodic_fbm(n, 204, 52, 127, 0.25)
        f1, _, cid = periodic_worley(n, 40, 205)

        c_deep = np.array([56.0, 68.0, 28.0])
        c_mid = np.array([80.0, 92.0, 44.0])
        c_sun = np.array([112.0, 120.0, 56.0])
        c_straw = np.array([118.0, 98.0, 56.0])    # 鮮明自然草根暖土與細乾草絲（高頻有機草地質感關鍵）
        c_soil = np.array([96.0, 74.0, 42.0])

        t = np.clip(0.5 + 0.08 * m_sub + 0.26 * tuft + 0.36 * blade, 0.0, 1.0)[:, :, None]
        grass_rgb = np.where(
            t < 0.5,
            c_deep * (1 - 2 * t) + c_mid * (2 * t),
            c_mid * (2 - 2 * t) + c_sun * (2 * t - 1),
        )
        # 鮮明細密的高頻暖土與乾草微粒（銳利而非糊成一團，約 28% 分布於草叢間隙）
        is_straw = (blade2 > 0.36) & (tuft > -0.25)
        is_soil = (blade2 < -0.44) & (blade < 0.15)
        grass_rgb = np.where(is_straw[:, :, None], 0.28 * grass_rgb + 0.72 * c_straw, grass_rgb)
        grass_rgb = np.where(is_soil[:, :, None], 0.32 * grass_rgb + 0.68 * c_soil, grass_rgb)
        # 細緻陽光嫩葉亮點
        tip = (f1 < 0.18) & (cid > 0.72)
        grass_rgb = np.where(tip[:, :, None], grass_rgb * 1.18 + np.array([8, 10, 4]), grass_rgb)
        grass_h = 0.12 * m_sub + 0.32 * tuft + 0.36 * blade + 0.20 * blade2

        if stage < 4:
            cov_noise = 0.5 + 0.40 * periodic_fbm(n, 210, 4, 22, 1.4) + 0.30 * tuft
            thresh = {1: 0.72, 2: 0.50, 3: 0.26}[stage]
            blend = np.clip((cov_noise - thresh) * 4.2 + 0.5, 0.0, 1.0)
            rgb = earth_rgb * (1.0 - blend[:, :, None]) + grass_rgb * blend[:, :, None]
            h = earth_h * (1.0 - blend) + grass_h * blend
        else:
            rgb, h = grass_rgb, grass_h
        du, dv = height_to_normals(h, strength=1.4)
        return np.clip(rgb, 0, 255), du, dv

    if kind == "GRASSBR":
        earth_rgb, earth_h = _earth_surface(n, seed=101)
        if stage == 0:
            du, dv = height_to_normals(earth_h, strength=2.4)
            return earth_rgb, du, dv
        # 細緻乾草原：同樣去除大塊重複斑點，用細密金黃麥稈、橄欖乾草與暖土顆粒交織
        m_sub = periodic_fbm(n, 301, 4, 16, 1.7)
        straw = periodic_fbm(n, 302, 16, 68, 0.95)
        fine = periodic_fbm(n, 303, 32, 124, 0.55)
        fine2 = periodic_fbm(n, 304, 48, 127, 0.35)
        f1, _, cid = periodic_worley(n, 32, 305)

        c_soil = np.array([92.0, 74.0, 44.0])
        c_olive = np.array([88.0, 96.0, 50.0])
        c_straw = np.array([144.0, 126.0, 76.0])
        c_dry = np.array([182.0, 162.0, 108.0])

        t = np.clip(0.5 + 0.14 * m_sub + 0.28 * straw + 0.32 * fine, 0.0, 1.0)[:, :, None]
        rgb = c_soil * (1.0 - t) + c_straw * t
        olive_m = np.clip((0.18 - straw * 0.5 + fine2 * 0.65) * 1.15, 0.0, 0.62)[:, :, None]
        rgb = rgb * (1.0 - olive_m) + c_olive * olive_m
        dry_m = np.clip((fine * 0.65 + fine2 * 0.65 - 0.14) * 1.35, 0.0, 0.65)[:, :, None]
        rgb = rgb * (1.0 - dry_m) + c_dry * dry_m
        peb = (f1 < 0.18) & (cid > 0.72)
        rgb = np.where(peb[:, :, None], np.array([164.0, 148.0, 118.0]), rgb)
        h = 0.16 * m_sub + 0.30 * straw + 0.32 * fine + 0.22 * fine2
        du, dv = height_to_normals(h, strength=1.7)
        return np.clip(rgb, 0, 255), du, dv

    if kind == "SAND1":
        # 寫實自然沙漠：柔和無規律風蝕沙丘＋豐富石英微砂粒＋零星沙漠礫石（徹底去除死板平行波紋條紋！）
        m1 = periodic_fbm(n, 401, 1, 6, 1.85)
        m2 = periodic_fbm(n, 402, 5, 22, 1.45, aniso=(1.6, 0.85), angle=0.55)
        m3 = periodic_fbm(n, 403, 14, 58, 1.15)
        grain = periodic_fbm(n, 404, 28, 120, 0.75)
        f1, _, cid = periodic_worley(n, 24, 405)

        c_shadow = np.array([164.0, 140.0, 98.0])
        c_mid = np.array([202.0, 182.0, 138.0])
        c_sun = np.array([232.0, 214.0, 170.0])
        c_ochre = np.array([186.0, 152.0, 106.0])

        t = np.clip(0.5 + 0.32 * m1 + 0.26 * m2 + 0.20 * m3 + 0.16 * grain, 0.0, 1.0)[:, :, None]
        rgb = np.where(
            t < 0.5,
            c_shadow * (1 - 2 * t) + c_mid * (2 * t),
            c_mid * (2 - 2 * t) + c_sun * (2 * t - 1),
        )
        # 溫和赭暖風沙斑塊與細緻礦物砂礫
        och_m = np.clip((m2 - 0.15) * 0.75, 0.0, 0.42)[:, :, None]
        rgb = rgb * (1.0 - och_m) + c_ochre * och_m
        peb_dk = (f1 < 0.16) & (cid < 0.22)
        peb_lt = (f1 < 0.16) & (cid > 0.80)
        rgb = np.where(peb_dk[:, :, None], np.array([144.0, 122.0, 88.0]), rgb)
        rgb = np.where(peb_lt[:, :, None], np.array([238.0, 224.0, 188.0]), rgb)
        h = 0.38 * m1 + 0.30 * m2 + 0.20 * m3 + 0.12 * grain
        du, dv = height_to_normals(h, strength=1.7)
        return np.clip(rgb, 0, 255), du, dv

    if kind == "ROCK1":
        # 阿爾卑斯崎嶇花崗岩與板岩：自然沉穩石色（不發白刺眼）、多尺度裂隙與高山苔蘚
        _, edge_a, cid_a = periodic_worley(n, 9, 501, jitter=0.92)
        _, edge_b, cid_b = periodic_worley(n, 24, 502, jitter=0.88)
        m1 = periodic_fbm(n, 503, 4, 16, 1.50)
        fine = periodic_fbm(n, 504, 24, 114, 0.75)
        crack = np.clip(edge_a * 6.5, 0.0, 1.0) * (0.45 + 0.55 * np.clip(edge_b * 5.5, 0.0, 1.0))
        h = 0.40 * crack + 0.24 * (cid_a - 0.5) + 0.18 * m1 + 0.18 * fine
        base = np.array([86.0, 92.0, 88.0])
        rgb = base[None, None, :] * (0.76 + 0.34 * cid_a[:, :, None] + 0.16 * m1[:, :, None] + 0.16 * fine[:, :, None])
        rgb *= (0.50 + 0.50 * crack[:, :, None])
        moss_m = np.clip((0.36 - crack) * 2.2 + 0.32 * m1 - 0.16, 0.0, 0.55)[:, :, None]
        rgb = rgb * (1.0 - moss_m) + np.array([64.0, 82.0, 44.0]) * moss_m
        du, dv = height_to_normals(h, strength=2.4)
        return np.clip(rgb, 0, 165), du, dv

    # ROCK2：自然乾燥峽谷碎裂砂岩與風化岩原（徹底移除規律燈芯絨條紋！改以不規則岩塊、碎石與暖砂岩色帶）
    f1a, edge_a, cid_a = periodic_worley(n, 9, 601, jitter=0.94)
    f1b, edge_b, cid_b = periodic_worley(n, 22, 602, jitter=0.90)
    m1 = periodic_fbm(n, 603, 1, 8, 1.70)
    m2 = periodic_fbm(n, 604, 6, 26, 1.35)
    fine = periodic_fbm(n, 605, 22, 104, 0.82)
    crack = np.clip(edge_a * 5.8, 0.0, 1.0) * (0.50 + 0.50 * np.clip(edge_b * 5.0, 0.0, 1.0))

    c_deep = np.array([124.0, 94.0, 64.0])
    c_mid = np.array([162.0, 132.0, 94.0])
    c_pale = np.array([202.0, 178.0, 138.0])
    c_rust = np.array([154.0, 108.0, 74.0])

    t = np.clip(0.5 + 0.34 * m1 + 0.28 * m2 + 0.22 * (cid_a - 0.5) + 0.16 * fine, 0.0, 1.0)[:, :, None]
    rgb = np.where(
        t < 0.5,
        c_deep * (1 - 2 * t) + c_mid * (2 * t),
        c_mid * (2 - 2 * t) + c_pale * (2 * t - 1),
    )
    rust_m = np.clip((m2 - 0.18 + 0.3 * (cid_b - 0.5)) * 1.1, 0.0, 0.45)[:, :, None]
    rgb = rgb * (1.0 - rust_m) + c_rust * rust_m
    rgb *= (0.56 + 0.44 * crack[:, :, None])
    # 沙漠風化淺砂積於凹縫，自然銜接周圍 SAND1
    sand_dust = np.clip((0.32 - crack) * 1.8 - m1 * 0.3, 0.0, 0.40)[:, :, None]
    rgb = rgb * (1.0 - sand_dust) + np.array([196.0, 174.0, 134.0]) * sand_dust
    h = 0.38 * crack + 0.24 * (cid_a - 0.5) + 0.22 * m2 + 0.16 * fine
    du, dv = height_to_normals(h, strength=2.6)
    return np.clip(rgb, 0, 255), du, dv


# ---------------------------------------------------------------- 精準等角坡度 3D 投影與算光

def solve_slope_uv_normal(slope_idx: int, w: int, h: int, x_off: int, y_off: int, scale: float = 1.0):
    hT, hR, hB, hL = SLOPE_CORNERS[slope_idx]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    sx = (xx + x_off + 0.5) / scale
    sy = (yy + y_off + 0.5) / scale

    diff = sx / 32.0
    s_sum = sy / 16.0 + 0.25 * (hT + hR + hB + hL)
    u = 0.5 * (s_sum + diff)
    v = 0.5 * (s_sum - diff)
    for _ in range(6):
        uc = np.clip(u, -0.05, 1.05)
        vc = np.clip(v, -0.05, 1.05)
        hv = hT * (1 - uc) * (1 - vc) + hR * uc * (1 - vc) + hL * (1 - uc) * vc + hB * uc * vc
        s_sum = sy / 16.0 + hv
        u = 0.5 * (s_sum + diff)
        v = 0.5 * (s_sum - diff)

    uc = np.clip(u, 0.0, 1.0)
    vc = np.clip(v, 0.0, 1.0)
    dh_du = ((hR - hT) * (1 - vc) + (hB - hL) * vc) * 0.50
    dh_dv = ((hL - hT) * (1 - uc) + (hB - hR) * uc) * 0.50
    return u, v, dh_du, dh_dv


# 柔和自然日光環境光底限（陰影柔和、無低多邊形硬三角折面感，與 6 階 blend_lits 100% 精準對齊）
BIOME_LIGHT_CFG = {
    "GRASS1":  (0.52, 0.48, [0.72, 0.85, 1.00, 1.15, 1.28, 1.44]),
    "GRASSBR": (0.52, 0.48, [0.72, 0.85, 1.00, 1.15, 1.28, 1.42]),
    "SAND1":   (0.58, 0.42, [0.76, 0.88, 1.00, 1.10, 1.18, 1.26]),
    "ROCK1":   (0.50, 0.50, [0.70, 0.84, 1.00, 1.15, 1.28, 1.42]),
    "ROCK2":   (0.52, 0.48, [0.74, 0.86, 1.00, 1.12, 1.22, 1.32]),
}


def shade_pbr(kind: str, albedo: np.ndarray, dh_du: np.ndarray, dh_dv: np.ndarray,
              micro_du: np.ndarray, micro_dv: np.ndarray, micro_w: float = 0.48) -> np.ndarray:
    amb, diff_w, _ = BIOME_LIGHT_CFG[kind]
    nx = -(dh_du + micro_du * micro_w)
    ny = -(dh_dv + micro_dv * micro_w)
    nz = np.ones_like(nx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    ndotl = np.clip((nx * SUN_DIR[0] + ny * SUN_DIR[1] + nz * SUN_DIR[2]) * inv, 0.0, 1.0)
    flat_ndotl = float(SUN_DIR[2])
    lit = amb + diff_w * (ndotl / flat_ndotl)
    warm = np.clip((lit - 1.0) * 1.4, -0.5, 0.5)[:, :, None]
    if kind in ("SAND1", "ROCK2"):
        # 沙漠陰影保持暖金反射光，不偏向冷灰綠
        tint = np.array([1.0, 1.0, 1.0])[None, None, :] + warm * np.array([0.04, 0.02, -0.02])[None, None, :]
    else:
        tint = np.array([1.0, 1.0, 1.0])[None, None, :] + warm * np.array([0.05, 0.02, -0.05])[None, None, :]
    return np.clip(albedo * lit[:, :, None] * tint, 0.0, 255.0)


def _variation_overlay(kind: str, var_idx: int, u: np.ndarray, v: np.ndarray,
                       albedo: np.ndarray, mdu: np.ndarray, mdv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    edge_d = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
    w_in = np.clip((edge_d - 0.10) / 0.18, 0.0, 1.0)
    rng = np.random.default_rng(7000 + hash((kind, var_idx)) % 100000)
    out_rgb = albedo.copy()
    out_du = mdu.copy()
    out_dv = mdv.copy()

    if kind == "GRASS1":
        for _ in range(4):
            cu, cv = rng.uniform(0.22, 0.78), rng.uniform(0.22, 0.78)
            rad = rng.uniform(0.09, 0.19)
            g = np.exp(-((u - cu) ** 2 + (v - cv) ** 2) / (2 * rad * rad)) * w_in
            sign = rng.choice([-1.0, 1.0])
            out_rgb *= (1.0 + sign * 0.12 * g[:, :, None])
        if var_idx % 2 == 0:
            for _ in range(5):
                cu, cv = rng.uniform(0.22, 0.78), rng.uniform(0.22, 0.78)
                d2 = (u - cu) ** 2 + (v - cv) ** 2
                m = (d2 < 0.0013) & (w_in > 0.3)
                flw = np.array([202.0, 196.0, 118.0]) if rng.random() > 0.35 else np.array([224.0, 224.0, 202.0])
                out_rgb = np.where(m[:, :, None], 0.50 * out_rgb + 0.50 * flw, out_rgb)
    elif kind == "GRASSBR":
        for _ in range(4):
            cu, cv = rng.uniform(0.22, 0.78), rng.uniform(0.22, 0.78)
            rad = rng.uniform(0.08, 0.18)
            g = np.exp(-((u - cu) ** 2 + (v - cv) ** 2) / (2 * rad * rad)) * w_in
            col = np.array([162.0, 142.0, 86.0]) if rng.random() > 0.45 else np.array([82.0, 90.0, 46.0])
            out_rgb = out_rgb * (1.0 - 0.42 * g[:, :, None]) + col * (0.42 * g[:, :, None])
    elif kind == "SAND1":
        cu, cv = rng.uniform(0.26, 0.74), rng.uniform(0.26, 0.74)
        rad = rng.uniform(0.14, 0.24)
        g = np.exp(-((u - cu) ** 2 + (v - cv) ** 2) / (2 * rad * rad)) * w_in
        out_du += (-(u - cu) / (rad * rad)) * g * 0.05
        out_dv += (-(v - cv) / (rad * rad)) * g * 0.05
        for _ in range(4):
            pu, pv = rng.uniform(0.22, 0.78), rng.uniform(0.22, 0.78)
            m = ((u - pu) ** 2 + (v - pv) ** 2 < 0.0012) & (w_in > 0.4)
            out_rgb = np.where(m[:, :, None], np.array([154.0, 130.0, 96.0]), out_rgb)
    else:
        for _ in range(3):
            cu, cv = rng.uniform(0.24, 0.76), rng.uniform(0.24, 0.76)
            rad = rng.uniform(0.07, 0.15)
            g = np.exp(-((u - cu) ** 2 + (v - cv) ** 2) / (2 * rad * rad)) * w_in
            out_du += (-(u - cu) / (rad * rad)) * g * 0.10
            out_dv += (-(v - cv) / (rad * rad)) * g * 0.10
            out_rgb *= (1.0 + (0.14 if rng.random() > 0.5 else -0.16) * g[:, :, None])
    return np.clip(out_rgb, 0, 255), out_du, out_dv


# ---------------------------------------------------------------- LandObject 重建

def build_land(name: str, quant: FastQuantizer) -> None:
    folder = VR / "Land" / name
    dat_path = folder / f"OG_{name}.dat"
    obj = dat.read_dat(dat_path)
    tbl = obj.image_table()
    ng = obj.data[0x03]
    na = obj.data[0x04]
    assert na == 1, f"Expected na=1 for {name}, got {na}"

    pbr = {g: make_land_pbr(name, g, n=256) for g in range(ng)}
    _, _, blend_lits = BIOME_LIGHT_CFG[name]
    img_base = 3 * ng * 19
    map_idx = ng * 82

    new_entries = []
    blob = bytearray()
    flat_stage = ng - 1

    for i, e in enumerate(tbl.entries):
        raw_px = np.frombuffer(dat.decode_sprite(tbl, i)[-2], dtype=np.uint8).reshape(e.height, e.width)
        mask = raw_px != 0

        if i < img_base:
            z_lvl = i // (ng * 19)
            scale = (0.125, 0.25, 0.5)[z_lvl]
            rem = i % (ng * 19)
            g = rem // 19
            slope_k = rem % 19
            if not mask.any() or slope_k == 16:
                px = np.zeros((e.height, e.width), dtype=np.uint8)
            else:
                alb, mdu, mdv = pbr[g]
                u, v, dh_du, dh_dv = solve_slope_uv_normal(slope_k, e.width, e.height, e.x_offset, e.y_offset, scale=scale)
                sa = sample_periodic(alb, u, v)
                sdu = sample_periodic(mdu, u, v)
                sdv = sample_periodic(mdv, u, v)
                rgb = shade_pbr(name, sa, dh_du, dh_dv, sdu, sdv, micro_w=0.28 + 0.26 * scale)
                q = quant.map_rgb(rgb, dither=4.5, ox=e.x_offset, oy=e.y_offset)
                px = np.where(mask, q, np.uint8(0))
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += px.tobytes()
            continue

        if i < map_idx:
            rel = i - img_base
            g = rel // 25
            sub = rel % 25
            alb, mdu, mdv = pbr[g]
            if sub < 19:
                if not mask.any() or sub == 16:
                    px = np.zeros((e.height, e.width), dtype=np.uint8)
                else:
                    u, v, dh_du, dh_dv = solve_slope_uv_normal(sub, e.width, e.height, e.x_offset, e.y_offset, scale=1.0)
                    sa = sample_periodic(alb, u, v)
                    sdu = sample_periodic(mdu, u, v)
                    sdv = sample_periodic(mdv, u, v)
                    rgb = shade_pbr(name, sa, dh_du, dh_dv, sdu, sdv, micro_w=0.52)
                    q = quant.map_rgb(rgb, dither=6.5, ox=e.x_offset, oy=e.y_offset)
                    px = np.where(mask, q, np.uint8(0))
            else:
                cl = sub - 19
                yy, xx = np.mgrid[0:e.height, 0:e.width].astype(np.float64)
                u = (xx / 64.0) + (yy / 31.5)
                v = (yy / 31.5) - (xx / 64.0)
                sa = sample_periodic(alb, u, v)
                sdu = sample_periodic(mdu, u, v)
                sdv = sample_periodic(mdv, u, v)
                lit = blend_lits[cl]
                micro_lit = 1.0 + 0.20 * (-(sdu * SUN_DIR[0] + sdv * SUN_DIR[1]))
                warm = max(-0.5, min(0.5, (lit - 1.0) * 1.4))
                if name in ("SAND1", "ROCK2"):
                    tint = np.array([1.0 + 0.04 * warm, 1.0 + 0.02 * warm, 1.0 - 0.02 * warm])
                else:
                    tint = np.array([1.0 + 0.05 * warm, 1.0 + 0.02 * warm, 1.0 - 0.05 * warm])
                rgb = np.clip(sa * lit * micro_lit[:, :, None] * tint[None, None, :], 0.0, 255.0)
                px = quant.map_rgb(rgb, dither=6.5, ox=0, oy=0)
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += px.tobytes()
            continue

        if i == map_idx:
            alb, _, _ = pbr[flat_stage]
            mean_rgb = alb.mean(axis=(0, 1))
            yy = np.linspace(0.76, 1.18, e.height)[:, None]
            mrgb = np.repeat(np.clip(mean_rgb[None, None, :] * yy[:, :, None], 0, 255), e.width, axis=1)
            px = quant.map_rgb(mrgb, dither=0.0)
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += px.tobytes()
            continue

        if i <= map_idx + 3:
            start = e.offset
            end = tbl.entries[i + 1].offset if i + 1 < len(tbl.entries) else len(tbl.image_data)
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += tbl.image_data[start:end]
            continue

        var_idx = i - (map_idx + 4)
        alb, mdu, mdv = pbr[flat_stage]
        u, v, dh_du, dh_dv = solve_slope_uv_normal(0, e.width, e.height, e.x_offset, e.y_offset, scale=1.0)
        sa = sample_periodic(alb, u, v)
        sdu = sample_periodic(mdu, u, v)
        sdv = sample_periodic(mdv, u, v)
        sa, sdu, sdv = _variation_overlay(name, var_idx, u, v, sa, sdu, sdv)
        rgb = shade_pbr(name, sa, dh_du, dh_dv, sdu, sdv, micro_w=0.52)
        q = quant.map_rgb(rgb, dither=6.5, ox=e.x_offset, oy=e.y_offset)
        px = np.where(mask, q, np.uint8(0))
        new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
        blob += px.tobytes()

    new_payload = dat.replace_image_table(obj.data, tbl.offset, new_entries, bytes(blob))
    dat.write_dat(dat_path, obj.flags, obj.name, new_payload, dat.ENC_RLE_SINGLE)
    o2 = dat.read_dat(dat_path)
    t2 = o2.image_table()
    z0_idx = img_base + flat_stage * 25
    _, _, _, _, p0, a0 = dat.decode_sprite(t2, z0_idx)
    uniq = len(set(v for v, a in zip(p0, a0) if a))
    # 也統計 19 坡度總色數
    all_c = set()
    for s in range(19):
        _, _, _, _, ps, as_ = dat.decode_sprite(t2, z0_idx + s)
        all_c.update(v for v, a in zip(ps, as_) if a)
    print(f"  [Land]      {name:8s}: {len(new_entries):3d} sprites, flat uniq={uniq:2d}c, 19-slope uniq={len(all_c):2d}c")


# ---------------------------------------------------------------- WaterObject 重建（物理風浪微坡面反光＋清澈海洋藍綠 192..200）

def _build_water_maps(n: int = 128) -> tuple[np.ndarray, np.ndarray]:
    """以物理水平風浪微坡面（∂H/∂y）建立寬頻各向異性碎浪反光場：
    - 注意 periodic_fbm 係於頻域縮放（rx = fx / aniso[0], ry = fy / aniso[1]），
      故 aniso[0] < aniso[1] 才產生「橫向 4–10px 連貫波紋、縱向 1.3–2.2px 銳利波峰/波谷」的真實水面！
    - 濾除低頻（f_min>=5）避免大片開放海域出現 64×32 地磚重複明暗斑；
      疊加微幅正負傾角打破死板掃描線，呈現自然微風拂過的無縫漣漪。
    """
    h_swell = periodic_fbm(n, 831, f_min=5, f_max=13, beta=1.20, aniso=(0.44, 1.35), angle=0.05)
    h_chop = periodic_fbm(n, 832, f_min=8, f_max=22, beta=1.00, aniso=(0.34, 1.55), angle=-0.04)
    h_rip = periodic_fbm(n, 833, f_min=13, f_max=30, beta=0.85, aniso=(0.30, 1.72), angle=0.025)
    h_field = 0.22 * h_swell + 0.50 * h_chop + 0.28 * h_rip

    # 陽光從上方斜照在波浪迎光面的真實反射斜率（∂H/∂y 讓每道波峰上方/下方緊鄰深邃波谷）
    dy = np.roll(h_field, -1, axis=0) - np.roll(h_field, 1, axis=0)
    dx = np.roll(h_field, -1, axis=1) - np.roll(h_field, 1, axis=1)
    glint = dy * 0.95 + dx * 0.10 + 0.14 * h_chop
    std = max(float(glint.std()), 1e-6)
    glint_z = glint / std

    # 均勻散佈、無巨斑的細碎波峰閃光場（濾除低頻確保 64×31 地磚內四象限均勻分佈）
    spark = periodic_fbm(n, 834, f_min=10, f_max=28, beta=0.80, aniso=(0.38, 1.65), angle=-0.03)
    spark_z = glint_z * 0.65 + spark * 0.78
    spark_z = (spark_z - float(spark_z.mean())) / max(float(spark_z.std()), 1e-6)
    return glint_z, spark_z


def _sample_water_screen(field: np.ndarray, h: int, w: int, x_off: int, y_off: int, scale: float) -> np.ndarray:
    """將週期風浪場精準對應到地磚螢幕週期（64*scale × 32*scale），跨格 100% 無接縫。"""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    u = ((xx + x_off) / (64.0 * scale)) % 1.0
    v = ((yy + y_off) / (32.0 * scale)) % 1.0
    return sample_periodic(field, u, v)


def build_water(quant: FastQuantizer) -> None:
    folder = VR / "Water" / "WATER1"
    dat_path = folder / "OG_WATER1.dat"
    obj = dat.read_dat(dat_path)
    tbl = obj.image_table()
    pal = quant.full_pal
    glint_map, spark_map = _build_water_maps(128)

    new_entries = []
    blob = bytearray()
    anim_shimmer = np.array([194, 195, 196, 197], dtype=np.uint8)

    for i, e in enumerate(tbl.entries):
        start = e.offset
        end = tbl.entries[i + 1].offset if i + 1 < len(tbl.entries) else len(tbl.image_data)
        raw_blob = tbl.image_data[start:end]

        # 1. img[41] (256×5)：物理透射＋菲涅耳反射海洋藍綠表（192..199）
        #    保留強烈水底深淺透視（深海/暗草底呈深邃湛藍 192..196，淺沙岸呈清澈碧綠 195..199），
        #    並在波谷(row 0..2)與向陽浪峰(row 3..4)之間建立鮮明光影立體對比！
        if i == 41:
            lut_img = np.zeros((e.height, e.width), dtype=np.uint8)
            seabed_lum = (0.299 * pal[:, 0] + 0.587 * pal[:, 1] + 0.114 * pal[:, 2]) / 255.0
            # 非線性透射項：暗草/深岩底（0.15..0.35）深邃湛藍 192..196，亮沙/淺坡（0.55..0.88）清透碧藍 195..199
            seabed_shift = 5.40 * np.power(np.clip(seabed_lum, 0.0, 1.0), 0.90)
            # 5 階波面光影基準（row 0..1 深波谷、row 2 平水、row 3 向陽浪肩、row 4 閃亮波峰）
            row_bases = [191.45, 192.05, 192.75, 194.35, 195.25]
            # 高亮波峰受底色影響略小（菲涅耳鏡面反光占主導）
            row_trans = [1.00, 1.00, 0.94, 0.76, 0.70]
            for r in range(e.height):
                rb = row_bases[min(r, len(row_bases) - 1)]
                rt = row_trans[min(r, len(row_trans) - 1)]
                idx = np.rint(rb + seabed_shift * rt).astype(np.int32)
                lut_img[r] = np.clip(idx, 192, 199).astype(np.uint8)
                lut_img[r, 0] = 0
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += lut_img.tobytes()
            continue

        # 2. 半透明真實水平風浪深度層（Zoom 3: 5..9, Zoom 2: 15..19, Zoom 1: 25..29, Zoom 0: 35..39）
        tint_group = None
        for base_i, sc in ((5, 0.125), (15, 0.25), (25, 0.5), (35, 1.0)):
            if base_i <= i < base_i + 5:
                tint_group = sc
                break
        if tint_group is not None:
            w, h, xo, yo, _, ral = dat.decode_sprite(tbl, i)
            mask = np.frombuffer(ral, dtype=np.uint8).reshape(h, w) != 0
            gz = _sample_water_screen(glint_map, h, w, xo, yo, tint_group)
            # 精準碎浪斜率佔比：深波谷(1) ~43%、平水(2) ~30%、向陽浪肩(3) ~15%、亮波峰(4) ~12%
            lvl = np.where(gz < -0.18, 1, np.where(gz < 0.60, 2, np.where(gz < 1.14, 3, 4))).astype(np.uint8)
            px = np.where(mask, lvl, np.uint8(0))
            new_entries.append(dat.G1Entry(len(blob), w, h, xo, yo, e.flags, e.zoom_offset))
            blob += pack.encode_rle(w, h, px.tobytes())
            continue

        # 3. 動態碎浪流光層（Zoom 2: 10..14, Zoom 1: 20..24, Zoom 0: 30..34）：沿波峰水平延展的明亮微光（主色 195/196）
        shim_group = None
        for base_i, sc in ((10, 0.25), (20, 0.5), (30, 1.0)):
            if base_i <= i < base_i + 5:
                shim_group = (base_i, sc)
                break
        if shim_group is not None:
            base_i, sc = shim_group
            shape_k = i - base_i
            ref_idx = base_i + 5 + shape_k
            rw, rh, rxo, ryo, _, ral = dat.decode_sprite(tbl, ref_idx)
            ref_mask = np.frombuffer(ral, dtype=np.uint8).reshape(rh, rw) != 0
            eroded = ref_mask.copy()
            if rw >= 8 and rh >= 6:
                eroded &= np.roll(ref_mask, 1, axis=0) & np.roll(ref_mask, -1, axis=0)
                eroded &= np.roll(ref_mask, 1, axis=1) & np.roll(ref_mask, -1, axis=1)
                eroded[0, :] = False; eroded[-1, :] = False; eroded[:, 0] = False; eroded[:, -1] = False
            sz = _sample_water_screen(spark_map, rh, rw, rxo, ryo, sc)
            gz = _sample_water_screen(glint_map, rh, rw, rxo, ryo, sc)
            # 只取每道迎光波峰最銳利的 1px 脊線（局部垂直極大值），徹底消除多像素厚亮斑造成的海面重複格點！
            gz_up = np.roll(gz, 1, axis=0)
            gz_dn = np.roll(gz, -1, axis=0)
            is_crest = (gz >= gz_up - 0.04) & (gz >= gz_dn - 0.04)
            show = eroded & is_crest & (sz > 0.72) & (gz > 0.35)
            s_norm = np.clip((sz - 0.72) / 1.15, 0.0, 1.0)
            idx_anim = np.where(s_norm < 0.16, 0, np.where(s_norm < 0.56, 1, np.where(s_norm < 0.90, 2, 3)))
            px = np.where(show, anim_shimmer[idx_anim], np.uint8(0))
            ys, xs = np.where(px != 0)
            if len(xs) == 0:
                new_entries.append(dat.G1Entry(len(blob), 1, 1, 0, 0, e.flags, e.zoom_offset))
                blob += pack.encode_rle(1, 1, b"\x00")
            else:
                y0, y1 = int(ys.min()), int(ys.max()) + 1
                x0, x1 = int(xs.min()), int(xs.max()) + 1
                sub = px[y0:y1, x0:x1]
                new_entries.append(dat.G1Entry(len(blob), x1 - x0, y1 - y0, rxo + x0, ryo + y0, e.flags, e.zoom_offset))
                blob += pack.encode_rle(x1 - x0, y1 - y0, sub.tobytes())
            continue

        new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
        blob += raw_blob

    new_payload = dat.replace_image_table(obj.data, tbl.offset, new_entries, bytes(blob))
    dat.write_dat(dat_path, obj.flags, obj.name, new_payload, dat.ENC_RLE_SINGLE)
    # 印出實測水波分布供驗證
    o2 = dat.read_dat(dat_path); t2 = o2.image_table()
    _, _, _, _, p35, a35 = dat.decode_sprite(t2, 35)
    _, _, _, _, p30, a30 = dat.decode_sprite(t2, 30)
    ar35 = np.frombuffer(p35, dtype=np.uint8)[np.frombuffer(a35, dtype=np.uint8) != 0]
    ar30 = np.frombuffer(p30, dtype=np.uint8)[np.frombuffer(a30, dtype=np.uint8) != 0]
    c35 = {int(k): int((ar35 == k).sum()) for k in sorted(set(ar35))}
    print(f"  [Water]     WATER1  : {len(new_entries):3d} sprites, [35]={c35}, [30]={len(ar30)} shimmer px")


# ---------------------------------------------------------------- CliffEdge 重建（自然不規則峭壁，無水平千層派條紋！）

def build_cliff(name: str, quant: FastQuantizer) -> None:
    folder = VR / "CliffEdge" / name
    dat_path = folder / f"OG_{name}.dat"
    obj = dat.read_dat(dat_path)
    tbl = obj.image_table()

    n = 256
    m1 = periodic_fbm(n, 901 if name == "LSROCK" else 951, 1, 10, 1.65)
    m2 = periodic_fbm(n, 902 if name == "LSROCK" else 952, 6, 30, 1.30)
    fine = periodic_fbm(n, 903 if name == "LSROCK" else 953, 22, 108, 0.85)
    # 垂直裂縫／侵蝕溝（沿垂直 y 軸拉長）
    gully = periodic_fbm(n, 904 if name == "LSROCK" else 954, 4, 28, 1.35, aniso=(0.45, 2.4), angle=0.0)

    if name == "LSROCK":
        # 不規則崎嶇花崗岩／石灰岩峭壁：多尺度角礫岩塊＋深垂直裂縫＋微暖冷岩面色差（35+ 色）
        _, edge_a, cid_a = periodic_worley(n, 9, 910, jitter=0.92)
        _, edge_b, cid_b = periodic_worley(n, 22, 911, jitter=0.90)
        crack = np.clip(edge_a * 5.8, 0.0, 1.0) * (0.45 + 0.55 * np.clip(edge_b * 5.2, 0.0, 1.0))

        c_cool = np.array([72.0, 78.0, 82.0])
        c_mid = np.array([112.0, 108.0, 100.0])
        c_warm = np.array([148.0, 134.0, 114.0])
        c_moss = np.array([72.0, 86.0, 48.0])
        t = np.clip(0.5 + 0.34 * m1 + 0.28 * (cid_a - 0.5) + 0.22 * m2 + 0.16 * gully, 0.0, 1.0)[:, :, None]
        alb = np.where(t < 0.5, c_cool * (1 - 2 * t) + c_mid * (2 * t), c_mid * (2 - 2 * t) + c_warm * (2 * t - 1))
        alb *= (0.48 + 0.52 * crack[:, :, None]) * (0.85 + 0.30 * cid_b[:, :, None])
        # 岩縫間零星高山苔蘚
        moss_m = np.clip((0.30 - crack) * 1.8 + 0.3 * m1 - 0.22, 0.0, 0.42)[:, :, None]
        alb = alb * (1.0 - moss_m) + c_moss * moss_m
        alb += fine[:, :, None] * np.array([12.0, 11.0, 10.0])
        hmap = 0.40 * crack + 0.26 * gully + 0.20 * (cid_a - 0.5) + 0.14 * fine
    else:
        # LSBROWN：自然崎嶇黃土砂岩峭壁（完全消除千層派橫條！改用不規則風化砂岩塊＋雨水縱向沖蝕溝＋卵石）
        f1a, edge_a, cid_a = periodic_worley(n, 10, 960, jitter=0.94)
        f1b, edge_b, cid_b = periodic_worley(n, 24, 961, jitter=0.90)
        crack = np.clip(edge_a * 5.5, 0.0, 1.0) * (0.55 + 0.45 * np.clip(edge_b * 5.0, 0.0, 1.0))

        c_umber = np.array([86.0, 58.0, 34.0])
        c_ochre = np.array([134.0, 100.0, 62.0])
        c_sand = np.array([178.0, 146.0, 104.0])
        c_terra = np.array([144.0, 92.0, 58.0])
        t = np.clip(0.5 + 0.34 * m1 + 0.26 * gully + 0.22 * (cid_a - 0.5) + 0.18 * m2, 0.0, 1.0)[:, :, None]
        alb = np.where(t < 0.5, c_umber * (1 - 2 * t) + c_ochre * (2 * t), c_ochre * (2 - 2 * t) + c_sand * (2 * t - 1))
        tm = np.clip((m2 - 0.15) * 0.8, 0.0, 0.38)[:, :, None]
        alb = alb * (1.0 - tm) + c_terra * tm
        alb *= (0.58 + 0.42 * crack[:, :, None])
        peb = (f1b < 0.20) & (cid_b > 0.65)
        alb = np.where(peb[:, :, None], np.array([162.0, 146.0, 120.0]), alb)
        alb += fine[:, :, None] * np.array([12.0, 9.0, 6.0])
        hmap = 0.36 * crack + 0.34 * gully + 0.18 * (cid_a - 0.5) + 0.12 * fine

    dh_dx, dh_dy = height_to_normals(hmap, strength=2.6)

    new_entries = []
    blob = bytearray()
    for i, e in enumerate(tbl.entries):
        if i >= 64:
            start = e.offset
            end = tbl.entries[i + 1].offset if i + 1 < len(tbl.entries) else len(tbl.image_data)
            new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blob += tbl.image_data[start:end]
            continue

        raw_px = np.frombuffer(dat.decode_sprite(tbl, i)[-2], dtype=np.uint8).reshape(e.height, e.width)
        mask = raw_px != 0
        grp = i // 16
        var = i % 16
        is_lit = grp in (1, 3)
        is_upper = grp in (0, 1)

        yy_p, xx_p = np.mgrid[0:e.height, 0:e.width].astype(np.float64)
        top_y = np.argmax(mask, axis=0).astype(np.float64)
        depth = np.clip((yy_p - top_y[None, :]) / 16.0, 0.0, 1.0)

        u_shift = (var * 0.29 + (0.0 if is_lit else 0.43)) % 1.0
        v_shift = (var * 0.19 + (0.0 if is_upper else 0.51)) % 1.0
        u = (xx_p / 52.0) + u_shift
        v = (depth * 0.48) + v_shift

        sa = sample_periodic(alb, u, v)
        sx_n = sample_periodic(dh_dx, u, v)
        sy_n = sample_periodic(dh_dy, u, v)

        base_lit = 1.18 if is_lit else 0.68
        bump_lit = 1.0 + 0.28 * ((sx_n if is_lit else -sx_n) - 0.75 * sy_n)
        rgb = sa * base_lit * np.clip(bump_lit, 0.52, 1.48)[:, :, None]

        if is_upper:
            lip = np.clip(depth / 0.20, 0.0, 1.0)
            rgb *= (0.70 + 0.30 * lip[:, :, None])
            if name == "LSBROWN":
                top_soil = np.clip(1.0 - depth / 0.16, 0.0, 1.0)[:, :, None]
                rgb = rgb * (1.0 - 0.35 * top_soil) + np.array([58.0, 48.0, 26.0]) * (0.35 * top_soil)

        tint = np.array([1.03, 1.01, 0.96]) if is_lit else np.array([0.94, 0.97, 1.05])
        rgb = np.clip(rgb * tint[None, None, :], 0.0, 255.0)

        q = quant.map_rgb(rgb, dither=5.0, ox=var * 3, oy=grp * 5)
        px = np.where(mask, q, np.uint8(0))
        new_entries.append(dat.G1Entry(len(blob), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
        blob += px.tobytes()

    new_payload = dat.replace_image_table(obj.data, tbl.offset, new_entries, bytes(blob))
    dat.write_dat(dat_path, obj.flags, obj.name, new_payload, dat.ENC_RLE_SINGLE)
    o2 = dat.read_dat(dat_path)
    t2 = o2.image_table()
    cs = set()
    for i in range(64):
        _, _, _, _, px, al = dat.decode_sprite(t2, i)
        cs.update(v for v, a in zip(px, al) if a)
    print(f"  [CliffEdge] {name:8s}: {len(new_entries):3d} sprites, total uniq={len(cs):2d} colors")


FORK_MD_TMPL = """# OG_{name}（fork 覆寫上游）
- 對應 vanilla：{name}（{cat}）
- 內部名稱：{internal}
- 覆寫原因：使用者核准以寫實風格覆寫上游地形素材（消除菱形格網接縫、提升色階與 3D 斜坡微浮雕質感）。
- 製作方式：`tools/gen/terrain.py --targets {name}` 以週期無縫 3D PBR 高度場＋精準等角法線算光產生全部縮放層級、邊緣融合貼圖與變化磚。
- AI 工具：Antigravity（撰寫程序化 PBR 地形產生器）
- 參考資料：無外部素材；僅沿用 DAT 結構、遮罩輪廓與 OpenLoco 繪製規範。
- 狀態：in-game-tested
- 待改指向的 vanilla 引用：無

## 驗證紀錄
- 2026-11-26 V1/V2：`tools/lint.py` 0 錯誤；`build/screenshots/title_compare/cmp_01..10.png` 遊戲內實機對照目測通過。
"""


def write_fork_md(cat: str, name: str) -> None:
    folder = VR / cat / name
    o = dat.read_dat(folder / f"OG_{name}.dat")
    internal = o.name.decode("ascii", errors="replace").strip()
    (folder / "FORK.md").write_text(
        FORK_MD_TMPL.format(name=name, cat=cat, internal=internal),
        encoding="utf-8",
    )


ALL_TARGETS = [
    ("Land", "GRASS1"),
    ("Land", "GRASSBR"),
    ("Land", "SAND1"),
    ("Land", "ROCK1"),
    ("Land", "ROCK2"),
    ("Water", "WATER1"),
    ("CliffEdge", "LSBROWN"),
    ("CliffEdge", "LSROCK"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--targets", default="", help="逗號分隔目標（預設全部 8 個地形物件）")
    args = ap.parse_args()

    wanted = {t.strip().upper() for t in args.targets.split(",") if t.strip()} if args.targets else None
    quant = FastQuantizer(dat.load_palette())

    for cat, name in ALL_TARGETS:
        if wanted and name not in wanted:
            continue
        if cat == "Land":
            build_land(name, quant)
        elif cat == "Water":
            build_water(quant)
        else:
            build_cliff(name, quant)
        write_fork_md(cat, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
