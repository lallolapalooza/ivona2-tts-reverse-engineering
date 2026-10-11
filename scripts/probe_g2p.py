#!/usr/bin/env python3
"""Drive the Kendra plugin's LTS FSM (FUN_0003f594) and packed-lexicon lookup
(FUN_0003e2b4) under the Unicorn harness and print the resulting phone lists.

The plugin's LtsInfo/LexInfo description structs are normally built by
FUN_00033590 in .bss; we fabricate equivalent structs in scratch memory so the
probe is independent of the engine's startup path.

Usage:  ~/venvs/re/bin/python scripts/probe_g2p.py [word ...]
        ~/venvs/re/bin/python scripts/probe_g2p.py --lts word   # force LTS
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "emu"))
from armemu import ArmLib  # noqa: E402

SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")

# ------------------------------------------------------------------ addresses
# (file offset == link VMA for this ELF; Ghidra dump addresses are +0x10000.)
LETTER_TABLE = 0x1EDA48          # 27 u32 FSM entry points
FSM          = 0x1CC088          # 6-byte records
LTS_PHONES   = 0x2E88FC          # char*[N]  ("epsilon", ...)
LEX_BLOB     = 0x64BFC           # packed dictionary blob
LEX_BLOB_LEN = 0x166E60
LEX_PHONES   = 0x2E7FC4          # char*[N]  ("_epsilon_","k","ax",...)
LEX_ALT      = 0x2E80F4          # u8-index string table (syllable table)
LEX_POOL     = 0x2E84F8          # char*[256] key-fragment pool

FUN_LTS   = 0x3F594 - 0x10000    # FUN_0003f594
FUN_LEX   = 0x3E2B4 - 0x10000    # FUN_0003e2b4
FUN_CSTR  = 0x272C0 - 0x10000    # FUN_000272c0  VAL(tag 5) -> char*


def _fix_sprintf(lib):
    """armemu's printf stub ignores `.*` (star precision), which the plugin's
    LTS uses for its context window; install a correct minimal sprintf."""
    from armemu import UC_ARM_REG_SP

    def sprintf(uc, a):
        sp = uc.reg_read(UC_ARM_REG_SP)
        args = list(a)
        stack = [0]

        def nxt():
            if args:
                return args.pop(0)
            v = struct.unpack("<I", uc.mem_read(sp + stack[0] * 4, 4))[0]
            stack[0] += 1
            return v

        fmt = lib.cstr(a[1])
        out = bytearray()
        i = 0
        args = [a[2], a[3]]
        while i < len(fmt):
            c = fmt[i]
            if c != 0x25:
                out.append(c)
                i += 1
                continue
            i += 1
            prec = None
            while i < len(fmt) and (fmt[i] in b"-+ #0" or 0x30 <= fmt[i] <= 0x39 or fmt[i] == 0x2E):
                if 0x30 <= fmt[i] <= 0x39:
                    prec = (prec or 0) * 10 + (fmt[i] - 0x30)
                i += 1
            if i < len(fmt) and fmt[i] == 0x2A:  # '*'
                prec = nxt()
                i += 1
            if i >= len(fmt):
                break
            spec = fmt[i]
            if spec == ord("s"):
                p = nxt()
                s = lib.cstr(p) if p else b""
                out += s[:prec] if prec is not None else s
            elif spec in (ord("d"), ord("i"), ord("u"), ord("x"), ord("X")):
                v = nxt()
                out += (("%d" % struct.unpack("<i", struct.pack("<I", v))[0]) if spec in (ord("d"), ord("i"))
                        else ("%x" % v if spec == ord("x") else "%X" % v)).encode()
            elif spec == ord("c"):
                out += bytes([nxt() & 0xFF])
            elif spec == ord("%"):
                out.append(ord("%"))
            else:
                out.append(spec)
            i += 1
        lib.uc.mem_write(a[0], bytes(out) + b"\x00")
        return len(out)

    lib.add_import("sprintf", sprintf)


def valtag(lib, p):
    return struct.unpack("<H", lib.rd(p, 2))[0] if p else 0


def walk_list(lib, head, depth=0):
    """VAL cons list (8-byte cells {car, cdr}) -> python list of values."""
    out = []
    node = head
    guard = 0
    while node and guard < 10000:
        guard += 1
        car = lib.u32(node)
        cdr = lib.u32(node + 4)
        out.append(car)
        node = cdr
    return out


def decode_val(lib, v):
    tag = valtag(lib, v)
    if tag == 5:
        s = lib.u32(v + 4)
        if s == 0:
            return ""
        try:
            return lib.cstr(s, 4096).decode("latin1")
        except Exception:
            return "<badstr>"
    return f"<tag{tag}>"


def make_out_list_words(lib, vals):
    """Build a cons list {VAL(str), ...} in emulator memory; return head."""
    head = 0
    for s in reversed(vals):
        sp = lib.alloc_str(s)
        v = lib.alloc(8)
        lib.wr(v, struct.pack("<H", 5) + b"\x00\x00")
        lib.w32(v + 4, sp)
        cell = lib.alloc(8)
        lib.w32(cell, v)
        lib.w32(cell + 4, head)
        head = cell
    return head


class G2P:
    def __init__(self):
        self.lib = ArmLib(SO)
        _fix_sprintf(self.lib)
        l = self.lib
        # LtsInfo
        self.lts_info = l.alloc(0x20)
        l.wr(self.lts_info, b"\x00" * 0x20)
        l.w32(self.lts_info + 0x00, l.alloc_str("en_us_lex_lts"))
        l.w32(self.lts_info + 0x04, LETTER_TABLE)
        l.w32(self.lts_info + 0x08, FSM)
        l.w32(self.lts_info + 0x0C, LTS_PHONES)
        l.w32(self.lts_info + 0x10, 4)
        l.w32(self.lts_info + 0x14, 1)
        l.w32(self.lts_info + 0x18, 0)
        l.w32(self.lts_info + 0x1C, 0)
        # LexInfo
        self.lex_info = l.alloc(0x24)
        l.wr(self.lex_info, b"\x00" * 0x24)
        l.w32(self.lex_info + 0x00, l.alloc_str("en_us_lex"))
        l.w32(self.lex_info + 0x04, 0x1EE0C)
        l.w32(self.lex_info + 0x08, LEX_BLOB)
        l.w32(self.lex_info + 0x0C, LEX_BLOB_LEN)
        l.w32(self.lex_info + 0x10, LEX_PHONES)
        l.w32(self.lex_info + 0x14, 0)
        self.empty = l.alloc(8)
        l.wr(self.empty, b"\x00" * 8)
        l.w32(self.lex_info + 0x18, self.empty)
        l.w32(self.lex_info + 0x1C, LEX_ALT)
        l.w32(self.lex_info + 0x20, LEX_POOL)
        self.empty_str = l.alloc_str("")
        self.tag0 = l.alloc_str("0")

    def lts_run(self, word):
        l = self.lib
        w = l.alloc_str(word)
        try:
            r = l.call(FUN_LTS, [w, self.empty_str, self.lts_info])
        except Exception as e:
            return f"<emuerror {e}>"
        if r == 0:
            return []
        return [decode_val(l, v) for v in walk_list(l, r)]

    def lex_run(self, word, tag=b"0"):
        l = self.lib
        w = l.alloc_str(word)
        t = l.alloc_str(tag.decode() if isinstance(tag, bytes) else tag)
        try:
            r = l.call(FUN_LEX, [self.lex_info, w, t])
        except Exception as e:
            return f"<emuerror {e}>"
        if r == 0:
            return None
        return [decode_val(l, v) for v in walk_list(l, r)]


def main():
    argv = sys.argv[1:]
    force_lts = False
    if argv and argv[0] == "--lts":
        force_lts = True
        argv = argv[1:]
    words = argv or ["cat", "hello", "zzyzx", "the", "of", "'cause", "thought",
                     "queue", "xylophone", "a", "beat"]
    g = G2P()
    print("%-14s %-8s %s" % ("word", "src", "phones"))
    for w in words:
        if not force_lts:
            r = g.lex_run(w)
            if r:
                print("%-14s %-8s %s" % (w, "lex", " ".join(r)))
                continue
        r = g.lts_run(w)
        print("%-14s %-8s %s" % (w, "lts", " ".join(r) if isinstance(r, list) else r))


if __name__ == "__main__":
    main()
