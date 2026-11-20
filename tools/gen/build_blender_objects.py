#!/usr/bin/env python3
"""建置以 Blender 建模的 M2 物件（城鎮建築、產業）。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_blender_objects.py [--reuse-render] [名稱…]

流程：模板（vanilla）取得部件高度 → tools/blender/static_rig.py 渲染（每部件 × 4 旋轉 + 公司色遮罩）
→ tools/quantize.py → （產業另外補上 2D 產生的影格）→ tools/pack.py → 刪 .gitkeep → 寫 FORK.md。
模型來源：建築用 tools/blender/models/building.py + 物件資料夾內的 model.json；產業用物件資料夾內的 model.py。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import dat  # noqa: E402
import objinfo  # noqa: E402

PY = str(REPO / ".venv" / "bin" / "python")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", str(Path.home() / "Locomotion" / "game")))
VR = REPO / "objects" / "VanillaReplacements"
BUILD = REPO / "build"

OBJECTS = {
    "BLDHOUS4": dict(folder="Building/BLDHOUS4", name="OGBLDHO4", display="Garden Cottage", size=128,
                     concept="小花園裡的平房：一種是白色粉刷牆配山形屋頂與煙囪，另一種是紅磚牆配轉向的屋頂。屋頂為公司色（城鎮隨機上色）。"),
    "BLDHOUS7": dict(folder="Building/BLDHOUS7", name="OGBLDHO7", display="Stone Cottage", size=128,
                     concept="砂岩牆的平房，三扇窗、山形屋頂與煙囪。屋頂為公司色。"),
    "BLDHOUS2": dict(folder="Building/BLDHOUS2", name="OGBLDHO2", display="Brick Terrace", size=128,
                     concept="三層紅磚排屋，每層四扇窗，一樓有門，山形屋頂與煙囪。屋頂為公司色。"),
    "BLDCTY3": dict(folder="Building/BLDCTY3", name="OGBLDCT3", display="Glass Office Block", size=256,
                    concept="2×2 的混凝土辦公大樓，每層一圈玻璃窗帶，樓層數依變化組合重複，平屋頂帶女兒牆與空調機組。女兒牆為公司色。"),
    "BLDCTY1": dict(folder="Building/BLDCTY1", name="OGBLDCT1", display="Sandstone Offices", size=256,
                    concept="2×2 的砂岩辦公樓，窗戶整齊排列，平屋頂帶女兒牆。女兒牆為公司色。"),
}

def industry_ground(style):
    """產業：在部件影格之後補上 21 張地面圖塊（tools/gen/industry_ground.py）。"""
    def extra(obj, info, sprites_dir):
        if info["has_shadows"]:
            raise SystemExit("尚未支援有陰影的產業")
        tpl = template_path(obj.name_str)
        run([PY, "tools/gen/industry_ground.py", "--template", str(tpl), "--style", style, "--append-to", str(sprites_dir)])
    return extra


OBJECTS.update({
    "COALMINE": dict(folder="Industry/COALMINE", name="OGCOALMI", display="Colliery", size=256, samples=24,
                     extra=industry_ground("coal"),
                     concept="煤礦：紅磚絞車房配公司色鋼構井架（天輪轉動 4 格動畫）、架高煤倉、選煤廠與煙囪；地面為煤場、碎石與泥土。"),
    "COALPS": dict(folder="Industry/COALPS", name="OGCOALPS", display="Coal Power Plant", size=256, samples=24,
                   extra=industry_ground("gravel"),
                   concept="燃煤電廠：雙曲線冷卻塔（頂端 32 格循環蒸汽）、紅磚鍋爐廠房與雙煙囪、兩種變電設備；地面為碎石與煤堆。"),
})

FORK_MD = """# OG_{vanilla}（fork 自製）
- 對應 vanilla：{vanilla}（{type_folder}）
- 內部名稱：{name}
- 遊戲內名稱：{display}
- 設計概念：{concept}
- 製作方式：Blender 5.2 程序化建模（{model}），`tools/blender/static_rig.py` 渲染 → `tools/quantize.py` → `tools/pack.py`；
  來源檔 `OG_{vanilla}.blend`（同一份模型腳本產生，所有部件沿 X 軸並排，可直接用 Blender 開啟檢視）；
  建置指令 `tools/gen/build_blender_objects.py {vanilla}`。以 vanilla {vanilla} 為結構模板，只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫模型參數與建置程式）
- 參考資料：無外部素材；vanilla 只用於部件高度、sprite 張數與尺寸比對
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet（含公司色變體與 vanilla 對照）已檢視
"""


def run(cmd, env=None):
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"失敗：{' '.join(map(str, cmd))}")
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    if lines:
        print("  " + lines[-1])


def template_path(vanilla: str) -> Path:
    p = LOCO / "ObjData" / f"{vanilla}.DAT"
    if p.exists():
        return p
    for f in (LOCO / "ObjData").iterdir():           # 有些 vanilla 檔名與內部名稱不同（例如 coalmine.dat）
        if dat.read_dat(f).name_str == vanilla:
            return f
    raise SystemExit(f"找不到模板 {vanilla}")


def build(vanilla: str, cfg: dict) -> None:
    folder = VR / cfg["folder"]
    tpl = template_path(vanilla)
    obj = dat.read_dat(tpl)
    info = objinfo.building(obj) if obj.type_name == "building" else objinfo.industry(obj)
    heights = ",".join(str(h) for h in info["heights"])
    render_dir = BUILD / "render" / vanilla
    sprites_dir = BUILD / "sprites" / vanilla
    print(f"== {vanilla}（{obj.type_name}，{len(info['heights'])} 部件）")
    env = dict(os.environ)
    if obj.type_name == "building":
        model = REPO / "tools" / "blender" / "models" / "building.py"
        env["MODEL_CONFIG"] = str(folder / "model.json")
        model_desc = "`tools/blender/models/building.py` + `model.json`"
    else:
        model = folder / "model.py"
        model_desc = "`model.py`"
    if REUSE_RENDER and (render_dir / "render.json").exists():
        print("  沿用既有的渲染結果")
    else:
        shutil.rmtree(render_dir, ignore_errors=True)
        run(["blender", "-b", "--factory-startup", "--python", "tools/blender/static_rig.py", "--",
             "--model", str(model), "--heights", heights, "--out", str(render_dir), "--size", str(cfg["size"]),
             "--samples", str(cfg.get("samples", 32))], env=env)
    # 來源檔：模型存成 .blend（AGENTS.md §2.3；所有部件並排，不渲染）
    run(["blender", "-b", "--factory-startup", "--python", "tools/blender/static_rig.py", "--",
         "--model", str(model), "--heights", heights, "--save-blend", str(folder / f"OG_{vanilla}.blend")], env=env)
    # 靜態 rig 有公司色遮罩，不用色鍵（避免一般顏色的雜訊被吸到 remap 色）
    run([PY, "tools/quantize.py", str(render_dir), "-o", str(sprites_dir), "--no-remap-colours"])
    if cfg.get("extra"):
        cfg["extra"](obj, info, sprites_dir)      # 產業：補上陰影／地面等 2D 影格
    out = folder / f"OG_{vanilla}.dat"
    pack = [PY, "tools/pack.py", "--template", str(tpl), "--sprites", str(sprites_dir), "--name", cfg["name"], "--relink",
            "--display", cfg["display"], "-o", str(out)]
    run(pack)
    (folder / ".gitkeep").unlink(missing_ok=True)
    fork_md = folder / "FORK.md"
    if not fork_md.exists():
        fork_md.write_text(FORK_MD.format(vanilla=vanilla, type_folder=cfg["folder"].split("/")[0], name=cfg["name"],
                                          display=cfg["display"], concept=cfg["concept"], model=model_desc),
                           encoding="utf-8")


REUSE_RENDER = False


def main() -> int:
    global REUSE_RENDER
    args = sys.argv[1:]
    if "--reuse-render" in args:                      # 只重新量化與打包（模型沒改時）
        REUSE_RENDER = True
        args.remove("--reuse-render")
    names = args or list(OBJECTS)
    for n in names:
        build(n, OBJECTS[n])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
