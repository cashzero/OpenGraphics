#!/usr/bin/env python3
"""2D 紊流蒸氣／黑煙精靈產生器（取代 COALPS 與 FACTORY 原本生硬的 3D 球體串）。

原理與原版 Locomotion 相同：以 2D 週期平滑卷積雜訊＋Bayer 4×4 有序抖動（半透明網點邊緣），
生成無縫循環 32 格的輕盈蒸氣羽流（OG_COALPS）與飄散煤煙羽流（OG_FACTORY），
並直接量測對應主體精靈（COALPS p=1 冷卻塔口／FACTORY p=3 最高煙囪口）在 4 個旋轉角的實際頂端座標，
確保所有旋轉方向皆精準對齊、不懸空、且 0% 公司色 remap。

用法：
  .venv/bin/python tools/gen/smoke_fx.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))
import dat  # noqa: E402
import objinfo  # noqa: E402
import pack  # noqa: E402

# Locomotion 調色盤灰白安全色階（全在 10..21 內，絕不觸碰公司色 remap！）
# 10..21 由深炭灰到純白：10=(11,11,11) .. 15=(103,103,103) .. 18=(167,167,167) .. 21=(239,239,239)
STEAM_RAMP = np.array([14, 15, 16, 17, 18, 19, 20, 21], dtype=np.uint8)
COAL_SMOKE_RAMP = np.array([10, 11, 12, 13, 14, 15, 16], dtype=np.uint8)

BAYER4 = np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float32) / 16.0


def periodic_noise(x: np.ndarray, y: np.ndarray, t: float, seed: int, fx: float, fy: float, ft: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros_like(x, dtype=np.float32)
    amp = 1.0
    tot = 0.0
    for _ in range(4):
        ang = rng.uniform(0, 2 * math.pi)
        kx = math.cos(ang) * fx
        ky = math.sin(ang) * fy
        ph = rng.uniform(0, 2 * math.pi)
        out += amp * np.sin(x * kx + y * ky + t * 2 * math.pi * ft + ph)
        tot += amp
        fx *= 1.85
        fy *= 1.85
        ft *= 2
        amp *= 0.55
    return (out / tot + 1.0) * 0.5


def render_cooling_steam(frame: int, n_frames: int = 32, base_y_attach: int = 10) -> tuple[int, int, int, int, bytes]:
    """寬闊蓬鬆、橫向翻湧飄散的真實冷卻塔白蒸氣雲團（122×118 px，帶多層有機雲隙與明暗立體感）。"""
    w, h = 122, 118
    t = frame / n_frames
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = (h - 1 - yy) / (h - 1)
    # 由塔口出發、隨高度自然往右上方橫向大跨度飄散
    cx = w * 0.42 + 16.0 * (v ** 1.15) + 4.5 * np.sin(v * 4.2 - t * 2 * math.pi)
    # 寬闊翻湧展開：塔口半寬 25px → 中上段張開至 52px（真實寬雲團而非細直柱！）
    half_w = 24.0 + 30.0 * (v ** 0.58)
    dx = (xx - cx) / half_w

    # 多尺度翻騰上升流雜訊（大雲團 + 中雲簇 + 細緻撕裂霧絲）
    y_adv = (h - 1 - yy) * 0.09 - t * 5.0
    x_adv = (xx - cx) * 0.08
    n_big = periodic_noise(x_adv, y_adv, t, seed=301, fx=0.75, fy=0.70, ft=1)
    n_mid = periodic_noise(x_adv, y_adv, t, seed=307, fx=1.75, fy=1.60, ft=2)
    n_fin = periodic_noise(x_adv * 1.5, y_adv * 1.5, t, seed=313, fx=3.40, fy=3.10, ft=2)
    # 讓雲隙更自然（有機破洞與捲曲白絲）
    puffs = 0.52 * n_big + 0.32 * n_mid + 0.16 * n_fin

    # 寬大包絡（不截斷兩側，讓左右兩側翻湧出自然白雲簇）
    env = np.clip(1.0 - (dx * dx * 0.88), 0.0, 1.0)
    bot_cut = np.clip((v + 0.06 * (1.0 - dx * dx)) / 0.11, 0.0, 1.0)
    top_fade = np.clip((1.0 - v) / 0.34, 0.0, 1.0) ** 0.78
    # 提高雜訊對比，拉出清晰的雲團塊與雲間縫隙（避免均勻點陣網格感！）
    cloud_shape = np.clip((puffs - 0.24) / 0.54, 0.0, 1.0)
    density = env * bot_cut * top_fade * (0.28 + 1.08 * cloud_shape)

    bayer = BAYER4[yy.astype(np.int32) & 3, xx.astype(np.int32) & 3]
    # 核心與亮雲簇保持實白棉絮感，邊緣與雲隙柔順抖動透空
    alpha_prob = np.clip((density - 0.16) / 0.44, 0.0, 1.0)
    alpha_prob = alpha_prob * (0.98 - 0.32 * (v ** 1.35))
    visible = alpha_prob > (bayer * 0.74 + 0.10)

    # 豐富立體受光：雲團左上方與頂部純白高光（20–21）、雲腹與底緣帶柔和冷灰陰影（15–18）
    lit = 0.44 + 0.34 * cloud_shape + 0.22 * (1.0 - np.clip(dx, -1, 1) * 0.5) + 0.18 * (v ** 0.55) + 0.20 * (n_mid - 0.5)
    lit = np.clip(lit + (bayer - 0.5) * 0.10, 0.0, 1.0)
    idx = np.clip((lit * (len(STEAM_RAMP) - 1) + 0.5).astype(np.int32), 0, len(STEAM_RAMP) - 1)

    px = np.zeros((h, w), dtype=np.uint8)
    px[visible] = STEAM_RAMP[idx[visible]]

    nz_y, nz_x = np.nonzero(px)
    if len(nz_x) == 0:
        return 1, 1, 0, 0, bytes(1)
    x0, x1 = int(nz_x.min()), int(nz_x.max()) + 1
    y0, y1 = int(nz_y.min()), int(nz_y.max()) + 1
    cropped = px[y0:y1, x0:x1]
    cw, ch = x1 - x0, y1 - y0
    x_off = x0 - int(round(w * 0.42))
    y_off = y0 - (h - 1) + base_y_attach
    return cw, ch, x_off, y_off, cropped.tobytes()


def render_factory_smoke(frame: int, n_frames: int = 32, attach_x: int = 0, attach_y: int = 0) -> tuple[int, int, int, int, bytes]:
    """輕盈飄散的工廠深灰煤煙羽流（對齊原版 FACTORY 24×96 px 細長輕煙）。"""
    w, h = 44, 96
    t = frame / n_frames
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    v = (h - 1 - yy) / (h - 1)
    # 由煙囪口細出、往右上飄散並隨風微晃
    cx = w * 0.34 + 12.0 * (v ** 1.25) + 2.2 * np.sin(v * 6.0 - t * 2 * math.pi)
    half_w = 3.2 + 11.5 * (v ** 0.85)
    dx = (xx - cx) / half_w

    y_adv = (h - 1 - yy) * 0.16 - t * 6.0
    x_adv = (xx - cx) * 0.16
    n1 = periodic_noise(x_adv, y_adv, t, seed=409, fx=1.1, fy=0.95, ft=1)
    n2 = periodic_noise(x_adv, y_adv, t, seed=419, fx=2.4, fy=2.2, ft=2)
    turb = 0.55 * n1 + 0.45 * n2

    env = np.clip(1.0 - np.abs(dx) * 0.95, 0.0, 1.0)
    bot_cut = np.clip(v / 0.06, 0.0, 1.0)
    top_fade = np.clip((1.0 - v) / 0.45, 0.0, 1.0)
    density = env * bot_cut * top_fade * (0.45 + 0.95 * turb)

    bayer = BAYER4[yy.astype(np.int32) & 3, xx.astype(np.int32) & 3]
    alpha_prob = np.clip((density - 0.15) / 0.55, 0.0, 1.0) * (0.90 - 0.55 * (v ** 1.1))
    visible = alpha_prob > (bayer * 0.88 + 0.07)

    # 煙囪口較深炭灰（10–12），往上漸亮稀薄成中淺灰（13–16）
    lit = 0.18 + 0.62 * (v ** 0.85) + 0.22 * (n2 - 0.5)
    lit = np.clip(lit + (bayer - 0.5) * 0.14, 0.0, 1.0)
    idx = np.clip((lit * (len(COAL_SMOKE_RAMP) - 1) + 0.5).astype(np.int32), 0, len(COAL_SMOKE_RAMP) - 1)

    px = np.zeros((h, w), dtype=np.uint8)
    px[visible] = COAL_SMOKE_RAMP[idx[visible]]

    nz_y, nz_x = np.nonzero(px)
    if len(nz_x) == 0:
        return 1, 1, 0, 0, bytes(1)
    x0, x1 = int(nz_x.min()), int(nz_x.max()) + 1
    y0, y1 = int(nz_y.min()), int(nz_y.max()) + 1
    cropped = px[y0:y1, x0:x1]
    cw, ch = x1 - x0, y1 - y0
    x_off = x0 - int(round(w * 0.34)) + attach_x
    y_off = y0 - (h - 1) + attach_y
    return cw, ch, x_off, y_off, cropped.tobytes()


def find_sprite_top_anchor(tbl: dat.ImageTable, sprite_idx: int) -> tuple[int, int]:
    """量測某精靈最頂端（前 4 列非透明像素）的螢幕 X 中點與 Y 座標。"""
    w, h, xo, yo, _px, al = dat.decode_sprite(tbl, sprite_idx)
    al_arr = np.frombuffer(al, dtype=np.uint8).reshape(h, w)
    ys, xs = np.nonzero(al_arr)
    if len(xs) == 0:
        return 0, 0
    y_min = int(ys.min())
    top_xs = xs[ys <= y_min + 3]
    cx = int(round(float(top_xs.mean())))
    return xo + cx, yo + y_min


def patch_sprites(dat_path: Path, repl: dict[int, tuple[int, int, int, int, bytes]], label: str) -> None:
    obj = dat.read_dat(dat_path)
    tbl = obj.image_table()
    n_total = len(tbl.entries)
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
    assert chk.checksum_ok(), f"{dat_path.name} checksum 驗證失敗"
    print(f"已更新 {dat_path}：{label}，checksum OK")


def patch_coalps(dat_path: Path) -> None:
    obj = dat.read_dat(dat_path)
    info = objinfo.industry(obj)
    tbl = obj.image_table()
    z_tower = info["heights"][1]  # 90
    # 量測 p=1 冷卻塔頂端實際螢幕 Y（約 -102..-112），讓蒸氣底端深入塔口內 10px
    _tx, ty_top = find_sprite_top_anchor(tbl, 1 * 4 + 0)
    # 遊戲繪製 part 7 時原點在 y = -z_tower；塔頂實際在 ty_top，故相對偏移 = (ty_top + z_tower) + 12
    base_y_attach = (ty_top + z_tower) + 12
    repl = {}
    for k in range(32):
        cw, ch, xo, yo, px_bytes = render_cooling_steam(k, 32, base_y_attach=base_y_attach)
        enc = pack.encode_rle(cw, ch, px_bytes)
        for r in range(4):
            repl[(7 + k) * 4 + r] = (cw, ch, xo, yo, enc)
    patch_sprites(dat_path, repl, f"替換 32×4 格 2D 半透明冷卻塔蒸氣（attach_y={base_y_attach}）")


def patch_factory(dat_path: Path) -> None:
    obj = dat.read_dat(dat_path)
    info = objinfo.industry(obj)
    tbl = obj.image_table()
    z_main = info["heights"][3]  # 107
    # 逐旋轉角量測 part 3 最高煙囪口實際螢幕 (x, y)
    anchors = []
    for r in range(4):
        sx, sy = find_sprite_top_anchor(tbl, 3 * 4 + r)
        # 遊戲繪製 part 4..35 時原點在 (0, -z_main)，故相對偏移 = (sx, sy + z_main + 2)
        anchors.append((sx, sy + z_main + 2))
    repl = {}
    for k in range(32):
        for r in range(4):
            ax, ay = anchors[r]
            cw, ch, xo, yo, px_bytes = render_factory_smoke(k, 32, attach_x=ax, attach_y=ay)
            enc = pack.encode_rle(cw, ch, px_bytes)
            repl[(4 + k) * 4 + r] = (cw, ch, xo, yo, enc)
    patch_sprites(dat_path, repl, f"替換 32×4 格 2D 飄散煤煙（anchors={anchors}）")


def main() -> int:
    patch_coalps(REPO / "objects/VanillaReplacements/Industry/COALPS/OG_COALPS.dat")
    patch_factory(REPO / "objects/VanillaReplacements/Industry/FACTORY/OG_FACTORY.dat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
