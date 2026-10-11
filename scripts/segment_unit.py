#!/usr/bin/env python3
"""Segment / splice an IVONA 2 acoustic unit exactly as libttsivonavoice.so does.

Model (all addresses are the ELF vaddrs used by emu/armemu.py; Ghidra = ELF + 0x10000):

  * `LAB_00067db8` (0x57db8, CDXV `type=14` decode callback, vtable +0x0f) parses the
    unit record `{u16 N; u16 ramp[N]; u16 Y; u32 gap_off; u32 gap_len}`, decodes
    `ramp[N-1]` samples of PCM with `FUN_00067a14` (warm-up `Y` discarded) and then
    builds a *segment object* out of them:

        obj+0x04 = sample rate (copied from cdxv+0x0c by FUN_0005ef70)
        obj+0x08 = N                        (number of segments)
        obj+0x0c = int32 pms[N]             (pms[i] = ramp[i], cumulative boundaries)
        obj+0x10 = int16* block[N]          (block i = PCM[ramp[i-1] : ramp[i])

    `ramp[]` are therefore *cumulative* sample marks (the engine's own debug printer
    `FUN_00062550` calls them "pms").  Segment i has length
    `FUN_000624c8(i) = pms[0] if i==0 else pms[i]-pms[i-1]` and starts at
    `FUN_000624b0(i) = 0 if i==0 else pms[i-1]`.  The last entry `ramp[N-1]` equals the
    total decoded sample count (the decode call is *asked* for exactly that many).

  * Splicing into the streamer output buffer is `FUN_00061620` (0x61620) with the
    crossfade `FUN_00062bd4` (0x62bd4) and its window `FUN_00062b6c` (0x62b6c).

This module re-implements both in pure Python and can diff the result against the
real library run under emu/armemu.py (`--verify-engine`, `--verify-splice`).

Usage
  ~/venvs/re/bin/python scripts/segment_unit.py --record 1 --show
  ~/venvs/re/bin/python scripts/segment_unit.py --record 1 --analyze
  ~/venvs/re/bin/python scripts/segment_unit.py --verify-engine --records 0,1,3,10
  ~/venvs/re/bin/python scripts/segment_unit.py --verify-splice --records 0,1,3,10
  ~/venvs/re/bin/python scripts/segment_unit.py --verify-finalize
"""
import argparse
import array
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))
sys.path.insert(0, HERE)

import decode_unit as du                                  # noqa: E402  (Obb, Codec, find_obb)
# `armemu` (Unicorn) is imported lazily inside Engine.__init__ so the pure-python
# segmentation / splice / finalize path (used by refimpl/tts.py) stays
# Unicorn-free at import time.

SO = os.path.join(ROOT, 'out', 'libs', 'kendra', 'libttsivonavoice.so')

# ---- ELF vaddrs of the functions used -------------------------------------
V_F49C = 0x4F49C      # FUN_0005f49c  CDXV container open
V_F064 = 0x4F064      # FUN_0005f064  diphonedb open (+ per-type codec init)
V_EF70 = 0x4EF70      # FUN_0005ef70  read one unit record -> decode -> segment object
V_61620 = 0x51620     # FUN_00061620  append a segment object to the streamer
V_618A8 = 0x518A8     # FUN_000618a8  finalise a chunk (copy out / slide down)
V_62BD4 = 0x52BD4     # FUN_00062bd4  crossfade
V_62B6C = 0x52B6C     # FUN_00062b6c  crossfade window (17-point raised cosine + slope)

# Window tables at file/ELF offset 0x152718 (DAT_00162718) and 0x15275c (DAT_0016275c),
# stored here as the exact IEEE-754 single bit patterns read from the .so.
# tab1[i] == round(0.5*(1+cos(pi*i/16)), 5)  for i=0..16   (raised cosine, 5 decimals)
# tab2[i] == tab1[i] - tab1[i+1] (slope of that 17-point table), i=0..15
WIN_TAB1_HEX = [0x3f800000, 0x3f7d8a33, 0x3f7641b3, 0x3f6a6d48, 0x3f5a8241,
                0x3f471d3f, 0x3f30fba9, 0x3f18f909, 0x3f000000, 0x3ece0ded,
                0x3e9e08af, 0x3e638b05, 0x3e15f6fd, 0x3dac95c0, 0x3d1be4cd,
                0x3c1d7343, 0x00000000]
WIN_SLOPE_HEX = [0xbc1d7343, 0xbce90ff9, 0xbd3d46b2, 0xbd7eb075, 0xbd9b280f,
                 0xbdb10cb3, 0xbdc014f9, 0xbdc7c84b, 0xbdc7c84b, 0xbdc014f9,
                 0xbdb10cb3, 0xbd9b280f, 0xbd7eb075, 0xbd3d46b2, 0xbce90ff9,
                 0xbc1d7343]


def _f32(bits):
    return struct.unpack('<f', struct.pack('<I', bits))[0]


WIN_TAB1 = [_f32(b) for b in WIN_TAB1_HEX]
WIN_SLOPE = [_f32(b) for b in WIN_SLOPE_HEX]


def _check_win_tables():
    """Confirm the embedded window tables match the .so at ELF 0x152718/0x15275c (bit-exact)."""
    d = open(SO, 'rb').read()
    t1 = struct.unpack_from('<17I', d, 0x152718)      # ELF vaddr == file offset
    t2 = struct.unpack_from('<16I', d, 0x15275C)
    return list(t1) == WIN_TAB1_HEX and list(t2) == WIN_SLOPE_HEX


# --------------------------------------------------------------------------
# 1. segmentation
# --------------------------------------------------------------------------
def boundaries_from_record(rec):
    """Segment boundaries straight from the record's `ramp[]` (== the engine's pms[])."""
    return [0] + list(rec['ramp'])


def segments_from_record(rec):
    """Return [(start, length), ...], one entry per segment, exactly as LAB_00067db8 builds."""
    pms = rec['ramp']
    out = []
    for i in range(rec['N']):
        start = 0 if i == 0 else pms[i - 1]
        out.append((start, pms[i] - start))
    return out


def segment_pcm(pcm, rec):
    """Slice decoded PCM (24000 Hz, ramp[N-1] samples) into the engine's blocks."""
    return [pcm[s:s + n] for s, n in segments_from_record(rec)]


# --------------------------------------------------------------------------
# 2. crossfade / splice
# --------------------------------------------------------------------------
def cf_window(k, length):
    """FUN_00062b6c (0x62b6c): w(k) = tab1[i] + frac*tab2[i], i = trunc(16k/length).

    Single-precision float maths, exactly as the ARM code (floatsisf/divsf3/mulsf3/addsf3).
    """
    t = np.float32(np.float32(k << 4) / np.float32(length))
    i = int(t)                                   # __fixsfsi: truncate toward zero
    frac = np.float32(t - np.float32(i))
    return np.float32(WIN_TAB1[i] + np.float32(frac * np.float32(WIN_SLOPE[i])))


def crossfade(buf, off, dst_len, src, src_len):
    """FUN_00062bd4 (0x62bd4): blend `src`'s **last** min(dst_len,src_len) samples into
    `buf[off:off+min]` with the window above; returns min.  `buf` is modified in place.

    out[k] = trunc_f32( w(k) * (buf[off+k] - src[(src_len-L)+k]) ) + src[(src_len-L)+k]
    with L = min(dst_len, src_len) and w going 1 -> ~0, i.e. out[0] == buf[off] and
    out[L-1] == src[src_len-1].
    """
    L = min(dst_len, src_len)
    for k in range(L):
        s = src[src_len - L + k]
        delta = np.float32(np.int32(buf[off + k]) - np.int32(s))
        w = cf_window(k, L)
        v = int(np.float32(w * delta))           # __fixsfsi
        buf[off + k] = ((int(s) + v + 0x8000) & 0xFFFF) - 0x8000   # int16 store
    return L


def splice(streamer, obj, flag):
    """FUN_00061620 (0x61620).  `streamer` and `obj` are dicts holding the fields the
    engine's C structs hold; returns the number of samples committed by this call.

    streamer: {'rate','cap','pos','tail','total','out': list[int16]}
    obj:      {'pms': [int], 'blocks': [list[int16]]}

    Semantics (see report_segmentation.md): all segments except the last are written
    after `pos`; the pending tail (`tail` samples already at `pos`) is crossfaded with
    block 0 (using block 0's *last* min(tail,len0) samples, the earlier ones dropped).
    With flag!=0 the last segment is written at `pos` too but left *uncommitted*
    (becomes the new pending tail); with flag==0 it is not written at all.
    """
    pms = obj['pms']
    blocks = obj['blocks']
    N = len(blocks)
    pos = streamer['pos']
    out = streamer['out']

    need = pms[-1] if N else 0                       # FUN_000624e8(obj, 0, N-1)
    if streamer['cap'] - pos < need:
        grow = streamer['rate'] * 5
        if need > grow:
            grow = need
        streamer['out'] = out + [0] * grow
        streamer['cap'] += grow

    written = 0
    if N >= 2:
        if streamer['tail'] >= 1:
            # segment 0: crossfade the pending tail with block 0's *last* min(tail,len0)
            # samples (the earlier ones of block 0 are dropped)
            written += crossfade(out, pos, streamer['tail'], blocks[0], len(blocks[0]))
        else:
            ln = len(blocks[0])
            out[pos:pos + ln] = blocks[0]
            written += ln
        i = 1
        while i < N - 1:                           # segments 1..N-2 plain-copied
            ln = len(blocks[i])
            out[pos + written:pos + written + ln] = blocks[i]
            written += ln
            i += 1

    streamer['pos'] = pos + written
    if flag != 0:
        lln = len(blocks[N - 1])
        streamer['tail'] = lln
        out[streamer['pos']:streamer['pos'] + lln] = blocks[N - 1]
    else:
        streamer['tail'] = 0
    streamer['total'] += written
    return written


def stretch_pass(pms, blocks, frm, to, target):
    """One deletion pass of `FUN_00062d14` (ELF 0x52d14; report_stretch.md).

    Rebuilds the whole object: segments outside `[frm..to]` are copied through,
    and inside the window each source segment faces a two-way choice -- *merge*
    it with the next (crossfade the next block onto it, consuming both) or keep
    it -- whichever leaves the accumulated ratio
    `new_run / old_run` closer to `target`:

        old_so_far = pms[i] - (pms[frm-1] if frm else 0)
        cur        = prev_new_mark - (new_pms[frm-1] if frm else 0)
        f_keep     = (cur + len_i) / old_so_far
        f_drop     = (len_next + cur) / (len_next + old_so_far)   if len_next <= len_i
                     (len_i    + cur) / (len_next + old_so_far)   otherwise
        merge iff |target - f_drop| < |target - f_keep|           (float32, strict)

    A merge writes `min(len_i, len_next)` samples (the crossfade length) and
    frees the next block; the window's last segment may merge with the first
    segment *after* the window (`local_78 == local_70` still decides), which is
    why the pass can consume one tail segment.  Returns `(new_pms, new_blocks,
    realized)` with `realized` the f32 ratio the engine accumulates.
    """
    n = len(blocks)
    lens = [pms[0]] + [pms[i] - pms[i - 1] for i in range(1, n)]
    old_start = pms[frm - 1] if frm else 0
    new_pms = []
    new_blocks = []
    old_run = 0
    new_run = 0
    i = 0
    while i < n:
        prev = new_pms[-1] if new_pms else 0
        new_pms.append(prev + lens[i])
        if frm <= i <= to and i + 1 < n:
            base = new_pms[frm - 1] if frm else 0
            cur = prev - base
            old_so_far = pms[i] - old_start
            ln = lens[i + 1]
            f_keep = np.float32(np.float32(cur + lens[i]) / np.float32(old_so_far))
            num = np.float32(ln + cur) if ln <= lens[i] else np.float32(cur + lens[i])
            f_drop = np.float32(num / np.float32(ln + old_so_far))
            if abs(np.float32(target - f_drop)) < abs(np.float32(target - f_keep)):
                buf = list(blocks[i])                    # destination (block i)
                L = crossfade(buf, 0, lens[i], blocks[i + 1], ln)
                new_blocks.append(buf[:L])
                new_pms[-1] = prev + L
                i += 2
                continue
        new_blocks.append(list(blocks[i]))
        i += 1
    return new_pms, new_blocks


def stretch(pms, blocks, frm, to, factor):
    """`FUN_00062d14(obj, frm, to, factor)`: the multi-pass SOLA restretch.

    Pass targets halve (`0.5`) while `0.5 * acc >= factor`, then the remainder
    `factor / acc` finishes; the loop ends when `acc == factor` exactly (f32).
    `upper` tracks the window's moving bound: `upper += (new_count - N0)` after
    every pass (`local_78 += iVar18 - local_50`), which keeps the window on the
    segments the previous pass produced.  The engine's return value (the achieved
    factor) is only used by `FUN_00063350`'s own ignored return, so it is not
    computed here.  `factor > 1` (the insertion path) is not implemented -- the
    shipped voices never reach it (all four transforms read 1.0).
    """
    factor = np.float32(factor)
    if factor == np.float32(1.0):
        return list(pms), [list(b) for b in blocks]
    if factor > np.float32(1.0):
        raise NotImplementedError('FUN_00062d14 insertion path (factor > 1)')
    acc = np.float32(1.0)
    cur_pms, cur_blocks = list(pms), [list(b) for b in blocks]
    upper = to
    while True:
        if np.float32(acc * np.float32(0.5)) < factor:
            target = np.float32(factor / acc)
        else:
            target = np.float32(0.5)
        if not target < np.float32(1.0):
            break
        before = len(cur_blocks)
        cur_pms, cur_blocks = stretch_pass(cur_pms, cur_blocks, frm, upper,
                                          float(target))
        upper += len(cur_blocks) - before
        acc = np.float32(acc * target)
        if acc == factor:
            break
    return cur_pms, cur_blocks


def finalize(streamer, want=0):
    """FUN_000618a8 (0x618a8) with an empty event list (streamer+0x1c == 0).

    Copies min(want, pos) samples out (want<=0 -> pos), slides the buffer down and
    decrements `pos`.  Note: the *pending tail* (streamer['tail'] samples written at
    `pos` but uncommitted) is NOT included in the copy.
    """
    pos = streamer['pos']
    if pos == 0:
        return []
    n = pos
    if 0 < want <= pos:
        n = want
    res = streamer['out'][:n]
    if (pos - n) > 0 or streamer['tail'] > 0:
        out = streamer['out']
        out[:streamer['cap'] - n] = out[n:streamer['cap']]
    streamer['pos'] = pos - n
    return res


# --------------------------------------------------------------------------
# 3. engine verification
# --------------------------------------------------------------------------
class Engine:
    """Drives the real library: CDXV -> diphonedb -> unit decode, plus splicing."""

    def __init__(self, obb, lib=SO):
        from armemu import ArmLib                       # Unicorn, only for --verify-engine
        self.lib = ArmLib(lib, verbosity=0)
        p = self.lib.alloc_str(os.path.abspath(obb))
        self.cdxv = self.lib.call(V_F49C, [p])
        if not self.cdxv:
            raise RuntimeError("CDXV open failed")
        self.db = self.lib.call(V_F064, [self.cdxv])
        if not self.db:
            raise RuntimeError("diphonedb open failed")

    @property
    def rate(self):
        return self.lib.u32(self.cdxv + 0xc)

    def unit(self, index):
        """FUN_0005ef70 -> segment object; return (obj_addr, {'rate','pms','blocks'})."""
        w = self.lib.call(V_EF70, [self.db, index])
        if not w:
            raise RuntimeError("unit %d decode failed" % index)
        rate = self.lib.u32(w + 4)
        n = self.lib.u32(w + 8)
        offs = self.lib.u32(w + 0xc)
        pcm = self.lib.u32(w + 0x10)
        pms = list(struct.unpack('<%di' % n, self.lib.rd(offs, 4 * n)))
        blocks = []
        for i in range(n):
            p = self.lib.u32(pcm + 4 * i)
            ln = pms[i] if i == 0 else pms[i] - pms[i - 1]
            b = self.lib.rd(p, ln * 2)
            blocks.append(list(struct.unpack('<%dh' % ln, b)))
        return w, dict(rate=rate, pms=pms, blocks=blocks)

    def new_streamer(self, cap=1 << 18, rate=None):
        """Allocate the streamer + output-buffer C structs the splice functions expect."""
        lib = self.lib
        ob = lib.alloc(0x14)
        data = lib.alloc(cap * 2)
        lib.wr(data, b'\x00' * (cap * 2))
        lib.w32(ob + 4, rate if rate is not None else self.rate)   # sample rate
        lib.w32(ob + 8, cap)                                       # capacity (samples)
        lib.w32(ob + 0xc, 1)                                       # channels
        lib.w32(ob + 0x10, data)                                   # int16* data
        st = lib.alloc(0x24)
        lib.wr(st, b'\x00' * 0x24)
        lib.w32(st + 0xc, ob)
        return dict(addr=st, obj=ob, data=data, cap=cap, pos=0, tail=0, total=0,
                    out=[0] * cap)

    def splice_call(self, streamer, obj_addr, flag):
        return self.lib.call(V_61620, [streamer['addr'], obj_addr, flag])

    def mark_sync(self, streamer):
        streamer['pos'] = self.lib.u32(streamer['addr'] + 0x10)
        streamer['tail'] = self.lib.s32(streamer['addr'] + 0x14)
        streamer['total'] = self.lib.u32(streamer['addr'] + 0x18)

    def read_out(self, streamer, n):
        return list(struct.unpack('<%dh' % n, self.lib.rd(streamer['data'], n * 2)))


# --------------------------------------------------------------------------
# 4. CLI
# --------------------------------------------------------------------------
def _recs(arg):
    return [int(x) for x in arg.split(',') if x.strip()]


def cmd_show(obb, recs, analyze):
    for idx in recs:
        rec = obb.record(idx)
        if not rec:
            print("record %d: empty" % idx)
            continue
        segs = segments_from_record(rec)
        print("record %d: N=%d total=%d (== ramp[N-1]=%d) Y=%d gap=0x%x+%d"
              % (idx, rec['N'], rec['samples'], rec['ramp'][-1], rec['Y'],
                 rec['gap_off'], rec['gap_len']))
        print("  pms[]      : %s" % (list(rec['ramp']),))
        print("  lengths    : %s" % ([n for _, n in segs],))
        print("  boundaries : %s" % (["%d..%d" % (s, s + n - 1) for s, n in segs[:6]],))
        if analyze:
            cd = du.Codec()
            pcm = cd.decode_window(obb.cksum, obb.window(rec), rec['Y'], rec['samples'])
            x = np.array(pcm, float); x -= x.mean()
            lens = [n for _, n in segs]
            print("  mean len %.1f  (24000/len => %.1f Hz)" % (np.mean(lens), 24000.0 / np.mean(lens)))
            track = []
            for a in range(0, max(1, len(x) - 600), 200):
                seg = x[a:a + 600]
                ac = np.correlate(seg, seg, 'full')[len(seg) - 1:]
                ac = ac / (ac[0] or 1)
                p = 40 + int(np.argmax(ac[40:280]))
                track.append((a, p, round(float(ac[p]), 2)))
            print("  autocorr period track (off, period, ac): %s" % (track,))


def cmd_verify_engine(obb, recs):
    print("[engine] CDXV + diphonedb ...")
    eng = Engine(obb.path)
    print("[engine] cdxv=%#x db=%#x rate=%d" % (eng.cdxv, eng.db, eng.rate))
    ok = True
    for idx in recs:
        rec = obb.record(idx)
        if not rec:
            print("record %d empty -- skip" % idx); continue
        _, obj = eng.unit(idx)
        # (a) pms[] must equal the record's ramp[]
        pms_ok = obj['pms'] == list(rec['ramp'])
        # (b) blocks must equal the PCM decoded by FUN_00067a14 sliced at ramp[]
        cd = du.Codec()
        pcm = cd.decode_window(obb.cksum, obb.window(rec), rec['Y'], rec['samples'])
        mine = segment_pcm(pcm, rec)
        blocks_ok = (len(mine) == len(obj['blocks'])
                     and all(list(a) == list(b) for a, b in zip(mine, obj['blocks'])))
        # (c) rate field
        rate_ok = obj['rate'] == obb.rate
        concat_ok = [v for b in obj['blocks'] for v in b] == list(pcm)
        print("  rec %-4d N=%-4d pms==ramp:%s  blocks==PCM[ramp] :%s  concat==PCM:%s  rate=%d %s"
              % (idx, obj['pms'] and len(obj['pms']), pms_ok, blocks_ok, concat_ok,
                 obj['rate'], "OK" if rate_ok else "MISMATCH(%d)" % obj['rate']))
        if not (pms_ok and blocks_ok and concat_ok):
            ok = False
            if not pms_ok:
                print("      engine pms : %s" % obj['pms'][:40])
                print("      record ramp: %s" % list(rec['ramp'])[:40])
            if not blocks_ok:
                for i, (a, b) in enumerate(zip(mine, obj['blocks'])):
                    if list(a) != list(b):
                        d = sum(1 for u, v in zip(a, b) if u != v)
                        print("      first differing segment %d: mine len=%d engine len=%d diffs=%d"
                              % (i, len(a), len(b), d))
                        break
    print("[engine] segmentation verification: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def cmd_verify_splice(obb, recs, flags):
    """Splice a chain of real units: every unit is appended with `flag` = 1 for all but
    the last, the last with each flag in `flags`; the whole output buffer is compared."""
    eng = Engine(obb.path)
    print("[engine] cdxv=%#x db=%#x rate=%d" % (eng.cdxv, eng.db, eng.rate))
    units = []
    for i in recs:
        w, o = eng.unit(i)
        units.append((i, w, o))
        print("[engine] rec %-5d N=%-4d total=%-6d block0=%d tail=%d"
              % (i, len(o['pms']), sum(len(b) for b in o['blocks']),
                 len(o['blocks'][0]), len(o['blocks'][-1])))

    ok = True
    for last_flag in flags:
        st = eng.new_streamer()
        call_flags = [1] * (len(units) - 1) + [last_flag]
        pst = dict(rate=eng.rate, cap=st['cap'], pos=0, tail=0, total=0,
                   out=[0] * st['cap'])
        for (idx, w, o), fl in zip(units, call_flags):
            eng.splice_call(st, w, fl)
            splice(pst, o, fl)
        eng.mark_sync(st)
        n = st['pos'] + st['tail']
        got = eng.read_out(st, n)
        want = pst['out'][:pst['pos'] + pst['tail']]
        nd = sum(1 for a, b in zip(got, want) if a != b) + abs(len(got) - len(want))
        first = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
        print("  flags=%s: engine pos=%d tail=%d total=%d | model pos=%d tail=%d total=%d "
              "| len %d/%d | sample diffs=%d%s"
              % (call_flags, st['pos'], st['tail'], st['total'], pst['pos'], pst['tail'],
                 pst['total'], len(got), len(want), nd,
                 "" if first is None else " (first @%d eng=%d mine=%d)"
                 % (first, got[first], want[first])))
        if nd or st['pos'] != pst['pos'] or st['tail'] != pst['tail']:
            ok = False
    # overlap rule spot-check: min(tail(prev), block0(next))
    for (ia, _, oa), (ib, _, ob_) in zip(units, units[1:]):
        L = min(len(oa['blocks'][-1]), len(ob_['blocks'][0]))
        which = 'tail' if len(oa['blocks'][-1]) <= len(ob_['blocks'][0]) else 'block0'
        print("  L(rec %d -> rec %d) = min(tail=%d, block0=%d) = %d  (limited by %s)"
              % (ia, ib, len(oa['blocks'][-1]), len(ob_['blocks'][0]), L, which))
    print("[engine] splice verification: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def cmd_verify_finalize(obb, recs):
    eng = Engine(obb.path)
    idx_a, idx_b = recs[0], recs[-1]
    wa, oa = eng.unit(idx_a)
    wb, ob_ = eng.unit(idx_b)
    ok = True
    for flag, want in ((1, 0), (1, 7), (0, 0)):
        st = eng.new_streamer()
        eng.splice_call(st, wa, 1)
        eng.splice_call(st, wb, flag)
        eng.mark_sync(st)
        pos_tail = st['pos'] + st['tail']
        r = eng.lib.call(V_618A8, [st['addr'], want, 0])
        n = eng.lib.u32(r + 8)
        got = list(struct.unpack('<%dh' % n, eng.lib.rd(eng.lib.u32(r + 0x10), n * 2)))
        pst = dict(rate=eng.rate, cap=st['cap'], pos=0, tail=0, total=0,
                   out=[0] * st['cap'])
        splice(pst, oa, 1)
        splice(pst, ob_, flag)
        mine = finalize(pst, want)
        nd = sum(1 for a, b in zip(got, mine) if a != b) + abs(len(got) - len(mine))
        print("  flag=%d want=%-3d: engine result n=%-5d (buffer pos_tail=%d) | model n=%-5d "
              "| diffs=%d" % (flag, want, n, pos_tail, len(mine), nd))
        if nd or n != len(mine):
            ok = False
    print("[engine] finalize verification: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--record', type=int, default=1)
    ap.add_argument('--records', default=None, help='comma list for the verify modes')
    ap.add_argument('--show', action='store_true')
    ap.add_argument('--analyze', action='store_true', help='with --show: pitch track vs ramp')
    ap.add_argument('--check-win', action='store_true', help='check the window tables vs the .so')
    ap.add_argument('--verify-engine', action='store_true')
    ap.add_argument('--verify-splice', action='store_true')
    ap.add_argument('--verify-finalize', action='store_true')
    ap.add_argument('--flags', default='0,1')
    args = ap.parse_args()

    if args.check_win:
        print("window tables == .so @0x152718/0x15275c:", _check_win_tables())

    obb = du.Obb(args.obb or du.find_obb('kendra'))
    print("[obb] %s  rate_field=%d type=%d" % (obb.path, obb.rate, obb.type))

    if args.verify_engine:
        return cmd_verify_engine(obb, _recs(args.records or str(args.record)))
    if args.verify_splice:
        return cmd_verify_splice(obb, _recs(args.records or '0,1'), _recs(args.flags))
    if args.verify_finalize:
        return cmd_verify_finalize(obb, _recs(args.records or '0,1'))
    if args.show or True:
        cmd_show(obb, [args.record] if args.records is None else _recs(args.records),
                 args.analyze)
    return 0


if __name__ == '__main__':
    sys.exit(main())
