#!/usr/bin/env python3
"""Region-wise strings extraction for a CDXV main OBB.

Splits the file into the regions known from the header table and the index
tail records, runs an ASCII strings scan over each region, and prints:
  region boundaries, byte counts, string count, sample strings.
Usage: 04_strings_by_region.py <main.obb> <label>
"""
import re
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def strings(data, minlen=4):
    out = []
    cur = bytearray()
    start = 0
    for i, c in enumerate(data):
        if 32 <= c < 127:
            if not cur:
                start = i
            cur.append(c)
        else:
            if len(cur) >= minlen:
                out.append((start, bytes(cur)))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append((start, bytes(cur)))
    return out


def main():
    path = sys.argv[1]
    label = sys.argv[2]
    with open(path, "rb") as f:
        data = f.read()
    size = len(data)

    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    pairs = []
    for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60):
        pairs.append((ho, u32(data, ho), u32(data, ho + 4)))

    regions = [("header", 0, 0x68)]
    regions.append(("index", idx_off, idx_off + idx_len))
    for ho, off, ln in pairs:
        if ln:
            regions.append((f"sect@hdr+0x{ho:X}", off, off + ln))
    # gap between chain end and first index-record
    chain_end = max((off + ln) for _, off, ln in pairs if ln)
    first_rec = u32(data, 0x68)
    regions.append(("gap", chain_end, first_rec))
    regions.append(("index_tail_records", first_rec, size))

    print(f"== {label} ({size} bytes)")
    for name, a, b in regions:
        chunk = data[a:b]
        ss = strings(chunk, 4)
        print(f"\n-- {name}: [0x{a:X}, 0x{b:X}) len={b-a} strings>=4: {len(ss)}")
        for off, s in ss[:15]:
            print(f"     +0x{a+off:08X}: {s.decode('ascii', 'replace')[:80]}")
        if len(ss) > 15:
            print(f"     ... {len(ss)-15} more")


if __name__ == "__main__":
    main()
