#!/usr/bin/env python3
"""Parse CDXV container header + index of IVONA 2 main OBB files.

Usage: 01_parse_header.py <main.obb> [max_index_pairs]
Prints header fields (little-endian u32) and the (offset,size) index table
found at the offset stored at header+0x30 (observed: 0x68).
"""
import struct
import sys


def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def main():
    path = sys.argv[1]
    max_pairs = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    with open(path, "rb") as f:
        data = f.read()
    size = len(data)
    print(f"file: {path}")
    print(f"file size: {size} (0x{size:X})")
    print(f"magic: {data[0:4]!r}")
    name = data[4:0x24].split(b"\x00")[0]
    print(f"name@0x04 (28 bytes): {name!r}")
    for off in range(0x20, 0x68, 4):
        v = u32(data, off)
        print(f"  +0x{off:02X}: {v:10d}  0x{v:08X}  {data[off:off+4]!r}")

    idx_off = u32(data, 0x30)
    print(f"\nindex start (u32 @0x30) = 0x{idx_off:X}")

    # walk contiguous (offset,size) pairs
    pos = idx_off
    prev_end = None
    n = 0
    bad = 0
    while pos + 8 <= size and n < 100000:
        off, ln = u32(data, pos), u32(data, pos + 4)
        if off == 0 and ln == 0:
            tag = " <NULL>"
        elif off > size or off + ln > size or ln == 0:
            tag = " <BREAK>"
            if bad == 0:
                print(f"  first break at index pos 0x{pos:X}: off=0x{off:X} len=0x{ln:X}")
            bad += 1
            if bad > 3:
                break
        else:
            tag = ""
            if prev_end is not None and off != prev_end:
                tag += f" (gap/overlap vs prev_end 0x{prev_end:X})"
            prev_end = off + ln
        if n < max_pairs:
            print(f"  [{n:5d}] @0x{pos:06X}: off=0x{off:08X} len=0x{ln:06X}{tag}")
        n += 1
        pos += 8
    print(f"pairs walked: {n}, end of walk pos=0x{pos:X}, last_end={hex(prev_end) if prev_end else None}")
    if prev_end:
        print(f"last_end vs filesize: {prev_end} / {size} (delta {size - prev_end})")


if __name__ == "__main__":
    main()
