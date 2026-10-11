#!/usr/bin/env python3
"""verify_codec_swap.py -- prove the clean-room decoder == the emulated one.

Compares, record by record and byte for byte, the PCM produced by

  * the emulated `decode_unit.Codec` (Unicorn;               the old path), and
  * the clean-room `codec_spec.Spec` (stdlib-only;           the new path),

at the codec rate (24 000) and at the shipped container rate (22 050).  It also
reuses a *single* `Spec` across records, which exercises `Spec.reset()`: without
that per-window reset the context carries over and every record after the first
decodes wrong (this is the bug the swap fix addressed).

Usage (needs Unicorn for the reference -- run with the project venv):

    ~/venvs/re/bin/python scripts/verify_codec_swap.py --voice kendra --count 12
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import codec_spec as cs                                     # noqa: E402
import decode_unit as du                                    # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice', default='kendra')
    ap.add_argument('--count', type=int, default=12,
                    help='number of records to test (spread across the index)')
    ap.add_argument('--rates', default='24000,22050')
    args = ap.parse_args()

    path = cs.find_obb(args.voice)
    ob = du.Obb(path)
    ob2 = cs.Obb(path)
    nrec = ob.n_rec if hasattr(ob, 'n_rec') else ob2.n_rec
    ids = [int(i * (nrec - 1) / max(1, args.count - 1)) for i in range(args.count)]

    ok = True
    for rate in [int(r) for r in args.rates.split(',')]:
        # fresh-Spec-per-record (typical caller) and one reused Spec (reset check)
        fresh_bad = reuse_bad = tested = 0
        reuse = cs.Spec(out_rate=rate)
        emu = du.Codec(rate=rate)
        for rid in ids:
            rec = ob.record(rid)
            if rec is None:
                continue
            win = ob.window(rec)
            ref = emu.decode_window(ob.cksum, win, rec['Y'], rec['samples'])
            got_fresh = cs.Spec(out_rate=rate).decode_window(
                ob2.cksum, ob2.window(rec), rec['Y'], rec['samples'])
            got_reuse = reuse.decode_window(ob2.cksum, ob2.window(rec), rec['Y'], rec['samples'])
            if got_fresh != ref:
                fresh_bad += 1
            if got_reuse != ref:
                reuse_bad += 1
            tested += 1
        status = 'BIT-EXACT' if not (fresh_bad or reuse_bad) else 'MISMATCH'
        ok = ok and not (fresh_bad or reuse_bad)
        print('rate %5d: %d records  fresh-Spec diffs=%d  reused-Spec diffs=%d -> %s'
              % (rate, tested, fresh_bad, reuse_bad, status))
    print('RESULT: %s' % ('clean-room decoder == emulated decoder' if ok else 'FAILED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
