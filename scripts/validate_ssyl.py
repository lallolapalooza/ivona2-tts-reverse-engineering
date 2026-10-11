#!/usr/bin/env python3
"""Validate the recovered `ssyl_from` / `ssyl_to` rule against a capture's own
`unit_feature_vectors.tsv`.

Recovered rule (plug-in getters `FUN_00044afc`/`FUN_00044b74` = ELF 0x34afc /
0x34b74, registered as the syllable features `ssyl_to`/`ssyl_from` by
`FUN_00044460` at plug-in dump :18862-18863):

    ssyl_to(syl)   = walk NEXT syllables  (sibling `+8`  in the Syllable relation)
                     counting 1, 2, ... until a syllable with `stress > 0` is
                     found; return that count
    ssyl_from(syl) = same, walking PREVIOUS syllables (`+0xc`)
    if the walk runs off the end of the chain first -> 0

The two getters are identical apart from the sibling slot (`+8` vs `+0xc`), the
string they test is `"stress"` (plug-in ELF 0x626ac, built as `pc + 0x2db0c` /
`pc + 0x2db84`), the sibling accessors are `FUN_00028c14` (= `*(x+8)`) and
`FUN_00028c20` (= `*(x+0xc)`), and the failure value is the global at ELF
0x2f0584 / 0x2f0588 (both 0 in the shipped .so and at runtime).

The capture is grouped by the syllable index slot 0x22 (`syl_in + 1`): every row
of one syllable carries the same `stress` (0x1d), `ssyl_in` (0x24), `ssyl_out`
(0x25) and `ssyl_from`/`ssyl_to` (0x26/0x27).

    python3 scripts/validate_ssyl.py out/oracle/ref_nopunct [...]
"""
from __future__ import annotations

import sys


def syllables(path):
    rows = []
    for ln in open(path):
        if ln.startswith("#"):
            continue
        pre, _, hx = ln.partition("#")
        cols = pre.split()
        rows.append((cols, bytes.fromhex(hx.strip())))
    real = []
    i = 0
    while i < len(rows):
        if i + 1 < len(rows) and rows[i][0][0] == rows[i + 1][0][0]:
            a, b = rows[i], rows[i + 1]
            real.append(b if any(b[1]) else a)
            i += 2
        else:
            real.append(rows[i])
            i += 1
    syls = {}
    order = []
    for cols, b in real:
        if not b[0x22]:                       # 0x22 == 0 -> the `pau` branch
            continue
        idx = b[0x22] - 1
        if idx not in syls:
            syls[idx] = {"phones": [], "stress": b[0x1d], "ssyl_in": b[0x24],
                         "ssyl_out": b[0x25], "ssyl_from": b[0x26],
                         "ssyl_to": b[0x27], "tokens": []}
            order.append(idx)
        s = syls[idx]
        s["phones"].append(cols[3])
        for k in ("stress", "ssyl_in", "ssyl_out", "ssyl_from", "ssyl_to"):
            if s[k] != b[{"stress": 0x1d, "ssyl_in": 0x24, "ssyl_out": 0x25,
                          "ssyl_from": 0x26, "ssyl_to": 0x27}[k]]:
                raise SystemExit(f"inconsistent syllable slot {k} in {path}")
    return [syls[i] for i in sorted(order)]


def rule(syls, k, direction):
    step = direction
    j = k + step
    count = 1
    while 0 <= j < len(syls):
        if syls[j]["stress"] > 0:
            return count
        count += 1
        j += step
    return 0


def check(path):
    syls = syllables(path)
    bad_f = bad_t = 0
    print(f"== {path}: {len(syls)} syllables")
    print(f"{'#':>3} {'phones':22s} {'str':>3} {'fr':>3}({'rule':>4}) "
          f"{'to':>3}({'rule':>4})")
    for k, s in enumerate(syls):
        rf, rt = rule(syls, k, -1), rule(syls, k, +1)
        okf = rf == s["ssyl_from"]
        okt = rt == s["ssyl_to"]
        bad_f += not okf
        bad_t += not okt
        mark = "" if (okf and okt) else "   <-- MISMATCH"
        print(f"{k+1:3d} {' '.join(s['phones']):22s} {s['stress']:3d} "
              f"{s['ssyl_from']:3d}({rf:4d}) {s['ssyl_to']:3d}({rt:4d}){mark}")
    print(f"   ssyl_from {len(syls)-bad_f}/{len(syls)}  "
          f"ssyl_to {len(syls)-bad_t}/{len(syls)}")
    return bad_f + bad_t


def main(argv):
    paths = argv[1:] or ["out/oracle/ref_nopunct/unit_feature_vectors.tsv"]
    bad = 0
    for p in paths:
        bad += check(p)
        print()
    print("ALL OK" if not bad else f"{bad} MISMATCHES")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
