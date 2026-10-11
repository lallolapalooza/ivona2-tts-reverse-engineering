#!/usr/bin/env python3
"""Parse a capture's `unit_feature_vectors.tsv` (the engine's 96-byte vectors as
written by `FUN_00060ed4`) into a readable per-phone table.

Usage:  analyze_feature_vectors.py out/oracle/ref_nopunct [--raw]

The tsv has one row per `FUN_00060ed4(item, out)` call; every real call is
preceded by an all-zero call for the same item pointer (the harness logs the
buffer before the writer ran), so rows are taken in pairs.

Slot names are those of `FUN_00060ed4` (engine dump :43702, see
`report_cost_terms_main.md` S4c).  The tsv's own decoded columns are
[0x04 p.p.name, 0x08 p.name, 0x0c name, 0x10 n.name, 0x14 n.n.name,
 0x38 word gpos, 0x4c endtone] (the header's 3rd label is a typo: 0x0c is the
item's own name -- `DAT_00155d00` == "name").
"""
from __future__ import annotations

import sys

SLOTS = [
    (0x00, "dur_float"), (0x04, "p.p.name"), (0x08, "p.name"), (0x0c, "name"),
    (0x10, "n.name"), (0x14, "n.n.name"), (0x18, "pos_in_syl+1"),
    (0x19, "rev_in_syl"), (0x1a, "p.stress"), (0x1b, "p.gsp"), (0x1c, "p.syl_nph"),
    (0x1d, "stress"), (0x1e, "gsp"), (0x1f, "syl_nph"), (0x20, "pos_in_word+1"),
    (0x21, "rev_in_word"), (0x22, "syl_in+1"), (0x23, "syl_out+1"),
    (0x24, "ssyl_in"), (0x25, "ssyl_out"), (0x26, "ssyl_from"), (0x27, "ssyl_to"),
    (0x28, "syl_vowel"), (0x2c, "n.stress"), (0x2d, "n.gsp"), (0x2e, "n.syl_nph"),
    (0x30, "p.gpos"), (0x34, "p.word_nsyl"), (0x38, "gpos"), (0x3c, "word_nsyl"),
    (0x3d, "phr_syls1"), (0x3e, "phr_syls2"), (0x40, "n.gpos"), (0x44, "n.word_nsyl"),
    (0x45, "p.phr_nsyl"), (0x46, "p.phr_nword"), (0x47, "phr_nsyl"), (0x48, "phr_nword"),
    (0x49, "pos_in_utt+1"), (0x4a, "rev_in_utt"), (0x4c, "endtone"),
    (0x50, "n.phr_nsyl"), (0x51, "n.phr_nword"), (0x54, "ph_vc"), (0x58, "ph_cvox"),
    (0x5c, "ph_ctype"),
]


def parse(path):
    rows = []
    for ln in open(path):
        if ln.startswith("#"):
            continue
        pre, _, hx = ln.partition("#")
        cols = pre.split()
        rows.append((cols, bytes.fromhex(hx.strip())))
    # keep the non-zero member of each consecutive pair (same item pointer)
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
    return real


def main(argv):
    d = argv[1]
    raw = "--raw" in argv
    real = parse(f"{d}/unit_feature_vectors.tsv")
    hdr = (f"{'phone':6s} {'stress':>6s} {'syl_in':>6s} {'syl_out':>7s} {'ssyl_in':>7s} "
           f"{'ssyl_out':>8s} {'ssyl_fr':>7s} {'ssyl_to':>7s} {'gpos':8s} {'endtone':8s}")
    print(hdr)
    for cols, b in real:
        g = lambda o: b[o]
        # tsv columns: 0 item, 1 p.p.name, 2 p.name, 3 name, 4 n.name, 5 n.n.name,
        #              6 gpos(str), 7 endtone
        print(f"{cols[3]:6s} {g(0x1d):6d} {g(0x22):6d} {g(0x23):7d} {g(0x24):7d} "
              f"{g(0x25):8d} {g(0x26):7d} {g(0x27):7d} {cols[6]:8s} {cols[7]:8s}")
        if raw:
            print("      ", " ".join(f"{o:#04x}={b[o]:#04x}" for o, _ in SLOTS))


if __name__ == "__main__":
    main(sys.argv)
