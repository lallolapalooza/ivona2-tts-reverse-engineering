"""Clean-room port of the IVONA "gap" codec AGC stage.

    gain(ctx, frame_info, samp, n)          # n == 480

Reproduces ARM `FUN_00149e54(ctx, frame_info, samp, 480)` (ELF vaddr 0x139e54)
and its callees:
  * `FUN_0014d9b0` (vaddr 0x13d9b0)  -- scaled sum-of-squares of the short
    buffer; returns (mantissa, exponent).  Ghidra lists 4 parameters but the
    body is `f(&mant, &exp, short *buf, int n)`; the gain call sites pass the
    two output pointers plus r2=samp / r3=n (the argument registers survive
    untouched into the `bl`).
  * `FUN_00149d84` (vaddr 0x139d84)  -- leading-zero count of a 16-bit value
    (returns 0..15, or 16 for input 0).

State read/written in `ctx` (all little-endian int32):
  +0x350c, +0x3544, +0x3550, +0x3554

The first call to FUN_0014d9b0 flags its buffer format with `buf_addr & 2`.
`gain` always hands it the spectrum buffer, whose guest address is 4-byte
aligned (bit1 == 0), so only the flag==False path is reachable here;
`flag` is exposed for completeness.  [INFERENCE]
"""

import struct

__all__ = ['gain']


def _u32(x):
    return x & 0xFFFFFFFF


def _s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def _s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def _rd32(b, off):
    return struct.unpack_from('<I', b, off)[0]


def _wr32(b, off, v):
    struct.pack_into('<I', b, off, v & 0xFFFFFFFF)


def _rd16s(b, off):
    return struct.unpack_from('<h', b, off)[0]


def _nlz(v):
    """FUN_00149d84: leading-zero count of a 16-bit value (16 if v == 0)."""
    v = _u32(v)
    if v == 0:
        return 0x10
    if (v & 0xff00) == 0:
        if (v & 0xfff0) == 0:
            a, b, c, d = 0xf, 0xe, 0xd, 0xc
        else:
            v = _s32(v) >> 4
            a, b, c, d = 0xb, 0xa, 9, 8
    elif (v & 0xf000) == 0:
        v = _s32(v) >> 8
        a, b, c, d = 7, 6, 5, 4
    else:
        v = _s32(v) >> 0xc
        a, b, c, d = 3, 2, 1, 0
    if (v & 0xc) != 0:
        if (v & 8) == 0:
            d = c
        return d
    if (v & 0xe) == 0:
        b = a
    return b


def _divsi3(a, b):
    """ARM __divsi3 (signed, truncate toward zero; /0 -> 0)."""
    a = _s32(a)
    b = _s32(b)
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return _u32(q)


def _d9b0(buf, n, flag=False):
    """FUN_0014d9b0(&mant, &exp, buf, n) -> (mantissa, exponent).

    Scaled sum of squares over the 16-bit samples in `buf`; the accumulator is
    halved (shifted right 2) whenever its top bits would overflow, the number
    of halvings tracked in the exponent.  `flag` mirrors `(buf_addr & 2) != 0`.
    """
    r32 = lambda off: _s32(struct.unpack_from('<I', buf, off)[0])
    r16 = lambda off: struct.unpack_from('<h', buf, off)[0]

    if flag:
        r5, r4, ip = 1, 3, 2
        v = r16(0)
        r1 = _u32(v * v)
    else:
        r5, r4, ip = 0, 2, 0
        r1 = 0
    r8 = n - 1

    goto_t = False
    if _s32(r5) < _s32(r8):
        # 0x14d9f0: first pair (shorts ip/2, ip/2+1)
        w = r32(ip)
        hi = _s32(w) >> 16
        r5 = _u32(hi * hi + r1)
        r1 = _u32(_s16(w) * _s16(w) + r5)
        if _s32(r1) >= 0:
            r5 = r4
            ptr = r4
            while True:
                if _s32(r8) <= _s32(r5):
                    r4 = 0
                    goto_t = True
                    break
                w = r32(2 * ptr)
                ptr += 2
                r5 += 2
                hi = _s32(w) >> 16
                r1 = _u32(r1 + _s16(w) * _s16(w) + hi * hi)
                if _s32(r1) < 0:
                    break
        else:
            r5 = r4

        if not goto_t:
            # 0x14da48
            if _s32(r8) <= _s32(r5):
                r4 = 2
                goto_t = True
            else:
                r1 = _u32(r1) >> 2
                ptr = r5
                acc = r5
                r4 = 2
                sb = r5
                while True:
                    w = r32(2 * ptr)
                    ptr += 2
                    r7 = r4 + 2
                    sl = _u32(_s16(w) * _s16(w) + (_s32(w) >> 16) ** 2)
                    acc += 2
                    sl2 = _u32(r1 + (sl >> (r4 & 31)))
                    r1 = sl2
                    if _s32(sl2) < 0:
                        r4 = r7
                        r1 = _u32(sl2) >> 2
                    if not (_s32(r8) > _s32(acc)):
                        break
                r3 = _u32((n - 2) - sb)
                r3 &= ~1 & 0xFFFFFFFF
                r5 = sb + 2 + r3
    else:
        r4 = 0
        goto_t = True

    # 0x14dabc (tail)
    if r5 == r8:
        v = _s16(r16(2 * r5))
        r1 = _u32(r1 + (_s32(_u32(v * v)) >> (r4 & 31)))
    if r1 & 0xc0000000:
        r1 = _u32(r1) >> 2
        r4 += 2
    return r1, r4


def _gain_from(sm, m, n):
    """Head of the AGC adjustment, 0x139edc..0x139f9c.

    `sm` = ctx+0x3550 value (u32), `m` = energy mantissa (s32).
    Writes the reshaped state mantissa back to ctx+0x3550 and returns
    (gain, step_numerator) where step = gain_from.. -> divsi3(step_numerator, n).
    """
    if (_u32(sm) >> 16) == 0:
        iv1 = _nlz(_s16(sm)) + 0x10
    else:
        iv1 = _nlz(_s32(sm) >> 16)
    u3 = _u32(0x18 - (iv1 - 1))
    iv1n = _u32(_u32(sm) << ((iv1 - 1) & 31))
    mask = _u32(u3 & (~(_s32(u3) >> 31) & 0xFFFFFFFF))
    iv7 = _u32(_s32(m) >> (mask & 31))
    if _s32(iv7) < 1:
        iv7 = 1
    _wr32(_CTX, 0x3550, iv1n)

    val = _divsi3(iv1n, iv7)
    if _s32(val) < 1:
        return 0, 0x1000

    v = _u32(val)
    if (v >> 16) == 0:
        u3b = _nlz(_s16(v)) + 0x10
    else:
        u3b = _nlz(_s32(v) >> 16)
    u4 = _u32(0x18 - u3b)
    if _s32(u4) < 1:
        u4 = _u32(0x38 - u3b)
    base = 0x8000 if (u3b & 1) else 0xb486
    u3c = _s32(_u32(_s32(base) >> (_s32(u3b) >> 1)))
    s = u4 & 31
    rot = _u32((v >> s) | ((v << ((32 - s) & 31)) & 0xFFFFFFFF))
    r7v = _s16(_u32((rot & 0x7f) * 213))
    hi = _s32(u3c) >> 16
    lo = _u32(u3c) & 0xFFFF
    prod_lo = _s32(_u32(r7v * lo)) >> 16
    gainv = _s32(_u32(_u32(r7v * hi) + u3c) + prod_lo)
    return gainv, _s32(_u32(0x1000 - gainv))


_CTX = None  # set by gain() so _gain_from can update ctx+0x3550


def gain(ctx, frame_info, samp, n):
    """FUN_00149e54: automatic gain control on the n-sample spectrum buffer."""
    global _CTX
    _CTX = ctx
    if _rd32(ctx, 0x350c) == 0:
        if _rd32(ctx, 0x3544) != 0:
            m, e = _d9b0(samp, n, False)          # local_20 = m, local_1c = e
            se = _s32(_rd32(ctx, 0x3554))
            sm = _rd32(ctx, 0x3550)
            if se < e:
                csm = _u32(_s32(sm) >> ((e - se) & 31))
                _wr32(ctx, 0x3550, csm)
                cm = _s32(m)
            else:
                if e < se:
                    m = _u32(_s32(m) >> ((se - e) & 31))
                csm = sm
                cm = _s32(m)
            if _s32(csm) < cm:
                gv, stepn = _gain_from(csm, cm, n)
                step = _s32(_divsi3(stepn, n))
                p = 0
                g = gv
                for _ in range(n):
                    x = _rd16s(samp, p)
                    t = _s32(g + step)
                    if not (t < 0x1000):
                        t = 0x1000
                    struct.pack_into('<h', samp, p,
                                     _s16(_s32(x * g) >> 12))
                    g = t
                    p += 2
        _wr32(ctx, 0x3544, 0)
    else:
        m, e = _d9b0(samp, n, False)
        _wr32(ctx, 0x3550, m)
        _wr32(ctx, 0x3554, e)
        _wr32(ctx, 0x3544, 1)


def _selftest():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import check

    def call(st, r):
        gain(st['ctx'], st['frame_info'], st['samp'], r['args'][3])

    return check('gain', call)


if __name__ == '__main__':
    total, failed = _selftest()
    raise SystemExit(1 if failed else 0)
