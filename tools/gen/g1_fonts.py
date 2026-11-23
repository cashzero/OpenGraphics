#!/usr/bin/env python3
"""g1 的 4 套字型（ROADMAP M4）：自製點陣字形，輸出到 base/g1/fonts/<字型>/（PNG + sprites.json）。

  .venv/bin/python tools/gen/g1_fonts.py [--sheet build/preview/g1_fonts.png]

字形設計：
- medium（一般）與 small 為手繪點陣（本檔的 MEDIUM／SMALL）；medium 粗體由一般體水平加粗；
  large（報紙標題用）由 medium 粗體放大 1.5 倍。重音字母由基本字母 + 重音符號自動組合。
- OpenLoco 以 text palette 換色（TextRenderer.cpp）：index 1 = 主色（永遠畫）；index 2 = 外框（只在 outline 樣式）；
  index 3 = 外框，inset（停用文字）樣式時是較淺的浮雕色。所以字形 = 主筆畫（1）+ 右下陰影（3）+ 其餘一圈外框（2），
  影像四周各留 1 px 給外框。
- 前進寬度 = 影像寬 + 修正（medium／small −1、large +1；Gfx.cpp initialiseCharacterWidths）→ 字距 1 px。
- 字元編碼依 OpenLoco Localisation/Conversion.h（LocoChar）：35 = £、96 = ‘、34 = ”、180 = “、186 = •、
  160／170／175／190 = ▲▼▶◀、188／189 = 小 ▲▼、172 = ✓、173 = ✗、177／182／183／184 = 鐵路／公路／航空／水運、
  波蘭文字母佔用 Æ Ð × Ø Ý Þ æ ð ÷ ø ý þ 的位置；123–158、168、174、179、255 不使用（OpenLoco 把 123–150 的寬度設為 0）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dat  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "docs" / "g1-catalog.json"
OUT = REPO / "base" / "g1" / "fonts"
INK, RING, SHADOW = 1, 2, 3


def G(top, *rows):
    """字形：top = 第一列在格線上的列號（medium：0 = 大寫頂、7 = 基線、8–9 下伸；small：0 = 大寫頂、4 = 基線、5 下伸）。"""
    return (top, [r.replace(".", " ") for r in rows])


# ---------------------------------------------------------------- medium（大寫 8 列、x 高 6 列、下伸 2 列）
MEDIUM = {
    "A": G(0, " ### ", "#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": G(0, "#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#   #", "#### "),
    "C": G(0, " ### ", "#   #", "#    ", "#    ", "#    ", "#    ", "#   #", " ### "),
    "D": G(0, "###  ", "#  # ", "#   #", "#   #", "#   #", "#   #", "#  # ", "###  "),
    "E": G(0, "#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    ", "#####"),
    "F": G(0, "#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    ", "#    "),
    "G": G(0, " ### ", "#   #", "#    ", "#    ", "# ###", "#   #", "#   #", " ####"),
    "H": G(0, "#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #", "#   #"),
    "I": G(0, "#", "#", "#", "#", "#", "#", "#", "#"),
    "J": G(0, "    #", "    #", "    #", "    #", "    #", "#   #", "#   #", " ### "),
    "K": G(0, "#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #", "#   #"),
    "L": G(0, "#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": G(0, "#     #", "##   ##", "# # # #", "#  #  #", "#     #", "#     #", "#     #", "#     #"),
    "N": G(0, "#   #", "##  #", "##  #", "# # #", "# # #", "#  ##", "#  ##", "#   #"),
    "O": G(0, " ### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": G(0, "#### ", "#   #", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": G(0, " ### ", "#   #", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": G(0, "#### ", "#   #", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": G(0, " ### ", "#   #", "#    ", " ### ", "    #", "    #", "#   #", " ### "),
    "T": G(0, "#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": G(0, "#   #", "#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": G(0, "#   #", "#   #", "#   #", "#   #", " # # ", " # # ", " # # ", "  #  "),
    "W": G(0, "#     #", "#     #", "#     #", "#  #  #", "#  #  #", "# # # #", "##   ##", "#     #"),
    "X": G(0, "#   #", "#   #", " # # ", "  #  ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": G(0, "#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": G(0, "#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#    ", "#####"),
    "a": G(2, " ### ", "    #", " ####", "#   #", "#   #", " ####"),
    "b": G(0, "#    ", "#    ", "#### ", "#   #", "#   #", "#   #", "#   #", "#### "),
    "c": G(2, " ### ", "#   #", "#    ", "#    ", "#   #", " ### "),
    "d": G(0, "    #", "    #", " ####", "#   #", "#   #", "#   #", "#   #", " ####"),
    "e": G(2, " ### ", "#   #", "#####", "#    ", "#   #", " ### "),
    "f": G(0, "  ##", " #  ", " #  ", "####", " #  ", " #  ", " #  ", " #  "),
    "g": G(2, " ####", "#   #", "#   #", "#   #", " ####", "    #", "#   #", " ### "),
    "h": G(0, "#    ", "#    ", "#### ", "#   #", "#   #", "#   #", "#   #", "#   #"),
    "i": G(0, "#", " ", "#", "#", "#", "#", "#", "#"),
    "j": G(0, "  #", "   ", "  #", "  #", "  #", "  #", "  #", "  #", "  #", "## "),
    "k": G(0, "#   ", "#   ", "#  #", "# # ", "##  ", "# # ", "#  #", "#  #"),
    "l": G(0, "#", "#", "#", "#", "#", "#", "#", "#"),
    "m": G(2, "### ## ", "#  #  #", "#  #  #", "#  #  #", "#  #  #", "#  #  #"),
    "n": G(2, "#### ", "#   #", "#   #", "#   #", "#   #", "#   #"),
    "o": G(2, " ### ", "#   #", "#   #", "#   #", "#   #", " ### "),
    "p": G(2, "#### ", "#   #", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "q": G(2, " ####", "#   #", "#   #", "#   #", " ####", "    #", "    #", "    #"),
    "r": G(2, "# ##", "##  ", "#   ", "#   ", "#   ", "#   "),
    "s": G(2, " ####", "#    ", " ### ", "    #", "    #", "#### "),
    "t": G(1, " #  ", "####", " #  ", " #  ", " #  ", " #  ", "  ##"),
    "u": G(2, "#   #", "#   #", "#   #", "#   #", "#   #", " ####"),
    "v": G(2, "#   #", "#   #", "#   #", " # # ", " # # ", "  #  "),
    "w": G(2, "#     #", "#     #", "#  #  #", "#  #  #", "# # # #", " #   # "),
    "x": G(2, "#   #", " # # ", "  #  ", "  #  ", " # # ", "#   #"),
    "y": G(2, "#   #", "#   #", "#   #", "#   #", " ####", "    #", "#   #", " ### "),
    "z": G(2, "#####", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "0": G(0, " ### ", "#   #", "#  ##", "# # #", "# # #", "##  #", "#   #", " ### "),
    "1": G(0, " # ", "## ", " # ", " # ", " # ", " # ", " # ", "###"),
    "2": G(0, " ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    "3": G(0, " ### ", "#   #", "    #", "  ## ", "    #", "    #", "#   #", " ### "),
    "4": G(0, "   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # ", "   # "),
    "5": G(0, "#####", "#    ", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    "6": G(0, " ### ", "#    ", "#    ", "#### ", "#   #", "#   #", "#   #", " ### "),
    "7": G(0, "#####", "    #", "   # ", "   # ", "  #  ", "  #  ", " #   ", " #   "),
    "8": G(0, " ### ", "#   #", "#   #", " ### ", "#   #", "#   #", "#   #", " ### "),
    "9": G(0, " ### ", "#   #", "#   #", "#   #", " ####", "    #", "    #", " ### "),
    "!": G(0, "#", "#", "#", "#", "#", "#", " ", "#"),
    "”": G(0, "## ##", " #  #", "#  # "),
    "“": G(0, " #  #", "#  # ", "## ##"),
    "£": G(0, "  ## ", " #  #", " #   ", "#### ", " #   ", " #   ", " #  #", "#####"),
    "$": G(0, "  #  ", " ####", "# #  ", "# #  ", " ### ", "  # #", "  # #", "#### ", "  #  "),
    "%": G(0, " #   #", "# # # ", " # #  ", "   #  ", "  #   ", "  # # ", " # # #", "#   # "),
    "&": G(0, " ##  ", "#  # ", "#  # ", " ##  ", "# # #", "#  # ", "#  # ", " ## #"),
    "’": G(0, "##", " #", "# "),
    "‘": G(0, " #", "# ", "##"),
    "(": G(0, "  #", " # ", "#  ", "#  ", "#  ", "#  ", "#  ", " # ", "  #"),
    ")": G(0, "#  ", " # ", "  #", "  #", "  #", "  #", "  #", " # ", "#  "),
    "*": G(1, "  #  ", "# # #", " ### ", "# # #", "  #  "),
    "+": G(2, "  #  ", "  #  ", "#####", "  #  ", "  #  "),
    ",": G(6, " #", " #", "# "),
    "-": G(4, "####"),
    ".": G(6, "#", "#"),
    "/": G(0, "    #", "    #", "   # ", "  #  ", "  #  ", " #   ", "#    ", "#    "),
    ":": G(2, "#", "#", " ", " ", "#", "#"),
    ";": G(2, " #", " #", "  ", "  ", " #", " #", "# "),
    "<": G(1, "   #", "  # ", " #  ", "#   ", " #  ", "  # ", "   #"),
    "=": G(3, "####", "    ", "####"),
    ">": G(1, "#   ", " #  ", "  # ", "   #", "  # ", " #  ", "#   "),
    "?": G(0, " ### ", "#   #", "    #", "   # ", "  #  ", "  #  ", "     ", "  #  "),
    "@": G(0, " ##### ", "#     #", "# ### #", "# # # #", "# # # #", "# #### ", "#      ", " ##### "),
    "[": G(0, "##", "# ", "# ", "# ", "# ", "# ", "# ", "# ", "##"),
    "\\": G(0, "#    ", "#    ", " #   ", "  #  ", "  #  ", "   # ", "    #", "    #"),
    "]": G(0, "##", " #", " #", " #", " #", " #", " #", " #", "##"),
    "^": G(0, "  #  ", " # # ", "#   #"),
    "_": G(8, "#####"),
    "¡": G(2, "#", " ", "#", "#", "#", "#", "#", "#"),
    "¿": G(2, "  #  ", "     ", "  #  ", "  #  ", " #   ", "#    ", "#   #", " ### "),
    "¤": G(2, "#   #", " ### ", " # # ", " ### ", "#   #"),
    "¥": G(0, "#   #", "#   #", " # # ", "  #  ", "#####", "  #  ", "#####", "  #  "),
    "©": G(0, " ##### ", "#     #", "#  ## #", "# #   #", "#  ## #", "#     #", " ##### "),
    "«": G(2, "  #  #", " #  # ", "#  #  ", " #  # ", "  #  #"),
    "»": G(2, "#  #  ", " #  # ", "  #  #", " #  # ", "#  #  "),
    "°": G(0, " # ", "# #", " # "),
    "²": G(0, "## ", "  #", " # ", "###"),
    "¹": G(0, " #", "##", " #", " #"),
    "µ": G(2, "#   #", "#   #", "#   #", "#   #", "##  #", "# ## ", "#    ", "#    "),
    "ß": G(0, " ##  ", "#  # ", "#  # ", "# #  ", "#  # ", "#   #", "#   #", "# ## "),
    "Ł": G(0, " #   ", " #   ", " #   ", " ##  ", "##   ", " #   ", " #   ", " ####"),
    "ł": G(0, " # ", " # ", " # ", " ##", "## ", " # ", " # ", " # "),
    # 符號（OpenLoco 的 LocoChar）
    "▲": G(3, "   #   ", "  ###  ", " ##### ", "#######"),
    "▼": G(3, "#######", " ##### ", "  ###  ", "   #   "),
    "▶": G(1, "#   ", "##  ", "### ", "####", "### ", "##  ", "#   "),
    "◀": G(1, "   #", "  ##", " ###", "####", " ###", "  ##", "   #"),
    "▴": G(4, "  #  ", " ### ", "#####"),
    "▾": G(4, "#####", " ### ", "  #  "),
    "•": G(3, " # ", "###", " # "),
    "✓": G(1, "       #", "      ##", "#    ## ", "##  ##  ", " ####   ", "  ##    "),
    "✗": G(1, "#    #", "##  ##", " #### ", "  ##  ", " #### ", "##  ##", "#    #"),
    "rail": G(1, " #    ####", " #    #  #", "##########", "##########", "##########", " ##  ## # "),
    "road": G(1, " ######## ", " # #  # ##", "##########", "##########", "  ##   ## "),
    "air": G(1, "    ##    ", "     ##   ", "#  ###### ", "##########", "#  ###### ", "     ##   ", "    ##    "),
    "water": G(1, "    #     ", "    ##    ", "    ###   ", "  ####### ", "##########", " ######## "),
}

# ---------------------------------------------------------------- small（大寫 5 列、x 高 4 列、下伸 1 列）
SMALL = {
    "A": G(0, " # ", "# #", "###", "# #", "# #"),
    "B": G(0, "## ", "# #", "## ", "# #", "## "),
    "C": G(0, " ##", "#  ", "#  ", "#  ", " ##"),
    "D": G(0, "## ", "# #", "# #", "# #", "## "),
    "E": G(0, "###", "#  ", "## ", "#  ", "###"),
    "F": G(0, "###", "#  ", "## ", "#  ", "#  "),
    "G": G(0, " ##", "#  ", "# #", "# #", " ##"),
    "H": G(0, "# #", "# #", "###", "# #", "# #"),
    "I": G(0, "#", "#", "#", "#", "#"),
    "J": G(0, "  #", "  #", "  #", "# #", " # "),
    "K": G(0, "# #", "# #", "## ", "# #", "# #"),
    "L": G(0, "#  ", "#  ", "#  ", "#  ", "###"),
    "M": G(0, "#   #", "## ##", "# # #", "#   #", "#   #"),
    "N": G(0, "#  #", "## #", "# ##", "#  #", "#  #"),
    "O": G(0, " ## ", "#  #", "#  #", "#  #", " ## "),
    "P": G(0, "## ", "# #", "## ", "#  ", "#  "),
    "Q": G(0, " ## ", "#  #", "#  #", "# ##", " ###"),
    "R": G(0, "## ", "# #", "## ", "# #", "# #"),
    "S": G(0, " ##", "#  ", " # ", "  #", "## "),
    "T": G(0, "###", " # ", " # ", " # ", " # "),
    "U": G(0, "#  #", "#  #", "#  #", "#  #", " ## "),
    "V": G(0, "# #", "# #", "# #", " # ", " # "),
    "W": G(0, "#   #", "#   #", "# # #", "## ##", "#   #"),
    "X": G(0, "# #", "# #", " # ", "# #", "# #"),
    "Y": G(0, "# #", "# #", " # ", " # ", " # "),
    "Z": G(0, "###", "  #", " # ", "#  ", "###"),
    "a": G(1, " ##", "# #", "# #", " ##"),
    "b": G(0, "#  ", "## ", "# #", "# #", "## "),
    "c": G(1, " ##", "#  ", "#  ", " ##"),
    "d": G(0, "  #", " ##", "# #", "# #", " ##"),
    "e": G(1, " # ", "###", "#  ", " ##"),
    "f": G(0, " ##", "#  ", "## ", "#  ", "#  "),
    "g": G(1, " ##", "# #", " ##", "  #", "## "),
    "h": G(0, "#  ", "#  ", "## ", "# #", "# #"),
    "i": G(0, "#", " ", "#", "#", "#"),
    "j": G(0, " #", "  ", " #", " #", " #", "# "),
    "k": G(0, "#  ", "# #", "## ", "# #", "# #"),
    "l": G(0, "#", "#", "#", "#", "#"),
    "m": G(1, "#### ", "# # #", "# # #", "# # #"),
    "n": G(1, "## ", "# #", "# #", "# #"),
    "o": G(1, " # ", "# #", "# #", " # "),
    "p": G(1, "## ", "# #", "## ", "#  ", "#  "),
    "q": G(1, " ##", "# #", " ##", "  #", "  #"),
    "r": G(1, "# #", "## ", "#  ", "#  "),
    "s": G(1, " ##", "#  ", "  #", "## "),
    "t": G(0, " # ", "###", " # ", " # ", " ##"),
    "u": G(1, "# #", "# #", "# #", " ##"),
    "v": G(1, "# #", "# #", "# #", " # "),
    "w": G(1, "#   #", "#   #", "# # #", " # # "),
    "x": G(1, "# #", " # ", " # ", "# #"),
    "y": G(1, "# #", "# #", " ##", "  #", "## "),
    "z": G(1, "###", "  #", "#  ", "###"),
    "0": G(0, " # ", "# #", "# #", "# #", " # "),
    "1": G(0, " # ", "## ", " # ", " # ", "###"),
    "2": G(0, "## ", "  #", " # ", "#  ", "###"),
    "3": G(0, "## ", "  #", " # ", "  #", "## "),
    "4": G(0, "# #", "# #", "###", "  #", "  #"),
    "5": G(0, "###", "#  ", "## ", "  #", "## "),
    "6": G(0, " ##", "#  ", "## ", "# #", " # "),
    "7": G(0, "###", "  #", " # ", " # ", " # "),
    "8": G(0, " # ", "# #", " # ", "# #", " # "),
    "9": G(0, " # ", "# #", " ##", "  #", "## "),
    "!": G(0, "#", "#", "#", " ", "#"),
    "”": G(0, " # #", "# # "),
    "“": G(0, " # #", "# # "),
    "£": G(0, " ## ", "#   ", "### ", "#   ", "####"),
    "$": G(0, " ### ", "# #  ", " ### ", "  # #", " ### "),
    "%": G(0, "# #", "  #", " # ", "#  ", "# #"),
    "&": G(0, " # ", "# #", " # ", "# #", " ##"),
    "’": G(0, " #", "# "),
    "‘": G(0, "# ", " #"),
    "(": G(0, " #", "# ", "# ", "# ", " #"),
    ")": G(0, "# ", " #", " #", " #", "# "),
    "*": G(1, "# #", " # ", "# #"),
    "+": G(1, " # ", "###", " # "),
    ",": G(4, " #", "# "),
    "-": G(2, "##"),
    ".": G(4, "#"),
    "/": G(0, "  #", "  #", " # ", "#  ", "#  "),
    ":": G(1, "#", " ", " ", "#"),
    ";": G(1, " #", "  ", "  ", " #", "# "),
    "<": G(0, "  #", " # ", "#  ", " # ", "  #"),
    "=": G(1, "###", "   ", "###"),
    ">": G(0, "#  ", " # ", "  #", " # ", "#  "),
    "?": G(0, "## ", "  #", " # ", "   ", " # "),
    "@": G(0, " ## ", "# ##", "# ##", "#   ", " ## "),
    "[": G(0, "##", "# ", "# ", "# ", "##"),
    "\\": G(0, "#  ", "#  ", " # ", "  #", "  #"),
    "]": G(0, "##", " #", " #", " #", "##"),
    "^": G(0, " # ", "# #"),
    "_": G(5, "###"),
    "¡": G(1, "#", " ", "#", "#", "#"),
    "¿": G(1, " # ", "   ", " # ", "#  ", " ##"),
    "¤": G(1, "# #", " # ", "# #"),
    "¥": G(0, "# #", " # ", "###", " # ", " # "),
    "©": G(0, " ### ", "# ## ", "##  #", "# ## ", " ### "),
    "«": G(1, " # #", "# # ", " # #"),
    "»": G(1, "# # ", " # #", "# # "),
    "°": G(0, " # ", "# #", " # "),
    "²": G(0, "## ", " # ", "###"),
    "¹": G(0, " #", "##", " #"),
    "µ": G(1, "# #", "# #", "# #", "## ", "#  "),
    "ß": G(0, " # ", "# #", "## ", "# #", "## "),
    "Ł": G(0, " #  ", " #  ", "##  ", " #  ", " ###"),
    "ł": G(0, " # ", " # ", "## ", " # ", " # "),
    "▲": G(2, "  #  ", " ### ", "#####"),
    "▼": G(1, "#####", " ### ", "  #  "),
    "▶": G(0, "#  ", "## ", "###", "## ", "#  "),
    "◀": G(0, "  #", " ##", "###", " ##", "  #"),
    "▴": G(2, " # ", "###"),
    "▾": G(2, "###", " # "),
    "•": G(2, "##", "##"),
    "✓": G(0, "    #", "   # ", "# #  ", " #   "),
    "✗": G(0, "# #", " # ", "# #"),
    "rail": G(0, "#   ##", "######", "######", " # # #"),
    "road": G(0, " #####", "######", "######", " #  # "),
    "air": G(0, "   #  ", "# #### ", "#######", "# #### ", "   #  "),
    "water": G(0, "  #   ", "  ##  ", "######", " #### "),
}

# 重音符號：(相對字形頂端的列, [列…])；medium 小寫放在 x 高之上兩列、大寫放在字頂之上兩列
ACCENTS_MEDIUM = {
    "acute": [" #", "# "], "grave": ["# ", " #"], "circ": [" # ", "# #"], "tilde": [" # #", "# # "],
    "uml": ["# #"], "ring": [" # ", "# #", " # "], "dot": ["#"],
}
ACCENTS_SMALL = {
    "acute": [" #", "# "], "grave": ["# ", " #"], "circ": [" # ", "# #"], "tilde": [" ##", "## "],
    "uml": ["# #"], "ring": ["##", "##"], "dot": ["#"],
}
COMPOSED = {  # 字元: (基本字母, 上方符號 或 None, 下方符號 cedilla/ogonek 或 None)
    "À": ("A", "grave", None), "Á": ("A", "acute", None), "Â": ("A", "circ", None), "Ã": ("A", "tilde", None),
    "Ä": ("A", "uml", None), "Å": ("A", "ring", None), "Ç": ("C", None, "cedilla"),
    "È": ("E", "grave", None), "É": ("E", "acute", None), "Ê": ("E", "circ", None), "Ë": ("E", "uml", None),
    "Ì": ("I", "grave", None), "Í": ("I", "acute", None), "Î": ("I", "circ", None), "Ï": ("I", "uml", None),
    "Ñ": ("N", "tilde", None), "Ò": ("O", "grave", None), "Ó": ("O", "acute", None), "Ô": ("O", "circ", None),
    "Õ": ("O", "tilde", None), "Ö": ("O", "uml", None), "Ù": ("U", "grave", None), "Ú": ("U", "acute", None),
    "Û": ("U", "circ", None), "Ü": ("U", "uml", None),
    "à": ("a", "grave", None), "á": ("a", "acute", None), "â": ("a", "circ", None), "ã": ("a", "tilde", None),
    "ä": ("a", "uml", None), "å": ("a", "ring", None), "ç": ("c", None, "cedilla"),
    "è": ("e", "grave", None), "é": ("e", "acute", None), "ê": ("e", "circ", None), "ë": ("e", "uml", None),
    "ì": ("ı", "grave", None), "í": ("ı", "acute", None), "î": ("ı", "circ", None), "ï": ("ı", "uml", None),
    "ñ": ("n", "tilde", None), "ò": ("o", "grave", None), "ó": ("o", "acute", None), "ô": ("o", "circ", None),
    "õ": ("o", "tilde", None), "ö": ("o", "uml", None), "ù": ("u", "grave", None), "ú": ("u", "acute", None),
    "û": ("u", "circ", None), "ü": ("u", "uml", None),
    # 波蘭文
    "Ą": ("A", None, "ogonek"), "Ć": ("C", "acute", None), "Ę": ("E", None, "ogonek"), "Ń": ("N", "acute", None),
    "Ś": ("S", "acute", None), "Ź": ("Z", "acute", None), "Ż": ("Z", "dot", None),
    "ą": ("a", None, "ogonek"), "ć": ("c", "acute", None), "ę": ("e", None, "ogonek"), "ń": ("n", "acute", None),
    "ś": ("s", "acute", None), "ź": ("z", "acute", None), "ż": ("z", "dot", None),
}

# Loco 字元碼 → 字形名稱（其餘 32–122 與 Latin-1 同碼）
SPECIAL_CODES = {35: "£", 34: "”", 39: "’", 96: "‘", 159: "Ą", 160: "▲", 162: "Ć", 163: "£", 166: "Ę", 167: "Ł",
                 170: "▼", 172: "✓", 173: "✗", 175: "▶", 177: "rail", 180: "“", 182: "road", 183: "air", 184: "water",
                 186: "•", 188: "▴", 189: "▾", 190: "◀", 198: "Ń", 208: "Ś", 215: "Ź", 216: "Ż", 221: "ą", 222: "ć",
                 230: "ę", 240: "ń", 247: "ł", 248: "ś", 253: "ż", 254: "ź"}
UNUSED = set(range(123, 159)) | {168, 174, 179, 255}


def code_to_glyph(code: int) -> str | None:
    if code in UNUSED:
        return None
    if code in SPECIAL_CODES:
        return SPECIAL_CODES[code]
    return bytes([code]).decode("latin1")


# ---------------------------------------------------------------- 字形組裝
class Bitmap:
    """以 (列, 欄) 為鍵的墨水點集合；列可以是負數（大寫的重音在字頂之上）。"""

    def __init__(self, pts=None):
        self.pts = set(pts or ())

    @staticmethod
    def of(glyph):
        top, rows = glyph
        return Bitmap((top + r, c) for r, row in enumerate(rows) for c, ch in enumerate(row) if ch == "#")

    def width(self):
        return max((c for _r, c in self.pts), default=-1) + 1

    def shifted(self, dr, dc):
        return Bitmap((r + dr, c + dc) for r, c in self.pts)

    def union(self, other):
        return Bitmap(self.pts | other.pts)


def compose(table, accents, name, cap_top, x_top, base_line):
    base_name, above, below = COMPOSED[name]
    if base_name == "ı":                                       # 無點 i：去掉 i 的點
        b = Bitmap.of(table["i"])
        b = Bitmap(p for p in b.pts if p[0] >= x_top)
    else:
        b = Bitmap.of(table[base_name])
    w = b.width()
    top = min(r for r, _c in b.pts)
    if above:
        acc = accents[above]
        aw = max(len(r) for r in acc)
        col = (w - aw) // 2                                    # 置中（1 欄寬的 i 會往左凸出，最後整體右移）
        gap = 0 if top > cap_top else 1                        # 小寫緊貼 x 高；大寫留 1 列
        first = top - len(acc) - gap
        for r, row in enumerate(acc):
            for c, ch in enumerate(row):
                if ch == "#":
                    b.pts.add((first + r, col + c))
    if below == "cedilla":
        mid = w // 2
        b.pts |= {(base_line + 1, mid), (base_line + 2, mid - 1)}
    elif below == "ogonek":
        b.pts |= {(base_line + 1, w - 2), (base_line + 2, w - 1)}
    # 左邊被重音推出去的欄（例如 í 的重音比 1 欄寬）→ 整體右移
    mn = min(c for _r, c in b.pts)
    if mn < 0:
        b = b.shifted(0, -mn)
    return b


def bold(b: Bitmap) -> Bitmap:
    return b.union(b.shifted(0, 1))


def render(b: Bitmap, line_offset: int, ring=True):
    """墨水點 → (w, h, x, y, pixels)。line_offset：格線第 0 列在行內的 y（含外框的 1 px）。
    ring = False（large）：不加外框，只在右邊多留 1 欄透明（前進寬度 = 影像寬 + 1 → 字距 2 px）。"""
    if not b.pts:
        return None
    r0 = min(r for r, _ in b.pts)
    r1 = max(r for r, _ in b.pts)
    c1 = max(c for _, c in b.pts)
    pad = 1 if ring else 0
    w, h = c1 + 1 + (2 * pad if ring else 1), r1 - r0 + 1 + 2 * pad
    px = bytearray(w * h)
    for r, c in b.pts:
        px[(r - r0 + pad) * w + c + pad] = INK
    if ring:
        for r, c in b.pts:                                    # 右下陰影（inset 樣式的浮雕色）
            y, x = r - r0 + pad + 1, c + pad + 1
            if px[y * w + x] == 0:
                px[y * w + x] = SHADOW
        for r, c in b.pts:                                    # 其餘一圈外框
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    y, x = r - r0 + pad + dy, c + pad + dx
                    if px[y * w + x] == 0:
                        px[y * w + x] = RING
    return w, h, 0, line_offset + r0 - pad, bytes(px)


def scale15(b: Bitmap) -> Bitmap:
    """1.5 倍放大：每個墨水點視為 1×1 方塊，放大後以涵蓋率 ≥ 0.5 取樣，再補上斜角接縫。"""
    out = set()
    for r, c in b.pts:
        y0, x0 = r * 1.5, c * 1.5
        for yy in range(int(y0) - 1, int(y0 + 1.5) + 1):
            for xx in range(int(x0) - 1, int(x0 + 1.5) + 1):
                cy = min(yy + 1, y0 + 1.5) - max(yy, y0)
                cx = min(xx + 1, x0 + 1.5) - max(xx, x0)
                if cy > 0 and cx > 0 and cy * cx >= 0.5:
                    out.add((yy, xx))
    pts = set(out)
    for r, c in b.pts:                                         # 原本斜向相接的點，放大後補一點避免斷開
        for dr, dc in ((1, 1), (1, -1)):
            if (r + dr, c + dc) in b.pts and (r + dr, c) not in b.pts and (r, c + dc) not in b.pts:
                y = int((r + 1) * 1.5)
                x = int((c + (1 if dc > 0 else 0)) * 1.5)
                pts.add((y - 1, x - (1 if dc < 0 else 0)))
    return Bitmap(pts)


FONTS = {  # catalog 字型名稱: (字形表, 重音表, 大寫頂, x 高頂, 基線, 行內偏移, 空白寬, 粗體, 放大)
    "characters_medium_normal": (MEDIUM, ACCENTS_MEDIUM, 0, 2, 7, 1, 4, False, False),
    "characters_medium_bold": (MEDIUM, ACCENTS_MEDIUM, 0, 2, 7, 1, 5, True, False),
    "characters_small": (SMALL, ACCENTS_SMALL, 0, 1, 4, 1, 3, False, False),
    "characters_large": (MEDIUM, ACCENTS_MEDIUM, 0, 2, 7, 3, 5, True, True),
}


def glyph_bitmap(spec, name):
    table, accents, cap, xtop, base, _off, _sp, is_bold, big = spec
    if name in table:
        b = Bitmap.of(table[name])
    elif name in COMPOSED:
        b = compose(table, accents, name, cap, xtop, base)
    else:
        return None
    if is_bold and name not in ("rail", "road", "air", "water"):
        b = bold(b)
    if big:
        b = scale15(b)
    return b


def build_font(font: str, base: int):
    spec = FONTS[font]
    frames = []
    for k in range(224):
        code = 32 + k
        name = code_to_glyph(code)
        idx = base + k
        if code == 32:
            frames.append((idx, (spec[6], 1, 0, 0, bytes(spec[6]))))
            continue
        b = glyph_bitmap(spec, name) if name else None
        if b is None:
            frames.append((idx, (1, 1, 0, 0, bytes(1))))
            continue
        frames.append((idx, render(b, spec[5], ring=not spec[8])))
    return frames


def write(font: str, frames):
    out = OUT / font
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    pal = dat.load_palette()
    preview_pal = list(pal)
    preview_pal[INK], preview_pal[RING], preview_pal[SHADOW] = (230, 230, 230), (40, 40, 40), (90, 90, 90)
    meta = []
    for idx, (w, h, x, y, px) in frames:
        fn = f"{idx}.png"
        dat.write_indexed_png(out / fn, w, h, px, bytes(255 if v else 0 for v in px), preview_pal)
        meta.append({"index": idx, "path": fn, "x": x, "y": y})
    (out / "sprites.json").write_text(json.dumps(meta, indent=1) + "\n")


def sheet(path: Path, fonts):
    """預覽：每套字型印一段範例文字（主色＋外框兩種樣式）。"""
    from PIL import Image
    samples = ["The quick brown fox jumps over 13 lazy dogs.", "ÀÉÎÕÜ àéîõü ÇçÑñß ĄĆĘŁŃŚŹŻ ąćęłńśźż ¡¿«»£$¥©°",
               "Station: 1,250 tons £3.4M ▲▼◀▶ ✓✗ •", "0123456789 !?#%&*()[]{}/\\<>=+-_.,:;@^"]
    cat = json.loads(CATALOG.read_text())
    rows = []
    for font, frames in fonts.items():
        fx = {idx: f for idx, f in frames}
        base = cat["fonts"][font]["base"]
        fudge = 1 if font == "characters_large" else -1
        line = 22 if font == "characters_large" else 13
        for outline in (False, True):
            for s in samples:
                im = Image.new("RGB", (560, line), (52, 82, 82) if outline else (180, 170, 150))
                x = 4
                for ch in s:
                    try:
                        code = ch.encode("latin1")[0]
                    except UnicodeEncodeError:
                        code = next((k for k, v in SPECIAL_CODES.items() if v == ch), 63)
                    inv = {v: k for k, v in SPECIAL_CODES.items()}
                    if ch in inv:
                        code = inv[ch]
                    f = fx.get(base + code - 32)
                    if not f:
                        continue
                    w, h, ox, oy, px = f
                    for j in range(h):
                        for i in range(w):
                            v = px[j * w + i]
                            col = {INK: (255, 255, 255) if outline else (20, 20, 60), RING: (0, 0, 0) if outline else None,
                                   SHADOW: (0, 0, 0) if outline else None}.get(v)
                            if col and 0 <= x + ox + i < im.width and 0 <= 3 + oy + j < im.height:
                                im.putpixel((x + ox + i, 3 + oy + j), col)
                    x += w + fudge
                rows.append(im)
    H = sum(r.height for r in rows)
    out = Image.new("RGB", (560, H))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    out = out.resize((out.width * 2, out.height * 2), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(REPO / "build" / "preview" / "g1_fonts.png"))
    args = ap.parse_args()
    cat = json.loads(CATALOG.read_text())
    built = {}
    for font in FONTS:
        frames = build_font(font, cat["fonts"][font]["base"])
        write(font, frames)
        built[font] = frames
    sheet(Path(args.sheet), built)
    print(f"寫出 4 套字型 → {OUT}；預覽 {args.sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
