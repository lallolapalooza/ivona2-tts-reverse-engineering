#!/usr/bin/env python3
"""Check whether section C's trailing u32 (per 36-byte record) is an offset
into section D, and characterize D entries.

Prints: first K offsets, monotonicity over all records, increment histogram,
last offset + implied final entry size vs D length.
Also dumps a few aligned D entries.
Usage: 08_c_to_d.py <main.obb> <label>
"""
import collections
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x40, 0x48, 0x50, 0x58)}
    coff, cln = S[0x50]
    doff, dln = S[0x58]
    n = cln // 36
    offs = [u32(data, coff + i * 36 + 32) for i in range(n)]
    print(f"== {label}: C records={n} first20 offsets={offs[:20]}")
    nonmono = sum(1 for i in range(1, n) if offs[i] < offs[i - 1])
    print(f"   non-monotone offsets: {nonmono}; last offset={offs[-1]} (D len={dln})")
    inc = collections.Counter(offs[i] - offs[i - 1] for i in range(1, n))
    print(f"   increment histogram (top15): {inc.most_common(15)}")
    in_d = sum(1 for o in offs if o <= dln)
    print(f"   offsets <= D len: {in_d}/{n}")
    if offs[-1] <= dln:
        print(f"   final implied entry size: {dln - offs[-1]}")
    # dump aligned D entries for first 8 records
    for i in range(8):
        a = doff + offs[i]
        b = doff + (offs[i + 1] if i + 1 < n else dln)
        e = data[a:b]
        print(f"   D entry[{i}] @0x{a:X} size={b-a} hex={e.hex()}")
        if b - a >= 2:
            print(f"        last u16={struct.unpack_from('<H', e, b - a - 2)[0]}")


if __name__ == "__main__":
    main()
