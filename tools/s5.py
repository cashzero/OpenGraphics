#!/usr/bin/env python3
"""S5 存檔／情境（.SV5/.SC5）工具。

  python3 tools/s5.py info <file>                        # 檔頭與必要物件清單
  python3 tools/s5.py info <file> --origin [--max-placeholders N]
      依類型統計必要物件來自 repo（objects/）還是 placeholder（build/placeholders/），
      placeholder 超過 N 個（或有找不到來源的物件）時以 1 結束。
  python3 tools/s5.py relink <in> -o <out> --alias build/placeholders/alias.json
      把必要物件清單中的 vanilla 物件改指向 OG 名稱，產生「只用 OG 物件」的測試存檔。
      地圖資料以物件 slot index 引用物件，所以只換清單裡的 header 即可。

格式依據 OpenLoco S5/S5.cpp：chunk 依序為 header、(saveDetails)、(scenario options)、
packed objects（16-byte header + chunk）、requiredObjects（rotate 編碼的 ObjectHeader 陣列）、遊戲狀態…；
檔尾 4 bytes 為前面所有 bytes 的總和。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dat  # noqa: E402

S5_TYPES = {0: "savedGame", 1: "scenario", 2: "objects", 3: "landscape"}
FLAG_HAS_SAVE_DETAILS = 1 << 3
EMPTY_HEADER = b"\xff" * 16


@dataclass
class Chunk:
    start: int      # 在檔案中的位置（encoding byte）
    encoding: int
    raw: bytes      # 編碼後資料


def read_chunk(buf: bytes, pos: int) -> tuple[Chunk, int]:
    enc = buf[pos]
    size, = struct.unpack_from("<I", buf, pos + 1)
    return Chunk(pos, enc, buf[pos + 5:pos + 5 + size]), pos + 5 + size


def locate(buf: bytes) -> dict:
    """回傳 header 資訊與 requiredObjects chunk 的位置。"""
    header_chunk, pos = read_chunk(buf, 0)
    hdr = dat.decode_chunk(header_chunk.encoding, header_chunk.raw)
    s5type, flags, num_packed = hdr[0], hdr[1], struct.unpack_from("<H", hdr, 2)[0]
    if flags & FLAG_HAS_SAVE_DETAILS:
        _c, pos = read_chunk(buf, pos)
    if s5type == 1:
        _c, pos = read_chunk(buf, pos)
    packed = []
    for _ in range(num_packed):
        packed.append(buf[pos:pos + 16])
        _c, pos = read_chunk(buf, pos + 16)
    req, _end = read_chunk(buf, pos)
    return {"type": s5type, "flags": flags, "packed": packed, "required": req}


def required_headers(info: dict) -> list[bytes]:
    data = dat.decode_chunk(info["required"].encoding, info["required"].raw)
    return [data[i:i + 16] for i in range(0, len(data), 16)]


def file_checksum_ok(buf: bytes) -> bool:
    return (sum(buf[:-4]) & 0xFFFFFFFF) == struct.unpack_from("<I", buf, len(buf) - 4)[0]


def _names_in(root: Path) -> set[tuple[int, str]]:
    out = set()
    for p in root.rglob("*"):
        if p.suffix.lower() == ".dat" and p.is_file():
            try:
                o = dat.read_dat(p)
            except Exception:  # noqa: BLE001  非物件 DAT（例如 g1）
                continue
            out.add((o.type_id, o.name_str.strip()))
    return out


def origin_report(heads: list[bytes], max_placeholders: int | None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    in_repo = _names_in(repo_root / "objects")
    in_ph = _names_in(repo_root / "build" / "placeholders") - in_repo
    by_type: dict[str, list] = {}
    n_ph = n_other = 0
    for h in heads:
        t, name = h[0] & 0x3F, h[4:12].decode("latin1").strip()
        row = by_type.setdefault(dat.OBJECT_TYPES[t], [0, [], []])
        if (t, name) in in_repo:
            row[0] += 1
        elif (t, name) in in_ph:
            row[1].append(name)
            n_ph += 1
        else:
            row[2].append(name)
            n_other += 1
    for t, (r, ph, other) in sorted(by_type.items()):
        extra = f"  placeholder：{' '.join(ph)}" if ph else ""
        extra += f"  來源不明：{' '.join(other)}" if other else ""
        print(f"  {t:14} repo {r:3}｜placeholder {len(ph):3}{extra}")
    print(f"合計 {len(heads)} 個物件：repo {len(heads) - n_ph - n_other}、placeholder {n_ph}、來源不明 {n_other}")
    if n_other or (max_placeholders is not None and n_ph > max_placeholders):
        return 1
    return 0


def cmd_info(args) -> int:
    buf = Path(args.file).read_bytes()
    info = locate(buf)
    heads = [h for h in required_headers(info) if h != EMPTY_HEADER]
    print(f"{args.file}: type={S5_TYPES.get(info['type'], info['type'])} packed={len(info['packed'])} "
          f"required={len(heads)} checksum={'OK' if file_checksum_ok(buf) else 'MISMATCH'}")
    if args.verbose:
        for h in heads:
            print(f"  {dat.OBJECT_TYPES[h[0] & 0x3F]:13} {h[4:12].decode('latin1').strip():9} source={(h[0] >> 6) & 3}")
    if args.origin:
        return origin_report(heads, args.max_placeholders)
    return 0


def cmd_relink(args) -> int:
    buf = Path(args.file).read_bytes()
    info = locate(buf)
    alias = {(a["type"], a["vanilla"]): a["og"] for a in json.loads(Path(args.alias).read_text())}
    heads = required_headers(info)
    out_heads = []
    changed = 0
    unmapped = []
    for h in heads:
        if h == EMPTY_HEADER:
            out_heads.append(h)
            continue
        t = h[0] & 0x3F
        name = h[4:12].decode("latin1").strip()
        if ((args.types and dat.OBJECT_TYPES[t] not in args.types) or dat.OBJECT_TYPES[t] in (args.exclude_types or [])
                or (args.names and name not in args.names)):
            out_heads.append(h)
            continue
        og = alias.get((dat.OBJECT_TYPES[t], name))
        if og is None:
            unmapped.append(f"{dat.OBJECT_TYPES[t]}/{name}")
            out_heads.append(h)
            continue
        flags = struct.unpack_from("<I", h, 0)[0]
        flags = (flags & ~0xC0) | (3 << 6)
        out_heads.append(struct.pack("<I", flags) + og.encode("latin1").ljust(8) + h[12:16])
        changed += 1
    req = info["required"]
    new_raw = dat.encode_chunk(req.encoding, b"".join(out_heads))
    body = (buf[:req.start] + bytes([req.encoding]) + struct.pack("<I", len(new_raw)) + new_raw
            + buf[req.start + 5 + len(req.raw):len(buf) - 4])
    out = body + struct.pack("<I", sum(body) & 0xFFFFFFFF)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_bytes(out)
    print(f"relink：{changed} 個物件改指向 OG，{len(unmapped)} 個沒有對應 → {args.output}")
    if unmapped:
        print("  沒有對應：" + ", ".join(unmapped))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info")
    p.add_argument("file")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--origin", action="store_true", help="統計物件來自 repo 還是 placeholder")
    p.add_argument("--max-placeholders", type=int, help="搭配 --origin：placeholder 超過此數量就以 1 結束")
    p.set_defaults(func=cmd_info)
    p = sub.add_parser("relink")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--alias", required=True, help="vanilla → OG 對照表（make_placeholders.py 產生的 alias.json）")
    p.add_argument("--types", nargs="*", help="只改指向這些物件類型（用來二分搜尋問題物件）")
    p.add_argument("--exclude-types", nargs="*", help="不改指向這些物件類型")
    p.add_argument("--names", nargs="*", help="只改指向這些 vanilla 物件名稱")
    p.set_defaults(func=cmd_relink)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
