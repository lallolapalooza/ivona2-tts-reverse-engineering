# `libttsivona.so` — JNI bridge / facade ("TtsEngineWithMarks")

Binary: `out/tts/lib/armeabi/libttsivona.so` (472 444 B, ELF32 ARM EABI5, Thumb, stripped, sha256
`a7cb15fe22b09dd99d6b5ce7ce363faff58d7e841f28b9b5907bde861bb36476`).
Depends on `libdl, liblog, libstdc++, libm, libc` only.

Reproduce everything here:

```sh
ghidra-analyzeHeadless out/ghidra ivona -process libttsivona.so -noanalysis \
    -scriptPath scripts/ghidra -postScript DumpDecompilation.java out/ghidra_dump/decompiled.c
~/venvs/re/bin/python scripts/litstrings.py out/tts/lib/armeabi/libttsivona.so 0x1c0e0 0x73a3c
```

Address convention: **Ghidra addr = ELF vaddr + 0x10000** (`.text` vaddr `0xc0e0` … `0x63a3c`,
`.rodata` vaddr `0x6c564`, size `0x38fc`, `.data.rel.ro` `0x715e8`, `.got` `0x73b38`, `.data` `0x74000`,
`.bss` `0x74098`). String addresses below are given as Ghidra addrs.

## 0. How string references are coded (needed to read the decompilation)

The library is PIC. A string is addressed with two instructions:

```
ldr rX, [pc, #imm]     ; signed displacement from the literal pool
add rX, pc             ; rX = (instruction_address + 4) + displacement   (NO 4-byte alignment)
```

`add …, pc` does **not** align to 4 (verified: `0x140e6 + 0x58663 = 0x6c749` = `"com.ivona.tts/files/"`,
while the aligned variant lands on the previous string's terminator). `ldr` literal loads *do* use
`(pc+4) & ~3`. `scripts/litstrings.py` implements this and dumps 151 literals; output:
`out/litstrings_all.txt`.

## 1. Exported symbols

JNI (`.dynsym`, all `Java_com_ivona_*`):

| symbol | Ghidra addr |
|---|---|
| `…_ics_NativeIVONAEngine_create` | `00020034` |
| `…_ics_NativeIVONAEngine_destroy` | `0002005c` |
| `…_ics_NativeIVONAEngine_stop` | `00020080` |
| `…_ics_NativeIVONAEngine_setContrast` | `00020098` |
| `…_ics_NativeIVONAEngine_onLoadLanguage` | `000200b8` |
| `…_ics_NativeIVONAEngine_getSampleRate` | `00020174` |
| `…_ics_NativeIVONAEngineICS_synthesizeText(Ljava/lang/String;[BLjava/util/List;I)` | `0002019c` |
| `…_ics_NativeIVONAEngineICS_synthesizeText(Ljava/lang/String;[B)` | `000202a0` (tail-calls the other) |
| `…_ics_NativeIVONAEngineICS_setProperty` | `000202b0` |
| `…_ics_NativeIVONAEngine_getVersion` | `00020330` |
| `…_ics_NativeIVONAEngine_onGetLanguage` | `000203bc` |
| `…_ics_NativeIVONAEngine_setEnvRuntime` | `000204bc` |
| `…_config_ConfigXMLDataSet_getSettingsCfg` | `00023148` |
| `…_config_ConfigXMLDataSet_getPackagesCfg` | `0002321c` |
| `…_packages_IvonaPackagesInfo_isoemn` | `000236d4` → returns constant `0` |
| `…_packages_IvonaPackagesInfo_getVoicesApiVersion` | `000236fc` |
| C: `getTtsEngine` | `0001cfe4` |

## 2. The facade object (`TtsEngineWithMarks`)

Singleton pointer `DAT_000842c4`, created by `FUN_0001cf48()` (function-local static, vtable
`PTR_LAB_0001c194_1_00081668` at `.data.rel.ro` file offset `0x70668`). `create()` then calls
`FUN_0001cec0(handle, 0x1fac1, 0)` — `0x1fac1` is the Thumb pointer of the audio callback
`FUN_0001fac0`; `FUN_0001cec0` stores it in `DAT_000840bc` and clears `DAT_000840c0`
(alternate 7-arg callback, unused in this build), logs `init called with NULL callback pointer`
if the pointer is 0.

| vtable | target | semantics |
|---|---|---|
| `+0x00` | `FUN_0001c194` | dtor (not emitted by Ghidra; label only) |
| `+0x04` | `FUN_0001c1a4` | deleting dtor (sets `PTR_LAB_0001c104`, `operator_delete`) |
| `+0x08` | `FUN_0001c59c` | last-error string — used as `(**(jt+8))()` before `could not create streamer: %s` (mirrors `tts_errmsg`) |
| `+0x0c` | `FUN_0001c504` | release/destroy instance (called from `destroy()` after `+0x10`) |
| `+0x10` | `FUN_0001c4ec` | `stop()` (JNI `stop` calls only this) |
| `+0x14` | `FUN_0001db6c` | unknown `[INFERENCE]` |
| `+0x18` | `FUN_0001c190` | unknown; `FUN_0001c174` forwards to `this->obj+0x2c` |
| `+0x1c` | `FUN_0001e90c` | `loadLanguage(lang, country, variant)` (§5) |
| `+0x20` | `FUN_0001c394` | `getLanguage()` → copies `*(DAT_000840ac+0xc)` / `+0x10`, variant always `""` |
| `+0x24` | `FUN_0001c544` | `getSampleRate()` — default `*out=16000`, `rate=1`, `channels? =1`; queries junction `+0x34` when a voice is loaded |
| `+0x28` | `FUN_0001c2c4` | `setProperty(key, value)` (§3) |
| `+0x2c` | `FUN_0001c1d4` | `getProperty(key, buf, size_t *iosize)` — recovered with `scripts/DecompAt.java` (Ghidra had not emitted it); see §3.1 |
| `+0x30` | `FUN_0001c8f0` | `synthesizeText(text, short* buf, int bytes, int marksEnabled)` (§4) |

`getTtsEngine()` (`0001cfe4`): returns the singleton; picks a different object when
`FUN_0001c8ac() == 4` (`FUN_0001cfa0()` → object with `PTR_FUN_0001cf04`), i.e. an
`android_version`-dependent variant `[INFERENCE]`. `FUN_0001c8ac()` reads
`/data/data/com.ivona.tts/files/.android_version` (`FUN_0001c424("android_version", …)`,
format `"%s.%s"` on `"<parentDataDir>/com.ivona.tts/files/"`) and `atoi`s it; `-1` when absent.

## 3. Properties (`FUN_0001c2c4`, also reachable through JNI `setProperty`)

| key | global | rule |
|---|---|---|
| `rate` | `DAT_00084004` | `atoi`; if `<=0` → `100` |
| `volume` | `DAT_00084008` | same |
| `pitch` | `DAT_0008400c` | same |

Returns `0` on success, `-3` if value is NULL, `-4` for unknown keys. During synthesis the bridge
computes `dur_stretch = 100.0f / rate` and `pitch_stretch = 100.0f / pitch` and pushes them into
the voice object (`FUN_0001c668(voice, "dur_stretch"/"pitch_stretch", v)`).
`setContrast(int)` goes through `FUN_0001cf1c` → `FUN_0001eea6` when `DAT_000840b8 != 0`; the
strings `set:contrast`, `could not set contrast: %s`, `could not adjust quality: %s`,
`could not adjust responsiveness: %s`, `could not adjust volume: %s` (literals at
`0001f2c8`, `0001ebdc`, `0001eb70`, `0001eb94`, `0001ebb8`) show the extra tunables the voice
object accepts.

## 3.1 `getProperty` — `FUN_0001c1d4` (facade `+0x2c`, recovered)

```c
int getProperty(const char *key, char *buf, size_t *iosize)   /* this = facade */
{
    if (!key)    { log("...getProperty called with NULL property"); return -4; }
    if (!buf)    { log("...getProperty called with NULL value");    return -3; }
    if (!iosize) { log("...getProperty called with NULL iosize");   return -3; }
    if      (!strcmp(key, "rate"))   n = snprintf(buf, *iosize, "%d", DAT_00084004);
    else if (!strcmp(key, "volume")) n = snprintf(buf, *iosize, "%d", DAT_00084008);
    else if (!strcmp(key, "pitch"))  n = snprintf(buf, *iosize, "%d", DAT_0008400c);
    else return -4;
    return (n <= (int)*iosize) ? 0 : -5;      /* -5 = buffer too small */
}
```

So the property surface is exactly `rate|volume|pitch`, integer percent, symmetric with
`setProperty` (§3); it is not exercised by the Java layer of this build (the app only calls
`setProperty`).

## 4. Synthesis loop — `FUN_0001c8f0` (facade `+0x30`)

```
junction = FUN_000234c0(0)                 ; loads libttsivonavoice.so (§6)
  err → "Cannot load voice junction."
if first run (android_version in [0,8)): DAT_000840c8 = enabled flag (set to 1) and the 16 doubles
  at DAT_000840d0..0008414c are written as *immediate* constants into .bss (they are NOT in the file,
  being runtime-initialised); the 6 state doubles DAT_00084150..0008417c are zeroed. See §4.1.
NULL checks → "…NULL string" / "…NULL buffer" / "…callback not set" / "…voice not loaded"
dur_stretch = 100/rate ; pitch_stretch = 100/pitch
streamer = junction->vtable+0x58  ( == tts_streamer_start; see report_engine_api.md §1 )
             (voice=DAT_000840b4, text, -1.0f)
  fail → error string from junction->vtable+0x8, log "could not create streamer: %s"
bytes >>= 1                                   ; byte count → 16-bit sample count
if marksEnabled: streamer->prealloc(samples)  (FUN_0001ee9a)
bind streamer to voice                        (FUN_0001edc8)
sampleRate = junction->vtable+0x34(voice)      ( == tts_voice_sample_rate )
loop:
  while produced < samples:
      n = streamer->step()                   (FUN_0001edf8 / FUN_0001ee00)
      if none left → break
      if !marks: streamer->pull(buf + off, remaining)   (FUN_0001f540)
      else:      mark = streamer->pull_marks()          (FUN_0001edee)  {+4 len, +8 data}
  if marks && produced: memcpy(buf, mark->data, produced*2)
  if DAT_000840c8: apply fixed IIR filter in place, saturate to int16
                   (coefficients from DAT_000840d0..8414c, state 84150..8417c)
  callback(userdata, sampleRate, 1, 1, &buf, &producedBytes, marksObj, 1)     ; DAT_000840bc
until streamer exhausted
final callback(..., bytes = 0) → signals end
```

The callback trampoline `FUN_0001fac0` (8 args) converts `marksObj` into Java `SpeechMark`s (§7)
and then calls `FUN_0001fa84`, which does `CallIntMethod(env, obj, audioAvailableClbk, length)`
(`FUN_0001fa42`) and frees the per-call struct when `status==0`.
Return codes seen by Java: `audioAvailableClbk(len, status)` with `status==0` = *synth done*.

## 4.1 Post-filter constants and formula (facade `FUN_0001c8f0`)

The loop applies, per sample `x` (as `double`), using four state doubles `s0..s3`
(stored in `.bss` at `DAT_00084150…0008417c`):

```
y = (x - (D12*s0 + D13*s1 + D14*s2 + D15*s3)) / D11
s3 = s2; s2 = s1; s1 = s0; s0 = y        /* 4-tap direct-form IIR */
y is then saturated to int16 into the output buffer
```

Constants, reconstructed from the immediate words in `FUN_0001c8f0` (word pairs are
`lo @addr`, `hi @addr+4`, little-endian double):

| const | Ghidra addr | value |
|---|---|---|
| D0 | `000840d0` | 0.3548133969306946 |
| D1 | `000840d8` | 0.43196899923127224 |
| D2 | `000840e0` | 0.4186597466468811 |
| D3 | `000840e8` | 0.908143162727356 |
| D4 | `000840f0` | 0.5956621766090393 |
| D5 | `000840f8` | 0.7770821339973708 |
| D6 | `00084100` | −1.3309413324533708 |
| D7 | `00084108` | 0.6001155631387476 |
| D8 | `00084110` | 1.0182713706162865 |
| D9 | `00084118` | 1.1703558402494565 |
| D10 | `00084120` | −0.5195118187237462 |
| D11 | `00084128` | 4.578831280665736 (divisor / a0) |
| D12 | `00084130` | −7.842357376587231 |
| D13 | `00084138` | 3.5360842725581536 |
| D14 | `00084140` | 1.1493555392224415 |
| D15 | `00084148` | −0.510189949079412 |

The role of D0…D10 is `[INFERENCE]`: `FUN_0001c8f0` writes all 16 (they are two coefficient sets —
one for the `android_version ∈ [0,8)` path, the other presumably for the other `getTtsEngine`
variant); only D11…D15 are read by the loop above. Reproducing the filter exactly therefore needs
only D11…D15 plus the update order and the `int16` saturation (values above are bit-exact).

## 5. Language matching — `FUN_0001e90c` (facade `+0x1c`)

1. `FUN_000234c0(0)` (junction) or log `Cannot load voice junction.`
2. `FUN_0002434c(1)` → refresh + return the voice-package list
   (`std::deque<boost::shared_ptr<CVoiceDataSimple>>`, global `DAT_000842dc`).
3. `FUN_0001e65c(list, lang, country, variant, out)` filters candidates.
4. For each candidate it builds (and lower-cases) the package name:
   `"com.ivona.tts" + ".voicebeta." + <entry+0xc> + "." + <entry+0x10> + "." + <entry+0x14>`
   (literals `0001e9d2` `"com.ivona.tts"`, `0001e9dc` `".voicebeta."`, `0007c99f` `"."`), i.e. the
   3-letter language / 3-letter country / voice name triple parsed straight out of the package name
   (`com.ivona.tts.voicebeta.eng.usa.kendra`).
5. If the candidate's flag `*(entry+8)` is set and `FUN_0001d0a2(...)` agrees, the voice is loaded:
   old streamer freed (`FUN_0001ef6c` / `operator_delete`), new one allocated (`operator_new(0x6c)`,
   ctor `FUN_0001efc4`) into `DAT_000840b8`, then `FUN_00023284()` (license, §8),
   `junction->vtable+0x28` ( == tts_load_voice ) with the vox path from `FUN_00023c10` (§6).
6. Errors logged: `could not load voice: %s`, `no voice matching requested locale found`,
   `could not load any available voice`.

`getLanguage` returns `""` for country-variant and only the current voice's stored lang/country.

## 6. Voice-junction loader — `FUN_000234c0`

Globals: `DAT_000842cc` = engine object from the voice library, `DAT_000842c8` = TTS instance,
`DAT_000842d0` = `dlopen` handle, `DAT_000842d8` = voice package name (std::string),
`DAT_000842d4` = second path string, `DAT_00084308`/`DAT_0008430c` = base dirs.

* defaults set by `_INIT_3` (`FUN_0002444c`): `"/data/data/"`, `"/sdcard/"`; both overwritten by
  `setEnvRuntime` (`FUN_0004d3fc` = `std::string::assign`).
* if `DAT_000842d8` empty → `FUN_0002434c(1)` refreshes the list from `ivona_pkgs.csv` (§7) and
  copies field `+0x4` of the first entry.
* `path = DAT_00084308 + DAT_000842d8 + "/lib/libttsivonavoice.so"` (literals `0002357e` …,
  `000235d0` `Cannot use voice library`) → `dlopen(…, RTLD_NOW)` → `dlsym("v")` → `engine = v()`.
  Failures: `Cannot open library: %s` (with `dlerror`).
* `FUN_00023284()` then decodes the license (§8), calls `engine->vtable+0x0c(certText)` and caches
  the result as `DAT_000842c8`; errors `could not prepare data for TTS instance`,
  `could not init TTS instance: %s`, `Failed to get voice handle.`.
* `libtiver.so` is dlopened for package/version queries (`000238d2`) and for vox-path resolution;
  `dlsym` names are the single letters **`"v"`** (`00023f10`) and `"h"` (`0007cf9c` in
  `getVoicesApiVersion`).

Vox file path (`FUN_00023cac`), based on the type stored at `*(voice_struct+0)`:

| type | path |
|---|---|
| `1` | `"/sdcard/" + <voice_struct+3 string>` |
| `2` | `"/sdcard/" + <*voice_struct+4 string> + <voice_struct+3 string>` (i.e. `…/Android/obb/<pkg>/…`) |
| other | log `An error occured on determinig path to vox file.` and return `""` |

Fragments used elsewhere: `"ivona/"` (`00023772`), `"Android/obb/"` (`0002377e`), `"/lib/"`,
`"/"`, `"%d;%d;"`, `";"`, `";%d"`.

## 7. Voice-package cache — `FUN_000240b8` (via `FUN_0002434c`)

Reads `path = <base std::string> + "com.ivona.tts/files/" + "ivona_pkgs.csv"`
(literals `0001c450`, `000240ee`) line by line, splits on `";"`:

* first line skipped (header),
* token 2: `sscanf %d`, must be `<= 2` else the whole line is discarded,
* token 3: `sscanf %d`; `== 0` sets flag byte at `entry+2`,
* token 6: `sscanf %d`, accepted only as `1` or `2` (else 0) and stored at `entry+0`
  — this is the **vox path type** consumed by `FUN_00023cac` (§6).

Populated objects are `CVoiceDataSimple` (0x18 B: `int type; std::string a; char flag;
std::string b,c,d` … field `+0xc/+0x10/+0x14` are the lang/country/voice strings used in §5).
The Java side of the same file (`report_engine_app.md` §5.1/§5.3) shows
`pkg;versionCode;apiVer;fstate;name;SDK` — so lines carry at least 7 `;`-fields `[INFERENCE]`
on the exact native column order.

## 8. Embedded Certificate of Authenticity

`FUN_00023284` (Ghidra `00023284`) de-XORs 1798 bytes and passes them to `engine->vtable+0x0c`:

```python
KEY, D, D2 = 0x6d070, 0x6d079, 0x6d07d          # ELF vaddrs == file offsets in .rodata
length = 0
for i in range(4):
    length |= ((d[KEY+(i+5)%9] ^ d[KEY+i%9] ^ d[D+i]) & 0xff) << (8*i)   # == 1798
out = bytes(d[D2+i] ^ d[KEY+(i+4)%9] for i in range(length))
```

Decoded text → `out/certs/ivona_certificate_decoded.txt` (Product IVONA, Certificate-ID a1169787,
threads/speed UNLIMITED, Expiration NEVER, Voices ALL, Extension-SSML TRUE, signature block of 14 lines / 1040 hex chars = 520 B, i.e. RSA-4096).
Engine-side strings about it live in `libttsivonavoice.so`
(`The certificate does not allow for SSML input`, `Invalid certificate of authenticity`, …).

## 9. Configuration XML

`FUN_00022ec8`: `fopen("/etc/ivona/ivona_config.xml")` → on failure `getSettingsCfg`/`getPackagesCfg`
return `null` (no APK-side copy exists; `unzip -l` shows no `assets/`).
Element names used: `ivona_config` (`0x6ce81`), `global` (`0x6ce8e`), `packages` (`0x6ce95`),
`package` (`0x6ce5d`, attribute `name` `0x6cc36`), settings keys `voice_data` (`0x6ce9e`),
`voice_lib` (`0x6cea9`), `lex_dir` (`0x6ceb3`), `ca` (`0x6cebb`).
`getSettingsCfg` returns `String[4] = {voice_data, voice_lib, lex_dir, ca}`;
`getPackagesCfg` returns one `"name"` per `<package>` child of `<packages>`.

## 10. Speech-marks marshalling — `FUN_0001fac0` / `FUN_0001fa84`

Record layout produced by the voice engine (stride `0x14`):

```
+0x00 int   type          (0..4)
+0x04 char* name (NUL-terminated; 0 → Java null)
+0x08 int   startTextOffset
+0x0c int   endTextOffset
+0x10 int   sampleOffset   (added to the running sample counter puVar1[4])
```

For each record, if the bit `1 << type` is set in the mask passed to `synthesizeText`, a
`android.speech.tts.SpeechMark` instance is created, fields set
(`type` via static field lookup on the SpeechMark class, `sampleOffset`, `startTextOffset`,
`endTextOffset`, `name`), and added to the Java `ArrayList` (which is `clear()`ed at the start of
each callback invocation). Field-name literals: `sampleOffset` (`0x7cc0f`), `startTextOffset`
(`0x7cc5e`), `endTextOffset`, `SpeechMark.type` (`0x7cbff`), `SpeechMark.name` (`0x7cc4e`),
class `android/speech/tts/SpeechMark` (`0x7cbb7`). Errors: `marks error: %s`.

## 11. Log/activation client

`FUN_0001f6e0(name)` — `socket(AF_UNIX=1, SOCK_STREAM=1, 0)`, `connect` to
`sun_path = name`, sets `SO_PASSCRED` (`setsockopt(SOL_SOCKET, 0x10)`) and `recvmsg`s one byte
(cred handshake). Names: `"%s.log"` with `com.ivona.tts` when `android_version < 14`,
else `"%s.%u.log"` with `getuid()`.
`FUN_0001f82c(type, status, str, out)` builds a 12-byte (or `12+len(str)`) body
(`*(u32)type, *(u32)status, byte 2, cstring`), encrypts it with `FUN_0001f5bc` into a
`body+0x30` buffer (0x30-byte header — matches the Java parser in `report_engine_app.md` §9.4),
`write()`s it, then reads a `u32` length (>11) + payload, decrypts with `FUN_0001f65c`, and if
`payload[8] == 2` splits the string at offset 9 on `\n`.
Java server side: `report_engine_app.md` §4.3/§9.3.

## 12. Misc verified facts

* `getVersion()` returns `{"IVONA_DIR", "0ff4b2c4fa69f57df9ccbe30ee665658f7b1ee49"}` — the only
  place these literals occur; no Java caller exists in the APK.
* `isoemn()` returns `0` unconditionally (an OEM flag).
* `getSampleRate()` default is **16000** (`FUN_0001c544` pre-fills the out-params with `1`, `0`, `16000`, `1` before delegating to junction `+0x34`);
  the Kendra voice OBB header stores **22050**.
* `onLoadLanguage` maps the native return to Android's convention: `>= -3` passed through,
  otherwise `-1`/`-2` are returned negated (Java sees `1`/`2`).
* `setEnvRuntime(a, b)` → `DAT_00084308 = a`, `DAT_0008430c = b`; failure logs
  `Could not prepare runtime`.
* Native log tag for everything: `IVONATTS` at priority 6 (ERROR).

## 13. Not determined

* bodies of `FUN_0001c194`, `FUN_0001c59c`, `FUN_0001c504`, `FUN_0001c4ec`, `FUN_0001db6c`,
  `FUN_0001c190` — Ghidra did not emit them as functions; only string literals and the vtable
  slots above pin them down. (`FUN_0001c1d4`/`getProperty` is now fully recovered, §3.1.)
* the exact meaning of the 22 filter coefficients in `FUN_0001c8f0` (looks like a fixed
  multi-section IIR/resampler enabled only for `android_version ∈ [0,8)`).
* which column of `ivona_pkgs.csv` is token 6 on disk (Java only documents 6 columns).
* who sends encrypted activation messages (no sender inside these three APKs).
