"""Clean-room port of the IVONA gap codec "setup" step.

Ported from the Ghidra decompilation of ``libttsivonavoice.so`` (addresses are
Ghidra addresses; ELF vaddr = Ghidra - 0x10000):

  FUN_0014add4  ``setup``        Ghidra dump 142004-142119  (vaddr 0x13add4)
  FUN_00149e34  helper           Ghidra dump 141579-141590  (vaddr 0x139e34)
  FUN_0014a04c  ``setup_audio``  Ghidra dump 141691-142004  (vaddr 0x13a04c)

``FUN_0014add4`` is really a thin prologue; with ``flag == 0`` it tail-branches
to a shared block at vaddr 0x13aab0 which builds the per-frame synthesis state
stored in the codec context.  With ``flag != 0`` it calls ``FUN_0014a04c`` (the
"audio" / first-frame path) and bumps ``ctx[0x350c]``.

Only the standard library is used; all arithmetic is done with explicit 32-bit
masking to reproduce the ARM code exactly (little-endian, 16-bit stores are
truncated, right shifts on signed values are arithmetic).
"""
import struct


# --------------------------------------------------------------------------- #
# 32/16-bit primitive helpers
# --------------------------------------------------------------------------- #
def u32(x):
    return x & 0xFFFFFFFF


def s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def ld_s32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def ld_u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def ld_s16(b, o):
    return struct.unpack_from('<h', b, o)[0]


def ld_u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def st_u32(b, o, v):
    struct.pack_into('<I', b, o, u32(v))


def st_u16(b, o, v):
    struct.pack_into('<H', b, o, v & 0xFFFF)


def divsi3(a, b):
    """ARM ``__divsi3``: signed division truncating toward zero; /0 returns 0."""
    if b == 0:
        return 0
    a = s32(a)
    b = s32(b)
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return s32(q)


def memcpy(dst, do, src, so, n):
    dst[do:do + n] = src[so:so + n]


# --------------------------------------------------------------------------- #
# FUN_00149e34  (Ghidra 141579-141590, vaddr 0x139e34)
# --------------------------------------------------------------------------- #
def _f149e34(ctx):
    st_u32(ctx, 0x3514, s32(ld_s32(ctx, 0x2be0)) >> 1)


# --------------------------------------------------------------------------- #
# FUN_0014add4  (Ghidra 142004-142119, vaddr 0x13add4)   -- the "setup" step
# --------------------------------------------------------------------------- #
def setup(ctx, frame_info, samp, n, flag):
    if ld_s32(ctx, 0x2bd8) != ld_s32(ctx, 0x356c):
        _f149e34(ctx)
        st_u32(ctx, 0x356c, ld_s32(ctx, 0x2bd8))

    if flag != 0:
        setup_audio(ctx, frame_info, samp, n)
        st_u32(ctx, 0x350c, s32(ld_s32(ctx, 0x350c) + 1))
        return

    # ---- tail block at vaddr 0x13aab0 ------------------------------------- #
    st_u32(ctx, 0x3510, ld_s32(frame_info, 0x9c))

    if ld_s32(frame_info, 0x9c) == 0:
        iVar10 = ld_s32(frame_info, 0xc)

        if iVar10 < 1:
            # vaddr 0x13ad78: zero the 5 shorts (10 bytes) at ctx+0x3518
            ctx[0x3518:0x3522] = b'\x00' * 10
            iVar10 = 0x3400
            _scale_shift(ctx, iVar10, 10)
        else:
            step = ld_s32(ctx, 0x2be4)          # 120
            ps = 0x82                            # short* into frame_info
            src = 0x82                           # short* source of memcpy
            off = 0                              # int* (iVar9), byte offset
            iVar7 = 0
            iVar2 = 0
            done = False
            while not done:
                # inner while: keep copying while the backwards group sum grows
                while True:
                    s = (ld_s16(frame_info, ps) + ld_s16(frame_info, ps + 2) +
                         ld_s16(frame_info, ps + 4) + ld_s16(frame_info, ps + 6) +
                         ld_s16(frame_info, ps + 8))
                    if not (iVar2 < s):
                        break
                    memcpy(ctx, 0x3518, frame_info, src, 10)
                    iVar7 += 1
                    st_u32(ctx, 0x3514, s32(ld_s32(frame_info, off + 0xc) << 8))
                    iVar10 = ld_s32(frame_info, 0xc)
                    ps -= 10
                    src -= 10
                    off -= 4
                    iVar2 = s
                    if iVar10 <= s32(step * iVar7):
                        done = True
                        break
                if done:
                    break
                iVar7 += 1
                ps -= 10
                src -= 10
                off -= 4
                if not (s32(step * iVar7) < iVar10):
                    break

            # LAB_0014aba8
            ctx[0x3518:0x3522] = b'\x00' * 10
            st_u16(ctx, 0x351c, iVar2)

            if iVar2 > 0x2ccc:
                if iVar2 > 0x3ccd:
                    if iVar2 < 1:
                        iVar2 = 1
                    iVar10 = s16(divsi3(0xf334000, iVar2))
                    _scale_shift(ctx, iVar10, 14)
            else:
                if iVar2 < 1:
                    iVar2 = 1
                iVar10 = s16(divsi3(0xb33400, iVar2))
                _scale_shift(ctx, iVar10, 10)
    else:
        # vaddr 0x13ad44
        st_u32(ctx, 0x3514, s32(s16(ld_s32(ctx, 0x2bd8)) * 0x1200))
        st_u16(ctx, 0x3520, 0)
        st_u32(ctx, 0x3518, 0)
        st_u32(ctx, 0x351c, 0)

    # ---- LAB_0014ac74 ----------------------------------------------------- #
    memcpy(ctx, 0x3522, frame_info, 0x44, s32(ld_s32(ctx, 0x2be8)) << 1)
    st_u16(ctx, 0x3558, ld_u16(frame_info, 0x8c))
    st_u32(ctx, 0x355c, ld_u32(frame_info, 0x10))
    st_u32(ctx, 0x3560, ld_u32(frame_info, 0x14))
    st_u32(ctx, 0x3564, ld_u32(frame_info, 0x18))
    st_u32(ctx, 0x3568, ld_u32(frame_info, 0x1c))


def _scale_shift(ctx, mult, shift):
    """The two ``(short)(ctx[short] * mult >> shift)`` blocks.

    ``mult`` is the sign-extended (16-bit) divisor result; each of the five
    shorts at ctx+0x3518.. is multiplied (32-bit wrap) and arithmetic-shifted.
    """
    for off in (0x3518, 0x351a, 0x351c, 0x351e, 0x3520):
        v = ld_s16(ctx, off)
        st_u16(ctx, off, s32(v * mult) >> shift)
