"""Static-table access for the clean-room codec port.

The original library keeps every codebook / window / constant in its static
image.  ``scripts/codec_tables.py`` dumped the two image windows the codec reads
into ``out/codec/tables.bin`` (+ ``tables.json``); this module maps a *link-time
ELF virtual address* to bytes of that dump.

Address convention (must stay consistent across the port):
  * ``FUN_0014xxxx`` / ``DAT_0018xxxx`` addresses quoted from the Ghidra dump are
    **Ghidra addresses**;  ELF vaddr = Ghidra - 0x10000.
  * Everything in this port is written in **ELF vaddrs** (what the loader used,
    relocation base == 0, so absolute pointer values stored in .data.rel.ro
    already equal the ELF vaddr).
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

GHIDRA_DELTA = 0x10000


def elf(ghidra_addr):
    """Ghidra address -> ELF vaddr used by the port."""
    return ghidra_addr - GHIDRA_DELTA


class Tables(object):
    """Read-only view of the dumped static image, addressed by ELF vaddr."""

    def __init__(self, bin_path=None, json_path=None):
        bin_path = bin_path or os.path.join(ROOT, 'out', 'codec', 'tables.bin')
        json_path = json_path or os.path.join(ROOT, 'out', 'codec', 'tables.json')
        with open(json_path) as fh:
            man = json.load(fh)
        with open(bin_path, 'rb') as fh:
            self.blob = fh.read()
        self.windows = [(w['base'], w['size'], w['off']) for w in man['windows']]
        self.sha256 = man.get('sha256')

    def rd(self, vaddr, n):
        for base, size, off in self.windows:
            if base <= vaddr and vaddr + n <= base + size:
                s = off + (vaddr - base)
                return self.blob[s:s + n]
        raise KeyError('vaddr %#x len %#x outside dumped windows %r'
                       % (vaddr, n, self.windows))

    def u32(self, vaddr):
        return struct.unpack('<I', self.rd(vaddr, 4))[0]

    def s32(self, vaddr):
        return struct.unpack('<i', self.rd(vaddr, 4))[0]

    def u16(self, vaddr):
        return struct.unpack('<H', self.rd(vaddr, 2))[0]

    def s16(self, vaddr):
        return struct.unpack('<h', self.rd(vaddr, 2))[0]

    def ptr(self, vaddr):
        """32-bit absolute pointer stored in the image (relocation base 0)."""
        return self.u32(vaddr)


_tables = None


def tables():
    global _tables
    if _tables is None:
        _tables = Tables()
    return _tables
