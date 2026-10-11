"""Clean-room port of the IVONA gap codec post-filter stage.

  FUN_0014dafc  post      Ghidra dump 143551-143599  (ELF vaddr 0x13dafc)

Called as ``FUN_0014dafc(samp, ctx[0xaf5], ctx[0xaf4], ctx+0xaf2, samp, n)``:
``param_2`` / ``param_3`` are two pointers (the codec context stores link-time
ELF vaddrs) into the static post-filter coefficient tables selected by the rate
in ``FUN_00148cb0`` -- for rate index 24 they are Ghidra ``DAT_0018d2d8`` /
``DAT_0018d2d4``, i.e. ELF 0x17d2d8 / 0x17d2d4.  ``param_4`` is the 2-int filter
state at ``ctx+0x2bc8``.

The filter runs in place on ``n`` signed 16-bit samples and keeps its 2-word
state across frames.  All arithmetic is 32-bit wrapping with arithmetic shifts.
"""
from prims import ld_s16, ld_u32, st_s16, st_u32, s32, u32, clamp_hi16
from tables import tables

CTX_POSTPTR2 = 0x2bd4        # ctx[0xaf5] -> param_2 (short*  table)
CTX_POSTPTR3 = 0x2bd0        # ctx[0xaf4] -> param_3 (ushort* table)
CTX_POSTSTATE = 0x2bc8       # ctx[0xaf2] -> 2-int filter state


def _neg16(u16val):
    """``(int)((uint)v * -0x10000) >> 0x10`` (32-bit wrapping, arithmetic shift)."""
    return s32(u32(u16val * 0xffff0000)) >> 16


def post(samp, ctx, n, out=None):
    """Apply FUN_0014dafc in place over ``n`` samples of ``samp``.

    ``samp`` is the sample bytearray; ``ctx`` supplies the two table pointers and
    holds the 2-int state.  ``out`` defaults to ``samp`` (in-place)."""
    t = tables()
    p2 = ld_u32(ctx, CTX_POSTPTR2)
    p3 = ld_u32(ctx, CTX_POSTPTR3)
    c0 = ld_s16(t.rd(p2, 2), 0)
    c1 = ld_s16(t.rd(p2 + 2, 2), 0)
    c2 = ld_s16(t.rd(p2 + 4, 2), 0)
    iv1 = _neg16(t.u16(p3))
    iv2 = _neg16(t.u16(p3 + 2))
    out = samp if out is None else out
    i4 = s32(ld_u32(ctx, CTX_POSTSTATE))
    i10 = s32(ld_u32(ctx, CTX_POSTSTATE + 4))
    if n > 0:
        for off in range(0, n * 2, 2):
            x = ld_s16(samp, off)
            u3 = u32(x * c0 + i4)
            i4 = s32(x * c1 + i10)
            i9 = (((s32(u3) >> 0xc) + 1) >> 1) + 1
            hi = s32(u3) >> 0x10
            lo = u3 & 0xffff
            i10 = s32(s32(x * c2) + s32(s32(s32(iv2 * hi) +
                                             (s32(iv2 * lo) >> 0x10)) * 8))
            st_s16(out, off, clamp_hi16(i9))
            i4 = s32(i4 + s32(s32(s32(iv1 * hi) +
                                  (s32(iv1 * lo) >> 0x10)) * 8))
    st_u32(ctx, CTX_POSTSTATE, i4)
    st_u32(ctx, CTX_POSTSTATE + 4, i10)


def _selftest():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness import check

    def call(st, r):
        post(st['samp'], st['ctx'], r['args'][5])

    return check('post', call)


if __name__ == '__main__':
    total, failed = _selftest()
    raise SystemExit(1 if failed else 0)
