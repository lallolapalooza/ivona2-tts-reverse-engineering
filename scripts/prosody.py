#!/usr/bin/env python3
"""Prosody + unit-selection model of the IVONA (Kendra en-US) engine.

Reimplements, from the decompiled ARM code, the parts of the synthesis pipeline that
decide *which unit* is used and *how long / how pitched* it is:

  * the **join cost** between two adjacent diphone records (five context variants,
    `FUN_0003055c` / `FUN_000313d0` / `FUN_00031868` / `FUN_00031cb0` / `FUN_000320f0`
    of ``libvoice_en_us_kendra.so``), selected per pair by the diphone-graph builder
    `FUN_00030214`;
  * the **target cost** dispatcher `FUN_00031234` built on `FUN_000309a4`;
  * the **duration model** (`duration_func` = `FUN_00048400`) backed by the `zdur_cart`
    CART (`FUN_00048110`), giving the per-segment ``end`` feature (cumulative seconds);
  * the **Viterbi** search (`FUN_0005fc04`, engine) with its beam histogram, and the
    pitch/duration transform hooks applied to the chosen unit.

Addresses are Ghidra addresses of ``out/ghidra_dump/libvoice_kendra.c`` (plug-in) and
``out/ghidra_dump/libttsivonavoice.c`` (engine); **ELF vaddr = Ghidra - 0x10000**.

All arithmetic is reproduced bit-exactly: the cost functions are pure and run in IEEE
binary32 (numpy.float32) with ARM soft-float semantics (truncate toward zero on
float->int).  ``scripts/probe_prosody.py`` diffs this module against the real library
running under Unicorn.

Usage:
    python3 scripts/prosody.py --selftest
"""
from __future__ import annotations

import argparse
import struct
import sys

try:
    import numpy as np
except Exception:                                    # pragma: no cover
    np = None

# --------------------------------------------------------------------------- floats
F32 = None


def _f32_init():
    global F32
    if np is not None:
        F32 = np.float32


_f32_init()


def f(x) -> float:
    """Round to binary32 (the ARM single-precision the engine uses)."""
    if F32 is None:
        return struct.unpack("<f", struct.pack("<f", x))[0]
    return float(F32(x))


def f2i(x) -> int:
    """ARM `__aeabi_f2iz`: float -> int, truncate toward zero, saturating."""
    if x != x:
        return 0
    if x >= 2 ** 31:
        return 2 ** 31 - 1
    if x <= -(2 ** 31):
        return -(2 ** 31)
    return int(x)                                  # Python int() truncates toward zero


# --------------------------------------------------------------------------- ladders
def ladder_dur(d):
    """`u16@10` difference penalty (FUN_00031cb0 etc.)."""
    if 2 * d < 5:
        return 0
    return 40 * d - 50


def ladder_ratio(a0, b0, s):
    """`u16@0` duration-ratio penalty.  a0,b0 are seconds (f32), s = a0+b0."""
    if not (s > 0.0):                              # s <= 0 -> divide-by-zero guard
        r = 100
    else:
        num = f(f(f(a0) - f(b0)) * f(50.0))
        r = f2i(f(num / f(s)))               # the division is binary32 too
        if r < 0:
            r = -r
        if r < 9:
            r = 3 * r - 10 if r > 5 else r     # 6..8 -> 8/11/14 ; 0..5 unchanged
        else:
            r = 5 * r - 32
    return r


#: `&DAT_000f4240` -- the "incompatible class" penalty (LAB_...; it is *added to the
#: running cost*, not an early return -- verified: e.g. FUN_00031868 returns 2e6, not 1e6).
REJECT = 0xF4240


def ladder4(a, j):
    """`u16@8` class/position field.  Returns the p4 term (1e6 for the reject classes).

    a, j are sign-extended 16-bit (`iVar1 = (x<<16)>>16`).  Flow copied from the
    labels in FUN_00031868 / `FUN_000320f0` (LAB_00031c4c / LAB_00031c88 / LAB_00031c44 /
    LAB_00031970 / LAB_0003197c).
    """
    if a >= 0x14:                                   # BR2, a >= 20
        if j <= 2:
            return REJECT
        base = 200 if j < 1 else 0
    elif a >= 3:                                    # BR2, 3..19 -> LAB_c88/LAB_c44
        base = 200 if j < 1 else 0
    else:                                           # BR1, a < 3
        if j > 0x13:
            return REJECT
        if a == 1:                                  # LAB_c88 falls through to LAB_c4c
            return abs(a - j) // 5
        if a <= 0:                                  # a == 0 (or negative): j>=2 -> 200
            base = 200 if j >= 2 else 0
        else:                                       # a == 2 -> LAB_c44
            base = 200 if j < 1 else 0
    return abs(a - j) // 5 + base


def ladder6(d):
    """`i16@12` (signed) difference penalty."""
    if d < 10:
        return 0
    if d < 0x10:
        return d // 3
    if d > 0x17:
        return d * 2 if d < 0x30 else d * 4
    return d                                        # 16..23 pass through unchanged


def ladder7(d):
    """`u16@14` difference penalty."""
    x = 2 * d
    if x < 4:
        return 6 * d - 3 if x > 1 else 0
    if x < 0x10:
        return 20 * d - 9
    return 40 * d


# ------------------------------------------------------------------- record access
class Rec:
    """A 36-byte diphonedb record as read by the cost functions."""

    __slots__ = ("b",)

    def __init__(self, buf: bytes):
        self.b = buf

    def u16(self, off):
        return self.b[off] | (self.b[off + 1] << 8)

    def s16(self, off):
        v = self.u16(off)
        return v - 0x10000 if v & 0x8000 else v

    def u8(self, off):
        return self.b[off]

    def sgn16(self, off):
        """`(x<<16)>>16` of the u16 field (sign-extend)."""
        v = self.u16(off)
        return v - 0x10000 if v & 0x8000 else v


def _spectral(a: Rec, b: Rec) -> int:
    """Shared 16-byte spectral distance.

    Groups of 3/3/3/7 bytes with weights 1/0.75/0.5/0.25; each weighted group is added
    in float32 and **truncated back to int** between groups (the
    `FUN_0006449c; FUN_00064b30; FUN_0006462c` ghost pattern in all five functions).
    """
    def g(offs):
        return sum(abs(a.u8(o) - b.u8(o)) for o in offs)

    acc = g((16, 17, 18))
    acc = f2i(f(f(acc) + f(f(g((19, 20, 21))) * f(0.75))))
    acc = f2i(f(f(acc) + f(f(g((22, 23, 24))) * f(0.5))))
    acc = f2i(f(f(acc) + f(f(g((25, 26, 27, 28, 29, 30, 31))) * f(0.25))))
    return acc


def _spectral_tail(a: Rec, b: Rec) -> int:
    """`uVar11 = trunc(1.5 * spectral)`, before the per-variant >threshold rescale."""
    return f2i(f(f(1.5) * f(_spectral(a, b))))


# --------------------------------------------------------------- join-cost variants
def join_cost_r(a: Rec, b: Rec, ctx: int):
    """FUN_0003055c -- context "r".  Scale 9.6; p7 halved; no `u16@10` term."""
    a0 = f(a.u16(0)); b0 = f(b.u16(0))
    ratio = ladder_ratio(f(f(a0) / f(1000.0)), f(f(b0) / f(1000.0)),
                         f(f(f(a0) / f(1000.0)) + f(f(b0) / f(1000.0))))
    p4 = ladder4(a.sgn16(8), b.sgn16(8))
    p6 = ladder6(abs(a.s16(12) - b.s16(12)))
    p7 = ladder7(abs(a.u16(14) - b.u16(14)))
    base = p4 + (p7 >> 1) + p6 + ratio
    if not (f(f(9.6) * f(base)) < f(ctx)):
        return REJECT
    tail = _spectral_tail(a, b)
    if tail > 0x3C:
        tail = tail * 3 - 0x78
    return f2i(f(f(9.6) * f(base + tail)))


def join_cost_dash(a: Rec, b: Rec, ctx: int):
    """FUN_000313d0 -- context "-".

    Float accumulator `p6 + 0.6*ratio + 0.05*p_dur + p4`, then **truncated to int**
    (`FUN_0006449c; FUN_00064b30; FUN_0006462c`) before the final 0.8 scale.
    """
    p6 = ladder6(abs(a.s16(12) - b.s16(12)))
    acc = f(p6)
    a0 = f(a.u16(0)); b0 = f(b.u16(0))
    ratio = ladder_ratio(f(f(a0) / f(1000.0)), f(f(b0) / f(1000.0)),
                         f(f(f(a0) / f(1000.0)) + f(f(b0) / f(1000.0))))
    acc = f(acc + f(f(ratio) * f(0.6)))
    acc = f(acc + f(f(ladder_dur(abs(a.u16(10) - b.u16(10)))) * f(0.05)))
    p4 = ladder4(a.sgn16(8), b.sgn16(8))
    acc = f(acc + f(p4))
    acc = float(f2i(acc))                       # the intermediate f2i/i2f round-trip
    if not (f(f(0.8) * acc) < f(ctx)):
        return REJECT
    tail = _spectral_tail(a, b)
    if tail > 0x5A:
        tail = tail * 5 - 0x168
    acc2 = f(acc + f(f(tail) * f(0.3)))
    return f2i(f(float(f2i(acc2)) * f(0.8)))


def _join_int(a: Rec, b: Rec, k_early: int):
    """Shared body of the +/g/-l/default variants (31868, 31cb0, 320f0)."""
    p_dur = ladder_dur(abs(a.u16(10) - b.u16(10)))
    a0 = f(a.u16(0)); b0 = f(b.u16(0))
    ratio = ladder_ratio(f(f(a0) / f(1000.0)), f(f(b0) / f(1000.0)),
                         f(f(f(a0) / f(1000.0)) + f(f(b0) / f(1000.0))))
    p6 = ladder6(abs(a.s16(12) - b.s16(12)))
    p7 = ladder7(abs(a.u16(14) - b.u16(14)))
    p4 = ladder4(a.sgn16(8), b.sgn16(8))
    base = p4 + p7 + p6 + ratio + p_dur
    return base, base * k_early


def join_cost_plus(a: Rec, b: Rec, ctx: int):
    """FUN_00031868 -- context "+".  Early exit 2*base; return 2*(base+tail)."""
    base, early = _join_int(a, b, 2)
    if not ((early & 0xFFFFFFFF) < (ctx & 0xFFFFFFFF)):
        return REJECT
    tail = _spectral_tail(a, b)
    if tail > 0x23:
        tail = tail * 10 - 0x13B
    return 2 * (base + tail)


def join_cost_gl(a: Rec, b: Rec, ctx: int):
    """FUN_00031cb0 -- context "g"/"l".  Early exit 4*base; return 4*(base+tail)."""
    base, early = _join_int(a, b, 4)
    if not ((early & 0xFFFFFFFF) < (ctx & 0xFFFFFFFF)):
        return REJECT
    tail = _spectral_tail(a, b)
    if tail > 0x28:
        tail = tail * 7 - 0xF0
    return 4 * (base + tail)


def join_cost_default(a: Rec, b: Rec, ctx: int):
    """FUN_000320f0 -- default context.  Early exit 0.8*base; return 0.8*(base+tail)."""
    base, _ = _join_int(a, b, 2)
    if not (f(f(0.8) * f(base)) < f(ctx)):
        return REJECT
    tail = _spectral_tail(a, b)
    if tail > 0x28:
        tail = tail * 5 - 0xA0
    return f2i(f(f(0.8) * f(base + tail)))


JOIN_COSTS = {
    "r": join_cost_r,
    "+": join_cost_plus,
    "g": join_cost_gl,
    "l": join_cost_gl,
    "-": join_cost_dash,
    "": join_cost_default,
}

# context char -> variant, matching FUN_00030214's dispatch order
def pick_join_cost(ctx_plus, ctx_minus, ctx_bc, ctx_6c, ctx_b4, ctx_b8):
    """FUN_00030214's selection.  Arguments are the decoded context strings.

    ``ctx_bc`` = *(char**)(param_2+0xbc) (phoneme class of the right edge), etc.
    """
    if ctx_bc == "r":
        return join_cost_r
    if ctx_b4 == "+":
        return join_cost_plus
    if ctx_bc == "g" or ctx_6c == "l":
        return join_cost_gl
    if ctx_b8 == "-":
        return join_cost_dash
    return join_cost_default


# --------------------------------------------------------------------------- selftest
def _selftest():
    import random
    rng = random.Random(1234)
    for name, fn in (("default", join_cost_default), ("plus", join_cost_plus),
                     ("gl", join_cost_gl), ("r", join_cost_r), ("dash", join_cost_dash)):
        outs = []
        for _ in range(5):
            ra = Rec(bytes(rng.randrange(256) for _ in range(36)))
            rb = Rec(bytes(rng.randrange(256) for _ in range(36)))
            outs.append(fn(ra, rb, 300000))
        print(f"{name:8s} {outs}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
    return 0




# =========================================================================== duration
# `duration_func` (FUN_00048400, plugin) walks the `Segment` chain and writes each
# segment's cumulative end time (seconds) into the item feature "end"; the CART
# `zdur_cart` (FUN_00048110) predicts the segment's own duration in ms.
#
# zdur_cart blob (plugin .so): PTR_DAT_002f4024 -> {phone_tbl, name_tbl, node_tbl};
# name table stride 0x40, phone table 6-byte records, node table 4-byte question cells.
# The per-phone record is {u8 nameIdx, u8 reserved, i16 mean_ms, i16 std_ms}.
#
# Leaf value:  ((leaf16 * std + round) / 1000) + mean      (round = ±500 by sign)

CART_NAMES_STRIDE = 0x40


class Cart:
    """The `zdur_cart` decision tree (FUN_00048110)."""

    def __init__(self, name_blob: bytes, phone_blob: bytes, node_blob: bytes):
        self.name_blob = name_blob
        self.phone_blob = phone_blob
        self.node_blob = node_blob
        self.names = [name_blob[i * CART_NAMES_STRIDE:(i + 1) * CART_NAMES_STRIDE]
                      .split(b"\x00")[0].decode("latin1")
                      for i in range(len(name_blob) // CART_NAMES_STRIDE)]
        self.phones = []           # (nameIdx, name, mean, std)
        a = 0
        while a + 6 <= len(phone_blob):
            if phone_blob[a] == 0xFF:
                break
            ni = phone_blob[a]
            mean = struct.unpack_from("<h", phone_blob, a + 2)[0]
            std = struct.unpack_from("<h", phone_blob, a + 4)[0]
            self.phones.append((ni, self.names[ni], mean, std))
            a += 6

    # -- static loaders ---------------------------------------------------------
    @classmethod
    def from_so(cls, so_path):
        """Extract the blob from the plugin `.so` (PTR_DAT_002f4024)."""
        from elftools.elf.elffile import ELFFile
        raw = open(so_path, "rb").read()
        elf = ELFFile(open(so_path, "rb"))

        def read_vaddr(v, n):
            for seg in elf.iter_segments():
                if seg["p_type"] != "PT_LOAD":
                    continue
                va, fsz = seg["p_vaddr"], seg["p_filesz"]
                if va <= v < va + fsz:
                    off = seg["p_offset"] + (v - va)
                    return raw[off:off + n]
            raise KeyError(v)
        ptr_addr = 0x2E4024                       # PTR_DAT_002f4024 (Ghidra 0x2f4024)
        phone, name, node = struct.unpack("<III", read_vaddr(ptr_addr, 12))
        return cls(read_vaddr(name, 0x40 * 420), read_vaddr(phone, 6 * 64),
                   read_vaddr(node, 0x10000))

    # -- evaluation -------------------------------------------------------------
    def _name(self, i):
        return self.names[i]

    def question(self, q, rhs_idx, feat):
        """One CART test.  `feat(path)` returns (tag, value): tag 1 = int, 5 = str.

        Equality questions compare either numerically or as strings depending on
        the *right-hand* side: the tree's RHS entries come from the name table
        and are literal integers or literal strings (`report_prosody.md` sec.3.2
        lists the value domains: `position_type` = single/initial/mid/final,
        `gpos` = content/cc/wp/..., `syl_break` = 0/1/3/4, ...).
        """
        entry = self._name(q)
        op, path = entry[0], entry[1:]
        rhs = self._name(rhs_idx)
        tag, val = feat(path)
        try:
            r = int(rhs)
            numeric = True
        except ValueError:
            numeric = False
        if numeric:
            if op == "<":
                return int(val) < r
            if op == ">":
                return int(val) > r
            try:
                return int(val) == r
            except (TypeError, ValueError):
                return False
        if op == "<":
            return str(val) < rhs
        if op == ">":
            return str(val) > rhs
        return str(val) == rhs

    def predict(self, name, feat):
        """`FUN_00048110`: ms duration for the segment `name` under features `feat`."""
        ph = next((p for p in self.phones if p[1] == name), self.phones[0])
        _, _, mean, std = ph
        node = 0
        nb = self.node_blob
        while True:
            p = node * 4
            while True:
                q = nb[p]
                if q == 0xFF:
                    leaf = struct.unpack_from("<h", nb, p + 2)[0]
                    rnd = 500 if leaf > 0 else -500
                    # C integer division truncates toward zero (Ghidra
                    # `(leaf*std + rnd) / 1000 + mean`), so a negative leaf must
                    # not be floored here.
                    num = leaf * std + rnd
                    qv = -((-num) // 1000) if num < 0 else num // 1000
                    v = qv + mean
                    v &= 0xFFFF
                    return v - 0x10000 if v & 0x8000 else v
                if not self.question(q, nb[p + 1], feat):
                    node = struct.unpack_from("<H", nb, p + 2)[0]
                    break
                p += 4


# ---- duration_func (FUN_00048400) pause / break rules ------------------------
# Defaults from the binary: pause_base_len = 0.35f (0x3eb33333).
PAUSE_BASE_LEN = 0.35
PAUSE_BREAK_DELTA = 0.05          # +0.05 for a "BB" phrase (sentence)
PAUSE_NEXT_DELTA = 0.10           # +0.10 more when a following segment exists
PAUSE_OTHER = 0.2                 # 0x3e4ccccd
PAUSE_LAST = 0.01                 # 0x3c23d70a (pause with no following segment)


def pause_duration(prev_phrase_name, has_prev, has_next, base=None):
    """`end` increment for a `pau` segment (`FUN_00048400`).

    Transcribed from the decompilation (plug-in `:20386-20408`): `prev = item.prev`;
    `prev == NULL` -> 0.01; else the name reached from `prev` through
    `R:SylStructure.parent.parent.R:Phrase.parent.name`; `"BB"` -> `pause_base_len +
    0.05` (f32 add), `+ 0.10` when `item.next != NULL`; anything else -> 0.20.

    `base` is the voice's `pause_base_len` parameter (engine default 0.35, but the
    shipped Kendra/Amy voices set **0**, so their sentence-final pause is 0.05 s).
    """
    if base is None:
        base = PAUSE_BASE_LEN
    if not has_prev:
        return PAUSE_LAST
    if prev_phrase_name == "BB":
        v = f(f(base) + PAUSE_BREAK_DELTA)
        if has_next:
            v = f(v + PAUSE_NEXT_DELTA)
        return v
    return PAUSE_OTHER


def duration_chain(cart, segments):
    """Reproduce FUN_00048400: cumulative `end` (seconds) per segment.

    `segments` = list of dicts with keys:
      name, prev_phrase (phrase name seen from the previous segment), has_prev (bool),
      has_next (bool), feat(path) -> (tag, value)   (the item feature getter)
    Returns the list of cumulative end times.
    """
    end = 0.0
    out = []
    for s in segments:
        if s["name"] == "pau":
            d = pause_duration(s.get("prev_phrase"), s.get("has_prev", False),
                               s.get("has_next", False))
        else:
            d = cart.predict(s["name"], s["feat"]) / 1000.0
        end = f(f(end) + f(d))
        out.append(end)
    return out


# =========================================================================== target cost
# `FUN_000309a4` (plug-in :8129, ~380 lines): compares a 96-byte candidate record with a
# 96-byte context vector and returns `trunc(0.4 * cost)`.  `FUN_00031234` (:8511) is the
# engine-visible entry: `FUN_000309a4(rec_l, ctx_l) + FUN_000309a4(rec_r, ctx_r)` plus
# boundary penalties.  Slot semantics: see report_prosody.md §2 / report_cost_terms_main.md §4c.

class Vec96:
    """A 96-byte feature vector.  `strs` maps word offsets (4,8,0xc,…) to their text."""

    __slots__ = ("b", "strs")

    def __init__(self, raw: bytes, strs=None):
        self.b = raw
        self.strs = strs or {}

    def u8(self, off):
        return self.b[off]

    def f32_0(self):
        return struct.unpack_from("<f", self.b, 0)[0]

    def st(self, off):
        return self.strs.get(off, "")

    def ch(self, off):
        t = self.strs.get(off, "")
        return t[0] if t else "\0"


def target_cost(a: Vec96, b: Vec96) -> int:
    """`FUN_000309a4`: candidate record `a` vs desired context `b`.  Returns an int."""
    A, B = a.u8, b.u8
    # --- front string schedule -------------------------------------------------
    if a.st(0x04) == b.st(0x04):
        iv7, iv21 = 7, 0
    else:
        iv7, iv21 = 10, 3
    if a.st(0x08) != b.st(0x08):
        iv21 = iv7
    iv7 = 0 if a.st(0x10) == b.st(0x10) else 7
    iv8 = 0 if a.st(0x14) == b.st(0x14) else 3
    iv8 = iv7 + iv21 + iv8
    if b.st(0x0c) == "r":
        iv8 *= 3
    c24 = b.ch(0x54)                                   # ph_vc of the *context* (param_2)
    if b.st(0x08) == "r" or b.st(0x10) == "r":
        iv7 = iv8 * 6 if c24 == "+" else iv8 * 3
    else:
        iv7 = iv8
    cVar3, cVar4 = B(0x1d), A(0x1d)
    cost = (3 * abs(A(0x19) - B(0x19)) + 3 * abs(A(0x18) - B(0x18))
            + 3 * abs(A(0x1a) - B(0x1a)) + iv7)
    if cVar3 != cVar4:
        cost += 5
    if c24 == "+" and cVar3 != cVar4:
        cost += 1000
    cost += 2 * (abs(A(0x21) - B(0x21)) + abs(A(0x20) - B(0x20)))
    # --- 0x22/0x23 tri-state ladder (labels LAB_00030b48 / LAB_0003109c / LAB_000310b0) --
    a22, b22, a23, b23 = A(0x22), B(0x22), A(0x23), B(0x23)
    if a22 == 1:
        path_add2 = (b22 > 1)
    else:
        path_add2 = not (a22 < 2 or b22 != 1)
    c26 = a23
    if path_add2:
        cost += 2
    if c26 == 1:
        if b23 > 1:
            cost += 10
    elif c26 != 0 and b23 == 1:
        cost += 3
    # --- scalar byte equalities ------------------------------------------------
    if A(0x26) != B(0x26):
        cost += 1
    if A(0x27) != B(0x27):
        cost += 1
    cost += 3 * abs(A(0x2c) - B(0x2c))
    if a.st(0x28) != b.st(0x28):
        cost += 3
    bVar5, bVar6 = A(0x3d), A(0x3e)
    b23_3e = B(0x3e)
    if A(0x3c) != B(0x3c):
        cost += 1
    if bVar5 == 1:
        if B(0x3d) > 1:
            cost += 2
    elif bVar5 > 1 and B(0x3d) == 1:
        cost += 1
    if bVar6 == 1:
        if b23_3e > 1:
            cost += 2
    elif bVar6 >= 2 and b23_3e == 1:
        cost += 1
    if A(0x44) != B(0x44):          # `param_1 + 0x11` (word index -> byte 0x44)
        cost += 1
    # --- "content" role ladder ------------------------------------------------
    pc22 = a.st(0x38)
    if pc22 == "content":
        local_34 = b.st(0x38)
        local_2c = 0 if local_34 == "content" else 1
        if local_2c != 0:
            cost += 0x32
    else:
        local_34 = b.st(0x38)
        local_2c = 0 if local_34 == "content" else 1
        if local_2c == 0:
            cost += 0x4B
    if a.st(0x30) == "content":
        if b.st(0x30) != "content":
            cost += 3
    elif b.st(0x30) == "content":
        cost += 3
    if a.st(0x40) == "content":
        if b.st(0x40) != "content":
            cost += 3
    elif b.st(0x40) == "content":
        cost += 3
    if local_2c != 0 and local_34 != pc22:
        cost += 10
    if A(0x48) != B(0x48):          # `param_1 + 0x12` (word index -> byte 0x48)
        cost += 1
    # --- 0x49/0x4a ladder ------------------------------------------------------
    a49, b49, a4a, b4a = A(0x49), B(0x49), A(0x4a), B(0x4a)
    if a49 == 1:
        path_add2b = (b49 > 1)
    else:
        path_add2b = not (a49 < 2 or b49 != 1)
    c18 = a4a
    if path_add2b:
        cost += 1
    if c18 == 1:
        if b4a >= 2:
            cost += 1
    elif c18 != 0 and b4a == 1:
        cost += 1
    # --- tail (`bVar23 == 1`) --------------------------------------------------
    if b23_3e == 1:
        iv7 = 0 if a.st(0x4c) == b.st(0x4c) else 10
        if b.st(0x4c) == "L*" and a.st(0x4c) == "L":
            iv7 = 0
        elif b.st(0x4c) == "L" and a.st(0x4c) == "L*":
            iv7 = 8
        iv8 = 0 if bVar6 == 1 else 4
        if B(0x23) == 1:
            if c26 == 1:
                iv14, iv9 = 0, 0
            else:
                iv14, iv9 = 0x5DC, 100
            if c24 == "+" or b.ch(0x58) != "-":
                cost += iv7 * 0xFA + iv14
            else:
                cost += iv7 * 0x14 + iv9
        elif cVar3 != 0:
            if bVar6 < 2 and cVar3 == cVar4:
                iv13, iv9, iv14 = 0, 0, 0
            else:
                iv13, iv9, iv14 = 0xFA, 0x96, 100
            if c24 == "+":
                cost += iv7 * 0x19 + iv13
            elif b.ch(0x58) == "-":
                cost += iv7 * 10 + iv14
            else:
                cost += iv7 * 0xF + iv9
        if B(0x19) == 1:
            cost += iv7 * 0x14 if b.ch(0x58) == "-" else iv7 * 0x28
        cost += iv8 + iv7
    # --- hard "H" penalty (endtone) -------------------------------------------
    if (bVar6 == 1 or bVar5 == 1) and B(0x23) > 1 and B(0x22) > 1 and a.st(0x4c) == "H":
        cost += 1000
    # --- pause-guard float branch (skipped for "pau") --------------------------
    if a.st(0x0c) != "pau":
        a0, b0 = f(a.f32_0()), f(b.f32_0())
        s = f(a0 + b0)
        r = abs(f(f(a0 - b0) / s)) if s != 0 else float("nan")
        if a0 >= b0:                                   # branch 1: 150-family
            t = f(r * 150.0)
            cost += f2i(t)
            if r > 0.15:
                cost += f2i(f(t - 22.5))
            if r > 0.35:
                cost += f2i(f(f(r * 360.0) - 126.0))
        elif a0 < b0:                                  # branch 2: 250-family
            cost += f2i(f(r * 250.0))
            if r > 0.2:
                cost += f2i(f(f(r * 120.0) - 24.0))
            if r > 0.3:
                cost += f2i(f(f(r * 150.0) - 45.0))
            if r > 0.4:
                cost += f2i(f(f(r * 300.0) - 120.0))
    return f2i(f(f(cost) * 0.4))


def dispatch_cost(a: Vec96, b: Vec96, c: Vec96, d: Vec96) -> int:
    """`FUN_00031234`: engine-visible candidate cost = target(rec_l,ctx_l)+target(rec_r,ctx_r)
    plus syllable/word-boundary bonuses (plug-in :8511)."""
    cost = target_cost(a, c) + target_cost(b, d)
    A, B, C, D = a.u8, b.u8, c.u8, d.u8
    if A(0x19) == 1 and A(0x21) == 1 and B(0x18) == 1 and B(0x20) == 1:
        if not (C(0x19) == 1 and C(0x21) == 1 and D(0x18) == 1 and D(0x20) == 1):
            cost += 500 if d.ch(0x54) == "+" else 0x15E
    elif C(0x19) == 1 and C(0x21) == 1 and D(0x18) == 1 and D(0x20) == 1:
        cost += 5
    if A(0x18) == 1 and A(0x20) == 1:
        b1, b2 = True, False
    else:
        b1, b2 = False, True
    if C(0x18) == 1 and C(0x20) == 1:
        b1 = b2
    if b1:
        cost += 10 if c.ch(0x54) == "+" else 5
    if B(0x19) == 1 and B(0x21) == 1:
        b1, b2 = True, False
    else:
        b1, b2 = False, True
    if D(0x19) == 1 and D(0x21) == 1:
        b1 = b2
    if b1:
        cost += 5
    return cost


if __name__ == "__main__":
    sys.exit(main())
