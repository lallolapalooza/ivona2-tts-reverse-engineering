# Session inventory — where everything lives

Everything produced by this reverse-engineering session now lives under
`/home/asdf/Downloads/ivona_re/` (≈465 MB incl. `scratch/`). The original archive
`/home/asdf/Downloads/IVONA 2-20210318T191653Z-001.zip` is untouched, and **nothing session-related
is left in `/tmp`** (verified by grepping `/tmp` for `kendra`, `CDXV`, `ttsivona`, `ivona_re` — no
hits).

## Top level

| path | what |
|---|---|
| `IVONA2_REVERSE_ENGINEERING.md` | entry document (architecture, contracts, evidence index) |
| `REPLICATION_STATUS.md` | per-layer verdict + verification evidence + residual causes |
| `REPLICATION_HANDBOOK.md` | build order, docs per step, acceptance tests |
| `report_*.md` (20 files) | the layer reports (`engine_synth` 103 k, `engine_app` 67 k, `libvoice` 45 k, `voice_pack` 46 k, `prosody` 36 k, `obb_format` 29 k, `engine_api` 41 k, `pipeline` 30 k, `codec_spec` 23 k, `emulation` 23 k, `libtiver` 27 k, `ttsivona` 19 k, `refimpl` 17 k, `cost_terms_main` 16 k, `gap_codec` 11 k, `oracle` 8.5 k, `segmentation` 8.3 k, `isef` 5.3 k, `frontend` 5.5 k) |
| `scripts/ghidra/` | the two Ghidra headless post-scripts used throughout: `DumpDecompilation.java` (bulk: decompile every function of a program into one `.c`) and `DecompAt.java` (targeted: decompile specific addresses, creating functions Ghidra skipped). Invoke with `-scriptPath scripts/ghidra -postScript <script> <out> [addr…]` |
| `scripts/` | 49 Python tools + Ghidra scripts (**`verify_all.py` — one-command validation of every layer**, `decode_unit.py`, `codec_spec.py`, `codec_parts/`, `prosody.py`, `probe_prosody.py`, `select_units.py`, `segment_unit.py`, `isef_decrypt.py`, `lex_decode.py`, `lts_decode.py`, `probe_g2p.py`, `compare_tts.py`, `verify_codec.py`, `cost_inventory.py`, `litstrings.py`, `DecompAt.java`, `cost_inventory.py`, …) |
| `refimpl/` | reference implementation: `cdxv.py`, `voices.py`, `license.py`, `marks.py`, `params.py`, `engine_prosody.py`, `tts.py` + `test_conformance.py` (74 tests) |
| `emu/` | ARM32/bionic Unicorn harness: `armemu.py`, `run.py`, `probe_gap.py`, `tts_run.py`, `README.md`, `evidence/` |
| `out/` | all derived data and oracles — see below |
| `scratch/` | session leftovers swept in from `/tmp` and superseded directories (see below) |
| `IVONA 2/` | the extracted original archive (read-only source material) |

## `out/` (derived data, evidence, oracles)

* `out/jadx_tts/`, `out/jadx_tts_res/`, `out/jadx_kendra/`, `out/jadx_amy/` — decompiled Java/res
* `out/tts/`, `out/libs/{kendra,amy}/` — extracted native libraries
* `out/ghidra_dump/*.c` — Ghidra decompilations (`decompiled.c`, `libttsivonavoice.c` 3.8 MB, `libtiver.c`, `libvoice_kendra.c`) plus recovered functions (`gap_bridge.c`, `gap_engine.c`, `gapdec.c`, `intonation_decomp.c`, `phrase_endtone.c`)
* `out/ghidra{,_v,_t,_l}/` — Ghidra projects (re-runnable)
* `out/obb/` — decrypted/extracted lexicon files (`lang_en_us.dat` + `.dec.bin`, `lang_en_gb.dat` + `.dec.bin`, `<voice>-suffixed` copies), region dumps, carved records
* `out/codec/` — static table dump (`tables.bin`, sha256 `ac5d586a…`), per-stage golden snapshots (`steps/rec*.pkl`)
* `out/gap/` — decoded unit audio (WAVs + spectrogram)
* `out/oracle/` — engine captures: **`ref_nopunct`** (acceptance reference, 38 783 samples @ 22 050 Hz), `ref_default`, `ref_lexclean`, bisection experiments, plus per-capture `settings.txt`, `unit_feature_vectors.tsv`, `candidate_lattice.txt`, `candidate_records.tsv`, `viterbi_candidates.tsv`, `unit_sequence.txt`, `prosody_transforms.tsv`, `kendra_hello.{pcm,wav}` and `README.md`
* `out/tts_demo/` — functional pipeline demos (WAV + JSON + analysis + spectrograms)
* `out/certs/` — APK signing certs + the decoded IVONA certificate

## `scratch/` (swept in during this cleanup)

| item | origin | why kept |
|---|---|---|
| `tmp_evidence/` | `/tmp` (agent scratch: comparison WAVs `cs*`/`du*`/`emu*`/`fe*`/`fs*`/`mg_*`, diagnostics `ltp_*.json`, `exc_stages.json`, `fir_regs.json`, `recheck.*`, Ghidra logs `decomp*.log`, `gh[1-6].log`, `*/gsp/DecompAt.java`, `run_decomp.sh`, disassembly dumps, `codec_steps/` snapshots, `certchk/`) | every intermediate that had evidence value; the rest was reproducible |
| `evidence_jadx_badcode/` | `/tmp/ivona_bad` | jadx `--show-bad-code` output used to recover the activation-socket protocol |
| `superseded_ghidra_script_dirs/` | `ghidra_scripts/`, `gs2/` | earlier scratch `-scriptPath` dirs. Ghidra compiles a script into an OSGi bundle keyed by its **directory**, so a failed compile poisons that directory ("Failed to get OSGi bundle containing script"); every retry therefore used a fresh dir (`gs`…`gs5`). Only the two working ones mattered; they are now consolidated into `scripts/ghidra/` |
| `ghproj_c210e/`, `gsp/` | `/tmp` | extra Ghidra project/scripts used during the cost-model work |
| `local_prosody_costs_main.md` | working dir (duplicate) | the copy that was published for the prosody agent; `report_cost_terms_main.md` is the canonical file |

## External dependencies (not session files, deliberately outside the tree)

| item | purpose | version |
|---|---|---|
| `~/venvs/re` | Python venv used by every script: `androguard` (DEX analysis), `capstone` (ARM disassembly), `unicorn` + `pyelftools` (the emulation harness), `numpy` | androguard 4.1.4, capstone 5.0.7, unicorn 2.1.4 |
| `~/tools/jadx` | Java decompiler used for the APKs | jadx 1.5.1 |
| `/opt/ghidra` + `~/.config/ghidra/ghidra_12.1.2_DEV` | headless decompilation, script compile cache | Ghidra 12.1.2 DEV |
| ghidra-log | projects created by this session are the ones under `out/ghidra*` and `scratch/ghproj_c210e` | — |

Reproduce the toolchain with: `python3 -m venv ~/venvs/re && ~/venvs/re/bin/pip install androguard
capstone unicorn pyelftools numpy` and `unzip jadx-1.5.1.zip -d ~/tools/jadx`.

## Safety note: what is *not* under version control

The public repo tracks the analysis (docs, `scripts/`, `refimpl/`, `emu/`, decompilations, oracle
metadata). The following exist **only in this working tree** and are excluded by `.gitignore` on
purpose (size and/or third-party rights):

`IVONA 2/` (the extracted product assets), `out/obb/`, `out/gap/`, `out/tts_demo/`,
`out/certs/*.rsa`, `out/ghidra*/` project databases, `scratch/`, and all generated audio/images.

Recovery if they are ever lost:

| asset | how to restore |
|---|---|
| `IVONA 2/` (APKs, OBBs, libs, store manifests) | re-extract the original archive: `unzip -o "~/Downloads/IVONA 2-20210318T191653Z-001.zip" -d .` (verified: restores the OBBs at exactly 152 219 597 / 149 905 560 bytes) |
| `out/obb/` (decrypted lexicons, carved regions) | `scripts/isef_decrypt.py` on the patch OBBs + `scripts/01_…13_*.py` carving (see `report_obb_format.md` §0) |
| `out/gap/`, `out/tts_demo/` (audio) | `scripts/codec_spec.py --record N --rate 22050 --out …`, `refimpl/tts.py --text … --out …` |
| `out/certs/*.rsa` | `unzip -p "<apk>" META-INF/CERT.RSA > …` |
| `out/ghidra*/` projects | `scripts/ghidra/*.java` via `ghidra-analyzeHeadless` (see §Top level) |
| `scratch/` | not needed for any verification; it was swept-in scratch |

A full validation of everything that is tracked runs in one command: `python3 scripts/verify_all.py`
(`--quick` for a smoke subset). Nothing in that suite depends on the untracked assets **except** the
checks that read the APKs/OBBs (`refimpl-tests`, `codec-*`, `prosody-costs`, `segmentation*`, `pipeline`).

## Session transcript

`omp-session-2026-10-09T16-01-55-252Z_01a12166-4e34-7019-8b73-be8734657cce.html` (≈65 MB) is the
full HTML transcript of the assistant session that produced this analysis: every tool call, command,
result and report draft, in order. It is the raw record behind the documents in this directory —
useful when a report's claim needs to be traced back to the exact command and output that produced
it. It was scanned for credentials/keys before publication (none present).
