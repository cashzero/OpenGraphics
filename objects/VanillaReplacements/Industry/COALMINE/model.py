"""OG_COALMINE 模型（tools/blender/static_rig.py）。部件與 vanilla COALMINE 的結構相同：
0 煤場地面（2×2）；1–4 絞車房 + 鋼構井架（天輪轉動 4 格）；5 碎石地面；6 架高煤倉；7 泥土地面；8 選煤廠。"""
import math

T = None


def _coal_piles(kit, n, spread):
    import random
    rng = random.Random(7)
    for _ in range(n):
        x, y = rng.uniform(-spread, spread), rng.uniform(-spread, spread)
        kit.cylinder(rng.uniform(1.0, 1.8), rng.uniform(0.8, 1.4), (x, y, 0), kit.coal(), verts=10, r_top=0.1)


def _headframe(kit, x, y, h, wheel_angle):
    steel = kit.material("Company Color 1 Steel", (0.5, 0.15, 0.1), rough=0.5, metal=0.5)
    leg = 0.45
    sp = kit.TILE * 0.22
    for dx, dy in ((-sp, -sp), (sp, -sp), (-sp, sp), (sp, sp)):
        o = kit.box(leg, leg, h, (x + dx, y + dy, 0), steel)
        o.rotation_euler = (math.radians(-dy / sp * 2.5), math.radians(dx / sp * 2.5), 0)
    for k in range(1, 5):                                   # 橫撐
        zz = h * k / 5
        kit.box(2 * sp, leg * 0.7, leg * 0.7, (x, y - sp, zz), steel)
        kit.box(2 * sp, leg * 0.7, leg * 0.7, (x, y + sp, zz), steel)
        kit.box(leg * 0.7, 2 * sp, leg * 0.7, (x - sp, y, zz), steel)
        kit.box(leg * 0.7, 2 * sp, leg * 0.7, (x + sp, y, zz), steel)
    kit.box(2 * sp + 1, 2 * sp + 1, 0.5, (x, y, h), steel)  # 頂部平台
    import bpy
    R = kit.TILE * 0.2
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.25, location=(x, y, h + R + 0.3),
                                     rotation=(math.radians(90), 0, 0))
    wheel = bpy.context.active_object
    wheel.data.materials.append(kit.dark_metal())
    for s in range(4):                                      # 輪輻（轉動的動畫靠它）
        a = wheel_angle + s * math.pi / 4
        kit.box(2 * R, 0.2, 0.2, (x, y, h + R + 0.3 - 0.1), kit.dark_metal()).rotation_euler = (0, a, 0)


def make_part(kit, index):
    T = kit.TILE
    if index == 0:
        kit.ground_plate(2, 2, kit.coal(), thickness=0.03)
        _coal_piles(kit, 7, T * 0.7)
    elif 1 <= index <= 4:
        import os
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        kit.box(T * 1.0, T * 0.75, H * 0.3, (-T * 0.4, T * 0.4, 0), kit.brick())             # 絞車房
        kit.gable_roof(T * 1.05, T * 0.8, H * 0.14, (-T * 0.4, T * 0.4, H * 0.3), kit.roof_tiles())
        kit.windows(T * 1.0, T * 0.75, H * 0.05, H * 0.27, 1, 4, loc=(-T * 0.4, T * 0.4, 0))
        _headframe(kit, T * 0.45, -T * 0.45, H * 0.78, (index - 1) * math.pi / 16)
        kit.box(T * 0.9, 0.3, 0.3, (0, 0, H * 0.55), kit.steel()).rotation_euler = (0, math.radians(-25), math.radians(-45))
    elif index == 5:
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
    elif index == 6:
        import os
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        legs_h = H * 0.42
        for dx in (-T * 0.55, 0, T * 0.55):
            for dy in (-T * 0.55, T * 0.55):
                kit.box(0.8, 0.8, legs_h, (dx, dy, 0), kit.steel())
        kit.box(T * 1.35, T * 1.35, H * 0.45, (0, 0, legs_h), kit.material("Company Color 1 Hopper", (0.3, 0.3, 0.32), noise=0.3))
        kit.cylinder(T * 0.5, H * 0.15, (0, 0, legs_h - H * 0.15), kit.dark_metal(), verts=4, r_top=T * 0.95)
        kit.box(T * 1.4, T * 1.4, 0.4, (0, 0, legs_h + H * 0.45), kit.dark_metal())
        kit.box(T * 1.1, 0.5, 0.5, (T * 0.5, 0, legs_h * 0.6), kit.steel()).rotation_euler = (0, math.radians(-30), 0)
    elif index == 7:
        kit.ground_plate(2, 2, kit.dirt(), thickness=0.03)
    elif index == 8:
        import os
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        kit.box(T * 1.3, T * 1.0, H * 0.5, (-T * 0.2, 0, 0), kit.material("Corrugated", (0.25, 0.27, 0.25), noise=0.4))
        kit.gable_roof(T * 1.35, T * 1.05, H * 0.14, (-T * 0.2, 0, H * 0.5), kit.roof_tiles(), along_x=True)
        kit.windows(T * 1.3, T * 1.0, H * 0.1, H * 0.45, 2, 5, loc=(-T * 0.2, 0, 0))
        kit.box(T * 0.6, T * 0.6, H * 0.3, (T * 0.65, T * 0.4, 0), kit.brick())
        for k in range(3):
            kit.cylinder(0.7, H * 0.88, (T * (0.55 + 0.16 * k), -T * 0.5, 0), kit.brick(), verts=12)
