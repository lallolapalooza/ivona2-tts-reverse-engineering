# Replication handbook — build order, inputs, acceptance tests

Purpose: let an agent with **no access to the original binaries** build a functionally equivalent
IVONA 2 text-to-speech system, and know at every step how to prove it is correct.
Everything referenced lives under `/home/asdf/Downloads/ivona_re/`.

Legend: ✅ = documented well enough to implement today; 🟡 = documented with a named residual risk;
📄 = source document; 🧪 = executable check you can run now.

---

## 0. Toolchain and inputs

* Python 3.13 + venv `~/venvs/re` (`pip install unicorn pyelftools numpy androguard capstone`);
  the emulation route additionally needs the Ghidra dumps for symbol resolution only.
* Original artifacts (read-only): the three APKs, the two voice OBBs + patches, `out/libs/*` (native
  libraries), `out/obb/lang_*.dat` (lexicons), `out/certs/ivona_certificate_decoded.txt`.
* Reference decompilations: `out/ghidra_dump/{decompiled.c, libttsivonavoice.c, libtiver.c,
  libvoice_kendra.c}` — Ghidra address = ELF vaddr + 0x10000.
* Entry document: `IVONA2_REVERSE_ENGINEERING.md` (architecture, contracts, evidence index).

---

## 1. Data layer — package/voice discovery, OBB container, packaging rules  ✅

📄 `report_engine_app.md` §5, `report_obb_format.md` (538 L), `report_libtiver.md`,
`report_voice_pack.md`, `IVONA2_REVERSE_ENGINEERING.md` §4–§5.
🧪 Reference implementation `refimpl/` (`cdxv.py`, `voices.py`, `license.py`, `marks.py`,
`params.py`) + 74 conformance tests:

```sh
python3 -m unittest discover -s refimpl        # OK (74 tests, ~8 s)
```

You are done with this step when your code reproduces: 426 991 / 404 847 unit entries per voice,
1 601 / 1 772 diphones, 58 / 62 phonemes, exact OBB byte sizes (152 219 597 / 149 905 560),
the `ivona_pkgs.csv` column rules, the selection file name `.<iso3lang>_<iso3country>`, and the
license XOR decode byte-for-byte.

## 2. Lexicon layer (`lang_*.dat`, `ISEF`)  ✅

📄 `report_isef.md`; 🧪 `scripts/isef_decrypt.py`.
Container: `"ISEF" | u32be 1 | u32be buildid | 512-B RSA-4096 block (public-key recovery of a
64-byte AES-256 key ‖ IV) | AES-256-CBC ciphertext of the section table`.
Test:

```sh
python3 scripts/isef_decrypt.py out/obb/lang_en_us.dat --sections   # 4 sections, 660 rules
python3 scripts/isef_decrypt.py out/obb/lang_en_us.dat --entries | head
```

Cross-checked against the engine itself: `emu/run.py --func FUN_000346d4 …` produces a
byte-identical 74 137-byte plaintext (`report_emulation.md`).

## 3. Acoustic decoder (the "gap" payload → PCM)  🟡

📄 `report_gap_codec.md`; 🟡 `report_codec_spec.md` (stage map + golden vectors + partial port).
Two valid routes:
* **Emulation route (works today)**: `scripts/decode_unit.py --record 3 --out u3.wav` decodes a unit
  to PCM by running the engine's own `LAB_00067db8`/`FUN_00067a14` path under Unicorn.
  🧪 Acceptance: sample count == `ramp[N−1]`; bit-exact vs the engine driver (`--verify`);
  speech-like output (record 3: F0 ≈ 134–138 Hz).
* **Clean-room route (complete, verified)**: `report_codec_spec.md` + `scripts/codec_probe.py` give the
  stage decomposition (parse → dequant → setup → gain → xform → post), the static table dump
  (`out/codec/tables.bin`, sha256 `ac5d586a…`) and **golden per-stage vectors**
  (`out/codec/steps/rec*.pkl`). The `setup` stage is already ported bit-exactly
  (`scripts/codec_parts/setup.py`; `test_setup.py` → 60/60 vectors byte-identical). Remaining:
  parse/Huffman, dequant, gain, xform/MDCT, post — each validated against its snapshot.
  🧪 Acceptance: `scripts/decode_unit.py --rate 22050` reproduced bit-exactly for ≥50 units of both
  voices.

You are done when the decoder produces PCM for arbitrary units of the *shipped* voices, with the
sample count explained by the record's own fields.

## 4. Synthesis: text → phonemes → prosody → unit selection → splice → PCM  🟡

📄 `report_frontend.md` (G2P ✅ verified; prosody/Viterbi 🟡 structural),
`report_segmentation.md` (ramp[]/slicing/splicing ✅ verified; transforms 🟡),
`report_engine_synth.md` (1 376 L pipeline map with addresses),
`report_oracle.md` (reference run of the real engine for A/B — being produced).

Sub-steps and their evidence:
1. **SSML + text normalisation**: element table + the three PCRE lexicon sections applied in
   `prm_lex_list` order → `report_frontend.md`.
2. **Grapheme→phoneme** ✅: packed lexicon lookup (`scripts/lex_decode.py`) + LTS FSM
   (`scripts/lts_decode.py`) — both cross-checked against the engine (`scripts/probe_g2p.py`):
   `hello → hh ax l ow1` (lexicon) and `kendra → k eh1 n d r ax` (LTS) match exactly.
3. **Prosody + unit selection** 🟡: join cost (5 context variants) and target cost are
   **bit-exactly reimplemented and validated** (`scripts/prosody.py`, `scripts/probe_prosody.py`,
   `report_prosody.md` §1–§2); the duration model is a decoded CART (`zdur_cart` blob: 44 phones,
   3951 nodes / 1584 leaves, Festival-style equality questions, leaf = `(leaf16*std ± 500)/1000 + mean`);
   pause rules transcribed; Viterbi (20-byte candidate entries, 51-bucket histogram beam 50/25,
   backpointers) implemented in `scripts/select_units.py`; intonation only assigns a phrase-final
   `endtone` (no parametric F0 in this voice — pitch lives in the units and is scaled by
   `pitch_stretch`).
4. **Splicing** ✅: `ramp[]` = cumulative segment marks (`pms`), block `i` = `PCM[ramp[i−1]:ramp[i]]`;
   splice = crossfade `L = min(prev tail, len(block0))` with the 17-point raised-cosine window
   (tables bit-exact); `flag=0` holds/drops the last segment as documented —
   `scripts/segment_unit.py --verify-engine/--verify-splice/--verify-finalize` all PASS with
   **0 sample differences** (`report_segmentation.md`).
5. **Rate chain**: codec 24 000 Hz → wave tag 22 050 Hz via `resample_wave` (`FUN_00059958`) →
   `report_segmentation.md`.

**Current state (verified):** `refimpl/tts.py --text "hello world" --out x.wav --verify-engine`
produces a WAV and reports `BIT-EXACT` when the *same unit chain* is re-spliced through the real
library (`27102/27102` samples, `0 diffs`); `--check-tables` verifies `418495/418495` diphone
instances, `--check-g2p` matches the lexicon/LTS reference. Deviations from the engine are
explicitly listed in `report_pipeline.md` (no Viterbi — a documented heuristic replaces it; no
prosody/pitch/duration transforms; no SSML/ISEF rewrite; the codec is emulated, with a single
drop-in point in `tts.py:synth`).

**Measured state:** the duration model and Viterbi costs are wired in; the diphone chain is **19/19
identical** to `out/oracle/ref_nopunct/`, durations are byte-identical per segment, target costs are
**100 %** exact on interior candidate rows (given the engine's `ssyl_*`), and the audio is +5.7 %
duration with envelope correlation 0.44. Remaining causes are enumerated in `REPLICATION_STATUS.md`
§4 (beam/pruning rule, chunked search, `ssyl_from/to`, `gpos`).

Acceptance for the full step: with the prosody model (`report_prosody.md`) and the clean-room codec
(`report_codec_spec.md`) in place, the pipeline's PCM should match a sentence-level engine reference
(`report_oracle.md`) rather than only matching for a given unit chain. **Reference captures:** use `out/oracle/ref_nopunct/` (`"Hello world this is a test"`) — punctuation-free, because the engine *speaks punctuation by name* (`,` → `comma`, `.` → `dot`). Each capture ships `unit_feature_vectors.tsv` (96-byte features), `candidate_lattice.txt` / `candidate_records.tsv` and `viterbi_candidates.tsv` (the engine's own per-candidate costs): reproduce those costs first, then the chosen sequence, then the audio.

## 5. Android shell + voice packs  ✅

📄 `report_engine_app.md` (770 L), `report_voice_pack.md` (422 L), `report_libtiver.md`.
Implement: `IVONATextToSpeechService` (TTS_SERVICE + `tts_engine.xml` settings activity), the
`CHECK_TTS_DATA` / `INSTALL_TTS_DATA` / `GET_SAMPLE_TEXT` activities, package discovery through the
shared UID, `ivona_pkgs.csv` cache, the `libtiver`-equivalent OBB validation (name + exact size),
patch extraction, and the voice-pack APK template (manifest + `libvoice_*.so` + OBB).
🧪 Acceptance: `adb shell settings`-level binding works, i.e. Android's TTS settings list the engine,
`CHECK_TTS_DATA` reports the voice installed, and `TextToSpeech.speak()` yields audio.

---

## 6. Progress tracker

| step | doc | status | blocking item |
|---|---|---|---|
| 1 data layer | `report_obb_format.md`, `refimpl/` | ✅ done, tested | — |
| 2 lexicon | `report_isef.md` | ✅ done, verified vs engine | — |
| 3 decoder | `report_gap_codec.md`, `report_codec_spec.md` | 🟡 emulation route verified bit-exact; clean-room 1 of 6 stages ported (setup 60/60) | parse/Huffman, dequant, gain, xform, post |
| 4 synthesis | `report_pipeline.md`, `report_prosody.md`, `report_frontend.md`, `report_segmentation.md` | 🟡 **functional pipeline working** (text→WAV); G2P ✅, segmentation+splicing ✅ (0 diffs), **join+target costs ✅ bit-exact** (`scripts/prosody.py`, 15000/15000 validated), duration CART **✅ now wired and byte-identical to the engine's per-segment durations**, Viterbi + engine prosody wired (`refimpl/tts.py --select viterbi`, see `report_pipeline.md` §10) | `ssyl_from/to` rule, first/last-node cost inputs, engine's chunked total-beam search, intonation plugin rule |
| 5 Android shell | `report_engine_app.md`, `report_voice_pack.md` | ✅ documented | device test (none available here) |

**Shared modules changed by the engine-match work** (`report_pipeline.md` §10):
`scripts/prosody.py` (`Cart.question` is now type-tolerant for the CART's
string-valued features such as `position_type`/`gpos`/`seg_onsetcoda`; the leaf
value uses C truncation toward zero, which the earlier floor division got wrong by
1 ms for negative leaves; `pause_duration(..., base=…)` takes the voice's
`pause_base_len`), `refimpl/tts.py` (new `--select viterbi` default + `--beam`),
new `scripts/phoneset.py`, `scripts/diphone_vec.py`, `scripts/compare_selection.py`,
`scripts/compare_costs.py`, `scripts/probe_record_vec.py`,
`refimpl/engine_prosody.py`. Nothing in `emu/` was modified by this work.

## 6.1 Oracle status (blocked, documented)

`emu/tts_run.py` drives the real engine under emulation and already reaches
**level 1a** — `tts_init(cert)` returns an engine handle (`0x40006720`).
`tts_load_voice(...)` then fails with `errno=4`, message `Failed to load voice`, so levels 2–3
(front-end intermediates, utterance PCM) are not yet available; the precise trace is in
`out/oracle/trace.log` and the task-relevant blockers (plugin mapped at a rebased address, its
`register_voice` path, vox-file stubs) are the next things to fix. Until then, ground truth is
available per component: `emu/run.py` (ISEF, certificate), `scripts/decode_unit.py` (units),
`scripts/segment_unit.py` (segmentation/splice), `scripts/probe_g2p.py` (G2P).

## 7. Definition of "fully reimplemented"

A port is complete when, for a fixed text (plain and SSML), it produces speech whose
(a) phoneme/duration/unit decisions match the oracle's captured intermediates, and
(b) PCM matches the oracle audio within the documented tolerance — using only the artifacts in this
directory plus the specs, with no original binary required at runtime. Until the clean-room codec
spec and the prosody/oracle levels are finished, the intermediate fallback is to link the emulated
modules from `emu/`, which already satisfies (b) bit-exactly for unit decoding and ISEF.
