#!/usr/bin/env python3
"""Diff `scripts/diphone_vec.py` (the `FUN_0005f1dc` port) against the real engine.

`libttsivonavoice.so` is executed under Unicorn (`emu/armemu.py`); the diphonedb
payload `FUN_0005f1dc` needs is synthesised in guest memory from the OBB itself
(payload[6] = section D, payload[7] = section E), so no voice load is required.
The engine's 96-byte output is compared byte-for-byte with the Python port for a
sample of section-C records.

    python3 scripts/probe_record_vec.py                 # 200 records
    python3 scripts/probe_record_vec.py --n 2000 --seed 7
"""
from __future__ import annotations

import argparse
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "emu"))
sys.path.insert(0, os.path.join(ROOT, "refimpl"))
sys.path.insert(0, HERE)

from armemu import ArmLib                                  # noqa: E402
import cdxv                                                # noqa: E402
import diphone_vec                                         # noqa: E402

SO = os.path.join(ROOT, "out/libs/kendra/libttsivonavoice.so")
FUN_5F1DC = 0x4F1DC                                        # ELF vaddr (Ghidra 0x5f1dc - 0x10000)
DEFAULT_OBB = os.path.join(
    ROOT, "IVONA 2/IVONA Kendra US English beta_v1.6.23.422_apkfab.com/Android/obb/"
    "com.ivona.tts.voicebeta.eng.usa.kendra/"
    "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--obb", default=DEFAULT_OBB)
    a = ap.parse_args(argv)

    r = cdxv.OBBReader(a.obb)
    D = r.d_pool()
    E = r.phonemes()
    port = diphone_vec.record_decoder(r)

    lib = ArmLib(SO, verbosity=0)
    d_ptr = lib.alloc_data(D)
    # section E as the engine sees it: 58 x 32-byte NUL-padded name records
    e_raw = bytearray(32 * len(E))
    for i, nm in enumerate(E):
        b = nm.encode("latin1")[:31]
        e_raw[i * 32:i * 32 + len(b)] = b
    e_ptr = lib.alloc_data(bytes(e_raw))
    payload = lib.alloc(0x24)
    lib.uc.mem_write(payload + 0x18, struct.pack("<I", d_ptr))
    lib.uc.mem_write(payload + 0x1C, struct.pack("<I", e_ptr))
    out = lib.alloc(0x60)

    rng = random.Random(a.seed)
    units = sorted(rng.sample(range(r.n_entries), min(a.n, r.n_entries)))
    bad = 0
    for u in units:
        rec = r.c_record(u)
        lib.uc.mem_write(out, b"\x00" * 0x60)
        rec_ptr = lib.alloc_data(rec)
        lib.call(FUN_5F1DC, [payload, rec_ptr, out], timeout=0)
        got = bytes(lib.uc.mem_read(out, 0x60))
        want = port.vector(u).b
        # the string slots hold guest pointers, so compare those through the
        # port's resolved names where the engine's pointer lands in E.
        diffs = [i for i in range(0x60) if got[i] != want[i]
                 and i not in diphone_vec.STR_SLOTS
                 and not any(i in range(s, s + 4) for s in diphone_vec.STR_SLOTS)]
        if diffs:
            bad += 1
            if bad <= 5:
                print("MISMATCH unit %d at %s" % (u, [hex(d) for d in diffs[:12]]))
                print("  engine %s" % got.hex())
                print("  model  %s" % want.hex())
        else:
            # compare the string slots by resolved name
            for off in diphone_vec.STR_SLOTS:
                ptr = struct.unpack_from("<I", got, off)[0]
                eng = "?"
                if e_ptr <= ptr < e_ptr + len(e_raw):
                    eng = e_raw[ptr - e_ptr:ptr - e_ptr + 32].split(b"\x00")[0].decode("latin1")
                else:
                    eng = "@%#x" % ptr
                if eng != port.vector(u).st(off):
                    bad += 1
                    if bad <= 5:
                        print("STRING mismatch unit %d slot %#x engine=%r model=%r"
                              % (u, off, eng, port.vector(u).st(off)))
                    break
    print("[record_vec] %d/%d records byte-identical (numeric slots) + string slots"
          % (len(units) - bad, len(units)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
