#!/usr/bin/env python3
"""V1 自動檢查（AGENTS.md §2、docs/PIPELINE.md V1）。

  python3 tools/lint.py                 # 檢查整個 repo
  python3 tools/lint.py <file.dat>...   # 只檢查指定 DAT（repo 層級的重複檢查仍會執行）
  python3 tools/lint.py --strict        # 警告也視為失敗

錯誤（exit 1）：checksum 不符、type 與資料夾不符、source 不是 openLoco、名稱格式錯、
              (type, 名稱) 重複、同 Category 檔名重複（CI 攤平會互相覆蓋）、sprite 無法解碼。
警告：引用 vanilla 物件、placeholder 資料夾殘留 .gitkeep、*.blend1、fork 物件缺少 FORK.md 欄位。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import deps  # noqa: E402
import repo  # noqa: E402

NAME_RE = re.compile(rb"^(OG|EX)[A-Z0-9_]{0,6} *$")
FORK_REQUIRED_FIELDS = ["對應 vanilla", "內部名稱", "製作方式", "狀態"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--strict", action="store_true", help="警告也視為失敗")
    ap.add_argument("--quiet-vanilla", action="store_true", help="不逐一列出上游物件的 vanilla 引用")
    args = ap.parse_args(argv)

    errors: list[str] = []
    warnings: list[str] = []
    folders = repo.object_folders()
    rdats = repo.repo_dats(folders)
    targets = {Path(f).resolve() for f in args.files}
    selected = [rd for rd in rdats if not targets or rd.path.resolve() in targets]
    if targets and len(selected) != len(targets):
        known = {rd.path.resolve() for rd in rdats}
        for t in targets - known:
            # 不在 objects/ 底下的檔案（例如 build/dat/）也照樣檢查單檔項目
            f = repo.ObjectFolder(t.parent, "?", "?", [t.name], [t])
            selected.append(repo.RepoDat(t, f, dat.read_dat(t)))

    vanilla = repo.vanilla_objects()
    known = deps.build_known(rdats, vanilla)

    # ---- 單檔檢查
    vanilla_ref_files = 0
    for rd in selected:
        o, rel = rd.obj, rd.path
        if not o.checksum_ok():
            errors.append(f"{rel}: checksum 不符")
        if rd.folder.category != "?" and o.type_name != rd.folder.expected_type:
            errors.append(f"{rel}: type={o.type_name}，但資料夾是 {rd.folder.category}（預期 {rd.folder.expected_type}）")
        if o.source != 3:
            errors.append(f"{rel}: source={o.source_name}，應為 openLoco(3)")
        if not NAME_RE.match(o.name):
            errors.append(f"{rel}: 內部名稱 {o.name!r} 不符合 OG*/EX* 規則")
        t = o.image_table()
        if t:
            for i in range(len(t.entries)):
                try:
                    dat.decode_sprite(t, i)
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{rel}: sprite #{i} 無法解碼：{ex}")
                    break
        elif o.type_name not in dat.TYPES_WITHOUT_IMAGES:
            errors.append(f"{rel}: {o.type_name} 應該有 image table，但找不到")
        vrefs = sorted((n, ty) for kind, n, ty in deps.scan_refs(o, known) if kind == "vanilla")
        if vrefs:
            vanilla_ref_files += 1
            if rd.folder.state == "fork" or not args.quiet_vanilla:
                warnings.append(f"{rel}: 引用 {len(vrefs)} 個 vanilla 物件：" + ", ".join(f"{ty}/{n}" for n, ty in vrefs[:8])
                                + (" …" if len(vrefs) > 8 else ""))

    # ---- repo 層級檢查
    by_id = defaultdict(list)
    by_file = defaultdict(list)
    for rd in rdats:
        by_id[(rd.obj.type_id, rd.obj.name)].append(rd.path)
        by_file[(rd.folder.category, rd.path.name.lower())].append(rd.path)
    for (t, n), paths in by_id.items():
        if len(paths) > 1:
            errors.append(f"(type, 名稱) 重複 {dat.OBJECT_TYPES[t]}/{n.decode('latin1').strip()}: " + ", ".join(map(str, paths)))
    for (c, n), paths in by_file.items():
        if len(paths) > 1:
            errors.append(f"同 Category {c} 檔名重複 {n}（CI 攤平會覆蓋）: " + ", ".join(map(str, paths)))
    for f in folders:
        if ".gitkeep" in f.files and f.state != "placeholder":
            warnings.append(f"{f.rel}: 已有內容但還留著 .gitkeep")
        for n in f.files:
            if n.endswith(".blend1"):
                warnings.append(f"{f.rel}/{n}: Blender 備份檔不應 commit")
        if f.state == "fork":
            text = (f.path / "FORK.md").read_text(encoding="utf-8", errors="replace")
            for field in FORK_REQUIRED_FIELDS:
                if field not in text:
                    warnings.append(f"{f.rel}/FORK.md: 缺少欄位「{field}」")

    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"WARNING {w}")
    print(f"\n檢查 {len(selected)} 個 DAT、{len(folders)} 個資料夾：{len(errors)} 個錯誤、{len(warnings)} 個警告"
          f"（其中 {vanilla_ref_files} 個 DAT 引用 vanilla）")
    if errors or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
