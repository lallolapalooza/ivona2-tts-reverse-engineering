#!/usr/bin/env python3
"""codec_probe.py -- step-wise oracle for the IVONA gap codec.

Replays one *unit record* of a shipped OBB through the individual codec functions of
`libttsivonavoice.so` **under Unicorn**, taking a snapshot of every buffer after each
call.  The snapshots are the golden vectors that `scripts/codec_spec.py` (the clean-room
Python port) is checked against, one function at a time.

Everything here uses the original ARM code as the oracle -- it is *not* the decoder; the
decoder is `codec_spec.py`, which must never import this module.

Usage
  ~/venvs/re/bin/python scripts/codec_probe.py --record 0 --packets 1
  ~/venvs/re/bin/python scripts/codec_probe.py --record 3 --engine   # whole-path PCM

Requires unicorn + pyelftools (venv ~/venvs/re).
"""
import argparse
import json
import os
import pickle
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))

from decode_unit import Obb, find_obb, deobfuscate, iter_packets   # noqa: E402

SO = os.path.join(ROOT, 'out', 'libs', 'kendra', 'libttsivonavoice.so')
RATE = 24000

# ELF vaddrs of the codec family (Ghidra addr = vaddr + 0x10000)
F_SIZE = 0x13794C      # FUN_0014794c  ctx size
F_RESET = 0x13E248     # FUN_0014e248  reset ctx
F_FRAME = 0x137C58     # FUN_00147c58  frame driver (5 calls / packet)
F_DRIVE = 0x137F74     # FUN_00147f74  per-frame orchestration
F_BITINIT = 0x13B17C   # FUN_0014b17c  range-decoder init from packet bytes
F_PARSE = 0x138190     # FUN_00148190  bitstream parse -> frame_info + coeffs
F_DEQUANT = 0x13E4EC   # FUN_0014e4ec  coeffs -> spectrum (sampbuf)
F_SETUP = 0x13ADD4     # FUN_0014add4  frame -> synth state
F_GAIN = 0x139E54      # FUN_00149e54  gain/AGC on spectrum
F_XFORM = 0x13DD18     # FUN_0014dd18  IMDCT + overlap-add -> 480 samples
F_POST = 0x13DAFC      # FUN_0014dafc  final 2-tap post filter
F_IMDCT8 = 0x150028    # FUN_00150028  transform for the 8-band (0x2be8==10) config
F_IMDCT16 = 0x15027C   # FUN_0015027c  transform for the 16-band config


class Probe:
    def __init__(self, obb_path, record, rate=RATE):
        self.obb = Obb(obb_path) if obb_path else Obb(find_obb())
        self.rec = self.obb.record(record)
        if self.rec is None:
            raise SystemExit('record %d empty/invalid' % record)
        win = self.obb.window(self.rec)
        pk, tot = iter_packets(win)
        assert tot == self.rec['gap_len'], (tot, self.rec['gap_len'])
        self.packets = [deobfuscate(p, self.obb.cksum)[0] for _, p in pk]
        from armemu import ArmLib
        self.lib = ArmLib(SO, verbosity=0)
        p = self.lib.alloc(4)
        self.lib.call(F_SIZE, [p])
        self.ctx_size = self.lib.u32(p)
        self.ctx = self.lib.alloc(self.ctx_size)
        self.info = self.lib.alloc(0x40)
        self.frame_info = self.lib.alloc(0x200)
        self.coeffs = self.lib.alloc(0x2000)
        self.samp = self.lib.alloc(0x2000)
        self.pkt = self.lib.alloc(0x800)
        self.nsp = self.lib.alloc(0x10)
        self.nwin = self.lib.alloc(0x10)
        self.rate = rate
        self.reset()

    # ---------------------------------------------------------------- state
    def zero(self):
        self.lib.wr(self.ctx, b'\x00' * self.ctx_size)
        self.lib.wr(self.info, b'\x00' * 0x40)
        self.lib.wr(self.frame_info, b'\x00' * 0x200)
        self.lib.wr(self.coeffs, b'\x00' * 0x2000)
        self.lib.wr(self.samp, b'\x00' * 0x2000)
        self.lib.wr(self.nsp, b'\x00' * 0x10)
        self.lib.w32(self.info, self.rate)

    def reset(self):
        self.zero()
        self.lib.call(F_RESET, [self.ctx])

    def snapshot(self):
        return {
            'ctx': self.lib.rd(self.ctx, self.ctx_size),
            'frame_info': self.lib.rd(self.frame_info, 0x200),
            'coeffs': self.lib.rd(self.coeffs, 0x2000),
            'samp': self.lib.rd(self.samp, 0x2000),
            'info': self.lib.rd(self.info, 0x40),
            'nsp': self.lib.rd(self.nsp, 0x10),
        }

    def load(self, snap):
        self.lib.wr(self.ctx, snap['ctx'])
        self.lib.wr(self.frame_info, snap['frame_info'])
        self.lib.wr(self.coeffs, snap['coeffs'])
        self.lib.wr(self.samp, snap['samp'])
        self.lib.wr(self.info, snap['info'])
        self.lib.wr(self.nsp, snap['nsp'])

    # ----------------------------------------------------------- primitives
    def call(self, addr, args):
        return self.lib.call(addr, args)

    def blit_packet(self, pkt):
        self.lib.wr(self.pkt, pkt + b'\x00' * (0x800 - len(pkt)))

    # -------------------------------------------------- engine whole path
    def engine_frames(self, npackets=None):
        """Drive FUN_00147c58 exactly like the container does; return the PCM of
        every frame (list of 480-sample lists in order)."""
        self.reset()
        out = []
        pkts = self.packets if npackets is None else self.packets[:npackets]
        for pkt in pkts:
            self.blit_packet(pkt)
            while True:
                self.lib.wr(self.nsp, b'\x00' * 4)
                r = self.lib.call(F_FRAME, [self.ctx, self.info, 0, self.pkt,
                                            len(pkt), self.samp, self.nsp])
                if r != 0:
                    break
                ns = struct.unpack('<h', self.lib.rd(self.nsp, 2))[0]
                if ns > 0:
                    out.append(list(struct.unpack('<%dh' % ns,
                                                  self.lib.rd(self.samp, ns * 2))))
                if self.lib.u32(self.info + 0xc) == 0:   # param_2[3] = ctx[0x2c3c]
                    break
        return out

    # ------------------------------------------------ step-wise replay
    def steps(self, npackets=1, frames=5, imdct_direct=False):
        """Replay frame by frame, calling each codec function separately.

        Returns a list of records:
          {pkt, frame, step, args, before, after}
        `before`/`after` snapshots bracket each call."""
        self.reset()
        seq = []
        pkts = self.packets[:npackets]
        for pi, pkt in enumerate(pkts):
            self.blit_packet(pkt)
            for fi in range(frames):
                sn = {k: v for k, v in self.snapshot().items()}
                if self.lib.u32(self.ctx + 0xb0d * 4) == 0:
                    seq.append(self._step('bitinit', pi, fi,
                                          [self.ctx, self.pkt, len(pkt)],
                                          F_BITINIT))
                seq.append(self._step('parse', pi, fi,
                                      [self.ctx, self.frame_info, self.coeffs, 1],
                                      F_PARSE))
                # FUN_00147f74: frame counter ++ (0xb0d == ctx+0x2c34) on success
                lib = self.lib
                lib.w32(self.ctx + 0x2c34, (lib.u32(self.ctx + 0x2c34) + 1) & 0xffffffff)
                seq.append(self._step('dequant', pi, fi,
                                      [self.ctx, self.frame_info, self.samp, self.coeffs],
                                      F_DEQUANT))
                seq.append(self._step('setup', pi, fi,
                                      [self.ctx, self.frame_info, self.samp, 480, 0],
                                      F_SETUP))
                # memcpy(ctx+0x90e, samp, 480*2); ctx[0xd43]=0; ctx[0xb0b]=0
                lib = self.lib
                lib.wr(self.ctx + 0x2438, lib.rd(self.samp, 960))
                lib.w32(self.ctx + 0x350c, 0)
                lib.w32(self.ctx + 0x2c2c, 0)
                seq.append(self._step('gain', pi, fi,
                                      [self.ctx, self.frame_info, self.samp, 480],
                                      F_GAIN))
                seq.append(self._step('xform', pi, fi,
                                      [self.ctx, self.frame_info, self.samp, 480],
                                      F_XFORM))
                seq.append(self._step('post', pi, fi,
                                      [self.samp, lib.u32(self.ctx + 0xaf5 * 4),
                                       lib.u32(self.ctx + 0xaf4 * 4), self.ctx + 0xaf2 * 4,
                                       self.samp, 480],
                                      F_POST))
        return seq

    def _step(self, name, pi, fi, args, addr):
        before = self.snapshot()
        ret = self.lib.call(addr, args)
        after = self.snapshot()
        return {'pkt': pi, 'frame': fi, 'step': name, 'addr': addr,
                'args': [a if isinstance(a, int) else 0 for a in args],
                'ret': ret, 'before': before, 'after': after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--record', type=int, default=0)
    ap.add_argument('--packets', type=int, default=1)
    ap.add_argument('--frames', type=int, default=5)
    ap.add_argument('--outdir', default=os.path.join(ROOT, 'out', 'codec', 'steps'))
    ap.add_argument('--engine', action='store_true', help='whole-path PCM only')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    P = Probe(args.obb, args.record)
    if args.engine:
        out = P.engine_frames(args.packets)
        pcm = [s for fr in out for s in fr]
        print('engine: %d frames, %d samples, min=%d max=%d nz=%d'
              % (len(out), len(pcm), min(pcm), max(pcm), sum(1 for x in pcm if x)))
        return

    seq = P.steps(args.packets, args.frames)
    os.makedirs(args.outdir, exist_ok=True)
    path = os.path.join(args.outdir, 'rec%06d.pkl' % args.record)
    with open(path, 'wb') as fh:
        pickle.dump({'obb': P.obb.path, 'cksum': P.obb.cksum, 'record': P.rec,
                     'rate': RATE, 'packets': P.packets, 'seq': seq}, fh)
    if not args.quiet:
        print('record %d: %d packets, %d steps -> %s (%.1f MB)'
              % (args.record, len(P.packets), len(seq), path,
                 os.path.getsize(path) / 1e6))
        for r in seq[:12]:
            print('  pkt %d frame %d %-8s ret=%#x  ctx[0x2c34]=%d  samp[0:4]=%s'
                  % (r['pkt'], r['frame'], r['step'], r['ret'],
                     struct.unpack_from('<I', r['after']['ctx'], 0x2c34)[0],
                     struct.unpack_from('<4h', r['after']['samp'], 0)))


if __name__ == '__main__':
    main()
