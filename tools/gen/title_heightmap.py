#!/usr/bin/env python3
"""標題畫面地圖的高度圖（ROADMAP M6）→ base/title/heightmap.png（384×384 灰階）。

  .venv/bin/python tools/gen/title_heightmap.py [--preview build/preview/title_heightmap.png]

OpenLoco 的 PNG 高度圖（Map/MapGenerator/PngTerrainGenerator.cpp）：亮度 v → 高度 2 + v/255×38 級（取整數），
1 級 = 16 世界單位（一段坡道的落差）；海平面 4 級，低於海平面的格子變成水。影像的 (列, 欄) = 地圖的 (x, y)，
所以這裡直接用 H[x, y] 陣列存成影像。地圖上方的角是 (0, 0)：+x 往畫面左下、+y 往畫面右下（rotation 0）。

地形分區（格座標）：
- 北角（x、y 都小）：阿爾卑斯高山，最高約 34 級（Mountain Climate 的雪線約 12–18 級）
- 中央：起伏丘陵 9–15 級；一條河從山谷流向西南的海（河床 3 級 = 水）
- x 大（畫面左側）：海岸與海灣
- 南方（y 大）：平原 6–7 級（城市、機場、農田）
FLATS 是各場景需要的平地（車站、機場、市中心），由場景腳本 base/title/title.yml 使用。
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "base" / "title" / "heightmap.png"
N = 384
SEA = 4

# 河道（格座標折線，從山谷到海）
RIVER = [(96, 132), (122, 150), (150, 158), (178, 170), (204, 176), (232, 190), (258, 204), (286, 214), (312, 218), (340, 222), (383, 226)]
# 場景用的地形區塊：(x0, y0, x1, y1, 高度級, 邊緣漸變格數)。區塊內設成該高度（可墊高也可壓低），
# 依序套用，後面的覆蓋前面的；河道在區塊之後才挖，所以河谷照樣存在。
FLATS = [
    # 1 秋季河谷：北岸車站台地 → 高架橋跨河 → 南側山脊（隧道）→ 南側車站台地
    (196, 144, 216, 161, 12, 4),
    (196, 205, 216, 222, 12, 3),
    (296, 226, 316, 240, 6, 6),     # 2 河港城鎮：碼頭邊的平地
    (281, 224, 289, 231, 10, 3),    # 2 河港城鎮：吊橋南岸橋頭（道路下橋處與公車站）
    (214, 284, 252, 318, 7, 6),     # 3 市中心
    (128, 114, 190, 121, 11, 5),    # 5 礦業線：鐵路路基（丘陵中的路塹與路堤）
    (126, 122, 142, 134, 11, 4),    # 5 煤礦
    (174, 122, 192, 136, 11, 4),    # 5 發電廠
    (266, 330, 300, 360, 7, 6),     # 4 機場
    (198, 24, 212, 70, 11, 5),      # 8 林場谷地：林場 → 鋸木廠的運材道路
    (316, 36, 322, 108, 11, 2),     # 9 海岸鐵路：海崖邊的路基
    (60, 70, 92, 84, 26, 6),        # 7 阿爾卑斯雪村
    (70, 112, 86, 120, 17, 6),      # 7 齒軌鐵道的山下車站
]

# 精確剖面（挖完河道與坡度限制後才套用；之後再做一次坡度限制，剖面本身不動）：x 範圍內，各「角」的 y → 高度級（格 (x, y) 的四角是 (x-1|x, y-1|y)）。
# x 方向兩側 soft 格漸變回周圍地形。高度圖的地面是連續的，做不出崖面；隧道口要用場景腳本的 raise 整塊抬高。
PROFILES = [
    # 1 秋季河谷：南岸從 183 起是 12 級平地；山脊由場景腳本的 raise 抬高（崖面才能開隧道口）
    {"x": (196, 216), "soft": 3, "y": {y: 12 for y in range(189, 223)}},
    # 7 齒軌鐵道：從山下車站（17 級，y 112）切穿山脊爬到雪村（26 級，y 84），約每 3 格升 1 級；山谷要夠寬，兩側崖壁才不會擋住列車
    {"x": (73, 83), "soft": 5, "y": {y: round(26 - (y - 84) * 9 / 28) for y in range(84, 113)}},
]


def value_noise(seed: int, cell: int) -> np.ndarray:
    """平滑的值雜訊（0–1）：隨機格點以三次插值放大。"""
    rng = np.random.default_rng(seed)
    g = N // cell + 3
    grid = rng.random((g, g))
    img = Image.fromarray((grid * 255).astype(np.uint8)).resize((g * cell, g * cell), Image.BICUBIC)
    a = np.asarray(img, dtype=np.float64)[cell:cell + N, cell:cell + N] / 255
    return a


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def dist_to_polyline(xs, ys, pts):
    d = np.full(xs.shape, 1e9)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((xs - x0) * dx + (ys - y0) * dy) / (dx * dx + dy * dy), 0, 1)
        d = np.minimum(d, np.hypot(xs - (x0 + t * dx), ys - (y0 + t * dy)))
    return d


def build() -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(N, dtype=np.float64), np.arange(N, dtype=np.float64), indexing="ij")
    n1, n2, n3 = value_noise(11, 48), value_noise(23, 20), value_noise(37, 8)
    rolling = 0.6 * n1 + 0.3 * n2 + 0.1 * n3

    # 丘陵底：9–15 級
    h = 8 + 9 * rolling

    # 南方平原（y 大）：漸變到 6–7 級
    plain = smoothstep(240, 290, ys) * smoothstep(120, 160, xs)
    h = h * (1 - plain) + (6.3 + 0.8 * n2) * plain

    # 北角高山：距 (40, 40) 越近越高，加上山脊雜訊
    dm = np.hypot(xs - 40, ys - 40)
    mountain = smoothstep(150, 40, dm)
    ridges = 1 - np.abs(2 * value_noise(51, 24) - 1)
    h = h + mountain * (14 + 12 * ridges)

    # 海岸：x 大的一側，海岸線隨 y 彎曲，並有一個海灣
    coast = 318 + 14 * np.sin(ys / 37) + 8 * np.sin(ys / 13 + 1.3)
    bay = 30 * np.exp(-((ys - 300) / 28) ** 2)
    sea = smoothstep(coast - bay - 6, coast - bay + 6, xs)
    h = h * (1 - sea) + 1.5 * sea

    # 河：河床 3 級，兩岸 8 格內漸升
    dr = dist_to_polyline(xs, ys, RIVER)
    river = smoothstep(15, 3.5, dr)
    h = h * (1 - river) + 3.0 * river

    # 平地
    for x0, y0, x1, y1, lvl, soft in FLATS:
        inside = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
        edge = np.maximum(np.maximum(x0 - xs, xs - x1), np.maximum(y0 - ys, ys - y1))
        blend = np.where(inside, 1.0, smoothstep(soft, 0, edge))
        h = h * (1 - blend) + lvl * blend

    h = relax(h, xs, ys, dr, mountain, sea)
    prof_mask = np.zeros_like(h, dtype=bool)
    for prof in PROFILES:
        x0, x1 = prof["x"]
        soft = prof["soft"]
        for y, lvl in prof["y"].items():
            for x in range(x0 - soft, x1 + soft + 1):
                d = max(x0 - x, x - x1, 0)
                w = 1.0 if d == 0 else 1 - d / (soft + 1)
                h[x, y] = h[x, y] * (1 - w) + lvl * w
                if w == 1.0:
                    prof_mask[x, y] = True
    h = relax(h, xs, ys, dr, mountain, sea, prof_mask)

    return np.clip(np.round(h), 2, 40).astype(np.int32)


def relax(h, xs, ys, dr, mountain, sea, extra_fixed=None):
    """坡度限制：相鄰點的高低差不超過 1 級（山區 2 級）：太高的壓低、太低的墊高。消除生成器會做成岩石崖面的陡坡，
    讓河岸與丘陵是連續的緩坡。河道中心（水面）與場景平地不動。"""
    h = np.round(h)
    limit = np.where(mountain > 0.5, 2.0, 1.0)
    fixed = (dr < 3.0) | (sea > 0.5)                # 河道中心與海域不動
    if extra_fixed is not None:
        fixed |= extra_fixed
    for x0, y0, x1, y1, *_ in FLATS:
        fixed |= (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
    for _ in range(60):
        lowest, highest = h.copy(), h.copy()
        padded = np.pad(h, 1, mode="edge")             # 不用 np.roll：地圖邊緣不可以繞到另一端
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = padded[1 + dx:1 + dx + N, 1 + dy:1 + dy + N]
            lowest, highest = np.minimum(lowest, nb), np.maximum(highest, nb)
        # 先壓低太高的點；再把固定高地（場景平地）旁太低的點墊高，讓平地邊緣延伸成緩坡
        new = np.where(fixed, h, np.minimum(h, lowest + limit))
        new = np.where(fixed, new, np.maximum(new, highest - limit))
        if np.array_equal(new, h):
            break
        h = new
    return h


def to_png_value(h: np.ndarray) -> np.ndarray:
    # 2 + v×38/255 取整數部分 = h：取能達到 h 的最小 v
    return np.clip(np.ceil((h - 2) * 255 / 38 + 1e-6), 0, 255).astype(np.uint8)


def preview(h: np.ndarray, path: Path) -> None:
    rgb = np.zeros((N, N, 3), dtype=np.uint8)
    water = h < SEA
    t = np.clip((h - SEA) / 30, 0, 1)
    rgb[..., 0] = (60 + 150 * t).astype(np.uint8)
    rgb[..., 1] = (140 + 80 * t).astype(np.uint8) * (1 - (t > 0.6)) + (230 * (t > 0.6)).astype(np.uint8)
    rgb[..., 2] = (60 + 120 * t).astype(np.uint8)
    rgb[water] = (40, 90, 170)
    for x0, y0, x1, y1, *_ in FLATS:
        rgb[x0:x1 + 1, y0] = rgb[x0:x1 + 1, y1] = (255, 0, 0)
        rgb[x0, y0:y1 + 1] = rgb[x1, y0:y1 + 1] = (255, 0, 0)
    Image.fromarray(rgb).resize((N * 2, N * 2), Image.NEAREST).save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", default=str(REPO / "build" / "preview" / "title_heightmap.png"))
    args = ap.parse_args()
    h = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(to_png_value(h), mode="L").save(OUT)
    Path(args.preview).parent.mkdir(parents=True, exist_ok=True)
    preview(h, Path(args.preview))
    print(f"高度 {h.min()}–{h.max()} 級，水域 {np.mean(h < SEA) * 100:.0f}% → {OUT}；預覽 {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
