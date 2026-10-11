# `refimpl/tts.py` — end-to-end text → speech on the shipped IVONA 2 voice data

Scope: a **functional** demonstration that the text → speech path is reimplementable from the
shipped artifacts (`IVONA 2/**/main.199.*.obb` + `out/libs/**`). Bit-exactness is *not* the goal:
the acoustic stage is proven bit-exact for the units the pipeline chooses (§6.3), while unit
selection, prosody and text normalisation are deliberate simplifications (§7).

Everything below was produced read-only from the originals; new files are `refimpl/tts.py`,
`scripts/analyze_tts.py`, `out/tts_demo/*` and this report.

---

## 1. Entry point

```sh
~/venvs/re/bin/python refimpl/tts.py --text "The quick brown fox jumps over the lazy dog." \
    --voice kendra --out out/tts_demo/quick_brown_fox.wav
```

| flag | meaning |
|---|---|
| `--text TEXT` | utterance to synthesise |
| `--voice kendra\|amy` | which OBB (acoustic data) to use |
| `--out FILE.wav` | output (default `out/tts_demo/tts.wav`) |
| `--rate HZ` | output WAV sample rate, default **22050** (the rate the container declares) |
| `--codec-rate HZ` | codec synthesis rate, default **24000** (engine-exact, §4.4) |
| `--select context\|first` | unit-selection heuristic (§3), default `context` |
| `--align` | print the unit alignment table |
| `--json PATH` | write the machine-readable alignment/selection trace |
| `--verify-engine` | re-splice the chosen units through the real `.so` and diff |
| `--phones TEXT` | print the phoneme sequence + diphone candidate counts, then exit |
| `--check-tables` | validate the diphone name/index/record chain (§6.5), then exit |
| `--check-g2p WORDS` | front-end regression against `scripts/lex_decode.py`/`lts_decode.py` |

---

## 2. Architecture

```
text
 └─ clauses_of()                    lowercase, digit spell-out, clause split, word regex
     └─ G2P.word()                  scripts/lex_decode.py (packed lexicon) else scripts/lts_decode.py (LTS FSM)
         └─ phone_sequence()        words chained; stress digits stripped; "pau" at clause edges
             └─ diphone_pairs()     snprintf("%s-%s", left, right)  == the engine's key
                 └─ UnitSelector     section A (pair2, 1601 × 20 B) -> (start,count)
                                     section B (pair3, 418 495 × 4 B) -> candidate unit ids
                                     section C (pair4, 426 991 × 36 B) -> features for the heuristic
                     └─ du.Codec      emulated format-14 codec (scripts/decode_unit.py, Unicorn)
                         └─ su.segment_pcm   ramp[]  = cumulative segment marks (report_segmentation §1)
                             └─ su.splice    FUN_00061620 rule-set: crossfade L = min(prev tail, len(block0)),
                                             earlier samples of block 0 dropped, last segment held as `tail`
                                 └─ su.finalize  FUN_000618a8 with an empty event list
                                     └─ resample (stand-in for FUN_00059958) -> WAV
```

Stage → evidence:

| stage | code | ground truth |
|---|---|---|
| text → words | `refimpl/tts.py:clauses_of` | `report_frontend.md` (full SSML/ISEF pipeline **not** applied, §7) |
| words → phonemes | `G2P` | `scripts/lex_decode.py`, `scripts/lts_decode.py`, verified against the engine by `scripts/probe_g2p.py` |
| phonemes → diphone key | `diphone_pairs` | `report_engine_synth.md` §1.5 step 3 (`"%s-%s"` + binary search in the 20-byte table) |
| diphone → candidate units | `UnitSelector` | `report_obb_format.md` §4/§5 (A slices B; B is a permutation of the non-null index entries) |
| candidate → one unit | `UnitSelector.select` | §3 below |
| unit → PCM | `decode_unit.Codec.decode_window` | bit-exact vs `FUN_00067a14` (`decode_unit.py --verify`) |
| PCM → stream | `segment_unit.splice/finalize` | `segment_unit.py --verify-splice/--verify-finalize` (0 diffs) |
| 24 k → 22.05 k | `resample` | **stand-in**; `FUN_00059958` untraced (§7) |

---

## 3. Unit selection heuristic

Section C (`pair4`) is positional over the index and holds the per-instance features documented in
`report_obb_format.md` §6: `u16 dur_ms` at 0–1, the 5-phone context window at 2–6
(`left-2, left-1, L, R, R+1` as section-E phone ids), the D-run nibbles at 7, feature u16s at
8/10/12/14 and the section-D root at 32–35.

The engine runs a Viterbi search whose cost callback consumes exactly those fields
(`report_engine_synth.md` §1.5; the five voice-side cost functions are `FUN_000320f0` /
`FUN_0003055c` / `FUN_00031868` / `FUN_00031cb0` / `FUN_000313d0`, selected by
`FUN_00030214`). That model is being recovered by a sibling task, so this pipeline uses a
documented stand-in:

```
candidates = B[start : start+count]                 # section-A slice, ascending unit id
identity   = C(u)[4:6] == (id(phones[i]), id(phones[i+1]))      # must hold: 418 495/418 495 (K), 396 683/396 683 (A)
score(u)   = |{i : C(u)[ctx_i] == target_i}|        # ctx = bytes 2,3,6; target = phone ids of
                                                    # phones[i-2], phones[i-1], phones[i+2]
                                                    # (id("0") for out-of-range)
pick argmin(not identity, -score, unit id)          # identity first, then context, then lowest id
```

`--select first` ignores the context score and always takes the lowest id among identity-matching
candidates (the plain "first candidate per diphone" rule). Both modes are deterministic.

Two structural assertions are enforced and reported:

* `C(u)[4:6]` — the record's own diphone phone ids — must equal the ids of the `"L-R"` name whose
  slice contains `u`; it is the primary sort key, so a candidate failing it is only ever chosen if
  *no* candidate matches. Verified for **418 495/418 495** instances of Kendra and
  **396 683/396 683** of Amy (`--check-tables`, §6.5), which also validates the whole
  A→B→index→C chain.
* the chosen unit's `dur_ms` and its section-C features are printed in the alignment table, so the
  selection is auditable against a future cost-function port.

---

## 4. Boundary cases mirrored from `report_segmentation.md` §3

1. **Held-back last segment.** A unit's last `ramp[]` block is never committed by `splice` while
   more units follow: it is written at `pos` and kept as `tail` (`flag != 0`), so the *next* unit's
   block 0 is crossfaded into it.
2. **Crossfade drop.** `L = min(prev tail, len(block 0))`, and the crossfade consumes the **last L
   samples of block 0** — block 0's earlier samples are dropped (`su.crossfade`). 17-point raised
   cosine window, float32 arithmetic with truncate-toward-zero, tables bit-exact from the `.so`.
3. **Final unit (`flag = 0`).** The last unit of the utterance is appended with `flag = 0`, so its
   final block is *not* written at all and `tail` returns to 0 — exactly the engine's rule; the
   committed stream therefore ends one sub-segment before the last unit's `ramp[N-1]`.
4. **Finalisation.** `finalize(streamer, want=0)` (empty event list) returns the committed
   `pos` samples; the uncommitted tail is not included.
5. **Rate chain.** Decoding is rate-parameterised; the engine always decodes at 24 000 Hz
   (format-14 init remaps the `0x5622` header sentinel to 24000 — `report_emulation.md`
   "Sample-rate nuance"), while the container declares 22 050. The pipeline decodes at
   `--codec-rate 24000` and resamples to `--rate 22050`; `--rate 24000` keeps the raw stream.

---

## 5. Exact commands

```sh
cd /home/asdf/Downloads/ivona_re
P=~/venvs/re/bin/python

# a) front-end regression (compare with scripts/lex_decode.py / scripts/lts_decode.py)
$P refimpl/tts.py --check-g2p "hello kendra world the quick brown fox jumps over lazy dog this is a test speech synthesis system rain spain stays mainly plain she sells sea shells by shore artificial intelligence transforming telephone coffee please"
$P refimpl/tts.py --phones "hello world"
$P scripts/lex_decode.py hello kendra fox over lazy dog
$P scripts/lts_decode.py world the quick brown jumps

# b) diphone name/index/record chain integrity
$P refimpl/tts.py --check-tables

# c) synthesis (Kendra), with alignment + engine diff
$P refimpl/tts.py --text "hello world" --out out/tts_demo/hello_world.wav \
    --json out/tts_demo/hello_world.json --align --verify-engine
$P refimpl/tts.py --text "Kendra speaks clearly." --out out/tts_demo/kendra_speaks.wav \
    --json out/tts_demo/kendra_speaks.json --align
$P refimpl/tts.py --text "The quick brown fox jumps over the lazy dog." \
    --out out/tts_demo/quick_brown_fox.wav --json out/tts_demo/quick_brown_fox.json --align
$P refimpl/tts.py --text "Hello world" --voice amy --out out/tts_demo/amy_hello_world.wav \
    --json out/tts_demo/amy_hello_world.json

# plain "first candidate per diphone", and the raw 24 kHz codec-rate stream
$P refimpl/tts.py --text "hello" --select first --out out/tts_demo/hello_first.wav --rate 24000
$P refimpl/tts.py --text "hello" --select first --out out/tts_demo/hello_first_22k.wav

# d) objective audio analysis (+ spectrogram PNG via ffmpeg)
$P scripts/analyze_tts.py out/tts_demo/quick_brown_fox.wav --json out/tts_demo/quick_brown_fox.json
```

---

## 6. Verification

### 6.1 Phone sequence vs the reference front-end (criterion a)

`--check-g2p` on 35 words: **35/35 match** `scripts/lex_decode.py` (lexicon hits) or
`scripts/lts_decode.py` (LTS fallback) after the documented stress-digit strip
(`ow1 → ow`, `eh1 → eh`) — the section-A diphone names carry base phones only.
The chained utterance sequence for the acceptance sentence is

```
pau dh k w ih k b r aw n f aa k s jh ah m p s ow v er dh l ey z iy d aa g pau
```

with **30/30 diphone pairs present in section A**. Across the 9 test sentences used during
development, the word-chained sequences produced 215 transitions with **0 absent** from the name
table — the table is the set of *attested* English transitions, so raw word chaining needs no
patching. Full log: `out/tts_demo/g2p_check.txt`.

*(Stress digits are dropped only for the diphone key; the lexicon/LTS output itself is unchanged —
`hello → hh ax l ow1`, `kendra → k eh1 n d r ax`, matching `report_frontend.md` §4.2.)*

### 6.2 Stream length and duration (criterion b)

`--align` prints, and `stream_len_model()` independently recomputes, the committed sample count for
the rule-set of §4. Every run below satisfies `committed == model` exactly:

| utterance | units | Σ decoded samples | drop (crossfade + held last segment + final block) | committed `pos` | model | WAV samples @ 22050 | duration | engine diff |
|---|---|---|---|---|---|---|---|---|
| `hello world` (Kendra) | 9 | 28 547 | 1 445 | 27 102 | 27 102 ✓ | 24 900 | 1.1293 s | **0 → BIT-EXACT** |
| `Kendra speaks clearly.` | 18 | 40 303 | 2 865 | 37 438 | 37 438 ✓ | 34 397 | 1.5599 s | — |
| `The quick brown fox jumps over the lazy dog.` | 30 | 73 533 | 4 690 | 68 843 | 68 843 ✓ | 63 250 | 2.8685 s | **0 → BIT-EXACT** |
| `Hello world` (Amy) | 9 | 30 534 | 1 280 | 29 254 | 29 254 ✓ | 26 878 | 1.2189 s | — |
| `hello` `--select first --rate 24000` | 5 | 22 070 | 880 | 21 190 | 21 190 ✓ | 21 190 | 0.8829 s | — |

The duration is `pos / 24000` (codec domain) = `WAV samples / 22050` up to the resampler's one-sample
tail, and the last row shows the raw path emits exactly `pos` samples. The overlap is *dropped*, not
stretched, so "duration = Σ used unit samples − crossfades − the final unit's held block" holds
exactly. In `--align` terms, `out_ms` < the record's own `dur_ms` for every unit
(Σ`out_ms`/Σ`dur_ms` = 0.947 / 0.933 / 0.922 / 0.828 for the four demos), which is the same
block-0 head drop and held tail the engine applies.

### 6.3 Acoustic stage is bit-exact with the engine

`--verify-engine` re-splices the *same* unit chain through the real `libttsivonavoice.so`
(`segment_unit.Engine`, unit decode `FUN_0005ef70`, splice `FUN_00061620`, finalize `FUN_000618a8`)
and diffs it sample-by-sample against the pipeline's 24 kHz stream:

```
$P refimpl/tts.py --text "hello world" --out out/tts_demo/hello_world.wav --verify-engine
[engine] same chain via libttsivonavoice.so: 27102 samples (ours 27102), sample diffs = 0 -> BIT-EXACT

$P refimpl/tts.py --text "The quick brown fox jumps over the lazy dog." \
    --out out/tts_demo/quick_brown_fox.wav --verify-engine
[engine] same chain via libttsivonavoice.so: 68843 samples (ours 68843), sample diffs = 0 -> BIT-EXACT
```

This is only true with `--codec-rate 24000`: `du.Codec(rate=22050)` differs from the engine for
nearly every segment (checked on records 0 / 3 / 420580: 32 / 33 / 26 differing segments, all
otherwise identical in length), which is how the 24 kHz codec rate was established independently of
the documentation. Corroborating evidence: the per-unit `dur_ms` metadata agrees with the sample
counts only at 24 kHz (median `ramp[-1]/dur_ms` = 24.14 ≈ 24 + ms-quantisation bias; 22.05 is
excluded because the metadata rounds *up*, never down).

### 6.4 Objective audio evidence (criterion c)

`scripts/analyze_tts.py OUT.wav --json OUT.json` writes the full per-demo report to
`out/tts_demo/*_analysis.txt` and a spectrogram PNG (ffmpeg `showspectrumpic`; the venv has no
matplotlib/scipy) to `out/tts_demo/*_spec.png`.

| demo | samples / duration | peak | RMS | 10 ms envelope | silence | F0 (autocorr., voiced) |
|---|---|---|---|---|---|---|
| `hello_world.wav` | 24 900 / 1.1293 s | −8.3 dBFS | 2 009 | 113 frames, max 4 318 | 35 silent, longest run 180 ms | 73 frames, 102.6 / **148.0** / 220.5 Hz |
| `kendra_speaks.wav` | 34 397 / 1.5599 s | −9.2 dBFS | 1 789 | 156 frames, max 5 005 | 35 silent, longest run 160 ms | 85 frames, 62.5 / **145.1** / 344.5 Hz |
| `quick_brown_fox.wav` | 63 250 / 2.8685 s | −7.2 dBFS | 2 116 | 287 frames, max 4 775 | 60 silent, longest run 160 ms | 173 frames, 80.8 / **162.1** / 400.9 Hz |
| `amy_hello_world.wav` | 26 878 / 1.2190 s | −6.0 dBFS | 3 106 | 122 frames, max 7 222 | 50 silent, longest run 259 ms | 68 frames, 108.1 / **162.1** / 393.8 Hz |

The numbers are consistent with connected speech: 31 % of the "hello world" frames are silence
(one leading and one trailing `pau` unit plus the pauses inside `X-pau` diphones), the voiced span
sits between them (0.17–0.97 s), median F0 ≈ 148 Hz (Kendra) / 162 Hz (Amy) — a female range — and
ZCR rises with the fricative content (1 394 /s for `hello world`, 3 257 /s for the fricative-heavy
pangram).

**Phone-level alignment** (`quick_brown_fox`, full table in
`out/tts_demo/quick_brown_fox_analysis.txt`) maps every phone pair to the recorded unit that
realises it, with start/end times, the record's own `dur_ms`, the number of `ramp[]` segments and
the context-match score, e.g.

```
#   diphone  unit     start     end     out_ms  db_ms  segs  ctx
0   pau-dh   42       0.0000    0.1598   159.8   252    27    2
1   dh-k     39079    0.1598    0.2443    84.6    70    15    0
...
14  jh-ah    14465    1.2590    1.3413    82.3    90    14    1
15  ah-m     14466    1.3413    1.3978    56.5    80    10    2
...
29  g-pau    95689    2.6903    2.8685   178.2    90    30    3
```

**Listening note.** This environment has no audio output and no listening capability, so I could
not audition the WAVs — no subjective judgement is claimed here. The intelligibility argument is
structural and stated as such: every unit in the output *is* the recording of exactly the diphone
being rendered (asserted on the record's own phone ids — §6.5 — and re-verified for each selected
unit), the phone order follows the engine-verified G2P, unit durations are the recorded ones, and
the joins use the engine's own crossfade. That is the standard diphone-concatenation case, which is
intelligible by construction **[INFERENCE]**; what a listener will notice is the *flat prosody*
(§7.2) and occasional spectral seams where consecutive units do not come from the same recording
(measured successor-of-previous counts: 4/8 for `hello world`, 4/17 for `Kendra speaks clearly.`,
5/29 for the pangram, 2/8 for Amy; mean context match 2.22 / 2.39 / 1.87 / 2.00 out of 3).
A human check of `out/tts_demo/quick_brown_fox.wav` against the text is the remaining subjective
step.

### 6.5 Diphone name/index/record chain (criterion a, structural)

```sh
$P refimpl/tts.py --check-tables
[tables] section C bytes 4,5 == (L,R) phone ids for 418495/418495 diphone instances (0 bad)
[tables] diphones 1601, B entries 418495, phonemes 58

$P refimpl/tts.py --check-tables --voice amy
[tables] section C bytes 4,5 == (L,R) phone ids for 396683/396683 diphone instances (0 bad)
[tables] diphones 1772, B entries 396683, phonemes 62
```

---

## 7. Known deviations from the engine

1. **Unit selection** — no Viterbi, no target/join cost; the context-match heuristic of §3. The
   engine's five piecewise-linear cost functions over the section-C fields are *not* used.
2. **Prosody absent** — no `pitch_stretch` / `dur_stretch` / `compress` / `gain`
   (`report_engine_synth.md` §1.7), no 96-byte segment features, no intonation model. Units play at
   their recorded duration and pitch: monotone, no phrase-final lengthening or accent.
   *Consequence*: intelligible words, flat/flat-ish prosody, and a hard seam wherever the selected
   unit for the next diphone does not continue the previous recording. The heuristic has **no
   join/continuity cost**, so consecutive units come from the same recorded token only by
   coincidence of the lowest-id tie-break (measured 4/8, 4/17, 5/29, 2/8 in the demos) — the
   engine's Viterbi does model this.
3. **Text normalisation** — no SSML, no ISEF rewrite rules (`report_isef.md`), no number/abbreviation
   expansion beyond single digits. **Punctuation is spoken by name** (`scripts/symbol_names.py`, the
   plug-in's printable-ASCII table; §11.2) — `,` → `comma`, `.` → `dot`, matching the engine. A
   sentence-final symbol still closes a clause; `, ; :` are only spoken, never paused.
4. **Front end for Amy** — `--voice amy` uses Amy's OBB/units but the en-US plug-in's lexicon + LTS,
   because `libvoice_en_gb_amy.so` was measured to embed the *same* 75-entry phoneme table and the
   *same* lexicon pronunciations as the en-US plug-in (identical for `colour`, `tomato`, `vase`,
   `advertisement`, `hello`, `kendra`). Her diphone symbol set (48) is a superset of the 44 en-US
   symbols used here, so the sequence is valid; en-GB-only symbols (`eax`, `iax`, `o`, `uax`) are
   never produced. (Amy's own LexInfo was partially located — `LEX_PHONES` 0x2e5104,
   `LEX_SYLL` 0x2e5234, `LEX_POOL` 0x2e5638, blob at 0x62798 — but it yields the same
   pronunciations, so no separate front end is needed for a functional demo.)
5. **Missing diphones** — 335 of the 1936 possible pairs are absent from section A (e.g. `eh-pau`,
   `pau-ng`). A pair that is absent is skipped and reported (`missing`); for the test sentences none
   were needed. Utterance-edge `pau` is inserted only when both boundary diphones exist.
6. **Rate chain** — the decoder now produces the engine's own samples with the **clean-room,
   stdlib-only** codec (`scripts/codec_spec.py`); the 24 k→22.05 k conversion uses the codec's own
   output-rate converter (`scripts/codec_parts/resample.py`, the engine's `FUN_0014b4a8`/
   `FUN_0014c494`), replacing the former Hamming-sinc stand-in (§11.1).
7. **No marks/events** — the alignment is reconstructed from the splice trace, not from the
   engine's mark timeline (`FUN_00061c1c`) or its 20-byte mark records.

---

## 8. Shortest path to the clean-room decoder

`scripts/decode_unit.py` is the only emulated component left (Unicorn). Replacing it:

1. `scripts/codec_probe.py` + `out/codec/steps/rec*.pkl` already expose per-stage golden vectors and
   `report_codec_spec.md` maps the six stages (`parse` → `dequant` → `setup` → `gain` → `xform` →
   `post`); `scripts/codec_parts/setup.py` is ported bit-exactly (60/60 vectors).
2. Port the remaining stages in that order, each validated against its snapshot, then accept with
   `decode_unit.py --verify` (engine path vs driver) and `--rate 22050` for both voices.
3. Drop-in: `Codec.decode_window(cksum, window, Y, samples)` has a single call site in
   `refimpl/tts.py:synth`, so a clean-room decoder only has to implement that signature; everything
   downstream (ramp slicing, splice, finalize, resample) is already pure Python.
4. Second-largest gap after that is the selection/prosody model (§7.1–7.2), which is a sibling
   task; when its cost functions land, swap `UnitSelector.select` — the rest of the pipeline,
   including the engine-exact splice, is unaffected.

---

## 9. Files

| file | role |
|---|---|
| `refimpl/tts.py` | the pipeline (new) |
| `scripts/symbol_names.py` | plug-in printable-ASCII symbol→name table (punctuation spoken by name; §11.2) |
| `scripts/verify_codec_swap.py` | byte-diff of the clean-room vs emulated decoder, both rates (§11.1) |
| `scripts/analyze_tts.py` | objective WAV analysis + spectrogram (new) |
| `out/tts_demo/*.wav` | demo outputs (new) |
| `out/tts_demo/*.json` | alignment/selection traces (new) |
| `out/tts_demo/*.log`, `*_analysis.txt` | reproducible run + analysis output (new) |
| `out/tts_demo/*_spec.png` | spectrograms (new) |

Originals under `IVONA 2/`, `out/libs/`, `emu/` and the pre-existing `scripts/`/`refimpl/`/reports
were opened read-only; nothing outside the paths above was modified.

---

## 10. Matching the engine utterance

`--select viterbi` (now the default) replaces the heuristic with the engine's own
prosody model: the `zdur_cart` duration CART, the `FUN_00060ed4` context vectors,
the target cost `FUN_00031234`→`FUN_000309a4`, the five context-specific join
costs and a beam-pruned Viterbi over the section-A/B candidate lattices. New
modules: `scripts/phoneset.py` (the plug-in's static 44-phone feature table),
`scripts/diphone_vec.py` (the `FUN_0005f1dc` record→96-byte decode),
`refimpl/engine_prosody.py` (item graph, CART durations, context vectors, search).

### 10.1 Voice parameters in force (from `out/oracle/*/settings.txt`)

| parameter | value | consequence |
|---|---|---|
| `viterbi_beam` | **25** | the beam is 25, not the 50 fallback — this **supersedes** `report_prosody.md` §1.7/§6's "50 / 25 fallback" reading and §1.7's `tb_min_distance` inference |
| `tb_min_distance` | **6** | the forced-keep spacing rule in `FUN_00030214` **is active** (an earlier note inferred it was unset for Kendra) |
| `pause_base_len` | **0** (engine default would be 0.35) | a sentence-final `pau` is `0+0.05 = 0.05 s`, not 0.40 s |
| `duration_stretch`, `pitch_stretch`, `amplify`, `compress` | 1 | no time/pitch/gain transforms: the acoustic length stays the recorded unit's |

### 10.2 Layer-by-layer agreement (all numbers reproducible with the commands in §10.5)

| layer | reference | result |
|---|---|---|
| `FUN_0005f1dc` (36-B record → 96-B vector) | engine under Unicorn (`scripts/probe_record_vec.py`) | **3000/3000 records byte-identical** (numeric slots) + all 10 string slots resolve to the same names; cross-checked against the engine's own `candidate_records.tsv` |
| phone classes (`ph_vc/cvox/ctype`) | plug-in `.so` static phoneset | 44/44 phones decoded; `vc/cvox/ctype/cplace/vlng/vheight/vfront/vrnd` |
| durations (`FUN_00048110` + `FUN_00048400`) | `unit_feature_vectors.tsv` slot `0x00` | **20/20 and 26/26 segments byte-identical** for `ref_nopunct`/`ref_lexclean` (after two fixes: C integer division truncates toward zero in the leaf formula, and `pause_base_len = 0`) |
| context vectors (`FUN_00060ed4`) | `unit_feature_vectors.tsv` | **every slot identical** for every segment of `ref_nopunct`/`ref_lexclean` (`compare_selection.py`: 20/20 and 26/26 vectors, "all numeric slots identical", "string slots all identical"); per-word `gpos` also agrees 73/73 segments over the three captures (`validate_gpos.py`) — the numeric slots, the seven resolved string slots, `0x26/0x27` (`ssyl_from`/`ssyl_to`, recovered rule: distance in syllables to the nearest stressed syllable, §10.4/1) and the `pau` items' `0x28`/`0x38` nil slots (§10.4/2); `gpos` comes from the recovered closed-class dictionary (§10.4/3) |
| target cost `FUN_00031234` | `viterbi_candidates.tsv` | **100 % on every node of all three captures — 6146/6146 (`ref_nopunct`), 5945/5945 (`ref_lexclean`), 9061/9061 (`ref_default`) = 21 152/21 152 candidate rows, first and last node included** |
| beam pruning | `viterbi_candidates.tsv` counts | *superseded by §12* (kept sets are exact).  At the time this row was written the decompiled rule (threshold = the cheapest value covering ≥51 candidates, +1, plus the two context-name exemptions) reproduced the engine's kept counts **exactly for 6/25 nodes** and within a few percent for most others |
| candidate lattice | `candidate_lattice.txt` | `count`/`b_start` identical for all positions; the engine's candidate sets are exact subsets of the section-B slices (0 extra units, all 25 nodes) |
| unit sequence | `unit_sequence.txt` | *superseded by §12* (**19/19** `ref_nopunct`, 25/25 `ref_lexclean`, 26/26 `ref_default`).  At the time this row was written: 3/19 exact for `ref_nopunct` (incl. the 3-unit run `107796/107797/107798` = the "test" token), 5/25 for `ref_lexclean` |
| PCM | `compare_tts.py` | see §10.3 |

The two edge-node anomalies are **solved**: their 5–6 point offset came from the
`pau` item's context vector, whose `0x28` (`syl_vowel`) and `0x38` (word `gpos`)
slots the engine fills with the nil string `"0"` although `FUN_00060ed4`'s `pau`
branch writes neither (see `report_cost_terms_main.md` §4d(c)).  Modelling those
two slots makes *every* candidate of the first and last node exact, so the target
cost now reproduces the engine **100 %** on all 21 152 candidate rows of the three
captures (`ref_nopunct` 6 146, `ref_lexclean` 5 945, `ref_default` 9 061).  The
remaining selection difference never came from the costs (join costs are
bit-exact, target cost is exact, the candidate lattice is the engine's own); the
beam model and the search structure (§10.4/4–5) have since been transcribed as
well — see **§12**, which reproduces the engine's unit ids on all three captures
— leaving the front end (§10.4/6 — our own G2P/LTS and punctuation handling
instead of the engine's) and the codec (§10.4/7).

### 10.3 Acceptance A/B — `ref_nopunct`, `"Hello world this is a test"`

```sh
~/venvs/re/bin/python refimpl/tts.py --text "hello world this is a test" \
    --out out/engine_match/nopunct_mine.wav --json out/engine_match/nopunct_mine.json --align
~/venvs/re/bin/python scripts/compare_tts.py \
    out/oracle/ref_nopunct/kendra_hello.wav out/engine_match/nopunct_mine.wav
~/venvs/re/bin/python scripts/compare_selection.py --oracle-dir out/oracle/ref_nopunct \
    --text "hello world this is a test"
```

* chain: **identical** — 19 diphone names and `diphoneset_num` (20 segments:
  `pau hh ax l ow w er l d dh ih s ih z ax t eh s t pau`);
* unit ids: **3/19 exact**, including the consecutive run `107796, 107797, 107798`;
* durations: Σ`zdur_cart` = 3684 ms (per-segment values identical to the engine's);
  the acoustic length is the *recorded* units' (2042 ms of record metadata, no
  time stretch), i.e. the engine's own convention;
* output: 40 991 samples = **1.8590 s** vs the engine's 38 783 samples = **1.7589 s**
  → duration delta **+100.1 ms (+5.7 %)**;
* `compare_tts.py`: envelope correlation **0.4375**, frames within ±3 dB **31.2 %**,
  best lag **−240 ms** (the output carries an extra 240 ms because different units
  were chosen);
* bit-exactness is *not* expected here (the unit sequence differs); for a *given*
  chain the codec→ramp→crossfade→finalize stage remains bit-exact
  (`--verify-engine`: 0 sample diffs, `report_pipeline.md` §6.3).

For `out/oracle/ref_lexclean/` (whose engine run *speaks* the punctuation as the
words `comma`/`dot`, so the pipeline is fed `"hello comma this is a comma dot dot"`
to obtain the engine's own phoneme chain) the same staged comparison gives
5/25 exact unit ids and 100 % exact interior-node costs.

### 10.4 Exact remaining causes of divergence

Items 1–3 are **closed** (they were the three feature-level unknowns); the list is kept
because it documents the evidence.

1. ~~**`ssyl_from`/`ssyl_to` (context 0x26/0x27)**~~ — **recovered.** They are the distance in
   syllables to the previous/next *stressed* syllable (1-based, 0 when there is none that way),
   computed by the plug-in's own getters (`FUN_00044afc`/`FUN_00044b74`, ELF 0x34afc/0x34b74) and
   reproduced by `refimpl/engine_prosody.ssyl_distance`; byte-exact for all 28 syllables of the
   three captures (`scripts/validate_ssyl.py`). Full transcription: `report_cost_terms_main.md`
   §4d(a). This is what raised the interior-node target-cost match from 42 % to 100 % without
   supplying any engine value.
2. ~~**First/last node target costs**~~ — **solved**: the 5–6 point constant was the `pau` item's
   `0x28`/`0x38` slots (the engine leaves the nil string `"0"` there; `FUN_00060ed4`'s `pau`
   branch writes neither) — `report_cost_terms_main.md` §4d(c). With both slots modelled every
   edge-node candidate is exact.
3. ~~**`gpos`**~~ — **recovered**: not a tagger at all but a closed-class dictionary shipped in the
   plug-in's `.rodata` (group array ELF 0x2eb860, string VALs 0x2ebb04; tags `in to det md cc wp
   pps pps$ aux`, default `content`), parsed by `scripts/gpos_table.py` and validated per word by
   `scripts/validate_gpos.py` — `report_cost_terms_main.md` §4d(b).  The earlier claim that the
   engine's tagging is context-dependent (`this` → `det`/`content`) is not supported by any
   capture: the table has exactly one entry per word.
4. ~~**Beam model**~~ — **closed, see §12.** Historical note: `EngineSelector` used the decompiled
   histogram rule, but `select_units.beam_prune` (the CLI default path, beam = 25)
   keeps only the *N* cheapest, so it retains 25–34 candidates per node where the
   engine keeps 60–500 after the context exemptions and `tb_min_distance = 6`
   forced flags. This is the largest single cause of the different unit chain.
5. ~~**Search structure**~~ — **closed, see §12.** Historical note: the engine runs `FUN_0005fc04` once per *chunk* (two
   calls here, `state[6]` persisting, candidates re-dumped and arrays reused),
   beam-pruning the *accumulated totals*; the pipeline runs one plain DP over the
   whole chain.
6. **Front end** — the engine's plain-text mode *speaks* punctuation by name
   (`comma`, `dot`), which the pipeline drops in favour of a clause pause; and
   `--select viterbi` uses the pipeline's lexicon/LTS G2P, not the engine's.
7. **Codec** — the emulated `scripts/decode_unit.py` decoder plus the Hamming-sinc
   24 k→22.05 k stand-in; `scripts/codec_spec.py` can replace the decode stage
   (single `Codec.decode_window` call site) but was not swapped in here.

### 10.5 Files added / changed

| file | role |
|---|---|
| `refimpl/engine_prosody.py` | item graph, `zdur_cart` durations, `FUN_00060ed4` context vectors, join dispatch, beam + Viterbi |
| `scripts/phoneset.py` | plug-in static phoneset reader (8 Festival features, 44 phones) |
| `scripts/diphone_vec.py` | `FUN_0005f1dc` port + `probe_record_vec.py` validator |
| `scripts/probe_record_vec.py` | Unicorn diff of the record decode (3000/3000) |
| `scripts/compare_selection.py` | stage-by-stage diff vs a capture (chain, lattice, contexts, selection) |
| `scripts/compare_costs.py` | per-candidate target-cost diff vs `viterbi_candidates.tsv` |
| `scripts/gpos_table.py` | reader for the plug-in's closed-class `gpos` dictionary (§10.4/3) |
| `scripts/validate_gpos.py` | per-word `gpos` diff (engine capture vs the recovered table) |
| `scripts/validate_ssyl.py` | `ssyl_from`/`ssyl_to` rule check against a capture (§10.4/1) |
| `scripts/analyze_feature_vectors.py` | human-readable dump of `unit_feature_vectors.tsv` |
| `scripts/probe_gpos.py` | Unicorn probe: reads of the plug-in's word tables + `FUN_00026a54` names |
| `scripts/probe_edge_nodes.py` | Unicorn probe: the four arguments of every `FUN_00031234` call |
| `refimpl/tts.py` | `--select viterbi` (default), `--beam`, CART durations, prosody diagnostics, JSON |
| `scripts/prosody.py` | `question()` type-tolerant (string CART features), leaf division truncates toward zero, `pause_duration(base=…)` |
| `out/engine_match/` | acceptance outputs + A/B JSON |
| `out/oracle/clean_they/` | independent capture: `"They came over here and said hello to me"` |

Tooling caveat found while diffing: `out/oracle/*/unit_sequence.txt`'s
`diphone_dur_ms`/`cum_ms` columns read the 36-byte record at the *diphone name
index* rather than at the selected unit's index (the same values appear for
different runs whose selected units differ; `record[1175]=70 ms` vs
`record[420595…]` for the chosen `pau-hh` unit = 450 ms). Use
`unit_feature_vectors.tsv` slot `0x00` for durations.

---

## 11. No-emulator runtime, punctuation, final A/B

This section replaces the last two pipeline-level deviations of
`REPLICATION_STATUS.md` §4: the demo no longer runs the emulated decoder plus a
Hamming-sinc resampler, and it reproduces the engine's *punctuation spoken by
name*.

### 11.1 Clean-room codec swap (no Unicorn on the runtime path)

`refimpl/tts.py:synth` now instantiates the clean-room decoder
`codec_spec.Spec(out_rate=codec_rate)` instead of `decode_unit.Codec`; the
Hamming-sinc `resample()` is gone, replaced by the codec's own output-rate
converter (`codec_parts/resample.Resampler`, ported `FUN_0014b4a8`/
`FUN_0014c494`; the same converter `Spec` uses internally).  `segment_unit.py`'s
`from armemu import ArmLib` moved into `Engine.__init__`, so importing the
pipeline no longer pulls Unicorn in; only `--verify-engine` touches the emulator.

**Bug found and fixed during the swap.** `codec_spec.Spec.decode_window` did not
reset the codec context, unlike `decode_unit.Codec.decode_window` (`FUN_00067a14`
resets per unit).  Reusing one `Spec` for a whole utterance therefore carried
state across units: a 19-unit utterance's pure-python splice differed from the
engine in **29 669 / 44 553** samples, with the mismatch starting at the second
unit.  `Spec.reset()` was added and is now called at the top of `decode_window`,
and the splice is bit-exact again (0 diffs).  (All in-tree callers already used a
fresh `Spec` per record, so nothing else changes.)

Evidence, all reproducible:

```sh
# (a) decoder == emulated decoder, byte-for-byte, both rates (fresh and reused Spec)
~/venvs/re/bin/python scripts/verify_codec_swap.py --voice kendra --count 6
#   -> rate 24000: 5 records fresh-Spec diffs=0 reused-Spec diffs=0 -> BIT-EXACT
#      rate 22050: 5 records fresh-Spec diffs=0 reused-Spec diffs=0 -> BIT-EXACT
# (b) pipeline 24 kHz stream == engine's own splice for the same chain
#     (--select first: deterministic heuristic chain, independent of the search model)
~/venvs/re/bin/python refimpl/tts.py --text "hello world" --select first \
    --out /tmp/x.wav --verify-engine
#   -> [engine] same chain via libttsivonavoice.so: 29966 samples (ours 29966), sample diffs = 0 -> BIT-EXACT
~/venvs/re/bin/python refimpl/tts.py --text "Hello world this is a test" --select first \
    --out /tmp/y.wav --verify-engine
#   -> [engine] same chain ...: 57767 samples (ours 57767), sample diffs = 0 -> BIT-EXACT
# (c) no Unicorn import even on the full synth path (import hook guard)
python3 -c "import builtins,sys; i=builtins.__import__; \
  builtins.__import__=lambda n,*a,**k: (_ for _ in ()).throw(AssertionError(n)) if n.split('.')[0] in ('unicorn','armemu') else i(n,*a,**k); \
  sys.path.insert(0,'refimpl'); import tts; tts.synth('Hello world, this is a test.')"
```

Rate-chain note: the engine's per-unit decode is the **24 000 Hz** codec output.
The engine's unit object labels itself `22050` (`segment_unit.Engine.unit`'s
`obj['rate']`) but its blocks are byte-identical to `codec_spec`/`decode_unit` at
**24000**, not at 22050 (2571 sample diffs, record 0) — the container's 22 050 Hz
is applied downstream, so the pipeline keeps the 24 k codec domain for
selection/splice and converts the committed stream once, exactly as before.  The
converter output length is `floor(22050·n/24000)` (the Hamming stand-in emitted
`floor(…)+1`), so durations are unchanged to a sample.

### 11.2 Punctuation spoken by name

The plug-in carries a 256-entry symbol→name table (pointer array in
`.data.rel.ro` at ELF `0x2eccc0`, strings in `.rodata` from `0x1f1380`); the
engine pronounces punctuation through it — the same "symbol without a reading"
fallback as an unknown word.  `scripts/symbol_names.py` holds the full table
(200 names: control names, all printable ASCII, Latin-1), extracted and re-proved
against the shipped plug-in:

```sh
python3 scripts/symbol_names.py --verify out/libs/kendra/libvoice_en_us_kendra.so
#   -> table is current: 200/200 names identical
python3 scripts/symbol_names.py                       # full mapping
#   0x2c  ,  comma      0x2e  .  dot         0x3a  :  colon
#   0x21  !  exclamation mark   0x3f  ?  question mark   0x3b  ;  semicolon
#   0x2d  -  dash       0x2f  /  slash       ... (also '#','$','%','&','(',')','*','+',
#   '<','=','>','@','[','\\',']','^','_','`','{','|','}','~' and all Latin-1 symbols)
```

`clauses_of` now tokenises words (`[A-Za-z0-9']+`) and single symbols; a symbol is
replaced by its table name and pronounced through G2P (`comma` → the lexicon's
`k aa m ax`, `dot` → `d aa t`), while a sentence-final symbol (`. ! ?`) also
closes a clause.  `, ; :` are spoken but do **not** pause (the old tokeniser
split clauses on them).  The chains match the oracle **position-wise**:

| capture | text | chain vs `diphone_lookups.tsv` |
|---|---|---|
| `ref_default` | `Hello world, this is a test.` | **26/26 identical** — `pau-hh hh-ax ax-l l-ow ow-w w-er er-l l-d d-k k-aa aa-m m-ax ax-dh dh-ih ih-s s-ih ih-z z-ax ax-t t-eh eh-s s-t t-d d-aa aa-t t-pau` |
| `ref_nopunct` | `Hello world this is a test` | **19/19 identical** |

```sh
python3 refimpl/tts.py --phones "Hello world, this is a test."
```

### 11.3 Final A/B against the engine (both captures)

```sh
python3 refimpl/tts.py --text "Hello world this is a test" \
    --out out/tts_demo/sys_nopunct.wav --json out/tts_demo/sys_nopunct.json
python3 refimpl/tts.py --text "Hello world, this is a test." \
    --out out/tts_demo/sys_default.wav --json out/tts_demo/sys_default.json
python3 scripts/compare_tts.py out/oracle/ref_nopunct/kendra_hello.wav out/tts_demo/sys_nopunct.wav
python3 scripts/compare_tts.py out/oracle/ref_default/kendra_hello.wav out/tts_demo/sys_default.wav
python3 scripts/analyze_tts.py out/tts_demo/sys_nopunct.wav
python3 scripts/analyze_tts.py out/tts_demo/sys_default.wav
```

| capture | engine | pipeline | Δ duration | best lag | env. corr. | ±3 dB frames |
|---|---|---|---|---|---|---|
| `ref_nopunct` | 38 783 / 1.7589 s | 39 834 / 1.8065 s | **+47.7 ms (+2.7 %)** | **−220 ms** | **0.6412** | **50.6 %** |
| `ref_default` | 53 649 / 2.4331 s | 53 085 / 2.4075 s | **−25.6 ms (−1.1 %)** | **+20 ms** | **0.6300** | **47.7 %** |

`analyze_tts.py` (objective figures, same runs): `ref_nopunct` peak −8.8 dBFS,
RMS 2 070, 181 × 10 ms envelope frames (38 silent, longest run 180 ms), F0 median
159.8 Hz / 107 voiced frames, ZCR 3 204 /s; `ref_default` peak −8.8 dBFS, RMS
2 315, 241 frames (52 silent, longest 180 ms), F0 median 168.3 Hz / 162 voiced
frames, ZCR 2 513 /s.  Spectrograms: `out/tts_demo/sys_*_spec.png`.

**Plumbing vs selection.**  With the search rewire (`scripts/select_units.py` →
`EngineSelector`: `build_candidates` + `search` + `tb_min_distance = 6`) the unit
choice is now **exact on the engine's own candidate sets** — unit ids 19/19
(`ref_nopunct`), 26/26 (`ref_default`), 25/25 (`ref_lexclean`), and the kept
counts / accumulated totals / flag bytes match the instrumented engine node-for-node
(`report_pipeline.md` §12).  The remaining duration/lag/correlation residual is
therefore **no longer selection**: it is per-unit window/duration handling before
the splice (`FUN_00062d14`), with the committed stream one direction in
`ref_nopunct` (+47.7 ms) and the other in `ref_default` (−25.6 ms).  The plumbing
columns — decoder byte-identical at both rates, punctuation chain position-wise
identical, codec→ramp→crossfade→finalize bit-exact for a given chain
(`--verify-engine`, 0 diffs, e.g. 43 357 samples) — are exact and independent of
both.  These A/B numbers are reproducible with the commands above on the current
tree.

**No-emulator runtime, punctuation, final A/B** — done: `refimpl/tts.py` runs
under system `python3` with no Unicorn on the import path and no resampler
stand-in, reproduces the oracle's punctuation chain for `ref_default`, and the
objective A/B above is the final pair.

---

## 12. Engine-exact unit search (`FUN_0005fc04`) — delivered

> Supersedes, in this file: §10.2's "beam pruning" and "unit sequence" rows (both now
> exact) and §10.4's causes 4–5 (the beam model and the search structure, both closed);
> §11.3's note that the call site "still does the old keep-the-`beam`-cheapest pruning"
> no longer holds — the measured A/B columns there need a re-run (§12.2).

`--select viterbi` (the default) now runs the engine's own search. The previous
"keep the `beam` cheapest candidates" rule is gone; the search, the candidate
build filter and the `tb_min_distance` boundaries are transcribed from
`out/ghidra_dump/libttsivonavoice.c:43094` (Ghidra addresses below; ELF = Ghidra −
0x10000) and its disassembly (`out/viterbi_disasm.txt`, ELF 0x4fc04..0x50b08), and
implemented in `scripts/select_units.py` (`build_candidates` / `threshold` /
`prune` / `search`) with the call sites in `refimpl/engine_prosody.py`
(`EngineSelector.lattice`, `.forced_nodes`, `.select`).

### 12.1 The rule

| phase | address | behaviour |
|---|---|---|
| candidate build | :43100 (node 0), :43294 (rest) | for every unit id of the node's section-B slice decode the 36-byte section-C records of `idx` and `idx+1` (`FUN_0005f1dc`) and **skip** the candidate when the node's left context is a `+` (vowel) and the record's stress (`+0x1d`) differs, or when the right context is a `+` and the right record's stress differs (0x4fd88..0x4fde4). Only survivors get a target cost (`FUN_00031234`, :43149) |
| beam | :43203 (0x502d4 / 0x508d0) | **only when the candidate count > 51** (`0x33`), otherwise the whole block is skipped and the flags stay 1. A **cost threshold sweep** (0x502e0..0x5036c) raises `thr` from `min(cost)` while `#{cost ≤ thr} ≤ 50` and `thr < max(cost)`, then increments once more — so the survivors are `cost ≤ thr` (ties and the +1 slop included), *not* a fixed count |
| context exemptions | 0x503e4..0x50454 | a candidate also survives when the phone **before** its left record (`record[+3]`) equals the node's previous-segment name (`ctx1+0x08`), or the phone **after** its right record (`record[+5]`) equals the next-next segment name (`ctx2+0x10`). The names come from the plug-in's inline phone table (`*(char**)(payload+0x1c) + byte*0x20`, 32-byte records) — equivalently the OBB's phone-name list. A side whose own phone (`ctx+0x0c`) is `pau` disables its exemption |
| flag bytes | 0x50478..0x50518 | `+5` (forced) survives only for `node ≠ 0` **and** a matching left context; `+4` (joint) only for `node+1 < n_nodes` **and** a matching right context |
| per node | 0x4fe50, 0x50878..0x508b8 | survivors are sorted by target (`FUN_0005fa84`, comparator `LAB_0005fa44` = u32 at +0), totalled (`+8 := +0`) and sorted by total (`LAB_0005fa64` = u32 at +8); both sorts are stable |
| transition | 0x4fe88..0x50128 | predecessor array = the **previous** node's array (ascending total). `npred = min(prev_count, beam)`, or all of them when the candidate carries `+5`. A predecessor `p` with `p.+4 ≠ 0` and `p.idx+1 == e.idx` is a **joint** continuation: cost 0, `e.total = base`, `p.+4 = 0`. Otherwise `join(rec[p.idx+1], rec[e.idx], budget = e.total − base)` runs on the **previous** node's `+0xc4` and replaces the total when smaller; only the first `beam` iterations evaluate a join cost. The scan stops at `base ≥ e.total`, at the count cap, or (when `e.+4 = 0` and `i ≥ beam`) once `beam_arr[beam−1] ≤ base`, where `beam_arr` holds the `beam` smallest totals seen for the node |
| chunk | :43495 (0x50140 / 0x5055c) | when the **previous** node's `+0xc8` is set and the current node is not the last, the current array is reduced to the candidates sharing the best entry's back-pointer (zeroed), the function returns the committed prefix and the caller re-invokes it: the persistent state is `param_1[5]` (node count), `[6]` (current node) and `[7]` (finished), and each call gets a fresh beam array |
| `tb_min_distance` | plug-in :7868, disasm 0x20384..0x204bc | a node is forced (`+0xc8 = 1`) when its **right** phone (`ctx2+0x54 ph_vc`) is `-`, at least `tb_min_distance` nodes past the previous forced one **and** at least `tb_min_distance` nodes before the end, and either the right phone is unvoiced (`ctx2+0x58 == "-"`) or the gap exceeds `1.5·tb` (`FUN_00053df8` = dmul with the double 1.5; the compare `FUN_00054380` returns 0 for "not greater" — `[INFERENCE]` from the disassembly, and the only reading that yields the observed single forced node), and the right phone's class is not one of `rplg` (`strchr`, 0x203e8). For the shipped voice this selects exactly **node 10** of the test sentence — hence the engine's two `FUN_0005fc04` calls |

`tb_min_distance` is taken from the voice configuration (`refimpl/tts.py:VOICES`,
value **6** measured in `out/oracle/*/settings.txt`; the plug-in default is −1, i.e.
no forced nodes at all).

### 12.2 Acceptance — staged against the instrumented engine

`scripts/probe_viterbi.py` re-runs the *unmodified* engine under emulation with a
basic-block hook over `FUN_0005fc04` and dumps every candidate-array mutation
(pre-prune, post-prune and post-transition, with the target cost, both flag bytes,
the accumulated total and the raw record bytes);
`scripts/check_viterbi.py rule` replays the rules against those dumps using the
**engine's own target costs** (isolating the search from our cost model), and
`check_viterbi.py pipeline` runs our full `EngineSelector`.

```sh
~/venvs/re/bin/python scripts/probe_viterbi.py --out-dir out/oracle/viterbi_probe2   # ~14 min
~/venvs/re/bin/python scripts/check_viterbi.py rule     --probe out/oracle/viterbi_probe2
~/venvs/re/bin/python scripts/check_viterbi.py pipeline --probe out/oracle/viterbi_probe2
~/venvs/re/bin/python refimpl/tts.py --text "Hello world this is a test" \
    --out out/tts_demo/beam_search.wav
~/venvs/re/bin/python scripts/compare_tts.py out/oracle/ref_nopunct/kendra_hello.wav \
    out/tts_demo/beam_search.wav
~/venvs/re/bin/python scripts/compare_selection.py --oracle-dir out/oracle/ref_default \
    --text "Hello world, this is a test." --beam 25
~/venvs/re/bin/python refimpl/tts.py --text "Hello world, this is a test." \
    --out out/tts_demo/beam_search_default.wav
~/venvs/re/bin/python scripts/compare_tts.py out/oracle/ref_default/kendra_hello.wav \
    out/tts_demo/beam_search_default.wav
```

| stage | engine | ours | result |
|---|---|---|---|
| candidate build (`+` filter, pre-prune sets) | 19 nodes, 552…3643 (post-slice) | same sets, same order | **19/19 exact** |
| beam/prune kept sets (ids, order, both flag bytes) | 87 / 25 / 119 / 82 / 54 / 116 / 105 / 159 / 131 / 477 / 494 / 141 / 257 / 210 / 253 / 199 / 392 / 623 / 268 (node 11 = 123 after the chunk boundary) | identical | **19/19 exact** |
| per-candidate accumulated totals after the transition | — | identical | **19/19 exact** |
| kept counts fed to the pipeline | 87 25 119 82 54 116 105 159 131 477 494 123 257 210 253 199 392 623 268 | identical | **19/19 exact** (node 11 = 123 is the post-chunk-boundary count) |
| chunk boundaries (`tb_min_distance`) | node 10 forced → 2 calls | node 10 forced → 2 chunks (11 + 8 units) | **identical** |
| unit id sequence | `294435 294436 183382 … 107798 107799` | identical | **19/19 exact** (was 3/19) |
| unit id sequence — other captures | `ref_default` 26 diphones, `ref_lexclean` 25 diphones | identical | **26/26 and 25/25 exact** (`compare_selection.py`; 70/70 over the three captures) |
| audio — `ref_nopunct` | 38 783 samples = 1.7589 s | 39 834 = 1.8065 s | **Δ +47.66 ms**; envelope corr. **0.6412**; ±3 dB frames **50.6 %**; best lag **−220 ms** (was: +97.5…+100.1 ms, 0.42–0.44, 31.2 %, −240 ms) |
| audio — `ref_default` | 53 649 samples = 2.4331 s | 53 085 = 2.4072 s | **Δ −25.58 ms**; envelope corr. **0.6300**; ±3 dB frames **47.7 %**; best lag **+20 ms** (stop-gap: +2.7 ms, 0.5924, 44.9 %, +30 ms) |
| splice layer | — | `--verify-engine` | still **bit-exact** for the chain (43 357 samples, 0 diffs) |

An honest caveat on the instrumented run: the harness re-implements `qsort` with the
library's comparators in Python (stable); the engine's own `qsort` on the device is
bionic's, so *ties* in the two per-node sorts are ordered by the harness. Every
comparison above therefore holds against the captured oracle (which was produced by
the same harness), and tie-free nodes are unaffected.

### 12.3 Residual after the search is exact

The unit choice is now identical, so the remaining audio difference is **not** the
search:

* the chosen chain re-spliced through the real `libttsivonavoice.so` is
  bit-exact (`--verify-engine`: 0 diffs), so our splice/window arithmetic for a
  given chain is the engine's;
* the engine's own per-unit durations for this chain sum to **2050 ms**
  (`unit_sequence.txt` `cum_ms`; the column's tooling caveat in §10.5 does not
  affect the pipeline's CART durations, which match slot `0x00` byte-exactly),
  while our committed stream is **1806 ms** (43 357 samples at 24 kHz) and the
  engine's final PCM is **1759 ms**. Our crossfade/splice drops 120 ms (2 871
  samples) of the 1 926 ms of decoded unit audio; the engine drops ~291 ms.
  and `ref_default` goes the other way (53 085 vs 53 649 samples, **−25.58 ms**) with the
  same identical chain, i.e. the offset is not a systematic search artefact.
  [INFERENCE]: the difference is the waveform stage's per-unit duration handling —
  the engine slices/overlaps each unit's window from its *target* duration
  (`FUN_00062d14` time stretch, driven by the CART), which the pipeline does not
  apply. `out/oracle/*/prosody_transforms.tsv` cannot settle it: the capture read
  `r1` while the arguments are `double` (ARM EABI passes them in `r0:r1`/`d0`), so
  the recorded values are `0` and `7e-45` instead of stretch factors. A fresh
  capture of `FUN_00062d14`/`FUN_00063540` (double arguments) is the next step for
  that stage; it is independent of the search.

### 12.4 Files added

| file | role |
|---|---|
| `scripts/probe_viterbi.py` | runs the engine under Unicorn with a block hook over `FUN_0005fc04`; dumps every candidate-array mutation (+ node contexts, `+0xc8` flags) to `out/oracle/viterbi_probe2/` |
| `scripts/check_viterbi.py` | replays `select_units` against those dumps (`rule` = engine target costs, `pipeline` = our cost model) and against `unit_sequence.txt` |
| `out/viterbi_disasm.txt` | capstone disassembly of `FUN_0005fc04` (ELF 0x4fc04..0x50b08) |
| `out/plugin_graph_disasm.txt` | capstone disassembly of the plug-in's `FUN_00030214` (the `tb_min_distance` block) |
| `out/oracle/viterbi_probe/`, `out/oracle/viterbi_probe2/` | instrumented captures (the `2` variant adds forced snapshots: pre-prune, post-prune, post-transition) |

---

## 13. The streaming contract — solved (`ref_nopunct`/`ref_default`/`ref_lexclean`)

Supersedes, in this file: §11.3's and §12.3's residual paragraphs and their A/B
tables (those compared a **22 050-resampled** pipeline against an **unresampled**
engine, see §13.4); §12.3's `[INFERENCE]` that the difference is "per-unit
window/duration handling" — the four transforms are indeed bypassed, but the
engine does modify two units per utterance, through the `pau` restretch (§13.5).

Evidence: `out/oracle/stream_*/stream_trace.txt`, written by
`emu/tts_run.py --stream-probe` (new `--stream-probe` flag), which snapshots the
streamer struct (`+0x10 pos`, `+0x14 tail`, `+0x18 total`) around every
`FUN_00061620` (splice), `FUN_000618a8` (finalize), `FUN_00061804` (silence pad),
`FUN_00063350`/`FUN_00062718` (the `pau` restretch).  The three captures were
re-run with it:

```sh
~/venvs/re/bin/python emu/tts_run.py --level 3 --ret-probe --stream-probe \
    --sentence "Hello world this is a test"   --out-dir out/oracle/stream_nopunct
~/venvs/re/bin/python emu/tts_run.py --level 3 --ret-probe --stream-probe \
    --sentence "Hello world, this is a test."  --out-dir out/oracle/stream_default
~/venvs/re/bin/python emu/tts_run.py --level 3 --ret-probe --stream-probe \
    --sentence "Hello, this is a comma dot."   --out-dir out/oracle/stream_lexclean
```

### 13.1 The pull loop and `finalize`

`tts_streamer_synth0(streamer, buf, n)` (`0x4b460`) loops `FUN_0004ae28` with
`remaining = n - written` until the caller's buffer is full or the producer
returns 0; the bridge's scratch buffer is `n = 0.3 * tts_voice_sample_rate` =
**6615** frames.  `FUN_0004ae28` → `FUN_0005a698(task, want, events)` →
`FUN_0005d7c4`, which appends units until `pos >= want` and then
`FUN_000618a8(streamer, want)`:

* copies `min(want, pos)` samples;
* slides the **whole buffer** — `memmove(dest, dest + n*2, (capacity - n)*2)`
  (capacity, not `pos`) — so `pos -= n` and the *pending* `tail` written at `pos`
  **rides along with the slide** and stays valid for the next unit's crossfade;
* the item-list end makes `want <= pos` fail, so the remainder (`n = pos`) is
  finalised and a pending tail is never committed: the last unit's final segment
  is dropped exactly once.

The trace confirms each clause individually, e.g. for `ref_nopunct`
(`splice #k … pos0 tail0 → written pos tail`):

| unit | flag | pos0 | tail0 | written | pos | tail |
|---|---|---|---|---|---|---|
| 3 | 1 | 4525 | 170 | 2180 | 6705 | 135 |  ← `finalize(6615)` follows: `pos = 90`, tail still 135 |
| 4 | 0 | **90** | **135** | 2819 | 2909 | 0 |
| 6 | 0 | 6011 | 143 | 2684 | 8695 | 0 |  ← `finalize(6615)`: `pos = 2080` |
| 7 | 1 | **2080** | 0 | 1836 | 3916 | 165 |
| 10 | 1 | 6273 | 0 | 1805 | 8078 | 148 | ← `finalize(6615)`: `pos = 1463` |
| 11 | 0 | 0 | **148** | 2212 | 2212 | 0 |

`want` is **6615**, i.e. the *same* number as the caller's frame count: the
engine does not scale it, which is consistent with §13.4 (the unit samples are
codec-domain while `rate`/`want` are the voice's 22 050).

### 13.2 The concat flag

`FUN_0005d7c4`:42382-42400 decides the `FUN_00061620` flag per unit:

```
flag = 0  <=>  next item exists, carries both "diphone" and "diphoneset_num",
               and its "diphone" value == this one + 1
flag = 1  otherwise
```

`"diphone"` is the **voxdb record index** (the index our `unit` field holds:
the same value `FUN_0005ef70` is called with and the 36-byte section-C records
are indexed by) — *not* the section-A `diphoneset_num`, which is how
`report_engine_synth.md` §1.7 read it.  Verified against the trace's own flag
column: **19/19** transitions (`ref_nopunct`), **25/25** (`ref_lexclean`),
**25/26** (`ref_default`; the exception is unit 237953 → 237954, flagged 1 even
though the ids are adjacent — the following item is not a plain diphone item and
one of the two feature tests fails).  That exception is **output-neutral** for
this capture: either flag leaves unit 237954's block 0 (147 samples) equal to the
held tail it would crossfade over, so the committed samples are identical.
Implemented in `refimpl/tts.py:unit_flags`.

Note this also corrects `report_segmentation.md` §3's reading of flag 0 as "the
last unit of the utterance": the last unit is spliced with flag **1** and its
last segment is dropped later, by the utterance-end `finalize` — the committed
output is the same, but the streamer state (`tail`) differs.

### 13.3 `refimpl/tts.py` now follows the contract

* `unit_flags()` — the rule of §13.2 (byte-identical unit chains, so the flag
  sequence is exact for the three captures up to the one exception);
* `stream_chunks()` — the caller-visible per-`synth0`-call frame counts
  (`min(6615, remaining)`; the engine's are 5×6615+5708 / 8×6615+729 /
  7×6615+2987 = 38 783 / 53 649 / 49 292);
* `stream_len_model()` — the committed-length model, now driven by the flags;
* `pause_align()` — the `pau` restretch windows of §13.5, reported per run.

The flag rule and the splice stay bit-exact with the engine for the same chain
(the engine is driven through the real `.so` with the *same* flags):

```sh
~/venvs/re/bin/python refimpl/tts.py --text "Hello world this is a test"        --verify-engine
~/venvs/re/bin/python refimpl/tts.py --text "Hello world, this is a test."      --verify-engine
~/venvs/re/bin/python refimpl/tts.py --text "Hello comma this is a comma dot dot" --verify-engine
# -> same chain via libttsivonavoice.so: 43358 / 57781 / 52981 samples (ours equal), 0 diffs -> BIT-EXACT
```

```sh
python3 refimpl/tts.py --text "Hello world this is a test" --out /tmp/x.wav
#   [stream] committed samples = 43358 == model 43358 ? True (held tail=148)
#   [pau]    unit 0 (pau-hh, L phone) setlen seg[0..16] = 220 samples (was 2507, factor 0.0878)
#   [pau]    unit 18 (t-pau, R phone) setlen seg[5..27] = 1102 samples (was 3392, factor 0.3249)
#   [pull]   tts_streamer_synth0 chunks (0.3 s = 6615 frames): 6615 ... 3668 -> 7 calls
```

### 13.4 The engine does **not** resample

The shipped voice defines **no `resample_wave`** parameter (the plug-in's 46-key
list in `out/oracle/*/trace.log`; absent from `settings.txt`), so `FUN_0005d7c4`'s
conditional `FUN_00059958` never runs: the wave object carries the **codec-domain
(24 000 Hz) samples labelled 22 050 Hz**, and the bridge hands them on unchanged.
Proof, sample-exact: the engine's PCM equals our committed stream at a constant
**+2360-sample offset** (§13.6) — impossible if a rate conversion had happened on
one side only.

`refimpl/tts.py` therefore no longer converts by default; `--resample` opts back
in to the codec's own 24 000 → `--rate` converter for callers that want a true
22 050 Hz signal.  **The earlier A/B numbers (§11.3, §12.3) were measured with
that conversion on, i.e. comparing a time-scaled pipeline against the engine** —
which is why the "lag" looked like −220 ms and the envelope metrics were low.

### 13.5 The one remaining mechanism: the `pau` restretch

The waveform stage *does* modify two units of every utterance, in the window
alignment of `FUN_0005d7c4`:42256-42400 (before the splice):

```
k = (int)((dur_ms/1000 * 0.5) * rate)        # rate = the *object's* rate field
i = FUN_00062500(obj, k)                     # segment whose marks bracket k
i -= 1  when  0.5*dur_ms/1000 <= (pms[i-1]+pms[i]) / (2*rate)
L phone == "pau" -> FUN_00063350(obj, 0,   i,   target)
R phone == "pau" -> FUN_00063350(obj, i+1, N-1, target)
target = (int)(rate * (end(seg) - end(prev(seg))))   # halved with both neighbours
```

`end` is the prosody model's cumulative segment end (`scripts/prosody.pause_duration`
for `pau`, `zdur_cart` otherwise); `FUN_00063350(from, to, newlen)` restretches the
segment range to `newlen` samples by calling `FUN_00062d14(from, to, newlen/cur)`,
the SOLA time-stretch.  `scripts/probe_stretch.py` (new) drives the real function
directly (CDXV + diphonedb only, no voice load) and printed `unit 294435:
rate=22050`, pinning the rate the targets use.

`refimpl/tts.py:pause_align` implements the window, the split index and the
target, and reproduces the engine's `trim` lines **6/6**:

| capture | unit | engine (`stream_trace.txt`) | ours |
|---|---|---|---|
| all three | 0 `pau-hh` (L) | `setlen(seg 0..16) = 220  (N=26)` | seg[0..16] = 220 (was 2507) |
| `ref_nopunct` | 18 `t-pau` (R) | `setlen(seg 5..27)  = 1102 (N=28)` | seg[5..27] = 1102 (was 3392) |
| `ref_default` | 25 `t-pau` (R) | `setlen(seg 10..29) = 1102 (N=30)` | seg[10..29] = 1102 (was 2949) |
| `ref_lexclean` | 24 `t-pau` (R) | `setlen(seg 10..25) = 1102 (N=26)` | seg[10..25] = 1102 (was 2359) |

The targets are `(int)(22050 * 0.01) = 220` (utterance-initial `pau`, no previous
segment) and `(int)(22050 * 0.05) = 1102` (sentence-final, `pause_base_len = 0`)
— the same values in all three captures, as the traces show.

`segment_unit.stretch_pass` / `segment_unit.stretch` implement it and are
**verified against the real function at every pass depth** (`scripts/probe_stretch.py`
drives `FUN_00062d14` on the decoded unit and dumps the object's `N`, `pms` and
blocks; `--raw-factor 0.5 / 0.25 / 0.125` give the 1-/2-/3-pass oracles):

| call (unit 294435, window 0..16) | engine | model |
|---|---|---|
| `factor 0.5` (1 pass) | N=17, 2503 samples, 8 blocks × 147 | identical (pms + all samples) |
| `factor 0.25` (2 passes) | N=13, 1915 | identical |
| `factor 0.125` (3 passes) | N=11, 1621 | identical |
| `factor 0.08775` (4 passes, the engine's own) | N=10, 1474 | identical |
| `(40107, 10..29, 0.5)` | N=20, 2945 | identical |

The pass: inside the window each segment is either *kept* or *merged with the
next* (the verified `FUN_00062bd4` crossfade into the kept block, emitting
`min(len_i, len_next)` samples and consuming both), choosing whichever leaves
`new_run/old_run` closer to the target — with `f_drop`'s numerator switching on
`len_next <= len_i`; the window's *last* segment may merge with the first
segment *after* it, which is why a pass can eat one tail segment.  The driver
halves (`0.5`) while `0.5·acc >= factor` and finishes with `factor/acc`, moving
the bound `upper += (new_count − N0)` after each pass.

### 13.6 Measured outcome (the acceptance numbers)

With the windows restretched by `segment_unit.stretch`, the pipeline reproduces
the engine's stream **sample for sample** on two captures and to within 69
samples on the third:

| capture | units | engine PCM | pipeline | Δ | sample diffs | `compare_tts.py` |
|---|---|---|---|---|---|---|
| `ref_nopunct` | 19 | 38 783 | 38 783 | **0** | **0 → BIT-EXACT** | 0 ms lag, corr 1.0000, ±3 dB 100 % |
| `ref_default` | 26 | 53 649 | 53 649 | **0** | **69** (0.13 %) | 0 ms lag, corr 1.0000, ±3 dB 100 % |
| `ref_lexclean` | 25 | 49 292 | 49 292 | **0** | **0 → BIT-EXACT** | 0 ms lag, corr 1.0000, ±3 dB 100 % |

The 69 `ref_default` samples are all in one crossfade seam (`41988…`), at the
concat-flag transition the rule of §13.2 cannot see: unit 237953 → 237954, whose
ids *are* adjacent (and whose voxdb records *are* contiguous) but which the
engine splices with **flag 1**.  The only mechanism that can produce that is an
*extra item* in the engine's item chain between those two diphone items (an item
that emits no audio — there are no `FUN_00061804` pad calls in any capture — and
that also cuts the chunk: the trace shows a `finalize` exactly between the two).
Everything else, including that seam's *length* (so the totals and the per-call
counts agree), is reproduced.

Per-call frame counts (acceptance (a)) — `stream_chunks()` against `trace.log`:
`6615×5 + 5708` (6 calls), `6615×8 + 729` (9), `6615×7 + 2987` (8): **identical
for all three captures**, in the same order.

`scripts/probe_stream_contract.py --pcm` (the earlier region check) now reports
0 differing samples for `ref_nopunct`/`ref_lexclean`:

```sh
python3 refimpl/tts.py --text "Hello world this is a test" --out /tmp/x.wav --json /tmp/x.json
python3 scripts/probe_stream_contract.py out/oracle/stream_nopunct --pcm /tmp/x.wav
#   [pcm] engine 38783 samples, ours 38783, measured shift +0 samples
#   [pcm] 0/38783 samples differ (0.000%)
#   [pcm] flag rule (next unit id == this + 1): 19/19 transitions agree with the engine
```

`--verify-engine` (the raw chain, i.e. without the `pau` windows, whose
restretch the probe verifies against the real `FUN_00062d14`):
`43358 samples (ours 43358), sample diffs = 0 -> BIT-EXACT`; the same holds for
`ref_default` (57 781) and `ref_lexclean` (52 981) chains.

```sh
python3 scripts/probe_stream_contract.py out/oracle/stream_nopunct \
    --pcm out/engine_match/nopunct_codec.wav
#   [pcm] engine 38783 samples, ours 38783, measured shift +0 samples
#   [pcm] 0/38783 samples differ (0.000%)
#   [pcm] flag rule (next unit id == this + 1): 19/19 transitions agree with the engine
```

That tool also replays the model against the engine's own per-call state: it
decodes the trace's chain with the clean-room codec, keeps the model in lock-step
with the engine's `pos0/tail0/total0` before every splice and compares
`written/pos/tail/total` — the two `pau` units excepted (they are restretched
before the splice), the bookkeeping is reproduced **exactly** (17/19, 24/26,
23/25 splice calls), which is what isolated the residual to `FUN_00062d14` alone.

### 13.7 Files

| file | role |
|---|---|
| `emu/tts_run.py` | `--stream-probe`: logs `pos/tail/total` and the arguments around every splice/finalize/pad/trim call to `stream_trace.txt` |
| `scripts/probe_stream_contract.py` | replays `segment_unit.splice` against the engine's own state, checks the flag rule, and aligns the engine's PCM against ours (`--pcm`) |
| `scripts/probe_stretch.py` | drives the real `FUN_00063350`/`FUN_00062d14` on one decoded unit (prints `N`/`pms` before and after, `--dump-blocks` writes the post-call samples) — the oracle for the SOLA |
| `scripts/segment_unit.py` | `stretch_pass` / `stretch`: the SOLA restretch (verified pass-by-pass) |
| `out/oracle/stream_nopunct/`, `stream_default/`, `stream_lexclean/` | instrumented captures (PCM + the original artefacts + `stream_trace.txt`) |
| `out/engine_match/*_codec.wav`, `*.json` | the pipeline's engine-exact output for the three captures |
| `refimpl/tts.py` | `unit_flags` / `pause_align` / `stream_chunks` / `stream_len_model`, the applied restretch, `--resample` (off by default), `--json` carries `concat_flags`, `pause_align`, `stream_chunks` |

### 13.8 The last 69 samples

Everything up to and including the `pau` restretch is reproduced.  The remaining
`ref_default` difference (69 samples of low-level noise, one crossfade seam at
`41988…`, total and pull counts already exact) is one concat-flag decision the
rule of §13.2 cannot see: unit 237953 → 237954 has adjacent ids *and* contiguous
voxdb records, yet the engine flags 1.  The remaining unknown is therefore in the
**item chain**, not in the ids: an item exists between those two diphone items
that emits no audio (no `FUN_00061804` call — the trace has 0 pads in all three
captures) and that also cuts the chunk (a `finalize` sits exactly there).

Smallest next step: probe the item chain at the flag decision
(`FUN_0005d7c4`:42382, where `FUN_00058e40(item)` is taken): dump the *current*
and *next* item's feature lists (`emu/tts_run.py` already has `item_features`;
the item cursor is `*(streamer + 8)`) for `ref_default` and see which feature
test fails there — then either model the extra item or fold the condition into
`unit_flags`.
