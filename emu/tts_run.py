#!/usr/bin/env python3
"""tts_run.py -- run the *real* IVONA engine under emulation and capture
reference ("oracle") outputs for the TTS pipeline.

Chain driven here (all code is the unmodified ARM32 library; only libc/bionic
imports are Python stubs, and the voice plug-in is mapped into the same
emulated address space because the harness' `dlopen`/`dlsym` are ours):

    tts_init(cert_text)                       -> engine   (level 1)
    tts_load_voice(engine, plugin.so, obb)    -> voice    (level 1)
    tts_streamer_start(voice, text, -1.0f)    -> streamer (level 2)
    tts_streamer_synth0(streamer, pcm, n) * k -> PCM      (level 3)
    tts_streamer_stop(streamer)

Why a second module has to be mapped manually
---------------------------------------------
`libvoice_en_us_kendra.so` is loaded by the engine through `dlopen`, which the
harness stubs.  The plug-in's link-time vaddrs overlap the engine's (both start
at 0), so it is mapped at `--plugin-base` (default 0x20000000) with every
relocation rebased by that delta; its undefined symbols resolve to the engine's
existing libc stub table (the two libraries' import sets were verified to be a
subset - see report_oracle.md).

Every captured artefact is written under --out-dir; the exact command line is
reproduced in report_oracle.md and echoed into `cmdline.txt`.

Reproduce (from the repository root):

    ~/venvs/re/bin/python emu/tts_run.py --sentence "Hello world, this is a test."
"""

import argparse
import io
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unicorn                                                    # noqa: E402
from unicorn import UC_HOOK_BLOCK, UC_HOOK_CODE, UC_PROT_ALL      # noqa: E402
from elftools.elf.elffile import ELFFile                           # noqa: E402
from elftools.elf.relocation import RelocationSection              # noqa: E402

import armemu                                                      # noqa: E402
from armemu import ArmLib, EmuError, RET_TRAP                      # noqa: E402
from run import load_ghidra_funcs                                  # noqa: E402

R_ARM_ABS32 = 2
R_ARM_GLOB_DAT = 21
R_ARM_JUMP_SLOT = 22
R_ARM_RELATIVE = 23


# --------------------------------------------------------------- engine API
# The reports cite *Ghidra dump* addresses (= ELF vaddr + 0x10000); the harness
# calls ELF vaddrs, so every literal below goes through G().
def G(addr):
    return addr - 0x10000


def float_bits(bits):
    """Reinterpret a 32-bit register value as a float (for diagnostics)."""
    return struct.unpack("<f", struct.pack("<I", bits & 0xFFFFFFFF))[0]

V_TTS_INIT = G(0x486E0)              # report_engine_api.md vtable slot +0x0c
V_TTS_LOAD_VOICE = G(0x4C028)        # slot +0x28
V_TTS_VOICE_SAMPLE_RATE = G(0x4BC64)  # slot +0x34
V_TTS_STREAMER_START = G(0x4AC38)    # slot +0x58
V_TTS_STREAMER_STOP = G(0x4AB34)     # slot +0x5c
V_TTS_STREAMER_SYNTH0 = G(0x4B460)   # slot +0x68
V_TTS_STREAMER_SYNTH = G(0x4B51C)    # slot +0x6c
V_TTS_WAVE_DELETE = G(0x4A9B4)       # slot +0x70
V_TTS_ERRNO = G(0x473BC)             # slot +0x04
V_TTS_ERRMSG = G(0x473CC)            # slot +0x08

# pipeline internals we instrument (Ghidra dump addresses from
# report_engine_synth.md / probe_gap.py, converted with G())
V_FUN_4A2D4 = G(0x4A2D4)        # input admission (text/plain -> SSML wrap)
V_FUN_4AE28 = G(0x4AE28)        # pump: produce one chunk
V_FUN_40770 = G(0x40770)        # front-end top: produce next utterance
V_FUN_64F38 = G(0x64F38)        # stage pipeline runner #1
V_FUN_65028 = G(0x65028)        # stage pipeline runner #2
V_FUN_650B0 = G(0x650B0)        # stage pipeline runner #3
V_FUN_5AA88 = G(0x5AA88)        # task init (runs the stage pipeline)
V_FUN_5A698 = G(0x5A698)        # per-chunk synthesis driver
V_FUN_5D7C4 = G(0x5D7C4)        # core synthesis (graph + viterbi + waveform)
V_FUN_5FC04 = G(0x5FC04)        # Viterbi search
V_FUN_5EF70 = G(0x5EF70)        # voxdb record read (== selected diphone index)
V_FUN_5EF00 = G(0x5EF00)        # diphone name -> index binary search
V_FUN_5F1DC = G(0x5F1DC)        # 36-byte diphonedb record decode
V_FUN_60ED4 = G(0x60ED4)        # item -> 96-byte feature vector (FEM)
V_FUN_61620 = G(0x61620)        # concat
V_FUN_618A8 = G(0x618A8)        # finalize chunk
V_FUN_61804 = G(0x61804)        # append silence/zero samples
V_FUN_63350 = G(0x63350)        # set length of a segment range (silence trim)
V_FUN_62718 = G(0x62718)        # insert zeros into a segment range
V_FUN_63540 = G(0x63540)        # pitch stretch
V_FUN_62D14 = G(0x62D14)        # time stretch
V_FUN_6706C = G(0x6706C)        # tokentowords applier (per Token)
V_FUN_674F8 = G(0x674F8)        # tokenizer default
V_FUN_58EFC = G(0x58EFC)        # item -> item[0][0] (feature param list head)
V_FUN_62C54 = G(0x62C54)        # gain / amplify
V_FUN_59064 = G(0x59064)        # item,key -> has-feature
V_FUN_52374 = G(0x52374)        # ctx, VAL -> resolved value

VAL_TAG_INT = 1
VAL_TAG_FLOAT = 3
VAL_TAG_STRING = 5

# Functions whose return values are logged right after they return (the r0 at
# the caller's continuation PC).  Enabled with --ret-probe.  Names/addresses
# mirror the --trace-funcs set; these are the ones that decide control flow.
RET_PROBE = {
    G(0x4e028): "FUN_0004e028", G(0x4a2d4): "FUN_0004a2d4",
    G(0x4ae28): "FUN_0004ae28", G(0x40770): "FUN_00040770",
    G(0x5a698): "FUN_0005a698", G(0x5d7c4): "FUN_0005d7c4",
    G(0x5fc04): "FUN_0005fc04", G(0x5ef00): "FUN_0005ef00",
    G(0x5ef70): "FUN_0005ef70", G(0x5f064): "FUN_0005f064",
    G(0x5f3cc): "FUN_0005f3cc", G(0x5d144): "FUN_0005d144",
    G(0x618a8): "FUN_000618a8", G(0x64f38): "FUN_00064f38",
    G(0x6706c): "FUN_0006706c", G(0x5fb94): "FUN_0005fb94",
    G(0x60ed4): "FUN_00060ed4", G(0x5f1dc): "FUN_0005f1dc",
}

# return-probes that fire very often are still captured but not printed
RET_PROBE_QUIET = {"FUN_0005f1dc": 0, "FUN_00060ed4": 0}


# ------------------------------------------------------- secondary module map
def load_module(lib, path, base, quiet=False):
    """Map `path` into lib's Unicorn instance at `base`, rebase its
    relocations, resolve undefined symbols against lib's stub table and return
    {export_name: address}."""
    raw = open(path, "rb").read()
    elf = ELFFile(io.BytesIO(raw))
    for seg in elf.iter_segments():
        if seg["p_type"] != "PT_LOAD":
            continue
        va, memsz, filesz = seg["p_vaddr"], seg["p_memsz"], seg["p_filesz"]
        start = va & ~0xFFF
        end = (va + memsz + 0xFFF) & ~0xFFF
        lib.uc.mem_map(base + start, end - start, UC_PROT_ALL, )
        data = seg.data()
        if data:
            lib.uc.mem_write(base + va, data)
        if memsz > filesz:
            lib.uc.mem_write(base + va + filesz, b"\x00" * (memsz - filesz))
    # ---- relocations, rebased by `base`
    for sec in elf.iter_sections():
        if not isinstance(sec, RelocationSection):
            continue
        symtab = elf.get_section(sec["sh_link"])
        for rel in sec.iter_relocations():
            rtype = rel["r_info_type"]
            off = base + rel["r_offset"]
            symidx = rel["r_info_sym"]
            name, sval, undef, otype = "", 0, True, None
            if symidx:
                sym = symtab.get_symbol(symidx)
                name, sval = sym.name, sym["st_value"]
                undef = sym["st_shndx"] == "SHN_UNDEF"
                otype = sym["st_info"]["type"]
            addend = 0
            if rtype in (R_ARM_RELATIVE, R_ARM_ABS32):
                if rel["r_offset"] + 4 <= len(raw):
                    addend = struct.unpack_from("<I", raw, rel["r_offset"])[0]
            if rtype == R_ARM_RELATIVE:
                val = base + addend
            elif rtype in (R_ARM_JUMP_SLOT, R_ARM_GLOB_DAT):
                if undef or sval == 0:
                    val = (lib._obj_backing(name) if otype == "STT_OBJECT"
                           else lib._stub_for(name))
                else:
                    val = base + sval
            elif rtype == R_ARM_ABS32:
                if not undef and sval:
                    val = base + sval + addend
                else:
                    val = (lib._obj_backing(name) if otype == "STT_OBJECT"
                           else lib._stub_for(name))
            else:
                continue
            lib.uc.mem_write(off, struct.pack("<I", val & 0xFFFFFFFF))
    # ---- exports
    exports = {}
    dyn = elf.get_section_by_name(".dynsym")
    if dyn is not None:
        for s in dyn.iter_symbols():
            if s["st_shndx"] != "SHN_UNDEF" and s.name:
                exports.setdefault(s.name, base + s["st_value"])
    if not quiet:
        print(f"[module] {os.path.basename(path)} mapped at {base:#x}: "
              f"exports={ {k: hex(v) for k, v in exports.items()} }")
    return exports


# --------------------------------------------------------------------- qsort
# `qsort` is used by the synthesis pipeline to order fixed-stride result
# records by a leading u32 key.  Calling the comparator through a *nested*
# `uc.emu_start` is not possible: Unicorn 2.1 is not re-entrant (verified --
# the outer run resumes with a corrupted PC / is stopped by the inner
# `emu_stop`), so the two in-library comparators are re-implemented here.
#
# key description: (deref, offset) -> key = u32 at  elem[offset]      (deref 0)
#                                            or  u32 at *elem + offset (deref 1)
QSORT_KEY = {
    0x4FA44: (0, 0),     # engine  LAB_0005fa44: unsigned u32 at +0
    0x4FA64: (0, 8),     # engine  LAB_0005fa64: unsigned u32 at +8
    0x130EC8: (1, 0),    # engine  LAB_00140ec8: u32 at *(elem)
    0x133A6C: (1, 0),    # engine  LAB_00143a6c: u32 at *(elem)
}
# plugin-side copy of the same sort helper (libvoice_*.so LAB_0002ee1c)
QSORT_PLUGIN_OFF = 0x1EE1C


def make_qsort(lib, plugin_base=0):
    """qsort with the library's own comparators evaluated in Python."""
    def qsort(uc, a):
        base, nmemb, size, cmpfn = a[0], a[1], a[2], a[3]
        if nmemb < 2 or size == 0 or not cmpfn:
            return 0
        key = QSORT_KEY.get(cmpfn & ~1)
        if key is None and (cmpfn & ~1) == plugin_base + QSORT_PLUGIN_OFF:
            key = (0, 0)
        if key is None:
            raise EmuError(
                f"qsort: comparator {cmpfn:#x} not re-implemented; nested "
                f"emulation is not re-entrant in Unicorn 2.1")
        deref, off = key
        items = [bytes(uc.mem_read(base + i * size, size)) for i in range(nmemb)]
        def sort_key(b):
            if deref:
                return struct.unpack_from("<I", uc.mem_read(
                    struct.unpack_from("<I", b, 0)[0] + off, 4))[0]
            return struct.unpack_from("<I", b, off)[0]
        # unsigned order == the comparators' `cmp` + `mvnlo`/`movhi`
        items.sort(key=sort_key)
        for i, it in enumerate(items):
            uc.mem_write(base + i * size, it)
        return 0
    return qsort


# ------------------------------------------------------------------- drivers
class Oracle:
    def __init__(self, args):
        self.args = args
        self.argv = sys.argv
        root = args.root
        self.engine_so = os.path.join(root, args.engine)
        self.plugin_so = os.path.join(root, args.plugin)
        self.cert = os.path.join(root, args.cert)
        self.obb = os.path.join(root, args.obb)
        self.dat_dir = os.path.join(root, args.dat_dir) if args.dat_dir else None
        self.lib = ArmLib(self.engine_so)
        self.lib.fs_root = args.fs_root
        if args.trace_alloc:
            _orig = self.lib.alloc
            R = unicorn.arm_const

            def _alloc(size, _o=_orig, _lib=self.lib, _args=args):
                if size >= _args.trace_alloc:
                    print(f"[heap] alloc {size:#x} used={_lib.heap_ptr - armemu.HEAP_BASE:#x} "
                          f"pc={_lib.uc.reg_read(R.UC_ARM_REG_PC):#x} "
                          f"lr={_lib.uc.reg_read(R.UC_ARM_REG_LR):#x}")
                return _o(size)

            self.lib.alloc = _alloc
        self.trace = []
        self.sample_rate = None
        self.engine = 0
        self.voice = 0
        self.streamer = 0
        self.unit_seq = []            # FUN_0005ef70 argument (selected diphones)
        self.fem = []                 # (item, 96-byte feature vector) pairs
        self.f1dc = []                # (36-byte section-C record, 96-byte FEM)
        self.viterbi_nodes = []       # per-node candidate arrays after FUN_0005fc04
        self.viterbi = []             # FUN_0005fc04 entry records
        self.tokens = []              # FUN_0006706c, decoded item features
        self.pitch_calls = []         # FUN_00063540 stretch arguments
        self.time_calls = []          # FUN_00062d14 stretch arguments
        self.gain_calls = []          # FUN_00062c54 gain arguments
        self.pipeline_runs = []       # stage-pipeline runner invocations
        self.pump_calls = 0
        self.stream_log = []          # per-call streamer state (splice/finalize/pad)
        self._st_pending = None
        self.splice_calls = 0
        self.pad_calls = 0
        self.entry_trace = []
        self.entry_counts = {}
        self.ddb = None
        self._hook_names = {}
        self.hooks = []
        self.exporter = None

    # -- infrastructure ----------------------------------------------------
    def log(self, msg):
        line = f"[oracle] {msg}"
        print(line)
        self.trace.append(msg)

    # -- guest structure readers -------------------------------------------
    def val_decode(self, val):
        """Decode an 8-byte engine VAL {i16 tag, i16 refcount, void* payload}."""
        if not val:
            return None
        tag = struct.unpack("<h", bytes(self.lib.uc.mem_read(val, 2)))[0]
        pay = self.lib.u32(val + 4)
        try:
            if tag == VAL_TAG_STRING:
                return "str:" + self.lib.cstr(pay).decode("latin1")
            if tag == VAL_TAG_INT:
                return "int:" + str(struct.unpack("<i", struct.pack("<I", pay))[0])
            if tag == VAL_TAG_FLOAT:
                return "flt:%.6g" % struct.unpack("<f", struct.pack("<I", pay))[0]
        except Exception:
            return f"tag{tag}:err"
        return f"tag{tag}:{pay:#x}"

    # -- streamer state probe (splice/finalize/pad) -------------------------
    def obj_dump(self, obj):
        """`(N, pms)` of a unit record object.

        Layout (report_segmentation.md sec.1): `obj+0x04` rate, `obj+0x08` N,
        `obj+0x0c` -> int32 pms[N] (a *pointer*, and the restretch reallocates it
        -- FUN_00062688 -- so a fixed offset would show a freed array),
        `obj+0x10` -> int16* block[N].
        """
        lib = self.lib
        n = lib.u32(obj + 8)
        if not (0 < n <= 4096):
            return n, []
        ptr = lib.u32(obj + 0xC)
        return n, [lib.s32(ptr + 4 * i) for i in range(n)]

    def stream_enter(self, name, a0, a1, a2, a3, lr):
        """Snapshot the streamer state around the waveform-assembly calls.

        streamer layout (report_segmentation.md sec.3): +0x0c = output buffer
        {+4 sample rate, +8 capacity, +0x10 int16* data}, +0x10 = pos,
        +0x14 = tail, +0x18 = total.  `obj` (a unit record object): +8 = N
        segments, +0xc = int32 pms[N] (cumulative sample marks).
        """
        if not self.args.stream_probe:
            return
        lib = self.lib
        try:
            if name == "FUN_00061620":
                st, obj, flag = a0, a1, a2
                N, pms = self.obj_dump(obj)
                self._st_pending = dict(kind="splice", st=st, pos=lib.u32(st + 0x10),
                                        total=lib.u32(st + 0x18))
                self.stream_log.append(
                    "splice #%d unit=%s flag=%d N=%d pos=%d tail=%d total=%d pms=%s"
                    % (self.splice_calls,
                       self.unit_seq[-1] if self.unit_seq else -1, flag, N,
                       lib.u32(st + 0x10), lib.u32(st + 0x14), lib.u32(st + 0x18),
                       pms))
                self.splice_calls += 1
                self._stream_watch[lr] = "splice"
            elif name == "FUN_000618a8":
                st = a0
                self._st_pending = dict(kind="finalize", st=st, want=a1,
                                        pos=lib.u32(st + 0x10),
                                        tail=lib.u32(st + 0x14))
                self._stream_watch[lr] = "finalize"
            elif name == "FUN_00061804":
                st, n = a0, a2
                self.stream_log.append(
                    "pad    #%d n=%d pos=%d tail=%d total=%d"
                    % (self.pad_calls, n, lib.u32(st + 0x10), lib.u32(st + 0x14),
                       lib.u32(st + 0x18)))
                self.pad_calls += 1
            elif name == "FUN_00063350":
                N, pms = self.obj_dump(a0)
                self.stream_log.append(
                    "trim   setlen(seg %d..%d) = %d  (N=%d pms=%s)"
                    % (a1, a2, a3, N, pms))
                self._st_pending = dict(kind="trim", st=a0)
                self._stream_watch[lr] = "trim"
            elif name == "FUN_00062718":
                N, pms = self.obj_dump(a0)
                self.stream_log.append(
                    "trim   insert_zeros(seg %d) n=%d (N=%d pms=%s)"
                    % (a1, a2, N, pms))
                self._st_pending = dict(kind="trim", st=a0)
                self._stream_watch[lr] = "trim"
        except Exception as e:
            self.stream_log.append("%s probe failed: %s: %s"
                                   % (name, type(e).__name__, e))

    def stream_return(self, kind):
        p = self._st_pending
        self._st_pending = None
        if p is None:
            return
        lib = self.lib
        try:
            st = p["st"]
            pos = lib.u32(st + 0x10)
            tail = lib.u32(st + 0x14)
            total = lib.u32(st + 0x18)
            if p["kind"] == "splice":
                self.stream_log.append(
                    "      -> written=%d pos=%d tail=%d total=%d"
                    % (pos - p["pos"], pos, tail, total))
            elif p["kind"] == "trim":
                n, pms = self.obj_dump(p["st"])
                self.stream_log.append(
                    "      -> after setlen: N=%d total=%d pms=%s"
                    % (n, pms[-1] if n else 0, pms))
            else:
                self.stream_log.append(
                    "finalize want=%d pos0=%d tail0=%d -> n=%d pos=%d tail=%d total=%d"
                    % (p["want"], p["pos"], p["tail"], p["pos"] - pos, pos, tail,
                       total))
        except Exception as e:
            self.stream_log.append("stream return probe failed: %s" % e)

    def dump_viterbi_nodes(self):
        """After FUN_0005fc04 returns: read the engine's own per-candidate cost
        arrays (state[4], stride 0xd4, +0xcc ptr / +0xd0 count, 20-byte entries
        {+0x00 target cost, +0x08 total, +0x0c diphone index})."""
        lib = self.lib
        try:
            state = self._fc04_state
            base = lib.u32(state + 0x10)
            nnodes = lib.u32(state + 0x14)
            for i in range(min(nnodes, 4096)):
                node = base + i * 0xD4
                ptr = lib.u32(node + 0xCC)
                cnt = lib.u32(node + 0xD0)
                if not ptr or not (0 < cnt < 4096):
                    continue
                ents = []
                for k in range(cnt):
                    e = ptr + k * 0x14
                    ents.append((lib.u32(e), lib.u32(e + 8), lib.u32(e + 0xC)))
                self.viterbi_nodes.append((i, ents))
        except Exception as e:
            self.log(f"dump_viterbi_nodes failed: {type(e).__name__}: {e}")

    def _try_cstr(self, p):
        """Best-effort: decode `p` as a printable NUL-terminated string."""
        if not p or p < 0x1000:
            return None
        try:
            b = self.lib.cstr(p, 64)
        except Exception:
            return None
        if not b or any(c < 0x20 or c > 0x7e for c in b):
            return None
        return b.decode("latin1")

    def param_list(self, head):
        """Walk a {char* key, VAL* val, node* next} list (stride 0xC)."""
        out = []
        node = head
        seen = set()
        while node and node not in seen and len(out) < 4096:
            seen.add(node)
            key = self.lib.cstr(self.lib.u32(node)).decode("latin1")
            out.append((key, self.lib.u32(node + 4)))
            node = self.lib.u32(node + 8)
        return out

    def item_features(self, item):
        """All features of a Festival-style item: item[0] -> feature list."""
        if not item:
            return {}
        try:
            head = self.lib.u32(self.lib.u32(item))
        except Exception:
            return {}
        return {k: self.val_decode(v) for k, v in self.param_list(head)}

    def find_diphonedb(self):
        """voice[5] -> wrapper -> plugin obj -> param list -> 'diphonedb'."""
        lib = self.lib
        try:
            wrapper = lib.u32(self.voice + 0x14)   # engine wrapper {params, dir, cbq}
            obj = lib.u32(wrapper)                 # plugin voice object (0xC)
            store = lib.u32(obj)                   # param store {head, ...} (8 B)
            head = lib.u32(store)                  # head of the {key,val,next} list
            items = self.param_list(head)
            self.voice_params = items
            self.log("voice[5]=%#x pluginobj=%#x store=%#x head=%#x nkeys=%d" % (
                wrapper, obj, store, head, len(items)))
            self.log("  keys: " + ",".join(k for k, _ in items[:64]))
            for key, val in items:
                if key == "diphonedb":
                    payload = lib.u32(val + 4)
                    self.ddb = {
                        "payload": payload,
                        "name": lib.cstr(lib.u32(payload)),
                        "checksum": lib.u32(payload + 4),
                        "n_records": lib.u32(payload + 8),
                        "name_table": lib.u32(payload + 0xC),
                        "index_table": lib.u32(payload + 0x10),
                        "records": lib.u32(payload + 0x14),
                        "ext": lib.u32(payload + 0x18),
                        "model": lib.u32(payload + 0x1C),
                    }
                    self.log("diphonedb: " + ", ".join(
                        f"{k}={v:#x}" if isinstance(v, int) else f"{k}={v}"
                        for k, v in self.ddb.items()))
                    return self.ddb
        except Exception as e:
            self.log(f"find_diphonedb failed: {type(e).__name__}: {e}")
        self.ddb = None
        return None

    def build_unit_names(self):
        """unit-id (a section-B entry) -> (diphone name, variant, diphone idx).

        Section A (diphoneset_num) is 1601 x 20-byte records
        {char name[12]; u32 b_start; u32 b_count}; section B is the flat u32
        list of unit ids, grouped per diphone.  All of it is read out of the
        guest image that the plug-in mapped.
        """
        if not self.ddb:
            return {}
        lib = self.lib
        names, idx_tab, n = (self.ddb["name_table"], self.ddb["index_table"],
                             self.ddb["n_records"])
        na = bytes(lib.uc.mem_read(names, n * 0x14))
        tot = sum(struct.unpack_from("<I", na, i * 0x14 + 16)[0]
                  for i in range(n))
        ib = bytes(lib.uc.mem_read(idx_tab, tot * 4))
        out = {}
        for i in range(n):
            nm = na[i * 0x14:i * 0x14 + 12].split(b"\x00", 1)[0].decode("latin1")
            start, count = struct.unpack_from("<II", na, i * 0x14 + 12)
            for k in range(count):
                unit = struct.unpack_from("<I", ib, (start + k) * 4)[0]
                out.setdefault(unit, (nm, k, i))
        return out

    def diphone_ranges(self):
        """diphone index -> (name, b_start, b_count, [first_unit, last_unit]).

        Section A entries as (name, start, count) with the section-B unit ids.
        """
        if not self.ddb:
            return {}
        lib = self.lib
        names, idx_tab, n = (self.ddb["name_table"], self.ddb["index_table"],
                             self.ddb["n_records"])
        na = bytes(lib.uc.mem_read(names, n * 0x14))
        tot = sum(struct.unpack_from("<I", na, i * 0x14 + 16)[0]
                  for i in range(n))
        ib = bytes(lib.uc.mem_read(idx_tab, tot * 4))
        out = {}
        for i in range(n):
            nm = na[i * 0x14:i * 0x14 + 12].split(b"\x00", 1)[0].decode("latin1")
            start, count = struct.unpack_from("<II", na, i * 0x14 + 12)
            if count:
                first = struct.unpack_from("<I", ib, start * 4)[0]
                last = struct.unpack_from("<I", ib, (start + count - 1) * 4)[0]
            else:
                first = last = 0
            out[i] = (nm, start, count, first, last)
        return out

    def diphone(self, idx):
        """(name, duration_ms) for a diphoneset_num."""
        if not self.ddb or not (0 <= idx < 0x100000):
            return ("?", 0)
        try:
            name = self.lib.cstr(self.ddb["name_table"] + idx * 0x14, 13).decode("latin1")
            dur = struct.unpack("<h", bytes(self.lib.uc.mem_read(
                self.ddb["records"] + idx * 0x24, 2)))[0]
            return (name, dur)
        except Exception:
            return ("?", 0)

    def setup_module(self):
        base = self.args.plugin_base
        self.plugin_exports = load_module(self.lib, self.plugin_so, base)
        self.plugin_base = base
        lib = self.lib

        handles = {}

        def dlopen(uc, a):
            path = lib.cstr(a[0]).decode("latin1")
            h = 0x1000 + len(handles) + 1
            handles[h] = path
            handles.setdefault(path, h)
            print(f"[dlopen] {path!r} -> {h:#x}")
            return h

        def dlsym(uc, a):
            name = lib.cstr(a[1]).decode("latin1")
            addr = self.plugin_exports.get(name, 0)
            print(f"[dlsym ] handle={a[0]:#x} {name!r} -> {addr:#x}")
            return addr

        lib.add_import("dlopen", dlopen)
        lib.add_import("dlsym", dlsym)
        lib.add_import("dlclose", lambda uc, a: 0)
        lib.add_import("dlerror", lambda uc, a: 0)
        lib.add_import("qsort", make_qsort(lib, base))
        if self.args.deterministic:
            # srand48(time(NULL)) + lrand48 in FUN_00064fbc: pin both
            lib.add_import("lrand48", lambda uc, a: 0x1234567 & 0x7FFFFFFF)
        # env for the engine's data-root resolution
        if self.dat_dir:
            lib.env["IVONA_LANG_DAT_DIR"] = self.dat_dir
        for kv in self.args.env:
            k, _, v = kv.partition("=")
            lib.env[k] = v

    def install_hooks(self):
        lib = self.lib
        R = unicorn.arm_const
        self.r0, self.r1, self.r2, self.r3 = (R.UC_ARM_REG_R0, R.UC_ARM_REG_R1,
                                              R.UC_ARM_REG_R2, R.UC_ARM_REG_R3)
        want = {V_FUN_5EF70: "FUN_0005ef70", V_FUN_5FC04: "FUN_0005fc04",
                V_FUN_6706C: "FUN_0006706c", V_FUN_674F8: "FUN_000674f8",
                V_FUN_4AE28: "FUN_0004ae28", V_FUN_40770: "FUN_00040770",
                V_FUN_5A698: "FUN_0005a698", V_FUN_5D7C4: "FUN_0005d7c4",
                V_FUN_64F38: "FUN_00064f38", V_FUN_65028: "FUN_00065028",
                V_FUN_650B0: "FUN_000650b0", V_FUN_63540: "FUN_00063540",
                V_FUN_62D14: "FUN_00062d14", V_FUN_62C54: "FUN_00062c54",
                V_FUN_618A8: "FUN_000618a8", V_FUN_61804: "FUN_00061804",
                V_FUN_5EF00: "FUN_0005ef00", V_FUN_5F1DC: "FUN_0005f1dc",
                V_FUN_61620: "FUN_00061620", V_FUN_4A2D4: "FUN_0004a2d4",
                V_FUN_63350: "FUN_00063350", V_FUN_62718: "FUN_00062718",
                V_FUN_60ED4: "FUN_00060ed4"}

        def on_code(uc, address, size, user):
            sw = self._stream_watch.pop(address, None)
            if sw is not None:
                self.stream_return(sw)
            rn = self._ret_watch.pop(address, None)
            if rn is not None:
                n = self._ret_counts.get(rn, 0)
                self._ret_counts[rn] = n + 1
                if n < RET_PROBE_QUIET.get(rn, 80):
                    print(f"[ret ] {rn} -> {uc.reg_read(self.r0):#x}")
                if rn == "FUN_0005ef00":
                    self.diphone_lookups.append((self._ef00_pending,
                                                 uc.reg_read(self.r0)))
                elif rn == "FUN_00060ed4" and self._fem_pending is not None:
                    item, out = self._fem_pending
                    self._fem_pending = None
                    if len(self.fem) < 400:
                        try:
                            self.fem.append((item, bytes(uc.mem_read(out, 0x60))))
                        except Exception:
                            pass
                elif rn == "FUN_0005f1dc" and self._f1dc_pending is not None:
                    rec, out = self._f1dc_pending
                    self._f1dc_pending = None
                    if len(self.f1dc) < 6000:
                        try:
                            self.f1dc.append((bytes(uc.mem_read(rec, 0x24)),
                                              bytes(uc.mem_read(out, 0x60))))
                        except Exception:
                            pass
                elif rn == "FUN_0005fc04":
                    self.dump_viterbi_nodes()
            name = want.get(address)
            if name is None:
                return
            a0 = uc.reg_read(self.r0)
            a1 = uc.reg_read(self.r1)
            a2 = uc.reg_read(self.r2)
            a3 = uc.reg_read(self.r3)
            if name in ("FUN_00061620", "FUN_000618a8", "FUN_00061804",
                        "FUN_00063350", "FUN_00062718"):
                self.stream_enter(name, a0, a1, a2, a3,
                                  uc.reg_read(R.UC_ARM_REG_LR))
            if name == "FUN_0005ef70":
                self.unit_seq.append(a1)
            elif name == "FUN_0005fc04":
                self.viterbi.append((a1, a2))
            elif name == "FUN_0006706c":
                self.tokens.append(self.item_features(a0))
            elif name == "FUN_00063540":
                self.pitch_calls.append(float_bits(a1))
            elif name == "FUN_00062d14":
                self.time_calls.append(float_bits(a1))
            elif name == "FUN_00062c54":
                self.gain_calls.append(float_bits(a1))
            elif name in ("FUN_00064f38", "FUN_00065028", "FUN_000650b0"):
                self.pipeline_runs.append(name)
            elif name == "FUN_0004ae28":
                self.pump_calls += 1
            elif name == "FUN_00060ed4":
                if len(self.fem) < 400:
                    try:
                        self.fem.append((a0, bytes(uc.mem_read(a1, 0x60))))
                    except Exception:
                        pass
            if self.args.trace_funcs:
                print(f"[trace] {name} r0={a0:#x} r1={a1:#x} r2={a2:#x} r3={a3:#x}")
            if name == "FUN_0005ef00":
                self._ef00_pending = self.lib.cstr(a1).decode("latin1")
            elif name == "FUN_00060ed4":
                self._fem_pending = (a0, a1)
            elif name == "FUN_0005f1dc":
                self._f1dc_pending = (a1, a2)
            elif name == "FUN_0005fc04":
                self._fc04_state = a0
            elif name == "FUN_0004a2d4" and not self._input_seen:
                self._input_seen = True
                self.log("input admission FUN_0004a2d4 text=%r"
                         % self.lib.cstr(a1).decode("latin1"))
            if self.args.ret_probe:
                probe = RET_PROBE.get(address)
                if probe is not None:
                    self._ret_watch[uc.reg_read(R.UC_ARM_REG_LR)] = probe
        self._ret_watch = {}
        self._stream_watch = {}
        self._ret_counts = {}
        self.diphone_lookups = []
        self._ef00_pending = ""
        self._fem_pending = None
        self._f1dc_pending = None
        self._fc04_state = 0
        self._input_seen = False
        self.hooks.append(lib.uc.hook_add(UC_HOOK_CODE, on_code))

        # full function-entry trace (engine dump, optionally the plug-in dump)
        self.entry_trace = []
        self.entry_counts = {}
        for dump, base, label in (
                (self.args.trace_engine_dump, 0, "engine"),
                (self.args.trace_plugin_dump, self.args.plugin_base, "plugin")):
            if not dump:
                continue
            funcs = load_ghidra_funcs(os.path.join(self.args.root, dump))
            funcs = {base + a: f"[{label}] {n}" for a, n in funcs.items()}

            def on_block(uc, address, size2, user, _f=funcs):
                nm = _f.get(address)
                if nm is not None:
                    if nm not in self.entry_counts:
                        self.entry_counts[nm] = 0
                        self.entry_trace.append(nm)
                    self.entry_counts[nm] += 1
            self.hooks.append(lib.uc.hook_add(UC_HOOK_BLOCK, on_block))

    # -- level 1 -----------------------------------------------------------
    def do_init(self):
        lib = self.lib
        cert = open(self.cert, "rb").read()
        self.cert_blob = cert
        p = lib.alloc_data(cert + b"\x00")
        self.engine = lib.call(V_TTS_INIT, [p], timeout=self.timeout)
        self.log(f"tts_init(cert {len(cert)} B) -> engine={self.engine:#x}")
        if not self.engine:
            self.log("BLOCKER: engine init failed: errno=%d msg=%r" % self.errno())
            return False
        return True

    def do_load_voice(self):
        lib = self.lib
        so = lib.alloc_str(self.plugin_so)
        vox = lib.alloc_str(self.obb)
        t0 = time.time()
        self.voice = lib.call(V_TTS_LOAD_VOICE, [self.engine, so, vox],
                              timeout=self.timeout)
        self.log(f"tts_load_voice(engine, {os.path.basename(self.plugin_so)!r}, "
                 f"{os.path.basename(self.obb)!r}) -> voice={self.voice:#x} "
                 f"({time.time()-t0:.2f}s)")
        if not self.voice:
            self.log(f"BLOCKER: load_voice failed: errno={self.errno()[0]} "
                     f"msg={self.errno()[1]!r}")
            return False
        self.sample_rate = lib.call(V_TTS_VOICE_SAMPLE_RATE, [self.voice])
        self.log(f"tts_voice_sample_rate(voice) -> {self.sample_rate} Hz")
        self.find_diphonedb()
        return True

    # -- level 2 -----------------------------------------------------------
    def do_streamer_start(self, text):
        lib = self.lib
        p = lib.alloc_str(text)
        speed = struct.unpack("<I", struct.pack("<f", -1.0))[0]
        self.text = text
        self.streamer = lib.call(V_TTS_STREAMER_START,
                                 [self.voice, p, speed], timeout=self.timeout)
        self.log(f"tts_streamer_start(voice, {text!r}, -1.0f) -> "
                 f"streamer={self.streamer:#x}")
        if not self.streamer:
            self.log(f"BLOCKER: streamer_start failed: errno={self.errno()[0]} "
                     f"msg={self.errno()[1]!r}")
            return False
        return True

    # -- level 3 -----------------------------------------------------------
    def do_synth(self, out_pcm, chunk=None, max_total=None):
        lib = self.lib
        chunk = chunk or max(1, int(0.3 * (self.sample_rate or 22050)))
        buf = lib.alloc(chunk * 2 + 0x1000)
        total = 0
        chunks = []
        t0 = time.time()
        for k in range(self.args.max_chunks):
            n = lib.call(V_TTS_STREAMER_SYNTH0, [self.streamer, buf, chunk],
                         timeout=self.timeout)
            if getattr(lib, "stop_pc", RET_TRAP) != RET_TRAP:
                self.log(f"!! synth0 #{k} emulation stopped abnormally at "
                         f"pc={lib.stop_pc:#x} lr={lib.stop_lr:#x}")
            if n in (0, 0xFFFFFFFF):     # end or error
                self.log(f"tts_streamer_synth0 #{k} -> {n:#x} (0=end, -1=err) "
                         f"errno={self.errno()} errmsg={self.errmsg()!r}")
                break
            data = bytes(lib.uc.mem_read(buf, n * 2))
            chunks.append(data)
            total += n
            if k < 3 or n != chunk:
                self.log(f"tts_streamer_synth0 #{k} -> {n} frames "
                         f"({total} total)")
            if max_total and total >= max_total:
                break
        pcm = b"".join(chunks)
        self.log(f"synth done: {total} frames = {total/(self.sample_rate or 22050):.3f}s "
                 f"in {time.time()-t0:.2f}s")
        if out_pcm:
            with open(out_pcm, "wb") as fh:
                fh.write(pcm)
            write_wav(out_pcm.replace(".pcm", ".wav"), pcm, self.sample_rate)
            self.log(f"wrote {out_pcm} ({len(pcm)} B) + .wav")
        return pcm

    # -- misc --------------------------------------------------------------
    def write_artefacts(self, outdir):
        import io as _io

        def w(name, text):
            with open(os.path.join(outdir, name), "w") as fh:
                fh.write(text)

        w("trace.log", "\n".join(self.trace) + "\n")
        argv = " ".join([os.path.basename(sys.executable)] + [
            (p if p.startswith("-") else
             (os.path.relpath(p, self.args.root) if os.path.isabs(p) else p))
            for p in self.argv[1:]])
        w("cmdline.txt", argv + "\n")

        # --- diphonedb: full unit dictionary with base durations
        if self.ddb:
            buf = ["# diphonedb payload dump (plugin-side, read from guest memory)",
                   "# n_records=%d name=%s checksum=%d" % (
                       self.ddb["n_records"], self.ddb["name"], self.ddb["checksum"]),
                   "# index\tname\tduration_ms"]
            n = self.ddb["n_records"]
            for i in range(min(n, 4096)):
                nm, dur = self.diphone(i)
                buf.append(f"{i}\t{nm}\t{dur}")
            w("diphonedb_names.txt", "\n".join(buf) + "\n")

        # --- selected units (FUN_0005ef70 argument == Viterbi path order).
        # The argument is an index into the voxdb section directory; the unit's
        # diphone name comes from section A/B (build_unit_names).
        if self.unit_seq:
            umap = self.build_unit_names()
            buf = ["# index\tunit_id\tdiphone\tdiphone_idx\tvariant\t"
                   "diphone_dur_ms\tcum_ms\tfrom",
                   "# unit_id = FUN_0005ef70 arg2 (voxdb waveform record index)",
                   "# diphone = section A name of the diphone owning this unit "
                   "(section B inverse)",
                   "# variant = position within that diphone's section-B list"]
            cum = 0
            for i, idx in enumerate(self.unit_seq):
                nm, k, di = umap.get(idx, ("?", -1, -1))
                dur = self.diphone(di)[1] if di >= 0 else 0
                cum += dur
                buf.append(f"{i}\t{idx}\t{nm}\t{di}\t{k}\t{dur}\t{cum}\tvoxdb")
            w("unit_sequence.txt", "\n".join(buf) + "\n")

        # --- diphone (name -> diphoneset_num) binary-search calls made while
        # building the graph: the linguistic diphone chain in pipeline order
        if self.diphone_lookups:
            buf = ["# call#\tdiphone_name\tdiphoneset_num(-1 = not in db)",
                   "# FUN_0005ef00(diphonedb, \"<left>-<right>\")"]
            for i, (nm, r) in enumerate(self.diphone_lookups):
                ri = r - 0x100000000 if r >= 0x80000000 else r
                buf.append(f"{i}\t{nm}\t{ri}")
            w("diphone_lookups.tsv", "\n".join(buf) + "\n")

        # --- voice settings in force for this capture
        if getattr(self, "voice_params", None):
            keys = ("voice_name", "voice_gender", "language_name", "language_code",
                    "eng_version", "eng_input_type", "eng_text_encoding",
                    "sample_rate", "viterbi_beam", "tb_min_distance",
                    "duration_stretch", "pitch_stretch", "amplify", "compress",
                    "eng_max_sentence", "eng_max_word", "eng_sentence_break",
                    "eng_paragraph_break", "pause_base_len")
            buf = ["# voice parameter values in force (read from the plug-in's"
                   " parameter store at runtime)",
                   "# key\tvalue"]
            for k, v in self.voice_params:
                if k in keys:
                    buf.append(f"{k}\t{self.val_decode(v)}")
            buf.append("# driver: sentence=%r level=%d plugin_base=%#x"
                       % (getattr(self, "text", self.args.sentence), self.args.level,
                          self.args.plugin_base))
            buf.append("# engine: tts_streamer_start(voice, text, -1.0f)"
                       " (speed = certificate speed)")
            w("settings.txt", "\n".join(buf) + "\n")

        # --- 96-byte feature vectors (FUN_00060ed4) for the graph nodes
        if self.fem:
            # slot map from report_cost_terms_main.md 4c
            istr = {0x04: "p.p.name", 0x08: "p.name", 0x0c: "p.name(str)",
                    0x10: "n.name", 0x14: "n.n.name", 0x38: "gpos(str)",
                    0x4c: "endtone"}
            buf = ["# 96-byte feature vectors, one row per FUN_00060ed4(item, out) call",
                   "# item\t" + "\t".join("slot%02x" % o for o in sorted(istr)),
                   "# hex\t" + "\t".join(istr[o] for o in sorted(istr))]
            for item, fem in self.fem:
                names = []
                for o in sorted(istr):
                    p = struct.unpack_from("<I", fem, o)[0]
                    s = self._try_cstr(p)
                    names.append(s if s is not None else f"{p:#x}")
                buf.append(f"{item:#x}\t" + "\t".join(names)
                           + f"\t# {fem.hex()}")
            w("unit_feature_vectors.tsv", "\n".join(buf) + "\n")

        # --- candidate lattice: for every diphone of the chain, the section-B
        # candidate unit ids (the Viterbi may pick any of them)
        if self.diphone_lookups:
            rng = self.diphone_ranges() if self.ddb else {}
            sel = {}
            for i, u in enumerate(self.unit_seq):
                sel[i] = u
            buf = ["# position\tdiphone\tdiphone_idx\tcandidates\tb_start\t"
                   "selected_unit\tvariant",
                   "# candidates = number of section-B unit ids of this diphone"]
            umap = self.build_unit_names() if self.ddb else {}
            for i, (nm, r) in enumerate(self.diphone_lookups):
                di = r - 0x100000000 if r >= 0x80000000 else r
                _, start, count, _f, _l = rng.get(di, ("?", 0, 0, 0, 0))
                u = sel.get(i, "")
                var = umap.get(u, ("", -1, -1))[1] if u != "" else ""
                buf.append(f"{i}\t{nm}\t{di}\t{count}\t{start}\t{u}\t{var}")
            w("candidate_lattice.txt", "\n".join(buf) + "\n")

        # --- candidate side of the target cost: every FUN_0005f1dc call
        # (36-byte section-C record -> 96-byte feature vector)
        if self.f1dc:
            buf = ["# call#\trecord_C_hex\tfeature_vector_hex",
                   "# FUN_0005f1dc(diphonedb, section-C record, out96): the two"
                   " calls per Viterbi pair are (p-side, n-side)"]
            for i, (rec, fem) in enumerate(self.f1dc):
                buf.append(f"{i}\t{rec.hex()}\t{fem.hex()}")
            w("candidate_records.tsv", "\n".join(buf) + "\n")

        # --- the engine's own per-candidate costs after FUN_0005fc04
        if self.viterbi_nodes:
            buf = ["# node\tk\ttarget_cost(+0)\ttotal(+8)\tdiphone_idx(+0xc)",
                   "# state[4] + node*0xd4, +0xcc ptr / +0xd0 count, 20-byte entries"]
            for node, ents in self.viterbi_nodes:
                for k, (c0, c8, didx) in enumerate(ents):
                    buf.append(f"{node}\t{k}\t{c0}\t{c8}\t{didx}")
            w("viterbi_candidates.tsv", "\n".join(buf) + "\n")

        # --- Viterbi invocations
        if self.viterbi:
            buf = ["# call#\tr1\tr2",
                   "# FUN_0005fc04(graph, viterbi_beam) entry registers"]
            for i, (a0, a1) in enumerate(self.viterbi):
                buf.append(f"{i}\t{a0:#x}\t{a1}")
            w("viterbi_calls.txt", "\n".join(buf) + "\n")

        # --- token stream
        if self.tokens:
            keys = ["name", "text", "phones", "xsampa", "silence", "punc",
                    "start_pos", "end_pos", "duration_stretch", "pitch_stretch",
                    "amplify", "interpret-as", "whitespace", "prepunctuation"]
            extra = sorted({k for t in self.tokens for k in t if k not in keys})
            cols = keys + extra
            buf = ["# token stream: FUN_0006706c(item) entry, all item features",
                   "# (VAL decoded: str:/int:/flt:)",
                   "# idx\t" + "\t".join(cols)]
            for i, t in enumerate(self.tokens):
                buf.append(f"{i}\t" + "\t".join(str(t.get(c, "")) for c in cols))
            w("token_stream.tsv", "\n".join(buf) + "\n")

        # --- prosody transforms actually applied to the waveform
        if self.pitch_calls or self.time_calls or self.gain_calls:
            buf = ["# per-segment prosody transforms (waveform stage)",
                   "# FUN_00063540 pitch_stretch, FUN_00062d14 duration_stretch,",
                   "# FUN_00062c54 amplify -- argument r1 (token*voice factor)"]
            for i, v in enumerate(self.pitch_calls):
                buf.append(f"pitch\t{i}\t{v:.9g}")
            for i, v in enumerate(self.time_calls):
                buf.append(f"time\t{i}\t{v:.9g}")
            for i, v in enumerate(self.gain_calls):
                buf.append(f"gain\t{i}\t{v:.9g}")
            w("prosody_transforms.tsv", "\n".join(buf) + "\n")

        if self.pipeline_runs or self.pump_calls:
            w("pipeline_calls.txt",
              "# stage-pipeline runner invocations (FUN_00064f38/65028/650b0)\n" +
              "\n".join(self.pipeline_runs) +
              f"\n# FUN_0004ae28 (pump) calls: {self.pump_calls}\n")

        if self.stream_log:
            w("stream_trace.txt",
              "# streamer waveform-assembly trace\n"
              "# splice = FUN_00061620(streamer, unit_obj, flag);"
              " finalize = FUN_000618a8(streamer, want, events);\n"
              "# pad = FUN_00061804(streamer, buf, n);"
              " trim = FUN_00063350/62718 (pau silence padding/trimming)\n" +
              "\n".join(self.stream_log) + "\n")

        if self.entry_trace:
            buf = ["# function-entry trace (first entry order, then hit counts)",
                   "# count\tfunction"]
            for nm in self.entry_trace:
                buf.append(f"{self.entry_counts[nm]}\t{nm}")
            w("front_end_trace.txt", "\n".join(buf) + "\n")

    def errno(self):
        lib = self.lib
        code = lib.call(V_TTS_ERRNO, [])
        msgp = lib.call(V_TTS_ERRMSG, [])
        msg = lib.cstr(msgp).decode("latin1") if msgp else ""
        return code, msg

    def errmsg(self):
        lib = self.lib
        msgp = lib.call(V_TTS_ERRMSG, [])
        return lib.cstr(msgp).decode("latin1") if msgp else ""

    @property
    def timeout(self):
        return 0 if not self.args.timeout else self.args.timeout * 1000000


def write_wav(path, pcm, rate):
    rate = rate or 22050
    n = len(pcm)
    with open(path, "wb") as fh:
        fh.write(b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt ")
        fh.write(struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16))
        fh.write(b"data" + struct.pack("<I", n) + pcm)


# ---------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    ap.add_argument("--engine", default="out/libs/kendra/libttsivonavoice.so")
    ap.add_argument("--plugin", default="out/libs/kendra/libvoice_en_us_kendra.so")
    ap.add_argument("--cert", default="out/certs/ivona_certificate_decoded.txt")
    ap.add_argument("--obb", default="IVONA 2/IVONA Kendra US English "
                   "beta_v1.6.23.422_apkfab.com/Android/obb/"
                   "com.ivona.tts.voicebeta.eng.usa.kendra/"
                   "main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb")
    ap.add_argument("--dat-dir", default="out/obb",
                    help="IVONA_LANG_DAT_DIR (lang_*.dat root)")
    ap.add_argument("--fs-root", default=None,
                    help="prefix prepended to absolute guest paths")
    ap.add_argument("--plugin-base", type=lambda s: int(s, 0), default=0x20000000)
    ap.add_argument("--sentence", default="Hello world, this is a test.")
    ap.add_argument("--ssml", default=None,
                    help="also run this application/ssml+xml input")
    ap.add_argument("--out-dir", default="out/oracle")
    ap.add_argument("--level", type=int, default=3,
                    help="stop after this level (1=init+voice, 2=start, 3=pcm)")
    ap.add_argument("--max-chunks", type=int, default=400)
    ap.add_argument("--trace-funcs", action="store_true",
                    help="print every instrumented pipeline entry")
    ap.add_argument("--ret-probe", action="store_true",
                    help="log the return value of the control-flow functions")
    ap.add_argument("--stream-probe", action="store_true",
                    help="log the streamer state around every splice/finalize/pad "
                         "call (FUN_00061620/618a8/61804/63350/62718)")
    ap.add_argument("--trace-dumps", action="store_true",
                    help="record the full function-entry trace of both libraries")
    ap.add_argument("--trace-engine-dump",
                    default="out/ghidra_dump/libttsivonavoice.c")
    ap.add_argument("--trace-plugin-dump",
                    default="out/ghidra_dump/libvoice_kendra.c")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--trace-filter", default=None,
                    help="regex; only imported calls matching are traced")
    ap.add_argument("--heap-size", type=lambda s: int(s, 0), default=0x10000000)
    ap.add_argument("--trace-alloc", type=lambda s: int(s, 0), default=0,
                    help="log every guest allocation >= N bytes")
    ap.add_argument("--deterministic", action="store_true", default=True)
    ap.add_argument("--timeout", type=int, default=0,
                    help="seconds of emulated wall clock per call (0=unlimited)")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--no-pcm", action="store_true")
    args = ap.parse_args(argv)

    os.makedirs(os.path.join(args.root, args.out_dir), exist_ok=True)
    if not args.trace_dumps:
        args.trace_engine_dump = None
        args.trace_plugin_dump = None
    armemu.HEAP_SIZE = args.heap_size
    o = Oracle(args)
    o.setup_module()
    if args.trace:
        o.lib.set_trace(True, args.trace_filter)
    o.install_hooks()

    ok = o.do_init() and o.do_load_voice()
    if ok and args.level >= 2:
        ok = o.do_streamer_start(args.sentence)
    pcm = b""
    if ok and args.level >= 3 and not args.no_pcm:
        pcm = o.do_synth(os.path.join(args.root, args.out_dir, "kendra_hello.pcm"))

    # ---- capture
    outdir = os.path.join(args.root, args.out_dir)
    o.write_artefacts(outdir)
    if o.lib.unknown_calls:
        print("[stub ] unhandled: " +
              ", ".join(f"{k}x{v}" for k, v in o.lib.unknown_calls.most_common()))
    print(f"[oracle] reached level {'3' if pcm else ('2' if ok else '1')}; "
          f"artefacts in {outdir}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
