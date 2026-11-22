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


def _parts_block(d, p, nparts, nvar):
    heights = list(d[p:p + nparts]); p += nparts
    anims = [tuple(d[p + 2 * i:p + 2 * i + 2]) for i in range(nparts)]; p += 2 * nparts
    variations = []
    for _ in range(nvar):
        parts = []
        while d[p] != 0xFF:
            parts.append(d[p]); p += 1
        p += 1
        variations.append(parts)
    return heights, anims, variations, p


def dock(obj: dat.DatObject) -> dict:
    """碼頭（OpenLoco DockObject::load）：部件高度、動畫、變化（只有 1 種，2×2，從前方那格畫）。"""
    d = obj.data
    _e, p = dat.parse_string_table(d, dat.STRUCT_SIZES["dock"])
    heights, anims, variations, p = _parts_block(d, p, d[0x12], d[0x13])
    return {"heights": heights, "anims": anims, "variations": variations, "large": True,
            "has_shadows": bool(d[0x10] & 1), "boat": struct.unpack_from("<hh", d, 0x24)}


def airport(obj: dat.DatObject) -> dict:
    """機場（OpenLoco AirportObject::load）：sprite set（部件）高度與動畫、每種圖塊的部件堆疊、
    建築位置 (index, rotation, x, y)（以格為單位）、移動節點 (x, y, z, flags) 與邊。"""
    d = obj.data
    nsets, ntiles = d[0x12], d[0x13]
    _e, p = dat.parse_string_table(d, dat.STRUCT_SIZES["airport"])
    heights, anims, variations, p = _parts_block(d, p, nsets, ntiles)
    positions = []
    while d[p] != 0xFF:
        idx, rot, x, y = struct.unpack_from("<BBbb", d, p)
        positions.append((idx, rot, x, y)); p += 4
    p += 1
    nn, ne = d[0xAC], d[0xAD]
    nodes = [struct.unpack_from("<hhhH", d, p + 8 * i) for i in range(nn)]; p += 8 * nn
    edges = [struct.unpack_from("<BBBBII", d, p + 12 * i) for i in range(ne)]; p += 12 * ne
    large = struct.unpack_from("<I", d, 0xA0)[0]
    return {"heights": heights, "anims": anims, "variations": variations, "positions": positions,
            "nodes": nodes, "edges": edges, "large_mask": large,
            "large_tiles": [bool(large & (1 << i)) for i in range(ntiles)],
            "extent": struct.unpack_from("<bbbb", d, 0xA4), "flags": struct.unpack_from("<H", d, 0x10)[0],
            "years": struct.unpack_from("<HH", d, 0xA8)}
