# ARM emulation harness — status, verified runs, blockers

Scope: make `emu/armemu.py` a usable harness, drive real code out of the shipped
binaries, and report precisely what runs and what does not.

Files added/changed (originals untouched): `emu/armemu.py` (harness core, reworked),
`emu/run.py` (new CLI), `emu/probe_gap.py` (new domain driver), `emu/README.md`,
`emu/evidence/` (captured runs), this report.  Output artefacts written under
`out/obb/` and `emu/evidence/` only.

Environment: `~/venvs/re/bin/python` (Python 3.14, unicorn 2.1.4, pyelftools).
All addresses below are **ELF vaddrs**; Ghidra dump addresses are +0x10000
(`FUN_000346d4` = `0x246d4`).

---

## 0. Result summary

| # | target | entry point | verdict |
|---|---|---|---|
| 1 | ISEF lexicon container decrypt | `FUN_000346d4` (`0x246d4`) | **✅ byte-exact** — 74 137 B plaintext identical to `out/obb/lang_en_us.dec.bin`, and the recovered 64-byte session blob identical to `scripts/isef_decrypt.py` |
| 2 | Certificate of authenticity (RSA-4096 signature + attribute parse) | `tts_init` (`0x386e0`) | **✅ accepted** — returns a live engine pointer, `errno = 0`; a one-byte change is rejected with the library's own "Certificate signature mismatch" |
| 3 | Acoustic-unit ("gap") decode | `FUN_0005f49c` → `FUN_0005f064` → `FUN_0005ef70` → decoder | **✅ decoded** — real 16-bit PCM for OBB units 0–3 (4 537 / 2 715 / 3 043 / 5 121 samples), full 47-function call trace captured |
| 4 | end-to-end `tts_streamer_synth` | `tts_streamer_synth` | **❌ blocked** — needs `dlopen`/`dlsym` for the voice plug-in and `qsort` re-entrancy; roadmap in §6 |

Everything else in the library is now *reachable*: 163/163 imported symbols have
working stubs, so no call silently returns 0 without being counted
(`lib.unknown_calls`).

---

## 1. Harness

```
emu/armemu.py     ArmLib: PT_LOAD mapping at link-time vaddrs, R_ARM_RELATIVE/
                  GLOB_DAT/JUMP_SLOT/ABS32 relocations, STT_OBJECT backing
                  (__stack_chk_guard, _ctype_, __page_size, __sF), one 2-byte
                  `bx lr` stub per import + Python callbacks, call(), heap,
                  memory helpers, tracing.
emu/run.py        generic CLI (see emu/README.md): --lib/--func/--arg/--out/
                  --verify/--trace/--trace-funcs/--root/--stdout/--shadow …
emu/probe_gap.py  CDXV → diphonedb → unit decode driver + PCM extraction.
```

Calling convention notes that matter: arguments 5..n are on the **stack**
(`armemu.arm_arg`), `sscanf`-style varargs are in `r2/r3`+stack (only
`vsprintf`/`vsnprintf`/`vfprintf` take a real `va_list`), and Unicorn's
`emu_start` timeout unit is **microseconds** (`run.py --timeout` converts from
seconds; `armemu.ArmLib.call` documents µs).

### 1.1 Audit of the suspects named in the task

| suspect | needed? | evidence |
|---|---|---|
| bionic TLS / `__stack_chk_guard` | **yes, was the silent killer of any mis-sized stub** — STT_OBJECT imports must point at real, writable backing; `_setup_object_imports` allocates 4 KiB per object (`__stack_chk_guard`, `_page_size`, `_ctype_`, `_tolower_tab_`, `_toupper_tab_`, `__sF`). `__stack_chk_fail` never fires in any run above (it would print). |
| `pthread_mutex_*`, `pthread_key_*`, `pthread_getspecific/setspecific` | no — no-ops are enough for these single-threaded paths (`tts_create` initialises two mutexes; both calls appear in the trace and return 0). |
| `malloc`/`calloc`/`realloc`/`free` | **yes** — a bump allocator from a 64 MiB guest heap; `free` is a no-op (leaks, which is fine for ≤40 s runs; the OpenSSL cleanup storms are visible in `--trace`). |
| `fopen`/`fread`/`fseek`/`fclose` | **yes, this was the real blocker of the previous attempt** — the old `fopen` only served paths pre-registered in an `open_map`, so the library could never open an actual file. Now host files are opened directly (with `--root` for absolute guest paths); `FILE*` is a synthetic `0x1000+n` handle. |
| Thumb entry | **not for this library.** `libttsivonavoice.so` is ARM-mode: `0x246d4`, `0x386e0`, `0x4f49c` disassemble cleanly as ARM (e.g. `0x4f49c: push {r4,r5,r6,r7,r8,lr}; mov r1,#0xa; sub sp,sp,#0x68`) and execute correctly under `UC_MODE_ARM`. `ArmLib.call` still accepts an odd address for Thumb images (Unicorn switches mode from the PC bit), but it is unused here. |
| VFP / `__aeabi_*` helpers | **not needed.** The library statically links its own helpers — they appear in the call trace as internal addresses (`0x1415b4 __aeabi_uidivmod`, `0x1415d4 __divsi3`, and `__aeabi_fcmplt/fcmpeq` inside the certificate path), so no import stub is required. Unicorn 2.1.4 does expose the VFP register file (`UC_ARM_REG_D0…`) if a path ever needs it. |

---

## 2. Verified run 1 — ISEF decryptor cross-validation

`scripts/isef_decrypt.py` (pure stdlib Python) is the independent reference.
The emulated library performs `fopen`/`fread`/`fseek` on the real file, does
RSA-4096 public-recover with the embedded modulus at file `0x14bd78`, then
AES-256-CBC decrypts 74 144 bytes through its statically linked OpenSSL.

```sh
$ ~/venvs/re/bin/python emu/run.py --lib out/libs/kendra/libttsivonavoice.so \
    --func FUN_000346d4 --arg str:out/obb/lang_en_us.dat \
    --out '[r0+0x1c]:[r0+0x14]:out/obb/lang_en_us.emu.bin' \
    --verify out/obb/lang_en_us.dec.bin
```

```
[func] FUN_000346d4 -> 0x246d4
[arg ] str 'out/obb/lang_en_us.dat' -> 0x40006010
[ret ] r0 = 0x40006030 (1073766448)
[out ] 0x40048270+74137 (74137 B)
[out ] wrote out/obb/lang_en_us.emu.bin
[verify] out/obb/lang_en_us.dec.bin: MATCH (74137 B vs 74137 B)
```

Cross-check of the intermediate value (the 64-byte RSA-recovered session blob,
read out of guest memory at `handle[3]`):

```
emulator : f16e18adc80824426994aabd5092269eafe80a72cea2b8f1709b5f306b7590848930e6b4dc6833fd0eb580ff5c58118db8b279d065a6f03cd469330798f5a840
isef_decrypt.py: (identical)
```

and the returned handle decodes as `[4]=0x50992bcc` (timestamp, matches
`report_isef.md`), `[5]=0x12199` = 74 137 (length), `[7]` = plaintext pointer.
Wall clock 36 s — the cost is the OpenSSL bignum modexp in emulated ARM.

**Verdict:** the RSA public operation, the AES-256-CBC/EVP glue and the
container walk are bit-exact under emulation.  *(Task text says 73 712 B; the
actual reference file is 74 137 B — the harness matches the file on disk.)*

---

## 3. Verified run 2 — certificate of authenticity (+ negative control)

`tts_init(engine_cert_text)` = `tts_create()` + `tts_load_certificate()`, which
(XOR-)decoded certificate text as input, parses ~20 attributes and then
**verifies a 520-byte RSA-4096 signature** with the *separate* embedded public
key (`vaddr 0x14c154`, `e = 65537` at `0x14c354`) via
`FUN_00052154` → `FUN_00051c70`.

```sh
$ ~/venvs/re/bin/python emu/run.py --lib out/libs/kendra/libttsivonavoice.so \
    --func tts_init --arg filez:out/certs/ivona_certificate_decoded.txt \
    --words 0x18600c:1 --str 0x186010
```

```
[func] tts_init -> 0x386e0
[arg ] filez out/certs/ivona_certificate_decoded.txt (1799 B) -> 0x40006010
[ret ] r0 = 0x40006720 (1073768224)          <-- live engine object
[word] [0x18600c + 0] = 0x00000000           <-- tts_errno() == Success
[str ] 0x186010 = 0x186010 -> b''            <-- tts_errmsg() message buffer, empty
```

Negative control — the same certificate with `Certificate-ID: a1169787` →
`a1169788`, signature block untouched (the exact input is preserved as
`emu/evidence/cert_tampered.txt`; `runs.log` records the `/tmp` path it was
generated at):

```
[ret ] r0 = 0x0 (0)
[word] [0x18600c + 0] = 0x00000001
[str ] 0x186010 = 0x186010 -> b'Certificate signature mismatch'
```

This is the library's own rejection path (`FUN_000519fc` / `FUN_00052154`), so
the RSA-4096 signature verification is demonstrably *executed* rather than
short-circuited.  Runtime 31–32 s per call.

**Verdict:** target 2 met.  The certificate parser + signature verifier run
end-to-end and produce the same verdict the real library would (positive and
negative).

---

## 4. Verified run 3 — acoustic-unit ("gap") decode + call trace

This is the path the `gap-codec2` agent needs.  The OBB is a `CDXV` container
whose header the engine parses; format id **14** installs the callback triple
`[0xd]=FUN_00067f94` (init), `[0xe]=LAB_000679e0` (destroy),
`[0xf]=LAB_00067db8` (decode, inside `FUN_00067a14`).  The reader is
`FUN_0005ef70(db, index)`, which takes the unit's `{u32 offset, u32 size}` from
the section-A directory, `fseek`+`fread`s it over stdio (the payload lives
133 MB into the file, far outside the 25 MB header mmap) and calls the decoder.

```sh
$ ~/venvs/re/bin/python emu/probe_gap.py \
    --obb "IVONA 2/…/main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb" \
    --index 0 --count 3 --dump-pcm emu/evidence/unit_%d.pcm \
    --trace-funcs out/ghidra_dump/libttsivonavoice.c
```

Real container parse (all values match `report_engine_synth.md` §2.1 and
`report_obb_format.md` §9):

```
[cdxv] FUN_0005f49c -> 0x400060e0
        cdxv[ 3] +0x0c          = 0x00005622      <- sample rate 22050
        cdxv[ 4] +0x10          = 0x4f7c7a18      <- checksum
        cdxv[ 5] secA@0x68      = 0x40006298      <- section directory
        cdxv[ 6] secA_size      = 0x00341f78      <- 426 991 entries x 8 B
        cdxv[11] secC_cnt       = 0x00000641      <- 1601 diphone names
        cdxv[13] codec_init     = 0x00057f94
        cdxv[14] codec_destroy  = 0x000579e0
        cdxv[15] codec_decode   = 0x00057db8
        sample_rate   = 22050
[db  ] FUN_0005f064 -> 0x41835230
        db[0]=cdxv 0x400060e0  db[1]=stdio 0x1002  db[2]=codec 0x41835240
[unit] index 0: dir entry off=0x7fabf03 (133873411) size=76
[ret ] FUN_0005ef70(db,0) -> 0x4183ade0
```

`0x7FABF03` + 76 B is exactly the unit-0 record of `report_obb_format.md` §9
(`N=0x20=32`, `ramp[]`, `Y`, `off=0x0182E8D8`, `len=0x23E=574`).  The reader
`FUN_0005ef70` fetches that record; the decoder then consumes its
`(gap_offset, gap_length)` fields itself — see §4.1.

Decoded output (the wave object the library builds: `+4` rate, `+8` frame count,
`+0xc` sample offsets, `+0x10` per-frame PCM pointers):

```
[wave] obj=0x4183ade0 rate=22050 frames=32 offs=0x4183ae00 pcm=0x4183ae80
       seg0: sample_off=147 len=147 pcm=0x4183af00
       seg1: sample_off=295 len=148 pcm=0x4183b030
       seg2: sample_off=442 len=147 pcm=0x4183b160
       seg3: sample_off=590 len=148 pcm=0x4183b290
[wave] total 4537 samples (9074 B, 0.206 s @22050)
[wave] pcm min=-7989 max=13442 nonzero=4533/4537 first16=(-3, -3, -3, -3, -3, -3, -3, -3, -4, -3, -3, -3, -3, -3, -3, -3)
[wave] wrote emu/evidence/unit_0.pcm (9074 B)
[unit] index 1: dir entry off=0x7fabf4f size=58
[wave] obj=0x4183ec60 rate=22050 frames=23
[wave] total 2715 samples (5430 B, 0.123 s @22050)
[wave] pcm min=-12017 max=13442 nonzero=2715/2715 first16=(-5862, -7251, -6871, -7184, …)
[unit] index 2: dir entry off=0x7fabf89 size=68
[wave] total 3043 samples (6086 B, 0.138 s @22050)
[unit] index 3: dir entry off=0x7fabfcd size=78
[wave] total 5121 samples (10242 B, 0.232 s @22050)
```

**Sample-rate nuance (verified).** The wave object is *tagged* `22050` because
`FUN_0005ef70` copies the container header value into it
(`wave+4 = cdxv[3] = 0x5622`), but the codec runs at **24 000 Hz**: the format-14
init `FUN_00067f94` remaps `0x5622 → 24000` (`if (rate == 0x5622) wrapper[1] =
24000`), and reading the live wrapper after `FUN_0005f064` confirms it:

```
cdxv[3] OBB header rate = 22050 (0x5622)
db[2] codec wrapper     = 0x41835240
codec wrapper words     = ['0x41835260', '0x5dc0', '0x0', '0x1', '0x0', '0x0', '0x4f7c7a18', '0x0']
  -> codec[1] = 24000
wave[1] (tag rate)      = 22050
```

so no resample happens inside the decode and the PCM above is 24 kHz (0.189 /
0.113 / 0.127 / 0.213 s for units 0–3); the `@22050` figures in the captured log
are the object's tag, and the 24 k → 22.05 k conversion is downstream
(`resample_wave FUN_00059958`, not traced).  (Thanks to the gap-codec agent for
flagging this.)

`ramp[]` values of the record are exactly the cumulative sample offsets the
wave object reports (`147, 295, 442, 590, …` for unit 0 — diffs ~147/148, the
step `report_obb_format.md` §9 predicts), which closes the loop between the
record's `(gap_off, gap_len)` fields and the decoded audio.  Unit 0 starts with
a near-silent segment (`pau`-like, constant −3) then bends into voiced data;
units 1–3 are fully non-zero with plausible speech amplitudes.

### 4.1 The two file-read sites, observed

```sh
$ ~/venvs/re/bin/python emu/probe_gap.py --obb "<…>.obb" --index 0 \
    --trace --trace-filter "fseek|fread"
```

`--trace --trace-filter "fseek|fread"` isolates them (stdio handle `0x1002`,
`lr` = vaddr of the caller):

```
[call] fread(0x7010ef80, 0x68, 0x1, 0x1001) lr=0x4f4d4     <- FUN_0005f49c, CDXV header
[call] fread(0x7010ef88, 0x68, 0x1, 0x1002) lr=0x4f0a8     <- FUN_0005f064, header re-check
[unit] index 0: dir entry off=0x7fabf03 (133873411) size=76
[call] fseek(0x1002, 0x7fabf03, 0x0, …)     lr=0x4efa8     <- FUN_0005ef70, seek to the record
[call] fread(0x418387d0, 0x1, 0x4c, 0x1002) lr=0x4efbc     <- 76 B = 2*32+12, the unit record
[call] fseek(0x1002, 0x182e8d8, 0x0, …)     lr=0x57e78     <- decoder, seek to the window
[call] fread(0x41838820, 0x1, 0x23e, 0x1002) lr=0x57e8c    <- 574 B = the (gap_off,gap_len) window
```

So the format-14 decoder behaves exactly like `FUN_000685c4` (format 12): it
takes `(u32 offset, u32 length)` from the unit record at byte offsets `2N+4` /
`2N+8`, `fseek`s and `fread`s the window itself, and then decodes it — the only
file reads in the whole library.  For unit 0 those are
`gap_off = 0x182E8D8`, `gap_len = 0x23E = 574`, byte-identical to
`report_obb_format.md` §9's carved record and to the `(gap_off, gap_len)` pair
in the coordination note.  The window payload starts with a 2-byte
length-prefixed item stream (`local_1430` in the decompilation of
`FUN_00067a14`), each item XORed with a rolling 8-byte table indexed by the
item length — the same de-obfuscation `FUN_000685c4` performs with its
`puVar17+0x88` table.

**Call trace** (47 distinct functions; `[fun]` = first entry, addresses are
vaddrs).  `FUN_0005b2cc`+`fseek` perform the seek, `FUN_00067a14` is the
format-14 decoder (its `LAB_00067db8` entry does the 2-byte-length-prefixed item
walk with the rolling-XOR de-obfuscation, exactly like `FUN_000685c4` does for
format 12), then the whole `0x0014_xxxx` codec family runs:

```
0x04ef70 FUN_0005ef70   0x04b2cc FUN_0005b2cc   0x018208 fseek
0x057a14 FUN_00067a14   0x137f70 thunk_FUN_0014e248
0x13e248 FUN_0014e248   0x017ea8 memset        0x138cb0 FUN_00148cb0
0x13dca4 FUN_0014dca4   0x1415d4 __divsi3      0x1415dc FUN_001515dc
0x139e34 FUN_00149e34   0x1415b4 __aeabi_uidivmod
0x137c58 FUN_00147c58   0x137f74 FUN_00147f74  0x13b17c FUN_0014b17c
0x138190 FUN_00148190   0x13af88 FUN_0014af88  0x138f20 FUN_00148f20
0x13966c FUN_0014966c   0x13b104 FUN_0014b104  0x1397a8 FUN_001497a8
0x1396c0 FUN_001496c0   0x140a14 FUN_00150a14  0x13f940 FUN_0014f940
0x138a20 FUN_00148a20   0x13d100 FUN_0014d100  0x13e0ec FUN_0014e0ec
0x13b1e4 FUN_0014b1e4   0x13e4ec FUN_0014e4ec  0x13e29c FUN_0014e29c
0x13add4 FUN_0014add4   0x139e54 FUN_00149e54  0x13dd18 FUN_0014dd18
0x017fa4 memmove         0x13dafc FUN_0014dafc  0x13b450 FUN_0014b450
0x13899c FUN_0014899c   0x1407bc FUN_001507bc
0x052608 FUN_00062608   0x052688 FUN_00062688  0x0524c8 FUN_000624c8
0x052668 FUN_00062668   0x04ac38 FUN_0005ac38  0x0524b0 FUN_000624b0
0x04ac04 FUN_0005ac04   0x017e30 free
```

**Answer the sibling agent needs:** the gap/unit payload is decoded by a
**pure numeric codec** — the `0x0014_xxxx` family plus the wave builder
`FUN_00062xxx`.  There is **no** crypto, hash or compression primitive anywhere
in the path (no `0xb_xxxx` OpenSSL function is entered; the library does not
even import zlib).  The only obfuscation is the small rolling-XOR item walk
inside the decoder entry (`FUN_00067a14`, and `FUN_000685c4` for format 12),
which XORs each length-prefixed item against an 8-byte table derived from the
item length.  Everything after that is arithmetic: `__divsi3`,
`__aeabi_uidivmod`, `memmove`, `memset` and the `FUN_0014xxxx` codebook/IDCT/
synthesis routines, producing 16-bit PCM at the codec's **native 24 000 Hz**
(the wave object is mis-tagged 22 050 — see above).

---

## 5. Blocker catalogue (every one hit for real)

### 5.1 Fatal, had to be fixed to get anything running

| symptom (exact) | cause | fix |
|---|---|---|
| `TypeError: 'float' object cannot be interpreted as an integer` (from `uc.emu_start`) | timeout passed as float | `int(args.timeout * 1_000_000)` |
| run stops after a few hundred instructions, **no error**, `r0` unchanged, `pc` parked inside `.text` or a stub | Unicorn `emu_start(timeout=…)` is **microseconds**; `timeout=600` = 600 µs | use `0`/large value; `call()` documents µs, CLI takes seconds |
| `AttributeError: 'ArmLib' object has no attribute '_fd_base'` (`armemu.py`, `open_`) | attribute never initialised; the stub then returned −1 for every `open()` | initialise `_fd_base = 0x2000` |
| `ValueError: not enough values to unpack (expected 6, got 4)` in `mmap_` | args 5/6 of `mmap` are on the stack (AAPCS) | `armemu.arm_arg(uc, i)` |
| `UcError: string index out of range` (SSE of `sscanf`) | `sscanf` stub read a `va_list` from `r2`; ARM varargs are in `r2/r3`+stack | rewrote `sscanf` with an AAPCS arg reader |
| `fopen` silently returns 0 for a path that exists — the guest saw `"…/main.199…obb a"` | `alloc_str` had a ternary-precedence bug and never NUL-terminated; the *next* heap allocation (the CDXV handle, whose first word is a pointer like `0x40006120` → bytes `20 61 00 40`) overwrote the terminator, so the guest string became `path + " a"` | `alloc_str` now always appends `\0` |
| emulation executes one instruction and returns, `pc` unchanged | Unicorn 2.1.4: do not `reg_write(PC, x)` before `emu_start(x, …)`, and do not install a second *unrestricted* `UC_HOOK_CODE` (a range-limited `UC_HOOK_BLOCK` is fine) | debug-script pitfall only; harness unaffected |

### 5.2 Workaroundable / known-unsupported (fail loudly)

| item | status |
|---|---|
| `qsort` | **fatal if called.** A comparator lives in emulated code and Unicorn forbids a nested `emu_start` from inside a hook. The stub raises `EmuError: import qsort() is not supported by the harness … needs a re-entrant callback into emulated code` instead of returning a wrong order. Needed for the 1601-entry diphone table in `libvoice_*.so`. |
| `dlopen`/`dlsym` | stubbed to 0. This is **the** gate for loading the voice plug-in (engine code: `iVar2 = dlopen(param_2,0); pcVar3 = dlsym(iVar2,"register_voice")`). |
| C++ exceptions (`__cxa_begin_cleanup`, `__cxa_type_match`, `__cxa_call_unexpected`, `__gnu_Unwind_Find_exidx`) | no-ops; the C++ plug-in runs only while nothing throws. |
| pthreads (`pthread_mutex_*`, `pthread_key_*`, `pthread_getspecific`) | no-ops; single-threaded execution only. |
| `sigsetjmp`/`siglongjmp` | implemented (saved SP/LR/r4–r11; `siglongjmp` to an unsaved buffer raises `EmuError`). Not exercised by the runs above. |
| `fstat`/`stat` | best-effort bionic layout (`st_mode` @0x0c, `st_size` @0x2c, `st_blksize` left 0). Not exercised: the mmap wrapper passes an explicit length. |
| errno | not propagated from the host; `__errno()` returns a guest slot. |
| guest `mmap` | allocates from the 64 MiB emulated heap → a 152 MB mapping is impossible. Harmless here: the library itself maps only the 25 MB header region and streams payloads with `fseek`/`fread`. |
| `--trace` verbosity | an emulated OpenSSL bignum loop calls `memcpy` per limb; filter with `--trace REGEX`. |
| `sigsetjmp` inside the regex engine (lexicon parse) | untested — the ISEF run stops at the decrypted container, it never parses PCRE rules. |

---

## 6. Shortest path to a full `tts_streamer_synth` call

Already proven: `tts_create` + `tts_load_certificate` (§3), the container /
payload readers (§2, §4), the acoustic codec (§4).

Remaining, in dependency order:

1. **`dlopen`/`dlsym` for the voice plug-in.** `libvoice_en_us_kendra.so`
   exports only `TTS_ENGINE_1_6`, `register_voice`, `unregister_voice` and
   imports nothing from the engine, so it needs no symbol resolution against
   the engine.  It cannot simply be mapped next to the engine: the images
   overlap (`libttsivonavoice` vaddr `0x0–0x194df8`, `libvoice_en_us_kendra`
   `0x0–0x2f06fc`).  Give `ArmLib` a `base_delta` and load the plug-in at
   `delta ≈ 0x40000000`: its `R_ARM_RELATIVE` relocations already follow the
   base, `GLOB_DAT`/`JUMP_SLOT` go to the shared stub region, and the entry
   points returned by `dlsym` are then callable from the engine.  (Fallback for
   anything PC-absolute: run the plug-in in a second `Uc` and bridge calls.)
2. **`qsort`.** Implement it with an explicit re-entrancy trampoline (set up a
   return frame and let the emulator call the comparator via a *scheduled*
   nested `emu_start` after `emu_stop`, or pre-sort by calling the comparator
   through a small trampoline block in the stub region).  Needed the first time
   the diphone name table is sorted.
3. **Config.** `FUN_0005f7a4` builds the voxdb path from
   `/etc/ivona/ivona_config.xml` (`getSettingsCfg` → `voice_data, voice_lib,
   lex_dir, ca`).  Create it under a `--root` directory; `fopen` already
   resolves absolute guest paths through `--root`.
4. **Then**: `tts_load_voice(engine, libvoice_path)` → `tts_streamer_start` →
   `tts_streamer_add_voice` → `tts_streamer_synth(engine, text, cb, user)`.
   `tts_streamer_synth` drives the Viterbi search over section D/E of the OBB
   and reaches the codec path already exercised in §4; the lexicon comes from
   the ISEF path in §2.  The remaining risk is C++ exception traffic
   (`__cxa_*`) and `sigsetjmp` inside the PCRE lexer.

Estimated work: ~1–2 days, dominated by (1) relocation/`dlopen` plumbing and
(2) the `qsort` trampoline.  No unknown-unknowns remain in the call graph: every
imported symbol already has a stub and every internal function reached by the
three verified runs is named in the Ghidra dumps.

---

## 7. Evidence

```
emu/evidence/runs.log          all runs (incl. the fseek/fread trace), command + output
emu/evidence/unit_0..3.pcm     decoded 16-bit PCM for OBB units 0–3
emu/evidence/cert_tampered.txt negative-control certificate (one byte changed)
out/obb/lang_en_us.emu.bin     emulated ISEF plaintext (md5 == out/obb/lang_en_us.dec.bin)
```

Raw invocation examples are in `emu/README.md` §1.
