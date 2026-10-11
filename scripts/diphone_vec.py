#!/usr/bin/env python3
"""`FUN_0005f1dc` (engine) — the 36-byte diphonedb record -> 96-byte feature vector.

The target cost `FUN_00031234` -> `FUN_000309a4` compares a *candidate record*,
decoded by `FUN_0005f1dc`, with a *context vector* built by `FUN_00060ed4` from
the utterance's Festival item graph.  This module is the candidate side: it turns
a section-C record into the same 96-byte layout `scripts/prosody.py:Vec96`
already consumes.

Inputs (all shipped in the OBB, no emulation):

* `rec`     = the 36-byte section-C record (`refimpl/cdxv.py: c_record(u)`)
* `D`       = section D byte pool (`d_pool()`) — the record's "extended data",
              reached by the u32 at `rec+0x20` (diphonedb payload field 6)
* `E`       = section E, 58 x 32-byte phone/class names (`phonemes()`); the
              diphonedb payload field 7 ("model blocks") is exactly this table,
              indexed by a byte with stride 0x20.

Decompiled body (`out/ghidra_dump/libttsivonavoice.c:42602-42667`, ELF vaddr
0x5f1dc; `param_2` is `undefined2*`, so Ghidra's `param_2 + n` means byte `2n`):

    out[0]  = f32(i16(rec+0)) / 1000.0f              # duration, seconds
    out[1]  = E + u8(rec+2)*0x20                     # p.p.name
    out[2]  = E + u8(rec+3)*0x20                     # p.name
    out[3]  = E + u8(rec+4)*0x20                     # name      (this unit's L)
    out[4]  = E + u8(rec+5)*0x20                     # n.name
    out[5]  = E + u8(rec+6)*0x20                     # n.n.name
    out[6]  = u8(rec+7) & 0xf                        # pos_in_syl + 1
    out[0x19]= u8(rec+7) >> 4                        # (1-pos_in_syl)+syl_num_phones
    x = D + u32(rec+0x20)                            # the record's ext block
    out[0x1a]= x[0] & 0xf ; out[0x1b] = x[0] >> 4
    out[0x1c]= x[1]
    out[0x1d]= x[2] & 0xf ; out[0x1e] = x[2] >> 4
    out[0x1f..0x27] = x[3..11]                       # 9 bytes
    out[0x28]= E + x[0xc]*0x20                       # syl_vowel
    out[0x2c]= x[0xd] & 0xf ; out[0x2d] = x[0xd] >> 4
    out[0x2e]= x[0xe]
    y = x + u16(x+0xf)
    out[0x30]= E + y[0]*0x20                         # p.gpos
    out[0x34]= y[1]
    out[0x38]= E + y[2]*0x20                         # gpos
    out[0x3c]= y[3] ; out[0x3d]= y[4] ; out[0x3e]= y[5]
    out[0x40]= E + y[6]*0x20                         # n.gpos
    out[0x44]= y[7]
    z = y + u16(y+8)
    out[0x45..0x4a] = z[0..5]
    out[0x4c]= E + z[6]*0x20                         # endtone
    out[0x50]= z[7] ; out[0x51]= z[8]
    out[0x54]=out[0x58]=out[0x5c]= 0                 # ph_vc/cvox/ctype cleared

Verified against the emulator: `scripts/probe_record_vec.py` diffs this port
against the real `FUN_0005f1dc` under Unicorn for every record of the OBB.
"""

from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prosody                                              # noqa: E402

#: offsets whose 4-byte slot holds a *string* pointer in the 96-byte vector.
STR_SLOTS = (0x04, 0x08, 0x0C, 0x10, 0x14, 0x28, 0x30, 0x38, 0x40, 0x4C)


class RecordDecoder:
    """`FUN_0005f1dc` over one OBB's section C/D/E."""

    def __init__(self, c_records, d_pool: bytes, phonemes):
        """`c_records` = callable u -> 36 bytes; `d_pool` = section D; `phonemes` = section E."""
        self.c = c_records
        self.d = d_pool
        self.e = [p.encode("latin1")[:31] for p in phonemes]
        self._E = {}
        self._cache = {}

    # ---- primitives --------------------------------------------------------
    def _ename(self, idx: int) -> str:
        if 0 <= idx < len(self.e):
            return self.e[idx].split(b"\x00")[0].decode("latin1")
        return "?%d" % idx            # out-of-range: the engine would read past E

    def _d8(self, off: int) -> int:
        return self.d[off]

    def _d16(self, off: int) -> int:
        return self.d[off] | (self.d[off + 1] << 8)

    def _d32(self, off: int) -> int:
        return struct.unpack_from("<I", self.d, off)[0]

    # ---- the decode --------------------------------------------------------
    def vector(self, unit: int) -> prosody.Vec96:
        """96-byte `Vec96` for section-C record `unit` (memoised)."""
        hit = self._cache.get(unit)
        if hit is not None:
            return hit
        rec = self.c(unit)
        raw = bytearray(0x60)
        strs = {}
        struct.pack_into("<f", raw, 0x00, struct.unpack_from("<h", rec, 0)[0] / 1000.0)
        for k, off in enumerate((0x04, 0x08, 0x0C, 0x10, 0x14)):
            strs[off] = self._ename(rec[2 + k])
        raw[0x18] = rec[7] & 0x0F
        raw[0x19] = rec[7] >> 4
        o = struct.unpack_from("<I", rec, 0x20)[0]
        # ext block
        raw[0x1A] = self._d8(o) & 0x0F
        raw[0x1B] = self._d8(o) >> 4
        raw[0x1C] = self._d8(o + 1)
        raw[0x1D] = self._d8(o + 2) & 0x0F
        raw[0x1E] = self._d8(o + 2) >> 4
        raw[0x1F:0x28] = self.d[o + 3:o + 12]
        strs[0x28] = self._ename(self._d8(o + 0x0C))
        raw[0x2C] = self._d8(o + 0x0D) & 0x0F
        raw[0x2D] = self._d8(o + 0x0D) >> 4
        raw[0x2E] = self._d8(o + 0x0E)
        y = o + self._d16(o + 0x0F)
        strs[0x30] = self._ename(self._d8(y + 0))
        raw[0x34] = self._d8(y + 1)
        strs[0x38] = self._ename(self._d8(y + 2))
        raw[0x3C] = self._d8(y + 3)
        raw[0x3D] = self._d8(y + 4)
        raw[0x3E] = self._d8(y + 5)
        strs[0x40] = self._ename(self._d8(y + 6))
        raw[0x44] = self._d8(y + 7)
        z = y + self._d16(y + 8)
        raw[0x45:0x4B] = self.d[z + 0:z + 6]
        strs[0x4C] = self._ename(self._d8(z + 6))
        raw[0x50] = self._d8(z + 7)
        raw[0x51] = self._d8(z + 8)
        vec = prosody.Vec96(bytes(raw), strs)
        self._cache[unit] = vec
        return vec


def record_decoder(reader) -> RecordDecoder:
    """Build a `RecordDecoder` from a `refimpl.cdxv.OBBReader`."""
    return RecordDecoder(reader.c_record, reader.d_pool(), reader.phonemes())


def main(argv=None):
    """Sanity dump: decode the records named on the command line (default 0..3)."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("units", nargs="*", type=int, default=[0, 1, 2, 3])
    ap.add_argument("--obb", default=None)
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "refimpl"))
    import cdxv
    obb = a.obb or os.path.join(
        os.path.dirname(HERE),
        "IVONA 2/IVONA Kendra US English beta_v1.6.23.422_apkfab.com/Android/obb/"
        "com.ivona.tts.voicebeta.eng.usa.kendra/"
        "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")
    r = cdxv.OBBReader(obb)
    dec = record_decoder(r)
    for u in (a.units or [0, 1, 2, 3]):
        v = dec.vector(u)
        print("unit %d: dur=%.3fs" % (u, v.f32_0()))
        for off in STR_SLOTS:
            print("   slot %#04x = %r" % (off, v.st(off)))
        print("   bytes:", v.b.hex())
    return 0


if __name__ == "__main__":
    sys.exit(main())
