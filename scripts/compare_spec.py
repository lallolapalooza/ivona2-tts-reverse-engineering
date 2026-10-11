#!/usr/bin/env python3
"""Acceptance check: ``codec_spec.py`` (pure Python) vs ``decode_unit.py`` (emulator).

For each sampled unit record both decoders produce PCM; the pure-Python port must
be **bit-identical**.  ``decode_unit`` is only used as the oracle here -- the
decoder under test (``codec_spec``) never imports it.

Usage
  ~/venvs/re/bin/python scripts/compare_spec.py --obb "<kendra obb>" --count 50
  ~/venvs/re/bin/python scripts/compare_spec.py --voice amy --count 50
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))

import decode_unit                                        # noqa: E402
import codec_spec                                         # noqa: E402


def safe_record(obb, i):
    """Like ``obb.record(i)`` but tolerant of the OBB's rare out-of-range index entries."""
    try:
        off, ln = obb.index(i)
        if off == 0 or ln < 12 or off + ln > len(obb.data):
            return None
        return obb.record(i)
    except Exception:                                     # noqa: BLE001
        return None


def pick_records(obb, count):
    """Evenly spread non-empty records with N >= 16 across the whole index."""
    n = obb.n_rec
    picks = []
    k = 0
    while len(picks) < count and k < n:
        want = k * (n - 1) // max(1, count - 1) if count > 1 else 0
        i = want
        rec = None
        while i < n and i < want + 400:
            rec = safe_record(obb, i)
            if rec and rec['N'] >= 16:
                break
            i += 1
            rec = None
        if rec is not None:
            picks.append(i)
        k += 1
    return sorted(set(picks))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--voice', default=None)
    ap.add_argument('--count', type=int, default=50)
    ap.add_argument('--records', default=None, help='explicit comma list')
    ap.add_argument('--rate', type=int, default=None,
                    help='output rate (default: the OBB\'s declared rate)')
    args = ap.parse_args()

    obb = decode_unit.Obb(args.obb or decode_unit.find_obb(args.voice or 'kendra'))
    print('OBB %s name=%s recs=%d' % (obb.path, obb.name, obb.n_rec))
    recs = ([int(x) for x in args.records.split(',')] if args.records
            else pick_records(obb, args.count))
    print('checking %d records' % len(recs))

    rate = args.rate or obb.rate
    print('comparing at %d Hz' % rate)
    emu = decode_unit.Codec(rate=rate)
    identical = 0
    tested = 0
    failed = []
    t0 = time.time()
    for idx, r in enumerate(recs):
        rec = safe_record(obb, r)
        if rec is None:
            continue
        tested += 1
        win = obb.window(rec)
        eng = emu.decode_window(obb.cksum, win, rec['Y'], rec['samples'])
        sp = codec_spec.Spec(out_rate=rate)
        mine = sp.decode_window(obb.cksum, win, rec['Y'], rec['samples'])
        n = min(len(eng), len(mine))
        same = sum(1 for i in range(n) if eng[i] == mine[i])
        ok = (same == n and len(eng) == len(mine))
        if ok:
            identical += 1
        else:
            first = next((i for i in range(n) if eng[i] != mine[i]), None)
            failed.append((r, same, n, first,
                           eng[first] if first is not None else None,
                           mine[first] if first is not None else None))
        if (idx + 1) % 10 == 0:
            print('  %d/%d  ok=%d  (%.1fs)' % (idx + 1, len(recs), identical,
                                               time.time() - t0))
    print('RESULT %s: picked=%d tested=%d bit-identical=%d failed=%d  (%.1fs)'
          % (obb.name, len(recs), tested, identical, len(failed), time.time() - t0))
    print('  records: %s' % (recs if len(recs) <= 60 else
                             '%s ... %s' % (recs[:12], recs[-12:])))
    for f in failed[:20]:
        print('  MISMATCH rec=%d same=%d/%d first=%s eng=%s mine=%s' % f)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
