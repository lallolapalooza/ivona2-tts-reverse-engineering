#!/usr/bin/env python3
"""Resolve PC-relative string literals in Thumb code (Ghidra-style addresses).

Handles the two-instruction pattern produced by PIC string addressing:
    ldr rX, [pc, #imm]      ; loads a signed displacement
    add rX, pc              ; rX = (addr+4 & ~3) + displacement  -> Ghidra addr of a string

Usage: litstrings.py <so> <ghidra_start> <ghidra_end>
"""
import sys, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

so, start, end = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
d = open(so, 'rb').read()
off0, off1 = start - 0x10000, end - 0x10000
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True


def cstr(va):
    if not (0 <= va < len(d)):
        return None
    j = d.find(b'\x00', va)
    if j < 0 or j - va > 300:
        return None
    s = d[va:j]
    return s if s and all(32 <= b < 127 or b in (9, 10) for b in s) else None


pending = {}   # reg -> displacement loaded from literal pool
seen = set()
pos = off0
while pos < off1:
    chunk = list(md.disasm(d[pos:off1], pos))
    if not chunk:
        pos += 2            # skip undecodable bytes (data/padding)
        continue
    for ins in chunk:
        pos = ins.address + ins.size
        if ins.mnemonic == 'ldr' and len(ins.operands) == 2 and ins.operands[1].type == 3 \
                and ins.reg_name(ins.operands[1].value.mem.base) == 'pc':
            lit = ((ins.address + 4) & ~3) + ins.operands[1].value.mem.disp
            if 0 <= lit + 4 <= len(d):
                pending[ins.operands[0].reg] = struct.unpack_from('<i', d, lit)[0]
            continue
        if ins.mnemonic == 'add' and len(ins.operands) == 2 and ins.operands[1].type == 1 \
                and ins.reg_name(ins.operands[1].value.reg) == 'pc':
            reg = ins.operands[0].reg
            if reg in pending:
                gva = (ins.address + 4) + pending.pop(reg)   # ADD (reg) with Rn=PC: no align
                s = cstr(gva)
                if s is not None and s not in seen:
                    seen.add(s)
                    print(f'{ins.address+0x10000:#08x}  "{s.decode()}"  @ {gva+0x10000:#x}')
