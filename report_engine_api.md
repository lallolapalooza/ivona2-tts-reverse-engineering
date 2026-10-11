# `libttsivonavoice.so` — Public C API & Engine Lifecycle (reverse-engineered)

Target: `out/libs/kendra/libttsivonavoice.so` (ELF32 ARM EABI5, stripped, identical in every IVONA 2 voice APK).
Evidence: Ghidra decompilation `out/ghidra_dump/libttsivonavoice.c` (unnamed funcs `FUN_...`), caller `out/ghidra_dump/decompiled.c` (= `libttsivona.so`, the JNI bridge), export list `out/exports_voice_engine.txt`, raw bytes/strings of the `.so`.

**Address convention:** Ghidra dump addresses = ELF vaddr **+ 0x10000** (verified: `v` ELF `0x18605` ↔ dump `00028604`; `.bss` start `0x18f1d0` ↔ `DAT_0019f1d0`). All `0x00xxxxxx` addresses below are **Ghidra dump addresses** unless stated. `.rodata` file offset == vaddr for the engine; bridge `.rodata` likewise (e.g. dump `0x7c7b2` → file `0x6c7b2`).

Vendor string (`tts_vendor_tag`, dump `0x473ac`):
`"IVONA Text-To-Speech\nivona-1.6.23\nFebruary 2013\n"` — engine/voice compatibility version is **`1.6.23`**.

---

## 1. The `v` symbol (dump `0x00028604`, ELF `0x18604`)

```c
undefined *v(void);   // returns &DAT_0019f1d4, guarded by __cxa_guard_acquire(&DAT_0019f1d0)
```
`v()` returns a pointer to a **static function-pointer table** (built once by `CIvonaTTS::CIvonaTTS()`, dump `0x000284cc`). It is *not* an object instance; it is a C-style API table. The bridge `dlopen`s `<voiceDir>/lib/libttsivonavoice.so` (`RTLD` flag 1), then `dlsym(handle, "v")` (`decompiled.c:10066`, string `0x7cf5c` = `"v"`), caches it in `DAT_000842cc`, and calls through it. A second dlsym name `"h"` (`0x7cf9c`) also exists in the bridge (`decompiled.c:10250`) but its use was not traced.

### 1.1 Vtable layout (dump `0x000284cc` `CIvonaTTS::CIvonaTTS`)

| off | slot | function | C signature (reconstructed) |
|-----|------|----------|------------------------------|
| +0x00 | vendor | `tts_vendor_tag` | `char* tts_vendor_tag(void)` |
| +0x04 | errno | `tts_errno` | `int tts_errno(void)` |
| +0x08 | errmsg | `tts_errmsg` | `char* tts_errmsg(void)` |
| +0x0c | init | `tts_init` | `void* tts_init(const char* cert_text)` |
| +0x10 | create | `tts_create` | `void* tts_create(void)` |
| +0x14 | cert file | `tts_load_certificate_file` | `void* tts_load_certificate_file(void* engine, const char* uri)` |
| +0x18 | cert mem | `tts_load_certificate` | `void* tts_load_certificate(void* engine, const void* cert_blob)` |
| +0x1c | destroy | `tts_destroy` | `int tts_destroy(void* engine)` |
| +0x20 | cert get | `tts_certificate_get` | `char* tts_certificate_get(void* engine_or_cert, const char* field)` |
| +0x24 | cert get1 | `tts_certificate_get_single` | identical body (see §4.3) |
| +0x28 | load voice | `tts_load_voice` | `void* tts_load_voice(void* engine, const char* so_path, const char* vox_path)` |
| +0x2c | unload voice | `tts_unload_voice` | `int tts_unload_voice(void* voice)` |
| +0x30 | voice param | `tts_voice_param` | `int tts_voice_param(void* voice, const char* cmd, void* value)` |
| +0x34 | sample rate | `tts_voice_sample_rate` | `int tts_voice_sample_rate(void* voice)` |
| +0x38 | dict insert | `tts_dict_insert` | `int tts_dict_insert(void* voice, const char* pattern, const char* replacement)` |
| +0x3c | dict remove | `tts_dict_remove` | `int tts_dict_remove(void* voice, int index)` |
| +0x40 | dict save | `tts_dict_save` | `int tts_dict_save(void* voice, const char* path, const char* filter_id)` |
| +0x44 | dict load | `tts_dict_load` | `int tts_dict_load(void* voice, const char* uri)` |
| +0x48 | dict count | `tts_dict_num_entries` | `int tts_dict_num_entries(void* voice)` |
| +0x4c | dict clear | `tts_dict_cleanup` | `void tts_dict_cleanup(void* voice)` |
| +0x50 | pls load | `tts_pls_load` | `int tts_pls_load(void* voice, const char* uri)` |
| +0x54 | pls unload | `tts_pls_unload` | `int tts_pls_unload(void* voice, int lexicon_id)` |
| +0x58 | start | `tts_streamer_start` | `void* tts_streamer_start(void* voice, const char* text, float speed)` |
| +0x5c | stop | `tts_streamer_stop` | `int tts_streamer_stop(void* streamer)` — **frees the streamer** |
| +0x60 | jump | `tts_streamer_jump` | `int tts_streamer_jump(void* streamer, int delta_segments)` |
| +0x64 | add voice | `tts_streamer_add_voice` | `int tts_streamer_add_voice(void* streamer, void* voice_or_-1)` |
| +0x68 | synth0 | `tts_streamer_synth0` | `int tts_streamer_synth0(void* streamer, int16_t* pcm, unsigned nframes)` |
| +0x6c | synth | `tts_streamer_synth` | `void* tts_streamer_synth(void* streamer, int max_frames)` |
| +0x70 | wave free | `tts_wave_delete` | `void tts_wave_delete(void* wave)` |
| +0x74 | warning | `tts_get_input_warning` | `int tts_get_input_warning(void* streamer, int* a, int* b, unsigned* c)` |

`tts_certificate_get` (ELF `0x383b8`) is literally `B tts_certificate_get_single` (`0xeaffffc9`) — a **tail-jump alias**; both vtable slots have identical behavior.

> Note the offset skew vs. the raw `tts_*` symbol set: `tts_dict_*`/`tts_pls_*` take the **voice** handle, not the engine (they index `voice[4]`/`voice[5]`, see §5).

### 1.2 Which slots the shipped bridge actually uses

| slot | call site in `decompiled.c` |
|---|---|
| +0x04 `tts_errno` | worker thread `FUN_0001f1d4` (marks-mode error test) |
| +0x08 `tts_errmsg` | all `"could not …: %s"` logs (e.g. `:2284`, `:5432`) |
| +0x0c `tts_init` | `FUN_00023284` `:9932` with the XOR-decoded certificate |
| +0x1c `tts_destroy` | `FUN_0002337c` `:9962` |
| +0x28 `tts_load_voice` | `:5421` `(*v)(engine, so_path, vox_path)` |
| +0x2c `tts_unload_voice` | `FUN_00023b80` `:10475` |
| +0x30 `tts_voice_param` | `FUN_0001c5f0` `:1918`; `set:quality/responsiveness/volume:max/contrast` `:5431-5446`; worker `set:contrast` |
| +0x34 `tts_voice_sample_rate` | `:1888`, `:2280`, worker (buffer sizing) |
| +0x44 `tts_dict_load` | `:5451` after voice load (user lexicon path) |
| +0x58 `tts_streamer_start` | `:2273` `(*v)(voice, text, -1.0f /* 0xbf800000 */)` |
| +0x5c `tts_streamer_stop` | worker (end of stream / replacement / shutdown) |
| +0x68 `tts_streamer_synth0` | worker (PCM mode) |
| +0x6c `tts_streamer_synth` | worker (marks mode) |
| +0x70 `tts_wave_delete` | `:2399`, `:5643` (marks flush) |
| not used by this bridge | +0x00,+0x10,+0x14,+0x18,+0x20,+0x24,+0x38..+0x50 (except +0x44),+0x60,+0x64,+0x74 |

---

## 2. Object model (from allocation sites)

### 2.1 Engine (`tts_create`, dump `0x00048230`) — 0x18 bytes
| off | field | init |
|---|---|---|
| +0x00 | magic `0x3e1b8f65` | checked by every engine-taking API |
| +0x04 | certificate list | `FUN_00055b40(4,0,FUN_000483bc)` (elements = 0xc-byte cert wrappers) |
| +0x08 | active cert context | set by `tts_load_certificate` via `FUN_0004e0d0` (dump `0x0004e0d0`) |
| +0x0c | loaded-voice list | guarded by mutex at +0x10 (`FUN_00048124`/`FUN_000480bc`) |
| +0x10 | mutex block | `FUN_000518b4()` |
| +0x14 | voice data-file registry | `FUN_000392a4()` (`FUN_00039300` check / `FUN_0003914c` remove) |

Global instance counter `DAT_001a4188` (inc in create, dec in destroy; at 0 → `FUN_000a96b8()` global cleanup). `tts_create` first runs `FUN_001264f0(3)` (global/network init); failure → errno **10** `"CURL initialization error: %s"`. `tts_destroy` (`0x0004815c`): bad magic → errno 8, return 0; counter underflow → errno 10 `"Free instances below 0"`, return 0; else frees cert list (`FUN_0004e1b8`), voice-related objects (`FUN_00055af0` ×2, `FUN_0005189c`, `FUN_0003927c`), zeroes magic, frees struct, returns 1.

A **named POSIX semaphore** `"/IVONA-e3a8a7e2d4d4fca3"` (`0x14807c`) is created/locked by helpers `FUN_00050860` (`sem_unlink`+`sem_open`), `FUN_000508a0` (`sem_post`), `FUN_00050910` (`sem_timedwait`, 2 s), used from `FUN_0005370c` → `FUN_0005191c(0x6da556e8)`/`FUN_000518dc`. [INFERENCE] cross-process mutex serializing certificate/limit verification ("one synthesis at a time" per device).

### 2.2 Certificate
- wrapper (0xc): `[0]=0x730366b1` magic, `[1]=parsed`, `[2]=chain` (`FUN_000537e0(parsed[+0x20])` or 0).
- parsed cert (fields observed at use sites): `+0x00` attr list (key/value/next), `+0x08/+0x0c` expiration (int64 low/high; `-1:-1` = NEVER), `+0x10` uint serial, `+0x14` int priority, `+0x18` **float thread-speed limit** (`-1.0f` = UNLIMITED), `+0x1c` **int num-threads limit** (`-1` = UNLIMITED), `+0x20` cert-group id, `+0x24` constraint list (`Voices`), `+0x28` **SSML-extension flag** (≠0 ⇒ SSML allowed).
- context `FUN_0004e0d0(parsed)` (0x30): `[0]` = *copy* of all attributes into a property map; `[2..8]` = parsed fields copied; `[9]` = copy of constraints; `[0xa],[0xb]` copied. Stored at engine+0x08; this is what `FUN_00048034` (`0x00048034`) returns everywhere ("active certificate").

### 2.3 Voice handle (`tts_load_voice`, `0x0004c028`) — 0x1c bytes
| off | field |
|---|---|
| +0x00 | engine back-pointer |
| +0x04 | info (0x24): `[0]` display name `"IVONA 2 - %s - %s"`(language_name, voice_name), `[1]` language_name, `[2]` language_code, `[3]` voice_gender, `[4]` voice_name, `[5]` eng_version, `[6],[7]` = 0, `[8]` normalized voice name (`FUN_0005519c`) |
| +0x08 | `props` handle: `b1c0(*register_handle, "name", "anonymous")` |
| +0x0c | **sample rate** (`b230(*register_handle,"sample_rate",0)`) |
| +0x10 | dictionary: NULL-terminated `entry*[]` (0x400-byte slab from `FUN_0004730c`) |
| +0x14 | registration record (`FUN_0004bf1c`): `[0]`=register_voice return, `[1]`, `[2]`=lexicon list, `[3]`=viterbi beam max, `[4]`=beam half |
| +0x18 | `dlopen` handle of the plugin |

### 2.4 Streamer (`tts_streamer_start`, `0x0004ac38`)
Handle = 8 bytes `{voice*, core*}`; core = `FUN_0004ab68` (0x44): `[0x1c]` speed float (`-1.0` ⇒ unpaced; `1.0` realtime; `>1` faster; values in `(-1,0)∪(0,1)` are snapped to `-1`/`1` by `FUN_0004ab68`), `[+0x20]` SSML parse context (contains warning queue at `ctx+0x24/0x28`), `[+0x38]` produced-wave list, `[+0x3c]` limits-verification handle [INFERENCE: passed as hidden arg from `FUN_00047fb4`], `[+0x40]` voice list (the initiating voice is appended at start), plus segment queue at `core+4`, cursor `core+8`, current segment `core+0xc/+0x10`, counters `core+0x14/+0x30/+0x34`.

### 2.5 Wave (`tts_streamer_synth`, 0x18) and marks (0x14 stride)
```
+0x00 opaque (copied from synthesis node +4)   +0x04 frame count
+0x08 int16 PCM (frames*2 bytes)               +0x0c mark count
+0x10 mark array: {u32 type, char* name, int start_text_off, int end_text_off, int sample_off}
```
`tts_wave_delete` (`0x0004a9b4`) frees name strings (per `DAT_0015bfc8` type table,5 entries), the mark array, PCM, and the struct. `NULL` → no-op.

---

## 3. Error model

| state | address | notes |
|---|---|---|
| `tts_errno()` | `DAT_0019600c` | **process-global** (no TLS, no locking) |
| message buffer | `DAT_00196010`, 0x100 bytes | custom message; first byte 0 ⇒ use code table |

`tts_errmsg()` (`0x000473cc`): if buffer non-empty → returns buffer; else static text per code (truncation appends `".."` at `DAT_0019610c/e` when `vsnprintf` ≥ 0x100):

| code | text |
|---|---|
| 0 | Success |
| 1 | Invalid certificate of authenticity |
| 2 | The certificate of authenticity has expired |
| 3 | The certificate of authenticity constraints would be violated |
| 4 | Failed to load voice |
| 5 | Format error |
| 6 | Argument out of range |
| 7 | Aborted by client |
| 8 | Invalid argument |
| 9 | Operating system error |
| 10 | Internal error |
| other | Unknown error |

Setters: `FUN_000474e4(code)` (clears message, sets code), `FUN_00047500(code, fmt, …)` (sets code + `vsnprintf` message), `FUN_00047570` (`"<fmt>: <old errmsg>"`), `FUN_00047628(syserrno, ctx)` → errno 9 via `strerror_r`. Success paths call `FUN_000474e4(0)`.

---

## 4. API reference (grouped)

### 4.1 Lifecycle
| fn (dump addr) | args | returns | semantics / state touched |
|---|---|---|---|
| `tts_init` `0x000486e0` | `cert_text` | engine\* or **0** | `tts_create()` then `tts_load_certificate(engine, text)`; on cert failure destroys engine and returns 0. This is the bridge's one-call bootstrap (`FUN_00023284`, `decompiled.c:9932`). |
| `tts_create` `0x00048230` | – | engine\* or 0 | see §2.1; errno 10 on global-init failure. |
| `tts_destroy` `0x0004815c` | engine | 1 / 0 | frees everything, decrements global counter; errors §2.1. |
| `tts_vendor_tag` `0x000473ac` | – | static string | quoted in the header block above. |
| `tts_errno`/`tts_errmsg` | – | code / text | §3. |

### 4.2 Certificates
| fn | args | returns | semantics |
|---|---|---|---|
| `tts_load_certificate` `0x00048464` | engine, blob | cert wrapper\* or 0 | null/bad-engine → errno 8. Parses via `FUN_0004e45c`; `FUN_0004e028` expiry check → **errno 2**; builds wrapper; group dedup: same `parsed+0x20` already present → newer-wins ordering on `+0x14/+0x10`, if not strictly newer → errno **6** `"Attempt to load the same certificate twice"`; cross-group compatibility `FUN_0004e244(old,new)` → 0 ⇒ fail. Appends to engine+4, rebuilds engine+8 context (`FUN_0004e0d0`, merge `FUN_0004db84`). |
| `tts_load_certificate_file` `0x0004871c` | engine, uri | same | null → errno 8; `FUN_000505ac(uri)` fetch (file:// / http), `FUN_00050430` content → `tts_load_certificate`. |
| `tts_certificate_get{,_single}` `0x000482e4/0x000483b8` | engine **or** cert-wrapper, `field` | `char*` or 0 | Accepts engine magic `0x3e1b8f65` (uses engine+8 context, fallback first list entry) or cert magic `0x730366b1`. `FUN_0005b1c0(attrs, field, 0)`; missing → **errno 8**, return 0. `FUN_0005575c` list empty → errno 3 `"No certificates loaded"`. |

Expiry (`FUN_0004e028`): expiration `(-1:-1)` or `now ≤ exp` → 0 (valid); else 1 → callers map to **errno 2**; `time()` failure → -1 + errno 9 (`"%s() failed: %s"`).

### 4.3 Voices — see §5 for the plugin contract.
| fn | args | returns |
|---|---|---|
| `tts_load_voice` `0x0004c028` | engine, `so_path`, `vox_path` (may be NULL) | voice\* / 0 |
| `tts_unload_voice` `0x0004c5b0` | voice (NULL ⇒ return 1) | 1/0 |
| `tts_voice_sample_rate` `0x0004bc64` | voice | Hz, or **-1** + errno 8 for NULL |

`tts_load_voice` step-by-step (all quoted strings are `.rodata`):
1. `FUN_00048034(engine)` must resolve active cert (errno 3/8 otherwise); `FUN_0004e028` must be 0 else **errno 2**.
2. `dlopen(so_path, 0)`; `dlsym("register_voice")`; failures → **errno 9** with `&DAT_0015645c` format (`"%s"`, dlerror text), `dlclose`.
3. `__errno()=0; props = register_voice(vox_path)`:
   - NULL + `errno==2` → errno **4** `"The vox file does not exist"`;
   - NULL + `errno!=0` → errno 9 (`FUN_00047628`);
   - NULL + `errno==0` → errno **4** (static `FUN_000474e4(4)` = "Failed to load voice").
4. Required properties (`FUN_0005b0bc` presence test): **`voice_name`, `voice_gender`, `eng_version`, `language_name`, `language_code`** — any missing → errno **4** `"Invalid voice library data"` (+ `unregister_voice`, `dlclose`).
5. Build info struct (§2.3), display name `sprintf("IVONA 2 - %s - %s", language_name, voice_name)`.
6. `eng_version` must `strcmp("1.6.23") == 0`, else errno **4** `"Voice library version mismatch: got %s, required %s"` (got=voice, required=`1.6.23`) and cleanup.
7. Certificate voice-allow: `FUN_0004dee4(active_cert, voice_name, language_code, custom_voice)`; 0 → errno **3** `"Voice not allowed by the certificate"` (§7).
8. Data file resolution: root = `$IVONA_LANG_DAT_DIR` (+`'/'`) if set, else **directory of `vox_path`** (or of `so_path` if `vox_path==NULL`; strip after last `/` or `\`). Then `FUN_0004be40` builds `lang_<language_code with -/space→'_'>_<voice_name with space//→'_'>.dat` and `FUN_00039300(registry, path)`; if that fails, fallback `FUN_0004bfb8` builds `lang_<language_code>.dat` and re-checks; still 0 → fail (returns 0; no extra message here [INFERENCE: relies on registry's errno]).
9. Alloc voice (0x1c), store fields (§2.3), `FUN_00049e98(voice)` **resets every voice param to its `:def`** (`FUN_0005af44(props,"pause_base_len",0)` + `FUN_00049448` seeds beam), register into engine voice list (`FUN_00048124`), fresh dictionary (`FUN_0004730c`).
10. Success → voice\*.

`tts_unload_voice`: `dlsym(handle,"unregister_voice")` → call with `record[0]`; `dlclose`; both failures → errno 9 (dlerror); then removes voice from engine list (`FUN_000480bc`), frees registration record (`FUN_0004bf00`), dictionary (`FUN_00047314`), info struct, engine back-ref check, frees voice. `param_1==NULL` ⇒ 1.

### 4.4 Dictionary (user lexicon) — first arg is the **voice** handle
| fn | returns | semantics |
|---|---|---|
| `tts_dict_insert(voice, pattern, replacement)` `0x00047158` | new count / -1 | NULL engine→errno8. If `pattern==NULL \|\| replacement==NULL` → just returns count. Converts both via `eng_text_encoding` (default `UTF-8`), compiles regex (`[:graph:]` etc. classes, `FUN_00080db8`), inserts at index (`eng_dict_insert_id` prop decides position); errors → errno 5 (`"Regex compilation error at offset %d: %s"` etc.). |
| `tts_dict_remove(voice, index)` `0x00046d28` | new count / -1 | out-of-range → errno 6. Frees entry {pattern,replacement,regex×2, id}. |
| `tts_dict_num_entries(voice)` `0x00046ce4` | count / -1 | errno 8 for NULL. |
| `tts_dict_save(voice, path, filter_id)` `0x00045f64` | 1 / -1 | `fopen(path,"w")` (errno 9 `"Cannot open file for writing"`; NULL engine errno 8). Header exactly `"#& encoding=UTF-8\n"`; then per entry (optional `filter_id` match on entry[4]): `pattern replacement\n`, `"`-quoting + `\"` escaping when the token contains whitespace/quotes. |
| `tts_dict_load(voice, uri)` `0x00046a6c` | count loaded / -1 | uri must start `file://` or `http://` (else treated as such anyway: plain path goes through `FUN_00046a10` → `FUN_000505ac`). Encoding from `eng_text_encoding`; insert id from `eng_dict_insert_id`. Parse (`FUN_0004620c`): honours `#& encoding=`, BOM UTF-8/UTF-16LE/BE detection; ≤100 errors else `"Too many errors. Quitting"`; messages `"Lexicon encoding not supported: %s"`, `"invalid dictionary format"`, `line %ld: %s`, `"%ld errors found"`, `"\nAt least %ld more errors follow"`; errors → errno **5**; http fetch path: `"Failed fetching lexicon file"`, abort → errno 7. Returns count of entries loaded (≥0) or -1. |
| `tts_dict_cleanup(voice)` `0x0004738c` | void | frees dict array + entries, allocates fresh 0x400 slab. NULL → no-op. |

### 4.5 PLS pronunciation lexicons — first arg is the **voice** handle
| fn | returns | semantics |
|---|---|---|
| `tts_pls_load(voice, uri)` `0x0004c6a8` | id ≥ 1 / **-1** | NULL→errno8. Requires active cert with **`cert+0x28` (SSML extension) ≠ 0**, else **errno 3**. `file://`/`http://`/plain path (`FUN_000505ac`, fetch timeout `0x42f00000` = 120 s via `FUN_000477e4`). Parses PLS XML (`FUN_0003816c`), namespace fallbacks `http://www.w3.org/2005/01/pronunciation-lexicon`; warnings quoted in §Appendix. Failures: errno **5** `"Failed parsing PLS lexicon file"` / `"…: %s"` detail, errno 9 `"Failed fetching PLS lexicon file"`, errno **10** `"Too many PLS lexicons"` (id space up to `0x7ffffffe`). Stores `{id, handle}` pairs into `record[2]` list; returns id. |
| `tts_pls_unload(voice, id)` `0x0004bd94` | 1 found / 0 not found / -1 errno8 | removes entry from the list. |

### 4.6 Streamer / synthesis — see §6 for the driving protocol.
| fn | returns | semantics |
|---|---|---|
| `tts_streamer_start(voice, text, speed)` `0x0004ac38` | streamer\* / 0 | NULL voice/text → errno 8. Resolves active cert (`FUN_00048034(*voice)`); `FUN_0004e028` ≠ 0 → errno 2. **Speed clamp**: effective = cert-speed `-1.0f` ? `speed` : `min(cert_speed, speed)` (negative `speed` → cert speed). Thread limit `cert+0x1c == -1` → OK, else `FUN_00047fb4(engine, …)` must return non-0 (else no streamer, errno 3 `"No certificates loaded"` possible). Creates core, appends voice to `core+0x40`, parses text `FUN_0004a2d4` (0 = ok; non-0 ⇒ core destroyed, returns 0; handles `text/plain` vs `application/ssml+xml` via `eng_input_type`, wraps plain text in a synthetic `<speak version=… xml:lang=…>`, `eng_text_encoding` default `UTF-8`; SSML parse errors: `"Unsupported MIME type"`? no — that's voice_param; parse returns 2 = XML/SSML error). Returns 8-byte handle `{voice*, core*}`. |
| `tts_streamer_synth0(streamer, pcm, n)` `0x0004b460` | frames written / -1 / 0 | gate: streamer≠0, `(int)n ≥ 0`, `pcm≠0` unless `n<1`; else errno 8, -1. Loop `FUN_0004ae28(streamer, remaining, pcm, 0)`; `pcm += frames*2`; stops on 0 (end) or -1 (error, propagates errno; e.g. 10 `"Limits verification error"`, 8, 7). Returns total frames. |
| `tts_streamer_synth(streamer, budget)` `0x0004b51c` | wave\* / 0 | `budget==0` → `FUN_0004ae28(…,0,0,0)` flush-parse, returns NULL. `budget<0` [INFERENCE] ⇒ synthesize until end. Collects waves from `core+0x38` until ≥budget frames or producer returns 0. 0 waves → NULL (end); 1 wave → returned directly; >1 → merges into a new wave (concatenates PCM, concatenates marks, rebases `sample_off` by running frame offset, duplicates non-interned names), frees sources. On producer error: frees all collected waves, clears list, returns NULL (errno set). OOM → errno 9 `"Out of memory"`. Always clears the wave list before returning. |
| `tts_streamer_stop(streamer)` `0x0004ab34` | always 1 | destroys core (`FUN_0004aacc`: parser, lists, voice list) and **frees the handle**. NULL → 1. |
| `tts_streamer_jump(streamer, delta)` `0x0004a898` | frames/segments actually moved, 0 = none | position = `core+8` (utterance index over `core+4` list); negative clamps to 0; positive synthesizes more utterances (`FUN_00040770(core+0x24)`) until target or list end (-1 ⇒ return 0). Frees current segment (`FUN_000597cc`), resets `core+0xc/+0x10`, mark cursors `core+0x30/+0x34`, `core+0x14`. Sets errno 0 on the success path. Not used by the ICS bridge. |
| `tts_streamer_add_voice(streamer, voice\|-1)` `0x0004b8d4` | 1/0 | `voice == (void*)-1` → add **all** engine voices (walks engine+0xc under engine mutex); else single voice. Per candidate: same `voice[3]` sample rate → else errno **6** `"Voices with different sample rate"`; same engine instance and both voices pass `FUN_0004dee4` cert check → else errno **6** `"Voices with different TTS instance"`. Appends to `core+0x40` if not present; already present → 1. [INFERENCE] backs SSML `<voice>` multi-voice synthesis; bridge never calls it directly. |
| `tts_wave_delete(wave)` | void | §2.5. |
| `tts_get_input_warning(streamer, int*, int*, unsigned*)` `0x0004a7d4` | warning code, 0 = none | Pops one node from the parser warning queue (`ctx+0x24` head / `ctx+0x28` current; node = `{v0, v1, code, v3, next@+0x10}`): `*a = v0`, `*b = v1`, `*c = v3`, **return = code**; node cleared. NULL engine/streamer → errno 8; queue empty → 0. Field meanings [INFERENCE: text offsets + warning id]. Unused by the ICS bridge. |

`FUN_0004ae28` (the producer, called only by synth0/synth) also: verifies certificate limits each chunk when `core+0x3c` ≠ 0 (`FUN_000539a0` → errno 10 `"Limits verification error"`); copies `duration_stretch` and `amplify` props onto the produced segment; **paces** output when speed ≠ -1: sleeps so each chunk takes ≈`elapsed vs 360 ms` (see §6).

---

## 5. Voice plugin contract expected by `tts_load_voice`

`register_voice` / `unregister_voice` are dlsym'd by name (strings `0x146f94`, `0x146f80`; versioned symbols `@@TTS_ENGINE_1_6` live in the plugin).

```c
// plugin side (assumed shape, consistent with all use sites):
void* register_voice(const char* vox_path);  // returns handle H (or NULL + *errno)
void  unregister_voice(void* H);
// H's first word H0 is a property container read via:
//   FUN_0005b0bc(H0, key)        → key exists?
//   FUN_0005b1c0(H0, key, def)   → string value
//   FUN_0005b15c(H0, key)        → string (owned copy)
//   FUN_0005b230(H0, key, def)   → int value
//   FUN_0005b1f8(H0, key, def)   → float value
```
- Argument: the **`vox_path` (3rd arg of `tts_load_voice`)** — engine treats it as the voice data file, and uses its directory as data root when `IVONA_LANG_DAT_DIR` is unset. `errno` protocol: `2` → "vox file does not exist"; other → OS error; `0` + NULL → generic load failure.
- Required keys: `voice_name`, `voice_gender`, `eng_version`, `language_name`, `language_code`.
- Optional keys consumed: `sample_rate` (int → `tts_voice_sample_rate`), `custom_voice` (int flag → cert check), `name` (default `"anonymous"` → voice+8).
- The **same property set must also carry the engine params** the engine reads through `record[0]`: `eng_contrast`, `amplify`, `duration_stretch`, `pitch_stretch`, `viterbi_beam`, `tb_min_distance`, `eng_sentence_break`, `eng_paragraph_break`, `eng_text_encoding`, `eng_max_sentence`, `eng_max_word`, `eng_dict_insert_id`, `eng_input_type`, `eng_ssml_base_uri`, `eng_fetch_function`, `eng_fetch_user_data`, `pause_base_len`, and the (bugged) float-limit keys `param_##p_l##_min|_def|_max` — i.e. these come from the `.vox` data file loaded by the plugin.
- Version gate: `eng_version` must equal **`1.6.23`** exactly (message §4.3-6). `TTS_ENGINE_1_6` itself is not checked by the engine — it is the ELF symbol-version of the plugin's exports.
- Data file gate: `lang_<code>_<name>.dat` (fallback `lang_<code>.dat`) must exist under the data root, else load fails.

---

## 6. Streamer semantics (incremental synthesis)

### 6.1 Speed / pacing
- `tts_streamer_start(voice, text, speed)` with `speed = -1.0f` (bridge always passes `0xbf800000`) means *as fast as possible*: core+0x1c = -1.0 and `FUN_0004ae28` skips pacing. Otherwise the engine sleeps to keep each ~0.3 s chunk taking ≈360 ms (`0x43160000`) scaled by speed [INFERENCE on exact factor].
- Certificate `Thread-speed` (`parsed+0x18`, -1.0 = UNLIMITED) caps the requested speed; `Num-threads` (`parsed+0x1c`, -1 = UNLIMITED) gates streamer creation.

### 6.2 PCM mode (bridge worker `FUN_0001f1d4`, decompiled out-of-band — see note)
Per new streamer:
1. `rate = tts_streamer… vtable+0x34(voice)`; on rate change: **chunk = 0.3×rate frames** (new `int16[chunk]` scratch), ring buffer resized to **capacity = 3.0×rate frames** (initial static ctor values `0x10266`=66150 / `0x19d7`=6615 exactly match rate=22050), producer wake threshold = 0.3×rate.
2. loop: `n = tts_streamer_synth0(streamer, scratch, chunk)`:
   - `n > 0` → push frames into the ring (consumer `FUN_0001f540`→`FUN_0001f4a4` pops into the app buffer; waits ≤1 s per call); if ring holds ≥ ~0.3–0.6 s, usleep so the chunk period ≈360 ms.
   - `n == 0` (end) or error → `tts_streamer_stop(streamer)` (**frees it**), clear slot, broadcast consumers; if in marks mode and `tts_errno() != 0` the loop aborts with error.
3. Main thread `TtsEngineWithMarks::synthesizeText` (`decompiled.c:2231-2408`): `streamer = v+0x58(voice, text, -1.0f)`, attaches to junction (`FUN_0001edc8`), then `for (frames = 0; frames < buf_frames; frames += got) got = pop_pcm(dst + frames, buf_frames - frames);` (byte buffer length is halved → frame count), applies a fixed IIR post-filter (coefficient table `DAT_000840d4…`), then invokes the Java callback `audioAvailableClbk(buf, sample_rate, 1, 1, &data, &nbytes, 1)`. Loop ends when the junction reports streamer gone and queues empty; a final callback with length 0 signals completion. `v+0x08` (`tts_errmsg`) is logged if start fails: `"could not create streamer: %s"`.

### 6.3 Marks mode (`synthesizeText(String, byte[], List, int)`)
- Junction flag `+0x60` set via `FUN_0001ee9a(buf, frames)`; worker then calls **`v+0x6c` = `tts_streamer_synth(streamer, frames_budget)`** and enqueues the returned wave (10-slot DWORD queue at junction+0x28); main pops waves (`FUN_0001edee`), copies PCM, and finally `v+0x70` `tts_wave_delete`.
- Each wave's marks become `android.speech.tts.SpeechMark{type, sampleOffset, name, startTextOffset, endTextOffset}` (`FUN_0001fac0`, `decompiled.c:6358-6502`); `sampleOffset = accumulated_prior_frames + mark.sample_off`; a type-mask (from the JNI `int` arg) filters which types are emitted.
- Engine mark type → SpeechMark constant (array `DAT_00080ea0`, file `0x70ea0`):

| engine type | pushed by | Android constant |
|---|---|---|
| 0 | (reserved) | `TYPE_PHONEME` |
| 1 | word/`start_pos`-`end_pos` boundary (`FUN_0004aa5c(wave,1,…)` ) | `TYPE_WORD` |
| 2 | sentence (`FUN_0004aa5c(wave,2,…)`) | `TYPE_SENTENCE` |
| 3 | named boundary (`FUN_0004ad70`) | `TYPE_SSML` |
| 4 | named event (`FUN_0004aa5c(wave,4,name,…)`; empty → `DAT_00156f00`) | `TYPE_VISEME` |

- Warnings (`v+0x74`, §4.6) are not consumed by this bridge revision.

### 6.4 Stop / flush
`FUN_0001ee14(junction)` (called by JNI `stop` path and when replacing a streamer): resets the PCM queue, and in marks mode drains queued waves calling `v+0x70` on each. The worker itself calls `v+0x5c` `tts_streamer_stop` on: streamer replacement, natural end, error, thread exit (`FUN_0001edae` waits for `+0x54/+0x68` to clear). `tts_streamer_stop` is thus the **only** correct way to dispose a streamer; `tts_wave_delete` disposes waves.

> **Recovery note:** the worker thread function (Ghidra addr `0x0001f1d4`) is missing from `decompiled.c` (function-creation gap); it was decompiled on demand for this report (`scripts/gap_bridge.c`, Ghidra headless `scripts/DecompAt.java`) — figures above are read from that output.

---

## 7. Certificate / licensing (what a reimplementation must reproduce or bypass)

**Transport.** `libttsivona.so` embeds the certificate XOR-obfuscated in `.rodata`; `FUN_00023284` (`decompiled.c:9882`) decodes it (`KEY=0x6d070`, `D=0x6d079`, `D2=0x6d07d`; length word = `Σ ((d[KEY+(i+5)%9]^d[KEY+i%9]^d[D+i])<<(8i))` = 1798; `out[i] = d[D2+i]^d[KEY+(i+4)%9]`) and calls **`v+0x0c` (`tts_init`) once**, caching the engine in `DAT_000842c8`; `v+0x08` is used to log failures. Decoded text: `out/certs/ivona_certificate_decoded.txt` — key=value fields `Product: IVONA; Certificate-ID: a1169787; Num-threads: UNLIMITED; Thread-speed: UNLIMITED; Expiration-date: NEVER; Voices: ALL; Extension-SSML: TRUE;` + `-----BEGIN SIGNATURE-----` (13×64 hex chars).

**Engine-side validation** (all inside `tts_load_certificate`/`FUN_0004e45c`+friends):
- parse errors (strings `0x147990…0x147c04`): `"Missing certificate attribute \"%s\""`, `"Invaid value of certificate attribute %s"` [sic], `"Invalid certificate line%s%.*s%s%s"`, `"Unsupported certificate comments"`, `"Error reading certificate attribute \"%s\""`, `"Duplicate certificate attribute %s"`.
- signature/authenticity → maps to **errno 1** `"Invalid certificate of authenticity"`; expiry (`Expiration-date`/`time()` check `FUN_0004e028`) → **errno 2** `"The certificate of authenticity has expired"`; constraint violations → **errno 3** `"The certificate of authenticity constraints would be violated"`.
- `Extension-SSML: TRUE` ⇔ `parsed+0x28 ≠ 0`: gates (a) `application/ssml+xml` input — `"The certificate does not allow for SSML input"` (errno 3, in `FUN_000491b4` voice_param `set:input_type`) and (b) SSML document parsing in `FUN_0004a2d4`, and (c) `tts_pls_load`.
- `Voices:` ⇔ `parsed+0x24` constraint list: `FUN_0004dee4` returns true for `"*"` or `"all"` (`DAT_001550fc`/`DAT_00157930`); otherwise every whitespace-separated token of `language_code` must match a constraint stored with the 4-byte prefix immediate `0x3a6c4c61` (LE bytes `61 4c 6c 3a`, i.e. `"aLl:"`) [INFERENCE on exact on-disk key form]; token >26 chars → deny; `custom_voice` requests take the dedicated early check (`FUN_000531cc()` with dropped args) and otherwise deny. Denial → `"Voice not allowed by the certificate"` (errno 3) in load_voice / errno 6 in `add_voice`.
- `Num-threads`/`Thread-speed` (§6.1): checked at streamer start (`FUN_00047fb4` → returns a limits object; -1 = unlimited short-circuits) and per-chunk (`core+0x3c` → `FUN_000539a0`, errno 10 `"Limits verification error"`), serialized cross-process by the `/IVONA-e3a8a7e2d4d4fca3` semaphore (§2.1).
- Multi-cert rules: newest-per-group wins; strictly-newer ordering on `+0x14/+0x10`; duplicate → errno 6 `"Attempt to load the same certificate twice"`; cross-group compatibility via `FUN_0004e244`; multiple contexts merged `FUN_0004db84`. Empty list → errno 3 `"No certificates loaded"` (also from `FUN_00048034`).

**For a reimplementation:** either implement `FUN_0004e45c` parsing + signature check (RSA-looking hex blob; algorithm not fully traced [INFERENCE]) or accept a pre-validated certificate and short-circuit errno 1/2/3 — every consumer (voice load, SSML, PLS, streamer start, limits) consults the same `parsed`/context fields listed in §2.2.

---

## 8. `tts_voice_param` — command grammar and key table

**Grammar** (parser `0x00049f78`): `cmd = "set" | "get"`, colon-separated:
```
set:KEY            → value = *ptr (in)     get:KEY            → *ptr = value (out)
set:KEY:min|max|def→ set to limit/default get:KEY:min|max|def → *ptr = limit/default
```
3rd argument is always a **`void*` to a value** (int / uint / float-bits / `char*` depending on key). Unknown cmd/KEY/qualifier → **errno 8**, return 0. Handler result is returned directly (`1` = ok, `0` = failed with errno set). Table base `DAT_00194fbc` (vaddr `0x184fbc`, entries `{char* key, char* engine_prop, handler}`):

| KEY | property in `.vox` | handler | value type / range / default |
|---|---|---|---|
| `volume` | `amplify` | `FUN_000494a4` (float) | **int 1..99** (encoded, see below); float limits min `0.0`, def `1.0`, max `1.6` (`0x3fcccccd`) |
| `dur_stretch` | `duration_stretch` | `FUN_000494a4` | int 1..99; float min `0.25`, def `1.0`, max `1.5` |
| `pitch_stretch` | `pitch_stretch` | `FUN_000494a4` | int 1..99; float min `0.9`, def `1.0`, max `1.1` |
| `contrast` | `eng_contrast` | `FUN_00048824` | int 0/1. set 1 → prop `compress = 4.0f`; set 0 → `compress = 1.0f`; get → `(compress==4.0)`; `min`/`def` → 0, `max` → 1; qualifier other than min/max/def → errno 8; value not 0/1 → errno 6 |
| `quality` | `viterbi_beam` | `FUN_00049cf0` | int **1..10**. beam = `base/2 + ((base-base/2)*(lvl-1) ± rnd)/8`, base = beam prop (seeded 50, half 25): lvl1→25 … lvl9→50; lvl10 → stores `-1` (`max` → `-1`, `min` → lvl1, `def` → half(25)). get: `-1`→10, base→9, half→1; unset→1; out-of-1..10 set → errno 6 |
| `responsiveness` | `tb_min_distance` | `FUN_00048b34` | int 0/1 (`set` requires `< 2` else errno 6); `min` stores `-1`, `max`/`def` store `6`; `get` returns `1` iff stored value `== 6`; `get:min` → 0, `get:max`/`def` → 1. [exact store of the plain set could not be fully recovered — Ghidra drops the value argument: `FUN_0005af6c(props,key)`] |
| `sentence_break` | `eng_sentence_break` | `FUN_000499e4` | int **milliseconds**; stored = ms×`0.001f`; stored range `[0, 0x42700069 (=60.0003 s)]` ⇒ input 0..60000 ms, **def 400 ms** (stored `0x3ecccccd` = 0.4 f); out of range → errno 6; `get` rounds (±0.5) |
| `paragraph_break` | `eng_paragraph_break` | `FUN_000499e4` | same units; **def 650 ms** (`0x3f266666` = 0.65 s); range 0..60000 |
| `max_sentence_length` | `eng_max_sentence` | `FUN_00048ca0` | int; min **1**, max `0x7fffffff`, **def 1000**; out of range → errno 6; `min`/`max`/`def` qualifiers supported |
| `max_word_length` | `eng_max_word` | `FUN_00048ca0` | int; min 1, max `0x7fffffff`, **def 100** |
| `text_encoding` | `eng_text_encoding` | `FUN_000493a8` | string; validated via `FUN_0005534c` → errno 6 `"Invalid character encoding"`; NULL/empty → errno 8; def `UTF-8` |
| `base_uri` | `eng_ssml_base_uri` | `FUN_000492c0` | string; scheme must be `file://` or `http://` (list at `DAT_00190200`) else errno 6 `"Unsupported URI scheme; must be file:// or http://"`; def `""` |
| `input_type` | `eng_input_type` | `FUN_000491b4` | string `""`/`text/plain`/`application/ssml+xml` (case-insens.); SSML needs cert flag else errno 3 `"The certificate does not allow for SSML input"`; other MIME → errno 6 `"Unsupported MIME type"`; def `""` |
| `fetch_function` | `eng_fetch_function` | `FUN_00048a0c` | pointer (`void*`); `def` → 0; get returns 0 if unset |
| `fetch_user_data` | `eng_fetch_user_data` | `FUN_00048a0c` | pointer; same |
| `dict_insert_id` | `eng_dict_insert_id` | `FUN_00048f7c` | string; `def` from table `DAT_001901d8`: `eng_dict_insert_id`→`""`, `eng_ssml_base_uri`→`""`, `eng_input_type`→`""`, `eng_text_encoding`→`"UTF-8"`; missing default → errno 10 `"Default string missing"` |

Float-key encoding (`FUN_000494a4`) — value is an **integer 1..99**, mapped to the float range with an XOR mask:
```
set:  f = min + (((v-1) ^ 0xe6aa80c7 ^ salt) % 99) * (max-min) / 99      ; v in [1,99], else errno 6
get:  n = round((f-min)*99/(max-min))  (round up when frac >= 0.75)
      out = (n ^ 0xe6aa80c7 ^ salt) % 99 + 1
salt = active_cert_context[+0x2c]  (0 if no context)
limits read from voice props keys literally "param_##p_l##_min" / "_def" / "_max"
(macro-stringization bug in the original; if the .vox lacks them the hard-coded defaults above apply)
```
`min/max/def` qualifiers bypass encoding and set/read the float limits directly.

Also relevant (not reachable through the command table):
- `set:KEY:min|max|def` variants listed per key above; `set:quality:def` stores the seeded half-beam.
- At voice load, `FUN_00049e98` force-applies `KEY:def` to **every** table entry (except handler `FUN_00048eb4`, which is not in the table) and clears `pause_base_len` — so unloaded voices start at defaults.
- Bridge observed settings: `set:quality`=1, `set:responsiveness`=1, `set:volume:max`, `set:contrast`=1 right after load (`decompiled.c:5431-5446`); per-synthesis `dur_stretch`/`pitch_stretch` computed as `get:KEY:def × factor` clamped to `[min,max]` then `set:KEY` (`FUN_0001c668`, strings `get/set/:def/:min/:max` at `0x6c7b2..0x6c7c5`); worker may flip `set:contrast` live (`junction+0x5c`, init 3 → set `(state==3)`).
- Keys seen in `.rodata` but *not* exposed via the table: `rate`, `pitch`, `volume` (SSML prosody attributes only), `pause_base_len`, `viterbi_beam`, `tb_min_distance`, `compress`.

---

## 9. Sample rate
`tts_voice_sample_rate(voice)` returns `voice[3]` = the plugin's `sample_rate` property (int, from `.vox`; bridge assumes **16000** when no voice is loaded, `FUN_0001c544`). Multi-voice mixes require identical rates (`"Voices with different sample rate"`). The bridge sizes its ring (3 s), chunk (0.3 s) and Java buffer conversions from this value; `getSampleRate` JNI defaults to 16000.

## 10. Bridge bootstrap recap (call order a reimplementation must satisfy)
1. `dlopen("<voiceDir>/lib/libttsivonavoice.so", 1)`; `dlsym("v")` → table (§1).
2. `engine = v+0x0c(decoded_certificate)`; log failures via `v+0x08`.
3. `voice = v+0x28(engine, <pkg>/lib/<plugin>.so, <voice>.dat)`; then `v+0x30` defaults, `v+0x44(voice, lexicon_uri)`.
4. per utterance: optional `v+0x30` stretch updates → `v+0x0c` … (cert already cached) → `streamer = v+0x58(voice, text, -1.0f)`; worker pumps `v+0x68`/`v+0x6c`; consumer reads sample-rate via `v+0x34`; end → `v+0x5c` (frees streamer); marks → `v+0x70` per wave.
5. voice switch: `v+0x2c(old_voice)`; shutdown: `v+0x1c(engine)` (`FUN_0002337c`).

---

## Appendix — notable quoted strings (file offsets, engine `.so`)
`0x147040 "Voice library version mismatch: got %s, required %s"` · `0x146fa4 "The vox file does not exist"` · `0x14701c "Invalid voice library data"` · `0x147074 "Voice not allowed by the certificate"` · `0x146c9c "The certificate does not allow for SSML input"` · `0x146980 "Invalid certificate of authenticity"` · `0x1469ac "…has expired"` · `0x1469d8 "…constraints would be violated"` · `0x146b98 "No certificates loaded"` · `0x146be8 "Attempt to load the same certificate twice"` · `0x146f14 "Voices with different sample rate"` · `0x146f48 "Voices with different TTS instance"` · `0x146f80/0x146f94 "unregister_voice"/"register_voice"` · `0x1470cc "Too many PLS lexicons"` · `0x1470e4 "Failed parsing PLS lexicon file"` · `0x145bbc "Failed fetching lexicon file \"%s\""` · `0x146d8c "Invalid float param"` · `0x146da0 "Invalid floatlength param"` (msg used by `FUN_000499e4`) · `0x14533c "Lexicon is empty"` · `0x14807c "/IVONA-e3a8a7e2d4d4fca3"`.

## Appendix — open items / [INFERENCE]
- Exact certificate signature algorithm (parse path `FUN_0004e45c`/`FUN_0004e244`/`FUN_0005403c`) not traced.
- `FUN_0005af6c` value semantics for `responsiveness` plain-set (Ghidra drops the argument).
- `FUN_0004ab68`'s 2nd arg (→ `core+0x3c` limits handle) dropped by the decompiler.
- `tts_streamer_add_voice`/`jump`/`get_input_warning` have no in-tree callers (available for other bridges).
- `DAT_00155d00`→`"name"` key default `"anonymous"`; separator class `0x145ff4` = `" \t\n\r"` for cert voice tokens.
- Pacing arithmetic mixes sample and byte units as decompiled; treat the 360 ms/0.3 s figures as approximate.
