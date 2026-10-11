#!/usr/bin/env python3
"""Walk the tts_voice_param key table in libttsivonavoice.so.

Ghidra dump addresses = ELF vaddr + 0x10000 (verified: v's guard DAT_0019f1d0
== .bss start 0x18f1d0). So table DAT_00194fbc -> vaddr 0x184fbc (.data.rel.ro).

Applies R_ARM_RELATIVE / R_ARM_ABS32 relocations so pointers resolve.
Table entries are 3 words: [0]=name, [1]=aux/default, [2]=handler; stop at name 0.
"""
import struct, sys

SO = "/home/asdf/Downloads/ivona_re/out/libs/kendra/libttsivonavoice.so"
data = bytearray(open(SO, "rb").read())
raw = bytes(data)

# section headers
e_shoff, = struct.unpack_from("<I", raw, 32)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from("<HHH", raw, 46)
secs = []
for i in range(e_shnum):
    off = e_shoff + i * e_shentsize
    name_off, stype, flags, addr, soff, size, link, info, align, entsize = \
        struct.unpack_from("<IIIIIIIIII", raw, off)
    secs.append(dict(off=soff, addr=addr, size=size, type=stype, link=link, entsize=entsize))
shstr = secs[e_shstrndx]

def sname(s):
    o = shstr["off"] + s.get("name_off", 0)
    return None

for s in secs:
    pass

def v2o(v):
    for s in secs:
        if s["type"] != 8 and s["addr"] and s["addr"] <= v < s["addr"] + s["size"]:
            return s["off"] + (v - s["addr"])
    return None

# apply relocations
# parse .dynsym + .rel.dyn
dynsym = next(s for s in secs if s["type"] == 11)  # SHT_DYNSYM
rel_dyn = next((s for s in secs if s["type"] == 9), None)  # SHT_REL
symtab = raw[dynsym["off"]: dynsym["off"] + dynsym["size"]]
def getsym(i):
    st_name, st_value, st_size, st_info, st_other, st_shndx = \
        struct.unpack_from("<IIIBBH", symtab, i * 16)
    return st_value
if rel_dyn:
    n = rel_dyn["size"] // 8
    for i in range(n):
        r_offset, r_info = struct.unpack_from("<II", raw, rel_dyn["off"] + i * 8)
        typ = r_info & 0xff
        symi = r_info >> 8
        o = v2o(r_offset)
        if o is None:
            continue
        if typ == 23:  # R_ARM_RELATIVE
            addend, = struct.unpack_from("<I", raw, o)
            struct.pack_into("<I", data, o, addend)
        elif typ == 2:  # R_ARM_ABS32
            addend, = struct.unpack_from("<I", raw, o)
            struct.pack_into("<I", data, o, getsym(symi) + addend)

def u32(v):
    o = v2o(v)
    if o is None:
        return None
    return struct.unpack_from("<I", data, o)[0]

def cstr(v, maxlen=160):
    if not v:
        return None
    o = v2o(v)
    if o is None:
        return None
    try:
        end = raw.index(b"\0", o, o + maxlen)
    except ValueError:
        return None
    return raw[o:end].decode("utf-8", "replace")

GHIDRA_BASE = 0x10000
base = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x194fbc
base -= GHIDRA_BASE
print(f"table @ ghidra {base + GHIDRA_BASE:#x} == vaddr {base:#x}")
i = 0
while True:
    e = base + i * 12
    name = u32(e)
    w1 = u32(e + 4)
    fn = u32(e + 8)
    if name is None:
        print(f"{e:#x}: <unmapped>")
        break
    print(f"entry {i}: vaddr {e:#x} name={name and hex(name)} {cstr(name)!r}  "
          f"w1={w1 and hex(w1)} {cstr(w1)!r}  fn={fn and hex(fn)} (ghidra {fn and hex(fn + GHIDRA_BASE)})")
    if name == 0:
        break
    i += 1
    if i > 80:
        print("...cap")
        break
