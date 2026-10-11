# IVONA 2 OBB data-format analysis (`CDXV` container)

Scope: byte-level reverse engineering of the voice expansion files under
`IVONA 2/` — the 152 MB / 150 MB `main.199.*.obb` files (custom `CDXV`
container, **not** ZIP), the `patch.199.*.obb` files (ZIP), and the
`lang_*.dat` payload inside them. All original archives were opened read-only;
scripts and extracts live in `scripts/` and `out/obb/`.

Every factual claim below is backed by observed bytes (hex dumps quoted) or by
observed behaviour of the shipped native libraries (the sibling agent's Ghidra
decompilations in `out/ghidra_dump/*.c`, cited as `file:line`, read-only).
Statements marked **[INFERENCE]** are interpretations not directly proven.

---

## 0. Scripts used (all Python 3, `scripts/`)

| script | purpose |
|---|---|
| `scripts/01_parse_header.py` | dump header u32s, walk first N index pairs |
| `scripts/02_walk_index.py` | walk full index; count pairs; contiguity/EOF checks |
| `scripts/03_dump_regions.py` | hexdump each section start; carve first index records → `out/obb/*_first_records.bin`, `out/obb/*_regions.txt` |
| `scripts/04_strings_by_region.py` | ASCII-strings scan per region (min len 4) |
| `scripts/05_sections.py` | per-section stats (A/B/C/D/E, tail-record sampling) |
| `scripts/06_crossref.py` | A→B slicing, B-sortedness, diphone→record examples |
| `scripts/07_fullpass.py` | full pass over every index record (layout validation) |
| `scripts/08_c_to_d.py` | section C trailing u32 → section D offsets |
| `scripts/09_isef.py` | `ISEF` header analysis, US/GB diff, magic scan of main OBBs |
| `scripts/10_probes.py` | ISEF decompress attempts, gap periodicity, C byte-position stats, B permutation check, D entry sizes |
| `scripts/11_probes2.py` | distinct blob count, D entries dump, phone-id correlation |
| `scripts/12_groups.py` | runs of index records sharing one D entry |
| `scripts/13_final.py` | blob prefixes, name-field NUL check, timestamp, D-run formula |

Extracts: `out/obb/lang_en_us.dat`, `out/obb/lang_en_gb.dat` (unzipped from
patches), `out/obb/kendra_regions.txt`, `out/obb/amy_regions.txt`,
`out/obb/*_first_records.bin`.

Files analysed:

| file | bytes |
|---|---|
| `…/com.ivona.tts.voicebeta.eng.usa.kendra/main.199.…obb` (Kendra) | 152 219 597 |
| `…/com.ivona.tts.voicebeta.eng.gbr.amy/main.199.…obb` (Amy) | 149 905 560 |
| `…/kendra/patch.199.…obb`, `…/amy/patch.199.…obb` | 74 861 each |

---

## 1. Top-level map of `main.obb`

```
0x00000000 ┌ header, 0x68 (104) bytes: magic, name, sample-rate, checksum,
           │ format id, 7 × (offset,length) section pairs
0x00000068 ├ index: N × 8 bytes, each = (u32 file_offset, u32 length)
           │        of the "unit records" region at the end of the file
0x00341FE0 ├ section A  diphone table          (20-byte records)
0x00349CF8 ├ section B  unit-id lists          (u32 array)
0x004E27F8 ├ section C  unit records           (36 bytes/unit, positional
           │                                   over the index)
0x0138B598 ├ section D  word/chunk blocks      (variable, byte-addressed)
0x0182E198 ├ section E  phoneme-name table     (32-byte records)
0x0182E8D8 ├ high-entropy payload ("gap": audio) — addressed by absolute
           │        (offset,length) from each unit record
0x07FABF03 └ unit records region (the data the index points into), to EOF
```
(Kendra offsets; Amy equivalents in §9.)

Section ends are padded to the next 8-byte boundary before the next region
starts (observed padding per boundary index→A, A→B, B→C, C→D, D→E, E→gap:
Kendra `0,4,4,4,3,0`; Amy `0,0,4,4,1,0`).
All seven header offsets are ≡ 0 (mod 8); all section lengths are ≡ 0 (mod 4)
except section D, whose length is a byte count (Kendra 4 860 925 ≡ 1, Amy
4 709 055 ≡ 3). Index entries themselves are **not** payload-aligned: the first
record offset is `0x7FABF03` (odd).

---

## 2. Header (0x00 … 0x67)

Kendra header hexdump (`scripts/01_parse_header.py`):

```
00000000: 43 44 58 56 76 6f 78 5f 65 6e 5f 75 73 5f 6b 65  CDXVvox_en_us_ke
00000010: 6e 64 72 61 00 00 00 00 00 00 00 00 00 00 00 00  ndra............
00000020: 00 00 00 00 22 56 00 00 0e 00 00 00 18 7a 7c 4f  ...."V.......z|O
00000030: 68 00 00 00 78 1f 34 00 d8 e8 82 01 00 00 00 00  h...x.4.........
00000040: e0 1f 34 00 14 7d 00 00 f8 9c 34 00 fc 8a 19 00  ..4..}..........
00000050: f8 27 4e 00 9c 8d ea 00 98 b5 38 01 fd 2b 4a 00  .'N.......8..+J.
00000060: 98 e1 82 01 40 07 00 00                          ....@...
```

| off | size | type | Kendra | Amy | meaning | evidence |
|---|---|---|---|---|---|---|
| 0x00 | 4 | magic | `43 44 58 56` = "CDXV" (u32 LE `0x56584443`) | same | file magic | engine compares `local_78[0] == 0x56584443` after `fread(hdr,0x68,1)` — `out/ghidra_dump/libvoice_kendra.c:2207,2225,2418,2471` |
| 0x04 | 32 | char[], NUL-padded | `vox_en_us_kendra` | `vox_en_gb_amy` | voice/database name | engine `strcmp`s it against config key `"name"` (`libvoice_kendra.c:2600-2601`, compare at `:2633`); 32-byte width from stack layout `local_80` + `auStack_7c[32]` in `FUN_00028008` (`:2432-2462`); config embeds `"name","vox_en_us_kendra"` (`:7805`) |
| 0x24 | 4 | u32 LE | 22050 | 22050 | sample rate | header field read as `local_54` and validated against expected rate (`:2228`); later stored as config `"sample_rate"` (`:2651`) |
| 0x28 | 4 | u32 LE | 14 | 14 | format/variant id | `switch(local_58)` with cases 2…14 selecting parser callbacks; 14 → `FUN_0002de60/LAB_0002d8ac/LAB_0002dc84` (`:2526-2565`) |
| 0x2C | 4 | u32 LE | 1333557784 | 1334671314 | "checksum" (engine name) | config `"checksum","1333557784"` (`:7806`) validated by `atol(cfg) == obj+0x10` (`:2634`); value also decodes as Unix time → 2012-04-04 16:43:04 UTC / 2012-04-17 14:01:54 UTC (`scripts/13_final.py`) |
| 0x30 | 4 | u32 LE | 104 | 104 | **index offset** (always 0x68 = right after header) | `puVar2[5] = base + local_50` (local_50 = header+0x30) (`:2520`); index bytes `[0x68, 0x68+len)` confirmed by full walk |
| 0x34 | 4 | u32 LE | 3 415 928 | 3 238 776 | **index byte length** (⇒ N = len/8 entries) | `puVar2[6] = local_4c` (header+0x34) (`:2524`); walk ends exactly at 0x68+len |
| 0x38 | 4 | u32 LE | 0x0182E8D8 | 0x017072A0 | offset of the payload region that follows section E (= start of high-entropy gap) | `if (local_44 != 0) puVar2[0x10] = base + local_48` (`:2521-2523`); byte value == end of section-E chain |
| 0x3C | 4 | u32 LE | 0 | 0 | length of that region; 0 ⇒ engine skips it (gap extent is instead given per record) | same code; both files store 0 |
| 0x40/0x44 | 4/4 | off/len | 0x341FE0 / 32020 | 0x316BE0 / 35440 | section A | `puVar2[10] = base+local_40`, **count = local_3c / 0x14** (`:2504-2506`) ⇒ A records are 20 bytes |
| 0x48/0x4C | 4/4 | off/len | 0x349CF8 / 1673980 | 0x31F650 / 1586732 | section B | `puVar2[9] = base+local_38` (`:2508-2510`) |
| 0x50/0x54 | 4/4 | off/len | 0x4E27F8 / 15371676 | 0x4A2C80 / 14574492 | section C | `puVar2[8] = base+local_30` (`:2511-2513`) |
| 0x58/0x5C | 4/4 | off/len | 0x138B598 / 4860925 | 0x1289020 / 4709055 | section D | `puVar2[7] = base+local_28` (`:2514-2516`) |
| 0x60/0x64 | 4/4 | off/len | 0x182E198 / 1856 | 0x1706AE0 / 1984 | section E | `puVar2[0xc] = base+local_20` (`:2517-2519`) |

The engine loads the whole prefix `0 … max(section ends)` into one buffer
(`FUN_0002bddc(param_1, 0, uVar5)` where `uVar5` is the running max of
`off+len` over all pairs — `:2476-2500`), i.e. bytes 0 … 25 356 504 (Kendra).
The index and the gap/records are read on demand: `FUN_00027adc` does
`fseek(fp, off, SEEK_SET); fread(buf, 1, len, fp)` on index entries
(`:2149-2174`, error text `"voxdb read"`).

**The count of index entries is not stored**; it is `header[0x34] / 8`
(426 991 Kendra, 404 847 Amy).

---

## 3. Index (0x68 … 0x68+len)

Layout: `N` records of `struct { u32 offset; u32 length; }` LE.

Evidence (`scripts/02_walk_index.py`):

```
kendra: index pairs: 426991
        index bytes: [0x68, 0x341FE0) -> 3415928 bytes
        first entry offset: 0x7FABF03 (133873411)
        last entry end: 0x912AFCD == file size: True
        contiguity anomalies (non-adjacent): []      <- NONE
amy:    index pairs: 404847
        index bytes: [0x68, 0x316BE0) -> 3238776 bytes
        last entry end: 0x8EF6098 == file size: True
        contiguity anomalies: []
```

First pairs (from the header dump, Kendra):

```
+0x68: off=0x07FABF03 len=0x4C
+0x70: off=0x07FABF4F len=0x3A   (0x7FABF03 + 0x4C = 0x7FABF4F)
+0x78: off=0x07FABF89 len=0x44   (0x7FABF4F + 0x3A = 0x7FABF89)
...
```

* The records are **contiguous**: `offset[i+1] == offset[i] + length[i]` for
  every adjacent pair (0 anomalies) except for explicit null slots, so the
  records region `[first_offset, EOF)` is fully tiled, ending exactly at EOF.
* **Null slots**: 8 496 (Kendra) / 8 164 (Amy) index entries are `(0,0)`.
  Example: Kendra file offset 0x1B0 holds `00 00 00 00 00 00 00 00`
  (index entry #41), and contiguity resumes right after it
  (`0x07FAC74F + 0x56 == 0x07FAC7A5` at +0x1B8). Null slots count as
  entries in N but hold no record data (`rl < 12` ⇒ skipped; see §7).
* **Not compressed**: entries are plain `u32` pairs; the records they point
  to are plain binary (§7). Only the *gap* payload (§8) is high-entropy.
* **Alignment**: index struct entries are naturally 8-byte aligned (table
  starts at 0x68); pointed-to payload has no alignment (first offset odd).

---

## 4. Section A — diphone table (`len/20` records)

Record (20 bytes): `char name[12] NUL-padded; u32 start; u32 count`
`start`/`count` index into section B.

```
Kendra @0x341FE0 (scripts/05_sections.py):
[0] 61612d616100000000000000 00000000 06000000  name="aa-aa" start=0   count=6
[1] 61612d616800000000000000 06000000 03000000  name="aa-ah" start=6   count=3
[2] 61612d616f00000000000000 09000000 08000000  name="aa-ao" start=9   count=8
[3] 61612d617800000000000000 11000000 02000000  name="aa-ax" start=17  count=2
[4] 61612d617900000000000000 13000000 01000000  name="aa-ay" start=19  count=1
[5] 61612d620000000000000000 14000000 ce000000  name="aa-b"  start=20  count=206
```

Validation (`scripts/06_crossref.py`, `13_final.py`):

* `start[i+1] == start[i] + count[i]` holds for all 1600 transitions (Kendra).
* `start[0] + Σcount == len(B)/4` exactly: **1601 records, Σcount = 418 495 =
  1 673 980/4** (Kendra); **1772 records, Σcount = 396 683 = 1 586 732/4** (Amy).
* Names are NUL-terminated within 12 bytes for every record
  (longest = 6 (K) / 7 (A) chars ⇒ fits `char[12]`; `scripts/13_final.py`:
  "A names without NUL in first 12 bytes: 0").
* Names are diphones `"X-Y"` built from the phoneme set of section E
  (1601 K / 1772 A tables).

---

## 5. Section B — per-diphone unit lists

`len(B)/4` u32 values; each A-record's slice `B[start : start+count]` is a
sorted list of **index-entry numbers** (positions in the index of §3).

Evidence (`scripts/10_probes.py`):

```
kendra: B entries=418495 distinct=418495; valid records=418495 nulls=8496
        B == valid set: True; B entries not valid: 0; valid not in B: 0
amy:    B entries=396683 distinct=396683; valid records=396683 nulls=8164  (same test passes)
```

* B is an exact **permutation of the non-null index-entry numbers** ⇒ every
  unit belongs to exactly one diphone, null slots belong to none.
* All 1601 (K) / 1772 (A) slices are sorted ascending
  (`sorted slices: 1601/1601`, `scripts/06_crossref.py`).
* Example: `'aa-aa'` → `[192511, 200036, 248261, 248420, 281738, 306412]`.

---

## 6. Section C — 36 bytes per index entry

`len(C) == 36 × N` **exactly** in both files (Kendra 15 371 676 = 36×426 991;
Amy 14 574 492 = 36×404 847 — `scripts/07_fullpass.py`), so C record *i* is
positional with index entry *i*.

Layout (36 bytes):

| bytes | type | meaning | evidence |
|---|---|---|---|
| 0–1 | u16 LE | scalar, mostly multiples of 10, range 4…1022; engine converts it with a 1000.0f constant (`FUN_00064878(x, 0x447A0000)`) ⇒ **[INFERENCE]** duration in ms (→ seconds) | byte-position stats (`scripts/10_probes.py`: pos0 top values 60/70/80, pos1 ∈ {0,1,2,3}); `libvoice_kendra.c:2310-2311` |
| 2–6 | 5 × u8 | **5-phone context window**, ids indexing section E (byte2 = left-2, byte3 = left-1, byte4/5 = this unit's diphone, byte6 = right phone) | engine builds 5 phoneme-table pointers from exactly these bytes: `param_3[1..5] = phon_base + byte(2,3,4,5,6)*0x20` (`:2317-2321`); empirical: every sampled unit of diphone `dh-ax` (ids 11,2) has bytes 4,5 = `11,2` — 40/40 (`scripts/11_probes2.py`) |
| 7 | u8 | packed nibbles `(remaining << 4) \| (index+1)` describing the run of consecutive units sharing one section-D root | engine splits byte7 into low/high nibbles (`:2322-2325`); observed sequences per run: size2 → `33,18`; size3 → `49,34,19`; size4 → `65,50,35,20`; … size7 → `113,98,83,68,53,38,23` (= `((size-i)<<4)|(i+1)`), both voices (`scripts/13_final.py`) |
| 8 | u8 | unknown (0…255 observed, often 0) | stats |
| 9 | u8 | constant 0 | 4000/4000 records |
| 10 | u8 | unknown | stats |
| 11 | u8 | flag 0/1 (1 in 59/4000) | stats |
| 12 | u8 | unknown | stats |
| 13 | u8 | ∈ {0xFE,0xFF,0x00} (3286/469/245 of 4000) ⇒ with byte12 forms a mostly-negative s16 | stats |
| 14 | u8 | 26…149 (byte15 = 0 ⇒ u16 range ≤255) | stats |
| 15 | u8 | constant 0 | 4000/4000 |
| 16–31 | 16 B | quantised spectral-like block, values 15…207; 207 = `0xCF` used as filler (silence) — Kendra rec0 = `cf cf … cf` | stats + hexdump below |
| 32–35 | u32 LE | **offset into section D** (monotone over record order; shared by runs of 1–7 consecutive records; last + final size = `len(D)` exactly) | `scripts/08_c_to_d.py`: first offsets `0,17,34,34,34,51,68,68,68,85,…`, `last offset=4860751`, `D len=4860925`, implied final entry = 174; Amy `4708863 + 192 = 4709055` |

Examples (Kendra, `scripts/11_probes2.py`):

```
rec  9: pos0-15 = [30,0, 5,9,11,2,7, 33,35,0,127,0, 85,255,90,0]
rec 17: pos0-15 = [50,0,14,15,11,2,16, 19, 0,0,154,0, 43,255,67,0]
rec 48: pos0-15 = [60,0,15,30,11,2, 9,33, 6,0,133,0, 55,255,74,0]
        ^u16  ^bytes2-6 = (dh,ax) core at 4,5              ^byte7 nibbles
header dump of section C head (scripts/03_dump_regions.py):
 004E27F8: 06 01 00 00 01 02 03 00 00 00 64 00 00 00 43 00
 004E2808: cf cf cf cf cf cf cf cf cf cf cf cf cf cf cf cf   <- silence fill
 004E2818: 00 00 00 00                                       <- D offset 0
 004E281C: 8c 00 00 01 02 03 05 11 19 00 c6 00 b8 ff 33 00 ...
```

---

## 7. Section D — variable-size blocks addressed from C

* D is a byte pool of size `len(D)`; **C's u32 is a root offset** into it.
  Consecutive units share a root (run lengths observed: 1…7; histograms:
  K `{2:67504, 3:55299, 1:42190, 4:16540, 5:3207, 6:266, 7:15}`,
  A `{2:65763, 3:52552, 1:42198, 4:14738, 5:2602, 6:245, 7:5}`).
  Distinct roots: 185 021 (Kendra) (`scripts/10_probes.py`).
* Root-to-next-root distances ("entry sizes") range 17…1020 bytes,
  most common 17 (176 525×), then 134/124/104/114/144/154/164/174… ; their
  sum equals `len(D)` exactly (by construction of the offsets).
* Block contents (small bytes 0…13 dominate the histogram) are a chain of
  sub-blocks linked by u16 **relative** offsets — decompiled parser
  `FUN_00027d48` (`libvoice_kendra.c:2296-2356`) reads, from a root at `p`:
  * `p[0]` → two nibbles, `p[1]` → one byte, `p[2]` → two nibbles,
    9 bytes copied from `p+3`, `p[12]` → **phoneme id → section-E pointer**
    (`+ id*0x20`), `p[13]` → two nibbles, `p[14]` → one byte,
  * `u16 at p+15` → relative offset to a second block, which holds phoneme
    ids at `+0, +2, +6`, parameter bytes, and `u16 at +8` → relative offset
    to a third block (6 bytes + phoneme id + 2 params).
* Observed roots (Kendra, `scripts/10_probes.py`):
  ```
  [0]  size=17 tail_u16=357 hex=0000000000000000000000000000016501
  [1]  size=17 tail_u16=350 hex=0000000101020102000100010201035e01
  [2]  size=17 tail_u16=333 hex=0001010302010201000000010500004d01
  [3]  size=17 tail_u16=326 hex=0103000000000000000000000001034601
  long[58376] size=1020 head=0001000000000000000000000000005903000000…
  ```
  The trailing u16 of a root is a relative link to another block: root0's
  value 357 targets `D+357`, which lies 17 bytes inside the entry whose root
  sits at offset 340 (roots run 0,17,…,340 then jump to 608) — chains cross
  root boundaries, so the root-to-next-root "size" is not a block's extent;
  D behaves as a shared pool.
* **[INFERENCE]** A run of 1–7 consecutive units sharing one D root = one
  recorded word/phrase token: run-length histogram matches word lengths in
  diphones, and the D chain carries that token's phoneme sequence + params.
  No orthography is present anywhere in the container to confirm this
  (see §10).

---

## 8. Section E — phoneme table, and the "gap" payload

### Section E
`len/32` records of `char name[32]`, NUL-padded; **id = record index**
(used by §6/§7 via `base + id*0x20`, see `libvoice_kendra.c:2317-2321`).

Kendra (58): `0, pau, ax, hh, content, eh, L, m, s, d, det, dh, aw, in, w, ih,
n, p, ao, r, t, nx, aux, aa, j, pps, H, uw, l, iy, z, ay, th, ng, ow, L*, cc,
f, ah, k, sh, v, er, b, g, pps$, ey, ae, ch, wp, jh, to, md, uh, zh, oy, lx, mx`

Amy (62): same set **plus** `eax, iax, o, uax` (set difference computed in
verification run; order differs). First record is `0` (edge/boundary symbol —
e.g. the very first unit's context window is `0,0,pau,ax,hh`).

Evidence (`scripts/03_dump_regions.py`):
```
0182E198: 30 00 00 00 00 ...      "0"
0182E1B8: 70 61 75 00 ...          "pau"      (+0x20)
0182E1D8: 61 78 00 00 ...          "ax"       (+0x20)
0182E1F8: 68 68 00 00 ...          "hh"       (+0x20)
```

### Gap payload (high-entropy region)

Region `[section-E end, first index-record)`:
Kendra `[0x182E8D8, 0x7FABF03)` = 108 516 907 B; Amy `[0x17072A0, 0x7C8F6C4)`
= 106 464 292 B.

* Entropy 7.996–8.000 per 64 KB window (near uniform); no `RIFF`/`OggS`/
  `ISEF`/`CDXV` magic inside (the lone `FORM` hit at 0x10E4542 and Amy's
  `RIFF` hit at 0x6F16BA sit in this random-looking region — false positives;
  `scripts/09_isef.py`).
* It is referenced by per-record `(u32 offset, u32 length)` windows (§9).
  Full pass over **all** records: every window lies inside the gap, min offset
  = gap start, `max(offset+length) == first index record` exactly, i.e. the
  gap is exactly bounded by the union of windows (verification run;
  `sum(length) = 361 352 490` K / `346 537 077` A ⇒ heavy overlap — windows
  share bytes ~3.4×).
* Blob prefixes start with a small u16 then arbitrary bytes
  (`3200f1cd7fce…`, `5d00f1cd7fce…`, `7401c754…` — no constant magic);
  repeated 4-grams in the first 2 MB have jittered deltas 71…81.
  Residue-entropy scan for frame sizes 4…64 found no low-entropy alignment.
* **[INFERENCE]** compressed/encrypted audio for the recorded unit corpus;
  the codec lives in the voice libraries (format-id-14 callbacks
  `FUN_0002de60` etc.), which the native-engine agent owns.

---

## 9. Tail unit records (what the index points into)

Each non-null index entry points to a record of `2N + 12` bytes:

```
u16  N            // count of ramp values
u16  ramp[N]      // non-decreasing positions (mostly step 147/148 early)
u16  Y            // scalar, Kendra 2063..4799, Amy 294..4799
u32  gap_offset   // absolute offset into the gap (§8)
u32  gap_length   // byte length of the window
```

Validation (`scripts/07_fullpass.py`, full pass over every record):

```
kendra: records=426991 (null/short slots: 8496)
        len==2N+12 violations: 0
        N range: 3..130; sum(N)=6662123
        ramp non-monotone records: 0
        gap_off non-monotone steps: 0; distinct gap_off: 324820
amy:    records=404847 (null/short slots: 8164)
        len==2N+12 violations: 0
        N range: 4..97; sum(N)=7267240
        ramp non-monotone records: 0
        gap_off non-monotone steps: 0; distinct gap_off: 304687
```

First record, carved verbatim (Kendra, `scripts/03_dump_regions.py`):

```
07FABF03: 20 00 93 00 27 01 ba 01 4e 02 e1 02 75 03 08 04   N=0x0020=32, ramp…
07FABF13: 9c 04 2f 05 c3 05 56 06 ea 06 7d 07 10 08 a4 08
07FABF23: 37 09 cb 09 5e 0a f2 0a 85 0b 19 0c ac 0c 40 0d
07FABF33: d3 0d 66 0e fa 0e 8d 0f 0e 10 6b 10 d4 10 48 11
07FABF43: b9 11 84 0b d8 e8 82 01 3e 02 00 00
          ramp ends 0x11B9=4537 | Y=0x0B84=2948 | off=0x0182E8D8 | len=0x23E=574
```
(76 B = 2·32 + 12 ✓; `0x0182E8D8` = gap start.)

* ramp values are ≤ `8 × gap_length` in 97.3 % (K) / 96.1 % (A) of records
  (violations 11 220/418 495 K, 15 574/396 683 A) ⇒
  **[INFERENCE]** ramp = bit positions inside the window (Y = some duration
  scalar); exact codec semantics belong to the native engine.
* **No text**: fraction of printable bytes > 70 % in body: 0 of 59 839
  sampled records (Kendra) (`scripts/05_sections.py`).

---

## 10. Where the metadata lives (strings inventory)

`scripts/04_strings_by_region.py` (both files):

| item | location |
|---|---|
| container magic `CDXV` | header +0x00 |
| voice/database name `vox_en_us_kendra` / `vox_en_gb_amy` | header +0x04 (32 B) |
| sample rate 22050 | header +0x24 (binary, not a string) |
| language codes | **not in OBB header**: voice name encodes `en_us`/`en_gb`; Java side maps voice→language file: `com/ivona/tts/voicelib/q.java:6` holds `("eng.usa.kendra","vox_en_us_kendra22v","lang_en_us.dat")`, `("eng.gbr.amy","vox_en_gb_amy22v","lang_en_gb.dat")`; native config has `"language_code","en-US"` (`libvoice_kendra.c:7827`) |
| diphone names (1375 K / 1528 A strings ≥4) | section A |
| phoneme names (only `content`, `pps$` are ≥4 chars) | section E |
| version (`versionName 1.6.23.422`, `versionCode 422`) | voice APK `AndroidManifest.xml` — **not in the OBB** (`out/jadx_kendra/resources/AndroidManifest.xml:4-5`) |
| display metadata (`voice_name "Kendra"`, `voice_gender "Female"`, `language_code`, `viterbi_beam 50`, `duration_stretch`, `vox_lexicon`, `zdur_cart`) | `libvoice_en_us_kendra.so` config block (`libvoice_kendra.c:7794-7833`) |
| dictionary words | **none in the OBB**: index/records/B/D are non-printable (0 printable-dominant records); gap strings are incidental (1.28 M runs ≥4 in random data); no `ISEF` inside main OBB (§11) |

The HQ APK's `classes.dex` contains no `obb`/`vox_`/`checksum` strings —
OBB handling is entirely in the native voice libraries
(`libtiver.so` builds `Android/obb/…` paths, `libttsivonavoice.so`,
`libvoice_*.so`; `out/ghidra_dump/libtiver.c:654,821`).

---

## 11. `patch.obb` and `lang_en_us.dat` (ISEF)

Both patches are **ZIP** archives containing exactly one file:

| patch | entry | uncompressed | deflated | date | CRC32 |
|---|---|---|---|---|---|
| Kendra | `lang_en_us.dat` | 74 668 | 74 863 | 2013-02-01 18:09:26 | `6cc78a8f` |
| Amy | `lang_en_gb.dat` | 74 668 | 74 863 | 2013-02-01 18:09:26 | `5dbfd93c` |

(deflated size > stored size ⇒ payload already incompressible.)

`lang_en_us.dat` header (`scripts/09_isef.py`):

```
00000000: 49 53 45 46 00 00 00 01 50 99 2b cc 1f 82 37 87  ISEF....P.+...7.
00000010: 93 97 61 75 ea 59 ea d7 ec bb 42 cd bb db 29 19  ..au.Y....B...).
```

| off | size | type | value | evidence |
|---|---|---|---|---|
| 0 | 4 | magic | `ISEF` | bytes |
| 4 | 4 | u32 **big-endian** | 1 (version?) | `00 00 00 01`; LE reading would be 0x01000000 |
| 8 | 4 | constant | `50 99 2b cc` identical in US and GB files | byte compare |
| 12 | 74 656 | payload | entropy **7.9974**, 256 distinct byte values, per-value counts 244–335 (uniform) | `scripts/10_probes.py` |

Payload tests (`scripts/10_probes.py`): `zlib`, raw deflate, gzip, bz2, lzma
tried at offsets 0/4/8/12 — **all fail**; histogram is uniform ⇒
**[INFERENCE]** encrypted (key material would be in the native libraries).
US vs GB: identical only in bytes 0–11; 74 336 of 74 668 bytes differ in
318 runs.

**Patch ↔ main relationship**: the main OBB contains **no `ISEF` magic**
(`scripts/09_isef.py` scan of both files) and no other patch-replaceable
section; the engine treats the patch purely as an *archive to extract*:
`FUN_000166e8` builds `…/patch.199.<name>`, opens it with minizip
(`unzOpen`), iterates `unzGetGlobalInfo` entries and writes each to disk with
`fopen(…,"wb")` (`out/ghidra_dump/libtiver.c:615-700`). So **the patch does
not replace sections of main; it adds a language file (`lang_*.dat`) that the
engine loads separately** (`FUN_000524e0(…, "lang_")`,
`libttsivonavoice.c:27884`).

---

## 12. Kendra vs Amy

| field | Kendra | Amy |
|---|---|---|
| file size | 152 219 597 | 149 905 560 |
| header name | `vox_en_us_kendra` | `vox_en_gb_amy` |
| sample rate @0x24 | 22050 | 22050 |
| format id @0x28 | 14 | 14 |
| checksum @0x2C | 1333557784 (2012-04-04) | 1334671314 (2012-04-17) |
| index off/len @0x30 | 104 / 3 415 928 | 104 / 3 238 776 |
| index entries N | 426 991 (8 496 null) | 404 847 (8 164 null) |
| pair @0x38/@0x3C | 0x0182E8D8 / 0 | 0x017072A0 / 0 |
| A off/len (records) | 0x341FE0 / 32 020 (1601) | 0x316BE0 / 35 440 (1772) |
| B off/len (u32) | 0x349CF8 / 1 673 980 (418 495) | 0x31F650 / 1 586 732 (396 683) |
| C off/len | 0x4E27F8 / 15 371 676 (36·N) | 0x4A2C80 / 14 574 492 (36·N) |
| D off/len | 0x138B598 / 4 860 925 | 0x1289020 / 4 709 055 |
| E off/len (32 B recs) | 0x182E198 / 1 856 (58 phonemes) | 0x1706AE0 / 1 984 (62 phonemes) |
| gap | 0x182E8D8 … 0x7FABF03 (108 516 907) | 0x17072A0 … 0x7C8F6C4 (106 464 292) |
| records region | 0x7FABF03 … EOF (18 346 186) | 0x7C8F6C4 … EOF (19 294 676) |
| Σ N (frames) | 6 662 123 | 7 267 240 |
| phoneme set | 58 | 58 + {eax, iax, o, uax}, order differs |

**Same layout**, byte-for-byte identical field semantics; only sizes/counts,
voice name, checksum and phoneme inventory differ. All cross-checks
(index contiguity, `Σ count == len(B)/4`, `len(C) == 36·N`, B = permutation
of non-null ids, `len == 2N+12`, D last-offset+len, gap bounds) pass on both.

---

## 13. Native-code cross-references (grounding, read-only)

From the sibling agent's Ghidra output (cited by file:line):

* `libvoice_kendra.c:2207-2260` `FUN_00027bd0` — opens the OBB, `fread`s a
  `0x68`-byte header, checks `magic == 0x56584443`, compares header+0x24
  (sample rate) and header+0x2C (checksum) with the config.
* `libvoice_kendra.c:2432-2574` `FUN_00028008` — full header decode (§2
  table), section pointers, format-id dispatch (`switch` at header+0x28).
* `libvoice_kendra.c:2149-2174` `FUN_00027adc` — index entry access:
  `fseek(off)` + `fread(len)` ⇒ index pair = (file offset, byte length).
* `libvoice_kendra.c:2296-2356` `FUN_00027d48` — section-C record decode
  (5 phone ids → `phon_base + id*0x20`, byte-7 nibbles, u16÷1000.0f, u32 → D)
  and D block chain (phone ids + u16 relative links).
* `libvoice_kendra.c:2394/2653` — the structure is registered as
  `"diphonedb"`; `:2651` `"sample_rate"` ← header.
* `libvoice_kendra.c:7794-7833` — per-voice config constants
  (`name`, `checksum`, `language_code`, `voice_name`, `vox_lexicon`, …).
* `libtiver.c:615-700` — `patch.199.*` opened with `unzOpen` and extracted
  file-by-file (§11).

---

## 14. What could NOT be determined (and what was tried)

1. **Gap codec / audio format.** Tried: magic scan (RIFF/OggS/ISEF/EBML),
   per-residue entropy for frame sizes 4–64 (no alignment), recurring 4-gram
   delta histograms (71–81, jittered), blob-prefix comparison (u16 + random).
   Result: high-entropy payload without identifiable container; decoding is
   the format-14 callback in the native libs (out of scope here).
2. **`ISEF` payload contents.** Tried: zlib/raw/gzip/bz2/lzma at 4 offsets;
   histogram & window-entropy analysis. Uniform random-looking bytes; almost
   certainly encrypted **[INFERENCE]**; key not searched for in this pass.
3. **Meaning of the tail record's `Y` u16** (2063…4799 K / 294…4799 A).
   Checked ratios vs N, `gap_length`, ramp values — no constant relation.
   Reported raw.
4. **Section C bytes 0–1, 8, 10–14 semantics.** Value distributions recorded
   (§6); only byte 0–1 has a decompiled ÷1000.0f conversion → duration
   **[INFERENCE]**.
5. **Whether D runs are word tokens.** Structural evidence only (run lengths
   1–7, phoneme chains inside D, no orthography anywhere) — **[INFERENCE]**.
   Confirmed: run bookkeeping via C byte 7, root sharing via C u32.
6. **Header pair @0x38/@0x3C** (gap offset with length 0). Engine skips it
   when length is 0; whether it is meant as an "audio section" descriptor is
   **[INFERENCE]**.

## 15. Reader/writer checklist (summary)

To read: parse 104-byte header (LE); index at `h[0x30]`, `h[0x34]/8` entries of
`(u32 off, u32 len)`; sections A–E at their pairs; C record ↔ index entry are
positional (36 B each); unit record = `u16 N, u16 ramp[N], u16 Y, u32 gap_off,
u32 gap_len` with `file_len == 2N+12`; phone ids index section E (32 B
records); A `(name[12], start, count)` slices B; B holds sorted unit numbers;
D roots via C+32, chained by u16 relative offsets. To write: emit header
pairs, pad each section to 8 bytes, keep index payloads contiguous to EOF,
and store null slots as `(0,0)`. Endianness is **little-endian throughout**
(the ISEF version field at byte 4 is the sole big-endian u32 observed).
