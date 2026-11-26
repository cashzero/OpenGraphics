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
    dark_st = kit.material("Dark Steel", (0.15, 0.16, 0.16), rough=0.48, metal=0.22)
    tank_m = kit.material("Steel Transformer", (0.30, 0.31, 0.32), rough=0.46, metal=0.22, noise=0.25)
    rust_m = kit.material("Rust Steel", (0.28, 0.16, 0.09), rough=0.65, metal=0.15, noise=0.35)
    porc = kit.material("Porcelain", (0.58, 0.54, 0.46), rough=0.38)
    # 混凝土設備基座＋雙主變壓器散熱本體
    kit.box(T * 0.86, T * 0.82, 0.45, (0, 0, 0), kit.concrete())
    for sy in (-T * 0.16, T * 0.18):
        kit.box(T * 0.66, T * 0.26, T * 0.30, (0, sy, 0.45), tank_m)
        kit.box(T * 0.68, T * 0.28, 0.25, (0, sy, 0.45 + T * 0.28), dark_st)
        for k in range(5):
            x = (k - 2.0) * T * 0.13
            kit.box(T * 0.035, T * 0.34, T * 0.24, (x, sy, 0.55), dark_st)
        for k in range(3):
            x = (k - 1) * T * 0.19
            kit.cylinder(0.28, T * 0.28, (x, sy + rng.uniform(-0.08, 0.08), 0.45 + T * 0.30), porc, verts=8, r_top=0.18)
            kit.cylinder(0.12, T * 0.10, (x, sy, 0.45 + T * 0.58), dark_st, verts=6)
    # 油枕圓筒
    kit.cylinder(0.32, T * 0.48, (-T * 0.22, -T * 0.28, 0.45 + T * 0.34), rust_m, verts=10)
    # 高壓鋼構匯流排雙門架＋絕緣子橫梁
    for gy in (-T * 0.34, T * 0.34):
        for dx in (-T * 0.38, 0.0, T * 0.38):
            kit.box(0.26, 0.26, T * 0.82, (dx, gy, 0.45), dark_st)
        kit.box(T * 0.84, 0.20, 0.22, (0, gy, 0.45 + T * 0.78), dark_st)
        kit.box(T * 0.84, 0.14, 0.14, (0, gy, 0.45 + T * 0.58), kit.steel())
    for dx in (-T * 0.24, 0.0, T * 0.24):
        kit.box(0.10, T * 0.70, 0.10, (dx, 0, 0.45 + T * 0.78), kit.steel())


def make_part(kit, index):
    T = kit.TILE
    if index == 0:
        kit.ground_plate(2, 2, kit.material("Concrete Ground", (0.28, 0.30, 0.30), noise=0.35, ground=True), thickness=0.03)
        kit.cylinder(T * 0.62, 1.8, (-T * 0.18, T * 0.18, 0), kit.coal(), verts=24, r_top=T * 0.32)
        kit.cylinder(T * 0.42, 1.3, (T * 0.42, -T * 0.32, 0), kit.coal(), verts=18, r_top=T * 0.18)
    elif index == 1:
        H = _h(kit)
        # 加寬雙曲線冷卻塔：底部 18 根進氣支柱環＋寬大雙曲線風化混凝土殼＋頂部深色內環（無公司色紅環）
        conc = kit.material("Cooling Concrete", (0.39, 0.37, 0.33), noise=0.35)
        dark = kit.material("Dark Concrete", (0.12, 0.12, 0.12), noise=0.35)
        for k in range(18):
            a0 = k * 2.0 * math.pi / 18
            a1 = (k + 0.5) * 2.0 * math.pi / 18
            r0 = T * 0.80
            r1 = T * 0.76
            kit.box(0.32, 0.32, H * 0.11, (r0 * math.cos(a0), r0 * math.sin(a0), 0), conc)
            kit.box(0.26, 0.26, H * 0.11, (r1 * math.cos(a1), r1 * math.sin(a1), 0), dark)
        prof = [
            (T * 0.80, H * 0.08),
            (T * 0.68, H * 0.30),
            (T * 0.55, H * 0.62),
            (T * 0.51, H * 0.82),
            (T * 0.56, H),
        ]
        kit.lathe(prof, (0, 0, 0), conc, segments=32)
        kit.lathe([(T * 0.53, H * 0.94), (T * 0.53, H)], (0, 0, 0), dark, segments=28)
        kit.lathe([(T * 0.81, H * 0.08), (T * 0.81, H * 0.11)], (0, 0, 0), dark, segments=32)
    elif index == 2:
        kit.ground_plate(1, 1, kit.material("Concrete Ground", (0.28, 0.30, 0.30), noise=0.35, ground=True), thickness=0.03)
    elif index in (3, 4):
        _transformer(kit, T, index)
        if index == 4:
            kit.box(T * 0.36, T * 0.30, T * 0.26, (T * 0.24, -T * 0.26, 0.45), kit.material("Stone Control", (0.28, 0.28, 0.26), noise=0.35))
    elif index == 5:
        H = _h(kit)
        dark_roof = kit.material("Dark Roof", (0.14, 0.15, 0.16), rough=0.85, noise=0.45)
        slate = kit.material("Slate", (0.10, 0.11, 0.12), rough=0.7, noise=0.35)
        cornice = kit.material("Stone Cornice", (0.46, 0.44, 0.39), rough=0.75, noise=0.30)
        kit.ground_plate(2, 2, kit.material("Concrete Ground", (0.28, 0.30, 0.30), noise=0.35, ground=True), thickness=0.03)
        # 滿格歐式火力電廠渦輪與鍋爐大廳（Battersea 風格：石砌基座＋高聳直條窗＋雙採光氣樓＋磚女兒牆）
        bx, by = 0.0, -T * 0.06
        bw, bd, bh = T * 1.82, T * 1.50, H * 0.92
        kit.box(bw + 0.14, bd + 0.14, H * 0.16, (bx, by, 0), cornice)
        kit.box(bw, bd, bh, (bx, by, 0), kit.brick())
        kit.windows(bw, bd, bh * 0.18, bh * 0.86, 2, 8, loc=(bx, by, 0))
        kit.box(bw * 0.94, bd * 0.92, H * 0.04, (bx, by, bh - H * 0.02), dark_roof)
        pt = T * 0.065
        ph = H * 0.09
        kit.box(bw, pt, ph, (bx, by - bd / 2 + pt / 2, bh), kit.brick())
        kit.box(bw, pt, ph, (bx, by + bd / 2 - pt / 2, bh), kit.brick())
        kit.box(pt, bd, ph, (bx - bw / 2 + pt / 2, by, bh), kit.brick())
        kit.box(pt, bd, ph, (bx + bw / 2 - pt / 2, by, bh), kit.brick())
        kit.box(bw + 0.14, 0.14, H * 0.06, (bx, by - bd / 2 - 0.02, bh - H * 0.04), cornice)
        kit.box(bw + 0.14, 0.14, H * 0.06, (bx, by + bd / 2 + 0.02, bh - H * 0.04), cornice)
        kit.box(0.14, bd + 0.14, H * 0.06, (bx - bw / 2 - 0.02, by, bh - H * 0.04), cornice)
        kit.box(0.14, bd + 0.14, H * 0.06, (bx + bw / 2 + 0.02, by, bh - H * 0.04), cornice)
        # 雙排屋頂採光氣樓＋排風管
        for dy_m in (-bd * 0.22, bd * 0.22):
            kit.box(bw * 0.74, bd * 0.22, H * 0.08, (bx, by + dy_m, bh), kit.glass())
            kit.gable_roof(bw * 0.78, bd * 0.26, H * 0.08, (bx, by + dy_m, bh + H * 0.08), slate, along_x=True)
    elif index == 6:
        H = _h(kit)
        conc = kit.material("Stack Concrete", (0.44, 0.42, 0.37), noise=0.35)
        dark = kit.material("Dark Steel", (0.14, 0.14, 0.14), rough=0.5, metal=0.22)
        for k in range(2):
            sx, sy = T * 0.48, T * (-0.18 + 0.46 * k)
            kit.cylinder(T * 0.18, H, (sx, sy, 0), conc, verts=18, r_top=T * 0.13)
            kit.cylinder(T * 0.142, H * 0.045, (sx, sy, H * 0.94), dark, verts=18)
            kit.cylinder(T * 0.155, H * 0.028, (sx, sy, H * 0.72), dark, verts=18)
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
