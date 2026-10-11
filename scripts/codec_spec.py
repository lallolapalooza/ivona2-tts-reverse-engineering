#!/usr/bin/env python3
"""Clean-room decoder for the IVONA acoustic "gap" codec -- no Unicorn.

Decodes one unit record of a shipped OBB (``main.199.*.obb``) to PCM, using only
the Python standard library plus the ported stage modules under
``scripts/codec_parts`` (``parse``, ``dequant``, ``setup``, ``gain``, ``xform``,
``post`` + ``dsp``) and the static table image ``out/codec/tables.bin``.

The packet layer (length-prefixed packets + the self-keyed XOR obfuscation) is
re-implemented here from ``report_gap_codec.md``; the per-frame stage order and
the driver semantics mirror the engine's ``FUN_00147c58`` / ``FUN_00147f74``
(ELF vaddrs 0x137c58 / 0x137f74).

Usage
  ~/venvs/re/bin/python scripts/codec_spec.py --record 3 --out out/gap/spec3.wav
  ~/venvs/re/bin/python scripts/codec_spec.py --record 0 --dump-stage xform
  ~/venvs/re/bin/python scripts/codec_spec.py --obb <amy.obb> --record 1 --rate 22050 --out amy1.wav
"""
import argparse
import array
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'codec_parts'))

from prims import ld_s32, ld_u32, st_u32, s32, divsi3          # noqa: E402
import parse as _parse                                    # noqa: E402
import dequant as _dequant                                # noqa: E402
import setup as _setup                                    # noqa: E402
import gain as _gain                                      # noqa: E402
import post as _post                                      # noqa: E402
import dsp as _dsp                                        # noqa: E402
import xform as _xform                                    # noqa: E402
try:
    import resample as _resample                          # noqa: E402
except ImportError:                                       # pragma: no cover
    _resample = None

CTX_SIZE = 0x3570
RATE = 24000                      # the codec's native rate index 24 -> 24 kHz
FRAMES_PER_PACKET = 5
SAMPLES_PER_FRAME = 480


# --------------------------------------------------------------------------- #
# container front-end (see report_gap_codec.md)
# --------------------------------------------------------------------------- #
def find_obb(voice='kendra'):
    import glob
    pats = [
        os.path.join(ROOT, 'IVONA 2', '*', 'Android', 'obb', '*', 'main.199.*.obb'),
        os.path.join(ROOT, 'out', 'obb', 'main.199.*.obb'),
    ]
    hits = []
    for p in pats:
        hits += glob.glob(p)
    hits = sorted(set(hits))
    if voice:
        v = [h for h in hits if voice in h.lower()]
        if v:
            hits = v
    if not hits:
        raise SystemExit('no main.199.*.obb found; pass --obb')
    return hits[0]


def deobfuscate(payload, cksum):
    """Self-keyed XOR: key = u32le(header checksum) || (payload[n&~3:] padded to 4)."""
    n = len(payload)
    p = bytearray(payload)
    m = n & ~3
    key = struct.pack('<I', cksum) + (bytes(p[m:n]) + b'\x00' * 4)[:4]
    for i in range(m):
        p[i] ^= key[i % 8]
    return bytes(p)


def iter_packets(buf):
    """Walk a gap window as ``u16le len; u8 payload[len]`` packets."""
    i, out = 0, []
    while i + 2 <= len(buf):
        ln = struct.unpack_from('<H', buf, i)[0]
        if i + 2 + ln > len(buf):
            break
        out.append((i, buf[i + 2:i + 2 + ln]))
        i += 2 + ln
    return out, i


class Obb(object):
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as fh:
            self.data = fh.read()
        d = self.data
        if d[:4] != b'CDXV':
            raise SystemExit('not a CDXV file: %s' % path)
        self.name = d[4:0x24].split(b'\x00')[0].decode('latin1')
        self.rate = struct.unpack_from('<I', d, 0x24)[0]
        self.type = struct.unpack_from('<I', d, 0x28)[0]
        self.cksum = struct.unpack_from('<I', d, 0x2C)[0]
        self.index_off = struct.unpack_from('<I', d, 0x30)[0]
        self.index_len = struct.unpack_from('<I', d, 0x34)[0]
        self.gap_off = struct.unpack_from('<I', d, 0x38)[0]
        self.n_rec = self.index_len // 8
        self.pairs = dict(zip(
            ('index', 'gap', 'A', 'B', 'C', 'D', 'E'),
            [(struct.unpack_from('<II', d, 0x30 + 8 * k)) for k in range(7)]))

    def index(self, i):
        return struct.unpack_from('<II', self.data, self.index_off + i * 8)

    def record(self, i):
        off, ln = self.index(i)
        if off == 0 or ln < 12:
            return None
        d = self.data
        n = struct.unpack_from('<H', d, off)[0]
        if 2 * n + 12 != ln:
            return None
        ramp = struct.unpack_from('<%dH' % n, d, off + 2)
        y = struct.unpack_from('<H', d, off + 2 + 2 * n)[0]
        goff, glen = struct.unpack_from('<II', d, off + 2 + 2 * n + 2)
        return dict(i=i, off=off, ln=ln, N=n, ramp=ramp, Y=y,
                    gap_off=goff, gap_len=glen, samples=ramp[-1])

    def window(self, rec):
        return self.data[rec['gap_off']:rec['gap_off'] + rec['gap_len']]


# --------------------------------------------------------------------------- #
# codec driver (FUN_00147c58 / FUN_00147f74 / FUN_0014e248)
# --------------------------------------------------------------------------- #
def codec_reset(ctx):
    """FUN_0014e248: memset(ctx,0,0x3570); cb0(ctx,24); ..."""
    ctx[:] = b'\x00' * CTX_SIZE
    _parse.cb0(ctx, RATE // 1000)                  # 0x18
    st_u32(ctx, 0x2c2c, 1)
    st_u32(ctx, 0x414, 0x10000)
    _dsp.f14dca4(ctx)
    st_u32(ctx, 0x3514, s32(ld_s32(ctx, 0x2be0)) >> 1)      # FUN_00149e34


class Spec(object):
    def __init__(self, out_rate=None):
        self.out_rate = out_rate            # None -> decode at the codec rate (24000)
        self.rs = None
        self.ctx = bytearray(CTX_SIZE)
        self.info = bytearray(0x40)
        self.fi = bytearray(0x200)          # frame_info
        self.coeffs = bytearray(0x2000)     # 480 int32 (probe-sized)
        self.samp = bytearray(0x2000)       # 480 int16 (probe-sized)
        self.tmp = bytearray(0x2000)        # FUN_00147c58's auStack_7ac
        self.dst = None                     # buffer the current frame's stages write to
        self.stage_cb = None
        codec_reset(self.ctx)
        st_u32(self.info, 0, out_rate or RATE)

    def reset(self):
        """Fresh codec context for a new window (FUN_00067a14 does this per unit).

        `decode_window` calls this itself, so a single `Spec` can decode many
        units -- matching `decode_unit.Codec.decode_window`.
        """
        codec_reset(self.ctx)
        st_u32(self.info, 0, self.out_rate or RATE)
        self.rs = None
        self.dst = None

    # ---------------------------------------------------------------- frame
    def frame(self, pkt, param6=0):
        """One FUN_00147c58 -> FUN_00147f74 call.  Returns (ret, consumed, nsamples)."""
        ctx, fi, coeffs, samp = self.ctx, self.fi, self.coeffs, self.samp
        i_var2 = ld_s32(ctx, 0x2be0)                     # 480
        i_var4 = ld_s32(ctx, 0x2bd8)                     # codec rate index (24)
        out_rate = self.out_rate
        codec_hz = i_var4 * 1000
        # FUN_00147c58: __src = samp, unless the output rate differs from the codec rate
        use_tmp = (out_rate is not None and (codec_hz - out_rate) != 0
                   and out_rate <= codec_hz)
        dst = self.tmp if use_tmp else samp
        self.dst = dst
        local_2c = 0
        ret = 0
        if param6 == 0:
            i_var1 = i_var4
            if ld_s32(ctx, 0x2c34) == 0:
                _parse.bitinit(ctx, pkt, len(pkt))
            _parse.parse(ctx, fi, coeffs, 1)
            if ld_s32(ctx, 16) == 0:
                local_2c = s32((ld_u32(ctx, 0) - ld_s32(ctx, 0x2c30)) & 0xFFFFFFFF)
                st_u32(ctx, 0x2c34, s32(ld_s32(ctx, 0x2c34) + 1))
                self._emit('parse')
                _dequant.dequant(ctx, fi, dst, coeffs)
                self._emit('dequant')
                _setup.setup(ctx, fi, dst, i_var2, 0)
                self._emit('setup')
                st_u32(ctx, 0x350c, 0)
                st_u32(ctx, 0x2c2c, 0)
            else:
                st_u32(ctx, 0x2c30, 0)
                _parse.cb0(ctx, i_var1)
                local_2c = ld_u32(ctx, 0)
                ret = s32(0xFFFFFFF5 if ld_s32(ctx, 16) == -8 else 0xFFFFFFF4)
        elif param6 != 1:
            pass
        else:
            _setup.setup(ctx, fi, dst, i_var2, 1)

        # LAB_00148070
        ctx[0x2438:0x2438 + i_var2 * 2] = dst[:i_var2 * 2]
        _gain.gain(ctx, fi, dst, i_var2)
        self._emit('gain')
        _xform.xform(ctx, fi, dst, i_var2)
        self._emit('xform')
        _post.post(dst, ctx, i_var2)
        self._emit('post')

        ns = i_var2
        if out_rate is not None and 8000 <= out_rate <= 48000:
            if out_rate != codec_hz:
                ns = self.resample(dst, i_var2, out_rate, i_var4)
            st_u32(ctx, 0x2bdc, out_rate)
        return ret, local_2c, ns

    def resample(self, src, n_in, out_rate, rate_idx):
        """FUN_00147c58's output-rate branch (memcpy + FUN_0014b6d0/FUN_0014b4a8)."""
        if _resample is None:
            raise RuntimeError('scripts/codec_parts/resample.py is missing')
        ctx = self.ctx
        codec_hz = ld_s32(ctx, 0x2bd8) * 1000
        if ld_s32(ctx, 0x2bd8) != rate_idx or ld_s32(ctx, 0x2bdc) != out_rate:
            self.rs = _resample.Resampler(codec_hz, out_rate)
        n_out = divsi3(out_rate * n_in, codec_hz)
        samples = list(struct.unpack_from('<%dh' % n_in, src, 0))
        out = self.rs.run(samples, n_out)
        out = list(out)[:n_out]
        struct.pack_into('<%dh' % len(out), self.samp, 0, *out)
        return len(out)

    def _emit(self, stage):
        if self.stage_cb is not None:
            self.stage_cb(stage, self)

    # -------------------------------------------------------------- window
    def decode_packet(self, pkt, out):
        """Feed one packet through the FUN_00147c58 loop; append PCM samples."""
        ctx = self.ctx
        first = True
        while True:
            if ld_s32(ctx, 0x2c3c) == 0:
                st_u32(ctx, 0x2c34, 0)
            param6 = 0
            err5 = 0
            if 0x400 < len(pkt) and ld_s32(ctx, 0x2c3c) == 0:
                param6 = 1
                err5 = -0xB
            ret, consumed, ns = self.frame(pkt, param6)
            if consumed != 0:
                if (ld_s32(ctx, 0x2c30) < 1 or ld_s32(ctx, 0x2c40) != 1
                        or 4 < ld_s32(ctx, 0x2c34)):
                    st_u32(ctx, 0x2c38, ld_s32(ctx, 0x2c34))
                    st_u32(ctx, 0x2c3c, 0)
                    if ld_s32(ctx, 0x2cf4) == 1:
                        iv = ld_s32(ctx, 0x2c40)
                        if iv == 0:
                            iv = ld_s32(ctx, 0x2cf8) + 1
                            st_u32(ctx, 0x2cf8, iv)
                            if 10 < iv:
                                st_u32(ctx, 0x2cfc, 0)
                        elif iv == 2:
                            st_u32(ctx, 0x2cfc, 1)
                            st_u32(ctx, 0x2cf8, 0)
                        elif iv == 3:
                            st_u32(ctx, 0x2cfc, 2)
                            st_u32(ctx, 0x2cf8, 0)
                else:
                    st_u32(ctx, 0x2c3c, 1)
            ret = s32(ret + err5)
            if ret != 0:
                break
            if ns > 0:
                out.extend(struct.unpack_from('<%dh' % ns, self.samp, 0))
            if ld_s32(ctx, 0x2c3c) == 0:
                break
        return ret

    def decode_window(self, cksum, win, y_skip, samples):
        self.reset()                                # fresh context per window (FUN_00067a14)
        pk, tot = iter_packets(win)
        if tot != len(win):
            raise SystemExit('window did not walk cleanly (%d/%d)' % (tot, len(win)))
        raw = []
        for _, pl in pk:
            self.decode_packet(deobfuscate(pl, cksum), raw)
        if y_skip:
            raw = raw[y_skip:]
        raw = raw[:samples]
        if len(raw) < samples:
            raw += [0] * (samples - len(raw))
        return raw


# --------------------------------------------------------------------------- #
def write_wav(path, pcm, rate, ch=1):
    a = array.array('h', pcm)
    with wave.open(path, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(a.tobytes())


def rms(pcm):
    if not pcm:
        return 0.0
    return (sum(float(x) * x for x in pcm) / len(pcm)) ** 0.5


DUMP_DIR = os.path.join(ROOT, 'out', 'codec', 'spec_stages')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--record', type=int, default=0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--rate', type=int, default=None,
                    help='output rate (default: the OBB\'s declared rate, 22050)')
    ap.add_argument('--dump-stage', default=None,
                    help='dump ctx/frame_info/coeffs/samp after this stage (first frame)')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()

    obb = Obb(args.obb or find_obb())
    print('OBB   %s  name=%s rate=%d type=%d cksum=%#x recs=%d'
          % (obb.path, obb.name, obb.rate, obb.type, obb.cksum, obb.n_rec))

    if args.list:
        n = 0
        for i in range(obb.n_rec):
            rec = obb.record(i)
            if rec and rec['N'] >= 16:
                pk, tot = iter_packets(obb.window(rec))
                print('rec %5d N=%3d Y=%5d gap_len=%6d samples=%6d pkts=%d ok=%s'
                      % (i, rec['N'], rec['Y'], rec['gap_len'], rec['samples'],
                         len(pk), tot == rec['gap_len']))
                n += 1
                if n >= 20:
                    break
        return

    rec = obb.record(args.record)
    if rec is None:
        raise SystemExit('record %d is empty/invalid' % args.record)
    win = obb.window(rec)
    pk, tot = iter_packets(win)
    print('record %d: N=%d Y=%d gap_len=%d samples=%d packets=%d walk=%d/%d'
          % (rec['i'], rec['N'], rec['Y'], rec['gap_len'], rec['samples'],
             len(pk), tot, rec['gap_len']))

    sp = Spec(out_rate=args.rate or obb.rate)
    out_rate = args.rate or obb.rate
    if args.dump_stage:
        os.makedirs(DUMP_DIR, exist_ok=True)
        state = {}

        def cb(stage, s):
            if stage == args.dump_stage and 'done' not in state:
                state['done'] = True
                for name, buf in (('ctx', s.ctx), ('frame_info', s.fi),
                                  ('coeffs', s.coeffs),
                                  ('samp', s.dst if s.dst is not None else s.samp)):
                    with open(os.path.join(DUMP_DIR, '%s.bin' % name), 'wb') as fh:
                        fh.write(bytes(buf))
                print('dumped %s buffers to %s' % (args.dump_stage, DUMP_DIR))
        sp.stage_cb = cb

    pcm = sp.decode_window(obb.cksum, win, rec['Y'], rec['samples'])
    nz = sum(1 for x in pcm if x)
    print('decoded: %d samples (ramp_last=%d) rms=%.1f min=%d max=%d nonzero=%d'
          % (len(pcm), rec['samples'], rms(pcm), min(pcm), max(pcm), nz))
    if args.out:
        write_wav(args.out, pcm, out_rate)
        print('wrote %s (%d samples, %d Hz, %.4f s)'
              % (args.out, len(pcm), out_rate, len(pcm) / float(out_rate)))


if __name__ == '__main__':
    main()
