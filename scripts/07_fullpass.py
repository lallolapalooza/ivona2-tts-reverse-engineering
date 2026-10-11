#!/usr/bin/env python3
"""Full pass over all tail index records of a CDXV main OBB.

Record layout hypothesis (verified):
  u16 N; u16 ramp[N]; u16 Y; u32 gap_off; u32 gap_len      (len == 2N+12)

Checks:
  - len == 2N+12 for every record
  - ramp monotone nondecreasing
  - ramp_max <= 8*gap_len (bit-addressable into blob)
  - gap_off monotone in record order; overlap statistics
  - sum(N) vs section D length  -> D indexing
  - section C length == 36 * record count
Usage: 07_fullpass.py <main.obb> <label>
"""
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    size = len(data)
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60)}
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    n = idx_len // 8
    clen = S[0x50][1]
    dlen = S[0x58][1]

    bad_len = 0
    short = 0
    nonmono = 0
    ramp_over = 0
    y_over = 0
    sum_n = 0
    sum_tlen = 0
    prev_off = -1
    off_nonmono = 0
    distinct_off = set()
    y_min, y_max = 1 << 30, 0
    n_min, n_max = 1 << 30, 0
    for i in range(n):
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl < 12 or ro + rl > size:  # observed null/short slots
            short += 1
            continue
        rec = data[ro:ro + rl]
        N = struct.unpack_from("<H", rec, 0)[0]
        if rl != 2 * N + 12:
            bad_len += 1
            if bad_len < 4:
                print(f"  len mismatch rec {i}: len={rl} N={N}")
            continue
        ramp = struct.unpack_from(f"<{N}H", rec, 2)
        Y = struct.unpack_from("<H", rec, 2 + 2 * N)[0]
        t_off, t_len = struct.unpack_from("<II", rec, 4 + 2 * N)
        sum_n += N
        sum_tlen += t_len
        if N and any(ramp[k] > ramp[k + 1] for k in range(N - 1)):
            nonmono += 1
        if N and max(ramp) > 8 * t_len:
            ramp_over += 1
        if Y > 8 * t_len:
            y_over += 1
        if t_off < prev_off:
            off_nonmono += 1
        prev_off = t_off
        distinct_off.add(t_off)
        n_min, n_max = min(n_min, N), max(n_max, N)
        y_min, y_max = min(y_min, Y), max(y_max, Y)

    print(f"== {label}: records={n} (null/short slots: {short})")
    print(f"  len==2N+12 violations: {bad_len}")
    print(f"  N range: {n_min}..{n_max}; sum(N)={sum_n}")
    print(f"  Y range: {y_min}..{y_max}")
    print(f"  ramp non-monotone records: {nonmono}")
    print(f"  ramp_max > 8*t_len: {ramp_over}; Y > 8*t_len: {y_over}")
    print(f"  gap_off non-monotone steps: {off_nonmono}; distinct gap_off: {len(distinct_off)}")
    print(f"  sum(t_len)={sum_tlen}; gap size={S[0x38][0] and (u32(data, 0x68) - S[0x38][0])}")
    print(f"  section C len={clen}; 36*npairs={36*n} equal={clen == 36*n}")
    print(f"  section D len={dlen}; D/npairs={dlen/n:.4f}; D/sum(N)={dlen/sum_n:.4f}; "
          f"D/len(B)={dlen/(S[0x48][1]//4):.4f}")
    # try to find integer relations
    for name, v in (("npairs", n), ("sumN", sum_n), ("sumN+npairs", sum_n + n),
                    ("Bcount", S[0x48][1] // 4), ("2*sumN", 2 * sum_n),
                    ("sumN-npairs", sum_n - n), ("3*sumN", 3 * sum_n),
                    ("sum(t_len)", sum_tlen)):
        if v and dlen % v == 0:
            print(f"  D divisible by {name}({v}) -> {dlen // v} per unit")


if __name__ == "__main__":
    main()
