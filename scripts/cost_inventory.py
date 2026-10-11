#!/usr/bin/env python3
"""Inventory of feature accesses, literals and cost constants inside a cost function.

Usage: cost_inventory.py <dump.c> <ghidra_start_hex> [ghidra_end_hex]

Extracts, for the function body:
  * every string literal compared / passed (strcmp / FUN_* string helpers)
  * every byte-offset access on each parameter: param_N + 0xNN, param_N[0xNN]
  * every integer constant added to a running cost (iVarN = iVarN + <const>)
  * every multiplier applied to a running cost (iVarN = ... * <const>)
This is a *complete inventory*, not a transcription: it lists exactly which fields and
constants a port must have, while control flow is described separately.
"""
import re
import sys

dump, start = sys.argv[1], int(sys.argv[2], 16)
end = int(sys.argv[3], 16) if len(sys.argv) > 3 else None

lines = open(dump).read().split('\n')
# locate function header
i0 = None
for i, l in enumerate(lines):
    m = re.match(r'^// ----- ([0-9a-f]{8}) : ', l)
    if m and int(m.group(1), 16) == start:
        i0 = i
        break
if i0 is None:
    sys.exit('function not found')
i1 = len(lines)
for i in range(i0 + 1, len(lines)):
    m = re.match(r'^// ----- ([0-9a-f]{8}) : ', lines[i])
    if m:
        i1 = i
        break
if end:
    for i in range(i0 + 1, len(lines)):
        m = re.match(r'^// ----- ([0-9a-f]{8}) : ', lines[i])
        if m and int(m.group(1), 16) >= end:
            i1 = i
            break
body = '\n'.join(lines[i0:i1])

print(f'== function {start:#010x}  ({i1 - i0} lines)')
print(f'   header: {lines[i0][:80]}')

lits = []
for m in re.finditer(r'(?:strcmp|FUN_[0-9a-f]+)\s*\(\s*[^,()]*,\s*"([^"]{1,32})"', body):
    lits.append(m.group(1))
for m in re.finditer(r'"(content|L\*|L|r|g|\+|-)?"', body):
    pass
print('\n-- string literals (deduped, in order) --')
seen = []
for l in lits:
    if l not in seen:
        seen.append(l)
for l in seen:
    print(f'   "{l}"  (×{lits.count(l)})')

# ---- parameter element size from the signature (u16* vs u32* vs u8*) ----
sig = lines[i0 + 1] + ' ' + lines[i0 + 2]
etypes = {}
for m in re.finditer(r'(undefined1|undefined2|undefined4|char|byte|ushort|short|uint|int)\s*\*\s*param_(\d)', sig):
    t, p_ = m.group(1), int(m.group(2))
    etypes[p_] = {'undefined1': 1, 'char': 1, 'byte': 1,
                  'undefined2': 2, 'ushort': 2, 'short': 2,
                  'undefined4': 4, 'uint': 4, 'int': 4}.get(t, 4)
print('   element sizes: ' + ', '.join(f'param_{k}×{v}' for k, v in sorted(etypes.items())))

print('\n-- byte-offset accesses per parameter --')
buckets = {}
for m in re.finditer(r'\(int\)param_(\d)\s*\+\s*(0x[0-9a-f]+|\d+)', body):
    p, off = int(m.group(1)), int(m.group(2), 0)
    buckets.setdefault(p, set()).add(off)
for m in re.finditer(r'\(param_(\d)\s*\+\s*(0x[0-9a-f]+|\d+)\)', body):
    p, off = int(m.group(1)), int(m.group(2), 0)
    buckets.setdefault(p, set()).add(off * 4)          # param_N is a word pointer here
for m in re.finditer(r'param_(\d)\[0x?([0-9a-f]+)\]', body):
    p, w = int(m.group(1)), int(m.group(2), 16)
    buckets.setdefault(p, set()).add(w * etypes.get(p, 4))
for p in sorted(buckets):
    offs = sorted(buckets[p])
    print(f'   param_{p} (elem×{etypes.get(p,4)}): ' + ', '.join(f'{o:#04x}({o})' for o in offs))

print('\n-- integer constants combined into a running cost (candidates) --')
adds = {}
for m in re.finditer(r'(iVar\d+|uVar\d+|local_[0-9a-f]+)\s*=\s*\1\s*\+\s*(0x[0-9a-f]+|\d+)', body):
    adds.setdefault(int(m.group(2), 0), 0)
    adds[int(m.group(2), 0)] += 1
for c in sorted(adds):
    print(f'   +{c}  (×{adds[c]})')

print('\n-- literal constants used inside expressions --')
for m in sorted(set(re.findall(r'\b0x[0-9a-f]{2,8}\b', body))):
    print(f'   {m} = {int(m, 16)}', end='')
print()
