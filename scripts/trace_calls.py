#!/usr/bin/env python3
"""Log r0..r3 at the entry of the codec helper functions while the oracle runs.

Used to recover the arguments that Ghidra omitted at call sites (it prints fewer
args than the callee declares; the missing ones live in leftover registers).

Usage: ~/venvs/re/bin/python scripts/trace_calls.py --record 0 --packets 1 --frames 2
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))

from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_LR)  # noqa: E402
import codec_probe  # noqa: E402

WATCH = {
    0x13AF88: 'f14af88 range_decode',
    0x13B1E4: 'f14b1e4 bitpos',
    0x13B450: 'f14b450 check_end',
    0x138CB0: 'f148cb0 config',
    0x138A20: 'f148a20 coeff_tree',
    0x138F20: 'f148f20 scale_idx',
    0x13B104: 'f14b104 cb_bits',
    0x1397A8: 'f1497a8 cb_amp',
    0x1396C0: 'f1496c0 clear_bands',
    0x13DC30: 'f14dc30 scale_ramp',
    0x13899C: 'f14899c set_gaindb',
    0x13DCA4: 'f14dca4 win_norm',
    0x13DD18: 'f14dd18 xform',
    0x13E4EC: 'f14e4ec dequant',
    0x13E29C: 'f14e29c matmul',
    0x140A14: 'f150a14',
    0x13F940: 'f14f940',
    0x1407BC: 'f1507bc',
    0x140028: 'f150028 imdct8',
    0x14027C: 'f15027c imdct16',
    0x13DAFC: 'f14dafc post',
    0x139E54: 'f149e54 gain',
    0x13D9B0: 'f14d9b0 energy',
    0x13ADD4: 'f14add4 setup',
    0x13E0EC: 'f14e0ec sign',
    0x13E1A0: 'f14e1a0 sign2',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--record', type=int, default=0)
    ap.add_argument('--packets', type=int, default=1)
    ap.add_argument('--frames', type=int, default=2)
    ap.add_argument('--max-per', type=int, default=400)
    ap.add_argument('--only', default=None, help='comma-separated pc names')
    args = ap.parse_args()

    P = codec_probe.Probe(args.obb, args.record)
    calls = collections.defaultdict(list)
    counts = collections.Counter()
    only = set(args.only.split(',')) if args.only else None

    def hook(uc, address, size, user):
        name = WATCH.get(address)
        if name is None:
            return
        if only and name.split()[0] not in only:
            return
        counts[name] += 1
        if counts[name] <= args.max_per:
            calls[name].append(tuple(uc.reg_read(r) for r in
                                     (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                      UC_ARM_REG_R3)))

    P.lib.uc.hook_add(4, hook)      # UC_HOOK_CODE == 4
    P.steps(args.packets, args.frames)

    for name in sorted(calls):
        print('=== %s  (%d calls) ===' % (name, counts[name]))
        for a in calls[name]:
            print('   r0=%#x r1=%#x r2=%#x r3=%#x' % a)


if __name__ == '__main__':
    main()
