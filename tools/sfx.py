#!/usr/bin/env python3
"""用 base/sfx/ 的 OpenSFX 音效組出 OpenLoco 的音效 bank 與環境音（ROADMAP M5）。只用標準函式庫，CI 也能直接執行。

  python3 tools/sfx.py install <Data 目錄>   # 寫出 CSS1.DAT、CSS2.DAT、CSS4.DAT、COPYING-sfx.txt
  python3 tools/sfx.py check

base/sfx/sounds.json：
- css1：SoundId 0–31（OpenLoco Audio.h 的 SoundId）各用哪個檔案、增益（依 vanilla 同一音效的 RMS 量出，只用數值）；
  silence = 靜音（vanilla 的 clickUp 幾乎無聲）。
- ambient：CSS2（荒野）／CSS4（森林）的循環，由數層素材混成：repeat = 交叉淡化接成連續的底音，at = 在第幾秒放一次。
  混好後頭尾交叉淡化成無縫循環，並把響度調到 vanilla 同一檔案的 RMS（target_rms）。
CSS1.DAT 格式（Audio.cpp loadSoundsFromCSS）：uint32 數量、uint32 offset × 數量，每個音效 = uint32 PCM 長度 + WAVEFORMATEX（18 bytes）+ PCM。
CSS2–4 是一般的 WAV（OpenLoco 以音樂的方式循環播放）。
"""
from __future__ import annotations

import argparse
import array
import json
import math
import struct
import sys
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SFX = REPO / "base" / "sfx"
RATE = 44100
AMBIENT_TARGET_RMS = {"CSS2": 0.046, "CSS3": 0.035, "CSS4": 0.029}  # vanilla 同名檔案的 RMS（量測值）
LOOP_FADE = 0.6  # 循環接縫的交叉淡化秒數


def load() -> dict:
    return json.loads((SFX / "sounds.json").read_text())


def read_wav(name: str) -> tuple[array.array, int, int]:
    """→ (16-bit 單聲道樣本, 取樣率, 聲道數)。OpenSFX 全部是 44.1 kHz 16-bit 單聲道。"""
    with wave.open(str(SFX / "opensfx" / name)) as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise SystemExit(f"{name}：只支援 16-bit 單聲道")
        raw = w.readframes(w.getnframes())
        samples = array.array("h")
        samples.frombytes(raw[: len(raw) // 2 * 2])  # 少數 OpenSFX 檔的資料長度是奇數（最後半個樣本截掉）
        if sys.byteorder == "big":
            samples.byteswap()
        return samples, w.getframerate(), 1


def scaled(samples, gain: float) -> array.array:
    return array.array("h", (max(-32768, min(32767, round(s * gain))) for s in samples))


def to_bytes(samples: array.array) -> bytes:
    if sys.byteorder == "big":
        samples = array.array("h", samples)
        samples.byteswap()
    return samples.tobytes()


def css1(doc: dict) -> bytes:
    entries = []
    for e in sorted(doc["css1"], key=lambda e: e["id"]):
        if "file" in e:
            samples, rate, ch = read_wav(e["file"])
            samples = scaled(samples, e.get("gain", 1.0))
        else:
            rate, ch = RATE, 1
            samples = array.array("h", [0] * max(1, round(e["silence"] * RATE)))
        pcm = to_bytes(samples)
        fmt = struct.pack("<hhiihhh", 1, ch, rate, rate * ch * 2, ch * 2, 16, 0)
        entries.append(struct.pack("<I", len(pcm)) + fmt + pcm)
    if [e["id"] for e in sorted(doc["css1"], key=lambda e: e["id"])] != list(range(32)):
        raise SystemExit("sounds.json 的 css1 必須剛好是 SoundId 0–31")
    out = bytearray(struct.pack("<I", len(entries)))
    offset = 4 + 4 * len(entries)
    for e in entries:
        out += struct.pack("<I", offset)
        offset += len(e)
    for e in entries:
        out += e
    return bytes(out)


def ambient(spec: dict, target_rms: float) -> array.array:
    n = round(spec["seconds"] * RATE)
    fade = round(LOOP_FADE * RATE)
    mix = [0.0] * (n + fade)                     # 多算一段，最後交叉淡化回開頭
    for layer in spec["layers"]:
        clip, _, _ = read_wav(layer["file"])
        gain = layer.get("gain", 1.0)
        if layer.get("repeat"):
            pos = -round(layer.get("offset", 0.0) * RATE)
            xf = min(round(0.4 * RATE), len(clip) // 3)
            while pos < len(mix):
                for i, s in enumerate(clip):
                    j = pos + i
                    if 0 <= j < len(mix):
                        a = min(1.0, i / xf, (len(clip) - i) / xf)   # 每段頭尾淡入淡出，相鄰兩段重疊 xf
                        mix[j] += s * gain * math.sin(a * math.pi / 2)  # 等功率交叉淡化（不相關的雜音不會在接縫變小聲）
                pos += len(clip) - xf
        else:
            start = round(layer["at"] * RATE)
            for i, s in enumerate(clip):
                mix[(start + i) % n] += s * gain
    loop = mix[:n]
    for i in range(fade):                       # 尾段淡出、疊回開頭 → 無縫循環
        a = i / fade * math.pi / 2
        loop[i] = loop[i] * math.sin(a) + mix[n + i] * math.cos(a)
    rms = math.sqrt(sum(s * s for s in loop) / n) / 32768
    g = target_rms / rms if rms else 1.0
    return array.array("h", (max(-32768, min(32767, round(s * g))) for s in loop))


def write_wav(path: Path, samples: array.array) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(to_bytes(samples))


def check(doc: dict) -> list[str]:
    errors = []
    for e in doc["css1"]:
        if "file" in e and e["file"] not in doc["files"]:
            errors.append(f"css1 {e['name']}：{e['file']} 沒有出處紀錄")
    for k, a in doc["ambient"].items():
        for layer in a["layers"]:
            if layer["file"] not in doc["files"]:
                errors.append(f"{k}：{layer['file']} 沒有出處紀錄")
    for name in doc["files"]:
        if not (SFX / "opensfx" / name).is_file():
            errors.append(f"找不到 base/sfx/opensfx/{name}")
    return errors


def install(data_dir: Path, doc: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "CSS1.DAT").write_bytes(css1(doc))
    for name, spec in doc["ambient"].items():
        write_wav(data_dir / f"{name}.DAT", ambient(spec, AMBIENT_TARGET_RMS[name]))
    credits = [f"OpenLoco 音效（OpenGraphics base/sfx）：{doc['source']}", f"授權：{doc['license']}", ""]
    credits += [f"- {name}: {info['credit']}" for name, info in sorted(doc["files"].items())]
    credits += ["", "CSS1.DAT 依 OpenLoco 的音效編號重新排列並調整音量；CSS2/CSS4.DAT 由上列風聲與鳥鳴混成循環。",
                "CC BY-SA 3.0：https://creativecommons.org/licenses/by-sa/3.0/"]
    (data_dir / "COPYING-sfx.txt").write_text("\n".join(credits) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("install")
    p.add_argument("data_dir", type=Path)
    sub.add_parser("check")
    args = ap.parse_args(argv)
    doc = load()
    errors = check(doc)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.cmd == "install":
        install(args.data_dir, doc)
        print(f"音效：CSS1.DAT（32 個）+ 環境音 {', '.join(doc['ambient'])} → {args.data_dir}")
    else:
        print(f"OK：css1 {len(doc['css1'])} 個、環境音 {len(doc['ambient'])} 個、素材 {len(doc['files'])} 個")
    return 0


if __name__ == "__main__":
    sys.exit(main())
