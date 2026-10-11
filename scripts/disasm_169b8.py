#!/usr/bin/env python3
"""Disassemble libtiver FUN_000169b8 and FUN_000166e8 (thumb) to verify
stat field offsets, local_1bc source, h return value."""
from capstone import *
so = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libtiver.so"
data = open(so, "rb").read()
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def disasm(elf_addr, size, title):
    print(f"===== {title} @ ELF 0x{elf_addr:x} =====")
    for insn in md.disasm(data[elf_addr:elf_addr+size], elf_addr):
        print(f"  0x{insn.address:05x}: {insn.mnemonic:8s} {insn.op_str}")

# h @ ELF 0x6a58 (dump 0x16a58) .. 0x6a64
disasm(0x6a58, 0x10, "h")
# FUN_000169b8 @ ELF 0x69b8 .. 0x6a58
disasm(0x69b8, 0xa0, "FUN_000169b8 (table lookup + stat check)")
