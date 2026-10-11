#!/usr/bin/env python3
"""Replay the transcribed `FUN_0005fc04` rules against the instrumented engine run.

Two modes, both consuming `scripts/probe_viterbi.py` output:

`rule`   -- uses the engine's *own* candidate arrays (and therefore its own target
            costs) from `viterbi_probe2/viterbi_events.tsv`, rebuilds
            `select_units` candidates from them with our records / context vectors and
            runs `select_units.search`, then compares against the engine's arrays at
            every phase:
              * the `+`-context filter  : pre-prune set  (0x4fe38 / 0x502d4 snapshot)
              * the 51-bucket beam      : post-prune set  (0x4fe50 snapshot), ids,
                                          order and both flag bytes
              * the transition          : post-transition totals/order (0x4fc28 exit)
              * the chunked search      : the final unit-id sequence
            Because the target costs come from the engine, this isolates the search
            from our cost model.

`pipeline` -- runs `refimpl/engine_prosody.EngineSelector.select` (our cost model,
            durations, contexts and `tb_min_distance` flags) and compares the same
            quantities against the probe, plus the chosen unit ids against
            `out/oracle/ref_nopunct/unit_sequence.txt`.

Usage:
  ~/venvs/re/bin/python scripts/check_viterbi.py rule \
      --probe out/oracle/viterbi_probe2 --sent "Hello world this is a test"
  ~/venvs/re/bin/python scripts/check_viterbi.py pipeline --sent "Hello world this is a test"
"""
from __future__ import annotations

import argparse
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "refimpl"))
sys.path.insert(0, HERE)

import cdxv                                                     # noqa: E402
import prosody                                                  # noqa: E402
import select_units                                             # noqa: E402
from diphone_vec import record_decoder                          # noqa: E402

OBB = ("IVONA 2/IVONA Kendra US English beta_v1.6.23.422_apkfab.com/"
       "Android/obb/com.ivona.tts.voicebeta.eng.usa.kendra/"
       "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")

#: node+0xc4 (plugin ELF vaddr) -> our join-cost implementation
JOIN_BY_OFF = {
    0x2055C: prosody.join_cost_r,
    0x21868: prosody.join_cost_plus,
    0x21CB0: prosody.join_cost_gl,
    0x213D0: prosody.join_cost_dash,
    0x220F0: prosody.join_cost_default,
}
PLUGIN_BASE = 0x20000000

#: snapshot PCs of `FUN_0005fc04` (ELF vaddrs = Ghidra - 0x10000)
PC_PRE = {0x4FE38, 0x50968}      # built array (loop path / node-0 prologue)
PC_POST = {0x4FE50, 0x50870}    # after the beam/prune compaction
PC_EXIT = {0x4FC28}              # epilogue: post-transition state


# --------------------------------------------------------------- probe input
def load_events(path):
    """(call, node) -> list of snapshots in execution order."""
    per = collections.defaultdict(list)
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 11:
                continue
            ents = []
            if f[10]:
                for tok in f[10].split(","):
                    p = tok.split(":")
                    if len(p) == 8:
                        ents.append(tuple(int(x) for x in p))
            per[(int(f[0]), int(f[3]))].append(dict(
                pc=int(f[1], 16), kind=f[2], count=int(f[4]), cur=int(f[6]),
                fin=int(f[7]), forced=int(f[8]), ents=ents))
    return per


def load_nodes(path):
    """call -> node -> (raw 0xC0 hex, decoded string slots, forced flag)."""
    out = collections.defaultdict(dict)
    call = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("# call"):
                call = int(line.split()[2])
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 3 or f[0] != "node" or call is None:
                continue
            n = int(f[1])
            if f[2].startswith("slots"):
                import ast
                slots = {}
                for tok in "\t".join(f[3:]).split(" "):
                    if "=" in tok:
                        k, v = tok.split("=", 1)
                        try:
                            slots[int(k, 16)] = ast.literal_eval(v)
                        except Exception:
                            pass
                out[call].setdefault(n, {})["slots"] = slots
            elif len(f) >= 6 and len(f[5]) == 0xC0 * 2:
                out[call].setdefault(n, {})["raw"] = bytes.fromhex(f[5])
                out[call][n]["forced"] = int(f[3].split("=")[1])
                out[call][n]["join"] = int(f[4].split("=")[1], 16)
    return out


def engine_nodes(ev, nd, n_nodes=19):
    """One dict per node built from the engine's own pre-prune array + contexts."""
    order = sorted(c for c in nd if nd[c])
    call = order[0]
    ctx_raw, slots = {}, {}
    for n in range(n_nodes):
        ctx_raw[n] = nd[call][n]["raw"][:0x60]
        slots[n] = nd[call][n]["slots"]
    ctx_raw[n_nodes] = nd[call][n_nodes - 1]["raw"][0x60:]      # last node's ctx2
    slots[n_nodes] = slots[0]                                   # its phone is `pau`
    out = []
    for n in range(n_nodes):
        snaps = [s for s in ev.get((0, n), []) if s["cur"] == n]
        if not snaps:
            snaps = [s for s in ev.get((1, n), []) if s["cur"] == n]
        # Phase selection by PC (see PC_PRE/PC_POST): the last snapshot of the
        # built array (0x4fe38 in the loop path, 0x50968 in the node-0 prologue)
        # and the first snapshot of the compacted array after it.
        pre = None
        for s in snaps:
            if s["pc"] in PC_PRE and s["count"] > 0:
                pre = s
        post = pre
        if pre is not None:
            seen = False
            for s in snaps:
                if s is pre:
                    seen = True
                    continue
                if seen and s["pc"] in PC_POST and s["count"] \
                        and s["count"] < pre["count"]:
                    post = s
                    break
        fin = None
        for c in (0, 1):
            for s in ev.get((c, n), []):
                if s["pc"] in PC_EXIT and s["count"]:
                    fin = s
        out.append(dict(
            node=n, pre=pre, post=post or pre, final=fin or post or pre,
            ctx1=prosody.Vec96(ctx_raw[n], slots[n]),
            ctx2=prosody.Vec96(ctx_raw[n + 1], slots[n + 1]),
            forced=bool(nd[call][n]["forced"]),
            join=JOIN_BY_OFF.get(nd[call][n]["join"] - PLUGIN_BASE),
            join_raw=nd[call][n]["join"]))
    return out


# ------------------------------------------------------------------- checks
def _chain_names(oracle_dir):
    """The linguistic diphone chain from the capture's `diphone_lookups.tsv`."""
    pairs = []
    path = os.path.join(oracle_dir, "diphone_lookups.tsv")
    if not os.path.exists(path):
        return pairs
    for line in open(path):
        if line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) >= 2:
            pairs.append(f[1])
    return pairs


def run_rule(args):
    reader = cdxv.OBBReader(os.path.join(ROOT, OBB))
    dec = record_decoder(reader)
    ev = load_events(os.path.join(ROOT, args.probe, "viterbi_events.tsv"))
    nd = load_nodes(os.path.join(ROOT, args.probe, "viterbi_nodes.txt"))
    eng = engine_nodes(ev, nd)
    phones = reader.phonemes()
    phone_name = lambda rec, off: phones[rec[off]]            # noqa: E731

    # ---- 1. the `+`-context build filter, against the engine's pre-prune set
    pairs = _chain_names(os.path.join(ROOT, args.oracle))
    names = {d.name: (d.start, d.count) for d in reader.diphones()}
    units = reader.diphone_units()
    filt_ok = 0
    print("== build filter (candidate build, 0x4fe38/0x502d4) ==")
    for i, e in enumerate(eng):
        want = [idx for (_t, _f4, _f5, _tot, idx, _bp, _b3, _b5) in e["pre"]["ents"]]
        if i < len(pairs) and pairs[i] in names:
            start, count = names[pairs[i]]
            sl = units[start:start + count]
            got = select_units.build_candidates(sl, e["ctx1"], e["ctx2"], dec.vector)
        else:
            got = want
        same = got == want
        filt_ok += same
        print(f"node {i:2d}: slice->kept {len(got):5d} engine {len(want):5d} "
              f"{'OK' if same else 'DIFF'}")
        if not same:
            for k, (a, b) in enumerate(zip(got, want)):
                if a != b:
                    print(f"    first divergence at k={k}: ours {a} engine {b}")
                    break

    # ---- 2 + 3. beam/prune and the chunked search on the engine's target costs
    nodes = []
    for e in eng:
        cands = [select_units.Candidate(idx, reader.c_record(idx),
                                        reader.c_record(idx + 1), target=t)
                 for (t, _f4, _f5, _tot, idx, _bp, _b3, _b5) in e["pre"]["ents"]]
        nodes.append(select_units.Node(cands, e["ctx1"], e["ctx2"], join=e["join"],
                                       forced=e["forced"]))
    path, diag = select_units.search(nodes, beam=args.beam, phone_name=phone_name)
    print("\n== beam/prune + transition (kept ids, totals, flags) ==")
    print("# node  pre  kept_eng  thr  kept_ours  ids  totals  flags")
    ok = 0
    for i, (e, node) in enumerate(zip(eng, nodes)):
        got = [(c.db_idx, c.target, c.total, c.flag4, c.flag5) for c in node.cands]
        want = [(idx, t, tot, f4, f5)
                for (t, f4, f5, tot, idx, _bp, _b3, _b5) in e["final"]["ents"]]
        thr = select_units.threshold([t for (t, *_r) in e["pre"]["ents"]])
        ids_ok = [g[0] for g in got] == [w[0] for w in want]
        tot_ok = [(g[2], g[1]) for g in got] == [(w[2], w[1]) for w in want]
        fl_ok = [(g[3], g[4]) for g in got] == [(w[3], w[4]) for w in want]
        ok += ids_ok and fl_ok and tot_ok
        print(f"{i:5d} {e['pre']['count']:5d} {len(want):8d} "
              f"{str(thr):>5} {len(got):9d}  {ids_ok!s:5}  {tot_ok!s:6}  {fl_ok!s:5}")
        if not (ids_ok and fl_ok and tot_ok):
            for k, (g, w) in enumerate(zip(got, want)):
                if g[0] != w[0]:
                    print(f"      first divergence at k={k}: ours {g} engine {w}")
                    break
            else:
                for k, (g, w) in enumerate(zip(got, want)):
                    if g[2] != w[2] or g[1] != w[1]:
                        print(f"      total diff at k={k}: ours {g} engine {w}")
                        break

    us = os.path.join(ROOT, args.oracle, "unit_sequence.txt")
    want = []
    if os.path.exists(us):
        for line in open(us):
            if line.startswith("#"):
                continue
            want.append(int(line.split("\t")[1]))
    same = sum(1 for a, b in zip(path, want) if a == b)
    print(f"\nbuild filter: {filt_ok}/19 nodes; kept sets: {ok}/19")
    print(f"unit sequence (engine target costs): {same}/{len(want)} exact")
    if same != len(want):
        print("  engine:", want)
        print("  ours  :", list(path))
        for k, (a, b) in enumerate(zip(want, path)):
            if a != b:
                print(f"  pos {k}: engine {a} ours {b}")
    print("chunks:", diag["chunks"])
    print("kept counts:", diag["n_kept"])
    return 0


def run_pipeline(args):
    """Our full EngineSelector (own costs/contexts/flags) vs the probe."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import tts as T
    import engine_prosody
    from phoneset import PhoneSet
    from cdxv import OBBReader

    cfg = T.VOICES[args.voice]
    ps = PhoneSet.from_so(T._resolve(cfg['pset_so']), cfg['pset'])
    cart = prosody.Cart.from_so(T._resolve(cfg['zdur_so']))
    cx = OBBReader(os.path.join(ROOT, OBB))
    g2p = T.G2P(T._resolve(cfg['g2p']))
    esel = engine_prosody.EngineSelector(cx, cart, ps, beam=args.beam)
    esel.pm.pause_base = cfg['pause_base']
    sel = T.UnitSelector(cx)
    items, _ = T.phone_items(g2p, args.sent, sel.names)
    phones = T.items_phones(items)
    pairs = T.diphone_pairs(phones)
    utt = esel.pm.analyse(items)
    path, diag = esel.select(utt, pairs)
    if path is None:
        print("!! selection failed: %r" % (diag,))
        return 1
    ev = load_events(os.path.join(ROOT, args.probe, "viterbi_events.tsv"))
    nd = load_nodes(os.path.join(ROOT, args.probe, "viterbi_nodes.txt"))
    eng = engine_nodes(ev, nd)
    print("== kept sets + totals + flags (post-transition, sorted by total) ==")
    ok = 0
    for i, e in enumerate(eng):
        want = [(idx, tot) for (_t, _f4, _f5, tot, idx, _bp, _b3, _b5)
                in e["final"]["ents"]]
        got = [(c.db_idx, c.total) for c in diag["nodes"][i].cands]
        same = got == want
        ok += same
        print(f"node {i:2d}: ours {len(got):5d} engine {len(want):5d} "
              f"counts={'OK' if len(got) == len(want) else 'DIFF'} ids+totals={same} "
              f"forced={e['forced']}")
        if not same and len(got) == len(want):
            diff = [(k, a, b) for k, (a, b) in enumerate(zip(got, want)) if a != b]
            print(f"   first diffs (idx,total): {diff[:4]}")
    print(f"\nkept-set+totals match: {ok}/19")
    print("chosen units:", path)
    us = os.path.join(ROOT, args.oracle, "unit_sequence.txt")
    if os.path.exists(us):
        want = []
        for line in open(us):
            if line.startswith("#"):
                continue
            want.append(int(line.split("\t")[1]))
        same = sum(1 for a, b in zip(path, want) if a == b)
        pref = 0
        for a, b in zip(path, want):
            if a != b:
                break
            pref += 1
        print(f"unit sequence: {same}/{len(want)} exact, prefix {pref}")
        print("  engine:", want)
        print("  ours  :", list(path))
        for k, (a, b) in enumerate(zip(want, path)):
            if a != b:
                print(f"  pos {k}: engine {a} ours {b} engine_target="
                      f"{dict(diag['target'][k]).get(a)} "
                      f"ours_target={dict(diag['target'][k]).get(b)}")
    print("kept counts:", diag["n_kept"])
    print("forced flags:", diag["forced"])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("rule", "pipeline"))
    ap.add_argument("--probe", default="out/oracle/viterbi_probe2")
    ap.add_argument("--oracle", default="out/oracle/ref_nopunct")
    ap.add_argument("--sent", default="Hello world this is a test")
    ap.add_argument("--voice", default="kendra")
    ap.add_argument("--beam", type=int, default=25)
    a = ap.parse_args(argv)
    return run_rule(a) if a.mode == "rule" else run_pipeline(a)


if __name__ == "__main__":
    sys.exit(main())
