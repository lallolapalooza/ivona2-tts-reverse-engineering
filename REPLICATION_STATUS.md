# IVONA 2 — replication status report

Verdict: **the system is reimplementable from these artefacts.** Every layer that the original
binaries implement has either a validated reference implementation in this directory or a complete
specification with an executable oracle to check a port against; the only piece not yet finished is
the final integration (wiring the validated duration model + Viterbi into the demo pipeline and
diffing against the engine's utterance) — see §4.

Everything below is verifiable in this directory: specs are the `report_*.md` files, code is under
`scripts/`, `refimpl/`, `emu/`, and the oracles are the captured engine outputs under `out/`.

---

## 1. Per-layer status

| # | layer | spec | reference implementation | independent verification | residual |
|---|---|---|---|---|---|
| 1 | Android shell, voice packs, package discovery, OBB packaging | `report_engine_app.md` (770 L), `report_voice_pack.md` (422 L), `report_libtiver.md` | `refimpl/{cdxv,voices,license,marks,params}.py` | `python3 -m unittest discover -s refimpl` → **74 tests OK** over the real APKs/OBBs | no device test performed |
| 2 | `CDXV` container + tables (index, sections, diphone/unit records) | `report_obb_format.md` (538 L) | `refimpl/cdxv.py` | invariant pass over both OBBs (426 991 / 404 847 units, contiguity, `len == 2N+12`, …) | — |
| 3 | Lexicon container `ISEF` | `report_isef.md` | `scripts/isef_decrypt.py` (stdlib) | engine's own `FUN_000346d4` under Unicorn → **byte-identical** 74 137 B; my re-check after the harness fix | — |
| 4 | Acoustic codec (gap → PCM), incl. internal 24 000→22 050 resampler | `report_gap_codec.md`, `report_codec_spec.md` (22.8 k) | `scripts/codec_spec.py` + `codec_parts/{parse,dequant,setup,gain,xform,post,dsp,resample}.py` (stdlib) | per-stage **55/55** byte-identical over 336 recorded calls / 1 344 buffers; chained **1 344/1 344**; end-to-end **59/59** records bit-identical per voice at 22 050 and 24 000 Hz; my `cmp` clean-room vs emulated WAVs **identical** (records 0 and 419 753) | polyphase converters unreachable from 24 000→22 050 raise `NotImplementedError` (documented) |
| 5 | G2P (packed lexicon + LTS FSM) | `report_frontend.md`, `report_libvoice.md` §2 | `scripts/lex_decode.py`, `scripts/lts_decode.py` | both cross-checked against the plug-in via `scripts/probe_g2p.py` (`hello → hh ax l ow1`, `kendra → k eh1 n d r ax`, `world → w er1 l d`) | — |
| 6 | Segmentation / splicing / finalise | `report_segmentation.md` | `scripts/segment_unit.py` | engine vs model: **0 sample differences** for segmentation, splice and finalise | — |
| 7 | Prosody + unit selection (join cost ×5, target cost, dispatcher, duration CART, pause rules, Viterbi) | `report_prosody.md` (35.7 k), `report_cost_terms_main.md` (+§4c feature-slot map) | `scripts/prosody.py`, `scripts/select_units.py` | `probe_prosody.py`: **15 000/15 000 bit-identical** (my re-run **2 400/2 400**); duration CART blob fully decoded (44 phones, 3 951 nodes / 1 584 leaves) | CART not yet run end-to-end; intonation only assigns phrase-final `endtone`; §1.7 `tb_min_distance` inference superseded by the measured `settings.txt` (active, = 6) |
| 8 | Engine API / handles / certificate / marks | `report_engine_api.md`, `report_ttsivona.md` | `refimpl/{license,marks,params}.py`; certificate path runs under emulation | certificate verification positive + tampered negative control; ISEF/cert paths byte-identical to the Python references | certificate signature routine end-to-end not traced |
| 9 | Emulation + oracles | `report_emulation.md` (22.7 k), `report_oracle.md` | `emu/{armemu,run,probe_gap,tts_run}.py` | engine runs levels 1–3: front end + PCM under Unicorn | punctuation is spoken by name (faithful engine behaviour, bounded) |
| 10 | Functional pipeline | `report_pipeline.md` (21.1 k) | `refimpl/tts.py` + `scripts/analyze_tts.py` | text→WAV for both voices; same unit chain re-spliced through the real library is **bit-exact** (27 102/27 102 samples, 0 diffs) | uses a documented heuristic for selection and flat prosody until §4 lands |

## 2. Engine ground truth now available

`out/oracle/ref_nopunct/` — `"Hello world this is a test"`, **38 783 samples = 1.759 s @ 22 050 Hz**,
phone chain `hh ax l ow | w er l d | dh ih s | ih z | ax | t eh s t`, produced by the **unmodified
engine** under emulation, with per-capture artefacts:

* `settings.txt` — live voice params: `viterbi_beam = 25`, `tb_min_distance = 6`,
  `eng_sentence_break = 0.4 s`, `eng_paragraph_break = 0.65 s`, `eng_max_sentence = 1000`,
  `eng_max_word = 100`, `pause_base_len = 0`, `duration_stretch = pitch_stretch = amplify = compress = 1`,
  `sample_rate = 22050`, `language_code = en-US`;
* `diphone_lookups.tsv` (linguistic chain), `unit_sequence.txt` (chosen units + per-unit durations),
* `unit_feature_vectors.tsv` (96-byte feature vectors, slot names in the header),
* `candidate_lattice.txt`, `candidate_records.tsv`, `viterbi_candidates.tsv` (**the engine's own
  per-candidate target/total costs**), `prosody_transforms.tsv`, `kendra_hello.{pcm,wav}`.

`ref_default` / `ref_lexclean` are also valid (word-correct) but contain punctuation spoken by name.
The top-level `out/oracle/` capture predates a harness fix and is kept only for the record.

## 3. Harness defects found and fixed (they all had real consequences)

| defect | effect | fix |
|---|---|---|
| `sprintf` stub ignored `.*` and never consumed the `*` argument | plug-in's LTS rule context corrupted → every out-of-lexicon word lost its phones ("Hello world" → only "hello") | formatter rewritten (`*` width/precision, length modifiers, `printf/sprintf/snprintf/fprintf/vsprintf/vsnprintf/vfprintf`) |
| `atol` registered as `strtol` (using a garbage base register) | `tts_load_voice` rejected the OBB (`errno 4`) | C-correct `strtol/atoi/atol` incl. base handling |
| nested `emu_start` for `qsort` comparators (not re-entrant in Unicorn 2.1.4) | Viterbi aborted → 0 frames | comparators re-implemented in Python (stable, matching glibc merge sort) |
| stale `errno` from the `lang_<code>_<voice>.dat` probe | cosmetic errno 9 at synthesis | documented; byte-identical copies supplied, fallback is the production path |

## 4. Utterance-level integration — **audio matches the engine** (two captures bit-exact, third within 69 samples)

The pipeline (`refimpl/tts.py` + `refimpl/engine_prosody.py` + `scripts/select_units.py`) now
reproduces the engine's decisions stage by stage. Every number below was re-verified by me on the
current tree (independent runs, not agent reports).

| stage | result (vs the captured engine) |
|---|---|
| diphone chain | **exact**: `ref_nopunct` 19/19, `ref_default` 26/26, `ref_lexclean` 25/25 |
| unit-id sequence | **exact 70/70** (was 3/19 before the search rewrite) |
| candidate build filter, kept sets, both flag bytes | **19/19 nodes exact** against the instrumented engine (`scripts/probe_viterbi.py` + `check_viterbi.py rule`) |
| chunk boundaries | 2 chunks, node 10 forced — same as the engine |
| target cost `FUN_00031234` | **21 152/21 152 exact** over three captures, with our own feature vectors (per-node `|d|` min/med/max = 0/0/0, edge nodes included) |
| durations | engine context slot `0x00` reproduced **byte-identically** for every segment |
| context-vector slots | all numeric + string slots identical (20/20 and 26/26 vectors) |
| codec | **clean-room, stdlib-only**, bit-identical to the engine at 24 000 and 22 050 Hz; **no Unicorn on the runtime path** |
| punctuation | plug-in's 200-name symbol table (`scripts/symbol_names.py`, `--verify` 200/200) |
| splice layer | bit-exact for a given chain (`--verify-engine`, 0 diffs) |
| concat flags + chunked finalise | engine's flag column reproduced 19/19, 25/25, 25/26; `pos/tail/total` bookkeeping reproduced for every non-`pau`-window splice (`scripts/probe_stream_contract.py`) |
| audio `ref_nopunct` | **38 783 = 38 783 samples, `sample_diffs = 0` → BIT-EXACT** (0 ms lag, envelope corr 1.0000, ±3 dB 100 %) |
| audio `ref_default` | 53 649 = 53 649 samples, **69 samples differ (0.13 %)** at one crossfade seam (`41988…`); 0 ms lag, corr 1.0000, ±3 dB 100 % |
| audio `ref_lexclean` | **49 292 = 49 292 samples, `sample_diffs = 0` → BIT-EXACT** (0 ms lag, envelope corr 1.0000, ±3 dB 100 %) |

### The seven causes, closed

1. **Beam/pruning** — transcribed from `FUN_0005fc04`: a **cost-threshold sweep** raising `thr` from the
   minimum target cost until ≥ 51 candidates are covered, plus context-name exemptions (phone-table
   bytes `+3`/`+5` vs context slots `0x08`/`0x10`, disabled on `pau` sides) and the `+4`/`+5` flag
   bytes; the whole block is skipped when a node has ≤ 51 candidates. Implemented in
   `select_units.prune`; kept sets match 19/19.
2. **Search structure** — node-0 prologue, per-node sort-by-target / total:=target / sort-by-total,
   the transition with `npred = min(prev, beam)` unless the forced flag is set, the joint
   continuation, `budget = e.total − base`, and the **chunked relaxation** with `tb_min_distance = 6`
   (plug-in rule `0x20384..0x204bc`, incl. the `1.5 × tb` compare) → chunk boundaries match.
3. **`ssyl_from` / `ssyl_to`** — recovered from the plug-in's own getters (ELF `0x34afc` / `0x34b74`):
   1-based distance along the Syllable sibling chain to the previous/next syllable with `stress > 0`,
   0 when the chain ends. `validate_ssyl.py`: 56/56 bytes.
4. **`gpos`** — not a tagger: the plug-in ships a closed-class **word→tag dictionary** in `.rodata`
   (`in, to, det, md, cc, wp, pps, pps$, aux` + default `content`; 159 entries, case-folded);
   `scripts/gpos_table.py`, `validate_gpos.py`: 73/73 segments. The earlier "context-dependent
   tagging" note is superseded (one entry per word).
5. **Edge nodes** — the first/last-node constant was the `pau` items' context slots `0x28`/`0x38`
   holding the nil string `"0"`; modelled → `|d| = 0` for every edge candidate.
6. **Punctuation** — spoken by name via the plug-in's 200-name table; chains now identical (19/19,
   26/26).
7. **Codec in the pipeline** — replaced by the clean-room decoder (and the codec's own resampler);
   a missing per-window `Spec.reset()` was found and fixed en route.

### Residual — closed except for 69 samples of one crossfade seam

The earlier re-scoping was right about the cause class and is now **measured**:
the four transforms are bypassed (all 1.0, guarded by `!= 1.0` at
`libttsivonavoice.c` ≈42255-42380), and what remained was the waveform stage's
streaming/termination contract **plus** the `pau` restretch.  Both are now
reproduced (details, commands and evidence: `report_pipeline.md` §13), from three
re-captures with a new streamer probe (`emu/tts_run.py --stream-probe` →
`out/oracle/stream_{nopunct,default,lexclean}/stream_trace.txt`):

* **pull loop** — `tts_streamer_synth0` asks for `0.3 × 22 050 = 6615` frames per call;
  `FUN_0005d7c4` appends units until `pos >= want` and `FUN_000618a8` copies `min(want, pos)`,
  sliding the *whole buffer* (`capacity - n`, not `pos - n`) so `pos -= n` and the pending `tail`
  **rides along**; the item-list end finalises the remainder (`n = pos`) and drops the pending tail.
  The trace's per-call `pos0/tail0` sequence confirms every clause.
* **concat flag** — `flag = 0` iff the next item's `diphone` feature (the **voxdb record index**,
  i.e. our unit id — *not* the section-A index) is this unit's +1; otherwise 1.  Verified **19/19**,
  **25/25**, **25/26** transitions across the three captures.
* **no resampling** — the voice defines no `resample_wave`, so the engine's wave carries the
  **codec-domain (24 kHz) samples labelled 22 050 Hz**; `refimpl/tts.py` now matches that
  (`--resample` opts in).  The earlier A/B tables compared a 22 050-converted pipeline against the
  *unconverted* engine and are superseded.
* **the `pau` restretch** — `FUN_00063350` → `FUN_00062d14` on the two `pau` windows per utterance.
  `refimpl/tts.py:pause_align` reproduces the engine's 6/6 `setlen` calls (`seg 0..16 = 220`;
  `seg 5..27 / 10..29 / 10..25 = 1102`) and `scripts/segment_unit.py:stretch` the SOLA itself,
  verified pass-by-pass against the real function (`scripts/probe_stretch.py`:
  `factor 0.5/0.25/0.125/0.08775` on unit 294435 → N 17/13/11/10 with bit-identical `pms` and
  samples; `(40107, 10..29, 0.5)` → N=20 likewise).

Measured outcome on the current tree:

| capture | engine PCM | pipeline | Δ | sample diffs | `compare_tts.py` |
|---|---|---|---|---|---|
| `ref_nopunct` | 38 783 | 38 783 | **0** | **0 → BIT-EXACT** | 0 ms lag, corr 1.0000, ±3 dB 100 % |
| `ref_default` | 53 649 | 53 649 | **0** | **69** (0.13 %) | 0 ms lag, corr 1.0000, ±3 dB 100 % |
| `ref_lexclean` | 49 292 | 49 292 | **0** | **0 → BIT-EXACT** | 0 ms lag, corr 1.0000, ±3 dB 100 % |

The per-call pull counts match `trace.log` exactly (`6615×5+5708`, `6615×8+729`,
`6615×7+2987`), and `scripts/verify_all.py` reports **12/12**.

The 69 remaining `ref_default` samples are one crossfade seam (`41988…`) at the
concat-flag transition 237953 → 237954, whose ids *are* adjacent (and whose voxdb
records *are* contiguous) yet which the engine splices with flag 1 — i.e. an
*extra item* in the engine's item chain between those two diphone items (it emits
no audio: 0 `FUN_00061804` pad calls in all three captures, and it also cuts the
chunk there).  Next step: probe the item chain's feature lists at
`FUN_0005d7c4`:42382 (`report_pipeline.md` §13.8).

## 5. How a third party proceeds

`REPLICATION_HANDBOOK.md` is the build order. In short: implement the data layer from `refimpl/`
(74 tests as the executable spec), then the lexicon reader (`report_isef.md`), then either port the
codec from `report_codec_spec.md` or drop in `scripts/codec_spec.py`, then the front-end + prosody
(`report_frontend.md`, `report_prosody.md`), then the Android shell (`report_engine_app.md`,
`report_voice_pack.md`). At every stage an oracle exists: 74 conformance tests, the codec's
per-stage snapshots, `probe_prosody.py`, `segment_unit.py --verify-*`, and the engine's own utterance
captures under `out/oracle/`.

**No layer requires the original binaries at runtime anymore** except the optional emulation oracles
used for validation — the clean-room codec is verified bit-exact and the ISEF reader is stdlib-only.
