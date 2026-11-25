"""OG_COALPS 模型（tools/blender/static_rig.py）。部件與 vanilla COALPS 的結構相同：
0 煤堆地面（2×2）；1 冷卻塔；2 混凝土地面（1×1）；3、4 變電設備（兩種）；5 鍋爐廠房（2×2，含地面）；
6 煙囪；7–38 冷卻塔蒸汽（32 格循環動畫）。"""
import math
import os
import random


def _h(kit):
    return kit.z(int(os.environ["PART_HEIGHT_PX"]))


def _transformer(kit, T, seed):
    rng = random.Random(seed)
    dark_st = kit.material("Dark Steel", (0.14, 0.15, 0.16), rough=0.5, metal=0.6)
    tank_m = kit.material("Transformer Steel", (0.28, 0.30, 0.32), rough=0.5, metal=0.5, noise=0.25)
    trim = kit.material("Company Color 1 Trim", (0.5, 0.5, 0.5))
    porc = kit.material("Porcelain", (0.58, 0.54, 0.46), rough=0.4)
    # 主變壓器鋼體＋散熱片＋公司色標示帶
    kit.box(T * 0.56, T * 0.38, T * 0.25, (0, 0, 0), tank_m)
    kit.box(T * 0.58, T * 0.40, T * 0.04, (0, 0, T * 0.18), trim)
    for k in range(4):
        x = (k - 1.5) * T * 0.13
        kit.box(T * 0.04, T * 0.46, T * 0.20, (x, 0, T * 0.02), dark_st)
    for k in range(3):
        x = (k - 1) * T * 0.16
        kit.cylinder(0.28, T * 0.22, (x, rng.uniform(-0.2, 0.2), T * 0.25), porc, verts=8)
        kit.cylinder(0.10, T * 0.08, (x, rng.uniform(-0.2, 0.2), T * 0.47), dark_st, verts=6)
    # 鋼構匯流排門架
    for dx in (-T * 0.38, T * 0.38):
        kit.box(0.28, 0.28, T * 0.62, (dx, T * 0.30, 0), dark_st)
    kit.box(T * 0.82, 0.22, 0.22, (0, T * 0.30, T * 0.58), dark_st)
    kit.box(T * 0.82, 0.14, 0.14, (0, T * 0.30, T * 0.42), kit.steel())


def make_part(kit, index):
    T = kit.TILE
    if index == 0:
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
        kit.cylinder(T * 0.55, 1.2, (-T * 0.2, T * 0.2, 0), kit.coal(), verts=24, r_top=T * 0.35)
    elif index == 1:
        H = _h(kit)
        prof = [(T * 0.68, 0), (T * 0.58, H * 0.3), (T * 0.47, H * 0.65), (T * 0.45, H * 0.8), (T * 0.48, H)]
        kit.lathe(prof, (0, 0, 0), kit.material("Cooling Tower", (0.42, 0.46, 0.46), noise=0.12))
        kit.lathe([(T * 0.69, 0), (T * 0.69, H * 0.04)], (0, 0, 0), kit.material("Company Color 1 Band", (0.5, 0.5, 0.5)))
    elif index == 2:
        kit.ground_plate(1, 1, kit.gravel(), thickness=0.03)
    elif index in (3, 4):
        _transformer(kit, T, index)
        if index == 4:
            kit.box(T * 0.32, T * 0.28, T * 0.18, (T * 0.25, -T * 0.25, 0), kit.material("Control Box", (0.24, 0.24, 0.23), noise=0.35))
    elif index == 5:
        H = _h(kit)
        dark_roof = kit.material("Dark Roof", (0.14, 0.15, 0.16), rough=0.85, noise=0.45)
        slate = kit.material("Slate", (0.10, 0.11, 0.12), rough=0.7, noise=0.35)
        trim = kit.material("Company Color 1 Trim", (0.5, 0.5, 0.5))
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
        # 紅磚鍋爐與汽機廠房：凹入暗屋頂＋磚女兒牆＋採光氣樓＋公司色簷口細條
        bx, by = -T * 0.10, -T * 0.16
        bw, bd, bh = T * 1.66, T * 1.22, H * 0.86
        kit.box(bw, bd, bh, (bx, by, 0), kit.brick())
        kit.windows(bw, bd, bh * 0.16, bh * 0.86, 2, 7, loc=(bx, by, 0))
        kit.box(bw * 0.94, bd * 0.92, H * 0.04, (bx, by, bh - H * 0.02), dark_roof)
        pt = T * 0.06
        ph = H * 0.09
        kit.box(bw, pt, ph, (bx, by - bd / 2 + pt / 2, bh), kit.brick())
        kit.box(bw, pt, ph, (bx, by + bd / 2 - pt / 2, bh), kit.brick())
        kit.box(pt, bd, ph, (bx - bw / 2 + pt / 2, by, bh), kit.brick())
        kit.box(pt, bd, ph, (bx + bw / 2 - pt / 2, by, bh), kit.brick())
        # 公司色細飾帶（不蓋屋頂，避免變成大面積白塊）
        kit.box(bw + 0.08, 0.08, H * 0.05, (bx, by - bd / 2 - 0.01, bh - H * 0.04), trim)
        kit.box(bw + 0.08, 0.08, H * 0.05, (bx, by + bd / 2 + 0.01, bh - H * 0.04), trim)
        kit.box(0.08, bd + 0.08, H * 0.05, (bx - bw / 2 - 0.01, by, bh - H * 0.04), trim)
        kit.box(0.08, bd + 0.08, H * 0.05, (bx + bw / 2 + 0.01, by, bh - H * 0.04), trim)
        # 屋頂採光氣樓＋排風管
        kit.box(bw * 0.72, bd * 0.30, H * 0.08, (bx, by, bh), kit.glass())
        kit.gable_roof(bw * 0.76, bd * 0.36, H * 0.09, (bx, by, bh + H * 0.08), slate, along_x=True)
        for k in range(3):
            kit.cylinder(T * 0.055, H * 0.14, (bx + (k - 1) * T * 0.35, by + bd * 0.30, bh), kit.steel(), verts=10)
    elif index == 6:
        H = _h(kit)
        for k in range(2):
            kit.cylinder(T * 0.08, H, (T * 0.6, T * (0.15 + 0.22 * k), 0), kit.concrete(), verts=12, r_top=T * 0.065)
            kit.cylinder(T * 0.082, H * 0.05, (T * 0.6, T * (0.15 + 0.22 * k), H * 0.92), kit.material("Company Color 1 Stripe", (0.6, 0.1, 0.1)), verts=12)
    else:
        # 7–38：冷卻塔頂的蒸汽，32 格循環（球團逐格上升、變大）
        frame = index - 7
        H = _h(kit)
        steam = kit.material("Steam", (0.85, 0.86, 0.88), rough=1.0)
        import bpy
        rng = random.Random(3)
        n = 14
        for k in range(n):
            phase = (k / n + frame / 32) % 1.0
            r = T * (0.25 + 0.35 * phase)
            x = rng.uniform(-0.2, 0.2) * T + phase * T * 0.3
            y = rng.uniform(-0.2, 0.2) * T
            zz = phase * H * 0.85
            bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(x, y, zz + r * 0.6), segments=12, ring_count=8)
            s = bpy.context.active_object
            s.scale = (1, 1, 0.75)
            s.data.materials.append(steam)
            bpy.ops.object.shade_smooth()
