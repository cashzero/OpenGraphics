#!/usr/bin/env python3
"""柔和冰藍雪地產生器（fork 覆寫上游 OG_SNOW）：消除原上游版斜坡黑點（index 253–254）與高頻雜訊，
改用 Locomotion 調色盤中最柔和的冰灰藍至雪白漸層（16, 17, 18, 19, 20, 21, 129）與平順風吹雪丘紋理。

  .venv/bin/python tools/gen/snow.py [--template <OG_SNOW.dat>] -o <資料夾>

產出 139 張影格（與原版 SNOW.DAT / OG_SNOW.dat 結構完全一致）：
  - #0..18   Zoom 3（8 px 寬）19 種坡度雪面
  - #19..37  Zoom 2（16 px 寬）19 種坡度雪面；#38..56 為格線
  - #57..75  Zoom 1（32 px 寬）19 種坡度雪面；#76..94 為格線
  - #95..113 Zoom 0（64 px 寬）19 種坡度雪面；#114..132 為格線
  - #133..138 六階無縫 64×63 明暗雪地紋理（供 OpenLoco 連續雪坡混合使用）
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common  # noqa: E402
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
GRASS_DAT = REPO / "objects" / "VanillaReplacements" / "Land" / "GRASS1" / "OG_GRASS1.dat"
GRASS_SLOPE_START = 285

# 全部嚴格落在 OpenLoco 可繪製色盤（10..245）內：由深冰藍影 → 柔和雪白 → 向陽冰白亮點
SNOW_RAMP = np.array([16, 17, 18, 19, 20, 21, 129], dtype=np.uint8)


def _smooth_inside_mask(vals: np.ndarray, mask: np.ndarray, passes: int = 3) -> np.ndarray:
    """只在有效遮罩內平滑草地坡度明暗，去除草地雜訊但保留清晰的坡面折線。"""
    out = vals.astype(np.float64).copy()
    m = mask.astype(np.float64)
    for _ in range(passes):
        acc = np.zeros_like(out)
        w = np.zeros_like(m)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                wt = 4.0 if (dx == 0 and dy == 0) else (2.0 if (dx == 0 or dy == 0) else 1.0)
                sy0, sy1 = max(0, -dy), out.shape[0] - max(0, dy)
                sx0, sx1 = max(0, -dx), out.shape[1] - max(0, dx)
                dy0, dy1 = max(0, dy), out.shape[0] - max(0, -dy)
                dx0, dx1 = max(0, dx), out.shape[1] - max(0, -dx)
                acc[dy0:dy1, dx0:dx1] += out[sy0:sy1, sx0:sx1] * m[sy0:sy1, sx0:sx1] * wt
                w[dy0:dy1, dx0:dx1] += m[sy0:sy1, sx0:sx1] * wt
        out = np.where(w > 0, acc / np.maximum(w, 1e-9), out)
    return out


def _snow_drift(w: int, h: int, seed: int, amp: float = 0.42, periodic: bool = False) -> np.ndarray:
    """柔和的低頻風吹雪丘起伏（無高頻顆粒雜訊）。periodic=True 時在 64×63 上完全無縫循環。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    field = np.zeros((h, w), dtype=np.float64)
    if periodic:
        # 週期性低頻諧波，保證平鋪完全無接縫
        for fx, fy, weight in (
            (1, 0, 0.30), (0, 1, 0.28), (1, 1, 0.25), (2, -1, 0.20),
            (-1, 2, 0.18), (2, 2, 0.15), (3, -1, 0.12), (-2, 3, 0.11),
            (4, 1, 0.08), (1, 4, 0.08),
        ):
            ph = rng.uniform(0, 2 * math.pi)
            field += weight * np.sin(2 * math.pi * (fx * xx / w + fy * yy / h) + ph)
        # 微弱細粒雪面質感（不產生黑點）
        field += rng.normal(0.0, 0.16, size=(h, w))
    else:
        for freq, weight in ((0.11, 0.40), (0.19, 0.30), (0.31, 0.18)):
            ang = rng.uniform(0, 2 * math.pi)
            ph = rng.uniform(0, 2 * math.pi)
            field += weight * np.sin((xx * math.cos(ang) + yy * math.sin(ang)) * freq + ph)
        field += rng.normal(0.0, 0.15, size=(h, w))
    # 正規化到 [-amp, +amp]
    std = max(float(field.std()), 1e-6)
    return (field / (std * 2.1)) * amp


def _load_slope_light_maps() -> list[np.ndarray]:
    """從 OG_GRASS1 的 19 張 Zoom 0 坡度圖塊萃取正規化坡度明暗場（0.0 最暗背陽坡 ～ 1.0 最亮向陽坡）。"""
    pal = np.array(dat.load_palette(), dtype=np.float64)
    lum_lut = 0.299 * pal[:, 0] + 0.587 * pal[:, 1] + 0.114 * pal[:, 2]
    gobj = dat.read_dat(GRASS_DAT)
    gtbl = gobj.image_table()
    raw = []
    masks = []
    for k in range(19):
        idx = GRASS_SLOPE_START + k
        e = gtbl.entries[idx]
        px = np.frombuffer(dat.decode_sprite(gtbl, idx)[-2], dtype=np.uint8).reshape(e.height, e.width)
        m = px != 0
        lm = np.where(m, lum_lut[px], 0.0)
        sm = _smooth_inside_mask(lm, m, passes=4)
        raw.append(sm)
        masks.append(m)
    # 依所有坡度的 5%～98% 亮度分布做全域對齊（平地約 0.62，背陽坡 ~0.12，陡向陽坡 ~0.98）
    all_v = np.concatenate([r[m] for r, m in zip(raw, masks) if m.any()])
    lo = float(np.percentile(all_v, 3))
    hi = float(np.percentile(all_v, 98))
    return [np.clip((r - lo) / max(hi - lo, 1e-6), 0.0, 1.0) for r in raw]


def _map_snow_level(level: np.ndarray) -> np.ndarray:
    """將連續雪地明暗值（0.0 = index 16，6.0 = index 129）對映到 SNOW_RAMP。"""
    idx = np.clip(np.rint(level), 0, len(SNOW_RAMP) - 1).astype(np.int64)
    return SNOW_RAMP[idx]


def build_frames(template: Path) -> list[tuple[int, int, int, int, bytes]]:
    obj = dat.read_dat(template)
    tbl = obj.image_table()
    if len(tbl.entries) != 139:
        raise SystemExit(f"預期 139 張雪地影像，模板只有 {len(tbl.entries)} 張")

    slope_lights = _load_slope_light_maps()
    frames = []

    # 坡度圖塊群組的起始 index
    SLOPE_STARTS = {0, 19, 57, 95}
    GRID_STARTS = {38, 76, 114}

    for i, e in enumerate(tbl.entries):
        raw_px = np.frombuffer(dat.decode_sprite(tbl, i)[-2], dtype=np.uint8).reshape(e.height, e.width)
        mask = raw_px != 0

        if i >= 133:
            # #133..138：六階無縫 64×63 明暗雪地紋理（對應原版：陰影坡 17/18 → 平地 19/20 → 向陽坡 21/129）
            # SNOW_RAMP index: 0=16, 1=17, 2=18, 3=19, 4=20, 5=21, 6=129
            lvl_cfg = {
                133: (1.95, 0.58),   # 深陰影坡（主 18/17，少量 19）
                134: (2.55, 0.55),   # 陰影坡（主 18/19，少量 20）
                135: (3.55, 0.48),   # 平緩雪面（主 20/19，極少量 21）
                136: (3.85, 0.72),   # 柔和雪丘（19/20/21 漸變）
                137: (4.92, 0.45),   # 向陽坡（主 21，少量 20 與 129 冰亮）
                138: (5.06, 0.36),   # 最亮向陽坡（主 21，微點 129）
            }
            base_lvl, amp = lvl_cfg[i]
            drift = _snow_drift(e.width, e.height, seed=1000 + i, amp=amp, periodic=True)
            out = _map_snow_level(base_lvl + drift)
            frames.append((e.width, e.height, e.x_offset, e.y_offset, out.tobytes()))
            continue

        # 格線群組（#38..56, #76..94, #114..132）：保留精確 1px 輪廓遮罩，填入柔和雪白 index 20
        is_grid = any(s <= i < s + 19 for s in GRID_STARTS)
        if is_grid:
            out = np.where(mask, np.uint8(20), np.uint8(0))
            frames.append((e.width, e.height, e.x_offset, e.y_offset, out.tobytes()))
            continue

        # 坡度雪面（Zoom 3: 0..18, Zoom 2: 19..37, Zoom 1: 57..75, Zoom 0: 95..113）
        base_start = max(s for s in SLOPE_STARTS if s <= i)
        slope_k = i - base_start
        if not mask.any():
            frames.append((e.width, e.height, e.x_offset, e.y_offset, bytes(e.width * e.height)))
            continue

        # 將 Zoom 0 的 19 坡度明暗場依座標取樣到當前縮放大小
        sl = slope_lights[slope_k]
        sh, sw = sl.shape
        yy = np.clip(np.floor(np.linspace(0, sh - 1, e.height)).astype(int), 0, sh - 1)
        xx = np.clip(np.floor(np.linspace(0, sw - 1, e.width)).astype(int), 0, sw - 1)
        L = sl[yy[:, None], xx[None, :]]

        # 明暗曲線：
        #   L ≈ 0.05 (最暗背陽坡) → level ≈ 1.75 (index 17–18 柔和冰藍影)
        #   L ≈ 0.62 (平地)       → level ≈ 3.72 (index 19–20 柔和雪白)
        #   L ≈ 0.96 (陡向陽坡)   → level ≈ 5.12 (index 21 + 129 冰白亮點)
        level = 1.65 + 3.55 * L
        amp = 0.44 if base_start == 95 else (0.34 if base_start == 57 else 0.22)
        drift = _snow_drift(e.width, e.height, seed=200 + i, amp=amp, periodic=False)
        mapped = _map_snow_level(level + drift)
        out = np.where(mask, mapped, np.uint8(0))
        frames.append((e.width, e.height, e.x_offset, e.y_offset, out.tobytes()))

    return frames


def pack_snow_dat(template: Path, out_dat: Path, frames: list[tuple[int, int, int, int, bytes]],
                  out_png_dir: Path | None = None) -> None:
    """保留模板 139 張雪地圖塊的精確 flags（1/17，非 RLE 原始像素）與 zoom_offset，寫出 OG_SNOW.dat 並驗證。"""
    obj = dat.read_dat(template)
    tbl = obj.image_table()
    if len(frames) != len(tbl.entries):
        raise SystemExit("影格數與模板不符")
    new_entries = []
    blob = bytearray()
    pal = dat.load_palette()
    for i, (e, (w, h, ox, oy, px)) in enumerate(zip(tbl.entries, frames)):
        if len(px) != w * h:
            raise SystemExit(f"#{i} 像素長度不符")
        # 確保全部像素為 0（透明）或 10..245（可繪色盤），絕不出現 253–254 黑點
        bad = [v for v in px if v != 0 and not (10 <= v <= 245)]
        if bad:
            raise SystemExit(f"#{i} 出現超出範圍的色盤 index：{set(bad)}")
        new_entries.append(dat.G1Entry(len(blob), w, h, ox, oy, e.flags, e.zoom_offset))
        blob += px
        if out_png_dir is not None:
            alpha = bytes(255 if v else 0 for v in px)
            dat.write_indexed_png(out_png_dir / f"{i}.png", w, h, px, alpha, pal)
    new_data = dat.replace_image_table(obj.data, tbl.offset, new_entries, bytes(blob))
    dat.write_dat(out_dat, obj.flags, obj.name, new_data, encoding=obj.encoding)
    # 讀回驗證 checksum 與解碼
    chk = dat.read_dat(out_dat)
    assert chk.checksum_ok(), "OG_SNOW.dat checksum 驗證失敗"
    ctbl = chk.image_table()
    for i, (_, _, _, _, px) in enumerate(frames):
        assert dat.decode_sprite(ctbl, i)[-2] == px, f"#{i} 解碼像素不一致"
    print(f"寫出 {out_dat}：{len(frames)} 張原始雪地影格，checksum OK，全部索引 10..245 驗證通過")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default=str(REPO / "objects/VanillaReplacements/Snow/SNOW/OG_SNOW.dat"))
    ap.add_argument("-o", "--output", help="輸出 sprites 資料夾（PNG + sprites.json）")
    ap.add_argument("--pack-dat", help="直接打包成 DAT（保留原始非 RLE flags 與 zoom_offset）")
    ap.add_argument("--png-dir", help="搭配 --pack-dat 同步寫出 0.png..138.png 來源圖")
    args = ap.parse_args()
    tpl = Path(args.template)
    frames = build_frames(tpl)
    if args.output:
        common.write_sprites(Path(args.output), frames)
    if args.pack_dat:
        pack_snow_dat(tpl, Path(args.pack_dat), frames, Path(args.png_dir) if args.png_dir else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
