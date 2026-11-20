#!/usr/bin/env python3
"""region 物件的 112×112 預覽圖：用 repo 內**已完成的 OG 物件 sprite** 拼成一個小場景（草地、房屋、樹、礦井），
不使用任何 vanilla 圖像。

  python3 tools/gen/region_image.py --template <模板.DAT> -o <資料夾> \\
      --scene building:BLDHOUS2@64,84 tree:OAK@24,88 ...

--scene 的每一項：<種類>:<vanilla 名稱>@<x>,<y>[:<部件 index>]，(x, y) 是該物件所在圖塊中心在畫布上的位置；
依 y 由後往前繪製。種類：building（依第一種變化堆疊部件）、tree（夏季、旋轉 0；index 為成長階段，預設成樹）、
industry（指定部件，預設 1）。
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import common
import dat
import objinfo

REPO = Path(__file__).resolve().parents[2]
SIZE = 112
BG_TOP, BG_BOTTOM = 0x0A + 2, 0x0A + 4          # 背景：black 色階的深灰漸層
GRASS = [0x46 + k for k in (3, 4, 5, 6)]         # mutedGrassGreen 色階
EDGE = 0x46 + 2
# 介面上的預覽圖不會套公司色：公司色 index 改成固定色階（primary → 紅褐屋瓦、secondary → 土黃）
PRIMARY_REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))
FIXED = {idx: 0x3A + k for k, idx in enumerate(PRIMARY_REMAP)}
FIXED.update({0xCA + k: 0x22 + k for k in range(12)})


def find_dat(vanilla: str) -> dat.DatObject:
    hits = list((REPO / "objects").glob(f"*/*/**/{vanilla}/OG_{vanilla}.dat"))
    if not hits:
        raise SystemExit(f"找不到 OG_{vanilla}.dat")
    return dat.read_dat(hits[0])


def sprite(obj: dat.DatObject, index: int):
    w, h, x, y, px, al = dat.decode_sprite(obj.image_table(), index)
    return w, h, x, y, bytes(FIXED.get(px[k], px[k]) if al[k] else 0 for k in range(w * h))


def blit(canvas: bytearray, spr, ax: int, ay: int) -> None:
    w, h, x, y, px = spr
    for j in range(h):
        cy = ay + y + j
        if not 0 <= cy < SIZE:
            continue
        for i in range(w):
            v = px[j * w + i]
            cx = ax + x + i
            if v and 0 <= cx < SIZE:
                canvas[cy * SIZE + cx] = v


def layers(kind: str, name: str, part: int | None):
    """回傳 [(sprite, 往上的位移 px)]。"""
    obj = find_dat(name)
    if kind == "building":
        info = objinfo.building(obj)
        z, out = 0, []
        for p in info["variations"][0]:
            out.append((sprite(obj, p * 4), z))
            z += info["heights"][p]
        return out
    if kind == "tree":
        d = obj.data
        rot, growth = d[6], d[7]
        seasons = [b for b in range(6) if d[0x3C] >> b & 1]
        season = 3 if 3 in seasons else seasons[0]
        stage = growth - 1 if part is None else min(part, growth - 1)
        index = seasons.index(season) * growth * rot + stage * rot
        return [(sprite(obj, index), 0)]
    if kind == "industry":
        info = objinfo.industry(obj)
        base = info["first_part_image"] + (len(info["variations"]) * 4 if info["has_shadows"] else 0)
        return [(sprite(obj, base + (part if part is not None else 1) * 4), 0)]
    raise SystemExit(f"不支援的種類：{kind}")


def background(seed: int) -> bytearray:
    rng = random.Random(seed)
    c = bytearray(SIZE * SIZE)
    for y in range(SIZE):
        for x in range(SIZE):
            c[y * SIZE + x] = BG_TOP if y < SIZE * 0.45 else BG_BOTTOM
    # 菱形草地（等角投影的一塊地）
    cx, cy, hw, hh = SIZE // 2, 76, 54, 27
    for y in range(SIZE):
        for x in range(SIZE):
            d = abs(x - cx) / hw + abs(y - cy) / hh
            if d <= 1.0:
                c[y * SIZE + x] = EDGE if d > 0.96 else rng.choice(GRASS)
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--scene", nargs="+", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    entry = common.template_entries(args.template)[0]
    if (entry.width, entry.height) != (SIZE, SIZE):
        raise SystemExit(f"模板圖片是 {entry.width}×{entry.height}，預期 {SIZE}×{SIZE}")
    canvas = background(args.seed)
    items = []
    for spec in args.scene:
        kind, rest = spec.split(":", 1)
        name, rest = rest.split("@", 1)
        pos, _, part = rest.partition(":")
        x, y = (int(v) for v in pos.split(","))
        items.append((y, x, kind, name, int(part) if part else None))
    for y, x, kind, name, part in sorted(items):
        for spr, dz in layers(kind, name, part):
            blit(canvas, spr, x, y - dz)
    common.write_sprites(args.out, [(SIZE, SIZE, entry.x_offset, entry.y_offset, bytes(canvas))], flags=[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
