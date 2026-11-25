"""參數化建築模型（給 tools/blender/static_rig.py）。設定檔路徑由環境變數 MODEL_CONFIG 指定（JSON）。

JSON：{"parts": [<每個部件的描述>…]}，部件 index 與模板的 part 相同，高度由 static_rig 的 --heights 決定
（模型裡用 H 代表該部件的高度，Blender 單位）。部件類型：
  {"type": "ground", "tiles": 1, "mat": "grass"|"gravel"|"pavement", "path": true}
  {"type": "walls", "size": [sx, sy], "mat": "plaster"|"brick"|"concrete", "windows": [rows, per_side], "door": true}
  {"type": "gable", "size": [sx, sy], "along": "x"|"y", "chimney": true}
  {"type": "flatroof", "size": [sx, sy], "parapet": true, "units": 2}
  {"type": "storey", "size": [sx, sy], "mat": "concrete", "band": true, "windows": [1, 6]}
尺寸單位為「格」（1 = 一整格寬）。
"""
import json
import os


def _cfg():
    with open(os.environ["MODEL_CONFIG"], encoding="utf-8") as fp:
        return json.load(fp)


HEIGHTS = None


def _mat(kit, name):
    return {
        "grass": kit.grass, "gravel": kit.gravel, "plaster": kit.plaster, "brick": kit.brick,
        "concrete": kit.concrete, "dirt": kit.dirt, "coal": kit.coal, "wood": kit.wood,
        "pavement": lambda: kit.material("Pavement", (0.48, 0.47, 0.44), noise=0.3),
        "sandstone": lambda: kit.material("Sandstone", (0.72, 0.60, 0.40), noise=0.35),
        "darkbrick": lambda: kit.material("Dark Brick", (0.28, 0.12, 0.09), noise=0.5),
    }[name]()


def make_part(kit, index):
    cfg = _cfg()["parts"][index]
    H = kit.z(int(os.environ["PART_HEIGHT_PX"]))
    T = kit.TILE
    t = cfg["type"]
    if t == "ground":
        n = cfg.get("tiles", 1)
        kit.ground_plate(n, n, _mat(kit, cfg.get("mat", "grass")), thickness=0.03)
        if cfg.get("path"):
            kit.box(T * 0.12, T * 0.5, 0.05, (0, -T * 0.25, 0), _mat(kit, "pavement"))
    elif t == "walls":
        sx, sy = cfg["size"][0] * T, cfg["size"][1] * T
        kit.box(sx, sy, H, (0, 0, 0), _mat(kit, cfg.get("mat", "plaster")))
        rows, per = cfg.get("windows", [1, 2])
        kit.windows(sx, sy, H * 0.15, H * 0.95, rows, per)
        if cfg.get("door"):
            kit.box(sx * 0.14, 0.05, H * 0.6, (0, -sy / 2 - 0.03, 0), kit.wood())
    elif t == "storey":
        sx, sy = cfg["size"][0] * T, cfg["size"][1] * T
        kit.box(sx, sy, H, (0, 0, 0), _mat(kit, cfg.get("mat", "concrete")))
        rows, per = cfg.get("windows", [1, 6])
        kit.windows(sx, sy, H * 0.2, H * 0.9, rows, per, size=sx / per * 0.6)
    elif t == "gable":
        sx, sy = cfg["size"][0] * T, cfg["size"][1] * T
        kit.gable_roof(sx, sy, H * 0.9, (0, 0, 0), kit.roof_tiles(), along_x=(cfg.get("along", "x") == "x"))
        if cfg.get("chimney"):
            kit.box(0.5, 0.5, H, (sx * 0.25, sy * 0.15, 0), kit.brick())
    elif t == "flatroof":
        sx, sy = cfg["size"][0] * T, cfg["size"][1] * T
        dark = kit.material("Dark Roof", (0.20, 0.20, 0.20), rough=0.85, noise=0.45)
        wall_m = _mat(kit, cfg.get("mat", "concrete"))
        kit.box(sx, sy, H * 0.22, (0, 0, 0), dark)
        if cfg.get("parapet"):
            pt = T * 0.06
            ph = H * 0.38
            trim = kit.material("Company Color 1 Trim", (0.5, 0.5, 0.5))
            kit.box(sx, pt, ph, (0, -sy / 2 + pt / 2, 0), wall_m)
            kit.box(sx, pt, ph, (0, sy / 2 - pt / 2, 0), wall_m)
            kit.box(pt, sy, ph, (-sx / 2 + pt / 2, 0, 0), wall_m)
            kit.box(pt, sy, ph, (sx / 2 - pt / 2, 0, 0), wall_m)
            kit.box(sx + 0.06, 0.08, H * 0.09, (0, -sy / 2 - 0.01, ph * 0.72), trim)
            kit.box(sx + 0.06, 0.08, H * 0.09, (0, sy / 2 + 0.01, ph * 0.72), trim)
            kit.box(0.08, sy + 0.06, H * 0.09, (-sx / 2 - 0.01, 0, ph * 0.72), trim)
            kit.box(0.08, sy + 0.06, H * 0.09, (sx / 2 + 0.01, 0, ph * 0.72), trim)
        kit.box(sx * 0.34, sy * 0.28, H * 0.62, (sx * 0.16, sy * 0.12, H * 0.20), wall_m)
        kit.box(sx * 0.36, sy * 0.30, H * 0.10, (sx * 0.16, sy * 0.12, H * 0.80), dark)
        for k in range(cfg.get("units", 0)):
            kit.box(sx * 0.16, sy * 0.12, H * 0.42, ((k - 0.5) * sx * 0.26 - sx * 0.15, -sy * 0.18, H * 0.20), kit.steel())
    else:
        raise ValueError(f"未知部件類型 {t}")
