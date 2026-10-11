# IVONA 2 reference implementation (`refimpl/`)

Pure-Python-3 (stdlib only) reference implementation of every IVONA 2
behaviour that is fully documented in the analysis reports in this repository
plus a conformance test-suite that runs against the **real** artifacts
(APKs, OBBs, unlocked `lang_*.dat` files and native libraries) in place.

It deliberately does **not** depend on the internals of the original analysis
scripts under `scripts/`; it re-derives everything from the shipped bytes.

## Running the tests

```sh
python3 -m unittest discover -s refimpl -v
```

(From the repository root.  Any working directory works — paths are resolved
relative to the test file.)  Discovery adds `refimpl/` to `sys.path`, so the
modules are imported as `cdxv`, `voices`, `license`, `marks`, `params`.

Expected result: **74 tests, all passing** (≈8–9 s; the two full CDXV
invariant passes over the 150 MB OBBs dominate the runtime).

## Modules

| module | covers | report sources |
|---|---|---|
| `cdxv.py` | `main.<N>.<pkg>.obb` CDXV reader: 104-byte header, index walk, sections A–E, tail unit records, and the full invariant pass (`len == 2N+12`, index contiguity, record windows inside the gap region, `sum(diphone counts) == len(B)/4`, `len(C) == 36·N`, B permutation). | `report_obb_format.md` (whole file); `IVONA2_REVERSE_ENGINEERING.md` §5.1 |
| `voices.py` | package-name grammar, `getVoicesApiVersion` report string, `ivona_pkgs.csv` read/write, per-locale selection-file naming, data-root probe order, `main.<N>` / `patch.199` naming, the 42-row table loader and exact byte-size gate, `v()` struct gate. | `report_engine_app.md` §5; `report_libtiver.md` §1–§7 |
| `license.py` | XOR de-obfuscation of the embedded certificate (KEY=0x6d070, D=0x6d079, D2=0x6d07d) and full `Key: value` attribute + signature parse. | `report_ttsivona.md` §8; `IVONA2_REVERSE_ENGINEERING.md` §4.4 |
| `marks.py` | 20-byte speech-mark record parser, engine type → Android constant table, `GENERATE_MARKS` bitmask rules, and the `{0,1,1,0,1}` name-ownership table read from the real library. | `report_ttsivona.md` §10; `report_engine_synth.md` §4.2/§4.3; `report_engine_api.md` §6.3 |
| `params.py` | `tts_voice_param` command grammar (`set\|get:KEY[:min\|max\|def]`), the 16-key table with min/default/max, value-range checks and the float-key 1–99 XOR encoding. | `report_engine_api.md` §8 |

## What the tests actually exercise

* `cdxv`: both real `main.199.*.obb` files — header fields, 426 991 / 404 847
  index entries (8 496 / 8 164 null), 1 601 / 1 772 diphones, 58 / 62 phonemes,
  N ranges, `sum(N)`, gap-window statistics, the first-carved record values and
  the complete invariant pass.
* `voices`: the two real OBB paths and exact byte sizes, the real
  `libvoice_en_*.so` sizes, and `scripts/table_full.json` (42 rows).
* `license`: the certificate decoded out of the real `libttsivona.so` and
  compared byte-for-byte with `out/certs/ivona_certificate_decoded.txt`.
* `marks`: the real ownership table (`{0,1,1,0,1}` at `0x14bfc8` of
  `libttsivonavoice.so`) and the real `TYPE_*` name strings in
  `libttsivona.so`, plus synthetic records for the layout/bitmask rules.
* `params`: the documented key table and grammar.

### Artifact vs. report discrepancy

`report_obb_format.md` §11 lists the patch payload as "deflated 74 863".  The
real ZIP central directory stores `compress_size = 74 683` for both patches
(digits transposed in the report).  The test asserts the **artifact** value;
the artifact is ground truth.

## Explicitly **not** covered (out of scope for this reference)

These behaviours are documented as unknown/unimplemented in the reports and are
*not* faked here:

1. **Gap codec / audio format.** The ~106–108 MB high-entropy payload region
   addressed by every unit record has no identified container (zlib/deflate/
   gzip/bz2/lzma all fail; no RIFF/OggS magic) — `report_obb_format.md` §14(1).
   Only the address arithmetic (windows, bounds) is implemented/tested.
2. **`ISEF` payload contents.** The 74 656-byte payload behind the RSA-wrapped
   key in `lang_*.dat` is treated as encrypted `[INFERENCE]`; key/IV derivation
   is unproven — `report_obb_format.md` §14(2), `report_engine_synth.md`.
   Only the 12-byte header is parsed/tested.
3. **Synthesis internals.** SSML parsing, text analysis, diphone selection
   (Viterbi), acoustic waveform generation, cross-fading and resampling are not
   reimplemented (`report_engine_synth.md` §1–§6).
4. **The native `tts_*` ABI / JNI bridge execution.** `cdxv`/`voices`/`marks`
   model data and contracts, but no `.so` is loaded and no PCM is produced; the
   32-bit ARMv7 libraries need a `qemu-arm`/Android harness for that.
5. **Certificate signature verification.** Framing + algorithm are partly
   known but not traced end-to-end — `report_engine_api.md` appendix.  Only the
   decoded text, attributes and signature byte-length (520 = RSA-4096) are
   checked.
6. **Section C bytes 0–1/8/10–14 and the unit-record `Y` field.** Documented as
   unresolved in `report_obb_format.md` §14(3)(4); the reader exposes them but
   assigns no semantics.
7. **Open items** listed in `report_engine_api.md` (facade `+0x2c` slot,
   `responsiveness` plain-set store, `tts_streamer_add_voice`/`jump`/
   `get_input_warning`) and `report_libvoice.md` §5 (voice-plugin variant tags,
   vox-path delivery) are not implemented.

## Not machine-checkable (listed, not tested)

Facts that cannot be asserted programmatically with the shipped artifacts:

* Behaviour of the native code at runtime (return codes of `checkFiles` on a
  live device, actual `h()` patch extraction side effects, PCM output).
* The exact certificate signature algorithm.
* The semantics of the gap codec, the `ISEF` payload and the unresolved
  section-C/`Y` fields (see above).
* The certificate **not** being modified at runtime (only the static decoded
  bytes are checked).
