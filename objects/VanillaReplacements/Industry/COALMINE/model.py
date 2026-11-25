"""OG_COALMINE 模型（tools/blender/static_rig.py）。部件與 vanilla COALMINE 的結構相同：
0 煤場地面（2×2）；1–4 絞車房 + 鋼構井架（天輪轉動 4 格）；5 碎石地面；6 架高煤倉；7 泥土地面；8 選煤廠。

配色原則：避免大面積使用 Company Color 1（產業隨機上色分到白色時會過曝成純白方塊）；
本體以深色風化鋼構、紅磚與暗石板屋頂為主，只在招牌飾帶與小細節使用公司色。"""
import math
import os
import random

import bpy
from mathutils import Vector


def _slate(kit):
    return kit.material("Slate Roof", (0.085, 0.085, 0.09), rough=0.65, noise=0.35)


def _dark_corr(kit):
    return kit.material("Dark Corrugated", (0.14, 0.15, 0.15), rough=0.65, metal=0.25, noise=0.45)


def _rust_steel(kit):
    return kit.material("Weathered Steel", (0.20, 0.13, 0.10), rough=0.75, metal=0.35, noise=0.5)


def _company_trim(kit):
    return kit.material("Company Color 1 Trim", (0.55, 0.18, 0.15), rough=0.65, noise=0.25)


def _seg(kit, a, b, r, mat):
    va, vb = Vector(a), Vector(b)
    d = vb - va
    if d.length < 1e-5:
        return None
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=r, depth=d.length, location=(va + vb) / 2)
    o = bpy.context.active_object
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.data.materials.clear()
    o.data.materials.append(mat)
    return o


def _coal_piles(kit, n, spread):
    rng = random.Random(7)
    for _ in range(n):
        x, y = rng.uniform(-spread, spread), rng.uniform(-spread, spread)
        kit.cylinder(rng.uniform(1.1, 2.1), rng.uniform(0.9, 1.9), (x, y, 0), kit.coal(), verts=10, r_top=0.15)


def _headframe(kit, x, y, h, wheel_angle, wh_x, wh_y, wh_h):
    """經典 A 型礦井鋼構井架：四支柱收分桁架、斜撐背腳、雙天輪（轉動動畫）與捲揚鋼索。"""
    iron = kit.dark_metal()
    trim = _company_trim(kit)
    sp0 = kit.TILE * 0.24
    sp1 = kit.TILE * 0.13
    # 四根斜收主柱
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for sx, sy in corners:
        _seg(kit, (x + sx * sp0, y + sy * sp0, 0), (x + sx * sp1, y + sy * sp1, h), 0.22, iron)
    # 橫撐與 X 型斜撐
    levels = 5
    for k in range(1, levels + 1):
        f0, f1 = (k - 1) / levels, k / levels
        s0 = sp0 + (sp1 - sp0) * f0
        s1 = sp0 + (sp1 - sp0) * f1
        z0, z1 = h * f0, h * f1
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % 4]
            _seg(kit, (x + ax * s1, y + ay * s1, z1), (x + bx * s1, y + by * s1, z1), 0.14, iron)
            _seg(kit, (x + ax * s0, y + ay * s0, z0), (x + bx * s1, y + by * s1, z1), 0.10, iron)
    # 朝向絞車房的兩支斜背撐腿
    for off in (-sp1 * 0.85, sp1 * 0.85):
        _seg(kit, (wh_x * 0.3 + off * 0.5, wh_y * 0.3 + off * 0.5, 0), (x + off * 0.6, y - off * 0.6, h * 0.92), 0.24, iron)
    # 頂部天輪平台與公司色護欄帶
    kit.box(sp1 * 2.7, sp1 * 2.7, 0.55, (x, y, h), iron)
    kit.box(sp1 * 2.8, sp1 * 2.8, 0.35, (x, y, h + 0.55), trim)
    # 雙天輪（轉動動畫）
    R = kit.TILE * 0.21
    for dy_w in (-0.55, 0.55):
        wy = y + dy_w
        wz = h + R + 0.6
        bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.22, location=(x, wy, wz),
                                         rotation=(math.radians(90), 0, 0))
        wheel = bpy.context.active_object
        wheel.data.materials.clear()
        wheel.data.materials.append(iron)
        for s in range(4):
            a = wheel_angle + s * math.pi / 4
            kit.box(2 * R, 0.16, 0.16, (x, wy, wz - 0.08), iron).rotation_euler = (0, a, 0)
        # 捲揚鋼索：從天輪連到絞車房山牆
        _seg(kit, (x, wy, wz + R * 0.7), (wh_x + 0.3 * kit.TILE, wh_y - 0.1 * kit.TILE, wh_h * 0.82), 0.07, kit.steel())
        _seg(kit, (x, wy, 0), (x, wy, wz), 0.06, kit.steel())


def make_part(kit, index):
    T = kit.TILE
    slate = _slate(kit)
    corr = _dark_corr(kit)
    rust = _rust_steel(kit)
    trim = _company_trim(kit)

    if index == 0:                                            # 2×2 煤場地面＋擋煤矮牆＋多座煤堆
        kit.ground_plate(2, 2, kit.coal(), thickness=0.03)
        _coal_piles(kit, 9, T * 0.65)
        kit.box(T * 1.4, 0.22, 1.1, (0, T * 0.78, 0), kit.wood())
        kit.box(0.22, T * 1.2, 1.1, (-T * 0.78, 0, 0), kit.wood())
    elif 1 <= index <= 4:                                     # 紅磚絞車房（暗石板屋頂）＋ A 型鋼構井架
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        wh_x, wh_y, wh_h = -T * 0.38, T * 0.36, H * 0.32
        kit.box(T * 1.06, T * 0.80, 0.6, (wh_x, wh_y, 0), kit.dark_metal())
        kit.box(T * 1.02, T * 0.76, wh_h, (wh_x, wh_y, 0), kit.brick())
        kit.gable_roof(T * 1.10, T * 0.84, H * 0.14, (wh_x, wh_y, wh_h), slate)
        # 屋脊通風氣樓與公司色簷口細條
        kit.box(T * 0.62, T * 0.18, H * 0.06, (wh_x, wh_y, wh_h + H * 0.12), corr)
        kit.gable_roof(T * 0.66, T * 0.22, H * 0.04, (wh_x, wh_y, wh_h + H * 0.18), slate)
        kit.windows(T * 1.02, T * 0.76, wh_h * 0.22, wh_h * 0.84, 1, 4, loc=(wh_x, wh_y, 0))
        kit.cylinder(0.55, H * 0.72, (wh_x - T * 0.36, wh_y + T * 0.24, 0), kit.brick(), verts=10, r_top=0.40)
        kit.cylinder(0.45, 0.5, (wh_x - T * 0.36, wh_y + T * 0.24, H * 0.72), kit.dark_metal(), verts=10)
        _headframe(kit, T * 0.44, -T * 0.42, H * 0.76, (index - 1) * math.pi / 16, wh_x, wh_y, wh_h)
    elif index == 5:
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
    elif index == 6:                                          # 架高鋼構煤倉（深色浪板＋雙漏斗＋斜輸送廊道＋底煤堆）
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        legs_h = H * 0.40
        bin_h = H * 0.38
        # 底部漏出的煤堆
        kit.cylinder(T * 0.55, 1.3, (0, 0, 0), kit.coal(), verts=12, r_top=0.2)
        # 重型鋼柱與斜撐
        xs = (-T * 0.58, 0.0, T * 0.58)
        ys = (-T * 0.46, T * 0.46)
        for dx in xs:
            for dy in ys:
                kit.box(0.55, 0.55, legs_h, (dx, dy, 0), kit.dark_metal())
                kit.box(0.85, 0.85, 0.6, (dx, dy, 0), kit.concrete())
        for dy in ys:
            _seg(kit, (-T * 0.58, dy, 0.4), (0, dy, legs_h - 0.3), 0.12, kit.dark_metal())
            _seg(kit, (T * 0.58, dy, 0.4), (0, dy, legs_h - 0.3), 0.12, kit.dark_metal())
        # 雙錐形下料漏斗
        for dx in (-T * 0.28, T * 0.28):
            kit.cylinder(T * 0.14, H * 0.16, (dx, 0, legs_h - H * 0.16), rust, verts=4, r_top=T * 0.44)
        # 深色浪板主倉體＋外露垂直加強鋼肋＋公司色飾帶
        kit.box(T * 1.32, T * 1.04, bin_h, (0, 0, legs_h), corr)
        for dx in (-T * 0.66, -T * 0.33, 0.0, T * 0.33, T * 0.66):
            kit.box(0.18, T * 1.10, bin_h, (dx, 0, legs_h), kit.dark_metal())
        kit.box(T * 1.36, T * 1.08, 0.55, (0, 0, legs_h + bin_h - 0.8), trim)
        # 頂部轉運機房（人字暗石板頂）＋走道
        kit.box(T * 1.44, T * 1.16, 0.35, (0, 0, legs_h + bin_h), kit.dark_metal())
        kit.box(T * 0.92, T * 0.68, H * 0.13, (0, 0, legs_h + bin_h + 0.35), rust)
        kit.gable_roof(T * 0.98, T * 0.74, H * 0.09, (0, 0, legs_h + bin_h + H * 0.13 + 0.35), slate)
        # 封閉式傾斜皮帶輸送廊道
        _seg(kit, (T * 0.92, -T * 0.42, 0.8), (T * 0.22, -T * 0.05, legs_h + bin_h + H * 0.08), 0.52, corr)
        _seg(kit, (T * 0.62, -T * 0.26, 0), (T * 0.62, -T * 0.26, legs_h * 0.72), 0.16, kit.dark_metal())
    elif index == 7:
        kit.ground_plate(2, 2, kit.dirt(), thickness=0.03)
    elif index == 8:                                          # 選煤廠：階梯鋼構廠房＋旋風除塵器＋紅磚三煙囪
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        # 主選煤廠房（底層紅磚＋上層深色浪板＋暗石板人字頂與氣樓）
        kit.box(T * 1.24, T * 0.96, H * 0.22, (-T * 0.22, T * 0.06, 0), kit.brick())
        kit.box(T * 1.20, T * 0.92, H * 0.32, (-T * 0.22, T * 0.06, H * 0.22), corr)
        kit.gable_roof(T * 1.28, T * 1.00, H * 0.14, (-T * 0.22, T * 0.06, H * 0.54), slate, along_x=True)
        kit.box(T * 0.84, T * 0.22, H * 0.06, (-T * 0.22, T * 0.06, H * 0.65), corr)
        kit.gable_roof(T * 0.88, T * 0.26, H * 0.05, (-T * 0.22, T * 0.06, H * 0.71), slate, along_x=True)
        kit.windows(T * 1.20, T * 0.92, H * 0.26, H * 0.50, 1, 5, loc=(-T * 0.22, T * 0.06, 0))
        kit.box(T * 1.24, T * 0.96, 0.5, (-T * 0.22, T * 0.06, H * 0.21), trim)
        # 側邊紅磚鍋爐室＋旋風除塵筒
        kit.box(T * 0.62, T * 0.64, H * 0.26, (T * 0.60, T * 0.36, 0), kit.brick())
        kit.gable_roof(T * 0.66, T * 0.68, H * 0.09, (T * 0.60, T * 0.36, H * 0.26), slate, along_x=False)
        for cy_c in (-T * 0.15, T * 0.12):
            kit.cylinder(T * 0.13, H * 0.18, (T * 0.50, cy_c - T * 0.28, H * 0.24), rust, verts=12)
            kit.cylinder(T * 0.04, H * 0.12, (T * 0.50, cy_c - T * 0.28, H * 0.12), rust, verts=12, r_top=T * 0.13)
        # 三支紅磚煙囪（配深石帽口與公司色環帶）
        for k in range(3):
            cx_s = T * (0.44 + 0.19 * k)
            cy_s = -T * 0.58
            ch = H * (0.88 - 0.06 * k)
            kit.cylinder(0.62, ch, (cx_s, cy_s, 0), kit.brick(), verts=12, r_top=0.45)
            kit.cylinder(0.50, 0.6, (cx_s, cy_s, ch), kit.dark_metal(), verts=12)
            kit.cylinder(0.54, 0.5, (cx_s, cy_s, ch * 0.82), trim, verts=12)
