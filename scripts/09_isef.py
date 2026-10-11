#!/usr/bin/env python3
"""Scan main OBBs for known magics; analyze lang_*.dat (ISEF) headers and
US/GB differences.

Usage: 09_isef.py <lang_en_us.dat> <lang_en_gb.dat> <main.obb>...
"""
import collections
import math
import struct
import sys


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def hx(b, base=0, limit=128):
    lines = []
    for i in range(0, min(len(b), limit), 16):
        chunk = b[i:i + 16]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        lines.append(f"  {base+i:08X}: {hexs:<47} {asc}")
    return "\n".join(lines)


def main():
    us_path, gb_path = sys.argv[1], sys.argv[2]
    us = open(us_path, "rb").read()
    gb = open(gb_path, "rb").read()
    print(f"== {us_path}: len={len(us)}")
    print(hx(us))
    print(f"   header: magic={us[0:4]!r} u32be@4={struct.unpack_from('>I', us, 4)[0]} "
          f"u32le@4={struct.unpack_from('<I', us, 4)[0]}")
    print(f"   entropy bytes[8:]= {entropy(us[8:]):.3f}; entropy[8:64]={entropy(us[8:64]):.3f}")
    # block entropy scan (4KB windows)
    blocks = [(i, entropy(us[i:i + 4096])) for i in range(0, len(us), 4096)]
    low = sorted(blocks, key=lambda x: x[1])[:8]
    print(f"   4KB window entropies: min8={[(hex(o), round(e,2)) for o,e in low]}")
    print(f"== {gb_path}: len={len(gb)}")
    print(hx(gb))
    # diff
    if len(us) == len(gb):
        diff = [i for i in range(len(us)) if us[i] != gb[i]]
        print(f"   US vs GB: differing bytes = {len(diff)} of {len(us)}")
        print(f"   first diffs at: {diff[:10]} ... last: {diff[-5:] if diff else None}")
        # run structure of diffs
        runs = []
        start = prev = None
        for i in diff:
            if start is None:
                start = prev = i
            elif i == prev + 1:
                prev = i
            else:
                runs.append((start, prev - start + 1))
                start = prev = i
        if start is not None:
            runs.append((start, prev - start + 1))
        print(f"   diff runs: count={len(runs)} first10={runs[:10]}")

    # magics in main obbs
    for p in sys.argv[3:]:
        d = open(p, "rb").read()
        print(f"== scan {p} ({len(d)} bytes)")
        for mag in (b"ISEF", b"CDXV", b"RIFF", b"OggS", b"FORM", b"\x1aE\xdf\xa3"):
            pos = []
            s = 0
            while len(pos) < 5:
                i = d.find(mag, s)
                if i < 0:
                    break
                pos.append(hex(i))
                s = i + 1
            print(f"   {mag!r}: {pos}")


if __name__ == "__main__":
    main()
