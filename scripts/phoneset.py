#!/usr/bin/env python3
"""The voice plug-in's *static phone set* table (Festival-style phone features).

`libvoice_*.so` registers a `phoneset` VAL (tag 0x19) built at compile time; the
engine's `FUN_0006f75c(params, phone, feat)` indexes it to answer the item
features `ph_vc`, `ph_cvox`, `ph_ctype`, ... that the synthesiser copies into the
96-byte context vector (`FUN_00060ed4`, slots 0x54/0x58/0x5c) and that the
diphone-graph dispatcher `FUN_00030214` uses to choose the join-cost variant.

Layout (report_engine_synth.md sec.3.4; verified by decoding the shipped
plug-ins here):

    struct PhoneSet {                // .data.rel.ro, reached from
        char  *name;                 //   `PTR_s_x_ivona_en_us_...` (field 0
        char **feature_names;        //   *is* the name string pointer)
        void **value_table;          // symbol values: VAL{tag=5 -> char*}
        char **phone_names;          // sorted (binary search enabled)
        char  *silence;              // "pau"
        int    n_phones;
        int  **matrix;               // matrix[phone] = row of feature indices
        int    sorted;               // 1
    };

`FUN_0006f75c` returns `value_table[ matrix[phone][feat] ]`, where the values are
typed VALs (tag 5 = string), so the cost model sees strings such as `+`, `-`,
`0`, `l`, `f`, `p`, ...

Usage:
    python3 scripts/phoneset.py [--so PATH]            # dump the table
    from phoneset import PhoneSet
    ps = PhoneSet.from_so("out/libs/kendra/libvoice_en_us_kendra.so")
    ps.get("r")            # {'vc': '-', 'cvox': '+', 'ctype': 'x', ...}
"""

from __future__ import annotations

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")

#: the feature names the engine's item features expose (`ph_<name>`).
FEATURES = ("vc", "cvox", "vlng", "vheight", "vfront", "vrnd", "ctype", "cplace")


class _Elf:
    """Minimal vaddr -> bytes reader over PT_LOAD segments."""

    def __init__(self, path):
        from elftools.elf.elffile import ELFFile
        self.raw = open(path, "rb").read()
        elf = ELFFile(open(path, "rb"))
        self.loads = []
        for s in elf.iter_segments():
            if s["p_type"] == "PT_LOAD" and s["p_filesz"]:
                self.loads.append((s["p_vaddr"], s["p_offset"], s["p_filesz"]))

    def read(self, vaddr, n):
        for va, off, fsz in self.loads:
            if va <= vaddr < va + fsz:
                o = off + (vaddr - va)
                return self.raw[o:o + n]
        raise KeyError(vaddr)

    def u32(self, vaddr):
        return struct.unpack("<I", self.read(vaddr, 4))[0]

    def i32(self, vaddr):
        return struct.unpack("<i", self.read(vaddr, 4))[0]

    def cstr(self, vaddr, n=64):
        return self.read(vaddr, n).split(b"\x00")[0].decode("latin1")

    def find(self, needle, start=0):
        """All vaddrs of `needle` (searched per segment)."""
        hits = []
        for va, off, fsz in self.loads:
            i = start
            while True:
                j = self.raw.find(needle, off + i, off + fsz)
                if j < 0:
                    break
                hits.append(va + (j - off))
                i = j - off + 1
        return hits


class PhoneSet:
    """The plug-in's static phone inventory with its 8 Festival features."""

    def __init__(self, name, features, phones, values, matrix, silence):
        self.name = name
        self.features = features          # ['vc','cvox',...]
        self.phones = phones              # sorted phone names
        self.silence = silence
        self._values = values             # feature index -> value symbol (str|int)
        self._matrix = matrix             # phone name -> [value index per feature]
        self._cache = {}

    # ---- construction ------------------------------------------------------
    @classmethod
    def from_so(cls, so_path: str, name: str = None) -> "PhoneSet":
        """Load the phoneset `name` (e.g. "x-ivona-en_us").

        Each plug-in ships *both* the en-US and the en-GB phone set (48 vs 44
        phones) and `register_voice` picks one by language
        (`libvoice_kendra.c:9455-9480`); `name=None` prefers en-US when present.
        """
        e = _Elf(so_path)
        found = {}
        for nv in e.find(b"x-ivona-en_"):
            nm = e.cstr(nv)
            if not nm.startswith("x-ivona-"):
                continue
            for pv in e.find(struct.pack("<I", nv)):
                st = cls._try_struct(e, pv, nm)
                if st is not None:
                    found.setdefault(nm, st)
        if not found:
            raise KeyError("no phoneset struct found in %s" % so_path)
        if name is not None:
            if name not in found:
                raise KeyError("phoneset %r not in %s (have %s)"
                               % (name, so_path, sorted(found)))
            return found[name]
        for pref in ("x-ivona-en_us", "x-ivona-en_gb"):
            if pref in found:
                return found[pref]
        return found[sorted(found)[0]]

    @staticmethod
    def _try_struct(e, st, name):
        try:
            fn_tbl = e.u32(st + 4)
            sym_tbl = e.u32(st + 8)
            ph_tbl = e.u32(st + 0xC)
            silence = e.cstr(e.u32(st + 0x10), 8)
            n = e.u32(st + 0x14)
            mat = e.u32(st + 0x18)
            if not (0 < n <= 256) or not (0x1000 < fn_tbl < 1 << 32):
                return None
            feats = []
            i = 0
            while i < 16:
                p = e.u32(fn_tbl + 4 * i)
                if p == 0:
                    break
                feats.append(e.cstr(p, 24))
                i += 1
            if tuple(feats) != FEATURES:
                return None
            phones = []
            for k in range(n):
                ph = e.cstr(e.u32(ph_tbl + 4 * k), 32)
                phones.append(ph)
            if "pau" not in phones or silence != "pau":
                return None
            vals = []
            for k in range(64):
                p = e.u32(sym_tbl + 4 * k)
                if p == 0:
                    break
                vals.append(PhoneSet._val(e, p))
            matrix = {}
            for k in range(n):
                row = e.u32(mat + 4 * k)
                matrix[phones[k]] = [e.i32(row + 4 * f) for f in range(len(feats))]
            return PhoneSet(name, feats, phones, vals, matrix, silence)
        except Exception:
            return None

    @staticmethod
    def _val(e, p):
        tag, _rc, payload = struct.unpack("<hhI", e.read(p, 8))
        if tag == 5:
            return e.cstr(payload, 24)
        if tag == 1:
            return struct.unpack("<i", struct.pack("<I", payload))[0]
        return "tag%d" % tag

    # ---- lookup ------------------------------------------------------------
    def get(self, phone: str) -> dict:
        """Feature dict for `phone`; unknown phones fall back to `pau` (all zeros)."""
        if phone in self._cache:
            return self._cache[phone]
        row = self._matrix.get(phone)
        if row is None:
            out = {f: "0" for f in self.features}
        else:
            out = {f: self._values[i] if 0 <= i < len(self._values) else "?%d" % i
                   for f, i in zip(self.features, row)}
        self._cache[phone] = out
        return out

    def phoneme_feats(self, phone: str, *names) -> str:
        """Convenience: `ph_*` item features (strings) for one or more feature names."""
        d = self.get(phone)
        vals = [str(d[n]) for n in names]
        return vals[0] if len(vals) == 1 else vals

    def vowels(self):
        return [p for p in self.phones if self.get(p)["vc"] == "+"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so", default=DEFAULT_SO)
    a = ap.parse_args(argv)
    ps = PhoneSet.from_so(a.so)
    print("[phoneset] %s  phones=%d  silence=%s  features=%s"
          % (ps.name, len(ps.phones), ps.silence, " ".join(ps.features)))
    print("%-6s %s" % ("phone", " ".join("%-8s" % f for f in ps.features)))
    for p in ps.phones:
        d = ps.get(p)
        print("%-6s %s" % (p, " ".join("%-8s" % d[f] for f in ps.features)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
