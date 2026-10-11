"""Clean-room port of the IVONA gap codec "xform" stage (ELF 0x13dd18).

``xform`` mirrors the engine call ``FUN_0014dd18(ctx, frame_info, samp, n)``:
it consumes the per-frame coefficients in ``ctx`` and produces the time-domain
samples in ``samp`` (with overlap-add), via the 16/8-band inverse transforms
``FUN_0015027c`` / ``FUN_00150028``.

The shared numerical helpers (``f1496c0``, ``f14dc30``, ``f14dca4`` -- plus
``f150a14``/``f14f940`` which they call) live in ``dsp.py``.
"""
from prims import (u32, s32, s16, ld_u16, ld_s32, ld_u32,
                   st_u16, st_u32, memcpy, memmove)
from dsp import f1496c0, f14dc30, f14dca4

__all__ = ['xform']


# --------------------------------------------------------------------------- #
# FUN_00150028  (ELF 0x140028) -- n-band inverse transform (nbands != 16)
# --------------------------------------------------------------------------- #
def _clamp_q16(x):
    """``((x >> 9) + 1) >> 1`` clamped to a signed 16-bit value."""
    v = ((x >> 9) + 1) >> 1
    if v < 0x8000:
        if v < -0x8000:
            v = -0x8000
        return v & 0xFFFF
    return 0x7FFF


def f150028(inp, inoff, coef, coff, state, stoff, outp, ooff, n, nbands):
    if n <= 0:
        return
    iVar4 = nbands - 1
    uVar2 = u32(ld_u32(state, stoff + 4 * iVar4))
    iVar9 = (nbands >> 1) - 1
    local_40 = 0
    while True:
        if iVar9 < 1:
            iVar8 = 0
        else:
            iVar8 = 0
            iVar3 = 0
            while True:
                iVar10 = s16(ld_u16(coef, coff + iVar3 * 4))
                iVar6 = (s32(iVar3 << 0x10) >> 0xF) + 1
                iVar5 = iVar4 - iVar6
                uVar11 = u32(ld_u32(state, stoff + 4 * iVar5))
                iVar7 = s16(ld_u16(coef, coff + iVar3 * 4 + 2))
                iVar3 += 1
                iVar6 = (nbands - 2) - iVar6
                st_u32(state, stoff + 4 * iVar5, uVar2)
                iVar8 = s32(s32(iVar7 * (s32(uVar11) >> 0x10)) +
                            s32((s32(uVar2) >> 0x10) * iVar10) + iVar8 +
                            s32(s32(u32((uVar2 & 0xFFFF) * iVar10)) >> 0x10) +
                            s32(s32(iVar7 * (uVar11 & 0xFFFF)) >> 0x10))
                uVar2 = u32(ld_u32(state, stoff + 4 * iVar6))
                st_u32(state, stoff + 4 * iVar6, uVar11)
                if not (iVar3 < iVar9):
                    break

        iVar3 = s16(ld_u16(coef, coff + iVar4 * 2))
        iVar5 = s16(ld_u16(coef, coff + (nbands - 2) * 2))
        uVar11 = s32(s32(iVar5 * (s32(uVar2) >> 0x10)) +
                     s32((s32(ld_s32(state, stoff)) >> 0x10) * iVar3) +
                     s32(s32(u32((ld_u32(state, stoff) & 0xFFFF) * iVar3)) >> 0x10) +
                     iVar8 +
                     s32(s32(iVar5 * (uVar2 & 0xFFFF)) >> 0x10))
        sIn = s16(ld_u16(inp, inoff + local_40))
        p3 = 0x4000000
        uVar12 = s32(s32(sIn * (s32(p3) >> 0x10)) +
                     s32(s32(u32((sIn & 0xFFFF) * (p3 & 0xFFFF))) >> 0x10))
        iVar8 = s32(uVar11 + uVar12)
        st_u32(state, stoff, uVar2)
        if iVar8 < 0:
            if s32(u32(uVar11) | u32(uVar12)) < 0:
                st_u16(outp, ooff + local_40, _clamp_q16(iVar8))
                uVar2 = _advance_q16(iVar8)
            else:
                st_u16(outp, ooff + local_40, 0x7FFF)
                uVar2 = 0x7FFFFFF0
        else:
            if s32(u32(uVar11) & u32(uVar12)) < 0:
                st_u16(outp, ooff + local_40, 0x8000)
                uVar2 = _advance_q16(-0x80000000)
            else:
                st_u16(outp, ooff + local_40, _clamp_q16(iVar8))
                uVar2 = _advance_q16(iVar8)
        local_40 += 2
        st_u32(state, stoff + 4 * iVar4, uVar2)
        if local_40 == n * 2:
            break


def _advance_q16(iVar8):
    """The shared ``param_4[iVar4]`` value: clamp to +-0x8000000, then <<4."""
    if iVar8 < 0x8000000:
        if iVar8 < -0x8000000:
            iVar8 = -0x8000000
        return u32(iVar8 << 4)
    return 0x7FFFFFF0


# --------------------------------------------------------------------------- #
# FUN_0015027c  (ELF 0x14027c) -- fixed 16-band inverse transform
# --------------------------------------------------------------------------- #
def f15027c(inp, inoff, coef, coff, state, stoff, outp, ooff, n):
    if n < 1:
        return

    def rd(i):
        return u32(ld_u32(state, stoff + 4 * i))

    local_84 = rd(7)
    local_90 = rd(4)
    local_98 = rd(0xB)
    local_9c = rd(0xA)
    local_88 = rd(6)
    local_8c = rd(5)
    uVar16 = rd(0xD)
    uVar17 = rd(9)
    uVar22 = rd(0xF)
    uVar18 = rd(3)
    uVar26 = rd(2)
    uVar30 = rd(0xE)
    local_94 = rd(0xC)
    local_80 = rd(8)
    iVar21 = 0
    while True:
        uVar24 = uVar18
        uVar23 = uVar22
        uVar20 = uVar17
        uVar19 = uVar16
        uVar16 = local_8c
        uVar18 = local_90
        uVar17 = local_9c
        sVar = [s16(ld_u16(coef, coff + 2 * k)) for k in range(16)]
        uVar22 = u32(ld_u32(state, stoff + 4))
        st_u32(state, stoff + 4, uVar26)
        stv = [uVar23, uVar30, uVar19, local_94, local_98, local_9c, uVar20,
               local_80, local_84, local_88, local_8c, local_90, uVar24,
               uVar26, uVar22, rd(0)]

        acc = 0
        low = 0
        for i in range(16):
            c = sVar[i]
            acc = u32(acc + u32(c * (s32(stv[i]) >> 0x10)))
            low = u32(low + u32(s32(u32(c * (stv[i] & 0xFFFF))) >> 0x10))
        uVar29 = s32(acc + low)

        sIn = s16(ld_u16(inp, inoff + iVar21))
        p3 = 0x4000000
        uVar26 = s32(s32(sIn * (s32(p3) >> 0x10)) +
                     s32(s32(u32((sIn & 0xFFFF) * (p3 & 0xFFFF))) >> 0x10))
        iVar25 = s32(uVar29 + uVar26)
        st_u32(state, stoff, uVar22)
        if iVar25 < 0:
            if s32(u32(uVar29) | u32(uVar26)) < 0:
                st_u16(outp, ooff + iVar21, _clamp_q16(iVar25))
                uVar22 = _advance_q16(iVar25)
                st_u32(state, stoff + 0x3C, uVar22)
            else:
                st_u16(outp, ooff + iVar21, 0x7FFF)
                uVar22 = 0x7FFFFFF0
                st_u32(state, stoff + 0x3C, 0x7FFFFFF0)
        else:
            if s32(u32(uVar29) & u32(uVar26)) < 0:
                st_u16(outp, ooff + iVar21, 0x8000)
                uVar22 = _advance_q16(-0x80000000)
            else:
                st_u16(outp, ooff + iVar21, _clamp_q16(iVar25))
                uVar22 = _advance_q16(iVar25)
            st_u32(state, stoff + 0x3C, uVar22)

        if iVar21 + 2 == n * 2:
            st_u32(state, stoff + 2 * 4, uVar24)
            st_u32(state, stoff + 8 * 4, uVar20)
            st_u32(state, stoff + 0xE * 4, uVar23)
            st_u32(state, stoff + 0xD * 4, uVar30)
            st_u32(state, stoff + 0xC * 4, uVar19)
            st_u32(state, stoff + 0xB * 4, local_94)
            st_u32(state, stoff + 0xA * 4, local_98)
            st_u32(state, stoff + 9 * 4, local_9c)
            st_u32(state, stoff + 7 * 4, local_80)
            st_u32(state, stoff + 6 * 4, local_84)
            st_u32(state, stoff + 5 * 4, local_88)
            st_u32(state, stoff + 4 * 4, local_8c)
            st_u32(state, stoff + 3 * 4, local_90)
            return
        iVar21 += 2
        local_8c = local_88
        local_90 = uVar16
        local_88 = local_84
        local_84 = local_80
        local_9c = local_98
        local_98 = local_94
        uVar16 = uVar30
        uVar26 = uVar24
        uVar30 = uVar23
        local_94 = uVar19
        local_80 = uVar20


# --------------------------------------------------------------------------- #
# FUN_0014dd18  (ELF 0x13dd18) -- the "xform" stage
# --------------------------------------------------------------------------- #
def xform(ctx, frame_info, samp, n):
    """``FUN_0014dd18(ctx, frame_info, samp, n)`` -- mutates ``ctx`` and ``samp``."""
    if ld_s32(ctx, 0x2BD8) != ld_s32(ctx, 0x3508):
        f14dca4(ctx)
        st_u32(ctx, 0x3508, ld_u32(ctx, 0x2BD8))

    nbands = ld_s32(ctx, 0x2BE8)
    if ld_s32(ctx, 0x350C) == 0:
        if ld_s32(ctx, 0x2CF4) != 0:
            ctx[0x34C0:0x34C0 + 4 * nbands] = b'\x00' * (4 * nbands)
            return

        # ---- per-band coefficient ramp toward the target spectrum --------- #
        for k in range(nbands) if nbands > 0 else ():
            uVar6 = u32(ld_s32(ctx, 0x2BEC + 4 * k) - ld_s32(ctx, 0x3480 + 4 * k))
            cur = ld_s32(ctx, 0x3480 + 4 * k)
            st_u32(ctx, 0x3480 + 4 * k,
                   s32(s32(s32(uVar6) >> 0x10) * 0x3FDC + cur +
                       (s32(u32((uVar6 & 0xFFFF) * 0x3FDC)) >> 0x10)))

        # ---- pick the 4-tap group with the largest frame_info values ------ #
        uVar10 = ld_u32(frame_info, 0x10) & ~(s32(ld_u32(frame_info, 0x10)) >> 31)
        uVar12 = ld_u32(frame_info, 0x14)
        uVar6 = uVar10
        idx = 1 if s32(uVar10) < s32(uVar12) else 0
        if s32(uVar10) < s32(uVar12):
            uVar6 = uVar12
        if s32(uVar6) < s32(ld_u32(frame_info, 0x18)):
            idx = 2
            uVar6 = ld_u32(frame_info, 0x18)
        if s32(uVar6) < s32(ld_u32(frame_info, 0x1C)):
            idx = 3

        m = ld_s32(ctx, 0x2BE4)
        memmove(ctx, 0x2D00 + 4 * m, ctx, 0x2D00, 12 * m)
        memcpy(ctx, 0x2D00, ctx, 0x1538 + 4 * m * idx, 4 * m)

        # ---- interpolate ctx[0x3500] through the 4 frame_info values ------ #
        for off in (0x10, 0x14, 0x18, 0x1C):
            uVar6 = u32(ld_s32(frame_info, off) - ld_s32(ctx, 0x3500))
            cur = ld_s32(ctx, 0x3500)
            st_u32(ctx, 0x3500,
                   s32(s32(s32(uVar6) >> 0x10) * 0x121A + cur +
                       (s32(u32((uVar6 & 0xFFFF) * 0x121A)) >> 0x10)))

        if ld_s32(ctx, 0x350C) == 0:
            ctx[0x34C0:0x34C0 + 4 * nbands] = b'\x00' * (4 * nbands)
            return
        iVar3 = ld_s32(ctx, 0x3500)
    else:
        iVar3 = ld_s32(ctx, 0x3500)

    # ---- window the running phase and run the inverse transform ----------- #
    buf = bytearray(2 * max(n, 1))
    if n < 0xFF:
        uVar6 = 0xFF
        while True:
            uVar6 = s32(uVar6) >> 1
            if not (n < s32(uVar6)):
                break
        iVar8 = ld_s32(ctx, 0x3504)
        if n < 1:
            st_u32(ctx, 0x3504, iVar8)
            _run_transform(ctx, buf, samp, n, nbands)
            return
    else:
        uVar6 = 0xFF
        iVar8 = ld_s32(ctx, 0x3504)

    p = 0
    while True:
        iVar8 = s32(iVar8 * 0xBB38435 + 0x3619636B)
        uVar12 = ld_u32(ctx, 4 * ((uVar6 & (s32(iVar8) >> 24)) + 0xB40))
        sh = s16(iVar3)
        t = s32(s32(sh * (s32(uVar12) >> 0x10)) +
                s32(((s32(iVar3) >> 0xF) + 1 >> 1) * s32(uVar12)) +
                (s32(u32(sh * (uVar12 & 0xFFFF))) >> 0x10))
        v = ((t >> 9) + 1) >> 1
        if v >= 0x8000:
            v = 0x7FFF
        elif v < -0x8000:
            v = -0x8000
        st_u16(buf, 2 * p, v)
        p += 1
        if p == n:
            break
    st_u32(ctx, 0x3504, iVar8)
    _run_transform(ctx, buf, samp, n, nbands)


def _run_transform(ctx, buf, samp, n, nbands):
    coef = bytearray(2 * nbands + 8)
    f1496c0(coef, 0, ctx, 0x3480, nbands)
    if nbands == 0x10:
        f15027c(buf, 0, coef, 0, ctx, 0x34C0, buf, 0, n)
    else:
        f150028(buf, 0, coef, 0, ctx, 0x34C0, buf, 0, n, nbands)
    for k in range(n) if n > 0 else ():
        v = s16(ld_u16(buf, 2 * k)) + s16(ld_u16(samp, 2 * k))
        if v >= 0x8000:
            v = 0x7FFF
        elif v < -0x8000:
            v = -0x8000
        st_u16(samp, 2 * k, v)


# --------------------------------------------------------------------------- #
# self-test against the recorded golden vectors
# --------------------------------------------------------------------------- #
def _selftest():
    from harness import check

    def call(st, r):
        xform(st['ctx'], st['frame_info'], st['samp'], r['args'][3])

    return check('xform', call, compare=('ctx', 'frame_info', 'samp'))


if __name__ == '__main__':
    _selftest()
