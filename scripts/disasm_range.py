#!/usr/bin/env python3
"""Disassemble FUN_000166e8 (ELF 0x66e8..0x69b8) and checkFiles (0x6a64..0x6b94)."""
from capstone import *
so = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libtiver.so"
data = open(so, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
import sys
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
for insn in md.disasm(data[lo:hi], lo):
    print(f"  0x{insn.address:05x}: {insn.mnemonic:8s} {insn.op_str}")
