"""靜態物件建模工具組（給 tools/blender/static_rig.py 的模型腳本使用）。

單位換算（與上游 Loco Graphics Helper 的相機相同：正交、俯仰 60.718°、方位 45°、84 px 對應 ortho_scale 19）：
- 1 格（tile）= TILE = 10.236 Blender 單位（正好畫成 64 px 寬的菱形）
- 遊戲中的高度 1 px（world z 1）= 1 / PX_PER_Z Blender 單位
材質名稱含 "Company Color 1"／"Company Color 2" 的部分會被當成 primary／secondary 公司色（remap）。
"""
import math

import bpy

PX_PER_UNIT = 84 / 19                   # 影像平面上每 Blender 單位的像素數
ELEVATION = math.radians(90 - 60.718)   # 相機仰角
PX_PER_Z = PX_PER_UNIT * math.cos(ELEVATION)
TILE = 64 / (math.sqrt(2) * PX_PER_UNIT)


def z(px: float) -> float:
    """遊戲高度（px）→ Blender 單位。"""
    return px / PX_PER_Z


_materials = {}


def material(name, rgb, rough=0.8, metal=0.0, noise=0.0):
    """建立（或取用）材質。noise > 0 時加上明暗雜訊，讓大面積不會太平板。"""
    key = (name, rgb, rough, metal, noise)
    if key in _materials:
        return _materials[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if noise > 0:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 6.0
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = noise
        mix.inputs["Color1"].default_value = (*rgb, 1)
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.6, 0.6, 0.6, 1)
        ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Color2"])
        nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    _materials[key] = m
    return m


# 常用材質（線性色值；AgX + 上游燈光會讓顏色變亮變淡，所以地面類顏色要給得很深）
def brick():
    return material("Brick", (0.42, 0.16, 0.10), noise=0.5)


def plaster():
    return material("Plaster", (0.78, 0.74, 0.62), noise=0.25)


def concrete():
    return material("Concrete", (0.55, 0.55, 0.52), noise=0.35)


def dark_metal():
    return material("Dark Metal", (0.12, 0.13, 0.14), rough=0.5, metal=0.6)


def steel():
    return material("Steel", (0.35, 0.37, 0.40), rough=0.45, metal=0.7)


def glass():
    return material("Window", (0.05, 0.08, 0.12), rough=0.2)


def roof_tiles():
    return material("Company Color 1 Roof", (0.6, 0.2, 0.2), noise=0.3)


def wood():
    return material("Wood", (0.32, 0.20, 0.10), noise=0.4)


def grass():
    return material("Grass", (0.035, 0.085, 0.015), noise=0.6)


def gravel():
    return material("Gravel", (0.09, 0.09, 0.085), noise=0.7)


def coal():
    return material("Coal", (0.05, 0.05, 0.05), rough=0.6, noise=0.6)


def dirt():
    return material("Dirt", (0.09, 0.055, 0.03), noise=0.7)


def _assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def box(sx, sy, sz, loc=(0, 0, 0), mat=None, rot=0.0):
    """以底面中心為基準的長方體。sx, sy, sz 為 Blender 單位；loc 為底面中心。"""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(loc[0], loc[1], loc[2] + sz / 2))
    o = bpy.context.active_object
    o.scale = (sx, sy, sz)
    o.rotation_euler[2] = rot
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _assign(o, mat or concrete())


def cylinder(r, h, loc=(0, 0, 0), mat=None, verts=16, r_top=None):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=(r if r_top is None else r_top), depth=h,
                                    location=(loc[0], loc[1], loc[2] + h / 2))
    return _assign(bpy.context.active_object, mat or concrete())


def gable_roof(sx, sy, h, loc=(0, 0, 0), mat=None, along_x=True):
    """山形屋頂：底面 sx × sy、屋脊高 h，屋脊沿 x（或 y）方向。"""
    hx, hy = sx / 2, sy / 2
    x0, y0, z0 = loc
    if along_x:
        verts = [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0), (-hx, 0, h), (hx, 0, h)]
        faces = [(0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
    else:
        verts = [(-hx, -hy, 0), (hx, -hy, 0), (hx, hy, 0), (-hx, hy, 0), (0, -hy, h), (0, hy, h)]
        faces = [(0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2), (0, 3, 2, 1)]
    mesh = bpy.data.meshes.new("roof")
    mesh.from_pydata([(x + x0, y + y0, zz + z0) for x, y, zz in verts], [], faces)
    o = bpy.data.objects.new("roof", mesh)
    bpy.context.collection.objects.link(o)
    return _assign(o, mat or roof_tiles())


def lathe(profile, loc=(0, 0, 0), mat=None, segments=32):
    """以 (半徑, 高度) 剖面旋轉成形（例如冷卻塔）。"""
    verts, faces = [], []
    n = len(profile)
    for s in range(segments):
        a = 2 * math.pi * s / segments
        for r, hz in profile:
            verts.append((loc[0] + r * math.cos(a), loc[1] + r * math.sin(a), loc[2] + hz))
    for s in range(segments):
        s2 = (s + 1) % segments
        for k in range(n - 1):
            faces.append((s * n + k, s2 * n + k, s2 * n + k + 1, s * n + k + 1))
    mesh = bpy.data.meshes.new("lathe")
    mesh.from_pydata(verts, [], faces)
    o = bpy.data.objects.new("lathe", mesh)
    bpy.context.collection.objects.link(o)
    return _assign(o, mat or concrete())


def windows(sx, sy, z0, z1, rows, per_side, loc=(0, 0, 0), inset=0.05, size=0.55):
    """在長方體四面貼上深色窗戶（薄片）。"""
    objs = []
    w = size
    hgt = (z1 - z0) / rows * 0.5
    for row in range(rows):
        zc = z0 + (row + 0.5) * (z1 - z0) / rows - hgt / 2
        for k in range(per_side):
            t = (k + 0.5) / per_side - 0.5
            for (px, py, fx, fy) in ((t * sx, -sy / 2 - inset, w, 0.02), (t * sx, sy / 2 + inset, w, 0.02),
                                     (-sx / 2 - inset, t * sy, 0.02, w), (sx / 2 + inset, t * sy, 0.02, w)):
                objs.append(box(fx, fy, hgt, (loc[0] + px, loc[1] + py, loc[2] + zc), glass()))
    return objs


GROUND_MARGIN = TILE * 0.03   # 反鋸齒邊緣在量化時會被削掉約 1 px，地面板加一點邊才會剛好是 64×32／128×64（校正值）


def ground_plate(tiles_x=1, tiles_y=1, mat=None, thickness=0.05):
    """覆蓋整個佔地的地面薄板（建築的 part 0）。"""
    return box(TILE * tiles_x + GROUND_MARGIN, TILE * tiles_y + GROUND_MARGIN, thickness, (0, 0, 0), mat or grass())
