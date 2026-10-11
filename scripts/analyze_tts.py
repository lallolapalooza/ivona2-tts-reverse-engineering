#!/usr/bin/env python3
"""Objective analysis of a WAV produced by refimpl/tts.py.

Reports, for a synthesised utterance:
  * sample count / duration / peak / RMS
  * a 10 ms RMS energy envelope summary (voiced vs silent frames, dynamic range)
  * a time-domain autocorrelation F0 track over voiced frames (min / median / max)
  * the phone-level alignment derived from the pipeline's `--json` sidecar
    (which recorded unit serves which diphone, the splice position and the time span)

and writes a spectrogram PNG (via ffmpeg `showspectrumpic`, so no scipy is needed).

Usage:
    python3 scripts/analyze_tts.py OUT.wav [--json OUT.json] [--spec out/tts_demo/x_spec.png]
"""
import argparse
import json
import os
import subprocess
import sys
import wave

import numpy as np


def read_wav(path):
    with wave.open(path, 'rb') as w:
        n, rate, sw, ch = w.getnframes(), w.getframerate(), w.getsampwidth(), w.getnchannels()
        raw = w.readframes(n)
    assert sw == 2, "expect 16-bit PCM"
    x = np.frombuffer(raw, dtype='<i2').astype(np.float64)
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, rate


def rms_envelope(x, rate, win_ms=10.0):
    w = max(1, int(rate * win_ms / 1000.0))
    n = len(x) // w
    frames = x[:n * w].reshape(n, w)
    return np.sqrt((frames ** 2).mean(axis=1)), w


def f0_track(x, rate, win_ms=40.0, hop_ms=10.0, fmin=60, fmax=400):
    """Autocorrelation F0 per frame; voiced when the normalised peak > 0.3."""
    w = int(rate * win_ms / 1000.0)
    h = int(rate * hop_ms / 1000.0)
    lo, hi = int(rate / fmax), int(rate / fmin)
    out = []
    for a in range(0, max(0, len(x) - w), h):
        seg = x[a:a + w]
        seg = seg - seg.mean()
        e = (seg ** 2).sum()
        if e < 1e-6:
            continue
        ac = np.correlate(seg, seg, 'full')[w - 1:]
        ac /= (ac[0] + 1e-12)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.3:
            out.append((a / float(rate), rate / float(k), float(ac[k])))
    return out


def spectrogram(wav, png):
    """Full-file spectrogram PNG via ffmpeg (no matplotlib/scipy in the venv)."""
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', wav,
           '-lavfi', 'showspectrumpic=s=1024x512:legend=1:scale=log', png]
    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:                      # noqa: BLE001
        print("spectrogram failed: %s" % e)
        return False


def phone_alignment(js, rate):
    """Turn the JSON unit trace into a phone-level alignment table.

    `pos_after` values are codec-domain sample counts, so times use the codec rate
    (resampling preserves time; the WAV may hold a different number of samples).
    """
    rows = []
    prev = 0
    for u in js['units']:
        a, b = prev, u['pos_after']
        rows.append((u['diphone'], u['unit'], a, b, (b - a) / float(rate) * 1000.0,
                     u['dur_ms'], u['N'], len(u['segs']), u['ctx_score']))
        prev = b
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('wav')
    ap.add_argument('--json', default=None)
    ap.add_argument('--spec', default=None)
    args = ap.parse_args()

    x, rate = read_wav(args.wav)
    dur = len(x) / float(rate)
    peak = float(np.abs(x).max())
    rms = float(np.sqrt((x ** 2).mean()))
    print("file      : %s" % args.wav)
    print("samples   : %d  (%.4f s @ %d Hz)" % (len(x), dur, rate))
    print("peak      : %.0f  rms: %.1f  (%.1f dBFS peak)"
          % (peak, rms, 20 * np.log10(peak / 32768.0 + 1e-12)))

    env, w = rms_envelope(x, rate)
    thr = max(1.0, 0.02 * env.max())
    silent = int((env < thr).sum())
    print("envelope  : %d frames @ %.0f ms, %d silent (<%.1f), max frame rms %.0f"
          % (len(env), w / float(rate) * 1000, silent, thr, env.max()))
    if silent:
        run, best = 0, 0
        for v in env:
            run = run + 1 if v < thr else 0
            best = max(best, run)
        print("            longest silent run: %d frames (%.0f ms)" % (best, best * w / float(rate) * 1000))

    track = f0_track(x, rate)
    if track:
        f0 = np.array([t[1] for t in track])
        print("f0 (ac)   : %d voiced frames, min %.1f  median %.1f  max %.1f  mean %.1f Hz"
              % (len(f0), f0.min(), np.median(f0), f0.max(), f0.mean()))
        print("            voiced span %.2f s .. %.2f s"
              % (track[0][0], track[-1][0]))
    else:
        print("f0 (ac)   : no voiced frames found")

    zc = int((np.diff(np.sign(x)) != 0).sum())
    print("zcr       : %d crossings (%.0f /s)" % (zc, zc / dur))

    if args.json:
        js = json.load(open(args.json))
        cps = js.get('codec_rate', rate)
        print("\nphone-level alignment (%d units, %d words), codec rate %d Hz:"
              % (len(js['units']), len(js['words']), cps))
        print("  %-4s %-10s %-8s %10s %10s %9s %6s %5s %4s"
              % ("#", "diphone", "unit", "start", "end", "out_ms", "db_ms", "segs", "ctx"))
        for k, (name, uid, a, b, ms, dbms, N, nseg, score) in enumerate(phone_alignment(js, cps)):
            print("  %-4d %-10s %-8d %10.4f %10.4f %9.1f %6d %5d %4d"
                  % (k, name, uid, a / float(cps), b / float(cps), ms, dbms, nseg, score))
        tot_out = sum(r[4] for r in phone_alignment(js, cps))
        tot_db = sum(r[5] for r in phone_alignment(js, cps))
        print("  total: out %.1f ms | sum(recorded diphone durations) %.1f ms | ratio %.3f"
              % (tot_out, tot_db, tot_out / tot_db if tot_db else 0))
        print("  used samples %d (codec-domain) = %.4f s; diphone crossfades/final-tail "
              "excluded" % (js['samples'], js['samples'] / float(cps)))
        print("  phones: %s" % " ".join(js['phones']))
        if js.get('missing'):
            print("  skipped diphones: %s" % js['missing'])

    spec = args.spec
    if spec is None:
        spec = os.path.splitext(args.wav)[0] + "_spec.png"
    if spectrogram(args.wav, spec):
        print("\nspectrogram: %s" % spec)
    return 0


if __name__ == '__main__':
    sys.exit(main())
