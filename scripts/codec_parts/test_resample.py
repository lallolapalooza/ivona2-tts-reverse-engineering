#!/usr/bin/env python3
"""Bit-exactness check for ``codec_parts.resample`` against the shipped engine.

The engine is the oracle (Unicorn emulation of ``libttsivonavoice.so``, via
``scripts/decode_unit.py``):

  * ``Codec(rate=24000).decode_stream(...)`` gives the codec-rate domain PCM
    (concatenated 480-sample frames, no rate conversion).
  * ``Codec(rate=22050).decode_window(...)`` decodes the same record through the
    real ``FUN_00147c58`` -> ``FUN_0014b4a8`` resampler.
  * ``Resampler(24000, 22050).run(frame, 441)`` must reproduce the second from
    the first, sample for sample.

Usage:
  cd scripts/codec_parts && ~/venvs/re/bin/python test_resample.py [--records N]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)                       # codec_parts (resample, prims)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))  # decode_unit

from resample import Resampler            # noqa: E402
import decode_unit as du                  # noqa: E402

MAX_SAMPLES = 20000          # codec-rate samples fed to the Resampler
N_RECORDS = 5                # checked records per voice


def first_records(obb, want, scan=200):
    """First `want` valid records (N >= 16, >= 2000 output samples)."""
    out = []
    for i in range(scan):
        rec = obb.record(i)
        if rec and rec['N'] >= 16 and rec['samples'] >= 2000:
            out.append(i)
            if len(out) >= want:
                break
    return out


def check_voice(voice, n_records, verbose=True):
    obb = du.Obb(du.find_obb(voice))
    print('--- %s: %s' % (voice, os.path.basename(obb.path)))
    c24 = du.Codec(rate=24000)
    c22 = du.Codec(rate=22050)
    ok = bad = 0
    for rid in first_records(obb, n_records):
        rec = obb.record(rid)
        win = obb.window(rec)
        pk, tot = du.iter_packets(win)
        packets = [du.deobfuscate(pl, obb.cksum)[0] for _, pl in pk]

        stream = c24.decode_stream(obb.cksum, packets, skip=0,
                                   max_samples=MAX_SAMPLES)
        rs = Resampler(24000, 22050)
        mine = []
        for i in range(0, len(stream) - 479, 480):
            mine += rs.run(stream[i:i + 480], 441)

        eng = c22.decode_window(obb.cksum, win, rec['Y'], rec['samples'])
        ref = mine[rec['Y']:rec['Y'] + rec['samples']]
        ref = ref + [0] * (rec['samples'] - max(0, len(mine) - rec['Y']))

        if ref == eng:
            ok += 1
            if verbose:
                print('  rec %3d  N=%2d  frames=%3d  Y=%5d  samples=%5d  '
                      'BIT-IDENTICAL' % (rid, rec['N'], len(stream) // 480,
                                         rec['Y'], rec['samples']))
        else:
            bad += 1
            n = min(len(ref), len(eng))
            d = next((i for i in range(n) if ref[i] != eng[i]), n)
            print('  rec %3d  N=%2d  Y=%5d  samples=%5d  MISMATCH at index %d: '
                  'engine=%d port=%d' % (rid, rec['N'], rec['Y'], rec['samples'],
                                         d, eng[d] if d < len(eng) else None,
                                         ref[d] if d < len(ref) else None))
    print('  %s: %d/%d records bit-identical' % (voice, ok, ok + bad))
    return ok, bad


def main():
    n = N_RECORDS
    if '--records' in sys.argv:
        n = int(sys.argv[sys.argv.index('--records') + 1])
    tok = bad = 0
    for voice in ('kendra', 'amy'):
        o, b = check_voice(voice, n)
        tok += o
        bad += b
    if bad:
        print('FAIL: %d mismatching record(s)' % bad)
        return 1
    print('OK: resampler bit-identical to the engine for %d records '
          '(Kendra + Amy, codec_rate=24000 -> out_rate=22050)' % tok)
    return 0


if __name__ == '__main__':
    sys.exit(main())
