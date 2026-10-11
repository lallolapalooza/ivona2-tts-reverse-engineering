#!/usr/bin/env python3
"""Map .rodata of a libvoice .so: entropy, printable density, big runs.

Usage: 06_rodata_map.py <libvoice.so> [block]
Prints one line per block: offset, entropy, printable ratio, first string.
Also reports long ASCII runs and low/high-entropy regions.
"""
import math
import sys


def entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def first_string(b, minlen=8):
    cur = bytearray()
    for c in b:
        if 32 <= c < 127:
            cur.append(c)
            if len(cur) >= minlen:
                return bytes(cur)[:60]
        else:
            cur = bytearray()
    return None


def main():
    path = sys.argv[1]
    block = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x10000
    data = open(path, "rb").read()
    # .rodata from readelf
    base, size = 0x569b0, 0x28d3d8
    print(f"== {path} .rodata @0x{base:X} size=0x{size:X} ({size} bytes)")
    off = base
    end = base + size
    while off < end:
        chunk = data[off:off + block]
        pr = sum(1 for c in chunk if 32 <= c < 127 or c in (9, 10, 13)) / len(chunk)
        s = first_string(chunk)
        print(f"  0x{off:07X} ent={entropy(chunk):.2f} printable={pr:.2f} "
              f"{('str=' + repr(s)) if s else ''}")
        off += block
    # long ascii runs
    runs = []
    cur = 0
    st = 0
    for i in range(base, end):
        c = data[i]
        if 32 <= c < 127 or c in (10, 13, 9):
            if cur == 0:
                st = i
            cur += 1
        else:
            if cur >= 4096:
                runs.append((st, cur))
            cur = 0
    if cur >= 4096:
        runs.append((st, cur))
    print(f"\n== ASCII runs >= 4096 bytes: {len(runs)}")
    tot = 0
    for st, ln in runs:
        tot += ln
        print(f"  0x{st:07X} len={ln} ent={entropy(data[st:st+ln]):.2f} "
              f"head={data[st:st+70]!r}")
    print(f"  total ascii-run bytes: {tot}")


if __name__ == "__main__":
    main()
