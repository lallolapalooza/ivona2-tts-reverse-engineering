# `out/oracle/` — reference outputs from the *real* IVONA engine under emulation

Ground truth for the synthesis pipeline, captured by executing the unmodified
ARM32 `libttsivonavoice.so` + `libvoice_en_us_kendra.so` under the Unicorn
harness `emu/armemu.py` (see `report_oracle.md`, `report_emulation.md`).
Nothing here is hand-written: every file is produced by `emu/tts_run.py`, and
each capture directory carries its own `cmdline.txt`.

## 1. Reproduction

```sh
cd <repo root>
~/venvs/re/bin/python emu/tts_run.py --level 3 --ret-probe \
    --sentence "Hello world this is a test" --out-dir out/oracle/ref_nopunct
```

`--level 3` writes PCM, `--level 1` stops after the voice handle, `--level 2`
starts the streamer.  `--ret-probe` enables the level-2 instrumentation (return
values of the control-flow functions, the 96-byte feature vectors, the candidate
lattice).  Runtime ≈7–11 min per utterance under the harness.

Plumbing the driver needs (all verified — `report_oracle.md` §2):

* `tts_init(cert)` → engine handle; `tts_load_voice(engine, so, obb)` → voice
  handle.  The plug-in is mapped at `--plugin-base` (default `0x20000000`) with
  relocations rebased because the harness' `dlopen`/`dlsym` are stubs.
* `IVONA_LANG_DAT_DIR=out/obb` must hold the language data.  The engine asks for
  `lang_<code>_<voice>.dat` and falls back to `lang_<code>.dat`; the shipped
  `patch.199….obb` contains only the fallback name, so
  `out/obb/lang_en_us_kendra.dat` is a byte-identical copy placed there to keep
  the engine's `errno` clean (the fallback is the production path).

## 2. Captures

| directory | sentence | status |
|---|---|---|
| `ref_nopunct/` | `Hello world this is a test` | **validated reference** — every token resolves (packed lexicon or working LTS) and there is no punctuation, so the chain is exactly `hh ax l ow \| w er l d \| dh ih s \| ih z \| ax \| t eh s t` (38 783 frames = 1.759 s @ 22050 Hz) |
| `ref_default/` | `Hello world, this is a test.` | correct words, but the `,` and `.` are additionally *spoken* as `comma`/`dot` (§5.1) |
| `ref_lexclean/` | `Hello, this is a comma dot.` | all tokens in the packed lexicon; same punctuation spell-out |
| `exp_nopunct/`, `exp_hello/`, `exp_punct2/` | bisection runs | evidence for §5 |
| `out/oracle/` (top level) | `Hello world, this is a test.` | **contaminated**: captured before the printf fix, so the LTS words `world`/`test` are missing.  Kept for the record only. |
| `clean_they/` | MagicGiraffe's capture | not produced by this ticket |

## 3. File → pipeline level

Levels: 1 = engine + voice handle, 2 = front-end/linguistic + selection,
3 = waveform/PCM.

| file | level | content |
|---|---|---|
| `trace.log` | 1–3 | driver log: handles, sample rate, the input text *as the engine received it*, per-chunk frame counts, `errno` |
| `cmdline.txt` | – | exact driver argv |
| `settings.txt` | 1 | voice parameters in force (`viterbi_beam`, `tb_min_distance`, `duration_stretch`, `pitch_stretch`, `amplify`, `compress`, `eng_*`, `sample_rate`, …) read from the plug-in's parameter store at runtime |
| `diphone_lookups.tsv` | 2 | linguistic diphone chain in graph order: `FUN_0005ef00(diphonedb, "<left>-<right>")` → `diphoneset_num` |
| `diphonedb_names.txt` | 2 | the voice's diphone table (section A): name + base duration per diphone index |
| `unit_feature_vectors.tsv` | 2 | one row per `FUN_00060ed4(item, out)`: the 96-byte feature vector (hex) + decoded string slots (`report_cost_terms_main.md` §4c names) — the cost model's input |
| `candidate_lattice.txt` | 2 | per chain position: diphone, diphone index, number of section-B candidate unit ids, `b_start`, the selected unit, its variant |
| `candidate_records.tsv` | 2 | every `FUN_0005f1dc(section-C record, out96)` call: raw 36-byte record + the 96-byte vector it decodes to (the candidate side of the target cost; two calls per Viterbi pair = p-side, n-side) |
| `viterbi_candidates.tsv` | 2 | after `FUN_0005fc04`: the engine's own per-candidate array (`state[4]`, stride `0xd4`, `+0xcc` ptr / `+0xd0` count, 20-byte entries `{+0 target cost, +8 total, +0xc diphone index}`) |
| `viterbi_calls.txt` | 2 | `FUN_0005fc04` entry registers per utterance |
| `pipeline_calls.txt` | 2 | utterance-stage runner invocations (`FUN_00064f38/…`) and pump calls |
| `unit_sequence.txt` | 3 | selected unit chain in `FUN_0005ef70` order: `unit_id, diphone, diphone_idx, variant, diphone_dur_ms, cum_ms` |
| `prosody_transforms.tsv` | 3 | per-segment `pitch_stretch` / `duration_stretch` / `amplify` actually applied (`FUN_00063540/62d14/62c54`) |
| `kendra_hello.pcm` / `.wav` | 3 | mono 16-bit PCM of the whole utterance (rate = `tts_voice_sample_rate(voice)` = 22050 Hz) |
| `token_stream.tsv` | 2 | **unusable** (§5.2) — kept because it is produced historically |
| `front_end_trace.txt` | 2–3 | function-entry census of both libraries (only with `--trace-dumps`) |

The voice registers no `resample_wave` parameter, so the chunk rate is the
output rate (no resampling happens).

## 4. Verified values

* `tts_init(cert 1798 B)` → `engine = 0x40006720` (RSA-4096 signature
  verification runs inside the real library; the tampered-certificate negative
  control fails — `report_emulation.md`).
* `tts_load_voice(...)` → voice handle; `tts_voice_sample_rate(voice)` = **22050 Hz**.
* `diphonedb`: `name = vox_en_us_kendra`, `checksum = 0x4F7C7A18`,
  `n_records = 1601` (0x641).
* `tts_streamer_start(voice, text, -1.0f)` — `-1.0f` means "certificate speed",
  i.e. no pacing.
* Frame counts / chains per capture: see `report_oracle.md` §3.

## 5. Defects found while building this (all in the harness unless noted)

1. **Punctuation is spoken by name (open).**  The plug-in's printable-ASCII
   symbol table (`.rodata`: "…asterisk, comma, dash, dot, oh, two…") is used to
   *pronounce* punctuation: `"Hello world, this is a test."` yields the extra
   words `comma` and `dot`.  `ref_nopunct/` avoids the path entirely.
   (`[INFERENCE]` the same "symbol with no reading" fallback that used to swallow
   the LTS words.)
2. **`token_stream.tsv` decodes the wrong object** — the hooked argument of
   `FUN_0006706c` is the utterance object, not a `Token`, so the decode walks the
   voice parameter list.  Use `diphone_lookups.tsv` and
   `unit_feature_vectors.tsv` instead.
3. **First `unit_feature_vectors.tsv` row** of each capture is an all-zero vector
   for the very first `FUN_00060ed4` call (the return-address probe fired once
   before the write).  Rows carry the item pointer and the raw hex, so filter on
   those; every later row holds the real vector.
4. Two harness bugs had to be fixed for levels 1–3 at all (details and evidence
   in `report_oracle.md` §2): the `atol` conversion base (blocked
   `tts_load_voice`), the non-re-entrant nested `emu_start` in `qsort` (blocked
   the Viterbi), and the `%.*s` formatter (swallowed every out-of-lexicon word).
