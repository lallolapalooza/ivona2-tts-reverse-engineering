#!/usr/bin/env python3
"""Compare the range-decoder state sequence (engine vs port) for one parse frame."""
import os
import pickle
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))
sys.path.insert(0, os.path.join(HERE, 'codec_parts'))

RECORD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
FRAME = int(sys.argv[2]) if len(sys.argv) > 2 else 0

# ---- engine side --------------------------------------------------------- #
import codec_probe                                        # noqa: E402
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1,      # noqa: E402
                               UC_ARM_REG_R2, UC_ARM_REG_R3)

P = codec_probe.Probe(None, RECORD)
eng = []


def hook(uc, address, size, user):
    if address != 0x13AF88:
        return
    r = [uc.reg_read(x) for x in (UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
    ctx = r[0]
    code = struct.unpack('<I', uc.mem_read(ctx + 8, 4))[0]
    rng = struct.unpack('<I', uc.mem_read(ctx + 12, 4))[0]
    pos = struct.unpack('<I', uc.mem_read(ctx + 4, 4))[0]
    eng.append((r[1], r[2], pos, code, rng))


P.lib.uc.hook_add(4, hook)
P.steps(1, FRAME + 1)

# ---- port side ----------------------------------------------------------- #
import parse as PT                                        # noqa: E402
PT.f1496c0 = lambda *a, **k: None
PT.f14dc30 = lambda *a, **k: None

with open(os.path.join(ROOT, 'out', 'codec', 'steps', 'rec%06d.pkl' % RECORD), 'rb') as fh:
    d = pickle.load(fh)
rs = [x for x in d['seq'] if x['step'] == 'parse'][FRAME]
st = {k: bytearray(rs['before'][k]) for k in ('ctx', 'frame_info', 'coeffs')}
mine = []
_orig = PT.af88


def spy(ctx, tbl, idx):
    mine.append((getattr(tbl, 'addr', None), idx,
                 struct.unpack_from('<I', ctx, 4)[0],
                 struct.unpack_from('<I', ctx, 8)[0],
                 struct.unpack_from('<I', ctx, 12)[0]))
    return _orig(ctx, tbl, idx)


PT.af88 = spy
for f in PT.__dict__:                                    # patch module-level refs
    pass
PT.parse(st['ctx'], st['frame_info'], st['coeffs'])

n = max(len(eng), len(mine))
print('engine calls=%d port calls=%d' % (len(eng), len(mine)))
first = None
for i in range(n):
    e = eng[i] if i < len(eng) else None
    m = mine[i] if i < len(mine) else None
    if e and m and (e[0] == m[0] and e[1] == m[1] and e[2] == m[2] and e[3] == m[3]
                    and e[4] == m[4]):
        continue
    first = i
    break
print('first divergence at call', first)
for i in range(max(0, (first or 0) - 4), min(n, (first or 0) + 6)):
    e = eng[i] if i < len(eng) else None
    m = mine[i] if i < len(mine) else None
    print(' %4d eng=%s' % (i, ('tbl=%#x n=%#x pos=%#x code=%#010x rng=%#x' % e) if e else '-'))
    if m:
        print('      por=%s' % ('tbl=%s n=%#x pos=%#x code=%#010x rng=%#x'
                                % (hex(m[0]) if m[0] else 'list', m[1], m[2], m[3], m[4])))
