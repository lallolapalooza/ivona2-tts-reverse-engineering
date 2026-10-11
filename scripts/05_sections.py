#!/usr/bin/env python3
"""Detailed per-section analysis of a CDXV main OBB.

Sections (from header u32 pairs at 0x38/0x40/0x48/0x50/0x58/0x60):
  A (0x40): 20-byte records: char name[16] + u32  -- diphone names
  B (0x48): u32 array
  C (0x50): frame-like records
  D (0x58): byte-heavy block
  E (0x60): 32-byte phoneme name records

Also analyzes tail index records: each ends with (u32 gap_off, u32 gap_len).
Usage: 05_sections.py <main.obb> <label>
"""
import collections
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    size = len(data)
    sect = {}
    for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60):
        sect[ho] = (u32(data, ho), u32(data, ho + 4))

    # --- Section A: diphone records @0x40
    off, ln = sect[0x40]
    print(f"== {label} section A @0x{off:X} len={ln} (20-byte records -> {ln/20} records)")
    for i in range(6):
        r = data[off + i * 20: off + i * 20 + 20]
        nm = r[0:16].split(b"\x00")[0]
        a, b = struct.unpack_from("<II", r, 16 - 4) if False else (None, None)
        v = struct.unpack_from("<I", r, 16)[0]
        v2 = None
        print(f"  [{i}] raw={r.hex()} name={nm!r} u32@16={v}")
    # check all names printable & fields distribution
    vals = collections.Counter()
    bad = 0
    for i in range(ln // 20):
        r = data[off + i * 20: off + i * 20 + 20]
        nm = r[0:16].split(b"\x00")[0]
        if not all(32 <= c < 127 for c in nm) or b"\x00" not in r[0:16]:
            bad += 1
            if bad < 5:
                print(f"  odd record [{i}]: {r.hex()}")
        vals[struct.unpack_from("<I", r, 16)[0]] += 1
    print(f"  non-name/empty-terminator records: {bad}; distinct u32@16: {len(vals)}; top: {vals.most_common(10)}")

    # --- Section B @0x48: u32 array
    off, ln = sect[0x48]
    n = ln // 4
    vals = [u32(data, off + i * 4) for i in range(n)]
    mono = sum(1 for i in range(1, n) if vals[i] >= vals[i - 1])
    print(f"== section B @0x{off:X} len={ln} ({n} u32) first10={vals[:10]} last5={vals[-5:]}")
    print(f"   nondecreasing pairs: {mono}/{n-1}; min={min(vals)} max={max(vals)}")
    # do these look like offsets into section C?
    coff, cln = sect[0x50]
    inrange = sum(1 for v in vals if v < cln)
    print(f"   values < sectionC length({cln}): {inrange}/{n}")

    # --- Section C @0x50: frame-like
    off, ln = sect[0x50]
    print(f"== section C @0x{off:X} len={ln}")
    print("   head:", data[off:off + 96].hex())
    # byte value histogram of first 1MB
    chunk = data[off:off + 1048576]
    hist = collections.Counter(chunk)
    top = hist.most_common(12)
    print(f"   first1MB byte hist top12: {top}; distinct={len(hist)}")

    # --- Section D @0x58: byte-heavy
    off, ln = sect[0x58]
    print(f"== section D @0x{off:X} len={ln}")
    print("   head:", data[off:off + 96].hex())
    chunk = data[off:off + 1048576]
    hist = collections.Counter(chunk)
    print(f"   first1MB byte hist top12: {hist.most_common(12)}; distinct={len(hist)}")

    # --- Section E @0x60: phoneme names
    off, ln = sect[0x60]
    print(f"== section E @0x{off:X} len={ln} ({ln/32} x 32-byte records)")
    names = []
    for i in range(ln // 32):
        r = data[off + i * 32: off + (i + 1) * 32]
        nm = r.split(b"\x00")[0]
        names.append(nm)
    print("   names:", [n.decode("ascii", "replace") for n in names])

    # --- tail index records: trailing pair analysis
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    npairs = idx_len // 8
    gap_start = sect[0x38][0]
    print(f"== tail records: {npairs} pairs")
    lens = []
    trail_offs = []
    printable = 0
    checked = 0
    sum_trail_len = 0
    for i in range(0, npairs, 7):  # sample every 7th record
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl == 0:
            continue
        rec = data[ro:ro + rl]
        checked += 1
        lens.append(rl)
        t_off, t_len = struct.unpack_from("<II", rec, rl - 8)
        trail_offs.append(t_off)
        sum_trail_len += t_len
        if sum(1 for c in rec[:-8] if 32 <= c < 127) > (rl - 8) * 0.7:
            printable += 1
    lens.sort()
    print(f"   sampled {checked} records; len min={lens[0]} p50={lens[len(lens)//2]} p90={lens[len(lens)*9//10]} max={lens[-1]}")
    print(f"   records whose body is >70% printable: {printable}/{checked}")
    to = trail_offs
    print(f"   trailing off: min=0x{min(to):X} max=0x{max(to):X} (gap_start=0x{gap_start:X}, "
          f"gap_end(first_rec)=0x{u32(data,0x68):X})")
    in_gap = sum(1 for t in to if gap_start <= t < u32(data, 0x68))
    print(f"   trailing offs inside gap: {in_gap}/{checked}")
    print(f"   sum of sampled trailing lens: {sum_trail_len} (avg {sum_trail_len/checked:.1f})")


if __name__ == "__main__":
    main()
