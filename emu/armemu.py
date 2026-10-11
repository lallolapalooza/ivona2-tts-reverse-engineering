"""Generic ARM32 (Thumb) shared-library emulator on Unicorn.

Loads a bionic-linked Android .so at its link-time addresses, applies
relocations, and replaces every imported libc/bionic symbol with a Python
stub.  Code that lives inside the .so runs natively; imported calls are
intercepted so the library can execute with a host-side fakes for files,
malloc, stdio, TLS and the like.

The module is deliberately dependency-light: pyelftools + unicorn.
"""
import struct
import sys
import re
from collections import Counter

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection
from unicorn import (
    Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED,
    UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED, UC_PROT_ALL,
    UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC,
)
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_ARM_REG_CPSR,
)

# fixed-region layout (well clear of the 1.8 MB library image)
STUB_BASE  = 0x60000000   # one 2-byte `bx lr` trampoline per imported symbol
RET_TRAP   = 0x70000000   # sentinel the harness returns into
STACK_BASE = 0x70010000
STACK_SIZE = 0x00100000
HEAP_BASE  = 0x40000000
HEAP_SIZE  = 0x04000000

R_ARM_ABS32      = 2
R_ARM_GLOB_DAT   = 21
R_ARM_JUMP_SLOT  = 22
R_ARM_RELATIVE   = 23

# ARM `bx lr`
BX_LR = b"\x1e\xff\x2f\xe1"
# ARM `b .` infinite loop (used as the return trap body)
B_SELF = b"\xfe\xff\xff\xea"


def align_down(x, a=0x1000):
    return x & ~(a - 1)


def arm_arg(uc, i):
    """i-th integer argument of the current call (AAPCS: r0-r3, then the stack)."""
    if i < 4:
        return uc.reg_read([UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3][i])
    sp = uc.reg_read(UC_ARM_REG_SP)
    return struct.unpack("<I", uc.mem_read(sp + (i - 4) * 4, 4))[0]


def align_up(x, a=0x1000):
    return (x + a - 1) & ~(a - 1)


class EmuError(Exception):
    pass


class ArmLib:
    """Emulated ARM shared library with libc stubs attached."""

    def __init__(self, path, verbosity=0):
        self.path = path
        with open(path, "rb") as fh:
            self.raw = fh.read()
        self.verbosity = verbosity
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.imports = {}       # name -> stub address (thumb, bit0 set)
        self.import_cbs = {}    # stub address -> python callback
        self.stub_next = 0
        self.exports = {}       # name -> address
        self.heap_ptr = HEAP_BASE
        self.heap_sizes = {}
        self.host_files = {}
        self._fd_next = 1
        self.results = {}       # scratch slots for object symbols
        # ---- host-integration / instrumentation knobs -------------------
        self.fs_root = None        # optional host dir prefix for open()/fopen()
        self.open_map = {}         # guest path -> host path override
        self.env = {}              # getenv() table
        self.capture_stdout = None # list -> capture stdout instead of printing it
        self.trace_calls = False   # log every imported/stubbed call
        self.trace_filter = None   # regex; only traced names matching it are logged
        self._trace_re = None
        self.unknown_calls = Counter()   # stub name -> number of unhandled hits
        self.jmpbufs = {}          # guest jmp_buf addr -> saved context (sigsetjmp)
        self.host_fds = {}         # raw fd -> host file object (open/read/lseek/mmap)
        self._fd_base = 0x2000     # first guest fd handed out by open()
        self.mmap_regions = {}     # guest addr -> size
        self.stub_names = {}       # stub code address -> import name
        self.libname = path.replace("\\", "/").rsplit("/", 1)[-1]
        self._load_elf()
        self._setup_regions()
        self._apply_relocations()
        self._install_hooks()
        self._install_libc()

    # ---------------------------------------------------------------- load
    def _load_elf(self):
        self.elf = ELFFile(open(self.path, "rb"))
        self.base = 0
        # map PT_LOAD segments
        for seg in self.elf.iter_segments():
            if seg["p_type"] != "PT_LOAD":
                continue
            va = seg["p_vaddr"]
            memsz = seg["p_memsz"]
            filesz = seg["p_filesz"]
            start = align_down(va)
            end = align_up(va + memsz)
            self._map(start, end - start, "seg")
            data = seg.data()
            if data:
                self.uc.mem_write(va, data)
            if memsz > filesz:
                self.uc.mem_write(va + filesz, b"\x00" * (memsz - filesz))

    def _map(self, addr, size, tag=""):
        prot = UC_PROT_ALL
        self.uc.mem_map(addr, size, prot)
        if self.verbosity >= 2:
            print(f"[map] {tag} {addr:#x}+{size:#x}")

    def _setup_regions(self):
        self._map(STUB_BASE, 0x10000, "stubs")
        self.uc.mem_write(STUB_BASE, BX_LR * (0x10000 // 4))
        self._map(RET_TRAP, 0x1000, "rettrap")
        self.uc.mem_write(RET_TRAP, B_SELF * (0x1000 // 4))
        self._map(STACK_BASE, STACK_SIZE, "stack")
        self._map(HEAP_BASE, HEAP_SIZE, "heap")
        self.uc.reg_write(UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x1000)

    # -------------------------------------------------------- relocations
    def _sym_name(self, symtab, idx):
        try:
            s = symtab.get_symbol(idx)
            return s.name, s["st_value"]
        except Exception:
            return "", 0

    def _stub_for(self, name):
        if name in self.imports:
            return self.imports[name]
        off = self.stub_next * 8
        self.stub_next += 1
        addr = STUB_BASE + off
        self.imports[name] = addr
        return self.imports[name]

    def _apply_relocations(self):
        for sec in self.elf.iter_sections():
            if not isinstance(sec, RelocationSection):
                continue
            symtab = self.elf.get_section(sec["sh_link"])
            for rel in sec.iter_relocations():
                rtype = rel["r_info_type"]
                off = rel["r_offset"] + self.base
                symidx = rel["r_info_sym"]
                name, sval = ("", 0)
                if isinstance(symtab, SymbolTableSection) and symidx:
                    name, sval = self._sym_name(symtab, symidx)
                if rtype == R_ARM_RELATIVE:
                    addend = struct.unpack_from("<I", self.raw, rel["r_offset"])[0] \
                        if rel["r_offset"] + 4 <= len(self.raw) else 0
                    val = self.base + addend
                elif rtype in (R_ARM_JUMP_SLOT, R_ARM_GLOB_DAT):
                    if sval == 0 or (name and symidx and
                                     symtab.get_symbol(symidx)["st_shndx"] == "SHN_UNDEF"):
                        val = self._stub_for(name)
                    else:
                        val = self.base + sval
                        self.exports[name] = val
                elif rtype == R_ARM_ABS32:
                    addend = struct.unpack_from("<I", self.raw, rel["r_offset"])[0]
                    if sval or not name:
                        val = self.base + sval + addend
                    else:
                        val = self._stub_for(name)
                else:
                    continue
                if rtype == R_ARM_RELATIVE:
                    # REL: addend already stored in memory; with base 0 it is a no-op
                    continue
                self.uc.mem_write(off, struct.pack("<I", val & 0xffffffff))

        # exported functions for direct call-by-name convenience
        symtab = self.elf.get_section_by_name(".dynsym")
        if symtab:
            for s in symtab.iter_symbols():
                if s["st_shndx"] not in ("SHN_UNDEF",) and s.name:
                    self.exports.setdefault(s.name, self.base + s["st_value"])

    # --------------------------------------------------------------- hooks
    def _install_hooks(self):
        self.uc.hook_add(UC_HOOK_CODE, self._code_hook)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped_hook)

    def _unmapped_hook(self, uc, access, address, size, value, user):
        print(f"[!!] UNMAPPED access access={access} addr={address:#x} size={size} "
              f"pc={uc.reg_read(UC_ARM_REG_PC):#x} lr={uc.reg_read(UC_ARM_REG_LR):#x}")
        return False   # abort emulation

    def _code_hook(self, uc, address, size, user):
        cb = self.import_cbs.get(address)
        if cb is not None:
            # emulate "call" semantics: run cb, then return to LR
            lr = uc.reg_read(UC_ARM_REG_LR)
            args = [uc.reg_read(r) for r in (
                UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            try:
                ret = cb(uc, args)
            except EmuError:
                raise
            uc.reg_write(UC_ARM_REG_R0, (ret or 0) & 0xffffffff)
            uc.reg_write(UC_ARM_REG_PC, lr)

    def add_import(self, name, fn, trace=False):
        addr = self.imports.get(name)
        if addr is None:
            addr = self._stub_for(name)
        base = addr & ~1
        self.stub_names[base] = name
        if trace:
            def wrapped(uc, a, _fn=fn, _n=name):
                sp = uc.reg_read(UC_ARM_REG_SP)
                lr = uc.reg_read(UC_ARM_REG_LR)
                print(f"[call] {_n}({', '.join(hex(x) for x in a)}) lr={lr:#x}")
                r = _fn(uc, a)
                print(f"[ret ] {_n} -> {hex((r or 0) & 0xffffffff)}")
                return r
            self.import_cbs[base] = wrapped
        else:
            self.import_cbs[base] = fn
        return addr

    # ------------------------------------------------------------- memory
    def rd(self, addr, n):
        return bytes(self.uc.mem_read(addr, n))

    def wr(self, addr, data):
        self.uc.mem_write(addr, data)

    def u32(self, addr):
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def s32(self, addr):
        return struct.unpack("<i", self.uc.mem_read(addr, 4))[0]

    def w32(self, addr, v):
        self.uc.mem_write(addr, struct.pack("<I", v & 0xffffffff))

    def cstr(self, addr, limit=1 << 20):
        out = bytearray()
        while len(out) < limit:
            b = self.uc.mem_read(addr + len(out), 1)[0]
            if b == 0:
                break
            out.append(b)
        return bytes(out)

    def putstr(self, addr, s):
        if isinstance(s, str):
            s = s.encode()
        self.uc.mem_write(addr, s + b"\x00")
        return addr

    def alloc(self, size):
        size = (size + 15) & ~15
        p = self.heap_ptr
        self.heap_ptr += size
        if self.heap_ptr >= HEAP_BASE + HEAP_SIZE:
            raise EmuError("emulated heap exhausted")
        self.heap_sizes[p] = size
        return p

    def alloc_data(self, data):
        p = self.alloc(len(data) or 1)
        if data:
            self.uc.mem_write(p, data)
        return p

    def alloc_str(self, s):
        b = s.encode() if isinstance(s, str) else bytes(s)
        if not b.endswith(b"\x00"):
            b += b"\x00"
        return self.alloc_data(b)

    # ------------------------------------------------------------- calling
    def call(self, addr, args=(), timeout=0, count=0, log=False):
        """Call addr (thumb ok) with up to 8 integer/pointer args.

        `timeout` is in *microseconds* (Unicorn semantics); 0 = unlimited.
        `count` bounds the instruction budget; 0 = unlimited.
        """
        regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
        for i, a in enumerate(args[:4]):
            self.uc.reg_write(regs[i], a & 0xffffffff)
        # remaining args on the stack (AAPCS)
        sp = self.uc.reg_read(UC_ARM_REG_SP)
        extra = list(args[4:])
        if extra:
            n = len(extra)
            sp -= ((n + 1) & ~1) * 4
            self.uc.reg_write(UC_ARM_REG_SP, sp)
            for i, a in enumerate(extra):
                self.w32(sp + i * 4, a)
        self.uc.reg_write(UC_ARM_REG_LR, RET_TRAP)
        self.ret_value = None

        def trap(uc, address, size, user):
            if address == RET_TRAP:
                uc.emu_stop()

        h = self.uc.hook_add(UC_HOOK_CODE, trap, begin=RET_TRAP, end=RET_TRAP + 2)
        try:
            self.uc.emu_start(addr, 0, timeout=timeout, count=count)
        finally:
            self.uc.hook_del(h)
        self.stop_pc = self.uc.reg_read(UC_ARM_REG_PC)
        self.stop_lr = self.uc.reg_read(UC_ARM_REG_LR)
        return self.uc.reg_read(UC_ARM_REG_R0)

    # ------------------------------------------------------------- libc
    def _install_libc(self):
        L = self

        def _copy(dst, src, n):
            if n:
                L.uc.mem_write(dst, bytes(L.uc.mem_read(src, n)))
            return dst

        def malloc(uc, a):
            return L.alloc(a[0] or 1)

        def calloc(uc, a):
            p = L.alloc((a[0] or 1) * (a[1] or 1))
            if a[0] and a[1]:
                L.uc.mem_write(p, b"\x00" * a[0] * a[1])
            return p

        def realloc(uc, a):
            old, size = a[0], a[1]
            if not old:
                return L.alloc(size or 1)
            oldsize = L.heap_sizes.get(old, 0)
            p = L.alloc(size or 1)
            if oldsize:
                L.uc.mem_write(p, bytes(L.uc.mem_read(old, min(oldsize, size))))
            return p

        def free(uc, a):
            return 0

        def memcpy(uc, a):
            return _copy(a[0], a[1], a[2])

        def memmove(uc, a):
            data = bytes(L.uc.mem_read(a[1], a[2])) if a[2] else b""
            if a[2]:
                L.uc.mem_write(a[0], data)
            return a[0]

        def memset(uc, a):
            if a[2]:
                L.uc.mem_write(a[0], bytes([a[1] & 0xff]) * a[2])
            return a[0]

        def memcmp(uc, a):
            x = bytes(L.uc.mem_read(a[0], a[2])); y = bytes(L.uc.mem_read(a[1], a[2]))
            return 0 if x == y else (-1 if x < y else 1)

        def memchr(uc, a):
            hay = bytes(L.uc.mem_read(a[0], a[2])); c = a[1] & 0xff
            i = hay.find(bytes([c]))
            return a[0] + i if i >= 0 else 0

        def strlen(uc, a):
            return len(L.cstr(a[0]))

        def strcmp(uc, a):
            x = L.cstr(a[0]); y = L.cstr(a[1])
            return 0 if x == y else (-1 if x < y else 1)

        def strncmp(uc, a):
            x = L.cstr(a[0])[:a[2]]; y = L.cstr(a[1])[:a[2]]
            return 0 if x == y else (-1 if x < y else 1)

        def strcasecmp(uc, a):
            x = L.cstr(a[0]).lower(); y = L.cstr(a[1]).lower()
            return 0 if x == y else (-1 if x < y else 1)

        def strncasecmp(uc, a):
            x = L.cstr(a[0]).lower()[:a[2]]; y = L.cstr(a[1]).lower()[:a[2]]
            return 0 if x == y else (-1 if x < y else 1)

        def _strcpy_common(dst, src):
            s = L.cstr(src)
            L.uc.mem_write(dst, s + b"\x00")
            return dst

        def strcpy(uc, a):
            return _strcpy_common(a[0], a[1])

        def strncpy(uc, a):
            s = L.cstr(a[1])[:a[2]]
            pad = b"\x00" * (a[2] - len(s))
            L.uc.mem_write(a[0], s + pad)
            return a[0]

        def strcat(uc, a):
            base = L.cstr(a[0]); s = L.cstr(a[1])
            L.uc.mem_write(a[0] + len(base), s + b"\x00")
            return a[0]

        def strchr(uc, a):
            hay = L.cstr(a[0]); i = hay.find(bytes([a[1] & 0xff]))
            return a[0] + i if i >= 0 else 0

        def strrchr(uc, a):
            hay = L.cstr(a[0]); i = hay.rfind(bytes([a[1] & 0xff]))
            return a[0] + i if i >= 0 else 0

        def strstr(uc, a):
            hay = L.cstr(a[0]); nee = L.cstr(a[1])
            i = hay.find(nee)
            return a[0] + i if i >= 0 else 0

        def strspn(uc, a):
            hay = L.cstr(a[0]).decode("latin1"); acc = set(L.cstr(a[1]).decode("latin1"))
            n = 0
            while n < len(hay) and hay[n] in acc:
                n += 1
            return n

        def strcspn(uc, a):
            hay = L.cstr(a[0]).decode("latin1"); acc = set(L.cstr(a[1]).decode("latin1"))
            n = 0
            while n < len(hay) and hay[n] not in acc:
                n += 1
            return n

        def strpbrk(uc, a):
            hay = L.cstr(a[0]).decode("latin1"); acc = set(L.cstr(a[1]).decode("latin1"))
            for i, c in enumerate(hay):
                if c in acc:
                    return a[0] + i
            return 0

        def __errno(uc, a):
            return L.errno_slot

        def __stack_chk_fail(uc, a):
            print("[!!] __stack_chk_fail called")
            uc.emu_stop()
            return 0

        def __android_log_vprint(uc, a):
            prio = a[0]; tag = L.cstr(a[1]); fmt = L.cstr(a[2])
            print(f"[liblog prio={prio} {tag.decode('latin1')}] {fmt.decode('latin1')}")
            return 0

        def __assert2(uc, a):
            print("[assert] file=%s line=%d func=%s expr=%s" %
                  (L.cstr(a[0]), a[1], L.cstr(a[2]), L.cstr(a[3])))
            uc.emu_stop()
            return 0

        def abort(uc, a):
            print("[abort]")
            uc.emu_stop()
            return 0

        def exit_(uc, a):
            uc.emu_stop()
            return 0

        def getenv(uc, a):
            name = L.cstr(a[0]).decode()
            val = L.env.get(name)
            if val is None:
                return 0
            return L.alloc_data(val.encode() + b"\x00")

        def _fmt_read(uc, fmt_addr, start_reg=1):
            """Resolve a printf-style format; returns (text, nargs_consumed)."""
            fmt = L.cstr(fmt_addr)
            argi = start_reg
            stack_slot = 0
            regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]

            def nextarg():
                nonlocal argi, stack_slot
                if argi < 4:
                    v = uc.reg_read(regs[argi]); argi += 1
                else:
                    sp = uc.reg_read(UC_ARM_REG_SP)
                    v = struct.unpack("<I", uc.mem_read(sp + stack_slot * 4, 4))[0]
                    stack_slot += 1
                return v

            def nextdouble():
                # AAPCS: a double argument starts in an even register pair
                nonlocal argi
                if argi in (1, 3):
                    argi += 1
                lo, hi = nextarg(), nextarg()
                return struct.unpack("<d", struct.pack("<II", lo, hi))[0]

            return L._c_format(fmt, nextarg, nextdouble), argi

        def _write_stdout(text):
            try:
                sys.stdout.write(text.decode("latin1"))
            except Exception:
                pass

        def printf(uc, a):
            txt, _ = _fmt_read(uc, a[0])
            if L.capture_stdout is not None:
                L.capture_stdout.append(txt)
            else:
                _write_stdout(txt)
            return len(txt)

        def fprintf(uc, a):
            txt, _ = _fmt_read(uc, a[1], start_reg=2)
            if L.capture_stdout is not None:
                L.capture_stdout.append(txt)
            else:
                _write_stdout(txt)
            return len(txt)

        def sprintf(uc, a):
            txt, _ = _fmt_read(uc, a[1], start_reg=2)
            L.uc.mem_write(a[0], txt + b"\x00")
            return len(txt)

        def snprintf(uc, a):
            txt, _ = _fmt_read(uc, a[2], start_reg=3)
            n = a[1]
            data = txt[:n - 1] + b"\x00" if n else b""
            if n:
                L.uc.mem_write(a[0], data)
            return len(txt)

        def fputs(uc, a):
            s = L.cstr(a[0])
            if L.capture_stdout is not None:
                L.capture_stdout.append(s)
            else:
                _write_stdout(s)
            return 0

        def puts(uc, a):
            s = L.cstr(a[0])
            if L.capture_stdout is not None:
                L.capture_stdout.append(s + b"\n")
            else:
                _write_stdout(s + b"\n")
            return 0

        def putchar(uc, a):
            if L.capture_stdout is not None:
                L.capture_stdout.append(bytes([a[0] & 0xff]))
            return a[0] & 0xff

        def fputc(uc, a):
            if L.capture_stdout is not None:
                L.capture_stdout.append(bytes([a[0] & 0xff]))
            return a[0] & 0xff

        def fflush(uc, a):
            return 0

        # ---- stdio file objects ---------------------------------------
        def _host_path(path):
            """Map a guest path to a host path (open_map override, then fs_root)."""
            import os
            host = L.open_map.get(path, path)
            if L.fs_root and host.startswith("/"):
                host = os.path.join(L.fs_root, host.lstrip("/"))
            return host

        def fopen(uc, a):
            path = L.cstr(a[0]).decode("latin1")
            mode = L.cstr(a[1]).decode("latin1")
            m = mode.replace("b", "")
            if "w" in m:
                pymode = "w+b"
            elif "a" in m:
                pymode = "a+b"
            elif "+" in m:
                pymode = "r+b"
            else:
                pymode = "rb"
            try:
                f = open(_host_path(path), pymode)
            except Exception:
                return 0
            fh = L._fd_next; L._fd_next += 1
            L.host_files[fh] = f
            return 0x1000 + fh

        def fileno_chk(uc, a):
            return a[0]

        def fread(uc, a):
            fh = L.host_files.get(a[3] - 0x1000)
            if fh is None or a[3] < 0x1000:
                # maybe a real stdio stream (stdin etc.)
                return 0
            data = fh.read(a[1] * a[2])
            if data:
                L.uc.mem_write(a[0], bytes(data))
            return len(data) // (a[1] or 1)

        def fwrite(uc, a):
            fh = L.host_files.get(a[3] - 0x1000)
            data = bytes(L.uc.mem_read(a[0], a[1] * a[2])) if a[1] * a[2] else b""
            if fh is not None:
                fh.write(data)
            elif L.capture_stdout is not None:
                L.capture_stdout.append(data)
            return a[1]

        def fseek(uc, a):
            fh = L.host_files.get(a[0] - 0x1000)
            if fh is None:
                return -1
            fh.seek(a[1], a[2])
            return 0

        def ftell(uc, a):
            fh = L.host_files.get(a[0] - 0x1000)
            return fh.tell() if fh else -1

        def fclose(uc, a):
            fh = L.host_files.pop(a[0] - 0x1000, None)
            if fh:
                fh.close()
            return 0

        def fgetc(uc, a):
            fh = L.host_files.get(a[0] - 0x1000)
            if fh is None:
                return -1
            b = fh.read(1)
            return b[0] if b else -1

        def fgets(uc, a):
            fh = L.host_files.get(a[2] - 0x1000)
            if fh is None:
                return 0
            data = fh.readline(a[1] - 1)
            if not data:
                return 0
            L.uc.mem_write(a[0], bytes(data) + b"\x00")
            return a[0]

        def stat_(uc, a):
            path = L.cstr(a[0]).decode("latin1")
            host = L.open_map.get(path)
            import os
            if host is None or not os.path.exists(host):
                return -1
            return 0

        def getpagesize(uc, a):
            return 0x1000

        def time_(uc, a):
            return 1352215500

        def isalnum(uc, a):
            c = chr(a[0] & 0xff); return 1 if c.isalnum() else 0

        def isalpha(uc, a):
            c = chr(a[0] & 0xff); return 1 if c.isalpha() else 0

        def isspace(uc, a):
            return 1 if chr(a[0] & 0xff) in " \t\n\r\f\v" else 0

        def isxdigit(uc, a):
            return 1 if chr(a[0] & 0xff) in "0123456789abcdefABCDEF" else 0

        def toupper(uc, a):
            c = a[0] & 0xff
            return c - 32 if 97 <= c <= 122 else c

        def _int_prefix(s, base):
            """C `strtol` conversion: skip blanks, optional sign, then digits.

            Only the longest valid digit prefix is consumed (like C); junk
            after it is ignored.  `base` is 10/16/8 or 0 (=auto-detect).
            """
            t = s.lstrip(" \t\n\r\f\v")
            neg = False
            if t[:1] in ("+", "-"):
                neg, t = t[0] == "-", t[1:]
            if base == 0:
                if t[:2].lower() == "0x":
                    base, t = 16, t[2:]
                elif t[:1] == "0":
                    base, t = 8, t[1:]
                else:
                    base = 10
            digits = "0123456789abcdefghijklmnopqrstuvwxyz"[:base]
            k = 0
            while k < len(t) and t[k].lower() in digits:
                k += 1
            if k == 0:
                return 0
            v = int(t[:k], base)
            return (-v if neg else v) & 0xffffffff

        def strtol(uc, a):
            base = a[2]
            if base < 0 or base > 36 or base == 1:
                base = 10
            return _int_prefix(L.cstr(a[0]).decode("latin1"), base)

        def atoi(uc, a):
            return _int_prefix(L.cstr(a[0]).decode("latin1"), 10)

        def atol(uc, a):
            return _int_prefix(L.cstr(a[0]).decode("latin1"), 10)

        def __cxa_atexit(uc, a):
            return 0

        def __cxa_finalize(uc, a):
            return 0

        def __cxa_guard_acquire(uc, a):
            return 1

        def __cxa_guard_release(uc, a):
            return 0

        def _noop0(uc, a):
            return 0

        self.capture_stdout = None
        self.env = {}
        self.open_map = {}
        self.errno_slot = self.alloc(8)

        simple0 = {
            "pthread_mutex_init": 0, "pthread_mutex_destroy": 0,
            "pthread_mutex_lock": 0, "pthread_mutex_unlock": 0,
            "pthread_key_create": 0, "pthread_key_delete": 0,
            "pthread_setspecific": 0, "pthread_getspecific": 0,
            "clock_gettime": 0, "gettimeofday": 0, "lseek": -1,
            "dlclose": 0, "dlerror": 0,
        }

        for nm in simple0:
            def mk(v):
                return lambda uc, a, v=v: v
            self.add_import(nm, mk(simple0[nm]))

        for nm, fn in {
            "malloc": malloc, "calloc": calloc, "realloc": realloc, "free": free,
            "memcpy": memcpy, "memmove": memmove, "memset": memset,
            "memcmp": memcmp, "memchr": memchr,
            "strlen": strlen, "strcmp": strcmp, "strncmp": strncmp,
            "strcasecmp": strcasecmp, "strncasecmp": strncasecmp,
            "strcpy": strcpy, "strncpy": strncpy, "strcat": strcat,
            "strchr": strchr, "strrchr": strrchr, "strstr": strstr,
            "strspn": strspn, "strcspn": strcspn, "strpbrk": strpbrk,
            "__errno": __errno, "__stack_chk_fail": __stack_chk_fail,
            "__android_log_vprint": __android_log_vprint, "__assert2": __assert2,
            "abort": abort, "exit": exit_, "getenv": getenv,
            "printf": printf, "fprintf": fprintf, "sprintf": sprintf,
            "snprintf": snprintf, "fputs": fputs, "puts": puts,
            "putchar": putchar, "fputc": fputc, "fflush": fflush,
            "fopen": fopen, "fread": fread, "fwrite": fwrite, "fseek": fseek,
            "ftell": ftell, "fclose": fclose, "fgetc": fgetc, "fgets": fgets,
            "stat": stat_, "time": time_,
            "isalnum": isalnum, "isalpha": isalpha, "isspace": isspace,
            "isxdigit": isxdigit, "toupper": toupper, "strtol": strtol,
            "atoi": atoi, "atol": atol,
            "__cxa_atexit": __cxa_atexit, "__cxa_finalize": __cxa_finalize,
            "__cxa_guard_acquire": __cxa_guard_acquire,
            "__cxa_guard_release": __cxa_guard_release,
        }.items():
            self.add_import(nm, fn)

        # remaining imports: harmless no-op returning 0 (logged on first use)
        for name, addr in list(self.imports.items()):
            if (addr & ~1) not in self.import_cbs:
                self.add_import(name, lambda uc, a, n=name: L._unknown(n, a))

        # ---- extended libc / syscall layer ---------------------------
        self._install_libc_extra()

        # ---- object (data) imports -----------------------------------
        self._setup_object_imports()

    def _unknown(self, name, args):
        self.unknown_calls[name] += 1
        if not self.trace_calls:
            print(f"[stub] {name}({', '.join(hex(x) for x in args)}) -> 0")
        return 0

    # ------------------------------------------------- extended stubs
    def _install_libc_extra(self):
        """Syscall/mmap/setjmp/math/format layer.

        Everything here is added on top of the core libc stubs so the library
        can be driven on real host files (open/read/lseek/mmap) and so the
        regex/exception glue (`sigsetjmp`/`siglongjmp`) does not kill the run.
        """
        L = self
        regs = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]

        def _host_path(path):
            import os
            host = L.open_map.get(path, path)
            if L.fs_root and host.startswith("/"):
                host = os.path.join(L.fs_root, host.lstrip("/"))
            return host

        # ---- raw fd layer (open/read/write/lseek/mmap) ---------------
        def open_(uc, a):
            path = L.cstr(a[0]).decode("latin1")
            flags = a[1]
            mode = "r+b" if (flags & 3) == 2 else "rb"
            try:
                f = open(_host_path(path), mode)
            except Exception:
                L.w32(L.errno_slot, 2)
                return 0xffffffff
            fd = L._fd_base + len(L.host_fds)
            L.host_fds[fd] = f
            return fd

        def close_(uc, a):
            f = L.host_fds.pop(a[0], None)
            if f:
                f.close()
                return 0
            return 0

        def read_(uc, a):
            f = L.host_fds.get(a[0])
            if f is None:
                return 0xffffffff
            data = f.read(a[2])
            if data:
                L.uc.mem_write(a[1], bytes(data))
            return len(data)

        def write_(uc, a):
            data = bytes(L.uc.mem_read(a[1], a[2])) if a[2] else b""
            if L.capture_stdout is not None:
                L.capture_stdout.append(data)
            else:
                try:
                    sys.stdout.write(data.decode("latin1"))
                except Exception:
                    pass
            return a[2]

        def lseek_(uc, a):
            f = L.host_fds.get(a[0])
            if f is None:
                return 0xffffffff
            f.seek(a[1], a[2])
            return f.tell()

        def mmap_(uc, a):
            addr, length, prot, flags = a[0], a[1], a[2], a[3]
            fd, offset = arm_arg(uc, 4), arm_arg(uc, 5)
            length = length or 0x1000
            p = L.alloc(max(length, 0x1000))
            f = L.host_fds.get(fd)
            if f is None and fd >= 0x1000:
                f = L.host_files.get(fd - 0x1000)
            if f is not None:
                cur = f.tell()
                f.seek(offset)
                data = f.read(length)
                f.seek(cur)
                if data:
                    L.uc.mem_write(p, bytes(data))
            L.mmap_regions[p] = length
            return p

        def munmap_(uc, a):
            L.mmap_regions.pop(a[0], None)
            return 0

        def fstat_(uc, a):
            import os
            f = L.host_fds.get(a[0]) or L.host_files.get(a[0] - 0x1000)
            if f is None:
                try:
                    f = os.fstat(a[0])
                except Exception:
                    return -1
                L.w16(a[1] + 0x2c, f.st_size & 0xffff)
                return 0
            try:
                st = os.fstat(f.fileno())
            except Exception:
                return -1
            L.uc.mem_write(a[1], b"\x00" * 0x40)
            L.w16(a[1] + 0x0c, st.st_mode & 0xffff)   # bionic off_t st_mode
            L.w32(a[1] + 0x2c, st.st_size & 0xffffffff)  # st_size
            return 0

        def stat_(uc, a):
            import os
            path = _host_path(L.cstr(a[0]).decode("latin1"))
            if not os.path.exists(path):
                L.w32(L.errno_slot, 2)
                return -1
            st = os.stat(path)
            L.uc.mem_write(a[1], b"\x00" * 0x40)
            L.w16(a[1] + 0x0c, st.st_mode & 0xffff)
            L.w32(a[1] + 0x2c, st.st_size & 0xffffffff)
            return 0

        # ---- setjmp / longjmp ---------------------------------------
        def sigsetjmp(uc, a):
            buf = a[0]
            L.jmpbufs[buf] = (uc.reg_read(UC_ARM_REG_SP), uc.reg_read(UC_ARM_REG_LR),
                              [uc.reg_read(r) for r in
                               (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                                UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11)])
            L.w32(buf, 0x53474a42)          # silly magic
            L.w32(buf + 4, uc.reg_read(UC_ARM_REG_LR))
            return 0

        def siglongjmp(uc, a):
            buf, val = a[0], (a[1] or 1)
            if buf not in L.jmpbufs:
                raise EmuError(f"siglongjmp to unsaved jmp_buf {buf:#x}")
            sp, lr, saved = L.jmpbufs[buf]
            for r, v in zip((UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
                             UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11),
                            saved):
                uc.reg_write(r, v)
            uc.reg_write(UC_ARM_REG_SP, sp)
            uc.reg_write(UC_ARM_REG_LR, lr)
            uc.reg_write(UC_ARM_REG_PC, lr)
            return val

        # ---- printf family with a va_list ---------------------------
        def _emit(text, a0):
            if L.capture_stdout is not None:
                L.capture_stdout.append(text)
            else:
                try:
                    sys.stdout.write(text.decode("latin1"))
                except Exception:
                    pass
            return len(text)

        def vsprintf(uc, a):
            text = L._format_va(a[1], a[2])
            L.uc.mem_write(a[0], text + b"\x00")
            return len(text)

        def vsnprintf(uc, a):
            text = L._format_va(a[2], a[3])
            n = a[1]
            if n:
                L.uc.mem_write(a[0], text[:n - 1] + b"\x00")
            return len(text)

        def vfprintf(uc, a):
            return _emit(L._format_va(a[1], a[2]), a[1])

        def _vaarg_reader(uc, start_reg=2):
            """AAPCS varargs: unconsumed args live in r(start)..r3 then on the stack."""
            ids = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3]
            state = {"reg": start_reg, "slot": 0}

            def nxt():
                if state["reg"] < 4:
                    v = uc.reg_read(ids[state["reg"]])
                    state["reg"] += 1
                else:
                    sp = uc.reg_read(UC_ARM_REG_SP)
                    v = struct.unpack("<I", uc.mem_read(sp + state["slot"] * 4, 4))[0]
                    state["slot"] += 1
                return v

            return nxt

        def sscanf(uc, a):
            """`sscanf(str, fmt, ...)` for %d %i %u %x %s %c %f %[set]."""
            src = L.cstr(a[0]).decode("latin1")
            fmt = L.cstr(a[1]).decode("latin1")
            nxt = _vaarg_reader(uc, 2)
            n = 0
            si = fi = 0
            while fi < len(fmt):
                c = fmt[fi]
                if c.isspace():
                    while fi < len(fmt) and fmt[fi].isspace():
                        fi += 1
                    while si < len(src) and src[si].isspace():
                        si += 1
                    continue
                if c != "%":
                    if si < len(src) and src[si] == c:
                        si += 1
                        fi += 1
                        continue
                    break
                fi += 1
                if fi < len(fmt) and fmt[fi] == "%":
                    if si < len(src) and src[si] == "%":
                        si += 1
                    fi += 1
                    continue
                while fi < len(fmt) and fmt[fi] in "-+ #0":
                    fi += 1
                width = 0
                while fi < len(fmt) and fmt[fi].isdigit():
                    width = width * 10 + int(fmt[fi])
                    fi += 1
                while fi < len(fmt) and fmt[fi] in "hlLzqjt":
                    fi += 1
                if fi >= len(fmt):
                    break
                spec = fmt[fi]
                fi += 1
                if spec == "[":
                    j = fi
                    if j < len(fmt) and fmt[j] == "^":
                        j += 1
                    if j < len(fmt) and fmt[j] == "]":
                        j += 1
                    while j < len(fmt) and fmt[j] != "]":
                        j += 1
                    cls = fmt[fi:j]
                    fi = min(j + 1, len(fmt))
                    negate = cls.startswith("^")
                    chars = cls[1:] if negate else cls
                    allowed = set()
                    k = 0
                    while k < len(chars):
                        if k + 2 < len(chars) and chars[k + 1] == "-":
                            allowed.update(chr(x) for x in
                                           range(ord(chars[k]), ord(chars[k + 2]) + 1))
                            k += 3
                        else:
                            allowed.add(chars[k])
                            k += 1
                    take = ""
                    while si < len(src) and (width == 0 or len(take) < width):
                        if (src[si] in allowed) == negate:
                            break
                        take += src[si]
                        si += 1
                    if not take:
                        break
                    L.putstr(nxt(), take)
                    n += 1
                    continue
                if spec not in "c[":
                    while si < len(src) and src[si].isspace():
                        si += 1
                lim = si + width if width else len(src)
                ptr = nxt()
                if spec in "diu":
                    m = re.match(r"\d+" if spec == "u" else r"[-+]?\d+", src[si:lim])
                    if not m:
                        break
                    v = int(m.group(0))
                    L.w32(ptr, v & 0xffffffff)
                    si += len(m.group(0))
                elif spec in "xX":
                    m = re.match(r"[-+]?(0[xX])?[0-9a-fA-F]+", src[si:lim])
                    if not m:
                        break
                    L.w32(ptr, int(m.group(0), 16 if not m.group(1) else 0) & 0xffffffff)
                    si += len(m.group(0))
                elif spec in "fFgGeE":
                    m = re.match(r"[-+]?(\d+\.?\d*([eE][-+]?\d+)?|\.\d+([eE][-+]?\d+)?)",
                                 src[si:lim])
                    if not m:
                        break
                    d = struct.pack("<d", float(m.group(0)))
                    L.uc.mem_write(ptr, d)
                    si += len(m.group(0))
                elif spec == "s":
                    m = re.match(r"\S+", src[si:lim])
                    if not m:
                        break
                    L.putstr(ptr, m.group(0))
                    si += len(m.group(0))
                elif spec == "c":
                    k = width or 1
                    if si + k > len(src):
                        break
                    L.uc.mem_write(ptr, src[si:si + k].encode("latin1"))
                    si += k
                else:
                    break
                n += 1
            return n

        def strdup(uc, a):
            return L.alloc_str(L.cstr(a[0]))

        def strtok_r(uc, a):
            s, delim, save = a[0], L.cstr(a[1]), a[2]
            base = s if s else L.u32(save)
            if not base:
                return 0
            delims = set(delim)
            pos = 0
            while True:
                chunk = L.cstr(base + pos)
                if not chunk:
                    return 0
                if chunk[0] not in delims:
                    break
                pos += 1
            tok = L.cstr(base + pos)
            cut = next((k for k, ch in enumerate(tok) if ch in delims), None)
            if cut is None:
                L.w32(save, 0)
                return base + pos
            L.uc.mem_write(base + pos + cut, b"\x00")
            L.w32(save, base + pos + cut + 1)
            return base + pos

        def strerror(uc, a):
            return L.alloc_str(f"errno {a[0]}")

        def strerror_r(uc, a):
            L.putstr(a[1], f"errno {a[0]}")
            return a[1]

        def _unimplemented(name):
            def f(uc, a):
                raise EmuError(
                    f"import {name}() is not supported by the harness "
                    f"(args={[hex(x) for x in a]}); it needs a re-entrant callback "
                    f"into emulated code (nested emu_start is not allowed from a hook).")
            return f

        def _f64(lo, hi):
            return struct.unpack("<d", struct.pack("<II", lo & 0xffffffff, hi & 0xffffffff))[0]

        def _f64lo(v):
            return struct.unpack("<II", struct.pack("<d", v))[0]

        def _f64hi(v):
            return struct.unpack("<II", struct.pack("<d", v))[1]

        def _ret_double(v):
            return _f64lo(v)

        def strtod(uc, a):
            """C strtod: parse an ASCII double, store *endptr (arg1) if given.

            AAPCS returns the double in r0 (low word) / r1 (high word), so r1 is
            written here (the import hook only sets r0 from the return value).
            """
            import re as _re
            s = L.cstr(a[0]).decode("latin1")
            m = _re.match(r"[ \t\n\r\f\v]*[-+]?(?:0[xX][0-9a-fA-F]+"
                          r"|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
                          r"|inf(?:inity)?|nan)", s, _re.I)
            if not m:
                val, consumed = 0.0, 0
            else:
                txt = m.group(0).strip()
                consumed = m.end()
                try:
                    if txt.lstrip("+-")[:2].lower() == "0x":
                        val = float(int(txt, 16))
                    else:
                        val = float(txt)
                except Exception:
                    val, consumed = 0.0, 0
            if a[1]:
                L.w32(a[1], a[0] + consumed)
            uc.reg_write(UC_ARM_REG_R1, _f64hi(val))
            return _f64lo(val)

        import math as _math

        def floor_(uc, a):
            return _ret_double(float(_math.floor(_f64(a[0], a[1]))))

        def ceil_(uc, a):
            return _ret_double(float(_math.ceil(_f64(a[0], a[1]))))

        def pow_(uc, a):
            return _ret_double(_math.pow(_f64(a[0], a[1]), _f64(a[2], a[3])))

        def exp_(uc, a):
            return _ret_double(_math.exp(_f64(a[0], a[1])))

        def fmod_(uc, a):
            return _ret_double(_math.fmod(_f64(a[0], a[1]), _f64(a[2], a[3])))

        def sqrt_(uc, a):
            return _ret_double(_math.sqrt(_f64(a[0], a[1])))

        def _gettimeofday(uc, a):
            if a[0]:
                L.w32(a[0], 1352215500)      # 2012-11-06
                L.w32(a[0] + 4, 0)
            return 0

        def _clock_gettime(uc, a):
            if a[1]:
                L.w32(a[1], 1352215500)
                L.w32(a[1] + 4, 0)
            return 0

        def _basename(uc, a):
            s = L.cstr(a[0]).decode("latin1").rstrip("/")
            return L.alloc_str(s.rsplit("/", 1)[-1])

        def _unwind_find_exidx(uc, a):
            # __gnu_Unwind_Find_exidx(pc, &count): return 0, count 0
            if a[1]:
                L.w32(a[1], 0)
            return 0

        extra = {
            # fd/file layer
            "open": open_, "close": close_, "read": read_, "write": write_,
            "lseek": lseek_, "mmap": mmap_, "munmap": munmap_,
            "fstat": fstat_, "stat": stat_, "fcntl": lambda uc, a: 0,
            "ioctl": lambda uc, a: -1, "umask": lambda uc, a: 0o22, "poll": lambda uc, a: 0,
            # setjmp/longjmp
            "sigsetjmp": sigsetjmp, "siglongjmp": siglongjmp,
            "setjmp": sigsetjmp, "longjmp": siglongjmp,
            # formatted io
            "vsprintf": vsprintf, "vsnprintf": vsnprintf, "vfprintf": vfprintf,
            "sscanf": sscanf,
            # strings
            "strdup": strdup, "strtok_r": strtok_r, "strerror": strerror,
            "strerror_r": strerror_r, "strtod": strtod,
            # time
            "gettimeofday": _gettimeofday, "clock_gettime": _clock_gettime,
            "mktime": lambda uc, a: 1352215500, "gmtime": lambda uc, a: 0,
            "gmtime_r": lambda uc, a: 0, "localtime": lambda uc, a: 0,
            "localtime_r": lambda uc, a: 0,
            # misc libc
            "basename": _basename, "getpid": lambda uc, a: 4242,
            "gettid": lambda uc, a: 4242, "getuid": lambda uc, a: 0,
            "geteuid": lambda uc, a: 0, "getpwuid": lambda uc, a: 0,
            "alarm": lambda uc, a: 0, "kill": lambda uc, a: 0, "raise": lambda uc, a: 0,
            "select": lambda uc, a: 0, "srand48": lambda uc, a: None,
            "lrand48": lambda uc, a: 0x1234567 & 0x7fffffff,
            "signal": lambda uc, a: 0, "sigaction": lambda uc, a: 0,
            "__gnu_Unwind_Find_exidx": _unwind_find_exidx,
            "__cxa_begin_cleanup": lambda uc, a: 0,
            "__cxa_type_match": lambda uc, a: 0,
            "__cxa_call_unexpected": lambda uc, a: 0,
            "__aeabi_unwind_cpp_pr0": lambda uc, a: 0,
            "__aeabi_unwind_cpp_pr1": lambda uc, a: 0,
            "__aeabi_unwind_cpp_pr2": lambda uc, a: 0,
            # sockets / semaphores (unused by the offline paths)
            "socket": lambda uc, a: -1, "connect": lambda uc, a: -1,
            "bind": lambda uc, a: -1, "recv": lambda uc, a: -1, "send": lambda uc, a: -1,
            "getsockname": lambda uc, a: -1, "getsockopt": lambda uc, a: -1,
            "setsockopt": lambda uc, a: -1, "inet_pton": lambda uc, a: 0,
            "inet_ntop": lambda uc, a: 0, "getaddrinfo": lambda uc, a: -1,
            "freeaddrinfo": lambda uc, a: 0, "gethostbyname_r": lambda uc, a: -1,
            "dlopen": lambda uc, a: 0, "dlsym": lambda uc, a: 0,
            "sem_open": lambda uc, a: 0, "sem_close": lambda uc, a: 0,
            "sem_post": lambda uc, a: 0, "sem_unlink": lambda uc, a: 0,
            "sem_getvalue": lambda uc, a: 0, "sem_timedwait": lambda uc, a: 0,
            # math (double args in r0/r1 pairs, result in r0/r1)
            "floor": floor_, "ceil": ceil_, "pow": pow_, "exp": exp_,
            "fmod": fmod_, "sqrt": sqrt_,
            # needs a re-entrant emulator: fail loudly instead of silently
            "qsort": _unimplemented("qsort"),
        }
        for nm, fn in extra.items():
            self.add_import(nm, fn)

    # ----------------------------------------------------- format helper
    def _c_format(self, fmt, nextarg, nextdouble):
        """printf-style formatter shared by the register/stack and va_list paths.

        Handles flags, width and precision (including the `*` forms the
        plug-in's letter-to-sound rule context uses), length modifiers and the
        conversions %s %d %i %u %x %X %o %c %p %% %f %e %g.  `nextarg()`
        returns the next integer-sized variadic word, `nextdouble()` the next
        double (two words).
        """
        out = bytearray()
        i, n = 0, len(fmt)
        while i < n:
            c = fmt[i]
            if c != 0x25:
                out.append(c); i += 1; continue
            i += 1
            if i >= n:
                break
            flags = bytearray()
            while i < n and fmt[i] in b"-+ #0":
                flags.append(fmt[i]); i += 1
            width = None
            if i < n and fmt[i] == 0x2A:                      # '*'
                width = nextarg(); i += 1
                if width >= 0x80000000:
                    width = 0x100000000 - width
                    flags.append(ord('-'))
            else:
                while i < n and 0x30 <= fmt[i] <= 0x39:
                    width = (width or 0) * 10 + fmt[i] - 0x30; i += 1
            prec = None
            if i < n and fmt[i] == 0x2E:                      # '.'
                i += 1
                if i < n and fmt[i] == 0x2A:
                    prec = nextarg(); i += 1
                    if prec >= 0x80000000:
                        prec = None
                else:
                    prec = 0
                    while i < n and 0x30 <= fmt[i] <= 0x39:
                        prec = prec * 10 + fmt[i] - 0x30; i += 1
            while i < n and fmt[i] in b"lhLqjzt":             # length modifiers
                i += 1
            if i >= n:
                break
            spec = fmt[i]; i += 1
            INT = (ord('d'), ord('i'), ord('u'), ord('x'), ord('X'), ord('o'))
            if spec == ord('s'):
                p = nextarg()
                text = self.cstr(p) if p else b""
                if prec is not None:
                    text = text[:prec]
            elif spec in (ord('d'), ord('i')):
                v = nextarg()
                text = str(v - 0x100000000 if v >= 0x80000000 else v).encode()
            elif spec == ord('u'):
                text = str(nextarg()).encode()
            elif spec in (ord('x'), ord('X'), ord('o')):
                v = nextarg()
                text = (("%x" % v) if spec == ord('x') else
                        ("%X" % v) if spec == ord('X') else ("%o" % v)).encode()
            elif spec == ord('p'):
                v = nextarg()
                text = b"(nil)" if not v else ("0x%x" % v).encode()
            elif spec == ord('c'):
                text = bytes([nextarg() & 0xff])
            elif spec == ord('%'):
                text = b"%"
            elif spec in (ord('f'), ord('F'), ord('e'), ord('E'), ord('g'), ord('G')):
                d = nextdouble()
                f = {ord('f'): "%f", ord('F'): "%F", ord('e'): "%e",
                     ord('E'): "%E", ord('g'): "%g", ord('G'): "%G"}[spec]
                if prec is not None:
                    f = f.replace("%", "%." + str(prec))
                text = (f % d).encode()
            else:
                text = bytes([spec])
            if prec is not None and spec in INT and len(text) < prec:
                text = b"0" * (prec - len(text)) + text
            if width and len(text) < width:
                pad = b" " * (width - len(text))
                text = text + pad if ord('-') in flags else pad + text
            out += text
        return bytes(out)

    def _format_va(self, fmt_addr, va_ptr):
        """printf-style format with a va_list pointing at a word array."""
        fmt = self.cstr(fmt_addr)
        n = [0]

        def nextarg():
            v = self.u32(va_ptr + 4 * n[0])
            n[0] += 1
            return v

        def nextdouble():
            if n[0] % 2:            # 8-byte aligned slot in the va_list array
                n[0] += 1
            lo, hi = nextarg(), nextarg()
            return struct.unpack("<d", struct.pack("<II", lo, hi))[0]

        return self._c_format(fmt, nextarg, nextdouble)

    # -------------------------------------------------------- utilities
    def w16(self, addr, v):
        self.uc.mem_write(addr, struct.pack("<H", v & 0xffff))

    def set_trace(self, flag=True, only=None):
        """Wrap every registered import callback with a call/return logger."""
        self.trace_calls = flag
        self.trace_filter = only
        self._trace_re = re.compile(only) if only else None
        for base, cb in list(self.import_cbs.items()):
            if getattr(cb, "_traced", False) or not flag:
                continue
            name = self.stub_names.get(base, hex(base))
            L = self

            def wrapped(uc, a, _fn=cb, _n=name):
                if L._trace_re and not L._trace_re.search(_n):
                    return _fn(uc, a)
                lr = uc.reg_read(UC_ARM_REG_LR)
                print(f"[call] {_n}({', '.join(hex(x) for x in a)}) lr={lr:#x}")
                r = _fn(uc, a)
                print(f"[ret ] {_n} -> {hex((r or 0) & 0xffffffff)}")
                return r

            wrapped._traced = True
            self.import_cbs[base] = wrapped

    def heap_span(self):
        return (HEAP_BASE, self.heap_ptr)

    def find_bytes(self, needle, start=HEAP_BASE, size=None):
        """Return the first address in emulated memory holding `needle`."""
        end = self.heap_ptr if size is None else start + size
        chunk = bytes(self.uc.mem_read(start, end - start))
        i = chunk.find(needle)
        return None if i < 0 else start + i

    def dump(self, addr, size, path):
        with open(path, "wb") as fh:
            fh.write(bytes(self.uc.mem_read(addr, size)))
        return path

    def read_struct(self, addr, words=8):
        return [self.u32(addr + 4 * i) for i in range(words)]

    def _obj_backing(self, name):
        """Return (allocating on first use) backing storage for a data import."""
        if name in self.obj_addrs:
            return self.obj_addrs[name]
        p = self.alloc(0x1000)
        self.obj_addrs[name] = p
        if name == "__page_size":
            self.w32(p, 0x1000)
        elif name == "__stack_chk_guard":
            self.w32(p, 0x0000ff0a)
        elif name in ("_ctype_", "_tolower_tab_", "_toupper_tab_"):
            tab = bytearray(0x101)
            for c in range(1, 256):
                ch = chr(c)
                flags = 0
                if ch.isalpha():
                    flags |= 0x01
                if ch.isdigit():
                    flags |= 0x04
                if ch.isspace():
                    flags |= 0x08
                if ch.isupper():
                    flags |= 0x02
                if ch.islower():
                    flags |= 0x04
                tab[c] = flags
            self.uc.mem_write(p, bytes(tab))
        return p

    def _setup_object_imports(self):
        """Point GOT entries of data imports (STT_OBJECT) at backing storage.

        Function imports are left pointing at their `bx lr` stubs.
        """
        self.obj_addrs = {}
        for sec in self.elf.iter_sections():
            if not isinstance(sec, RelocationSection):
                continue
            symtab = self.elf.get_section(sec["sh_link"])
            for rel in sec.iter_relocations():
                if rel["r_info_type"] not in (R_ARM_GLOB_DAT, R_ARM_ABS32):
                    continue
                sym = symtab.get_symbol(rel["r_info_sym"])
                if (sym.name and sym["st_shndx"] == "SHN_UNDEF"
                        and sym["st_info"]["type"] == "STT_OBJECT"):
                    self.w32(rel["r_offset"], self._obj_backing(sym.name))

    # ------------------------------------------------------------ helpers
    def regs(self):
        names = ["r0","r1","r2","r3","r4","r5","r6","r7","r8","r9","r10","fp","ip","sp","lr","pc"]
        ids = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
               UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
               UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC]
        return {n: self.uc.reg_read(i) for n, i in zip(names, ids)}
