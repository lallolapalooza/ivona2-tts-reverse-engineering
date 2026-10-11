# IVONA 2 TTS — complete reverse engineering (analysis + tooling)

A from-scratch reverse engineering of the **IVONA 2 Android text-to-speech stack** (the
`com.ivona.tts` engine app, the `com.ivona.tts.voicebeta.*` voice packs, and their Google-Play
expansion data), documented and tooled to the point where **another engineer or agent can
reimplement the whole system** — including reading the shipped voice data.

Everything here is derived from static analysis (jadx, Ghidra) plus a custom ARM32/bionic
**Unicorn emulator** that runs the original libraries as a ground-truth oracle.

> **Not affiliated with, endorsed by, or sponsored by IVONA Software or Amazon.** Trademarks are used
> only to identify the subject of the analysis. **No third-party binaries or voice data are
> redistributed** — see *Legal and scope* below.

---

## Headline results

| layer | state | strongest evidence |
|---|---|---|
| Android shell, voice packs, package discovery, packaging rules | ✅ reimplemented | `refimpl/` passes **74 conformance tests** against the real APK/OBB metadata |
| `CDXV` voice container (header, index, 5 sections, diphone/unit records) | ✅ byte-level spec + reader | invariants verified over both shipped voices (426 991 / 404 847 units) |
| Lexicon container `ISEF` (RSA-4096 public-key recovery + AES-256-CBC) | ✅ cracked, stdlib decryptor | the engine's own decrypt routine run under emulation produces a **byte-identical** 74 137-byte plaintext |
| Acoustic codec (proprietary fixed-point MDCT + Huffman, `u16le`-framed packets, self-keyed XOR) | ✅ clean-room port | per-stage **55/55** byte-identical (336 calls / 1 344 buffers); end-to-end **59/59 records bit-identical** per voice at 22 050 and 24 000 Hz |
| Grapheme→phoneme (packed lexicon + letter-to-sound FSM) | ✅ reimplemented | matches the plug-in when driven under emulation |
| Unit segmentation / splicing / finalisation | ✅ reimplemented | engine vs model: **0 sample differences** |
| Prosody: join cost (5 context variants), target cost, dispatcher, duration CART, pauses | ✅ reimplemented | `probe_prosody.py` → **15 000/15 000 bit-identical** |
| Engine API, handles, certificate, speech marks | ✅ spec + reference | certificate verify positive/negative control under emulation |
| Streaming contract: 0.3 s pull loop, `min(want,pos)` finalise with the tail riding the slide, concat flags, `pau`-window SOLA restretch | ✅ reproduced | per-call pull counts identical to the engine's trace (`6615×5+5708`, `6615×8+729`, `6615×7+2987`); restretch verified pass-by-pass |
| Unit selection: candidate build, 51-candidate beam with context exemptions, `tb_min_distance` forced nodes, chunked search | ✅ reimplemented | **kept sets, both flag bytes and unit-id sequences match the instrumented engine 19/19 / 26/26 / 25/25 (70/70)**; chunk boundaries identical |
| Context features: `ssyl_from/to`, `gpos`, edge-node slots | ✅ recovered | target cost **21 152/21 152 exact** over three captures with per-node `\|d\|` = 0/0/0 |
| Punctuation spoken by name | ✅ reimplemented | plug-in's 200-name table, `symbol_names.py --verify` **200/200**; chains identical |
| Whole-utterance integration | ✅ **audio matches the engine** | diphone chain, unit ids, concat flags, chunk boundaries and per-call pull counts all exact; the engine's `pau`-window SOLA restretch (`FUN_00062d14`) is implemented and verified pass-by-pass. Result: **`ref_nopunct` and `ref_lexclean` BIT-EXACT (0 differing samples), `ref_default` within 69 samples (0.13 %) at one crossfade seam** — 0 ms lag, envelope correlation 1.0000, 100 % of frames within ±3 dB. `REPLICATION_STATUS.md` §4 |

The engine itself runs under emulation (`emu/tts_run.py`): levels 1–3 (init → certificate → voice
load → front end → **PCM**) with captured references, including per-candidate Viterbi costs, in
`out/oracle/`.

## Start here

| document | purpose |
|---|---|
| **`REPLICATION_STATUS.md`** | per-layer verdict with the verification evidence and the remaining causes of divergence |
| **`REPLICATION_HANDBOOK.md`** | build order for a reimplementation, with the acceptance test at each step |
| `IVONA2_REVERSE_ENGINEERING.md` | architecture, component/JNI/vtable contracts, data layouts, evidence index |
| `INVENTORY.md` | what every directory/file is, how the toolchain is set up, and how to restore the assets that are deliberately not in the repo |
| **`scripts/verify_all.py`** | one command that re-runs every layer verification (12 checks) and prints a PASS/FAIL table — `--quick` for a smoke run |
| `report_*.md` (20 files) | the detailed layer reports (engine internals, OBB format, codec, prosody, oracle, emulation, …) |

## Repository layout

```
report_*.md                 layered reverse-engineering reports (≈9 k lines total)
IVONA2_REVERSE_ENGINEERING.md   entry document
REPLICATION_STATUS.md       per-layer verdict + residuals
REPLICATION_HANDBOOK.md     build order + acceptance tests
INVENTORY.md                file-by-file map of the project
scripts/                    analysis + decoder toolchain (48 Python tools)
scripts/ghidra/             Ghidra headless post-scripts (bulk dump / targeted decompile)
refimpl/                    reference implementation of the data layers + 74 conformance tests
emu/                        ARM32/bionic Unicorn harness (runs the original libraries)
out/ghidra_dump/            Ghidra decompilations (text) of the native libraries
out/oracle/                 captured engine ground truth (chain, feature vectors, Viterbi costs)
out/codec/                  codec table dump + per-stage golden snapshots
```

## Reproducing

Tools used: `jadx` 1.5.1, Ghidra 12.1.2, a Python venv with `androguard`, `capstone`, `unicorn`,
`pyelftools`, `numpy` (the emulation harness needs `unicorn` + `pyelftools`; the clean-room decoder
needs only the standard library).

1. **Supply your own copy** of the IVONA 2 archive (engine APK + a voice pack APK + its OBB
   expansions — these are *not* in this repo). Unpack it next to this tree, e.g. `IVONA 2/`.
2. Decompile the APKS: `jadx -d out/jadx_tts "<engine>.apk"`.
3. Decompile the native libraries with Ghidra headless, e.g.
   `ghidra-analyzeHeadless out/ghidra ivona -import libttsivonavoice.so \
    -scriptPath scripts/ghidra -postScript DumpDecompilation.java out/ghidra_dump/libttsivonavoice.c`
   (and `DecompAt.java <out.c> <addr>…` for targeted functions Ghidra skips).
4. **Validate every layer with one command** — `python3 scripts/verify_all.py` (add `--quick` for a
   ~30 s smoke run, `--json out.json` for machine-readable results). It drives the refimpl test suite,
   the codec stage/end-to-end checks (clean-room vs emulation, byte-for-byte), the prosody cost
   validator, the segmentation/splice/finalise verifications, G2P and the end-to-end pipeline.
5. Re-capture engine ground truth if you want it: `emu/tts_run.py --level 3 --ret-probe \
     --sentence "Hello world this is a test" --out-dir out/oracle/ref_nopunct`.

## Legal and scope

* This repository contains **analysis, tooling and decompiled text produced for interoperability
  research**. It contains **no APKs, no OBB/voice data, no native libraries, no decrypted
  proprietary dictionaries and no generated audio** — those are excluded by `.gitignore` and must be
  obtained by you from your own copy of the software.
* Decompiled listings under `out/ghidra_dump/` and fragments quoted in the reports are derived from
  third-party binaries and remain the property of their respective rights holders; they are included
  as technical evidence. No licence is granted over any third-party material.
* The original work in this repository (documents, scripts, reference implementation) is provided
  as-is, without warranty, for research and educational use.
* If you are a rights holder and want something removed, open an issue and it will be taken down.
