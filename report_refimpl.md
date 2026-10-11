# Reference implementation + conformance tests for IVONA 2 (`refimpl/`)

Scope: a runnable, stdlib-only Python 3 reference implementation of every IVONA 2
behaviour that is **fully documented** in the reports in this repository, plus a
conformance suite that checks it against the **real** artifacts (the three APKs,
the two `main.199.*.obb` + `patch.199.*.obb`, the unlocked `lang_*.dat` files,
`out/certs/ivona_certificate_decoded.txt` and the native libraries).

Nothing under `refimpl/` imports the previous analysis scripts' internals; all
module code re-derives its facts from the shipped bytes or the decoded tables.
All originals were opened read-only; the only new files are under `refimpl/`
and this report.

---

## 1. Modules

| module | responsibility | report source |
|---|---|---|
| `refimpl/cdxv.py` | CDXV (`main.<N>.<pkg>.obb`) reader — 104-byte header (magic, name, sample rate, format id, checksum, 7 offset/length pairs), index walk (`N = len/8`), sections A–E, tail unit records (`u16 N; u16 ramp[N]; u16 Y; u32 gap_off; u32 gap_len`), and the complete invariant pass. | `report_obb_format.md` (whole); `IVONA2_REVERSE_ENGINEERING.md` §5.1 |
| `refimpl/voices.py` | package-name grammar (`com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>` → locale triple), `getVoicesApiVersion` 5-field report + `ivona_pkgs.csv` (7 columns), selection-file naming `.<iso3lang>_<iso3country>`, data-root probe order (`ivona/` then `Android/obb/`), `main.<N>`/`patch.199` naming, the 42-row table loader and exact byte-size gate, `v()` struct gate + 43-entry accessor bound. | `report_engine_app.md` §5; `report_libtiver.md` §1–§7 |
| `refimpl/license.py` | XOR de-obfuscation of the embedded certificate (`KEY=0x6d070`, `D=0x6d079`, `D2=0x6d07d`) and parsing of every `Key: value` attribute plus the `-----BEGIN/END SIGNATURE-----` block. | `report_ttsivona.md` §8; `IVONA2_REVERSE_ENGINEERING.md` §4.4 |
| `refimpl/marks.py` | 20-byte speech-mark record parser (`type, name*, start, end, sample`), engine type → Android `TYPE_*` table, `GENERATE_MARKS` bitmask rules, and the `{0,1,1,0,1}` name-ownership table read from the real library. | `report_ttsivona.md` §10; `report_engine_synth.md` §4.2/§4.3; `report_engine_api.md` §6.3 |
| `refimpl/params.py` | `tts_voice_param` grammar `set\|get:KEY[:min\|max\|def]`, the 16-key table with min/default/max, value-range checks (errno 6) and the float-key 1–99 XOR encoding. | `report_engine_api.md` §8 |
| `refimpl/test_conformance.py` | `unittest` conformance suite (74 tests); every test docstring cites the report + section it encodes. | — |
| `refimpl/README.md` | run instructions, module map, and the boundary list. | — |

### What each module verified against the real artifacts

* **cdxv** — both `main.199.*.obb`: header fields, `N = 426 991 / 404 847`
  (8 496 / 8 164 null slots), 1 601 / 1 772 diphones with
  `sum(count) == len(B)/4` (418 495 / 396 683), 58 / 62 phonemes,
  `len(C) == 36·N`, B a permutation of the non-null ids, `len == 2N+12`,
  monotone ramps, every gap window inside the payload region with
  `min(offset) == gap_start` and `max(offset+len) == first record offset`,
  `N` ranges `3..130` / `4..97`, `sum(N) = 6 662 123 / 7 267 240`, distinct
  gap offsets `324 820 / 304 687`, `sum(gap_len) = 361 352 490 / 346 537 077`.
* **voices** — real OBB paths and exact sizes (152 219 597 / 149 905 560),
  real voice-lib sizes, `scripts/table_full.json` 42 rows, `N ∈ {183,199,422}`,
  the size gate, and the `v()` gate on the real `{20, 2, "20130201_150739", 48,
  accessor}` struct.
* **license** — `decode_certificate(libttsivona.so)` equals
  `out/certs/ivona_certificate_decoded.txt` byte-for-byte (1 798 bytes);
  attributes `Product=IVONA`, `Certificate-ID=a1169787`,
  `Num-threads/Thread-speed=UNLIMITED`, `Expiration-date=NEVER`, `Voices=ALL`,
  `Extension-SSML=TRUE`; 1 040 hex chars = 520-byte signature.
* **marks** — ownership table `(0,1,1,0,1)` read from `0x14bfc8` of
  `libttsivonavoice.so`; the five `TYPE_*` strings read from
  `libttsivona.so`; synthetic 20-byte records for layout/bitmask/ownership
  rules.
* **params** — the documented key table, grammar and ranges.

---

## 2. Test run

Command (repository root, `/home/asdf/Downloads/ivona_re`):

```
python3 -m unittest discover -s refimpl -v
```

Full output:

```
test_header_amy (test_conformance.TestCDXVHeader.test_header_amy)
report_obb_format.md §2/§12: Amy header fields. ... ok
test_header_kendra (test_conformance.TestCDXVHeader.test_header_kendra)
report_obb_format.md §2/§12: Kendra header fields. ... ok
test_contiguity_and_eof (test_conformance.TestCDXVIndex.test_contiguity_and_eof)
report_obb_format.md §3: records tile [first_offset, EOF) contiguously. ... ok
test_counts_and_nulls (test_conformance.TestCDXVIndex.test_counts_and_nulls)
report_obb_format.md §3/§12: N=426991/404847, nulls 8496/8164. ... ok
test_first_entry (test_conformance.TestCDXVIndex.test_first_entry)
report_obb_format.md §3: first entry offset 0x7FABF03 (Kendra). ... ok
test_amy_extra_phonemes (test_conformance.TestCDXVPhonemes.test_amy_extra_phonemes)
report_obb_format.md §8: Amy adds {eax, iax, o, uax}. ... ok
test_counts (test_conformance.TestCDXVPhonemes.test_counts)
report_obb_format.md §8/§12: 58 phonemes (Kendra) / 62 (Amy). ... ok
test_first_is_boundary_symbol (test_conformance.TestCDXVPhonemes.test_first_is_boundary_symbol)
report_obb_format.md §8: first record is '0'. ... ok
test_b_is_permutation_of_non_null_ids (test_conformance.TestCDXVSections.test_b_is_permutation_of_non_null_ids)
report_obb_format.md §5: B is an exact permutation of non-null ids. ... ok
test_diphone_counts (test_conformance.TestCDXVSections.test_diphone_counts)
report_obb_format.md §4/§12: 1601/1772 diphones, sum(count) == len(B)/4. ... ok
test_first_diphone_record (test_conformance.TestCDXVSections.test_first_diphone_record)
report_obb_format.md §4 hexdump: record 0 == 'aa-aa' start=0 count=6. ... ok
test_section_c_is_36n (test_conformance.TestCDXVSections.test_section_c_is_36n)
report_obb_format.md §6: len(C) == 36*N exactly. ... ok
test_first_record_fields (test_conformance.TestCDXVUnitRecords.test_first_record_fields)
report_obb_format.md §9 hexdump: first Kendra record values. ... ok
test_overall_ok (test_conformance.TestCDXVUnitRecords.test_overall_ok)
All documented CDXV invariants hold on both real files. ... ok
test_record_invariants (test_conformance.TestCDXVUnitRecords.test_record_invariants)
report_obb_format.md §9: len==2N+12, ramp monotone, windows inside gap. ... ok
test_statistics (test_conformance.TestCDXVUnitRecords.test_statistics)
report_obb_format.md §9/§12: N ranges, sum(N), gap stats. ... ok
test_known_rows (test_conformance.TestLibtiverTable.test_known_rows)
report_libtiver.md §4 rows 8/16 (amy/kendra). ... ok
test_main_obb_name_matches_row (test_conformance.TestLibtiverTable.test_main_obb_name_matches_row)
report_libtiver.md §7.1: main_obb_name(N, pkg) == table field. ... ok
test_obb_versions (test_conformance.TestLibtiverTable.test_obb_versions)
report_libtiver.md §4: N in {183, 199, 422}. ... ok
test_row_count (test_conformance.TestLibtiverTable.test_row_count)
report_libtiver.md §4: 42 hardcoded table rows. ... ok
test_terminator_not_in_table (test_conformance.TestLibtiverTable.test_terminator_not_in_table)
The decoded table excludes the all-zero terminator row (§4). ... ok
test_voice_lib_sizes_match_disk (test_conformance.TestLibtiverTable.test_voice_lib_sizes_match_disk)
report_libtiver.md §4 field [6]: voice-lib size verified on disk. ... ok
test_attributes (test_conformance.TestLicense.test_attributes)
brief §4.4: certificate attribute values. ... ok
test_decode_length (test_conformance.TestLicense.test_decode_length)
brief §4.4: decoded length == 1798. ... ok
test_decode_matches_reference_dump (test_conformance.TestLicense.test_decode_matches_reference_dump)
brief §4.4: decode == out/certs/ivona_certificate_decoded.txt. ... ok
test_semantic_flags (test_conformance.TestLicense.test_semantic_flags) ... ok
test_signature_block (test_conformance.TestLicense.test_signature_block)
brief §4.4: 14 lines / 1040 hex chars = 520 bytes (RSA-4096). ... ok
test_bitmask (test_conformance.TestMarks.test_bitmask)
brief §6: bit N of GENERATE_MARKS enables type N. ... ok
test_iter_marks (test_conformance.TestMarks.test_iter_marks) ... ok
test_name_resolver (test_conformance.TestMarks.test_name_resolver) ... ok
test_null_name_maps_to_none (test_conformance.TestMarks.test_null_name_maps_to_none)
report_ttsivona.md §10: name pointer 0 -> Java null. ... ok
test_ownership_rule (test_conformance.TestMarks.test_ownership_rule)
report_engine_synth.md §4.2: 1 => alias/never free, 0 => heap copy. ... ok
test_ownership_table (test_conformance.TestMarks.test_ownership_table)
report_engine_synth.md §4.2: table at 0x14bfc8 == {0,1,1,0,1}. ... ok
test_record_pack_unpack_roundtrip (test_conformance.TestMarks.test_record_pack_unpack_roundtrip) ... ok
test_record_parse (test_conformance.TestMarks.test_record_parse)
report_ttsivona.md §10: 20-byte record {type, name*, start, end, sample}. ... ok
test_type_names (test_conformance.TestMarks.test_type_names)
report_engine_api.md §6.3: the five SpeechMark constants, in order. ... ok
test_type_table (test_conformance.TestMarks.test_type_table)
report_engine_api.md §6.3: engine type -> Android constant. ... ok
test_lang_dat_differs_after_12 (test_conformance.TestObbArtifacts.test_lang_dat_differs_after_12)
report_obb_format.md §11: US/GB identical only in bytes 0-11. ... ok
test_lang_dat_header (test_conformance.TestObbArtifacts.test_lang_dat_header)
report_obb_format.md §11: 'ISEF' + BE u32 1 + constant 50 99 2b cc. ... ok
test_main_obb_sizes (test_conformance.TestObbArtifacts.test_main_obb_sizes)
brief §1: main.199 sizes 152 219 597 (Kendra) / 149 905 560 (Amy). ... ok
test_patch_sizes (test_conformance.TestObbArtifacts.test_patch_sizes)
report_obb_format.md §1/§11: both patches are 74 861 bytes. ... ok
test_patch_zip_contents (test_conformance.TestObbArtifacts.test_patch_zip_contents)
report_obb_format.md §11: one entry, uncompressed 74 668, CRC32, date. ... ok
test_main_name (test_conformance.TestObbNaming.test_main_name)
report_libtiver.md §6: main.<N>.<pkg>.obb. ... ok
test_obb_path (test_conformance.TestObbNaming.test_obb_path) ... ok
test_patch_always_199 (test_conformance.TestObbNaming.test_patch_always_199)
report_libtiver.md §3.1/§7.1: patch version is hardcoded 199. ... ok
test_columns (test_conformance.TestPackagesCsv.test_columns)
report_engine_app.md §5.3: 7 ';'-separated fields per data line. ... ok
test_roundtrip (test_conformance.TestPackagesCsv.test_roundtrip) ... ok
test_short_lines_ignored (test_conformance.TestPackagesCsv.test_short_lines_ignored)
report_engine_app.md §5.3: reader consumes lines with >= 6 fields. ... ok
test_float_decode_bounds (test_conformance.TestParams.test_float_decode_bounds) ... ok
test_float_encoding_range_endpoints (test_conformance.TestParams.test_float_encoding_range_endpoints)
report_engine_api.md §8: min/def/max float limits per key. ... ok
test_float_key_encoding_range (test_conformance.TestParams.test_float_key_encoding_range)
report_engine_api.md §8: int 1..99 -> float in [min,max]. ... ok
test_grammar (test_conformance.TestParams.test_grammar)
report_engine_api.md §8: 'set|get:KEY[:min|max|def]'. ... ok
test_int_defaults (test_conformance.TestParams.test_int_defaults)
report_engine_api.md §8: documented integer defaults. ... ok
test_int_ranges (test_conformance.TestParams.test_int_ranges)
report_engine_api.md §8 value ranges -> errno 6 when out of range. ... ok
test_prop_names (test_conformance.TestParams.test_prop_names)
report_engine_api.md §8: KEY -> .vox property name. ... ok
test_string_defaults (test_conformance.TestParams.test_string_defaults)
report_engine_api.md §8: default strings (text_encoding UTF-8). ... ok
test_table_keys (test_conformance.TestParams.test_table_keys)
report_engine_api.md §8: the 16 command-table keys. ... ok
test_unknown_command_errors (test_conformance.TestParams.test_unknown_command_errors)
report_engine_api.md §8: unknown cmd/KEY/qualifier -> errno 8. ... ok
test_uri_scheme (test_conformance.TestParams.test_uri_scheme)
report_engine_api.md §8: base_uri must be file:// or http://. ... ok
test_check_package (test_conformance.TestSizeGate.test_check_package)
report_libtiver.md §3: table lookup + size gate -> 0. ... ok
test_real_sizes_pass (test_conformance.TestSizeGate.test_real_sizes_pass)
brief §1 / report_libtiver.md §7.1: exact byte-size gate. ... ok
test_wrong_size_fails (test_conformance.TestSizeGate.test_wrong_size_fails) ... ok
test_accessor_limit (test_conformance.TestVStruct.test_accessor_limit)
report_libtiver.md §2: entry(i) valid for i <= 43 only. ... ok
test_build_stamp (test_conformance.TestVStruct.test_build_stamp)
report_libtiver.md §2: struct[2] == '20130201_150739'. ... ok
test_gate_accepts_reference_struct (test_conformance.TestVStruct.test_gate_accepts_reference_struct)
report_libtiver.md §2/§5: the real struct {20,2,stamp,48,acc} passes. ... ok
test_gate_rejects_each_failing_field (test_conformance.TestVStruct.test_gate_rejects_each_failing_field)
report_libtiver.md §5: gates are abi>0x13, stride>0x2f, apiVer<3. ... ok
test_data_location_fold (test_conformance.TestVoicePackageGrammar.test_data_location_fold)
report_libtiver.md §5: 1=/ivona/, 2=/Android/obb/, 0=none. ... ok
test_parse (test_conformance.TestVoicePackageGrammar.test_parse)
report_engine_app.md §5.6: 7 dot parts -> locale triple. ... ok
test_probe_order (test_conformance.TestVoicePackageGrammar.test_probe_order)
report_libtiver.md §5: '<sdcard>/ivona/' then '<sdcard>/Android/obb/'. ... ok
test_rejects_malformed (test_conformance.TestVoicePackageGrammar.test_rejects_malformed) ... ok
test_selection_file_name (test_conformance.TestVoicePackageGrammar.test_selection_file_name)
report_engine_app.md §5.7: '.<iso3lang>_<iso3country>' lowercased. ... ok
test_five_fields (test_conformance.TestVoiceReport.test_five_fields) ... ok
test_format (test_conformance.TestVoiceReport.test_format)
report_libtiver.md §5: '%d;%d;' + name + ';' + stamp + ';%d'. ... ok
test_roundtrip (test_conformance.TestVoiceReport.test_roundtrip) ... ok

----------------------------------------------------------------------
Ran 74 tests in 8.544s

OK
```

**74 tests, 0 failures, 0 errors.**

### Artifact vs. report discrepancy found during testing

`report_obb_format.md` §11 lists the patch entry as "deflated 74 863".  The
real ZIP central directory stores `compress_size = 74 683` for both patches
(the report transposed the last two digits).  The suite asserts the **artifact**
value (74 683); the artifact is treated as ground truth.

---

## 3. Boundary — what is deliberately **not** implemented/tested

These areas are documented as unknown/unimplemented in the reports and are not
faked:

1. **Gap codec / audio format** — the ~106–108 MB high-entropy payload region
   addressed by the unit records has no identified container (`report_obb_format.md`
   §14(1)).  Only the address arithmetic (windows + bounds) is implemented.
2. **`ISEF` payload contents** — the 74 656-byte payload behind the RSA-wrapped
   key in `lang_*.dat` is treated as encrypted `[INFERENCE]`; key/IV derivation
   is unproven (`report_obb_format.md` §14(2), `report_engine_synth.md`).  Only
   the 12-byte header is parsed.
3. **Synthesis internals** — SSML parsing, text analysis, diphone selection
   (Viterbi), waveform generation, cross-fade and resampling
   (`report_engine_synth.md` §1–§6) are not reimplemented.
4. **Native `tts_*` ABI / JNI execution** — no `.so` is loaded and no PCM is
   produced; the 32-bit ARMv7 libraries need a `qemu-arm`/Android harness.
5. **Certificate signature verification** — framing/algorithm only partly known
   (`report_engine_api.md` appendix); only decoded text, attributes and the
   520-byte signature length are checked.
6. **Unresolved fields** — section-C bytes 0–1/8/10–14 and the unit-record `Y`
   field (`report_obb_format.md` §14(3)(4)) are exposed by the reader but carry
   no assigned semantics.
7. **Other open items** — facade `+0x2c`/`getProperty` slot and
   `responsiveness` plain-set store (`report_engine_api.md` appendix);
   `tts_streamer_add_voice`/`jump`/`get_input_warning`; voice-plugin variant
   tags beyond `0x1F`/`0x1B` and vox-path delivery (`report_libvoice.md` §5).

### Documented facts that are **not machine-checkable** with these artifacts

Listed rather than faked:

* Runtime behaviour of the native code (live `checkFiles` return codes, `h()`
  patch side effects, PCM output) — no executable ARM harness here.
* The exact certificate signature algorithm.
* The semantics of the gap codec, the `ISEF` payload, and the unresolved
  section-C/`Y` fields (see items 1, 2, 6).
* That the certificate is not modified at runtime (only the static decoded
  bytes are checked).

---

## 4. Files added

```
refimpl/cdxv.py
refimpl/voices.py
refimpl/license.py
refimpl/marks.py
refimpl/params.py
refimpl/test_conformance.py
refimpl/README.md
report_refimpl.md            (this file)
```

All original artifacts were opened read-only; no original file was modified.
