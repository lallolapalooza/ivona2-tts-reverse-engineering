#!/usr/bin/env python3
"""Pure-Python reader/writer for the Kendra/IVONA *packed* lexicon blob.

Verified against `FUN_0003e2b4` (vaddr 0x2e2b4) under the emulation harness
(`scripts/verify_g2p.py`).

Blob record layout (stored so that the key is sorted ascending by key[1:]):

    <pron bytes>  0xFF  <key bytes>  0x00      <- repeated

    * key bytes   : u8 indices into the 256-entry *fragment pool*
                    (LexInfo+0x20); the decoded string is `tag + word`
                    where `tag` is a single char (part of speech, "n"/"v"/...),
                    "0" for the default entry.  Terminated by a 0x00 byte.
    * pron bytes  : u8 indices into the *syllable table* (LexInfo+0x1C).
                    Read *backward* from the 0xFF down to the preceding 0x00.
                    Each index selects a NUL-terminated byte string whose
                    bytes are indices into the *phone table* (LexInfo+0x10).
                    Syllables concatenate in forward address order.

The binary search in the engine finds record starts as positions p with
blob[p-1] == 0xFF and compares `key[1:]` against the query word (then the
whole key against tag+word).

Usage:  python3 scripts/lex_decode.py WORD [WORD ...]   # lookup, no LTS fallback
        python3 scripts/lex_decode.py --dump N          # first N records
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")

# en-US instance of LexInfo (vaddr = Ghidra label - 0x1000 for .rodata here)
LEX_BLOB = 0x64BFC
LEX_COUNT = 0x1EE0C
LEX_LEN = 0x166E60
LEX_PHONES = 0x2E7FC4
LEX_SYLL = 0x2E80F4
LEX_POOL = 0x2E84F8


class Lexicon:
    def __init__(self, so=SO):
        d = open(so, "rb").read()
        self.d = d

        def cstr(p):
            if not p:
                return ""
            return d[p:d.index(b"\0", p)].decode("latin1")

        self.pool = [cstr(struct.unpack_from("<I", d, LEX_POOL + 4 * i)[0])
                     for i in range(256)]
        self.syll = {}
        for i in range(257):
            p = struct.unpack_from("<I", d, LEX_SYLL + 4 * i)[0]
            if p:
                self.syll[i] = p
        self.phones = []
        i = 0
        while True:
            p = struct.unpack_from("<I", d, LEX_PHONES + 4 * i)[0]
            if p == 0:
                break
            self.phones.append(cstr(p))
            i += 1

        # records in file (= sorted) order
        self.records = []          # (key, [phone,...])
        blob = d[LEX_BLOB:LEX_BLOB + LEX_LEN]
        self.blob = blob
        n = len(blob)
        p = 0
        while p < n:
            if blob[p] != 0xFF:
                p += 1
                continue
            # key forward
            k = p + 1
            key = []
            while blob[k] != 0:
                key.append(self.pool[blob[k]])
                k += 1
            key = "".join(key)
            # pron backward from p-1 down to the preceding 0x00
            q = p - 1
            back = []
            while q >= 0 and blob[q] != 0:
                back.append(blob[q])
                q -= 1
            phones = []
            for s in reversed(back):        # fragments in forward address order
                sp = self.syll.get(s)
                if sp is None:
                    continue
                while d[sp] != 0:
                    idx = d[sp]
                    phones.append(self.phones[idx] if idx < len(self.phones) else "?%d" % idx)
                    sp += 1
            self.records.append((key, phones))
            p = k

    def lookup(self, word, tag="0"):
        want = tag + word
        for key, phones in self.records:
            if key == want:
                return list(phones)
        return None


def main():
    lx = Lexicon()
    args = sys.argv[1:]
    if args and args[0] == "--dump":
        for key, ph in lx.records[:int(args[1])]:
            print("%-24s %s" % (key, " ".join(ph)))
        return
    for w in args or ["cat"]:
        r = lx.lookup(w)
        print("%-16s %s" % (w, " ".join(r) if r else "(not found)"))


if __name__ == "__main__":
    main()
