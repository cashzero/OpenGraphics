#!/usr/bin/env python3
"""為還沒有 OG 版本的 vanilla 物件產生 placeholder DAT（docs/PIPELINE.md §6、ROADMAP D4 建議做法）。

  LOCO_DATA_DIR=$HOME/Locomotion/game python3 tools/make_placeholders.py [--out build/placeholders]

做法（以本機 vanilla DAT 為「結構模板」，產物只放 build/，絕不 commit）：
- 物件屬性與結構沿用 vanilla 模板；內部名稱依 README 規則改為 OG 名稱（撞名時改用備用規則）。
- 名稱字串加上前綴 "[PH] "，遊戲裡一眼看得出是 placeholder。
- 所有 sprite 換成純色方塊：只沿用模板的寬、高、偏移、張數（metadata），不使用 vanilla 的圖像或輪廓。
  方塊 = 深色外框 + 橘黃棋盤格；車輛／建築／產業另加一條 primary remap 帶（看得出公司色有沒有套用）。
- 音效物件的 PCM 換成靜音。
- 相依引用一律改指向 OG 名稱（上游已有的 OG 物件，或其他 placeholder），讓 placeholder 不再依賴 vanilla。
輸出：<out>/objects/<Category>/OG_<NAME>.dat，以及 <out>/manifest.json（vanilla → OG 名稱對照）。
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402
import deps  # noqa: E402
import repo  # noqa: E402

PH_PREFIX = b"[PH] "
# 調色盤 index（Graphics/Colour.h）
C_BORDER = 0x0C        # black2
C_A = 0xB2 + 6         # orange6
C_B = 0x2E + 8         # yellow8
C_REMAP = 0xF9         # primaryRemap6

TYPE_FOLDER = {t: t[:1].upper() + t[1:] for t in dat.OBJECT_TYPES}
TYPE_FOLDER["trackSignal"] = "TrainSignal"


# 只有這些類型在遊戲中以公司色／隨機色 remap 繪製；其他類型若用 remap index 會畫出原始的粉紅色
REMAP_TYPES = {"vehicle", "building", "industry"}


def placeholder_pixels(w: int, h: int, remap_band: bool = True) -> bytes:
    px = bytearray(w * h)
    band_top, band_bottom = h * 2 // 5, h * 3 // 5
    for y in range(h):
        for x in range(w):
            if w < 3 or h < 3 or x in (0, w - 1) or y in (0, h - 1):
                c = C_BORDER
            elif remap_band and band_top <= y < band_bottom and h >= 6:
                c = C_REMAP
            else:
                c = C_A if ((x // 4) + (y // 4)) % 2 == 0 else C_B
            px[y * w + x] = c
    return bytes(px)


def placeholder_images(table: dat.ImageTable, remap_band: bool = True) -> tuple[list[dat.G1Entry], bytes]:
    entries = []
    data = bytearray()
    cache: dict[tuple[int, int], int] = {}
    for e in table.entries:
        if e.flags & dat.G1_DUPLICATE_PREVIOUS:
            entries.append(dat.G1Entry(0, e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset))
            continue
        key = (e.width, e.height)
        if key not in cache:
            cache[key] = len(data)
            data += placeholder_pixels(max(e.width, 0), max(e.height, 0), remap_band)
        keep = e.flags & (dat.G1_HAS_ZOOM | dat.G1_NO_ZOOM_DRAW)
        entries.append(dat.G1Entry(cache[key], e.width, e.height, e.x_offset, e.y_offset,
                                   keep | dat.G1_HAS_TRANSPARENCY, e.zoom_offset))
    return entries, bytes(data)


def silence_sound(obj: dat.DatObject, data: bytes) -> bytes:
    off = obj.strings_offset()
    _entries, end = dat.parse_string_table(data, off)
    hdr = end + 8                                   # unknown u32 + pcmDataAndHeaderLength u32
    length, = struct.unpack_from("<I", data, hdr + 8)
    bits, = struct.unpack_from("<H", data, hdr + 12 + 14)
    pcm_start = hdr + 0x1E
    fill = b"\x80" if bits == 8 else b"\x00"
    return data[:pcm_start] + fill * length + data[pcm_start + length:]


def relink(data: bytes, known_vanilla: dict[int, set[bytes]], v2og: dict[tuple[bytes, int], bytes]) -> tuple[bytes, int, set[str]]:
    """把資料中的 vanilla header 引用改指向 OG 名稱。回傳 (新資料, 改了幾處, 找不到 OG 版的名稱)。"""
    d = bytearray(data)
    changed = 0
    unresolved: set[str] = set()
    for m in range(len(d) - 12):
        t = d[m] & 0x3F
        names = known_vanilla.get(t)
        if not names:
            continue
        nm = bytes(d[m + 4:m + 12])
        if nm not in names:
            continue
        og = v2og.get((nm, t))
        if og is None:
            unresolved.add(f"{dat.OBJECT_TYPES[t]}/{nm.decode('latin1').strip()}")
            continue
        d[m + 4:m + 12] = og
        d[m] = (d[m] & 0x3F) | (3 << 6)        # source = openLoco
        changed += 1
    return bytes(d), changed, unresolved


def unique_name(vanilla_name: str, typ: int, used: set[tuple[int, bytes]]) -> bytes:
    cands = [dat.og_internal_name(vanilla_name)]
    stem = vanilla_name.rstrip("0123456789")
    digits = vanilla_name[len(stem):]
    room = 6 - len(digits)
    if len(stem) > room > 1:
        cands.append(("OG" + stem[:room - 1] + stem[-1] + digits).encode("latin1").ljust(8))
        consonants = stem[0] + "".join(c for c in stem[1:] if c not in "AEIOU")
        cands.append(("OG" + consonants[:room] + digits).encode("latin1").ljust(8))
    for k in range(1, 36):
        cands.append(("OG" + stem[:max(room - 1, 1)] + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[k] + digits)[:8].encode("latin1").ljust(8))
    for c in cands:
        if (typ, c) not in used:
            return c
    raise RuntimeError(f"no unique name for {vanilla_name}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(repo.REPO_ROOT / "build" / "placeholders"))
    ap.add_argument("--loco-data", default=os.environ.get("LOCO_DATA_DIR"))
    args = ap.parse_args(argv)
    if not args.loco_data or not (Path(args.loco_data) / "ObjData").is_dir():
        sys.exit("需要 vanilla 資料：設定 LOCO_DATA_DIR 或 --loco-data（見 docs/PIPELINE.md）")

    out = Path(args.out)
    vanilla = repo.in_scope_vanilla()
    rdats = repo.repo_dats()
    v2og_repo = repo.vanilla_to_og(rdats, vanilla)

    # vanilla 模板：(name, type) → path
    templates = {}
    for f in (Path(args.loco_data) / "ObjData").iterdir():
        try:
            o = dat.read_dat(f)
        except Exception:  # noqa: BLE001
            continue
        templates[(o.name_str, o.type_name)] = f

    used = {(rd.obj.type_id, rd.obj.name) for rd in rdats}
    todo = sorted(k for k in vanilla if k not in v2og_repo)
    names: dict[tuple[str, str], bytes] = {}
    for (n, t) in todo:
        typ = dat.OBJECT_TYPES.index(t)
        nm = unique_name(n, typ, used)
        used.add((typ, nm))
        names[(n, t)] = nm

    # 完整對照：上游 OG + placeholder
    v2og: dict[tuple[bytes, int], bytes] = {}
    for (n, t), (og, _t) in v2og_repo.items():
        v2og[(n.encode("latin1").ljust(8), dat.OBJECT_TYPES.index(t))] = og.encode("latin1").ljust(8)
    for (n, t), nm in names.items():
        v2og[(n.encode("latin1").ljust(8), dat.OBJECT_TYPES.index(t))] = nm
    known_vanilla: dict[int, set[bytes]] = {}
    for (n, t) in vanilla:
        known_vanilla.setdefault(dat.OBJECT_TYPES.index(t), set()).add(n.encode("latin1").ljust(8))

    manifest = []
    made = 0
    missing_template = []
    all_unresolved: set[str] = set()
    for (n, t) in todo:
        tpl_path = templates.get((n, t))
        if tpl_path is None:
            missing_template.append(f"{t}/{n}")
            continue
        tpl = dat.read_dat(tpl_path)
        data = dat.replace_first_string_table(tpl, lambda s: PH_PREFIX + s)
        obj = dat.DatObject(None, tpl.flags, tpl.name, 0, tpl.encoding, data)
        if t == "sound":
            data = silence_sound(obj, data)
        table = dat.find_image_table(data, obj.strings_offset() or 0) if t not in dat.TYPES_WITHOUT_IMAGES else None
        if table:
            entries, img = placeholder_images(table, t in REMAP_TYPES)
            data = dat.replace_image_table(data, table.offset, entries, img)
        data, _changed, unresolved = relink(data, known_vanilla, v2og)
        all_unresolved |= unresolved
        nm = names[(n, t)]
        flags = (tpl.flags & ~0xC0) | (3 << 6)
        dst = out / "objects" / TYPE_FOLDER[t] / f"OG_{n}.dat"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dat.write_dat(dst, flags, nm, data, dat.ENC_RLE_SINGLE)
        chk = dat.read_dat(dst)
        assert chk.checksum_ok()
        ct = chk.image_table()
        if ct:
            for i in range(len(ct.entries)):
                dat.decode_sprite(ct, i)
        manifest.append({"type": t, "vanilla": n, "og": nm.decode("latin1").strip(), "file": str(dst.relative_to(out))})
        made += 1

    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # 完整的 vanilla → OG 對照（上游 + placeholder），給 relink 與別名層使用
    alias = [{"type": dat.OBJECT_TYPES[t], "vanilla": n.decode("latin1").strip(), "og": og.decode("latin1").strip()}
             for (n, t), og in sorted(v2og.items(), key=lambda x: (x[0][1], x[0][0]))]
    (out / "alias.json").write_text(json.dumps(alias, indent=2) + "\n")
    repo.write_aliases_yml(out / "aliases.yml", [(a["type"], a["vanilla"], a["og"]) for a in alias])
    print(f"產生 {made} 個 placeholder → {out / 'objects'}")
    print(f"對照表：{out / 'manifest.json'}（placeholder）、{out / 'alias.json'} 與 {out / 'aliases.yml'}（全部 {len(alias)} 筆 vanilla → OG）")
    if missing_template:
        print(f"找不到 vanilla 模板：{', '.join(missing_template)}")
    if all_unresolved:
        print(f"仍有無法改指向的 vanilla 引用（沒有 OG 版也沒有 placeholder）：{', '.join(sorted(all_unresolved))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
