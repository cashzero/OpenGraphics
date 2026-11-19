#!/usr/bin/env python3
"""相依引用稽核：找出 DAT 內嵌的物件 header 引用，特別是指向 vanilla 的引用。

  python3 tools/deps.py                       # 摘要：被引用的 vanilla 物件與對應的 OG 版本
  python3 tools/deps.py --per-file            # 逐檔列出引用
  python3 tools/deps.py <file.dat>...         # 只看指定檔案
  python3 tools/deps.py --alias-json build/alias.json   # 產生 vanilla → OG 對照表（ROADMAP D1-A）
  python3 tools/deps.py --aliases-yml build/aliases.yml # OpenLoco fork 別名層用的 aliases.yml

方法：在解碼後的物件資料中，尋找「type byte + 8 字元名稱」符合已知物件的 16-byte header。
已知物件 = OpenLoco 的 vanilla 清單 + repo 內所有 DAT。屬於啟發式掃描，但名稱與類型
必須同時吻合，誤判機率很低。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import repo  # noqa: E402


def build_known(rdats, vanilla):
    """{type_id: {name_bytes: ("vanilla"|"og", name_str)}}"""
    known: dict[int, dict[bytes, tuple[str, str]]] = defaultdict(dict)
    for (name, typ) in vanilla:
        known[dat.OBJECT_TYPES.index(typ)][name.encode("latin1").ljust(8)] = ("vanilla", name)
    for rd in rdats:
        known[rd.obj.type_id][rd.obj.name] = ("og", rd.obj.name_str)
    return known


def scan_refs(obj: dat.DatObject, known) -> set[tuple[str, str, str]]:
    """回傳 {(kind, name, type)}。"""
    d = obj.data
    found = set()
    for m in range(len(d) - 12):
        t = d[m] & 0x3F
        names = known.get(t)
        if not names:
            continue
        nm = d[m + 4:m + 12]
        hit = names.get(nm)
        if hit and not (nm == obj.name and t == obj.type_id):
            found.add((hit[0], hit[1], dat.OBJECT_TYPES[t]))
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="只掃描這些 DAT（預設：repo 全部）")
    ap.add_argument("--per-file", action="store_true")
    ap.add_argument("--json", help="把完整結果寫成 JSON")
    ap.add_argument("--alias-json", help="寫出 vanilla → OG 對照表（JSON）")
    ap.add_argument("--aliases-yml", help="寫出 OpenLoco fork 別名層用的 aliases.yml（只含 repo 已有的 OG 物件）")
    args = ap.parse_args(argv)

    vanilla = repo.vanilla_objects()
    rdats = repo.repo_dats()
    known = build_known(rdats, vanilla)
    v2og = repo.vanilla_to_og(rdats, vanilla)

    if args.files:
        targets = [(Path(f), dat.read_dat(f)) for f in args.files]
    else:
        targets = [(rd.path, rd.obj) for rd in rdats]

    per_file = {}
    vanilla_ref_count: dict[tuple[str, str], int] = defaultdict(int)
    files_with_vanilla = 0
    for path, obj in targets:
        refs = scan_refs(obj, known)
        per_file[str(path)] = sorted(refs)
        vrefs = [r for r in refs if r[0] == "vanilla"]
        if vrefs:
            files_with_vanilla += 1
        for _k, n, t in vrefs:
            vanilla_ref_count[(n, t)] += 1

    if args.per_file:
        for f, refs in per_file.items():
            if not refs:
                continue
            print(f)
            for kind, n, t in refs:
                extra = ""
                if kind == "vanilla":
                    og = v2og.get((n, t))
                    extra = f"  → 已有 OG 版 {og[0]}" if og else "  → 尚無 OG 版"
                print(f"  {kind:7} {t:13} {n}{extra}")

    print(f"掃描 {len(targets)} 個 DAT；{files_with_vanilla} 個含有 vanilla 引用；"
          f"共引用 {len(vanilla_ref_count)} 個不同的 vanilla 物件。")
    have = [(k, c) for k, c in vanilla_ref_count.items() if k in v2og]
    missing = [(k, c) for k, c in vanilla_ref_count.items() if k not in v2og]
    print(f"  其中 {len(have)} 個已有 OG 版本（可由別名層或改指向解決），{len(missing)} 個尚無 OG 版本。")
    if not args.per_file:
        print("\n被引用最多的 vanilla 物件（引用次數｜OG 版本）：")
        for (n, t), c in sorted(vanilla_ref_count.items(), key=lambda x: -x[1])[:25]:
            og = v2og.get((n, t))
            print(f"  {c:4}  {t:13} {n:9} {'→ ' + og[0] if og else '（尚無 OG 版）'}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({
            "per_file": {f: [list(r) for r in refs] for f, refs in per_file.items()},
            "vanilla_ref_count": {f"{t}/{n}": c for (n, t), c in vanilla_ref_count.items()},
        }, indent=2, ensure_ascii=False) + "\n")
        print(f"寫出 {args.json}")
    if args.alias_json:
        table = [{"type": t, "vanilla": n, "og": og[0]} for (n, t), og in sorted(v2og.items(), key=lambda x: (x[0][1], x[0][0]))]
        Path(args.alias_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.alias_json).write_text(json.dumps(table, indent=2) + "\n")
        print(f"寫出 {args.alias_json}（{len(table)} 筆 vanilla → OG 對應）")
    if args.aliases_yml:
        n = repo.write_aliases_yml(args.aliases_yml, [(t, n, og[0]) for (n, t), og in v2og.items()])
        print(f"寫出 {args.aliases_yml}（{n} 筆）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
