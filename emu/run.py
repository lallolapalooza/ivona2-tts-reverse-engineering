#!/usr/bin/env python3
"""run.py -- drive a single function of an ARM32 bionic .so under Unicorn.

Examples
--------
ISEF decryptor (libttsivonavoice.so):

    python emu/run.py --lib out/libs/kendra/libttsivonavoice.so \
        --func FUN_000346d4 --arg str:out/obb/lang_en_us.dat \
        --out '[r0+0x1c]:[r0+0x14]:/tmp/emu_plain.bin' \
        --verify out/obb/lang_en_us.dec.bin

Gap/window decode probe with a per-instruction call trace:

    python emu/run.py --lib .../libttsivonavoice.so --func FUN_000685c4 \
        --arg '@db' --arg '@unit' --trace --trace-funcs out/ghidra_dump/libttsivonavoice.c

Argument/`--out` expressions may use:
  * integers (`123`, `0x1f`), registers (`r0`..`r12`, `sp`, `lr`, `pc`),
  * `@stdin` / `@heap` / `@stack` and `@NAME` from `--bind NAME=LIST-INDEX`,
  * dereference `[expr]` (u32), and `+ - *` arithmetic.

`--arg` values are one of `str:TEXT`, `file:PATH`, `hex:HEXBYTES`, or an
expression (passed as the raw integer).
"""
import argparse
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from armemu import ArmLib, EmuError  # noqa: E402

try:
    from unicorn import UC_HOOK_BLOCK
    from unicorn.unicorn_const import UcError
except Exception:  # pragma: no cover
    UC_HOOK_BLOCK = None
    UcError = Exception


# ------------------------------------------------------------------ expressions
_TOKEN = re.compile(r"\s*(0[xX][0-9a-fA-F]+|\d+|[A-Za-z_@][A-Za-z0-9_]*|[-+*\[\]()])")


class ExprParser:
    def __init__(self, text, env):
        self.toks = []
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if not m:
                raise ValueError(f"bad expression {text!r} at {pos}")
            self.toks.append(m.group(1))
            pos = m.end()
        self.i = 0
        self.env = env

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want=None):
        t = self.peek()
        if t is None:
            raise ValueError("unexpected end of expression")
        self.i += 1
        if want is not None and t != want:
            raise ValueError(f"expected {want!r}, got {t!r}")
        return t

    def parse(self):
        v = self.expr()
        if self.peek() is not None:
            raise ValueError(f"trailing tokens {self.toks[self.i:]}")
        return v & 0xffffffff

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            r = self.term()
            v = v + r if op == "+" else v - r
        return v

    def term(self):
        v = self.unary()
        while self.peek() == "*":
            self.take()
            v = v * self.unary()
        return v

    def unary(self):
        t = self.peek()
        if t == "-":
            self.take()
            return -self.unary()
        if t == "[":
            self.take("[")
            addr = self.expr()
            self.take("]")
            return self.env["__deref"](addr)
        return self.primary()

    def primary(self):
        t = self.take()
        if t == "(":
            v = self.expr()
            self.take(")")
            return v
        if t.startswith("0x") or t.startswith("0X") or t.isdigit():
            return int(t, 0)
        if t in self.env:
            return self.env[t]
        raise ValueError(f"unknown name {t!r}")


def evaluate(lib, text, env=None):
    from armemu import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                        UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
                        UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
    names = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10",
             "r11", "r12", "sp", "lr", "pc"]
    ids = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
           UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
           UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
           UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC]
    base = {n: lib.uc.reg_read(i) for n, i in zip(names, ids)}
    base["@heap"] = lib.heap_ptr
    base["__deref"] = lib.u32
    if env:
        base.update(env)
    return ExprParser(text, base).parse()


# ------------------------------------------------------------------ ghidra map
FUNC_LINE = re.compile(r"^//\s*----- ([0-9a-fA-F]+) : ([A-Za-z_][\w.]*) -----")


def load_ghidra_funcs(path, offset=0x10000):
    funcs = {}
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = FUNC_LINE.match(line)
            if m:
                funcs[int(m.group(1), 16) - offset] = m.group(2)
    return funcs


# ------------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", required=True, help="ARM32 .so to load")
    ap.add_argument("--func", help="target: 0xVADDR | FUN_000xxxxx (Ghidra) | symbol name")
    ap.add_argument("--ghidra", action="store_true",
                    help="treat a bare hex --func as a Ghidra address (+0x10000 delta)")
    ap.add_argument("--arg", action="append", default=[],
                    help="argument: str:.. | file:.. | hex:.. | EXPR")
    ap.add_argument("--stdin", help="load FILE into guest memory; binds @stdin "
                                    "(also becomes arg0 when no --arg is given)")
    ap.add_argument("--out", action="append", default=[],
                    help="ADDR_EXPR:LEN_EXPR[:PATH] -- dump guest memory after the call")
    ap.add_argument("--verify", help="compare the single --out dump against FILE")
    ap.add_argument("--root", help="chdir here before probing (host path prefix)")
    ap.add_argument("--env", action="append", default=[],
                    help="NAME=VALUE for the guest getenv() table")
    ap.add_argument("--stdout", help="capture guest stdout to this file")
    ap.add_argument("--trace", nargs="?", const="", default=None, metavar="REGEX",
                    help="log every imported call (optionally filtered by REGEX)")
    ap.add_argument("--trace-funcs", metavar="GHIDRA_DUMP.c",
                    help="log entry into each named function of a Ghidra dump")
    ap.add_argument("--trace-funcs-filter", help="only log functions matching this regex")
    ap.add_argument("--shadow", metavar="ADDR:LEN",
                    help="log guest reads/writes touching this range")
    ap.add_argument("--words", metavar="EXPR:N",
                    help="print N words of guest memory at EXPR after the call")
    ap.add_argument("--str", action="append", default=[],
                    help="print the C string at EXPR after the call")
    ap.add_argument("--peek", action="append", default=[],
                    help="hex+ascii dump 64 bytes at EXPR after the call")
    ap.add_argument("--timeout", type=float, default=0, help="wall-clock emulation budget in seconds (0 = unlimited)")
    ap.add_argument("--count", type=int, default=0, help="instruction budget")
    ap.add_argument("--list-exports", action="store_true")
    ap.add_argument("--list-imports", action="store_true")
    args = ap.parse_args(argv)

    libpath = os.path.abspath(args.lib)
    if args.root:
        os.chdir(args.root)

    cap = [] if args.stdout else None

    lib = ArmLib(libpath)
    lib.capture_stdout = cap
    for kv in args.env:
        k, _, v = kv.partition("=")
        lib.env[k] = v

    if args.list_exports:
        for n, a in sorted(lib.exports.items()):
            print(f"{a:#010x} {n}")
        return 0
    if args.list_imports:
        for n in sorted(lib.imports):
            print(n)
        return 0
    if not args.func:
        ap.error("--func is required (or use --list-exports/--list-imports)")

    # ---- resolve the target ------------------------------------------------
    f = args.func
    if f.startswith("FUN_") or f.startswith("LAB_") or args.ghidra:
        vaddr = int(f.replace("FUN_", "").replace("LAB_", ""), 16) - 0x10000
    elif re.fullmatch(r"0[xX][0-9a-fA-F]+", f):
        vaddr = int(f, 16)
    elif re.fullmatch(r"\d+", f):
        vaddr = int(f)
    else:
        if f not in lib.exports:
            ap.error(f"no such export {f!r}; try --list-exports")
        vaddr = lib.exports[f]
    print(f"[func] {f} -> {vaddr:#x}")

    # ---- bind stdin --------------------------------------------------------
    extra = {}
    stdin_addr = None
    if args.stdin:
        data = open(args.stdin, "rb").read()
        stdin_addr = lib.alloc_data(data)
        extra["@stdin"] = stdin_addr
        print(f"[stdin] {args.stdin} ({len(data)} B) -> {stdin_addr:#x}")

    # ---- optional traces ---------------------------------------------------
    if args.trace is not None:
        lib.set_trace(True, args.trace or None)

    funcs = {}
    if args.trace_funcs:
        funcs = load_ghidra_funcs(args.trace_funcs)
        seen = set()
        filt = re.compile(args.trace_funcs_filter) if args.trace_funcs_filter else None

        def on_block(uc, address, size, user):
            name = funcs.get(address)
            if name and address not in seen:
                seen.add(address)
                if not filt or filt.search(name):
                    print(f"[fun ] {address:#08x} {name}")

        lib.uc.hook_add(UC_HOOK_BLOCK, on_block)
        print(f"[trace-funcs] {len(funcs)} functions from {args.trace_funcs}")

    if args.shadow:
        lo_s, _, ln_s = args.shadow.partition(":")
        lo, ln = int(lo_s, 0), int(ln_s, 0)
        from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
        from armemu import UC_ARM_REG_PC

        def on_mem(uc, access, address, size, value, user):
            pc = uc.reg_read(UC_ARM_REG_PC)
            print(f"[mem ] {'W' if access == UC_MEM_WRITE else 'R'} {address:#x}+{size} "
                  f"pc={pc:#x} val={value:#x}")

        lib.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, on_mem, begin=lo,
                        end=lo + ln - 1)
        print(f"[shadow] watching {lo:#x}..{lo+ln:#x}")

    # ---- build arguments ---------------------------------------------------
    if not args.arg and stdin_addr is not None:
        args.arg = ["@stdin"]
    argv_vals = []
    for spec in args.arg:
        kind, _, val = spec.partition(":")
        if kind == "str":
            p = lib.alloc_str(val)
            print(f"[arg ] str {val!r} -> {p:#x}")
            argv_vals.append(p)
        elif kind in ("file", "filez"):
            data = open(val, "rb").read()
            if kind == "filez":
                data += b"\x00"
            p = lib.alloc_data(data)
            print(f"[arg ] {kind} {val} ({len(data)} B) -> {p:#x}")
            argv_vals.append(p)
        elif kind == "hex":
            p = lib.alloc_data(bytes.fromhex(val))
            argv_vals.append(p)
        else:
            v = evaluate(lib, spec, extra)
            print(f"[arg ] {spec} = {v:#x}")
            argv_vals.append(v)
    if args.arg and stdin_addr is not None:
        pass

    # ---- run ---------------------------------------------------------------
    rc = 0
    try:
        ret = lib.call(vaddr, argv_vals, timeout=int(args.timeout * 1_000_000),
                         count=args.count)
    except EmuError as e:
        print(f"[fatal] EmuError: {e}")
        return 2
    except UcError as e:
        r = lib.regs()
        print(f"[fatal] UcError: {e}")
        print("[state] " + " ".join(f"{k}={v:#x}" for k, v in r.items()))
        return 3
    print(f"[ret ] r0 = {ret:#x} ({ret})")
    for k, v in lib.regs().items():
        print(f"        {k} = {v:#010x}")

    # ---- post-call extraction ---------------------------------------------
    if args.words:
        spec, _, n_s = args.words.rpartition(":")
        addr = evaluate(lib, spec, extra)
        for i in range(int(n_s)):
            print(f"[word] [{addr:#x} + {i}] = {lib.u32(addr + 4*i):#010x}")

    for spec in args.str:
        addr = evaluate(lib, spec, extra)
        try:
            s = lib.cstr(addr, 512)
        except Exception:
            s = b""
        print(f"[str ] {spec} = {addr:#x} -> {s!r}")

    for spec in args.peek:
        addr = evaluate(lib, spec, extra)
        data = bytes(lib.uc.mem_read(addr, 64))
        print(f"[peek] {addr:#x}: {data.hex()}")
        print(f"[peek] {addr:#x}: " +
              "".join(chr(c) if 32 <= c < 127 else "." for c in data))

    saved = []
    for spec in args.out:
        parts = spec.split(":")
        if len(parts) < 2:
            ap.error(f"--out wants ADDR:LEN[:PATH], got {spec!r}")
        addr = evaluate(lib, parts[0], extra)
        length = evaluate(lib, parts[1], extra)
        path = parts[2] if len(parts) > 2 else None
        data = bytes(lib.uc.mem_read(addr, length))
        saved.append(data)
        print(f"[out ] {addr:#x}+{length} ({len(data)} B)")
        if path:
            with open(path, "wb") as fh:
                fh.write(data)
            print(f"[out ] wrote {path}")

    if args.verify:
        ref = open(args.verify, "rb").read()
        got = b"".join(saved)
        ok = got == ref
        print(f"[verify] {args.verify}: {'MATCH' if ok else 'MISMATCH'} "
              f"({len(got)} B vs {len(ref)} B)")
        if not ok:
            n = min(len(got), len(ref))
            first = next((i for i in range(n) if got[i] != ref[i]), n)
            print(f"[verify] first differing byte at {first:#x}")
            rc = 4

    if lib.unknown_calls:
        print("[stub ] unhandled imports: " +
              ", ".join(f"{k}x{v}" for k, v in lib.unknown_calls.most_common()))

    if cap is not None:
        blob = b"".join(cap)
        with open(args.stdout, "wb") as fh:
            fh.write(blob)
        print(f"[stdout] {args.stdout} ({len(blob)} B)")

    return rc


if __name__ == "__main__":
    sys.exit(main())
