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
    """寬大輕盈的冷卻塔白色蒸氣羽流（仿原版 COALPS 104×126 px 半透明網點霧氣）。"""
    w, h = 104, 124
    t = frame / n_frames
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # 歸一化高度 v=0（塔口底端）→ v=1（頂端消散）
    v = (h - 1 - yy) / (h - 1)
    # 隨高度微微向右上方順風飄移＋自然搖擺
    cx = w * 0.44 + 13.0 * (v ** 1.35) + 3.2 * np.sin(v * 5.0 - t * 2 * math.pi)
    # 塔口處與冷卻塔上緣等寬（半寬 ~22 px），往上蓬鬆擴散到 ~44 px
    half_w = 21.0 + 24.0 * (v ** 0.72)
    dx = (xx - cx) / half_w

    # 往上平移的多層週期紊流場（視覺上升流）
    y_adv = (h - 1 - yy) * 0.11 - t * 6.0
    x_adv = (xx - cx) * 0.10
    n1 = periodic_noise(x_adv, y_adv, t, seed=301, fx=0.95, fy=0.85, ft=1)
    n2 = periodic_noise(x_adv, y_adv, t, seed=307, fx=2.10, fy=1.90, ft=2)
    n3 = periodic_noise(x_adv * 1.4, y_adv * 1.4, t, seed=313, fx=3.60, fy=3.30, ft=2)
    turb = 0.48 * n1 + 0.34 * n2 + 0.18 * n3

    # 橢圓塔口底端包絡＋頂部自然羽化消散
    radial = np.sqrt(dx * dx + ((v - 0.12) * 0.35) ** 2)
    env = np.clip(1.0 - radial * 0.92, 0.0, 1.0)
    # 底端柔順貼合冷卻塔圓弧口
    bot_cut = np.clip((v + 0.04 * (1.0 - dx * dx)) / 0.12, 0.0, 1.0)
    top_fade = np.clip((1.0 - v) / 0.42, 0.0, 1.0) ** 0.85
    density = env * bot_cut * top_fade * (0.42 + 0.98 * turb)

    # Bayer 4×4 有序網點產生原版般的「半透明輕霧」感（外緣呈現細緻網格孔洞，不再是實心球團！）
    bayer = BAYER4[yy.astype(np.int32) & 3, xx.astype(np.int32) & 3]
    # 網點可見機率：中核濃密，中層 45-75% 透空，外緣 10-35% 輕煙點
    alpha_prob = np.clip((density - 0.14) / 0.58, 0.0, 1.0)
    # 頂端強制輕薄化，永遠不會變成厚重實心圓餅
    alpha_prob = alpha_prob * (0.94 - 0.48 * (v ** 1.2))
    visible = alpha_prob > (bayer * 0.86 + 0.08)

    # 明暗著色：上方與左上方受暖陽照亮（純白 20–21），底部與右下方帶柔和灰影（15–17）
    lit = 0.56 + 0.28 * (1.0 - np.clip(dx, -1, 1) * 0.5) + 0.26 * (v ** 0.6) + 0.28 * (n2 - 0.5)
    lit = np.clip(lit + (bayer - 0.5) * 0.12, 0.0, 1.0)
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
    # 讓 (w*0.44, h-1) 對齊塔口 (0, base_y_attach)
    x_off = x0 - int(round(w * 0.44))
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
