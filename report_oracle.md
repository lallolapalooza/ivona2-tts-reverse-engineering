# Oracle — running the real engine under emulation (status: **working**, levels 1–3 captured)

Goal: execute the original ARM engine in the Unicorn harness so any
reimplementation can be diffed against reference outputs. Driver: `emu/tts_run.py`
(documented in `emu/README.md`, `report_emulation.md`); artefacts under
`out/oracle/` (see `out/oracle/README.md` for the file → pipeline-level map).

## 1. What works

```sh
~/venvs/re/bin/python emu/tts_run.py --level 3 --ret-probe \
    --sentence "Hello world, this is a test." --out-dir out/oracle/ref_default
```

| level | result |
|---|---|
| 1 | `tts_init(cert 1798 B)` → `engine = 0x40006720`; `tts_load_voice(engine, libvoice_en_us_kendra.so, main.199….obb)` → voice handle; `tts_voice_sample_rate` = **22050 Hz** |
| 2 | front end runs end to end: tokenisation → G2P (packed lexicon + LTS) → diphone graph → Viterbi → unit selection; intermediates dumped (see below) |
| 3 | `tts_streamer_synth0` loop → **PCM**: `ref_default` 53 649 frames = **2.433 s** @ 22050 Hz; `ref_lexclean` 49 292 frames = 2.235 s |

Everything below the API surface is the *unmodified* library; only libc/bionic
imports are Python stubs, and the voice plug-in is mapped into the same emulated
address space at `--plugin-base` because the harness' `dlopen`/`dlsym` are ours.

## 2. What had to be fixed to get there

Four defects in the plumbing, in the order they surfaced (each was located by
tracing the *argument* of the engine's own error path, not by guessing):

1. **`errno 4` "Failed to load voice"** — the plug-in's `FUN_00028310` compares
   `atol(checksum)` with the CDXV header checksum. `emu/armemu.py` registered
   `atol` as `strtol`, which read `r2` (garbage for a 1-argument call) as the
   conversion base, hit `int(s, 0x182e8d8)` → `ValueError` → returned 0, so the
   comparison `0 == 1333557784` failed and the plug-in discarded the voice file.
   Fix: `atol`/`atoi` are base-10 C conversions (`_int_prefix`); `strtol`
   validates its base. This was the level-1a→1b blocker.
2. **Stale `errno` masking the next failure** — `tts_load_voice` probes
   `lang_<code>_<voice>.dat` first and falls back to `lang_<code>.dat`. The
   shipped `patch.199….obb` contains only `lang_en_us.dat`, so the first probe
   always fails and leaves `errno = 9 "File not found: …lang_en_us_kendra.dat"`
   set even though the fallback succeeds. Copying the file to the voice-specific
   name (identical bytes) keeps `errno` clean; **this is not a functional
   difference** — the fallback is the production path.
3. **`tts_streamer_synth0` returned 0 frames** — `FUN_0005fc04` (Viterbi) ends
   its node-cost pass with `qsort(node_candidates, n, 0x14, LAB_0005fa64)`.
   `emu/tts_run.py` sorted by calling the *emulated* comparator through a nested
   `uc.emu_start`; Unicorn 2.1 is not re-entrant (verified with a synthetic
   program: the outer run resumes with a corrupted PC / is killed by the inner
   `emu_stop`), which aborted the whole synthesis call. The driver now
   re-implements the comparators in Python — the two used here are
   `u32@+0` (`LAB_0005fa44`, also the plug-in's `LAB_0002ee1c`) and `u32@+8`
   (`LAB_0005fa64`), both unsigned, stride `0x14`; sorting is stable, matching
   glibc's merge sort. Unknown comparators raise loudly.
4. **Words missing from the packed lexicon were silently dropped** — the
   plug-in's letter-to-sound fallback builds its rule context with
   `sprintf("%.*s…")`, and the harness' formatter ignored `.*` (it also never
   consumed the `*` argument, shifting every following argument). Fix:
   `ArmLib._c_format` now parses flags/width/precision (including the `*` forms),
   length modifiers and the full conversion set; it backs
   `printf/sprintf/snprintf/fprintf/vsprintf/vsnprintf/vfprintf`. With it,
   `"Hello world"` produces `hh ax l ow w er l d` instead of only `hh ax l ow`.

## 3. Captured values (reproducible)

| capture | sentence | diphone chain (phones) | PCM |
|---|---|---|---|
| `out/oracle/ref_nopunct/` **(recommended reference)** | `Hello world this is a test` | `hh ax l ow w er l d dh ih s ih z ax t eh s t` | 38 783 frames = **1.759 s** |
| `out/oracle/ref_default/` | `Hello world, this is a test.` | `hh ax l ow w er l d k aa m ax dh ih s ih z ax t eh s t d aa t` | 53 649 frames = 2.433 s |
| `out/oracle/ref_lexclean/` | `Hello, this is a comma dot.` | `hh ax l ow k aa m ax dh ih s ih z ax k aa m ax d aa t d aa t` | 49 292 frames = 2.235 s |
| `out/oracle/` (older, pre-fix harness) | `Hello world, this is a test.` | `hh ax l ow k aa m ax dh ih s ih z ax d aa t` | 34 724 frames = 1.575 s |

`ref_nopunct` is the cleanest acceptance target: every token resolves (packed
lexicon or working LTS), no punctuation, so the chain is exactly the intended
phone sequence `hh ax l ow | w er l d | dh ih s | ih z | ax | t eh s t`.
`ref_default`/`ref_lexclean` differ only by the punctuation tokens that the
plug-in spells out as `comma`/`dot` (§4).

Voice parameters in force (`out/oracle/ref_default/settings.txt`):
`viterbi_beam = 25`, `tb_min_distance = 6`, `duration_stretch = pitch_stretch =
amplify = compress = 1.0`, `eng_sentence_break = 0.4 s`, `eng_paragraph_break =
0.65 s`, `eng_max_sentence = 1000`, `eng_max_word = 100`, `pause_base_len = 0`,
`eng_input_type = ""` (plain text → wrapped in a synthetic `<speak>`),
`sample_rate = 22050`, `eng_version = 1.6.23`. `tts_streamer_start` is called
with `speed = -1.0f`, i.e. the certificate's rate (no pacing).

Intermediates (all under each capture directory): the linguistic diphone chain
(`diphone_lookups.tsv`), the 96-byte feature vector per graph node
(`unit_feature_vectors.tsv`, slot names from `report_cost_terms_main.md` §4c),
the candidate lattice per position (`candidate_lattice.txt`), every
section-C record → 96-byte vector decode (`candidate_records.tsv`), the engine's
own per-candidate costs after `FUN_0005fc04` (`viterbi_candidates.tsv`), the
selected unit chain (`unit_sequence.txt`), and the applied prosody factors
(`prosody_transforms.tsv`).

## 4. Remaining defects / caveats

* **Punctuation is spoken by name.**  The chain for `ref_default`/`ref_lexclean`
  contains the words `comma` and `dot` where the input has `,` and `.` — i.e. the
  plug-in's printable-ASCII symbol table (`.rodata`, "…asterisk, comma, dash,
  dot…") is used to *pronounce* the punctuation.  A sentence without punctuation
  (`out/oracle/ref_nopunct/`, `"Hello world this is a test"`) has no such
  tokens, so it is the cleanest acceptance target; the punctuation path still
  needs bounding (it is the same "symbol without a reading" fallback the LTS
  words used to hit).
* **`token_stream.tsv` is not usable** — the hooked argument of `FUN_0006706c`
  is the utterance object, not a `Token`, so the feature decode walks the voice
  parameter list.  Use `diphone_lookups.tsv` + `unit_feature_vectors.tsv`
  instead; a per-token dump would need the Token relation walk.
* **`unit_feature_vectors.tsv` first row** (per capture) is an all-zero vector
  for the first `FUN_00060ed4` call — the probe's return-address heuristic fired
  once before the write; all later rows carry the real vector (rows are labelled
  with the item pointer and the raw hex, so filter on that).
* **Wall time**: 7–11 min per utterance under the harness (one instruction-level
  Python hook); `tts_init` alone is ~50 s (RSA-4096 verification inside the real
  library).
* **qsort**: only the "sort 20-byte records by a u32 key" family is
  re-implemented; a comparator outside that family aborts with a clear
  `EmuError` rather than corrupting the run.
* Not attempted here: `--ssml` input, `tts_streamer_synth` (marks mode), the
  Android-app/`libttsivona.so` layer.

## 5. Ground truth available meanwhile (per component)

| component | tool | verified |
|---|---|---|
| ISEF lexicon decrypt | `emu/run.py --func FUN_000346d4` | byte-identical to `scripts/isef_decrypt.py` |
| certificate verification | `emu/run.py --func tts_init` | positive + tampered negative control |
| unit decode (gap → PCM) | `scripts/decode_unit.py` | engine path == driver, bit-exact; length == `ramp[N−1]` |
| segmentation / splice / finalize | `scripts/segment_unit.py --verify-*` | 0 sample differences |
| G2P (lexicon + LTS) | `scripts/probe_g2p.py` | matches `scripts/lex_decode.py` / `lts_decode.py` |
| codec stage port | `scripts/codec_probe.py` + `out/codec/steps/*.pkl` | `setup` stage 60/60 vectors byte-identical |
