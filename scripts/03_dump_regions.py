#!/usr/bin/env python3
"""Hexdump + identify regions of a CDXV main OBB.

- dumps first 0x100 bytes at each section start from the header table
- carves the first K index records to out/obb/ and prints their bytes/strings
- reports entropy of major regions
"""
import math
import os
import struct
import sys

OUT = os.path.join(os.path.dirname(__file__), "..", "out", "obb")


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return -sum((c / n) * math.log2(c / n) for c in counts if c)


def hx(b, base=0, width=16):
    lines = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        lines.append(f"  {base+i:08X}: {hexs:<47} {asc}")
    return "\n".join(lines)


def main():
    path = sys.argv[1]
    name = sys.argv[2]  # short name for output files
    with open(path, "rb") as f:
        data = f.read()
    size = len(data)

    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    secs = []
    for o in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60):
        secs.append((u32(data, o), u32(data, o + 4), o))

    print(f"== {name} size={size}")
    print(f"index: off=0x{idx_off:X} len={idx_len} end=0x{idx_off+idx_len:X}")
    for off, ln, ho in secs:
        print(f"section @{ho:#x}: off=0x{off:X} len={ln} end=0x{off+ln:X}")

    # hexdump at each section start + after-chain gap start
    marks = [("header", 0x0)]
    for off, ln, ho in secs:
        marks.append((f"section(hdr+0x{ho:X})", off))
    for label, off in marks:
        if off < size:
            print(f"\n-- {label} file offset 0x{off:X} (entropy16k={entropy(data[off:off+16384]):.2f})")
            print(hx(data[off:off + 0x80], off))

    # gap region probes (after last section to first index entry)
    last_end = max(off + ln for off, ln, _ in secs if ln)
    first_entry = u32(data, 0x68)
    print(f"\n-- probe unaccounted gap [0x{last_end:X}, 0x{first_entry:X})")
    for frac in (0, 1000, 1_000_000, 10_000_000, 50_000_000):
        off = last_end + frac
        if off < first_entry:
            print(f"  at 0x{off:X}: entropy={entropy(data[off:off+65536]):.2f}")
            print(hx(data[off:off + 0x40], off))

    # carve first 8 index records
    os.makedirs(OUT, exist_ok=True)
    print("\n-- first 12 index records:")
    carve = []
    for i in range(12):
        o = idx_off + i * 8
        eoff, eln = u32(data, o), u32(data, o + 4)
        rec = data[eoff:eoff + eln]
        carve.append((i, eoff, eln, rec))
        print(f"  [{i}] off=0x{eoff:X} len={eln} entropy={entropy(rec):.2f}")
        print(hx(rec, eoff))
        s = "".join(chr(c) if 32 <= c < 127 else "." for c in rec)
        print(f"        ascii: {s}")
    with open(os.path.join(OUT, f"{name}_first_records.bin"), "wb") as f:
        for i, eoff, eln, rec in carve:
            f.write(rec)

    # tail-of-index records (near EOF) and middle records
    n_pairs = (idx_len) // 8
    print(f"\n-- pair count={n_pairs}; middle record:")
    for idx in (n_pairs // 2, n_pairs - 2, n_pairs - 1):
        o = idx_off + idx * 8
        eoff, eln = u32(data, o), u32(data, o + 4)
        rec = data[eoff:eoff + eln]
        print(f"  [{idx}] off=0x{eoff:X} len={eln} entropy={entropy(rec):.2f}")
        print(hx(rec, eoff))
        s = "".join(chr(c) if 32 <= c < 127 else "." for c in rec)
        print(f"        ascii: {s}")


if __name__ == "__main__":
    main()
