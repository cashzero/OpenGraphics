"""解析模板物件中與建模有關的結構（部件高度、變化組合等）。格式依 OpenLoco Objects/*Object.cpp 的 load()。"""
from __future__ import annotations

import struct

import dat


def building(obj: dat.DatObject) -> dict:
    d = obj.data
    nparts, nvar = d[6], d[7]
    _e, p = dat.parse_string_table(d, dat.STRUCT_SIZES["building"])
    heights = list(d[p:p + nparts]); p += nparts
    anims = [tuple(d[p + 2 * i:p + 2 * i + 2]) for i in range(nparts)]; p += 2 * nparts
    variations = []
    for _ in range(nvar):
        parts = []
        while d[p] != 0xFF:
            parts.append(d[p]); p += 1
        p += 1
        variations.append(parts)
    return {"heights": heights, "anims": anims, "variations": variations, "large": bool(d[0x98] & 1)}


def industry(obj: dat.DatObject) -> dict:
    d = obj.data
    nparts, nvar = d[0x1E], d[0x1F]
    flags = struct.unpack_from("<I", d, 0xE4)[0]
    p = dat.STRUCT_SIZES["industry"]
    for _ in range(8):
        _e, p = dat.parse_string_table(d, p)
    heights = list(d[p:p + nparts]); p += nparts
    anims = [tuple(d[p + 2 * i:p + 2 * i + 2]) for i in range(nparts)]; p += 2 * nparts
    for _ in range(4):
        p += 1 + d[p]
    while d[p] != 0xFF:
        p += 2
    p += 1
    variations = []
    for _ in range(nvar):
        parts = []
        while d[p] != 0xFF:
            parts.append(d[p]); p += 1
        p += 1
        variations.append(parts)
    has_shadows = bool(flags & (1 << 21))
    return {"heights": heights, "anims": anims, "variations": variations, "flags": flags,
            "has_shadows": has_shadows, "size_flags": struct.unpack_from("<I", d, 0xC6)[0],
            "first_part_image": (nvar * 4 if has_shadows else 0), "num_part_images": nparts * 4}
