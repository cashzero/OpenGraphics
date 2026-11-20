"""repo 掃描共用函式：物件資料夾狀態、vanilla 清單、vanilla ↔ OG 對應。"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import dat

REPO_ROOT = Path(__file__).resolve().parent.parent
OBJECTS_DIR = REPO_ROOT / "objects"
OPENLOCO_OBJECT_CPP = REPO_ROOT.parent / "OpenLoco" / "src" / "OpenLoco" / "src" / "Objects" / "Object.cpp"

# 資料夾名稱 → ObjectType（大多是首字母小寫，例外列在這裡）
FOLDER_TYPE_EXCEPTIONS = {"TrainSignal": "trackSignal"}

# 不在專案範圍內的 vanilla 物件（見 docs/ROADMAP.md）
OUT_OF_SCOPE = {"AIRPORT4", "HPORT2", "SHINKT0", "SHINKF0"}


def folder_type(category: str) -> str:
    return FOLDER_TYPE_EXCEPTIONS.get(category, category[:1].lower() + category[1:])


@dataclass
class ObjectFolder:
    path: Path
    pack: str
    category: str               # objects/<pack>/<category>/…
    files: list[str]
    dats: list[Path] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(REPO_ROOT))

    @property
    def expected_type(self) -> str:
        return folder_type(self.category)

    @property
    def state(self) -> str:
        if set(self.files) == {".gitkeep"}:
            return "placeholder"
        if "FORK.md" in self.files:
            return "fork"
        if self.dats:
            return "upstream"
        return "other"

    @property
    def base_name(self) -> str:
        """資料夾對應的 vanilla 名稱（去掉 OG_/OGE_ 前綴）。"""
        return re.sub(r"^(OGE_|OG_|OSE_)", "", self.path.name).upper()


def object_folders() -> list[ObjectFolder]:
    out = []
    for dirpath, _dirs, files in os.walk(OBJECTS_DIR):
        if not files:
            continue
        p = Path(dirpath)
        parts = p.relative_to(OBJECTS_DIR).parts
        if len(parts) < 3:
            continue
        f = ObjectFolder(p, parts[0], parts[1], sorted(files))
        f.dats = sorted(p / n for n in files if n.lower().endswith(".dat"))
        out.append(f)
    return sorted(out, key=lambda x: x.rel)


def vanilla_objects() -> dict[tuple[str, str], str]:
    """{(name, type): 說明}。依序讀：OpenLoco 原始碼的 _vanillaObjects、docs/vanilla-objects.json、LOCO_DATA_DIR/ObjData。"""
    result: dict[tuple[str, str], str] = {}
    if OPENLOCO_OBJECT_CPP.exists():
        src = OPENLOCO_OBJECT_CPP.read_text(encoding="utf-8", errors="replace")
        for name, typ, desc in re.findall(r'\{\s*"([^"]{8})",\s*ObjectType::(\w+)\s*\},?\s*(?://\s*"([^"]*)")?', src):
            result[(name.rstrip(), typ)] = desc
        if result:
            return result
    # CI 等沒有 OpenLoco 原始碼的環境：讀 repo 內的清單（由 OpenLoco 原始碼匯出的 metadata）
    listed = REPO_ROOT / "docs" / "vanilla-objects.json"
    if listed.exists():
        import json
        for o in json.loads(listed.read_text(encoding="utf-8"))["objects"]:
            result[(o["name"], o["type"])] = o.get("desc", "")
        if result:
            return result
    loco = os.environ.get("LOCO_DATA_DIR")
    if loco and (Path(loco) / "ObjData").is_dir():
        for f in (Path(loco) / "ObjData").iterdir():
            try:
                o = dat.read_dat(f)
            except Exception:  # noqa: BLE001
                continue
            result[(o.name_str, o.type_name)] = o.display_name() or ""
    return result


def in_scope_vanilla() -> dict[tuple[str, str], str]:
    return {k: v for k, v in vanilla_objects().items() if k[0] not in OUT_OF_SCOPE}


@dataclass
class RepoDat:
    path: Path
    folder: ObjectFolder
    obj: dat.DatObject


def repo_dats(folders: list[ObjectFolder] | None = None) -> list[RepoDat]:
    out = []
    for f in folders or object_folders():
        for p in f.dats:
            out.append(RepoDat(p, f, dat.read_dat(p)))
    return out


def vanilla_to_og(rdats: list[RepoDat], vanilla: dict[tuple[str, str], str]) -> dict[tuple[str, str], tuple[str, str]]:
    """vanilla (name, type) → 取代它的 OG 物件 (name, type)。依資料夾名稱或 DAT 檔名對應。"""
    mapping = {}
    for rd in rdats:
        if rd.folder.pack.endswith("Expansion"):
            continue
        typ = rd.obj.type_name
        candidates = {rd.folder.base_name,
                      re.sub(r"^(OGE_|OG_|OSE_)", "", rd.path.stem).upper()}
        for c in candidates:
            if (c, typ) in vanilla:
                mapping[(c, typ)] = (rd.obj.name_str, typ)
    return mapping


def write_aliases_yml(path, rows) -> int:
    """寫出 OpenLoco fork 別名層讀取的 aliases.yml。rows：[(type_name, vanilla_name, og_name)]。"""
    rows = sorted(set(rows), key=lambda r: (dat.OBJECT_TYPES.index(r[0]), r[1]))
    lines = [
        "# vanilla 物件 → OpenGraphics 物件的別名表（OpenLoco fork 的 ObjectAliases 讀取）",
        "# 由 OpenGraphics 的 tools 自動產生，請勿手改。每列：[ObjectType 數值, vanilla 名稱, OG 名稱]",
        "aliases:",
    ]
    for typ, vanilla, og in rows:
        lines.append(f'  - [{dat.OBJECT_TYPES.index(typ)}, "{vanilla}", "{og}"]  # {typ}')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)
