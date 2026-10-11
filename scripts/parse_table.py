#!/usr/bin/env python3
"""Parse libtiver.so: apply R_ARM_RELATIVE relocs and dump the
package->obb table at ELF 0x1d538 (Ghidra 0x2d538)."""
import struct

so = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libtiver.so"
data = open(so, "rb").read()

# (name, addr, file_off, size) from readelf -S
SECTIONS = [
    (".rodata",        0x18b84, 0x18b84, 0x2ed0),
    (".data.rel.ro.l", 0x1d538, 0x1c538, 0xeb8),
    (".fini_array",    0x1e3f0, 0x1d3f0, 0x8),
    (".data.rel.ro",   0x1e3f8, 0x1d3f8, 0x8fc),
    (".init_array",    0x1ecf4, 0x1dcf4, 0x10),
    (".data",          0x1f000, 0x1e000, 0x20),
    (".bss",           0x1f020, None,    0x4f45),
]

img = bytearray(data)

def sec_of(addr):
    for name, a, o, s in SECTIONS:
        if o is not None and a <= addr < a + s:
            return o + (addr - a)
    return None

# apply relocations from .rel.dyn (parse ELF)
e_shoff = struct.unpack_from("<I", data, 0x20)[0]
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2e)
sh = [struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
str_off = sh[e_shstrndx][4]
def name(i):
    o = str_off + sh[i][0]
    return data[o:data.index(b"\0", o)].decode()

nrel = 0
for i in range(e_shnum):
    if sh[i][1] == 9:  # SHT_REL
        tgt_off = sh[sh[i][3]][4]   # target section file offset
        tgt_addr = sh[sh[i][3]][3]
        for j in range(0, sh[i][5], 8):
            r_offset, r_info = struct.unpack_from("<II", data, sh[i][4] + j)
            if (r_info & 0xff) == 23:  # R_ARM_RELATIVE
                o = tgt_off + (r_offset - tgt_addr)
                addend = struct.unpack_from("<I", img, o)[0]
                struct.pack_into("<I", img, o, addend)
                nrel += 1
print(f"applied {nrel} R_ARM_RELATIVE relocs")

def u32(addr):
    o = sec_of(addr)
    return None if o is None else struct.unpack_from("<I", img, o)[0]

def cstr(addr):
    o = sec_of(addr)
    if o is None:
        return None
    end = data.index(b"\0", o)
    s = data[o:end].decode("ascii", "replace")
    return s if s and all(32 <= ord(c) < 127 for c in s) else None

TABLE = 0x1d538
addr = TABLE
n = 0
while True:
    words = [u32(addr + 4 * i) for i in range(12)]
    if words[0] == 0:
        print(f"terminator at 0x{addr:x}: rest={['0x%x' % w for w in words]}")
        break
    parts = []
    for i, w in enumerate(words):
        s = cstr(w)
        parts.append(f"w{i}=" + (f'"{s}"' if s else f"{w}/0x{w:x}"))
    print(f"0x{addr:05x}: " + "  ".join(parts))
    addr += 48
    n += 1
    if n > 120:
        print("...stopped")
        break
