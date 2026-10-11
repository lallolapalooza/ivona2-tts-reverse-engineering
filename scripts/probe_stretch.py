#!/usr/bin/env python3
"""Probe the engine's `pau` silence restretch (`FUN_00063350` -> `FUN_00062d14`).

`FUN_0005d7c4`:42256-42400 aligns the silence part of a `pau` unit to the pause
target from the segment `end` feature by calling

    FUN_00063350(obj, from, to, newlen)       # 0x53350
      cur    = FUN_000624e8(obj, from, to)    # samples in segments [from..to]
      factor = newlen / cur
      FUN_00062d14(obj, from, to, factor)     # 0x52d14, the SOLA time-stretch

which replaces the object's `pms[]`/block arrays in place (`FUN_00062688`
reallocates, the old arrays are freed).  This runner loads only the CDXV /
diphonedb (no voice plug-in), decodes one unit with the real codec, snapshots
`{N, pms}` before and after the call and prints the block lengths, so the
stretch's *selection* and *length* semantics can be read off directly.

    ~/venvs/re/bin/python scripts/probe_stretch.py --unit 294435 --from 0 --to 16 \
        --target 220
    ~/venvs/re/bin/python scripts/probe_stretch.py --unit 294435 --from 0 --to 16 \
        --target 2507 --raw-factor 0.5      # one single halving pass (seconds)

Verified runs (ELF vaddrs, `--target 2507 --raw-factor 0.5`): the range's 17
segments / 2507 samples become **8 blocks of 147 samples** (1176 samples), i.e.
the halving pass keeps every second source period, and `--raw-factor 1` is a
no-op.  The *composite* factors the engine uses (220/2507, 1102/3392, …) compose
2–3 such passes and are slow in emulation (minutes): the window/target model of
`refimpl/tts.py:pause_align` is instead verified against the engine's own
`stream_trace.txt` lines (6/6, report_pipeline.md sec.13.5).
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))
sys.path.insert(0, os.path.join(ROOT, 'refimpl'))

import decode_unit as du                            # noqa: E402
import segment_unit as su                           # noqa: E402

V_FUN_63350 = 0x53350          # FUN_00063350  setlength via FUN_00062d14
V_FUN_62D14 = 0x52D14          # FUN_00062d14  SOLA time stretch


def fbits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]


def dump(eng, obj, label, raw=None):
    lib = eng.lib
    n = lib.u32(obj + 8)
    ptr = lib.u32(obj + 0xC)
    pms = list(struct.unpack('<%di' % n, lib.rd(ptr, 4 * n)))
    lens = [pms[0]] + [pms[i] - pms[i - 1] for i in range(1, n)]
    print('%-6s N=%-3d total=%-6d pms=%s' % (label, n, pms[-1] if n else 0, pms))
    print('       segs=%s' % (lens,))
    if raw:
        bptr = lib.u32(obj + 0x10)
        data = b''
        for i in range(n):
            p = lib.u32(bptr + 4 * i)
            data += lib.rd(p, 2 * lens[i])
        with open(raw, 'wb') as fh:
            fh.write(data)
        print('       block PCM -> %s (%d B)' % (raw, len(data)))
    return n, pms, lens


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--obb', default=None)
    ap.add_argument('--unit', type=int, required=True)
    ap.add_argument('--from', dest='frm', type=int, default=0)
    ap.add_argument('--to', type=int, required=True)
    ap.add_argument('--target', type=int, required=True,
                    help='the `newlen` FUN_00063350 is called with (samples)')
    ap.add_argument('--raw-factor', type=float, default=None,
                    help='call FUN_00062d14 directly with this factor instead of '
                         'deriving it from --target (a multi-pass restretch can take '
                         'minutes under the emulator; factors >= 0.5 return in seconds)')
    ap.add_argument('--dump-blocks', metavar='PATH',
                    help='write the object\'s blocks (concatenated int16) after the '
                         'call, for a bit-exact diff against the model')
    args = ap.parse_args()

    obb = args.obb
    if obb is None:
        import tts as P
        obb = P._resolve(P.VOICES['kendra']['obb'])
    eng = su.Engine(obb)
    obj, u = eng.unit(args.unit)
    print('unit %d: rate=%d' % (args.unit, u['rate']))
    n0, pms0, _l0 = dump(eng, obj, 'before')

    cur = pms0[args.to] if args.frm == 0 else pms0[args.to] - pms0[args.frm - 1]
    if args.raw_factor is not None:
        factor = args.raw_factor
        ret = eng.lib.call(V_FUN_62D14, [obj, args.frm, args.to, fbits(factor)])
        print('FUN_00062d14(obj, %d, %d, %.9g) -> %.9g' % (args.frm, args.to, factor,
                                                          struct.unpack('<f', struct.pack('<I', ret))[0]))
    else:
        factor = args.target / float(cur)
        print('cur(segments %d..%d) = %d samples, factor = %d/%d = %.9g'
              % (args.frm, args.to, cur, args.target, cur, factor))
        ret = eng.lib.call(V_FUN_63350, [obj, args.frm, args.to, fbits(factor)])
        print('FUN_00063350 -> %.9g' % struct.unpack('<f', struct.pack('<I', ret))[0])
    n1, pms1, lens1 = dump(eng, obj, 'after', args.dump_blocks)
    print('range length before=%d after=%d  (delta %+d)' % (cur, pms1[-1], pms1[-1] - pms0[-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
