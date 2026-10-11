# `emu/` — ARM32 (bionic) shared-library emulation harness

Runs **real, unmodified Android ARM `.so` code** under Unicorn: the library is
mapped at its link-time addresses, its relocations are applied, and every
imported libc/bionic symbol is replaced by a Python stub.  Inside-the-library
code executes natively (including its statically linked OpenSSL subset), so
anything reached from a callable entry point can be driven and observed.

```
emu/armemu.py      ArmLib -- ELF loader, relocations, libc/syscall stubs, call()
emu/run.py         generic CLI: call one function, pass args, dump memory
emu/probe_gap.py   domain driver: CDXV container -> diphonedb -> unit decode
emu/evidence/      captured runs (see report_emulation.md)
```

Requires the venv at `~/venvs/re` (unicorn 2.1.4 + pyelftools):

```sh
~/venvs/re/bin/python emu/run.py --lib … --func … 
```

## 1. Quick start

**Decrypt an `ISEF` lexicon container** (`FUN_000346d4`, Ghidra address; the
guest path is opened on the host filesystem):

```sh
~/venvs/re/bin/python emu/run.py \
  --lib out/libs/kendra/libttsivonavoice.so \
  --func FUN_000346d4 \
  --arg str:out/obb/lang_en_us.dat \
  --out '[r0+0x1c]:[r0+0x14]:out/obb/lang_en_us.emu.bin' \
  --verify out/obb/lang_en_us.dec.bin
```

`--out` takes two expressions: the buffer address (`struct[7]`) and the length
(`struct[5]`) from the returned handle, then compares with `--verify`.

**Verify a certificate of authenticity** (`tts_init` = `tts_create` +
`tts_load_certificate`; the argument is the decoded certificate text):

```sh
~/venvs/re/bin/python emu/run.py \
  --lib out/libs/kendra/libttsivonavoice.so \
  --func tts_init --arg filez:out/certs/ivona_certificate_decoded.txt
```

`r0` = the engine pointer on success; on rejection `r0 = 0` and the engine's
diagnostic is at `0x186010` (`--str 0x186010`).

**Decode an acoustic unit out of the 152 MB voice OBB** (real reader chain:
`FUN_0005f49c` container parse → `FUN_0005f064` diphonedb + codec init →
`FUN_0005ef70` directory read + decode):

```sh
~/venvs/re/bin/python emu/probe_gap.py \
  --obb "IVONA 2/…/main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb" \
  --index 0 --count 3 --trace-funcs out/ghidra_dump/libttsivonavoice.c \
  --dump-pcm /tmp/unit_%d.pcm
```

## 2. `run.py` reference

| flag | meaning |
|---|---|
| `--lib PATH` | ARM/Thumb `.so` to load |
| `--func SPEC` | `0xVADDR`, `FUN_000346d4`/`LAB_…` (Ghidra addr, i.e. `vaddr + 0x10000`), `tts_init` (export name) |
| `--ghidra` | force Ghidra-address interpretation of a bare hex `--func` |
| `--arg SPEC` | repeatable; `str:TEXT`, `file:PATH`, `filez:PATH` (+NUL), `hex:AABB`, or an expression (raw integer) |
| `--stdin FILE` | map FILE into guest memory as `@stdin` (auto-arg0 if no `--arg`) |
| `--out A:L[:PATH]` | dump guest memory after the call |
| `--verify FILE` | compare the concatenated `--out` dumps with FILE |
| `--root DIR` | `chdir` first; used as the prefix for absolute guest paths |
| `--env K=V` | guest `getenv()` table |
| `--stdout FILE` | capture guest stdout instead of printing it |
| `--trace [REGEX]` | log every imported call (+return), optionally filtered |
| `--trace-funcs DUMP.c` | Ghidra dump → print each named function on first entry |
| `--shadow A:L` | log guest reads/writes touching `[A, A+L)` with the PC |
| `--words EXPR:N` / `--str EXPR` / `--peek EXPR` | post-call memory inspection |
| `--timeout S` | wall-clock budget in **seconds** (0 = unlimited) |
| `--count N` | instruction budget (0 = unlimited) |
| `--list-exports` / `--list-imports` | discover callable/needed symbols |

### Expressions

Used by `--arg`, `--out`, `--words`, `--str`, `--peek`:

```
123 0x1f        integers            r0 … r12 sp lr pc   registers
@stdin @heap    bound buffers       [EXPR]              u32 dereference
+ - *  ( )      arithmetic
```

## 3. `armemu.ArmLib` API

```python
lib = ArmLib("x.so")            # map, relocate, install stubs
lib.call(addr, [args], timeout=0, count=0)     # timeout in MICROSECONDS
lib.alloc(data) / alloc_str(s) / alloc_data(b) # guest heap (never freed)
lib.rd/wr/u32/s32/w32/w16/cstr/putstr          # memory helpers
lib.add_import("name", fn)      # fn(uc, [r0,r1,r2,r3]) -> r0
lib.set_trace(True, only="malloc|free")        # wrap all import callbacks
lib.unknown_calls               # Counter of silently-stubbed imports
lib.find_bytes(b"…") / dump(addr, n, path) / read_struct(addr, words)
```

Stubs provided: malloc/calloc/realloc/free, mem*/str*, printf family (incl.
`vsnprintf` with a real `va_list`), `sscanf` (AAPCS varargs), stdio `fopen`
(host filesystem!), `read`/`fwrite`/`fseek`/`ftell`/`fstat`/`stat`, `open`/
`read`/`write`/`lseek`/`mmap`/`munmap`/`close`, `sigsetjmp`/`siglongjmp`,
`getenv`, `qsort` (**fails loudly**, see below), math (`pow/exp/floor/ceil/
fmod/sqrt`), `time`/`gettimeofday`/`clock_gettime`, pthread mutex/TLS no-ops,
iOS/Android log + `__android_log_vprint`, `__stack_chk_guard`, `_ctype_`,
`__page_size`, `__sF`, sockets/semaphores/dlopen as no-ops.

Unimplemented imports are logged on first use as `[stub] name(args) -> 0` and
counted in `lib.unknown_calls`, so a silent 0 can never be mistaken for
success.

## 4. Pitfalls (all hit for real while building this)

* **`timeout` is microseconds.** `timeout=600` (what looks like 10 minutes)
  truncates the run after a few hundred instructions with no error message —
  the symptom is `r0` unchanged and `pc` parked inside `.text` or a stub.
  Use `0` for unlimited (`run.py --timeout` converts seconds → µs).
* **Unicorn ≥ 2.1.4 leaks `pc` from the CPU state**: do not `reg_write(PC, x)`
  before `emu_start(x, …)`, and do not add a second *unrestricted*
  `UC_HOOK_CODE` hook — either can make `emu_start` execute one instruction and
  return.  `--trace-funcs` uses `UC_HOOK_BLOCK`, which is safe.
* **`alloc_str` must NUL-terminate** (it did not in the first version).  The
  failure mode is vicious: the next heap allocation overwrites the terminator
  and the guest sees `"/path/to/x.obb a"`, so `fopen` simply returns 0.
* **AAPCS varargs**: `sscanf(char*, fmt, ...)` receives its variadic arguments
  in `r2/r3` then on the stack — *not* as a `va_list` pointer.  Only
  `vsprintf`/`vsnprintf`/`vfprintf` get a real `va_list`.
* **Arguments 5..n are on the stack** — use `armemu.arm_arg(uc, i)`.
* Ghidra addresses in `out/ghidra_dump/*.c` are `vaddr + 0x10000`.

## 5. Known gaps

* `qsort` needs a re-entrant call back into emulated code, which Unicorn
  forbids from inside a hook; the stub raises `EmuError` rather than returning
  a wrong order.  (`libvoice_*.so` uses it to sort the 1601-entry diphone table.)
* C++ exception unwinding (`__cxa_*`, `__gnu_Unwind_Find_exidx`) is stubbed, so
  the C++ voice plug-ins only run as long as nothing throws.
* pthreads are no-ops: single-threaded execution only.
* Guest `mmap` allocates from a 64 MiB emulated heap, so very large mappings
  (the whole 152 MB OBB) are not representable — the library itself only maps
  the 25 MB header region and reads payloads with `fseek`/`fread`, which the
  host-file stdio stubs serve exactly.
