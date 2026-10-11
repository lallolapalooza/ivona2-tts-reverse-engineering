#!/usr/bin/env python3
"""
decode_unit.py -- decode an acoustic "gap" unit from an IVONA 2 `main.199.*.obb` to PCM/WAV.

The gap payload is a *continuous stream of length-prefixed, obfuscated packets* decoded by a
proprietary fixed-point transform codec embedded in `libttsivonavoice.so` (it is NOT
zlib/deflate/vorbis/mp3 -- see report_gap_codec.md).  This tool reproduces the exact engine
code path (`FUN_00067db8` -> `FUN_00067a14` -> `FUN_00147c58`) by emulating the original ARM
code with Unicorn, so the output is bit-faithful to the shipped engine.

Container summary (Kendra / Amy `main.199.*.obb`):
  header 0x00 "CDXV"; 0x24 u32 sample rate (22050); 0x28 u32 type (14); 0x2C u32 "checksum"
  (per-file de-obfuscation seed); 0x30 u32 index off (=0x68); 0x34 u32 index len (N*8);
  0x38/0x3C gap (off,0); 0x40.. pairs (off,len) for tables A..E.
  index entry i = {u32 rec_off, u32 rec_len}; record = u16 N; u16 ramp[N]; u16 Y;
  u32 gap_off; u32 gap_len   (rec_len == 2N+12).
  gap window = a byte range of the gap stream = k whole packets of `u16le len; len bytes`.

De-obfuscation of one packet p (n = len):
  m   = n & ~3
  key = le32(checksum) || p[m:n] (zero-padded to 4 bytes)
  p[i] ^= key[i % 8]   for i in 0..m-1        # last n&3 bytes unchanged

The de-obfuscated packets are fed to the codec (`FUN_00147c58`) from a freshly reset context
(`FUN_0014e248`); the first `Y` decoded samples are discarded (codec delay), after which up to
`ramp[N-1]` samples are the unit waveform.

Usage:
  decode_unit.py [--obb FILE] [--record N] [--out OUT.wav] [--rate HZ] [--list]
                 [--python-decode] [--dump-packets]
Requires: pyelftools + unicorn (see emu/armemu.py) -- use the project venv:
  ~/venvs/re/bin/python scripts/decode_unit.py --record 0 --out unit0.wav
"""
import argparse
import array
import os
import struct
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))

SO = os.path.join(ROOT, 'out', 'libs', 'kendra', 'libttsivonavoice.so')

# Ghidra addr = ELF vaddr + 0x10000 ; addresses below are ELF vaddrs (as used by the emulator)
ADDR_SIZE = 0x13794C        # FUN_0014794c : codec context size (stores 0x3570)
ADDR_RESET = 0x13E248       # FUN_0014e248 : reset/init codec context
ADDR_DECODE = 0x137C58      # FUN_00147c58 : decode one codec frame
ADDR_WINDOW = 0x57A14       # FUN_00067a14 : TLV walk + de-obfuscation + codec; -> PCM


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
        v = hits and [h for h in hits if voice in h.lower()] or []
        if v:
            hits = v
    if not hits:
        raise SystemExit("no main.199.*.obb found; pass --obb")
    return hits[0]


def deobfuscate(payload, cksum):
    """Pure-python front-end transform (verified byte-exact against the engine)."""
    n = len(payload)
    p = bytearray(payload)
    m = n & ~3
    tail = bytes(p[m:n])
    key = struct.pack('<I', cksum) + (tail + b'\x00' * 4)[:4]
    for i in range(m):
        p[i] ^= key[i % 8]
    return bytes(p), key


def iter_packets(buf):
    """Walk a gap window as `u16le len; payload` packets."""
    i, out = 0, []
    while i + 2 <= len(buf):
        L = struct.unpack_from('<H', buf, i)[0]
        if i + 2 + L > len(buf):
            break
        out.append((i, buf[i + 2:i + 2 + L]))
        i += 2 + L
    return out, i


class Obb:
    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        d = self.data
        if d[:4] != b'CDXV':
            raise SystemExit("not a CDXV file: %s" % path)
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
        N = struct.unpack_from('<H', d, off)[0]
        if 2 * N + 12 != ln:
            return None
        ramp = struct.unpack_from('<%dH' % N, d, off + 2)
        Y = struct.unpack_from('<H', d, off + 2 + 2 * N)[0]
        goff, glen = struct.unpack_from('<II', d, off + 2 + 2 * N + 2)
        return dict(i=i, off=off, ln=ln, N=N, ramp=ramp, Y=Y,
                    gap_off=goff, gap_len=glen, samples=ramp[-1])

    def window(self, rec):
        return self.data[rec['gap_off']:rec['gap_off'] + rec['gap_len']]


class Codec:
    """Emulated libttsivonavoice.so gap decoder."""

    def __init__(self, so=SO, rate=24000):
        from armemu import ArmLib
        self.lib = ArmLib(so, verbosity=0)
        self.rate = rate
        self.size = self._size()
        self.ctx = self.lib.alloc(self.size)
        self.wrapper = self.lib.alloc(0x20)

    def _size(self):
        p = self.lib.alloc(4)
        self.lib.call(ADDR_SIZE, [p])
        return self.lib.u32(p)

    def reset(self, cksum):
        self.lib.wr(self.ctx, b'\x00' * self.size)
        self.lib.call(ADDR_RESET, [self.ctx])
        self.lib.wr(self.wrapper, b'\x00' * 0x20)
        self.lib.w32(self.wrapper + 0x00, self.ctx)
        self.lib.w32(self.wrapper + 0x04, self.rate)
        self.lib.w32(self.wrapper + 0x0C, 1)
        self.lib.wr(self.wrapper + 0x18, struct.pack('<I', cksum))

    def decode_window(self, cksum, win, Y, samples):
        """Reproduce FUN_00067a14: returns int16 PCM (list), len == samples."""
        self.reset(cksum)
        buf = self.lib.alloc_data(bytes(win))
        pcm = self.lib.alloc(samples * 2 + 64)
        self.lib.wr(pcm, b'\x00' * (samples * 2 + 64))
        r = self.lib.call(ADDR_WINDOW, [self.wrapper, buf, len(win), Y, pcm, samples])
        if r != 0:
            raise RuntimeError("decode failed: ret=%d" % r)
        a = array.array('h')
        a.frombytes(self.lib.rd(pcm, samples * 2))
        return a.tolist()

    def decode_stream(self, cksum, packets, skip=0, max_samples=None):
        """Direct driver: reset once, de-obfuscate + feed each packet, no per-window reset.

        Mirrors FUN_00067a14: the first `skip` decoded samples are discarded (codec delay),
        then up to `max_samples` are kept."""
        self.reset(cksum)
        sampbuf = self.lib.alloc(65536)
        nsp = self.lib.alloc(4)
        out = []
        pending_skip = skip
        for pkt in packets:
            buf = self.lib.alloc_data(pkt)
            while True:
                self.lib.wr(nsp, b'\x00\x00\x00\x00')
                r = self.lib.call(ADDR_DECODE,
                                  [self.ctx, self.wrapper + 4, 0, buf, len(pkt), sampbuf, nsp])
                if r != 0:
                    break
                ns = struct.unpack('<h', bytes(self.lib.rd(nsp, 2)))[0]
                if ns > 0:
                    a = array.array('h')
                    a.frombytes(self.lib.rd(sampbuf, ns * 2))
                    seg = a.tolist()
                    if pending_skip:
                        k = min(pending_skip, len(seg))
                        pending_skip -= k
                        seg = seg[k:]
                    if seg:
                        out.extend(seg)
                        if max_samples and len(out) >= max_samples:
                            return out[:max_samples]
                if self.lib.u32(self.wrapper + 0x10) == 0:
                    break
        return out


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
    s = sum(float(x) * x for x in pcm)
    return (s / len(pcm)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--obb', default=None)
    ap.add_argument('--record', type=int, default=0)
    ap.add_argument('--out', default=None)
    ap.add_argument('--rate', type=int, default=24000)
    ap.add_argument('--list', action='store_true', help='list first records that decode non-empty')
    ap.add_argument('--dump-packets', action='store_true')
    ap.add_argument('--python-decode', action='store_true',
                    help='drive FUN_00147c58 with the pure-python front-end (no FUN_00067a14)')
    ap.add_argument('--verify', action='store_true',
                    help='cross-check engine path (FUN_00067a14) vs python front-end driver')
    args = ap.parse_args()

    obb = Obb(args.obb or find_obb())
    print("OBB   %s  name=%s rate=%d type=%d cksum=%#x recs=%d gap=[%#x,%#x)"
          % (obb.path, obb.name, obb.rate, obb.type, obb.cksum, obb.n_rec,
             obb.gap_off, obb.pairs['gap'][0] + 0))

    if args.list:
        n = 0
        for i in range(obb.n_rec):
            rec = obb.record(i)
            if rec and rec['N'] >= 16:
                win = obb.window(rec)
                pk, tot = iter_packets(win)
                print("rec %5d off=%#x N=%3d Y=%5d gap_len=%6d samples=%6d pkts=%d ok=%s"
                      % (i, rec['off'], rec['N'], rec['Y'], rec['gap_len'],
                         rec['samples'], len(pk), tot == rec['gap_len']))
                n += 1
                if n >= 20:
                    break
        return

    rec = obb.record(args.record)
    if rec is None:
        raise SystemExit("record %d is empty/invalid" % args.record)
    win = obb.window(rec)
    pk, tot = iter_packets(win)
    print("record %d: N=%d Y=%d gap_off=%#x gap_len=%d samples=%d packets=%d walk=%d/%d"
          % (rec['i'], rec['N'], rec['Y'], rec['gap_off'], rec['gap_len'],
             rec['samples'], len(pk), tot, rec['gap_len']))

    if args.dump_packets:
        for j, (off, pl) in enumerate(pk):
            de, key = deobfuscate(pl, obb.cksum)
            print("  pkt %d @win+%d len=%d key=%s deobf[:16]=%s"
                  % (j, off, len(pl), key.hex(), de[:16].hex(' ')))

    codec = Codec(rate=args.rate)
    if args.verify:
        eng = codec.decode_window(obb.cksum, win, rec['Y'], rec['samples'])
        packets = [deobfuscate(pl, obb.cksum)[0] for _, pl in pk]
        py = codec.decode_stream(obb.cksum, packets, skip=rec['Y'], max_samples=rec['samples'])
        py += [0] * (rec['samples'] - len(py))
        n = min(len(eng), len(py))
        same = sum(1 for i in range(n) if eng[i] == py[i])
        print("VERIFY rec %d: engine(FUN_00067a14) vs python-driver(FUN_00147c58) "
              "identical %d/%d samples" % (rec['i'], same, n))
        sys.exit(0 if same == n else 1)
    if args.python_decode:
        packets = [deobfuscate(pl, obb.cksum)[0] for _, pl in pk]
        pcm = codec.decode_stream(obb.cksum, packets, skip=rec["Y"], max_samples=rec["samples"])
        pcm = pcm + [0] * (rec['samples'] - len(pcm))
    else:
        pcm = codec.decode_window(obb.cksum, win, rec['Y'], rec['samples'])

    nz = sum(1 for x in pcm if x)
    print("decoded: %d samples (ramp_last=%d) rms=%.1f min=%d max=%d nonzero=%d"
          % (len(pcm), rec['samples'], rms(pcm), min(pcm), max(pcm), nz))
    if len(pcm) != rec['samples']:
        print("WARNING: sample count != ramp[N-1]")
    out = args.out or os.path.join(ROOT, 'out', 'gap_unit_%03d.wav' % rec['i'])
    write_wav(out, pcm, args.rate)
    print("wrote %s (%d samples, %d Hz, %.4f s)"
          % (out, len(pcm), args.rate, len(pcm) / float(args.rate)))


if __name__ == '__main__':
    main()
