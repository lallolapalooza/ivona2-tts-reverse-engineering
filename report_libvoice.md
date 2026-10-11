# `libvoice_en_us_kendra.so` — reverse-engineering report

Target: `out/libs/kendra/libvoice_en_us_kendra.so` (3,085,840 bytes, ARM EABI5, `md5 446e4028eb7cb47f0abc18597a2d8106`),
comparison: `out/libs/amy/libvoice_en_gb_amy.so` (3,073,872 bytes, `md5 361f44ba1a84430a29a0a0e8c1396b02`).
Decompilation: `out/ghidra_dump/libvoice_kendra.c` (43,894 lines), engine: `out/ghidra_dump/libttsivonavoice.c`.

## 0. Address conventions and method

* For every allocated section of these ELFs **file offset == link VMA** (e.g. `.text` Addr `0x1688c` Off `0x1688c`), so
  "VMA" and "file offset" are used interchangeably below.
* The Ghidra dump was produced with **image base `0x10000`**, therefore
  `ghidra_addr = file_offset + 0x10000`. Verified repeatedly against raw bytes:
  `register_voice` = `0x268a0` (Ghidra) / `0x168a0` (readelf); `&DAT_00066bbc` → `0x56bbc` = ASCII `"22v"`;
  `&DAT_00066ebc` → `0x56ebc` = `"36"`; `&DAT_00066a28` → `0x56a28` = `"%d"`;
  `&DAT_00155d00` in the engine → `0x145d00` = `"name"`.
  **A `DAT_xxxxxxxx` label in the dump maps to file offset `xxxxxxxx - 0x10000`.**
* Everything below is grounded in: `readelf`, byte/structure scans (scratch scripts `scripts/06_rodata_map.py`,
  `scripts/08_refs.py`, plus ad-hoc inline python), ARM disassembly, and the Ghidra C dump.
  Every instruction listing in this report was produced **and cross-checked** with capstone
  (`/home/asdf/venvs/re/bin/python`, `CS_ARCH_ARM`/`CS_MODE_ARM`) and agrees with the Ghidra C output
  (e.g. `bl 0x16de0` ↔ Ghidra `FUN_00026de0`, `bl 0x1bb98` ↔ `FUN_0002bb98`, `b 0x20008` ↔ `FUN_00030008`).
  Anything not directly observed is marked `[INFERENCE]`.

---

## 1. `register_voice` / `unregister_voice`: the plug-in interface

### 1.1 Exports and ABI version

```
$ readelf -W --dyn-syms out/libs/kendra/libvoice_en_us_kendra.so | grep -v UND
     1: 0001688c  SECTION LOCAL  DEFAULT    9 .text
     2: 002e4014  SECTION LOCAL  DEFAULT   15 .data.rel.ro
    21: 000168a0    56 FUNC GLOBAL DEFAULT    9 register_voice@@TTS_ENGINE_1_6
    50: 00000000     0 OBJECT GLOBAL DEFAULT  ABS TTS_ENGINE_1_6
    65: 0001689c     4 FUNC GLOBAL DEFAULT    9 unregister_voice@@TTS_ENGINE_1_6
```

* Exactly **two function exports**, both versioned `@@TTS_ENGINE_1_6`.
* `readelf -V`: one VERDEF besides the base node — `Rev:1 Flags:none Index:2 Cnt:1 Name: TTS_ENGINE_1_6`;
  `.gnu.version` entry 2 = `TTS_ENGINE_1_6` is applied to dynsym #21 and #65 (and to the ABS node).
* `DT_SONAME = libvoice_en_us_kendra.so`; `DT_NEEDED = libm, libdl, liblog, libc`; `DT_TEXTREL` present
  (the only `.text` relocation is `00016898 R_ARM_RELATIVE` — the `__dso_handle` pointer of the `.init` stub).
* **How the version is actually checked**: the engine uses plain `dlsym()` (no `dlvsym`), so the version node is
  *not* enforced at symbol lookup. The enforced ABI contract is the string `eng_version == "1.6.23"` (§1.5) plus the
  ELF symbol-version name `TTS_ENGINE_1_6` that identifies the ABI family. `[INFERENCE: TTS_ENGINE_1_6 is a
  labelling/compatibility marker, not a runtime gate]`

### 1.2 `register_voice` — signature and code

Hand-decoded from `0x168a0..0x168d8` (56 bytes):

```
000168A0: 10 40 2d e9   push {r4, lr}
000168A4: dd 25 00 eb   bl   0x20020            ; FUN_00030020()   (Ghidra FUN_00030020)
000168A8: 00 40 50 e2   subs r4, r0, #0
000168AC: 05 00 00 0a   beq  0x168C8            ; NULL -> skip setter
000168B0: 18 10 9f e5   ldr  r1, [pc, #0x18]    ; pool word @0x168D0 = 0x400F0
000168B4: 18 20 9f e5   ldr  r2, [pc, #0x18]    ; pool word @0x168D4 = 0x400F8
000168B8: 01 10 8f e0   add  r1, pc, r1         ; r1 = 0x168C0+0x400F0 = 0x569B0 "eng_version"
000168BC: 02 20 8f e0   add  r2, pc, r2         ; r2 = 0x168C4+0x400F8 = 0x569BC "1.6.23"
000168C0: 00 00 94 e5   ldr  r0, [r4]           ; voice->field0 (property list head)
000168C4: 9c 00 00 eb   bl   0x16B3C            ; FUN_00026b3c(list,"eng_version","1.6.23")
000168C8: 04 00 a0 e1   mov  r0, r4
000168CC: 10 80 bd e8   pop  {r4, pc}           ; return voice pointer
000168D0: f0 00 04 00   literal 0x400F0
000168D4: f8 00 04 00   literal 0x400F8
```

* **Signature:** `void *register_voice(const char *vox_path);`
  The incoming `r0` is never overwritten before `bl FUN_00030020`, so the argument is passed through verbatim —
  instruction-level proof that the argument exists even though Ghidra renders the function as `register_voice(void)`
  (line 902 of the dump).
* Engine side confirms the same signature (`libttsivonavoice.c` line 28007 ff., `tts_load_voice(int, char*, char*)`):

```c
  pcVar3 = (code *)dlsym(iVar2,"register_voice");
  ...
  puVar4 = (undefined4 *)(*pcVar3)(param_3);        /* param_3 is char* (vox path / data dir) */
  if (puVar4 == (undefined4 *)0x0) {
      ... __errno() == 2 -> "The vox file does not exist"
      ... __errno() != 0 -> generic error, errno passed on
      ... __errno() == 0 -> FUN_000474e4(4) (generic failure)
  }
```
* Returns the object produced by `FUN_00030020` (Ghidra `0x30020`, file `0x20020`) or **NULL** with `errno` set.
* Capstone reproduces this listing instruction-for-instruction; the two `bl` targets (`0x20020`, `0x16B3C`)
  and the `beq` target (`0x168C8`) match the Ghidra functions exactly, and the two pc-relative loads resolve to
  `0x569B0 "eng_version"` / `0x569BC "1.6.23"` byte-verified.

### 1.3 Construction — `FUN_00030020` (dump line 7794)

```
FUN_00030020(path):
  obj = FUN_00044438()                     ; alloc 0x0C bytes, two fresh property lists
  set(obj[0], "name",           "vox_en_us_kendra")
  set(obj[0], "checksum",       "1333557784")
  set(obj[0], "vox_lexicon",    FUN_0003e1ec(&DAT_002f4030))     ; variant tag 0x1B "lexicon"
  set(obj[0], "duration_stretch", 1.0f)                           ; FUN_00026b64 = float setter
  set(obj[0], "duration_func",  FUN_00029510(FUN_00048400))
  set(obj[0], "zdur_cart",      FUN_000482d0(&PTR_DAT_002f4024))
  if (FUN_00028310(obj[0], path, 0) == 0) { FUN_00044410(obj); return NULL; }   ; vox-file load, may fail
  set(obj[0], "diphone_graph_func", FUN_00027a18(FUN_00030214))
  set(obj[0], "viterbi_beam",   50)
  set(obj[0], "language_code",  "en-US")
  set(obj[0], "voice_name",     "Kendra")
  set(obj[0], "voice_gender",   "Female")
  set(obj[0], "voice_age",      &DAT_00066ebc  -> "36")
  FUN_0003256c(obj)                         ; finaliser (§1.6)
```
The `set` helpers are: `FUN_00026b3c` = string, `FUN_00026b64` = float, `FUN_00026b8c` = int,
`FUN_00026a54` = raw variant (dump lines 1013 `FUN_00026a54`, 1082 `FUN_00026b3c` string,
1096 `FUN_00026b64` float, 1110 `FUN_00026b8c` int).

**`FUN_00044438` (line 18794)**: `malloc(0x0C)`; `obj[0] = new list`, `obj[1] = new list`, `obj[2]` untouched (0).
**`FUN_00044410` (line 18778)**: `if (obj){ free_list(obj[0]); free_list(obj[1]); free(obj); }`.

### 1.4 The object handed to the engine (field by field)

```
offset  size  contents
+0x00   4     *property list A*  — head pointer of the key/value list the engine reads
                                   (`*voice` is what every engine accessor dereferences)
+0x04   4     *property list B*  — feature-name -> function registry filled by the plug-in itself
                                   (FUN_0003d9b0 registrations, §1.6); no engine-side reader of
                                   `voice+4` was found
+0x08   4     unused/zero (never written by the construction path)  [INFERENCE: reserved]
(0x0C bytes total; FUN_00044438)
```
Everything the engine consumes is reached through `*voice` (i.e. `+0x00`); no access to `voice+8` was
observed in the decompiled engine. (`tts_unload_voice`'s `*(owner_struct + 4)` refers to the 0x14-byte
owner record built by `FUN_0004bf1c`, *not* to `voice+4`.)

**List node** (`FUN_00026a54`, dump line 1013) — 0x0C bytes, head-inserted:

```
+0x00 char *key      (not copied; the plugin stores .rodata pointers)
+0x04 variant *value (copy made by FUN_000270a0)
+0x08 node  *next
```

**Variant value** (`FUN_00027f20`, `FUN_0003e1ec`) — 8 bytes:

```
+0x00 uint16 type_tag   (+0x02 pad)
+0x04 void  *payload
```
Known tags observed in code: `0x1F` = `diphonedb` (`FUN_00027f20`/`FUN_00027f38`),
`0x1B` = `lexicon` (`FUN_0003e1ec`/`FUN_0003e25c`). A wrong tag aborts via
`"VAL: tried to access %s in %d type val\n"` + `exit(-1)`.

Type-name strings in `.rodata`: `features` @`0x56A0C`, `userdata` @`0x56A9C`, `int` `0x56AA8`, `float` `0x56AAC`,
`string` `0x56AB4`, `utterance` `0x56ABC`, `wave` `0x56AC8`, `track` `0x56AD0`, `uttfunc` `0x56AD8`,
`ffunc` `0x56AE0`, `relation` `0x56AE8`, `item` `0x56AF4`, `phoneset` `0x56AFC`, `dur_stats` `0x56B08`,
`diphonedb` `0x56B14`, `wavesynth` `0x56B20`, `audiotag` `0x56B2C`, `itemfunc` `0x56B38`, `phonefunc` `0x56B44`,
`xsampafunc` `0x56B50`, `allwordposfunc` `0x56B5C`, `zdur_cart` `0x56B6C`.
A `{char *name, code-ptr}` registry array for these lives in `.data.rel.ro` at `0x2EFB90..0x2EFCFC`
(e.g. `0x2EFCA4 → "diphonedb"` + `0x17D44`, `0x2EFCCC → "userdata"` + `0x17A00`, `0x2EFC94 → "lexicon"` + `0x179F8`).
The complete tag↔name mapping was **not** determined (§5).

### 1.5 `unregister_voice`

* `0x1689c`, 4 bytes, single instruction `d9 25 00 ea` = `b 0x20008` → Ghidra `FUN_00030008` (line 7782):
  `{ thunk_FUN_00036fe0(); FUN_00044410(voice); }` where `FUN_00036fe0` (line 9753) is an **empty function**.
  So the whole export is `void unregister_voice(void *voice)` → frees list A, list B, then the object.
* Engine caller (line 27940 / 28169):
```c
  pcVar1 = (code *)dlsym(handle,"unregister_voice");
  uVar4 = *(undefined4 *)voice_owner_struct;   /* the pointer register_voice returned */
  (*pcVar1)(uVar4);
```

### 1.6 Properties published by the voice

Required by the engine in `tts_load_voice` (line 28036 ff.): all of
`voice_name`, `voice_gender`, `eng_version`, `language_name`, `language_code` must be present
(`FUN_0005b0bc(*voice_ptr, key) != 0`), else `"Invalid voice library data"`.

**Version gate** (line 28060 ff.):
```c
  pcVar12 = FUN_0005b15c(*puVar4,"eng_version");
  if (strcmp("1.6.23", pcVar12) != 0) {
      FUN_00047500(4,"Voice library version mismatch: got %s, required %s", pcVar12,"1.6.23");
      FUN_0004bf64(handle, voice); dlclose(handle); return NULL;
  }
```

Other engine reads (deduped from `FUN_0005b0bc/15c/1c0/230` literal arguments):
`custom_voice` (int, default 0 → certificate check `FUN_0004dee4`, error `"Voice not allowed by the certificate"`),
`sample_rate` (int, default 0), `name` (string, default `"anonymous"`), `voxdbname`, `checksum`, `diphonedb`,
`encoding`, `voice_age`, `viterbi_beam`, `text_whitespace`, `text_singlecharsymbols`, `text_prepunctuation`,
`text_postpunctuation`, `eng_max_sentence`, `eng_max_word`, `eng_dict_insert_id`, `eng_text_encoding`,
`eng_input_type`, `eng_ssml_base_uri`, `eng_fetch_function`, `eng_fetch_user_data`, `streamer`,
`resample_wave`, `deterministic_path`, `Certificate-ID`, `Expiration-date`, `Licensee`, `Licensor`, `Product`.
`FUN_0005b10c(list,key)` is the raw lookup returning the variant pointer (line 39502 of the engine dump).

**Set by `register_voice` (order as in the decompilation):**

| property | value (kendra) | setter | dump line |
|---|---|---|---|
| `name` | `vox_en_us_kendra` | str | 7805 |
| `checksum` | `1333557784` | str | 7806 |
| `vox_lexicon` | lexicon variant (`0x1B`, data `&DAT_002f4030`) | raw | 7809 |
| `duration_stretch` | `1.0f` | float | 7810 |
| `duration_func` | func variant | raw | 7813 |
| `zdur_cart` | CART variant from `PTR_DAT_002f4024` | raw | 7816 |
| `sample_rate` | from vox header `+0x24` (22050) | int | 2651 (loader) |
| `diphonedb` | diphonedb variant (`0x1F`) wrapping the parsed vox file | raw | 2653 (loader) |
| `diphone_graph_func` | func `FUN_00030214` | raw | 7825 |
| `viterbi_beam` | `50` | int | 7826 |
| `language_code` | `en-US` | str | 7827 |
| `voice_name` | `Kendra` | str | 7828 |
| `voice_gender` | `Female` | str | 7829 |
| `voice_age` | `36` | str | 7830 |
| `encoding` | `ISO-8859-1` | str | 9425 |
| `language_name` | `US English` (by `language_code`: `en-AU`/`en-GB`/`en-GB-WLS`/`en-US`) | str | 9428-9443 |
| `syl_boundaries_func`, `xsampa_to_xivona_func`, `xivona_to_xsampa_rules` | per-language (`en-US` vs `en-GB` tables) | raw | 9448-9473 |
| `wordtosegments_func`, `postlex_func`, `phoneset` | funcs/phoneset variant | raw | 9476-9482 |
| `silence` | phoneset's silence phone (`ppuVar5[4]`) | str | 9483 |
| `text_whitespace`, `text_postpunctuation` (`.,:!?`), `text_prepunctuation`, `text_singlecharsymbols` | from `.rodata` `0x62718..0x62724` | str | 9484-9487 |
| `sentence_boundary_func`, `tokentowords_func`, `phrasesylendtone_func` | funcs | raw | 9490-9496 |

Then `FUN_0003256c` fills **list B** with ~52 feature extractors via `FUN_0003d9b0`
(`ph_vc`, `ph_vlng`, `ph_vheight`, `ph_vfront`, `ph_vrnd`, `ph_ctype`, `ph_cplace`, `ph_cvox`,
`word_num_syls`, `word_break`, `word_punc`, `ssyl_in/out`, `syl_out/break/onsetsize/codasize`,
`accented`, `seg_*`, `pos_in_syl`, `position_type`, `sub_phrases`, `last/next_accent`, `syl_final`,
`syl_vowel`, `segment_duration`, `syl_num_phones`, `phrase_num_words/syls`, `num_phrases`,
`pos_in_word/phrase/utt`, `ssyl_from/to`, `num_digits`, …) — dump lines 18812 ff. (`FUN_00044460`).

---

## 2. The data payload

### 2.1 ELF layout (kendra)

```
[ 6] .rel.dyn     REL      0x000ae8 size 0x0158b8  (11031 entries; DT_RELCOUNT 11023 = R_ARM_RELATIVE,
                                                       remaining 8 = R_ARM_GLOB_DAT)
[ 7] .rel.plt     REL      0x0163a0 size 0x0001f0  (62 R_ARM_JUMP_SLOT)
[ 8] .plt         0x016590 size 0x0002fc
[ 9] .text        0x01688c size 0x040124   (262,436 B)
[10] .rodata      0x0569b0 size 0x28d3d8   (2,675,672 B  = 86.7 % of the file)
[11] .ARM.extab   0x2e3d88 size 0x24
[12] .ARM.exidx   0x2e3dac size 0xf8
[13] .init_array  0x2e4000 size 8
[15] .data.rel.ro 0x2e4014 size 0x00c040   (49,216 B; 10,778 R_ARM_RELATIVE words)
[16] .dynamic     0x2f0054
[17] .got         0x2f0154 size 0x458
[18] .data        0x2f05ac size 0x98
[19] .bss         0x2f0650 size 0xac
```
`.data.rel.ro` pointer words resolve to: 9,969 → `.rodata`, 36 → `.text`, 773 → `.data.rel.ro` (self-referencing
structures), 0 elsewhere.

### 2.2 CDXV: exactly three occurrences, all in `.text`

```
$ (whole-file scan for b'CDXV')
0x17CD0  43 44 58 56 10 40 2d e9 ...        ; literal pool of FUN_00027bd0 (file 0x17BD0)
0x18004  43 44 58 56 f0 41 2d e9 ...        ; literal pool of FUN_00027f90 (file 0x17F90)
0x182E0  43 44 58 56 cd cc cc cc 54 03 00 00 64 01 00 00 ...
                                              ; literal pool of FUN_00028008 (file 0x18008)
```
Hexdump in context (third occurrence — a genuine ARM literal pool: 4-byte word `0x56584443`, float `0.1f`,
then ten voice-specific `u32` sizes that differ between kendra and amy, §3):

```
000182D8: d2 ff ff ea 2c 81 2d 00  43 44 58 56 cd cc cc cc  ....,...CDXV....
000182E8: 54 03 00 00 64 01 00 00  ac 02 00 00 b0 03 00 00  T...d...........
000182F8: 80 02 00 00 28 01 00 00  bc 02 00 00 cc 03 00 00  ....(...........
00018308: 7c 01 00 00 e8 01 00 00  f0 4f 2d e9 ...          |....... .O-..
```

`0x56584443` is the vox-file magic. Three functions compare against it:

| Ghidra | file | code | role |
|---|---|---|---|
| `FUN_00027bd0` (line 2207) | `0x17BD0` | `fread(h,0x68,1,f); if (h[0]==0x56584443) { compare sample_rate(h+0x24) with param[3] and checksum(h+0x2c) with param[4]; keep FILE* }` | validating open (keeps the stream) |
| `FUN_00027f90` (line 2401) | `0x17F90` | same 0x68-byte read + magic; returns `strdup(header+4)` (name probe) | header peek |
| `FUN_00028008` (line 2432) | `0x18008` | full header parse (§2.3), `switch(header+0x28)` on the format id | main loader |

**Conclusion for the "is the container embedded?" question:** *No.*
A whole-file scan finds `CDXV` only at those three `.text` literal-pool words; `.rodata` begins with
`eng_version\0 1.6.23\0 …` (hexdump §2.4) and contains no `CDXV` header, no 0x68-byte header image, and no
diphone/phoneme name records (`b'aa-aa'`, `b'aa-ah'`, `b'w-ah'` → **0 hits** in the `.so`, while the vox file has
them at `0x341FE0`). The container lives in an **external file** that the plug-in opens during `register_voice`.

### 2.3 The external vox file (CDXV container) and how the plug-in reads it

Path built by `FUN_00028310` (line 2576):

```c
  name     = get("name", 0);            /* "vox_en_us_kendra" */
  checksum = get("checksum", 0);        /* "1333557784"       */
  voxdbname= get("voxdbname", name);
  if (path != NULL && is_directory(path))
      sprintf(buf, "%s/%s/%s/%s%s", path, voxdbname, checksum, voxdbname, &DAT_00066bbc);
      /* &DAT_00066bbc -> file 0x56BBC = "22v"  =>  <dir>/<name>/<checksum>/<name>22v */
  else use `path` itself;
  hdr = FUN_00028008(file);                       /* NULL -> "**Error: cannot open or incorrect file `%s'" */
  strcmp(hdr->name(+0x04), name)                  must match
  atol(checksum) == hdr->u32(+0x2c)               must match
  the five section offsets hdr +0x40/+0x48/+0x50/+0x58/+0x60 must be non-zero
                                                   else "**Error: file `%s' lacks needed features"
  set_int("sample_rate", hdr->u32(+0x24));
  wrap hdr as variant 0x1F -> set("diphonedb", …)
```
If `path == NULL` the loader simply uses `name` as the file name (so a NULL argument fails with
`errno == ENOENT` → the engine prints *"The vox file does not exist"*).

**Header layout, 0x68 = 104 bytes** (derived from the stack buffer of `FUN_00028008` and confirmed byte-for-byte
against the shipped OBB, which is a CDXV container whose `name`/`checksum` are exactly the plug-in's):

```
00000000: 43 44 58 56 76 6f 78 5f  65 6e 5f 75 73 5f 6b 65  CDXVvox_en_us_ke
00000010: 6e 64 72 61 00 00 00 00  00 00 00 00 00 00 00 00  ndra............
00000020: 00 00 00 00 22 56 00 00  0e 00 00 00 18 7a 7c 4f  ...."V.......z|O
00000030: 68 00 00 00 78 1f 34 00  d8 e8 82 01 00 00 00 00  h...x.4.........
00000040: e0 1f 34 00 14 7d 00 00  f8 9c 34 00 fc 8a 19 00  ..4..}....4.....
00000050: f8 27 4e 00 9c 8d ea 00  98 b5 38 01 fd 2b 4a 00  .'N.......8..+J.
00000060: 98 e1 82 01 40 07 00 00  ....@...
```

| offset | field | kendra OBB value | consumer |
|---|---|---|---|
| `+0x00` | `u32 magic 'CDXV'` (`0x56584443`) | `43 44 58 56` | all three openers |
| `+0x04` | `char name[32]` | `vox_en_us_kendra` | `strcmp` vs `name` prop; `strdup` → vox-obj `+0x04` |
| `+0x24` | `u32 sample_rate` | `22050` | `set_int("sample_rate",…)`; vox-obj field `+0x0C` |
| `+0x28` | `u32 format/codec id` | `14` | `switch` in `FUN_00028008`: only 2, 8, 12 (0xC), 14 (0xE) install codec fns into vox-obj `+0x34/+0x38/+0x3C` |
| `+0x2C` | `u32 checksum` | `1333557784` | `atol(checksum)` compare; vox-obj field `+0x10` |
| `+0x30/+0x34` | section (off,len) | `0x68 , 0x341F78` | the `(offset,size)` index: 426,991 pairs → vox-obj `+0x14` (mmap base+off) / `+0x18` (len) |
| `+0x38/+0x3C` | section (off,len) | `0x182E8D8 , 0` | `len==0` → vox-obj `+0x40` not installed (`+0x44` would hold len) |
| `+0x40/+0x44` | section (off,len) | `0x341FE0 , 0x7D14` | vox-obj `+0x28` (base) / `+0x2C` = `len/20` = **1601** records of 20 B (`char name[12]; u32; u32`) → diphone names `aa-aa`, `aa-ah`, …; must be non-zero |
| `+0x48/+0x4C` | section (off,len) | `0x349CF8 , 0x198AFC` | vox-obj `+0x24` (base); `len` only feeds the mmap-size maximum; must be non-zero |
| `+0x50/+0x54` | section (off,len) | `0x4E27F8 , 0xEA8D9C` | vox-obj `+0x20` (base); must be non-zero |
| `+0x58/+0x5C` | section (off,len) | `0x138B598 , 0x4A2BFD` | vox-obj `+0x1C` (base); must be non-zero |
| `+0x60/+0x64` | section (off,len) | `0x182E198 , 0x740` | vox-obj `+0x30` (base); must be non-zero |

* `FUN_00028008` mmaps `[0, max(off+len))` = `0x182E8D8` (25,356,504 B) of the file
  (`FUN_0002bddc`, line 5490: `open`+`fstat`+`mmap(NULL,size,PROT_READ,MAP_PRIVATE,fd,off)`, keeps `fd` at `+0x0C`),
  stores section base pointers as `mmap_base + off`, and records `+0x44`/20 as a record count.
* Record data beyond the mapped window is read through `FILE*` helpers — `FUN_00026f88` builds `"rb"`/`"r"` modes,
  `FUN_00026eec` seeks, `FUN_00026f58` = `fread` — e.g. codec `FUN_0002e490` (line 7291) does
  `FUN_00026eec(stream, offset, 0); FUN_00026f58(stream, buf, 1, len)`. `[INFERENCE: which object reopens the
  stream after `FUN_00028008` fcloses it — `FUN_00027bd0` retains a `FILE*` but no direct call site was found]`
* The shipped Kendra OBB (`IVONA 2/…/main.199.com.ivona.tts.voicebeta.eng.usa.kendra.obb`, 152,219,597 B) is such
  a container: `magic CDXV`, `name vox_en_us_kendra`, `+0x24 = 22050`, `+0x28 = 14`, `+0x2C = 1333557784` —
  all four checks of the plug-in pass. **How the Android app hands that path to `register_voice` (OBB path vs.
  extracted copy at `<dir>/vox_en_us_kendra/1333557784/vox_en_us_kendra22v`) was not determined (§5).**

### 2.4 `.rodata` layout (kendra, file offsets)

Entropy/printable per 64 KiB (`scripts/06_rodata_map.py`): 6.4–7.6 everywhere except the string-rich blocks;
no ASCII run ≥ 4 KiB exists (data is packed/interleaved, not plain text).

| from | to | size | content / evidence |
|---|---|---|---|
| `0x0569B0` | `0x060428` | `0x9A78` (39,544) | shared runtime strings: property keys, format strings, variant type names, error texts. Head hexdump below. |
| `0x060428` | `0x064BFC` | `0x47D4` (18,388) | short-string tables: word/flag lists (`0abdullah`, `*brewpubs`, `0tussaud's`…), language config (`en-AU`, `en-GB`, `en-GB-WLS`, `US English`, `en_US_lex`/`en_gb_lex` names), phoneme feature names (`cvox vlng vheight vfront vrnd ctype cplace eax iax uax` @`0x61464`), `x-ivona-en_gb` @`0x61450`, text-normalisation tables (`0123456789`, `punc`, `percent`, `a.m`, `interpret-as` @`0x64406..0x645F0`). 1,417 + 540 + 328 pointer-table entries point into it. |
| `0x064BFC` | `0x1CBA5C` | `0x166E60` (1,470,048) | **en_US packed lexicon** (§2.5.1) |
| `0x1CBA5C` | `0x1CC088` | `0x62C` (1,580) | en_US string-pool substrings (615 `.data.rel.ro` pointers; `_epsilon_`, `0sel`, `f-`, `sk`, `ism`, `ization`, `ing's`, …) |
| `0x1CC088` | `0x1EDA48` | `0x219C0` (137,664) | **en_US letter-to-sound FSM** (6-byte records) + inline phone strings (`0d 0c 0h 0p 0s 0b 0m` just below `0x1CC088`) |
| `0x1EDA48` | `0x1F2CBC` | `0x5274` (21,108) | en_US **letter index table** = 27 × `u32` ascending (`0, 0x1147, 0x1196, … 0x5962`) ending exactly at `0x1EDAB4`, then phone-name arrays (`epsilon, eh1, ae1, …`), pointer clusters (201, 4,253, 439 pointers) |
| `0x1F2CBC` | `0x2AE0BC` | `0xBB400` (766,976) | **en_GB packed lexicon** (§2.5.1) |
| `0x2AE0BC` | `0x2D0000` | `0x21F44` (139,076) | en_GB pool substrings (288 pointers, `eax1`… ending `0x2AE430`), **en_GB FSM** @`0x2AE434`, en_GB **letter table** @`0x2CEC48` (27 × u32, ends `0x2CECB4`), feature/CART tables |
| `0x2D0000` | `0x2E3D88` | `0x13D88` (81,288) | tail tables: float arrays (e.g. `0x430D7F6A, 0x431D8C0A, …` @`0x2D69B0`), `u32` offset tables @`0x2E3D00` (`0xFFFFE9F0, 0xFFFFE960, …`), remaining pointer clusters; entropy 7.58 (dense numeric data) |

Head of `.rodata`:

```
000569B0: 65 6e 67 5f 76 65 72 73  69 6f 6e 00 31 2e 36 2e  eng_version.1.6.
000569C0: 32 33 00 00 25 73 20 25  73 0a 00 00 25 73 20 25  23..%s %s...%s %
000569D0: 64 0a 00 00 25 73 20 25  66 0a 00 00 25 73 20 25  d...%s %f...%s %
000569E0: 70 0a 00 00 56 41 4c 3a  20 74 72 69 65 64 20 74  p...VAL: tried t
000569F0: 6f 20 61 63 63 65 73 73  20 25 73 20 69 6e 20 25  o access %s in %
00056A00: 64 20 74 79 70 65 20 76  61 6c 0a 00 66 65 61 74  d type val..feat
00056A10: 75 72 65 73 00 00 00 00  72 2b 00 00 61 2b 00 00  ures....r+..a+..
```

Region statistics (`scripts/…` entropy run):

```
shared strings/keys      0x00569B0-0x0060428  ent=5.71 printable=0.192
word/phoneme string lists0x0060428-0x0064BFC  ent=5.25 printable=0.529
en_US lex blob           0x0064BFC-0x01CB9BC  ent=6.83 printable=0.097   (blob field ends 0x01CBA5C)
en_US pool substrings    0x01CBA5C-0x01CC088  ent=4.09 printable=0.311
en_US LTS FSM + strings  0x01CC088-0x01F2CBC  ent=6.90 printable=0.512
en_GB lex blob           0x01F2CBC-0x02AE0BC  ent=6.90 printable=0.106
en_GB pool/FSM/tables    0x02AE0BC-0x02D0000  ent=6.97 printable=0.487
tail tables              0x02D0000-0x02E3D88  ent=7.58 printable=0.357
```

### 2.5 The tables

#### 2.5.1 Packed dictionary (`en_us_lex` / `en_gb_lex`)

Descriptor filled at runtime by `FUN_00033590` (line 9592) — two structs per language in `.bss`
(`.bss` `0x2F0650..0x2F06FC`, Ghidra `0x300650..0x3006FC`):

```
struct LexInfo  (0x24 B)          struct LtsInfo (0x20 B)
+0x00 char *name                  +0x00 char *name        ("en_us_lex_lts"/"en_gb_lex")
+0x04 u32  entry_count*           +0x04 u32 *letter_table (27 u32)
+0x08 u8  *blob (base)            +0x08 rec6 *fsm         (6-byte records)
+0x0C u32  blob_length            +0x0C char **phone_names
+0x10 ptr  phone-name table*      +0x10 int  ctx_len (=4)
+0x14 ?                          +0x14 int  (=1)
+0x18 ptr  hash/aux table         +0x18 ptr  char-class table (=0)
+0x1C ptr  pronunciation table    +0x1C int  offset (=0)
+0x20 char** string pool (u8 idx)
```
\* `LexInfo+0x04` is ~the number of entries (`0x1EE0C` = 126,476 vs 126,462 decoded) `[INFERENCE: semantics]`;
  `LexInfo+0x10` points at a `{epsilon, k, ax, z, j, uw1, …}` name table (`0x2E7FC4`); it is not read by
`FUN_0003e2b4`, so its consumer is unverified.

en-US instances: `LexInfo @0x300680`, `LtsInfo @0x300660`; en-GB: `0x3006C4` / `0x3006A4`
(Ghidra constants, all independently re-derived from the raw `ldr rX,[pc,#n]` + `add rX,pc,rX` pools and the
`R_ARM_RELATIVE` GOT words at `0x2F02A8`, `0x2F0378`, `0x2F044C`, `0x2F0454`, `0x2F04E8`).

Measured values (kendra):

| dataset | base | length | count | end = base+len |
|---|---|---|---|---|
| `en_us_lex` | `0x064BFC` | `0x166E60` | `0x1EE0C` (126,476) | `0x1CBA5C` = start of the pool strings |
| `en_gb_lex` | `0x1F2CBC` | `0x0BB400` | `0x0F126` (61,734) | `0x2AE0BC` = start of the pool strings |

Both blobs are preceded in `.rodata` by an 8-byte header `{ u32 entry_count; u32 blob_length }` immediately
before the base — verified bytes:

```
00064BF0: 6e 74 73 00 | 0c ee 01 00 60 6e 16 00 | 00 f8 d0 ff …   en_US: 0x1EE0C, 0x166E60, blob…
001F2CB0: 73 6d 00 00 | 26 f1 00 00 40 b4 01 00 | 00 f8 f2 ff …   en_GB: 0x0F126, 0x0BB400, blob…
```

**Blob format** (decoded by `FUN_0003e2b4`, line 13812):
* entries delimited by `0xFF`; the binary search walks byte positions looking for the `0xFF` preceding a candidate
  entry start;
* inside an entry the key is `0x00`-terminated sequence of **u8 indices into a 256-entry `char*` string pool**
  (pool = `LexInfo+0x20`), pool slot 0 = empty; the first decoded character is a flag (leading digit/letter) that the
  compare skips (`strcmp(local_68+1, query+1)`);
* the remaining bytes up to the next `0xFF` are a variable-length tail = pronunciation code
  `[INFERENCE on the exact pronunciation encoding]`.

Verification (script decode over the real bytes):

```
0x64C00 -> b"0'cause"      0x64C0A -> b"0'cos"      0x64C13 -> b"0'cuse"
0x1AE434 (inside blob) -> b'0tussaud's'  '0tussey'  '0tussing'
0x1CB9B7 (last)         -> b'0zwilling'   '0zwieback' '0zwiefelhofer'
walk = 126,462 entries from 0x64BFC to 0x1CB9C2, alphabetically sorted  (count field: 126,476)
```
Pool sample (`0x2E84F8`, 256 × `char*`): `[0]="" [1]="4" [2]="3" [3]="2" [4]="q" [5]="0sel" [6]="f-"
[7]="sk" [8]="'" [9]="0bl" [10]="ism" [11]="pl" [15]="ization" [17]="0self-" [18]="ing's"`.

Blob head hexdump:

```
00064BFC: 00 f8 d0 ff f6 08 f2 f9  b8 fe 00 f8 d0 ff f6 08
00064C0C: f2 bb 00 f8 95 f9 ff f6  08 f2 b8 fe 00 c5 ff f6
00064C1C: 08 b3 00 91 ff f6 08 f4  00 91 ff f6 08 f4 08 00
```
(`ff`/`00` density ≈ 0.085 each — consistent with ~11.6 bytes/entry × 126 k entries.)

#### 2.5.2 Letter-to-sound FSM (`LtsInfo+0x08`)

`FUN_0003f594` (line 14736) drives it: build context `"<pad>#<word>#<pad>"` with `ctx_len-1 = 3` zeros,
walk `while (rec.input_pos != 0xFF) { next = (ctx[rec.input_pos] == rec.ch) ? rec.next_if : rec.next_else }`,
then index `phone_names[rec.ch]`.

Record = 6 bytes: `u8 input_pos; u8 ch; u16 next_if; u16 next_else`.

```
001CC088: 04 72 02 00 01 00 | 04 74 04 00 03 00 | 01 30 06 00 05 00 | 02 23 08 00 07 00
          pos=4 'r'  if=2 else=1   pos=4 't'  if=4 else=3   pos=1 '0' …      pos=2 '#' …
001CC0A8: 06 6f 0a 00 09 00 | 05 69 0c 00 0b 00 | 03 77 0e 00 0d 00 | 04 6c 10 00 0f 00
```
Entry points: `LtsInfo+0x04` = letter table, `0x1EDA48` (en_US) / `0x2CEC48` (en_GB), 27 ascending `u32`:

```
001EDA48: 00 00 00 00 47 11 00 00 96 11 00 00 af 12 00 00  ba 13 00 00 09 23 00 00 …
001EDAA0: cd 51 00 00 2d 57 00 00 2e 57 00 00 70 57 00 00  9e 57 00 00 62 59 00 00
001EDAB0: 00 00 00 00                                       <- table ends (0x6C bytes)
001EDAB4: 65 70 73 69 …                                     <- phone names "epsilon", …
```

#### 2.5.3 Other tables

* **`vox_lexicon`** (`FUN_0003e1ec`, variant `0x1B`) wraps `&DAT_002f4030` → `.data.rel.ro` word `0x2E4030`
  → `"vox_en_us_kendra"` (the payload is a pointer to the voice's base name, not a table).
  Its getter `FUN_0003e25c` and the key string `"vox_lexicon"` (dump line 7809) have **no other reference** in
  either the plug-in or the engine — no reader was found `[INFERENCE: consumed by a component outside these two
  binaries, or vestigial]`.
  Separately, the `.rodata` word lists at `0x6199C..0x62634` (540 pointers: `with`, `winds`, `read`, `lipread`,
  `don't`, …) are ordinary `.data.rel.ro`-indexed dictionaries used by the token/POS logic.
* **`zdur_cart`**: `FUN_000482d0(&PTR_DAT_002f4024)` — `.data.rel.ro` `0x2E4024` → `"'"`; the surrounding
  `0x2E4048..0x2E452C` chain (773 self-pointers) is the CART tree/index graph.
* **text-processing arrays** at the very front of `.data.rel.ro`: `0x2E4014 → " \t\n\r"`, `0x2E4018 → "(){}[]"`,
  `0x2E401C → "\"'`({[", 0x2E4020 → "\"'`.,:;!?(){}[]"` — these become `text_whitespace`,
  `text_singlecharsymbols`, `text_prepunctuation`, `text_postpunctuation`.
* **diphone/unit tables are NOT in the `.so`**: they come from the vox file (§2.3) — 1,601 × 20-byte diphone-name
  records at vox `0x341FE0`, 32-byte phoneme records, frame blocks etc. The plug-in consumes them through the
  `diphonedb` variant (`FUN_00030214` builds per-unit cost records of `0x60+0x60` bytes and dispatches to four
  cost functions `FUN_0003055c/000313d0/00031868/00031cb0` keyed on the diphone flags `r/g/l/+/-`).
* `.data.rel.ro` also carries all function-valued tables: e.g. `PTR_s_x_ivona_en_us_002f8dcc` (phoneset),
  `PTR_s_epsilon_002f88fc` (LTS phone names), `PTR_DAT_002f6980` (lex aux), string pools `0x2E84F8` / `0x2EEBC4`.

---

## 3. Kendra vs Amy

### 3.1 What is *identical*

* `libttsivonavoice.so` and `libtiver.so` inside the two voice packages are **byte-identical**
  (`md5 2274b82e216f8dd4123deea94e00511c`, `md5 b381ee3b994d615c997f1b0ddd1b09bd`) — only the voice plug-in differs.
* `.text` has the **same size** in both (`0x40124`) and the **same internal layout**: comparing
  `kendra[0x1688c + i]` with `amy[0x14d90 + i]`:
  * 3,894 differing bytes of 262,436 = **1.48 %**;
  * **no differing run longer than 3 bytes** (2,009 differing 4-byte words; longest contiguous run = 3 B);
  * 2,008 of the differing bytes sit at 4-byte alignment (constant/literal slots);
  * per Ghidra function spans: **386 of 495 functions are byte-for-byte identical**; the 109 that differ contain
    only address/size constants — measured examples: `FUN_00028008` (vox loader) **0 B**, `FUN_0003256c` **0 B**,
    `FUN_00028310` 96/1,156 B, `FUN_00030020` 6/500 B, `FUN_00030214` 23/840 B, `FUN_0003e2b4` 32/1,480 B,
    `FUN_0003f594` 48/1,140 B, the `FUN_00033590` span 516/13,052 B.
* Same property *key* strings in the same order; the offsets drift `0x1AFC → 0x1B00 → 0x1B04` because the
  per-voice values differ in length (`vox_en_us_kendra` 16 B vs `vox_en_gb_amy` 13 B → +4 after NUL padding).

Conclusion: **identical code, different data** — the two binaries are the same object code linked against
per-voice data.

### 3.2 What differs

Section table:

| section | kendra | amy | Δ |
|---|---|---|---|
| `.rel.dyn` | `0xAE8 / 0x158B8` | `0xAE4 / 0x13DC0` | −0x1AF8 |
| `.text` | `0x1688c / 0x40124` | `0x14d90 / 0x40124` | start −0x1AFC, same size |
| `.rodata` | `0x569b0 / 0x28D3D8` | `0x54eb4 / 0x28CA78` | start −0x1AFC, size −0x960 (2,400 B) |
| `.data.rel.ro` | `0x2E4014 / 0xC040` (10,778 reloc words) | `0x2E2014 / 0xB180` | −0xEC0 (944 pointer slots) |

Classification of the 2,009 differing 4-byte words in `.text` (all of them constants, never instruction
patterns — see the ≤3-byte-run and 386/495-identical-function figures above):

* 1,065 words whose stored value lies inside `.rodata` in both files, and 765 whose value lies inside
  `.text` in both — i.e. pc-relative address material of the `ldr rX,[pc,#n]` + `add rX,pc,rX` idiom (the
  same idiom that materialises `"eng_version"`/`"1.6.23"` inside `register_voice`, §1.2). Verified sample:
  `0x1858C` kendra `0x49554` / amy `0x48BC4` — as `add rX,pc,rY` deltas both resolve into `.rodata`
  (`0x1858C+8+0x49554`, `0x16A8C+8+0x48BC4`), at different `.rodata`-relative positions.
  `[INFERENCE: the same interpretation applied to the remaining words of these two buckets]`
* 179 others, of which two classes are directly identifiable:
  1. the `__dso_handle` pointer of the init stub at `0x16898` (`0x2F0650` kendra / `0x2ED790` amy, i.e. `.bss`;
     this is the file's single relocated `.text` word);
  2. voice-specific **table size constants** in the CDXV literal pool and friends:

```
addr     kendra  amy     (0x182E0 pool = right after the CDXV magic word)
0x182E8  0x354   0x350
0x182F0  0x2AC   0x2A0
0x182F4  0x3B0   0x3AC
0x182F8  0x280   0x278
0x182FC  0x128   0x124
0x18300  0x2BC   0x2B4
0x1830C  0x1E8   0x1E4
```

Per-voice literals (`.rodata` content at the corresponding property block):

| property | kendra (`0x569b0+`) | amy (`0x54eb4+`) |
|---|---|---|
| `name` | `vox_en_us_kendra` @`0x56DF8` | `vox_en_gb_amy` @`0x552FC` |
| `checksum` | `1333557784` @`0x56E0C` | `1334671314` @`0x5530C` |
| `language_code` | `en-US` @`0x56E7C` | `en-GB` @`0x5537C` |
| `voice_name` | `Kendra` @`0x56E90` | `Amy` @`0x55390` |
| `voice_gender` | `Female` @`0x56EA8` | `Female` @`0x553A4` |
| `voice_age` | `36` @`0x56EBC` | `37` @`0x553B8` |
| `eng_version` | `1.6.23` @`0x569BC` | `1.6.23` @`0x54EC0` |

Locale-specific content:

* both binaries contain **both** language datasets (`US English` *and* `British English` strings, `en-US`/`en-GB`
  tables, the `FUN_00033590` dual-branch selector) — `language_code` decides at runtime;
* the actual dataset constants differ per binary (kendra en_US lex `0x64BFC/0x166E60`, en_GB FSM `0x2AE434`,
  letter table `0x2CEC48`; all re-derived from raw literal pools/GOT words);
* `.rodata` internal layout is **not a uniform slide**: the section starts differ by `0x1AFC`, but concrete
  content sits `0x2464` further along in kendra (measured: `_epsilon_` `0x1CBA5C` vs `0x1C95F8`), i.e. kendra's
  extra `0x960` bytes (its `.rodata` size surplus) are inserted **before** that point. The stored address
  constants reflect this: their kendra/amy differences cluster at `0x950/0x95C/0x960` (= layout shift minus
  section shift) and at `0x13C4/0x13C8` for other regions;
* `en_GB`-specific strings sit at `0x5537C`/`0x5E7A8` in amy and `0x60C38`/`0x60C50` in kendra.

Structure offsets (`.data.rel.ro` head, property block) are identical modulo the `0x1AFC`/section shift; the
amy `.data.rel.ro` is 944 pointer slots smaller — attributable to the smaller en_GB/en_US auxiliary tables
`[INFERENCE: exact allocation of the 944 slots not diffed entry-by-entry]`.

---

## 4. Recipe: building a compatible voice plug-in

### 4.1 What must be exported / linked

1. ELF32 ARM shared object, `DT_SONAME = libvoice_<locale>_<name>.so`, PIC, `DT_NEEDED = libm, libdl, liblog, libc`.
2. Exactly two exports, both with ELF version node **`TTS_ENGINE_1_6`** (VERDEF, `.gnu.version = 2`):
   * `register_voice@@TTS_ENGINE_1_6`
   * `unregister_voice@@TTS_ENGINE_1_6`
3. `unregister_voice` must accept exactly the pointer returned by `register_voice` and must be safe on that object
   (the stock implementation only frees it).
4. The original also carries `.init_array`/`.fini_array` slots — `.fini_array[1] = 0x1688c`, the `.text` stub
   `add r0,pc,#4; ldr r0,[r0]; b __cxa_finalize` over the pointer `0x2F0650` in `.text` (the file's single
   relocated `.text` word). Whether the engine requires them was not established `[INFERENCE]`.

### 4.2 `register_voice(const char *path)` contract

Return a 12-byte object `{ listA, listB, 0 }` where `listA` is a head-inserted linked list of
`{ const char *key, variant *val, node *next }` (12 B nodes) and `variant` is `{ uint16 tag; pad; void *payload }` (8 B).
On failure return `NULL` and set `errno` — `errno == ENOENT` is rendered as *"The vox file does not exist"* by the
engine.

Keys the engine looks up (★ = **presence is required**, the load fails with *"Invalid voice library data"*
if it is missing):

| key | type | ★ | notes |
|---|---|---|---|
| `voice_name` | string | ★ | display name (`Kendra`) |
| `language_name` | string | ★ | e.g. `US English` — only checked for presence |
| `language_code` | string | ★ | `en-US` / `en-GB` / `en-AU` / `en-GB-WLS` |
| `voice_gender` | string | ★ | `Female`/`Male` |
| `eng_version` | string | ★ | **must be exactly `1.6.23`** or the engine logs *"Voice library version mismatch: got %s, required %s"* and unloads |
| `name` | string | – | vox file base name (`vox_en_us_kendra`); engine reads it with default `"anonymous"` |
| `sample_rate` | int | – | read with default 0; must match the vox header `+0x24` (22050) |
| `custom_voice` | int | – | default 0; non-zero triggers the certificate check (`Voice not allowed by the certificate`) |

Keys only the plug-in itself uses (its own loader aborts without them): `checksum` (decimal, compared with the
vox header `+0x2C`), `voxdbname` (defaults to `name`), `diphonedb` (the parsed vox handle).

Recommended (the stock plug-in always sets them and the engine reads them with defaults):
`voice_age`, `encoding`, `diphonedb`, `vox_lexicon`, `zdur_cart`, `duration_stretch`, `duration_func`,
`diphone_graph_func`, `viterbi_beam` (50), `silence`, `text_whitespace`, `text_prepunctuation`,
`text_postpunctuation`, `text_singlecharsymbols`, `phoneset`, `syl_boundaries_func`, `xsampa_to_xivona_func`,
`xivona_to_xsampa_rules`, `wordtosegments_func`, `postlex_func`, `sentence_boundary_func`, `tokentowords_func`,
`phrasesylendtone_func`; plus list B with the ~52 feature functions (names listed in §1.6).

### 4.3 Data that must be present

* **`.rodata`/`.data.rel.ro`** — the linguistic side (§2.4/§2.5): property-key strings, variant type registry,
  word/flag lists, packed `en_XX_lex` dictionary (sorted, `0xFF`-delimited, string-pool-indexed, with
  `entry_count` + `blob_length`), its 256-slot string pool, the LTS FSM + 27-entry letter table + phone-name
  arrays, phoneset, CART/duration tables, text-normalisation tables, punctuation sets.
* **external vox file** with a `CDXV` header (§2.3): 104-byte header
  `{ 'CDXV'; char name[32]; u32 sample_rate; u32 format; u32 checksum; 7 × (u32 offset, u32 length) }`,
  the `(offset,size)` index, the 20-byte diphone-name table (`len/20` records), and the unit/frame blocks.
  Reachable either as `<dir>/<name>/<checksum>/<name>22v` (directory case) or as the path passed in
  `register_voice(path)`.

### 4.4 Invariants the engine will check

1. `dlopen` + `dlsym("register_voice")` succeed (symbol must exist with the right version node).
2. `register_voice(path) != 0`; `errno` semantics on failure (2 → *"The vox file does not exist"*).
3. Property presence: `voice_name`, `voice_gender`, `eng_version`, `language_name`, `language_code`.
4. `strcmp("1.6.23", eng_version) == 0` (exact).
5. `custom_voice` (int, default 0) passes `FUN_0004dee4(context, voice_name, language_code, custom_voice)`
   — *"Voice not allowed by the certificate"*.
6. Vox header: magic `0x56584443`, `name == ` plug-in `name`, `atol(checksum) == header+0x2C`,
   `sample_rate` at `+0x24`, format id ∈ {2, 8, 12, 14}, and five section offsets (`+0x40,+0x48,+0x50,+0x58,+0x60`)
   non-zero — otherwise the *plug-in* reports *"**Error: file `%s' lacks needed features"* and `register_voice`
   returns NULL.
7. Phoneme set / sample rate are consumed later (`diphonedb`, `sample_rate`); the engine additionally installs
   `sample_rate` from *its own* header read (`libttsivonavoice.c` line 42957), so a mismatch between the voice's
   `sample_rate` property and the vox header would be visible to the engine `[INFERENCE: no explicit comparison
   was found]`.
8. Data directory: `IVONA_LANG_DAT_DIR` if set, else the directory of the plug-in path (engine walks backwards
   from the end of the path with `strchr("/\\", c)`, line 28081 ff.).

---

## 5. Not determined / what was tried

1. **Exact pronunciation code inside lexicon entries** — the word part decodes cleanly (§2.5.1) but the
   `0xFF`-terminated tail after each `0x00` was only identified as a variable-length byte sequence
   `[INFERENCE]`. Tried: raw decoding with the 256-entry pool, entry-boundary statistics (0xFF/0x00 both ≈ 8.5 %),
   cross-referencing `LexInfo+0x1C` (pointer table `0x2E80F4`, whose payloads are short byte blobs such as
   `"\x02\x11\r\x17"`). Not closed: mapping tail bytes → `LexInfo+0x10` phone indices.
2. **Variant type tag ↔ name mapping** (beyond `0x1F diphonedb`, `0x1B lexicon`). Tried: the `.rodata` name run
   and the `{name, code}` registry at `0x2EFB90..0x2EFCFC`; the ordering does not line up with the two known tags,
   and the registry has a hidden entry between `diphonedb` (`0x2EFCA4`) and `wavesynth` (`0x2EFCB4`).
3. **Who re-opens the vox file for record reads.** `FUN_00028008` `fclose`s after mmap; `FUN_00027bd0` keeps a
   `FILE*` but has **no call site** in the decompilation (searched `FUN_00027bd0(`/`FUN_00027f90(` and raw address
   words `0x17BD0/0x17F90` — zero hits; pc-relative `bl` targets are invisible to a raw-word search). Either
   indirect/dead code, or reached through a table I did not resolve.
4. **How the Android app supplies the vox path** (OBB path vs. extracted
   `<dir>/vox_en_us_kendra/1333557784/vox_en_us_kendra22v`). The shipped OBB header satisfies every check, but the
   path-construction string ends in `"22v"` with no dot and the OBB lives at
   `Android/obb/<pkg>/main.199.<pkg>.obb`. Tried: APK listings (`unzip -l` — only the three `.so`s, no data),
   engine strings (`IVONA_LANG_DAT_DIR`, `main.`/`patch.` absent from `libttsivonavoice.so`).
5. **Why the mmap covers only `0x182E8D8` (25.3 MB) of a 152 MB file** — resolved in part: record reads use
   `fseek`/`fread` helpers (`FUN_0002e490`), and `FUN_0002bddc` retains the `fd`. The exact accessor used for the
   426,991 index pairs (offsets pointing at `0x07FABF03..0x083C1FE7`) was not traced end-to-end.
6. **Codec/format ids**: the `switch(header+0x28)` installs decoder triples only for cases 2, 8, 12, 14
   (`FUN_0002d7f0`, `FUN_0002e244/FUN_0002e208/LAB_0002df34`, `DAT_0002ea50/FUN_0002ea14/FUN_0002e490`,
   `FUN_0002de60/LAB_0002d8ac/LAB_0002dc84`); cases 3–7, 9–11, 13 fall through to failure. What the ids mean
   (codec flavour) was not determined.
7. **Host `objdump` cannot disassemble ARM** (`objdump: can't disassemble for architecture UNKNOWN`, no
   `llvm-objdump`). The first pass was hand-decoded from hexdumps; a later pass found capstone in
   `/home/asdf/venvs/re` and re-verified every listing in §1.2/§2.2 (`0x1688c..0x168D8`, the three CDXV pool
   sites `0x17CB0/0x17FD8/0x182D0`, and the `FUN_00033590` prologue `0x23590..0x235CC`) — all match.
   Beyond those sites the report relies on the Ghidra C output rather than instruction listings.
8. **Amy-only structures** were read from raw bytes (property block, section tables, `.text` diff); amy's Ghidra
   dump was not produced, so amy claims rest on byte comparison rather than decompilation.

### Scratch artefacts (allowed location)

`scripts/06_rodata_map.py` (entropy/printable map + ASCII-run scan), `scripts/08_refs.py`
(Ghidra `DAT_` reference → `.rodata` clustering). Scripts `01`–`05` pre-date this report and analyse the OBB.
No binary was modified.
