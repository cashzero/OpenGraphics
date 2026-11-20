#!/usr/bin/env python3
"""程序化合成音效（sound 物件用的 WAV，22050 Hz、16-bit、單聲道，與 vanilla 相同格式）。
全部以數學公式合成，不使用任何取樣。循環音效的頭尾會無縫接合。

  python3 tools/gen/sound.py --kind track|electric|steam_idle|whistle --seconds 2.1 [--seed 1] \\
      [--pitch 1.0] -o <檔案.wav>

- track：鋼軌接縫的「喀噠—喀噠」節奏 + 低頻隆隆聲（循環）
- electric：電動機的嗡嗡聲與高頻嘯音（循環）
- steam_idle：蒸汽洩壓的嘶嘶聲，帶緩慢起伏（循環）
- whistle：和弦汽笛（不循環，含起音與尾音）；--pitch 改變音高
"""
from __future__ import annotations

import argparse
import math
import random
import struct
import wave

RATE = 22050


def lowpass(samples: list[float], alpha: float) -> list[float]:
    out, y = [], 0.0
    for s in samples:
        y += alpha * (s - y)
        out.append(y)
    return out


def make_loop(samples: list[float], fade: int) -> list[float]:
    """把尾段淡出並疊到開頭，讓循環接縫平順。"""
    n = len(samples)
    body = samples[: n - fade]
    for i in range(fade):
        a = i / fade
        body[i] = body[i] * a + samples[n - fade + i] * (1 - a)
    return body


def track(seconds: float, rng: random.Random) -> list[float]:
    n = int(RATE * seconds)
    rumble = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.02)
    out = [0.35 * r for r in rumble]
    # 每個循環兩組輪軸經過接縫：喀、噠（間隔約 0.11 秒）
    for start in (0.0, 0.11, seconds / 2, seconds / 2 + 0.11):
        s0 = int(start * RATE)
        for k in range(int(0.05 * RATE)):
            if s0 + k >= n:
                break
            env = math.exp(-k / (0.008 * RATE))
            thump = math.sin(2 * math.pi * 90 * k / RATE)
            out[s0 + k] += env * (0.55 * thump + 0.35 * rng.uniform(-1, 1))
    return make_loop(out + out[: int(0.05 * RATE)], int(0.05 * RATE))


def electric(seconds: float, rng: random.Random) -> list[float]:
    n = int(RATE * seconds)
    out = []
    for i in range(n):
        t = i / RATE
        # 頻率取整數週期，循環時不會跳音
        v = (0.40 * math.sin(2 * math.pi * 100 * t) + 0.20 * math.sin(2 * math.pi * 200 * t)
             + 0.10 * math.sin(2 * math.pi * 300 * t)
             + 0.08 * math.sin(2 * math.pi * 820 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 2 * t)))
        out.append(v + 0.03 * rng.uniform(-1, 1))
    return out


def steam_idle(seconds: float, rng: random.Random) -> list[float]:
    n = int(RATE * seconds) + int(0.1 * RATE)
    hiss = [rng.uniform(-1, 1) for _ in range(n)]
    hiss = lowpass(hiss, 0.6)
    out = []
    for i in range(n):
        t = i / RATE
        env = 0.55 + 0.25 * math.sin(2 * math.pi * t / seconds) + 0.1 * math.sin(2 * math.pi * 3 * t / seconds)
        out.append(hiss[i] * env * 0.6)
    return make_loop(out, int(0.1 * RATE))


def whistle(seconds: float, rng: random.Random, pitch: float) -> list[float]:
    n = int(RATE * seconds)
    freqs = [440 * pitch, 554.37 * pitch, 659.25 * pitch]   # 大三和弦
    attack, release = int(0.06 * RATE), int(0.18 * RATE)
    out = []
    breath = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.3)
    for i in range(n):
        t = i / RATE
        env = min(1.0, i / attack) * min(1.0, (n - i) / release)
        vib = 1 + 0.004 * math.sin(2 * math.pi * 5.5 * t)
        v = sum(math.sin(2 * math.pi * f * vib * t) / (k + 1.4) for k, f in enumerate(freqs))
        out.append(env * (0.55 * v + 0.12 * breath[i]))
    return out


def write_wav(path: str, samples: list[float]) -> None:
    peak = max(1e-9, max(abs(s) for s in samples))
    scale = 0.85 * 32767 / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * scale)) for s in samples))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["track", "electric", "steam_idle", "whistle"], required=True)
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pitch", type=float, default=1.0)
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    if args.kind == "track":
        s = track(args.seconds, rng)
    elif args.kind == "electric":
        s = electric(args.seconds, rng)
    elif args.kind == "steam_idle":
        s = steam_idle(args.seconds, rng)
    else:
        s = whistle(args.seconds, rng, args.pitch)
    write_wav(args.output, s)
    print(f"寫出 {args.output}（{len(s) / RATE:.2f} 秒）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
