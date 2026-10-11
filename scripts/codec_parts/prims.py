"""Shared fixed-width primitives for the clean-room codec port.

The ARM code is little-endian, uses 32-bit wrapping arithmetic, arithmetic right
shifts on signed values and truncating 16-bit stores; every helper here mirrors
that exactly.  Buffers are ``bytearray`` objects addressed by *byte* offset.
"""
import struct


def u32(x):
    return x & 0xFFFFFFFF


def s32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def asr(x, n):
    """Arithmetic shift right of the 32-bit value ``x`` by ``n``."""
    return s32(x) >> (n & 31) if n < 32 else (s32(x) >> 31)


def ld_s8(b, o):
    return struct.unpack_from('<b', b, o)[0]


def ld_u8(b, o):
    return b[o] if isinstance(b, (bytes, bytearray)) else struct.unpack_from('<B', b, o)[0]


def ld_u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def ld_s16(b, o):
    return struct.unpack_from('<h', b, o)[0]


def ld_u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def ld_s32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def st_u16(b, o, v):
    struct.pack_into('<H', b, o, v & 0xFFFF)


def st_s16(b, o, v):
    struct.pack_into('<h', b, o, s16(v))


def st_u32(b, o, v):
    struct.pack_into('<I', b, o, u32(v))


def divsi3(a, b):
    """ARM ``__divsi3``: signed division truncating toward zero; /0 returns 0."""
    a = s32(a)
    b = s32(b)
    if b == 0:
        return 0
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return s32(q)


def memcpy(dst, do, src, so, n):
    dst[do:do + n] = src[so:so + n]


def memmove(dst, do, src, so, n):
    dst[do:do + n] = bytes(src[so:so + n])


def clamp_hi16(v):
    """``iVar = -0x8000; if (-0x8000 < v) iVar = v; out = (v < 0x8000) ? iVar : 0x7fff``."""
    if v < 0x8000:
        return -0x8000 if v <= -0x8000 else v
    return 0x7FFF


def nlz16(v):
    """FUN_00149d84: leading-zero count of a 16-bit value (16 if v == 0)."""
    v = u32(v)
    if v == 0:
        return 0x10
    if (v & 0xff00) == 0:
        if (v & 0xfff0) == 0:
            base = 0x10
        else:
            v = s32(v) >> 4
            base = 0x0C
    elif (v & 0xf000) == 0:
        v = s32(v) >> 8
        base = 0x08
    else:
        v = s32(v) >> 0xc
        base = 4
    if (v & 0x0c) != 0:
        return base - (1 if (v & 8) == 0 else 2)
    if (v & 0x0e) == 0:
        return base + 2
    return base + 1
