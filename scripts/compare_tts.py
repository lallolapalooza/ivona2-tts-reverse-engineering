#!/usr/bin/env python3
"""compare_tts.py — A/B two WAVs of the same utterance (reference vs reimplementation).

Reports, without any assumption about sample-exactness:
  * rate/length of both files and the duration delta,
  * global alignment (best lag by cross-correlation on 10 ms RMS envelopes),
  * per-frame RMS correlation after alignment, and the fraction of frames within ±3 dB,
  * sample-exact match when the lengths and rates agree,
  * a coarse per-segment table (start, end, ref RMS dBFS, test RMS dBFS).

Usage:
  python3 scripts/compare_tts.py REF.wav TEST.wav [--json out.json] [--frames 50]
"""
import argparse
import array
import json
import math
import wave


def rd(path):
    w = wave.open(path)
    a = array.array('h')
    a.frombytes(w.readframes(w.getnframes()))
    return w.getframerate(), w.getnchannels(), a


def frames_rms(a, rate, ms=10):
    n = max(1, int(rate * ms / 1000.0))
    out = []
    for i in range(0, len(a) - n + 1, n):
        s = sum(float(v) * v for v in a[i:i + n])
        out.append(math.sqrt(s / n))
    return out, n


def dbfs(x):
    return -999.0 if x <= 0 else 20.0 * math.log10(x / 32768.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('test')
    ap.add_argument('--json')
    ap.add_argument('--frames', type=int, default=50)
    args = ap.parse_args()

    r1, c1, a1 = rd(args.ref)
    r2, c2, a2 = rd(args.test)
    res = {'ref': {'rate': r1, 'channels': c1, 'samples': len(a1), 'seconds': len(a1) / r1},
           'test': {'rate': r2, 'channels': c2, 'samples': len(a2), 'seconds': len(a2) / r2}}
    res['duration_delta_ms'] = round(1000.0 * (len(a2) / r2 - len(a1) / r1), 2)

    if r1 != r2:
        res['note'] = 'rates differ; resample before sample-exact comparison'
        print(json.dumps(res, indent=1))
        if args.json:
            open(args.json, 'w').write(json.dumps(res, indent=1))
        return 0

    if len(a1) == len(a2):
        d = sum(1 for x, y in zip(a1, a2) if x != y)
        res['sample_diffs'] = d
        res['sample_exact'] = (d == 0)
        if d == 0:
            res['note'] = 'BIT-EXACT'

    # envelope alignment
    e1, n = frames_rms(a1, r1)
    e2, _ = frames_rms(a2, r2)
    L = min(len(e1), len(e2))
    e1, e2 = e1[:L], e2[:L]
    best, blag = -1e18, 0
    for lag in range(-200, 201):
        s = 0.0
        cnt = 0
        for i in range(max(0, lag), min(L, L + lag)):
            s += e1[i] * e2[i - lag]
            cnt += 1
        if cnt:
            v = s / cnt
            if v > best:
                best, blag = v, lag
    res['best_lag_frames'] = blag
    res['best_lag_ms'] = round(blag * 10.0, 1)

    m1 = sum(e1) / max(1, len(e1))
    m2 = sum(e2) / max(1, len(e2))
    num = sum((x - m1) * (y - m2) for x, y in zip(e1, e2))
    den = math.sqrt(sum((x - m1) ** 2 for x in e1) * sum((y - m2) ** 2 for y in e2)) or 1.0
    res['envelope_correlation'] = round(num / den, 4)
    within = sum(1 for x, y in zip(e1, e2) if abs(dbfs(x) - dbfs(y)) <= 3.0 and x > 0 and y > 0)
    voiced = sum(1 for x, y in zip(e1, e2) if x > 0 and y > 0)
    res['frames_within_3dB_pct'] = round(100.0 * within / max(1, voiced), 1)

    step = max(1, L // max(1, args.frames))
    rows = []
    for i in range(0, L, step):
        rows.append([round(i * 10.0, 1), round(min(i + step, L) * 10.0, 1),
                     round(dbfs(e1[i]), 1), round(dbfs(e2[i]), 1)])
    res['segments_ms_ref_rms_test_rms'] = rows
    print(json.dumps(res, indent=1))
    if args.json:
        open(args.json, 'w').write(json.dumps(res, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
