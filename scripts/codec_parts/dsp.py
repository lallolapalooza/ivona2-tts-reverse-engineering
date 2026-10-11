"""Shared DSP helpers for the IVONA gap codec (clean-room stdlib port).

Transliterated from ``out/ghidra_dump/libttsivonavoice.c`` (Ghidra addr = ELF
vaddr + 0x10000):

  f1496c0  FUN_001496c0  (ELF 0x1396c0)  iterative spectral refinement: takes n
                                        32-bit coefficients and produces n Q15
                                        shorts (the 16-band LPC -> spectrum map)
  f14dc30  FUN_0014dc30  (ELF 0x13dc30)  in-place scaling of n 16-bit samples
  f14dca4  FUN_0014dca4  (ELF 0x13dca4)  per-band ramp reset in ctx
  f150a14  FUN_00150a14  (ELF 0x140a14)  n int32 coeffs -> n Q15 coeffs
                                        (cosine-table interpolation + Levinson)
  f14f940  FUN_0014f940  (ELF 0x13f940)  one Schur/Levinson refinement pass
  f151448  FUN_00151448  (ELF 0x141448)  in-place Q15 polynomial scaling

Everything uses 32-bit wrapping arithmetic and arithmetic right shifts, exactly
as the ARM ``SMULL``/``UMULL``/``__divsi3`` sequences of the original.

The inverse transforms (``FUN_00150028`` / ``FUN_0015027c``) and the stage entry
``xform`` live in ``xform.py``.
"""
from prims import (u32, s32, s16, ld_s16, ld_s32, ld_u32,
                   st_u16, st_u32, divsi3)
from tables import tables

__all__ = ['f1496c0', 'f14dc30', 'f14dca4', 'f150a14', 'f14f940', 'f151448']

# FUN_00150a14 loads the 129-entry Q13 cosine table (0x2000*cos(pi*i/128),
# i = 0..128) from the .got slot at ELF 0x185db0, whose (relocated) value is
# ELF 0x17e354.
_COS_GOT = 0x185db0


def _ctab(i):
    return tables().s32(tables().ptr(_COS_GOT) + 4 * i)


# --------------------------------------------------------------------------- #
# 32-bit multiply helpers (the SMULL/UMULL idioms Ghidra renders inline)
# --------------------------------------------------------------------------- #
def _mulhi_s(a, b):
    """High 32 bits of the signed 64-bit product ``a*b``."""
    return s32(((s32(a) * s32(b)) >> 32) & 0xFFFFFFFF)


def _mulhi_u(a, b):
    """High 32 bits of the unsigned 64-bit product ``a*b``."""
    return s32((((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) >> 32) & 0xFFFFFFFF)


def _shr64_1(hi, lo):
    """``u32((((s64)hi:lo) + 1) >> 1)`` -- 64-bit add-one then arithmetic shift.

    Ghidra renders this as
    ``(uint)((char)(hi) + (0xfffffffe < lo) & 1) << 0x1f | (lo + 1) >> 1``.
    """
    x = (s32(hi) << 32) | u32(lo)
    return u32((x + 1) >> 1)


def _q19(a, b, m):
    """The ``(uVar7, mulhi_s(a,b))`` word: low32(a*b)>>19 | m<<13."""
    return u32((u32(a * b) >> 0x13) | u32(m * 0x2000))


# --------------------------------------------------------------------------- #
# FUN_0014dc30  (ELF 0x13dc30)
# --------------------------------------------------------------------------- #
def f14dc30(buf, off, n, mult):
    """Scale ``n`` signed 16-bit samples at byte offset ``off`` of ``buf``.

    ``mult`` is the 32-bit multiplier; the reciprocal of ``0x10000`` seeds the
    geometric update of the per-tap multiplier.
    """
    iVar3 = u32(mult - 0x10000)
    p = s32(mult)
    if n > 1:
        k = 0
        while True:
            v = ld_s16(buf, off + 2 * k)
            st_u16(buf, off + 2 * k, ((s32(v * p) >> 15) + 1) >> 1)
            p = s32(p + (((s32(iVar3 * p) >> 15) + 1) >> 1))
            k += 1
            if k == n - 1:
                break
    v = ld_s16(buf, off + 2 * (n - 1))
    st_u16(buf, off + 2 * (n - 1), ((s32(v * p) >> 15) + 1) >> 1)


# --------------------------------------------------------------------------- #
# FUN_0014dca4  (ELF 0x13dca4)
# --------------------------------------------------------------------------- #
def f14dca4(ctx):
    """Reset the per-band ramps at ctx+0x3480 and the LCG/accumulator state."""
    n = ld_s32(ctx, 0x2be8)
    step = divsi3(0x7FFF, n + 1)
    acc = 0
    for k in range(n):
        acc = s32(acc + step)
        st_u32(ctx, 0x3480 + 4 * k, acc)
    st_u32(ctx, 0x3504, 0x307880)
    st_u32(ctx, 0x3500, 0)


# --------------------------------------------------------------------------- #
# FUN_00151448  (ELF 0x141448)
# --------------------------------------------------------------------------- #
def f151448(buf, off, n, mult):
    """In-place Q15 polynomial scaling of the ``n`` 32-bit words at ``off``."""
    idx = 0
    uVar5 = u32(mult)
    if 0 < n - 1:
        while True:
            uVar3 = u32(ld_u32(buf, off + 4 * idx))
            iVar1 = s16(uVar5)
            iVar2 = ((s32(uVar5) >> 0xF) + 1) >> 1
            st_u32(buf, off + 4 * idx,
                   u32(s32(s32(uVar3) >> 0x10) * iVar1 + s32(uVar3 * iVar2) +
                       (s32(u32((uVar3 & 0xFFFF) * iVar1)) >> 0x10)))
            uVar5 = u32(s32(s32(mult) >> 0x10) * iVar1 + s32(mult * iVar2) +
                        (s32(u32((mult & 0xFFFF) * iVar1)) >> 0x10))
            idx += 1
            if not (idx < n - 1):
                break
    uVar3 = u32(ld_u32(buf, off + 4 * (n - 1)))
    iVar1 = s16(uVar5)
    st_u32(buf, off + 4 * (n - 1),
           u32(s32(s32(uVar3) >> 0x10) * iVar1 +
               s32(uVar3 * (((s32(uVar5) >> 0xF) + 1) >> 1)) +
               (s32(u32((uVar3 & 0xFFFF) * iVar1)) >> 0x10)))


# --------------------------------------------------------------------------- #
# FUN_0014f940  (ELF 0x13f940)
# --------------------------------------------------------------------------- #
def f14f940(out, ooff, src, soff, n):
    """One Schur/Levinson refinement pass over the ``n`` Q15 shorts at ``src``.

    Writes one 32-bit word to ``out`` and returns 1 while refining, 0 on
    convergence.  ``src`` is read as signed 16-bit samples.
    """
    A = [0] * 33
    lb = (n & 1) * 16

    def tail(lb_):
        v = A[lb_]
        if u32(v + 0xFFF0) <= 0x1FFE0:
            u2 = u32(v * -0x8000)
            x = s32(0x3FFFFFFF - u32(_mulhi_u(u2, u2) +
                                     u32(u2 * (s32(u2) >> 31) * 2)))
            st_u32(out, ooff, u32(_mulhi_s(x, ld_s32(out, ooff)) << 2))
            return 0
        return 1

    if n > 0:
        for i in range(n):
            A[lb + i] = s32(s16(ld_s16(src, soff + 2 * i)) << 4)
    uVar13 = u32(n - 1)
    iVar5 = 0x40000000
    st_u32(out, ooff, 0x40000000)
    if s32(uVar13) < 1:
        return tail(lb)
    iVar6 = A[lb + uVar13]
    if not (u32(iVar6 + 0xFFF0) <= 0x1FFE0):
        return 1
    piVar3 = lb
    local_bc = (n - 2) * 4
    while True:
        uVar2 = u32(iVar6 * -0x8000)
        uVar9 = u32(0x3FFFFFFF - u32(_mulhi_u(uVar2, uVar2) +
                                     u32(uVar2 * (s32(uVar2) >> 31) * 2)))
        uVar8 = u32(abs(s32(uVar9)))

        # ---- normalise uVar8 -> (uVar8, uVar10) --------------------------- #
        if (uVar8 & 0xFFFF0000) == 0:
            if (uVar8 & 0xFFFF) == 0:
                uVar8 = 0xFFFFFFF0
                uVar10 = 0x1F
            else:
                uVar8 = u32(uVar8 * 0x10000)
                uVar10 = s32(uVar8) >> 0x10
                if (uVar10 & 0xFF00) == 0:
                    if (uVar10 & 0xFFF0) == 0:
                        n7, n11, n4, n6 = 0xF, 0xE, 0xD, 0xC
                    else:
                        uVar8 = u32((s32(uVar8) >> 0x14) << 0x10)
                        n7, n11, n4, n6 = 0xB, 0xA, 9, 8
                elif (uVar10 & 0xF000) == 0:
                    uVar8 = u32((s32(uVar8) >> 0x18) << 0x10)
                    n7, n11, n4, n6 = 7, 6, 5, 4
                else:
                    uVar8 = u32((s32(uVar8) >> 0x1C) << 0x10)
                    n7, n11, n4, n6 = 3, 2, 1, 0
                uVar8 = uVar8 >> 0x10
                if (uVar8 & 0xC) == 0:
                    if (uVar8 & 0xE) == 0:
                        n11 = n7
                    uVar10 = u32(n11 + 0xF)
                    uVar8 = u32(0xF - uVar10)
                else:
                    if (uVar8 & 8) == 0:
                        n6 = n4
                    uVar10 = u32(n6 + 0xF)
                    uVar8 = u32(0xF - uVar10)
        elif (uVar8 >> 0x10) == 0:
            uVar10 = 0xF
            uVar8 = 0
        else:
            uVar8 = u32((uVar8 >> 0x10) << 0x10)
            uVar10 = s32(uVar8) >> 0x10
            if (uVar10 & 0xFF00) == 0:
                if (uVar10 & 0xFFF0) == 0:
                    n7, n11, n4, n6 = 0xF, 0xE, 0xD, 0xC
                else:
                    uVar8 = u32((s32(uVar8) >> 0x14) << 0x10)
                    n7, n11, n4, n6 = 0xB, 0xA, 9, 8
            elif (uVar10 & 0xF000) == 0:
                uVar8 = u32((s32(uVar8) >> 0x18) << 0x10)
                n7, n11, n4, n6 = 7, 6, 5, 4
            else:
                uVar8 = u32((s32(uVar8) >> 0x1C) << 0x10)
                n7, n11, n4, n6 = 3, 2, 1, 0
            uVar8 = uVar8 >> 0x10
            if (uVar8 & 0xC) == 0:
                if (uVar8 & 0xE) == 0:
                    n11 = n7
                uVar10 = u32(n11 - 1)
                uVar8 = u32(0xF - uVar10)
            else:
                if (uVar8 & 8) == 0:
                    n6 = n4
                uVar10 = u32(n6 - 1)
                uVar8 = u32(0xF - uVar10)

        uVar10 = u32(uVar9 << (uVar10 & 0xFF))
        iVar6t = s32(uVar10) >> 0x10
        iVar4t = divsi3(0x1FFFFFFF, iVar6t)
        iVar11t = s32(u32(iVar4t * 0x10000)) >> 0x10
        iVar7t = s32(u32(iVar6t * iVar11t) +
                     u32(s32(u32((uVar10 & 0xFFFF) * iVar11t)) >> 0x10))
        iVar6u = s32(iVar7t * -8)
        iVar6v = s32(u32(u32(iVar11t * (s32(iVar6u) >> 0x10)) +
                         u32(u32(((s32(iVar4t) >> 0xF) + 1) >> 1) * iVar6u) +
                         u32(iVar4t * 0x10000) +
                         u32(s32(u32(iVar11t * (u32(iVar7t * -0x80000) >> 0x10))) >> 0x10)))

        take_fad8 = False
        if s32(uVar8) < 1:
            uVar8 = u32(-uVar8)
            iVar11x = s32(0x7FFFFFFF >> (uVar8 & 0xFF))
            if iVar6v <= iVar11x:
                iVar4x = s32(-0x80000000) >> (uVar8 & 0xFF)
                iVar11x = iVar6v
                if iVar6v < iVar4x:
                    iVar11x = iVar4x
            uVar8 = u32(iVar11x << (uVar8 & 0xFF))
            take_fad8 = True
        elif s32(uVar8) < 0x20:
            uVar8 = u32(s32(iVar6v) >> (uVar8 & 0xFF))
            take_fad8 = True
        else:
            st_u32(out, ooff, u32(_mulhi_s(uVar9, iVar5) << 2))
            lb2 = (uVar13 & 1) * 16
            iVar6 = A[piVar3]
            uVar9 = u32(A[piVar3 + local_bc // 4])
            local_c0 = 0xFFFFFFF1
            uVar8 = 0
            iVar5 = 0

        if take_fad8:
            lb2 = (uVar13 & 1) * 16
            st_u32(out, ooff, u32(_mulhi_s(uVar9, iVar5) << 2))
            if (uVar8 & 0xFFFF0000) == 0:
                if (uVar8 & 0xFFFF) == 0:
                    uVar8 = u32(uVar8 << 0x1F)
                    iVar5 = s32(uVar8) >> 0x1F
                    iVar6 = A[piVar3]
                    uVar9 = u32(A[piVar3 + local_bc // 4])
                    local_c0 = 0xFFFFFFF1
                else:
                    ub = u32(uVar8 << 0x10)
                    uVar10 = s32(ub) >> 0x10
                    if (uVar10 & 0xFF00) == 0:
                        high = (uVar10 & 0xFFF0) != 0
                        if high:
                            ub = u32((s32(ub) >> 0x14) << 0x10)
                        uVar10 = u32(ub) >> 0x10
                        ub = uVar10
                        if high:
                            e4, e5, e6, e7 = 0xB, 0xA, 9, 8
                        else:
                            e4, e5, e6, e7 = 0xF, 0xE, 0xD, 0xC
                    else:
                        if (uVar10 & 0xF000) == 0:
                            ub = u32(s32(ub) >> 0x18)
                            e4, e5, e6, e7 = 7, 6, 5, 4
                        else:
                            ub = u32(s32(ub) >> 0x1C)
                            e4, e5, e6, e7 = 3, 2, 1, 0
                        uVar10 = ub & 0xFFFF
                    if (ub & 0xC) == 0:
                        if (uVar10 & 0xE) != 0:
                            ub = u32(e5 + 0xF)
                            local_c0 = u32(0x10 - ub)
                            _fb74 = True
                            goto_fb74 = True
                        else:
                            uVar8 = u32(uVar8 << (e4 + 0xF))
                            local_c0 = u32(0x10 - (e4 + 0xF))
                            iVar6 = A[piVar3]
                            uVar9 = u32(A[piVar3 + local_bc // 4])
                            iVar5 = s32(uVar8) >> 0x1F
                            goto_fb74 = False
                    elif (ub & 8) == 0:
                        uVar8 = u32(uVar8 << (e6 + 0xF))
                        local_c0 = u32(0x10 - (e6 + 0xF))
                        iVar5 = s32(uVar8) >> 0x1F
                        iVar6 = A[piVar3]
                        uVar9 = u32(A[piVar3 + local_bc // 4])
                        goto_fb74 = False
                    else:
                        uVar8 = u32(uVar8 << (e7 + 0xF))
                        local_c0 = u32(0x10 - (e7 + 0xF))
                        iVar5 = s32(uVar8) >> 0x1F
                        iVar6 = A[piVar3]
                        uVar9 = u32(A[piVar3 + local_bc // 4])
                        goto_fb74 = False
                    if goto_fb74:
                        uVar8 = u32(uVar8 << (ub & 0xFF))
                        iVar6 = A[piVar3]
                        uVar9 = u32(A[piVar3 + local_bc // 4])
                        iVar5 = s32(uVar8) >> 0x1F
            else:
                if (uVar8 >> 0x10) == 0:
                    local_c0 = 1
                    ub = 0xF
                else:
                    ub = u32((uVar8 >> 0x10) << 0x10)
                    uVar10 = s32(ub) >> 0x10
                    if (uVar10 & 0xFF00) == 0:
                        if (uVar10 & 0xFFF0) == 0:
                            e4, e5, e11, e6 = 0xF, 0xE, 0xD, 0xC
                        else:
                            ub = u32((s32(ub) >> 0x14) << 0x10)
                            e4, e5, e11, e6 = 0xB, 0xA, 9, 8
                    elif (uVar10 & 0xF000) == 0:
                        ub = u32((s32(ub) >> 0x18) << 0x10)
                        e4, e5, e11, e6 = 7, 6, 5, 4
                    else:
                        ub = u32((s32(ub) >> 0x1C) << 0x10)
                        e4, e5, e11, e6 = 3, 2, 1, 0
                    ub = u32(ub) >> 0x10
                    if (ub & 0xC) == 0:
                        if (ub & 0xE) == 0:
                            e5 = e4
                        ub = u32(e5 - 1)
                        local_c0 = u32(0x10 - ub)
                    elif (ub & 8) == 0:
                        ub = u32(e11 - 1)
                        local_c0 = u32(0x10 - ub)
                    else:
                        ub = u32(e6 - 1)
                        local_c0 = u32(0x10 - ub)
                uVar8 = u32(uVar8 << (ub & 0xFF))
                iVar6 = A[piVar3]
                uVar9 = u32(A[piVar3 + local_bc // 4])
                iVar5 = s32(uVar8) >> 0x1F

        # ---- the Schur update loop ---------------------------------------- #
        iVar11 = 0
        puVar12 = piVar3 + (local_bc - 4) // 4
        piVar14 = lb2
        while True:
            iVar11 += 1
            inner = u32(u32((s32(uVar9) >> 31) * uVar2) +
                        u32(uVar9 * (s32(uVar2) >> 31)) + u32(_mulhi_u(uVar2, uVar9)))
            uVar9 = u32(iVar6 - 2 * inner)
            local_cc = u32(_mulhi_u(uVar8, uVar9))
            A[piVar14] = u32(u32(u32(uVar8 * (s32(uVar9) >> 31)) +
                                 u32(uVar9 * iVar5) + local_cc) << (local_c0 & 0xFF))
            if s32(uVar13) <= iVar11:
                break
            piVar3 += 1
            iVar6 = A[piVar3]
            uVar9 = u32(A[puVar12])
            puVar12 -= 1
            piVar14 += 1

        uVar13 = u32(uVar13 - 1)
        if uVar13 == 0:
            return tail(lb2)
        iVar6 = A[lb2 + local_bc // 4]
        if not (u32(iVar6 + 0xFFF0) <= 0x1FFE0):
            return 1
        iVar5 = ld_s32(out, ooff)
        piVar3 = lb2
        local_bc -= 4


# --------------------------------------------------------------------------- #
# FUN_00150a14  (ELF 0x140a14)
# --------------------------------------------------------------------------- #
def f150a14(dst, doff, src, soff, n):
    """Convert ``n`` 32-bit coefficients at ``src`` into ``n`` Q15 shorts.

    Uses the .rodata cosine table for the piecewise-linear interpolation, then
    a Levinson-style recursion plus 10 Newton iterations of Q15 gain scaling.
    """
    lb0 = [0] * 16
    if n > 0:
        for i in range(n):
            x = s32(ld_s32(src, soff + 4 * i))
            xd = s32(x) >> 8
            lb0[i] = s32(s32((x - s32(xd << 8)) *
                             s32(_ctab(xd + 1) - _ctab(xd))) +
                         s32(_ctab(xd) << 8))

    l4c = [0] * 10
    l70 = [0] * 9
    iVar5 = s32(n) >> 1

    l4c[1] = u32(-lb0[0])
    l4c[0] = 0x100000
    if iVar5 < 2:
        l70[1] = u32(-lb0[1])
        l70[0] = 0x100000
        if iVar5 < 1:
            return _f150a14_tail(dst, doff, lb0, l70, l4c, n, iVar5)
    else:
        c12 = 1
        ci = 0
        while True:
            u8 = u32(lb0[c12 * 2])
            p15 = ci + 1
            u7 = u32(l4c[p15])
            sv = s32(u8)
            iv4 = sv >> 31
            iv2 = _mulhi_s(u8, u7)
            u7b = _q19(u8, u7, iv2)
            l4c[ci + 2] = u32(u32(u32(l4c[ci]) * 2) - _shr64_1(s32(iv2) >> 0x13, u7b))
            if c12 != 1:
                iv2b = c12
                if 3 < c12:
                    iv2b = c12 - 1
                    i18 = 0
                    l16c = u32(l4c[ci])
                    l154 = u32(l4c[p15])
                    while True:
                        u12 = u32(l4c[p15 + (i18 - 8) // 4])
                        iv9 = _mulhi_s(u8, l16c)
                        u7c = _q19(u8, l16c, iv9)
                        iv3 = _mulhi_s(u8, u12)
                        u10 = _q19(u8, u12, iv3)
                        l4c[p15 + i18 // 4] = u32(u32(u12 + l154) - _shr64_1(s32(iv9) >> 0x13, u7c))
                        u7d = u32(l4c[p15 + (i18 - 0xC) // 4])
                        iv2b -= 2
                        l4c[p15 + (i18 - 4) // 4] = u32(l16c + u32(u7d - _shr64_1(s32(iv3) >> 0x13, u10)))
                        i18 -= 8
                        l16c = u7d
                        l154 = u12
                        if not (2 < iv2b):
                            break
                    iv2b = u32((c12 - 2) - u32(u32(c12 - 4) & 0xFFFFFFFE))
                i18b = iv2b - 1
                p13 = iv2b
                p14 = i18b
                p16 = iv2b - 2
                while True:
                    u7e = u32(l4c[p14])
                    iv2c = _mulhi_s(u8, u7e)
                    u7f = _q19(u8, u7e, iv2c)
                    again = i18b != 1
                    i18b -= 1
                    l4c[p13] = u32(u32(u32(l4c[p13]) + u32(l4c[p16])) -
                                   _shr64_1(s32(iv2c) >> 0x13, u7f))
                    p13 -= 1
                    p14 -= 1
                    p16 -= 1
                    if not again:
                        break
            c12 += 1
            l4c[1] = u32(l4c[1] - u8)
            ci = p15
            if c12 == iVar5:
                break

        # ---- second recursion (odd taps) --------------------------------- #
        l70[1] = u32(-lb0[1])
        l70[0] = 0x100000
        c134 = 1
        l150 = 0
        while True:
            u7 = u32(lb0[l150 * 2 + 3])
            p15b = l150 + 1
            u8 = u32(l70[p15b])
            iv4 = s32(u7) >> 31
            iv2 = _mulhi_s(u7, u8)
            u8b = _q19(u7, u8, iv2)
            l70[l150 + 2] = u32(u32(u32(l70[l150]) * 2) - _shr64_1(s32(iv2) >> 0x13, u8b))
            if c134 != 1:
                pu13 = c134
                if 3 < c134:
                    iv2b = c134 - 1
                    i18 = 0
                    l160 = u32(l70[p15b])
                    l128 = u32(l70[l150])
                    while True:
                        u12 = u32(l70[p15b + (i18 - 8) // 4])
                        iv9 = _mulhi_s(u7, l128)
                        u8c = _q19(u7, l128, iv9)
                        iv3 = _mulhi_s(u7, u12)
                        u10 = _q19(u7, u12, iv3)
                        l70[p15b + i18 // 4] = u32(u32(u12 + l160) - _shr64_1(s32(iv9) >> 0x13, u8c))
                        u8d = u32(l70[p15b + (i18 - 0xC) // 4])
                        iv2b -= 2
                        l70[p15b + (i18 - 4) // 4] = u32(l128 + u32(u8d - _shr64_1(s32(iv3) >> 0x13, u10)))
                        i18 -= 8
                        l160 = u12
                        l128 = u8d
                        if not (2 < iv2b):
                            break
                    pu13 = u32((c134 - 2) - u32(u32(c134 - 4) & 0xFFFFFFFE))
                iv2b = pu13 - 1
                p14 = pu13
                p16 = iv2b
                p13b = pu13 - 2
                while True:
                    u8e = u32(l70[p16])
                    iv2c = _mulhi_s(u7, u8e)
                    u8f = _q19(u7, u8e, iv2c)
                    again = iv2b != 1
                    iv2b -= 1
                    l70[p14] = u32(u32(u32(l70[p13b]) + u32(l70[p14])) - _shr64_1(s32(iv2c) >> 0x13, u8f))
                    p14 -= 1
                    p16 -= 1
                    p13b -= 1
                    if not again:
                        break
            c134 += 1
            l70[1] = u32(l70[1] - u7)
            l150 = p15b
            if c134 == iVar5:
                break

    return _f150a14_tail(dst, doff, lb0, l70, l4c, n, iVar5)


def _f150a14_tail(dst, doff, lb0, l70, l4c, n, iVar5):
    """LAB_00150fcc..0x141058 + LAB_00151058..0x14115c."""
    lf0 = bytearray(4 * max(n, 1))
    for k in range(iVar5):
        iVar18 = u32(u32(l70[k + 1]) - u32(l70[k]))
        iVar2 = u32(u32(l4c[k]) + u32(l4c[k + 1]))
        st_u32(lf0, 4 * k, s32(-((((s32(iVar18 + iVar2)) >> 8) + 1) >> 1)))
        st_u32(lf0, 4 * (n - 1 - k), s32((((s32(iVar18 - iVar2)) >> 8) + 1) >> 1))

    if n > 0:
        idx = 0
        for _ in range(10):
            iVar5b = 0
            iVar2 = 0
            iVar18 = 0
            for i in range(n):
                a = u32(abs(ld_s32(lf0, 4 * i)))
                if iVar2 < a:
                    iVar5b = iVar18
                if a < iVar2:
                    a = iVar2
                iVar2 = s32(a)
                iVar18 += 1
            if iVar2 < 0x8000:
                break
            if 0x18040 < iVar2:
                iVar2 = 0x18041
            i2 = divsi3(u32(iVar2 * -0x3FEF + 0x1FF74011),
                        u32(iVar5b * iVar2 + iVar2) >> 2)
            idx += 1
            f151448(lf0, 0, n, u32(i2 + 0xFFBE))
        if idx == 10:
            for i in range(n):
                v = ld_s32(lf0, 4 * i)
                if v < -0x8000:
                    v = -0x8000
                if v < 0x8000:
                    st_u32(lf0, 4 * i, v)
                else:
                    st_u32(lf0, 4 * i, 0x7FFF)
        for i in range(n):
            st_u16(dst, doff + 2 * i, ld_s32(lf0, 4 * i))


# --------------------------------------------------------------------------- #
# FUN_001496c0  (ELF 0x1396c0)
# --------------------------------------------------------------------------- #
def f1496c0(dst, doff, src, soff, n):
    """Iterative spectral refinement.

    ``dst`` holds ``n`` 16-bit samples at byte offset ``doff`` (written);
    ``src`` holds ``n`` little-endian int32 coefficients at byte offset
    ``soff`` (read).
    """
    f150a14(dst, doff, src, soff, n)
    out = bytearray(4)
    iVar7 = 0
    while True:
        iVar2 = f14f940(out, 0, dst, doff, n)
        iVar3 = s32((iVar7 + 10) * iVar7)
        iVar7 += 1
        if iVar2 != 1:
            return
        f14dc30(dst, doff, n, u32(0x10000 - iVar3))
        if iVar7 == 0x14:
            break
    dst[doff:doff + 2 * n] = b'\x00' * (2 * n)
