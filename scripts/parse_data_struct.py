#!/usr/bin/env python3
"""Dump libtiver.so .data voice-info struct (ELF 0x1f004) with R_ARM_RELATIVE applied."""
import struct

so = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libtiver.so"
data = open(so, "rb").read()
img = bytearray(data)

e_shoff = struct.unpack_from("<I", data, 0x20)[0]
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", data, 0x2e)
sh = [struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_shentsize) for i in range(e_shnum)]
str_off = sh[e_shstrndx][4]
def name(i):
    o = str_off + sh[i][0]
    return data[o:data.index(b"\0", o)].decode()

secs = [(name(i), sh[i][3], sh[i][4], sh[i][5], sh[i][1]) for i in range(e_shnum)]

nrel = 0
for i in range(e_shnum):
    if sh[i][1] == 9:
        tgt_addr, tgt_off = sh[sh[i][3]][3], sh[sh[i][3]][4]
        for j in range(0, sh[i][5], 8):
            r_offset, r_info = struct.unpack_from("<II", data, sh[i][4] + j)
            if (r_info & 0xff) == 23:
                o = tgt_off + (r_offset - tgt_addr)
                addend = struct.unpack_from("<I", img, o)[0]
                struct.pack_into("<I", img, o, addend)
                nrel += 1

def sec_of(addr):
    for n, a, o, s, t in secs:
        if o and t in (1, 8) and a <= addr < a + s:
            return o + (addr - a), t
    return None, None

def u32(addr):
    o, t = sec_of(addr)
    return None if o is None else struct.unpack_from("<I", img, o)[0]

def cstr(addr):
    o, t = sec_of(addr)
    if o is None or t != 1:
        return None
    end = data.index(b"\0", o)
    s = data[o:end].decode("ascii", "replace")
    return s if s and all(32 <= ord(c) < 127 for c in s) else None

print("=== .data voice-info struct (v() returns 0x1f004) ===")
for off in range(0, 0x20, 4):
    addr = 0x1f000 + off
    w = u32(addr)
    s = cstr(w)
    tag = f'  -> "{s}"' if s else ""
    label = "v() return / &struct" if addr == 0x1f004 else ""
    print(f"  0x{addr:05x} (+0x{off-4:+02x} struct[{(off-4)//4 if off>=4 else -1}]) = 0x{w:08x} ({w}){tag}  {label}")

print("\n=== terminator entry of table (0x1d838) resolved ===")
for i in range(12):
    addr = 0x1d838 + 4*i
    w = u32(addr)
    s = cstr(w)
    print(f"  w{i} = 0x{w:08x} ({w})" + (f' -> "{s}"' if s else ""))
