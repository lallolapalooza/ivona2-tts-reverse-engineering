#!/usr/bin/env python3
"""Locate the code that assigns the word feature `gpos` (the tag the engine
reads into 96-byte vector slots 0x30/0x38/0x40).

Method
------
Run the real engine+plug-in under Unicorn (`emu/tts_run.py` machinery) and:

1. hook memory *reads* of the plug-in's closed-class word tables and of the
   string pool they live in (``.rodata`` 0x60000..0x62000 and the pointer
   tables in ``.data.rel.ro`` 0x2e4000..0x2e6400; ELF vaddrs, added to
   ``--plugin-base``);
2. hook the engine's ``FUN_00026a54(container, name, value)`` (*"set VAL"*) and
   log every call whose name argument contains ``gpos``.

Both give a PC (and LR) inside the deciding function; the plug-in's own Ghidra
function map (`out/ghidra_dump/libvoice_kendra.c`) names it.

    ~/venvs/re/bin/python scripts/probe_gpos.py [--sentence "..."]
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
import tts_run                                                    # noqa: E402
from tts_run import Oracle, G, load_ghidra_funcs                  # noqa: E402

RODATA_LO, RODATA_HI = 0x60000, 0x62000        # plug-in ELF vaddrs (strings)
TABLES_LO, TABLES_HI = 0x2EBB00, 0x2EC100      # the gpos word table (8-byte VALs)
PAIRS_LO, PAIRS_HI = 0xEA00, 0xF200            # the {word VAL*, 0x17} index array

OBB_DEFAULT = ("IVONA 2/IVONA Kendra US English "
               "beta_v1.6.23.422_apkfab.com/Android/obb/"
               "com.ivona.tts.voicebeta.eng.usa.kendra/"
               "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")


class GposProbe(Oracle):
    def __init__(self, args):
        super().__init__(args)
        self.reads = {}            # (pc, lr) -> count
        self.sets = []             # (name, lr)
        self._nread = 0

    def install_hooks(self):
        super().install_hooks()
        lib = self.lib
        base = self.args.plugin_base
        R = unicorn.arm_const
        maxread = self.args.max_read

        def on_mem(uc, access, address, size, value, user):
            if self._nread >= maxread:
                return
            self._nread += 1
            key = (uc.reg_read(R.UC_ARM_REG_PC), uc.reg_read(R.UC_ARM_REG_LR))
            self.reads[key] = self.reads.get(key, 0) + 1

        for lo, hi in ((RODATA_LO, RODATA_HI), (TABLES_LO, TABLES_HI),
                       (PAIRS_LO, PAIRS_HI)):
            self.hooks.append(lib.uc.hook_add(unicorn.UC_HOOK_MEM_READ, on_mem,
                                              begin=base + lo, end=base + hi - 1))

        setaddr = G(0x26a54)

        def on_set(uc, address, size, user):
            if len(self.sets) > 4000:
                return
            try:
                name = lib.cstr(uc.reg_read(R.UC_ARM_REG_R1)).decode("latin1")
            except Exception:
                return
            if "gpos" in name:
                self.sets.append((name, uc.reg_read(R.UC_ARM_REG_LR)))

        self.hooks.append(lib.uc.hook_add(unicorn.UC_HOOK_CODE, on_set,
                                          begin=setaddr, end=setaddr))


def attribute(funcs, addr, base):
    if addr < base:
        return "engine %#x" % addr
    off = addr - base
    best = None
    for a, n in funcs:
        if a <= off:
            best = (a, n)
        else:
            break
    if best is None:
        return "plug-in +%#x (unattributed)" % off
    return f"{best[1]} (elf {best[0]:#06x} +{off - best[0]:#x})"


def make_args(sentence, out_dir, max_read):
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
    a.max_read = max_read
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sentence", default="Hello world this is a test")
    ap.add_argument("--out-dir", default="out/gpos_probe")
    ap.add_argument("--max-read", type=int, default=200000)
    a = ap.parse_args(argv)

    args = make_args(a.sentence, a.out_dir, a.max_read)
    os.makedirs(os.path.join(ROOT, a.out_dir), exist_ok=True)
    armemu.HEAP_SIZE = args.heap_size
    o = GposProbe(args)
    o.setup_module()
    o.install_hooks()
    ok = o.do_init() and o.do_load_voice()
    if ok:
        ok = o.do_streamer_start(args.sentence)
    if ok:
        o.do_synth(os.path.join(ROOT, a.out_dir, "kendra_hello.pcm"))
    o.write_artefacts(os.path.join(ROOT, a.out_dir))

    funcs = sorted(load_ghidra_funcs(
        os.path.join(ROOT, "out/ghidra_dump/libvoice_kendra.c")).items())
    base = args.plugin_base
    print("\n== reads of the plug-in word tables / string pool ==")
    agg = {}
    for (pc, lr), c in o.reads.items():
        k = (attribute(funcs, pc, base), attribute(funcs, lr, base))
        agg[k] = agg.get(k, 0) + c
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:30]:
        print(f"  {v:8d}  pc={k[0]:48s} lr={k[1]}")
    print("\n== set-VAL calls carrying a gpos name ==")
    for name, lr in o.sets[:60]:
        print(f"  {name!r} <- lr={lr:#x} {attribute(funcs, lr, base)}")
    if not o.sets:
        print("  (none)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
