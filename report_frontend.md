# Text front-end — G2P solved, prosody partially specified

Scope: everything from input text/SSML to the phoneme/unit level. Addresses are Ghidra addresses of
`out/ghidra_dump/libvoice_kendra.c` (plugin tables/functions) or `libttsivonavoice.c` (engine);
**ELF vaddr = Ghidra − 0x10000**. File/table offsets are of `out/libs/kendra/*.so`.

Status: ✅ **grapheme→phoneme (lexicon + LTS) is reimplemented and cross-checked against the engine**;
🟡 text normalisation is specified at the container/rule level; 🟡 prosody + Viterbi are structurally
mapped but not formula-complete.

---

## 1. Phoneme inventory

58 phoneme names (en_US) / 62 (en_GB) as 32-byte records (phoneme table `pair6` of the OBB, and the
plugin's own phone-name table). Names observed: `hh ax l ow w er1 l d k eh1 n d r ax sil …`; stress
is part of the name (`ow1`, `er1`, `eh1`), vowels have 0/1/2 variants; `sil` = pause. A port needs
the table order to map indices → names (`refimpl/cdxv.py` reads it; `scripts/lts_decode.py`
uses it).

## 2. Packed lexicon lookup — ✅ verified

Reader: `scripts/lex_decode.py` (pure Python, no emulation). Blob record layout (from
`FUN_0003e2b4`, Ghidra `0003e2b4`):

```
<pron bytes> 0xFF <key bytes> 0x00      (repeated; keys sorted ascending)
key : u8 indices into the 256-entry fragment pool → decoded as `tag + word`
      (tag = 1 char, part-of-speech; "0" = default entry), 0x00-terminated
pron: u8 indices into the syllable table, read *backward* from the 0xFF;
      each index selects a NUL-terminated string of indices into the phone table
```

Lookup example (Python): `hello → hh ax l ow1`.
Engine cross-check (`scripts/probe_g2p.py`, drives the real plugin under Unicorn):
`hello → lex hh ax l ow1` — **identical**.

## 3. Letter-to-sound FSM — ✅ verified

Reimplementation: `scripts/lts_decode.py` (pure Python), from `FUN_0003f594` (Ghidra `0003f594`):

```
context = "0"*(ctx-1) + "#" + word + "#" + "0"*(ctx-1)          ctx = 4
for i = last..first word char:
    win   = ctx_chars[i-ctx .. i-1] + ctx_chars[i+1 .. i+ctx]  (current char excluded)
    state = letter_table[ord(word[i]) - 'a']                   (27-entry u32 table)
    while fsm[state].pos != 0xFF:                              (6-byte records)
        state = fsm[state].next_if  if win[fsm[state].pos] == fsm[state].ch
                else fsm[state].next_else
    emit lts_phone_names[fsm[state].ch]        (prepended → output L→R)
    "epsilon" emits nothing; a trailing '0' on a name is dropped; "A-B" emits A then B
```

Examples: `world → w er1 l d`, `kendra → k eh1 n d r ax`; the engine probe returns the same phone
strings (`kendra → lex k eh1 n d r ax`).

## 4. Text normalisation / SSML — 🟡 specified at container level

* SSML accepted elements and their handler types (from `FUN_0003d998`, expat element table):
  audio 2, break 3, desc 4, emphasis 5, lang 6, lexicon 7, lookup 8, mark 9, meta 10, metadata 11,
  p 12, phoneme 13, prosody 14, s 15, say-as 16, speak 17, sub 18, voice 19, w 20.
* Lexicon rewriting: the `ISEF` sections `prm_pre_lexicon` / `prm_lexicon` (660 rules en_US) /
  `prm_post_lexicon` are applied in the order given by `prm_lex_list`
  (`prm_pre_lexicon → prm_lexicon → prm_post_lexicon`); rules are RFC-style
  `"pattern" "replacement"` PCRE pairs with `#& encoding=UTF-8` and `#` comments
  (`report_isef.md`, decrypted files in `out/obb/`).
* What still needs work: the exact engine semantics of the `<say-as>`/`<phoneme>`/`<sub>` handlers,
  the interaction between the lexicon rewrite stage and the packed-lexicon lookup, and the
  boundary rule that decides lexicon vs LTS per word (the probe shows both branches: `hello` and
  `kendra` are looked up in the lexicon, but `kendra`'s form equals the LTS output).

## 5. Prosody and unit selection — 🟡 structural only

Established (from `report_engine_synth.md`, with addresses): stage chain
`FUN_00064f38/65028/650b0` over the stage tables in `.data.rel.ro` (files `0x184160/0x1841a8/0x1841f8`),
96-byte segment feature vectors `FUN_00060ed4`, candidate records = 36-byte entries (`pair4` of the
OBB) + the diphone index (`pair3`), Viterbi `FUN_0005fc04` with beam 50 (25 when `quality` is low),
and the chosen unit's `(gap_off,gap_len)` feeding the decoder
(`report_gap_codec.md`/`report_segmentation.md`).

Not yet specified (the remaining gap for a from-scratch front-end): the *cost terms* — target cost
over the 96-byte features, join cost between adjacent diphones, the duration model
(`duration_func`/`phonefunc`/`syl_num_phones`), the intonation model, and how `dur_stretch`/
`pitch_stretch`/`volume` scale them. These are computable from the decompiled code but each needs a
trace + numeric validation.

Recommended next method (the one that already worked twice): extend
`scripts/codec_probe.py`'s approach to the prosody stage — snapshot the vectors/costs after each
`FUN_0005fc04` step for a fixed input, then port the cost functions one at a time and diff the
snapshots, exactly as `scripts/codec_parts/test_setup.py` does for the codec.

## 6. Reproduce

```sh
~/venvs/re/bin/python scripts/lts_decode.py hello world kendra     # pure-python LTS
~/venvs/re/bin/python scripts/lex_decode.py hello                  # pure-python lexicon lookup
~/venvs/re/bin/python scripts/probe_g2p.py hello kendra            # engine oracle (Unicorn)
```

All three agree on the tested words; the reference vectors above are the acceptance data for a port
of this layer.
