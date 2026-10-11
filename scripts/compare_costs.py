#!/usr/bin/env python3
"""Diff my target cost (`FUN_00031234`) against the engine's own per-candidate costs.

`emu/tts_run.py` dumps, per Viterbi node, the candidate array the engine actually
built (`viterbi_candidates.tsv`: `diphone_idx`, `target_cost`, `total`).  This
script recomputes those target costs with `refimpl/engine_prosody.py`
(`prosody.dispatch_cost` over the `FUN_0005f1dc`-decoded candidate records and my
`FUN_00060ed4` context vectors) and reports, per node and overall:

* exact agreement, and the distribution of |engine − mine|,
* the worst offenders with both costs,
* optionally the Viterbi path restricted to the engine's *own* candidate sets
  (`--beam 0`), which isolates the cost model from beam-pruning differences.

Usage:
  python3 scripts/compare_costs.py --oracle-dir out/oracle/ref_lexclean \
      --text "hello comma this is a comma dot dot"
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "refimpl"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cdxv                                                # noqa: E402
import select_units                                        # noqa: E402
import prosody                                             # noqa: E402
import tts                                                 # noqa: E402
import engine_prosody                                      # noqa: E402
from phoneset import PhoneSet                              # noqa: E402


def load_viterbi(path):
    nodes = {}
    for line in open(path):
        if line.startswith("#"):
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 5:
            continue
        n, k, target, total, idx = (int(f[0]), int(f[1]), int(f[2]), int(f[3]),
                                    int(f[4]))
        nodes.setdefault(n, []).append(dict(k=k, target=target, total=total,
                                            idx=idx))
    return [nodes[i] for i in sorted(nodes)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oracle-dir", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--voice", default="kendra")
    ap.add_argument("--beam", type=int, default=0,
                    help="beam passed to my Viterbi (0 = keep the engine's sets)")
    ap.add_argument("--json")
    a = ap.parse_args(argv)

    path = os.path.join(a.oracle_dir, "viterbi_candidates.tsv")
    if not os.path.exists(path):
        raise SystemExit("no viterbi_candidates.tsv in %s" % a.oracle_dir)
    eng_nodes = load_viterbi(path)

    cfg = tts.VOICES[a.voice]
    cx = cdxv.OBBReader(tts._resolve(cfg['obb']))
    usel = tts.UnitSelector(cx)
    g2p = tts.G2P(tts._resolve(cfg['g2p']))
    items, _ = tts.phone_items(g2p, a.text, usel.names)
    phones = tts.items_phones(items)
    pairs = tts.diphone_pairs(phones)
    ps = PhoneSet.from_so(tts._resolve(cfg['pset_so']), cfg['pset'])
    cart = prosody.Cart.from_so(tts._resolve(cfg['zdur_so']))
    esel = engine_prosody.EngineSelector(cx, cart, ps, beam=a.beam)
    utt = esel.pm.analyse(items)
    dur = esel.pm.durations(utt)
    ctxs = esel.pm.context_vectors(utt, dur)

    if len(eng_nodes) != len(pairs):
        print("!! node count %d vs my %d diphones" % (len(eng_nodes), len(pairs)))

    res = {"nodes": [], "exact": 0, "n": 0, "engine_sets_path": None}
    myst = {}
    for n, cands in enumerate(eng_nodes):
        if n >= len(pairs):
            break
        row = []
        for c in cands:
            u = c["idx"]
            mine = prosody.dispatch_cost(esel.dec.vector(u), esel.dec.vector(u + 1),
                                         ctxs[n], ctxs[n + 1])
            row.append((u, c["target"], mine))
            myst[u] = mine
        exact = sum(1 for _u, e, m in row if e == m)
        deltas = sorted(abs(e - m) for _u, e, m in row)
        res["exact"] += exact
        res["n"] += len(row)
        worst = sorted(row, key=lambda t: -abs(t[1] - t[2]))[:3]
        print("node %-2d %-8s cands=%-4d exact %-4d/%d  |d| min/med/max = %d/%d/%d   worst: %s"
              % (n, pairs[n], len(row), exact, len(row), deltas[0],
                 deltas[len(deltas) // 2], deltas[-1],
                 " ".join("%d(e%d m%d)" % t for t in worst)))
        res["nodes"].append(dict(node=n, diphone=pairs[n], cands=len(row),
                                 exact=exact,
                                 worst=[dict(unit=u, engine=e, mine=m)
                                        for u, e, m in worst]))
    print("TOTAL exact %d/%d (%.2f%%)"
          % (res["exact"], res["n"], 100.0 * res["exact"] / max(1, res["n"])))

    # Viterbi restricted to the engine's own candidate sets, costs recomputed
    if a.beam <= 0:
        beams = []
        for n, cands in enumerate(eng_nodes):
            if n >= len(pairs):
                break
            beams.append([select_units.Candidate(u, cx.c_record(u), target=myst[u])
                          for u in [c["idx"] for c in cands]])
        # the transition *into* node i runs the join function of node i-1
        # (the engine reads `[prev + 0xc4]`), whose right context is `ctxs[i]`
        join_fns = [engine_prosody.join_fn_for(ctxs[i]) for i in range(len(pairs))]
        BIG = 1000000000
        for c in beams[0]:
            c.total = c.target
        for i in range(1, len(beams)):
            fn = join_fns[i]
            for cand in beams[i]:
                cand.total = BIG
                cand.backptr = None
                for pc in beams[i - 1]:
                    if pc.total >= BIG:
                        continue
                    base = pc.total + cand.target
                    budget = cand.total - base
                    if budget < 0:
                        continue
                    if pc.db_idx + 1 == cand.db_idx:
                        trans = 0
                    else:
                        trans = fn(prosody.Rec(pc.record), prosody.Rec(cand.record), budget)
                    if base + trans < cand.total:
                        cand.total = base + trans
                        cand.backptr = pc
        cur = min(beams[-1], key=lambda c: c.total)
        path = []
        for i in range(len(beams) - 1, -1, -1):
            path.append(cur.db_idx)
            cur = cur.backptr
        path.reverse()
        ou = []
        up = os.path.join(a.oracle_dir, "unit_sequence.txt")
        if os.path.exists(up):
            for line in open(up):
                if not line.startswith("#"):
                    ou.append(int(line.split("\t")[1]))
        # NB: this plain DP keeps *all* of the engine's candidates and ignores the
        # engine's prune/threshold + flag/chunk rules, so the path it returns is a
        # diagnostic only -- the engine-exact search lives in
        # `refimpl/engine_prosody.EngineSelector` / `scripts/select_units.py`
        # (report_pipeline.md §12)
        print("Viterbi over the engine's own candidate sets (no prune/flags, "
              "diagnostic only): %s" % path)
        if ou:
            same = sum(1 for x, y in zip(ou, path) if x == y)
            print("engine path:                                     %s" % ou)
            print("exact %d/%d" % (same, len(ou)))
            res["engine_sets_path"] = dict(path=path, engine=ou, exact=same)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 0


def _unused(u, target):
    c = select_units.Candidate(u, None, target=target)
    return c


if __name__ == "__main__":
    sys.exit(main())
