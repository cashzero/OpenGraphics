#!/usr/bin/env python3
"""物件盤點：每個 vanilla 物件類型的完成狀態。

  python3 tools/inventory.py            # 依類型列出 已完成／fork 自製／placeholder／缺資料夾
  python3 tools/inventory.py --list placeholder    # 列出所有 placeholder 資料夾
  python3 tools/inventory.py --json build/inventory.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", choices=["placeholder", "fork", "upstream", "missing"])
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    folders = repo.object_folders()
    vanilla = repo.in_scope_vanilla()
    by_name: dict[str, list[repo.ObjectFolder]] = defaultdict(list)
    for f in folders:
        by_name[f.base_name].append(f)
        for d in f.dats:
            by_name[d.stem.upper().replace("OGE_", "").replace("OG_", "").replace("OSE_", "")].append(f)

    status: dict[tuple[str, str], str] = {}
    where: dict[tuple[str, str], str] = {}
    rank = {"upstream": 3, "fork": 2, "placeholder": 1, "other": 0}
    for key in vanilla:
        name, typ = key
        cands = [f for f in by_name.get(name, []) if f.expected_type == typ and not f.pack.endswith("Expansion")]
        if not cands:
            status[key] = "missing"
            continue
        best = max(cands, key=lambda f: rank[f.state])
        status[key] = best.state
        where[key] = best.rel

    table: dict[str, Counter] = defaultdict(Counter)
    for (name, typ), st in status.items():
        table[typ][st] += 1
    print(f"{'type':14} {'total':>5} {'done':>5} {'fork':>5} {'todo':>5} {'miss':>5}")
    tot = Counter()
    for typ in sorted(table):
        c = table[typ]
        total = sum(c.values())
        tot.update(c)
        tot["total"] += total
        print(f"{typ:14} {total:5} {c['upstream']:5} {c['fork']:5} {c['placeholder']:5} {c['missing']:5}")
    print(f"{'TOTAL':14} {tot['total']:5} {tot['upstream']:5} {tot['fork']:5} {tot['placeholder']:5} {tot['missing']:5}")
    exp = Counter(f.state for f in folders if f.pack.endswith("Expansion"))
    print(f"\n擴充包（非 vanilla 替代）資料夾：{sum(exp.values())}（上游 {exp['upstream']}、fork {exp['fork']}）")
    print(f"不在範圍內：{', '.join(sorted(repo.OUT_OF_SCOPE))}")

    if args.list:
        print()
        for (name, typ), st in sorted(status.items(), key=lambda x: (x[0][1], x[0][0])):
            if st == args.list:
                print(f"{typ:14} {name:9} {where.get((name, typ), '')}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(
            [{"type": t, "vanilla": n, "status": s, "folder": where.get((n, t))} for (n, t), s in sorted(status.items())],
            indent=2) + "\n")
        print(f"寫出 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
