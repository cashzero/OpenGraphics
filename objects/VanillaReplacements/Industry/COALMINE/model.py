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
    return kit.material("Iron Trim", (0.24, 0.16, 0.12), rough=0.62, metal=0.20, noise=0.35)


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
    """厚重寫實 A 型煤礦鋼構井架：粗壯四支柱桁架、雙斜撐背腳、巨型雙天輪（轉動動畫）與捲揚鋼索。"""
    iron = kit.dark_metal()
    steel = kit.steel()
    trim = _company_trim(kit)
    sp0 = kit.TILE * 0.30
    sp1 = kit.TILE * 0.16
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for sx, sy in corners:
        _seg(kit, (x + sx * sp0, y + sy * sp0, 0), (x + sx * sp1, y + sy * sp1, h), 0.32, iron)
    levels = 5
    for k in range(1, levels + 1):
        f0, f1 = (k - 1) / levels, k / levels
        s0 = sp0 + (sp1 - sp0) * f0
        s1 = sp0 + (sp1 - sp0) * f1
        z0, z1 = h * f0, h * f1
        for i in range(4):
            ax, ay = corners[i]
            bx, by = corners[(i + 1) % 4]
            _seg(kit, (x + ax * s1, y + ay * s1, z1), (x + bx * s1, y + by * s1, z1), 0.20, steel)
            _seg(kit, (x + ax * s0, y + ay * s0, z0), (x + bx * s1, y + by * s1, z1), 0.14, iron)
    for off in (-sp1 * 0.90, sp1 * 0.90):
        _seg(kit, (wh_x * 0.25 + off * 0.5, wh_y * 0.25 + off * 0.5, 0), (x + off * 0.65, y - off * 0.65, h * 0.94), 0.34, iron)
    kit.box(sp1 * 3.0, sp1 * 3.0, 0.75, (x, y, h), iron)
    kit.box(sp1 * 3.1, sp1 * 3.1, 0.45, (x, y, h + 0.75), trim)
    R = kit.TILE * 0.26
    for dy_w in (-0.65, 0.65):
        wy = y + dy_w
        wz = h + R + 0.8
        bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=0.28, location=(x, wy, wz),
                                         rotation=(math.radians(90), 0, 0))
        wheel = bpy.context.active_object
        wheel.data.materials.clear()
        wheel.data.materials.append(steel)
        for s in range(4):
            a = wheel_angle + s * math.pi / 4
            kit.box(2 * R, 0.20, 0.20, (x, wy, wz - 0.10), iron).rotation_euler = (0, a, 0)
        _seg(kit, (x, wy, wz + R * 0.7), (wh_x + 0.35 * kit.TILE, wh_y - 0.1 * kit.TILE, wh_h * 0.85), 0.10, steel)
        _seg(kit, (x, wy, 0), (x, wy, wz), 0.08, steel)


def make_part(kit, index):
    T = kit.TILE
    slate = _slate(kit)
    corr = _dark_corr(kit)
    rust = _rust_steel(kit)
    trim = _company_trim(kit)

    if index == 0:                                            # 2×2 煤場地面＋擋煤矮牆＋多座煤堆
        kit.ground_plate(2, 2, kit.coal(), thickness=0.03)
        _coal_piles(kit, 11, T * 0.68)
        kit.box(T * 1.48, 0.26, 1.3, (0, T * 0.80, 0), kit.wood())
        kit.box(0.26, T * 1.28, 1.3, (-T * 0.80, 0, 0), kit.wood())
    elif 1 <= index <= 4:                                     # 2×2 厚實紅磚捲揚機房＋粗壯 A 型鋼井架＋井口棚
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        wh_x, wh_y, wh_h = -T * 0.34, T * 0.34, H * 0.40
        kit.box(T * 1.24, T * 0.94, 0.9, (wh_x, wh_y, 0), kit.concrete())
        kit.box(T * 1.20, T * 0.90, wh_h, (wh_x, wh_y, 0), kit.brick())
        kit.gable_roof(T * 1.28, T * 0.98, H * 0.16, (wh_x, wh_y, wh_h), slate)
        kit.box(T * 0.76, T * 0.24, H * 0.07, (wh_x, wh_y, wh_h + H * 0.13), corr)
        kit.gable_roof(T * 0.80, T * 0.28, H * 0.05, (wh_x, wh_y, wh_h + H * 0.20), slate)
        kit.windows(T * 1.20, T * 0.90, wh_h * 0.20, wh_h * 0.86, 2, 4, loc=(wh_x, wh_y, 0))
        kit.cylinder(0.70, H * 0.82, (wh_x - T * 0.44, wh_y + T * 0.28, 0), kit.brick(), verts=12, r_top=0.50)
        kit.cylinder(0.56, 0.7, (wh_x - T * 0.44, wh_y + T * 0.28, H * 0.82), kit.dark_metal(), verts=12)
        # 井口底座卸煤棚與煤堆
        kit.box(T * 0.78, T * 0.78, H * 0.14, (T * 0.42, -T * 0.40, 0), corr)
        _headframe(kit, T * 0.42, -T * 0.40, H * 0.78, (index - 1) * math.pi / 16, wh_x, wh_y, wh_h)
    elif index == 5:
        kit.ground_plate(2, 2, kit.gravel(), thickness=0.03)
    elif index == 6:                                          # 2×2 滿格巨型重鋼裝車大煤倉（滿溢黑煤＋密集桁架腳＋雙漏斗＋斜輸送廊道）
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        legs_h = H * 0.36
        bin_h = H * 0.44
        # 底部漏出的煤堆與混凝土地梁
        kit.cylinder(T * 0.65, 1.6, (0, 0, 0), kit.coal(), verts=14, r_top=0.25)
        # 滿格重型六柱鋼構支撐與 X 斜撐
        xs = (-T * 0.74, 0.0, T * 0.74)
        ys = (-T * 0.62, T * 0.62)
        for dx in xs:
            for dy in ys:
                kit.box(0.72, 0.72, legs_h, (dx, dy, 0), kit.dark_metal())
                kit.box(1.05, 1.05, 0.9, (dx, dy, 0), kit.concrete())
        for dy in ys:
            _seg(kit, (-T * 0.74, dy, 0.6), (0, dy, legs_h - 0.4), 0.18, kit.dark_metal())
            _seg(kit, (T * 0.74, dy, 0.6), (0, dy, legs_h - 0.4), 0.18, kit.dark_metal())
            _seg(kit, (-T * 0.74, dy, legs_h - 0.4), (0, dy, 0.6), 0.14, kit.steel())
            _seg(kit, (T * 0.74, dy, legs_h - 0.4), (0, dy, 0.6), 0.14, kit.steel())
        for dx in (-T * 0.74, T * 0.74):
            _seg(kit, (dx, -T * 0.62, 0.6), (dx, T * 0.62, legs_h - 0.4), 0.16, kit.dark_metal())
            _seg(kit, (dx, T * 0.62, 0.6), (dx, -T * 0.62, legs_h - 0.4), 0.16, kit.dark_metal())
        # 雙巨型錐形下料漏斗
        for dx in (-T * 0.38, T * 0.38):
            kit.cylinder(T * 0.18, H * 0.18, (dx, 0, legs_h - H * 0.16), rust, verts=4, r_top=T * 0.56)
        # 滿格巨型鉚接鋼板主煤斗＋密集垂直鋼肋＋頂部滿溢黑煤山＋四周檢修走道
        kit.box(T * 1.66, T * 1.38, bin_h, (0, 0, legs_h), kit.steel())
        for dx in (-T * 0.82, -T * 0.41, 0.0, T * 0.41, T * 0.82):
            kit.box(0.24, T * 1.44, bin_h, (dx, 0, legs_h), kit.dark_metal())
        for dy in (-T * 0.68, 0.0, T * 0.68):
            kit.box(T * 1.72, 0.24, bin_h, (0, dy, legs_h), kit.dark_metal())
        for zf in (0.28, 0.62, 0.94):
            kit.box(T * 1.74, T * 1.46, 0.45, (0, 0, legs_h + bin_h * zf), kit.dark_metal())
        # 頂部敞口滿溢黑煤堆＋一側上料轉運小機房＋粗封閉式傾斜皮帶輸送廊道
        kit.cylinder(T * 0.66, H * 0.12, (-T * 0.10, 0, legs_h + bin_h - 0.5), kit.coal(), verts=14, r_top=T * 0.24)
        kit.box(T * 0.72, T * 0.62, H * 0.14, (T * 0.38, T * 0.18, legs_h + bin_h), corr)
        kit.gable_roof(T * 0.78, T * 0.68, H * 0.08, (T * 0.38, T * 0.18, legs_h + bin_h + H * 0.14), slate)
        _seg(kit, (T * 0.94, -T * 0.52, 1.0), (T * 0.34, T * 0.08, legs_h + bin_h + H * 0.08), 0.72, corr)
        _seg(kit, (T * 0.66, -T * 0.26, 0), (T * 0.66, -T * 0.26, legs_h + bin_h * 0.4), 0.22, kit.dark_metal())
    elif index == 7:
        kit.ground_plate(2, 2, kit.dirt(), thickness=0.03)
    elif index == 8:                                          # 2×2 滿格大型多層洗選煤廠＋濃縮槽＋三紅磚煙囪
        H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
        # 滿格主選煤廠房（底層紅磚＋上層重鋼浪板＋寬大石板人字頂與貫穿氣樓）
        kit.box(T * 1.54, T * 1.18, H * 0.24, (-T * 0.14, T * 0.12, 0), kit.brick())
        kit.box(T * 1.50, T * 1.14, H * 0.36, (-T * 0.14, T * 0.12, H * 0.24), kit.steel())
        kit.gable_roof(T * 1.58, T * 1.22, H * 0.15, (-T * 0.14, T * 0.12, H * 0.60), slate, along_x=True)
        kit.box(T * 1.06, T * 0.28, H * 0.07, (-T * 0.14, T * 0.12, H * 0.72), corr)
        kit.gable_roof(T * 1.10, T * 0.32, H * 0.05, (-T * 0.14, T * 0.12, H * 0.79), slate, along_x=True)
        kit.windows(T * 1.50, T * 1.14, H * 0.28, H * 0.56, 2, 6, loc=(-T * 0.14, T * 0.12, 0))
        kit.box(T * 1.54, T * 1.18, 0.6, (-T * 0.14, T * 0.12, H * 0.23), trim)
        # 前方煤泥濃縮鋼槽＋紅磚鍋爐室＋粗傾斜輸送廊道
        kit.cylinder(T * 0.34, H * 0.22, (-T * 0.46, -T * 0.60, 0), rust, verts=18)
        kit.box(T * 0.70, T * 0.66, H * 0.28, (T * 0.56, T * 0.34, 0), kit.brick())
        kit.gable_roof(T * 0.74, T * 0.70, H * 0.10, (T * 0.56, T * 0.34, H * 0.28), slate, along_x=False)
        _seg(kit, (T * 0.82, -T * 0.68, 1.2), (T * 0.12, -T * 0.14, H * 0.48), 0.56, corr)
        # 雙座粗壯紅磚煙囪（配深石帽口與鋼環）
        for k in range(2):
            cx_s = T * (0.48 + 0.28 * k)
            cy_s = -T * 0.56
            ch = H * (0.94 - 0.08 * k)
            kit.cylinder(0.76, ch, (cx_s, cy_s, 0), kit.brick(), verts=14, r_top=0.52)
            kit.cylinder(0.58, 0.7, (cx_s, cy_s, ch), kit.dark_metal(), verts=14)
            kit.cylinder(0.64, 0.55, (cx_s, cy_s, ch * 0.80), trim, verts=14)
