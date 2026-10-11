#!/usr/bin/env python3
"""Plug-in printable-ASCII symbol names -- the table the engine uses to *speak*
punctuation by name (`,` -> "comma", `.` -> "dot").

Provenance
----------
`libvoice_en_us_kendra.so` (and the byte-identical en-GB Amy plug-in) contains a
256-entry array of string pointers in `.data.rel.ro` at ELF vaddr **0x2eccc0**,
indexed by the character byte value.  The strings live in `.rodata`
(file offset == vaddr) starting at 0x1f1380 ("backspace").  Entry 0 gives the
character's spoken/written name, e.g.::

    0x2c (',') -> "comma"      0x2e ('.') -> "dot"
    0x3f ('?') -> "question mark"   0x21 ('!') -> "exclamation mark"
    0x3a (':') -> "colon"      0x3b (';') -> "semicolon"

The oracle capture `out/oracle/ref_default` (`"Hello world, this is a test."`)
shows this table in action: the engine's diphone chain contains the phones of
`comma` (`k aa m ax`) and `dot` (`d aa t`) where the input has `,` and `.`
(`diphone_lookups.tsv`), i.e. the symbol is *spoken by name* through the normal
G2P path -- the same "symbol without a reading" fallback as an unknown word.

`NAMES` below is that table copied verbatim; `extract_from_so()` re-derives it
from the shipped binary and `--verify` proves the copy is current::

    python3 scripts/symbol_names.py --verify out/libs/kendra/libvoice_en_us_kendra.so
    python3 scripts/symbol_names.py                 # full mapping

This module is stdlib-only; nothing here imports Unicorn.
"""
import struct
import sys

# table base (ELF vaddr == file offset) and the rodata string range
TABLE_VADDR = 0x2eccc0
RODATA_LO = 0x0569b0
RODATA_HI = 0x2e3d88

# ---------------------------------------------------------------------------
# char byte -> name, verbatim from the plug-in (see module docstring)
# ---------------------------------------------------------------------------
NAMES = {
    0x08: 'backspace',
    0x09: 'tab',
    0x0a: 'line feed',
    0x0b: 'vertical tab',
    0x0c: 'form feed',
    0x0d: 'carriage return',
    0x1b: 'escape',
    0x20: 'space',
    0x21: 'exclamation mark',
    0x22: 'quote',
    0x23: 'hash',
    0x24: 'dollar',
    0x25: 'percent',
    0x26: 'and',
    0x27: 'apostrophe',
    0x28: 'opening parenthesis',
    0x29: 'closing parenthesis',
    0x2a: 'asterisk',
    0x2b: 'plus',
    0x2c: 'comma',
    0x2d: 'dash',
    0x2e: 'dot',
    0x2f: 'slash',
    0x30: 'oh',
    0x31: 'one',
    0x32: 'two',
    0x33: 'three',
    0x34: 'four',
    0x35: 'five',
    0x36: 'six',
    0x37: 'seven',
    0x38: 'eight',
    0x39: 'nine',
    0x3a: 'colon',
    0x3b: 'semicolon',
    0x3c: 'less than',
    0x3d: 'equals',
    0x3e: 'greater than',
    0x3f: 'question mark',
    0x40: 'at',
    0x41: '_a',
    0x42: 'b',
    0x43: 'c',
    0x44: 'd',
    0x45: 'e',
    0x46: 'f',
    0x47: 'g',
    0x48: 'h',
    0x49: 'i',
    0x4a: 'j',
    0x4b: 'k',
    0x4c: 'l',
    0x4d: 'm',
    0x4e: 'n',
    0x4f: 'o',
    0x50: 'p',
    0x51: 'q',
    0x52: 'r',
    0x53: 's',
    0x54: 't',
    0x55: 'u',
    0x56: 'v',
    0x57: 'w',
    0x58: 'x',
    0x59: 'y',
    0x5a: 'z',
    0x5b: 'opening bracket',
    0x5c: 'backslash',
    0x5d: 'closing bracket',
    0x5e: 'caret',
    0x5f: 'underscore',
    0x60: 'grave accent',
    0x61: '_a',
    0x62: 'b',
    0x63: 'c',
    0x64: 'd',
    0x65: 'e',
    0x66: 'f',
    0x67: 'g',
    0x68: 'h',
    0x69: 'i',
    0x6a: 'j',
    0x6b: 'k',
    0x6c: 'l',
    0x6d: 'm',
    0x6e: 'n',
    0x6f: 'o',
    0x70: 'p',
    0x71: 'q',
    0x72: 'r',
    0x73: 's',
    0x74: 't',
    0x75: 'u',
    0x76: 'v',
    0x77: 'w',
    0x78: 'x',
    0x79: 'y',
    0x7a: 'z',
    0x7b: 'opening brace',
    0x7c: 'vertical bar',
    0x7d: 'closing brace',
    0x7e: 'tilde',
    0x7f: 'delete',
    0x85: 'next line',
    0xa0: 'space',
    0xa1: 'inverted exclamation mark',
    0xa2: 'cent',
    0xa3: 'pound',
    0xa4: 'currency',
    0xa5: 'yen',
    0xa6: 'broken bar',
    0xa7: 'section',
    0xa8: 'diaeresis',
    0xa9: 'copyright',
    0xaa: 'superscript _a',
    0xab: 'angle quote',
    0xac: 'negation',
    0xad: 'soft hyphen',
    0xae: 'registered',
    0xaf: 'macron',
    0xb0: 'degree',
    0xb1: 'plus minus',
    0xb2: 'squared',
    0xb3: 'cubed',
    0xb4: 'acute accent',
    0xb5: 'micro',
    0xb6: 'pilcrow',
    0xb7: 'midlle dot',
    0xb8: 'cedilla',
    0xb9: 'superscript one',
    0xba: 'superscript o',
    0xbb: 'angle quote',
    0xbc: 'one fourth',
    0xbd: 'one half',
    0xbe: 'three fourths',
    0xbf: 'inverted question mark',
    0xc0: '_a grave',
    0xc1: '_a acute',
    0xc2: '_a circumflex',
    0xc3: '_a tilde',
    0xc4: '_a diaeresis',
    0xc5: '_a ring',
    0xc6: 'ash',
    0xc7: 'c cedilla',
    0xc8: 'e grave',
    0xc9: 'e acute',
    0xca: 'e circumflex',
    0xcb: 'e diaeresis',
    0xcc: 'i grave',
    0xcd: 'i acute',
    0xce: 'i circumflex',
    0xcf: 'i diaeresis',
    0xd0: 'eth',
    0xd1: 'n tilde',
    0xd2: 'o grave',
    0xd3: 'o acute',
    0xd4: 'o circumflex',
    0xd5: 'o tilde',
    0xd6: 'o diaeresis',
    0xd7: 'times',
    0xd8: 'o with stroke',
    0xd9: 'u grave',
    0xda: 'u acute',
    0xdb: 'u circumflex',
    0xdc: 'u diaeresis',
    0xdd: 'y acute',
    0xde: 'thorn',
    0xdf: 'sharp s',
    0xe0: '_a grave',
    0xe1: '_a acute',
    0xe2: '_a circumflex',
    0xe3: '_a tilde',
    0xe4: '_a diaeresis',
    0xe5: '_a ring',
    0xe6: 'ash',
    0xe7: 'c cedilla',
    0xe8: 'e grave',
    0xe9: 'e acute',
    0xea: 'e circumflex',
    0xeb: 'e diaeresis',
    0xec: 'i grave',
    0xed: 'i acute',
    0xee: 'i circumflex',
    0xef: 'i diaeresis',
    0xf0: 'eth',
    0xf1: 'n tilde',
    0xf2: 'o grave',
    0xf3: 'o acute',
    0xf4: 'o circumflex',
    0xf5: 'o tilde',
    0xf6: 'o diaeresis',
    0xf7: 'divided by',
    0xf8: 'o with stroke',
    0xf9: 'u grave',
    0xfa: 'u acute',
    0xfb: 'u circumflex',
    0xfc: 'u diaeresis',
    0xfd: 'y acute',
    0xfe: 'thorn',
    0xff: 'y diaeresis',
}

# A "word" is spelled normally; everything else is a *symbol without a reading*
# and is pronounced by its name from NAMES.  Digits are handled separately by
# the caller (the demo spells them "zero".."nine", the table names them
# "oh"/"one"/..); letters and the apostrophe are word characters.
WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'")
_SENTENCE_END = set('.!?')


def spoken_name(ch):
    """Name the engine pronounces for symbol `ch`, or None for a word character.

    Returns None for whitespace, letters, digits and the apostrophe (these are
    read normally / handled by the digit spelling), otherwise the plug-in table's
    name (``',' -> 'comma'``, ``'.' -> 'dot'``, ...).
    """
    if ch in WORD_CHARS or ch.isspace():
        return None
    return NAMES.get(ord(ch))


def is_sentence_end(ch):
    """Sentence-final punctuation (the engine's `eng_sentence_break` triggers)."""
    return ch in _SENTENCE_END


# ---------------------------------------------------------------------------
def extract_from_so(path):
    """Re-derive {byte: name} from a voice plug-in; used to prove NAMES is current."""
    with open(path, 'rb') as fh:
        d = fh.read()
    base = _find_table_base(d)
    if base is None:
        raise SystemExit('symbol name table not found in %s' % path)
    out = {}
    for i in range(256):
        off = struct.unpack_from('<I', d, base + 4 * i)[0]
        if not (RODATA_LO <= off < RODATA_HI):
            continue
        end = d.find(b'\0', off)
        try:
            name = d[off:end].decode('latin1')
        except UnicodeDecodeError:
            continue
        if name and all(32 <= ord(c) < 127 for c in name):
            out[i] = name
    return out


def _find_table_base(d):
    """Locate the 256-pointer name array: find the pointer slot for "comma" (',')
    and back-compute the base (index 0x2c)."""
    needle = b'comma\x00'
    j = d.find(needle)
    while j >= 0:
        ptr = struct.pack('<I', j)          # ELF vaddr == file offset in .rodata
        k = d.find(ptr)
        while k >= 0:
            base = k - 0x2c * 4
            if base >= 0:
                # sanity: slot for '.' (0x2e) at base+0x2e*4 points at "dot"
                po = struct.unpack_from('<I', d, base + 0x2e * 4)[0]
                if 0 < po < len(d) and d[po:po + 4] == b'dot\x00':
                    return base
            k = d.find(ptr, k + 1)
        j = d.find(needle, j + 1)
    return None


def main():
    args = sys.argv[1:]
    if args and args[0] == '--verify':
        so = args[1]
        got = extract_from_so(so)
        missing = {k: v for k, v in NAMES.items() if got.get(k) != v}
        extra = {k: v for k, v in got.items() if k not in NAMES}
        print("[symbols] %d names in module, %d in %s" % (len(NAMES), len(got), so))
        if missing or extra:
            print("[symbols] MISMATCH missing/changed=%s extra=%s" % (missing, extra))
            return 1
        print("[symbols] table is current: %d/%d names identical" % (len(NAMES), len(NAMES)))
        return 0
    for code in sorted(NAMES):
        ch = chr(code) if 32 <= code < 127 else '\\x%02x' % code
        print("0x%02x  %-5s  %s" % (code, ch, NAMES[code]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
