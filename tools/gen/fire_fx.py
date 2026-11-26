#!/usr/bin/env python3
"""2D 粒子／流體紊流火炬火焰與黑煙產生器（給 OG_OILREFIN 64 格動畫使用）。

原版 Locomotion 煉油廠火炬並非 3D 錐體建模，而是 2D 精靈火焰動畫（約 20×83 px，四旋轉共用同一張 2D 畫面）。
本工具以週期性 2D 流體紊流場（白黃高溫火芯 → 橘紅劇烈躍動火舌 → 暗紅餘燼 → 上升捲曲黑煙）
直接繪製 64 格無縫循環的索引色精靈，並回寫至 OG_OILREFIN.dat 的 part 14..77（sprite #56..#311）。

用法：
  .venv/bin/python tools/gen/fire_fx.py [--preview build/preview/check_oilrefin_fire.png]
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import dat  # noqa: E402
import pack  # noqa: E402

# Locomotion 調色盤火焰與黑煙色階（低溫黑煙 → 暗紅餘燼 → 鮮紅 → 烈橘 → 亮黃 → 白熱火芯）
# 查表自 palettes/locopal.act
FIRE_RAMP = [
    168,  # (115,  0,  0) 深暗紅外緣
    170,  # (171,  0,  0) 暗紅火舌
    172,  # (227,  7,  0) 鮮紅火焰
    174,  # (255, 79, 67) 亮紅橘
    182,  # (219, 79,  0) 濃烈橘紅
    184,  # (255,111, 23) 亮橘火
    186,  # (255,163, 79) 淺橘黃
    52,   # (215,167, 19) 金黃
    54,   # (255,231, 47) 熾黃
    56,   # (255,251,143) 淺白黃
    244,  # (255,242,204) 白熱火芯
]
SMOKE_RAMP = [
    10,   # ( 23, 35, 35) 濃黑煤煙
    214,  # ( 39, 19,  0) 焦褐黑煙
    12,   # ( 47, 67, 67) 深灰煙
    178,  # ( 79, 39,  0) 火光照映的暗紅褐煙
    14,   # ( 75, 99, 99) 淡灰捲煙
]


def _periodic_noise(x: np.ndarray, y: np.ndarray, phase: float, freq_x: float, freq_y: float,
                    speed: float, harmonics: list[tuple[float, float, float, float]]) -> np.ndarray:
    """無縫循環（phase ∈ [0, 2π)）的 2D 向上平流紊流場。"""
    acc = np.zeros_like(x, dtype=np.float64)
    wsum = 0.0
    for amp, kx, ky, phi in harmonics:
        # 向上平流（y 隨 phase 向上捲動），speed 必為整數確保 64 格完美首尾相接
        acc += amp * np.sin(x * freq_x * kx + y * freq_y * ky + speed * phase + phi)
        wsum += amp
    return acc / max(wsum, 1e-6)


def render_flare_frame(k: int, n_frames: int = 64, w: int = 24, h: int = 84, attach_y: int = -1) -> tuple[int, int, int, int, bytes]:
    """產生第 k 格火炬火焰＋黑煙 sprite，回傳 (cw, ch, x_off, y_off, px_bytes)。
    原點 (0, 0) 對齊火炬燃燒口中心（畫布底端 y = h - 2、水平中心 x = w / 2）。
    """
    phase = 2.0 * math.pi * k / n_frames
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    # 局部座標：u = 水平（0 = 中心），v = 距燃燒口的向上高度（0 = 火口，1 = 頂端 84px）
    u = xx - (w - 1) * 0.5
    v_px = (h - 2.0) - yy
    v = np.clip(v_px / (h - 2.0), 0.0, 1.0)

    # 兩股不同速度向上捲動的風切擺動，讓火焰與黑煙像真實強風火炬般扭動
    sway = (
        1.6 * np.sin(v * 5.2 - 2.0 * phase + 0.4) * (v ** 0.85)
        + 1.1 * np.sin(v * 9.5 - 3.0 * phase + 1.9) * (v ** 1.1)
        + 0.7 * np.sin(v * 14.0 - 4.0 * phase - 0.7) * (v ** 1.3)
        + 1.3 * (v ** 1.4)  # 微向右上方順風飄散
    )
    us = u - sway

    # 多頻向上平流紊流（決定火舌撕裂、氣泡與煙縷）
    turb1 = _periodic_noise(
        us, v_px, phase, 0.42, 0.22, 3.0,
        [(1.0, 1.0, 1.0, 0.2), (0.65, -1.7, 1.3, 1.7), (0.45, 2.3, 2.1, 3.4), (0.30, -3.1, 2.7, 5.1)],
    )
    turb2 = _periodic_noise(
        us, v_px, phase, 0.68, 0.34, 5.0,
        [(1.0, 1.2, 1.0, 1.1), (0.70, -2.1, 1.6, 2.8), (0.45, 2.9, 2.3, 4.3)],
    )
    turb = 0.62 * turb1 + 0.38 * turb2

    # 火焰高度隨時間自然脈動（約 44–58 px，飽滿劇烈燃燒＋上方捲曲火舌與煤煙）
    pulse = 0.58 + 0.08 * math.sin(2.0 * phase + 0.3) + 0.04 * math.sin(5.0 * phase - 1.1)
    # 火焰寬度：火口收束 (r≈3.2px) → 下中段飽滿膨脹 (r≈6.2px) → 向上尖細分裂成躍動火舌
    f_v = v / pulse
    fire_radius = np.where(
        f_v < 0.24,
        2.8 + 3.4 * (np.maximum(0.0, f_v) / 0.24) ** 0.65,
        6.2 * np.maximum(0.0, 1.0 - (np.maximum(0.0, f_v - 0.24) / 0.86) ** 1.10),
    )
    # 紊流咬出銳利不規則火舌邊緣（不像 3D 圓錐平滑）
    fire_field = 1.0 - (np.abs(us) / np.maximum(fire_radius, 0.35)) ** 1.60
    fire_heat = fire_field * np.clip(1.24 - 0.86 * f_v, 0.0, 1.25) + turb * (0.30 + 0.44 * np.clip(f_v, 0.0, 1.1))
    # 火口正上方強制白熱核心（讓火炬根部隨時明亮穩定）
    core_dist = np.hypot(u * 0.90, (v_px - 5.0) * 0.44)
    core_boost = np.clip(1.0 - core_dist / 5.2, 0.0, 1.0) ** 1.35 * 0.95
    fire_heat = np.where(v_px >= 0.0, fire_heat + core_boost, -1.0)

    # 飛散分離小火舌（緊貼主焰軸心向上竄出，不往兩側亂散）
    spark_field = _periodic_noise(
        us, v_px, phase, 0.78, 0.32, 4.0,
        [(1.0, 1.1, 1.0, 0.6), (0.8, -1.9, 1.5, 2.2), (0.5, 2.7, 2.0, 4.8)],
    )
    spark_env = np.exp(-((us / 2.5) ** 2)) * np.exp(-(((v - 0.60) / 0.14) ** 2))
    spark_mask = (spark_field * spark_env > 0.34) & (v_px > 24.0)

    # 捲曲上升淡灰黑煙（從火焰上緣開始，輕盈向上飄散到 84px 頂端）
    smoke_v = np.clip((v - 0.38) / 0.62, 0.0, 1.0)
    smoke_r = 2.4 + 3.6 * (smoke_v ** 0.75)
    smoke_turb = _periodic_noise(
        us, v_px, phase, 0.48, 0.22, 2.0,
        [(1.0, 1.0, 1.0, 2.1), (0.7, -1.6, 1.4, 0.5), (0.5, 2.5, 2.2, 3.9)],
    )
    smoke_base = (1.0 - (np.abs(us) / smoke_r) ** 1.5) * np.sin(np.pi * np.clip(smoke_v, 0.0, 1.0)) ** 0.55
    smoke_dens = smoke_base + smoke_turb * 0.38 - 0.24 * smoke_v

    # 合成像素（先畫黑煙，再畫火焰與飛散火舌，最上層是熾黃白熱核心）
    px = np.zeros((h, w), dtype=np.uint8)
    rng_grid = np.sin(xx * 12.9898 + yy * 78.233 + k * 37.719) * 43758.5453
    dither = (rng_grid - np.floor(rng_grid) - 0.5) * 0.14

    # 1. 捲曲黑煙
    sm_val = smoke_dens + dither * 1.4
    sm_on = (v > 0.42) & (sm_val > 0.28)
    sm_idx = np.clip(((1.0 - np.clip((sm_val - 0.28) / 0.52, 0.0, 1.0)) * (len(SMOKE_RAMP) - 1)).astype(np.int32),
                     0, len(SMOKE_RAMP) - 1)
    near_fire = sm_on & (v < 0.64) & (sm_val > 0.44)
    px[sm_on] = np.array(SMOKE_RAMP, dtype=np.uint8)[sm_idx[sm_on]]
    px[near_fire] = 178

    # 2. 飛散小火舌（鮮橘／亮紅）
    px[spark_mask] = np.where(spark_field[spark_mask] > 0.58, 184, 174)

    # 3. 主火焰（白熱核心 → 熾黃 → 亮橘 → 鮮紅 → 暗紅外緣）
    fh = fire_heat + dither
    fire_on = (v_px >= 0.0) & (fh > 0.20)
    # 映射到 FIRE_RAMP（0..10）
    norm_t = np.clip((fh - 0.20) / 1.38, 0.0, 1.0)
    fi = np.clip((norm_t * (len(FIRE_RAMP) - 1) + 0.5).astype(np.int32), 0, len(FIRE_RAMP) - 1)
    px[fire_on] = np.array(FIRE_RAMP, dtype=np.uint8)[fi[fire_on]]

    # 4. 燃燒口金屬小火嘴 2px 銜接（確保不懸空）
    cx = w // 2
    px[h - 2, cx - 1:cx + 2] = 56
    px[h - 1, cx - 1:cx + 2] = 184

    # 裁切到實際非透明邊界並計算相對火口 (cx, h - 1) 的精準偏移
    nz_y, nz_x = np.nonzero(px)
    if len(nz_x) == 0:
        return 1, 1, 0, 0, bytes(1)
    x0, x1 = int(nz_x.min()), int(nz_x.max()) + 1
    y0, y1 = int(nz_y.min()), int(nz_y.max()) + 1
    cropped = px[y0:y1, x0:x1]
    cw, ch = x1 - x0, y1 - y0
    # 讓 (cx, h - 1) 精準貼合 part 13 火炬噴口（由 patch_oilrefin 實測 part 13 頂端座標傳入 attach_y）
    x_off = x0 - cx
    y_off = y0 - (h - 1) + attach_y
    return cw, ch, x_off, y_off, cropped.tobytes()


def patch_oilrefin(dat_path: Path) -> None:
    import objinfo
    obj = dat.read_dat(dat_path)
    info = objinfo.industry(obj)
    tbl = obj.image_table()
    n_total = len(tbl.entries)
    # 動態量測 part 13 火炬噴口實際螢幕 Y（遊戲繪製 part 14 時原點在 y = -heights[13]）
    z_tower = info["heights"][13]
    e13 = tbl.entries[13 * 4 + 0]
    attach_y = (e13.y_offset + z_tower) + 1
    # part 14..77 = 64 格 × 4 旋轉 = sprites #56..#311
    repl = {}
    for k in range(64):
        cw, ch, xo, yo, px_bytes = render_flare_frame(k, 64, attach_y=attach_y)
        enc = pack.encode_rle(cw, ch, px_bytes)
        for r in range(4):
            repl[56 + k * 4 + r] = (cw, ch, xo, yo, enc)

    entries = []
    blobs = bytearray()
    for i, e in enumerate(tbl.entries):
        if i in repl:
            cw, ch, xo, yo, enc = repl[i]
            flags = dat.G1_HAS_TRANSPARENCY | dat.G1_IS_RLE
            entries.append(dat.G1Entry(len(blobs), cw, ch, xo, yo, flags, 0))
            blobs += enc
        else:
            start = e.offset
            end = tbl.entries[i + 1].offset if i + 1 < n_total else len(tbl.image_data)
            entries.append(dat.G1Entry(len(blobs), e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            blobs += tbl.image_data[start:end]

    new_payload = dat.replace_image_table(obj.data, tbl.offset, entries, bytes(blobs))
    dat.write_dat(dat_path, obj.flags, obj.name, new_payload, dat.ENC_RLE_SINGLE)
    chk = dat.read_dat(dat_path)
    assert chk.checksum_ok(), "OG_OILREFIN checksum 驗證失敗"
    print(f"已更新 {dat_path}：替換 64 格 × 4 旋轉（256 張）2D 紊流火炬火焰精靈，checksum OK")


def save_preview(out_path: Path) -> None:
    from PIL import Image
    pal = dat.load_palette()
    cols, rows = 16, 4
    cell_w, cell_h = 30, 90
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (34, 42, 48, 255))
    for k in range(64):
        cw, ch, xo, yo, px_bytes = render_flare_frame(k, 64)
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        pix = im.load()
        for y in range(ch):
            for x in range(cw):
                v = px_bytes[y * cw + x]
                if v:
                    r, g, b = pal[v]
                    pix[x, y] = (r, g, b, 255)
        gx, gy = (k % cols) * cell_w, (k // cols) * cell_h
        # 基準點對齊每格底部中央
        sheet.paste(im, (gx + cell_w // 2 + xo, gy + cell_h - 4 + yo), im)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"預覽輸出 → {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dat", default=str(REPO / "objects/VanillaReplacements/Industry/OILREFIN/OG_OILREFIN.dat"))
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    patch_oilrefin(Path(args.dat))
    if args.preview:
        save_preview(Path(args.preview))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
