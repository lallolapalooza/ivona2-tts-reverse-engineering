#!/usr/bin/env python3
"""Chained stage verification: run the port's *own* pipeline from a fresh reset and
compare every buffer against the engine's per-step snapshots (``codec_probe.py``).

This is stronger than the per-stage self-tests: it starts from a reset context and
carries the ported state through the whole chain (bitinit -> parse -> dequant ->
setup -> gain -> xform -> post), so a bug that only shows up after several stages
cannot hide.

Usage:  ~/venvs/re/bin/python scripts/verify_codec.py [--record N]
"""
import argparse
import glob
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'codec_parts'))

import codec_spec as CS                                  # noqa: E402
import parse as P                                        # noqa: E402
import dequant as D                                      # noqa: E402
import setup as S                                        # noqa: E402
import gain as G                                         # noqa: E402
import post as PP                                        # noqa: E402
import xform as X                                        # noqa: E402
import struct

BUFS = ('ctx', 'frame_info', 'coeffs', 'samp')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--record', type=int, default=None)
    args = ap.parse_args()

    pats = [os.path.join(ROOT, 'out', 'codec', 'steps', 'rec*.pkl')]
    if args.record is not None:
        pats = [os.path.join(ROOT, 'out', 'codec', 'steps', 'rec%06d.pkl' % args.record)]
    files = sorted(p for p in pats for p in glob.glob(p))
    assert files, 'no probe pickles'

    steps = 0
    fails = 0
    for path in files:
        with open(path, 'rb') as fh:
            d = pickle.load(fh)
        sp = CS.Spec()
        pi = -1
        pkt = None
        for r in d['seq']:
            if r['pkt'] != pi:
                pi = r['pkt']
                pkt = d['packets'][pi]
            st = r['step']
            if st == 'bitinit':
                P.bitinit(sp.ctx, pkt, len(pkt))
            elif st == 'parse':
                P.parse(sp.ctx, sp.fi, sp.coeffs, 1)
            elif st == 'dequant':
                # FUN_00147f74 bumps the frame counter between parse and dequant
                struct.pack_into('<I', sp.ctx, 0x2c34,
                                 (struct.unpack_from('<I', sp.ctx, 0x2c34)[0] + 1))
                D.dequant(sp.ctx, sp.fi, sp.samp, sp.coeffs)
            elif st == 'setup':
                S.setup(sp.ctx, sp.fi, sp.samp, r['args'][3], r['args'][4])
            elif st == 'gain':
                sp.ctx[0x2438:0x2438 + 960] = sp.samp[:960]
                struct.pack_into('<I', sp.ctx, 0x350c, 0)
                struct.pack_into('<I', sp.ctx, 0x2c2c, 0)
                G.gain(sp.ctx, sp.fi, sp.samp, r['args'][3])
            elif st == 'xform':
                X.xform(sp.ctx, sp.fi, sp.samp, r['args'][3])
            elif st == 'post':
                PP.post(sp.samp, sp.ctx, r['args'][5])
            else:
                continue
            steps += 1
            for name, buf in (('ctx', sp.ctx), ('frame_info', sp.fi),
                              ('coeffs', sp.coeffs), ('samp', sp.samp)):
                exp = r['after'][name]
                got = bytes(buf)[:len(exp)]
                if got != exp:
                    fails += 1
                    bad = next((i for i in range(min(len(got), len(exp)))
                                if got[i] != exp[i]), None)
                    print('FAIL %s pkt=%d frame=%d %-6s -> %s off=%s'
                          % (os.path.basename(path), r['pkt'], r['frame'], st, name,
                             hex(bad) if bad is not None else 'len'))
                    break
    print('chained verification: files=%d steps=%d buffer-compares=%d failed=%d'
          % (len(files), steps, steps * len(BUFS), fails))
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
