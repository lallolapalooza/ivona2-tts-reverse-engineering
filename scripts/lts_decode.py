#!/usr/bin/env python3
"""Pure-Python reimplementation of the Kendra/IVONA letter-to-sound FSM.

Model (from `FUN_0003f594`, vaddr 0x2f594; tables in
`libvoice_en_us_kendra.so`):

    context  = "0"*(ctx-1) + "#" + word + "#" + "0"*(ctx-1)      ctx = 4
    for i = last..first word char:
        win = ctx_chars[i-ctx .. i-1] + ctx_chars[i+1 .. i+ctx]  (current char excluded)
        state = letter_table[ord(word[i]) - 'a']
        while fsm[state].pos != 0xFF:
            state = fsm[state].next_if if win[fsm[state].pos] == fsm[state].ch \
                    else fsm[state].next_else
        emit lts_phone_names[fsm[state].ch]        (prepended, so output is L->R)
        "epsilon" -> nothing; a trailing '0' on the name is dropped;
        "A-B" -> two phones A then B.

Usage:  python3 scripts/lts_decode.py WORD [WORD ...]
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(ROOT, "out/libs/kendra/libvoice_en_us_kendra.so")

LETTER_TABLE = 0x1EDA48
FSM = 0x1CC088
LTS_PHONES = 0x2E88FC
CTX = 4


class Lts:
    def __init__(self, so=SO):
        d = open(so, "rb").read()
        self.d = d
        self.letter_table = struct.unpack("<27I", d[LETTER_TABLE:LETTER_TABLE + 108])
        self.phones = []
        i = 0
        while True:
            p = struct.unpack_from("<I", d, LTS_PHONES + 4 * i)[0]
            if p == 0 or p > len(d):
                break
            self.phones.append(d[p:d.index(b"\0", p)].decode("latin1"))
            i += 1
        # FSM records: index -> (pos, ch, next_if, next_else)
        self.fsm = {}
        for idx in range(0x6000):
            a, b, ni, ne = struct.unpack_from("<BBHH", d, FSM + idx * 6)
            self.fsm[idx] = (a, b, ni, ne)
            if idx > 0x6000 - 1:
                break

    def rec(self, idx):
        return self.fsm[idx]

    def lts(self, word):
        ctxs = "0" * (CTX - 1) + "#" + word + "#" + "0" * (CTX - 1)
        out = []
        last = CTX - 1 + len(word)
        if ctxs[last] == "#":
            return []
        for i in range(last, CTX - 1, -1):
            c = ctxs[i]
            o = ord(c)
            if not (0x61 <= o <= 0x7A):
                if c == "#":
                    break
                continue
            win = ctxs[i - CTX:i] + ctxs[i + 1:i + 1 + CTX]
            state = self.letter_table[(o - 0x61) % 26]
            pos, ch, ni, ne = self.rec(state)
            guard = 0
            while pos != 0xFF:
                guard += 1
                if guard > 10000:
                    raise RuntimeError("fsm loop")
                pick = ni if (pos < len(win) and win[pos] == chr(ch)) else ne
                state = pick
                pos, ch, ni, ne = self.rec(state)
            name = self.phones[ch] if ch < len(self.phones) else "?%d" % ch
            emit = []
            for part in name.split("-"):
                if part == "epsilon":
                    continue
                if part.endswith("0"):
                    part = part[:-1]
                emit.append(part)
            out = emit + out          # the engine *prepends* each phone (FUN_000278d0)
        return out


def main():
    l = Lts()
    for w in sys.argv[1:] or ["cat", "hello", "zzyzx", "thought", "beat", "xylophone"]:
        print("%-14s %s" % (w, " ".join(l.lts(w))))


if __name__ == "__main__":
    main()
