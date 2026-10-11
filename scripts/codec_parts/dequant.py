"""Clean-room port of the IVONA gap codec inverse-quantiser (dequant) stage.

    FUN_0014e4ec  dequant   Ghidra dump 143975-144592  (ELF vaddr 0x13e4ec)
    FUN_0014e29c  helper    Ghidra dump 143889-143975  (ELF 0x13e29c)
    FUN_001507bc  helper    Ghidra dump 145619-145669  (ELF 0x1507bc)

Called as ``FUN_0014e4ec(ctx, frame_info, samp, coeffs)``: ``ctx`` is the
0x3570-byte codec state, ``frame_info`` the parsed per-frame side info (0x200
bytes), ``samp`` the sample output buffer and ``coeffs`` the parsed coefficient
words.  The engine runs over four "bands" (``local_660`` in the dump); per band
it normalises the band gain, derives a Q16 reciprocal from ``ctx[0x414]`` and
the knob, scales the 16-word synthesis state at ``ctx+0x1318``, mixes the
120-word spectrum chunk and finally writes 120 int16 samples into
``ctx+0x27f8``; after the fourth band 480 samples are copied out to ``samp``.

The transliteration keeps ARM semantics literally: every arithmetic op is
32-bit wrapping, signed right shifts are arithmetic, ``>>``/``&`` on ``uint``
values are logical, 16-bit stores truncate, and ``__divsi3`` replaces the ARM
helper.  Two places (the mid-function reciprocal and the final gain) store the
``__divsi3`` result through a 16-bit temporary in the original, so the quotient
is truncated to 16 bits there.
"""
from prims import (u32, s32, s16, ld_s16, ld_u16, ld_s32, ld_u32, st_s16,
                   st_u32, memcpy, divsi3, clamp_hi16)
from tables import tables

# --------------------------------------------------------------------------- #
# ctx byte offsets
# --------------------------------------------------------------------------- #
C_2BB8 = 0x2bb8        # reset/setup scalar
C_2BE0 = 0x2be0        # 480
C_2BE4 = 0x2be4        # 120
C_2BE8 = 0x2be8        # 16 (number of bands)
C_350C = 0x350c
C_3510 = 0x3510
C_414 = 0x414          # previous Q16 band gain

C_STATE = 0x1318       # 16-word synthesis state (piVar17)
C_SPEC = 0x1538        # 480-word dither/spectrum scratch (__src)
C_SPEC2 = 0x1cb8       # 120-word working spectrum (local_674)
C_SAMP = 0x27f8        # 480 int16 output samples (local_64c)

TBL_D374 = 0x17d374    # DAT_0018d374 -> ELF vaddr

# stack-scratch sizes (all modelled as bytearrays)
_N_ASSTACK = 480       # asStack_628: int16[480]
_N_AU88 = 64           # auStack_88 : int32[16]
_N_AU48 = 32           # auStack_48 : int16[16]
_N_LOCAL268 = 480      # local_268  : int32[120]


def _mul(a, b):
    return s32(a * b)


def _add(a, b):
    return s32(a + b)


def _exact_mul(v, coef):
    """``((int)v >> 16) * coef + ((int)(coef * (v & 0xffff)) >> 16)`` (32-bit)."""
    v = u32(v)
    hi = s32(s32(v) >> 16)
    lo = v & 0xffff
    return s32(_mul(hi, coef) + (s32(_mul(coef, lo)) >> 16))


def _f1507bc(src, so, tbl, to, acc, ao, out, oo, n, nband):
    """FUN_001507bc: n int16 taps through an nband-tap recursion into ``out``."""
    if n <= 0:
        return
    iVar1 = (nband - 1) * 2
    iVar8 = 0
    while True:
        iVar7 = ld_s16(src, so + iVar8)
        iVar2 = ((_add(_mul(iVar7, 0x1000), -s32(ld_s32(acc, ao))) >> 0xb) + 1) >> 1
        if nband > 1:
            iVar6 = 0
            k = 0
            while True:
                val = ld_s16(tbl, to + iVar6)
                iVar6 += 2
                st_u32(acc, ao + 4 * k, _add(_mul(iVar7, val),
                                             ld_s32(acc, ao + 4 * (k + 1))))
                k += 1
                if iVar6 == iVar1:
                    break
        st_u32(acc, ao + 4 * (nband - 1), _mul(iVar7, ld_s16(tbl, to + iVar1)))
        st_s16(out, oo + iVar8, clamp_hi16(iVar2))
        iVar8 += 2
        if iVar8 == n << 1:
            break


def _f14e29c(ctx, coef_off, out, ok, inp, ip, band, bo, nband, count):
    """FUN_0014e29c: nband-tap reversed dot product + spectrum add.

    ``out[k] = sum_b coef[coef_off+4k+4*(15-b)]*band[b] + inp[k]`` and the same
    sum is written back to ``ctx[coef_off+4k+0x40]``.
    """
    for k in range(count):
        acc = 0
        base = coef_off + 4 * k
        for b in range(nband):
            c = ld_u32(ctx, base + 4 * (nband - 1 - b))
            bv = ld_s16(band, bo + 2 * b)
            acc = _add(acc, _exact_mul(c, bv))
        v = ld_s32(inp, ip + 4 * k)
        tot = _add(acc, v)
        st_u32(out, ok + 4 * k, tot)
        st_u32(ctx, base + 0x40, _mul(tot, 0x10))


def dequant(ctx, frame_info, samp, coeffs):
    """FUN_0014e4ec: run the inverse quantiser, writing 480 samples to ``samp``."""
    t = tables()
    local_678 = ld_s32(ctx, C_2BE0)
    iVar7 = ld_s32(frame_info, 0x28 * 4)

    idx = (ld_s32(frame_info, 0x26 * 4) + ld_s32(frame_info, 0x27 * 4) * 2) * 2
    sVar5 = t.s16(TBL_D374 + idx)

    iVar11 = ld_s32(frame_info, 8 * 4)
    if local_678 > 0:
        for i in range(local_678):
            iVar11 = s32(_add(_mul(iVar11, 0xbb38435), 0x3619636b))
            sign = s32(iVar11) >> 31
            ci = ld_s32(coeffs, 4 * i)
            val = s32(sVar5 + s32(ci * 0x400))
            st_u32(ctx, 0x1538 + 4 * i, s32((sign ^ val) - sign))
            iVar11 = s32(iVar11 + ci)

    local_64c = C_SAMP
    local_674 = C_SPEC2
    piVar17 = C_STATE
    local_648 = 0
    local_664 = 0x64                 # byte offset into frame_info
    __src = C_SPEC
    local_660 = 0
    local_658 = 0                    # int index into frame_info

    asStack = bytearray(_N_ASSTACK * 2)
    au88 = bytearray(_N_AU88)
    au48 = bytearray(_N_AU48)
    local268 = bytearray(_N_LOCAL268)

    while True:
        # memcpy(auStack_48, frame_info + 36 + 32*(local_660>>1), 2*ctx[0x2be8])
        memcpy(au48, 0, frame_info, 36 + 32 * (local_660 >> 1),
               2 * ld_s32(ctx, C_2BE8))

        uVar25 = ld_u32(frame_info, 4 * (local_660 + 4))
        uVar14 = uVar25
        if s32(uVar25) < 1:
            uVar14 = 1
        uVar20 = ld_s32(frame_info, 4 * 0x27)

        # ---- normalise uVar14 -> (uVar18, uVar9) -------------------------- #
        iVar10 = iVar22 = iVar23 = iVar11 = 0
        if (uVar14 & 0xffff0000) == 0:
            uVar18 = u32(uVar14 << 0x10)
            uVar9 = s32(uVar18) >> 0x10
            if (uVar9 & 0xff00) == 0:
                if (uVar9 & 0xfff0) == 0:
                    iVar10, iVar22, iVar23, iVar11 = 0xf, 0xe, 0xd, 0xc
                else:
                    uVar18 = u32(s32(s32(uVar18) >> 0x14) << 0x10)
                    iVar10, iVar22, iVar23, iVar11 = 0xb, 10, 9, 8
            elif (uVar9 & 0xf000) == 0:
                uVar18 = u32(s32(s32(uVar18) >> 0x18) << 0x10)
                iVar10, iVar22, iVar23, iVar11 = 7, 6, 5, 4
            else:
                uVar18 = u32(s32(s32(uVar18) >> 0x1c) << 0x10)
                iVar10, iVar22, iVar23, iVar11 = 3, 2, 1, 0
            uVar18 = u32(uVar18) >> 0x10
            if (uVar18 & 0xc) == 0:
                if (uVar18 & 0xe) == 0:
                    iVar22 = iVar10
                uVar9 = iVar22 + 0xf
            else:
                if (uVar18 & 8) == 0:
                    iVar11 = iVar23
                uVar9 = iVar11 + 0xf
            uVar18 = 0x1d - uVar9
        else:
            uVar18 = u32((uVar14 >> 0x10) << 0x10)
            uVar9 = s32(uVar18) >> 0x10
            if (uVar9 & 0xff00) == 0:
                if (uVar9 & 0xfff0) == 0:
                    iVar10, iVar22, iVar23, iVar11 = 0xf, 0xe, 0xd, 0xc
                else:
                    uVar18 = u32(s32(s32(uVar18) >> 0x14) << 0x10)
                    iVar10, iVar22, iVar23, iVar11 = 0xb, 10, 9, 8
            elif (uVar9 & 0xf000) == 0:
                uVar18 = u32(s32(s32(uVar18) >> 0x18) << 0x10)
                iVar10, iVar22, iVar23, iVar11 = 7, 6, 5, 4
            else:
                uVar18 = u32(s32(s32(uVar18) >> 0x1c) << 0x10)
                iVar10, iVar22, iVar23, iVar11 = 3, 2, 1, 0
            uVar18 = u32(uVar18) >> 0x10
            if (uVar18 & 0xc) == 0:
                if (uVar18 & 0xe) == 0:
                    iVar22 = iVar10
                uVar9 = iVar22 - 1
            else:
                if (uVar18 & 8) == 0:
                    iVar11 = iVar23
                uVar9 = iVar11 - 1
            uVar18 = 0x1d - uVar9

        # ---- reciprocal of the normalised mantissa -> band gain ----------- #
        uVar14 = u32(uVar14 << (uVar9 & 0xff))
        iVar11 = s32(uVar14) >> 0x10
        iVar10 = divsi3(0x1fffffff, iVar11)
        iVar22 = s32(iVar10 << 0x10) >> 0x10
        iVar23 = _add(_mul(iVar11, iVar22), s32(_mul(uVar14 & 0xffff, iVar22)) >> 0x10)
        iVar11 = s32(iVar23 * -8)
        iVar11 = _add(_add(_add(_mul(iVar22, s32(iVar11) >> 0x10),
                                _mul(((s32(iVar10) >> 0xf) + 1) >> 1, iVar11)),
                           s32(iVar10 << 0x10)),
                      s32(_mul(iVar22, u32(iVar23 * -0x80000) >> 0x10)) >> 0x10)

        if s32(uVar18) < 1:
            uVar18 = s32(-uVar18)
            iVar22 = s32(0x7fffffff) >> (uVar18 & 0xff)
            if iVar11 <= iVar22:
                iVar10 = s32(-0x80000000) >> (uVar18 & 0xff)
                iVar22 = iVar11
                if iVar11 < iVar10:
                    iVar22 = iVar10
            uVar14 = u32(iVar22 << (uVar18 & 0xff))
            if 0x7ffe < s32(uVar14):
                uVar14 = 0x7fff
        elif s32(uVar18) < 0x20:
            uVar14 = u32(s32(iVar11) >> (uVar18 & 0xff))
            if 0x7ffe < s32(uVar14):
                uVar14 = 0x7fff
        else:
            uVar14 = 0

        # ---- derive the Q16 scale triple from ctx[0x414]/uVar14 ----------- #
        uVar18 = ld_u32(ctx, C_414)
        if uVar18 == uVar14:
            uVar19 = 0x10000
            uVar18 = 0
            uVar9 = 1
        else:
            sg = s32(uVar14) >> 31
            uVar9 = u32((uVar14 ^ sg) - sg)                    # abs(uVar14)
            if (uVar9 & 0xffff0000) == 0:
                uVar9 = u32(s32(uVar9) << 0x10)
                uVar19 = s32(uVar9) >> 0x10
                if (uVar19 & 0xff00) == 0:
                    if (uVar19 & 0xfff0) == 0:
                        iVar11, iVar22, iVar23, iVar10 = 0xf, 0xe, 0xd, 0xc
                    else:
                        uVar9 = u32(s32(s32(uVar9) >> 0x14) << 0x10)
                        iVar11, iVar22, iVar23, iVar10 = 0xb, 10, 9, 8
                elif (uVar19 & 0xf000) == 0:
                    uVar9 = u32(s32(s32(uVar9) >> 0x18) << 0x10)
                    iVar11, iVar22, iVar23, iVar10 = 7, 6, 5, 4
                else:
                    uVar9 = u32(s32(s32(uVar9) >> 0x1c) << 0x10)
                    iVar11, iVar22, iVar23, iVar10 = 3, 2, 1, 0
                uVar9 = u32(uVar9) >> 0x10
                if (uVar9 & 0xc) == 0:
                    if (uVar9 & 0xe) != 0:
                        iVar11 = iVar22
                    iVar22 = iVar11 + 0x1c
                    uVar9 = iVar11 + 0xf
                elif (uVar9 & 8) == 0:
                    iVar22 = iVar23 + 0x1c
                    uVar9 = iVar23 + 0xf
                else:
                    iVar22 = iVar10 + 0x1c
                    uVar9 = iVar10 + 0xf
            else:
                if (uVar9 >> 0x10) == 0:
                    iVar11 = 0x10
                else:
                    uVar9 = u32((uVar9 >> 0x10) << 0x10)
                    uVar19 = s32(uVar9) >> 0x10
                    if (uVar19 & 0xff00) == 0:
                        if (uVar19 & 0xfff0) == 0:
                            iVar22, iVar11, iVar10, iVar23 = 0xf, 0xe, 0xd, 0xc
                        else:
                            uVar9 = u32(s32(s32(uVar9) >> 0x14) << 0x10)
                            iVar22, iVar11, iVar10, iVar23 = 0xb, 10, 9, 8
                    elif (uVar19 & 0xf000) == 0:
                        uVar9 = u32(s32(s32(uVar9) >> 0x18) << 0x10)
                        iVar22, iVar11, iVar10, iVar23 = 7, 6, 5, 4
                    else:
                        uVar9 = u32(s32(s32(uVar9) >> 0x1c) << 0x10)
                        iVar22, iVar11, iVar10, iVar23 = 3, 2, 1, 0
                    uVar9 = u32(uVar9) >> 0x10
                    if (uVar9 & 0xc) == 0:
                        if (uVar9 & 0xe) == 0:
                            iVar11 = iVar22
                    else:
                        iVar11 = iVar10
                        if (uVar9 & 8) != 0:
                            iVar11 = iVar23
                iVar22 = iVar11 + 0xc
                uVar9 = iVar11 - 1

            sg = s32(uVar18) >> 31
            uVar19 = u32((uVar18 ^ sg) - sg)                   # abs(ctx[0x414])
            uVar9 = u32(uVar14 << (uVar9 & 0xff))
            if (uVar19 & 0xffff0000) == 0:
                if (uVar19 & 0xffff) == 0:
                    uVar19 = 0x1f
                else:
                    uVar19 = u32(s32(uVar19) << 0x10)
                    uVar1 = s32(uVar19) >> 0x10
                    if (uVar1 & 0xff00) == 0:
                        if (uVar1 & 0xfff0) == 0:
                            iVar23, iVar11, iVar12, iVar10 = 0xf, 0xe, 0xd, 0xc
                        else:
                            uVar19 = u32(s32(s32(uVar19) >> 0x14) << 0x10)
                            iVar23, iVar11, iVar12, iVar10 = 0xb, 10, 9, 8
                    elif (uVar1 & 0xf000) == 0:
                        uVar19 = u32(s32(s32(uVar19) >> 0x18) << 0x10)
                        iVar23, iVar11, iVar12, iVar10 = 7, 6, 5, 4
                    else:
                        uVar19 = u32(s32(s32(uVar19) >> 0x1c) << 0x10)
                        iVar23, iVar11, iVar12, iVar10 = 3, 2, 1, 0
                    uVar19 = u32(uVar19) >> 0x10
                    if (uVar19 & 0xc) == 0:
                        if (uVar19 & 0xe) == 0:
                            iVar11 = iVar23
                        uVar19 = iVar11 + 0xf
                    elif (uVar19 & 8) == 0:
                        uVar19 = iVar12 + 0xf
                    else:
                        uVar19 = iVar10 + 0xf
            else:
                goto_e8dc = False
                if (uVar19 >> 0x10) == 0:
                    iVar11 = 0x10
                else:
                    uVar19 = u32((uVar19 >> 0x10) << 0x10)
                    uVar1 = s32(uVar19) >> 0x10
                    if (uVar1 & 0xff00) == 0:
                        if (uVar1 & 0xfff0) == 0:
                            iVar23, iVar10, iVar11, iVar12 = 0xf, 0xe, 0xd, 0xc
                        else:
                            uVar19 = u32(s32(s32(uVar19) >> 0x14) << 0x10)
                            iVar23, iVar10, iVar11, iVar12 = 0xb, 10, 9, 8
                    elif (uVar1 & 0xf000) == 0:
                        uVar19 = u32(s32(s32(uVar19) >> 0x18) << 0x10)
                        iVar23, iVar10, iVar11, iVar12 = 7, 6, 5, 4
                    else:
                        uVar19 = u32(s32(s32(uVar19) >> 0x1c) << 0x10)
                        iVar23, iVar10, iVar11, iVar12 = 3, 2, 1, 0
                    uVar19 = u32(uVar19) >> 0x10
                    if (uVar19 & 0xc) == 0:
                        if (uVar19 & 0xe) == 0:
                            iVar10 = iVar23
                        uVar19 = iVar10 - 1
                        goto_e8dc = True
                    else:
                        if (uVar19 & 8) != 0:
                            iVar11 = iVar12
                if not goto_e8dc:
                    uVar19 = iVar11 - 1

            # ---- LAB_0014e8dc --------------------------------------------- #
            iVar10 = u32(uVar18 << (uVar19 & 0xff))
            q = divsi3(0x1fffffff, s32(iVar10) >> 0x10)
            iVar11 = s16(q)                                   # 16-bit temporary
            uVar19 = u32(iVar22 - uVar19)
            iVar22 = _add(_mul(s32(uVar9) >> 0x10, iVar11),
                          s32(_mul(uVar9 & 0xffff, iVar11)) >> 0x10)
            hi64 = (s32(iVar22) * s32(iVar10)) >> 0x20
            uVar9 = u32(_add(uVar9, s32(hi64 * -8)))
            iVar11 = _add(_add(_mul(iVar11, s32(uVar9) >> 0x10), iVar22),
                          s32(_mul(iVar11, uVar9 & 0xffff)) >> 0x10)

            if s32(uVar19) < 1:
                uVar19 = s32(-uVar19)
                iVar22 = s32(0x7fffffff) >> (uVar19 & 0xff)
                if iVar11 <= iVar22:
                    iVar10 = s32(-0x80000000) >> (uVar19 & 0xff)
                    iVar22 = iVar11
                    if iVar11 < iVar10:
                        iVar22 = iVar10
                uVar19 = u32(iVar22 << (uVar19 & 0xff))
                uVar18 = uVar19 & 0xffff
                uVar9 = s32(uVar19) >> 0x10
            elif s32(uVar19) < 0x20:
                uVar19 = u32(s32(iVar11) >> (uVar19 & 0xff))
                uVar18 = uVar19 & 0xffff
                uVar9 = s32(uVar19) >> 0x10
            else:
                uVar19 = 0
                uVar18 = 0
                uVar9 = 0

        # ---- scale the synthesis state / mux ------------------------------ #
        ecb8 = False
        memset_path = False
        if ld_s32(ctx, C_350C) == 0 or ld_s32(ctx, C_3510) != 0:
            if uVar20 == 0:
                ecb8 = True
        else:
            uVar1 = local_660 if local_660 >= 2 else uVar20
            if uVar1 != 1:
                if uVar20 == 0:
                    ecb8 = True
            else:
                ecb8 = True
                memset_path = True

        if ecb8:
            if memset_path:
                memcpy(frame_info, local_664, b'\x00' * 10, 0, 10)
                st_u16(frame_info, local_664 + 4, 0x1000)
                st_u32(frame_info, 4 * local_660, ld_u32(ctx, C_2BB8))
            local_648 = s32(ld_s32(frame_info, 4 * local_660))
            if (local_660 & ((1 if iVar7 < 4 else 0) * -2 + 3)) == 0:
                iVar11 = s32(ld_s32(ctx, C_2BE0) - 2 - ld_s32(ctx, C_2BE8)) - local_648
                memcpy(au88, 0, b'\x00' * _N_AU88, 0, _N_AU88)
                _f1507bc(ctx, 2 * ((ld_s32(ctx, C_2BE0) >> 2) * local_660 + iVar11 + 0x121c),
                         frame_info, 36 + 32 * (local_660 >> 1),
                         au88, 0, asStack, 2 * iVar11,
                         ld_s32(ctx, C_2BE0) - iVar11, ld_s32(ctx, C_2BE8))
                uVar20 = u32(uVar14 << 0x10)
                if local_660 == 0:
                    uVar20 = _mul(_mul(s16(ld_u32(frame_info, 0x23 * 4)),
                                       s32(uVar20) >> 0x10), 4)
                if local_648 > -2:
                    base = (local_678 + 0x106) * 4
                    for n in range(2 + local_648):
                        x = ld_s16(asStack, 2 * (479 - n))
                        st_u32(ctx, base - 4 * (n + 1),
                               _add(_mul(x, s32(uVar20) >> 0x10),
                                    s32(_mul(x, uVar20 & 0xffff)) >> 0x10))
                    uVar20 = 0
            elif uVar19 != 0x10000 and local_648 > -2:
                base = (local_678 + 0x106) * 4
                for n in range(local_648 + 2):
                    pi = base - 4 * (n + 1)
                    lr = ld_s32(ctx, pi)
                    iVar22 = s16(lr)
                    st_u32(ctx, pi,
                           _add(_add(_mul(((s32(lr) >> 0xf) + 1) >> 1, uVar19),
                                     _mul(iVar22, uVar9)),
                                s32(_mul(iVar22, uVar18)) >> 0x10))
            uVar20 = 0

        # ---- scale the 16-word synthesis state (LAB_0014e998) ------------- #
        for k in range(16):
            x = ld_s32(ctx, piVar17 + 4 * k)
            iVar22 = s16(x)
            st_u32(ctx, piVar17 + 4 * k,
                   _add(_add(_mul(((s32(x) >> 0xf) + 1) >> 1, uVar19),
                             _mul(iVar22, uVar9)),
                        s32(_mul(iVar22, uVar18)) >> 0x10))
        st_u32(ctx, C_414, uVar14)

        iVar11 = local_678
        if uVar20 == 0:
            iVar22 = ld_s32(ctx, C_2BE4)
            if iVar22 > 0:
                iVar21 = (local_678 - local_648 + 0x108) * 4
                c = [ld_s16(frame_info, local_664 + 2 * j) for j in range(5)]
                iVar10 = 0
                while True:
                    iVar15 = iVar21 + iVar10
                    acc = ld_s32(ctx, __src + iVar10)
                    tot = 0
                    for tapoff, cval in ((-0x10, c[4]), (-0xc, c[3]),
                                         (-8, c[2]), (-4, c[1]), (0, c[0])):
                        tot = _add(tot, _exact_mul(ld_u32(ctx, iVar15 + tapoff), cval))
                    val = _add(acc, ((s32(tot) >> 3) + 1) >> 1)
                    st_u32(ctx, local_674 + iVar10, val)
                    iVar11 += 1
                    st_u32(ctx, 0x418 + local_678 * 4 + iVar10, _mul(val, 0x40))
                    iVar15 += 4
                    iVar10 += 4
                    if not (iVar11 - local_678 < ld_s32(ctx, C_2BE4)):
                        break
        else:
            memcpy(ctx, local_674, ctx, __src, ld_s32(ctx, C_2BE4) << 2)
            iVar22 = ld_s32(ctx, C_2BE4)

        local_678 = iVar11
        _f14e29c(ctx, piVar17, local268, 0, ctx, local_674, au48, 0,
                 ld_s32(ctx, C_2BE8), iVar22)

        iVar11 = ld_s32(ctx, C_2BE4)
        if iVar11 > 0:
            for k in range(iVar11):
                uVar14 = ld_u32(local268, 4 * k)
                iVar10 = s32(_add(_add(_mul(s32(uVar14) >> 0x10, s16(uVar25)),
                                        _mul(uVar14, ((s32(uVar25) >> 0xf) + 1) >> 1)),
                                   s32(_mul(uVar14 & 0xffff, s16(uVar25))) >> 0x10))
                iVar10 = ((s32(iVar10) >> 9) + 1) >> 1
                st_s16(ctx, local_64c + 2 * k, clamp_hi16(iVar10))

        local_660 += 1
        memcpy(ctx, piVar17, ctx, piVar17 + 4 * iVar11, 0x40)
        local_664 += 10
        local_658 += 1
        if local_660 == 4:
            __n = ld_s32(ctx, C_2BE0) * 2
            memcpy(samp, 0, ctx, 0x2438 + __n, __n)
            return
        iVar11 = ld_s32(ctx, C_2BE4) * 4
        local_674 += iVar11
        local_64c += ld_s32(ctx, C_2BE4) * 2
        __src += iVar11


def _selftest():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import check

    def call(st, r):
        dequant(st['ctx'], st['frame_info'], st['samp'], st['coeffs'])

    return check('dequant', call, compare=('ctx', 'frame_info', 'samp', 'coeffs'))


if __name__ == '__main__':
    total, failed = _selftest()
    raise SystemExit(1 if failed else 0)
