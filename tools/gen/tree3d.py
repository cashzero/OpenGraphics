#!/usr/bin/env python3
"""3D 點雲樹木（ROADMAP M6 美術調整：取代 tree.py 的平面色塊畫法）。

  .venv/bin/python tools/gen/tree3d.py --template <模板.DAT> --species oak [--seed 1] -o <資料夾>
  .venv/bin/python tools/gen/tree3d.py --sheet build/preview/trees3d.png --species oak,scpine,...   # 預覽

做法（像一個極小的軟體算圖器，不用 Blender）：
1. 依樹種建 3D 模型：樹幹（有法線的圓柱面）、枝幹（從樹幹長到各葉簇，冬季看得到）、葉簇（球殼上的大量葉點）。
   針葉樹是一層層下垂的圓盤，柱狀樹是細長的葉簇堆疊，另有垂柳、棕櫚、仙人掌、約書亞樹、絲蘭。
2. 以遊戲的 2:1 等角投影（sx = X − Y，sy = (X + Y)/2 − Z）畫到 sprite 上，深度緩衝取最靠近相機的點。
3. 光從畫面左上照下；明暗 = 環境光 + 漫射，再乘上「葉簇深處」與「背光面」的遮蔽，讓樹冠有體積感。
4. 顏色在 RGB 計算（暗橄欖綠、秋季棕紅橙黃混色、樹皮棕色），最後對到 Locomotion 調色盤的最近色。
5. 影子：把同一個點雲沿光線方向投影到地面，畫成有空隙的影子。
影像順序與 tree.py 相同（季節組 → 成長階段 × 旋轉；積雪版；陰影），尺寸與偏移沿用模板。
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
LIGHT = np.array([-0.35, 0.65, 0.68])          # 從畫面左前上方照下：樹的左側受光、右側背光
LIGHT /= np.linalg.norm(LIGHT)

# ---------------------------------------------------------------- 顏色（RGB 0–1）


def rgb(r, g, b):
    return np.array([r, g, b], dtype=np.float64) / 255


LEAF = {
    "green": rgb(78, 102, 44), "darkgreen": rgb(52, 78, 40), "avocado": rgb(108, 122, 50), "olive": rgb(98, 104, 52),
    "gold": rgb(168, 150, 58), "copper": rgb(104, 52, 42), "seagreen": rgb(66, 98, 90), "blue": rgb(70, 96, 104),
}
SPRING = rgb(120, 150, 66)
AUTUMN = {
    "orange": [rgb(150, 82, 34), rgb(122, 58, 30), rgb(168, 124, 48), rgb(98, 94, 42), rgb(136, 104, 40)],
    "red": [rgb(132, 42, 32), rgb(108, 36, 30), rgb(156, 76, 38), rgb(120, 92, 40)],
    "yellow": [rgb(170, 138, 48), rgb(146, 116, 40), rgb(118, 102, 40), rgb(160, 128, 60)],
    "rust": [rgb(138, 66, 46), rgb(120, 56, 42), rgb(156, 88, 66), rgb(110, 72, 44)],
    "copper": [rgb(104, 48, 38), rgb(88, 42, 34), rgb(124, 60, 40)],
}
FLOWERS = {"cream": rgb(224, 214, 176), "white": rgb(232, 232, 224), "pink": rgb(214, 150, 168)}
BARK = {"brown": rgb(100, 84, 66), "light": rgb(186, 182, 168), "red": rgb(112, 62, 46), "dark": rgb(58, 48, 40), "grey": rgb(96, 92, 86)}
SNOW = rgb(236, 240, 244)
DEAD = rgb(104, 98, 88)

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
    """64³ 查表：RGB（每通道 6 bit）→ 感知色差（Lab）最近的允許色號。色相權重較高，暗綠不會變成棕色。"""
    global _LUT
    if _LUT is None:
        allowed = np.array(quantize.ALLOWED)
        cols = to_lab(PAL[allowed])
        grid = (np.arange(64) * 4 + 2).astype(np.float64)
        r, g, b = np.meshgrid(grid, grid, grid, indexing="ij")
        q = to_lab(np.stack([r, g, b], -1).reshape(-1, 3))
        w = np.array([1.0, 1.6, 1.6])
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
        self.p, self.n, self.c, self.ao, self.size = [], [], [], [], []

    def add(self, p, n, c, ao=1.0, size=1):
        p = np.atleast_2d(p)
        k = len(p)
        self.p.append(p)
        self.n.append(np.broadcast_to(np.atleast_2d(n), (k, 3)))
        self.c.append(np.broadcast_to(np.atleast_2d(c), (k, 3)))
        self.ao.append(np.broadcast_to(np.atleast_1d(ao), (k,)))
        self.size.append(np.full(k, size))

    def arrays(self):
        if not self.p:
            return (np.zeros((0, 3)),) * 3 + (np.zeros(0), np.zeros(0))
        return (np.concatenate(self.p), np.concatenate(self.n), np.concatenate(self.c),
                np.concatenate(self.ao), np.concatenate(self.size))


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def sphere_dirs(rng, k):
    return unit(rng.normal(size=(k, 3)))


def cylinder(cloud, a, b, r0, r1, colour, rng, density=1.6, ao=1.0, rough=0.12):
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
    k = int(max(6, density * length * max(rmax, 0.6) * 2 * math.pi))
    t = rng.random(k)
    ang = rng.random(k) * 2 * math.pi
    rad = r0 + (r1 - r0) * t
    nrm = np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v
    pts = a + t[:, None] * axis + nrm * rad[:, None]
    col = np.asarray(colour) * (1 + rough * rng.normal(size=(k, 1)))
    cloud.add(pts, nrm, col, ao)


def leaf_cluster(cloud, c, r, colour_fn, rng, density, crown_c, crown_r, size=1, holes=0.22):
    """葉簇：球殼上的葉點；法線混合「葉簇表面」與「整個樹冠表面」方向。holes：隨機挖掉幾個小球，留出葉間空隙。"""
    k = int(density * 4 * math.pi * r * r)
    if k <= 0:
        return
    u = sphere_dirs(rng, k)
    rad = r * (0.55 + 0.45 * np.sqrt(rng.random(k)))
    pts = c + u * rad[:, None]
    keep = np.ones(k, dtype=bool)
    for _ in range(int(holes * 10)):
        hc = c + unit(rng.normal(size=3)) * r * 0.85
        keep &= np.linalg.norm(pts - hc, axis=1) > r * (0.18 + 0.2 * rng.random())
    pts, u = pts[keep], u[keep]
    outer = unit(pts - crown_c)
    nrm = unit(0.55 * u + 0.45 * outer + rng.normal(size=u.shape) * 0.75)   # 每片葉子朝向不同 → 細碎的亮點與暗斑
    depth = np.linalg.norm(pts - crown_c, axis=1) / max(crown_r, 1e-6)
    ao = 0.60 + 0.40 * np.clip(depth, 0, 1) ** 0.8
    cloud.add(pts, nrm, colour_fn(len(pts)), ao, size)


def branch_to(cloud, a, b, r0, r1, colour, rng, twig_density=1.4):
    cylinder(cloud, a, b, r0, r1, colour, rng, density=twig_density)

# ---------------------------------------------------------------- 樹種


def season_colours(cfg, season, rng):
    """→ (葉色函式 or None, 葉量 0–1, 花色 or None)。季節：0 秋、1 冬、2 春、3 夏、4 枯萎。"""
    base = LEAF[cfg.get("leaf", "green")]
    if season == 4:
        return None, 0.0, None
    if cfg.get("evergreen"):
        return _solid(base, 0.10), 1.0 if season != 1 else 0.95, None
    if season == 1:
        return None, 0.0, None
    if season == 0:
        pal = AUTUMN[cfg.get("autumn", "orange")]
        return _mixed(pal, base, cfg.get("autumn_green", 0.18)), 0.84, None
    if season == 2:
        spring = LEAF[cfg["spring"]] if "spring" in cfg else SPRING
        flowers = FLOWERS.get(cfg.get("flowers"))
        return _solid(spring, 0.09), 0.10, flowers
    return _solid(base, 0.10), 1.0, None


def _solid(base, jitter):
    def fn(rng, k):
        tint = 1 + jitter * rng.normal(size=(k, 1))
        hue = rng.normal(size=(k, 3)) * 0.025
        return np.clip(base * tint + hue, 0, 1)
    return fn


def _mixed(pal, green, green_share):
    choices = pal + [green]
    weights = np.array([(1 - green_share) / len(pal)] * len(pal) + [green_share])

    def fn(rng, k):
        # 葉簇內大致同色（每次呼叫＝一個葉簇），再加少量雜色
        main = choices[rng.choice(len(choices), p=weights)]
        cols = np.tile(main, (k, 1))
        mix = rng.random(k) < 0.25
        if mix.any():
            cols[mix] = np.array(choices)[rng.choice(len(choices), size=int(mix.sum()), p=weights)]
        return np.clip(cols * (1 + 0.10 * rng.normal(size=(k, 1))), 0, 1)
    return fn


def build_deciduous(cfg, season, rng, H, snow):
    """闊葉樹：樹幹＋分枝＋葉簇。H = 樹高（像素）。"""
    cloud = Cloud()
    cw, ch, ccy = cfg.get("crown", (0.46, 0.46, 0.60))
    rx, rz = H * cw * 0.62, H * ch * 0.5
    cz = H * ccy
    crown_c = np.array([0, 0, cz])
    trunk_top = H * cfg.get("trunk_h", 0.45)
    bark = BARK[cfg.get("trunk", "brown")] if season != 4 else DEAD
    tr = max(0.8, H * 0.028 * cfg.get("trunk_w", 1.0))
    cylinder(cloud, (0, 0, 0), (0, 0, trunk_top + rz * 0.4), tr, tr * 0.55, bark, rng, ao=0.9)
    leafcol, amount, flowers = season_colours(cfg, season, rng)

    n = int(cfg.get("blobs", 11) * 1.1)
    blob_r = cfg.get("blob_r", (0.34, 0.55))
    dens = cfg.get("density", 1.0) * amount * cfg.get("airy", 1.0)
    twig = bark * 1.25
    # 主葉簇均勻填滿樹冠橢球；每個主葉簇再分成數個小葉簇。枝幹骨架一律建好（夏季被葉子遮住，春季、冬季看得到）
    for _ in range(n):
        d = unit(rng.normal(size=3))
        rr = 0.25 + 0.55 * rng.random() ** 0.6
        c = crown_c + d * np.array([rx, rx, rz]) * rr
        c[2] = max(c[2], trunk_top * 0.95)
        r = min(rx, rz) * (blob_r[0] + (blob_r[1] - blob_r[0]) * rng.random())
        start = np.array([0, 0, trunk_top * (0.80 + 0.30 * rng.random())])
        mid = start + (c - start) * 0.5 + rng.normal(size=3) * r * 0.25
        branch_to(cloud, start, mid, tr * 0.55, tr * 0.34, bark, rng)
        branch_to(cloud, mid, c, tr * 0.34, tr * 0.18, bark, rng)
        for _ in range(int(rng.integers(5, 8))):
            sc = c + unit(rng.normal(size=3) + np.array([0, 0, 0.2])) * r * (0.35 + 0.35 * rng.random())
            sr = r * (0.40 + 0.22 * rng.random())
            # 小葉簇不超出樹冠橢球（輪廓是粗糙的橢圓，不會有大鼓包）
            rel = (sc - crown_c) / np.array([rx, rx, rz])
            lim = np.linalg.norm(rel) + sr / min(rx, rz)
            if lim > 1.0:
                sc = crown_c + rel / lim * np.array([rx, rx, rz])
            branch_to(cloud, c, sc, tr * 0.18, 0.42, bark, rng, twig_density=1.2)
            for _ in range(5):                  # 細枝
                tip = sc + unit(rng.normal(size=3) + np.array([0, 0, 0.4])) * sr * (0.8 + 0.6 * rng.random())
                branch_to(cloud, sc, tip, 0.38, 0.28, twig, rng, twig_density=0.9)
            if leafcol is None or amount == 0:
                continue
            leaf_cluster(cloud, sc, sr, lambda k: leafcol(rng, k), rng, dens * 1.25, crown_c, max(rx, rz),
                         holes=0.18 if amount > 0.9 else (0.30 if amount > 0.5 else 0.6))
            if flowers is not None:
                leaf_cluster(cloud, sc, sr * 1.03, lambda k: np.tile(flowers, (k, 1)), rng, dens * 0.3, crown_c, max(rx, rz), holes=0)
    if snow:
        _snow(cloud)
    return cloud


def build_conifer(cfg, season, rng, H, snow):
    """針葉樹：細長的圓錐；從下到上一層層輪生的枝條，枝上掛小葉簇（有層次與深色縫隙）。"""
    cloud = Cloud()
    bark = BARK[cfg.get("trunk", "dark")] if season != 4 else DEAD
    tr = max(0.7, H * 0.022)
    cylinder(cloud, (0, 0, 0), (0, 0, H * 0.98), tr, 0.4, bark, rng, ao=0.85)
    shape = cfg.get("shape", "conifer")
    z0 = H * (0.06 if shape == "conifer" else 0.18)
    R = H * 0.22 * cfg.get("width", 1.0)
    whorls = int(14 * cfg.get("layers", 7) / 7)
    crown_c = np.array([0, 0, H * 0.45])
    base = LEAF[cfg.get("leaf", "darkgreen")]
    colfn = _solid(base, 0.12)
    for k in range(whorls):
        t = k / max(whorls - 1, 1)
        z = z0 + (H * 0.94 - z0) * t
        rmax = R * (1 - t) ** 0.9 + H * 0.02
        for _ in range(max(3, int(7 * (1 - t)) + 3)):
            a = rng.random() * 2 * math.pi
            length = rmax * (0.65 + 0.35 * rng.random())
            d = unit(np.array([math.cos(a), math.sin(a), -0.28]))
            start = np.array([0, 0, z])
            end = start + d * length
            branch_to(cloud, start, end, 0.45, 0.3, bark, rng, twig_density=1.0)
            if season == 4:                         # 枯萎：只剩細枝與少量褐色針葉
                cloud.add(end + rng.normal(size=(4, 3)) * 0.8, np.tile([0, 0, 1.0], (4, 1)), rgb(120, 92, 60), 0.9)
                continue
            for j in range(3):
                f = (j + 1) / 3
                c = start + d * length * f + np.array([0, 0, H * 0.01])
                r = H * 0.040 * (1.25 - 0.55 * f) * (0.8 + 0.4 * rng.random())
                leaf_cluster(cloud, c, r, lambda kk: colfn(rng, kk), rng, 1.5, crown_c, H * 0.5, holes=0.08)
    if snow:
        _snow(cloud, 0.45)
    return cloud


def build_pine(cfg, season, rng, H, snow):
    """松樹（蘇格蘭松、銀松）：高聳的紅褐色樹幹，上部分枝，枝端是扁平的雲朵狀葉簇。"""
    cloud = Cloud()
    bark = BARK[cfg.get("trunk", "red")] if season != 4 else DEAD
    tr = max(0.9, H * 0.03)
    lean = np.array([rng.normal() * H * 0.03, rng.normal() * H * 0.03, 0])
    top = lean + np.array([0, 0, H * 0.92])
    cylinder(cloud, (0, 0, 0), top, tr, tr * 0.6, bark, rng, ao=0.9)
    base = LEAF[cfg.get("leaf", "darkgreen")]
    colfn = _solid(base, 0.12)
    crown_c = top * 0.75
    for k in range(int(cfg.get("tufts", 9))):
        z = H * (0.45 + 0.45 * k / max(cfg.get("tufts", 9) - 1, 1))
        start = lean * (z / H) + np.array([0, 0, z])
        a = rng.random() * 2 * math.pi
        reach = H * (0.10 + 0.14 * rng.random()) * (1.1 - 0.5 * (z / H))
        end = start + np.array([math.cos(a) * reach, math.sin(a) * reach, H * 0.04])
        branch_to(cloud, start, end, tr * 0.4, tr * 0.25, bark, rng)
        if season == 4:
            continue
        # 扁平雲朵：幾個壓扁的葉簇
        for _ in range(3):
            c = end + np.array([rng.normal() * reach * 0.25, rng.normal() * reach * 0.25, rng.normal() * H * 0.01])
            r = H * (0.06 + 0.03 * rng.random())
            sub_cloud = Cloud()
            leaf_cluster(sub_cloud, c, r, lambda kk: colfn(rng, kk), rng, 1.5, crown_c, H * 0.4, holes=0.1)
            pp, nn, cc, aa, _ = sub_cloud.arrays()
            if len(pp):
                pp = c + (pp - c) * np.array([1.25, 1.25, 0.55])
                cloud.add(pp, nn, cc, aa)
    if snow:
        _snow(cloud)
    return cloud


def build_column(cfg, season, rng, H, snow):
    """柱狀（義大利柏、愛爾蘭紫杉、扁柏）：細長的葉簇堆疊。"""
    cloud = Cloud()
    bark = BARK["dark"]
    cylinder(cloud, (0, 0, 0), (0, 0, H * 0.3), max(0.7, H * 0.02), 0.6, bark, rng)
    leafcol, amount, _ = season_colours({**cfg, "evergreen": True}, season, rng)
    if leafcol is None:
        return cloud
    w = H * 0.13 * cfg.get("width", 0.6) * 1.6
    crown_c = np.array([0, 0, H * 0.55])
    for k in range(14):
        z = H * (0.12 + 0.80 * k / 13)
        taper = 1 - abs((z / H) - 0.5) * 1.1
        r = w * max(taper, 0.25) * (0.85 + 0.25 * rng.random())
        c = np.array([rng.normal() * r * 0.15, rng.normal() * r * 0.15, z])
        leaf_cluster(cloud, c, r, lambda k: leafcol(rng, k), rng, 1.0 * amount, crown_c, H * 0.45)
    if snow:
        _snow(cloud)
    return cloud


def build_weeping(cfg, season, rng, H, snow):
    """垂柳：圓頂樹冠＋從樹冠外緣垂下的枝條。"""
    cloud = build_deciduous({**cfg, "crown": (0.42, 0.34, 0.70), "blobs": 8}, season, rng, H, False)
    leafcol, amount, _ = season_colours(cfg, season, rng)
    bark = BARK["brown"]
    for _ in range(46):
        a = rng.random() * 2 * math.pi
        rr = H * 0.22 * (0.7 + 0.4 * rng.random())
        top = np.array([math.cos(a) * rr, math.sin(a) * rr, H * (0.72 + 0.12 * rng.random())])
        length = H * (0.30 + 0.25 * rng.random())
        out = np.array([math.cos(a), math.sin(a), 0]) * H * 0.08
        t = np.linspace(0, 1, 24)[:, None]
        curve = top + out * np.sin(t * math.pi / 2) - np.array([0, 0, 1.0]) * length * t ** 1.4   # 先向外再垂下
        if leafcol is None or amount == 0:
            for q0, q1 in zip(curve[:-1], curve[1:]):
                branch_to(cloud, q0, q1, 0.3, 0.3, bark * 1.3, rng, twig_density=0.6)
            continue
        m = int(length * 3.0 * amount)
        idx = rng.integers(0, len(curve), m)
        pts = curve[idx] + rng.normal(size=(m, 3)) * np.array([0.9, 0.9, 0.4])
        nrm = unit(np.tile([math.cos(a), math.sin(a), 0.3], (m, 1)) + rng.normal(size=(m, 3)) * 0.5)
        cloud.add(pts, nrm, leafcol(rng, m), 0.85)
    if snow:
        _snow(cloud)
    return cloud


def build_palm(cfg, season, rng, H, snow):
    """棕櫚：微彎有環紋的樹幹＋下垂的羽狀葉。"""
    cloud = Cloud()
    lean = np.array([H * 0.08, -H * 0.03, 0])
    segs = 10
    prev = np.zeros(3)
    for k in range(1, segs + 1):
        t = k / segs
        p = lean * t * t + np.array([0, 0, H * 0.78 * t])
        col = BARK["grey"] * (0.85 if k % 2 else 1.05)
        cylinder(cloud, prev, p, H * 0.03, H * 0.026, col, rng, density=2.0)
        prev = p
    top = prev
    base = LEAF[cfg.get("leaf", "green")]
    for f in range(9):
        a = f / 9 * 2 * math.pi + rng.random() * 0.3
        d = np.array([math.cos(a), math.sin(a), 0])
        length = H * (0.34 + 0.08 * rng.random())
        m = 60
        t = np.linspace(0, 1, m)
        spine = top + d * length * t[:, None] + np.array([0, 0, 1]) * (H * 0.10 * t - H * 0.30 * t * t)[:, None]
        side = np.cross(d, [0, 0, 1])
        for s in (-1, 1):
            leaf = spine + side * s * (H * 0.07 * np.sin(np.pi * t) * (0.6 + 0.4 * rng.random()))[:, None]
            for q in np.linspace(0.2, 1.0, 4):
                pts = spine + (leaf - spine) * q
                nrm = unit(np.tile([0, 0, 1.0], (m, 1)) + side * s * 0.4)
                cloud.add(pts, nrm, np.clip(base * (1 + 0.1 * rng.normal(size=(m, 1))), 0, 1), 0.9)
    if snow:
        _snow(cloud)
    return cloud


def build_cactus(cfg, season, rng, H, snow):
    """仙人掌：柱狀（巨柱）、圓桶、扇形莖節。稜紋用法線起伏表現。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "green")] * 1.05
    kind = cfg.get("shape", "cactus")

    def ribbed(a, b, r, ribs=8):
        a, b = np.asarray(a, float), np.asarray(b, float)
        axis = b - a
        length = np.linalg.norm(axis)
        d = axis / length
        ref = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
        u = unit(np.cross(d, ref))
        v = np.cross(d, u)
        k = int(2.2 * length * r * 2 * math.pi + 30)
        t = rng.random(k)
        ang = rng.random(k) * 2 * math.pi
        rib = 1 + 0.12 * np.cos(ang * ribs)
        nrm = unit((np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v) + 0.35 * np.sin(ang * ribs)[:, None] * (np.cos(ang)[:, None] * v - np.sin(ang)[:, None] * u))
        pts = a + t[:, None] * axis + (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v) * (r * rib)[:, None]
        col = base * (0.9 + 0.2 * (np.cos(ang * ribs) > 0.6)[:, None])
        cloud.add(pts, nrm, col, 1.0)
        # 頂端半球
        m = int(2 * math.pi * r * r * 2 + 10)
        uu = sphere_dirs(rng, m)
        uu = uu[(uu @ d) > 0]
        cloud.add(b + uu * r, uu, base, 1.0)

    if kind == "barrel":
        for off in ((-0.12, 0.05), (0.14, -0.06)):
            c = np.array([off[0] * H, off[1] * H, H * 0.30])
            m = int(4 * math.pi * (H * 0.3) ** 2 * 1.2)
            u = sphere_dirs(rng, m)
            ang = np.arctan2(u[:, 1], u[:, 0])
            pts = c + u * np.array([H * 0.28, H * 0.28, H * 0.34]) * (1 + 0.08 * np.cos(ang * 12))[:, None]
            pts = pts[pts[:, 2] > 0]
            nrm = unit(pts - c)
            cloud.add(pts, nrm, base, 1.0)
            if season in (2, 3):
                fl = c + np.array([0, 0, H * 0.33]) + rng.normal(size=(18, 3)) * H * 0.05
                cloud.add(fl, np.tile([0, 0, 1.0], (18, 1)), rgb(214, 96, 60), 1.0)
    elif kind == "pear":
        pads = [((0, 0, 0.18), 0.0, 0.0), ((-0.12, 0.05, 0.45), 0.5, 0.25), ((0.13, -0.04, 0.48), -0.6, 0.2),
                ((0.02, 0.0, 0.72), 0.2, 0.1), ((-0.16, 0.06, 0.74), 0.9, 0.3)]
        for (x, y, z), tilt, turn in pads:
            c = np.array([x * H, y * H, z * H])
            m = int(2.4 * math.pi * (H * 0.16) * (H * 0.2)) + 40
            a = rng.random(m) * 2 * math.pi
            rho = np.sqrt(rng.random(m))
            lx, lz = np.cos(a) * rho * H * 0.16, np.sin(a) * rho * H * 0.2
            face = np.array([math.cos(turn), math.sin(turn), 0])
            right = np.array([-math.sin(turn), math.cos(turn), 0])
            pts = c + lx[:, None] * right + lz[:, None] * np.array([0, 0, 1]) + face * (rng.normal(size=(m, 1)) * 0.4)
            cloud.add(pts, np.tile(unit(face + np.array([0, 0, 0.3])), (m, 1)), base * (1 + 0.08 * rng.normal(size=(m, 1))), 1.0)
    else:  # 巨柱仙人掌
        r = H * 0.08
        ribbed((0, 0, 0), (0, 0, H * 0.92), r)
        for side, h0, h1 in ((1, 0.35, 0.68), (-1, 0.48, 0.80)):
            p0 = np.array([0, side * r * 0.8, H * h0])
            p1 = p0 + np.array([0, side * H * 0.16, H * 0.02])
            ribbed(p0, p1, r * 0.72)
            ribbed(p1, p1 + np.array([0, 0, H * (h1 - h0)]), r * 0.72)
    return cloud


def build_rosette(cfg, season, rng, H, snow):
    """約書亞樹（分叉枝端的尖葉簇）與絲蘭（地面的尖葉叢＋花梗）。"""
    cloud = Cloud()
    base = LEAF[cfg.get("leaf", "olive")]
    bark = BARK["grey"]
    tips = []
    if cfg.get("shape") == "joshua":
        tr = H * 0.05
        trunk_top = np.array([0, 0, H * 0.45])
        cylinder(cloud, (0, 0, 0), trunk_top, tr, tr * 0.8, bark, rng)
        for k in range(5):
            a = k / 5 * 2 * math.pi + rng.random() * 0.5
            mid = trunk_top + np.array([math.cos(a) * H * 0.14, math.sin(a) * H * 0.14, H * 0.16])
            end = mid + np.array([math.cos(a) * H * 0.06, math.sin(a) * H * 0.06, H * (0.14 + 0.1 * rng.random())])
            cylinder(cloud, trunk_top, mid, tr * 0.6, tr * 0.5, bark, rng)
            cylinder(cloud, mid, end, tr * 0.5, tr * 0.45, bark, rng)
            tips.append((end, H * 0.12))
    else:
        tips.append((np.array([0, 0, H * 0.18]), H * 0.32))
        stalk_top = np.array([0, 0, H * 0.95])
        cylinder(cloud, (0, 0, H * 0.2), stalk_top, 0.6, 0.4, rgb(120, 110, 70), rng)
        fl = stalk_top - np.array([0, 0, H * 0.15]) * rng.random((30, 1)) + rng.normal(size=(30, 3)) * np.array([H * 0.03, H * 0.03, 0])
        cloud.add(fl, np.tile([0, 0, 1.0], (30, 1)), rgb(228, 224, 196), 1.0)
    for c, length in tips:
        for _ in range(90):
            d = unit(rng.normal(size=3) + np.array([0, 0, 0.6]))
            t = np.linspace(0, 1, int(length * 2) + 2)[:, None]
            side = unit(np.cross(d, [0, 0, 1.0]) + 1e-6) * 0.6
            for off in (-0.5, 0.5):
                pts = c + d * length * t + side * off * (1 - t)
                cloud.add(pts, np.tile(unit(d + np.array([0, 0, 0.5])), (len(pts), 1)), base * (0.85 + 0.3 * rng.random()), 0.9)
    return cloud


SPECIES = {
    # 闊葉
    "oak": dict(build="deciduous", leaf="green", crown=(0.58, 0.80, 0.53), blobs=14, autumn="rust", autumn_green=0.06, trunk_w=1.3, trunk_h=0.18),
    "beech": dict(build="deciduous", leaf="darkgreen", crown=(0.46, 0.50, 0.62), blobs=12, autumn="orange"),
    "birch": dict(build="deciduous", leaf="avocado", crown=(0.38, 0.52, 0.64), blobs=10, blob_r=(0.30, 0.48), autumn="yellow",
                  trunk="light", airy=0.8),
    "chestnut": dict(build="deciduous", leaf="darkgreen", crown=(0.50, 0.48, 0.60), blobs=13, autumn="orange", flowers="cream"),
    "elm": dict(build="deciduous", leaf="green", crown=(0.44, 0.54, 0.60), blobs=12, autumn="yellow", trunk_h=0.5),
    "copperbeech": dict(build="deciduous", leaf="copper", crown=(0.50, 0.46, 0.60), blobs=12, autumn="copper", spring="copper"),
    "frisia": dict(build="deciduous", leaf="gold", crown=(0.46, 0.48, 0.60), blobs=11, autumn="yellow", spring="gold", airy=0.85),
    "ash": dict(build="deciduous", leaf="avocado", crown=(0.46, 0.46, 0.63), blobs=14, blob_r=(0.28, 0.46), autumn="yellow", airy=0.75),
    "robinia": dict(build="deciduous", leaf="green", crown=(0.48, 0.44, 0.63), blobs=14, blob_r=(0.28, 0.48), autumn="yellow",
                    airy=0.8, flowers="white"),
    "maple": dict(build="deciduous", leaf="green", crown=(0.50, 0.48, 0.58), blobs=12, autumn="orange"),
    "sugarmaple": dict(build="deciduous", leaf="darkgreen", crown=(0.48, 0.50, 0.58), blobs=12, autumn="red", autumn_green=0.08),
    "crab": dict(build="deciduous", leaf="green", crown=(0.48, 0.42, 0.52), blobs=10, autumn="red", flowers="pink", trunk_h=0.35),
    "snowbell": dict(build="deciduous", leaf="avocado", crown=(0.50, 0.44, 0.55), blobs=10, autumn="yellow", flowers="white", trunk_h=0.38),
    "birch2": dict(build="deciduous", leaf="avocado", crown=(0.36, 0.52, 0.64), blobs=10, blob_r=(0.30, 0.48), autumn="yellow",
                   airy=0.75, trunk="light"),
    "strawberry": dict(build="deciduous", leaf="darkgreen", crown=(0.50, 0.52, 0.50), blobs=12, evergreen=True, trunk_h=0.25),
    "yew": dict(build="deciduous", leaf="darkgreen", crown=(0.50, 0.56, 0.50), blobs=14, evergreen=True, trunk_h=0.2),
    "willow": dict(build="weeping", leaf="avocado", autumn="yellow"),
    # 針葉
    "pine": dict(build="conifer", leaf="darkgreen", layers=6, width=1.0),
    "scotspine": dict(build="pine", leaf="darkgreen", trunk="red", tufts=9),
    "fir": dict(build="conifer", leaf="green", layers=7, width=0.95),
    "bluespruce": dict(build="conifer", leaf="seagreen", layers=6, width=1.0),
    "grandfir": dict(build="conifer", leaf="darkgreen", layers=5, width=1.0),
    "borisfir": dict(build="conifer", leaf="green", layers=7, width=0.9),
    "redcedar": dict(build="conifer", leaf="darkgreen", layers=8, width=0.75, trunk="red"),
    "redwood": dict(build="conifer", leaf="green", layers=7, width=0.9, trunk="red", shape="cone"),
    "pondcypress": dict(build="conifer", leaf="avocado", layers=7, width=0.8, shape="cone"),
    "swampcypress": dict(build="conifer", leaf="green", layers=7, width=1.0, shape="cone"),
    "silverpine": dict(build="pine", leaf="seagreen", trunk="grey", tufts=11),
    "cedar": dict(build="conifer", leaf="darkgreen", layers=4, width=1.3, shape="cone"),
    "italiancypress": dict(build="column", leaf="darkgreen", width=0.55),
    "irishyew": dict(build="column", leaf="darkgreen", width=0.8),
    "hinoki": dict(build="column", leaf="avocado", width=0.9),
    # 其他
    "palm": dict(build="palm", leaf="green"),
    "silverpalm": dict(build="palm", leaf="seagreen"),
    "cactus": dict(build="cactus", leaf="green"),
    "barrel": dict(build="cactus", leaf="green", shape="barrel"),
    "pricklypear": dict(build="cactus", leaf="avocado", shape="pear"),
    "joshua": dict(build="rosette", leaf="olive", shape="joshua"),
    "yucca": dict(build="rosette", leaf="seagreen", shape="yucca"),
}
BUILDERS = {"deciduous": build_deciduous, "conifer": build_conifer, "pine": build_pine, "column": build_column, "weeping": build_weeping,
            "palm": build_palm, "cactus": build_cactus, "rosette": build_rosette}


def _snow(cloud, threshold=0.35):
    p, n, c, ao, size = cloud.arrays()
    top = n[:, 2] > threshold
    c = c.copy()
    c[top] = SNOW
    cloud.__init__()
    cloud.add(p, n, c, ao, 1)

# ---------------------------------------------------------------- 算圖


def project(p):
    return p[:, 0] - p[:, 1], (p[:, 0] + p[:, 1]) / 2 - p[:, 2]


def render(cloud, w, h, ox, oy):
    """→ (w×h 調色盤 index, 0 = 透明)。"""
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
    # 背光面（以整棵樹的中心判斷）較暗
    centre = pp.mean(0)
    flat = LIGHT * np.array([1, 1, 0])                # 只依水平方向判斷背光面（下方不額外變暗）
    side = ((pp - centre) @ flat) / max(np.abs((pp - centre) @ flat).max(), 1e-6)
    lightfac = 0.70 + 0.30 * np.clip((side + 0.6) / 1.4, 0, 1)
    inten = np.maximum((0.50 + 0.80 * lam) * ao * lightfac, 0.42)
    col = c * inten[:, None]
    col += (np.array([0.10, 0.10, 0.01]) * lam[:, None] ** 3)      # 受光的葉面偏黃綠
    col = col * (1 - 0.12 * (1 - lam))[:, None] + np.array([0.0, 0.01, 0.03]) * (1 - lam)[:, None]
    order = np.argsort(depth)                       # 由遠到近覆蓋 → 最後留下最近的點
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
    holes = rng.random((h, w)) < 0.22                 # 葉間透光
    out[holes] = 0
    return out


def tree_height(e) -> float:
    """sprite 的可用高度（原點上方）與寬度限制下的樹高。"""
    return float(-e.y_offset) * 0.98


def make_cloud(cfg, season, H, seed, snow):
    rng = np.random.default_rng(seed)
    return BUILDERS[cfg["build"]](cfg, season, rng, H, snow)


def fit_cloud(cfg, season, e, seed, snow, ref=None):
    """依 sprite 的大小縮放，讓樹撐滿影格（原點在 (-x_offset, -y_offset)）：X/Y 依寬度、Z 依高度分別縮放。
    ref：同一棵樹夏季的點雲；各季節用同一組縮放比例，季節切換時大小不跳動。"""
    H = tree_height(e)
    cloud = make_cloud(cfg, season, H, seed, snow)
    base = ref if ref is not None else cloud
    p, *_ = base.arrays()
    if not len(p):
        return cloud, (1.0, 1.0)
    ox, oy = -e.x_offset, -e.y_offset
    sx, _ = project(p)
    half = min(ox, e.width - ox) - 1.0
    fx = np.clip(half / max(np.abs(sx).max(), 1e-6), 0.5, 1.8)
    q = p * np.array([fx, fx, 1.0])
    _, sy = project(q)
    fz = np.clip((oy - 1.0 - 0.0) / max(-sy.min(), 1e-6), 0.5, 1.8)
    return scale_cloud(cloud, fx, fz), (fx, fz)


def scale_cloud(cloud, fx, fz):
    p, n, c, ao, size = cloud.arrays()
    out = Cloud()
    if len(p):
        out.add(p * np.array([fx, fx, fz]), unit(n / np.array([fx, fx, fz])), c, ao, 1)
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
            # 同一棵樹各季節形狀一致：種子只依旋轉與成長階段；縮放比例取自夏季（或第一個季節）的樣子
            sd = seed * 1000 + r * 37 + g
            ref_season = 3 if 3 in seasons else seasons[0]
            ref = make_cloud(cfg, ref_season, tree_height(entries[k]), sd, False)
            clouds[key] = fit_cloud(cfg, s, entries[k], sd, snow, ref)[0]
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
        im = Image.new("RGB", (cell_w * 5, cell_h * len(names)), (120, 132, 96))
        for row, name in enumerate(names):
            cfg = SPECIES[name]
            for col, (season, snow) in enumerate(((3, False), (0, False), (2, False), (1, False), (3, True))):
                cloud = make_cloud(cfg, season, 120, args.seed, snow)
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
