#!/usr/bin/env python3
"""Dump the four arguments of every plug-in target-cost call
(`FUN_00031234(struct*, struct*, ctx*, ctx*)"`) during a real engine run.

The engine's Viterbi calls the graph node's cost entry point (plug-in
`FUN_00031234` = ELF vaddr 0x21234, mapped at `--plugin-base + 0x21234`) once per
(candidate pair, context) evaluation.  Logging the *actual pointers and bytes*
answers what the first/last Viterbi node is scored with, which the
`unit_feature_vectors.tsv` capture (one vector per `FUN_00060ed4` call on the
*item* chain) does not necessarily expose.

Output: `out/edge_probe/target_cost_calls.tsv`

    call  ret  ctx_l  ctx_r  rec_l  rec_r  v_l  v_r  c_l  c_r
where `v_*`/`c_*` are the 96-byte hex blobs of the record and context vectors and
`ret` is the function's integer result (read at the return address, which is
unique per call site).

    ~/venvs/re/bin/python scripts/probe_edge_nodes.py [--sentence "..."] [--max 4000]
"""
from __future__ import annotations

import argparse
import os
import sys
import types

import unicorn

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "emu"))

import armemu                                                     # noqa: E402
from tts_run import Oracle                                        # noqa: E402

TC_ELF = 0x21234                       # plug-in FUN_00031234 (Ghidra 0x31234)
OBB_DEFAULT = ("IVONA 2/IVONA Kendra US English "
               "beta_v1.6.23.422_apkfab.com/Android/obb/"
               "com.ivona.tts.voicebeta.eng.usa.kendra/"
               "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")


class EdgeProbe(Oracle):
    def __init__(self, args):
        super().__init__(args)
        self.calls = []
        self._pending = []             # (call_index,)
        self._ret_hooks = set()

    def install_hooks(self):
        super().install_hooks()
        lib = self.lib
        base = self.args.plugin_base
        R = unicorn.arm_const
        addr = base + TC_ELF
        maxc = self.args.max_calls

        def on_entry(uc, address, size, user):
            if len(self.calls) >= maxc:
                return
            lr = uc.reg_read(R.UC_ARM_REG_LR)
            idx = len(self.calls)
            self.calls.append({
                "r": [uc.reg_read(R.UC_ARM_REG_R0), uc.reg_read(R.UC_ARM_REG_R1),
                      uc.reg_read(R.UC_ARM_REG_R2), uc.reg_read(R.UC_ARM_REG_R3)],
                "ret": None, "lr": lr,
            })
            self._pending.append(idx)
            if lr not in self._ret_hooks:
                self._ret_hooks.add(lr)
                lib.uc.hook_add(unicorn.UC_HOOK_CODE, on_ret, begin=lr, end=lr)

        def on_ret(uc, address, size, user):
            if self._pending:
                idx = self._pending.pop()
                self.calls[idx]["ret"] = uc.reg_read(R.UC_ARM_REG_R0)

        self.hooks.append(lib.uc.hook_add(unicorn.UC_HOOK_CODE, on_entry,
                                          begin=addr, end=addr))

    def dump(self, path):
        lib = self.lib
        with open(path, "w") as fh:
            fh.write("# call\tret\tctx_l\tctx_r\trec_l\trec_r\t"
                     "rec_l_hex\trec_r_hex\tctx_l_hex\tctx_r_hex\n")
            for i, c in enumerate(self.calls):
                r = c["r"]
                try:
                    blobs = [bytes(lib.uc.mem_read(p, 0x60)) for p in r]
                except Exception:
                    blobs = [b""] * 4
                ret = c["ret"]
                ret = -1 if ret is None else (ret - 0x100000000 if ret >= 0x80000000
                                              else ret)
                fh.write("\t".join([
                    str(i), str(ret)] + [hex(x) for x in r] +
                    [b.hex() for b in blobs]) + "\n")


def make_args(sentence, out_dir, max_calls):
    a = types.SimpleNamespace()
    a.root = ROOT
    a.engine = "out/libs/kendra/libttsivonavoice.so"
    a.plugin = "out/libs/kendra/libvoice_en_us_kendra.so"
    a.cert = "out/certs/ivona_certificate_decoded.txt"
    a.obb = OBB_DEFAULT
    a.dat_dir = "out/obb"
    a.fs_root = None
    a.plugin_base = 0x20000000
    a.trace_alloc = 0
    a.timeout = 0
    a.heap_size = 0x10000000
    a.out_dir = out_dir
    a.level = 3
    a.max_chunks = 400
    a.sentence = sentence
    a.ret_probe = False
    a.trace = False
    a.trace_filter = None
    a.trace_funcs = False
    a.trace_dumps = False
    a.trace_engine_dump = None
    a.trace_plugin_dump = None
    a.deterministic = True
    a.no_pcm = False
    a.env = []
    a.max_calls = max_calls
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sentence", default="Hello world this is a test")
    ap.add_argument("--out-dir", default="out/edge_probe")
    ap.add_argument("--max", dest="max_calls", type=int, default=4000)
    a = ap.parse_args(argv)
    args = make_args(a.sentence, a.out_dir, a.max_calls)
    out = os.path.join(ROOT, a.out_dir)
    os.makedirs(out, exist_ok=True)
    armemu.HEAP_SIZE = args.heap_size
    o = EdgeProbe(args)
    o.setup_module()
    o.install_hooks()
    ok = o.do_init() and o.do_load_voice()
    if ok:
        ok = o.do_streamer_start(args.sentence)
    if ok:
        o.do_synth(os.path.join(out, "kendra_hello.pcm"))
    o.write_artefacts(out)
    o.dump(os.path.join(out, "target_cost_calls.tsv"))
    print(f"[edge] captured {len(o.calls)} FUN_00031234 calls -> "
          f"{os.path.join(a.out_dir, 'target_cost_calls.tsv')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
