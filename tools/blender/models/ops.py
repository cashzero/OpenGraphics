"""通用「幾何指令」模型（給 tools/blender/static_rig.py）：設定檔（環境變數 MODEL_CONFIG，JSON）列出每個部件的
基本形體，由 tools/gen/building_recipes.py 依配方產生。Blender 端只負責把指令畫出來。

JSON：{"parts": [{"ops": [指令…]}, …]}；平面座標與尺寸以「格」為單位（1 = 一整格寬），高度以遊戲 px 為單位。
  {"op": "ground", "tiles": 1|2, "m": 材質}                                     地面板（建築的 part 0）
  {"op": "box",   "c": [x, y, z], "s": [sx, sy, h], "m": 材質, "r": 旋轉角度}      c = 底面中心
  {"op": "cyl",   "c": [x, y, z], "r": 半徑, "h": 高, "m": 材質, "v": 邊數, "rt": 頂半徑}
  {"op": "gable", "c": [x, y, z], "s": [sx, sy, h], "m": 材質, "a": "x"|"y"}         山形屋頂（屋脊沿 a）
  {"op": "hip",   "c": [x, y, z], "s": [sx, sy, h], "m": 材質, "k": 屋脊長度比例}     四坡／金字塔屋頂
  {"op": "lathe", "c": [x, y, z], "p": [[半徑, 高], …], "m": 材質, "seg": 邊數}       旋轉體（圓頂、尖塔）
  {"op": "seg",   "a": [x, y, z], "b": [x, y, z], "r": 半徑, "m": 材質}               圓柱線段（桁架、天線）
材質名稱見 MATS；"company"／"company2" 為公司色（primary／secondary remap）。

設定檔頂層 "unit": "m" 時（車輛用），平面與高度都直接是 Blender 單位（約等於公尺），不做格／px 換算。
車輛用的額外指令（單位同上）：
  {"op": "cylx", "c": [x, y, z], "r": 半徑, "w": 寬, "m": 材質, "v": 邊數}           沿 X 軸的圓柱（車輪、車軸）
  {"op": "cyly", "c": [x, y, z], "r": 半徑, "l": 長, "m": 材質, "v": 邊數, "rt": 末端半徑}  沿 Y 軸的圓柱（鍋爐、煙囪橫置）
  {"op": "finx", "p": [[y, z], …], "x": [x0, x1], "m": 材質}                       YZ 平面多邊形沿 X 擠出（側面輪廓、尾翼）
  {"op": "prism", "p": [[x, y], …], "z": [z0, z1], "m": 材質}                       XY 平面多邊形沿 Z 擠出（機翼、甲板）
  {"op": "loft", "s": [[y, 半寬, z底, z頂], …], "m": 材質}                          沿 Y 的方形斷面放樣（船殼、車頭）
  {"op": "tube", "s": [[y, 半徑, z中心], …], "m": 材質, "seg": 邊數}                  沿 Y 的圓形斷面放樣（機身、鍋爐）
"""
import json
import math
import os

import bpy
from mathutils import Vector

MATS = {  # 名稱: (RGB 線性值, 粗糙度, 金屬度, 雜訊)
    "grass": ((0.035, 0.085, 0.015), 0.9, 0, 0.6), "gravel": ((0.09, 0.09, 0.085), 0.9, 0, 0.7),
    "pavement": ((0.48, 0.47, 0.44), 0.8, 0, 0.3), "dirt": ((0.09, 0.055, 0.03), 0.9, 0, 0.7),
    "plaster": ((0.78, 0.74, 0.62), 0.8, 0, 0.25), "whitewash": ((0.86, 0.85, 0.80), 0.8, 0, 0.15),
    "ochre": ((0.70, 0.52, 0.26), 0.8, 0, 0.25), "pink": ((0.76, 0.52, 0.48), 0.8, 0, 0.2),
    "cream": ((0.80, 0.72, 0.52), 0.8, 0, 0.2), "sage": ((0.50, 0.58, 0.46), 0.8, 0, 0.2),
    "brick": ((0.42, 0.16, 0.10), 0.85, 0, 0.5), "darkbrick": ((0.28, 0.12, 0.09), 0.85, 0, 0.5),
    "yellowbrick": ((0.62, 0.48, 0.28), 0.85, 0, 0.45), "stone": ((0.46, 0.45, 0.42), 0.85, 0, 0.5),
    "darkstone": ((0.26, 0.26, 0.25), 0.85, 0, 0.5), "sandstone": ((0.72, 0.60, 0.40), 0.85, 0, 0.35),
    "concrete": ((0.55, 0.55, 0.52), 0.8, 0, 0.35), "darkconcrete": ((0.34, 0.34, 0.33), 0.8, 0, 0.35),
    "whiteconcrete": ((0.78, 0.78, 0.76), 0.7, 0, 0.2), "wood": ((0.32, 0.20, 0.10), 0.8, 0, 0.4),
    "darkwood": ((0.16, 0.09, 0.05), 0.8, 0, 0.4), "lightwood": ((0.55, 0.38, 0.20), 0.8, 0, 0.4),
    "glass": ((0.05, 0.08, 0.12), 0.2, 0, 0), "blueglass": ((0.10, 0.20, 0.32), 0.15, 0.3, 0),
    "greenglass": ((0.10, 0.24, 0.22), 0.15, 0.3, 0), "lit": ((0.85, 0.75, 0.40), 0.5, 0, 0),
    "slate": ((0.085, 0.085, 0.09) if os.environ.get("OG_RENDER_STYLE", "vanilla") == "vanilla" else (0.12, 0.13, 0.15), 0.6, 0, 0.3), "shingle": ((0.22, 0.13, 0.08), 0.8, 0, 0.5),
    "thatch": ((0.24, 0.17, 0.07), 0.95, 0, 0.5), "terracotta": ((0.55, 0.22, 0.10), 0.8, 0, 0.35),
    "copper": ((0.20, 0.42, 0.34), 0.5, 0.3, 0.3), "lead": ((0.30, 0.32, 0.34), 0.5, 0.4, 0.2),
    "steel": ((0.35, 0.37, 0.40), 0.42, 0.25, 0), "darksteel": ((0.16, 0.16, 0.16), 0.48, 0.25, 0),
    "white": ((0.85, 0.85, 0.85), 0.6, 0, 0), "red": ((0.55, 0.05, 0.04), 0.6, 0, 0),
    "black": ((0.02, 0.02, 0.02), 0.6, 0, 0), "gold": ((0.70, 0.52, 0.12), 0.35, 0.5, 0),
    "hedge": ((0.02, 0.06, 0.012), 0.9, 0, 0.7), "water": ((0.04, 0.10, 0.16), 0.1, 0, 0),
    "flame": ((1.0, 0.45, 0.05), 0.5, 0, 0.2), "glow": ((1.0, 0.70, 0.20), 0.5, 0, 0.1),
    "smoke": ((0.45, 0.45, 0.44), 0.95, 0, 0.3), "steam": ((0.80, 0.80, 0.80), 0.95, 0, 0.2),
    "rust": ((0.30, 0.13, 0.06), 0.72, 0.15, 0.5), "corrugated": ((0.25, 0.27, 0.25), 0.55, 0.2, 0.4),
    "yellowsteel": ((0.75, 0.55, 0.05), 0.45, 0.25, 0.1), "silver": ((0.58, 0.57, 0.54), 0.36, 0.25, 0.1),
    "chemblue": ((0.10, 0.22, 0.52), 0.45, 0.20, 0.2),
    "coal": ((0.05, 0.05, 0.05), 0.6, 0, 0.6), "ore": ((0.25, 0.10, 0.06), 0.9, 0, 0.6),
    "logs": ((0.30, 0.18, 0.08), 0.9, 0, 0.5), "planks": ((0.62, 0.45, 0.25), 0.8, 0, 0.3),
    "hay": ((0.70, 0.55, 0.20), 0.95, 0, 0.5), "snow": ((0.90, 0.92, 0.95), 0.9, 0, 0.1),
    "company": ((0.6, 0.2, 0.2), 0.7, 0, 0.3), "company2": ((0.2, 0.5, 0.2), 0.7, 0, 0.2),
    "quay": ((0.40, 0.40, 0.38), 0.85, 0, 0.08), "apron": ((0.50, 0.50, 0.47), 0.85, 0, 0.06),
    "asphalt": ((0.10, 0.10, 0.10), 0.9, 0, 0.08),
}
REMAP_NAMES = {"company": "Company Color 1", "company2": "Company Color 2"}


def _mat(kit, name, ground=False):
    rgb, rough, metal, noise = MATS[name]
    return kit.material(f"{REMAP_NAMES.get(name, name.title())} {name}", rgb, rough, metal, noise, ground=ground)


def _mesh(name, verts, faces, kit, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    o = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(_mat(kit, mat))
    return o


def _poly_prism(name, pts2d, a0, a1, axis, kit, mat):
    """平面多邊形擠出。axis = "z"：pts 為 (x, y)，沿 z 從 a0 到 a1；axis = "x"：pts 為 (y, z)，沿 x；axis = "y"：pts 為 (x, z)，沿 y。"""
    n = len(pts2d)
    if axis == "z":
        verts = [(x, y, a0) for x, y in pts2d] + [(x, y, a1) for x, y in pts2d]
    elif axis == "x":
        verts = [(a0, y, z) for y, z in pts2d] + [(a1, y, z) for y, z in pts2d]
    else:
        verts = [(x, a0, z) for x, z in pts2d] + [(x, a1, z) for x, z in pts2d]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    o = _mesh(name, verts, faces, kit, mat)
    o.data.validate()
    o.data.update()
    # 法線一致（凹多邊形也能正確著色）
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    return o


def run_op(kit, op, T=None, Z=None):
    T = kit.TILE if T is None else T
    Z = Z or kit.z
    kind = op["op"]
    m = op.get("m", "concrete")
    if kind == "ground":                                  # 覆蓋整個佔地的地面板（含校正用的邊緣）
        return kit.ground_plate(op.get("tiles", 1), op.get("tiles", 1), _mat(kit, m, ground=True), thickness=0.03)
    if kind == "box":
        (x, y, z), (sx, sy, h) = op["c"], op["s"]
        o = kit.box(sx * T, sy * T, Z(h), (x * T, y * T, Z(z)), _mat(kit, m), rot=math.radians(op.get("r", 0)))
        return o
    if kind == "cyl":
        x, y, z = op["c"]
        return kit.cylinder(op["r"] * T, Z(op["h"]), (x * T, y * T, Z(z)), _mat(kit, m), verts=op.get("v", 16),
                            r_top=(op["rt"] * T if "rt" in op else None))
    if kind == "gable":
        (x, y, z), (sx, sy, h) = op["c"], op["s"]
        return kit.gable_roof(sx * T, sy * T, Z(h), (x * T, y * T, Z(z)), _mat(kit, m), along_x=(op.get("a", "x") == "x"))
    if kind == "hip":
        (x, y, z), (sx, sy, h) = op["c"], op["s"]
        hx, hy, H = sx * T / 2, sy * T / 2, Z(h)
        k = op.get("k", 0.0)
        if sx >= sy:
            rx, ry = hx * k, 0.0
        else:
            rx, ry = 0.0, hy * k
        X, Y, Z0 = x * T, y * T, Z(z)
        verts = [(X - hx, Y - hy, Z0), (X + hx, Y - hy, Z0), (X + hx, Y + hy, Z0), (X - hx, Y + hy, Z0),
                 (X - rx, Y - ry, Z0 + H), (X + rx, Y + ry, Z0 + H)]
        if sx >= sy:
            faces = [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
        else:
            faces = [(0, 1, 4), (2, 3, 5), (1, 2, 5, 4), (3, 0, 4, 5), (0, 3, 2, 1)]
        return _mesh("hip", verts, faces, kit, m)
    if kind == "lathe":
        x, y, z = op["c"]
        prof = [(r * T, Z(h)) for r, h in op["p"]]
        return kit.lathe(prof, (x * T, y * T, Z(z)), _mat(kit, m), segments=op.get("seg", 24))
    if kind == "seg":
        a = Vector((op["a"][0] * T, op["a"][1] * T, Z(op["a"][2])))
        b = Vector((op["b"][0] * T, op["b"][1] * T, Z(op["b"][2])))
        d = b - a
        r = op.get("r", 0.01) * T
        bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=r, depth=d.length, location=(a + b) / 2)
        o = bpy.context.active_object
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
        o.data.materials.clear()
        o.data.materials.append(_mat(kit, m))
        return o
    if kind == "cylx" or kind == "cyly":
        x, y, z = op["c"]
        if kind == "cylx":
            bpy.ops.mesh.primitive_cylinder_add(vertices=op.get("v", 12), radius=op["r"] * T, depth=op["w"] * T,
                                                location=(x * T, y * T, Z(z)), rotation=(0, math.radians(90), 0))
            o = bpy.context.active_object
        else:
            bpy.ops.mesh.primitive_cone_add(vertices=op.get("v", 12), radius1=op["r"] * T, radius2=op.get("rt", op["r"]) * T,
                                            depth=op["l"] * T, location=(x * T, y * T, Z(z)), rotation=(math.radians(-90), 0, 0))
            o = bpy.context.active_object
        o.data.materials.clear()
        o.data.materials.append(_mat(kit, m))
        return o
    if kind == "finx":
        x0, x1 = op["x"]
        return _poly_prism("finx", [(y * T, Z(z)) for y, z in op["p"]], x0 * T, x1 * T, "x", kit, m)
    if kind == "finy":
        y0, y1 = op["y"]
        return _poly_prism("finy", [(x * T, Z(z)) for x, z in op["p"]], y0 * T, y1 * T, "y", kit, m)
    if kind == "prism":
        z0, z1 = op["z"]
        return _poly_prism("prism", [(x * T, y * T) for x, y in op["p"]], Z(z0), Z(z1), "z", kit, m)
    if kind in ("loft", "tube"):
        secs = op["s"]
        seg = 4 if kind == "loft" else op.get("seg", 12)
        verts, faces = [], []
        for (yy, a, b, *rest) in secs:
            if kind == "loft":
                hw, z0, z1 = a, b, rest[0]
                ring = [(-hw, z0), (hw, z0), (hw, z1), (-hw, z1)]
            else:
                r, zc = a, b
                ring = [(r * math.cos(2 * math.pi * k / seg), zc + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)]
            verts += [(px * T, yy * T, Z(pz)) for px, pz in ring]
        n = len(secs)
        for i in range(n - 1):
            for k in range(seg):
                a0, a1 = i * seg + k, i * seg + (k + 1) % seg
                faces.append((a0, a1, a1 + seg, a0 + seg))
        faces.append(tuple(range(seg))[::-1])
        faces.append(tuple(range((n - 1) * seg, n * seg)))
        o = _mesh(kind, verts, faces, kit, m)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(o.data)
        bm.free()
        return o
    raise ValueError(f"未知指令 {kind}")


_CFG = None


def make_part(kit, index):
    global _CFG
    if _CFG is None:
        with open(os.environ["MODEL_CONFIG"], encoding="utf-8") as fp:
            _CFG = json.load(fp)
    if _CFG.get("unit") == "m":
        for op in _CFG["parts"][index]["ops"]:
            run_op(kit, op, T=1.0, Z=lambda v: v)
    else:
        for op in _CFG["parts"][index]["ops"]:
            run_op(kit, op)
