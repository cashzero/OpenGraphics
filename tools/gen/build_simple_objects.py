#!/usr/bin/env python3
"""建置 M2 的程序化物件（貨幣、氣候、平交道警示牌、蒸汽／排氣／火花、音效、號誌、樹、region）。

  LOCO_DATA_DIR=$HOME/Locomotion/game .venv/bin/python tools/gen/build_simple_objects.py [名稱…]

每個物件：用 tools/gen/ 的產生器在物件資料夾內產生 PNG + sprites.json（或 WAV）→ tools/pack.py 以
vanilla 物件為結構模板打包成 OG_<名稱>.dat → 刪除 .gitkeep → 寫 FORK.md（已存在就不覆蓋）。
模板只提供結構、屬性與其他字串；所有圖像與聲音都是新產生的。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "bin" / "python")
LOCO = Path(os.environ.get("LOCO_DATA_DIR", str(Path.home() / "Locomotion" / "game")))
VR = REPO / "objects" / "VanillaReplacements"

# vanilla 名稱 → 設定
OBJECTS = {
    "CURRDOLL": dict(folder="Currency/CURRDOLL", name="OGCURRDO", display="Dollar",
                     gen=["currency.py", "--symbol", "$", "--coins", "3"],
                     concept="硬幣堆與錢幣符號的介面圖示，以文字色（text remap）繪製，介面會套用文字顏色。"
                             "顯示名稱用單數 Dollar，與 vanilla 的 Dollars 區分（AGENTS.md §2.1）；貨幣符號等其他字串沿用模板。"),
    "CLIM3": dict(folder="Climate/CLIM3", name="OGCLIM3", display="Continental Climate",
                  sets=["u8@3=60", "u8@4=78", "u8@5=98", "u8@6=81", "u8@7=46", "u8@8=70"],
                  concept="大陸型氣候：季節長度改為 60/78/98/81 天（總天數不變），冬季雪線 46、夏季雪線 70。沒有圖片。"),
    "LCROSS4": dict(folder="LevelCrossing/LCROSS4", name="OGLCROS4", display="Crossbuck Signs",
                    gen=["lcross_signs.py"],
                    concept="木柱上的 X 形白底紅邊警示牌；正面組看得到 X 形牌，側面組只看到牌子厚度。"),
    "STEAM": dict(folder="Steam/STEAM", name="OGSTEAM", display="Steam Cloud",
                  gen=["steam.py", "--style", "steam", "--seed", "11"],
                  concept="淺灰白的蒸汽團，逐格變大、上亮下暗，最後消散。"),
    "EXH1": dict(folder="Steam/EXH1", name="OGEXH1", display="Diesel Fumes",
                 gen=["steam.py", "--style", "exhaust", "--seed", "21"],
                 concept="深灰柴油排氣團，逐格變大後消散。"),
    "EXH2": dict(folder="Steam/EXH2", name="OGEXH2", display="Heavy Diesel Fumes",
                 gen=["steam.py", "--style", "exhaust", "--seed", "22"],
                 concept="與 OG_EXH1 同類但雜訊不同的較濃排氣團。"),
    "SPARK1": dict(folder="Steam/SPARK1", name="OGSPARK1", display="Pantograph Spark",
                   gen=["steam.py", "--style", "spark", "--seed", "31"],
                   concept="集電弓的藍白電弧火花，稀疏亮點逐格擴散。"),
    "SNDTR1": dict(folder="Sound/SNDTR1", name="OGSNDTR1", display="Rail Joint Clatter",
                   wav=["--kind", "track", "--seconds", "2.14", "--seed", "41"],
                   concept="鋼軌接縫的喀噠聲節奏加低頻隆隆聲，循環音效。"),
    "SNDE1": dict(folder="Sound/SNDE1", name="OGSNDE1", display="Electric Motor Hum",
                  wav=["--kind", "electric", "--seconds", "1.0", "--seed", "42"],
                  concept="電動機嗡嗡聲與高頻嘯音，頻率取整數週期，循環無接縫。"),
    "SNDS1": dict(folder="Sound/SNDS1", name="OGSNDS1", display="Steam Idle Hiss",
                  wav=["--kind", "steam_idle", "--seconds", "1.95", "--seed", "43"],
                  concept="蒸汽洩壓的嘶嘶聲，緩慢起伏，循環音效。"),
    "SNDW7": dict(folder="Sound/SNDW7", name="OGSNDW7", display="Chime Whistle",
                  wav=["--kind", "whistle", "--seconds", "1.23", "--seed", "44", "--pitch", "1.0"],
                  concept="大三和弦汽笛，含起音與尾音。"),
    "SNDW8": dict(folder="Sound/SNDW8", name="OGSNDW8", display="Short High Whistle",
                  wav=["--kind", "whistle", "--seconds", "0.65", "--seed", "45", "--pitch", "1.33"],
                  concept="較高音、較短的和弦汽笛。"),
    "SIGS": dict(folder="TrainSignal/SIGS", name="OGSIGS", display="Upper Arm Semaphore",
                 gen=["signal.py"],
                 concept="灰色號誌柱配紅色臂板（末端白條紋）與燈號；8 個視角，動畫逐格把臂板揚起（上象限式）。"),
    "OAK": dict(folder="Tree/OAK", name="OGOAK", display="Broad Oak",
                gen=["tree.py", "--style", "deciduous", "--leaf", "green", "--seed", "51"],
                concept="寬闊圓冠的闊葉樹：夏季翠綠、春季淡綠稀疏、秋季橘紅黃混色、冬季光禿；含陰影。"),
    "BEECH": dict(folder="Tree/BEECH", name="OGBEECH", display="Forest Beech",
                  gen=["tree.py", "--style", "deciduous", "--leaf", "darkgreen", "--seed", "53"],
                  concept="深綠樹冠的闊葉樹，四季變化同 OG_OAK，樹冠形狀不同；含陰影。"),
    "BIRCH": dict(folder="Tree/BIRCH", name="OGBIRCH", display="White Birch",
                  gen=["tree.py", "--style", "deciduous", "--leaf", "birch", "--trunk", "light", "--seed", "54"],
                  concept="淺色樹幹、黃綠色樹冠的闊葉樹，四季變化；含陰影。"),
    "SCPINE": dict(folder="Tree/SCPINE", name="OGSCPINE", display="Highland Pine",
                   gen=["tree.py", "--style", "conifer", "--leaf", "darkgreen", "--seed", "52"],
                   concept="分層圓錐形的深綠針葉樹，含積雪版（枝葉上緣覆雪）、枯萎版與陰影；兩個旋轉角度。"),
    "RFIR": dict(folder="Tree/RFIR", name="OGRFIR", display="Mountain Fir",
                 gen=["tree.py", "--style", "conifer", "--leaf", "green", "--seed", "55"],
                 concept="綠色分層針葉樹，含積雪版、枯萎版與陰影。"),
    "QPALM": dict(folder="Tree/QPALM", name="OGQPALM", display="Coastal Palm",
                  gen=["tree.py", "--style", "palm", "--seed", "56"],
                  concept="微彎樹幹、七片下垂葉的棕櫚樹；含陰影。"),
    "REGUK": dict(folder="Region/REGUK", name="OGREGUK", display="British Isles",
                  gen=["region_image.py", "--seed", "61", "--scene", "industry:COALMINE@84,58", "tree:SCPINE@14,70:1", "building:BLDHOUS7@36,78",
                       "building:BLDHOUS2@72,98", "tree:OAK@102,104:1"],
                  pack=["--og-only-will-load"],
                  concept="英國地區：沿用 vanilla REGUK 的結構與 cargo 設定，但選取時一併載入的物件（willLoad）"
                          "只保留已有 OG 版本的項目，開新遊戲不會帶進 placeholder。預覽圖由本 repo 的 OG 房屋、樹與礦井 sprite 拼成。"),
    "CACTUS1": dict(folder="Tree/CACTUS1", name="OGCACTU1", display="Desert Cactus",
                    gen=["tree.py", "--style", "cactus", "--seed", "57"],
                    concept="三柱式仙人掌，兩側分枝；四個旋轉角度、六個成長階段；含陰影。"),
}

FORK_MD = """# OG_{vanilla}（fork 自製）
- 對應 vanilla：{vanilla}（{type_folder}）
- 內部名稱：{name}
- 遊戲內名稱：{display}
- 設計概念：{concept}
- 製作方式：程序化產生（`tools/gen/build_simple_objects.py {vanilla}`），產生器與參數記錄在該腳本中；以 vanilla {vanilla} 為結構模板（`tools/pack.py`），只沿用結構、屬性與其他字串
- AI 工具：Claude（撰寫產生器程式與參數）
- 參考資料：無外部素材；vanilla 只用於 sprite 尺寸、偏移與張數
- 狀態：v1-passed
- 待改指向的 vanilla 引用：無（或由別名層處理）

## 驗證紀錄
- 2026-11-19 V1：`tools/lint.py` 0 錯誤；contact sheet 已檢視
"""


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"失敗：{' '.join(cmd)}")
    for line in (r.stdout.strip().splitlines()[-1:] if r.stdout.strip() else []):
        print("  " + line)


def build(vanilla: str, cfg: dict) -> None:
    folder = VR / cfg["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    template = LOCO / "ObjData" / f"{vanilla}.DAT"
    out = folder / f"OG_{vanilla}.dat"
    print(f"== {vanilla} → {out.relative_to(REPO)}")
    pack = [PY, "tools/pack.py", "--template", str(template), "--name", cfg["name"], "--relink", "-o", str(out)]
    if cfg.get("display"):
        pack += ["--display", cfg["display"]]
    pack += cfg.get("pack", [])
    for s in cfg.get("sets", []):
        pack += ["--set", s]
    if "gen" in cfg:
        run([PY, f"tools/gen/{cfg['gen'][0]}", "--template", str(template), *cfg["gen"][1:], "-o", str(folder)])
        pack += ["--sprites", str(folder)]
    if "wav" in cfg:
        wav = folder / f"OG_{vanilla}.wav"
        run([PY, "tools/gen/sound.py", *cfg["wav"], "-o", str(wav)])
        pack += ["--wav", str(wav)]
    run(pack)
    (folder / ".gitkeep").unlink(missing_ok=True)
    fork_md = folder / "FORK.md"
    if not fork_md.exists():
        fork_md.write_text(FORK_MD.format(vanilla=vanilla, type_folder=cfg["folder"].split("/")[0], name=cfg["name"],
                                          display=cfg.get("display") or "（沿用模板）", concept=cfg["concept"]),
                           encoding="utf-8")


def main() -> int:
    names = sys.argv[1:] or list(OBJECTS)
    for n in names:
        build(n, OBJECTS[n])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
