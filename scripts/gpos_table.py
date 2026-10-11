#!/usr/bin/env python3
"""The plug-in's `gpos` word table — the engine's closed-class POS dictionary.

`FUN_00060ed4` (engine dump :43702) writes three `gpos` string slots into every
96-byte context vector — 0x30 `p.gpos`, 0x38 the word's own `gpos`, 0x40
`n.gpos` — and `FUN_000309a4` compares them against the literals `content` /
`aux` / `det` / `in` / `cc` / `wp` / `md` / `to` / `pps` / `pps$`
(plug-in dump :8302-8340).  The values themselves come from a table in the
plug-in's `.rodata`:

  * `0x2ebb04`, stride 8: an array of string VALs `{u32 meta = 0xffff0005,
    u32 char* string}`, terminated by `meta == 0` at `0x2ebb00`;
  * `0x2eb860`, stride 4: an array of pointers to those VALs' **meta** word
    (so `*(p+4)` is the string), grouped into runs separated by `0x00000000`.

Each run is one tag: its **first** element is the tag string itself, the rest
are the words carrying that tag (`in` and `to` are words as well as tags, so
their tag entry doubles as the member).  Everything not listed is `content`
(which the plug-in also holds as a plain string at ELF 0x60be0).

Tag inventory (plug-in ELF 0x2eb860 group order):

    in     about across afore after against among amongst as at atop before
           beside besides between by down for from in into of on onto over per
           than that through thru under until unto up via while with without
    to     to
    det    a all an another any both each either every many neither no some the
           these this those yon
    md     'd 'll can can't cannot could couldn't may mayn't might mightn't must
           mustn't ought oughtn't shall shan't should shouldn't will won't would
           wouldn't wouldst
    cc     and because but if nor or plus yet
    wp     how what when whence where whereby wherein which whither who whom
           whose why
    pps    he hers herself him himself i it itself me mine myself oneself ours
           ourselves she theirs them themselves they thine thou us we ye yerself
           you yours yourself yourselves
    pps$   her his its my our their thy your
    aux    'm 're 've am are be had has have is was were

Cross-references that prove this is the table the engine uses: the same tag
strings are tested by the plug-in's own rules (`FUN_00032b70` tests `wp`/`cc`
on `daughter.gpos`, `_FINI_1` tests `in`/`md`/`on`/`into`/`with`/`up`/`down`
when choosing a heteronym's lexicon entry) and the observed engine values in the
captures are exactly these strings (`this`→`det`, `is`→`aux`, `a`→`det`;
`scripts/validate_gpos.py` reports 73/73 segments over the three `ref_*`
captures).  The lookup is case-folded: in `out/oracle/gpos_case/`
(`"That can go to the market"`) the engine tags `That` as `in` — `that`'s tag.

The tagger *stage* is never run (`pos_tagger_func` is NULL by default in the
engine's stage table and the Kendra plug-in registers none); the dictionary is
applied by the plug-in's front end as the word items are built.

    python3 scripts/gpos_table.py                     # print the groups
    python3 scripts/gpos_table.py --lookup WORDS...
"""
from __future__ import annotations

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")

ARRAY_OFF = 0x2EB860           # ELF vaddr of the group array ([]p, run-separated)
VAL_LO, VAL_HI = 0x2EBB04, 0x2EC000   # {meta, char*} VAL array
DEFAULT_TAG = "content"


def _cstr(d, p):
    e = d.index(b"\0", p)
    return d[p:e].decode("latin1")


def load(so=SO):
    """Return (groups, word2tag); groups = [(tag, [word, ...]), ...]."""
    d = open(so, "rb").read()
    groups = []
    cur = []
    p = ARRAY_OFF
    while p < VAL_LO:
        v = struct.unpack_from("<I", d, p)[0]
        if v == 0:
            groups.append(cur)
            cur = []
        else:
            assert VAL_LO <= v < VAL_HI, f"bad entry pointer {v:#x} at {p:#x}"
            cur.append(_cstr(d, struct.unpack_from("<I", d, v + 4)[0]))
        p += 4
    if cur:
        groups.append(cur)
    groups = [g for g in groups if g]
    out = []
    for g in groups:
        out.append((g[0], list(g)))
    w2t = {}
    for tag, words in out:
        for w in words:
            w2t[w] = tag
    return out, w2t


def gpos_of(word, table=None, casefold=True):
    """The engine's tag for *word* (`content` when the table has no entry)."""
    if table is None:
        table = load()[1]
    return table.get(word.lower() if casefold else word, DEFAULT_TAG)


def main(argv):
    if "--lookup" in argv:
        i = argv.index("--lookup")
        casefold = "--no-casefold" not in argv
        table = load()[1]
        for w in argv[i + 1:]:
            print(f"{w:16s} {gpos_of(w, table, casefold)}")
        return 0
    groups, w2t = load()
    for tag, words in groups:
        print(f"{tag:6s} ({len(words):3d}) {' '.join(words)}")
    print(f"total {sum(len(w) for _t, w in groups)} entries, "
          f"{len(groups)} tags, default {DEFAULT_TAG!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
