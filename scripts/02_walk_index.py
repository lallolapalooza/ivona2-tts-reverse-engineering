#!/usr/bin/env python3
"""Walk the full (offset,size) index of a CDXV main OBB and report its extent.

Prints: entry count, where the index bytes end in the file, whether the last
entry ends at EOF, and coverage of the file by index entries.
"""
import struct
import sys


def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()
    size = len(data)
    pos = u32(data, 0x30)  # index start
    n = 0
    first_off = None
    prev_end = None
    anomalies = []
    while pos + 8 <= size:
        off, ln = u32(data, pos), u32(data, pos + 4)
        if off == 0 and ln == 0:  # observed empty-slot entries
            n += 1
            pos += 8
            continue
        if off > size or ln == 0 or off + ln > size:
            print(f"STOP at pair {n}, pos=0x{pos:X}: off=0x{off:X} len=0x{ln:X}")
            break
        if first_off is None:
            first_off = off
        if prev_end is not None and off != prev_end and len(anomalies) < 10:
            anomalies.append((n, pos, hex(prev_end), hex(off)))
        prev_end = off + ln
        n += 1
        pos += 8
    print(f"index pairs: {n}")
    print(f"index bytes: [0x{u32(data,0x30):X}, 0x{pos:X}) -> {pos - u32(data, 0x30)} bytes")
    print(f"first entry offset: 0x{first_off:X} ({first_off})")
    print(f"last entry end: 0x{prev_end:X} ({prev_end}); file size 0x{size:X} ({size})")
    print(f"last_end == filesize: {prev_end == size}")
    print(f"contiguity anomalies (non-adjacent): {anomalies}")
    print(f"header section chain start (u32@0x34): 0x{u32(data,0x34):X}")
    print(f"index end == section start: {pos == u32(data, 0x34)}")
    # coverage summary
    print(f"gap [index_end, first_entry_off) = {first_off - pos} bytes")
    print(f"tail [first_entry_off, EOF) = {size - first_off} bytes")


if __name__ == "__main__":
    main()
