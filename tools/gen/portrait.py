#!/usr/bin/env python3
"""競爭對手頭像（competitor 物件）：以 Pillow 畫向量卡通頭像（4 倍解析度繪製後縮小），量化到 Loco 調色盤。
背景是公司色漸層（primary remap，遊戲會換成該公司的顏色），不使用任何既有圖像。

  .venv/bin/python tools/gen/portrait.py --template <模板.DAT> --look '<JSON>' --seed 1 -o <資料夾>

影像（OpenLoco Objects/CompetitorObject.cpp）：依 emotions 位元（0 平常、1 高興、2 擔心、3 思考、4 沮喪、
5 驚訝、6 害怕、7 生氣、8 厭惡），每個有的表情 2 張：24×24（小）、64×64（大）。

--look 的欄位（都可省略，省略時依 seed 隨機）：
  gender: m|f、skin: 0–4（淺→深）、hair: bald|short|side|curly|long|bob|bun|quiff|crop、
  hair_colour: black|darkbrown|brown|blonde|red|grey|white、jacket: grey|navy|brown|green|maroon|beige、
  shirt: white|blue|cream、tie: red|blue|yellow|green|none、glasses: none|round|square、
  facial: none|moustache|beard|goatee、age: 0–2（皺紋）、face: 0.85–1.15（臉寬）
"""
from __future__ import annotations

import argparse
import json
import math
import random
import struct
import sys
from pathlib import Path

import common

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

SKIN = [(245, 208, 178), (228, 184, 146), (196, 142, 102), (150, 102, 70), (104, 70, 50)]
HAIR = {"black": (38, 32, 32), "darkbrown": (78, 50, 32), "brown": (128, 84, 48), "blonde": (222, 190, 112),
        "red": (176, 78, 38), "grey": (160, 160, 158), "white": (226, 226, 222)}
JACKET = {"grey": (70, 72, 80), "navy": (40, 52, 96), "brown": (96, 64, 42), "green": (62, 84, 52),
          "maroon": (104, 40, 48), "beige": (176, 154, 112)}
SHIRT = {"white": (236, 236, 232), "blue": (168, 198, 228), "cream": (236, 222, 184)}
TIE = {"red": (180, 30, 30), "blue": (40, 70, 170), "yellow": (220, 180, 40), "green": (40, 130, 60)}
PRIMARY_REMAP = [0x07, 0x08, 0x09] + list(range(0xF6, 0xFF))      # 公司色 12 階（暗 → 亮）
ALLOWED = list(range(0x0A, 0xCA)) + list(range(0xD6, 0xE2))           # 量化可用的一般色
EMOTIONS = ["neutral", "happy", "worried", "thinking", "dejected", "surprised", "scared", "angry", "disgusted"]


def darker(c, f=0.78):
    return tuple(int(v * f) for v in c)


def lighter(c, f=1.12):
    return tuple(min(255, int(v * f + 8)) for v in c)


def random_look(rng: random.Random, look: dict) -> dict:
    g = look.get("gender") or rng.choice("mf")
    out = {
        "gender": g,
        "skin": rng.randrange(5),
        "hair": rng.choice(["bald", "short", "side", "curly", "quiff", "crop"] if g == "m" else ["long", "bob", "bun", "curly", "side"]),
        "hair_colour": rng.choice(list(HAIR)),
        "jacket": rng.choice(list(JACKET)),
        "shirt": rng.choice(list(SHIRT)),
        "tie": rng.choice(list(TIE) + ["none"]) if g == "m" else "none",
        "glasses": rng.choice(["none", "none", "round", "square"]),
        "facial": rng.choice(["none", "none", "moustache", "beard", "goatee"]) if g == "m" else "none",
        "age": rng.randrange(3),
        "face": rng.uniform(0.9, 1.1),
    }
    if look:                                            # 有指定外觀時，沒寫的配件一律不加
        out.update({"glasses": "none", "facial": "none", "tie": "none", "age": 0})
    out.update(look)
    return out


def draw(look: dict, emotion: str, S: int, bold: float) -> tuple[Image.Image, Image.Image]:
    """回傳 (RGB 圖, 背景遮罩)。座標以 256 為基準縮放到 S。"""
    k = S / 256
    img = Image.new("RGB", (S, S), (0, 0, 0))
    mask = Image.new("L", (S, S), 255)
    d = ImageDraw.Draw(img)
    m = ImageDraw.Draw(mask)

    def P(*pts):
        return [(x * k, y * k) for x, y in pts]

    def ell(box, fill, md=True, outline=None, width=0):
        x0, y0, x1, y1 = box
        d.ellipse(P((x0, y0), (x1, y1)), fill=fill, outline=outline, width=int(width * k))
        if md:
            m.ellipse(P((x0, y0), (x1, y1)), fill=0)

    def poly(pts, fill, md=True):
        d.polygon(P(*pts), fill=fill)
        if md:
            m.polygon(P(*pts), fill=0)

    def line(pts, fill, w):
        d.line(P(*pts), fill=fill, width=max(1, int(w * k * bold)), joint="curve")

    def arc(box, start, end, fill, w):
        x0, y0, x1, y1 = box
        d.arc(P((x0, y0), (x1, y1)), start, end, fill=fill, width=max(1, int(w * k * bold)))

    skin = SKIN[look["skin"]]
    hair = HAIR[look["hair_colour"]]
    fw = 60 * look["face"]
    cx, top, bottom = 128, 42, 186
    dejected = emotion == "dejected"
    if dejected:
        top, bottom = top + 8, bottom + 8

    # 長髮（在頭後面）
    if look["hair"] in ("long", "bob"):
        hb = 236 if look["hair"] == "long" else 176
        poly([(cx - fw - 14, 90), (cx - fw - 18, hb), (cx + fw + 18, hb), (cx + fw + 14, 90)], hair)
        ell((cx - fw - 16, top - 10, cx + fw + 16, top + 120), hair)
    # 肩膀與外套
    jacket = JACKET[look["jacket"]]
    ell((6, 196, 250, 340), jacket)
    ell((22, 204, 120, 300), lighter(jacket, 1.08), md=False)
    shirt = SHIRT[look["shirt"]]
    if look["gender"] == "m":
        poly([(cx - 34, 198), (cx + 34, 198), (cx, 258)], shirt)
        if look["tie"] != "none":
            tie = TIE[look["tie"]]
            poly([(cx - 9, 214), (cx + 9, 214), (cx + 13, 256), (cx, 262), (cx - 13, 256)], tie)
            poly([(cx - 10, 202), (cx + 10, 202), (cx + 7, 216), (cx - 7, 216)], darker(tie, 0.85))
    else:
        ell((cx - 40, 192, cx + 40, 246), shirt)
        for a in range(-60, 61, 20):                       # 項鍊
            x = cx + math.sin(math.radians(a)) * 30
            y = 214 + math.cos(math.radians(a)) * 12
            ell((x - 3, y - 3, x + 3, y + 3), (230, 226, 210), md=False)
    # 脖子
    poly([(cx - 24, 150), (cx + 24, 150), (cx + 26, 206), (cx - 26, 206)], darker(skin, 0.82))
    # 耳朵
    ell((cx - fw - 12, 96 + (8 if dejected else 0), cx - fw + 10, 138 + (8 if dejected else 0)), darker(skin, 0.9))
    ell((cx + fw - 10, 96 + (8 if dejected else 0), cx + fw + 12, 138 + (8 if dejected else 0)), darker(skin, 0.86))
    if look["gender"] == "f":
        ell((cx - fw - 6, 134, cx - fw + 4, 144), (230, 200, 60), md=False)
        ell((cx + fw - 4, 134, cx + fw + 6, 144), (230, 200, 60), md=False)
    # 臉（光源左上：右側較暗）
    ell((cx - fw, top, cx + fw, bottom), darker(skin, 0.86))
    ell((cx - fw, top, cx + fw - 10, bottom - 6), skin, md=False)
    ell((cx - fw + 14, top + 18, cx - fw + 50, top + 60), lighter(skin, 1.06), md=False)
    # 頭髮（頂部）
    hs = look["hair"]
    if hs == "bald":
        ell((cx - fw - 4, 92, cx - fw + 12, 130), hair, md=False)
        ell((cx + fw - 12, 92, cx + fw + 4, 130), hair, md=False)
        ell((cx - fw + 20, top + 8, cx - fw + 56, top + 30), lighter(skin, 1.15), md=False)
    elif hs in ("short", "crop", "side", "quiff", "curly", "long", "bob", "bun"):
        thick = {"crop": 8, "short": 14, "side": 16, "quiff": 14, "curly": 22, "long": 18, "bob": 20, "bun": 14}[hs]
        # 髮量：包住頭頂與兩側（到耳朵上方）
        d.chord(P((cx - fw - 5, top - thick), (cx + fw + 5, top + 130)), 180, 360, fill=hair)
        m.chord(P((cx - fw - 5, top - thick), (cx + fw + 5, top + 130)), 180, 360, fill=0)
        # 額頭：弧形髮際線（旁分時髮際線偏一側）
        fx = {"side": 12, "quiff": -4}.get(hs, 0)
        fh = {"crop": 10, "short": 16, "side": 18, "quiff": 14, "curly": 26, "long": 30, "bob": 34, "bun": 18}[hs]
        d.ellipse(P((cx - fw + 9 + fx, top + fh), (cx + fw - 9 + fx, top + fh + 150)), fill=skin)
        d.ellipse(P((cx - fw + 18 + fx, top + fh + 10), (cx - fw + 54 + fx, top + fh + 46)), fill=lighter(skin, 1.06))
        if hs == "quiff":
            ell((cx - 40, top - thick - 18, cx + 30, top + 10), hair)
        if hs == "curly":
            for a in range(180, 361, 18):
                x = cx + math.cos(math.radians(a)) * (fw + 4)
                y = top + 48 + math.sin(math.radians(a)) * (thick + 44)
                ell((x - 14, y - 14, x + 14, y + 14), hair)
        if hs == "bun":
            ell((cx - 26, top - thick - 34, cx + 26, top - thick + 12), hair)
        hl = lighter(hair, 1.25)
        arc((cx - fw + 10, top - thick + 8, cx + fw - 30, top + 60), 200, 250, hl, 5)
    # 皺紋
    for a in range(look["age"]):
        arc((cx - 30, top + 22 + a * 9, cx + 30, top + 48 + a * 9), 200, 340, darker(skin, 0.75), 3)

    # ---- 表情 ----
    ey = 108 + (8 if dejected else 0)
    exl, exr = cx - 26, cx + 26
    brow = darker(hair, 0.9) if look["hair_colour"] not in ("white", "grey") else (110, 110, 110)
    eye_w, eye_h = 13, 8
    look_dx, look_dy = 0, 0
    lid = 0.0
    if emotion in ("surprised", "scared"):
        eye_w, eye_h = 15, 13
    if emotion == "angry":
        eye_h = 6
    if emotion == "disgusted":
        eye_h = 5
    if emotion == "thinking":
        look_dx, look_dy = -5, -4
    if emotion == "dejected":
        lid, look_dy = 0.55, 3
    if emotion == "worried":
        look_dx = 3
    for ex, side in ((exl, -1), (exr, 1)):
        if emotion == "happy":                               # 瞇眼笑
            arc((ex - eye_w, ey - 6, ex + eye_w, ey + 12), 200, 340, (40, 30, 30), 5)
        else:
            ell((ex - eye_w, ey - eye_h, ex + eye_w, ey + eye_h), (245, 245, 240), md=False)
            r = 6 if emotion != "scared" else 4
            ell((ex - r + look_dx, ey - r + look_dy, ex + r + look_dx, ey + r + look_dy), (50, 40, 35), md=False)
            if lid:
                d.chord(P((ex - eye_w - 1, ey - eye_h - 1), (ex + eye_w + 1, ey + eye_h + 1)), 180, 360, fill=darker(skin, 0.9))
        # 眉毛
        bx0, bx1 = ex - 16, ex + 16
        by = ey - 22
        inner, outer = by, by                               # 內側（靠鼻）／外側高度
        if emotion in ("angry",):
            inner, outer = by + 10, by - 4
        elif emotion in ("worried", "scared", "dejected"):
            inner, outer = by - 8, by + 4
        elif emotion == "surprised":
            inner = outer = by - 10
        elif emotion == "thinking":
            if side == 1:
                inner = outer = by - 10
        elif emotion == "disgusted":
            inner, outer = by + 6, by
        pts = [(bx0, outer), (bx1, inner)] if side == -1 else [(bx0, inner), (bx1, outer)]
        line(pts, brow, 7)
    # 眼鏡
    if look["glasses"] != "none":
        fr = (30, 30, 34)
        for ex in (exl, exr):
            box = (ex - 19, ey - 15, ex + 19, ey + 15)
            if look["glasses"] == "round":
                d.ellipse(P(box[:2], box[2:]), outline=fr, width=max(1, int(4 * k * bold)))
            else:
                d.rectangle(P(box[:2], box[2:]), outline=fr, width=max(1, int(4 * k * bold)))
        line([(exl + 19, ey - 2), (exr - 19, ey - 2)], fr, 4)
    # 鼻子
    ny = ey + 30
    poly([(cx - 2, ey + 4), (cx + 10, ny), (cx - 8, ny + 2)], darker(skin, 0.8), md=False)
    # 生氣：臉紅
    if emotion == "angry":
        ell((cx - fw + 8, ny - 6, cx - fw + 36, ny + 12), (210, 90, 80), md=False)
        ell((cx + fw - 36, ny - 6, cx + fw - 8, ny + 12), (190, 80, 70), md=False)
    # 鬍子
    my = ny + 24
    if look["facial"] in ("beard", "goatee"):
        if look["facial"] == "beard":
            d.chord(P((cx - fw + 2, my - 70), (cx + fw - 2, bottom + 14)), 0, 180, fill=hair)
        else:
            ell((cx - 16, my + 4, cx + 16, bottom + 8), hair, md=False)
    if look["facial"] in ("moustache", "beard"):
        poly([(cx - 26, my - 2), (cx, my - 10), (cx + 26, my - 2), (cx + 20, my + 4), (cx, my - 2), (cx - 20, my + 4)], hair, md=False)
    # 嘴
    lipc, dark = (150, 60, 60) if look["gender"] == "f" else darker(skin, 0.6), (60, 25, 25)
    mw = 22
    if emotion == "neutral":
        line([(cx - mw, my + 6), (cx + mw, my + 6)], lipc, 5)
    elif emotion == "happy":
        d.chord(P((cx - mw - 6, my - 14), (cx + mw + 6, my + 22)), 0, 180, fill=dark)
        d.chord(P((cx - mw, my - 10), (cx + mw, my + 8)), 0, 180, fill=(240, 240, 235))
    elif emotion == "worried":
        line([(cx - mw, my + 8), (cx - 8, my + 4), (cx + 8, my + 9), (cx + mw, my + 5)], lipc, 5)
    elif emotion == "thinking":
        line([(cx - 6, my + 8), (cx + mw, my + 4)], lipc, 5)
    elif emotion == "dejected":
        arc((cx - mw, my + 6, cx + mw, my + 30), 200, 340, lipc, 5)
    elif emotion == "surprised":
        ell((cx - 10, my - 4, cx + 10, my + 20), dark, md=False)
    elif emotion == "scared":
        d.rectangle(P((cx - mw, my), (cx + mw, my + 14)), fill=dark)
        d.rectangle(P((cx - mw + 3, my + 1), (cx + mw - 3, my + 6)), fill=(240, 240, 235))
    elif emotion == "angry":
        d.rectangle(P((cx - mw, my + 2), (cx + mw, my + 12)), fill=(240, 240, 235))
        line([(cx - mw, my + 2), (cx + mw, my + 2)], dark, 4)
        line([(cx - mw, my + 12), (cx + mw, my + 12)], dark, 4)
        line([(cx, my + 2), (cx, my + 12)], dark, 2)
    elif emotion == "disgusted":
        line([(cx - mw, my + 10), (cx - 4, my + 6), (cx + mw, my - 2)], lipc, 5)
        arc((cx - 16, ny - 12, cx + 4, ny + 4), 180, 300, darker(skin, 0.7), 3)
    return img, mask


_PAL_IMG = None


def quantize(img: Image.Image) -> bytes:
    global _PAL_IMG
    if _PAL_IMG is None:
        flat = []
        for i in range(256):
            r, g, b = common.PALETTE[i] if i in ALLOWED else (255, 0, 255)
            flat += [r, g, b]
        _PAL_IMG = Image.new("P", (1, 1))
        _PAL_IMG.putpalette(flat)
    q = img.quantize(palette=_PAL_IMG, dither=Image.Dither.NONE)
    return q.tobytes()


def render(look: dict, emotion: str, size: int) -> bytes:
    scale = 4 if size >= 64 else 10
    bold = 1.0 if size >= 64 else 1.7
    big, mask = draw(look, emotion, size * scale, bold)
    small = big.resize((size, size), Image.LANCZOS)
    msk = mask.resize((size, size), Image.BOX)
    idx = bytearray(quantize(small))
    mk = msk.tobytes()
    for y in range(size):
        shade = 10 - round(8 * y / (size - 1))                # 上亮下暗
        for x in range(size):
            if mk[y * size + x] >= 128:
                idx[y * size + x] = PRIMARY_REMAP[max(0, min(11, shade))]
    return bytes(idx)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--look", default="{}")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    obj = dat.read_dat(args.template)
    emotions = struct.unpack_from("<I", obj.data, 0x0C)[0]
    look = random_look(random.Random(args.seed), json.loads(args.look))
    frames = []
    for i, e in enumerate(EMOTIONS):
        if emotions & (1 << i):
            for size in (24, 64):
                frames.append((size, size, 0, 0, render(look, e, size)))
    if len(frames) != len(obj.image_table().entries):
        raise SystemExit(f"影像數不符：{len(frames)} vs 模板 {len(obj.image_table().entries)}")
    common.write_sprites(args.output, frames)
    print("外觀：" + json.dumps(look, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
