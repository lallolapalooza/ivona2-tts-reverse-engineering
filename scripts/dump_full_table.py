#!/usr/bin/env python3
"""Full dump of libtiver .data.rel.ro.local (ELF 0x1d538, file 0x1c538, size 0xeb8)
as 48-byte entries; resolve pointers; also dump .data voice-info struct,
check .rel.dyn targets on .data, and grep for two conflicting size dwords."""
import struct, collections

so = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libtiver.so"
data = open(so, "rb").read()

SECS = [  # name, vaddr, fileoff, size
    (".rodata", 0x18b84, 0x18b84, 0x2ed0),
    (".text", 0x66a0, 0x66a0, 0x111d4),
    (".data.rel.ro.local", 0x1d538, 0x1c538, 0xeb8),
    (".data.rel.ro", 0x1e3f8, 0x1d3f8, 0x8fc),
    (".data", 0x1f000, 0x1e000, 0x20),
]

def cstr(addr):
    for n, a, o, s in SECS:
        if a <= addr < a + s and n in (".rodata",):
            off = o + (addr - a)
            end = data.index(b"\0", off)
            t = data[off:end].decode("ascii", "replace")
            if t and all(32 <= ord(c) < 127 for c in t):
                return t
    return None

def u32(fileoff):
    return struct.unpack_from("<I", data, fileoff)[0]

print("=== full table region 0x1d538 .. 0x1de00, 48-byte rows ===")
base = 0x1c538
for row in range(80):
    off = base + row * 48
    if off + 48 > 0x1c538 + 0xeb8:
        break
    words = [u32(off + 4*i) for i in range(12)]
    parts = []
    for i, w in enumerate(words):
        s = cstr(w)
        parts.append(f"[{i}]" + (f'"{s}"' if s else f"{w}"))
    print(f"row{row:3d} 0x{0x1d538+row*48:05x}: " + " ".join(parts))

print("\n=== .rel.dyn targets inside .data 0x1f000-0x1f020 ===")
e_shoff = struct.unpack_from("<I", data, 0x20)[0]
entsz, shnum, shstr = struct.unpack_from("<HHH", data, 0x2e)
sh = [struct.unpack_from("<IIIIIIIIII", data, e_shoff + i*entsz) for i in range(shnum)]
for i in range(shnum):
    if sh[i][1] == 9:  # SHT_REL
        for j in range(0, sh[i][5], 8):
            r_offset, r_info = struct.unpack_from("<II", data, sh[i][4] + j)
            if 0x1f000 <= r_offset < 0x1f020:
                print(f"  reloc @0x{r_offset:x} type={r_info & 0xff} sym={r_info>>8}")

print("\n=== dword occurrence counts ===")
for val in (152219597, 56420797, 149905560, 56615161, 46420646, 26309235):
    pat = struct.pack("<I", val)
    offs = []
    st = 0
    while True:
        k = data.find(pat, st)
        if k < 0: break
        offs.append(k)
        st = k + 1
    print(f"  {val} (0x{val:x}): {len(offs)}x at file offs {offs[:6]}")
