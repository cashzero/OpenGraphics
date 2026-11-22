#!/usr/bin/env python3
"""程序化合成音效（sound 物件用的 WAV，22050 Hz、16-bit、單聲道，與 vanilla 相同格式）。
全部以數學公式合成，不使用任何取樣。循環音效的頭尾會無縫接合。

  python3 tools/gen/sound.py --kind <種類> --seconds 2.1 [--seed 1] [--pitch 1.0] [--tone 1.0] \\
      [--chord major|minor|fifth|single] -o <檔案.wav>

- track：鋼軌接縫的「喀噠—喀噠」節奏 + 低頻隆隆聲（循環）
- electric：電動機的嗡嗡聲與高頻嘯音（循環）
- steam_idle：蒸汽洩壓的嘶嘶聲，帶緩慢起伏（循環）
- whistle：和弦汽笛（不循環，含起音與尾音）；--pitch 改變音高、--chord 改變和弦
- prop：活塞螺旋槳引擎的低沉嗡嗡聲（循環）；--pitch 改變轉速
- turboprop：渦輪螺旋槳（螺旋槳 + 渦輪嘯音，循環）
- jet：噴射引擎的呼嘯與高頻嘯音（循環）
- chuff：蒸汽機車排氣的單次「噗」聲（不循環）；--tone 改變音色（越大越亮），--strong 為起步時較長較重的版本
- diesel：柴油引擎（循環）；--pitch 為點火頻率倍率、--tone 為機體共鳴音色
- horn：船笛（低音和弦，不循環）
- touchdown：飛機落地的輪胎摩擦聲 + 撞擊聲（不循環）
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


def whistle(seconds: float, rng: random.Random, pitch: float, chord: str = "major") -> list[float]:
    n = int(RATE * seconds)
    ratios = {"major": [1, 1.2599, 1.4983], "minor": [1, 1.1892, 1.4983], "fifth": [1, 1.4983],
              "single": [1]}[chord]
    freqs = [440 * pitch * r for r in ratios]   # 預設大三和弦
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


def _int_freq(f: float, seconds: float) -> float:
    """把頻率調到在 seconds 內剛好整數個週期，循環時不會跳音。"""
    return max(1, round(f * seconds)) / seconds


def prop(seconds: float, rng: random.Random, pitch: float, whine: float = 0.0) -> list[float]:
    n = int(RATE * seconds)
    f0 = _int_freq(38 * pitch, seconds)          # 曲軸點火基頻
    fw = _int_freq(1900 * pitch, seconds)        # 渦輪嘯音
    fm = _int_freq(4.0, seconds)                 # 慢速起伏
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n + 2000)], 0.08)[2000:]
    out = []
    for i in range(n):
        t = i / RATE
        ph = 2 * math.pi * f0 * t
        v = sum(math.sin(k * ph + k * 0.7) / k ** 0.9 for k in range(1, 9)) * 0.32
        v *= 0.8 + 0.2 * math.sin(2 * math.pi * fm * t)
        v += 0.45 * noise[i]
        if whine:
            v += whine * 0.12 * math.sin(2 * math.pi * fw * t) * (0.8 + 0.2 * math.sin(2 * math.pi * fm * t))
        out.append(v)
    return out


def jet(seconds: float, rng: random.Random, pitch: float) -> list[float]:
    n = int(RATE * seconds) + int(0.2 * RATE)
    roar = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.18)
    hiss = [rng.uniform(-1, 1) for _ in range(n)]
    hiss = [a - b for a, b in zip(hiss, lowpass(hiss, 0.3))]       # 高通：嘶嘶聲
    fw1, fw2 = 2600 * pitch, 3100 * pitch
    out = []
    for i in range(n):
        t = i / RATE
        w = 0.07 * math.sin(2 * math.pi * fw1 * t) + 0.04 * math.sin(2 * math.pi * fw2 * t)
        out.append(0.8 * roar[i] + 0.25 * hiss[i] + w)
    return make_loop(out, int(0.2 * RATE))


def chuff(seconds: float, rng: random.Random, tone: float, strong: bool) -> list[float]:
    n = int(RATE * seconds)
    raw = [rng.uniform(-1, 1) for _ in range(n)]
    body = lowpass(raw, 0.10 * tone)
    bright = lowpass(raw, 0.35 * tone)
    decay = (0.20 if strong else 0.11) * RATE
    attack = int(0.006 * RATE)
    out = []
    for i in range(n):
        env = min(1.0, i / attack) * math.exp(-i / decay)
        tail = 1.0 if i < n - int(0.03 * RATE) else (n - i) / (0.03 * RATE)
        thump = math.sin(2 * math.pi * 70 * i / RATE) * math.exp(-i / (0.04 * RATE))
        v = env * (0.9 * body[i] + 0.35 * bright[i]) + (0.35 if strong else 0.2) * thump
        if strong:                                       # 起步時的第二股排氣
            j = i - int(0.12 * RATE)
            if j > 0:
                v += 0.5 * math.exp(-j / decay) * min(1.0, j / attack) * body[i]
        out.append(v * tail)
    return out


def diesel(seconds: float, rng: random.Random, pitch: float, tone: float) -> list[float]:
    n = int(RATE * seconds)
    fire = _int_freq(24 * pitch, seconds)           # 點火頻率（每秒爆發數）
    period = RATE / fire
    reson = 110 * tone                               # 機體共鳴
    noise = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.12)
    rumble = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.015)
    out = []
    for i in range(n):
        ph = (i % period) / RATE                     # 距上一次爆發的秒數（循環時自然接上）
        k = int(i // period)
        amp = 0.85 + 0.15 * ((k * 7919) % 5) / 4      # 每缸略有不同
        burst = math.exp(-ph / 0.012) * (math.sin(2 * math.pi * reson * ph) + 0.6 * noise[i])
        out.append(amp * burst + 0.4 * rumble[i] + 0.15 * math.sin(2 * math.pi * fire * i / RATE))
    return out


def horn(seconds: float, rng: random.Random, pitch: float, chord: str) -> list[float]:
    n = int(RATE * seconds)
    base = 98 * pitch
    freqs = [base] + {"major": [base * 1.26], "minor": [base * 1.19], "fifth": [base * 1.5], "single": []}[chord]
    attack, release = int(0.12 * RATE), int(0.35 * RATE)
    breath = lowpass([rng.uniform(-1, 1) for _ in range(n)], 0.05)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, i / attack) * min(1.0, (n - i) / release)
        v = 0.0
        for f in freqs:                                  # 鋸齒波（加法合成）：低沉帶金屬感
            v += sum(math.sin(2 * math.pi * f * k * t) / k for k in range(1, 12))
        out.append(env * (0.4 * v + 0.15 * breath[i]))
    return out


def touchdown(seconds: float, rng: random.Random) -> list[float]:
    n = int(RATE * seconds)
    raw = [rng.uniform(-1, 1) for _ in range(n)]
    band = [a - b for a, b in zip(lowpass(raw, 0.55), lowpass(raw, 0.18))]   # 帶通：輪胎摩擦
    out = []
    for i in range(n):
        t = i / RATE
        screech = band[i] * math.exp(-t / 0.12) * (1 + 0.5 * math.sin(2 * math.pi * 31 * t))
        thump = math.sin(2 * math.pi * 55 * t) * math.exp(-t / 0.06)
        tail = min(1.0, (n - i) / (0.03 * RATE))
        out.append((1.2 * screech + 0.8 * thump) * tail)
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
    ap.add_argument("--kind", required=True, choices=["track", "electric", "steam_idle", "whistle", "prop", "turboprop",
                                                      "jet", "chuff", "diesel", "horn", "touchdown"])
    ap.add_argument("--tone", type=float, default=1.0)
    ap.add_argument("--chord", choices=["major", "minor", "fifth", "single"], default="major")
    ap.add_argument("--strong", action="store_true")
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
    elif args.kind == "whistle":
        s = whistle(args.seconds, rng, args.pitch, args.chord)
    elif args.kind in ("prop", "turboprop"):
        s = prop(args.seconds, rng, args.pitch, whine=(1.0 if args.kind == "turboprop" else 0.0))
    elif args.kind == "jet":
        s = jet(args.seconds, rng, args.pitch)
    elif args.kind == "chuff":
        s = chuff(args.seconds, rng, args.tone, args.strong)
    elif args.kind == "diesel":
        s = diesel(args.seconds, rng, args.pitch, args.tone)
    elif args.kind == "horn":
        s = horn(args.seconds, rng, args.pitch, args.chord)
    else:
        s = touchdown(args.seconds, rng)
    write_wav(args.output, s)
    print(f"寫出 {args.output}（{len(s) / RATE:.2f} 秒）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
