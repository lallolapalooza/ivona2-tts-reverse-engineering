#!/usr/bin/env python3
"""Diff `refimpl/tts.py --select viterbi` against a captured engine run.

Consumes an `out/oracle/<capture>/` directory produced by `emu/tts_run.py`
(`--level 3 --ret-probe`) and reports, layer by layer:

1. **chain**      — the linguistic diphone chain my pipeline builds vs
                    `diphone_lookups.tsv` (and the section-A `diphoneset_num`);
2. **lattice**    — candidate counts / `b_start` vs `candidate_lattice.txt`;
3. **contexts**   — my 96-byte context vectors (`FUN_00060ed4`) vs
                    `unit_feature_vectors.tsv`, numeric slots and string slots;
4. **target cost** — my `FUN_00031234` per candidate vs `viterbi_candidates.tsv`
                    (when the capture has it);
5. **selection**  — the chosen unit ids vs `unit_sequence.txt`, plus where the
                    engine's unit ranks in my cost model.

Usage:
  python3 scripts/compare_selection.py --oracle-dir out/oracle/ref_lexclean \
      --text "Hello, this is a comma dot." [--beam 50] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "refimpl"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cdxv                                                # noqa: E402
import prosody                                             # noqa: E402
import tts                                                 # noqa: E402
import engine_prosody                                      # noqa: E402
from phoneset import PhoneSet                              # noqa: E402
from diphone_vec import STR_SLOTS                          # noqa: E402

FEM_STR = {0x04: "p.p.name", 0x08: "p.name", 0x0C: "name", 0x10: "n.name",
           0x14: "n.n.name", 0x38: "gpos", 0x4C: "endtone"}


def _rows(path):
    if not os.path.exists(path):
        return None
    out = []
    for line in open(path):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        out.append(line.split("\t"))
    return out


def load_oracle(d):
    o = {}
    r = _rows(os.path.join(d, "diphone_lookups.tsv"))
    if r:
        o["chain"] = [x[1] for x in r]
        o["chain_idx"] = [int(x[2]) for x in r]
    r = _rows(os.path.join(d, "candidate_lattice.txt"))
    if r:
        o["lattice"] = [dict(name=x[1], idx=int(x[2]), count=int(x[3]),
                             b_start=int(x[4]),
                             selected=int(x[5]) if x[5] else None,
                             variant=int(x[6]) if len(x) > 6 and x[6] else None)
                        for x in r]
    r = _rows(os.path.join(d, "unit_sequence.txt"))
    if r:
        o["units"] = [int(x[1]) for x in r]
        o["unit_names"] = [x[2] for x in r]
    fem_path = os.path.join(d, "unit_feature_vectors.tsv")
    if os.path.exists(fem_path):
        vecs, strs = [], []
        for line in open(fem_path):
            if not line.startswith("0x"):
                continue
            m = re.search(r"#\s*([0-9a-f]{192})\s*$", line.strip())
            if not m:
                continue
            # the harness logs each `FUN_00060ed4` call twice: at entry (the
            # output buffer is still the caller's zeroed one) and at return.
            # Keep the return-time row only.
            vec = bytes.fromhex(m.group(1))
            if not any(vec):
                continue
            cols = line.split("\t")
            vecs.append(vec)
            # columns after the item pointer: the resolved string slots in the
            # order sorted({0x04,0x08,0x0c,0x10,0x14,0x38,0x4c}) -- see the dump
            strs.append([c for c in cols[1:] if not c.strip().startswith("#")])
        o["fem"] = vecs
        o["fem_strs"] = strs
    r = _rows(os.path.join(d, "candidate_records.tsv"))
    if r:
        recs = []
        for x in r:
            hexes = [f for f in x if re.fullmatch(r"[0-9a-f]+", f) and len(f) in (72, 192)]
            d36 = next((f for f in hexes if len(f) == 72), None)
            d96 = next((f for f in hexes if len(f) == 192), None)
            if d36:
                recs.append((bytes.fromhex(d36), bytes.fromhex(d96) if d96 else None))
        o["cand_records"] = recs
    r = _rows(os.path.join(d, "viterbi_candidates.tsv"))
    if r:
        o["viterbi"] = r
    r = _rows(os.path.join(d, "settings.txt"))
    if r:
        o["settings"] = dict((x[0], x[1]) for x in r if len(x) > 1)
    return o


HEADER_FIELDS = ("# position\tdiphone\tcount\toracle_count\tb_start\tb_start_oracle\t"
                 "oracle_unit\tmine_unit\ttarget(oracle_unit)\ttarget(mine)\trank")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--oracle-dir", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--voice", default="kendra")
    ap.add_argument("--beam", type=int, default=50)
    ap.add_argument("--json")
    a = ap.parse_args(argv)

    o = load_oracle(a.oracle_dir)
    cfg = tts.VOICES[a.voice]
    obb = tts._resolve(cfg['obb'])
    cx = cdxv.OBBReader(obb)
    usel = tts.UnitSelector(cx)
    g2p = tts.G2P(tts._resolve(cfg['g2p']))
    items, _det = tts.phone_items(g2p, a.text, usel.names)
    phones = tts.items_phones(items)
    pairs = tts.diphone_pairs(phones)
    ps = PhoneSet.from_so(tts._resolve(cfg['pset_so']), cfg['pset'])
    cart = prosody.Cart.from_so(tts._resolve(cfg['zdur_so']))
    esel = engine_prosody.EngineSelector(cx, cart, ps, beam=a.beam)
    utt = esel.pm.analyse(items)
    durations = esel.pm.durations(utt)
    ctxs = esel.pm.context_vectors(utt, durations)
    path, diag = esel.select(utt, pairs)

    res = {"oracle_dir": a.oracle_dir, "text": a.text, "voice": a.voice,
           "beam": a.beam}
    print("== chain ==")
    oc = o.get("chain", [])
    res["chain_match"] = (oc == pairs)
    print("mine   : %s" % " ".join(pairs))
    print("oracle : %s" % " ".join(oc))
    print("chain identical: %s" % res["chain_match"])
    if o.get("chain_idx"):
        order = {d.name: i for i, d in enumerate(cx.diphones())}
        mine_idx = [order.get(n, -1) for n in pairs]
        res["chain_idx"] = {"mine": mine_idx, "oracle": o["chain_idx"],
                            "match": mine_idx == o["chain_idx"]}
        print("diphone idx identical: %s" % res["chain_idx"]["match"])

    print("\n== lattice ==")
    lat = o.get("lattice") or []
    if lat:
        res["lattice"] = []
        print(HEADER_FIELDS)
        for i, (p, mine) in enumerate(zip(lat, diag["n_cand"])):
            u = p["selected"]
            t_or = next((t for (uu, t) in diag["target"][i] if uu == u), None)
            t_me = diag["target"][i][
                [uu for (uu, _t) in diag["target"][i]].index(path[i])][1]
            rank = sorted(t for (_uu, t) in diag["target"][i]).index(t_or) + 1 \
                if t_or is not None else None
            print("# %-3d %-9s %-6d %-12d %-8d %-14d %-10s %-10s %-16s %-12s %s"
                  % (i, p["name"], mine, p["count"], usel.names[p["name"]][0],
                     p["b_start"], u, path[i], t_or, t_me,
                     "%d/%d" % (rank, mine) if rank else "-"))
            res["lattice"].append(dict(position=i, diphone=p["name"],
                                       count_mine=mine, count_oracle=p["count"],
                                       b_start_oracle=p["b_start"],
                                       oracle_unit=u, mine_unit=path[i],
                                       target_oracle_unit=t_or, target_mine=t_me,
                                       rank_of_oracle_unit=rank))
    else:
        print("(no candidate_lattice.txt in the capture)")

    print("\n== context vectors (FUN_00060ed4) ==")
    fem = o.get("fem") or []
    if fem:
        n = min(len(fem), len(ctxs))
        slot_bad = {}
        examples = {}
        for i in range(n):
            e, m = fem[i], ctxs[i].b
            for off in range(0x60):
                # string-pointer slots: 0x54/0x58/0x5c (ph_vc/ph_cvox/ph_ctype)
                # hold guest pointers in the engine's vector and are carried as
                # text in `Vec96.strs` on our side, so the byte compare skips
                # them too (the capture does not decode them).
                if any(off in range(s, s + 4)
                       for s in STR_SLOTS + (0x54, 0x58, 0x5C)):
                    continue
                if e[off] != m[off]:
                    slot_bad[off] = slot_bad.get(off, 0) + 1
                    examples.setdefault(off, []).append(
                        (i, ctxs[i].st(0x0C), e[off], m[off]))
        str_bad = {}
        str_ex = {}
        fs = o.get("fem_strs") or []
        order = sorted(FEM_STR)
        if fs:
            for i in range(min(n, len(fs))):
                cols = fs[i]
                for k, off in enumerate(order):
                    if k >= len(cols):
                        break
                    eng = cols[k]
                    mine = ctxs[i].st(off)
                    if eng.startswith("0x"):       # unresolvable pointer
                        continue
                    if eng != mine:
                        str_bad[FEM_STR[off]] = str_bad.get(FEM_STR[off], 0) + 1
                        str_ex.setdefault(FEM_STR[off], []).append((i, eng, mine))
        # names (slot 0x0c) must line up positionally, else the dump order differs
        name_ok = sum(1 for i in range(min(n, len(fs))) if fs[i]
                      and fs[i][2] == ctxs[i].st(0x0C)) if fs else n
        res["context_slots"] = {"vectors_compared": n,
                                "engine_vectors": len(fem), "mine": len(ctxs),
                                "names_aligned": name_ok,
                                "bad_offsets": {hex(k): v for k, v in sorted(slot_bad.items())},
                                "bad_strings": str_bad}
        print("vectors compared: %d (mine %d, oracle %d), names aligned %d"
              % (n, len(ctxs), len(fem), name_ok))
        if slot_bad:
            for off in sorted(slot_bad):
                ex = examples.get(off, [])[:4]
                print("  slot %#04x differs in %d/%d vectors; e.g. %s"
                      % (off, slot_bad[off], n,
                         ", ".join("i=%d(%s) engine=%d mine=%d" % t for t in ex)))
        else:
            print("  all numeric slots identical")
        if str_bad:
            for k, v in sorted(str_bad.items()):
                print("  string %-9s differs in %d/%d; e.g. %s"
                      % (k, v, n, ", ".join("i=%d engine=%r mine=%r" % t
                                            for t in str_ex[k][:4])))
        else:
            print("  string slots (0x04/0x08/0x0c/0x10/0x14/0x38/0x4c) all identical")
    else:
        print("(no unit_feature_vectors.tsv in the capture)")

    print("\n== selection ==")
    ou = o.get("units") or []
    if ou:
        same = sum(1 for x, y in zip(ou, path) if x == y)
        pref = 0
        for x, y in zip(ou, path):
            if x != y:
                break
            pref += 1
        res["selection"] = dict(n=len(ou), exact=same, prefix=pref,
                                oracle=ou, mine=path,
                                diffs=[dict(pos=i, oracle=x, mine=y)
                                       for i, (x, y) in enumerate(zip(ou, path))
                                       if x != y])
        print("unit ids oracle: %s" % ou)
        print("unit ids mine  : %s" % path)
        print("exact %d/%d, common prefix %d" % (same, len(ou), pref))
        for i, (x, y) in enumerate(zip(ou, path)):
            if x != y:
                print("  pos %-3d oracle %-8d mine %-8d (%s)" %
                      (i, x, y, o.get("unit_names", ["?"] * len(ou))[i]))
    else:
        print("(no unit_sequence.txt in the capture)")
    print("\nchain: %d segments, %d diphones; join variants: %s"
          % (len(phones), len(pairs), " ".join(diag["join_variants"])))
    print("durations (ms): %s"
          % " ".join("%.0f" % (d * 1000.0) for d, _e in durations))

    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
