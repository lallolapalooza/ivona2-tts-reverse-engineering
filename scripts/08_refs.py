#!/usr/bin/env python3
"""Extract every DAT_/PTR_DAT_ reference from a Ghidra decompilation,
map it to the file offset (Ghidra base = link addr + 0x10000), and cluster
references that fall into .rodata to reveal table boundaries.

Usage: 08_refs.py <decompiled.c> <label>
"""
import re
import sys
from collections import defaultdict

PAT = re.compile(r"\b(PTR_DAT_|DAT_)([0-9a-f]{8})\b")
FUNC = re.compile(r"^// ----- ([0-9a-f]+) : (\S+) -----")

RODATA = (0x569b0, 0x569b0 + 0x28d3d8)


def main():
    path, label = sys.argv[1], sys.argv[2]
    refs = []            # (file_off, func_addr, func_name, line)
    func = ("?", "?")
    with open(path) as f:
        for ln, line in enumerate(f, 1):
            m = FUNC.match(line)
            if m:
                func = (m.group(1), m.group(2))
                continue
            for mm in PAT.finditer(line):
                addr = int(mm.group(2), 16)
                off = addr - 0x10000
                refs.append((off, func[0], func[1], ln))
    ro = [r for r in refs if RODATA[0] <= r[0] < RODATA[1]]
    print(f"== {label}: {len(refs)} DAT refs total, {len(ro)} into .rodata")
    offs = sorted(set(r[0] for r in ro))
    print(f"distinct .rodata addresses referenced: {len(offs)}")
    # cluster: gap > 0x40 starts a new table
    clusters = []
    start = prev = offs[0]
    for o in offs[1:]:
        if o - prev > 0x40:
            clusters.append((start, prev))
            start = o
        prev = o
    clusters.append((start, prev))
    print(f"clusters (gap>0x40): {len(clusters)}")
    data = open("/home/asdf/Downloads/ivona_re/out/libs/kendra/libvoice_en_us_kendra.so", "rb").read()
    for a, b in clusters:
        # first referenced function for this cluster
        users = sorted({r[1] for r in ro if a <= r[0] <= b})
        head = data[a:a + 40]
        s = ""
        cur = bytearray()
        for c in head:
            if 32 <= c < 127:
                cur.append(c)
            else:
                break
        if len(cur) >= 4:
            s = bytes(cur).decode()
        print(f"  0x{a:07X}..0x{b:07X} span=0x{b-a+4:X} refs={sum(1 for r in ro if a<=r[0]<=b):4d} "
              f"funcs={','.join(users[:4])}{'...' if len(users)>4 else ''} head={s!r}")


if __name__ == "__main__":
    main()
