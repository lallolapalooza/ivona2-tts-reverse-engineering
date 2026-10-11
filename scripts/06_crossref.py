#!/usr/bin/env python3
"""Verify cross-section structure of CDXV main OBB.

1. Section A (@0x40): records char name[12] + u32 start + u32 count.
   Verify start_{i+1} == start_i + count_i and sum(count) == len(B)/4.
2. Section B (@0x48): u32 array sliced per A-record; check each slice sorted
   and values valid tail-index positions.
3. Tail index: for chosen diphones, show member record sizes/trailing pairs.
4. Gap region: probe frame periodicity (byte entropy by residue mod F).
5. Section C (@0x50): probe for repeated record headers.
Usage: 06_crossref.py <main.obb> <label>
"""
import collections
import math
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    size = len(data)
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60)}
    aoff, aln = S[0x40]
    boff, bln = S[0x48]
    coff, cln = S[0x50]
    gap_start = S[0x38][0]
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    npairs = idx_len // 8
    first_rec = u32(data, 0x68)

    # ---- 1. section A records
    nrec = aln // 20
    recs = []
    for i in range(nrec):
        r = data[aoff + i * 20: aoff + i * 20 + 20]
        name = r[0:12].split(b"\x00")[0].decode("ascii")
        start, count = struct.unpack_from("<II", r, 12)
        recs.append((name, start, count))
    ok_chain = all(recs[i][1] + recs[i][2] == recs[i + 1][1] for i in range(nrec - 1))
    total = recs[0][1] + sum(r[2] for r in recs)
    print(f"== {label}: A records={nrec} start-chain ok={ok_chain} "
          f"first={recs[0]} last={recs[-1]} sum(count)={total} len(B)/4={bln//4}")

    # ---- 2. section B slices
    B = [u32(data, boff + i * 4) for i in range(bln // 4)]
    bad_val = 0
    sorted_slices = 0
    unsorted_slices = []
    for i, (nm, st, ct) in enumerate(recs):
        sl = B[st:st + ct]
        if any(v >= npairs for v in sl):
            bad_val += 1
        if all(sl[j] <= sl[j + 1] for j in range(len(sl) - 1)):
            sorted_slices += 1
        else:
            unsorted_slices.append(nm)
    print(f"   slices with value>=npairs: {bad_val}; sorted slices: {sorted_slices}/{nrec}")
    print(f"   unsorted examples: {unsorted_slices[:10]}")

    # ---- 3. chosen diphones: member records
    for want in ("aa-aa", "pau-pau" if any(r[0] == "pau-pau" for r in recs) else recs[0][0],
                 recs[5][0]):
        i = next((k for k, r in enumerate(recs) if r[0] == want), None)
        if i is None:
            continue
        nm, st, ct = recs[i]
        sl = B[st:st + ct]
        print(f"   diphone '{nm}' count={ct} slice idx {st}..{st+ct-1} "
              f"first idx={sl[:5]} last idx={sl[-3:]}")
        for j in sl[:4]:
            ro, rl = u32(data, idx_off + j * 8), u32(data, idx_off + j * 8 + 4)
            rec = data[ro:ro + rl]
            t_off, t_len = struct.unpack_from("<II", rec, rl - 8)
            nu16 = (rl - 8) // 2
            u16s = struct.unpack_from(f"<{nu16}H", rec, 0)
            mono = all(u16s[k] <= u16s[k + 1] for k in range(nu16 - 1))
            print(f"       rec@0x{ro:X} len={rl} nu16={nu16} mono={mono} "
                  f"u16[0:3]={u16s[:3]} u16[-3:]={u16s[-3:]} trail=(0x{t_off:X},{t_len})")

    # global u16 monotonicity over sample
    mono_n = 0
    tot = 0
    last_pairs = []
    for j in range(0, npairs, 13):
        ro, rl = u32(data, idx_off + j * 8), u32(data, idx_off + j * 8 + 4)
        if rl < 12:
            continue
        rec = data[ro:ro + rl]
        nu16 = (rl - 8) // 2
        u16s = struct.unpack_from(f"<{nu16}H", rec, 0)
        tot += 1
        if all(u16s[k] <= u16s[k + 1] for k in range(nu16 - 1)):
            mono_n += 1
        if len(last_pairs) < 8:
            t_off, t_len = struct.unpack_from("<II", rec, rl - 8)
            last_pairs.append((j, rl, u16s[-2:], t_off, t_len))
    print(f"   u16 monotonic in {mono_n}/{tot} sampled records")
    print(f"   sample trailing pairs (recno, len, last2u16, off, len): {last_pairs}")

    # ---- 4. gap frame periodicity probe
    slice_ = data[gap_start:gap_start + 65536]
    print(f"   gap entropy 64k={entropy(slice_):.3f}")
    best = []
    for F in range(4, 65):
        # entropy by residue
        total_e = 0.0
        for r in range(F):
            total_e += entropy(slice_[r::F])
        best.append((total_e / F, F))
    best.sort()
    print(f"   lowest mean per-residue entropy (F candidates): {best[:8]}")
    # recurring 4-gram scan
    pat = data[gap_start:gap_start + 4]
    occ = []
    p = gap_start
    while len(occ) < 12:
        p = data.find(pat, p + 1, gap_start + 200000)
        if p < 0:
            break
        occ.append(p)
    print(f"   first bytes {pat.hex()} occurrences: {occ} deltas={[occ[i+1]-occ[i] for i in range(len(occ)-1)]}")

    # ---- 5. section C structure probe: find repeated short byte patterns
    head = data[coff:coff + 65536]
    # look for repeated 4-byte windows frequency
    cnt = collections.Counter(head[i:i + 4] for i in range(0, len(head) - 4))
    common = [(k.hex(), v) for k, v in cnt.most_common(8)]
    print(f"   C first64k repeated 4-grams: {common}")
    # does 0x11000000 recur?
    pat2 = bytes.fromhex("110000006400")
    pos = []
    p = coff
    while len(pos) < 10:
        p = data.find(pat2, p + 1, coff + 100000)
        if p < 0:
            break
        pos.append(p - coff)
    print(f"   offsets of '11 00 00 00 64 00' within C: {pos} deltas={[pos[i+1]-pos[i] for i in range(len(pos)-1)]}")


if __name__ == "__main__":
    main()
