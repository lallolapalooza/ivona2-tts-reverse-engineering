#!/usr/bin/env python3
"""Round-3 probes:
  - distinct (t_off,t_len) blob count vs D distinct entries
  - dump first 20 D entries (payload + trailing u16) and some long entries
  - section C: correlate block1 positions 2..6 with phoneme ids for a diphone
  - section C: correlate u16@0 with N / Y / t_len of the same index record
Usage: 11_probes2.py <main.obb> <label>
"""
import collections
import struct
import sys


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main():
    path, label = sys.argv[1], sys.argv[2]
    data = open(path, "rb").read()
    S = {ho: (u32(data, ho), u32(data, ho + 4)) for ho in (0x38, 0x40, 0x48, 0x50, 0x58, 0x60)}
    idx_off, idx_len = u32(data, 0x30), u32(data, 0x34)
    n = idx_len // 8
    coff, cln = S[0x50]
    doff, dln = S[0x58]

    # per-record: blob pair, N, Y
    blobs = set()
    rec_meta = []
    for i in range(n):
        ro, rl = u32(data, idx_off + i * 8), u32(data, idx_off + i * 8 + 4)
        if rl < 12:
            rec_meta.append(None)
            continue
        rec = data[ro:ro + rl]
        N = struct.unpack_from("<H", rec, 0)[0]
        Y = struct.unpack_from("<H", rec, 2 + 2 * N)[0]
        t_off, t_len = struct.unpack_from("<II", rec, 4 + 2 * N)
        blobs.add((t_off, t_len))
        rec_meta.append((N, Y, t_off, t_len))
    print(f"== {label}: distinct (t_off,t_len) blobs={len(blobs)}")

    # D offsets from C
    offs = [u32(data, coff + i * 36 + 32) for i in range(n)]
    uniq = []
    for o in offs:
        if not uniq or o != uniq[-1]:
            uniq.append(o)
    print(f"   distinct D entries={len(uniq)}")

    # do records sharing a D entry share a blob? (sample)
    same = diff = 0
    for i in range(1, n):
        if rec_meta[i] is None or rec_meta[i - 1] is None:
            continue
        if offs[i] == offs[i - 1]:
            if rec_meta[i][2:] == rec_meta[i - 1][2:]:
                same += 1
            else:
                diff += 1
    print(f"   records sharing D entry: same blob={same} different blob={diff}")

    # ---- first 20 D entries
    print("   first 20 D entries:")
    for k in range(20):
        a = uniq[k]
        b = uniq[k + 1] if k + 1 < len(uniq) else dln
        e = data[doff + a: doff + b]
        if len(e) >= 2:
            tail = struct.unpack_from("<H", e, len(e) - 2)[0]
        else:
            tail = None
        print(f"     [{k}] off={a:6d} size={len(e):4d} tail_u16={tail} hex={e[:24].hex()}")
    # some long entries
    sizes = [(uniq[k + 1] if k + 1 < len(uniq) else dln) - a0
             for k, a0 in enumerate(uniq)]
    big = sorted(range(len(uniq)), key=lambda k: -sizes[k])[:3]
    for k in big:
        a = uniq[k]
        b = uniq[k + 1] if k + 1 < len(uniq) else dln
        e = data[doff + a: doff + b]
        print(f"     long[{k}] size={len(e)} head={e[:64].hex()}")
        print(f"              tail={e[-32:].hex()}")

    # ---- section C: phone-id correlation
    aoff, aln = S[0x40]
    nA = aln // 20
    phon = [data[S[0x60][0] + i * 32: S[0x60][0] + i * 32 + 32].split(b"\x00")[0].decode()
            for i in range(S[0x60][1] // 32)]
    boff, bln = S[0x48]
    B = [u32(data, boff + i * 4) for i in range(bln // 4)]
    # find a common diphone, e.g. the one with most records
    best = None
    for ai in range(nA):
        nm, st, ct = (data[aoff + ai * 20: aoff + ai * 20 + 12].split(b"\x00")[0].decode(),
                      struct.unpack_from("<I", data, aoff + ai * 20 + 12)[0],
                      struct.unpack_from("<I", data, aoff + ai * 20 + 16)[0])
        if best is None or ct > best[2]:
            best = (nm, st, ct)
    nm, st, ct = best
    print(f"   most common diphone '{nm}' count={ct}; phones: {nm.split('-')}")
    pidx = {p: i for i, p in enumerate(phon)}
    want = [pidx.get(p) for p in nm.split("-")]
    print(f"   expected phone ids in C pos2..6: {want}")
    hits = 0
    checked = 0
    for j in B[st:st + min(ct, 40)]:
        rec = data[coff + j * 36: coff + j * 36 + 16]
        six = list(rec[2:7])
        checked += 1
        if all(w is None or w in six for w in want):
            hits += 1
        if checked <= 5:
            print(f"     rec {j}: pos0-15 = {list(rec)}")
    print(f"   records whose pos2..6 contain expected ids: {hits}/{checked}")

    # ---- u16@0 vs N/Y/t_len (sample)
    pairs = []
    for i in range(0, n, 997):
        if rec_meta[i] is None:
            continue
        N, Y, t_off, t_len = rec_meta[i]
        u = struct.unpack_from("<H", data, coff + i * 36, )[0]
        pairs.append((u, N, Y, t_len))
    print("   (u16@0, N, Y, t_len) samples:", pairs[:15])
    # ratios
    import statistics
    r1 = [u / t for u, N, Y, t in pairs if t]
    print(f"   u16@0/t_len: mean={statistics.mean(r1):.3f} min={min(r1):.3f} max={max(r1):.3f}")


if __name__ == "__main__":
    main()
