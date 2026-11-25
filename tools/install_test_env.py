#!/usr/bin/env python3
"""組出 V2 遊戲內驗證用的 OpenLoco 隔離環境（docs/PIPELINE.md V2）。

  python3 tools/install_test_env.py [--env build/openloco-env] [--with-placeholders] [--relink]

產生：
  <env>/data/language -> OpenLoco build 的 data/language（symlink）
  <env>/data/objects/    本 repo 的物件（+ placeholder），取代 build 內建的上游 v0.1.12 物件
  <env>/data/base/       （--with-base）standalone 用的基礎資料，結構同 Locomotion 安裝目錄（Data/g1.DAT…）
  <env>/OpenLoco/        使用者目錄（XDG_CONFIG_HOME=<env>），每次清掉物件索引快取 plugin.dat
執行 OpenLoco 時設定 OPENLOCO_DATA_DIR=<env>/data、XDG_CONFIG_HOME=<env>（見 PIPELINE.md）。

--with-placeholders：repo 沒有的物件用 build/placeholders/objects/ 補上（先跑 make_placeholders.py）。
--relink：把**測試副本**中的 vanilla 引用依 build/placeholders/alias.json 改指向 OG 名稱。
          repo 內的檔案不會被修改。使用 OpenLoco fork 的別名層時不需要。
另外一律寫出 data/objects/aliases.yml，供 fork 的別名層使用。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import make_placeholders  # noqa: E402
import repo  # noqa: E402

OPENLOCO_DATA = repo.REPO_ROOT.parent / "OpenLoco" / "build" / "posix" / "Release" / "data"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=str(repo.REPO_ROOT / "build" / "openloco-env"))
    ap.add_argument("--with-placeholders", action="store_true")
    ap.add_argument("--placeholders", default=str(repo.REPO_ROOT / "build" / "placeholders"))
    ap.add_argument("--relink", action="store_true")
    ap.add_argument("--with-base", action="store_true",
                    help="把 build/placeholders/base/（g1.DAT 等）與 base/music/、base/sfx/ 的音訊放進 data/base/，供 standalone 模式使用")
    ap.add_argument("--openloco-data", default=str(OPENLOCO_DATA), help="OpenLoco build 的 data 目錄（取 language）")
    args = ap.parse_args(argv)

    env = Path(args.env).resolve()
    data_dir = env / "data"
    obj_dir = data_dir / "objects"
    user_dir = env / "OpenLoco"
    if obj_dir.exists():
        shutil.rmtree(obj_dir)
    obj_dir.mkdir(parents=True)
    user_objects = user_dir / "objects"
    if user_objects.exists():
        shutil.rmtree(user_objects)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "plugin.dat").unlink(missing_ok=True)
    lang = data_dir / "language"
    if not lang.exists() and not lang.is_symlink():
        os.symlink(Path(args.openloco_data) / "language", lang)

    relink_ctx = None
    if args.relink:
        alias_path = Path(args.placeholders) / "alias.json"
        if not alias_path.exists():
            sys.exit(f"找不到 {alias_path}（先執行 tools/make_placeholders.py）")
        alias = json.loads(alias_path.read_text())
        v2og = {(a["vanilla"].encode("latin1").ljust(8), dat.OBJECT_TYPES.index(a["type"])): a["og"].encode("latin1").ljust(8)
                for a in alias}
        known: dict[int, set[bytes]] = {}
        for (n, t) in v2og:
            known.setdefault(t, set()).add(n)
        relink_ctx = (known, v2og)

    taken: set[tuple[int, bytes]] = set()
    stats = {"repo": 0, "placeholder": 0, "relinked_refs": 0}
    unresolved: set[str] = set()

    def install(src: Path, obj: dat.DatObject, kind: str):
        if relink_ctx:
            data, changed, unres = make_placeholders.relink(obj.data, *relink_ctx)
            unresolved.update(unres)
            if changed:
                stats["relinked_refs"] += changed
                dat.write_dat(obj_dir / src.name, obj.flags, obj.name, data, obj.encoding)
                stats[kind] += 1
                return
        shutil.copy2(src, obj_dir / src.name)
        stats[kind] += 1

    for rd in repo.repo_dats():
        key = (rd.obj.type_id, rd.obj.name)
        if key in taken:
            continue
        install(rd.path, rd.obj, "repo")
        taken.add(key)

    if args.with_placeholders:
        ph = Path(args.placeholders) / "objects"
        if not ph.is_dir():
            sys.exit(f"找不到 placeholder：{ph}（先執行 tools/make_placeholders.py）")
        for f in sorted(ph.rglob("*.dat")):
            o = dat.read_dat(f)
            if (o.type_id, o.name) in taken:
                continue
            install(f, o, "placeholder")
            taken.add((o.type_id, o.name))

    # OpenLoco fork 別名層：aliases.yml（只列出這個環境裡真的有的 OG 物件）
    rows = [(t, n, og[0]) for (n, t), og in repo.vanilla_to_og(repo.repo_dats(), repo.vanilla_objects()).items()]
    if args.with_placeholders:
        manifest = json.loads((Path(args.placeholders) / "manifest.json").read_text())
        rows += [(m["type"], m["vanilla"], m["og"]) for m in manifest]
    n_alias = repo.write_aliases_yml(obj_dir / "aliases.yml", rows)
    print(f"別名表：{obj_dir / 'aliases.yml'}（{n_alias} 筆）")

    base_dst = data_dir / "base"
    if base_dst.exists():
        shutil.rmtree(base_dst)
    if args.with_base:
        base_src = Path(args.placeholders) / "base"
        if not (base_src / "Data" / "g1.DAT").exists():
            sys.exit(f"找不到 {base_src / 'Data' / 'g1.DAT'}（先執行 .venv/bin/python tools/g1.py build -o {base_src / 'Data' / 'g1.DAT'}）")
        shutil.copytree(base_src, base_dst)
        print(f"standalone base：{base_dst}")
        import music  # noqa: E402（M5：OpenMSX MIDI + SoundFont + 曲名）
        music.install(base_dst / "Data", music.load())
        import sfx  # noqa: E402（M5：OpenSFX 音效 bank 與環境音）
        sfx.install(base_dst / "Data", sfx.load())
        import title  # noqa: E402（M6：標題畫面地圖與鏡頭清單；還沒 build 時略過）
        title.install(base_dst / "Data")

    print(f"安裝到 {obj_dir}：repo 物件 {stats['repo']} 個、placeholder {stats['placeholder']} 個"
          + (f"；測試副本中改指向 {stats['relinked_refs']} 個 vanilla 引用" if args.relink else ""))
    if unresolved:
        print("仍引用 vanilla（沒有對應）：" + ", ".join(sorted(unresolved)))
    print(f"執行時設定：OPENLOCO_DATA_DIR={data_dir} XDG_CONFIG_HOME={env}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
