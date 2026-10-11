#!/usr/bin/env python3
"""Disassemble a range of an ELF (ARM/Thumb). Usage:
   disasm_arm.py lib.so LO HI [thumb|arm]
Addresses are ELF vaddrs (file offset == vaddr for the first PT_LOAD)."""
import sys
from capstone import *

so = sys.argv[1]
lo = int(sys.argv[2], 16)
hi = int(sys.argv[3], 16)
mode = sys.argv[4] if len(sys.argv) > 4 else 'thumb'
data = open(so, 'rb').read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if mode == 'thumb' else CS_MODE_ARM)
for insn in md.disasm(data[lo:hi], lo):
    print(f"  0x{insn.address:05x}: {insn.bytes.hex():<10s} {insn.mnemonic:8s} {insn.op_str}")
