#!/usr/bin/env python3
"""g1 的地圖疊加圖（ROADMAP M4）：施工選取框（角／邊／四分之一）、集貨範圍、格線、橋影（整格／半格），各 19 種坡形；
以及不再使用的縮小版（index 0–303）。輸出 base/g1/overlays/（PNG + sprites.json）。

  .venv/bin/python tools/gen/g1_overlays.py

繪製方式（OpenLoco Paint/PaintSurface.cpp）：
- 選取框以 ImageId(圖, ExtColour::unk21–2B) 繪製，像素 = 對照表[來源色號]、0 = 不畫。圖塊分成 4 區，
  每區用一個「標記色號」（tools/g1.py 的 MARK_C／MARK_E／MARK_Q），對照表只讓選中的區顯示（見 tools/g1.py SELECTION_MAPS）。
  區的編號依 World::getQuadrantFromPos（角／四分之一）與 getSideFromPos（邊），以 rotation 0 的世界座標（圖塊內 0–32）：
  角 0 = (32, 32)、1 = (32, 0)、2 = (0, 0)、3 = (0, 32) 那一角的四分之一；邊 0 = x 0、1 = y 32、2 = x 32、3 = y 0 那邊的三角形。
  填色是 50% 棋盤點陣（看起來半透明），外緣一圈實心。
- 集貨範圍以 Colour::darkBlue 換色：用 primary remap 色號的棋盤點陣。
- 格線以 translucentGlass0 半透明疊加，地下檢視時又當遮罩（圖 AND 遮罩）用，所以是 0xFF 的 1 px 外框。
坡形：四角的畫面位置直接從 OG_GRASS1 的坡形圖（image 285 + slope）量出，雙線性內插後再以同一輪廓裁切。
縮小版：OpenLoco 只在有 hasZoomSprites 旗標時使用；正式版一律不提供（tools/g1.py 會拿掉旗標），所以改為 1×1 透明。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402
import g1  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "overlays"


def quadrant(x, y):
    if x >= 16:
        return 0 if y >= 16 else 1
    return 3 if y >= 16 else 2


def side(x, y):
    if x < y:
        return 0 if x + y < 32 else 1
    return 3 if x + y < 32 else 2


def shape_corners(slope):
    """直接從 OG_GRASS1 的坡形圖量出四角的畫面位置：最左／最右欄的中點 = 左角／右角，正中欄的頂／底 = 上角／下角。"""
    ax, ay, aw, ah, alpha = g1.slope_alpha()[slope]

    def col(u):
        return [v for v in range(ah) if alpha[v * aw + u]]
    us = [u for u in range(aw) if col(u)]
    left, right = col(us[0]), col(us[-1])
    mid = col(min(us, key=lambda u: abs(ax + u + 0.5)))
    L = (ax + us[0], ay + (left[0] + left[-1] + 1) / 2)
    R = (ax + us[-1] + 1, ay + (right[0] + right[-1] + 1) / 2)
    T = (0.0, ay + mid[0])
    B = (0.0, ay + mid[-1] + 1)
    return T, R, B, L


def tile_pixels(slope):
    """{(sx, sy): (x, y)}：坡形圖塊在畫面上的每個像素 → 圖塊內的世界座標（雙線性反推；以 OG_GRASS1 坡形裁切）。"""
    ax, ay, aw, ah, alpha = g1.slope_alpha()[slope]
    if not any(alpha):                                     # displaySlope 16 不會出現（vanilla 也是 1×1）
        return {}
    T, R, B, L = shape_corners(slope)
    best = {}
    n = 160
    for i in range(n + 1):
        u = i / n
        for j in range(n + 1):
            v = j / n
            sx = T[0] * (1 - u) * (1 - v) + R[0] * (1 - u) * v + B[0] * u * v + L[0] * u * (1 - v)
            sy = T[1] * (1 - u) * (1 - v) + R[1] * (1 - u) * v + B[1] * u * v + L[1] * u * (1 - v)
            px, py = int(sx // 1), int(sy // 1)
            d = (sx - px - 0.5) ** 2 + (sy - py - 0.5) ** 2
            if (px, py) not in best or d < best[(px, py)][0]:
                best[(px, py)] = (d, (u * 32, v * 32))
    out = {}
    for (px, py), (_d, xy) in best.items():
        uu, vv = px - ax, py - ay
        if 0 <= uu < aw and 0 <= vv < ah and alpha[vv * aw + uu]:
            out[(px, py)] = xy
    # 坡形輪廓內沒被取樣到的像素（極少數）用最近的鄰居補
    for vv in range(ah):
        for uu in range(aw):
            if alpha[vv * aw + uu] and (ax + uu, ay + vv) not in out:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
                    if (ax + uu + dx, ay + vv + dy) in out:
                        out[(ax + uu, ay + vv)] = out[(ax + uu + dx, ay + vv + dy)]
                        break
    return out


def frame(pix):
    if not pix:
        return (1, 1, 0, 0, bytes(1))
    xs = [p[0] for p in pix]
    ys = [p[1] for p in pix]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    px = bytearray(w * h)
    for (x, y), v in pix.items():
        px[(y - y0) * w + x - x0] = v
    return (w, h, x0, y0, bytes(px))


def edge_set(shape):
    return {p for p in shape if any((p[0] + dx, p[1] + dy) not in shape for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}


def selection(shape, region_of, markers):
    outline = edge_set(shape)
    pix = {}
    for (x, y), xy in shape.items():
        if (x, y) in outline or (x + y) % 2 == 0:
            pix[(x, y)] = markers[region_of(*xy)]
    return frame(pix)


def catchment(shape):
    """集貨範圍：圖塊內縮 2 px 的棋盤點陣（primary remap 色號，遊戲換成深藍）。"""
    inner = {p: xy for p, xy in shape.items() if 2 <= xy[0] <= 30 and 2 <= xy[1] <= 30}
    return frame({p: g1.PRIMARY_REMAP[7] for p in inner if (p[0] + p[1]) % 2 == 0})


def gridlines(shape):
    return frame({p: 0xFF for p in edge_set(shape)})


BRIDGE_REGIONS = {  # 橋影（Paint/PaintBridge.cpp，以陰影對照表 unk32 半透明疊加）：圖塊內哪一半（rotation 0 世界座標）
    "FullTile": lambda x, y: True,
    "Quarter0": lambda x, y: x + y < 32, "Quarter1": lambda x, y: x + y >= 32,
    "Quarter2": lambda x, y: y < x, "Quarter3": lambda x, y: y >= x,
}


def bridge_shadow(shape, region):
    return frame({p: 0x0A + 1 for p, xy in shape.items() if region(*xy)})


def build():
    cat = json.loads(CATALOG.read_text())
    ids = {e["name"]: e["i"] for e in cat["entries"] if e.get("name")}
    frames = []
    for s in range(19):
        shape = tile_pixels(s)
        frames.append((ids[f"constructionSelectionCornersSlope{s}"], selection(shape, quadrant, g1.MARK_C)))
        frames.append((ids[f"constructionSelectionQuadsSlope{s}"], selection(shape, quadrant, g1.MARK_Q)))
        frames.append((ids[f"constructionSelectionEdgesSlope{s}"], selection(shape, side, g1.MARK_E)))
        frames.append((ids[f"constructionCatchmentSlope{s}"], catchment(shape)))
        frames.append((ids[f"gridlinesSlope{s}"], gridlines(shape)))
        for kind, region in BRIDGE_REGIONS.items():
            name = f"bridgeShadow{kind}Slope{s}"
            if name in ids:
                frames.append((ids[name], bridge_shadow(shape, region)))
    # 縮小版（只被 hasZoomSprites 引用；正式版不提供）
    zoom_targets = {e["i"] - e["z"] for e in cat["entries"] if e["f"] & dat.G1_HAS_ZOOM}
    for i in sorted(zoom_targets):
        frames.append((i, (1, 1, 0, 0, bytes(1))))
    return frames


def main() -> int:
    frames = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    pal = list(dat.load_palette())
    meta = []
    for idx, (w, h, x, y, px) in sorted(frames):
        fn = f"{idx}.png"
        dat.write_indexed_png(OUT / fn, w, h, px, bytes(255 if v else 0 for v in px), pal)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (OUT / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"寫出 {len(frames)} 張 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
