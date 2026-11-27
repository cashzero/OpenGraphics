#!/usr/bin/env python3
"""3D 點雲樹木（ROADMAP M6 美術調整：對齊並超越原版 Locomotion 樹木質感）。

  .venv/bin/python tools/gen/tree3d.py --template <模板.DAT> --species oak [--seed 1] -o <資料夾>
  .venv/bin/python tools/gen/tree3d.py --sheet build/preview/trees3d.png --species oak,scpine,...   # 預覽

做法（軟體 3D 點雲算圖器，不用 Blender）：
1. 依樹種建 3D 模型：
   - 闊葉樹（deciduous / weeping）：遞迴分叉深色樹幹與枝幹骨架（冬季呈現細緻剪影），夏季／秋季為多葉冠丘與方向性小葉叢（有明暗對比與葉冠縫隙）。
   - 針葉樹（conifer）：多層下垂羽狀針葉枝棚，每層上亮下暗形成清晰層次；落葉針葉樹（水杉、落羽松、池杉）支援秋紅／冬枯／春芽。
   - 松樹（pine）：彎曲暖色樹幹＋中上層厚實層疊傘狀松針枝棚（避免光桿細棒）。
   - 沙漠植物（cactus / barrel / pear / joshua / yucca / fanpalm）：針對 16–24px 小圖特化，保留俐落輪廓、肋紋與四方向旋轉。
2. 以遊戲的 2:1 等角投影（sx = X − Y，sy = (X + Y)/2 − Z）畫到 sprite 上，深度緩衝取最靠近相機的點。
3. 太陽自左上照下：高對比暖陽黃綠高光＋深邃森林暗影（對齊 Locomotion 調色盤 70–81、82–93、142–153、22–33、58–69 等最豐富的 12 階色帶），
   不再把陰影染成偏冷青灰，也不鎖死高環境光底線。
4. 積雪：依幾何朝上權重（snow_w，不受葉片微法線雜訊干擾）形成覆蓋在枝棚與冠頂的連續雪帽，而非白點雜訊。
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402
import dat  # noqa: E402
import quantize  # noqa: E402

PAL = np.array(dat.load_palette(), dtype=np.float64)
SHADOW_INDEX = 0x0A + 1                       # 與舊版相同（深灰，遊戲以半透明繪製）
LIGHT = np.array([-0.42, 0.62, 0.66])         # 從畫面左前上方照下：左側受暖光、右側深陰影
LIGHT /= np.linalg.norm(LIGHT)

# ---------------------------------------------------------------- 顏色（RGB 0–1，對齊 Locomotion 最佳色帶）


def rgb(r, g, b):
    return np.array([r, g, b], dtype=np.float64) / 255


LEAF = {
    "green": rgb(102, 142, 58),      # 命中 70–81 暖陽森綠（橡樹、榆樹、楓樹）
    "darkgreen": rgb(60, 110, 48),   # 命中 70–81 / 142–153 飽滿針葉綠（冷杉、紅檜、紫杉）
    "conifer": rgb(54, 102, 44),     # 沉穩但不焦黑的杉綠，受光枝梢帶暖橄欖高光
    "pine": rgb(92, 134, 58),        # 暖陽松針綠（蘇格蘭松／Shot 04 河岸松樹，命中 70–81 / 82–93）
    "avocado": rgb(124, 156, 70),    # 命中 70–81 / 82–93 明亮橄欖綠（白樺、梣樹、垂柳）
    "olive": rgb(112, 128, 58),      # 命中 22–33 / 82–93 沙漠橄欖綠
    "gold": rgb(176, 162, 60),       # 命中 22–33 金黃葉（黃金刺槐、黃金扁柏）
    "copper": rgb(126, 58, 46),      # 命中 58–69 紫銅山毛櫸
    "seagreen": rgb(64, 118, 82),    # 命中 142–153 藍雲杉（微冷針葉綠，不落入泥青色）
    "cactus": rgb(124, 152, 86),     # 沙漠日曬灰鼠尾草綠（命中 82–93，不再黑壓壓）
    "desert_sage": rgb(140, 166, 94),# 約書亞樹／絲蘭／銀棕的日曬淺橄欖鼠尾草綠
}
SPRING = rgb(134, 162, 70)
AUTUMN = {
    "orange": [rgb(168, 92, 34), rgb(142, 68, 28), rgb(186, 136, 48), rgb(112, 106, 44), rgb(156, 116, 42)],
    "red": [rgb(148, 46, 34), rgb(120, 36, 28), rgb(168, 78, 36), rgb(136, 96, 38)],
    "yellow": [rgb(184, 154, 52), rgb(160, 128, 42), rgb(132, 114, 44), rgb(172, 142, 64)],
    "rust": [rgb(154, 76, 44), rgb(130, 58, 36), rgb(172, 98, 58), rgb(114, 54, 34)],
    "copper": [rgb(116, 50, 38), rgb(96, 42, 32), rgb(138, 66, 42)],
}
FLOWERS = {"cream": rgb(232, 222, 182), "white": rgb(236, 236, 226), "pink": rgb(222, 152, 170)}
BARK = {
    "brown": rgb(108, 86, 62),
    "light": rgb(174, 170, 158),
    "red": rgb(132, 82, 54),
    "dark": rgb(66, 54, 44),
    "grey": rgb(96, 92, 84),
    "desert_tan": rgb(158, 142, 114), # 日曬沙漠灰褐樹皮（約書亞樹／銀棕，不焦黑）
}
TWIG_DARK = rgb(52, 46, 40)          # 冬季細枝一律用深木褐／炭褐，避免白樺細枝變白雜訊
SNOW = rgb(234, 240, 244)
DEAD = rgb(94, 86, 74)

# ---------------------------------------------------------------- 調色盤對應（RGB → index）

_LUT = None


def to_lab(rgb255: np.ndarray) -> np.ndarray:
    c = rgb255 / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.2126, 0.0193], [0.3576, 0.7152, 0.1192], [0.1805, 0.0722, 0.9505]])
    xyz /= np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def lut() -> np.ndarray:
    """64³ 查表：RGB（每通道 6 bit）→ 感知色差（Lab）最近的允許色號。色相權重較高，暗綠不會變成灰或棕色。"""
    global _LUT
    if _LUT is None:
        allowed = np.array(quantize.ALLOWED)
        cols = to_lab(PAL[allowed])
        grid = (np.arange(64) * 4 + 2).astype(np.float64)
        r, g, b = np.meshgrid(grid, grid, grid, indexing="ij")
        q = to_lab(np.stack([r, g, b], -1).reshape(-1, 3))
        w = np.array([1.0, 1.7, 1.7])
        best = np.zeros(len(q), dtype=np.int64)
        for start in range(0, len(q), 32768):
            part = q[start:start + 32768]
            d = (((part[:, None, :] - cols[None, :, :]) ** 2) * w).sum(-1)
            best[start:start + 32768] = d.argmin(1)
        _LUT = allowed[best].reshape(64, 64, 64).astype(np.uint8)
    return _LUT


def to_index(img: np.ndarray) -> np.ndarray:
    c = np.clip(img * 255, 0, 255).astype(np.int64) >> 2
    return lut()[c[..., 0], c[..., 1], c[..., 2]]

# ---------------------------------------------------------------- 點雲


class Cloud:
    def __init__(self):
        self.p, self.n, self.c, self.ao, self.sw = [], [], [], [], []

    def add(self, p, n, c, ao=1.0, snow_w=0.0):
        p = np.atleast_2d(p)
        k = len(p)
        if k == 0:
            return
        self.p.append(p)
        self.n.append(np.broadcast_to(np.atleast_2d(n), (k, 3)))
        self.c.append(np.broadcast_to(np.atleast_2d(c), (k, 3)))
        self.ao.append(np.broadcast_to(np.atleast_1d(ao), (k,)))
        self.sw.append(np.broadcast_to(np.atleast_1d(snow_w), (k,)))

    def arrays(self):
        if not self.p:
            return (np.zeros((0, 3)),) * 3 + (np.zeros(0), np.zeros(0))
        return (np.concatenate(self.p), np.concatenate(self.n), np.concatenate(self.c),
                np.concatenate(self.ao), np.concatenate(self.sw))


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def sphere_dirs(rng, k):
    return unit(rng.normal(size=(k, 3)))


def cylinder(cloud, a, b, r0, r1, colour, rng, density=1.8, ao=0.92, rough=0.12, snow_w=0.0):
    """圓柱（樹幹、粗枝、仙人掌莖）：表面點帶法線。"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    axis = b - a
    length = np.linalg.norm(axis)
    if length < 1e-6:
        return
    d = axis / length
    ref = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    u = unit(np.cross(d, ref))
    v = np.cross(d, u)
    rmax = max(r0, r1)
    k = int(max(8, density * length * max(rmax, 0.55) * 2 * math.pi))
    t = rng.random(k)
    ang = rng.random(k) * 2 * math.pi
    rad = r0 + (r1 - r0) * t
    nrm = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    pts = a + t[:, None] * axis + nrm * rad[:, None]
    col = np.asarray(colour) * (1 + rough * rng.normal(size=(k, 1)))
    sw = np.clip(nrm[:, 2], 0, 1) * snow_w if snow_w > 0 else 0.0
    cloud.add(pts, nrm, np.clip(col, 0, 1), ao, sw)


def leaf_tuft(cloud, c, rx, ry, rz, colour_fn, rng, density, crown_c, crown_r,
              holes=0.14, jitter=0.36, snow_bias=0.0):
    """方向性葉叢（橢球殼上的葉點）：法線連貫（每團都有清楚的受光左上與背光右下），並記錄乾淨的幾何積雪權重。"""
    r_eq = (rx * ry * rz) ** (1 / 3)
    k = int(density * 4.2 * math.pi * max(r_eq, 0.8) ** 2)
    if k <= 0:
        return
    u = sphere_dirs(rng, k)
    rad = 0.62 + 0.38 * np.sqrt(rng.random(k))
    local = u * (rad[:, None] * np.array([rx, ry, rz]))
    pts = c + local
    if holes > 0 and r_eq > 2.2:
        keep = np.ones(k, dtype=bool)
        for _ in range(int(holes * 9)):
            hc = c + unit(rng.normal(size=3)) * np.array([rx, ry, rz]) * 0.82
            keep &= np.linalg.norm((pts - hc) / np.maximum([rx, ry, rz], 1e-6), axis=1) > (0.20 + 0.18 * rng.random())
        pts, u = pts[keep], u[keep]
    if len(pts) == 0:
        return
    outer = unit(pts - crown_c)
    geom_n = unit(0.62 * u + 0.38 * outer)
    nrm = unit(geom_n + rng.normal(size=u.shape) * jitter)
    depth = np.linalg.norm(pts - crown_c, axis=1) / max(crown_r, 1e-6)
    # 葉團底面明顯壓暗，拉出原版般的立體層次
    under = np.clip(0.55 + 0.45 * u[:, 2], 0.30, 1.0)
    ao = (0.34 + 0.66 * np.clip(depth, 0, 1) ** 0.85) * under
    sw = np.clip(geom_n[:, 2] * 0.72 + u[:, 2] * 0.28 + snow_bias, 0.0, 1.0)
    cloud.add(pts, nrm, colour_fn(len(pts)), ao, sw)


def branch_to(cloud, a, b, r0, r1, colour, rng, twig_density=1.6, ao=0.88, snow_w=0.0):
    cylinder(cloud, a, b, r0, r1, colour, rng, density=twig_density, ao=ao, snow_w=snow_w)

# ---------------------------------------------------------------- 季節配色


def season_colours(cfg, season, rng):
    """→ (葉色函式 or None, 葉量 0–1, 花色 or None)。季節：0 秋、1 冬、2 春、3 夏、4 枯萎。"""
    base = LEAF[cfg.get("leaf", "green")]
    if season == 4:
        return None, 0.0, None
    if cfg.get("evergreen"):
        return _solid(base, 0.10), 1.0 if season != 1 else 0.96, None
    if season == 1:
        return None, 0.0, None
    if season == 0:
        pal = AUTUMN[cfg.get("autumn", "orange")]
        return _mixed(pal, base, cfg.get("autumn_green", 0.15)), 0.88, None
    if season == 2:
        spring = LEAF[cfg["spring"]] if "spring" in cfg else SPRING
        flowers = FLOWERS.get(cfg.get("flowers"))
        return _solid(spring, 0.10), 0.20 if flowers is None else 0.24, flowers
    return _solid(base, 0.10), 1.0, None


def _solid(base, jitter):
    def fn(rng, k):
        tint = 1 + jitter * rng.normal(size=(k, 1))
        hue = rng.normal(size=(k, 3)) * 0.018
        return np.clip(base * tint + hue, 0, 1)
    return fn


def _mixed(pal, green, green_share):
    choices = pal + [green]
    weights = np.array([(1 - green_share) / len(pal)] * len(pal) + [green_share])

    def fn(rng, k):
        main = choices[rng.choice(len(choices), p=weights)]
        cols = np.tile(main, (k, 1))
        mix = rng.random(k) < 0.28
        if mix.any():
            cols[mix] = np.array(choices)[rng.choice(len(choices), size=int(mix.sum()), p=weights)]
        return np.clip(cols * (1 + 0.10 * rng.normal(size=(k, 1))), 0, 1)
    return fn

# ---------------------------------------------------------------- 闊葉樹（含清晰冬季骨架＋蓬鬆多葉冠丘）


def build_deciduous(cfg, season, rng, H, snow):
    """闊葉樹：低分叉纖細樹幹（比照原版 12–20% 起分枝、幹寬僅 3–5px）＋通透細碎的蓬鬆羽狀葉冠。"""
    cloud = Cloud()
    cw, ch, ccy = cfg.get("crown", (0.46, 0.62, 0.54))
    rx, rz = H * cw * 0.62, H * ch * 0.48
    cz = H * ccy
    crown_c = np.array([0, 0, cz])
    trunk_h = cfg.get("trunk_h", 0.16)
    trunk_top = H * trunk_h
    bark = BARK[cfg.get("trunk", "brown")] if season != 4 else DEAD
    # 白樺只有低段主幹淺灰白，上部枝條與細枝一律用深木褐
    limb_col = TWIG_DARK * 1.15 if cfg.get("trunk") == "light" else bark * 0.82
    twig_col = TWIG_DARK if season != 4 else DEAD * 0.85
    # 纖細自然的樹幹半徑（成熟樹幹寬約 3.5–5px，不再像 10px 粗水泥柱）
    tr = max(0.65, H * 0.017 * cfg.get("trunk_w", 1.0))

    lean = np.array([rng.normal() * H * 0.014, rng.normal() * H * 0.014, 0.0])
    mid_t = lean * 0.5 + np.array([0, 0, trunk_top * 0.55])
    top_t = lean + np.array([0, 0, trunk_top])
    cylinder(cloud, (0, 0, 0), mid_t, tr * 1.18, tr * 0.90, bark, rng, ao=0.88)
    cylinder(cloud, mid_t, top_t, tr * 0.90, tr * 0.72, bark, rng, ao=0.85)
    # 主幹一路細長向上延伸進樹冠，沿途層層分出斜上枝條
    upper_t = top_t + np.array([rng.normal() * rx * 0.06, rng.normal() * rx * 0.06, rz * 0.95])
    branch_to(cloud, top_t, upper_t, tr * 0.68, tr * 0.22, limb_col, rng, ao=0.72)

    leafcol, amount, flowers = season_colours(cfg, season, rng)
    bare = (leafcol is None or amount == 0)

    n_limbs = int(cfg.get("limbs", 8)) + 3
    small_boost = 1.0 + max(0.0, (60.0 - H) / 45.0) * 0.48
    hole_scale = min(1.0, max(0.35, H / 65.0))
    dens = cfg.get("density", 1.0) * amount * cfg.get("airy", 1.0) * small_boost
    lobe_scale = cfg.get("lobe_r", 0.36)
    base_ang = rng.random() * 2 * math.pi

    for i in range(n_limbs):
        is_apex = (i == n_limbs - 1)
        is_inner = (i >= n_limbs - 3 and not is_apex)
        if is_apex:
            ang = rng.random() * 2 * math.pi
            rad_f = 0.12 + 0.14 * rng.random()
            z_f = 0.76 + 0.20 * rng.random()
            start = upper_t
        elif is_inner:
            ang = base_ang + i * 2.4 + rng.normal() * 0.3
            rad_f = 0.20 + 0.24 * rng.random()
            z_f = -0.10 + 0.55 * rng.random()
            start = top_t + (upper_t - top_t) * (0.25 + 0.45 * rng.random())
        else:
            ang = base_ang + (i / (n_limbs - 3)) * 2 * math.pi + rng.normal() * 0.24
            tier = (i % 4) / 3.0
            rad_f = (0.52 + 0.34 * rng.random()) * (1.0 - 0.24 * tier)
            z_f = -0.58 + 1.32 * tier + rng.normal() * 0.14
            start = top_t + (upper_t - top_t) * np.clip(0.05 + 0.80 * tier, 0, 1)

        lobe_c = crown_c + np.array([math.cos(ang) * rx * rad_f, math.sin(ang) * rx * rad_f, rz * z_f])
        lobe_c[2] = max(lobe_c[2], trunk_top * 0.90 + H * 0.04)
        mid = start + (lobe_c - start) * 0.50 + np.array([rng.normal() * rx * 0.07, rng.normal() * rx * 0.07, -H * 0.01])
        if not is_inner or not bare:
            branch_to(cloud, start, mid, tr * 0.44, tr * 0.26, limb_col, rng, twig_density=1.7, ao=0.78, snow_w=0.45 if bare else 0.0)
            branch_to(cloud, mid, lobe_c, tr * 0.26, tr * 0.14, limb_col, rng, twig_density=1.5, ao=0.74, snow_w=0.55 if bare else 0.0)

        n_sub = 4 if not is_inner else 3
        r_lobe = min(rx, rz) * lobe_scale * (0.82 + 0.32 * rng.random())
        for j in range(n_sub):
            sa = ang + (j - (n_sub - 1) / 2) * 0.65 + rng.normal() * 0.24
            s_reach = r_lobe * (0.58 + 0.42 * rng.random())
            s_z = r_lobe * (0.14 + 0.58 * rng.random() - 0.18 * (j == 0))
            sub_c = lobe_c + np.array([math.cos(sa) * s_reach, math.sin(sa) * s_reach, s_z])
            sub_c[2] = max(sub_c[2], trunk_top * 0.85)
            if not is_inner:
                branch_to(cloud, lobe_c, sub_c, tr * 0.15, max(0.28, tr * 0.08), twig_col, rng,
                          twig_density=1.35 if bare else 0.95, ao=0.74, snow_w=0.65 if bare else 0.0)
                if bare or amount < 0.35:
                    for k in range(2):
                        ta = sa + (k - 0.5) * 0.72 + rng.normal() * 0.2
                        t_len = r_lobe * (0.45 + 0.35 * rng.random())
                        tip = sub_c + np.array([math.cos(ta) * t_len, math.sin(ta) * t_len, t_len * (0.48 + 0.36 * rng.random())])
                        branch_to(cloud, sub_c, tip, 0.32, 0.20, twig_col, rng, twig_density=1.1, ao=0.76, snow_w=0.7 if bare else 0.0)
            if bare:
                continue
            # 細碎通透葉簇（留出微光孔隙，並依尺寸收斂孔洞避免縮小時變得稀疏）
            sr = r_lobe * (0.32 + 0.14 * rng.random()) * (0.76 + 0.24 * amount)
            leaf_tuft(cloud, sub_c, sr * 1.08, sr * 1.08, sr * 0.84,
                      lambda kk: leafcol(rng, kk), rng, dens * 1.12, crown_c, max(rx, rz) * 1.05,
                      holes=(0.30 if amount > 0.7 else 0.42) * hole_scale, jitter=0.46)
            for _ in range(3):
                off = unit(rng.normal(size=3) + np.array([0, 0, 0.15])) * sr * (0.55 + 0.45 * rng.random())
                mr = sr * (0.38 + 0.18 * rng.random())
                leaf_tuft(cloud, sub_c + off, mr * 1.08, mr * 1.08, mr * 0.82,
                          lambda kk: leafcol(rng, kk), rng, dens * 1.05, crown_c, max(rx, rz) * 1.05,
                          holes=0.26 * hole_scale, jitter=0.48)
                if flowers is not None and rng.random() < 0.65:
                    leaf_tuft(cloud, sub_c + off + np.array([0, 0, mr * 0.2]), mr * 0.68, mr * 0.68, mr * 0.48,
                              lambda kk: np.tile(flowers, (kk, 1)), rng, dens * 0.55, crown_c, max(rx, rz),
                              holes=0.0, jitter=0.30)

    if snow:
        _snow(cloud, 0.50 if not bare else 0.52)
    return cloud


# ---------------------------------------------------------------- 針葉樹（多層羽狀下垂枝棚＋支援落葉針葉季節）


def build_conifer(cfg, season, rng, H, snow):
    """針葉樹：豐滿圓錐輪廓、多層重疊下垂羽狀枝棚（每層上亮下暗），落葉針葉樹隨季節變紅或落葉。"""
    cloud = Cloud()
    bark = BARK[cfg.get("trunk", "dark")] if season != 4 else DEAD
    tr = max(0.60, H * 0.017)
    cylinder(cloud, (0, 0, 0), (0, 0, H * 0.98), tr * 1.15, 0.35, bark, rng, ao=0.80)

    is_decid = cfg.get("deciduous_conifer", False)
    if season == 4:
        leafcol, amount = None, 0.0
    elif is_decid:
        leafcol, amount, _ = season_colours(cfg, season, rng)
    else:
        leafcol, amount = _solid(LEAF[cfg.get("leaf", "conifer")], 0.11), 1.0

    bare = (leafcol is None or amount == 0)
    z0 = H * cfg.get("z0", 0.10)
    R = H * 0.255 * cfg.get("width", 1.0)
    whorls = max(8, int(round(int(cfg.get("whorls", 15)) * min(1.0, 0.58 + H / 130.0))))
    crown_c = np.array([0, 0, H * 0.44])
    az0 = rng.random() * 2 * math.pi

    for k in range(whorls):
        t = k / max(whorls - 1, 1)
        z = z0 + (H * 0.96 - z0) * (t ** 0.96)
        # 底部略微飽滿、頂部收尖成清晰圓錐
        profile = (1.0 - t) ** 0.82 * (0.90 + 0.14 * math.sin(t * math.pi))
        rmax = R * profile + H * 0.018
        n_boughs = max(4, int(9 * (1.0 - 0.55 * t)))
        az_tier = az0 + k * 2.39996  # 黃金角錯開各層枝條
        for b in range(n_boughs):
            a = az_tier + (b / n_boughs) * 2 * math.pi + rng.normal() * 0.18
            length = rmax * (0.78 + 0.32 * rng.random())
            droop = -0.34 + 0.26 * t  # 下層枝條自然下垂，上層略微平展
            d = unit(np.array([math.cos(a), math.sin(a), droop]))
            start = np.array([0, 0, z])
            end = start + d * length
            branch_to(cloud, start, end, max(0.35, tr * 0.42 * (1 - 0.5 * t)), 0.28, bark, rng,
                      twig_density=1.4 if bare else 0.9, ao=0.72, snow_w=0.6 if bare else 0.0)
            if season == 4:
                cloud.add(end + rng.normal(size=(4, 3)) * 0.7, np.tile([0, 0, 1.0], (4, 1)), rgb(118, 86, 54), 0.85, 0.3)
                continue
            if bare:
                continue
            # 沿每條枝棚鋪設 3–4 片重疊的扁平針葉羽片（寬度 > 厚度，上表面受光積雪、下表面深影）
            n_pads = 4 if t < 0.65 else 3
            for j in range(n_pads):
                f = (j + 0.7) / n_pads
                c = start + d * (length * f) + np.array([0, 0, H * 0.008])
                pr = H * 0.044 * (1.18 - 0.42 * f) * (1.05 - 0.48 * t) * (0.85 + 0.30 * rng.random())
                pr = max(pr, 1.2)
                # 羽片上層壓扁成自然針葉棚，並略微向上傾斜受光
                leaf_tuft(cloud, c, pr * 1.25, pr * 1.25, pr * 0.62,
                          lambda kk: leafcol(rng, kk), rng, 2.05 * amount, crown_c, H * 0.48,
                          holes=0.05, jitter=0.28, snow_bias=0.14 * (0.3 + 0.7 * f))

    # 頂梢尖芽
    if not bare:
        apex_r = max(1.4, H * 0.028)
        leaf_tuft(cloud, np.array([0, 0, H * 0.96]), apex_r, apex_r, apex_r * 1.4,
                  lambda kk: leafcol(rng, kk), rng, 2.0 * amount, crown_c, H * 0.5,
                  holes=0.0, jitter=0.25, snow_bias=0.25)

    if snow:
        _snow(cloud, 0.48)
    return cloud


# ---------------------------------------------------------------- 松樹（蘇格蘭松、石松：厚實層疊傘冠，不再光桿細棒）


def build_pine(cfg, season, rng, H, snow):
    """松樹（蘇格蘭松、石松）：粗壯暖色彎幹，從 34% 高度起分出厚實斜枝與層疊傘狀松針雲冠。"""
    cloud = Cloud()
    bark = BARK[cfg.get("trunk", "red")] if season != 4 else DEAD
    tr = max(0.65, H * 0.019)
    lean = np.array([rng.normal() * H * 0.035, rng.normal() * H * 0.035, 0.0])
    mid = lean * 0.45 + np.array([0, 0, H * 0.42])
    top = lean + np.array([0, 0, H * 0.88])
    cylinder(cloud, (0, 0, 0), mid, tr * 1.25, tr * 0.88, bark, rng, ao=0.88)
    cylinder(cloud, mid, top, tr * 0.88, tr * 0.45, bark, rng, ao=0.82)

    base = LEAF[cfg.get("leaf", "pine")]
    colfn = _solid(base, 0.11)
    crown_c = top * 0.78
    n_tiers = int(cfg.get("tufts", 11))
    az0 = rng.random() * 2 * math.pi

    for k in range(n_tiers):
        t = k / max(n_tiers - 1, 1)
        z = H * (0.38 + 0.54 * t)
        start = lean * (z / H) + np.array([0, 0, z])
        a = az0 + k * 2.39996 + rng.normal() * 0.22
        # 中上層展開寬傘冠，頂部微圓頂
        reach = H * (0.15 + 0.12 * math.sin(t * math.pi)) * (0.82 + 0.34 * rng.random())
        if k == n_tiers - 1:
            reach *= 0.35
        end = start + np.array([math.cos(a) * reach, math.sin(a) * reach, H * (0.04 + 0.04 * t)])
        branch_to(cloud, start, end, tr * 0.42, tr * 0.22, bark, rng, ao=0.78)
        if season == 4:
            continue
        # 每枝頂端由 9 顆通透細碎的暖綠松針小叢組成（留出透光縫隙，對應原版 Shot 04 河岸松樹質感）
        for j in range(9):
            ang_p = j / 9 * 2 * math.pi + rng.random() * 0.55
            rad_p = reach * (0.14 + 0.44 * rng.random())
            off = np.array([math.cos(ang_p) * rad_p, math.sin(ang_p) * rad_p, rng.normal() * H * 0.016])
            c = end + off
            r = H * (0.036 + 0.016 * rng.random()) * (1.06 - 0.16 * t)
            leaf_tuft(cloud, c, r * 1.32, r * 1.32, r * 0.56,
                      lambda kk: colfn(rng, kk), rng, 1.75 if H < 70 else 1.48, crown_c, H * 0.42,
                      holes=0.16 if H < 70 else 0.28, jitter=0.48, snow_bias=0.18)

    if snow:
        _snow(cloud, 0.48)
    return cloud


# ---------------------------------------------------------------- 柱狀常綠樹


def build_column(cfg, season, rng, H, snow):
    """柱狀（義大利柏、愛爾蘭紫杉、黃金扁柏）：細密向上的常綠針葉柱，帶清晰立體陰影。"""
    cloud = Cloud()
    bark = BARK["dark"]
    cylinder(cloud, (0, 0, 0), (0, 0, H * 0.28), max(0.7, H * 0.022), 0.55, bark, rng, ao=0.8)
    leafcol, amount, _ = season_colours({**cfg, "evergreen": True}, season, rng)
    if leafcol is None:
        return cloud
    w = H * 0.145 * cfg.get("width", 0.65) * 1.45
    crown_c = np.array([0, 0, H * 0.52])
    for k in range(16):
        t = k / 15
        z = H * (0.10 + 0.84 * t)
        taper = math.sin(math.pi * (0.12 + 0.84 * t)) ** 0.72
        r = max(1.3, w * max(taper, 0.22) * (0.88 + 0.22 * rng.random()))
        c = np.array([rng.normal() * r * 0.14, rng.normal() * r * 0.14, z])
        leaf_tuft(cloud, c, r * 1.05, r * 1.05, r * 0.92,
                  lambda kk: leafcol(rng, kk), rng, 1.6 * amount, crown_c, H * 0.46,
                  holes=0.06, jitter=0.30, snow_bias=0.20 * t)
    if snow:
        _snow(cloud, 0.48)
    return cloud


# ---------------------------------------------------------------- 垂柳


def build_weeping(cfg, season, rng, H, snow):
    """垂柳：蓬鬆圓頂樹冠＋自然垂墜的細長柳絲簾幕。"""
    cloud = build_deciduous({**cfg, "crown": (0.44, 0.36, 0.70), "limbs": 6, "lobe_r": 0.44}, season, rng, H, False)
    leafcol, amount, _ = season_colours(cfg, season, rng)
    for _ in range(52):
        a = rng.random() * 2 * math.pi
        rr = H * 0.23 * (0.72 + 0.38 * rng.random())
        top = np.array([math.cos(a) * rr, math.sin(a) * rr, H * (0.70 + 0.14 * rng.random())])
        length = H * (0.32 + 0.26 * rng.random())
        out = np.array([math.cos(a), math.sin(a), 0]) * H * 0.085
        t = np.linspace(0, 1, 24)[:, None]
        curve = top + out * np.sin(t * math.pi / 2) - np.array([0, 0, 1.0]) * length * t ** 1.35
        if leafcol is None or amount == 0:
            for q0, q1 in zip(curve[::2][:-1], curve[::2][1:]):
                branch_to(cloud, q0, q1, 0.28, 0.22, TWIG_DARK, rng, twig_density=0.75, ao=0.75)
            continue
        m = max(10, int(length * 4.0 * amount))
        idx = rng.integers(0, len(curve), m)
        pts = curve[idx] + rng.normal(size=(m, 3)) * np.array([0.85, 0.85, 0.35])
        nrm = unit(np.tile([math.cos(a), math.sin(a), 0.25], (m, 1)) + rng.normal(size=(m, 3)) * 0.35)
        ao = 0.55 + 0.38 * (1.0 - idx / max(len(curve) - 1, 1))
        cloud.add(pts, nrm, leafcol(rng, m), ao, 0.25)
    if snow:
        _snow(cloud, 0.50)
    return cloud


# ---------------------------------------------------------------- 棕櫚與沙漠低矮扇棕


def build_palm(cfg, season, rng, H, snow):
    """棕櫚：QPALM 為彎曲海岸椰子樹；SPALM（silverpalm）為纖細沙漠銀棕（細灰褐幹＋通透銀綠羽狀圓冠）。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "green")]
    if cfg.get("shape") == "silverpalm":
        # 沙漠銀棕（SPALM 11×21 → 40×73）：纖細微彎的日曬灰褐幹＋通透銀橄欖綠扇葉圓冠
        lean = np.array([rng.normal() * H * 0.04, rng.normal() * H * 0.04, 0.0])
        tr = max(0.75, H * 0.024)
        segs = 8
        prev = np.zeros(3)
        bark = BARK["desert_tan"] if season != 4 else DEAD
        for k in range(1, segs + 1):
            t = k / segs
            p = lean * (t * t) + np.array([0, 0, H * 0.62 * t])
            col = bark * (0.86 if k % 2 else 1.06)
            cylinder(cloud, prev, p, tr * (1.2 - 0.35 * t), tr * (1.1 - 0.35 * t), col, rng, density=2.2, ao=0.90)
            prev = p
        top = prev
        if season == 4:
            # 枯萎態：稀疏殘枝與少許灰褐殘葉
            for f in range(6):
                a = f / 6 * 2 * math.pi + rng.random() * 0.4
                d = unit(np.array([math.cos(a), math.sin(a), 0.35]))
                end = top + d * (H * 0.24)
                branch_to(cloud, top, end, 0.45, 0.25, DEAD, rng, ao=0.85)
                leaf_tuft(cloud, end, H * 0.06, H * 0.06, H * 0.05, lambda kk: np.tile(base * 0.72, (kk, 1)),
                          rng, 0.7, top, H * 0.25, holes=0.35, jitter=0.45)
            return cloud
        # 14 片向外展開再微垂的銀橄欖綠羽狀棕櫚葉，留出通透縫隙
        for f in range(14):
            a = f / 14 * 2 * math.pi + rng.random() * 0.3
            tier = (f % 3) / 2.0
            d = np.array([math.cos(a), math.sin(a), 0.0])
            length = H * (0.24 + 0.11 * (1.0 - 0.3 * tier))
            lift = H * (0.14 + 0.18 * tier)
            droop = H * (0.20 + 0.10 * (1.0 - tier))
            m = max(14, int(length * 1.4))
            t = np.linspace(0, 1, m)
            spine = top + d * (length * t)[:, None] + np.array([0, 0, 1]) * (lift * t - droop * t * t)[:, None]
            side = np.cross(d, [0, 0, 1])
            for s in (-1, 0, 1):
                w_leaf = H * 0.048 * np.sin(np.pi * np.clip(t * 1.05, 0, 1))
                pts = spine + side * (s * w_leaf)[:, None] + rng.normal(size=(m, 3)) * 0.35
                nrm = unit(np.tile([math.cos(a) * 0.35, math.sin(a) * 0.35, 0.85], (m, 1)) + side * (s * 0.35))
                ao = 0.62 + 0.38 * (0.4 + 0.6 * tier)
                col = np.clip(base * (0.90 + 0.20 * rng.normal(size=(m, 1))), 0, 1)
                cloud.add(pts, nrm, col, ao, 0.50)
        return cloud

    # 高大海岸棕櫚（QPALM）：優雅弧彎環紋樹幹＋11 片下垂羽狀大葉
    lean = np.array([H * 0.085, -H * 0.03, 0])
    segs = 11
    prev = np.zeros(3)
    for k in range(1, segs + 1):
        t = k / segs
        p = lean * (t * t) + np.array([0, 0, H * 0.78 * t])
        col = BARK["brown"] * (0.80 if k % 2 else 1.08)
        cylinder(cloud, prev, p, H * 0.032 * (1.15 - 0.3 * t), H * 0.025, col, rng, density=2.2, ao=0.86)
        prev = p
    top = prev
    for f in range(11):
        a = f / 11 * 2 * math.pi + rng.random() * 0.22
        d = np.array([math.cos(a), math.sin(a), 0])
        length = H * (0.34 + 0.08 * rng.random())
        lift = H * (0.14 if f % 2 == 0 else 0.08)
        droop = H * (0.28 if f % 2 == 0 else 0.34)
        m = 56
        t = np.linspace(0, 1, m)
        spine = top + d * length * t[:, None] + np.array([0, 0, 1]) * (lift * t - droop * t * t)[:, None]
        side = np.cross(d, [0, 0, 1])
        for s in (-1, 1):
            leaf = spine + side * s * (H * 0.075 * np.sin(np.pi * t) * (0.65 + 0.35 * rng.random()))[:, None]
            for q in np.linspace(0.25, 1.0, 4):
                pts = spine + (leaf - spine) * q
                nrm = unit(np.tile([0, 0, 1.0], (m, 1)) + side * s * 0.45)
                ao = 0.55 + 0.45 * (1.0 - 0.35 * t)
                cloud.add(pts, nrm, np.clip(base * (1 + 0.09 * rng.normal(size=(m, 1))), 0, 1), ao, 0.55)
    if snow:
        _snow(cloud, 0.50)
    return cloud


# ---------------------------------------------------------------- 仙人掌（修長纖細、日曬淡鼠尾草綠、三種分枝姿態）


def build_cactus(cfg, season, rng, H, snow):
    """仙人掌（CACTUS1/2/3）：全部為修長纖細（莖寬僅 2–3px）的日曬鼠尾草綠巨柱仙人掌，三種不同彎臂造型。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "cactus")]
    kind = cfg.get("shape", "saguaro1")

    def ribbed(a, b, r, ribs=6):
        a, b = np.asarray(a, float), np.asarray(b, float)
        axis = b - a
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        d = axis / length
        ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
        u = unit(np.cross(d, ref))
        v = np.cross(d, u)
        k = int(4.5 * length * max(r, 0.7) * 2 * math.pi + 40)
        t = rng.random(k)
        ang = rng.random(k) * 2 * math.pi
        rib = 1.0 + 0.12 * np.cos(ang * ribs)
        radial = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
        tang = np.cos(ang)[:, None] * v - np.sin(ang)[:, None] * u
        nrm = unit(radial + 0.30 * np.sin(ang * ribs)[:, None] * tang)
        pts = a + t[:, None] * axis + radial * (r * rib)[:, None]
        col = base * (0.88 + 0.24 * (np.cos(ang * ribs) > 0.35)[:, None])
        cloud.add(pts, nrm, np.clip(col, 0, 1), 0.96, 0.0)
        m = int(3.0 * math.pi * max(r, 0.7) ** 2 + 18)
        uu = sphere_dirs(rng, m)
        uu = uu[(uu @ d) > 0]
        cloud.add(b + uu * r, uu, base * 1.06, 0.98, 0.0)

    def curved_arm(z0, z1, ang_xy, reach, arm_r):
        dxy = np.array([math.cos(ang_xy), math.sin(ang_xy), 0.0])
        p0 = np.array([0.0, 0.0, H * z0])
        p1 = p0 + dxy * (H * reach * 0.72) + np.array([0.0, 0.0, H * 0.02])
        p2 = p0 + dxy * (H * reach) + np.array([0.0, 0.0, H * 0.11])
        p3 = p2 + np.array([0.0, 0.0, max(1.0, H * (z1 - z0 - 0.11))])
        ribbed(p0, p1, arm_r)
        ribbed(p1, p2, arm_r)
        ribbed(p2, p3, arm_r)

    # 纖細主莖：雙臂對齊世界座標 ±X 或 ±Y（僅微調 ±0.12 rad），確保等角投影 sx=X-Y 在 4 個旋轉方向
    # 都對稱伸向主莖左右兩側（|sx| ≈ 1.0），絕不會在 rot=1/3 縮成筆直單桿
    r = max(0.75, min(1.35, H * 0.044))
    arm_r = max(0.65, r * 0.80)
    if kind == "saguaro2":
        # 雙臂一低一高不對稱展開
        ribbed((0, 0, 0), (0, 0, H * 0.96), r)
        curved_arm(0.28, 0.72, 0.08, 0.16, arm_r)
        curved_arm(0.46, 0.88, math.pi - 0.10, 0.15, arm_r)
    elif kind == "saguaro3":
        # 雙臂交錯＋高位第三短臂（3D 輪廓在各角度皆生動自然）
        ribbed((0, 0, 0), (H * 0.02, -H * 0.02, H * 0.95), r)
        curved_arm(0.24, 0.64, math.pi / 2 + 0.10, 0.16, arm_r)
        curved_arm(0.44, 0.84, -math.pi / 2 - 0.08, 0.15, arm_r)
        curved_arm(0.56, 0.88, 0.06, 0.12, arm_r * 0.90)
    else:
        # 經典雙臂巨柱仙人掌
        ribbed((0, 0, 0), (0, 0, H * 0.95), r)
        curved_arm(0.32, 0.78, -0.08, 0.16, arm_r)
        curved_arm(0.42, 0.84, math.pi + 0.10, 0.16, arm_r)
    return cloud


# ---------------------------------------------------------------- 約書亞樹與樹狀絲蘭


def build_rosette(cfg, season, rng, H, snow):
    """約書亞樹（日曬淺灰褐扭曲分叉樹幹＋枝端淺鼠尾草綠尖刺簇）與樹狀絲蘭（纖細直幹＋頂端淡銀綠尖葉蓮座）。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "desert_sage")]
    bark = BARK["desert_tan"]
    tips = []
    if cfg.get("shape") == "joshua":
        # 約書亞樹（17×27 → 48×53）：日曬淺灰褐扭曲主幹，優雅分成 U 字型多叉彎枝，留出通透空隙
        tr = max(0.95, H * 0.044)
        p_base = np.array([0.0, 0.0, 0.0])
        p_fork = np.array([rng.normal() * H * 0.02, rng.normal() * H * 0.02, H * 0.34])
        cylinder(cloud, p_base, p_fork, tr * 1.15, tr * 0.88, bark, rng, density=2.8, ao=0.92)
        # 3 條主彎臂（寬展 U 型弧度），每條再各分 2 條末枝
        az0 = 0.45 + rng.random() * 0.4
        for k in range(3):
            a = az0 + k * (2 * math.pi / 3) + rng.normal() * 0.18
            dxy = np.array([math.cos(a), math.sin(a), 0.0])
            elbow = p_fork + dxy * (H * (0.20 + 0.06 * rng.random())) + np.array([0, 0, H * 0.16])
            upper = elbow + dxy * (H * 0.06) + np.array([0, 0, H * (0.18 + 0.06 * rng.random())])
            cylinder(cloud, p_fork, elbow, tr * 0.72, tr * 0.56, bark, rng, density=2.6, ao=0.90)
            cylinder(cloud, elbow, upper, tr * 0.56, tr * 0.42, bark, rng, density=2.4, ao=0.92)
            for s in (-1, 1):
                sa = a + s * (0.65 + 0.25 * rng.random())
                tip = upper + np.array([math.cos(sa) * H * 0.13, math.sin(sa) * H * 0.13, H * (0.12 + 0.08 * rng.random())])
                cylinder(cloud, upper, tip, tr * 0.38, tr * 0.26, bark * 1.04, rng, density=2.2, ao=0.94)
                tips.append((tip, H * 0.135))
        # 每個末枝頂端長出通透的淺鼠尾草綠星狀尖葉簇
        for c, length in tips:
            for _ in range(46):
                d = unit(rng.normal(size=3) + np.array([0, 0, 0.55]))
                t = np.linspace(0, 1, max(4, int(length * 1.8) + 2))[:, None]
                pts = c + d * (length * t)
                nrm = np.tile(unit(d + np.array([0, 0, 0.45])), (len(pts), 1))
                ao = 0.68 + 0.32 * t[:, 0]
                col = np.clip(base * (0.86 + 0.26 * rng.random()), 0, 1)
                cloud.add(pts, nrm, col, ao, 0.0)
    else:
        # 樹狀絲蘭（YUKKA 8×11 → 26×32）：纖細直立褐幹（約 55% 高）＋頂端寬張的淡銀綠星狀尖葉叢
        tr = max(0.65, H * 0.042)
        top = np.array([0.0, 0.0, H * 0.56])
        cylinder(cloud, (0, 0, 0), top, tr * 1.1, tr * 0.85, BARK["brown"] * 1.15, rng, density=2.8, ao=0.90)
        # 兩叢略錯開的頂端尖葉蓮座（有如原版 YUKKA 的蓬鬆淺綠劍葉冠）
        for off in ((0.0, 0.0, 0.0), (H * 0.05, -H * 0.04, H * 0.04)):
            c = top + np.array(off)
            length = H * 0.36
            for _ in range(52):
                d = unit(rng.normal(size=3) + np.array([0, 0, 0.35]))
                t = np.linspace(0, 1, max(4, int(length * 2.0) + 2))[:, None]
                pts = c + d * (length * t)
                nrm = np.tile(unit(d + np.array([0, 0, 0.5])), (len(pts), 1))
                ao = 0.65 + 0.35 * t[:, 0]
                col = np.clip(base * (0.85 + 0.28 * rng.random()), 0, 1)
                cloud.add(pts, nrm, col, ao, 0.0)
    return cloud


# ---------------------------------------------------------------- 樹種表

SPECIES = {
    # 闊葉（17 種：低分叉 14–22%、纖細樹幹、通透細碎羽狀葉冠，比例對齊原版）
    "oak": dict(build="deciduous", leaf="green", crown=(0.50, 0.72, 0.52), limbs=8, lobe_r=0.38, autumn="rust", autumn_green=0.08, trunk_w=1.15, trunk_h=0.14),
    "beech": dict(build="deciduous", leaf="darkgreen", crown=(0.46, 0.66, 0.54), limbs=7, lobe_r=0.36, autumn="orange", trunk_h=0.16),
    "birch": dict(build="deciduous", leaf="avocado", crown=(0.42, 0.68, 0.54), limbs=7, lobe_r=0.34, autumn="yellow", trunk="light", airy=0.82, trunk_w=0.90, trunk_h=0.16),
    "chestnut": dict(build="deciduous", leaf="green", crown=(0.48, 0.64, 0.54), limbs=8, lobe_r=0.38, autumn="orange", flowers="cream", trunk_h=0.16),
    "elm": dict(build="deciduous", leaf="green", crown=(0.45, 0.68, 0.54), limbs=7, lobe_r=0.36, autumn="yellow", trunk_h=0.20),
    "copperbeech": dict(build="deciduous", leaf="copper", crown=(0.48, 0.64, 0.54), limbs=8, lobe_r=0.38, autumn="copper", spring="copper", trunk_h=0.16),
    "frisia": dict(build="deciduous", leaf="gold", crown=(0.46, 0.64, 0.54), limbs=7, lobe_r=0.36, autumn="yellow", spring="gold", airy=0.84, trunk_h=0.18),
    "ash": dict(build="deciduous", leaf="avocado", crown=(0.46, 0.66, 0.55), limbs=7, lobe_r=0.34, autumn="yellow", airy=0.80, trunk_h=0.18),
    "robinia": dict(build="deciduous", leaf="green", crown=(0.46, 0.64, 0.55), limbs=7, lobe_r=0.35, autumn="yellow", airy=0.82, flowers="white", trunk_h=0.18),
    "maple": dict(build="deciduous", leaf="green", crown=(0.48, 0.64, 0.53), limbs=8, lobe_r=0.37, autumn="orange", trunk_h=0.16),
    "sugarmaple": dict(build="deciduous", leaf="darkgreen", crown=(0.48, 0.66, 0.53), limbs=8, lobe_r=0.37, autumn="red", autumn_green=0.06, trunk_h=0.16),
    "crab": dict(build="deciduous", leaf="green", crown=(0.48, 0.56, 0.50), limbs=6, lobe_r=0.38, autumn="red", flowers="pink", trunk_h=0.16),
    "snowbell": dict(build="deciduous", leaf="avocado", crown=(0.48, 0.58, 0.52), limbs=6, lobe_r=0.36, autumn="yellow", flowers="white", trunk_h=0.16),
    "birch2": dict(build="deciduous", leaf="avocado", crown=(0.40, 0.66, 0.55), limbs=6, lobe_r=0.34, autumn="yellow", airy=0.78, trunk="light", trunk_w=0.90, trunk_h=0.18),
    "strawberry": dict(build="deciduous", leaf="darkgreen", crown=(0.50, 0.62, 0.48), limbs=7, lobe_r=0.38, evergreen=True, trunk_h=0.14),
    "yew": dict(build="deciduous", leaf="conifer", crown=(0.50, 0.66, 0.48), limbs=8, lobe_r=0.40, evergreen=True, trunk_h=0.12),
    "willow": dict(build="weeping", leaf="avocado", autumn="yellow"),
    # 針葉（15 種，含落葉針葉水杉／落羽松／池杉）
    "pine": dict(build="conifer", leaf="conifer", whorls=15, width=1.02, z0=0.10),
    "scotspine": dict(build="pine", leaf="pine", trunk="red", tufts=10),
    "fir": dict(build="conifer", leaf="darkgreen", whorls=16, width=0.98, z0=0.08),
    "bluespruce": dict(build="conifer", leaf="seagreen", whorls=16, width=1.02, z0=0.08),
    "grandfir": dict(build="conifer", leaf="conifer", whorls=15, width=1.00, z0=0.09),
    "borisfir": dict(build="conifer", leaf="darkgreen", whorls=16, width=0.95, z0=0.09),
    "redcedar": dict(build="conifer", leaf="conifer", whorls=17, width=0.82, trunk="red", z0=0.08),
    "redwood": dict(build="conifer", leaf="darkgreen", whorls=16, width=0.92, trunk="red", z0=0.12, deciduous_conifer=True, autumn="rust", autumn_green=0.04),
    "pondcypress": dict(build="conifer", leaf="avocado", whorls=15, width=0.78, z0=0.12, deciduous_conifer=True, autumn="rust", autumn_green=0.08),
    "swampcypress": dict(build="conifer", leaf="green", whorls=16, width=0.96, z0=0.12, deciduous_conifer=True, autumn="rust", autumn_green=0.06),
    "silverpine": dict(build="conifer", leaf="pine", whorls=17, width=0.96, trunk="brown", z0=0.14),
    "cedar": dict(build="conifer", leaf="conifer", whorls=13, width=1.22, z0=0.12),
    "italiancypress": dict(build="column", leaf="conifer", width=0.55),
    "irishyew": dict(build="column", leaf="conifer", width=0.78),
    "hinoki": dict(build="column", leaf="gold", width=0.88),
    # 棕櫚與沙漠植物（7 種：沙漠反光較亮，不焦黑）
    "palm": dict(build="palm", leaf="green"),
    "silverpalm": dict(build="palm", leaf="desert_sage", shape="silverpalm", desert=True),
    "cactus": dict(build="cactus", leaf="cactus", shape="saguaro1", no_stretch=True, desert=True),
    "barrel": dict(build="cactus", leaf="cactus", shape="saguaro2", no_stretch=True, desert=True),
    "pricklypear": dict(build="cactus", leaf="cactus", shape="saguaro3", no_stretch=True, desert=True),
    "joshua": dict(build="rosette", leaf="desert_sage", shape="joshua", desert=True),
    "yucca": dict(build="rosette", leaf="desert_sage", shape="yucca", no_stretch=True, desert=True),
}
BUILDERS = {"deciduous": build_deciduous, "conifer": build_conifer, "pine": build_pine, "column": build_column, "weeping": build_weeping,
            "palm": build_palm, "cactus": build_cactus, "rosette": build_rosette}


def _snow(cloud, threshold=0.48):
    """用幾何朝上權重（snow_w）鋪設連續雪帽，邊緣略帶冷灰藍陰影，不產生隨機白點雜訊。"""
    p, n, c, ao, sw = cloud.arrays()
    if len(p) == 0:
        return
    c = c.copy()
    ao = ao.copy()
    # 頂部受雪較厚，下層枝棚僅受外緣積雪
    z_norm = (p[:, 2] - p[:, 2].min()) / max(p[:, 2].max() - p[:, 2].min(), 1e-6)
    score = sw + 0.16 * z_norm
    heavy = score > threshold + 0.10
    edge = (score > threshold) & ~heavy
    c[heavy] = SNOW
    ao[heavy] = np.maximum(ao[heavy], 0.85)
    c[edge] = c[edge] * 0.30 + SNOW * 0.70
    ao[edge] = np.maximum(ao[edge], 0.72)
    cloud.__init__()
    cloud.add(p, n, c, ao, sw)

# ---------------------------------------------------------------- 算圖


def project(p):
    return p[:, 0] - p[:, 1], (p[:, 0] + p[:, 1]) / 2 - p[:, 2]


def rotate_cloud(cloud, rot):
    """將點雲繞 Z 軸旋轉 rot × 90°（給 rot=2/4 的樹木與沙漠植物）。"""
    if rot % 4 == 0:
        return cloud
    a = rot * math.pi / 2
    ca, sa = math.cos(a), math.sin(a)
    R = np.array([[ca, -sa, 0.0], [sa, ca, 0.0], [0.0, 0.0, 1.0]])
    p, n, c, ao, sw = cloud.arrays()
    out = Cloud()
    if len(p):
        out.add(p @ R.T, n @ R.T, c, ao, sw)
    return out


def render(cloud, w, h, ox, oy, desert: bool = False):
    """→ (w×h 調色盤 index, 0 = 透明)。高對比暖陽光影；沙漠植物帶沙地反光，避免陰影焦黑。"""
    p, n, c, ao, _ = cloud.arrays()
    if len(p) == 0:
        return np.zeros((h, w), dtype=np.uint8)
    sx, sy = project(p)
    x = np.floor(ox + sx + 0.5).astype(int)
    y = np.floor(oy + sy + 0.5).astype(int)
    depth = p.sum(1)
    ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    x, y, depth, n, c, ao, pp = x[ok], y[ok], depth[ok], n[ok], c[ok], ao[ok], p[ok]
    lam = np.clip(n @ LIGHT, 0, 1)
    centre = pp.mean(0)
    flat = LIGHT * np.array([1, 1, 0])
    side = ((pp - centre) @ flat) / max(np.abs((pp - centre) @ flat).max(), 1e-6)
    if desert:
        lightfac = 0.76 + 0.34 * np.clip((side + 0.55) / 1.35, 0, 1)
        inten = np.clip((0.54 + 0.76 * lam) * (0.55 + 0.45 * ao) * lightfac, 0.44, 1.42)
    else:
        # 暖陽光影：受光枝冠明亮清脆（真正命中 70–81 / 82–93 暖橄欖高光），暗部保有深森綠但不焦黑
        lightfac = 0.68 + 0.50 * np.clip((side + 0.55) / 1.35, 0, 1)
        inten = np.clip((0.36 + 1.08 * lam) * (0.45 + 0.55 * ao) * lightfac, 0.24, 1.48)
    col = c * inten[:, None]
    col += (np.array([0.095, 0.115, 0.025]) * (lam[:, None] ** 2.0) * ao[:, None])
    order = np.argsort(depth)
    img = np.zeros((h, w, 3))
    mask = np.zeros((h, w), dtype=bool)
    img[y[order], x[order]] = col[order]
    mask[y[order], x[order]] = True
    out = to_index(img)
    out[~mask] = 0
    return out.astype(np.uint8)


def render_shadow(cloud, w, h, ox, oy, rng):
    """影子：樹的垂直投影（地面上的輪廓），置中縮放到影子 sprite 的框內，再隨機留出葉間透光的空隙。"""
    p, *_ = cloud.arrays()
    out = np.zeros((h, w), dtype=np.uint8)
    if len(p) == 0:
        return out
    g = p * np.array([1, 1, 0])
    sx, sy = project(g)
    cx, cy = (sx.max() + sx.min()) / 2, (sy.max() + sy.min()) / 2
    k = min((w - 2) / max(sx.max() - sx.min(), 1e-6), (h - 2) / max(sy.max() - sy.min(), 1e-6))
    x = np.floor(w / 2 + (sx - cx) * k).astype(int)
    y = np.floor(h / 2 + (sy - cy) * k).astype(int)
    ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
    out[y[ok], x[ok]] = SHADOW_INDEX
    holes = rng.random((h, w)) < 0.22
    out[holes] = 0
    return out


def tree_height(e) -> float:
    return float(-e.y_offset) * 0.98


def make_cloud(cfg, season, H, seed, snow, rot=0):
    rng = np.random.default_rng(seed)
    cloud = BUILDERS[cfg["build"]](cfg, season, rng, H, snow)
    return rotate_cloud(cloud, rot)


def fit_cloud(cfg, season, e, seed, snow, ref=None, rot=0):
    """依 sprite 的大小縮放，讓樹撐滿影格；沙漠細長植物限制水平拉伸避免肥腫。"""
    H = tree_height(e)
    cloud = make_cloud(cfg, season, H, seed, snow, rot=rot)
    base = ref if ref is not None else cloud
    p, *_ = base.arrays()
    if not len(p):
        return cloud, (1.0, 1.0)
    ox, oy = -e.x_offset, -e.y_offset
    sx, _ = project(p)
    # 留出自然空氣邊界（~86% 寬、~88% 高），避免把實心樹冠硬撐滿整張影格顯得過度膨脹
    scale_cap = 0.94 if cfg.get("no_stretch") else 0.86
    half = (min(ox, e.width - ox) - 1.0) * scale_cap
    max_fx = 1.12 if cfg.get("no_stretch") else 1.25
    fx = np.clip(half / max(np.abs(sx).max(), 1e-6), 0.55, max_fx)
    q = p * np.array([fx, fx, 1.0])
    _, sy = project(q)
    top_cap = 0.94 if cfg.get("no_stretch") else 0.88
    fz = np.clip((oy - 1.0) * top_cap / max(-sy.min(), 1e-6), 0.55, 1.25)
    return scale_cloud(cloud, fx, fz), (fx, fz)


def scale_cloud(cloud, fx, fz):
    p, n, c, ao, sw = cloud.arrays()
    out = Cloud()
    if len(p):
        out.add(p * np.array([fx, fx, fz]), unit(n / np.array([fx, fx, fz])), c, ao, sw)
    return out

# ---------------------------------------------------------------- 主程式


DEFAULT_SCALE = 0.45


def effective_scale(cfg: dict, scale: float = DEFAULT_SCALE) -> float:
    """回傳實際縮放比：一般喬木使用 scale（預設 0.45，對齊真實建築比例），
    低矮沙漠仙人掌／絲蘭維持最低 0.62、約書亞樹 0.50，避免小圖過度縮小成難以辨識的像素點。"""
    if cfg.get("no_stretch"):
        return max(scale, 0.62)
    if cfg.get("shape") == "joshua":
        return max(scale, 0.50)
    return scale


class _Box:
    __slots__ = ("width", "height", "x_offset", "y_offset")

    def __init__(self, width: int, height: int, x_offset: int, y_offset: int):
        self.width = width
        self.height = height
        self.x_offset = x_offset
        self.y_offset = y_offset


def _scaled_entry(e, sc: float, is_shadow: bool = False) -> _Box:
    nw = max(6, int(round(e.width * sc)))
    nh = max(6, int(round(e.height * sc)))
    nxo = int(round(e.x_offset * sc))
    nyo = int(round(e.y_offset * sc))
    if not is_shadow:
        if -nxo >= nw - 1:
            nw = -nxo + 3
        if -nyo >= nh:
            nh = -nyo + 2
    return _Box(nw, nh, nxo, nyo)


def build_frames(template: Path, cfg, seed: int, scale: float = DEFAULT_SCALE):
    obj = dat.read_dat(template)
    d = obj.data
    rot, growth = d[6], d[7]
    flags = struct.unpack_from("<H", d, 8)[0]
    seasons = [b for b in range(6) if d[0x3C] >> b & 1]
    has_snow, has_shadow = bool(flags & 1), bool(flags & 0x80)
    entries = obj.image_table().entries
    plan = [(s, g, r, False) for s in seasons for g in range(growth) for r in range(rot)]
    if has_snow:
        plan += [(s, g, r, True) for (s, g, r, _) in plan]
    n_main = len(plan)
    if n_main * (2 if has_shadow else 1) != len(entries):
        raise SystemExit(f"影像數不符：依結構計算 {n_main * (2 if has_shadow else 1)}，模板有 {len(entries)}")
    sc = effective_scale(cfg, scale)
    scaled = [_scaled_entry(e, sc, is_shadow=(i >= n_main)) for i, e in enumerate(entries)]
    clouds = {}
    frames = []
    for i, e in enumerate(scaled):
        k = i if i < n_main else i - n_main
        s, g, r, snow = plan[k]
        key = (s, g, r, snow)
        if key not in clouds:
            # 同一成長階段共用種子，旋轉由 rotate_cloud 實際轉動角度
            sd = seed * 1000 + g
            ref_season = 3 if 3 in seasons else seasons[0]
            ref = make_cloud(cfg, ref_season, tree_height(scaled[k]), sd, False, rot=r)
            clouds[key] = fit_cloud(cfg, s, scaled[k], sd, snow, ref, rot=r)[0]
        ox, oy = -e.x_offset, -e.y_offset
        if i < n_main:
            px = render(clouds[key], e.width, e.height, ox, oy, desert=bool(cfg.get("desert")))
        else:
            px = render_shadow(clouds[key], e.width, e.height, ox, oy, np.random.default_rng(seed + i))
        frames.append((e.width, e.height, e.x_offset, e.y_offset, px.tobytes()))
    return frames


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", help="結構模板 DAT（vanilla 或現有 OG 樹）")
    ap.add_argument("--species", required=True, help="樹種（SPECIES 的鍵；--sheet 時可用逗號列多個）")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--scale", type=float, default=DEFAULT_SCALE, help=f"相對模板的高度與尺寸比例（預設 {DEFAULT_SCALE}）")
    ap.add_argument("-o", "--output")
    ap.add_argument("--sheet", help="輸出預覽圖（各樹種 夏／秋／春／冬／積雪，最大成長階段）")
    args = ap.parse_args()
    if args.sheet:
        from PIL import Image
        names = args.species.split(",")
        cell_w, cell_h = 110, 150
        im = Image.new("RGB", (cell_w * 5, cell_h * len(names)), (108, 120, 82))
        for row, name in enumerate(names):
            cfg = SPECIES[name]
            sc = effective_scale(cfg, args.scale)
            H = (22 if cfg.get("no_stretch") else 120) * sc
            for col, (season, snow) in enumerate(((3, False), (0, False), (2, False), (1, False), (3, True))):
                cloud = make_cloud(cfg, season, H, args.seed, snow)
                px = render(cloud, cell_w, cell_h, cell_w // 2, cell_h - 12)
                sh = render_shadow(cloud, cell_w, cell_h, cell_w // 2, cell_h - 12, np.random.default_rng(1))
                for yy in range(cell_h):
                    for xx in range(cell_w):
                        v = px[yy, xx] or sh[yy, xx]
                        if v:
                            im.putpixel((col * cell_w + xx, row * cell_h + yy), tuple(int(t) for t in PAL[v]))
        im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(args.sheet)
        print(f"預覽 → {args.sheet}")
        return 0
    frames = build_frames(Path(args.template), SPECIES[args.species], args.seed, scale=args.scale)
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
