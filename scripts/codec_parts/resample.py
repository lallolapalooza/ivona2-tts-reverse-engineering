"""Clean-room port of the IVONA codec **output-rate converter** (the resampler
at ``ctx+0x2c44``).

Engine entry points (Ghidra names, both address conventions):

  * ``FUN_0014b668`` (ELF 0x13b668) -- ``Resampler()`` constructor defaults.
  * ``FUN_0014b6d0`` (ELF 0x13b6d0) -- ``Resampler.__init__`` (setup).  Called by
    ``FUN_00147c58`` as ``f(ctx+0x2c44, codec_rate, out_rate)``; the third
    argument is the *left-over* ``r2`` (see the module below) but really is the
    requested output rate.
  * ``FUN_0014b4a8`` (ELF 0x13b4a8) -- ``Resampler.run``: consumes ``n``
    codec-rate samples and writes ``n * out_rate / codec_rate`` samples.
  * ``FUN_0014c494`` (ELF 0x13c494) -- the fractional-delay interpolator used
    for the ``(24000, 22050)`` configuration (``struct+0x60``), together with
    the 2x half-band filter at ELF 0x13c6f4 (``struct+0x64``, an address Ghidra
    merged into ``FUN_0014c494``'s range).

For ``codec_rate=24000, out_rate=22050`` the setup selects

    struct+0x60 = FUN_0014c494      struct+0x64 = 0x13c6f4
    struct+0x68 = 240               struct+0x6c = 142664
    struct+0x74 = 1                 struct+0x9c = struct+0xa0 = 0

so ``FUN_0014b4a8`` takes its "single call into struct+0x60" fast path and the
whole frame is handled by ``FUN_0014c494`` in two 240-sample chunks.  That pair
is byte-exact (see ``test_resample.py``, which replays real Kendra/Amy records
through both the engine and this port).  Beyond it, every one of the 140 rate
pairs swept from {8000..96000}^2 produces a setup struct identical to the
engine's, and every pair whose selected stage functions *are* ported (49 of
them, including the two-stage ``FUN_0014b4a8`` loop) was additionally checked
sample-for-sample against the emulator over two consecutive frames.

Other setup selections pick engine code that is *not* part of this port and
raise :class:`NotImplementedError` naming the exact field value and engine
symbol -- never silently wrong data:

  * ``struct+0x60 = FUN_0014bf38`` (0x13bf38): polyphase converter used by many
    other down/up-sampling pairs.  Its building blocks could not be validated
    here, so it is a clear error rather than a guess.
  * ``struct+0x60 = LAB_0014bdf8`` (0x13bdf8), ``DAT_0014ca68`` (0x13ca68).
  * ``struct+0x8c = LAB_0014be08`` (0x13be08), ``struct+0x90 = LAB_0014cba8``
    (0x13cba8) / ``LAB_0014ca6c`` (0x13ca6c).
  * ``struct+0x64 = 0x13cba8`` (the 2x half-band filter for in-rates >= 24001,
    another Ghidra-merged blob).

``FUN_0014cce0`` (0x13cce0), ``FUN_0014ae64`` (0x13ae64) and ``FUN_00151448``
(0x141448) are *not* reachable from the resampler: no field this setup writes
ever holds their addresses (checked against the image) and no ported resampler
function calls them -- they belong to other codec stages.

All arithmetic is 32-bit wrapping with arithmetic shifts (``prims`` helpers).
"""
from prims import u32, s32, s16, asr, divsi3
from tables import tables

__all__ = ['Resampler']

# --------------------------------------------------------------------------- #
# function-pointer identities used by the setup dispatcher (ELF vaddrs)
FUN_0014bcd8 = 0x13BCD8             # half-band decimator (ported)
FUN_0014bf38 = 0x13BF38             # polyphase converter (not ported)
FUN_0014c494 = 0x13C494             # fractional-delay interpolator (ported)
FILTER_2X = 0x13C6F4                # 2x half-band filter, struct+0x64 (ported)
LAB_0014bdf8 = 0x13BDF8             # equal-rate passthrough (not ported)
LAB_0014be08 = 0x13BE08             # in-rate >= 0x17701 stage (not ported)
LAB_0014ca6c = 0x13CA6C             # out-rate >= 0x17701 stage (not ported)
LAB_0014cba8 = 0x13CBA8             # out-rate >= 0xbb81 stage (not ported)
DAT_0014ca68 = 0x13CA68             # exact-2x converter (not ported)
FILTER_2X_HI = 0x13CBA8             # struct+0x64 for in-rate >= 24001

CONV_MAGIC = 0x75BCD15

# static images (ELF vaddrs, read through tables())
COEF_BASE = 0x178790                # 8 unique coefficients, C[0..7]
COEF_N = 8
INTERP_BASE = 0x178894              # 144 x 3 int16 interpolation table
INTERP_N = 432

_cache = {}


def _coef():
    if 'c' not in _cache:
        t = tables()
        _cache['c'] = [t.s16(COEF_BASE + 2 * i) for i in range(COEF_N)]
    return _cache['c']


def _itab():
    if 'i' not in _cache:
        t = tables()
        _cache['i'] = [t.s16(INTERP_BASE + 2 * i) for i in range(INTERP_N)]
    return _cache['i']


def _shorts(vaddr, n):
    """Read ``n`` int16 values at an image vaddr (coefficient table)."""
    t = tables()
    return [t.s16(vaddr + 2 * i) for i in range(n)]


def _ptr(vaddr):
    """Read a 32-bit pointer out of the static image (GOT slot or direct)."""
    return tables().u32(vaddr)


# --------------------------------------------------------------------------- #
# FUN_0014c6f4 (ELF 0x13c6f4): 2x half-band upsampling filter, 6-word state.
#
# Disassembled from the image (Ghidra had merged it into FUN_0014c494).  It
# reads the six 32-bit state words at struct+0x00..0x17, consumes `n` int16
# input samples and writes `2n` int16 output samples, then stores the state
# back.  Six "registers" are real state that survives an iteration: w0 (ip),
# w1 (saved at sp+0x34), w2 (r3), w3 (r4), w4 (sp+4) and w5 (fp); plus the
# duplicated hi/lo halves of w5 (r0/r1) and the previous w3 (sp+0x18).
def _filter_2x(w, inp, inpos, n, out):
    C = _coef()
    k0, k1, k2, c3, c4, c5, k6, c7 = (C[0], C[1], C[2], C[3],
                                      C[4], C[5], C[6], C[7])
    ip = w[0]
    r8 = w[1]
    r4 = w[2]
    hist3 = w[3]
    w4 = w[4]
    fp = w[5]
    r0 = asr(fp, 16)                # hi16(w5)
    r1 = u32(fp) & 0xFFFF           # lo16(w5)
    r3 = 0
    save34 = 0
    for i in range(n):
        if i:
            # 0x13c7c8 loop-back: w1 <- sp+0x34, w3 <- previous r4, r4 <- r3
            r8 = save34
            hist3 = r4
            r4 = r3
        x = s16(inp[inpos + i])
        xa = s32(x << 10)                       # 0x13c7e8
        sb = s32(r1 * k6)                       # 0x13c7ec  C[6]*lo(w5)
        r1 = s32(xa - ip)                       # 0x13c7f0
        r2 = u32(r1) & 0xFFFF                   # lo16(r1)
        sl = s32(r2 * k0)                       # 0x13c7fc  C[0]*lo
        r1 = asr(r1, 16)                        # hi16(r1)
        r2 = s32(r1 * k0)                       # 0x13c808  C[0]*hi
        sl = s32(r2 + asr(sl, 16))              # 0x13c810
        r5 = s32(sl + ip)                       # 0x13c814
        r2 = s32(r5 - r8)                       # 0x13c818
        r1 = s32(asr(r2, 16) * k1 + r2)         # 0x13c824/28  mla r1,C[1],hi,r2
        ip = u32(r2) & 0xFFFF                   # lo16(r2)
        r7 = s32(ip * k1)                       # 0x13c838  C[1]*lo(r2)
        r7 = s32(r1 + asr(r7, 16))              # 0x13c840
        r8 = s32(r8 + r7)                       # 0x13c84c
        r2 = s32(r0 * k6 + r8)                  # 0x13c850  mla C[6]*hi(w5)
        r2 = s32(r2 + asr(sb, 16))              # 0x13c858
        r1 = w4
        w4lo = u32(r1) & 0xFFFF                 # 0x13c860
        w4hi = asr(r1, 16)                      # 0x13c864
        r8 = s32(c5 * w4hi + r2)                # 0x13c868
        r0 = s32(c4 * w4hi)                     # 0x13c86c
        sb = s32(c5 * w4lo)                     # 0x13c870
        r6 = s32(c4 * w4lo)                     # 0x13c874
        r8 = s32(r8 + asr(sb, 16))              # 0x13c878
        r0 = s32(r0 + asr(r6, 16))              # 0x13c87c
        r0 = s32(r0 + r8)                       # 0x13c884
        hi0 = asr(r0, 16)
        lo0 = u32(r0) & 0xFFFF                  # 0x13c898
        sb = s32(c7 * hi0)                      # 0x13c894
        r0 = s32(c7 * lo0)                      # 0x13c89c
        sb = s32(sb + 0x100)                    # 0x13c8a0 (rounding)
        r0 = s32(sb + asr(r0, 16))              # 0x13c8a4
        v = asr(r0, 9)                          # 0x13c8ac
        r5 = s32(r7 + r5)                       # 0x13c8b0
        fp = s32(r8 - fp)                       # 0x13c8b8 : new state w5
        ip = s32(sl + xa)                       # 0x13c8bc : new state w0
        save34 = r5                             # 0x13c8c0
        if s32(v) > 0x7FFF:                     # 0x13c8b4/0x13c8c4
            r6 = 0x7FFF
        else:
            r6 = -0x8000 if v < -0x8000 else v
            r6 = u32(r6) & 0xFFFF
        # ---------------- second half ---------------------------------- #
        r5 = s32(xa - r4)                       # 0x13c8e0
        r2 = s32((u32(r5) & 0xFFFF) * k2)       # 0x13c8f4 (C[2]*lo(r5))
        r0 = s32(asr(r5, 16) * k2)              # 0x13c900 (C[2]*hi(r5))
        r6b = s32(r0 + asr(r2, 16))             # 0x13c908
        r4 = s32(r4 + r6b)                      # 0x13c910
        r0 = s32(r4 - hist3)                    # 0x13c914
        r8 = s32(c3 * (u32(r0) & 0xFFFF))       # 0x13c928 (C[3]*lo(r0))
        r5 = s32(c3 * asr(r0, 16) + r0)         # 0x13c92c  mla
        r5 = s32(r5 + asr(r8, 16))              # 0x13c938
        r1 = s32(hist3 + r5)                    # 0x13c944
        r0 = s32(w4lo * k6)                     # 0x13c940 (sp+0x2c = C[6])
        sl = s32(w4hi * k6 + r1)                # 0x13c948  mla
        sl = s32(sl + asr(r0, 16))              # 0x13c95c
        r7 = c4
        r8 = c5
        r1 = u32(fp) & 0xFFFF                   # lo16(fp)
        r0 = asr(fp, 16)                        # hi16(fp)
        r2 = s32(r8 * r0 + sl)                  # 0x13c968
        sb = s32(r8 * r1)                       # 0x13c96c
        sl = s32(r7 * r1)                       # 0x13c970
        r8 = s32(r7 * r0)                       # 0x13c974
        r2 = s32(r2 + asr(sb, 16))              # 0x13c978
        r8 = s32(r8 + asr(sl, 16))              # 0x13c97c
        r8 = s32(r8 + r2)                       # 0x13c984
        hi8 = asr(r8, 16)                       # 0x13c990
        lo8 = u32(r8) & 0xFFFF                  # 0x13c998
        sl = s32(c7 * hi8)                      # 0x13c994
        r8 = s32(c7 * lo8)                      # 0x13c99c
        sl = s32(sl + 0x100)                    # 0x13c9a0
        r8 = s32(sl + asr(r8, 16))              # 0x13c9a4
        v2 = asr(r8, 9)                         # 0x13c9bc
        w4 = s32(r2 - w4)                       # 0x13c9c0 : new state w4
        if s32(v2) > 0x7FFF:                    # 0x13c9c4/0x13c9d4
            r7 = 0x7FFF
        else:
            r7 = -0x8000 if v2 < -0x8000 else v2
            r7 = u32(r7) & 0xFFFF
        out[2 * i] = s16(r6)
        out[2 * i + 1] = s16(r7)
        r3 = s32(r6b + xa)                      # 0x13c9cc : new state w2
        r4 = s32(r5 + r4)                       # 0x13c9d0 : new state w3
    w[0] = u32(ip)
    w[1] = u32(save34)
    w[2] = u32(r3)
    w[3] = u32(r4)
    w[4] = u32(w4)
    w[5] = u32(fp)


# --------------------------------------------------------------------------- #
# FUN_0014c494 (ELF 0x13c494): fractional-delay interpolator.
#
# struct fields used: 0x68 chunk, 0x6c phase step, 0x74 flag, 0x64 inner
# function pointer (+0x78 table pointer for the non-flag path), 0x18..0x23 the
# six-sample interpolator history.
def _interp_step(comb, uVar5):
    """One output sample of FUN_0014c494's interpolation loop.

    ``comb`` is the 6-sample history followed by the chunk's 2n filter output,
    i.e. the engine's ``work`` buffer in int16 units.
    """
    T = _itab()
    i4 = asr(s32((u32(uVar5) & 0xFFFF) * 9), 12)
    i9 = 0x8F - i4
    b = s32(uVar5) >> 16
    v = s32(comb[b + 1] * T[i4 * 3 + 1] + comb[b] * T[i4 * 3]
            + comb[b + 2] * T[i4 * 3 + 2] + comb[b + 3] * T[i9 * 3 + 2]
            + comb[b + 4] * T[i9 * 3 + 1] + comb[b + 5] * T[i9 * 3])
    v = ((asr(v, 14) + 1) >> 1)
    if v > 0x7FFF:
        return 0x7FFF
    if v < -0x8000:
        return -0x8000
    return v


def _f0014c494(st, out, inp, n_in, inpos=0):
    """struct+0x60 for the ported rate pairs (see the module docstring)."""
    chunk_lim = st.f68
    step = st.f6c
    flag = st.f74
    hist6 = list(st.hist)               # struct+0x18..0x23 (6 int16 samples)
    remaining = n_in
    while True:
        n = chunk_lim if chunk_lim < remaining else remaining
        if flag == 1:
            inner = [0] * (2 * n)
            if st.f64 != FILTER_2X:
                raise NotImplementedError(
                    'resampler: struct+0x64 = %#x (FILTER_2X_HI, the 2x filter '
                    'for in-rates >= 24001) is not ported' % st.f64)
            _filter_2x(st.fw, inp, inpos, n, inner)
        else:
            inner = []
            _f00151234(st, inner, inp[inpos:inpos + n],
                       _shorts(st.f78, 7), n)
        target = s32(n << ((flag + 0x10) & 0xFF))
        comb = hist6 + inner          # engine `work`: history then filter out
        uVar5 = 0
        if target > 0:
            while True:
                out.append(_interp_step(comb, uVar5))
                uVar5 = u32(uVar5 + step)
                if not (s32(uVar5) < target):
                    break
        remaining -= n
        # memcpy(work, work + (n << flag)*2, 0x18) -- runs between chunks and
        # again after the loop (into struct+0x18).  The first six samples of
        # that window are the tail of the chunk's 2n-sample filter output; the
        # remaining 12 bytes land behind the next chunk's output and are never
        # read back.
        start = ((n << (flag & 0xFF)) * 2) // 2
        hist6 = [comb[start + k] if start + k < len(comb) else 0
                 for k in range(6)]
        if remaining < 1:
            break
        inpos += n
    st.hist = hist6


# --------------------------------------------------------------------------- #
# FUN_0014bcd8 (ELF 0x13bcd8): half-band decimator, reuses struct+0x58 as its
# two-word state in FUN_0014bf38 and struct+0x7c in FUN_0014b4a8's loop.
# Exercised end-to-end by the ported two-stage rate pairs (verified).
def _f0014bcd8(st, out, inp, n, inpos=0):
    if (n >> 1) > 0:
        iVar9 = st.dc[0]
        iVar2 = st.dc[1]
        i = 0
        while True:
            x0 = inp[inpos + i]
            x1 = inp[inpos + i + 1]
            uVar4 = s32(x0 * 0x400 - iVar9)
            uVar6 = s32(x1 * 0x400 - iVar2)
            iVar7 = s32(asr(uVar6, 16) * 0x2690
                        + asr(s32((u32(uVar6) & 0xFFFF) * 0x2690), 16))
            iVar5 = s32(asr(uVar4, 16) * -0x647F + uVar4
                        + asr(s32((u32(uVar4) & 0xFFFF) * -0x647F), 16))
            iVar9n = s32(iVar5 + x0 * 0x400)
            iVar2n = s32(iVar7 + x1 * 0x400)
            iVar1 = asr(s32(iVar9 + iVar2 + iVar5 + iVar7), 10)
            iVar1 = s32(iVar1 + 1) >> 1
            if iVar1 >= 0x8000:
                out.append(0x7FFF)
            elif iVar1 < -0x8000:
                out.append(-0x8000)
            else:
                out.append(iVar1)
            iVar9 = iVar9n
            iVar2 = iVar2n
            i += 2
            if i == (n >> 1) << 1:
                break
        st.dc[0] = iVar9
        st.dc[1] = iVar2


# --------------------------------------------------------------------------- #
# FUN_001511b4 (ELF 0x1411b4): integer-phase polyphase interpolator.  Only
# FUN_0014bf38 (ELF 0x13bf38) calls it, and that converter is not ported; kept
# because it is cheap and was verified bit-exact (outputs + state) by direct
# emulation.  Writes int32 words; state is the two words at struct+0x00.
def _f001511b4(st, out, inp, tab, n):
    if n > 0:
        sVar4 = tab[1]
        sVar5 = tab[0]
        j = 0
        while True:
            uVar7 = u32(st.p1[0] + inp[j] * 0x100)
            out.append(uVar7)
            iVar2 = asr(s32(s32(uVar7) * 4), 16)
            iVar1 = s32((u32(uVar7) & 0x3FFF) * 4)
            st.p1[0] = s32(iVar2 * sVar5 + st.p1[1] + asr(s32(iVar1 * sVar5), 16))
            st.p1[1] = s32(iVar2 * sVar4 + asr(s32(iVar1 * sVar4), 16))
            j += 1
            if j == n:
                break


# --------------------------------------------------------------------------- #
# FUN_00151234 (ELF 0x141234): fractional-phase polyphase interpolator; the
# inner stage of FUN_0014c494 when struct+0x74 != 1 (verified end-to-end, e.g.
# codec_rate=88200 -> out_rate=16000).  State: four words at struct+0x00.
def _f00151234(st, out, inp, tab, n):
    if n <= 0:
        return
    iVar5 = st.p2[0]
    iVar10 = st.p2[2]
    iVar13 = st.p2[1]
    iVar12 = st.p2[3]
    j = 0
    while True:
        x = s16(inp[j])
        iVar1 = s32(x * 0x100)
        uVar6 = u32(iVar1 + s32(iVar5 * 4))
        uVar11 = u32(uVar6 + s32(iVar10 * 4))
        iVar3 = asr(s32(uVar11), 16)
        iVar4 = asr(s32(uVar6), 16)
        uVar2 = u32(uVar6) & 0xFFFF
        uVar11 &= 0xFFFF
        iVar10 = s32(tab[4] * iVar3 + tab[1] * iVar4 + iVar12
                     + asr(s32(uVar2 * tab[1]), 16)
                     + asr(s32(tab[4] * uVar11), 16))
        iVar9 = s32(asr(s32(tab[6] * iVar3 + 0x80
                            + asr(s32(uVar11 * tab[6]), 16)), 8))
        iVar5 = s32(tab[2] * iVar4 + asr(s32(iVar1), 16) * tab[0] + iVar13
                    + asr(s32(tab[0] * (x & 0xFF) * 0x100), 16)
                    + asr(s32(tab[2] * uVar2), 16))
        iVar13 = s32(tab[3] * iVar4 + asr(s32(iVar1), 2) + asr(s32(uVar2 * tab[3]), 16))
        iVar12 = s32(tab[5] * iVar3 + asr(s32(uVar6), 2) + asr(s32(tab[5] * uVar11), 16))
        if iVar9 >= 0x8000:
            out.append(0x7FFF)
        else:
            out.append(-0x8000 if iVar9 < -0x8000 else iVar9)
        j += 1
        if j == n:
            break
    st.p2[3] = u32(iVar12)
    st.p2[0] = u32(iVar5)
    st.p2[2] = u32(iVar10)
    st.p2[1] = u32(iVar13)


# --------------------------------------------------------------------------- #
class Resampler(object):
    """Output-rate converter, mirrors ``FUN_0014b668`` + ``FUN_0014b6d0``."""

    def __init__(self, codec_rate=24000, out_rate=22050):
        self.codec_rate = s32(codec_rate)
        self.out_rate = s32(out_rate)
        # ---- FUN_0014b668: reset -------------------------------------- #
        self.fw = [0] * 6           # struct+0x00  filter state (FUN_0014c6f4)
        self.hist = [0] * 6         # struct+0x18  interpolation history
        self.dc = [0, 0]            # struct+0x58  (FUN_0014bcd8 state)
        self.p1 = [0, 0]            # struct+0x00  (FUN_001511b4 state)
        self.p2 = [0, 0, 0, 0]      # struct+0x00  (FUN_00151234 state)
        self.f60 = 0                # struct+0x60  main converter pointer
        self.f64 = 0                # struct+0x64  inner filter pointer
        self.f68 = 0                # struct+0x68  chunk limit
        self.f6c = 0                # struct+0x6c  phase step
        self.f70 = 0                # struct+0x70  phase count
        self.f74 = 0                # struct+0x74  flag
        self.f78 = 0                # struct+0x78  table pointer
        self.f8c = 0                # struct+0x8c
        self.f90 = 0                # struct+0x90
        self.f94 = 0                # struct+0x94
        self.f98 = 0                # struct+0x98
        self.f9c = 0                # struct+0x9c
        self.fa0 = 0                # struct+0xa0
        self.a4 = 0                 # struct+0xa4  magic
        self._setup(codec_rate, out_rate)

    # -------------------------------------------------- FUN_0014b6d0 ---- #
    def _setup(self, param_2, param_3):
        self.codec_rate = s32(param_2)
        self.out_rate = s32(param_3)
        if (u32(param_2 - 8000) > 0x2CEC0 or param_3 < 8000
                or param_3 > 0x2EE00):
            return 0xFFFFFFFF
        # ---- in-rate stage selection ---------------------------------- #
        if param_2 < 0x17701:
            if param_2 < 0xBB81:
                self.f8c = 0
                self.f9c = 0
            else:
                self.f9c = 1
                self.f8c = FUN_0014bcd8
        else:
            self.f9c = 2
            self.f8c = LAB_0014be08
        # ---- out-rate stage selection --------------------------------- #
        if param_3 < 0x17701:
            if param_3 < 0xBB81:
                iVar8 = 0
                self.fa0 = 0
                self.f90 = 0
            else:
                iVar8 = 1
                self.f90 = LAB_0014cba8
                self.fa0 = 1
        else:
            iVar8 = 2
            self.f90 = LAB_0014ca6c
            self.fa0 = 2
        uVar11 = self.f9c
        iVar10 = param_2
        if (iVar8 + uVar11) > 0:
            uVar1 = divsi3(param_3 << 13, param_2)
            iVar10 = ((param_2 >> 15) + 1) >> 1
            iVar3 = s16(param_2)
            iVar8 = s32(uVar1 * 8)
            self.f98 = iVar8
            if (s32(iVar3 * (iVar8 >> 16) + iVar10 * iVar8
                    + asr(s32(iVar3 * (uVar1 & 0x1FFF) * 8), 16)) < param_3):
                uVar1 = u32(iVar8 + 1)
                iVar8 = s32(iVar10 * uVar1)
                while True:
                    iVar2 = s32(iVar3 * (s32(uVar1) >> 16) + iVar8)
                    iVar8 = s32(iVar8 + iVar10)
                    if not (s32(iVar2 + asr(s32(iVar3 * (uVar1 & 0xFFFF)), 16))
                            < param_3):
                        break
                    uVar1 = u32(uVar1 + 1)
                self.f98 = uVar1
            param_3 = s32(param_3 >> (self.fa0 & 0xFF))
            iVar10 = s32(param_2 >> (uVar11 & 0xFF))
            self.f94 = divsi3(param_2, 100)
        # store the rate values the rest of FUN_0014b6d0 works on
        self.f68 = divsi3(iVar10, 100)
        iVar3 = param_3
        iVar8 = iVar10
        if (s32(divsi3(iVar10, 100) * 100 - iVar10) != 0):
            while True:
                iVar2 = iVar3
                if not (s32(iVar2) > 0):
                    break
                iVar3 = s32(iVar8 - divsi3(iVar8, iVar2) * iVar2)  # rem
                iVar8 = iVar2
            iVar8 = divsi3(iVar10, iVar8)
            iVar3 = divsi3(0x1E0, iVar8)
            if iVar3 == 0:
                iVar8 = 0x1E0
            else:
                iVar8 = s32(iVar8 * iVar3)
            self.f68 = iVar8
        # ---- main converter selection --------------------------------- #
        if iVar10 < param_3:
            if param_3 == iVar10 * 2:
                iVar9 = 0
                self.f60 = DAT_0014ca68
                iVar2 = 0xE
                iVar8 = 0
                iVar3 = 0
                return self._tail(iVar9, iVar2, iVar3, iVar8, iVar10, param_3)
            self.f60 = FUN_0014c494
            iVar8 = -0x6C if iVar10 < 0x5DC1 else -0x80
            self.f64 = _ptr(0x185DB4 + iVar8)
            return self._tail(1, 0xF, 0, 1, iVar10, param_3)
        if iVar10 <= param_3:
            self.f60 = LAB_0014bdf8
            return self._tail(0, 0xE, 0, 0, iVar10, param_3)
        # ---- iVar10 > param_3 : downsampling ------------------------- #
        if param_3 * 4 == iVar10 * 3:
            puVar5 = 0x1787A0
            pcVar7 = FUN_0014bf38
            self.f70 = 3
            return self._sel(puVar5, pcVar7, iVar10, param_3)
        if param_3 * 3 == iVar10 * 2:
            puVar5 = 0x1787C8
            pcVar7 = FUN_0014bf38
            self.f70 = 2
            return self._sel(puVar5, pcVar7, iVar10, param_3)
        if param_3 * 2 == iVar10:
            self.f60 = FUN_0014bf38
            self.f70 = 1
            self.f78 = _ptr(0x185DB4 - 0x7C)
            return self._tail(0, 0xE, 0, 0, iVar10, param_3)
        if iVar10 * 3 == param_3 * 8:
            self.f60 = FUN_0014bf38
            self.f70 = 3
            self.f78 = 0x1787F4
            return self._tail(0, 0xE, 0, 0, iVar10, param_3)
        if iVar10 == param_3 * 3:
            self.f60 = FUN_0014bf38
            self.f70 = 1
            self.f78 = _ptr(0x185DB4 - 0x5C)
            return self._tail(0, 0xE, 0, 0, iVar10, param_3)
        if iVar10 == param_3 * 4:
            self.f60 = FUN_0014bf38
            self.f70 = 1
            self.f78 = _ptr(0x185DB4 - 0x7C)
            return self._tail(1, 0xD, 1, 0, iVar10, param_3)
        if param_3 * 6 == iVar10:
            self.f60 = FUN_0014bf38
            self.f70 = 1
            self.f78 = _ptr(0x185DB4 - 0x5C)
            return self._tail(1, 0xD, 1, 0, iVar10, param_3)
        iVar8 = s32(param_3 * 0x1B9)
        for mul, puVar5 in ((-0x50, 0x178884), (-0x78, 0x178874),
                            (-0xA0, 0x178864), (-0xF0, 0x178854),
                            (-0x140, 0x178844)):
            if s32(iVar8 + iVar10 * mul) == 0:
                self.f70 = 0
                return self._sel(puVar5, FUN_0014c494, iVar10, param_3)
        # ---- default: LAB_0014b8b4 (our 24000 -> 22050 case) ---------- #
        self.f60 = FUN_0014c494
        iVar8 = -0x6C if iVar10 < 0x5DC1 else -0x80
        self.f64 = _ptr(0x185DB4 + iVar8)
        return self._tail(1, 0xF, 0, 1, iVar10, param_3)

    def _sel(self, puVar5, pcVar7, iVar10, param_3):
        """LAB_0014ba50: table pointer + converter with a phase count."""
        self.f78 = puVar5
        self.f60 = pcVar7
        return self._tail(0, 0xE, 0, 0, iVar10, param_3)

    # ---- LAB_0014b8e8 -------------------------------------------------- #
    def _tail(self, iVar9, iVar2, iVar3, iVar8, iVar10, param_3):
        self.f74 = iVar9
        uVar11 = divsi3(s32(iVar10 << iVar2), param_3)
        iVar2 = s16(s32(param_3 << iVar3))
        iVar9b = ((s32(param_3 << iVar3) >> 0xF) + 1) >> 1
        iVar3b = s32(uVar11 * 4)
        self.f6c = iVar3b
        if (s32(iVar3b * iVar9b + iVar2 * (iVar3b >> 16)
                + asr(s32(iVar2 * (uVar11 & 0x3FFF) * 4), 16))
                < s32(iVar10 << iVar8)):
            uVar11 = u32(iVar3b + 1)
            iVar3c = s32(uVar11 * iVar9b)
            while True:
                iVar4 = s32(iVar2 * (s32(uVar11) >> 16) + iVar3c)
                iVar3c = s32(iVar3c + iVar9b)
                if not (s32(iVar4 + asr(s32(iVar2 * (uVar11 & 0xFFFF)), 16))
                        < s32(iVar10 << iVar8)):
                    break
                uVar11 = u32(uVar11 + 1)
            self.f6c = uVar11
        self.a4 = CONV_MAGIC
        return 0

    # --------------------------------------------------- FUN_0014b4a8 -- #
    def run(self, inp, n_out=None):
        """Feed ``len(inp)`` codec-rate int16 samples; return int16 samples.

        Mirrors ``FUN_0014b4a8``; the returned length defaults to
        ``divsi3(out_rate * len(inp), codec_rate)`` (the engine's
        ``*param_7 = __divsi3(rate * n, codec_rate*1000)`` at ELF 0x147d0x).
        """
        if self.a4 != CONV_MAGIC:
            return None
        inp = [s16(x) for x in inp]
        n = len(inp)
        out = []
        if (self.f9c + self.fa0) < 1:
            # the whole frame goes through the main converter in one call
            self._call_main(out, inp, 0, n)
        else:
            self._run_mixed(out, inp, n)
        count = (n_out if n_out is not None
                 else divsi3(s32(self.out_rate * n), self.codec_rate))
        return out[:count]

    def _call_main(self, out, inp, inpos, n):
        """``(**(struct+0x60))(st, out, in, n)``."""
        if self.f60 == FUN_0014c494:
            _f0014c494(self, out, inp, n, inpos)
        elif self.f60 == FUN_0014bf38:
            raise NotImplementedError(
                'resampler: struct+0x60 = FUN_0014bf38 (0x13bf38, polyphase '
                'converter for other rate pairs) is not ported')
        elif self.f60 == LAB_0014bdf8:
            raise NotImplementedError(
                'resampler: struct+0x60 = LAB_0014bdf8 (0x13bdf8, equal-rate '
                'passthrough) is not ported')
        elif self.f60 == DAT_0014ca68:
            raise NotImplementedError(
                'resampler: struct+0x60 = DAT_0014ca68 (0x13ca68, exact-2x '
                'converter) is not ported')
        else:
            raise NotImplementedError(
                'resampler: struct+0x60 = %#x is not ported' % self.f60)

    def _call_decim(self, out, inp, inpos, n):
        """``(**(struct+0x8c))(...)``: in-rate stage."""
        if self.f8c == FUN_0014bcd8:
            _f0014bcd8(self, out, inp, n, inpos)
        elif self.f8c == LAB_0014be08:
            raise NotImplementedError(
                'resampler: struct+0x8c = LAB_0014be08 (0x13be08, in-rate >= '
                '0x17701) is not ported')
        else:
            raise NotImplementedError(
                'resampler: struct+0x8c = %#x is not ported' % self.f8c)

    def _call_interp(self, out, inp, inpos, n):
        """``(**(struct+0x90))(...)``: out-rate stage."""
        if self.f90 == LAB_0014cba8:
            name = 'LAB_0014cba8 (0x13cba8, out-rate >= 0xbb81)'
        elif self.f90 == LAB_0014ca6c:
            name = 'LAB_0014ca6c (0x13ca6c, out-rate >= 0x17701)'
        else:
            name = '%#x' % self.f90
        raise NotImplementedError(
            'resampler: struct+0x90 = %s is not ported' % name)

    def _run_mixed(self, out, inp, n):
        """FUN_0014b4a8's sample loop (reached when struct+0x9c/+0xa0 != 0).

        Two-stage rate conversion: decimate by 2^f9c, convert, interpolate by
        2^fa0.  Only the (FUN_0014bcd8, FUN_0014c494) combination is reachable
        with the ported stage functions.
        """
        f94 = self.f94
        f98 = self.f98
        flag_in = self.f9c
        remaining = n
        inpos = 0
        buf = []              # param_2 target
        pos = 0               # param_2 (advances by iVar4, not by what a stage wrote)
        while True:
            iVar2 = f94 if f94 <= remaining else remaining
            iVar4 = s32((s32(f98) >> 16) * s16(iVar2)
                        + asr(s32((u32(f98) & 0xFFFF) * s16(iVar2)), 16))
            if flag_in < 1:
                tmp = []
                self._call_main(tmp, inp, inpos, iVar2 >> (flag_in & 0xFF))
                res = []
                self._call_interp(res, tmp, 0, iVar4 >> (self.fa0 & 0xFF))
            else:
                dec = []
                self._call_decim(dec, inp, inpos, iVar2)
                res = []
                self._call_main(res, dec, 0, iVar2 >> (flag_in & 0xFF))
                if self.fa0 >= 1:
                    tmp = []
                    self._call_interp(tmp, res, 0, iVar4 >> (self.fa0 & 0xFF))
                    res = tmp
            if len(buf) < pos + len(res):
                buf.extend([0] * (pos + len(res) - len(buf)))
            buf[pos:pos + len(res)] = res
            remaining -= iVar2
            if remaining < 1:
                break
            inpos += iVar2
            pos += iVar4
        out.extend(buf)
        return
