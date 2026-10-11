#!/usr/bin/env python3
"""Unit selection exactly as the engine's `FUN_0005fc04` (Ghidra 0x5fc04) does it.

The engine has no "keep the N cheapest" rule.  Transcribed from
`out/ghidra_dump/libttsivonavoice.c:43094` and its disassembly (`out/viterbi_disasm.txt`,
ELF 0x4fc04..0x50b08), the search is:

1. **Candidate build** (:43100 / 0x50648 for node 0, :43294 / 0x4fc84 for the rest).
   For every unit id of the node's section-B slice the engine decodes the 36-byte
   section-C record of `idx` and of `idx+1` (`FUN_0005f1dc`), then skips the candidate
   when the node's *left* context is a `+` (vowel) and the record's stress byte
   (`+0x1d`) differs, or when the node's *right* context is a `+` and the right
   record's stress differs (:43123-43140, 0x4fd88..0x4fde4).  Surviving candidates
   get their **target cost** (`FUN_00031234`, :43149).
2. **Beam / prune** (:43203, 0x502d4 / 0x508d0).  Only when the candidate count is
   **> 51** (`0x33`): a cost **threshold sweep** raises `thr` from the minimum target
   cost until at least 51 candidates have `target <= thr`, and then `thr` is one
   higher still (the increment at 0x50350 happens before the exit test).  Candidates
   survive when `target <= thr` **or** they are context-exempt: the phone before
   their left record (`record[+3]`, named through the plug-in's phone table) equals
   the node's previous-segment name (`ctx1+0x08`), or the phone after their right
   record (`record[+5]`) equals the next-next segment name (`ctx2+0x10`).  A side
   whose own phone (`ctx+0x0c`) is `pau` disables its exemption.  Survivors get their
   two flag bytes updated: `+5` (forced) survives only for `node != 0` with a matching
   *left* context, `+4` (joint) only for `node + 1 < n_nodes` with a matching *right*
   context.
3. **Per node** the survivors are sorted by target (`FUN_0005fa84`, comparator
   `LAB_0005fa44` = u32 at +0), totalled (`+8 := +0`), and sorted by total
   (`LAB_0005fa64` = u32 at +8).  Both sorts are stable.
4. **Transition** (:43360, 0x4fe88).  The predecessor array is the *previous* node's
   array, ascending by total.  For candidate `e` the predecessors scanned are
   `min(prev_count, beam)` -- all of them when `e` carries the forced flag `+5` -- and
   only the first `beam` iterations compute a join cost.  A predecessor `p` with
   `p.flag4 and p.idx + 1 == e.idx` is a *joint* continuation: cost 0, `e.total := base`,
   `p.flag4 := 0`.  Otherwise `join(rec[p.idx + 1], rec[e.idx], budget = e.total - base)`
   runs on the **previous** node's join function (`node+0xc4`, 0x50024) and replaces the
   total when smaller.  The scan stops when `base >= e.total`, when the count cap is
   reached, or when `beam <= i` (the candidate's index), `e.flag4 == 0` and
   `beam_arr[beam-1] <= base`; `beam_arr` holds the `beam` smallest totals seen so far
   for this node.
5. **Chunk** (:43495, 0x50140 / 0x5055c).  The graph carries persistent state
   `param_1[5]` (node count), `[6]` (current node) and `[7]` (finished).  When the
   *previous* node's `+0xc8` flag is set and the current node is not the last, the
   current array is reduced to the candidates sharing the best entry's back-pointer
   (which is zeroed) and the function returns; the caller walks that prefix, commits
   it, and calls `FUN_0005fc04` again to finish with a fresh beam array.  `+0xc8` is set
   by the plug-in's graph builder (`FUN_00030214`) under the `tb_min_distance` rule --
   for the shipped Kendra voice exactly node 10 carries it, which is why the oracle
   capture shows two calls for the test sentence.

`scripts/probe_viterbi.py` re-runs the engine with a basic-block hook over
`FUN_0005fc04` and dumps every candidate-array mutation; `scripts/check_viterbi.py`
replays the rules above against those dumps.
"""
from __future__ import annotations

import argparse
import bisect
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prosody                                              # noqa: E402

BUCKETS = 0x33                      # 51: the sweep's candidate target
BEAM_DEFAULT = 50                   # plug-in `viterbi_beam` default (0x32)
BEAM_REDUCED = 25                   # beam >> 1, used at reduced quality
BIG = 1000000000                    # `1000000000`: "no path yet" total

REC_PREV_PHONE = 3                  # record byte: phone *before* the record's own phone
REC_NEXT_PHONE = 5                  # record byte: phone *after* it

SLOT_PREV_NAME = 0x08               # p.name    (name of the previous segment)
SLOT_SELF_NAME = 0x0C               # this phone's own name
SLOT_NEXT_NAME = 0x10               # n.name    (name of the next segment)
SLOT_STRESS = 0x1D                  # stress
SLOT_PH_VC = 0x54                   # ph_vc ("+": vowel right edge)


class Candidate:
    """One 20-byte engine candidate entry (`+0/+4/+5/+8/+0xc/+0x10`)."""

    __slots__ = ("db_idx", "record", "next_record", "target", "total",
                 "flag4", "flag5", "backptr")

    def __init__(self, db_idx, record, next_record=None, target=0):
        self.db_idx = db_idx
        self.record = record                  # 36-byte section-C record of the left phone
        self.next_record = next_record        # ... of the right phone (rec[db_idx + 1])
        self.target = target                  # entry +0x00
        self.total = BIG                      # entry +0x08
        self.flag4 = 1                        # entry +0x04 (joint / right context)
        self.flag5 = 1                        # entry +0x05 (forced  / left context)
        self.backptr = None                   # entry +0x10


class Node:
    """One graph node: a diphone position, its candidates and its contexts."""

    __slots__ = ("cands", "ctx1", "ctx2", "join", "forced")

    def __init__(self, cands=None, ctx1=None, ctx2=None, join=None, forced=False):
        self.cands = list(cands) if cands else []
        self.ctx1 = ctx1                      # node+0x04, 96-byte context vector
        self.ctx2 = ctx2                      # node+0x64
        self.join = join                      # node+0xc4: the variant for the *next* transition
        self.forced = forced                  # node+0xc8: tb_min_distance / chunk boundary


# --------------------------------------------------------------------------
# 1. candidate build: the `+`-context skip (:43123, 0x4fd88)
# --------------------------------------------------------------------------
def build_candidates(units, ctx1, ctx2, vec):
    """`FUN_0005fc04`'s in-build filter: the surviving unit ids, in slice order.

    `units` = the node's section-B unit ids; `vec(u)` = the 96-byte feature vector the
    engine's `FUN_0005f1dc` decodes for unit `u` (stress byte at 0x1d).
    """
    plus_left = ctx1.ch(SLOT_PH_VC) == "+"
    plus_right = ctx2.ch(SLOT_PH_VC) == "+"
    if not plus_left and not plus_right:
        return list(units)
    stress_left = ctx1.u8(SLOT_STRESS)
    stress_right = ctx2.u8(SLOT_STRESS)
    out = []
    for u in units:
        if plus_left and vec(u).u8(SLOT_STRESS) != stress_left:
            continue
        if plus_right and vec(u + 1).u8(SLOT_STRESS) != stress_right:
            continue
        out.append(u)
    return out


# --------------------------------------------------------------------------
# 2. the 51-bucket beam and the context exemptions (:43203, 0x502d4/0x508d0)
# --------------------------------------------------------------------------
def threshold(costs):
    """`FUN_0005fc04`'s sweep (0x502e0..0x5036c); `None` = no sweep (count <= 51)."""
    if len(costs) <= BUCKETS:
        return None
    mn, mx = min(costs), max(costs)
    if mn >= mx:
        return mn
    thr = mn
    while True:
        k = 0
        for c in costs:
            if c <= thr:
                k += 1
        thr += 1
        if k >= BUCKETS:                  # 0x50354: `cmp r1, #0x32` -> continue while <= 50
            break
        if thr >= mx:                     # 0x50360: continue while thr < mx
            break
    return thr


def prune(node, index, n_nodes, phone_name):
    """Apply the beam and the context exemptions to `node.cands` (in place).

    `phone_name(record, offset)` names a record byte through the plug-in's phone table
    (`*(char**)(payload+0x1c) + byte*0x20`).
    """
    cands = node.cands
    if len(cands) <= BUCKETS:
        return cands          # 0x502e4 / 0x508d4: the whole prune block is skipped
    thr = threshold([c.target for c in cands])
    left_pau = node.ctx1.st(SLOT_SELF_NAME) == "pau"
    right_pau = node.ctx2.st(SLOT_SELF_NAME) == "pau"
    prev_name = node.ctx1.st(SLOT_PREV_NAME)
    next_name = node.ctx2.st(SLOT_NEXT_NAME)
    out = []
    for c in cands:
        left_ok = (not left_pau) and phone_name(c.record, REC_PREV_PHONE) == prev_name
        right_ok = (not right_pau) and phone_name(c.next_record, REC_NEXT_PHONE) == next_name
        if not ((thr is not None and c.target <= thr) or left_ok or right_ok):
            continue
        c.flag5 = 1 if (index != 0 and left_ok) else 0
        c.flag4 = 1 if (index + 1 < n_nodes and right_ok) else 0
        out.append(c)
    node.cands = out
    return out


# --------------------------------------------------------------------------
# 4. transition (:43360, 0x4fe88)
# --------------------------------------------------------------------------
def _transition(prev_node, node, beam):
    """One node's relaxation pass; mirrors 0x4fe88..0x50128."""
    prev = prev_node.cands
    pc = len(prev)
    beam_on = beam is not None and beam > 0
    best = [BIG] * beam if beam_on else None      # `auStack_2028`, one array per node pass
    join = prev_node.join                         # 0x50024: `ldr pc, [r4, #0xc4]`
    for i, e in enumerate(node.cands):
        if e.flag5:
            npred = pc
        elif not beam_on or pc <= beam:           # unsigned compare with beam == -1
            npred = pc
        else:
            npred = beam
        e.total = BIG
        if npred:
            base = prev[0].total + e.target
            if base < e.total:
                j = 0
                fails = 0
                while True:
                    if beam_on and not e.flag4 and i >= beam and best[beam - 1] <= base:
                        break                     # 0x4ff88: short-circuit on the beam array
                    p = prev[j]
                    if p.flag4 and p.db_idx + 1 == e.db_idx:
                        e.backptr = p             # joint continuation: no join cost
                        p.flag4 = 0
                        e.total = base
                    elif not beam_on or fails < beam:
                        trans = join(prosody.Rec(p.next_record),
                                     prosody.Rec(e.record), e.total - base)
                        if trans + base < e.total:
                            e.backptr = p
                            e.total = trans + base
                    fails += 1
                    if fails >= npred:
                        break
                    j += 1
                    base = prev[j].total + e.target
                    if base >= e.total:
                        break
        if beam_on and e.total < best[beam - 1]:  # keep the `beam` smallest totals
            bisect.insort(best, e.total)
            del best[beam:]


# --------------------------------------------------------------------------
# 3 + 5. the search: prologue, per-node pass, chunk boundaries (`FUN_0005fc04`)
# --------------------------------------------------------------------------
def _chain(entry):
    """`FUN_0005faa0`: follow the back-pointers; returns the chain oldest-first."""
    out = []
    cur = entry
    while cur is not None:
        out.append(cur)
        cur = cur.backptr
    out.reverse()
    return out


def search(nodes, beam=BEAM_DEFAULT, phone_name=None, diag=None):
    """Run the engine's search over `nodes` (context-filtered and target-scored).

    Returns `(path, diag)`: the selected unit id per position and the diagnostics
    (kept sets per node, chunk boundaries).  `phone_name(record, offset)` names a
    record byte (required by the context exemptions); `beam <= 0` disables the beam
    (the engine's `-1`).
    """
    diag = {} if diag is None else diag
    n_nodes = len(nodes)
    if not n_nodes or not nodes[0].cands:
        return [], diag
    if phone_name is None:
        raise TypeError("search() needs phone_name(record, offset) for the "
                        "context exemptions")

    def by_total(c):
        return c.total

    def by_target(c):
        return c.target

    # prologue (:43259..43294): node 0 has no predecessor
    prune(nodes[0], 0, n_nodes, phone_name)
    nodes[0].cands.sort(key=by_target)            # FUN_0005fa84 (LAB_0005fa44)
    for c in nodes[0].cands:
        c.total = c.target
    nodes[0].cands.sort(key=by_total)             # qsort LAB_0005fa64

    chunks = []
    cur = 0
    while True:
        if cur >= n_nodes - 1:                    # last node reached (:43250)
            if nodes[-1].cands:
                chunks.append(_chain(nodes[-1].cands[0]))
            break
        nxt = cur + 1
        node = nodes[nxt]
        prune(node, nxt, n_nodes, phone_name)
        node.cands.sort(key=by_target)
        for c in node.cands:
            c.total = c.target
        node.cands.sort(key=by_total)
        _transition(nodes[cur], node, beam)
        node.cands.sort(key=by_total)
        if nodes[cur].forced:                     # chunk boundary (:43495)
            best_bp = node.cands[0].backptr if node.cands else None
            kept = [c for c in node.cands if c.backptr is best_bp]
            for c in kept:
                c.backptr = None
            node.cands = kept
            chunks.append(_chain(best_bp))
            cur = nxt
            continue                              # new call: fresh beam array
        cur = nxt

    path = [c.db_idx for ch in chunks for c in ch]
    diag["path"] = path
    diag["chunks"] = [[c.db_idx for c in ch] for ch in chunks]
    diag["kept"] = [[c.db_idx for c in n.cands] for n in nodes]
    diag["nodes"] = nodes
    diag["n_kept"] = [len(n.cands) for n in nodes]
    diag["beam"] = beam
    diag["cost"] = nodes[-1].cands[0].total if nodes[-1].cands else None
    return path, diag


def select(nodes, beam=BEAM_DEFAULT, phone_name=None):
    """`search()` without the diagnostics."""
    path, _ = search(nodes, beam=beam, phone_name=phone_name)
    return path


def _demo():
    import random

    raw = bytearray(0x60)
    raw[SLOT_STRESS] = 0
    strs = {0x08: "0", 0x0C: "pau", 0x10: "hh", 0x54: "0"}
    rng = random.Random(7)
    nodes = []
    for _ in range(4):
        cands = []
        for _ in range(80):
            rec = bytes(rng.randrange(256) for _ in range(36))
            cands.append(Candidate(rng.randrange(100000), rec, rec,
                                   target=rng.randrange(40)))
        nodes.append(Node(cands, prosody.Vec96(bytes(raw), strs),
                          prosody.Vec96(bytes(raw), strs), prosody.join_cost_default))
    path, diag = search(nodes, phone_name=lambda rec, off: "0")
    print("path:", path, "kept:", diag["n_kept"], "cost:", diag["cost"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.parse_args(argv)
    _demo()
    return 0


if __name__ == "__main__":
    sys.exit(main())
