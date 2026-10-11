"""Clean-room port of the IVONA gap codec **parse** stage (range/Huffman decode).

Ported from the Ghidra decompilation of ``libttsivonavoice.so``.  The comments quote
Ghidra addresses; **ELF vaddr = Ghidra - 0x10000** and the whole port works in ELF
vaddrs.  The static codebooks live in ``out/codec/tables.bin`` (read through
``tables``); nothing here touches the .so or the emulator.

  FUN_0014b17c  0x13b17c  bit-reader init from a packet
  FUN_0014af88  0x13af88  range-decoder symbol decode
  FUN_0014b1e4  0x13b1e4  consumed-bit count
  FUN_0014b450  0x13b450  end-of-stream check
  FUN_00148cb0  0x138cb0  per-rate configuration
  FUN_0014966c  0x13966c  index -> linear amplitude
  FUN_00148f20  0x138f20  band-gain table
  FUN_0014d100  0x14d100  bit-tree coefficient decode
  FUN_001497a8  0x1497a8  codebook -> band amplitudes (+ shaping)
  FUN_0014d944  0x14d944  monotone-isation helper
  FUN_0014899c  0x14899c  per-channel gain offsets
  FUN_0014e0ec  0x13e0ec  coefficient sign decode
  FUN_00148a20  0x138a20  coefficient decode driver
  FUN_00148190  0x138190  the parse entry point

Two helpers are shared with the transform stage and live in ``dsp`` (written by the
xform porter): FUN_001496c0 -> ``f1496c0`` and FUN_0014dc30 -> ``f14dc30``.
"""
from prims import (u32, s32, s16, ld_u16, ld_s16, ld_u32, ld_s32,
                   st_u16, st_u32)
from tables import tables

try:                                     # dsp.py is written by the xform porter
    from dsp import f1496c0, f14dc30
except ImportError:                      # pragma: no cover
    f1496c0 = f14dc30 = None

T = tables()

A_D324 = 0x17d324        # rate-code table (u32: 8, 12, 16, 24)
A_D334 = 0x17d334        # first-frame block-type codebook
A_D344 = 0x17d344        # block-size codebook
A_D30C = 0x17d30c        # module-gain codebook
A_D318 = 0x17d318
A_D354 = 0x17d354
A_D364 = 0x17d364
A_D37C = 0x17d37c
A_D304 = 0x17d304
A_DBA4 = 0x17dba4
A_D4F0 = 0x17d4f0
A_E2D4 = 0x17e2d4
A_E2E4 = 0x17e2e4
A_E30C = 0x17e30c
A_E2AC = 0x17e2ac
A_E10C = 0x17e10c
A_E040 = 0x17e040
A_DFD8 = 0x17dfd8
A_DF94 = 0x17df94
A_DF44 = 0x17df44
A_DC34 = 0x17dc34
A_DDAE = 0x17ddae
A_8BF4 = 0x178bf4
A_8CFC = 0x178cfc
A_8D5C = 0x178d5c
A_8E00 = 0x178e00
A_95_14 = 0x185514      # PTR_DAT_00195514   (Ghidra 0x195514)
A_95_2C = 0x18552c      # PTR_DAT_0019552c   (Ghidra 0x19552c)
A_GOT = 0x185db4        # DT_PLTGOT          (Ghidra __DT_PLTGOT)


class StaticTbl(object):
    """A cumulative-frequency table in the static image."""

    __slots__ = ('addr',)

    def __init__(self, addr):
        self.addr = addr

    def u16(self, i):
        return T.u16(self.addr + 2 * i)


class ListTbl(object):
    """A small cumulative-frequency table consulted from 'stack' storage."""

    __slots__ = ('vals',)

    def __init__(self, vals):
        self.vals = vals

    def u16(self, i):
        return self.vals[i]


# --------------------------------------------------------------------------- #
# FUN_0014b17c  (Ghidra 142321-142348, ELF 0x13b17c)
# --------------------------------------------------------------------------- #
def bitinit(ctx, pkt, ln):
    if s32(ln) < 0x401:
        ctx[0x14:0x14 + ln] = pkt[:ln]
        st_u32(ctx, 4, 0)
        st_u32(ctx, 0, ln)
        b0 = pkt[0] if ln > 0 else 0
        b1 = pkt[1] if ln > 1 else 0
        b2 = pkt[2] if ln > 2 else 0
        b3 = pkt[3] if ln > 3 else 0
        st_u32(ctx, 16, 0)
        st_u32(ctx, 8, (b3 | (b0 << 24) | (b1 << 16) | (b2 << 8)) & 0xFFFFFFFF)
        st_u32(ctx, 12, 0xFFFF)
    else:
        st_u32(ctx, 16, 0xFFFFFFF8)


# --------------------------------------------------------------------------- #
# FUN_0014af88  (Ghidra 142187-142297, ELF 0x13af88)   range-decoder decode
# --------------------------------------------------------------------------- #
def _af88_store(ctx, rng, code, pos, sym):
    if rng != 0:
        st_u32(ctx, 4, pos)
        st_u32(ctx, 8, code)
        st_u32(ctx, 12, rng)
        return sym
    st_u32(ctx, 16, 0xFFFFFFFC)
    return 0


def _af88_renorm(ctx, rng, code, pos, sym):
    if rng & 0xFF000000:
        return _af88_store(ctx, (rng >> 16) & 0xFFFFFFFF, code, pos, sym)
    if (rng & 0xFFFF0000) == 0:
        if (code >> 16) != 0:
            st_u32(ctx, 16, 0xFFFFFFFD)
            return 0
        ln = ld_u32(ctx, 0)
        if s32(ln) <= s32(pos):
            return _af88_store(ctx, rng, (code << 16) & 0xFFFFFFFF, pos, sym)
        code = ((code << 8) | ctx[0x18 + pos]) & 0xFFFFFFFF
        pos = (pos + 1) & 0xFFFFFFFF
    else:
        if (code >> 24) != 0:
            st_u32(ctx, 16, 0xFFFFFFFD)
            return 0
        rng = (rng >> 8) & 0xFFFFFFFF
    ln = ld_u32(ctx, 0)
    u2 = ln
    if s32(pos) < s32(ln):
        u2 = ctx[0x18 + pos]
    code = (code << 8) & 0xFFFFFFFF
    if s32(pos) < s32(ln):
        pos = (pos + 1) & 0xFFFFFFFF
        code = (code | u2) & 0xFFFFFFFF
    return _af88_store(ctx, rng, code, pos, sym)


def af88(ctx, tbl, idx):
    """FUN_0014af88: decode one symbol (0 on error, error code in ctx+0x10)."""
    code = ld_u32(ctx, 8)
    rng = ld_u32(ctx, 12)
    pos = ld_u32(ctx, 4)
    if ld_u32(ctx, 16) != 0:
        return 0
    u8 = tbl.u16(idx)
    if code < ((rng * u8) & 0xFFFFFFFF):
        p = idx - 1
        idx = idx - 1
        while True:
            u2 = tbl.u16(p)
            u6 = (rng * u2) & 0xFFFFFFFF
            if u6 <= code:
                break
            p -= 1
            idx -= 1
            u8 = u2
            if u2 == 0:
                st_u32(ctx, 16, 0xFFFFFFFE)
                return 0
        rng = (rng * ((u8 - u2) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return _af88_renorm(ctx, rng, (code - u6) & 0xFFFFFFFF, pos, idx)
    p = idx + 1
    i3 = idx + 1
    u2 = u8
    while True:
        u8 = tbl.u16(p)
        if code < ((rng * u8) & 0xFFFFFFFF):
            u6 = (rng * u2) & 0xFFFFFFFF
            rng = (rng * ((u8 - u2) & 0xFFFFFFFF)) & 0xFFFFFFFF
            return _af88_renorm(ctx, rng, (code - u6) & 0xFFFFFFFF, pos, idx)
        p += 1
        idx = i3
        i3 += 1
        u2 = u8
        if u8 == 0xFFFF:
            st_u32(ctx, 16, 0xFFFFFFFE)
            return 0


# --------------------------------------------------------------------------- #
# FUN_0014b1e4  (Ghidra 142350-142454, ELF 0x13b1e4)   consumed-bit count
# --------------------------------------------------------------------------- #
def _b1e4_tail(ctx, iv5):
    prod = (ld_u32(ctx, 4) * 8) & 0xFFFFFFFF
    ret = s32((prod + iv5 - 14) & 0xFFFFFFFF)
    bytepos = s32((prod + iv5 - 7) & 0xFFFFFFFF) >> 3
    return ret, bytepos


def b1e4(ctx):
    """Returns ``(ret, bytepos)``; ``ret`` is what the engine leaves in r0."""
    v = (ld_u32(ctx, 0xc) - 1) & 0xFFFFFFFF
    if (v >> 16) == 0:
        if (v & 0xFFFF) == 0:
            return _b1e4_tail(ctx, 0x20)
        v = (v << 16) & 0xFFFFFFFF
        s = s32(v) >> 16
        if (s & 0xFF00) == 0:
            if (s & 0xFFF0) == 0:
                iv6, iv2, iv4, iv5 = 0x1F, 0x1E, 0x1D, 0x1C
            else:
                v = ((s32(v) >> 0x14) << 16) & 0xFFFFFFFF
                iv6, iv2, iv4, iv5 = 0x1B, 0x1A, 0x19, 0x18
        elif (s & 0xF000) == 0:
            v = ((s32(v) >> 0x18) << 16) & 0xFFFFFFFF
            iv6, iv2, iv4, iv5 = 0x17, 0x16, 0x15, 0x14
        else:
            v = ((s32(v) >> 0x1C) << 16) & 0xFFFFFFFF
            iv6, iv2, iv4, iv5 = 0x13, 0x12, 0x11, 0x10
    else:
        v = ((v >> 16) << 16) & 0xFFFFFFFF
        s = s32(v) >> 16
        if (s & 0xFF00) == 0:
            if (s & 0xFFF0) == 0:
                iv6, iv2, iv4, iv5 = 0xF, 0xE, 0xD, 0xC
            else:
                v = ((s32(v) >> 0x14) << 16) & 0xFFFFFFFF
                iv6, iv2, iv4, iv5 = 0xB, 10, 9, 8
        elif (s & 0xF000) == 0:
            v = ((s32(v) >> 0x18) << 16) & 0xFFFFFFFF
            iv6, iv2, iv4, iv5 = 7, 6, 5, 4
        else:
            v = ((s32(v) >> 0x1C) << 16) & 0xFFFFFFFF
            iv6, iv2, iv4, iv5 = 3, 2, 1, 0
    v = v >> 16
    if (v & 0xC) == 0:
        iv5 = iv2
        if (v & 0xE) == 0:
            iv5 = iv6
    elif (v & 8) == 0:
        iv5 = iv4
    return _b1e4_tail(ctx, iv5)


# --------------------------------------------------------------------------- #
# FUN_0014b450  (Ghidra 142499-142519, ELF 0x13b450)   stream-end check
# --------------------------------------------------------------------------- #
def b450(ctx):
    ret, bytepos = b1e4(ctx)
    if s32(ld_u32(ctx, 0)) < s32(bytepos):
        st_u32(ctx, 16, 0xFFFFFFFB)
        return
    u = ret & 7
    if u != 0:
        m = 0xFF >> u
        if (m & ctx[bytepos + 0x13]) != m:
            st_u32(ctx, 16, 0xFFFFFFFB)


# --------------------------------------------------------------------------- #
# FUN_00148cb0  (Ghidra 140720-140776, ELF 0x138cb0)   per-rate configuration
# --------------------------------------------------------------------------- #
def cb0(ctx, code):
    code = s32(code)
    if ld_s32(ctx, 0x2bd8) == code:
        return
    st_u32(ctx, 0x2be0, s32(s16(code) * 0x14))
    st_u32(ctx, 0x2be4, s32(s16(code) * 5))
    st_u32(ctx, 0x2bd8, code)
    if code == 8:
        st_u32(ctx, 0x2be8, 10)
        st_u32(ctx, 0x2cec, 0x185598)
        st_u32(ctx, 0x2cf0, 0x1856C8)
        ctx[0x1318:0x1358] = b'\x00' * 0x40
        ctx[0x2438:0x27f8] = b'\x00' * 0x3c0
        ctx[0x2bec:0x2c2c] = b'\x00' * 0x40
        st_u32(ctx, 0x2bd4, 0x17d2fc)
        st_u32(ctx, 0x2bb8, 100)
        st_u32(ctx, 0x3510, 0)
        st_u32(ctx, 0x2c2c, 1)
        st_u32(ctx, 0x2bd0, 0x17d2f8)
        st_u32(ctx, 0x2bbc, 1)
        return
    st_u32(ctx, 0x2be8, 0x10)
    st_u32(ctx, 0x2cec, 0x185650)
    st_u32(ctx, 0x2cf0, 0x185780)
    ctx[0x1318:0x1358] = b'\x00' * 0x40
    ctx[0x2438:0x27f8] = b'\x00' * 0x3c0
    ctx[0x2bec:0x2c2c] = b'\x00' * 0x40
    st_u32(ctx, 0x2bb8, 100)
    st_u32(ctx, 0x3510, 0)
    st_u32(ctx, 0x2c2c, 1)
    st_u32(ctx, 0x2bbc, 1)
    if code == 0x18:
        st_u32(ctx, 0x2bd4, 0x17d2d8)
        st_u32(ctx, 0x2bd0, 0x17d2d4)
    elif code == 0x10:
        st_u32(ctx, 0x2bd4, 0x17d2e4)
        st_u32(ctx, 0x2bd0, 0x17d2e0)
    elif code == 0xc:
        st_u32(ctx, 0x2bd4, 0x17d2f0)
        st_u32(ctx, 0x2bd0, 0x17d2ec)


# --------------------------------------------------------------------------- #
# FUN_0014966c  (Ghidra 141154-141180, ELF 0x13966c)   index -> amplitude
# --------------------------------------------------------------------------- #
def _f966c(x):
    x = s32(x)
    if x < 0:
        return 0
    u3 = x & 0x7F
    i2 = 1 << ((x >> 7) & 0xFF)
    i1 = s32(((u3 * (0x80 - u3)) & 0xFFFF) * -0xAE) >> 16
    if x < 0x800:
        i1 = s32(i2 * (u3 + i1)) >> 7
    else:
        i1 = (i2 >> 7) * (u3 + i1)
    return s32(i2 + i1)


# --------------------------------------------------------------------------- #
# FUN_00148f20  (Ghidra 140776-140832, ELF 0x138f20)   band-gain table
# --------------------------------------------------------------------------- #
def _f8f20(fi, a50, ctx, flag):
    out = []
    for k in range(4):
        base = ld_s32(ctx, 0x2bbc)
        if k == 0 and flag == 0:
            v = ld_u32(a50, 0)
        else:
            v = (base + ld_u32(a50, 4 * k) - 4) & 0xFFFFFFFF
        st_u32(ctx, 0x2bbc, v)
        x = s16(v)
        y = s32(x * 0x1B + 0x880 + (s32(x * 0x1451) >> 16))
        if 0xF7E < y:
            y = 0xF7F
        out.append(_f966c(y))
    for k in range(4):
        st_u32(fi, 0x10 + 4 * k, out[k])


# --------------------------------------------------------------------------- #
# FUN_0014d100  (Ghidra 143257-143422, ELF 0x14d100)   bit-tree decode
# --------------------------------------------------------------------------- #
def _f_d100(coeffs, off, ctx, n):
    def tree(base, idx, nbits):
        sub = ld_u16(T.rd(A_E2AC + 2 * idx, 2), 0)
        return af88(ctx, StaticTbl(base + sub * 2), nbits)

    def zero(a, b):
        st_u32(coeffs, off + 4 * a, 0)
        st_u32(coeffs, off + 4 * b, 0)

    l24 = l28 = l34 = l38 = l54 = l58 = l50 = l4c = l48 = l44 = l30 = l2c = l40 = l3c = 0
    if n < 1:
        zero(0, 1)
    else:
        l28 = tree(A_E10C, n, n >> 1)
        l34 = l28
        l24 = n - l28
        if l28 < 1:
            l34 = 0
            l38 = 0
            l54 = 0
            l58 = 0
            zero(0, 1)
        else:
            l38 = tree(A_E040, l28, l28 >> 1)
            l54 = l38
            l34 = l34 - l38
            if l38 < 1:
                l54 = 0
                l58 = 0
                zero(0, 1)
            else:
                l58 = tree(A_DFD8, l38, l38 >> 1)
                i1 = l58
                l54 = l54 - l58
                if l58 < 1:
                    zero(0, 1)
                else:
                    st_u32(coeffs, off, tree(A_DF94, l58, l58 >> 1))
                    st_u32(coeffs, off + 4, (i1 - ld_s32(coeffs, off)) & 0xFFFFFFFF)
    i1 = l54
    if l54 < 1:
        zero(2, 3)
    else:
        st_u32(coeffs, off + 8, tree(A_DF94, l54, l54 >> 1))
        st_u32(coeffs, off + 12, (i1 - ld_s32(coeffs, off + 8)) & 0xFFFFFFFF)
    i1 = l34
    if l34 < 1:
        l4c = l50 = 0
        zero(4, 5)
    else:
        l50 = tree(A_DFD8, l34, l34 >> 1)
        i2 = l50
        l4c = i1 - l50
        if l50 < 1:
            zero(4, 5)
        else:
            st_u32(coeffs, off + 16, tree(A_DF94, l50, l50 >> 1))
            st_u32(coeffs, off + 20, (i2 - ld_s32(coeffs, off + 16)) & 0xFFFFFFFF)
    i1 = l4c
    if l4c < 1:
        zero(6, 7)
    else:
        st_u32(coeffs, off + 24, tree(A_DF94, l4c, l4c >> 1))
        st_u32(coeffs, off + 28, (i1 - ld_s32(coeffs, off + 24)) & 0xFFFFFFFF)
    i1 = l24
    if l24 < 1:
        l2c = l30 = l44 = l48 = 0
        zero(8, 9)
    else:
        l30 = tree(A_E040, l24, l24 >> 1)
        l44 = l30
        l2c = i1 - l30
        if l30 < 1:
            zero(8, 9)
        else:
            l48 = tree(A_DFD8, l30, l30 >> 1)
            i1 = l48
            l44 = l44 - l48
            if l48 < 1:
                zero(8, 9)
            else:
                st_u32(coeffs, off + 32, tree(A_DF94, l48, l48 >> 1))
                st_u32(coeffs, off + 36, (i1 - ld_s32(coeffs, off + 32)) & 0xFFFFFFFF)
    i1 = l44
    if l44 < 1:
        zero(10, 11)
    else:
        st_u32(coeffs, off + 40, tree(A_DF94, l44, l44 >> 1))
        st_u32(coeffs, off + 44, (i1 - ld_s32(coeffs, off + 40)) & 0xFFFFFFFF)
    l40 = l3c = 0
    if l2c >= 1:
        i1 = l2c
        l40 = tree(A_DFD8, l2c, l2c >> 1)
        i2 = l40
        l3c = i1 - l40
        if l40 > 0:
            st_u32(coeffs, off + 48, tree(A_DF94, l40, l40 >> 1))
            st_u32(coeffs, off + 52, (i2 - ld_s32(coeffs, off + 48)) & 0xFFFFFFFF)
        else:
            zero(12, 13)
    else:
        zero(12, 13)
    i1 = l3c
    if l3c < 1:
        zero(14, 15)
    else:
        st_u32(coeffs, off + 56, tree(A_DF94, l3c, l3c >> 1))
        st_u32(coeffs, off + 60, (i1 - ld_s32(coeffs, off + 56)) & 0xFFFFFFFF)


# --------------------------------------------------------------------------- #
# FUN_0014d944  (Ghidra 143422-143464, ELF 0x14d944)   monotone-isation
# --------------------------------------------------------------------------- #
def _f_d944(arr, off, n):
    if n > 1:
        i4 = 0
        while i4 != n - 1:
            i3 = ld_s32(arr, off + 4 * (i4 + 1))
            i1 = i4
            j = i4 + 1
            while True:
                k = j - 1
                if ld_s32(arr, off + 4 * k) <= i3:
                    i1 = (i1 + 1) * 4
                    break
                i1 = i1 - 1
                st_u32(arr, off + 4 * j, s32(ld_s32(arr, off + 4 * k)))
                j -= 1
                if i1 == -1:
                    i1 = 0
                    break
            st_u32(arr, off + i1, i3)
            i4 += 1


# --------------------------------------------------------------------------- #
# FUN_0014b104  (Ghidra 142297-142321, ELF 0x13b104)   codebook bit lengths
# --------------------------------------------------------------------------- #
def _f_b104(dst, doff, ctx, ptbl, ntbl, count):
    for k in range(count):
        st_u32(dst, doff + 4 * k,
               af88(ctx, StaticTbl(T.u32(ptbl + 4 * k)), T.s32(ntbl + 4 * k)))


# --------------------------------------------------------------------------- #
# FUN_001497a8  (Ghidra 141247-141525, ELF 0x1497a8)   codebook -> amplitudes
# --------------------------------------------------------------------------- #
def _f97a8(b8, off, cb, a78, nbands):
    count = T.u32(cb)
    tblp = T.u32(cb + 4)
    lo = T.u32(cb + 8)
    i17 = T.u32(tblp + 4)
    v0 = ld_s32(a78, 0)

    def O(i):
        return ld_s32(b8, off + 4 * i)

    def S(a):
        return T.s32(a)

    if nbands > 0:
        for k in range(nbands):
            st_u32(b8, off + 4 * k, s32(T.s16(i17 + (v0 * nbands + k) * 2)))
    i16 = count
    if count > 1:
        i17 = 0xc
        i13 = 1
        while i13 < i16:
            v1 = ld_s32(a78, 4 * i13)
            i8 = T.u32(tblp + i17 + 4)
            if nbands == 0x10:
                t = i8 + v1 * 0x20
                for j in range(16):
                    st_u32(b8, off + 4 * j, (O(j) + T.s16(t + 2 * j)) & 0xFFFFFFFF)
            else:
                for j in range(nbands):
                    st_u32(b8, off + 4 * j,
                           (O(j) + T.s16(i8 + (s16(nbands) * s16(v1) + j) * 2)) & 0xFFFFFFFF)
            i16 = T.u32(cb)
            i13 += 1
            i17 += 0xc

    i16 = nbands - 1
    i7 = nbands * 4
    hi = lo + 4 * nbands
    local_48 = 0
    while True:
        i13 = O(0)
        i17 = i13 - S(lo)
        i14 = 0
        if nbands < 2:
            i8 = 0
        else:
            if nbands < 4:
                i8 = 0
                i14 = 1
            else:
                i11 = 2
                i8 = 0
                p10 = lo
                p12o = off
                while True:
                    i15 = (ld_s32(b8, p12o + 4) - S(p10 + 4)) - i13
                    i14 = i17
                    if i15 < i17:
                        i14 = i15
                    i13 = ld_s32(b8, p12o + 8)
                    if i15 < i17:
                        i8 = i11 - 1
                    i15 = (i13 - S(p10 + 8)) - ld_s32(b8, p12o + 4)
                    i17 = i14
                    if i15 < i14:
                        i17 = i15
                        i8 = i11
                    i11 += 2
                    p12o += 8
                    p10 += 8
                    i14 = ((nbands - 4) & 0xFFFFFFFE) + 3
                    if not (i11 < i16):
                        break
            i13 = i14 * 4
            i11 = 0
            while True:
                i15 = (ld_s32(b8, off + i11 + i13) - S(lo + i11 + i13)) - \
                      ld_s32(b8, off + i11 + i13 - 4)
                i6 = i14
                if i17 <= i15:
                    i15 = i17
                    i6 = i8
                i8 = i6
                i17 = i15
                i14 += 1
                i11 += 4
                if not (i14 < nbands):
                    break
        i14 = S(hi)
        i13 = (0x8000 - i14) - O(i16)
        if i13 < i17:
            i8 = nbands
            i17 = i13
        if i17 >= 0:
            break
        if i8 == 0:
            st_u32(b8, off, S(lo))
        elif i8 == nbands:
            st_u32(b8, off + 4 * i16, 0x8000 - i14)
        else:
            i17b = 0
            if i8 >= 1:
                i13b = 0
                i17b = 0
                while True:
                    i13b += 1
                    i17b += S(lo + 4 * (i13b - 1))
                    if i13b == i8:
                        break
            i13 = S(lo + 4 * i8) >> 1
            i17b = i17b + i13
            if i8 < nbands:
                i11 = 0x8000
                i15 = nbands
                p10 = lo + 4 * i16
                while True:
                    i15 -= 1
                    i11 -= i14
                    if i15 == i8:
                        break
                    i14 = S(p10)
                    p10 -= 4
            else:
                i11 = 0x8000
            i11 = (i13 - S(lo + 4 * i8)) + i11
            base14 = off + 4 * (i8 - 1)
            i15 = ((ld_s32(b8, base14) + ld_s32(b8, base14 + 4)) & 1) + \
                  ((ld_s32(b8, base14) + ld_s32(b8, base14 + 4)) >> 1)
            if i11 < i17b:
                i14b = i17b
                if i15 <= i17b:
                    i14b = i11
                    if i11 < i15:
                        i14b = i15
            else:
                i14b = i11
                if i15 <= i11:
                    i14b = i17b
                    if i17b < i15:
                        i14b = i15
            st_u32(b8, base14, (i14b - i13) & 0xFFFFFFFF)
            st_u32(b8, base14 + 4, ((i14b - i13) + S(lo + 4 * i8)) & 0xFFFFFFFF)
        local_48 += 1
        if local_48 == 0x14:
            _f_d944(b8, off, nbands)
            if O(0) < S(lo):
                st_u32(b8, off, S(lo))
            if nbands > 1:
                for k in range(1, nbands):
                    if O(k) < S(lo + 4 * k) + O(k - 1):
                        st_u32(b8, off + 4 * k, (S(lo + 4 * k) + O(k - 1)) & 0xFFFFFFFF)
            if 0x8000 - S(lo + 4 * nbands) < O(i16):
                st_u32(b8, off + 4 * i16, (0x8000 - S(lo + 4 * nbands)) & 0xFFFFFFFF)
            if nbands - 2 >= 0:
                idx = nbands - 2
                koff = 0
                nn = nbands
                while nn != 1:
                    nn -= 1
                    i17b = ld_s32(b8, off + koff + i7 - 4) - S(hi + koff - 4)
                    if not (O(idx) < i17b):
                        st_u32(b8, off + 4 * idx, i17b & 0xFFFFFFFF)
                    idx -= 1
                    koff -= 4
            return


# --------------------------------------------------------------------------- #
# FUN_0014899c  (Ghidra 140587-140622, ELF 0x13899c)   gain offsets
# --------------------------------------------------------------------------- #
def _f899c(x, sym, fi, rate):
    x = s32(x + ((rate << 16) >> 15))
    i = sym * 2
    if rate == 8:
        s2 = T.s16(0x1785ea + i)
        s3 = T.s16(0x178600 + i)
        s4 = T.s16(0x1785d4 + sym * 2)
        s5 = T.s16(0x178616 + i)
    else:
        s2 = T.s16(0x178670 + i)
        s3 = T.s16(0x1786b4 + i)
        s4 = T.s16(0x17862c + sym * 2)
        s5 = T.s16(0x1786f8 + i)
    st_u32(fi, 0, s32(x + s4))
    st_u32(fi, 4, s32(x + s2))
    st_u32(fi, 8, s32(x + s3))
    st_u32(fi, 12, s32(x + s5))


# --------------------------------------------------------------------------- #
# FUN_0014e0ec  (Ghidra 143803-143834, ELF 0x13e0ec)   coefficient signs
# --------------------------------------------------------------------------- #
def _f_e0ec(ctx, coeffs, count, p4, p5, p6):
    idx = s16(p5 + p4 * 2) * 9 + p6
    prob = T.u16(A_E30C + 2 * idx)
    tbl = ListTbl([0, prob, 0xFFFF])
    for i in range(count):
        v = ld_s32(coeffs, 4 * i)
        if v > 0:
            s = af88(ctx, tbl, 1)
            st_u32(coeffs, 4 * i, s32((s * 2 - 1) * v))


# --------------------------------------------------------------------------- #
# FUN_00148a20  (Ghidra 140622-140720, ELF 0x138a20)   coefficient driver
# --------------------------------------------------------------------------- #
def _f8a20(ctx, fi, coeffs, n):
    blk = ld_s32(fi, 0x9c)
    st_u32(fi, 0x94, af88(ctx, StaticTbl(A_DF44 + blk * 0x14), 4))
    i1 = (n >> 4) if n >= 0 else ((n + 0xF) >> 4)
    i8 = ld_s32(fi, 0x94)
    if i1 > 0:
        cnt = [0] * i1          # local_11c : escape counts
        amp = [0] * i1          # local_a4  : 6-bit band symbols
        for k in range(i1):
            sym = af88(ctx, StaticTbl(A_DC34 + s32(i8) * 0x2A), 6)
            amp[k] = sym
            if sym == 0x13:
                i4 = 1
                while True:
                    i2 = i4
                    sym = af88(ctx, StaticTbl(A_DDAE), 6)
                    amp[k] = sym
                    i4 = i2 + 1
                    if sym != 0x13:
                        break
                cnt[k] = i2
        for k in range(i1):
            if amp[k] > 0:
                _f_d100(coeffs, k * 0x40, ctx, amp[k])
            else:
                coeffs[k * 0x40:k * 0x40 + 0x40] = b'\x00' * 0x40
        for k in range(i1):
            if cnt[k] > 0:
                for j in range(16):
                    v = ld_s32(coeffs, k * 0x40 + 4 * j)
                    for _ in range(cnt[k]):
                        v = (v * 2 + af88(ctx, StaticTbl(A_D304), 1)) & 0xFFFFFFFF
                    st_u32(coeffs, k * 0x40 + 4 * j, v)
        i8 = ld_s32(fi, 0x94)
    _f_e0ec(ctx, coeffs, n, ld_s32(fi, 0x9c), ld_s32(fi, 0x98), i8)


# --------------------------------------------------------------------------- #
# FUN_00148190  (Ghidra 140402-140587, ELF 0x138190)   parse entry point
# --------------------------------------------------------------------------- #
def parse(ctx, fi, coeffs, flag=1):
    first = ld_s32(ctx, 0x2c34) == 0
    if first:
        s = af88(ctx, StaticTbl(A_D334), 2)
        if s > 3:
            st_u32(ctx, 16, -7)
            return
        cb0(ctx, ld_s32(T.rd(A_D324 + 4 * s, 4), 0))
        if ld_s32(ctx, 0x2c34) == 0:
            s = af88(ctx, StaticTbl(A_E2D4), 2)
        else:
            s = af88(ctx, StaticTbl(A_E2E4 + ld_s32(ctx, 0x2bc4) * 10), 2)
    else:
        s = af88(ctx, StaticTbl(A_E2E4 + ld_s32(ctx, 0x2bc4) * 10), 2)
    st_u32(fi, 0x98, s & 1)
    st_u32(fi, 0x9c, s >> 1)
    st_u32(ctx, 0x2bc4, s)

    a50 = bytearray(4)
    a4c = bytearray(4)
    a48 = bytearray(4)
    a44 = bytearray(4)
    if ld_s32(ctx, 0x2c34) == 0:
        st_u32(a50, 0, af88(ctx, StaticTbl(A_8BF4 + (s >> 1) * 0x82), 0x20))
    else:
        st_u32(a50, 0, af88(ctx, StaticTbl(A_8CFC), 5))
    st_u32(a4c, 0, af88(ctx, StaticTbl(A_8CFC), 5))
    st_u32(a48, 0, af88(ctx, StaticTbl(A_8CFC), 5))
    st_u32(a44, 0, af88(ctx, StaticTbl(A_8CFC), 5))
    a5 = bytearray(20)
    for k in range(4):
        st_u32(a5, 4 * k, ld_u32(a50, 0) if k == 0 else
               (ld_u32(a4c, 0) if k == 1 else (ld_u32(a48, 0) if k == 2 else ld_u32(a44, 0))))
    _f8f20(fi, a5, ctx, ld_s32(ctx, 0x2c34))

    blk = ld_s32(fi, 0x9c)
    cbp = ld_u32(ctx, 0x2cec + 4 * blk)
    nbands = ld_s32(ctx, 0x2be8)
    a78 = bytearray(40)
    lb8 = bytearray(64)
    lf8 = bytearray(64)
    _f_b104(a78, 0, ctx, T.u32(cbp + 16), T.u32(cbp + 20), T.u32(cbp))
    _f97a8(lb8, 0, cbp, a78, nbands)
    st_u32(fi, 0xa0, af88(ctx, StaticTbl(A_D344), 4))
    if ld_s32(ctx, 0x2c2c) == 1:
        st_u32(fi, 0xa0, 4)
    if flag != 0:
        f1496c0(fi, 0x44, lb8, 0, nbands)
        i2 = ld_s32(fi, 0xa0)
        if i2 < 4:
            if nbands > 0:
                for i in range(nbands):
                    g = ld_s32(ctx, 0x2bec + 4 * i)
                    st_u32(lf8, 4 * i,
                           s32(g + ((i2 * (ld_s32(lb8, 4 * i) - g)) >> 2)))
            f1496c0(fi, 0x24, lf8, 0, nbands)
        else:
            fi[0x24:0x24 + nbands * 2] = fi[0x44:0x44 + nbands * 2]
    ctx[0x2bec:0x2bec + nbands * 4] = lb8[:nbands * 4]
    if ld_s32(ctx, 0x350c) == 0:
        i2 = ld_s32(fi, 0x9c)
    else:
        f14dc30(fi, 0x24, nbands, 0xF852)
        f14dc30(fi, 0x44, nbands, 0xF852)
        i2 = ld_s32(fi, 0x9c)
    if i2 == 0:
        rate = ld_s32(ctx, 0x2bd8)
        if rate == 8:
            cbp2, off = 0x17d4ec, -0xE4
        elif rate == 0xc:
            cbp2, off = 0x17d690, -0xDC
        elif rate == 0x10:
            cbp2, off = 0x17d898, -0xEC
        else:
            cbp2, off = 0x17dba0, -0x154
        sym = af88(ctx, StaticTbl(T.u32(A_GOT + off)), T.s32(cbp2))
        if rate == 8:
            s2 = af88(ctx, StaticTbl(A_D4F0), 5)
        else:
            s2 = af88(ctx, StaticTbl(A_DBA4), 0x11)
        _f899c(sym, s2, fi, rate)
        n24 = af88(ctx, StaticTbl(A_8D5C), 1)
        st_u32(fi, 0x90, n24)
        pu5 = T.u32(A_95_2C + 4 * n24)
        tbl = T.u32(A_95_14 + 4 * n24)
        nbits = T.s32(A_8E00 + 4 * n24)
        for b in range(4):
            idx = af88(ctx, StaticTbl(tbl), nbits)
            src = pu5 + idx * 10
            for k in range(5):
                st_u16(fi, 0x64 + b * 10 + 2 * k, T.u16(src + 2 * k))
        s3 = af88(ctx, StaticTbl(A_D30C), 2)
        st_u32(fi, 0x8c, s32(T.s16(A_D37C + 2 * s3)))
    else:
        for o, v in ((0x00, 0), (0x04, 0), (0x8c, 0), (0x08, 0), (0x64, 0),
                     (0x0c, 0), (0x68, 0), (0x6c, 0), (0x70, 0), (0x74, 0),
                     (0x78, 0), (0x7c, 0), (0x80, 0), (0x84, 0), (0x88, 0),
                     (0x90, 0)):
            st_u32(fi, o, v)
    st_u32(fi, 0x20, af88(ctx, StaticTbl(A_D364), 2))
    _f8a20(ctx, fi, coeffs, ld_s32(ctx, 0x2be0))
    st_u32(ctx, 0x2cf4, af88(ctx, StaticTbl(A_D318), 1))
    st_u32(ctx, 0x2c40, af88(ctx, StaticTbl(A_D354), 2))
    ret, bp = b1e4(ctx)
    local_30 = s32((ld_u32(ctx, 0) - bp) & 0xFFFFFFFF)
    st_u32(ctx, 0x2c30, local_30)
    if local_30 < 0:
        st_u32(ctx, 16, -6)
    elif local_30 == 0:
        b450(ctx)


def _selftest():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import check

    def call(st, r):
        parse(st['ctx'], st['frame_info'], st['coeffs'])

    return check('parse', call, compare=('ctx', 'frame_info', 'coeffs'))


if __name__ == '__main__':
    total, failed = _selftest()
    raise SystemExit(1 if failed else 0)
