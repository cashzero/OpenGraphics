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
    "green": rgb(94, 134, 52),       # 命中 70–81 暖森綠（橡樹、榆樹、楓樹）
    "darkgreen": rgb(50, 98, 42),    # 命中 142–153 / 70–81 深針葉綠（冷杉、紅檜、紫杉）
    "conifer": rgb(44, 90, 38),      # 沉穩深杉綠，枝梢可吃到暖綠高光
    "pine": rgb(60, 106, 46),        # 暖松針綠（蘇格蘭松、石松）
    "avocado": rgb(118, 148, 64),    # 命中 70–81 / 82–93 淺橄欖綠（白樺、梣樹、垂柳）
    "olive": rgb(104, 118, 52),      # 命中 22–33 / 82–93 沙漠橄欖綠
    "gold": rgb(172, 158, 56),       # 命中 22–33 金黃葉（黃金刺槐、黃金扁柏）
    "copper": rgb(118, 52, 42),      # 命中 58–69 紫銅山毛櫸
    "seagreen": rgb(56, 108, 76),    # 命中 142–153 藍雲杉（微冷針葉綠，不落入泥青色）
    "cactus": rgb(76, 112, 48),      # 仙人掌深橄欖綠
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
    "brown": rgb(84, 66, 48),
    "light": rgb(168, 164, 152),
    "red": rgb(104, 58, 40),
    "dark": rgb(52, 42, 34),
    "grey": rgb(82, 78, 72),
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
    dens = cfg.get("density", 1.0) * amount * cfg.get("airy", 1.0)
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
            # 細碎通透葉簇（留出微光孔隙，像原版一樣輕盈透出內枝，不糊成巨大實心麵團）
            sr = r_lobe * (0.32 + 0.14 * rng.random()) * (0.76 + 0.24 * amount)
            leaf_tuft(cloud, sub_c, sr * 1.08, sr * 1.08, sr * 0.84,
                      lambda kk: leafcol(rng, kk), rng, dens * 1.12, crown_c, max(rx, rz) * 1.05,
                      holes=0.30 if amount > 0.7 else 0.42, jitter=0.50)
            for _ in range(3):
                off = unit(rng.normal(size=3) + np.array([0, 0, 0.15])) * sr * (0.55 + 0.45 * rng.random())
                mr = sr * (0.38 + 0.18 * rng.random())
                leaf_tuft(cloud, sub_c + off, mr * 1.08, mr * 1.08, mr * 0.82,
                          lambda kk: leafcol(rng, kk), rng, dens * 1.05, crown_c, max(rx, rz) * 1.05,
                          holes=0.26, jitter=0.52)
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
    whorls = int(cfg.get("whorls", 15))
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
                          lambda kk: leafcol(rng, kk), rng, 1.85 * amount, crown_c, H * 0.48,
                          holes=0.06, jitter=0.30, snow_bias=0.14 * (0.3 + 0.7 * f))

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
        # 每枝頂端由 7 顆不規則細碎松針小叢組成，呈現鋸齒松針層理而非圓球
        for j in range(7):
            ang_p = j / 7 * 2 * math.pi + rng.random() * 0.5
            rad_p = reach * (0.18 + 0.38 * rng.random())
            off = np.array([math.cos(ang_p) * rad_p, math.sin(ang_p) * rad_p, rng.normal() * H * 0.014])
            c = end + off
            r = H * (0.044 + 0.018 * rng.random()) * (1.06 - 0.18 * t)
            leaf_tuft(cloud, c, r * 1.35, r * 1.35, r * 0.55,
                      lambda kk: colfn(rng, kk), rng, 1.95, crown_c, H * 0.42,
                      holes=0.16, jitter=0.48, snow_bias=0.18)

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
        m = int(length * 3.2 * amount)
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
    """棕櫚：高大品種（QPALM）為微彎環紋椰子樹；小尺寸品種（SPALM，≤24px）為沙漠低矮扇葉棕櫚叢。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "green")]
    if cfg.get("shape") == "fanpalm" or H <= 26:
        # 低矮沙漠扇棕（SPALM 11×21）：短粗深褐基幹＋9 片向外展開的摺扇葉
        cylinder(cloud, (0, 0, 0), (0, 0, H * 0.26), H * 0.08, H * 0.06, BARK["dark"], rng, density=3.0, ao=0.72)
        hub = np.array([0, 0, H * 0.24])
        for f in range(9):
            a = f / 9 * 2 * math.pi + rng.random() * 0.25
            elev = 0.28 + 0.48 * (f % 3) / 2.0
            d = unit(np.array([math.cos(a), math.sin(a), elev]))
            length = H * (0.48 + 0.20 * (f % 2))
            m = 28
            t = np.linspace(0, 1, m)
            spine = hub + d * length * t[:, None] - np.array([0, 0, H * 0.20]) * (t * t)[:, None]
            side = unit(np.cross(d, [0, 0, 1.0]) + 1e-6)
            for s in (-1, 0, 1):
                w_fan = H * 0.075 * np.sin(np.pi * np.clip(t * 1.1, 0, 1))
                pts = spine + side * (s * w_fan)[:, None]
                nrm = unit(np.tile([math.cos(a) * 0.4, math.sin(a) * 0.4, 0.85], (m, 1)) + side * (s * 0.35))
                ao = 0.52 + 0.48 * t
                cloud.add(pts, nrm, np.clip(base * (0.94 + 0.12 * rng.normal(size=(m, 1))), 0, 1), ao, 0.45)
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


# ---------------------------------------------------------------- 仙人掌（針對 18–21px 俐落輪廓特化）


def build_cactus(cfg, season, rng, H, snow):
    """仙人掌：巨柱（清晰彎肘雙臂＋深稜紋）、圓桶（多球簇＋頂花）、團扇（立體交錯扁莖節）。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "cactus")]
    kind = cfg.get("shape", "cactus")

    def ribbed(a, b, r, ribs=7):
        a, b = np.asarray(a, float), np.asarray(b, float)
        axis = b - a
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return
        d = axis / length
        ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
        u = unit(np.cross(d, ref))
        v = np.cross(d, u)
        k = int(3.5 * length * max(r, 0.9) * 2 * math.pi + 50)
        t = rng.random(k)
        ang = rng.random(k) * 2 * math.pi
        rib = 1.0 + 0.14 * np.cos(ang * ribs)
        radial = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
        tang = np.cos(ang)[:, None] * v - np.sin(ang)[:, None] * u
        nrm = unit(radial + 0.42 * np.sin(ang * ribs)[:, None] * tang)
        pts = a + t[:, None] * axis + radial * (r * rib)[:, None]
        col = base * (0.80 + 0.32 * (np.cos(ang * ribs) > 0.45)[:, None])
        cloud.add(pts, nrm, np.clip(col, 0, 1), 0.92, 0.0)
        # 圓潤頂蓋
        m = int(3.0 * math.pi * max(r, 0.9) ** 2 + 24)
        uu = sphere_dirs(rng, m)
        uu = uu[(uu @ d) > 0]
        cloud.add(b + uu * r, uu, base * 1.04, 0.96, 0.0)

    if kind == "barrel":
        for (ox, oy, sc) in ((-0.13, 0.05, 1.0), (0.15, -0.06, 0.78), (0.01, -0.14, 0.62)):
            c = np.array([ox * H, oy * H, H * 0.26 * sc])
            m = int(6 * math.pi * max(H * 0.24 * sc, 2.0) ** 2 + 80)
            u = sphere_dirs(rng, m)
            ang = np.arctan2(u[:, 1], u[:, 0])
            rib = 1.0 + 0.11 * np.cos(ang * 10)
            pts = c + u * np.array([H * 0.21 * sc, H * 0.21 * sc, H * 0.27 * sc]) * rib[:, None]
            pts = pts[pts[:, 2] >= 0]
            ang = ang[:len(pts)]
            nrm = unit(pts - c)
            col = base * (0.82 + 0.28 * (np.cos(ang * 10) > 0.4)[:, None])
            cloud.add(pts, nrm, np.clip(col, 0, 1), 0.92, 0.0)
            if season in (2, 3):
                fl = c + np.array([0, 0, H * 0.27 * sc]) + rng.normal(size=(20, 3)) * H * 0.045
                cloud.add(fl, np.tile([0, 0, 1.0], (20, 1)), rgb(232, 170, 52), 1.0, 0.0)
    elif kind == "pear":
        pads = [
            ((0.0, 0.0, 0.18), 0.0, 0.17),
            ((-0.14, 0.06, 0.44), 0.45, 0.15),
            ((0.14, -0.05, 0.46), -0.55, 0.15),
            ((-0.02, 0.02, 0.70), 0.15, 0.14),
            ((0.16, 0.04, 0.74), -0.35, 0.12),
        ]
        for (x, y, z), turn, sz in pads:
            c = np.array([x * H, y * H, z * H])
            m = 160
            a = rng.random(m) * 2 * math.pi
            rho = np.sqrt(rng.random(m))
            lx, lz = np.cos(a) * rho * H * sz, np.sin(a) * rho * H * (sz * 1.25)
            face = np.array([math.cos(turn), math.sin(turn), 0])
            right = np.array([-math.sin(turn), math.cos(turn), 0])
            pts = c + lx[:, None] * right + lz[:, None] * np.array([0, 0, 1]) + face * (rng.normal(size=(m, 1)) * 0.45)
            nrm = unit(np.tile(face * 0.65 + np.array([0, 0, 0.55]), (m, 1)) + np.cos(a)[:, None] * right * 0.4)
            ao = 0.70 + 0.30 * (1.0 - 0.5 * rho)
            cloud.add(pts, nrm, np.clip(base * (0.94 + 0.12 * rng.normal(size=(m, 1))), 0, 1), ao, 0.0)
    else:  # 巨柱仙人掌（CACTUS1）：修長直立、左右高低錯落彎肘臂
        r = max(1.05, H * 0.068)
        ribbed((0, 0, 0), (0, 0, H * 0.94), r)
        for side, h0, h1 in ((1, 0.34, 0.72), (-1, 0.48, 0.82)):
            arm_r = max(0.85, r * 0.74)
            # 沿畫面左右方向（X - Y 軸）展開手臂，讓等角視角一眼看出經典仙人掌剪影
            dir_xy = unit(np.array([1.0, -1.0, 0.0])) * side
            p0 = dir_xy * (r * 0.7) + np.array([0, 0, H * h0])
            p1 = p0 + dir_xy * (H * 0.15) + np.array([0, 0, H * 0.05])
            p2 = p1 + np.array([0, 0, H * (h1 - h0)])
            ribbed(p0, p1, arm_r)
            ribbed(p1, p2, arm_r)
    return cloud


# ---------------------------------------------------------------- 約書亞樹與絲蘭


def build_rosette(cfg, season, rng, H, snow):
    """約書亞樹（粗獷分叉灰褐枝幹＋枝端深橄欖綠尖刺球）與絲蘭（緊密尖葉蓮座＋米白高花穗）。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "olive")]
    bark = BARK["brown"] * 0.92
    tips = []
    if cfg.get("shape") == "joshua":
        tr = max(1.0, H * 0.062)
        trunk_top = np.array([0, 0, H * 0.42])
        cylinder(cloud, (0, 0, 0), trunk_top, tr * 1.15, tr * 0.85, bark, rng, density=2.8, ao=0.85)
        for k in range(5):
            a = k / 5 * 2 * math.pi + 0.35 + rng.random() * 0.35
            mid = trunk_top + np.array([math.cos(a) * H * 0.17, math.sin(a) * H * 0.17, H * 0.15])
            end = mid + np.array([math.cos(a) * H * 0.06, math.sin(a) * H * 0.06, H * (0.16 + 0.10 * (k % 2))])
            cylinder(cloud, trunk_top, mid, tr * 0.65, tr * 0.52, bark, rng, density=2.6, ao=0.82)
            cylinder(cloud, mid, end, tr * 0.52, tr * 0.42, bark, rng, density=2.4, ao=0.82)
            tips.append((end, H * 0.15))
    else:
        tips.append((np.array([0, 0, H * 0.16]), H * 0.32))
        stalk_top = np.array([0, 0, H * 0.96])
        cylinder(cloud, (0, 0, H * 0.18), stalk_top, 0.55, 0.38, BARK["brown"], rng, density=2.5)
        fl = stalk_top - np.array([0, 0, H * 0.20]) * rng.random((45, 1)) + rng.normal(size=(45, 3)) * np.array([H * 0.035, H * 0.035, 0])
        cloud.add(fl, np.tile([0, 0, 1.0], (45, 1)), rgb(232, 228, 198), 0.98, 0.0)

    for c, length in tips:
        for _ in range(72):
            d = unit(rng.normal(size=3) + np.array([0, 0, 0.45]))
            t = np.linspace(0, 1, max(4, int(length * 2.2) + 2))[:, None]
            pts = c + d * (length * t)
            nrm = np.tile(unit(d + np.array([0, 0, 0.35])), (len(pts), 1))
            ao = (0.48 + 0.52 * t[:, 0])
            cloud.add(pts, nrm, np.clip(base * (0.88 + 0.24 * rng.random()), 0, 1), ao, 0.0)
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
    # 棕櫚與沙漠植物（7 種）
    "palm": dict(build="palm", leaf="green"),
    "silverpalm": dict(build="palm", leaf="olive", shape="fanpalm", no_stretch=True),
    "cactus": dict(build="cactus", leaf="cactus", no_stretch=True),
    "barrel": dict(build="cactus", leaf="cactus", shape="barrel", no_stretch=True),
    "pricklypear": dict(build="cactus", leaf="olive", shape="pear", no_stretch=True),
    "joshua": dict(build="rosette", leaf="olive", shape="joshua", no_stretch=True),
    "yucca": dict(build="rosette", leaf="olive", shape="yucca", no_stretch=True),
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


def render(cloud, w, h, ox, oy):
    """→ (w×h 調色盤 index, 0 = 透明)。高對比暖陽光影，不將陰影偏藍。"""
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
    # 整體受光面（左上）與背光面（右下）的體積明暗
    centre = pp.mean(0)
    flat = LIGHT * np.array([1, 1, 0])
    side = ((pp - centre) @ flat) / max(np.abs((pp - centre) @ flat).max(), 1e-6)
    lightfac = 0.58 + 0.48 * np.clip((side + 0.55) / 1.35, 0, 1)
    inten = np.clip((0.26 + 0.96 * lam) * ao * lightfac, 0.16, 1.36)
    col = c * inten[:, None]
    # 受光頂緣帶自然暖黃綠高光；不再對陰影加藍色偏色
    col += (np.array([0.075, 0.085, 0.012]) * (lam[:, None] ** 2.4) * ao[:, None])
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


def build_frames(template: Path, cfg, seed: int):
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
    clouds = {}
    frames = []
    for i, e in enumerate(entries):
        k = i if i < n_main else i - n_main
        s, g, r, snow = plan[k]
        key = (s, g, r, snow)
        if key not in clouds:
            # 同一成長階段共用種子，旋轉由 rotate_cloud 實際轉動角度
            sd = seed * 1000 + g
            ref_season = 3 if 3 in seasons else seasons[0]
            ref = make_cloud(cfg, ref_season, tree_height(entries[k]), sd, False, rot=r)
            clouds[key] = fit_cloud(cfg, s, entries[k], sd, snow, ref, rot=r)[0]
        ox, oy = -e.x_offset, -e.y_offset
        if i < n_main:
            px = render(clouds[key], e.width, e.height, ox, oy)
        else:
            px = render_shadow(clouds[key], e.width, e.height, ox, oy, np.random.default_rng(seed + i))
        frames.append((e.width, e.height, e.x_offset, e.y_offset, px.tobytes()))
    return frames


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", help="結構模板 DAT（vanilla 或現有 OG 樹）")
    ap.add_argument("--species", required=True, help="樹種（SPECIES 的鍵；--sheet 時可用逗號列多個）")
    ap.add_argument("--seed", type=int, default=1)
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
            H = 22 if cfg.get("no_stretch") else 120
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
    frames = build_frames(Path(args.template), SPECIES[args.species], args.seed)
    common.write_sprites(args.output, frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
