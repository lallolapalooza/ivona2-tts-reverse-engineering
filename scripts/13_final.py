#!/usr/bin/env python3
"""Round-4 probes:
  - blob prefix stats: first 8 bytes of first M blobs (do they share a header?)
  - section A: confirm name field fits in 12 bytes (NUL within first 12)
  - header timestamp decode
  - D-group size histogram and pos7 (C byte 7) pattern per group member
Usage: 13_final.py <main.obb> <label>
"""
import collections
import datetime
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60)}
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    n = idx_len // 8
    coff, _ = S[0x50]

    # header fields
    ts = u32(data, 0x2C)
    nm = data[4:32].split(b"\x00")[0]
    print(f"== {label}: name={nm!r} "
          f"sr={u32(data,0x24)} f0x28={u32(data,0x28)} ts={ts} "
          f"({datetime.datetime.utcfromtimestamp(ts)} UTC)")

    # blob prefixes
    print("   first 20 blob prefixes (8 bytes):")
    pat_count = collections.Counter()
    M = 400
    for i in range(M):
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl < 12:
            continue
        rec = data[ro:ro + rl]
        N = struct.unpack_from("<H", rec, 0)[0]
        t_off, t_len = struct.unpack_from("<II", rec, 4 + 2 * N)
        pre = data[t_off:t_off + 8]
        pat_count[pre[2:6]] += 1
        if i < 20:
            print(f"     rec {i}: {pre.hex()}")
    print(f"   bytes[2:6] patterns top8: {[(k.hex(), v) for k, v in pat_count.most_common(8)]} of {M}")

    # section A name NUL check
    aoff, aln = S[0x40]
    bad = 0
    maxlen = 0
    for i in range(aln // 20):
        r = data[aoff + i * 20: aoff + i * 20 + 12]
        z = r.find(b"\x00")
        if z < 0:
            bad += 1
        else:
            maxlen = max(maxlen, z)
    print(f"   A names without NUL in first 12 bytes: {bad}; longest name={maxlen}")

    # D group sizes + pos7 pattern
    offs = [u32(data, coff + i * 36 + 32) for i in range(n)]
    groups = []
    start = 0
    for i in range(1, n + 1):
        if i == n or offs[i] != offs[start]:
            groups.append((start, i))
            start = i
    sizes = collections.Counter(b - a for a, b in groups)
    print(f"   D group size hist: {sizes.most_common(10)}")
    # pos7 per member for groups of each size (first 3 examples each)
    by_size = collections.defaultdict(list)
    for a, b in groups:
        if len(by_size[b - a]) < 3:
            by_size[b - a].append((a, b))
    for sz, ex in sorted(by_size.items()):
        for a, b in ex[:2]:
            seq = [data[coff + i * 36 + 7] for i in range(a, min(b, a + 8))]
            print(f"   size={sz} group[{a},{b}) pos7 seq={seq}")


if __name__ == "__main__":
    main()
