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

# 原版風格（ROADMAP M6 美術調整）：OG_RENDER_STYLE=vanilla 時，所有非金屬、非玻璃材質疊上細顆粒雜訊（約 1–2 px），
# 再加一層中等尺度的斑駁，模仿原版算圖的顆粒質感；static_rig.py 同時改用 Standard 色彩轉換與較強的明暗對比。
import os  # noqa: E402
VANILLA_STYLE = os.environ.get("OG_RENDER_STYLE", "vanilla") == "vanilla"   # classic = M3 的舊風格
GRAIN = 0.42


def material(name, rgb, rough=0.8, metal=0.0, noise=0.0, ground=False):
    """建立（或取用）材質。地表類材質（dirt/gravel/grass/pavement/ore/coal/apron/quay/asphalt，或 ground=True）
    使用多色帶程序化地形著色器＋3D Bump 凹凸法線，確保量化至 Locomotion 256 色調色盤後仍有豐富顆粒與接縫質感。
    """
    key = (name, rgb, rough, metal, noise, ground)
    if key in _materials:
        return _materials[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal

    gkind = _detect_ground_kind(name, ground)
    if VANILLA_STYLE and gkind:
        _add_ground_shader(nt, bsdf, gkind, rgb)
    else:
        if noise > 0:
            coord = nt.nodes.new("ShaderNodeTexCoord")
            tex = nt.nodes.new("ShaderNodeTexNoise")
            tex.inputs["Scale"].default_value = 2.2
            tex.inputs["Detail"].default_value = 6.0
            tex.inputs["Roughness"].default_value = 0.65
            nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
            mix = nt.nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MULTIPLY"
            mix.inputs["Fac"].default_value = noise
            mix.inputs["Color1"].default_value = (*rgb, 1)
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.elements[0].position = 0.25
            ramp.color_ramp.elements[1].position = 0.75
            ramp.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1)
            ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
            nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
            nt.links.new(ramp.outputs["Color"], mix.inputs["Color2"])
            nt.links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
        if VANILLA_STYLE and "brick" in name.lower():
            _add_bricks(nt, bsdf, rgb)
        if VANILLA_STYLE and metal < 0.5 and rough > 0.3:
            _add_grain(nt, bsdf)
    _materials[key] = m
    return m


def _detect_ground_kind(name: str, ground: bool) -> str | None:
    """辨識應套用多色帶程序化地表著色器的材質種類。"""
    low = name.lower()
    if "company color" in low:
        return None
    for k in ("dirt", "gravel", "grass", "pavement", "ore", "coal", "apron", "quay", "asphalt"):
        if k in low:
            return k
    if ground:
        if "snow" in low:
            return "snow"
        if "darkconcrete" in low:
            return "darkconcrete"
        if "concrete" in low:
            return "concrete"
    return None


def _make_ramp(nt, stops):
    """建立多段色彩漸層節點：stops = [(pos, (r, g, b)), ...]。"""
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = (*stops[0][1], 1.0)
    cr.elements[1].position = stops[-1][0]
    cr.elements[1].color = (*stops[-1][1], 1.0)
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = (*col, 1.0)
    return ramp


def _add_ground_shader(nt, bsdf, kind: str, rgb):
    """地表專用多尺度程序化著色器：結合大尺度斑駁、中尺度碎石／土塊、細顆粒／鋪面縫線與 3D Bump 凹凸。
    座標使用 Object 空間（1 tile = 10.236 單位 ≈ 64px），尺度刻意落在 2–12px 可辨識區間，避免被 TAA 糊成單色。
    """
    coord = nt.nodes.new("ShaderNodeTexCoord")
    vec = coord.outputs["Object"]

    # 四層地形雜訊：大斑塊（~22px）、中塊（~6px）、細粒（~2px）、微顆粒抖動（~1px）
    n_macro = nt.nodes.new("ShaderNodeTexNoise")
    n_macro.inputs["Scale"].default_value = 0.28
    n_macro.inputs["Detail"].default_value = 4.0
    n_macro.inputs["Roughness"].default_value = 0.65
    nt.links.new(vec, n_macro.inputs["Vector"])

    n_med = nt.nodes.new("ShaderNodeTexNoise")
    n_med.inputs["Scale"].default_value = 1.50
    n_med.inputs["Detail"].default_value = 8.0
    n_med.inputs["Roughness"].default_value = 0.78
    nt.links.new(vec, n_med.inputs["Vector"])

    n_fine = nt.nodes.new("ShaderNodeTexNoise")
    n_fine.inputs["Scale"].default_value = 4.40
    n_fine.inputs["Detail"].default_value = 10.0
    n_fine.inputs["Roughness"].default_value = 0.85
    nt.links.new(vec, n_fine.inputs["Vector"])

    # Voronoi 碎石／土塊／草叢微粒（~2px 銳利石粒）
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 4.2 if kind in ("gravel", "ore", "coal") else 3.4
    nt.links.new(vec, vor.inputs["Vector"])

    # 混合成主紋理因子：以中細顆粒為主（0.26 大斑塊 + 0.34 中塊 + 0.40 細粒），避免糊成雲霧色塊
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY_ADD"
    m1.inputs[1].default_value = 0.26
    nt.links.new(n_macro.outputs["Fac"], m1.inputs[0])

    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    m2.inputs[1].default_value = 0.34
    nt.links.new(n_med.outputs["Fac"], m2.inputs[0])
    nt.links.new(m2.outputs["Value"], m1.inputs[2])

    m3 = nt.nodes.new("ShaderNodeMath")
    m3.operation = "MULTIPLY"
    m3.inputs[1].default_value = 0.40
    nt.links.new(n_fine.outputs["Fac"], m3.inputs[0])

    m_sum = nt.nodes.new("ShaderNodeMath")
    m_sum.operation = "ADD"
    nt.links.new(m1.outputs["Value"], m_sum.inputs[0])
    nt.links.new(m3.outputs["Value"], m_sum.inputs[1])

    # 關鍵：3 層 Perlin 相加後集中在 0.36..0.64，展開至 0..1 才能命中 10–20 個調色盤色階
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = 0.35
    mr.inputs["From Max"].default_value = 0.65
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(m_sum.outputs["Value"], mr.inputs["Value"])

    # 各類地表的專屬多色帶色盤（精準對齊 pal[214–225] 暖石泥、pal[34–45] 暖土、pal[70–81/82–93] 草地、pal[10–21] 混凝土灰）
    palettes = {
        # 農場泥土／庭院土：深濕泥(214-216) → 暖棕土(36-38/218) → 淺黃沙土(40-42/220) → 乾沙礫(222)
        "dirt": [
            (0.05, (0.015, 0.008, 0.003)),
            (0.25, (0.048, 0.028, 0.011)),
            (0.48, (0.105, 0.066, 0.028)),
            (0.72, (0.185, 0.128, 0.062)),
            (0.92, (0.310, 0.235, 0.135)),
        ],
        # 碎石庭院：全段鎖在 pal[214–225] 暖石灰（R > G > B），徹底避免冷青色塊跳變
        "gravel": [
            (0.05, (0.022, 0.016, 0.009)),
            (0.28, (0.068, 0.055, 0.038)),
            (0.52, (0.145, 0.125, 0.095)),
            (0.76, (0.255, 0.228, 0.185)),
            (0.95, (0.395, 0.360, 0.300)),
        ],
        # 草地／花園：全段展開 pal[70–81] & pal[82–93] 豐富草色層次
        "grass": [
            (0.05, (0.010, 0.028, 0.004)),
            (0.28, (0.028, 0.062, 0.010)),
            (0.52, (0.062, 0.112, 0.020)),
            (0.76, (0.118, 0.175, 0.035)),
            (0.95, (0.205, 0.260, 0.072)),
        ],
        # 鐵礦赤土：暗鐵礦 → 鐵鏽紅土(106-112) → 赭橘礦土 → 淺砂岩礫
        "ore": [
            (0.05, (0.025, 0.010, 0.005)),
            (0.28, (0.095, 0.036, 0.016)),
            (0.54, (0.210, 0.088, 0.042)),
            (0.78, (0.340, 0.168, 0.088)),
            (0.95, (0.420, 0.265, 0.165)),
        ],
        # 煤場：炭黑煤屑 → 暗灰煤渣 → 中灰石粉
        "coal": [
            (0.08, (0.006, 0.008, 0.008)),
            (0.35, (0.024, 0.030, 0.030)),
            (0.65, (0.062, 0.074, 0.074)),
            (0.92, (0.145, 0.160, 0.160)),
        ],
        # 人行道／石板廣場：全段鎖在 pal[214–225] 暖石板（避免藍灰雜斑）
        "pavement": [
            (0.05, (0.085, 0.074, 0.058)),
            (0.32, (0.165, 0.148, 0.122)),
            (0.64, (0.275, 0.252, 0.215)),
            (0.94, (0.410, 0.382, 0.335)),
        ],
        # 工業混凝土地坪／停機坪／碼頭／柏油：統一鎖在 pal[10–21] 乾淨冷石板灰
        "concrete": [
            (0.06, (0.065, 0.085, 0.086)),
            (0.34, (0.145, 0.175, 0.176)),
            (0.68, (0.260, 0.295, 0.296)),
            (0.95, (0.395, 0.430, 0.430)),
        ],
        "darkconcrete": [
            (0.06, (0.032, 0.044, 0.045)),
            (0.36, (0.080, 0.102, 0.104)),
            (0.70, (0.155, 0.185, 0.186)),
            (0.95, (0.255, 0.290, 0.290)),
        ],
        "apron": [
            (0.06, (0.075, 0.095, 0.096)),
            (0.36, (0.145, 0.172, 0.174)),
            (0.70, (0.235, 0.268, 0.270)),
            (0.95, (0.340, 0.375, 0.376)),
        ],
        "quay": [
            (0.06, (0.055, 0.072, 0.074)),
            (0.36, (0.125, 0.152, 0.154)),
            (0.70, (0.220, 0.252, 0.254)),
            (0.95, (0.335, 0.370, 0.372)),
        ],
        "asphalt": [
            (0.08, (0.015, 0.022, 0.022)),
            (0.40, (0.042, 0.056, 0.057)),
            (0.74, (0.082, 0.102, 0.104)),
            (0.95, (0.135, 0.160, 0.162)),
        ],
        "snow": [
            (0.08, (0.340, 0.415, 0.490)),
            (0.38, (0.580, 0.655, 0.720)),
            (0.72, (0.820, 0.865, 0.905)),
            (0.95, (0.975, 0.988, 1.000)),
        ],
    }

    ramp = _make_ramp(nt, palettes[kind])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    col_out = ramp.outputs["Color"]

    # 泥土地混入自然雜草／苔蘚斑點（命中 pal[70–81]）
    if kind == "dirt":
        weed = nt.nodes.new("ShaderNodeTexNoise")
        weed.inputs["Scale"].default_value = 0.75
        weed.inputs["Detail"].default_value = 6.0
        weed.inputs["Roughness"].default_value = 0.75
        nt.links.new(vec, weed.inputs["Vector"])
        wr = _make_ramp(nt, [(0.55, (0, 0, 0)), (0.68, (1, 1, 1))])
        nt.links.new(weed.outputs["Fac"], wr.inputs["Fac"])
        wmix = nt.nodes.new("ShaderNodeMixRGB")
        wmix.inputs["Color2"].default_value = (0.055, 0.098, 0.020, 1.0)
        nt.links.new(wr.outputs["Color"], wmix.inputs["Fac"])
        nt.links.new(col_out, wmix.inputs["Color1"])
        col_out = wmix.outputs["Color"]

    # 草地混入極少許裸土／野花點綴，增添自然草皮層次
    if kind == "grass":
        bare = nt.nodes.new("ShaderNodeTexNoise")
        bare.inputs["Scale"].default_value = 0.95
        bare.inputs["Detail"].default_value = 5.0
        nt.links.new(vec, bare.inputs["Vector"])
        br = _make_ramp(nt, [(0.60, (0, 0, 0)), (0.72, (1, 1, 1))])
        nt.links.new(bare.outputs["Fac"], br.inputs["Fac"])
        bm = nt.nodes.new("ShaderNodeMixRGB")
        bm.inputs["Color2"].default_value = (0.110, 0.075, 0.032, 1.0)
        nt.links.new(br.outputs["Color"], bm.inputs["Fac"])
        nt.links.new(col_out, bm.inputs["Color1"])
        col_out = bm.outputs["Color"]

    # 碎石／泥土／礦土／草地：疊加高對比 Voronoi 小礫石／土塊明暗點（拉出 crisp 1–2px 顆粒）
    if kind in ("dirt", "gravel", "ore", "coal", "grass"):
        vor.inputs["Scale"].default_value = 4.2 if kind in ("gravel", "ore", "coal") else 3.4
        vramp = _make_ramp(nt, [(0.0, (0.30, 0.30, 0.30)), (0.38, (0.85, 0.85, 0.85)), (0.75, (1.0, 1.0, 1.0))])
        nt.links.new(vor.outputs["Distance"], vramp.inputs["Fac"])
        vmix = nt.nodes.new("ShaderNodeMixRGB")
        vmix.blend_type = "MULTIPLY"
        vmix.inputs["Fac"].default_value = 0.78 if kind in ("gravel", "ore", "coal") else 0.55
        nt.links.new(col_out, vmix.inputs["Color1"])
        nt.links.new(vramp.outputs["Color"], vmix.inputs["Color2"])
        col_out = vmix.outputs["Color"]

    # 人行道／混凝土／停機坪／碼頭：加上清晰鋪磚或伸縮縫格線
    bump_src = mr.outputs["Result"]
    if kind in ("pavement", "concrete", "darkconcrete", "apron", "quay"):
        brick = nt.nodes.new("ShaderNodeTexBrick")
        if kind == "pavement":
            brick.offset = 0.5
            brick.inputs["Scale"].default_value = 0.55
            brick.inputs["Brick Width"].default_value = 1.0
            brick.inputs["Row Height"].default_value = 0.55
            brick.inputs["Mortar Size"].default_value = 0.055
            brick.inputs["Mortar Smooth"].default_value = 0.08
        else:
            brick.offset = 0.0
            brick.inputs["Scale"].default_value = 0.30
            brick.inputs["Brick Width"].default_value = 1.0
            brick.inputs["Row Height"].default_value = 1.0
            brick.inputs["Mortar Size"].default_value = 0.035
            brick.inputs["Mortar Smooth"].default_value = 0.08
        brick.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
        brick.inputs["Color2"].default_value = (0.78, 0.78, 0.76, 1.0)
        brick.inputs["Mortar"].default_value = (0.28, 0.28, 0.27, 1.0)
        nt.links.new(vec, brick.inputs["Vector"])
        bmix = nt.nodes.new("ShaderNodeMixRGB")
        bmix.blend_type = "MULTIPLY"
        bmix.inputs["Fac"].default_value = 0.90 if kind == "pavement" else 0.75
        nt.links.new(col_out, bmix.inputs["Color1"])
        nt.links.new(brick.outputs["Color"], bmix.inputs["Color2"])
        col_out = bmix.outputs["Color"]
        bump_src = brick.outputs["Fac"]

    nt.links.new(col_out, bsdf.inputs["Base Color"])

    # 3D Bump 法線凹凸，讓 4 盞方向太陽光照出碎石、土塊與地磚縫立體明暗
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = {
        "dirt": 0.75, "gravel": 0.90, "grass": 0.65, "ore": 0.85, "coal": 0.80,
        "pavement": 0.60, "concrete": 0.50, "darkconcrete": 0.50, "apron": 0.45,
        "quay": 0.55, "asphalt": 0.55, "snow": 0.35,
    }[kind]
    bump.inputs["Distance"].default_value = 0.22
    nt.links.new(bump_src, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _add_bricks(nt, bsdf, rgb):
    """磚紋（磚縫約每 2 px 一條），取代原本的單色。"""
    coord = nt.nodes.new("ShaderNodeTexCoord")
    tex = nt.nodes.new("ShaderNodeTexBrick")
    tex.inputs["Scale"].default_value = 0.6
    tex.inputs["Mortar Size"].default_value = 0.035
    tex.inputs["Color1"].default_value = (*rgb, 1)
    tex.inputs["Color2"].default_value = (rgb[0] * 0.78, rgb[1] * 0.78, rgb[2] * 0.78, 1)
    tex.inputs["Mortar"].default_value = (0.30, 0.28, 0.25, 1)
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])


def _add_grain(nt, bsdf):
    """細顆粒（scale 3.2，約 1–1.5 px）＋斑駁（scale 0.9）兩層雜訊，乘到 Base Color 上。"""
    src = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
    base_rgb = bsdf.inputs["Base Color"].default_value
    coord = nt.nodes.new("ShaderNodeTexCoord")
    out = src
    for scale, amount in ((3.2, GRAIN), (0.9, GRAIN * 0.45)):
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = scale
        tex.inputs["Detail"].default_value = 1.0
        nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.3
        ramp.color_ramp.elements[1].position = 0.7
        ramp.color_ramp.elements[0].color = (1 - amount, 1 - amount, 1 - amount, 1)
        ramp.color_ramp.elements[1].color = (1 + amount * 0.6, 1 + amount * 0.6, 1 + amount * 0.6, 1)
        nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = 1.0
        if out is None:
            mix.inputs["Color1"].default_value = base_rgb
        else:
            nt.links.new(out, mix.inputs["Color1"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Color2"])
        out = mix.outputs["Color"]
    nt.links.new(out, bsdf.inputs["Base Color"])


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
