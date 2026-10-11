#!/usr/bin/env python3
"""Validate the recovered `gpos` table against a capture.

For the capture's `unit_feature_vectors.tsv` every row is one segment and the
`0x38` slot holds the *word's* `gpos` string (the tsv column labelled
`gpos(str)`).  This script rebuilds the same utterance with
`refimpl/engine_prosody.py` (so each segment knows which word it belongs to),
aligns the two phone chains and reports, per word, the engine's tag vs the tag
the recovered closed-class table predicts (`scripts/gpos_table.py`).

    python3 scripts/validate_gpos.py --oracle-dir out/oracle/ref_nopunct \
        --text "hello world this is a test"
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "refimpl"))
sys.path.insert(0, HERE)

import cdxv                                                # noqa: E402
import prosody                                             # noqa: E402
import tts                                                 # noqa: E402
import engine_prosody                                      # noqa: E402
from phoneset import PhoneSet                              # noqa: E402


def engine_rows(path):
    rows = []
    cur = None
    for ln in open(path):
        if ln.startswith("#"):
            continue
        pre, _, hx = ln.partition("#")
        cols = pre.split()
        b = bytes.fromhex(hx.strip())
        if not any(b):
            continue
        if cur is not None and cols[0] == cur[0] and cols[3] == cur[2]:
            continue
        cur = (cols[0], None, cols[3], cols[6], b)
        rows.append(cur)
    # the harness logs each item twice (entry-time zero buffer + return-time
    # value); keep the rows whose 0x38 slot is set, else the last of the pair
    out = []
    i = 0
    while i < len(rows):
        if i + 1 < len(rows) and rows[i][0] == rows[i + 1][0]:
            a, b2 = rows[i], rows[i + 1]
            out.append(b2 if b2[3] not in ("0", "0x0") else a)
            i += 2
        else:
            out.append(rows[i])
            i += 1
    return [(r[2], r[3]) for r in out]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oracle-dir", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--voice", default="kendra")
    a = ap.parse_args(argv)

    eng = engine_rows(os.path.join(a.oracle_dir, "unit_feature_vectors.tsv"))

    cfg = tts.VOICES[a.voice]
    cx = cdxv.OBBReader(tts._resolve(cfg['obb']))
    usel = tts.UnitSelector(cx)
    g2p = tts.G2P(tts._resolve(cfg['g2p']))
    items, _ = tts.phone_items(g2p, a.text, usel.names)
    ps = PhoneSet.from_so(tts._resolve(cfg['pset_so']), cfg['pset'])
    cart = prosody.Cart.from_so(tts._resolve(cfg['zdur_so']))
    esel = engine_prosody.EngineSelector(cx, cart, ps, beam=1)
    utt = esel.pm.analyse(items)
    dur = esel.pm.durations(utt)
    ctxs = esel.pm.context_vectors(utt, dur)

    mine = [(utt.segs[i].name, ctxs[i].st(0x38), utt.words[utt.segs[i].word].text
             if utt.segs[i].word >= 0 else "")
            for i in range(len(utt.segs))]
    print(f"engine {len(eng)} segments, model {len(mine)} segments")
    n = min(len(eng), len(mine))
    bad = 0
    per_word = {}
    for i in range(n):
        e_name, e_tag = eng[i]
        m_name, m_tag, wtext = mine[i]
        ok = e_tag == m_tag
        bad += not ok
        per_word.setdefault(wtext, set()).add((e_tag, m_tag, ok))
        print(f"{i:3d} {e_name:5s} engine={e_tag:8s} model={m_tag:8s} "
              f"{wtext:12s} {'OK' if ok else '<-- MISMATCH'}")
    print(f"\nper word:")
    for w, s in per_word.items():
        tags = {t for t, _m, _o in s}
        print(f"  {w or '(pau)':14s} engine={sorted({t for t,_m,_o in s})} "
              f"model={sorted({m for _t,m,_o in s})}")
    print(f"\n{'-' if bad else 'all'} {n - bad}/{n} segment gpos slots agree")
    return 1 if bad or len(eng) != len(mine) else 0


if __name__ == "__main__":
    sys.exit(main())
