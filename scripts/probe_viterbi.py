#!/usr/bin/env python3
"""Instrument the engine's Viterbi (`FUN_0005fc04`) while it runs under Unicorn.

`emu/tts_run.py` captures the *result* of the search (the candidate arrays when
the function returns).  To transcribe the search itself we need the intermediate
states: the candidate list right after it is built, right after the beam/prune
compaction, and right after the transition pass -- together with the two
per-candidate flag bytes (`+4`, `+5`), the node flag `+0xc8` and the two 96-byte
context vectors of every node.

This script subclasses `emu.tts_run.Oracle` (originals untouched), adds a basic
block hook over the `FUN_0005fc04` range, and dumps a node's candidate array
whenever its `(ptr, count)` pair changes:

    --out-dir/viterbi_events.tsv   one line per mutation, entries inline
    --out-dir/viterbi_blocks.tsv   executed basic-block addresses per call
    --out-dir/viterbi_nodes.txt    per-node context vectors, +0xc8 flag, names

Usage (same driver as the oracle capture):

    ~/venvs/re/bin/python scripts/probe_viterbi.py \
        --sentence "Hello world this is a test" --out-dir out/oracle/viterbi_probe
"""
from __future__ import annotations

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "emu"))

import unicorn                                                    # noqa: E402
from unicorn import UC_HOOK_BLOCK                                 # noqa: E402

import tts_run as T                                               # noqa: E402

R = unicorn.arm_const

FC_ENTRY = T.V_FUN_5FC04          # ELF 0x4fc04 (Ghidra 0x5fc04)
FC_END = FC_ENTRY + 0xF04         # next function starts at Ghidra 0x60b08
FC_EPILOGUE = FC_ENTRY + 0x24     # 0x4fc28: `add sp, sp, #0x4c` -- the exit path

# state (param_1) layout, see report_prosody.md Sec.6
S_NODES = 0x10                    # node array base
S_COUNT = 0x14                    # node count
S_CUR = 0x18                      # current node
S_FIN = 0x1C                      # finished
S_BEST = 0x0C                     # param_1[3]: "best" back-pointer / array ptr

NODE_STRIDE = 0xD4
N_DESC = 0x00                     # +0x00 descriptor (start/count of the unit list)
N_CTX1 = 0x04                     # +0x04 96-byte context vector (left)
N_CTX2 = 0x64                     # +0x64 96-byte context vector (right)
N_JOIN = 0xC4                     # +0xc4 join-cost function pointer
N_FORCED = 0xC8                   # +0xc8 forced/boundary flag (tb_min_distance)
N_CAND = 0xCC                     # +0xcc candidate array
N_NCAND = 0xD0                    # +0xd0 candidate count

C_SIZE = 0x14                     # candidate entry stride


class ViterbiProbe(T.Oracle):
    def __init__(self, args):
        super().__init__(args)
        self.fc_call = -1
        self.fc_state = 0
        self.fc_seen = {}
        self.events = []
        self.blocks = []
        self.node_ctx = {}
        self.calls = []
        self._records = None
        self._rec_base = 0
        self.payload = 0
        self.force_pcs = set()

    # -- driven by the block hook -----------------------------------------
    def _read_uint(self, addr):
        try:
            return self.lib.u32(addr)
        except Exception:
            return None

    def _snapshot(self, kind, pc, force=False):
        lib = self.lib
        st = self.fc_state
        base = self._read_uint(st + S_NODES)
        nn = self._read_uint(st + S_COUNT)
        if not base or not nn or not (0 < nn < 4096):
            return
        cur = self._read_uint(st + S_CUR)
        fin = self._read_uint(st + S_FIN)
        if self.fc_call not in self.node_ctx:
            self._ensure_records()
            self.payload = self._read_uint(st) or 0
            self.node_ctx[self.fc_call] = self._dump_nodes(base, nn)
            self.calls.append({
                "call": self.fc_call, "state": st, "nodes": nn,
                "target_fn": self._read_uint(st + 0x08),
                "debug_fn": self._read_uint(st + 0x04),
                "best": self._read_uint(st + S_BEST),
                "cur": cur, "fin": fin,
            })
        for i in range(nn):
            node = base + i * NODE_STRIDE
            ptr = self._read_uint(node + N_CAND)
            cnt = self._read_uint(node + N_NCAND)
            if not force and self.fc_seen.get(i) == (ptr, cnt):
                continue
            self.fc_seen[i] = (ptr, cnt)
            ents = self._entries(ptr, cnt)
            self.events.append({
                "call": self.fc_call, "pc": pc, "kind": kind, "node": i,
                "ptr": ptr, "count": cnt, "n_nodes": nn, "cur_node": cur,
                "fin": fin, "forced": self._read_uint(node + N_FORCED),
                "desc": self._read_uint(node + N_DESC),
                "ents": ents,
            })

    def _ensure_records(self):
        """Load the raw 36-byte record table once (payload+0x14, 0x24 stride)."""
        if self._records is not None:
            return
        if not self.ddb:
            self._records, self._rec_base = b"", 0
            return
        lib = self.lib
        n = self.ddb["index_table"]
        # total number of units = sum of the section-A counts
        try:
            names = bytes(lib.uc.mem_read(self.ddb["name_table"], 1601 * 0x14))
            tot = sum(struct.unpack_from("<I", names, i * 0x14 + 16)[0]
                      for i in range(1601))
            base = self.ddb["records"]
            self._records = bytes(lib.uc.mem_read(base, tot * 0x24))
            self._rec_base = base
        except Exception as e:
            self.log(f"record table unavailable: {type(e).__name__}: {e}")
            self._records, self._rec_base = b"", 0
        del n

    def _entries(self, ptr, cnt):
        """Candidate entries plus the two raw record bytes the keep rule reads.

        `+3` of the candidate's left record and `+5` of its right record index the
        phone-descriptor table at `payload+0x1c` (32-byte stride); dumping the byte
        values here makes the rule checkable offline.
        """
        if not ptr or not cnt or cnt > 100000:
            return []
        try:
            raw = bytes(self.lib.uc.mem_read(ptr, cnt * C_SIZE))
        except Exception:
            return []
        rec, recs = self._records, self._rec_base
        out = []
        for k in range(cnt):
            e = raw[k * C_SIZE:(k + 1) * C_SIZE]
            idx = struct.unpack_from("<i", e, 0xC)[0]
            b3 = b5 = -1
            if recs and 0 <= idx:
                try:
                    b3 = rec[recs + idx * 0x24 + 3]
                    b5 = rec[recs + (idx + 1) * 0x24 + 5]
                except Exception:
                    pass
            out.append((struct.unpack_from("<i", e, 0)[0], e[4], e[5],
                        struct.unpack_from("<i", e, 8)[0], idx,
                        struct.unpack_from("<I", e, 0x10)[0], b3, b5))
        return out

    def _dump_nodes(self, base, nn):
        """Per node: context vectors (raw + decoded pointer slots) and flags."""
        lib = self.lib
        out = []
        for i in range(nn):
            node = base + i * NODE_STRIDE
            try:
                raw = bytes(lib.uc.mem_read(node + N_CTX1, 0xC0))
            except Exception:
                raw = b""
            slots = {}
            for off in (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20,
                        0x24, 0x28, 0x2C, 0x30, 0x34, 0x38, 0x3C, 0x40, 0x44,
                        0x48, 0x4C, 0x50, 0x54, 0x58, 0x5C):
                v = struct.unpack_from("<I", raw, off)[0] if len(raw) >= off + 4 else 0
                s = self._try_cstr(v)
                if s is not None:
                    slots["%02x" % off] = s
                slots["b%02x" % off] = raw[off] if len(raw) > off else None
            out.append({
                "node": i, "desc": self._read_uint(node + N_DESC),
                "forced": self._read_uint(node + N_FORCED),
                "join_fn": self._read_uint(node + N_JOIN),
                "ctx": raw.hex(), "slots": slots,
            })
        return out

    # -- hook installation -------------------------------------------------
    def install_hooks(self):
        super().install_hooks()
        uc = self.lib.uc

        def on_block(ucu, address, size, user):
            if address == FC_ENTRY:
                self.fc_call += 1
                self.fc_state = ucu.reg_read(R.UC_ARM_REG_R0)
                self.fc_seen = {}
                self.blocks.append([])
                self._snapshot("entry", address)
                return
            if self.fc_call < 0:
                return
            self.blocks[-1].append(address)
            if address in self.force_pcs:
                self._snapshot("forced", address, force=True)
            else:
                self._snapshot("block", address)
            if address == FC_EPILOGUE:
                self._snapshot("exit", address, force=True)

        self.hooks.append(uc.hook_add(UC_HOOK_BLOCK, on_block,
                                      begin=FC_ENTRY, end=FC_END))

    # -- artefacts ---------------------------------------------------------
    def write_probe_artefacts(self, outdir):
        def w(name, text):
            with open(os.path.join(outdir, name), "w") as fh:
                fh.write(text)

        buf = ["# call\tpc\tkind\tnode\tcount\tn_nodes\tcur_node\tfin\tforced\tdesc"
               "\tentries(t:target:tot:f4:f5:bp:b3:b5)"]
        for ev in self.events:
            ents = ",".join("%d:%d:%d:%d:%d:%d:%d:%d" % e for e in ev["ents"])
            buf.append("\t".join(str(x) for x in (
                ev["call"], "0x%x" % ev["pc"], ev["kind"], ev["node"],
                ev["count"], ev["n_nodes"], ev["cur_node"], ev["fin"],
                ev["forced"], ev["desc"])) + "\t" + ents)
        w("viterbi_events.tsv", "\n".join(buf) + "\n")

        buf = ["# call\tbasic blocks executed in FUN_0005fc04 (in order)"]
        for i, seq in enumerate(self.blocks):
            buf.append("%d\t%s" % (i, ",".join("0x%x" % a for a in seq)))
        w("viterbi_blocks.tsv", "\n".join(buf) + "\n")

        buf = ["# FUN_0005fc04 call records"]
        for c in self.calls:
            buf.append("# call %d state=0x%x nodes=%d target_fn=0x%x debug_fn=0x%x "
                       "cur=%s fin=%s" % (c["call"], c["state"], c["nodes"],
                                          c["target_fn"] or 0, c["debug_fn"] or 0,
                                          c["cur"], c["fin"]))
            for n in self.node_ctx[c["call"]]:
                buf.append("node\t%d\tdesc=0x%x\tforced=%s\tjoin_fn=0x%x\t%s" % (
                    n["node"], n["desc"] or 0, n["forced"], n["join_fn"] or 0,
                    n["ctx"]))
                buf.append("node\t%d\tslots\t%s" % (
                    n["node"], " ".join("%s=%r" % (k, v) for k, v in sorted(
                        n["slots"].items()) if len(k) == 2)))
        w("viterbi_nodes.txt", "\n".join(buf) + "\n")

        print(f"[probe] {len(self.calls)} FUN_0005fc04 calls, "
              f"{len(self.events)} array mutations")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--engine", default="out/libs/kendra/libttsivonavoice.so")
    ap.add_argument("--plugin", default="out/libs/kendra/libvoice_en_us_kendra.so")
    ap.add_argument("--cert", default="out/certs/ivona_certificate_decoded.txt")
    ap.add_argument("--obb", default="IVONA 2/IVONA Kendra US English "
                   "beta_v1.6.23.422_apkfab.com/Android/obb/"
                   "com.ivona.tts.voicebeta.eng.usa.kendra/"
                   "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")
    ap.add_argument("--dat-dir", default="out/obb")
    ap.add_argument("--plugin-base", type=lambda s: int(s, 0), default=0x20000000)
    ap.add_argument("--sentence", default="Hello world this is a test")
    ap.add_argument("--out-dir", default="out/oracle/viterbi_probe")
    ap.add_argument("--level", type=int, default=3)
    ap.add_argument("--max-chunks", type=int, default=400)
    ap.add_argument("--heap-size", type=lambda s: int(s, 0), default=0x10000000)
    ap.add_argument("--deterministic", action="store_true", default=True)
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--no-pcm", action="store_true")
    ap.add_argument("--force-pcs", default="0x4fe38,0x4fe50,0x502d4,0x50870,0x50968,"
                    "0x50644,0x4fc28",
                    help="PCs (hex, comma separated) at which all node arrays are "
                         "snapshotted unconditionally")
    ap.add_argument("--fs-root", default=None)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--trace-filter", default=None)
    ap.add_argument("--trace-alloc", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--ret-probe", action="store_true")
    ap.add_argument("--trace-funcs", action="store_true",
                    help="print every instrumented pipeline entry (base class)")
    ap.add_argument("--trace-dumps", action="store_true")
    ap.add_argument("--trace-engine-dump",
                    default="out/ghidra_dump/libttsivonavoice.c")
    ap.add_argument("--trace-plugin-dump", default="out/ghidra_dump/libvoice_kendra.c")
    args = ap.parse_args(argv)

    outdir = os.path.join(args.root, args.out_dir)
    os.makedirs(outdir, exist_ok=True)
    if not args.trace_dumps:
        args.trace_engine_dump = None
        args.trace_plugin_dump = None
    import armemu                                                # noqa: E402
    armemu.HEAP_SIZE = args.heap_size
    o = ViterbiProbe(args)
    o.force_pcs = {int(x, 0) for x in args.force_pcs.split(",") if x}
    o.setup_module()
    if args.trace:
        o.lib.set_trace(True, args.trace_filter)
    o.install_hooks()
    ok = o.do_init() and o.do_load_voice()
    if ok and args.level >= 2:
        ok = o.do_streamer_start(args.sentence)
    if ok and args.level >= 3 and not args.no_pcm:
        o.do_synth(os.path.join(outdir, "probe.pcm"))
    o.write_probe_artefacts(outdir)
    print(f"[probe] artefacts in {outdir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
