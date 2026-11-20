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
    kit.box(T * 0.6, T * 0.42, T * 0.26, (0, 0, 0), kit.material("Company Color 1 Transformer", (0.3, 0.35, 0.3), noise=0.2))
    for k in range(3):
        x = (k - 1) * T * 0.18
        kit.cylinder(0.32, T * 0.2, (x, rng.uniform(-0.3, 0.3), T * 0.26), kit.material("Porcelain", (0.7, 0.65, 0.55)), verts=8)
    for dx in (-T * 0.38, T * 0.38):
        kit.box(0.3, 0.3, T * 0.6, (dx, T * 0.3, 0), kit.steel())
    kit.box(T * 0.8, 0.25, 0.25, (0, T * 0.3, T * 0.58), kit.steel())


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
        kit.ground_plate(1, 1, kit.material("Pavement", (0.48, 0.47, 0.44), noise=0.3), thickness=0.03)
    elif index in (3, 4):
        _transformer(kit, T, index)
        if index == 4:
            kit.box(T * 0.3, T * 0.3, T * 0.15, (T * 0.25, -T * 0.25, 0), kit.concrete())
    elif index == 5:
        H = _h(kit)
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
        kit.box(T * 1.7, T * 1.25, H * 0.95, (-T * 0.1, -T * 0.2, 0), kit.brick())
        kit.windows(T * 1.7, T * 1.25, H * 0.15, H * 0.9, 2, 7, loc=(-T * 0.1, -T * 0.2, 0))
        kit.box(T * 1.75, T * 1.3, H * 0.08, (-T * 0.1, -T * 0.2, H * 0.95), kit.material("Company Color 1 Roof Edge", (0.4, 0.4, 0.4)))
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
