#!/usr/bin/env python3
"""probe_gap.py -- drive libttsivonavoice.so's real acoustic-unit decode path.

Chain (all real library code, only libc/stdio stubbed by the harness):

    FUN_0005f49c(vox_path)        -> CDXV container handle
    FUN_0005f064(cdxv)            -> diphonedb handle {cdxv, FILE*, codec}
                                     (runs the per-format codec init [0xd])
    FUN_0005ef70(db, index)       -> reads the 8-byte {u32 offset, u32 size}
                                     directory entry at `*(cdxv+0x14)+index*8`,
                                     fseek+fread from the huge .obb over stdio,
                                     then calls the format decoder `[0xf](db, buf)`.

Everything the decoder touches internally is logged: `--trace-funcs` prints each
named function of the Ghidra dump on first entry, which is the call trace the
gap-codec agent needs.

    python emu/probe_gap.py --obb "<path>/main.199...obb" --index 0 \
        --trace-funcs out/ghidra_dump/libttsivonavoice.c
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from armemu import ArmLib, EmuError          # noqa: E402
from run import load_ghidra_funcs             # noqa: E402

try:
    from unicorn import UC_HOOK_BLOCK
except Exception:                             # pragma: no cover
    UC_HOOK_BLOCK = 8

V_F49C = 0x4F49C     # FUN_0005f49c  CDXV parser
V_F064 = 0x4F064     # FUN_0005f064  diphonedb open (+codec init)
V_EF70 = 0x4EF70     # FUN_0005ef70  voxdb section/unit read + decode
V_EF00 = 0x4EE00     # FUN_0005ef00  diphonename lookup (optional)


def dump_wave(lib, w, index, out_path=None):
    """Decode the wave object FUN_0005ef70 returns (FUN_00062608 family).

    +0x04 sample rate, +0x08 frame count, +0x0c int offsets[], +0x10 void* pcm[]
    """
    rate = lib.u32(w + 4)
    n = lib.u32(w + 8)
    offs = lib.u32(w + 0xc)
    pcm = lib.u32(w + 0x10)
    print(f"[wave] obj={w:#x} rate={rate} frames={n} offs={offs:#x} pcm={pcm:#x}")
    if not (0 < n < 1 << 20):
        return
    total = 0
    blob = bytearray()
    for i in range(n):
        o = lib.u32(offs + 4 * i)
        p = lib.u32(pcm + 4 * i)
        ln = o if i == 0 else o - lib.u32(offs + 4 * (i - 1))
        total += ln
        if i < 4:
            print(f"       seg{i}: sample_off={o} len={ln} pcm={p:#x}")
        if p and 0 < ln < 1 << 22:
            try:
                blob += bytes(lib.uc.mem_read(p, ln * 2))
            except Exception:
                pass
    print(f"[wave] total {total} samples ({total*2} B, {total/22050.0:.3f} s @22050)")
    if blob:
        import struct as _s
        vals = _s.unpack(f"<{len(blob)//2}h", blob[:len(blob) // 2 * 2])
        nz = sum(1 for v in vals if v)
        pmin, pmax = min(vals), max(vals)
        print(f"[wave] pcm min={pmin} max={pmax} nonzero={nz}/{len(vals)} "
              f"first16={vals[:16]}")
        if out_path:
            path = out_path if "%d" not in out_path else out_path % index
            with open(path, "wb") as fh:
                fh.write(blob)
            print(f"[wave] wrote {path} ({len(blob)} B)")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", default="out/libs/kendra/libttsivonavoice.so")
    ap.add_argument("--obb", required=True)
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--count", type=int, default=0, help="max extra indices to run")
    ap.add_argument("--trace-funcs", help="Ghidra dump for a function-entry trace")
    ap.add_argument("--trace-filter", help="only log imports matching this regex")
    ap.add_argument("--trace", action="store_true", help="log every libc stub call")
    ap.add_argument("--timeout", type=int, default=0, help="emulation budget in MICROSECONDS (0 = unlimited)")
    ap.add_argument("--dump-pcm", help="write concatenated 16-bit PCM here (%%d = index)")
    args = ap.parse_args(argv)

    lib = ArmLib(os.path.abspath(args.lib))
    if args.trace:
        lib.set_trace(True, args.trace_filter)

    obb = os.path.abspath(args.obb)
    print(f"[obb ] {obb} ({os.path.getsize(obb)} B)")

    # ---- 1. CDXV container --------------------------------------------------
    p = lib.alloc_str(obb)
    cdxv = lib.call(V_F49C, [p], timeout=args.timeout)
    print(f"[cdxv] FUN_0005f49c -> {cdxv:#x}")
    if not cdxv:
        print("[fatal] CDXV parse failed")
        return 2
    names = ["path", "name", "mmap", "+0x0c", "+0x10", "secA@0x68", "secA_size",
             "+0x1c", "+0x20", "+0x24", "+0x28", "secC_cnt", "+0x30",
             "codec_init", "codec_destroy", "codec_decode", "secB", "secB_size"]
    for i, n in enumerate(names):
        print(f"        cdxv[{i:2d}] {n:<14} = {lib.u32(cdxv + 4*i):#010x}")

    base = lib.u32(lib.u32(cdxv + 8))
    print(f"        mmap base = {base:#x}")
    print(f"        sample_rate   = {lib.u32(cdxv + 0xc)}")
    print(f"        format_id     = {lib.u32(cdxv + 0x10)}")

    # ---- 2. diphonedb (+ per-format codec init) -----------------------------
    db = lib.call(V_F064, [cdxv], timeout=args.timeout)
    print(f"[db  ] FUN_0005f064 -> {db:#x}")
    if not db:
        print("[fatal] diphonedb open failed")
        return 2
    print(f"        db[0]=cdxv {lib.u32(db):#x}  db[1]=stdio {lib.u32(db+4):#x} "
          f" db[2]=codec {lib.u32(db+8):#x}")

    # ---- 3. directory entry + decode ---------------------------------------
    dtab = lib.u32(cdxv + 0x14)
    n = int(args.index)
    for k in range(n, n + 1 + args.count):
        off = lib.u32(dtab + 8 * k)
        size = lib.u32(dtab + 8 * k + 4)
        print(f"[unit] index {k}: dir entry off={off:#x} ({off}) size={size}")

        funcs = {}
        seen = []
        if args.trace_funcs:
            funcs = load_ghidra_funcs(args.trace_funcs)

            def on_block(uc, address, size2, user, _f=funcs, _s=seen):
                name = _f.get(address)
                if name and address not in _s:
                    _s.append(address)
                    print(f"    [fun] {address:#08x} {name}")

            h = lib.uc.hook_add(UC_HOOK_BLOCK, on_block)
        try:
            ret = lib.call(V_EF70, [db, k], timeout=args.timeout)
            print(f"[ret ] FUN_0005ef70(db,{k}) -> {ret:#x}")
        except EmuError as e:
            print(f"[fatal] EmuError: {e}")
            return 2
        except Exception as e:
            print(f"[fatal] {type(e).__name__}: {e}")
            return 3
        finally:
            if args.trace_funcs:
                lib.uc.hook_del(h)
        if args.trace_funcs:
            print(f"[calls] {len(seen)} distinct functions entered")

        if ret:
            dump_wave(lib, ret, k, args.dump_pcm)

    if lib.unknown_calls:
        print("[stub ] unhandled: " +
              ", ".join(f"{k}x{v}" for k, v in lib.unknown_calls.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
