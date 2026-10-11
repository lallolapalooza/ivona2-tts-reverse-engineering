# libtiver.so — reverse-engineering report

Target: `out/libs/{amy,kendra}/libtiver.so`, MD5 `b381ee3b994d615c997f1b0ddd1b09bd` (byte-identical in every IVONA 2 voice-pack APK; verified with `md5sum` on both copies). ELF 32-bit LSB ARM EABI5 shared object, stripped, 124 164 bytes.

Evidence sources (all addresses cited in both notations):

* Ghidra decompilation `out/ghidra_dump/libtiver.c` — **dump addresses** here are link addresses + 0x10000 (Ghidra base), so *ELF address = dump address − 0x10000* (confirmed: `readelf -S` puts `.text` at 0x66a0 / dump 0x166a0; the Ghidra log `out/ghidra_tiver.log:57` shows the import with base 0x10000).
* Direct Thumb disassembly of the binary with Capstone (scripts under `scripts/`: `disasm_169b8.py`, `disasm_range.py`, `parse_table.py`, `parse_data_struct.py`, `dump_full_table.py`; decoded table in `scripts/table_full.json`).
* Raw section/`readelf` decoding (`.data` voice-info struct, `.data.rel.ro.local` package table, R_ARM_RELATIVE relocation addends).
* Java callers: `out/jadx_{amy,kendra}/sources/com/ivona/tts/voicelib/VoiceFiles.java` (voice APK), `out/ghidra_dump/decompiled.c` (= `out/tts/lib/armeabi/libttsivona.so`, engine native) + `out/jadx_tts/sources/com/ivona/ttslib/packages/IvonaPackagesInfo.java`.
* Real OBB artifacts in `IVONA 2/*/Android/obb/<pkg>/` (amy & kendra main+patch obbs) used to verify sizes and patch contents.

Everything below is **observed** unless marked `[INFERENCE]`.

---

## 1. Exported API

`readelf -sW` (all Thumb, bit0 set in symbol value):

| Symbol | ELF addr | dump addr | Size |
|---|---|---|---|
| `v` | 0x66dc (sym 0x66dd) | 0x166dc | 12 |
| `h` | 0x6a58 (sym 0x6a59) | 0x16a58 | 10 |
| `Java_com_ivona_tts_voicelib_VoiceFiles_checkFiles` | 0x6a64 (sym 0x6a65) | 0x16a64 | 196 |

Everything else is bundled minizip (`unz*`, `fill_fopen_filefunc`, …), libc++abi, and gnustl string helpers; zlib (`inflate`, `crc32`, `inflateInit2_`, `get_crc_table`) is imported from the system `libz.so`.

### 1.1 `v` — fetch the voice-info struct

Dump 0x166dc:

```c
undefined * v(void) { return &DAT_0002f004; }
```

`DAT_0002f004` = ELF **0x1f004** = `.data + 4` (`.data` is at 0x1f000, file offset 0x1e000, 0x20 bytes, statically initialized — no constructor needed). Signature: `uint32_t* v(void)`.

### 1.2 `h` — check + patch one voice package

Decompiler shows 4 dummy params, but the Thumb body (ELF 0x6a58) is:

```asm
h:  push {r3, lr}
    movs r2, #0          ; applyFlag = 0
    bl   0x69b8          ; FUN_000169b8(pkg, basePath, 0)
    pop  {r3, pc}        ; returns r0
```

Signature: **`int h(const char* packageName, const char* basePath)`** — extra register args ignored; **returns the int result of `FUN_000169b8` with flag 0** (i.e. “force-apply patch”). The engine treats the return as 0 = success / nonzero = not present (see §5).

### 1.3 `Java_…_VoiceFiles_checkFiles` — JNI entry from the voice APK

```c
// dump 0x16a64; params: (JNIEnv*, jclass, jstring pkgName, jstring basePath)
```

Behavior (disasm ELF 0x6a64..0x6b28 matches decompile):

1. `GetStringUTFChars(arg3)` → if NULL: log `"Failed to obtain package name."`, return **-2** (0xfffffffe).
2. `GetStringUTFChars(arg4)` → if NULL: release arg3, log `"Failed to obtain path to files."`, return **-2**.
3. Builds `path = basePath + "Android/obb/"` (literal `"Android/obb/"` at ELF 0x18ccc; the Java caller passes `<sdcard-absolute-path> + "/"`, so the result is e.g. `/storage/emulated/0/Android/obb/`).
4. `r = FUN_000169b8(pkg, path, 1)` — flag **1** (“check-first”, as opposed to h’s 0).
5. Releases both UTF strings, destroys the temp std::string, returns `r` to Java **as a plain int**:

| return | meaning |
|---|---|
| 0 | main obb present with exact expected size **and** patch zip opened & all entries extracted without error |
| 1 | package not found / obb missing / obb size mismatch |
| -1 | patch open/read/write error (details in logcat) |
| -2 | NULL jstring argument |

Java side (`VoiceFiles.a(Context)` in the voice APK, jadx_amy/kendra `VoiceFiles.java:16-71`): derives the voice package name from its own class name (walks back 3 dots; `checkFiles` receives the full package name, e.g. `com.ivona.tts.voicebeta.eng.usa.kendra`), deletes legacy files `<sdcard>/ivona/<vox>` and `<sdcard>/ivona/<lang.dat>` (names from class `q`), then `checkFiles(substring, Environment.getExternalStorageDirectory().getAbsolutePath() + "/")` and returns **`checkFiles == 0`**. The native lib is loaded by `System.loadLibrary("tiver")` in `VoiceFiles`’s static initializer. All native logging uses `__android_log_print(6 /*ANDROID_LOG_INFO*/, "IVONAVOICE", …)`.

---

## 2. Voice-info struct returned by `v`

`.data` (ELF 0x1f000, 32 bytes) decoded with R_ARM_RELATIVE addends (`readelf -rW` shows RELATIVE relocs at 0x1f00c, 0x1f014, 0x1f018, 0x1f01c):

| struct idx | addr | raw / relocated value | meaning |
|---|---|---|---|
| (word before) | 0x1f000 | 0 | padding / `__dso_handle` region |
| [0] | 0x1f004 | 20 (0x14) | **ABI version gate** — engine requires `> 0x13` (19) |
| [1] | 0x1f008 | 2 | **apiVersion / table-access mode** — engine requires `< 3` |
| [2] | 0x1f00c | ptr → ELF 0x18cd9 = `"20130201_150739"` | **build stamp string** (`.rodata`), passed through to Java verbatim |
| [3] | 0x1f010 | 48 (0x30) | **table entry stride in bytes** — engine requires `> 0x2f` (47) |
| [4] | 0x1f014 | 0x66c5 (Thumb ptr → ELF 0x66c4) | **voice-table accessor function** (see below) |
| [5] | 0x1f018 | 0xb554 → ELF 0xb554 = `terminate` | cxxabi handler pointer stored in `.data` — **not** read by any libtiver/voice-code path `[INFERENCE: adjacent C++ runtime data]` |
| [6] | 0x1f01c | 0xdc64 → ELF 0xdc64 = `__verbose_terminate_handler` | same |

So the engine-visible struct is 5 words (20 bytes): `{uint32 abi=20; uint32 apiVer=2; const char* buildStamp; uint32 stride=48; void* entryAccessor;}`.

**Accessor function** at ELF 0x66c4 (Thumb), passed as `struct[4]`, called by the engine as `entry = accessor(i)`:

```asm
        movs r3, #0
        cmp  r0, #0x2b          ; if (i > 43) return NULL
        bhi  +0xc
        movs r2, #0x30          ; stride 48
        ldr  r3, [pc, #8]       ; -> 0x16e64
        muls r0, r2, r0
        add  r3, pc             ; base = 0x16e64 + 0x66d4 = 0x1d538  (the package table!)
        adds r3, r3, r0
        adds r0, r3, #0
```

i.e. `entry(i) = &table[i]` for `i ≤ 43`, else NULL — the same 48-byte table at ELF 0x1d538 described in §4. (Mode `struct[1]==1` would instead treat `struct[4]` as a direct table pointer — engine function `FUN_00023a70`, decompiled.c 10363; our build uses mode 2 → `FUN_00023a94`, decompiled.c 10385, which calls `struct[4]` as a function pointer and `strcmp`s `entry+0x10` = field [4].)

---

## 3. Core logic: `FUN_000169b8` (dump 0x169b8 / ELF 0x69b8)

`int FUN_000169b8(const char* pkg, const char* baseDir, int applyFlag)` — shared by `h` (flag 0) and `checkFiles` (flag 1):

1. `pkg == NULL || baseDir == NULL` → return **-1** (0xffffffff; disasm `movs r4,#1; rsbs r4,r4,#0`).
2. **Table lookup**: walk 48-byte rows from ELF 0x1d538 while `row[0] != 0 && strcmp(pkg, *(row+0x10)) != 0`; `row += 0x30`. Field `row+0x10` = dword [4] = package name.
   *Packages not in the table* land on the all-zero terminator row (§4) and path construction then uses a NULL obb-name pointer → undefined behavior (likely crash). All real callers only pass known packages `[INFERENCE]`.
3. **Main-obb path** = `baseDir + pkg + "/" + row[8]` where `row+0x20` = dword [8] = obb file name; the separator is the literal `"/"` at ELF 0x18b84.
4. `stat(path)`: fail → return **1**. Compare `st` field at **offset 0x30** with `row+0x24` = dword [9] (expected size), and require the field at **offset 0x34 == 0**. Mismatch → return **1**. *(Both offsets observed in disasm: stat buffer at `sp+8`, operands at `sp+0x38`/`sp+0x3c`. The compiled struct evidently has the 64-bit size at +0x30, so the check is “low 32 bits of st_size == expected table size AND next word (high half) == 0” — i.e. exact byte-size match, files < 4 GiB. `[INFERENCE on the C mapping; the offsets and semantics are disasm-confirmed]`.)*
5. Size OK → `return FUN_000166e8(row, baseDir, applyFlag)` (§3.1).

Net contract: **0 = installed+patched OK, 1 = absent/size mismatch, -1/-2 = errors.**

### 3.1 `FUN_000166e8` (dump 0x166e8 / ELF 0x66e8) — patch extraction

`int FUN_000166e8(row, baseDir, applyFlag)`:

1. NULL row/baseDir → return **-2** (0xfffffffe).
2. **Patch path** = `baseDir + pkg + "/" + "patch.199." + pkg + ".obb"`.
   Literals: `"patch.199."` @ ELF 0x18b86, `".obb"` @ 0x18b91. **The patch version 199 is hardcoded in C** and independent of the main-obb `N` in the table (183/199/422). Verified on disk: `IVONA 2/*/Android/obb/<pkg>/patch.199.<pkg>.obb` exists for both amy and kendra.
3. `unzOpen(patchPath)` fails → log `"Error on opening patch file:%s"` → return **-1**. (A missing patch file is therefore an error, not “no patch”: `h`/`checkFiles` return -1 for a voice whose main obb is fine but which has no `patch.199.…obb` next to it `[INFERENCE from control flow]`.)
4. `unzGetGlobalInfo` fails → log `"Error %d on reading patch data"` → -1.
5. `malloc(0x2000)` copy buffer; iterate every zip entry:
   * `unzGetCurrentFileInfo` (name buffer 0x100) fails → log `"Error %d on getting file info"` → -1.
   * Entry name containing `'/'` or `'\\'` → **skipped** (only flat entries extracted; incidentally blocks zip-slip).
   * Target file = `baseDir + pkg + "/" + entryName` (no directory creation — `<base>/<pkg>/` must already exist, which it does because the main obb is there).
   * **Skip test** (only when `applyFlag != 0`): `stat(target)` succeeds **and** size-field@0x30 == the zip entry’s `size_filename` (unz_file_info dword at +0x1c — the *length of the entry name*, standard minizip layout) **and** field@0x34 == 0 → skip re-extraction. Comparing a data file’s byte size against the entry-name length is essentially never true, so **entries are re-extracted on every call even with flag=1** (likely a bug in the original — intended offset was probably +0x18 uncompressed_size; faithful reimplementations should copy the observed behavior). With `applyFlag==0` (the `h` path) extraction is unconditional.
   * `unzOpenCurrentFile` < 0 → log `"Error opening current file!"` → -1.
   * `fopen(target,"wb")` NULL → log `"Error creating file:%s"` → -1.
   * Copy loop `unzReadCurrentFile(8 KiB)` → `fwrite`; read error → log `"Error reading patch file:%s"` (entry name) → -1; short write → log `"Error on writting file:%s."` (target path), `fclose`, → -1. Loop ends when read returns 0.
   * `unzCloseCurrentFile` — its UNZ_CRCERROR (-105) return **is ignored** by this caller (disasm 0x6896: result unused), so CRC mismatches do not fail patching; `fclose`, destroy target string.
   * `unzGoToNextFile`: -100 (`UNZ_END_OF_LIST_OF_FILE`) → done; 0 → next; else log `"Error %d on switching to next file"` → -1.
6. `free` buffer, `unzClose`, destroy path strings, return **0** (all entries OK).

---

## 4. The hardcoded package→OBB table

Location: ELF **0x1d538** (dump 0x2d538), section `.data.rel.ro.local` (file offset 0x1c538 — note the −0x1000 file/vaddr delta for this section; `.rodata` has none). 48-byte rows = 12 little-endian dwords; pointer dwords are R_ARM_RELATIVE to `.rodata` strings (vaddr == file offset in `.rodata`). Row 42 (ELF 0x1dd18) is all-zero = terminator; the walk in `FUN_000169b8` stops when dword [0] == 0. Full decoded content also in `scripts/table_full.json`.

Field layout (byte offset → meaning; fields used by libtiver itself are **bold**, fields consumed by the engine via the accessor are *): [0] **package-name-walk sentinel** / ISO 639-3 language*, [1] ISO 3166-3 country*, [2] short voice name*, [3] display name (UTF-8)*, [4] **Android package name (strcmp key)**, [5] voice-lib filename* (e.g. `libvoice_en_us_kendra.so`), [6] voice-lib byte size* (verified: kendra 3085840 = on-disk `libvoice_en_us_kendra.so`, amy 3073872 = on-disk lib), [7] second, slightly different size — meaning unresolved `[INFERENCE]`, not referenced by any traced code, [8] **main OBB filename**, [9] **expected main OBB byte size** (verified: amy 149905560 = `stat` of the real obb; kendra 152219597 = real obb), [10] lexicon filename* (`english.lex`, …), [11] localized trial-expired message* (one shared UTF-8 string per language).

Note dword [0] is the *pointer to `"IVONAVOICE"`* (ELF 0x18b99) for every real row — any non-zero value works as the sentinel.

### Table content (42 rows)

`lang | country | name | display | package | voice lib | lib size | size2 | main obb | obb bytes | lexicon`
(trial message per language: English rows share "The trial period of the IVONA voice has expired. You can still enjoy the high quality IVONA voice by simply updating it through the Google Play."; other languages have localized equivalents — full text in `scripts/table_full.json`)

| # | lang | ctry | name | package | voice lib | libsz | sz2 | main obb | obb bytes | lex |
|---|---|---|---|---|---|---|---|---|---|---|
|0|cym|GBR|geraint|"IVONA Geraint"|com.ivona.tts.voicebeta.cym.gbr.geraint|libvoice_cy_geraint.so|888276|929008|main.422.…gy.obb|183535422|welsh.lex|
|1|cym|GBR|gwyneth|"IVONA Gwyneth"|com.ivona.tts.voicebeta.cym.gbr.gwyneth|libvoice_cy_gwyneth.so|894308|930896|main.199.…|200948617|welsh.lex|
|2|dan|DNK|mads|"IVONA Mads"|com.ivona.tts.voicebeta.dan.dnk.mads|libvoice_da_mads.so|2798488|2808984|main.422.…|244758366|danish.lex|
|3|dan|DNK|naja|"IVONA Naja"|com.ivona.tts.voicebeta.dan.dnk.naja|libvoice_da_naja.so|2798488|2808984|main.422.…|224192234|danish.lex|
|4|deu|DEU|hans|"IVONA Hans"|com.ivona.tts.voicebeta.deu.deu.hans|libvoice_de_hans.so|1332844|1341888|main.422.…|137986884|german.lex|
|5|deu|DEU|marlene|"IVONA Marlene"|com.ivona.tts.voicebeta.deu.deu.marlene|libvoice_de_marlene.so|1325216|1332096|main.199.…|150077998|german.lex|
|6|eng|AUS|nicole|"IVONA Nicole"|com.ivona.tts.voicebeta.eng.aus.nicole|libvoice_en_au_nicole.so|3073736|3085852|main.199.…|149745872|english.lex|
|7|eng|AUS|russell|"IVONA Russell"|com.ivona.tts.voicebeta.eng.aus.russell|libvoice_en_au_russell.so|3071620|3083068|main.422.…|141372541|english.lex|
|8|eng|GBR|amy|"IVONA Amy"|com.ivona.tts.voicebeta.eng.gbr.amy|libvoice_en_gb_amy.so|3073872|3086172|main.199.…|149905560|english.lex|
|9|eng|GBR|brian|"IVONA Brian"|com.ivona.tts.voicebeta.eng.gbr.brian|libvoice_en_gb_brian.so|3074092|3086300|main.422.…|157007845|english.lex|
|10|eng|GBR|emma|"IVONA Emma"|com.ivona.tts.voicebeta.eng.gbr.emma|libvoice_en_gb_emma.so|3073872|3086172|main.422.…|145308445|english.lex|
|11|eng|USA|chipmunk|"IVONA Chipmunk"|com.ivona.tts.voicebeta.eng.usa.chipmunk|libvoice_en_us_chipmunk.so|3086204|3099004|main.422.…|135037254|english.lex|
|12|eng|USA|eric|"IVONA Eric"|com.ivona.tts.voicebeta.eng.usa.eric|libvoice_en_us_eric.so|3087080|3099484|main.422.…|166309115|english.lex|
|13|eng|USA|ivy|"IVONA Ivy"|com.ivona.tts.voicebeta.eng.usa.ivy|libvoice_en_us_ivy.so|3069900|3081468|main.422.…|146211477|english.lex|
|14|eng|USA|jennifer|"IVONA Jennifer"|com.ivona.tts.voicebeta.eng.usa.jennifer|libvoice_en_us_jennifer.so|3046816|3057980|main.422.…|66907906|english.lex|
|15|eng|USA|joey|"IVONA Joey"|com.ivona.tts.voicebeta.eng.usa.joey|libvoice_en_us_joey.so|3086264|3099772|main.422.…|149182268|english.lex|
|16|eng|USA|kendra|"IVONA Kendra"|com.ivona.tts.voicebeta.eng.usa.kendra|libvoice_en_us_kendra.so|3085840|3099004|main.199.…|152219597|english.lex|
|17|eng|USA|kimberly|"IVONA Kimberly"|com.ivona.tts.voicebeta.eng.usa.kimberly|libvoice_en_us_kimberly.so|3083992|3099004|main.422.…|153536559|english.lex|
|18|eng|USA|salli|"IVONA Salli"|com.ivona.tts.voicebeta.eng.usa.salli|libvoice_en_us_salli.so|3070640|3082268|main.183.…|150748397|english.lex|
|19|eng|GBR|geraint|"IVONA Geraint"|com.ivona.tts.voicebeta.eng.gbr.geraint|libvoice_en_wls_geraint.so|3077812|3090236|main.422.…|138213561|english.lex|
|20|eng|GBR|gwyneth|"IVONA Gwyneth"|com.ivona.tts.voicebeta.eng.gbr.gwyneth|libvoice_en_wls_gwyneth.so|3074192|3085948|main.199.…|159038208|english.lex|
|21|spa|ESP|conchita|"IVONA Conchita"|com.ivona.tts.voicebeta.spa.esp.conchita|libvoice_es_conchita.so|416240|426372|main.199.…|126275305|spanish.lex|
|22|spa|ESP|enrique|"IVONA Enrique"|com.ivona.tts.voicebeta.spa.esp.enrique|libvoice_es_enrique.so|416652|426820|main.422.…|106429722|spanish.lex|
|23|spa|USA|miguel|"IVONA Miguel"|com.ivona.tts.voicebeta.spa.usa.miguel|libvoice_es_us_miguel.so|418996|428420|main.422.…|116132083|spanish.lex|
|24|spa|USA|penelope|"IVONA Penélope"|com.ivona.tts.voicebeta.spa.usa.penelope|libvoice_es_us_penelope.so|415492|424804|main.199.…|121236908|spanish.lex|
|25|fra|CAN|chantal|"IVONA Chantal"|com.ivona.tts.voicebeta.fra.can.chantal|libvoice_fr_ca_chantal.so|883520|895192|main.422.…|141266981|french.lex|
|26|fra|FRA|celine|"IVONA Céline"|com.ivona.tts.voicebeta.fra.fra.celine|libvoice_fr_celine.so|882324|892344|main.199.…|137349265|french.lex|
|27|fra|FRA|mathieu|"IVONA Mathieu"|com.ivona.tts.voicebeta.fra.fra.mathieu|libvoice_fr_mathieu.so|884280|891576|main.422.…|142774986|french.lex|
|28|isl|ISL|dora|"IVONA Dora"|com.ivona.tts.voicebeta.isl.isl.dora|libvoice_is_dora.so|596096|605380|main.422.…|273993035|icelandic.lex|
|29|isl|ISL|karl|"IVONA Karl"|com.ivona.tts.voicebeta.isl.isl.karl|libvoice_is_karl.so|594380|604868|main.422.…|257631105|icelandic.lex|
|30|ita|ITA|carla|"IVONA Carla"|com.ivona.tts.voicebeta.ita.ita.carla|libvoice_it_carla.so|3044948|3074628|main.422.…|154910693|italian.lex|
|31|ita|ITA|giorgio|"IVONA Giorgio"|com.ivona.tts.voicebeta.ita.ita.giorgio|libvoice_it_giorgio.so|3044248|3074276|main.199.…|139040821|italian.lex|
|32|nld|NLD|lotte|"IVONA Lotte"|com.ivona.tts.voicebeta.nld.nld.lotte|libvoice_nl_lotte.so|1811724|1821264|main.422.…|172600710|dutch.lex|
|33|nld|NLD|ruben|"IVONA Ruben"|com.ivona.tts.voicebeta.nld.nld.ruben|libvoice_nl_ruben.so|1817212|1826096|main.422.…|146604768|dutch.lex|
|34|pol|POL|agnieszka|"IVONA Agnieszka"|com.ivona.tts.voicebeta.pol.pol.agnieszka|libvoice_pl_agnieszka.so|846620|834008|main.422.…|164741811|polish.lex|
|35|pol|POL|ewa|"IVONA Ewa"|com.ivona.tts.voicebeta.pol.pol.ewa|libvoice_pl_ewa.so|826648|811516|main.422.…|52883267|polish.lex|
|36|pol|POL|jacek|"IVONA Jacek"|com.ivona.tts.voicebeta.pol.pol.jacek|libvoice_pl_jacek.so|814232|799252|main.422.…|30440335|polish.lex|
|37|pol|POL|jan|"IVONA Jan"|com.ivona.tts.voicebeta.pol.pol.jan|libvoice_pl_jan.so|814232|799092|main.422.…|30748926|polish.lex|
|38|pol|POL|maja|"IVONA Maja"|com.ivona.tts.voicebeta.pol.pol.maja|libvoice_pl_maja.so|822756|811516|main.183.…|53042002|polish.lex|
|39|por|BRA|ricardo|"IVONA Ricardo"|com.ivona.tts.voicebeta.por.bra.ricardo|libvoice_pt_br_ricardo.so|494880|498960|main.422.…|142001879|brportuguese.lex|
|40|por|BRA|vitoria|"IVONA Vitoria"|com.ivona.tts.voicebeta.por.bra.vitoria|libvoice_pt_br_vitoria.so|491016|497104|main.422.…|154606468|brportuguese.lex|
|41|ron|ROU|carmen|"IVONA Carmen"|com.ivona.tts.voicebeta.ron.rou.carmen|libvoice_ro_carmen.so|1608148|1619968|main.199.…|30988954|romanian.lex|

(`main.…obb` abbreviates the full grammar `main.<N>.<package>.obb`, e.g. row 16 = `main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb`. N per row: **183** for rows 18 (salli) and 38 (maja); **199** for rows 1, 5, 6, 8, 16, 20, 21, 24, 26, 31, 41; **422** for all remaining rows. Exact names in `table_full.json`.)

OBB version numbers `N` are baked per-voice in this table; the **patch** is always version 199 regardless.

---

## 5. How the engine uses all this (`libttsivona.so`)

Cited from `out/ghidra_dump/decompiled.c` (same base convention, +0x10000 over ELF) and cross-checked by disassembly of the literals:

* **Load**: engine dex only `System.loadLibrary("ttsivona")`. Per voice package, `Java_…_IvonaPackagesInfo_getVoicesApiVersion` (decompiled.c ~10198, ELF 0x136fc) does `dlopen("<base>" + pkg + "/lib/libtiver.so", RTLD_LAZY)`, then `dlsym("v")` (rodata 0x6cf5c) and `dlsym("h")` (0x6cf9c). The base string `DAT_00084308` is set by `Java_…_NativeIVONAEngine_setEnvRuntime` (decompiled.c 6802) from Java `IvonaPackagesInfo.c()`: `new File(applicationInfo.dataDir).getParent() + "/"` → `"/data/data/"`, and the sdcard root `Environment.getExternalStorageDirectory().getAbsolutePath() + "/"` → `DAT_0008430c`. A second, lazy loader `FUN_00023ecc` (decompiled.c ~10711) does the same `dlopen` when a voice is first used, gates on `v()[0] > 0x13 && v()[3] > 0x2f`, and copies 4 struct words + package name into the engine voice record (`FUN_00023ac4`, decompiled.c 10413, also copies `entry+0x14` = voice lib, `entry+0x20` = main obb name, `entry+0x28` = lexicon from the table entry found through the accessor).
* **Gates** (getVoicesApiVersion, decompiled.c ~10236): `0x13 < *piVar8`, `0x2f < piVar8[3]`, `piVar8[1] < 3`; a package failing any gate is skipped silently (`dlclose`).
* **h probes**: `iVar9 = h(pkg, DAT_0008430c + "ivona/")` — legacy IVONA-1 layout `<sdcard>/ivona/<pkg>/…` (literal `"ivona/"` at ELF 0x6cf77); if nonzero, `iVar10 = h(pkg, DAT_0008430c + "Android/obb/")` — Play expansion layout (literal `"Android/obb/"` at 0x6cf7e). Result encoding appended at the end of the voice string: `1` = found under `ivona/`, `2` = found under `Android/obb/`, `0` = not found.
* **Voice name**: with `apiVer == 2`, `struct[4]` is called as `entry = accessor(i)`; `strcmp(entry+0x10, pkg)` matches; the display name at `entry+0x0c` (field [3], e.g. `"IVONA Kendra"`) is appended.
* **Result string** handed back to Java per package:
  `"%d;%d;" % (struct[1], last_h_result)` + display name + `";"` + `struct[2]` (build stamp) + `";%d" % location`
  e.g. `2;0;IVONA Kendra;20130201_150739;2`.
* **Java parsing** (`IvonaPackagesInfo.c()`, jadx_tts lines ~146–160): splits on `";"`; `[0]`→apiVer int, `[1]`→fstate int via `packages.b.a()` (0 = files fully installed; the value is the *last* h() result, so 0 = obb found in whichever dir), `[2]`→display name, `[3]`→stamp, `[4]`→data-location (persisted into `ivona_pkgs.csv`, ignored). CSV line = `pkg;versionCode;<the 5 fields>`; first line of the file is a `System.currentTimeMillis()` timestamp.

---

## 6. OBB location & path grammar (what a reimplementation must produce)

Base directories handed to `h`/`checkFiles` (must end with `/`):

1. Legacy: `<sdcard>/ivona/` (engine probe only; the voice APK deletes stale files here)
2. Play expansion: `<sdcard>/Android/obb/` — exactly what `checkFiles` uses (`basePath + "Android/obb/"`, and Google Play itself places expansion files at `<sdcard>/Android/obb/<pkg>/<file>`, matching)

Path assembly (string concatenation, no normalization):

```
main obb : <base><package>/main.<N>.<package>.obb          N ∈ {183, 199, 422} per table
patch obb: <base><package>/patch.199.<package>.obb         199 always (hardcoded C literal)
extracted: <base><package>/<entryName>                     flat entry names only
```

Verified real layout: `IVONA 2/IVONA Kendra…/Android/obb/com.ivona.tts.voicebeta.eng.usa.kendra/{main.199.…obb (152 219 597 B), patch.199.…obb (74 861 B)}` and amy equivalents (149 905 560 B / 74 861 B).

**Patch zip contents** (Python `zipfile` on the real files): each patch.199 obb is a standard ZIP containing exactly one flat entry: `lang_en_us.dat` (74 668 B) for kendra, `lang_en_gb.dat` (74 668 B) for amy — matching the extracted `out/obb/lang_en_*.dat`. The main obb is **not** a zip (`zipfile.BadZipFile`); it is the raw voice-data blob, read directly by `libttsivonavoice.so`.

---

## 7. Byte-for-byte checklist for a reimplementer

1. **File name grammar**: `main.<N>.<pkg>.obb` with the exact per-package `N` and byte size from the table (§4); `patch.199.<pkg>.obb` with 199 always. Sizes must match **exactly** (`uint32` low half of `st_size`; upper half must read 0).
2. **v() struct**: `{20, 2, "20130201_150739", 48, accessor}`; accessor = `i > 43 ? NULL : &table[i]` (48-byte stride, table of §4, terminator row all-zero, walk stops on dword[0] == 0). Engine gates `s[0] > 19`, `s[3] > 47`, `s[1] < 3`.
3. **Return codes**: `0` OK; `1` not installed/size mismatch; `-1` (0xffffffff) patch or stat-path error / NULL args in `FUN_000169b8`; `-2` (0xfffffffe) NULL args in `FUN_000166e8` and NULL jstrings in `checkFiles`. Java treats only `== 0` as success; the engine treats any nonzero `h()` result as “try the other base dir”.
4. **Patch behavior**: patch missing → `"Error on opening patch file:%s"`, -1; entries with `/` or `\` in the name are skipped; extraction is unconditional when called via `h` (flag 0) and in practice also via `checkFiles` (flag 1 — the skip predicate compares `st_size` to the entry-name length and never triggers); CRC errors are computed by minizip but ignored; write granularity 8 KiB; the `<base><pkg>/` directory is *not* created.
5. **Log messages verbatim** (tag `IVONAVOICE`, level 6): `Error on opening patch file:%s`, `Error %d on reading patch data`, `Error %d on getting file info`, `Error opening current file!`, `Error creating file:%s`, `Error reading patch file:%s`, `Error on writting file:%s.`, `Error %d on switching to next file`, `Failed to obtain package name.`, `Failed to obtain path to files.` (note original typos “writting”, “occured” elsewhere).
6. **No dynamic content**: the table, struct, and version literals are compile-time constants identical in every voice APK; no file in the APK mutates them.
7. **Threading/lifecycle**: `checkFiles` is called from the voice APK process (`VoiceFiles.a`); `h`/`v` from the engine process via `dlopen`/`dlclose` per probe — no persistent state is kept inside libtiver (only scratch `std::string`s in `.bss`, e.g. `DAT_0002f02c` at ELF 0x1f02c).

### Residual uncertainties

* Exact C mapping of the two compared `stat` fields (offsets 0x30/0x34 observed; read as low/high halves of a 64-bit size) `[INFERENCE]`.
* Table field [7] (second per-voice size; smaller than [6] for Polish rows) — unreferenced by any traced code `[INFERENCE]`.
* Behavior for a package name absent from the table: lookup stops on the zero terminator row and path building dereferences a NULL obb-name pointer (likely SIGSEGV) `[INFERENCE]`.
* Words [5]/[6] of `.data` (addresses of `terminate`/`__verbose_terminate_handler`) are almost certainly C++ runtime handler slots adjacent to the struct, not voice fields `[INFERENCE]`.
