# libttsivonavoice.so — synthesis pipeline and voice data formats

Reverse-engineering report (IVONA 2 TTS core, `out/libs/kendra/libttsivonavoice.so`,
ARM ELF32, 1,637,476 bytes).

## 0. Conventions and evidence base

* **Address convention.** The Ghidra dump `out/ghidra_dump/libttsivonavoice.c` was produced with
  image base `0x10000`: **dump address = ELF vaddr + 0x10000** (e.g. dump `0x48464 : tts_load_certificate`
  = ELF dynsym value `0x38464`). All addresses cited below are *dump* addresses as they appear in the
  `// ----- <addr> : <name> -----` headers. `readelf --dyn-syms` gives the ELF values (subtract `0x10000`).
* **File offsets.** `strings -t x <so>` prints file offsets; for `.text` (vaddr `0x184a8`) and `.rodata`
  (vaddr `0x144978`) file offset == vaddr, so a string found at file offset `F` is referenced from code as
  dump address `F + 0x10000`. For `.data.rel.ro*`/`.data`, vaddr = file offset + `0x1000`
  (`.data.rel.ro.local` vaddr `0x17f678` / file `0x17e678`), so dump address = file offset + `0x11000`.
* **Helper.** `python3 scripts/fn_at.py <dump.c> <line>` maps a dump line to its enclosing function;
  `--name <substr>` lists matching function headers.
* Citation style: `libttsivonavoice.c:<line> (<function> @ <addr>)`. Hypotheses are marked **[INFERENCE]**.
* Parallel investigations (voice-plugin tables, OBB container walk, certificate decoding) are cross-referenced
  by their file/byte evidence where noted.

---

## 1. Pipeline: input text/SSML → PCM

### 1.1 API surface and object model

The library exports a flat C API which the JNI bridge (`libttsivona.so`) reaches through the
`CIvonaTTS` vtable built in the constructor (`libttsivonavoice.c:2030`, `CIvonaTTS::CIvonaTTS @ 0x284cc`):

| vtable off | function | dump header |
|---|---|---|
| +0x00..+0x08 | `tts_vendor_tag`, `tts_errno`, `tts_errmsg` | 0x473ac / 0x473bc / 0x473cc |
| +0x0c / +0x10 | `tts_init`, `tts_create` | `libttsivonavoice.c:25597` (0x486e0), `:25319` (0x48230) |
| +0x14 / +0x18 | `tts_load_certificate_file`, `tts_load_certificate` | `:25615` (0x4871c), `:25479` (0x48464) |
| +0x1c..+0x24 | `tts_destroy`, `tts_certificate_get`, `tts_certificate_get_single` | 0x4815c / 0x483b8 / 0x482e4 |
| +0x28..+0x34 | `tts_load_voice`, `tts_unload_voice`, `tts_voice_param`, `tts_voice_sample_rate` | `:27971` (0x4c028), 0x4c5b0, `:26489` (0x49f78), `:27780` (0x4bc64) |
| +0x38..+0x4c | `tts_dict_insert/remove/save/load/num_entries/cleanup` | 0x47158 / 0x46d28 / 0x45f64 / 0x46a6c / 0x46ce4 / 0x4738c |
| +0x50 / +0x54 | `tts_pls_load`, `tts_pls_unload` | 0x4c6a8, 0x4bd94 |
| +0x58..+0x6c | `tts_streamer_start/stop/jump/add_voice/synth0/synth` | `:27117` (0x4ac38), `:27060` (0x4ab34), 0x4a898, `:27648` (0x4b8d4), `:27437` (0x4b460), `:27492` (0x4b51c) |
| +0x70 / +0x74 | `tts_wave_delete`, `tts_get_input_warning` | 0x4a9b4, `:26837` (0x4a7d4) |

`tts_create @ 0x48230` allocates the engine object (magic `0x3e1b8f65`, parameter vectors, a global
voice list, `FUN_000518b4` state) after `FUN_001264f0(3)` — a **libcurl** global init; failure yields
`"CURL initialization error: %s"` (error code 10, `libttsivonavoice.c:25319-25345`). The engine embeds
a full HTTP client used for SSML base-URI / lexicon fetches (`eng_ssml_base_uri`, `eng_fetch_function`
params, string file offsets `0x145d00-0x145d40`).

Objects: **engine** (`tts_create`) → **voice** (`tts_load_voice`, one per plugin) → **streamer**
(`tts_streamer_start`, one utterance-stream) → **wave** (24-byte result, see §4.1).

### 1.2 Streamer start — input admission

`tts_streamer_start(tts, text, rate)` (`libttsivonavoice.c:27117`, 0x4ac38):

1. Validates handles; `FUN_0004e028 @ 0x4e028` gates the call (certificate state; error 2).
2. Clamps the requested rate float against voice limits (`*(engine+0x18)` / `*(engine+0x1c)`, float
   compares against `0xbf800000` = −1.0f and `0x3f800000` = 1.0f).
3. `FUN_0004ab68 @ 0x4ab68` (`libttsivonavoice.c:27077`) creates the streamer (0x44-byte object:
   `[1]` utterance vector, `[6]` document (`FUN_00054314`), `[7]` clamped rate, `[0xe]/[0x10]` lists,
   `[0xf]` flag).
4. `FUN_0004a2d4 @ 0x4a2d4` (`libttsivonavoice.c:26683`) **admits the input**:
   * reads voice params `eng_input_type` (default `""`) and `eng_text_encoding` (default `"UTF-8"`);
   * **if the certificate has not enabled SSML** (`FUN_00048034(...)` → `+0x28` = the active
     certificate's `Extension-SSML` flag; the same flag gates `FUN_000491b4`'s
     `"The certificate does not allow for SSML input"` at `:26005-26006`, parsed from the
     `Extension-SSML` attribute at `:29904-29919`) the input is **always**
     plain-text-wrapped regardless of `eng_input_type`; otherwise `eng_input_type` decides;
   * `text/plain` (or empty type): the raw text is **wrapped into a
     synthetic SSML document** — root element created by `FUN_00056d8c @ 0x56d8c` with name
     `"http://www.w3.org/2001/10/synthesis^speak"` (namespace-tagged `speak`), attribute `version`
     set from string `DAT_00155f94` (file `0x145f94` = **`"1.1"`**, proven) and `xml:lang` from the
     voice default language (`libttsivonavoice.c:26706-26740`, repeated 3× for the three admission paths);
   * `application/ssml+xml`: `FUN_000552dc @ 0x552dc` (encoding conversion) → `FUN_0003d998 @ 0x3d998`
     (`libttsivonavoice.c:18837`) **parses the SSML/XML with embedded expat**: `XML_ParserCreate`
     `FUN_000fa864("UTF-8", 0x5e)` (`:18914`, namespace separator `'^'`), user data (`:18922`),
     **element handlers `FUN_0003e1f0` (start) / `FUN_0003d5e0` (end)** (`:18923`, bodies
     (`:19131`/`:18683`), further handlers (`:18924-18927`), namespace registration
     `"ivona"` → `http://www.ivona.com/2009/12/ssml` (`:18928`; also `:18953`), `XML_Parse`
     (`:18929`); SSML fragments without `<speak>` are wrapped textually (`"<speak>"` prepend
     `FUN_000536e4 :18885-18890`). **Element name→type table `DAT_0018fe00`** (file `0x17ee00`,
     rows `{char* name, u32 type}`), byte-proven: `audio`2, `break`3, `desc`4, `emphasis`5,
     `lang`6, `lexicon`7, `lookup`8, `mark`9, `meta`10, `metadata`11, `p`/`paragraph`12,
     `phoneme`13, `prosody`14, `s`/`sentence`15, `say-as`16, `speak`17, `sub`18, `voice`19,
     `w`/`token`20 (type 1 = text nodes, created directly). On success `doc+0x18 = 1` marks
     "input is SSML" and `FUN_0003b4d8 @ 0x3b4d8` normalises encoding (`:26755-26770`);
   * unknown type: `FUN_000561d4 @ 0x561d4` sniffs whether the text is markup; if yes → parse as SSML,
     else fall back to the plain-text wrapper (`libttsivonavoice.c:26775-26815`);
   * `FUN_0003c7f8 @ 0x3c7f8` (`libttsivonavoice.c:18143`, uses `eng_ssml_base_uri` at `:18184`) runs
     **SSML semantic validation** (namespace/element checks — produces the input warning);
     `FUN_0003f638 @ 0x3f638` (`libttsivonavoice.c:19954`) builds the **utterance/sentence list**;
     `FUN_0003d508 @ 0x3d508` installs the **mark table** into `streamer+0x28` from `doc+0x1c`
     (`libttsivonavoice.c:26824-26833`) — this table later yields mark type 3 (§4.3).
   * Non-zero return = start failure; warnings are retrievable later via `tts_get_input_warning @ 0x4a7d4`
     (`streamer+0x20 → +0x24/+0x28` lists, `libttsivonavoice.c:26837-26870`).

### 1.3 The pump: `tts_streamer_synth` → `FUN_0004ae28`

`tts_streamer_synth(handle, maxSamples)` (`libttsivonavoice.c:27492`, 0x4b51c):

```
do { produced = FUN_0004ae28(streamer, maxSamples-need, 0, &wave); push wave;
} while (produced != 0 && need < maxSamples);
merge waves [0..n] → one 24-byte wave (sample_rate, total samples, concatenated int16,
                     mark array with rebased sampleOffsets); free inputs; return wave
```

Merge details (`libttsivonavoice.c:27560-27650`): sums `wave+4` (sample counts) and `wave+0xc`
(mark counts), `malloc(total*2)` for samples, `malloc(numMarks*0x14)` for marks, `memcpy`s each
segment, and rebases every mark's `sampleOffset` by the running sample base `iVar8`
(`*(dst+0x10) = iVar8 + *(src+0x10)`). If there is exactly 1 wave it is returned as-is
(`libttsivonavoice.c:27545-27552`). `tts_streamer_synth0 @ 0x4b460` is the raw variant that copies
int16 samples straight into a caller buffer (`libttsivonavoice.c:27437-27485`).

`FUN_0004ae28 @ 0x4ae28` (`libttsivonavoice.c:27233`) is the per-chunk pump:

1. **Limits check**: if `streamer+0x3c` set → `FUN_000539a0 @ 0x539a0` ("Limits verification error",
   code 10) — certificate-driven synthesis limits (`libttsivonavoice.c:27246-27253`).
2. **Utterance production**: while `streamer+8` (current sentence index) ≥ utterance-vector size
   (`FUN_0005575c` = vector size, `FUN_000557b8` = vector get), call
   `FUN_00040770 @ 0x40770` (`libttsivonavoice.c:20605`) on the front-end ctx — the **front-end
   top** (also driven by `tts_streamer_jump :26926`); `-1` = fatal, return = number of new
   utterances (`:21392-21403`). No more utterances → return 0 (end of stream) (`:27270-27286`).
   * **Ctx** (built by `FUN_0003f638 @ 0x3f638 :19954-19993`): `[0]` utterance output list
     (= the vector the pump reads), `[1]` SSML doc ctx, `[2]` voice list, `[3]` token/sentence
     builder (`FUN_00042734 @ 0x42734 :21816-21903`), `[5]` DOM event queue seeded with the
     `<speak>` root (`:19975`), `[6]` interpret-as/lexicon stack (primed with document lexicons
     `:19998-20005`), `[8]` error flag, `[10]` utterance stack seeded with the root (`:19984`).
   * **Event state machine** over element types: text nodes (type 1) are decoded
     (`FUN_000545a0 :20797`), punctuation-scanned (`FUN_000425d8 :20800`), tokenised
     (`FUN_00044c1c @ 0x44c1c :20807`, body `:22989`, honouring voice `text_*` params
     `:23000-23027` — whitespace/single-chars/pre-post-punctuation) and per-word processed by
     `FUN_00043bb0 @ 0x43bb0` (`:23090`, body `:22522`). Element cases dispatch to builders:
     `audio`(2) `FUN_00043348 :20890`; `break`(3) `FUN_000436a8 :20905` (time clamp 120 s,
     `0x42f00000 :20897`); `emphasis`(5) level scaling `:20915-20945`; **`lexicon`(7)** checked
     with the SSML-1.0 guard (`FUN_0003b044 :20919-20924`); `lookup`(8) matches its
     `name` attr against the loaded-lexicon table (doc+8, stride 0x2c, `:20936-20946`) and pushes
     the lexicon onto the stack (`FUN_0003f300 :19795-19830`); **`mark`(9)** records name+position
     into **`doc+0x1c`** — the mark FIFO later installed at `streamer+0x28` (`:20965-20984`);
     `p`(0xc, type 12) adjusts the **paragraph** depth counter (`builder+8`) via
     `FUN_00042b24 :21999` (open) / `FUN_00042a6c :21966` (close, sets flush flags +0x1c/+0x18);
     `s`(0xf, type 15) adjusts the **sentence** depth counter (`builder+0xc`) via
     `FUN_0004290c :21904` / `FUN_000429bc :21935` (flag +0x18); both force a sentence flush when
     the token's `punc` attr (key `DAT_001565c8` = `"punc"`) ends in `".!?"` (`strchr :22139`);
     `phoneme`(0xd) alphabet id (`FUN_0004cfe8 :21003`) with
     native/conversion modes (`FUN_0004349c :21022`, `FUN_0004cf50 :21028`); `prosody`(0xe)
     `:21046-21157`; `say-as`(0x10) `FUN_0003f058/FUN_000423cc :21172-21174`; `sub`(0x12)
     `FUN_0003af58 :21181`; `voice`(0x13)
     attribute validation (age/gender/variant/name/languages/order/required/onvoicefailure,
     `:21185-21235`) and selection `FUN_00040104 @ 0x40104` (`:21239`); `w`(0x14, type 20) token
     element; the common tail validates xml:lang against voice languages with
     `onlangfailure=changevoice|ignoretext|ignorelang` (`:21268-21360`) and strips ivona-namespace
     attrs (`:21247-21260`, lang stack `FUN_00042374 :21616`). Open events push onto `[10]`,
     spoken children re-queue to `[5]` (`:20835-20844`, `:21380-21388`).
   * **Sentence rotation & flush**: `FUN_00042d28 @ 0x42d28 (:22075)` / `FUN_00043bb0
     (:22640-22675)` rotate sentences; flush `FUN_00042bdc @ 0x42bdc (:22032)` snapshots the
     WordInfo list (`FUN_00039f24 :16295-16320` via `FUN_00045498 @ 0x45498 :23251-23570`) and
     pushes it onto the output list (`:22056`).
3. **Task creation** (first chunk of an utterance): `FUN_00039e78 @ 0x39e78` creates the synthesis task;
   `FUN_0005aa88 @ 0x5aa88` (`libttsivonavoice.c:39007`) initialises it: requires the `Token` relation
   (`FUN_00059744`), runs `FUN_00064fbc @ 0x64fbc` (state copy + `deterministic_path` param: if 0,
   re-seeds `srand48(time(NULL))`, `libttsivonavoice.c:46175-46196`), then runs the **utterance
   processing pipeline** `FUN_00064f38 @ 0x64f38` (§1.4).
4. **Prosody parameters** are copied from the voice parameter set into the task each chunk:
   `duration_stretch` and `amplify` via `FUN_0005b16c` (get typed param) + `FUN_0005af44` (set param)
   (`libttsivonavoice.c:27288-27298`).
5. **Synthesis step**: `FUN_0005a698 @ 0x5a698(task, wantSamples, &events)`
   (`libttsivonavoice.c:38850`) → returns the produced chunk `{+4: sample_rate, +8: nSamples,
   +0x10: int16*}` or 0. On 0 with utterance exhausted → advance sentence index and reset.
6. The chunk is wrapped into a **wave** (`malloc(0x18)`): `[0]=sample_rate, [1]=nSamples,
   [2]=samples, [5]=chunk-result object`, then marks are appended from the event list (§4.3)
   (`libttsivonavoice.c:27350-27425`).
7. **Position callback**: running total `streamer+0x14 += nSamples`;
   if `streamer+0x1c` (rate) ≠ −1.0f, computes `ms = progress_ratio × 1000 / rate` and calls
   `FUN_000542b4 @ 0x542b4(document, ms)` (`libttsivonavoice.c:27456-27472`) — i.e. an
   audio-position-in-ms callback into the document/bridge layer **[INFERENCE on the exact consumer]**.

### 1.4 The utterance processing pipeline (voice-overridable stages)

Three static stage tables live in `.data.rel.ro` (file offsets `0x184160`, `0x1841a8`, `0x1841f8`;
dump addresses `0x195160`, `0x1951a8`, `0x1951f8`; each row = 8 bytes `{char* stage_name, code* default_fn}`,
terminated by a NULL name). They are walked by:

| runner | table | stages (in order) |
|---|---|---|
| `FUN_00064f38 @ 0x64f38` (`:46146`) | `DAT_00195160` (file `0x184160`) | `text_analysis_func`, `pos_tagger_func`, `phrasing_func`, `lettertosound_func`, `pause_insertion_func`, `postlex_func`, `intonation_func`, `duration_func` |
| `FUN_00065028 @ 0x65028` (`:46198`) | `DAT_001951a8` (file `0x1841a8`) | `tokenizer_func` + the same 8 |
| `FUN_000650b0 @ 0x650b0` (`:46225`) | `DAT_001951f8` (file `0x1841f8`) | `tokenizer_func`, `text_analysis_func` (alt default `0x56230`), `phrasing_func`, `lettertosound_func`, `pause_insertion_func`, `intonation_func`, `duration_func` (no `pos_tagger`/`postlex` rows) |

Runner logic (`libttsivonavoice.c:46146-46195`):

```c
for (row = table; result && row->name; row++)
    if ((fn = voice_param_get(params, row->name)) == 0)   /* voice override?  */
        result = row->default_fn ? row->default_fn(result) : result;
    else
        result = call_voice_fn(fn, result);
```

i.e. **every stage is looked up in the voice parameter set by stage name first; otherwise the engine's
built-in default (table value) runs**. Default implementations in `.text` (ELF vaddrs; add `0x10000`
for dump): `tokenizer_func 0x574f8`, `text_analysis_func 0x5706c / 0x56230`, `phrasing_func
0x56dc4`, `lettertosound_func 0x567e0`, `pause_insertion_func 0x566c8`, `intonation_func 0x56554`.
`pos_tagger_func` and `postlex_func` defaults are NULL; `duration_func` default is NULL (row at file
`0x184198` = `"duration_func"`; the Kendra plugin *registers* `duration_func` as userdata
(plugin `:7816-7818`) and also ships `zdur_cart` — per-voice duration modelling **[INFERENCE]**).

**Decompilation coverage of the defaults** (verified): present — `text_analysis_func` default =
`FUN_0006706c @ 0x6706c` (`:46944`, the tokentowords applier) and `tokenizer_func` default =
`FUN_000674f8 @ 0x674f8` (`:47091`, re-splits text with voice params `text_whitespace`,
`text_singlecharsymbols`, `text_prepunctuation`, `text_postpunctuation` `:47105-47108`); **missing
from the dump** — the other five default bodies (dump `0x66230`, `0x66554`, `0x666c8`, `0x667e0`,
`= text_analysis#2 / intonation / pause_insertion / lettertosound / phrasing`; their addresses fall
between the headers `FUN_00065c0c :46745` and `FUN_0006706c :46944` but no code is emitted for them)
— see §6. In practice Kendra overrides every language-specific stage anyway (§1.4 evidence below).

The three runners are invoked from the task wrappers `FUN_0005aa88 / FUN_0005aaec @ 0x5aaec
(:39030) / FUN_0005ab78 @ 0x5ab78 (:39050)` — i.e. different entry paths (plain utterance,
`FUN_0005abd0 @ 0x5abd0 (:39070)` = one-shot) select which table runs
(`libttsivonavoice.c:39007-39090`).

**Stage content evidence**

* **G2P / token expansion**: `tokentowords_func` is applied per `Token` by `FUN_0006706c @ 0x6706c`
  (`libttsivonavoice.c:46944-47060`): tokens carrying a `phones` or `xsampa` attribute bypass
  conversion; suffixes `"?^"`/`"?_"` set an `endtone` feature (`:46964-46981`); the literal
  `\PSA{...}` notation injects a phoneme string directly (`:46984-47010`); otherwise the
  `tokentowords_func` voice callback is called (`:46948`, call `:47012-47020`). The **engine
  default `FUN_0005d6b0 @ 0x5d6b0 (:41729)` is an identity wrapper** — all real language logic is
  injected by the plugin: `libvoice_kendra.c FUN_0003256c (:9411-9510)` registers
  `tokentowords_func → DAT_00037c5c`, `sentence_boundary_func`, `phrasesylendtone_func →
  DAT_00032d20`, `syl_boundaries_func`, `wordtosegments_func`, `postlex_func`,
  `xsampa_to_xivona_func`, `text_*` params and `num_digits` rules; `FUN_00033590 (plugin
  :9530-9620)` installs the resources **`en_us_lex_lts`** (letter-to-sound) and the binary
  lexicon **`en_us_lex`, size 0x1ee0c** (en-GB: `en_gb_lex`, 0xf126). **Number/date/time/ordinal
  expansion lives entirely in the plugin**: `FUN_000387d0 @ 0x387d0 (plugin :10259-11142)` with
  `"hundred"` `:10499`, `"thousand"/"million"` `:11795/:12009`, digit-word table `DAT_002fd528`
  `:12044`, ordinals `:12372-12382`, time words `:12494` — none of these strings exist in
  `libttsivonavoice.so`.
* **Phoneme alphabets** (`<phoneme alphabet>`): `FUN_0004cfe8 @ 0x4cfe8 (:28639)` maps
  `""`/`"ipa"` → 3, `"x-ivona"` → 1 (native), `"x-sampa"` → 2, `"nt-sampa"`/`"navteq"` → 4+lang
  (table `DAT_00190850`); `FUN_0004cf50 (:28601)` converts IPA → internal via `FUN_0004cbf8`
  (`'#'→' '`, `'$'→'.'`, `:28611-28625`).
* **User dictionary**: `user_lexicon` param set by `FUN_0005a608 @ 0x5a608 (:38814-38828)` from
  `FUN_0006519c @ 0x6519c (:46278-46344)` ("IVONA_Lexicon"-header text files → word→phoneme alist;
  errors `"IVONA_Lexicon: Missing file header"` `:46339`); query helper `FUN_00065138 @ 0x65138
  (:46252-46275)` with key `"%c%s"`. No engine-side call sites — **[INFERENCE]** consulted from the
  voice's tokentowords path (the plugin has its own IVONA_Lexicon reader,
  `libvoice_kendra.c:23940+`). The exported `tts_dict_*` PCRE-rewrite API (§2.4) is host-facing
  normalisation, not on the hot phonemization path. PLS lexicons (§2.5) are pushed onto the
  front-end lexicon stack (`ctx+6`, `:19998-20005`, per text node `:20858-20869`, `<lookup>`
  `:19827`) — **[INFERENCE]** the consuming lookup happens inside the voice's `tokentowords_func`.
* Sentence splitting: `FUN_00042734 @ 0x42734 (:21816)` reads `eng_max_sentence` (`:21843`) and
  `eng_sentence_break` (float default `0x3ecccccd` = **0.4 s**, `:21874`);
  `FUN_00042d28 @ 0x42d28 (:22075)` calls the voice's `sentence_boundary_func` (string file `0x146644`;
  present in `libvoice_en_us_kendra.so` file `0x60d3c`) at `:22113/:22591/:22750/:22932`.
  `sentence_boundary_func` is fetched as a voice param via `FUN_0005b18c` (`:39582+`); when absent,
  the default heuristic marks a boundary iff the token's last char is in `".!?"` (`strchr :22139`)
  with single-letter-abbreviation rejection (`:22117-22136`); when present it is resolved
  (`FUN_0005922c :37569`) and invoked as `fp(token)` — nonzero = boundary (`:22166-22172`).
  The splitter itself is `FUN_00043bb0 @ 0x43bb0 (:22522-22987)`, windowing the input buffer in
  slices of `param_1[0x14]` (`:22556-22560`); a boundary ends the current sentence record whose
  text span later becomes the type-2 SENTENCE mark (§4.3).
* Phoneme strings on segments are cross-checked against the engine's `xsampa`⇄`xivona` mapping:
  `xivona_to_xsampa_rules` param (`:46773`), `"xsampa"` feature reads (`:22217`, `:22822`, `:23497`),
  `xsampafunc` VAL entry (`:46394`); the voice provides `xsampa_to_xivona_func`
  (voice string file `0x60c8c`).

#### Prosody: SSML `<prosody>` → token params → waveform

* **Attribute parsers** (produce a 3-slot triple, default `{1,1,1}` `FUN_0003969c :15857`):
  volume `FUN_000396b0 @ 0x396b0` (`:15865-15965`), rate `FUN_00039948 @ 0x39948`
  (`:15970-16040`, SSML 1.0 rejects relative forms `:15993`), pitch `FUN_00039b40`
  (`:16044-16160`); SSML-1.1 deprecation warnings for single-number/percentage volume and
  relative-rate forms (`:15923-15951`, `:16020-16034`, unsigned pitch percentage `:16138`).
  **Named tables (byte-proven)** — volume `DAT_0018fd68` (file `0x17ed68`, rows `{char*, float}`):
  `silent` 0.0, `x-soft` 0.625, `soft` 0.79058, `medium` 1.0, `loud` 1.2649, `x-loud` 1.6
  (≈ 10^(dB/20) steps of ±2/±4 dB); rate `DAT_0018fda0` (file `0x17eda0`): `x-slow` 0.66667,
  `slow` 0.81653, `medium` 1.0, `fast` 1.22470, `x-fast` 1.5; decibel volume via `10^(dB/20)`
  (`:15919-15930`). Pushed/popped per `<prosody>` scope by `FUN_000423a0 @ 0x423a0` (`:21640`,
  stack at builder+0x68; current triple `FUN_0004251c @ 0x4251c :21723`).
* **Per-token params** written by `FUN_00043bb0` (`:22710-22735`): `amplify` = volume,
  `duration_stretch` = **1/rate clamped ≥ 0.05**, `pitch_stretch` = **1/pitch clamped to
  [0.9, 1.1]**; carried into the WordInfo snapshot (`FUN_00045498 :23385-23549`); voice-level
  clamps come from param setters `FUN_000494a4` (`"param_##p_l##_min"` `:26139-26142`); the pump
  additionally copies voice-level `duration_stretch`/`amplify` onto the chunk (`:27299-27306`).
* **Application** happens per diphone in `FUN_0005d7c4` (§1.7): base durations come from the
  diphone DB duration shorts (stride 0x24, ms→s `:42256-42264`), pauses from the Segment `end`
  feature with pad/trim (`FUN_00063350/62718`), then token×voice `pitch_stretch` /
  `duration_stretch` / `compress` / `amplify` are applied via `FUN_00063540 / FUN_00062d14 /
  FUN_00063850 / FUN_00062c54` (`:42340-42400`). Phone-level *target* durations/pitch come from
  voice-side models (`duration_func`/`zdur_cart`/intonation stage — §1.4, §6).

### 1.5 Core synthesis: diphone graph + Viterbi (`FUN_0005a698` → `FUN_0005d7c4`)

`FUN_0005a698 @ 0x5a698` (`libttsivonavoice.c:38850`) drives one synthesis step:

1. `FUN_0005d7c4 @ 0x5d7c4` (`libttsivonavoice.c:41802`) does the real work and also returns an
   **event list** (through its 3rd parameter) — the raw material for marks (§4.3).
2. It converts the events into **mark nodes**: utterance-level events become nodes with flag bits
   (see §4.3), using Festival-style relation navigation
   (`FUN_00058e4c` = relation get, `FUN_00059334` = `R:<name>`, `FUN_00062124` = feature-path resolve,
   `FUN_00058fec` = feature get; path grammar implemented in `FUN_00061d28 @ 0x61d28 (:44267)` which
   understands `p`/`n`/`pp`/`nn`/`parent`/`daughter`/`daughtern`/`R:<rel>` steps).

`FUN_0005d7c4 @ 0x5d7c4` (lines 41802–42454) is the **unit-selection heart**:

1. **Voice params fetched**: `diphonedb` (`:41837`), `diphoneset_num` (`:41912`), `diphone_graph_func`
   (`:41926/:42018`), `resample_wave` (`:42104`), `viterbi_beam` (int, default −1, `:42076`).
2. **Diphonedb open**: `FUN_0005f3cc @ 0x5f3cc (:42684)` obtains the diphonedb object, and
   `FUN_0005f064 @ 0x5f064 (:42513)` **opens the CDXV container** backing it (§2.1) on the object at
   `diphonedb+0x20`; the opened streamer state (`FUN_00061b20 @ 0x61b20 (:44119)`) stores the container
   header field at `*(state[3]+4) = *(*handle + 0xc)` (`libttsivonavoice.c:41842-41857`).
3. **Diphone pair construction**: for each segment chain position, the left/right segment names are
   formatted as `"%s-%s"` (`snprintf(acStack_34,10,"%s-%s", left, right)`, `:41958`), looked up in the
   diphonedb name table by **binary search** `FUN_0005ef00 @ 0x5ef00 (:42419)`
   (`strcmp` against entries of stride **0x14 = 20 bytes** at `diphonedb+0xc`, count at `+8`;
   returns `0xffffffff` if absent) and the resulting index is stored as the `diphoneset_num` feature
   (`FUN_00058fac`). The walk stops at a segment named `"pau"` (`:41975`).
4. **Graph construction**: the voice-provided `diphone_graph_func` (fetched via
   `FUN_0005b10c @ 0x5b10c (:41926)`, unwrapped by `FUN_0005d724 @ 0x5d724 (:41761)`) is called as
   `graph = graph_func(utterance, feature_array, count)` (`:41990/:42085`). The feature array is built
   by `FUN_00060ed4 @ 0x60ed4 (:43702)` — a **0x60 = 96-byte feature vector per segment**
   (§1.6); the array has `count+2` slots (a copy of the first and last segment are prepended/appended,
   `:41960-41984`). The graph is cached on the streamer state (`state+0x20`), the R:Unit chain head on
   `state+0x28`.
5. **Viterbi beam search**: `FUN_0005fc04 @ 0x5fc04 (:43094)` runs the search with `viterbi_beam`
   fetched as `FUN_0005b230(*params,"viterbi_beam",0xffffffff)` at `:41971/:42063` (default −1 =
   no beam limit), while `FUN_00049448 @ 0x49448 (:26087-26107)` stages `state+0xc = beam` and
   `state+0x10 = beam>>1` with **50 / 25** as fallback when the param is ≤ 0 (the Kendra plugin
   registers `viterbi_beam = 50`, plugin `:7829`). It evaluates candidate diphones by calling the
   **cost callback `(*graph+2)(left_record, right_record, ctx_left, ctx_right)`** — the two decoded
   record/name buffers (`auStack_88`/`auStack_e8` from `FUN_0005f1dc`) plus context pointers
   (`:43143-43155`) — over records of stride 0x24 = **36 bytes**
   (read by `FUN_0005f1dc @ 0x5f1dc (:42602)`; record stride `0x24` also visible in the waveform step
   at `:42256-42263`), applies context filters (`strcmp(ctx,"+")`, context char compare
   `:43160-43180`), a min/max cost histogram (51 buckets, `0x33`, `:43195+`) and returns the winning
   path. The path is written back as `diphone` attributes on the R:Unit items
   (`FUN_00058fcc(item,"diphone",…)`, `:42005/:42098`); optional `dp_debug_func` hook at `:42117`.
   **[INFERENCE]** the cost callback is also voice-supplied (it is a code pointer inside the graph
   object returned by `diphone_graph_func`).
6. Then the assembly loop runs (§1.7) — until enough samples exist (`state+4` vs `param_2`) or units
   are exhausted; then `FUN_000618a8 @ 0x618a8` finalises the chunk (§1.7) and, if the voice param
   `resample_wave` exists, `FUN_00059958 @ 0x59958` resamples it (§1.8).

**Segment feature vector** (`FUN_00060ed4 @ 0x60ed4`, `libttsivonavoice.c:43702-43890`; offsets in the
0x60-byte struct; float = 4 bytes, byte fields as noted):

| off | type | feature (Festival-style path) |
|---|---|---|
| +0x00 | float | duration = `end − p.end` |
| +0x04..+0x14 | ptr | `p.p.name`, `p.name`, `name`, `n.name`, `n.n.name` (phoneme names) |
| +0x18/+0x19 | s8 | `pos_in_syl+1`, `(1−pos_in_syl)+syl_num_phones` |
| +0x1a..+0x1f | u8 | `p.stress`, `p.glottal_stop_pos`, `p.syl_num_phones`, `stress`, `glottal_stop_pos`, `syl_num_phones` |
| +0x20/+0x21 | s8 | `pos_in_word+1`, `(1−pos_in_word)+word_num_syls` |
| +0x22..+0x27 | u8 | `syl_in+1`, `syl_out+1`, `ssyl_in`, `ssyl_out`, `ssyl_from`, `ssyl_to` |
| +0x2c..+0x2e | u8 | `n.stress`, `n.glottal_stop_pos`, `n.syl_num_phones` |
| +0x30 | ptr | `p.gpos` |
| +0x34/+0x38 | u8/ptr | `p.word_num_syls`, word `gpos` (`DAT_00158d10` = `"gpos"`, file `0x148d10`) |
| +0x3c..+0x3e | u8 | `word_num_syls`, phrase counts before/after |
| +0x40/+0x44 | ptr/u8 | `n.gpos`, `n.word_num_syls` |
| +0x45..+0x48 | u8 | `p.phrase_num_syls`, `p.phrase_num_words`, `phrase_num_syls`, `phrase_num_words` |
| +0x4c | ptr | `daughtern.R:SylStructure.daughtern.endtone` (on Phrase) |
| +0x49/+0x4a | u8 | `pos_in_utt+1`, `(1−pos_in_utt)+num_phrases` |
| +0x50/+0x51 | u8 | `n.phrase_num_syls`, `n.phrase_num_words` |
| +0x54/+0x58/+0x5c | ptr | `ph_vc`, `ph_cvox`, `ph_ctype` (phone feature classes) |

For `"pau"` segments a reduced context variant is used (`:43800-43883`). These are exactly the
feature names that appear as strings in the binary (`p.R:SylStructure.parent.parent.R:Word.word_num_syls`
etc., file `0x148cc4-0x1492b8`).

### 1.6 Utterance representation

**Front-end output** = a list of utterances; each utterance is a **sentence snapshot = WordInfo
chain** built by `FUN_00039f24 (:16295-16320)` from Token items via `FUN_00045498 @ 0x45498
(:23251-23570)`. WordInfo types: `0` word `{text, whitespace, name, prepunctuation, interpret-as,
interpret-as-format, amplify, duration_stretch, pitch_stretch}`, `1` phones, `2` xsampa,
`3` silence, `4` break (`DAT_00156678`). The pump wraps a sentence into an utterance + `Token`
relation (`FUN_00039e78 @ 0x39e78 :16219-16233`).

At synthesis time the utterance becomes a **Festival/clustergen-style item/relation structure**:
relations `Token`, `Phrase`, `Word`, `SylStructure`, `Segment`, `Unit` are created/navigated by name
(`FUN_00059744/5978c` get-or-create, `FUN_00059334` `R:`-relation, `FUN_00061d28` path evaluator,
`FUN_00059720 @ 0x59720 (:37926)` ensures the `Token` relation exists in `FUN_0005d7c4 :41858`).
Feature values are typed **VAL**s: type tags seen `1` (int), `3` (float), `5` (string) and others
(`FUN_0005d144 @ 0x5d144 (:41448)` unwraps int/float/string to int; `FUN_0005d1d8 @ 0x5d1d8 (:41476)`
compares; misuse aborts with `"VAL: tried to access %s in %d type val\n"` — e.g. `:42700`,
`:52249`, `:52710`, `:37585`, `:38060`, `:46394`; full tag table in §3.6).

### 1.7 Waveform assembly and concatenation

Back in `FUN_0005d7c4`'s loop (`libttsivonavoice.c:42100-42454`), per selected unit:

* **Real diphone** (item has `diphoneset_num`):
  1. `FUN_0005d144(FUN_00059034(item,"diphone"))` resolves the diphone index (typed VAL unwrap).
  2. `FUN_0005ef70 @ 0x5ef70 (:42455)` **reads the waveform record from the voxdb**: seeks
     `fseek(file, section[param_2].offset, SEEK_SET)` and `fread(size)` where the section table is an
     array of 8-byte `{u32 offset, u32 size}` at `voxdb_obj+0x14` (`:42460-42470`), then hands the
     buffer to the record parser callback at `vtable+0x3c`; short reads print
     `"**Error: voxdb read: \`%s'\n"` (`:42479`). Result record: `{+4: nSamples, +8: …, +0x10: per-part
     sample-block pointer array}` (usage at `:42256+` and in `FUN_00061620`).
  3. **Boundary alignment**: the u16 at the start of each 36-byte diphonedb record (a
     **duration in ms** — see the `FUN_0005f1dc` decode §3.3, `rec+0 u16 duration_ms`) is read for
     records `idx` and `idx+1` and divided by `1000.0f` (`0x447a0000`) (`:42256-42264`); combined
     with the record's sample count it sizes the start/end adjustment windows applied below
     **[INFERENCE on the exact window formula]**; sample statistics over `[0,k]` are computed with
     `FUN_000624e8/62500`.
  4. **Silence (`"pau"`) handling**: target length derived from the segment's `end` feature
     (`DAT_00158af0` = `"end"`, file `0x148af0`) relative to the previous segment; the diphone's
     silence part is padded/trimmed by `FUN_00063350 @ 0x63350 (:45411)` (set length) or
     `FUN_00062718 @ 0x62718 (:44834)` (insert zeros at midpoint) (`:42272-42340`).
  5. **Speech-segment prosody transforms** — for each of the start and end windows of the record,
     token-level parameters (each read twice: token-own and voice-own, multiplied; defaults `1.0f` =
     `0x3f800000`; `FUN_00058efc`/`FUN_00058f0c` fetch token param tables):
     * `pitch_stretch` → `FUN_00063540 @ 0x63540 (:45506)` **pitch shift**; the duration factor is
       divided by the returned pitch result to compensate length (`:42348-42356`);
     * `duration_stretch` → `FUN_00062d14 @ 0x62d14 (:45135)` **time stretch**;
     * `compress` → `FUN_00063850 @ 0x63850 (:45625)` **[INFERENCE: spectral/duration compression]**;
     * `amplify` → `FUN_00062c54 @ 0x62c54 (:45088)` **gain**.
     (token params copied into the task at `:27288-27298`, §1.3).
  6. **Concatenation**: `FUN_00061620 @ 0x61620 (:43892)` appends the record's sample blocks into the
     streamer output buffer (`streamer+0xc` = `{+4 capacity, +8 channels, +0x10 int16*}`):
     - if a previous join tail is pending (`streamer+0x14 != 0`), the first block is **crossfaded**
       into the tail by `FUN_00062bd4 @ 0x62bd4 (:45052)` with a window curve from
       `FUN_00062b6c @ 0x62b6c (:45030)` (tables `DAT_0016275c`/`DAT_00162718`, 16 sub-samples per step);
     - the flag argument decides the seam: `FUN_00061620(puVar6, wave, 1)` **holds the record's last
       block back** (it is written at the current write position but the position is *not* committed;
       `streamer+0x14` = its length) so the next record crossfades over it
       (`libttsivonavoice.c:43936-43955`); flag `0` clears the pending tail and commits everything
       (`:43956-43959`).
     Decision at `:42404-42416`: flag `1` when there is no next unit, the next unit has no
     `diphone`/`diphoneset_num` attribute, or its diphone index is not `current_index + 1`;
     flag `0` only when `next_index == current_index + 1` — i.e. adjacent diphonedb indices are treated
     as already-continuous, everything else gets the crossfade seam **[INFERENCE: why index+1 is
     special — the diphonedb record stream and the Viterbi pair evaluation (`idx` and `idx+1`
     records read together at `:43128-43140`) suggest consecutive records share a joint waveform]**.
  7. `FUN_00062aa4 @ 0x62aa4 (:45005)` frees the record; `FUN_00061c1c @ 0x61c1c (:44214)` appends a
     `{segment, sampleOffset}` event to `streamer+0x1c` — the timeline used for mark positions;
     `FUN_00061bb8 @ 0x61bb8 (:44184)` attaches token events on silence/wave paths.
* **Silence unit** (attr `silence`): duration = `silence_feature × sample_rate` →
  `FUN_00061804 @ 0x61804 (:43958)` appends N zero samples (or memcpy if a buffer is given) (`:42160-42185`).
* **`wave` unit** (attr `wave`, `DAT_00156678` = `"wave"`, file `0x146678`): a unit carrying its own
  waveform — fetched via `FUN_00059b70/59be0`, gained with `FUN_000598d4` when token×voice `amplify`
  ≠ 1.0, appended with `FUN_00061804`; a `short` feature compared against `0x29` selects between the
  two fetch paths (`:42118-42150`) **[INFERENCE: meaning of 0x29 undetermined]**.

`FUN_000618a8 @ 0x618a8 (:44001)` finalises a chunk: allocates the result object
(`FUN_00059914`, `{+4 sample_rate, +8 nSamples, +0xc channels=1, +0x10 samples}`), copies up to the
requested count, slides the remainder down with `memmove`, and prunes consumed events from
`streamer+0x1c` (`FUN_0005ce60`), returning unconsumed events through its 3rd parameter — these
become the mark nodes in `FUN_0005a698` (`:44001-44118`).

### 1.8 Resample / output rate

If the voice defines the parameter **`resample_wave`** (`DAT_00158af4`, file `0x148af4`; fetched at
`:42104-42107`), `FUN_00059958 @ 0x59958 (:38129)` converts the finished chunk to that rate:
creates a rate converter (`FUN_00059c64(new/1000, old/1000, channels)`), new count =
`old_count × new/old + 0x800`, reallocates `channels × count × 2` bytes, streams through
`FUN_0005a4fc/5a050` and replaces `chunk+4` (sample rate) with the target (`:38129-38180`).
`tts_voice_sample_rate @ 0x4bc64 (:27780)` reports the voice's rate. The debug dump
`FUN_00062550 @ 0x62550 (:44717)` prints `num_frames`/`sample_rate`/`pms = { … }` for frame tables
(stdout debug only).

### 1.9 End-to-end call chain (summary)

```
JNI bridge (libttsivona.so)  ──vtable──▶  tts_streamer_start(0x4ac38)
   FUN_0004ab68  create streamer
   FUN_0004a2d4  input admission: text/plain → wrap into <speak> (FUN_00056d8c)
                 application/ssml+xml → SSML parse (FUN_0003d998, expat)
                 validate (FUN_0003c7f8) → utterances (FUN_0003f638) → mark table (FUN_0003d508)
tts_streamer_synth(0x4b51c) ─ loop ─▶ FUN_0004ae28  (pump)
   FUN_00040770   produce next utterance (sentence) from the SSML/text stream
   FUN_00039e78 + FUN_0005aa88  task init → FUN_00064fbc → stage pipeline FUN_00064f38
        (tokenizer/text_analysis/pos_tagger/phrasing/lettertosound/pause_insertion/
         postlex/intonation/duration — voice-overridable by name)
   FUN_0005a698  per-chunk synthesis
        └ FUN_0005d7c4
             diphonedb open: FUN_0005f3cc → FUN_0005f064 (CDXV container)
             diphone names "L-R" → FUN_0005ef00 (binary search, 20-byte name entries)
             features: FUN_00060ed4 (96-byte vectors)
             graph:  voice diphone_graph_func(utt, feats, n)
             search: FUN_0005fc04 (Viterbi, viterbi_beam, 36-byte diphonedb records)
             waveform: FUN_0005ef70 (voxdb read) → prosody transforms
                       (63540 pitch / 62d14 time / 63850 compress / 62c54 gain)
                       → FUN_00061620 concat w/ FUN_00062bd4 crossfade
                       → FUN_00061804 silence pad
             finalise: FUN_000618a8 → (resample_wave? FUN_00059958)
             events → mark nodes (FUN_00061c1c timeline)
   mark nodes → 20-byte records (FUN_0004aa5c / FUN_0004ad70)  — §4
   merge all waves (sampleOffset rebasing) → return 24-byte wave
JNI bridge: int16 → Java audio; mark records → android.speech.tts.SpeechMark (decompiled.c:6319+)
```

---

## 2. On-disk formats

### 2.0 File-open plumbing (shared)

* `FUN_0005b368 @ 0x5b368` (`:39759-39796`): fopen wrapper (mode-bit → string; arg `10` = `"rb"`).
* `FUN_0005b338 @ 0x5b338` (`:39753`): fread wrapper.
* `FUN_000505ac @ 0x505ac` (`:30491-30506`): generic file reader — `fopen(name,"rb")`, on failure
  `FUN_00047628(errno,"file_open")`; returns 0x18-byte handle `{…, FILE* at +0x14}`; used by the
  ISEF, dictionary and PLS loaders.
* `FUN_00067830 @ 0x67830` (`:47240-47263`): mmap wrapper (`open(O_RDONLY)`,
  `mmap(PROT_READ,MAP_PRIVATE)`, page-rounded length); handle `{void* map, size, fd}`.

### 2.1 The `CDXV` container (vox voice-data file; the OBB *main* file is this format)

**Three readers**, all `fread(hdr, 0x68, 1, fp)` then LE u32 `0x56584443` (`"CDXV"`); the ASCII
magic sits in `.text` literal pools at file offsets `0x4f164`, `0x4f498`, `0x4f774` (each: ARM `b`
+ `.ascii "CDXV"`), decompiled as the constant at `:42531`, `:42724`, `:42777`:

* `FUN_0005f064 @ 0x5f064` (`:42513-42560`) — reopen/validation path (used from `FUN_0005d7c4
  :41849`): after the magic it compares header u32 `+0x24` vs `caller[3]` (sample rate) and `+0x2c`
  vs `caller[4]` (checksum) (`:42534`), then runs the optional validator `caller[0xd]` (`:42537`).
* `FUN_0005f424 @ 0x5f424` (`:42707-42736`) — header-only check, returns strdup of the name field
  (`FUN_0005b884` = strdup, `:40030-40043`).
* `FUN_0005f49c @ 0x5f49c` (`:42738-42882`) — **main parser**: mmaps only the header-described
  range (`FUN_00067830`, `:42805`) and materialises section pointers.
* A duplicate engine-side CDXV reader exists inside `libvoice_en_us_kendra.so` (file `0x17cd0`);
  the plugin exports `register_voice@@TTS_ENGINE_1_6` and is self-contained.

**Header layout — 104 (0x68) bytes, little-endian** (derived from the `FUN_0005f49c` stack map
`local_80→+0x00 … local_1c→+0x64`, `:42746-42882`; confirmed byte-for-byte against the OBB):

| off | size | field | evidence |
|---|---|---|---|
| 0x00 | 4 | magic `"CDXV"` (LE `0x56584443`) | `:42777`; OBB bytes `43 44 58 56` |
| 0x04 | 32 | voice name, NUL-padded (`vox_en_us_kendra\0…`) | strdup `:42779-42781`; compared vs config `name` in `FUN_0005f7a4 :42940` |
| 0x24 | 4 | sample rate (OBB = **22050** = `0x5622`) | struct[3] `:42782`; feature `sample_rate` `:42957`; `FUN_00067f94 :47532` remaps `0x5622`→24000 |
| 0x28 | 4 | format/codec version id (OBB = **14**) | switch `:42846-42879` selects per-version callbacks `[0xd]/[0xe]/[0xf]`; v14 → `FUN_00067f94` (`:47514-47557`: stores checksum bytes into codec ctx, inits decoder) |
| 0x2c | 4 | checksum / file tag (OBB = `0x4f7c7a18`) | struct[4] `:42783`; `atol("checksum")` compare `:42943`; re-checked on reopen `:42534` |
| 0x30/0x34 | 4+4 | section A = **section directory** (OBB: off `0x68`, size 3,415,928) | `puVar2[5] = map+0x68` `:42826`, `puVar2[6]` `:42830` |
| 0x38/0x3c | 4+4 | section B (OBB: off 25,356,504 = end-of-data, size 0 → pointer not set) | guard `:42827` |
| 0x40/0x44 | 4+4 | section C (OBB: 3,416,032 / 32,020 = **1601×0x14**) | count `puVar2[0xb] = size/0x14` `:42812`; 20-byte records qsorted in `FUN_0005fa84 :42974` |
| 0x48/0x4c | 4+4 | section D (OBB: 3,448,056 / 1,673,980 = 418,495×4) | `:42814-42816` |
| 0x50/0x54 | 4+4 | section E (OBB: 5,122,040 / 15,371,676 = **426,991×36**) | `:42817-42819` |
| 0x58/0x5c | 4+4 | section F (OBB: 20,493,720 / 4,860,925) | `:42820-42822` |
| 0x60/0x64 | 4+4 | section G (OBB: 25,354,648 / 1,856; off+size = 25,356,504 = mmap length) | mmap len = max(offset+size) over pairs `:42787-42804` |

Arithmetic identities verified: `3,415,928/8 = 426,991` exactly; `15,371,676/36 = 426,991`
exactly; `32,020/20 = 1,601`; sections are contiguous up to 3–4-byte alignment padding; the mmap
covers only `0x68 + 25,356,504` bytes although the OBB file is 152,219,597 bytes — the remainder
lies beyond what the container describes (§6).

**Lazy section directory at file offset `0x68`** — `FUN_0005ef70 @ 0x5ef70` (`:42455-42481`) treats
`*(blob+0x14)` (= `map+0x68`) as an array of 8-byte `{u32 file_offset, u32 size}` indexed by section
number: malloc, `fseek(fp, off, 0)`, `fread(buf,1,size,fp)` on the stdio handle from `FUN_0005f064`,
short read → `"**Error: voxdb read: \`%s'\n"` + `strerror` (`:42470`), then the parse callback
`*(blob+0x3c)` (the v14 decoder) runs on the bytes (`:42482-42486`). Verified against the OBB:
entries such as `{off 133,873,411, size 76}` point *deep into the 152 MB file* — **beyond** the
25.4 MB mmap, hence the stdio path. **[INFERENCE]** directory count = the 426,991 implied by the
section-A size (matches the parallel OBB walk).

`FUN_0005f7a4 @ 0x5f7a4` (`:42884-42972`) — config-driven loader: reads config keys `name`
(`DAT_00155d00`, file `0x145d00`) and `checksum`; builds the voxdb path
`sprintf("%s/%s/%s/%s%s", dir, voxdbname, checksum, voxdbname, "22v")` (format at file `0x148b38`,
suffix literal at `0x148b48`) — i.e. **`<dir>/<voxdbname>/<checksum>/<voxdbname>22v`**
**[INFERENCE: "22v" = 22 kHz vox suffix]**; requires 5 features else
`"**Error: file \`%s' lacks needed features\n"` (`:42963`); publishes the `diphonedb` VAL
(`FUN_0005f3b4/f3cc :42669-42705`; misuse string `:42700`); errors
`"**Error: cannot open or incorrect file \`%s'\n"` (`:42934`). `FUN_0005f028 @ 0x5f028 (:42487)`
closes (`vtable+0x38`, `fclose`, free); a second reader with the same error string is
`FUN_000685c4 @ 0x685c4 (:47924)`.

**Section→structure correspondence** (combining the engine reads with the sizes above):

* section A (426,991×8 B) = the `{offset,size}` directory consumed by `FUN_0005ef70` — one entry
  per diphone *instance* (waveform payload location; payloads live past the mmap, read by stdio);
* section C (1601×20 B) = the **diphoneset name table** (`"L-R"` names) binary-searched by
  `FUN_0005ef00 :42419-42447` at `diphonedb+0xc` — 1601 = 40²+1 **[INFERENCE: all phoneme pairs
  incl. `pau`]**;
* section E (426,991×36 B) = the **36-byte diphone instance records** read by `FUN_0005f1dc :42602`
  (`table + idx*0x24`; first u16 = duration in ms, ÷1000.0 at `:42256-42263`), which is the
  table at `diphonedb+0x14`;
* section D (418,495×4 B) = the **u32 diphone index table** mapped from header `+0x48` into
  `handle+0x24`/`diphonedb[4]` (§3.3), enumerated by the Viterbi pre-pass
  (`*(index_table + (i + base)*4)` at `:43110-43120`) **[INFERENCE on the exact enumeration]**;
* sections F/G semantics → parallel OBB investigation (§6).

### 2.2 `voxdb` reads and codec

The `**Error: voxdb read` path is §2.1 (`FUN_0005ef70`); payload decoding for format v14 is
`FUN_00067f94 @ 0x67f94` (`:47514-47557`): sample-rate sentinel `0x5622`→24000, checksum bytes into
the decoder context (`:47539-47542`), then codec init (`FUN_0014794c…`).
`FUN_00062550 @ 0x62550 (:44717)` is a stdout debug dump (`num_frames`, `sample_rate`, `pms = {…}`).

### 2.3 `lang_*.dat` (patch data) — the `ISEF` encrypted lexicon container

**Filename** (`tts_load_voice`, `:28046-28243`): `getenv("IVONA_LANG_DAT_DIR")` (`:28081`) else the
voice `.so` directory; `FUN_0004be40 @ 0x4be40 (:27878-27897)` builds
`lang_<language_code>` + `DAT_00156f74` (file `0x146f74` = `"_"`) + `<voice_variant>` +
`DAT_00156f78` (file `0x146f78` = `".dat"`) e.g. `lang_en_us_kendra.dat` (`'-'/' ' → '_'`,
`FUN_0005519c :34599-34615` normalises the voice name); fallback `FUN_0004bfb8 @ 0x4bfb8
(:27951-27966)` = `lang_<language_code>.dat` (matches the shipped `lang_en_us.dat`); first choice
`:28102-28104`, fallback `:28106-28110`, both failing aborts voice load (`:28111-28120`).

**Open/parse**: `FUN_00039300 @ 0x39300` (`:15702-15768`) — `stat()` cache keyed by path +
timestamp field (`"File not found: %s"` `:15775`; re-parse when the stat timestamp changes
**[INFERENCE: st_mtime]**); `FUN_000394b8 @ 0x394b8` (`:15771-15830`) opens the container
(`FUN_000346d4`), reads section `"prm_lex_list"` (default content `"prm_lexicon\n"`, len 0xC,
`:12622-12625`), iterates its newline-separated lexicon names and parses each into the lexicon as
UTF-8 via `FUN_0004620c(stream,"UTF-8",lex,"<file>:<N>",0,0)` (`:12640-12647`).

**ISEF container format** (`FUN_000346d4 @ 0x346d4`, `:12617-12741`):

| off | size | field | evidence |
|---|---|---|---|
| 0x00 | 4 | magic `"ISEF"` | memcmp vs `DAT_00155244` (file `0x145244`) `:12656`; file bytes `49 53 45 46` |
| 0x04 | 4 | version = BE 1 (`00 00 00 01`) | memcmp `:12662`; mismatch → `"Invalid version of file %s"` `:12732` **[UNRESOLVED: the decompiled pointer at file `0x14bd70` reads `"Port"` — decompiler artifact]** |
| 0x08 | 4 | BE u32 `0x50992bcc` = 1,352,215,500 (identical in en_us/en_gb ≈ 2012-11-05) | byteswapped into container[4] `:12667-12674` **[INFERENCE: build timestamp]** |
| 0x0c | 0x200 | RSA-4096-wrapped session blob | see below |
| 0x20c | … | block-cipher-encrypted payload (74,144 B; %16==0) | see below |

Crypto (embedded polarssl-style code): fixed **512-byte modulus** from file `0x14bd78` + 4-byte
exponent from `0x14bf78` = `00 01 00 01` = **65537** → RSA-4096 public key (`FUN_000b2684`,
`:12683-12690`, failure `"Load key"`); `FUN_000b34fc(0x200,in,out,…)` decrypts the first 0x200
bytes; success check `(ret & 0x1fffffff) == 0x40` → 64-byte session blob (`:12689-12698`, else
`"Invalid file %s"`); `FUN_000b8fe0(..., blob, blob+0x20)` initialises a block cipher with
key = `blob[0..]`, IV = `blob+0x20` **[INFERENCE: AES-256-CBC, 32-B key + 16-B IV]**; streaming
decrypt of the remainder (`FUN_000b950c :12715`, finish+unpad `FUN_000b974c :12716-12723`; failure
`"Broken file %s"`).

**Decrypted payload = section table**: `FUN_000345b0 @ 0x345b0` (`:12561-12592`) walks records
`{char name[16] NUL-padded, u32be size, u8 data[size]}`; next record at `cur + size + 0x14`; each
section's data is **lexicon text** (§2.4). Contents beyond the `prm_lex_list` name are
**undecryptable without IVONA's RSA private key** (§6).

### 2.4 Lexicon/dictionary text format (shared by dict files and ISEF sections)

Parser `FUN_0004620c @ 0x4620c` (`:23783-24093`):

* Encoding sniff: `FF FE`→UTF-16LE, `FE FF`→UTF-16BE, `EF BB BF`→UTF-8; first-line `#&` directive
  with `key=value` pairs (only `encoding=` honoured; unsupported →
  `"Lexicon encoding not supported: %s"` `:23895`); else the caller's default (`"UTF-8"`)
  (`:23824-23903`).
* Line tokenizer `FUN_00045eac @ 0x45eac` (`:23632-23656`) + `FUN_00045dc0 @ 0x45dc0`
  (`:23572-23618`): blank lines and `#` comments skipped; **two whitespace-separated tokens per
  line: `pattern replacement`**; tokens may be double-quoted with backslash escapes (`\"`);
  unterminated quote → `"invalid dictionary format"` (`:24033`); max 100 errors
  (`"Too many errors. Quitting"` `:24041`), errors reported as `"line %ld: %s"` (`:24021`).
* Each line becomes a **PCRE regex rewrite rule** via `FUN_00046e10 @ 0x46e10` (`:23953-24056`;
  `regcomp` flags `0x20002801`, POSIX-class rewrites `[:graph:]` etc.); entry (20 B) =
  `{char* pattern, char* replacement, pcre* code, pcre_extra* analysis, char* tag}` (`:24013-24027`).
  Semantics = grapheme-rewrite rules (text normalisation / letter-to-sound input shaping), **not**
  word→pronunciation pairs.

**`tts_dict_save @ 0x45f64`** (`:23677-23753`): `fopen(path,"w")` (`"Cannot open file for writing"`
`:23700`); writes literal `#& encoding=UTF-8\n`; per entry `pattern replacement\n`, `"` escaped as
`\"`, a token wrapped in `"…"` iff empty or containing whitespace (`:23724-23748`); optional 3rd
argument filters by entry tag (`entry+0x10`, `:23712-23715`).
**`tts_dict_load @ 0x46a6c`** (`:24119-24204`): local path → `FUN_00046a10` (`FUN_000505ac` +
`FUN_0004620c` + close, `:24095-24107`); `file://`/`http://` → fetcher `FUN_0004bc88 @ 0x4bc88`
(`:27793-27823`, config `eng_ssml_base_uri`/`eng_fetch_function`/`eng_fetch_user_data`) then parse
from memory (`"Failed fetching lexicon file"` `:24167`); config keys `eng_dict_insert_id` (tag),
`eng_text_encoding` (`:24141-24143`); returns entry count or −1.
**`tts_dict_insert @ 0x47158`** (`:24394-24460`): encoding-converts both args (`FUN_00055318`) then
the same rule insert; `tts_dict_remove @ 0x46d28`, `tts_dict_num_entries @ 0x46ce4`,
`tts_dict_cleanup @ 0x4738c` complete the API.

### 2.5 `tts_pls_load` — W3C PLS 1.0 XML via embedded expat 2.0.1

* `tts_pls_load @ 0x4c6a8` (`:28215-28380`): non-URL path reads the whole file via `FUN_000505ac`
  (`:28238-28244`); `file://`/`http://` uses the fetcher (`:28275-28360`; errors
  `"Failed parsing PLS lexicon file"` `:28257/:28328`, `"Too many PLS lexicons"` at id
  `0x7ffffffe` `:28287`).
* Parser `FUN_0003816c @ 0x3816c` (`:14853-14957`): `XML_ParserCreateNS`-equivalent
  `FUN_000fa864(0,'^')` (namespace separator `^`; `.rodata` carries `expat_2.0.1`,
  `lib/xmlparse.c`); token regex `[\p{L}\p{M}\p{N}]+|[\p{S}]|[\p{P}]|[\p{Z}\p{C}]+` (`:14874`);
  result = `FUN_00036f10` lexicon object.
* Element handler `FUN_000388dc @ 0x388dc` (`:15207-15410`): element table `DAT_0018fd20` starts
  `lexicon`; root must be `lexicon` in the W3C namespace
  `http://www.w3.org/2005/01/pronunciation-lexicon` (assumed when unbound, `:15237-15252`);
  checks `version` (`"1.0"`) and `alphabet` attrs (`:15350-15410`); warns
  `"PLS element names should be lowercase"`; sub-elements `phoneme`/`alias`/`sub` handled.
* Storage: `tts_pls_load` keeps `(auto-increment id, lexicon*)` pairs in an engine vector
  (`:28281-28290`); `tts_pls_unload @ 0x4bd94` (`:27825-27850`) removes by id. The engine's
  `"Too many PLS lexicons"` limit is id saturation, **not** certificate-derived (§5).

---

## 3. Voice database in-memory structures

### 3.1 `tts_load_voice` end-to-end (`@ 0x4c028`, `:27971-28197`)

Signature `int* tts_load_voice(int engine, char* voice_so_path, char* vox_or_dir_path)`:

1. Guards; `FUN_00048034` = engine singleton; `FUN_0004e028` certificate/expiry gate
   (failure → code 2, `:28144`).
2. `dlopen(voice_so_path, RTLD_LAZY)` (`:28003`); `dlsym(handle, "register_voice")` (`:28007`);
   failure → dlerror log + `dlclose`.
3. `*errno = 0; voice = (*register_voice)(data_path)` (`:28013-28016`). On NULL: `dlclose`;
   `errno == ENOENT` → `"The vox file does not exist"` (code 4, `:28022`); other errno →
   `FUN_00047628(errno)`; 0 → code 4 (`:28030-28036`).
4. The returned object's first word is a **named parameter list** (§3.6); required names checked
   with `FUN_0005b0bc` (has-param): `voice_name`, `voice_gender`, `eng_version`, `language_name`,
   `language_code` (`:28038-28050`); missing → `"Invalid voice library data"` (code 4, `:28138`).
5. A 0x24-byte **voice descriptor** is built (`:28052`): `[0] = sprintf("IVONA 2 - %s - %s",
   language_name, voice_name)` (`:28056-28077`), `[1] language_name, [2] language_code,
   [3] gender, [4] voice_name, [5] eng_version, [6]=[7]=0, [8] = FUN_0005519c(voice_name)` copy
   (freed by `FUN_0004be18 :27861`).
6. `eng_version` must strcmp-equal **`"1.6.23"`** else `"Voice library version mismatch: got %s,
   required %s"` (code 4) + unregister/free/dlclose (`:28062-28069`).
7. `custom_voice` param (`:28073`) → `FUN_0004dee4 @ 0x4dee4` certificate voice-allowlist gate
   (§5.4); denial → `"Voice not allowed by the certificate"` (code 3, `:28074-28080`).
8. Data dir: `getenv("IVONA_LANG_DAT_DIR")` else dirname of the vox path (`:28082-28096`);
   `FUN_0004be40 @ 0x4be40 (:27877-27897)` builds `lang_<code>_<voice>.dat`, fallback
   `FUN_0004bfb8 @ 0x4bfb8` builds `lang_<code>.dat` (§2.3); `FUN_00039300(engine+0x14, dir)`
   registers the directory (`:28099`).
9. A 0x1c-byte **voice object** is allocated (`:28118-28135`):

   | off | field | source |
   |---|---|---|
   | [0] | engine | param_1 |
   | [1] | 0x24-byte descriptor | `:28121` |
   | [2] | param `"name"` (default `"anonymous"`) | `FUN_0005b1c0 :28127` |
   | [3] | sample_rate (int param) | `FUN_0005b230 :28125` |
   | [4] | synth context (`FUN_0004730c`, freed `FUN_00047314`) | `:28133` |
   | [5] | param wrapper `FUN_0004bf1c` = `{params, dir handle, cbqueue FUN_00055b40(8,0,…)}` | `:27914-27929` |
   | [6] | dlopen handle | `:28128` |

   then `FUN_00049e98(voice)` init and `FUN_00048124(engine, voice)` registration (`:28131-28132`).
   `tts_voice_sample_rate @ 0x4bc64` returns voice[3] (`:27780`).
10. **Unload** `tts_unload_voice @ 0x4c5b0` (`:28153-28197`): `dlsym(voice[6],"unregister_voice")`
    → `unregister_voice(*voice[5])`, `dlclose`, deregister data dir, free wrapper/synth context/
    descriptor, remove from engine list. `FUN_0004bf64 @ 0x4bf64` (`:27932-27949`) is the
    error-path helper doing the same (used at `:28066/:28076/:28107/:28139`).

### 3.2 The plugin side: `register_voice` (libvoice_en_us_kendra.so)

`register_voice` (plugin `libvoice_kendra.c:900-912`) = `obj = FUN_00030020(); set "eng_version"
= "1.6.23"; return obj`. `FUN_00030020` (plugin `:7794-7841`) returns a **0xC-byte voice object
`{listA, listB, pad}`** whose first word is the parameter list. Registered entries (name → VAL):

* `"name"` = `"vox_en_us_kendra"`, `"checksum"` = `"1333557784"` (plugin `:7807-7808`);
* `"vox_lexicon"` = lexicon VAL (tag 0x1b) wrapping the embedded static lexicon `&DAT_002f4030`
  (`:7812-7814`, §3.5);
* `"duration_stretch"` = 1.0f, `"duration_func"` = userdata(`FUN_00048400`), `"zdur_cart"` =
  CART VAL (tag 0x35) of `PTR_DAT_002f4024` (plugin `:7815-7821`);
* **vox loading**: `FUN_00028310(listA, data_dir)` (plugin `:7817`, the engine-side
  `FUN_0005f7a4` clone) opens the `.vox` file and sets `"sample_rate"` (int, CDXV hdr+0x24) and
  `"diphonedb"` (tag 0x1f) (plugin `:2651-2653`); failure → unregister+NULL → the engine reports
  *"The vox file does not exist"*;
* `"diphone_graph_func"` = userdata(`FUN_00030214`), `"viterbi_beam"` = **50**,
  `"language_code"` = `"en-US"`, `"voice_name"` = `"Kendra"`, `"voice_gender"` = `"Female"`
  (plugin `:7826-7834`);
* `FUN_0003256c` (plugin `:9421-9502`): `"encoding"` = `"ISO-8859-1"`, `"language_name"`,
  `"syl_boundaries_func"`, `"xsampa_to_xivona_func"`, `"xivona_to_xsampa_rules"`,
  `"wordtosegments_func"`, `"postlex_func"`, `"phoneset"` (tag 0x19 wrapping static
  `&PTR_s_x_ivona_en_us_002f8dcc`), `"silence"` (phoneset+0x10), tokenisation params,
  `"sentence_boundary_func"`, `"tokentowords_func"`, `"phrasesylendtone_func"`; then per-item
  feature funcs `ph_vc, ph_vlng, ph_vheight, ph_vfront, ph_vrnd, ph_ctype, ph_cplace, ph_cvox …`
  (plugin `:18823-18824`).

The plugin exports `register_voice@@TTS_ENGINE_1_6`, carries a self-contained duplicate of the CDXV
reader (file `0x17cd0`) and has **no engine imports**.

### 3.3 CDXV handle and `diphonedb` payload (in-memory)

`FUN_0005f49c @ 0x5f49c` (`:42738-42882`) builds a **0x48-byte vox handle** from the 104-byte
header (§2.1), with only format versions **2, 8, 0xc, 0xe** accepted (`:42852-42885`):

| handle | field | header source |
|---|---|---|
| +0x04 | name (strdup) | hdr+0x04 |
| +0x0c | sample_rate | hdr+0x24 |
| +0x10 | checksum | hdr+0x2c (compared with `atol("checksum")` param, `:42927-42944`) |
| +0x14 | **section directory** `{offset,size}×8` (file 0x68) | hdr+0x30/0x34 |
| +0x1c | extended record data | hdr+0x58 |
| +0x20 | **36-byte diphone records** (stride 0x24) | hdr+0x50 |
| +0x24 | **u32 diphone index table** | hdr+0x48 |
| +0x28 / +0x2c | **diphone name table** ptr / count (= size/0x14) | hdr+0x40/0x44 |
| +0x30 | model parameter blocks (stride 0x20) | hdr+0x60 |
| +0x38 / +0x3c | section ptr / count (+ parse/version callbacks) | hdr+0x38/0x3c |

The **`diphonedb` VAL** payload is 0x24 bytes (`FUN_0005f3b4 @ 0x5f3b4 :42669`, getter
`FUN_0005f3cc :42684`, tag 0x1f; `:42917-42954`): `[0] name, [1] checksum, [2] n_records,
[3] name table, [4] index table, [5] 36-B records, [6] ext data, [7] model blocks, [8] vox handle`;
all five table pointers must be non-NULL else `"**Error: file \`%s' lacks needed features\n"`
(`:42948-42954`). This resolves the two `+0x14` fields seen earlier: **voxblob handle +0x14 =
section directory (8-byte entries)** used by `FUN_0005ef70`, while **diphonedb payload +0x14 =
36-byte records** used by the Viterbi/waveform code.

**Lookup**: `FUN_0005ef00 @ 0x5ef00` (`:42419-42449`) — binary search, `count = *(ddb+8)`,
`table = *(ddb+0xc)`, stride **0x14**, key = NUL-terminated name at record start (`strcmp :42433`),
returns index or −1; the key is built by `snprintf(buf,10,"%s-%s", prev, next)` (`:41963`; plugin
`:7855`).

**36-byte record decode** `FUN_0005f1dc @ 0x5f1dc` (`:42602-42667`): `out[0] = i16(rec+0)/1000.0`
(**duration in ms → seconds**, `:42616-42622`); u32 at `rec+0x20` = offset into the extended-data
block (`:42620`); `out[1..5]` = model-block pointers `ext_base + u8(rec+2..rec+6)*0x20`
(`:42623-42627`); byte `rec+7` split into nibbles → `out+0x18/+0x19` (`:42628-42629`); the
extended-data bytes yield more nibble flags, further model pointers (u8×0x20) and jump offsets
(u16 at ext+0xf / ext+8) plus 6- and 9-byte memcpy'd sub-blocks (`:42630-42660`); `out[0x15..0x17]`
cleared (`:42661-42663`). In the waveform step the duration i16s of records `idx` and `idx+1` are
read as `i16/1000.0` seconds (`:42256-42264`) and combined with the record length to size the
boundary adjustment windows **[INFERENCE on the exact window formula]**.

**Payload unpackers** (per format version, dispatched at `handle+0x3c`): v2 `FUN_00067924`
(`:47297-47330`, raw multi-frame PCM: u16 nframes, per-frame u16 lengths, int16 samples);
v8 `FUN_00068378/6833c`; **v0xc `FUN_000685c4 @ 0x685c4` (`:47679-47933`)** = first u16 = PCM sample
count, u32 compressed size, length-prefixed packets XOR-deobfuscated with an 8-byte key at
`handle+0x88` (`:47795-47845`), decompressed (`FUN_0013e250/…` — **[INFERENCE: LZO-style]**),
int32 samples `>>9` clamped to int16 (`:47873-47893`), zero-padded, wave built via
`FUN_00062608/62688`; v0xe `FUN_00067f94` (`:47514-47557`, sample-rate sentinel `0x5622`→24000,
checksum into codec ctx). Kendra ships **v14 (0xe)**. Versions 3–7, 9–0xb, 0xd have empty switch
cases (`:42852-42885`).

### 3.4 `phoneset`, `ph_cvox`, `phonefunc`

* `phoneset` VAL (tag 0x19) accessor `FUN_0006f848 @ 0x6f848` (`:52223-52252`; misuse string
  `:52249`). Structure from accessors: `+0x04` feature-name table (NULL-terminated `char**`,
  linear scan — `FUN_0006f660 :52111-52137`), `+0x08` feature-value symbol table (`FUN_0006f75c
  :52192-52208`), `+0x0c` phone-name table (`FUN_0006f6b4 :52140-52189`), `+0x10` silence phone
  name (plugin sets `"silence"` = ppuVar5[4], plugin `:9483` **[INFERENCE]**), `+0x14` phone count
  (`:52148-52170`), `+0x18` phone×feature index matrix (`int**`, `:52203-52206`), `+0x1c` sorted
  flag enabling binary search. `FUN_0006f75c(params, phone, feat)` =
  `*(*(phoneset+8) + *(*(phoneset+0x18) + phone*4) + feat*4)*4` with default `DAT_00192a8c`
  (`:52203-52207`). Kendra's phoneset is a compile-time static (`&PTR_s_x_ivona_en_us_002f8dcc`,
  plugin `:9474-9478`).
* **`ph_cvox`** = per-phone phoneset feature `"cvox"` (consonant voicing): registered by the plugin
  (`FUN_0003d9b0(item_feats,"ph_cvox",FUN_0004566c)`, plugin `:18824`; `FUN_0004566c` plugin
  `:18948-18959` = `phoneset_feature(phone,"cvox")`), alongside `ph_vc, ph_vlng, ph_vheight,
  ph_vfront, ph_vrnd, ph_ctype, ph_cplace` (Festival-compatible naming). The engine copies these
  into the 96-byte context vector in `FUN_00060ed4`: `param_2[0x15]=ph_vc, [0x16]=ph_cvox,
  [0x17]=ph_ctype` (`:43882-43887`). Phone classification also uses feature `"ctype"` with values
  in `"grl"/"fap"/"n"` (`FUN_0006f110 :51917-51946`).
* `phonefunc` VAL (tag 0x2f) accessor `FUN_000700f8 @ 0x700f8` (`:52694-52713`, misuse `:52710`);
  Kendra registers no `phonefunc` — role undetermined (§6). Adjacent `FUN_00070150 @ 0x70150`
  (`:52717-52806`) is a phone decision-tree evaluator: name table stride 0x40 at +4; 4-byte rule
  entries `{u8 name_idx, char op '<'/'>'/eq, u8 feat, u16 jump}`, terminator `0xff`; returns
  `((prev_delta*cur+500)/1000 + base)` — **[INFERENCE: duration model evaluator]**
  (the Kendra `zdur_cart` VAL (tag 0x35, `FUN_… :52815`) and `duration_func` userdata are the
  voice-side pieces).

### 3.5 `vox_lexicon` and lexicon objects

`vox_lexicon` is a **plugin-registered param** (not an engine string): `FUN_0003e1ec(&DAT_002f4030)`
wrapped as lexicon VAL (tag 0x1b), plugin `:7812-7814` (wrapper `:13774-13783`). Engine-side lookup
`FUN_00069044 @ 0x69044` (`:47979-48103`, identical plugin copy `FUN_0003e2b4 :13817+`); the tag-0x1b
VAL getter is `FUN_00068fec @ 0x68fec` (`:47955-47965`, misuse string `"lexicon"`):

* `+0x08` sorted packed word blob (entries NUL-terminated, separated by `0xff` sentinels; binary
  search `:48020-48065`), `+0x0c` blob size, `+0x18` override map consulted first
  (`FUN_00070484 :52869` — `{flag char, name, jump}` entries with `*` wildcard, `:52831-52867`),
  `+0x20` optional string dictionary (char** indexed by blob byte) for compressed entries
  (`:48053-48074`). The destructor comes from the VAL dispatch table (lexicon row free-fn vaddr
  `0x4d6f8`), whose body is **missing from the decompilation** (gap between `FUN_0005d6b0 :41729`
  and `FUN_0005d718 :41746`) — §6. (Note: `FUN_00068b48 @ 0x68b48 :47934-47953`, adjacent to the
  codec area, is the **v0xc codec-context teardown**, not the lexicon destructor.)
* Role: **precompiled word→pronunciation lexicon inside the plugin**; the word (prefixed with a
  category char, `sprintf("%c%s", …) :47998-48000`) is binary-searched and the pronunciation used
  during phonemization, ahead of diphone graph construction.

The engine also loads **text lexicons**: `FUN_0006519c @ 0x6519c` (`:46278-46345`) parses files
whose first token is `"IVONA_Lexicon"` (else error `:46337`); `#` comments; each entry = word +
pronunciation parsed by `FUN_00070040 @ 0x70040` (`:52659-52692`) into a list of string VALs;
stored as param `"user_lexicon"` (`FUN_0005a608`, `:38821-38823`). PLS XML lexicons are handled by
`tts_pls_load` (§2.5).

### 3.6 The parameter/VAL store (how everything binds)

* **Parameter list**: `register_voice`'s return is a singly-linked list, node = 0xC
  `{char* name, VAL* value, next}` (set `FUN_0005ae34 :39293-39335`; get `FUN_0005b10c :39565`;
  has `FUN_0005b0bc :39502`; delete `FUN_0005af94`; free `FUN_0005b00c`). Lookup is `strcmp` over
  the list — **there are no fixed slots**; `voxdbname`, `diphonedb`, `phoneset`, `duration_func`,
  … are just names. Typed getters (`:39546-39660`): `FUN_0005b15c` raw string, `FUN_0005b16c`
  float, `FUN_0005b17c` int, `FUN_0005b1c0` string+default, `FUN_0005b1f8` float+default,
  `FUN_0005b230` int+default. `"voxdbname"` overrides `"name"` when building the vox path
  (`:42893-42901`).
* **VAL = 8 bytes** `{int16 tag, int16 refcount, void* payload}` (ctors `FUN_0005d650/5d690/5d6b0/
  5d718 …`, `:41593-41757`; incref/decref `FUN_0005cda0/5cdd0 :41138-41173`). **Cons cells** (lists)
  = 8-byte `{car,cdr}` with no tag; `FUN_0005cd54` = "is list iff car's low bit clear"
  (`:41101-41108`); car/cdr `FUN_0005cf98/5cedc`; build `FUN_0005d5d0 :41563`; reverse
  `FUN_0005cd64 :41111`.
* **Tag enum** — proven from the type-name/dispatch table `DAT_00195088` (file `0x184088`; rows
  `{char* name, code* free_fn}` indexed by `(tag−1)/2`; tags are odd):
  `0x01` int, `0x03` float, `0x05` string, `0x07` utterance, `0x09` wave, `0x0b` track, `0x0d`
  (name blank), `0x0f` uttfunc, `0x11` ffunc, `0x13` relation, `0x15` **item**, `0x17` **cart**,
  `0x19` phoneset, `0x1b` lexicon, `0x1d` dur_stats, `0x1f` diphonedb (free `0x4f1d8`), `0x21`
  (blank), `0x23` wavesynth (free `0x51b1c`), `0x25` audiotag (free `0x4a58c`), `0x27` (blank),
  `0x29` userdata (free `0x4d700`), `0x2b` itemfunc, `0x2d` features (free `0x4b048`),
  `0x2f` phonefunc, `0x31` xsampafunc, `0x33` allwordposfunc, `0x35` zdur_cart. Print/free
  dispatch: `FUN_0005d390 (:41427)` and `FUN_0005d4fc (:41577-41589)` (tag > 6 → row free-func;
  tag 5 → `free` string). Direct getters: int `FUN_0005d144 :41448`, float `FUN_0005d094 :41650`,
  string `FUN_0005cfc0 :41323`.
* **Runtime binding in the synthesiser** (`FUN_0005d7c4 :41802+`): `FUN_0005f3cc` = diphonedb VAL
  getter (tag 0x1f); `FUN_00061b58` = wavesynth VAL getter (tag 0x23); `FUN_00061b20 (:44120)`
  allocates the 0x2c-byte **streamer**: `[0] voxdb (FUN_0005f064 re-open, validating hdr+0x24 ==
  sample rate and hdr+0x2c == checksum)`, `[1] Token relation`, `[2] current item`,
  `[0x0c] wavesynth object (its +4 = voxdb sample rate)`, `[9] diphonedb`, `[0x20] cached Viterbi
  graph`, `[0x28] segment list`. The `"diphone_graph_func"` userdata is fetched via
  `FUN_0005d724 (:41763)` and called `(params, ctx_buf, n)` with the 96-byte context vectors.

### 3.7 `diphoneset_num`, `diphone_graph_func`, `resample_wave`

* **`diphoneset_num`** (int attr on items): index of the `"p-n"` diphone in the name table —
  `FUN_0005ef00` (`:41963-41972`), stored via `FUN_00058fac(item,"diphoneset_num",idx)`
  (`:41970`); used to index the u32 index table and 36-B records (`:43143-43150`, `:42172-42179`)
  and as the section id for payload reads (`FUN_0005ef70`, `:42168`). Items missing both
  `diphone` and `diphoneset_num` force a graph rebuild (`:42101-42102`, `:42388-42393`).
* **`diphone_graph_func`** (userdata 0x29): called once per utterance with
  `(params, ctx_buf, n)`; the plugin implementation `FUN_00030214` (plugin `:7843-7872`) builds
  nodes `{ptr = name_table + idx*0x14, memcpy 0x60 ctx, cost func ptr}` for each adjacent pair
  (same `"%s-%s"` keying); returns the graph cached at `streamer+0x20`; `dp_debug_func`
  (uttfunc tag 0xf) is invoked after Viterbi for debugging (`:42053-42057`); empty/failed graph
  resets the cache (`:42058-42062`).
* **`resample_wave`** (int param, Hz): `FUN_0005b17c` → `FUN_00059958(wave, hz)` (`:42103-42109`,
  §1.8). Wave struct: `+4 sample_rate, +8 num_frames, +0xc channels, +0x10 int16 buffer`.

---

## 4. Speech marks

### 4.1 Record and container layouts (proven)

**Mark record = 20 bytes (0x14):**

| off | type | field |
|---|---|---|
| +0x00 | u32 | `type` (0..4) |
| +0x04 | u32 | `name` (char* or NULL; see §4.3) |
| +0x08 | s32 | `startTextOffset` |
| +0x0c | s32 | `endTextOffset` |
| +0x10 | s32 | `sampleOffset` (samples from wave start) |

Proof: constructor `FUN_0004aa5c @ 0x4aa5c` (`libttsivonavoice.c:27004-27030`) writes exactly these
five words at stride `0x14`; growth in 128-record chunks: `if ((count & 0x7f) == 0) realloc(array,
(count+0x80)*0x14)`; count at `wave+0x0c`, array at `wave+0x10`. The same layout is re-read by the
merge loop (`:27600-27630`) and by the JNI bridge (`decompiled.c:6470+`).

**Wave object = 24 bytes (0x18):** `{u32 sample_rate, u32 nSamples, int16* samples, u32 nMarks,
mark* marks, void* chunk}` — built in `FUN_0004ae28 :27350-27360` (`malloc(0x18)`; `[5]` = the
`FUN_0005a698` result object that owns the sample buffer), merged in
`tts_streamer_synth :27560-27650`, released by `tts_wave_delete @ 0x4a9b4 (:26958)`.

### 4.2 The name-copy table

During merge, names are deep-copied only for some types (`libttsivonavoice.c:27604-27616`):

```c
if (type < 5 && word_at_dump_0x15bfc8[type] != 0) dst.name = src.name;   /* pointer copy */
else                                              dst.name = FUN_0005b884(src.name); /* strdup */
```

Table at file `0x14bfc8` (dump `0x15bfc8`) = `{0, 1, 1, 0, 1}` for types 0..4 — an **ownership
flag**: value 1 (types 1, 2, 4) → name pointer used as-is and never freed (NULL, static `"sil"`,
static viseme-class string); value 0 (types 0, 3) → heap copy that `tts_wave_delete @ 0x4a9b4`
frees (the scan in `:26970-26997` frees the name only when `type > 4 || table[type] == 0`).
`FUN_0005b884 @ 0x5b884 (:40030-40046)` is a NULL-safe **strdup** (`NULL→NULL;
malloc(strlen+1); strcpy`). The merge applies the same rule when copying between waves:
alias if the table entry is nonzero, else strdup (`:27606-27614`).

### 4.3 Producers (engine side)

All engine-side producers are in the pump loop of `FUN_0004ae28` (`libttsivonavoice.c:27360-27425`)
plus its helpers. The pump consumes **"audiotag" event nodes** (VAL tag `0x25`, accessor
`FUN_0005a5b0 :38791`) built by `FUN_0005a698 @ 0x5a698` (`:38850-39010`) from synthesis timing
records `{[0] utterance item, [1] attrs, [2] sample-pos, [3] sample-end}` (`FUN_0005d724 :41761`).
Node layout (20 B, alloc `FUN_0005a590 :38765`): `[0]` token-name attr, **`[1] =
FUN_00065c0c(item)` phoneme string** (`:38966/:38970`), `[2]` sample pos, `[3]` flags, `[4]` attrs
item (`:38989`). Flag writers: `4`+`0x10` pair for non-item timing records (`:38881-38900`);
`0x30` (`=0x10|0x20`) for token transitions whose token has **no SylStructure segment**
(punctuation-only/non-phonetic token — `LAB_0005aa34 :38949`) which arms the `"sil"` viseme path;
`1` for segments, OR'd with `4` when the previous item's token differs
(`R:SylStructure.parent.parent.R:Token.parent` comparison, `:38908-38920`, OR at `:38981`) and with
`8` when the Phrase→SylStructure walk fails (`:38985`); **flag 2 never occurs**.
`start_pos`/`end_pos` attrs (consumed at `:27379-27380`) are written by the text/SSML pipeline:
`FUN_00042bdc` (`:22052`, silence tokens = −1), `FUN_00043348` (`:22295`), `FUN_0004349c`
(`:22343`), `FUN_000436a8` (`:22431/:22499`), `FUN_00043bb0` (`:22702/:22865/:22884`), and copied
from parsed token records by `FUN_000450a0` (`:23157-23159`, record +8/+0xc, text ptr +0x10 —
its per-token-type switch `:23164-23231` also handles attrs `phones`, `xsampa`, `silence`,
`prepunctuation`, `interpret-as`, `interpret-as-format`).

| type | producer | name | text offsets | sample offset | meaning |
|---|---|---|---|---|---|
| **2** | `:27368` `FUN_0004aa5c(wave,2,0, utt+8, utt+0xc, 0)` when the utterance starts (`*(state+0x14)==0`) | NULL | utterance start/end text offsets | 0 (utterance start) | **sentence** (`TYPE_SENTENCE`) |
| **1** | `:27387` `FUN_0004aa5c(wave,1,0, start_pos, end_pos, node_sample)` when a node has flags `&4` and the token span changed | NULL | `start_pos`/`end_pos` from the node's feature table (`FUN_0005901c(node+0x10,"start_pos"/"end_pos")`) | node sample pos | **word/token** (`TYPE_WORD`) |
| **3** | `FUN_0004ad70 @ 0x4ad70 (:27185-27230)` called at `:27385` (flags `&4`) and `:27396` (flags `&0x10`): dequeues from the **SSML mark FIFO** at `streamer+0x28` via `FUN_0003d514 @ 0x3d514` (`:18646-18659`; monotone FIFO with a cursor — an entry fires when `entry+0xc ≤ currentPos`) and emits one record per mark whose `end > base` | `strdup(entry[0])` (table flag 0 → `FUN_0005b884`) | entry +4 / +8 (start/end text offsets) | current sample pos (`param_5`) | **SSML `<mark>`** (`TYPE_SSML`) |
| **4** | `:27401/:27407` — flags `&0x20` → name `"sil"` (static `DAT_00156f00`, file `0x146f00`); flags `&1` → name `FUN_0004d17c(node+1)` (nonzero only) | `"sil"` or viseme class | 0, 0 | node sample pos | **viseme** (`TYPE_VISEME`) |
| **0** | no producer found in this library (see §6) | (strdup'd when present) | — | — | **phoneme** (`TYPE_PHONEME`) — unused in this build |

**Type names are proven**, not guessed: the JNI bridge maps the engine's type value to Java static
fields `TYPE_PHONEME, TYPE_WORD, TYPE_SENTENCE, TYPE_SSML, TYPE_VISEME` (table `DAT_00080ea0` in
`libttsivona.so` at file `0x6fea0`; strings at file `0x6cd37/0x6cd44/0x6cd4e/0x6cd5c/0x6cd66`;
`GetStaticIntField` loop `decompiled.c:6440-6451`, `switch` `:6457-6471`, index = engine type).

**Type-4 (viseme) name mapping proven**: `FUN_0004d17c @ 0x4d17c (:28679)` looks the input up in a
sorted `{char* key, char* value}` table of 0x109+1 entries at dump `DAT_001915e0` = file `0x1805e0`
(dump `0x1915e0` − `0x10000` base = vaddr `0x1815e0` − `0x1000` file shift in `.data.rel.ro.local`).
Dumped from the binary: **keys are phoneme symbols** (XSAMPA-style: `1`, `A:`, `3\`, `@U`, `B`, …
including punctuation `!`, `"`, `%`, `.`, `?`, `:`) and **values are viseme classes** — only 19 distinct
values: `""  @  B  E  J  O  S  T  a  e  f  i  k  o  p  r  s  t  u`. Exact match first, then a
longest-substring fallback (`FUN_0005257c`); leading `" .\"%"` delimiters are skipped.
The input string is built by `FUN_00065c0c @ 0x65c0c (:46745)` from the segment's syllable: a bracketed
phoneme string (`'['`/`']'`, stress markers `DAT_00157164`/`DAT_00155208`/`DAT_0015510c`, prefix
`DAT_00159250`), converted with the voice's `xivona_to_xsampa_rules` param. `"sil"` is the silence
viseme emitted for pause nodes.

* Flag bits on mark nodes (set in `FUN_0005a698 :38865-39000`): `1` = has name/viseme event, `4` = has
  `start_pos/end_pos`, `8` = token-parent-changed extra (OR'd onto flag-4 nodes → flags `5`/`0xd`),
  `0x10` = end-position node, `0x20` = silence variant (`puVar8[3] = 0x30` = `0x10|0x20` at
  `LAB_0005aa34`); the pump tests only `1`, `4`, `0x10`, `0x20` (bits 2/3 are never consumed).
* Timeline: sample offsets come from `FUN_00061c1c @ 0x61c1c (:44214)` events
  (`{segment, sampleOffset}` sorted into `streamer+0x1c`), consumed during `FUN_000618a8` and passed
  into the node list; text offsets are feature `start_pos`/`end_pos` (token spans) and the SSML mark
  table entries. In the merge, `sampleOffset` is rebased by the cumulative sample base of each input
  wave (`:27618-27620`).

### 4.4 Consumer (JNI bridge → Java)

`FUN_0001fac0` in `out/ghidra_dump/decompiled.c` (line ~6319, `libttsivona.so`; the bridge dump also
uses the +0x10000 base — dump `0x80ea0` = vaddr `0x70ea0` = file `0x6fea0`):

* `param_7` is the wave; marks count at `+0x0c`, array at `+0x10`; records are read as
  `{type u32, name, startTextOffset, endTextOffset, sampleOffset}` (`decompiled.c:6470-6500`), walking
  `local_74 += 0x14` per record (`:6497`).
* A per-object **bitmask `puVar11[5]`** filters marks: `((mask >> (type & 0xff)) & 1) != 0`
  (`decompiled.c:6454`) — bit *n* enables type *n* (e.g. 0x1F = all). The mask is set by the JNI
  setter `Java_…_NativeIVONAEngineICS_synthesizeText(String,byte[],List,int)`
  (`decompiled.c:6639-6692`): it builds a 0x1C-byte callback ctx
  `{env, thiz, methodID of audioAvailableClbk, marks ArrayList, cumBase=0, **mask = param_6**
  (`:6653`), audio buffer}`; registered once at `Java_…_create` via
  `FUN_0001cec0(engine, 0x1fac1, 0)` (`:6511-6519`). On the Java side the mask comes from
  `Integer.parseInt(request.getParams().getString("com.ivona.tts.oem.GENERATE_MARKS"))`
  (`NativeIVONAEngineICS.java:13,75`); `i > 0` selects the marks path (`:79-94`), otherwise the
  no-marks `synthesizeText(text, buf)` overload is used (`:103/:112`). No code inside this APK sets
  `GENERATE_MARKS` — the requesting app/OEM integration supplies it **[observed absence]**.
* For each kept mark a `android/speech/tts/SpeechMark` is allocated (`FindClass` at `:6388`) and its
  fields `type`, `sampleOffset`, `name` (String), `startTextOffset`, `endTextOffset` are set through
  JNI (`GetFieldID`s at `:6405-6435`; `SetIntField`/`SetLongField` at `:6472-6484`; name null →
  `NewStringUTF("")` else `NewString`, `:6487-6491`; object added to the `ArrayList` at `:6493`).
* **Type translation**: a `switch(type)` `case 0..4` (`decompiled.c:6457-6471`) selects
  `local_2c[N]`, where `local_2c[0..4]` are **static int fields fetched from the SpeechMark class**
  via `GetStaticFieldID`/`GetStaticIntField` (name-pointer table `DAT_00080ea0`, loop at
  `:6440-6451`): index 0 = `TYPE_PHONEME`, 1 = `TYPE_WORD`, 2 = `TYPE_SENTENCE`, 3 = `TYPE_SSML`,
  4 = `TYPE_VISEME` (strings in `libttsivona.so` `.rodata` at file `0x6cd37`, `0x6cd44`, `0x6cd4e`,
  `0x6cd5c`, `0x6cd66`).
* After the per-mark loop, `puVar11[4] += *(param_7 + 4)` (`:6495`) — **[INFERENCE]** a running
  sample base used when the caller delivers marks in chunks (chunk base added to offsets in the
  sampleOffset setter `:6474` via `puVar11[4] + mark+0x10`).
* The Java side (`com/ivona/ttslib/ics/NativeIVONAEngineICS.java:88-94`) collects the marks into an
  `ArrayList` passed to `synthesizeText(text, audioBuffer, marks, …)` and delivers them via the
  `audioAvailableWithMarks` callback (`:48-50`).

**Type semantics (all five, proven):** 0 = phoneme (never produced by this engine build),
1 = word boundary, 2 = sentence boundary, 3 = SSML `<mark>` (named), 4 = viseme (phoneme→viseme class
name, `"sil"` for pauses).

### 4.5 Offset semantics (text and sample)

* **Text offsets** (`startTextOffset`/`endTextOffset`, types 1/2/3) are byte positions produced by
  the text/SSML parser over the **engine's input buffer**: the bridge passes the request text as
  UTF-8 (`GetStringUTFChars`, `decompiled.c:6655`) and the sentence splitter indexes that buffer
  directly (`*param_2 + param_3`, `:22556-22560`; token text attr = interior pointer, `:23159`).
  **[INFERENCE]** offsets are UTF-8 byte offsets into the request text as submitted (which may itself
  be SSML — the exact offset mapping inside SSML documents was not line-traced).
  Type 2 spans the whole sentence record (+8/+0xc); type 3 spans the mark's own entry; type 1 spans
  `start_pos`/`end_pos`; type 4 carries 0/0.
* **Sample offsets** are the audiotag node's sample position (`node[2]`, `:38967`), valid relative
  to the current chunk wave (bounds-checked against wave+4 at `:27377`; type 2's in-wave offset is 0
  = sentence start). Two rebase stages make them globally correct: (1) `tts_streamer_synth` merge
  adds the cumulative sample count of preceding chunk waves (`:27625`);
  (2) the bridge adds its own cumulative base `puVar11[4]` when setting `sampleOffset`
  (`decompiled.c:6474-6477`), incremented by wave+4 after each callback chunk (`:6533`).

---

## 5. Certificate / authenticity subsystem

The certificate text itself is embedded XOR-obfuscated in `libttsivona.so` and decoded by
`FUN_00023284` (`decompiled.c:9897`); the decoded reference certificate is
`out/certs/ivona_certificate_decoded.txt` (1798 B: comments, 9 attributes, signature block of 1040
hex chars = **520 bytes**). This section covers what `libttsivonavoice.so` does with it.
All certificate structs come from `FUN_0005ac10` = `calloc` (`:39105-39126`), so unset = 0.

### 5.1 Grammar and attribute parsing — `FUN_0004e45c @ 0x4e45c` (`:29487-30000`)

* Pre-pass `FUN_00052d10` (`:29539`, fn `:32953-32998`): replace-all of `DAT_00157984` (file
  `0x147984` = `"\r\n"`) with `DAT_00156814` (file `0x146814` = `"\n"`) — **proven** CRLF→LF
  normalisation before hashing/parsing.
* Line loop (`:29546-29575`): skip `" \t\r\f\v"`; `#`-comment and empty lines skipped silently;
  a line of exactly 25 chars must be `-----BEGIN SIGNATURE-----` (`strncmp :29564-29575`).
* Attribute lines = `Key: Value` (first `:` splits; both sides trimmed; `:29576-29607`);
  malformed → code 1 `Invalid certificate line…` (`:29991`); **duplicates** → code 1
  `Duplicate certificate attribute %s` (`:29943-29946`).

| attribute | parse | citations |
|---|---|---|
| `License-ID` / `Certificate-ID` | `strlen<9`, `sscanf("%x%c")` → u32 into cert[8] (both write the same slot) | `:29713-29732`, `:29948-29965`; errors `Expected a hexadecimal integer`, `Value too long` |
| `Num-threads` | `"unlimited"`(case-insens.) → −1; else base-10 `strtol` (whole string) | `:29744-29770`; errors `Expected a decimal integer`, `Additional characters after number` |
| `Thread-speed` | `"unlimited"` → −1.0f (`0xbf800000`); else float via `FUN_00052860` (`:32573`) | `:29771-29782`; error `Not a floating-point number` |
| `Expiration-date` | `"NEVER"` → (−1,−1); else POSIX regex `^YYYY-MM-DD( HH:MM(:SS)?)?$` (`regcomp 0x80db8`, `regexec 0xa34ec`, captures 4/6/7) → `timegm` (`FUN_00057840 :36483+`); date-only ⇒ **23:59:59** (`:29846-29854`); ranges y≥1970, mo 1-12, d 1-31, h≤23, m≤59, s≤60 | `:29783-29890`; errors `Date regex compile error` (10), `Regex exec error %d` (10), `Invalid date format` (5) |
| `Voices` | tokenised by separator charset `DAT_00155ff4` (file `0x145ff4`) = **`" \t\n\r\xa0"`** (space, tab, LF, CR, NBSP) via `FUN_0004e18c`/`FUN_00053318`/`FUN_0005329c` (`:33306-33317`, `:33270-33293`); empty → required-check fails | `:29897-29902` |
| `Extension-SSML` | `strcasecmp` TRUE→cert[10]=1, FALSE→0, else error | `:29904-29919`; error `Expected "TRUE" or "FALSE"` (5) |
| `Comments` | explicit rejection path `FUN_00047500(1,"Unsupported certificate comments")` + cleanup goto (`:29921-29929`); the decompiler renders the guard as statically false — treat per intent **[INFERRED: reject]** (§6) | `:29921-29929` |
| any other (`Product`, `Licensee`, `Licensor`, …) | stored verbatim in the attr map (`FUN_0005af1c`), no validation; there is **no** `Unsupported certificate attributes` string in this dump (grep-verified) | fall-through `:29930-29934` |

**Required attributes**, checked only when the signature marker is reached (`:29605-29690`, all
code 1): `Certificate-ID` ≠ 0 (`:29634`), `Expiration-date` set (`:29637`), `Voices` non-empty
(`:29640`), `Product`+`Licensee`+`Licensor` present (`:29644-29657`), `Num-threads` = −1 or > 0
(`:29658`, error `:29685`), `Thread-speed` = −1.0f or ≥ 1.0f (`:29659-29666`, error `:29681`) —
the last two are **de-facto mandatory** because calloc defaults (0, 0.0f) fail the range checks.
Optional: `License-ID`, `Extension-SSML` (default FALSE), `Comments`, unknown names.
EOF without signature → code 1 `Certificate signature is missing` (`:29695`); per-attribute value
failures are wrapped as code 1 `Error reading certificate attribute "<name>": …` (`:29967`, wrapper
`FUN_00047570 :24590`).

### 5.2 Signature format and verification

* **Block parser `FUN_000519fc @ 0x519fc` (`:31677-31786`)**: re-checks the marker (`:31696`);
  hex digits accumulate two nibbles per byte, whitespace allowed between digits (`:31706-31751`);
  odd nibble → `Invalid certificate signature size` (`:31759`); must be followed by
  `-----END SIGNATURE-----` (23 chars; `Invalid certificate signature format` `:31766-31772`) and
  nothing but whitespace to EOF (`Illegal data after certificate signature` `:31774-31779`) —
  the signature block must be **last**; the parser returns right after verification (`:29653-29656`).
* **Size**: exactly **0x208 = 520 bytes** required (`FUN_00051c70` `:32093-32096`); matches the
  measured 1040 hex chars (13×76 + 52). Layout: `[0:0x200]` encoded RSA signature, u32 at `+0x200`
  and u32 at `+0x204` = trailers read at `:32040-32041`.
* **Encoding** (`FUN_00051c70 :31818-32029`): unpack the 520 bytes into an 8×520 bit-plane matrix,
  reassemble transposed, XOR every byte with a 32-byte mask at file `0x14c134` (period `i & 0x1f`)
  **[INFERENCE: net effect = 8×520 bit-matrix transpose + XOR; transcribe the two loops verbatim
  for a byte-exact reimplementation]**.
* **Hash + verify** (`:32042-32092`):
  * **SHA-512** (init `FUN_000a9b68 :65742-65771` with the standard IVs `0x6a09e667…0x5be0cd19`,
    digest len `0x40`; final pads 128-byte blocks `:65774-65823`; OpenSSL 0.9.8l strings at files
    `0x162600`/`0x162a30`); SHA plumbing errors → code 10 `SHA Init`/`Feeding SHA`/`SHA Final`
    (`:32057-32074`).
  * **Message = `u32le(sig[0x204:0x208])` ‖ certificate text bytes `[0 … offset-of-BEGIN-marker)` ‖ `u32le(sig[0x200:0x204])`** — updates at `:32050-32064`; the hashed text prefix includes comment lines and exact line breaks.
  * **RSA PKCS#1 v1.5 verify**: `FUN_000b3df0` (`:68074-68166`, polarssl `rsa_sign.c`) decrypts the
    signature, ASN.1-parses the DigestInfo, compares the OID-derived NID against `0x2a2` = **674 =
    `NID_sha512`** and digest length `0x40` (`:68129-68145`). Key: 512-byte modulus (RSA-**4096**)
    from file `0x14c154`, exponent 4 bytes from file `0x14c354`, loaded per verification by
    `FUN_00052154 @ 0x52154` (`:32102-32133`; failure → code 10 `Load pubkey`). Mismatch → code 1
    `Certificate signature mismatch` (`:32077-32081`).
  * On success, `sig[0x204:0x208]` is exported as the **signing timestamp** (`:32082-32085`), and the
    0x22c-byte key blob at file `0x14c12c` is copied onto cert[0xb] (`:32123-32127`) — later reused
    as an XOR seed for audio-parameter quantisation in `FUN_000494a4`
    (`(val ^ 0xe6aa80c7 ^ cert[0xb]_lo) % 99 + 1`, `:26167-26220`).
* `Invalid certificate of authenticity` is the default text of **error code 1**
  (`tts_errmsg` switch, `:24535-24536`); in this build every code-1 set carries a more specific
  message, so a reimplementation should surface the specific text and map code 1 to the generic one.

### 5.3 Expiry, constraints, multi-certificate rules

* Expiry check `FUN_0004e028 @ 0x4e028` (`:29265-29297`): `now64 > exp64` (NEVER short-circuits 0);
  `tts_load_certificate` frees the cert → code 2 (`:25507-25514`); re-checked at `tts_load_voice`
  (`:27997-28002` → code 2 at `:28140`) and `tts_streamer_start` (`:27135-27142`).
* Anti-rollback: `now ≥ signing timestamp` else code 1 (`:29670-29678`) —
  `"The system time is shifted back. Please update the system time."`.
* **Error code 3** (default `The certificate of authenticity constraints would be violated`,
  `:24539`) is set at: `No certificates loaded` (`FUN_00047fb4 :25191`, `FUN_00048034 :25222`,
  getters `:25370/:25412`), SSML MIME gate (`:26004-26008`), voice-not-allowed (`:28076`),
  PLS-without-SSML (`:28226-28230`).
* **Same Certificate-ID re-load** → replace only if the new signing timestamp is strictly greater,
  else code 6 `Attempt to load the same certificate twice` (`:25560-25573`). **Different ID** →
  compatibility check `FUN_0004e244 @ 0x4e244` (`:29415-29485`): IDs differ (`:29427`),
  `Extension-SSML` equal (`:29431-29433`), `Thread-speed` equal (`:29438`), then every other shared
  attribute must `strcmp`-equal **except those in the match-exempt pointer table**
  `PTR_s_Certificate_ID_00191e44` (dump `0x191e44` = file `0x180e44`) whose six entries are
  byte-proven: **`Certificate-ID`, `Num-threads`, `Voices`, `Expiration-date`, `Extension-SSML`,
  `Thread-speed`** (a second, four-entry list `{Certificate-ID, Num-threads, Voices,
  Expiration-date}` sits just before it at file `0x180e30`); violations → code 6 `Values of
  attribute "%s" do not match` (`:29440-29475`). Compatible certs are merged into the active view
  by `FUN_0004db84 @ 0x4db84` (`:29077-29180`): Certificate-IDs concatenated, Num-threads summed
  (any UNLIMITED → UNLIMITED), Voices unioned, **earliest** Expiration-date kept.

### 5.4 Enforcement points (what a reimplementation must gate)

1. **SSML MIME gate** — `FUN_000491b4 @ 0x491b4` (`:25989-26022`): `application/ssml+xml` requires
   the active cert's `Extension-SSML` (cert+0x28) else code 3 (`:26004-26008`); `text/plain`/`""`
   allowed; other MIME → code 6 `Unsupported MIME type` (`:26011-26014`).
2. **SSML tokenizer gates** — `FUN_0003bcf4` (`:17697-17707`) and `FUN_0003c548` (`:18041-18050`)
   pass cert+0x28 into the parser so raw SSML is disabled when FALSE.
3. **Input admission** — `FUN_0004a2d4` (`:26705-26740`) wraps input in a synthetic `<speak>` when
   Extension-SSML = 0 (§1.2).
4. **Voice allowlist** — `FUN_0004dee4 @ 0x4dee4` (`:29206-29262`): `custom_voice != 0` → allow
   (`:29219`); else the `Voices` list (cert+0x24) is matched case-insensitively
   (`FUN_000531cc :33210` list-contains on voice_name; exact-match `FUN_00053104 :33182` against
   `DAT_001550fc` = file `0x1450fc` = **`"*"`**; case-insensitive match against `DAT_00157930` =
   file `0x147930` = **`"all"`**; language-code tokens split on the charset above, each ≤ 0x1a
   chars prefixed with u32 constant `0x3a6c4c61` = memory bytes `61 4c 6c 3a` = **`"all:"`** and
   looked up case-insensitively — allowed iff any lookup hits, `:29237-29256`). The shipping cert's
   `Voices: ALL` is accepted via the `"all"` path. Consumers: `tts_load_voice` (`:28070`,
   reject = `dlclose` + code 3 `Voice not allowed by the certificate`) and `tts_streamer_add_voice`
   (both voices checked, `:27683-27706`, `:27734-27747`).
5. **PLS gate** — `tts_pls_load` (`:28226-28230`): requires Extension-SSML else code 3.
6. **Speed / thread caps** — `tts_streamer_start` (`:27135-27163`): requested speed is **clamped**
   (never rejected) by cert+0x18 (−1.0f = unlimited) (`:27143-27161`); if cert+0x1c (Num-threads)
   ≠ −1, a per-certificate thread slot must be acquired (`FUN_00047fb4 :25175-25204` →
   `FUN_0005403c`) else code 3 `No certificates loaded`; slot re-validation inside the pump
   (`:27263-27267`, i.e. the `Limits verification` path §1.3) and `FUN_00053f38/FUN_0005403c`
   (`:33999`, `:34043`).
7. **Getters** — `tts_certificate_get_single @ 0x482e4` (`:25351`) and `tts_certificate_get @
   0x483b8` (`:25393`): bodies identical; accept a tts handle (magic `0x3e1b8f65`) or a loaded-cert
   entry (magic `0x730366b1`); return the raw string value of an attribute from the ACTIVE
   certificate (merged view, else first cert); empty list → code 3; bad args/unknown attr → code 8.

### 5.5 The semaphore `/IVONA-e3a8a7e2d4d4fca3` (cross-process certificate/thread registry)

* `FUN_000509ec @ 0x509ec` (`:30775-30812`): loop { `sem_open(name, O_RDONLY,0,0)` under
  `umask(0)`; ENOENT → `sem_open(name, 0xc0, 0x1b6, 1)` where **`0xc0` = O_CREAT|O_EXCL,
  `0x1b6` = 0666, initial value 1**; EEXIST → retry } — race-safe create-or-open.
* `FUN_000508a0` (post, `:30696-30719`) posts only if `sem_getvalue ≤ 0`; `FUN_00050910` (wait,
  `:30721-30747`) uses `sem_timedwait` with a **2 s timeout**, retries on EINTR, and treats
  ETIMEDOUT as success (best-effort lock); `FUN_00050998` = close+free; `FUN_00050860 @ 0x50860`
  (`:30677-30694`) = `sem_unlink`, called only from `FUN_0005370c` (`:33587`) which has no internal
  callers (teardown-only **[UNDETERMINED external caller]**).
* **Purpose**: guards a system-wide registry. `FUN_000537e0 @ 0x537e0` (`:33655-33736`, called from
  `tts_load_certificate :25518-25528` **only when Num-threads ≠ UNLIMITED**, keyed by Certificate-ID
  + pid): open sem → `FUN_00051944(0x6da556e8, 0x1ff8, …)` — a SysV shared-memory table of 686
  (0x2aa) 12-byte slots `{Certificate-ID, pid, tid}` → wait → claim a free slot or one whose pid is
  dead (`kill(pid,0)` = ESRCH) → post. Full table → code 10 `Too many certificates concurrently
  loaded in the system` (`:33698-33700`). Release = clear slot (`FUN_0005374c :33613-33653`).
  Re-validation (e.g. after fork) = `FUN_000539a0 @ 0x539a0` (`:33738-33986`, the pump's
  `Limits verification` step; `No access to shared memory` `:33752`).
* **In this build the shm layer is stubbed**: `FUN_0005191c/FUN_00051944` unconditionally error
  `System function missing: shmget` and return 0 (`:31621-31644`). Consequence: a certificate with
  a finite `Num-threads` can never load here; `Num-threads: UNLIMITED` bypasses the registry —
  which is why the shipping IVONA certificate loads.

### 5.6 Error codes (`tts_errmsg` table `:24526-24562`; setters `FUN_000474e4 :24564`,
`FUN_00047500 :24576`; thread-local code `DAT_0019600c`, message `DAT_00196010` 256 B)

`0` success · `1` Invalid certificate of authenticity (all parse/signature/time-shift failures,
each carrying a specific sub-message) · `2` certificate expired (load / tts_load_voice /
tts_streamer_start) · `3` constraints violated (No certificates loaded, SSML gate, voice allowlist,
PLS gate) · `4` failed to load voice (vox errors, version mismatch) · `5` format error (attribute
value errors, wrapped into 1) · `6` argument out of range (same-cert-twice, attribute mismatch,
unsupported MIME, mixed voices) · `8` invalid argument (bad handles) · `9` OS error
(file/semaphore/strerror_r) · `10` internal error (Load pubkey, SHA steps, date regex, semaphore
registry full, `No access to shared memory`, `System function missing: shmget`, `Too many PLS
lexicons`, CURL init, `Limits verification error`). `FUN_00050860` passes raw errno as the code
(`:30688`).

### 5.7 Accept/reject checklist for a reimplementation

**ACCEPT iff all hold:** (1) grammar §5.1 (comments/blank lines skipped, `Key: Value`, trimmed);
(2) signature block last: marker + 1040 hex chars + END marker + EOF; (3) required attributes
`Certificate-ID` (hex u32 < 9 chars), `Expiration-date`, `Voices` (non-empty), `Product`,
`Licensee`, `Licensor`, `Num-threads` (UNLIMITED or > 0), `Thread-speed` (UNLIMITED or ≥ 1.0);
(4) `Extension-SSML` ∈ {TRUE,FALSE} if present, unknown attributes accepted verbatim, no
duplicates; (5) signature verifies: 520 B decode (bit-transpose + XOR mask file `0x14c134`),
SHA-512 of `u32le(sig[0x204]) ‖ text[0:marker) ‖ u32le(sig[0x200])`, RSA-4096 PKCS#1 v1.5
(modulus file `0x14c154`, exponent file `0x14c354`); (6) `now ≥ sig[0x204]` and
`now ≤ Expiration-date` (unless NEVER); (7) second certificate: different ID + equal
Extension-SSML/Thread-speed + equal shared attrs → merge (voices union, threads sum, earliest
expiry); same ID → only as an upgrade with strictly later signing time.

**REJECT:** (8) malformed line (no/leading colon, empty key) → code 1; (9) duplicate attribute →
code 1; a `Comments:` attribute → code 1 (subject to §6 item 23); (10) missing any required
attribute or Num-threads = 0 / Thread-speed < 1.0 → code 1; malformed values → code 1 wrapped;
(11) signature problems (absent / odd hex length / size ≠ 520 / bad END marker / trailing data /
mismatch) → code 1; (12) expired (code 2) or clock before signing time (code 1); (13) runtime:
SSML or PLS without Extension-SSML (code 3), voice not in Voices list with `custom_voice == 0`
(code 3). Speed above the cap is **silently clamped**, not rejected; finite Num-threads without a
working shm registry always fails in this build (code 10).

---

## 6. What we could not determine

Consolidated from this investigation; each item states what was tried.

### Front-end / pipeline

1. **Five default stage bodies are missing from the decompilation**: dump addresses `0x66230`
   (`text_analysis_func` #2), `0x66554` (`intonation`), `0x666c8` (`pause_insertion`),
   `0x667e0` (`lettertosound`), `0x66dc4` (`phrasing`). Their addresses fall between the headers
   `FUN_00065c0c :46745` and `FUN_0006706c :46944`, but no code is emitted for them. *Tried:* header
   listing via `fn_at.py`, grep for `0x66xxx`/`FUN_0006xxxx` names and xrefs — nothing. Needs a raw
   disassembly or Ghidra re-run with those ranges analyzed. In practice Kendra overrides all five
   stages, and the two present defaults (`FUN_0006706c`, `FUN_000674f8`) were read.
2. **`lang`(6), `meta`(10), `metadata`(11), `speak`(17), `desc`(4) dispatcher cases** were not
   separately observed in `FUN_00040770`'s switch (the name→type table is proven; the behaviors of
   cases 1/2/3/5/7/8/9/0xc/0xd/0xe/0xf/0x10/0x12/0x13/0x14 were read). *Tried:* single pass over
   `:20605-21400`.
3. **`duration_func` execution**: the string exists only in the stage table (file `0x184198`, NULL
   default); Kendra registers a `duration_func` userdata (plugin `:7816-7818`) but the plugin body
   was not decompiled here — how per-phone durations/pitch targets are computed inside the voice
   (with `zdur_cart`) is **[INFERENCE]**.
4. **Where PLS/user lexicons are consulted during phonemization**: push sites (front-end lexicon
   stack `ctx+6`, `user_lexicon` param) are proven; the consuming instruction is inside the voice's
   `tokentowords_func` (`DAT_00037c5c`, plugin body not decompiled). Likewise the callers of
   `FUN_0005a608`/`FUN_00065138` (user-lexicon install/query) have no sites in the engine dump.
5. **Sentence-record +8/+0xc writers**: produced by the splitter chain
   `FUN_00043348/4349c/436a8/43bb0` from input-buffer offsets — the exact assignment lines for the
   final sentence record were not traced to the scanner top **[INFERENCE on the range]**.
6. **Waveform window formula**: the boundary-adjustment windows in `FUN_0005d7c4 :42256-42400`
   combine the record duration (`i16/1000`) with sample counts through `0.5f`-scaled float math;
   the exact intent (window length in samples vs seconds) was not derived.
7. **Why `next_index == current_index + 1` disables the crossfade** (`:42404-42416`) — adjacency is
   proven to control `FUN_00061620`'s flag; the structural reason (shared joint waveform vs
   sort-order artifact) is **[INFERENCE]**.
8. **`wave`-item feature value `0x29`** (`:42118-42150`, branch between `FUN_00059b70`/`FUN_00059be0`)
   — semantics unread.
9. **Position callback consumer**: `FUN_000542b4(document, ms)` (`:27456-27472`) is invoked with a
   millisecond position; its downstream (bridge/Java) was not line-traced.
10. **Post-filter**: no dedicated post-filter stage was found — only boundary transforms
    (pitch/duration/compress/gain), the crossfade (`FUN_00062bd4`) and the optional resampler.
    Either none exists or filtering happens inside voice-side graph/cost functions
    **[INFERENCE]**.

### Speech marks

11. **Type 0 (`TYPE_PHONEME`) has no producer** anywhere in `libttsivonavoice.so`, `libttsivona.so`
    or the app's Java (exhaustive `*0x14` record-write search: only `:27025` generic type,
    `:27220` literal 3, plus Viterbi/rsa structs). Whether other voice plugins/API versions produce
    it was not audited. *Tried:* stride-pattern grep, call-site enumeration, bridge and Java grep.
12. **Numeric values of `android.speech.tts.SpeechMark.TYPE_*` constants** — the five names are
    proven (bridge table) but the values live in the framework class, absent from this repo.
13. **Who sets `com.ivona.tts.oem.GENERATE_MARKS`** — no producer in the APK (observed absence);
    it arrives via the SynthesisRequest params bundle from the requesting app/OEM integration.
14. **SSML-mark FIFO (`streamer+0x28`) fill site**: consumption (`FUN_0003d514`) and installation
    (`FUN_0003d508` from `doc+0x1c`) are proven; the parse-time enqueue of `<mark>` records into
    `doc+0x1c` (dispatcher case 9 area, `:20965-20984`) was located but not line-traced to the
    record writer.

### On-disk formats

15. **ISEF version check**: the second magic/version literal resolves oddly in the decompilation
    (`DAT_0015bd70` reads `"Port"` at file `0x14bd70`) while the file bytes are `00 00 00 01`;
    decompiler pointer artifact — version-check semantics not byte-exact. *Tried:* direct file
    read, constant search.
16. **ISEF crypto details**: block cipher assumed AES-256-CBC (32-B key + 16-B IV from the
    RSA-decrypted 64-B session blob) **[INFERENCE]**; the payload (section contents beyond
    `prm_lex_list`) is **undecryptable** without IVONA's RSA-4096 private key; the BE u32 timestamp
    at ISEF+8 has no traced consumer.
17. **CDXV sections F/G** (20,493,720/4,860,925 and 25,354,648/1,856) semantics; the `"22v"` vox
    filename suffix meaning; the hdr `+0x38/+0x3c` section's reader; payload unpackers for format
    versions 3–7, 9–0xb, 0xd (empty switch cases `:42852-42885`). The 152,219,597-byte OBB vs the
    25,356,504-byte described range (directory entries point deeper into the file) is covered by
    the parallel OBB-container investigation.
18. **`vox_lexicon` blob internals** (`+0x24/+0x38` structures freed at `:47939-47953`) — the
    embedded pronunciation FST/blob belongs to the voice-data-tables investigation.

### In-memory structures

19. **`phonefunc` (0x2f)**: accessor exists; Kendra registers no such param — role undetermined.
20. **Second plugin param list** (`voice object +4` / `listB`) role; `register_voice`'s argument
    forwarding (engine passes the data path `:28016`, plugin prototype decompiles as `(void)`)
    **[INFERENCE]**.
21. **`FUN_0004730c/47314` synth-context object** and the `FUN_00055b40` callback queue
    (`LAB_0004bf5c`) semantics unread.
22. Blank VAL tags `0x0d`, `0x21`, `0x27` (name field empty in the type table).

### Certificate

23. **`Comments:` rejection branch**: the decompiler renders the guard as statically false
    (`:29921-29929`); the string + cleanup goto indicate intent to reject — needs disassembly
    confirmation.
24. **`License-ID` and `Certificate-ID` both write cert[8]** — aliasing intent unknown; it lets
    `License-ID` satisfy the `Certificate-ID` presence check.
25. **Purpose of `sig[0x200:0x204]`** (hashed but otherwise unused) **[INFERENCE: serial/version]**;
    the exact 520-byte bit-permutation must be transcribed verbatim from `:31841-32029`.
26. **External caller of `FUN_0005370c`** (`sem_unlink` teardown) — none inside
    `libttsivonavoice.so`.
27. Whether `FUN_0004e028` in `tts_load_certificate`/`tts_load_voice` receives the cert pointer —
    Ghidra dropped the argument at call sites **[INFERENCE: the freshly parsed cert]**.
28. Whether a reimplementation should implement the SysV-shm thread registry (stubbed here
    `System function missing: shmget`) or treat finite `Num-threads` as unsupported — a product
    decision, not derivable from the binary.

### Cross-cutting

29. Full byte-exact OBB container walk (owned by the parallel OBB investigation; this report only
    uses its header/directory facts verified against engine code).
30. Voice-plugin internals beyond what the engine requires (`libvoice_en_us_kendra.c` stage bodies,
    embedded lexicon/CART data) — owned by the voice-data investigation.
31. **Decompilation gaps**: besides the five stage defaults (item 1), the lexicon VAL destructor
    (VAL dispatch-table free-fn vaddr `0x4d6f8`) has no emitted body — the gap between
    `FUN_0005d6b0 :41729` and `FUN_0005d718 :41746`. Other small functions may be similarly omitted
    from `libttsivonavoice.c`. *Tried:* header listings around each missing address via `fn_at.py`
    and grep — no headers exist.
