#!/usr/bin/env python3
"""Inspect groups of consecutive index records that share one section-D entry:
print all fields of section C record + tail-record meta for each group,
to see what the group members have in common.

Usage: 12_groups.py <main.obb> <label>
"""
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x40, 0x48, 0x50, 0x58, 0x60)}
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    n = idx_len // 8
    coff, _ = S[0x50]
    offs = [u32(data, coff + i * 36 + 32) for i in range(n)]
    phon = [data[S[0x60][0] + i * 32: S[0x60][0] + i * 32 + 32].split(b"\x00")[0].decode()
            for i in range(S[0x60][1] // 32)]

    def meta(i):
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl < 12:
            return None
        rec = data[ro:ro + rl]
        N = struct.unpack_from("<H", rec, 0)[0]
        Y = struct.unpack_from("<H", rec, 2 + 2 * N)[0]
        t_off, t_len = struct.unpack_from("<II", rec, 4 + 2 * N)
        return N, Y, t_off, t_len, rl

    # find groups: boundaries where offs changes; pick a few multi-record groups
    groups = []
    start = 0
    for i in range(1, n + 1):
        if i == n or offs[i] != offs[start]:
            groups.append((start, i))
            start = i
    multi = [g for g in groups if g[1] - g[0] >= 3]
    print(f"== {label}: groups={len(groups)} multi>=3: {len(multi)}")
    for gi, (a, b) in enumerate(multi[:6]):
        print(f"-- group {gi}: records [{a},{b}) D_off={offs[a]}")
        for i in range(a, min(b, a + 5)):
            crec = data[coff + i * 36: coff + i * 36 + 36]
            ctx = list(crec[2:7])
            ctx_names = [phon[c] if c < len(phon) else f"?{c}" for c in ctx]
            m = meta(i)
            print(f"   rec {i}: C={crec[:16].hex()} spec={crec[16:32].hex()} "
                  f"ctx={ctx_names} meta={m}")
    # control: groups of size 1 neighbors
    singles = [g for g in groups if g[1] - g[0] == 1][:3]
    for a, b in singles:
        print(f"-- single group record {a}: C={data[coff+a*36:coff+a*36+16].hex()} meta={meta(a)}")


if __name__ == "__main__":
    main()
