#!/usr/bin/env python3
"""Locomotion / OpenLoco 物件 DAT 讀寫工具（只用標準函式庫）。

格式依據 OpenLoco 原始碼（../OpenLoco/src/OpenLoco/）：
- 檔頭 16 bytes：flags(u32) + name(8) + checksum(u32)        Objects/Object.h `ObjectHeader`
- 接著一個 chunk：encoding(u8) + size(u32) + data             S5/SawyerStream.cpp
- checksum：seed 0xF369A75B，flags 第 1 byte、名稱、解碼後資料    Objects/ObjectManager.cpp
- 物件資料：固定結構 → 字串表 → 可變資料 → G1 image table（最後）

用法：
  python3 tools/dat.py info <file.dat>...
  python3 tools/dat.py verify <file.dat>...          # 驗證 checksum 與編碼往返
  python3 tools/dat.py extract <file.dat> -o <dir>   # 匯出 sprite PNG + sprites.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PALETTE_ACT = REPO_ROOT / "palettes" / "locopal.act"

# OpenLoco ObjectType enum 順序（Objects/Object.h）
OBJECT_TYPES = [
    "interfaceSkin", "sound", "currency", "steam", "cliffEdge", "water", "land",
    "townNames", "cargo", "wall", "trackSignal", "levelCrossing", "streetLight",
    "tunnel", "bridge", "trainStation", "trackExtra", "track", "roadStation",
    "roadExtra", "road", "airport", "dock", "vehicle", "tree", "snow", "climate",
    "hillShapes", "building", "scaffolding", "industry", "region", "competitor",
    "scenarioText",
]
SOURCE_GAMES = ["custom", "data", "vanilla", "openLoco"]

# 各類型固定結構大小（各 *Object.h 的 static_assert）
STRUCT_SIZES = {
    "airport": 0xBA, "bridge": 0x2C, "building": 0xBE, "cargo": 0x1F,
    "cliffEdge": 0x6, "climate": 0xA, "competitor": 0x38, "currency": 0xC,
    "dock": 0x28, "hillShapes": 0xE, "industry": 0xF4, "interfaceSkin": 0x18,
    "land": 0x1E, "levelCrossing": 0x12, "region": 0x12, "roadExtra": 0x12,
    "road": 0x30, "roadStation": 0x6E, "scaffolding": 0x12, "scenarioText": 0x6,
    "snow": 0x6, "sound": 0xC, "steam": 0x28, "streetLight": 0xC,
    "townNames": 0x1A, "trackExtra": 0x12, "track": 0x36, "trackSignal": 0x1E,
    "trainStation": 0xAE, "tree": 0x4C, "tunnel": 0x6, "vehicle": 0x15E,
    "wall": 0xA, "water": 0xE,
}

# 這些類型的 load() 不會呼叫 loadImageTable（以 OpenLoco Objects/*Object.cpp 確認）
TYPES_WITHOUT_IMAGES = {"sound", "climate", "scenarioText", "townNames"}

ENC_NONE, ENC_RLE_SINGLE, ENC_RLE_MULTI, ENC_ROTATE = 0, 1, 2, 3
CHECKSUM_SEED = 0xF369A75B

# G1ElementFlags（Graphics/Gfx.h）
G1_HAS_TRANSPARENCY = 1 << 0
G1_IS_RLE = 1 << 2
G1_IS_PALETTE = 1 << 3
G1_HAS_ZOOM = 1 << 4
G1_NO_ZOOM_DRAW = 1 << 5
G1_DUPLICATE_PREVIOUS = 1 << 6


# ---------------------------------------------------------------- chunk 編碼

def _rotl8(v: int, s: int) -> int:
    return ((v << s) | (v >> (8 - s))) & 0xFF


def _rotr8(v: int, s: int) -> int:
    return ((v >> s) | (v << (8 - s))) & 0xFF


def decode_rle_single(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        code = data[i]
        if code & 0x80:
            if i + 1 >= n:
                raise ValueError("invalid RLE")
            out += bytes([data[i + 1]]) * (257 - code)
            i += 2
        else:
            ln = code + 1
            if i + 1 + ln > n:
                raise ValueError("invalid RLE")
            out += data[i + 1:i + 1 + ln]
            i += 1 + ln
    return bytes(out)


def decode_rle_multi(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == 0xFF:
            if i + 1 >= n:
                raise ValueError("invalid RLE multi")
            out.append(data[i + 1])
            i += 2
        else:
            offset = (b >> 3) - 32
            if -offset > len(out):
                raise ValueError("invalid RLE multi back-reference")
            start = len(out) + offset
            for k in range((b & 7) + 1):
                out.append(out[start + k])
            i += 1
    return bytes(out)


def decode_rotate(data: bytes) -> bytes:
    out = bytearray(len(data))
    code = 1
    for i, b in enumerate(data):
        out[i] = _rotr8(b, code)
        code = (code + 2) & 7
    return bytes(out)


def encode_rle_single(data: bytes) -> bytes:
    """移植自 SawyerStreamWriter::encodeRunLengthSingle。"""
    out = bytearray()
    n = len(data)
    src = 0
    norm_start = 0
    count = 0
    while src < n - 1:
        if (count != 0 and data[src] == data[src + 1]) or count > 125:
            out.append((count - 1) & 0xFF)
            out += data[norm_start:norm_start + count]
            norm_start += count
            count = 0
        if data[src] == data[src + 1]:
            while count < 125 and src + count < n:
                if data[src] != data[src + count]:
                    break
                count += 1
            out.append((257 - count) & 0xFF)
            out.append(data[src])
            src += count
            norm_start = src
            count = 0
        else:
            count += 1
            src += 1
    if src == n - 1:
        count += 1
    if count != 0:
        out.append((count - 1) & 0xFF)
        out += data[norm_start:norm_start + count]
    return bytes(out)


def encode_rle_multi(data: bytes) -> bytes:
    """移植自 SawyerStreamWriter::encodeRunLengthMulti（之後還要再做一次 RLE single）。"""
    n = len(data)
    if n == 0:
        return b""
    out = bytearray([0xFF, data[0]])
    i = 1
    while i < n:
        search_index = 0 if i < 32 else i - 32
        search_end = i - 1
        best_index = best_count = 0
        for r in range(search_index, search_end + 1):
            max_count = min(7, search_end - r, n - i - 1)
            cnt = 0
            for j in range(max_count + 1):
                if data[r + j] == data[i + j]:
                    cnt += 1
                else:
                    break
            if cnt > best_count:
                best_index, best_count = r, cnt
                if cnt == 8:
                    break
        if best_count == 0:
            out += bytes([0xFF, data[i]])
            i += 1
        else:
            out.append(((best_count - 1) | ((32 - (i - best_index)) << 3)) & 0xFF)
            i += best_count
    return bytes(out)


def encode_rotate(data: bytes) -> bytes:
    out = bytearray(len(data))
    code = 1
    for i, b in enumerate(data):
        out[i] = _rotl8(b, code)
        code = (code + 2) & 7
    return bytes(out)


def decode_chunk(encoding: int, data: bytes) -> bytes:
    if encoding == ENC_NONE:
        return bytes(data)
    if encoding == ENC_RLE_SINGLE:
        return decode_rle_single(data)
    if encoding == ENC_RLE_MULTI:
        return decode_rle_multi(decode_rle_single(data))
    if encoding == ENC_ROTATE:
        return decode_rotate(data)
    raise ValueError(f"unknown encoding {encoding}")


def encode_chunk(encoding: int, data: bytes) -> bytes:
    if encoding == ENC_NONE:
        return bytes(data)
    if encoding == ENC_RLE_SINGLE:
        return encode_rle_single(data)
    if encoding == ENC_RLE_MULTI:
        return encode_rle_single(encode_rle_multi(data))
    if encoding == ENC_ROTATE:
        return encode_rotate(data)
    raise ValueError(f"unknown encoding {encoding}")


# ---------------------------------------------------------------- checksum

def _checksum_update(c: int, data: bytes) -> int:
    for b in data:
        c ^= b
        c = ((c << 11) | (c >> 21)) & 0xFFFFFFFF
    return c


def compute_checksum(flags: int, name: bytes, data: bytes) -> int:
    c = _checksum_update(CHECKSUM_SEED, bytes([flags & 0xFF]))
    c = _checksum_update(c, name)
    return _checksum_update(c, data)


# ---------------------------------------------------------------- 物件

@dataclass
class G1Entry:
    offset: int
    width: int
    height: int
    x_offset: int
    y_offset: int
    flags: int
    zoom_offset: int


@dataclass
class ImageTable:
    offset: int                 # 在物件資料中的起點
    entries: list[G1Entry]
    image_data: bytes


@dataclass
class DatObject:
    path: Path | None
    flags: int
    name: bytes
    checksum: int
    encoding: int
    data: bytes                 # 解碼後的物件資料
    raw_chunk: bytes = field(repr=False, default=b"")

    @property
    def type_id(self) -> int:
        return self.flags & 0x3F

    @property
    def type_name(self) -> str:
        t = self.type_id
        return OBJECT_TYPES[t] if t < len(OBJECT_TYPES) else f"unknown({t})"

    @property
    def source(self) -> int:
        return (self.flags >> 6) & 3

    @property
    def source_name(self) -> str:
        return SOURCE_GAMES[self.source]

    @property
    def name_str(self) -> str:
        return self.name.decode("latin1").rstrip(" ")

    def checksum_ok(self) -> bool:
        return compute_checksum(self.flags, self.name, self.data) == self.checksum

    def strings_offset(self) -> int | None:
        return STRUCT_SIZES.get(self.type_name)

    def display_name(self) -> str | None:
        """第一個字串表的第一個字串（通常是英文名稱）。"""
        off = self.strings_offset()
        if off is None or off >= len(self.data):
            return None
        d = self.data
        i = off
        first = None
        while i < len(d) and d[i] != 0xFF:
            lang = d[i]
            end = d.find(b"\x00", i + 1)
            if end < 0:
                return None
            s = d[i + 1:end].decode("latin1")
            if first is None or lang == 0:
                first = s
                if lang == 0:
                    break
            i = end + 1
        return first

    def image_table(self) -> ImageTable | None:
        if self.type_name in TYPES_WITHOUT_IMAGES:
            return None
        start = self.strings_offset() or 0
        return find_image_table(self.data, start)


def find_image_table(data: bytes, start: int = 0) -> ImageTable | None:
    """image table 一定在物件資料最後：找出 8 + 16n + totalSize 剛好等於剩餘長度的起點。
    start：從固定結構之後開始找（image table 不可能在固定結構裡）。"""
    n = len(data)
    candidates = []
    for off in range(start, n - 8 + 1):
        num, total = struct.unpack_from("<II", data, off)
        if num == 0 or num > 0x40000:
            continue
        if off + 8 + 16 * num + total == n:
            candidates.append(off)
    if not candidates:
        return None
    # 取最前面的合法候選（最完整的 table），並確認每個 entry 的 offset 都在範圍內
    for off in candidates:
        num, total = struct.unpack_from("<II", data, off)
        entries = []
        ok = True
        for k in range(num):
            e = G1Entry(*struct.unpack_from("<IhhhhHh", data, off + 8 + 16 * k))
            if e.offset > total or e.width < 0 or e.height < 0:
                ok = False
                break
            entries.append(e)
        if ok:
            img_start = off + 8 + 16 * num
            return ImageTable(off, entries, data[img_start:img_start + total])
    return None


def decode_sprite(table: ImageTable, index: int, zero_is_transparent: bool | None = None
                  ) -> tuple[int, int, int, int, bytearray, bytearray]:
    """回傳 (width, height, xOffset, yOffset, pixels, alpha)。pixels 為調色盤 index，alpha 0/255。

    zero_is_transparent（只影響非 RLE 的 bitmap）：
      None  依 hasTransparency flag 判斷（不套 remap 繪製時的行為）
      True  index 0 一律透明。OpenLoco 以公司色 remap 繪製（車輛等）時就是這樣，
            不論 flag（Graphics/DrawSprite.cpp getDrawBlendOp）。
    """
    e = table.entries[index]
    if e.flags & G1_DUPLICATE_PREVIOUS:
        if index == 0:
            raise ValueError("duplicatePrevious on first entry")
        w, h, x, y, px, al = decode_sprite(table, index - 1, zero_is_transparent)
        return w, h, x + e.x_offset, y + e.y_offset, px, al
    w, h = e.width, e.height
    px = bytearray(w * h)
    al = bytearray(w * h)
    src = table.image_data
    base = e.offset
    if w == 0 or h == 0:
        return w, h, e.x_offset, e.y_offset, px, al
    if e.flags & G1_IS_PALETTE:
        return 0, 0, e.x_offset, e.y_offset, bytearray(), bytearray()
    if e.flags & G1_IS_RLE:
        for row in range(h):
            p = base + struct.unpack_from("<H", src, base + row * 2)[0]
            while True:
                size = src[p]
                x0 = src[p + 1]
                end_of_line = size & 0x80
                size &= 0x7F
                run = src[p + 2:p + 2 + size]
                for k, v in enumerate(run):
                    xi = x0 + k
                    if 0 <= xi < w:
                        px[row * w + xi] = v
                        al[row * w + xi] = 255
                p += 2 + size
                if end_of_line:
                    break
    else:
        raw = src[base:base + w * h]
        px[:len(raw)] = raw
        transparent = bool(e.flags & G1_HAS_TRANSPARENCY) if zero_is_transparent is None else zero_is_transparent
        for k, v in enumerate(raw):
            al[k] = 0 if (transparent and v == 0) else 255
    return w, h, e.x_offset, e.y_offset, px, al


# ---------------------------------------------------------------- 修改物件資料

def parse_string_table(data: bytes, off: int) -> tuple[list[tuple[int, bytes]], int]:
    """解析一個字串表：[(language, text_bytes)...]，回傳 (entries, 結束位置)。"""
    entries = []
    i = off
    while data[i] != 0xFF:
        lang = data[i]
        end = data.index(b"\x00", i + 1)
        entries.append((lang, data[i + 1:end]))
        i = end + 1
    return entries, i + 1


def build_string_table(entries: list[tuple[int, bytes]]) -> bytes:
    return b"".join(bytes([lang]) + text + b"\x00" for lang, text in entries) + b"\xFF"


def replace_first_string_table(obj: DatObject, transform) -> bytes:
    """把第一個字串表（名稱）每個語言的字串以 transform(bytes)->bytes 改寫，回傳新的物件資料。"""
    off = obj.strings_offset()
    if off is None:
        raise ValueError(f"unknown struct size for {obj.type_name}")
    entries, end = parse_string_table(obj.data, off)
    new = build_string_table([(lang, transform(text)) for lang, text in entries])
    return obj.data[:off] + new + obj.data[end:]


def build_image_table(entries: list[G1Entry], image_data: bytes) -> bytes:
    out = struct.pack("<II", len(entries), len(image_data))
    for e in entries:
        out += struct.pack("<IhhhhHh", e.offset, e.width, e.height, e.x_offset, e.y_offset, e.flags, e.zoom_offset)
    return out + image_data


def replace_image_table(data: bytes, table_offset: int, entries: list[G1Entry], image_data: bytes) -> bytes:
    """image table 一定在最後，直接截斷後接上新的。"""
    return data[:table_offset] + build_image_table(entries, image_data)


def sound_data_offset(type_name: str, data: bytes) -> int:
    """音效物件中 SoundObjectData（0x1E bytes）的起點（Objects/SoundObject.cpp load）：
    固定結構 → 字串表 → numUnkStructs(u32) → pcmDataAndHeaderLength(u32) → numUnkStructs × 16 → SoundObjectData → PCM。"""
    _e, end = parse_string_table(data, STRUCT_SIZES[type_name])
    num_unk, = struct.unpack_from("<I", data, end)
    return end + 8 + 16 * num_unk


def og_internal_name(vanilla_name: str, prefix: str = "OG") -> bytes:
    """依 README 規則由 vanilla 名稱產生 8 字元內部名稱：保留結尾數字，從前面截斷。
    例：LIVESTCK→OGLIVEST、CATTLE1→OGCATTL1、BLDALP11→OGBLDA11。"""
    m = re.search(r"\d+$", vanilla_name)
    digits = m.group(0) if m else ""
    stem = vanilla_name[:len(vanilla_name) - len(digits)] if digits else vanilla_name
    room = 8 - len(prefix) - len(digits)
    name = prefix + stem[:max(room, 0)] + digits
    return name[:8].encode("latin1").ljust(8)


# ---------------------------------------------------------------- 讀寫檔案

def read_dat(path: str | os.PathLike) -> DatObject:
    p = Path(path)
    raw = p.read_bytes()
    if len(raw) < 21:
        raise ValueError(f"{p}: too small")
    flags, = struct.unpack_from("<I", raw, 0)
    name = raw[4:12]
    checksum, = struct.unpack_from("<I", raw, 12)
    enc = raw[16]
    size, = struct.unpack_from("<I", raw, 17)
    chunk = raw[21:21 + size]
    if len(chunk) != size:
        raise ValueError(f"{p}: truncated chunk")
    return DatObject(p, flags, name, checksum, enc, decode_chunk(enc, chunk), chunk)


def build_dat(flags: int, name: bytes, data: bytes, encoding: int = ENC_RLE_SINGLE) -> bytes:
    if len(name) != 8:
        raise ValueError("name must be exactly 8 bytes (pad with spaces)")
    checksum = compute_checksum(flags, name, data)
    chunk = encode_chunk(encoding, data)
    return struct.pack("<I", flags) + name + struct.pack("<I", checksum) + bytes([encoding]) + struct.pack("<I", len(chunk)) + chunk


def write_dat(path: str | os.PathLike, flags: int, name: bytes, data: bytes, encoding: int = ENC_RLE_SINGLE) -> None:
    Path(path).write_bytes(build_dat(flags, name, data, encoding))


# ---------------------------------------------------------------- PNG（索引色，標準函式庫）

def load_palette(path: Path = PALETTE_ACT) -> list[tuple[int, int, int]]:
    raw = path.read_bytes()[:768]
    return [tuple(raw[i:i + 3]) for i in range(0, 768, 3)]


def write_indexed_png(path: str | os.PathLike, w: int, h: int, pixels: bytes, alpha: bytes,
                      palette: list[tuple[int, int, int]]) -> None:
    """寫出 8-bit 索引色 PNG。透明像素寫成 index 0，並以 tRNS 讓 index 0 透明。"""
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        for x in range(w):
            k = y * w + x
            rows.append(pixels[k] if alpha[k] else 0)

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    plte = b"".join(bytes(c) for c in palette)
    trns = bytes([0]) + bytes([255] * 255)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", max(w, 1), max(h, 1), 8, 3, 0, 0, 0))
           + chunk(b"PLTE", plte) + chunk(b"tRNS", trns)
           + chunk(b"IDAT", zlib.compress(bytes(rows) if w and h else b"\x00\x00", 9))
           + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


# ---------------------------------------------------------------- CLI

def cmd_info(args) -> int:
    rc = 0
    for f in args.files:
        try:
            o = read_dat(f)
        except Exception as ex:  # noqa: BLE001
            print(f"{f}: ERROR {ex}")
            rc = 1
            continue
        t = o.image_table()
        print(f"{f}")
        print(f"  type={o.type_name}({o.type_id}) source={o.source_name}({o.source}) name={o.name_str!r}")
        print(f"  checksum=0x{o.checksum:08X} {'OK' if o.checksum_ok() else 'MISMATCH'} encoding={o.encoding} data={len(o.data)} bytes")
        print(f"  display_name={o.display_name()!r}")
        print(f"  images={len(t.entries) if t else 0}" + (f" (table @0x{t.offset:X}, image data {len(t.image_data)} bytes)" if t else ""))
    return rc


def cmd_verify(args) -> int:
    bad = 0
    total = 0
    for f in args.files:
        total += 1
        try:
            o = read_dat(f)
            problems = []
            if not o.checksum_ok():
                problems.append("checksum mismatch")
            if decode_chunk(o.encoding, encode_chunk(o.encoding, o.data)) != o.data:
                problems.append("encode/decode roundtrip mismatch")
        except Exception as ex:  # noqa: BLE001
            problems = [f"error: {ex}"]
        if problems:
            bad += 1
            print(f"FAIL {f}: {', '.join(problems)}")
        elif args.verbose:
            print(f"ok   {f}")
    print(f"verified {total} file(s): {total - bad} ok, {bad} failed")
    return 1 if bad else 0


def cmd_extract(args) -> int:
    o = read_dat(args.file)
    t = o.image_table()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if not t:
        print("no image table")
        return 0
    pal = load_palette()
    meta = []
    for i, e in enumerate(t.entries):
        w, h, x, y, px, al = decode_sprite(t, i)
        fn = f"{i}.png"
        write_indexed_png(out / fn, w, h, px, al, pal)
        meta.append({"path": fn, "x": x, "y": y, "zoomOffset": e.zoom_offset, "flags": e.flags, "name": None})
    (out / "sprites.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"extracted {len(meta)} sprite(s) to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info", help="顯示 DAT 檔頭、名稱、checksum、image 數")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_info)
    p = sub.add_parser("verify", help="驗證 checksum 與編碼往返")
    p.add_argument("files", nargs="+")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("extract", help="匯出 sprite PNG 與 sprites.json")
    p.add_argument("file")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_extract)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
