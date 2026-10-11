#!/usr/bin/env python3
"""Diff the prosody join costs of `scripts/prosody.py` against the real plug-in.

`out/libs/kendra/libvoice_en_us_kendra.so` is executed under Unicorn; each of the five
context-specific join-cost functions (`FUN_0003055c` / `FUN_000313d0` / `FUN_00031868` /
`FUN_00031cb0` / `FUN_000320f0`) is called with random 36-byte diphonedb records and a
budget, and the result is compared with the Python model.  Any mismatch prints the
records, the budget, and both values, and the process exits non-zero.

    python3 scripts/probe_prosody.py                 # 300 cases per function
    python3 scripts/probe_prosody.py --n 3000
    python3 scripts/probe_prosody.py --vectors       # print reference vectors only
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "emu"))
sys.path.insert(0, HERE)

from armemu import ArmLib                                  # noqa: E402
import prosody                                             # noqa: E402

SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")
E = lambda gh: gh - 0x10000                                # noqa: E731

JOIN_FNS = [
    ("FUN_0003055c", 0x3055C, prosody.join_cost_r,        "r"),
    ("FUN_000313d0", 0x313D0, prosody.join_cost_dash,     "-"),
    ("FUN_00031868", 0x31868, prosody.join_cost_plus,     "+"),
    ("FUN_00031cb0", 0x31CB0, prosody.join_cost_gl,       "g/l"),
    ("FUN_000320f0", 0x320F0, prosody.join_cost_default,  ""),
]

BUDGETS = [10 ** 9, 300000, 100000, 40000, 5000, 500, 0]


def gen_record(rng, structured):
    """A 36-byte diphonedb record; structured draws cover the ladder regions."""
    b = bytearray(rng.randrange(256) for _ in range(36))
    if structured:
        def u16(off, lo, hi):
            v = rng.randrange(lo, hi + 1)
            b[off], b[off + 1] = v & 0xFF, (v >> 8) & 0xFF
        u16(0, 0, 1000)          # record+0: duration ms
        u16(8, 0, 40)            # class ladder (0,1,2,3..19,20..)
        u16(10, 0, 200)          # duration-ish
        u16(12, 0, 200)          # signed field
        u16(14, 0, 60)
        for o in range(16, 32):
            b[o] = rng.randrange(0, 64)
    return bytes(b)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="cases per function")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--vectors", action="store_true",
                    help="print a deterministic reference vector table and stop")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    lib = ArmLib(SO)

    if a.vectors:
        print("# variant\tbudget\trecord_a(hex)\trecord_b(hex)\tengine\tmodel")
        for name, gh, model, _ctx in JOIN_FNS:
            for i in range(3):
                ra = gen_record(rng, i % 2 == 0)
                rb = gen_record(rng, i % 2 == 1)
                bud = rng.choice(BUDGETS)
                got = lib.call(E(gh), [lib.alloc_data(ra), lib.alloc_data(rb), bud],
                               timeout=0)
                want = model(prosody.Rec(ra), prosody.Rec(rb), bud)
                print(f"{name}\t{bud}\t{ra.hex()}\t{rb.hex()}\t{got}\t{want}")
        return 0

    checks = fails = 0
    # ---- target cost FUN_000309a4 and dispatcher FUN_00031234 -----------------
    t_checks = t_fails = 0
    STR_OFFS = [0x04, 0x08, 0x0c, 0x10, 0x14, 0x28, 0x30, 0x38, 0x40, 0x4c,
                0x54, 0x58, 0x5c]
    BYTE_OFFS = [0x18, 0x19, 0x1a, 0x1d, 0x20, 0x21, 0x22, 0x23, 0x26, 0x27,
                 0x2c, 0x3c, 0x3d, 0x3e, 0x48, 0x49, 0x4a]
    ALPHA = ["x", "r", "content", "pau", "L", "L*", "H", "+", "-", "a", ""]

    def gen_vec():
        raw = bytearray(rng.randrange(256) for _ in range(96))
        struct.pack_into("<f", raw, 0, rng.choice([0.0, 0.5, 1.0, 2.0, 3.0, 0.1]))
        strs = {}
        for off in STR_OFFS:
            t = rng.choice(ALPHA)
            struct.pack_into("<I", raw, off, lib.alloc_str(t))
            strs[off] = t
        for off in BYTE_OFFS:
            raw[off] = rng.choice([0, 1, 2, 3, 4, 5, 7, 9, 255])
        return bytes(raw), strs

    tv = []
    for i in range(max(200, a.n)):
        raw, strs = gen_vec()
        tv.append((raw, strs))
    for i in range(max(100, a.n // 2)):
        (ra, sa), (rb, sb) = rng.choice(tv), rng.choice(tv)
        got = lib.call(E(0x309A4), [lib.alloc_data(ra), lib.alloc_data(rb)], timeout=0)
        want = prosody.target_cost(prosody.Vec96(ra, sa), prosody.Vec96(rb, sb))
        t_checks += 1
        if got != want:
            t_fails += 1
            if t_fails <= 3:
                print(f"MISMATCH FUN_000309a4 eng={got} model={want}\n a={ra.hex()} {sa}"
                      f"\n b={rb.hex()} {sb}")
    print(f"FUN_000309a4: {t_checks - t_fails}/{t_checks} match"
          + ("" if not t_fails else "   <-- FAIL"))
    d_checks = d_fails = 0
    for i in range(max(100, a.n // 2)):
        (ra, sa), (rb, sb), (rc, sc), (rd, sd) = (rng.choice(tv) for _ in range(4))
        got = lib.call(E(0x31234), [lib.alloc_data(ra), lib.alloc_data(rb),
                                    lib.alloc_data(rc), lib.alloc_data(rd)], timeout=0)
        want = prosody.dispatch_cost(prosody.Vec96(ra, sa), prosody.Vec96(rb, sb),
                                     prosody.Vec96(rc, sc), prosody.Vec96(rd, sd))
        d_checks += 1
        if got != want:
            d_fails += 1
            if d_fails <= 3:
                print(f"MISMATCH FUN_00031234 eng={got} model={want}\n a={ra.hex()} {sa}"
                      f"\n b={rb.hex()} {sb}\n c={rc.hex()} {sc}\n d={rd.hex()} {sd}")
    print(f"FUN_00031234: {d_checks - d_fails}/{d_checks} match"
          + ("" if not d_fails else "   <-- FAIL"))
    checks += t_checks + d_checks
    fails += t_fails + d_fails

    for name, gh, model, _ctx in JOIN_FNS:
        addr = E(gh)
        bad = 0
        for i in range(a.n):
            ra = gen_record(rng, i % 2 == 0)
            rb = gen_record(rng, i % 2 == 1)
            bud = rng.choice(BUDGETS)
            got = lib.call(addr, [lib.alloc_data(ra), lib.alloc_data(rb), bud], timeout=0)
            want = model(prosody.Rec(ra), prosody.Rec(rb), bud)
            checks += 1
            if got != want:
                bad += 1
                if bad <= 3:
                    print(f"MISMATCH {name} budget={bud}\n  a={ra.hex()}\n  b={rb.hex()}\n"
                          f"  engine={got:#x} ({got}) model={want:#x} ({want})")
        print(f"{name:12s} context {_ctx!r:5s}: {a.n - bad}/{a.n} match"
              + ("" if not bad else "   <-- FAIL"))
        fails += bad
    print(f"TOTAL {checks - fails}/{checks} bit-identical")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
