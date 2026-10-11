#!/usr/bin/env python3
"""Second-round probes: ISEF payload, gap periodicity, section C field stats,
section B permutation check, section D entry sizes.

Usage: 10_probes.py <main.obb> <lang.dat>
"""
import bz2
import collections
import lzma
import math
import struct
import sys
import zlib


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    path, lang = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    L = open(lang, "rb").read()

    # ---- 1. ISEF payload: compression attempts
    print("== ISEF payload decompression attempts")
    payload = L[12:]
    for off in (0, 4, 8, 12):
        for name, fn in (("zlib", lambda d: zlib.decompress(d)),
                         ("deflate-raw", lambda d: zlib.decompress(d, -15)),
                         ("gzip", lambda d: zlib.decompress(d, 31)),
                         ("bz2", bz2.decompress),
                         ("lzma", lzma.decompress)):
            try:
                out = fn(payload[off:off + 4096])
                print(f"   offset {off} {name}: OK len={len(out)}")
            except Exception:
                pass
    h = collections.Counter(payload)
    print(f"   payload bytes={len(payload)} distinct={len(h)} entropy={entropy(payload):.4f}")
    print(f"   most common bytes: {h.most_common(6)}; least: {h.most_common()[-4:]}")

    # ---- 2. gap periodicity: 4-gram recurrence
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60)}
    gap = S[0x38][0]
    slice_ = data[gap:gap + 2_000_000]
    cnt = collections.Counter(slice_[i:i + 4] for i in range(0, len(slice_) - 4, 1))
    top = cnt.most_common(5)
    print(f"== gap top 4-grams in first 2MB: {[(k.hex(), v) for k, v in top]}")
    # for the most common non-trivial 4-gram, delta histogram
    pat, _ = top[0]
    d = collections.Counter()
    last = None
    start = 0
    while True:
        i = slice_.find(pat, start)
        if i < 0:
            break
        if last is not None:
            d[i - last] += 1
        last = i
        start = i + 1
        if start > len(slice_):
            break
    print(f"   deltas for {pat.hex()}: top10={d.most_common(10)} total_occ={sum(d.values())}")

    # ---- 3. section C field stats
    coff, cln = S[0x50]
    n = cln // 36
    pos_stats = [[] for _ in range(32)]
    for i in range(0, min(n, 4000)):
        rec = data[coff + i * 36: coff + i * 36 + 32]
        for p in range(32):
            pos_stats[p].append(rec[p])
    print("== section C byte-position stats (first 4000 records):")
    for p in range(32):
        vals = pos_stats[p]
        c = collections.Counter(vals)
        lo, hi = min(vals), max(vals)
        distinct = len(c)
        top3 = c.most_common(3)
        print(f"   pos {p:2d}: min={lo:3d} max={hi:3d} distinct={distinct:3d} top3={top3}")

    # ---- 4. B permutation check: are B values exactly the non-null record ids?
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    npairs = idx_len // 8
    valid = set()
    nulls = 0
    for i in range(npairs):
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl < 12:
            nulls += 1
        else:
            valid.add(i)
    boff, bln = S[0x48]
    B = [u32(data, boff + i * 4) for i in range(bln // 4)]
    Bs = set(B)
    print(f"== B: entries={len(B)} distinct={len(Bs)}; valid records={len(valid)} nulls={nulls}")
    print(f"   B == valid set: {Bs == valid}; B entries not valid: {len(Bs - valid)}; "
          f"valid not in B: {len(valid - Bs)}")

    # ---- 5. D entry sizes
    doff, dln = S[0x58]
    offs = [u32(data, coff + i * 36 + 32) for i in range(n)]
    sizes = collections.Counter()
    distinct_entries = 0
    ent_sizes = []
    uniq = []
    for o in offs:
        if not uniq or o != uniq[-1]:
            uniq.append(o)
    for i, o in enumerate(uniq):
        nxt = uniq[i + 1] if i + 1 < len(uniq) else dln
        ent_sizes.append(nxt - o)
        distinct_entries += 1
    print(f"== D: distinct entries={distinct_entries}; size hist (top20)="
          f"{collections.Counter(ent_sizes).most_common(20)}")
    print(f"   size min={min(ent_sizes)} max={max(ent_sizes)} sum={sum(ent_sizes)} (D len={dln})")


if __name__ == "__main__":
    main()
