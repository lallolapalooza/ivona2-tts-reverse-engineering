# Cost functions — main's share (superseded in part by `report_prosody.md`)

> **Status note (post-coordination, verified):** `report_prosody.md` §1–§2 is the **authoritative**
> description of the cost model and supersedes parts of this file:
> * the five context variants (`FUN_0003055c/313d0/31868/31cb0/320f0`) are called by the engine with
>   **raw 36-byte diphonedb records** (`libttsivonavoice.c:43473`, `rec[prev+1]`, `rec[cur]`, budget int),
>   while the **target cost** (`FUN_00031234` → `FUN_000309a4`) receives the decoded
>   **96-byte feature vectors** plus separate context pointers — so the §4c slot map applies to the
>   target-cost path, not to the five join-cost variants;
> * the target-cost transcription here is incomplete relative to the validated implementation: the
>   byte tests at `0x44` and `0x48` were missing, and the `ph_vc` character comes from `param_2`
>   (the context), not `param_1`;
> * all five variants + the dispatcher + the target cost are **reimplemented and bit-exactly
>   validated** in `scripts/prosody.py` / `scripts/probe_prosody.py`
>   (`--n 2500` → `TOTAL 15000/15000 bit-identical`; independently re-run by me at `--n 400` →
>   `2400/2400`).
>
> What remains useful here: the machine-extracted inventories (§2/§3 constants and field lists), the
> decoded float-constant table (§4), the `FUN_000309a4` tail transcription (§4b) and the
> feature-slot map (§4c) as documentation of the engine's 96-byte vector.
>
> **Update (feature-level unknowns closed):** §4d records the three values the slot map could not
> name — the `ssyl_from`/`ssyl_to` rule, the source of the `gpos` tags, and the `pau` items'
> `0x28`/`0x38` slots.  With §4d in place the target cost is exact at **every** node of both
> validation captures (see `report_pipeline.md` §10.4).


Split agreed with RelievedCondor: they take `FUN_00031868`, `FUN_00031cb0`, `FUN_000320f0`, the
dispatcher `FUN_00031234`, the duration cart and the intonation default. This file covers my three,
with a **machine-extracted inventory** (field offsets, literals, constants) plus the control-flow
structure I read out. All addresses are **Ghidra addresses in `out/ghidra_dump/libvoice_kendra.c`**
(ELF vaddr = Ghidra − 0x10000; the plug-in binary is `out/libs/kendra/libvoice_en_us_kendra.so`).

Reproduce the inventory with: `python3 scripts/cost_inventory.py out/ghidra_dump/libvoice_kendra.c 0x309a4`

## 0. Call graph / how they are reached

```
engine Viterbi (FUN_0005fc04, libttsivonavoice.c)
   └── calls the graph's cost entry  =  FUN_00031234 (dispatcher, stored by the plug-in)
          ├── FUN_000309a4(record_left, ctx_left)      ← my share (target cost)
          ├── FUN_000309a4(record_right, ctx_right)    ← my share
          └── boolean/context penalties (RelievedCondor)
per-pair node cost pointers (set in FUN_00030214, plugin lines 7840-7900):
   "r" ctx → FUN_0003055c | "+" → FUN_00031868 | "g"/"l" → FUN_00031cb0 | "-" → FUN_000313d0 | else → FUN_000320f0
          └── FUN_0003055c and FUN_000313d0 are my share (pure float penalties)
```

Argument shapes (from the decompiled bodies):
* `FUN_000309a4(param_1 = record_a, param_2 = context_b)` — both accessed as *word* pointers
  (`param_N[k]` ⇒ byte offset `4k`) in some lines and as *byte* pointers (`(int)param_N + 0xNN`) in
  others, i.e. the same structure; the inventory lists the byte offsets actually touched.
* `FUN_0003055c(param_1 = record_a, param_2 = record_b, param_3)` — two 36-byte-class records,
  read as bytes at odd offsets (`0x11, 0x13, …`) and at word offsets (`0x20, 0x24, … 0x3c`);
  returns a **float** (via the soft-float helpers `FUN_0006462c` int→float, `FUN_000646e0` mul,
  `FUN_00064878` div).
* `FUN_000313d0` — same shape as `FUN_0003055c`.

## 1. `FUN_000309a4` — target cost (int, 382 C lines)

**Literals compared:** `"r"` (×2), `"content"` (×3).
**Byte offsets touched:** both params: `0x18,0x19,0x1a,0x1d,0x20,0x21,0x22,0x23,0x26,0x27,0x2c,0x30,
0x38,0x3c,0x3d,0x3e,0x40,0x44,0x48,0x49,0x4a,0x4c`; additionally on `param_2` (the context):
`0x54, 0x58` — these are the **context string pointers** (`*(char**)` compared with `+`/`-`/`r`).
**String-feature comparisons** use word slots: `param_1[1]`, `[2]`, `[4]`, `[5]`, `param_2[1..5]`
(feature strings, e.g. phone/word names), and `[0xc]`, `[0xe]`, `[0x10]`, `[0x13]` compared against
the literal `"content"`.

**Integer cost terms added (machine-extracted, exact):** `+1` (nine sites), `+2` (three),
`+3` (three), `+5`, `+10` (two), `+50`, `+75`, `+1000` (two).

**Structure read from the body (in order):**

```c
/* 1. string-feature mismatch schedule */
iVar21 = {0,3,7,10}  /* depends on which of param_1[1]-vs-[1], [2]-vs-[2] match           */
iVar7  = (param_1[4]==param_2[4]) ? 0 : 7
iVar8  = (param_1[5]==param_2[5]) ? 0 : 3
base   = iVar7 + iVar21 + iVar8
if (param_2[3] == "r")                      base *= 3
if (param_2[2] == "r" || param_2[4] == "r") base *= (param_2[0x15][0]=='+') ? 6 : 3
/* 2. numeric feature differences |a-b| with weights */
base += 3*|p1[0x19] - p2[0x19]| + 3*|p1[0x1a] - p2[0x1a]| + 3*|p1[6word] - p2[6word]|
if (p1[0x1d] != p2[0x1d]) base += 5
if (ctx[0]=='+' && p1[0x1d] != p2[0x1d]) base += 1000
base += 2*( |p1[0x21]-p2[0x21]| + |p1[8word]-p2[8word]| )
/* 3. tri-state byte features 1/2/0 at 0x22/0x23 and 0x3d/0x3e/0x49/0x4a → +1/+2/+3/+10 */
/* 4. byte equality penalties +1 each at 0x26, 0x27, 0xf-word, 0x11-word, 0x12-word */
/* 5. word-feature mismatch schedule: param_N[0xb] |diff| * 3;  param_N[10] mismatch → 3 */
/* 6. "content" role ladder:
        p1[0xe]=="content" != p2[0xe] → +50 ;  reversed → +75 ;  both != → +10
        p1[0xc]/p1[0x10] vs p2[0xc]/p2[0x10] "content" mismatches → +3 each */
/* 7. tail: string/feature comparisons over param_N[0x13] with literals "L*" / "L" and
        float terms built with the constants in §4 (150/250/300/360/1000 …) */
```

Sections 1–6 are read directly from the decompiled body (lines 8129-8380); section 7 continues to
line 8511 and mixes the same field set with float helpers — a porter should transcribe it against
the emulator (recipe in §5).

## 2. `FUN_0003055c` — node cost for `"r"` context (float, 198 C lines)

**No string literals, no integer additions** — a pure float accumulator.
**Byte offsets (identical on both params):** `0x11,0x13,0x15,0x17,0x19,0x1b,0x1d,0x1f` (odd bytes,
i.e. one byte per 2-byte field) and `0x20,0x24,0x28,0x2c,0x30,0x34,0x38,0x3c` (word-aligned fields).
**Float constants used** (decoded): `0.25, 0.5, 0.75, 1.5, 50.0, 1000.0, 9.6` (the last via
`0x4119999a`), plus `0x3f000000/0x3e800000/0x3f400000/0x3fc00000` (0.5/0.25/0.75/1.5) used as
weights and `0xffff`/`0x20000` as masking/shift helpers.
**Shape:** per feature pair, `d = |f_a − f_b|` (integer), then a piecewise weight
(`0.25 / 0.5 / 0.75 / 1.5 / 9.6 / 50` depending on the magnitude class), accumulated in float and
finally scaled (`× 1000.0`/`÷ 1000.0` conversions via `FUN_00064878`). This is the same
"piecewise magnitude → weight" pattern as `FUN_000320f0` (already partly transcribed by
RelievedCondor), so its transcription should follow that template with the field list above.

## 3. `FUN_000313d0` — node cost for `"-"` context (float, 204 C lines)

Same shape and the same field set as §2, with a slightly different weight ladder:
`0.05, 0.15, 0.2, 0.3, 0.35, 0.4, 0.6, 0.75, 0.8, 1.5, 50.0, 1000.0`,
plus integer constants `+360`, `+50`, `+90` and `0x55555555`/`0xffff` masks. No literals, no
integer cost additions through `iVar += const` (the +360/+50/+90 appear inside expressions).

## 4. Constants decoded (for all three functions)

| hex | float | hex | float |
|---|---|---|---|
| `0x3d4ccccd` | 0.05 | `0x41b40000` | 22.5 |
| `0x3e19999a` | 0.15 | `0x41c00000` | 24.0 |
| `0x3e4ccccd` | 0.20 | `0x42340000` | 45.0 |
| `0x3e800000` | 0.25 | `0x42480000` | 50.0 |
| `0x3e99999a` | 0.30 | `0x42f00000` | 120.0 |
| `0x3eb33333` | 0.35 | `0x42fc0000` | 126.0 |
| `0x3ecccccd` | 0.40 | `0x43160000` | 150.0 |
| `0x3f000000` | 0.50 | `0x437a0000` | 250.0 |
| `0x3f19999a` | 0.60 | `0x43960000` | 300.0 |
| `0x3f400000` | 0.75 | `0x43b40000` | 360.0 |
| `0x3f4ccccd` | 0.80 | `0x447a0000` | 1000.0 |
| `0x3fc00000` | 1.50 | `0x4119999a` | 9.60 |

## 4b. `FUN_000309a4` tail (dump lines 8380-8511) — transcribed

Entered when `*(byte*)(param_1+0x3e) == 1` (`bVar6`). With
`A = param_1[0x13]`, `B = param_2[0x13]` (string features), `v = *(char*)(param_2+0x16)`:

```c
iVar7 = (strcmp(A,B) == 0) ? 0 : 10;
if (strcmp("L*", B) == 0 && strcmp("L", A) == 0)      iVar7 = 0;
else if (strcmp("L", B) == 0 && strcmp("L*", A) == 0) iVar7 = 8;
iVar8 = (bVar6 == 1) ? 0 : 4;

if (*(byte*)(param_2+0x23) == 1) {                       /* right-side flag byte */
    (iVar14, iVar9) = (cVar26 == 1) ? (0, 0) : (1500, 100);
    if (cVar24 == '+' || v != '-')   cost += iVar7*250 + iVar14;
    else                             cost += iVar7*20  + iVar9;
} else if (cVar3 != 0) {                                 /* cVar3 = param_2[0x1d] */
    if (bVar6 < 2 && cVar3 == cVar4) (iVar13, iVar9, iVar14) = (0, 0, 0);
    else                             (iVar13, iVar9, iVar14) = (250, 150, 100);
    if (cVar24 == '+')        cost += iVar7*25 + iVar13;
    else if (v == '-')        cost += iVar7*10 + iVar14;
    else                      cost += iVar7*15 + iVar9;
}
if (bVar2 == 1)                                   /* param_2[0x19] == 1 */
    cost += (v == '-') ? iVar7*20 : iVar7*40;
cost += iVar8 + iVar7;
```

Then, outside that block (again with `bVar5 = param_1[0x3d]`, `bVar6 = param_1[0x3e]`,
`cVar24 = *(char*)param_2[0x15]`):

```c
if (((bVar6 == 1 || bVar5 == 1) && *(byte*)(param_2+0x23) > 1)
    && (*(byte*)(param_2+0x22) > 1 && strcmp(param_1[0x13], "H") == 0))
    cost += 1000;                                            /* hard "H" context penalty */
```

**Pause (`pau`) branch** — skipped entirely when `strcmp(param_1[3], "pau") == 0`; otherwise it adds
float penalties derived from the ratio of the records' first float field
(`uVar20 = *param_1`, `uVar19 = *param_2`):

```c
r = fabs( uVar20 / uVar19 )            /* FUN_00064498 = divide, FUN_0006449c = fabs,   */
                                       /* FUN_00064878 masks the sign (0x7fffffff)      */
if (FUN_00064aac(uVar20,uVar19) != 0) {          /* branch 1 */
    cost += (int)(r * 150.0);
    if (r > 0.15f) cost += (int)((r * 150.0) / 22.5);
    if (r > 0.35f) cost += (int)((r * 360.0) / 126.0);
} else if (FUN_00064a84(uVar20,uVar19) != 0) {   /* branch 2 */
    cost += (int)(r * 250.0);
    if (r > 0.2f) cost += (int)((r * 120.0) / 24.0);
    if (r > 0.3f) cost += (int)((r * 150.0) / 45.0);
    if (r > 0.4f) cost += (int)((r * 300.0) / 120.0);
}
```

**Return value** (the function's result, after all branches):

```c
return (float)cost * 0.4f;          /* FUN_0006462c int→float, FUN_000646e0 ×0.4f (0x3ecccccd) */
```

Verification helper semantics used above are `[INFERENCE]` from call-site behaviour, not from
symbol names: `FUN_00064498` = arithmetic op on two floats, `FUN_0006449c` = sign/abs op,
`FUN_00064878` = op + mask (used as `/1000` in `FUN_000320f0`), `FUN_00064aac`/`00064a84`/
`00064ac0` = float comparisons returning bool, `FUN_00064ad4` = fetch float result,
`FUN_0006462c` = int→float, `FUN_000646e0` = float multiply, `FUN_00064b30` = float return.
Confirm each with a one-shot emulator call when you validate (they are used identically in
`FUN_000320f0`, so one confirmation covers all five cost functions).

## 4c. Feature-vector slot map (what the cost functions are actually reading)

Correction that matters for all five cost functions: their two record arguments are **not** the
36-byte voice records — they are the engine's **96-byte feature vectors** (`FUN_00030214` copies
`0x60` bytes per side into the graph node: `memcpy(piVar5+1, param_2, 0x60)` /
`memcpy(piVar5+0x19, param_2+0x60, 0x60)`), produced by `FUN_00060ed4` (engine dump line 43702).
The offsets listed in §2/§3 are therefore byte offsets **into that vector**. Its writer names every
slot, which fixes the semantics of every cost term:

| slot | feature (as written by `FUN_00060ed4`) | | slot | feature |
|---|---|---|---|---|
| `0x00` | float: `FUN_00059004(R:Unit,p.end) − p.end` | | `0x24` | `ssyl_in` |
| `0x04` | `p.p.name` | | `0x25` | `ssyl_out` |
| `0x08` | `p.name` | | `0x26` | `ssyl_from` |
| `0x0c` | string slot (literal name at `DAT_00155d00`) | | `0x27` | `ssyl_to` |
| `0x10` | `n.name` | | `0x28` | `syl_vowel` |
| `0x14` | `n.n.name` | | `0x2c` | `n.stress` |
| `0x18` | `pos_in_syl + 1` | | `0x2d` | `n.glottal_stop_pos` |
| `0x19` | `(1 − (pos_in_syl+1)) + syl_num_phones` | | `0x2e` | `n.syl_num_phones` |
| `0x1a` | `p.stress` | | `0x30` | `p.gpos` |
| `0x1b` | `p.glottal_stop_pos` | | `0x34` | `p.word_num_syls` |
| `0x1c` | `p.syl_num_phones` | | `0x38` | string slot (literal at `DAT_00158d10`) |
| `0x1d` | `stress` | | `0x3c` | `word_num_syls` |
| `0x1e` | `glottal_stop_pos` | | `0x3d` | syl count in phrase (`FUN_00059334`/`58e4c` loop) |
| `0x1f` | `syl_num_phones` | | `0x3e` | syl count in phrase, 2nd relation (`58e40` loop) |
| `0x20` | `pos_in_word + 1` | | `0x40` | `n.gpos` |
| `0x21` | `(1 − (pos_in_word+1)) + word_num_syls` | | `0x44` | `n.word_num_syls` |
| `0x22` | `syl_in + 1` | | `0x45` | `p.phrase_num_syls` |
| `0x23` | `syl_out + 1` | | `0x46` | `p.phrase_num_words` |
| | | | `0x47` | `phrase_num_syls` |
| | | | `0x48` | `phrase_num_words` |
| | | | `0x49` | `pos_in_utt + 1` |
| | | | `0x4a` | `(1 − (pos_in_utt+1)) + num_phrases` |
| | | | `0x4c` | `daughtern.R:SylStructure.daughtern.endtone` |
| | | | `0x50` | `n.phrase_num_syls` |
| | | | `0x51` | `n.phrase_num_words` |
| | | | `0x54` | `ph_vc` |
| | | | `0x58` | `ph_cvox` |
| | | | `0x5c` | `ph_ctype` |

Two writer branches exist in `FUN_00060ed4`: the **"pau" (pause) item** branch fills only the
`p.*`/`n.*` syllable/word/phrase slots (`0x1a/0x1b/0x1c`, `0x2c/0x2d/0x2e`, `0x30`, `0x34`, `0x40`,
`0x44`, `0x45/0x46`, `0x50/0x51`), while the **normal item** branch fills the full grid above
(including the `pos_in_*`/`syl_in|out`/`ssyl_*` derivatives). The three string-valued slots
(`0x0c`, `0x38`, `0x4c`) plus `p.p.name`/`p.name`/`n.name`/`n.n.name` are what `FUN_000309a4`
compares with `strcmp` and what the `"content"`/`"L*"`/`"L"`/`"H"` literals test against.

Feature names are Festival/Flite-style (`R:SylStructure`, `R:Word`, `R:Phrase`, `gpos`,
`ssyl_from`, `pos_in_utt`, `ph_vc`…), which is also why the stage tables are named
`tokenizer/text_analysis/pos_tagger/phrasing/lettertosound/pause_insertion/postlex/intonation/duration`.

## 4d. The slot *values* the engine puts in `0x26`-`0x27`, `0x28` and `0x30`-`0x40` (recovered)

§4c names the slots; these three groups were the ones whose *values* were still approximations.
All three are now recovered and validated; the reference implementation
(`refimpl/engine_prosody.py`) no longer approximates any of them.

**(a) `0x26 ssyl_from` / `0x27 ssyl_to` — distance to the nearest stressed syllable.**
The names are registered as plug-in feature getters by `FUN_00044460` (plug-in `:18862-18863`):

```c
FUN_0003d9b0(param_1, "ssyl_from", &DAT_00044b74);   /* ELF 0x34b74 */
FUN_0003d9b0(param_1, "ssyl_to",   &DAT_00044afc);   /* ELF 0x34afc */
```

They are *not* stressed-syllable counts (`0x24`/`0x25` are).  Both are the same loop over the
**Syllable** sibling chain, differing only in the link slot:

* `ssyl_to` (ELF `0x34afc`): `FUN_00029108(item, "Syllable")` (ELF `0x19108`, the item resolved in
  the *Syllable* relation) then `*(x+8)`, stepping with `FUN_00028c14` (= `*(x+8)`, ELF `0x18c14`),
* `ssyl_from` (ELF `0x34b74`): the same lookup, then `*(x+0xc)`, stepping with `FUN_00028c20`
  (= `*(x+0xc)`, ELF `0x18c20`),

counting `1, 2, …` and returning the count as soon as a sibling's `stress` feature is `> 0`
(`FUN_00028df0(item, "stress")` with the string built at `pc + 0x2db0c` / `pc + 0x2db84` =
plug-in ELF `0x626ac` = `"stress"`).  If the chain runs out first the getter returns the static
string VAL at ELF `0x2efb8c` / `0x2efba4` (`{tag 5, refcount -1, payload 0x1f1f5c}`), whose payload
is the one-character string `"0"` (`0x1f1f5c`), so the engine's integer coercion yields **0**.

So, in words: `ssyl_from`/`ssyl_to` are the number of syllables from the previous/next syllable to
the nearest *stressed* syllable, 0 when there is none that way.  Both cross word **and** phrase
boundaries (verified: in `ref_lexclean` the syllable `this` has `ssyl_from = 2`, which walks into
the preceding word `comma`).

Validated **byte-exact for all 28 syllables of `ref_nopunct` / `ref_lexclean` / `ref_default`**
(`scripts/validate_ssyl.py`) and, at the cost level, by the fact that the interior-node target
costs become 100 % exact without supplying any engine value (`scripts/compare_costs.py`).

**(b) `0x30 p.gpos` / `0x38 gpos` / `0x40 n.gpos` — a closed-class dictionary, not a tagger.**
The engine's `pos_tagger_func` default is NULL and the Kendra plug-in never registers one (its
stage registrations, plug-in dump `:9453-9496`, cover only
`duration/diphone_graph/syl_boundaries/xsampa_to_xivona/wordtosegments/postlex/sentence_boundary/
tokentowords/phrasesylendtone`; the feature registry in `FUN_00044460` registers no `gpos` getter
either), yet every word item carries a `gpos` string.  The values come from a table in the
plug-in's own `.rodata`:

| address (ELF) | what |
|---|---|
| `0x2ebb04`, stride 8, terminator `meta == 0` | array of string VALs `{u32 meta = 0xffff0005, u32 char* string}` |
| `0x2eb860`, stride 4, runs separated by `0x00000000` | pointers to those VALs' `meta` word, **one run per tag**; the first element of a run is the tag string itself |

The nine tags and their words (159 table entries: 9 tag strings plus 150 word entries, `in` and
`to` occurring both as a tag and as the group's first word) are listed in `scripts/gpos_table.py`:
`in` (38 entries), `to` (2), `det` (19), `md` (25), `cc` (9), `wp` (14), `pps` (30), `pps$` (9),
`aux` (13); **everything else is `content`** (the plug-in also holds
`content` as a plain `.rodata` string at `0x60be0`).  The same tag strings are the ones the
plug-in's own rules test (`FUN_00032b70` tests `wp`/`cc` on `daughter.gpos`; `_FINI_1` tests
`in`/`md`/`on`/`into`/`with`/`up`/`down` when choosing a heteronym's lexicon entry;
`FUN_000309a4` tests `content`), which is what pins the table to the feature.

Observed values match the table in every capture (`this`→`det`, `is`→`aux`, `a`→`det`,
`hello`/`world`/`test`/`comma`/`dot`→`content`) — `scripts/validate_gpos.py` reports **73/73
segments** over `ref_nopunct` (20/20), `ref_lexclean` (26/26) and `ref_default` (27/27).
Lookups are **case-folded**: in the dedicated capture `out/oracle/gpos_case/`
(`"That can go to the market"`, `emu/tts_run.py --ret-probe --max-chunks 2`) the capitalised
`That` carries `gpos = in` (the tag of `that`), and `can`/`to`/`the` carry `md`/`to`/`det` while
`go`/`market` carry `content` — exactly the table's prediction.  The old claim that the tagging is
context-dependent is **not** supported: the same word gets the same tag in every capture, and the
table has exactly one entry per word.  (The tagger *stage* never runs at all: `pos_tagger_func`
defaults to NULL in the engine's stage table and the Kendra plug-in does not register one — the
dictionary is applied by the front end while the word items are built, which is why the plug-in,
not the engine, holds the table.  `[INFERENCE]` for *which* plug-in function consumes it; the
table's addresses are referenced from the parallel index array at ELF 0x2eb860 and the result is
behaviourally exact.)

**(c) `0x28 syl_vowel` and `0x38 gpos` of the `pau` items.**
`FUN_00060ed4`'s `pau` branch writes neither `0x28` nor `0x38`, but the engine's *actual* context
vector for the sentence-initial/`final pau` item holds the nil string `"0"` in both
(`ref_nopunct/unit_feature_vectors.tsv`: slots `0x28` and `0x38` are the engine's nil string at
ELF `0x148430` of `libttsivonavoice.so`, `"0"`).  This is the whole of the previously unexplained
"constant 5–6 points" at the first/last Viterbi node: with the two slots left empty every
first/last-node candidate target cost is 5–6 low; with them set to `"0"` every candidate of both
edge nodes matches **exactly** (recomputing the engine's dumped costs with the two slots patched
gives delta 0 for all 174 candidates of node 0 and all 268 of node 18; `scripts/compare_costs.py`
`--oracle-dir out/oracle/ref_nopunct` then reports 6146/6146 — see `report_pipeline.md` §10.2).
It is a per-node constant and
can therefore never reorder a node's candidates — but it *does* shift that node's join budgets, so
it is now modelled explicitly in `ProsodyModel.context_vectors` (for **every** `pau`-branch item;
`[INFERENCE]` for *interior* pauses, since no capture contains one — the value is a property of
the `pau` branch, not of the utterance edges, so the generalisation is the natural one).

## 5. Validation recipe (how to prove a transcription)

The plug-in's functions can be called directly under the emulator — `scripts/probe_g2p.py` already
calls plug-in code (`FUN_0003f594` LTS) this way, including building its structs in scratch memory:

```sh
~/venvs/re/bin/python emu/run.py --lib out/libs/kendra/libvoice_en_us_kendra.so \
    --func FUN_000309a4 --arg <rec_ptr> --arg <ctx_ptr> --trace
```

Vectors: take two real 36-byte records from the OBB (`refimpl/cdxv.py` → `pair4`) and a context
block; run both the engine function and the Python port and require **bit-identical** integer
results (`FUN_000309a4`, dispatcher) or float results (`FUN_0003055c`, `FUN_000313d0`). Cover at
least: identical records (cost 0), one-field outliers in each magnitude class, and both
`"r"`/`"+"`/`"content"` contexts.

## 6. Open items (for the porter)

1. ~~`FUN_000309a4` tail~~ — **done, see §4b** (still worth one emulator cross-check of the float
   helper semantics listed there).
2. The odd-byte accesses in `FUN_0003055c`/`FUN_000313d0` (`0x11,0x13,…`) most likely read the
   **high byte of 2-byte feature fields** — confirm by dumping the actual record bytes used by the
   plug-in (the records are 36-byte-class; see `report_libvoice.md` §2 for the record layout and
   `report_codec_spec.md` for how they are stored).
3. ~~Feature-name ↔ offset mapping~~ — **done, see §4c** (engine `FUN_00060ed4`; the cost functions
   read the engine's 96-byte feature vector, not the 36-byte voice records).
