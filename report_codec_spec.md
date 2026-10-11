# Acoustic codec — clean-room port complete (no Unicorn)

Goal: a **pure-Python** implementation of the de-obfuscated OBB packet stream → PCM that
matches the original engine **bit-exactly**, with no Unicorn at runtime.

Status: ✅ **delivered**. Every stage is ported to stdlib Python, each is byte-verified
against the engine snapshots, and the assembled decoder reproduces the emulator decoder's
PCM bit-for-bit (see §7).

Address convention: `FUN_…` = **Ghidra** addresses of `out/ghidra_dump/libttsivonavoice.c`;
**ELF vaddr = Ghidra − 0x10000** (what the loader and this port use). All static data is read
from `out/codec/tables.bin` by ELF vaddr (`scripts/codec_parts/tables.py`).

---

## 1. Deliverables

| file | role |
|---|---|
| `scripts/codec_spec.py` | the decoder: OBB/packet front-end + codec driver, stdlib only |
| `scripts/codec_parts/prims.py` | 32/16-bit primitives (`u32/s32/s16`, `ld_*/st_*`, `divsi3`, …) |
| `scripts/codec_parts/tables.py` | static image view by ELF vaddr (`tables.bin` + `tables.json`) |
| `scripts/codec_parts/harness.py` | replays the `codec_probe.py` golden vectors through a part |
| `scripts/codec_parts/parse.py` | bit reader (`bitinit`, `af88`, `b1e4`, `b450`) + parse/Huffman decode (stage 1) |
| `scripts/codec_parts/dequant.py` | inverse quantiser (stage 2) |
| `scripts/codec_parts/setup.py` | per-frame synthesis setup (stage 3) |
| `scripts/codec_parts/gain.py` | AGC (stage 4) |
| `scripts/codec_parts/xform.py` | IMDCT + overlap-add (stage 5) |
| `scripts/codec_parts/post.py` | 2-tap post filter (stage 6) |
| `scripts/codec_parts/dsp.py` | shared DSP helpers (`f1496c0`, `f14dc30`, `f14dca4`, `f150a14`, `f14f940`, `f151448`) |
| `scripts/codec_parts/resample.py` | output-rate conversion (`FUN_0014b668/6d0/4a8/4c494` + the 2× stage) |
| `scripts/codec_parts/test_resample.py` | resampler vs engine oracle (both voices) |
| `scripts/verify_codec.py` | chained stage verification from a fresh reset |
| `scripts/compare_spec.py` | acceptance: `codec_spec.py` vs the emulator oracle |
| `scripts/trace_calls.py`, `scripts/trace_af88.py` | diagnostic: log the engine's register arguments / range-decoder state (used to recover the call arguments Ghidra omits and to diff the decode sequence) |

Usage

```sh
~/venvs/re/bin/python scripts/codec_spec.py --record 3 --out out/gap/spec3.wav
~/venvs/re/bin/python scripts/codec_spec.py --record 0 --dump-stage xform     # diff buffers
~/venvs/re/bin/python scripts/codec_spec.py --obb "<amy obb>" --record 1 --rate 22050 --out amy1.wav
```

`codec_spec.py` imports **no** emulator/Unicorn code: only `array, os, struct, sys, wave`
plus the ported modules (and `numpy` is not used at all).

---

## 2. Container / packet layer (solved earlier — see `report_gap_codec.md`)

Re-implemented in `codec_spec.py` (`Obb`, `deobfuscate`, `iter_packets`):

* a unit record is `{u16 N; u16 ramp[N]; u16 Y; u32 gap_off; u32 gap_len}` in the OBB index;
* the gap is one continuous stream of `u16le len; u8 payload[len]` packets; the record's
  window `[gap_off, gap_off+gap_len)` is a whole number of packets;
* payload XOR key = `u32le(header+0x2C checksum) ‖ (payload[n&~3:] + zero-pad to 4)`, applied
  to bytes `i < n&~3` (hand-written at `FUN_00067a14`, ELF `0x57a14`).

---

## 3. Codec context layout (`0x3570` bytes)

The context is byte-addressed in the port; the dump indexes it as `int*` (so `ctx[i]` in the
dump = byte `4*i` here).

| byte | dump idx | meaning |
|---|---|---|
| `0x0000/4/8/c/10` | `0…4` | range decoder: packet length, byte pos, code, range, error (0=ok) |
| `0x0014` | `5…` | packet copy (`len` bytes); the decoder reads bytes at `0x18+pos` = packet byte `4+pos` |
| `0x0414` | | previous Q16 band gain (dequant) |
| `0x1318` | | 16-word synthesis state (dequant) |
| `0x1538` | | 480-word dither/spectrum scratch (dequant) |
| `0x1cb8` | | 120-word working spectrum (dequant) |
| `0x2438` | `0x90e` | 480 int16 samples of the previous frame (`memcpy` before `gain`) |
| `0x27f8` | | 480 int16 dequant output |
| `0x2bb8` | `0xaee` | reset scalar (100) |
| `0x2bbc` | `0xaef` | running band-gain index (parse) |
| `0x2bc4` | `0xaf1` | last block/channel-type symbol |
| `0x2bc8` | `0xaf2` | post-filter state (2 ints) |
| `0x2bd0/4` | `0xaf4/5` | post-filter coefficient table pointers |
| `0x2bd8` | `0xaf6` | rate index (24 → 24 kHz) |
| `0x2be0/4/8` | `0xaf8/9/a` | 480, 120, 16 (frame length, band stride, bands) |
| `0x2bec` | `0xafb` | 16 int32 band amplitudes of the previous frame |
| `0x2c2c` | `0xb0b` | flag (1 → parse forces `fi[0x28]=4`) |
| `0x2c30` | `0xb0c` | bits left after parse |
| `0x2c34` | `0xb0d` | frame counter (0 → (re)init the bit reader) |
| `0x2c38/0x2c3c` | `0xb0e/f` | frame counter of the last packet, packet-continuation flag |
| `0x2c40` | `0xb10` | 2-bit parsed flag (must be 1 to continue a packet) |
| `0x2cec/0x2cf0` | `0xb3b/c` | codebook struct pointer for block type 0 / 1 |
| `0x2cf4` | `0xb3d` | 1-bit parsed flag |
| `0x347c/0x3480` | | per-band ramp / value (nbands ints each) |
| `0x34c0` | | overlap-add history |
| `0x3500/0x3504/0x3508` | | xform lerp state, LCG state, last rate |
| `0x350c` | `0xd43` | first-frame flag (0 → transform path) |
| `0x3510` | `0xd44` | block type copy (setup) |
| `0x3514` | | setup step |
| `0x3518…` | | 5 shorts + 16 shorts (setup) |
| `0x3544/0x3550/0x3554` | | AGC latch, mantissa, exponent |
| `0x3558…0x3568` | | setup outputs (`fi` copies) |
| `0x356c` | | rate cache (setup) |

Reset (`FUN_0014e248`, ELF `0x13e248`): `memset(ctx,0,0x3570)`; `FUN_00148cb0(ctx,24)`;
`ctx[0x2c2c]=1`; `ctx[0x414]=0x10000`; `FUN_0014dca4(ctx)`; `FUN_00149e34(ctx)`.

---

## 4. Stage 1 — bit reader + parse

### 4.1 Range decoder (`FUN_0014af88`, ELF `0x13af88`)

The bit reader **is a range decoder whose state lives at the head of the codec context**:

* init `FUN_0014b17c` (ELF `0x13b17c`): error `-8` if `len ≥ 0x401`; otherwise copy the packet
  to `ctx+0x14`, set `code = big-endian(packet[0:4])`, `range = 0xFFFF`, `pos = 0`, `err = 0`.
* decode: `table` is a `u16` non-decreasing cumulative-frequency table; `param_4` is the
  starting index (= number of symbols).  If `code < range*table[idx]` it walks *down* to the
  interval containing `code`, else *up* until an entry equals `0xFFFF`; the symbol index is the
  interval's lower index.  `range *= table[hi]-table[lo]`, `code -= range*table[lo]`; then
  renormalise: when `range ≥ 0x1000000` shift `range` down 16 bits and consume nothing; otherwise
  shift `range` down 8 bits and append one stream byte, and when `range < 0x10000` append a second
  byte as well (if the stream is exhausted, `code` is shifted left 16 instead of reading).  A
  stream byte is at `ctx[0x18+pos]` and `pos` is bounded by `ctx[0]`.
* error codes written to `ctx[4]`: `-2` (table ran off), `-3` (code too wide for the range),
  `-4` (zero range); the out word is set to 0 on any error.
* `FUN_0014b1e4` (ELF `0x13b1e4`) reports the consumed position; it returns
  `bitpos*8 + nlz(range-1) - 14` in `r0` and stores `(bitpos*8 + nlz - 7) >> 3` — both are used
  (the parse tail uses the byte position, the end check uses `r0 & 7`).

### 4.2 `FUN_00148190` (ELF `0x138190`) — parse entry

Reads, in order (tables quoted as ELF vaddrs):

1. **first frame only** (`ctx[0x2c34]==0`): block-type codebook `0x17d334` (n=2); if the symbol
   is > 3 → error `-7`; then reconfigure via `FUN_00148cb0(ctx, {8,12,16,24}[sym])`.
2. block/channel type `s`: `0x17e2d4` (n=2) on the first configured frame, else
   `0x17e2e4 + ctx[0x2bc4]*10` (n=2).  `fi[0x98]=s&1`, `fi[0x9c]=s>>1`, `ctx[0x2bc4]=s`.
3. four 5-bit reads: `0x178bf4 + (s>>1)*0x82` with n=0x20 on the first frame, then
   `0x178cfc` (n=5) three times.
4. `FUN_00148f20` (ELF `0x138f20`) maps them to `fi+0x10…0x1f` using
   `FUN_0014966c` (ELF `0x13966c`, index→amplitude) and `ctx[0x2bbc]`.
5. codebook struct pointer `cb = ctx[0x2cec + 4*fi[0x9c]]` (`0x185650` for type 0,
   `0x185780` for type 1).  Struct fields: `[0]`=count(10), `[1]`=amplitude pointer table,
   `[2]`=amplitude base table, `[4]`=bit-length table pointers, `[5]`=bit-length counts.
   `FUN_0014b104` reads `count` symbols from `(T.u32(pt[4]+4k), T.u32(nt[5]+4k))` into a
   10-int vector; `FUN_001497a8` (ELF `0x1497a8`) turns the codebook into the 16 int32 band
   amplitudes (with its monotone-isation/saturation loop, `FUN_0014d944`).
6. `fi[0xa0] = af88(0x17d344, 4)`; if `ctx[0x2c2c]==1` it is forced to 4.
7. `f1496c0(fi, 0x44, lb8, 0, 16)` — spectral refinement of `lb8` (see §6); if `fi[0xa0] < 4`
   a lerp from `ctx+0x2bec` is written to `fi+0x24` through `f1496c0` again, else copied.
   `ctx+0x2bec ← lb8` (16 int32).
8. if `ctx[0x350c] != 0` (not the first frame) both arrays are scaled by
   `f14dc30(…, 0xF852)`.
9. if `fi[0x9c]==0` the **codebook/module branch** runs: for rate 24, `count=128` (at
   `0x17dba0`) and the frequency table is `.got[0x185c60] → 0x17d89c`; then a 0x11-entry read
   (`0x17dba4`); `FUN_0014899c` (ELF `0x13899c`) fills `fi[0..3]`; a 1-bit symbol selects one of
   `PTR_DAT_00195514` / `PTR_DAT_0019552c` (`0x185514` / `0x18552c`) and four groups of five
   shorts are copied to `fi+0x64…0x8a`; finally `fi+0x8c = s16(0x17d37c + 2*sym)`.  Otherwise the
   engine zeroes those `fi` fields.
10. `fi[0x20] = af88(0x17d364, 2)`.
11. `FUN_00148a20(ctx, fi, coeffs, 480)`:
    * `fi[0x94] = af88(0x17df44 + fi[0x9c]*0x14, 4)`;
    * **30 bands** (`480>>4`): symbol = `af88(0x17dc34 + fi[0x94]*0x2a, 6)`; a symbol of
      `0x13` escapes: repeat `af88(0x17ddae, 6)` until ≠ `0x13`, the iteration count is the
      band's extra-bit count;
    * per band with symbol > 0: `FUN_0014d100(coeffs + band*0x40, ctx, symbol)` decodes a
      16-int vector with a 4-level bit tree (`0x17e10c`/`0x17e040`/`0x17dfd8`/`0x17df94`,
      indexed through `0x17e2ac`); otherwise the 64-byte block is zeroed;
    * per band with an escape count > 0: each of the 16 ints gets that many low bits appended
      from `af88(0x17d304, 1)`;
    * `FUN_0014e0ec` (ELF `0x13e0ec`) applies signs to all 480 coefficients using the
      per-band probability `0x17e30c[s16(fi[0x98]+2*fi[0x9c])*9 + fi[0x94]]` (table
      `{0, p, 0xFFFF}`, one bit per non-zero coefficient).
12. `ctx[0x2cf4] = af88(0x17d318, 1)`; `ctx[0x2c40] = af88(0x17d354, 2)`.
13. `ctx[0x2c30] = ctx[0] - bytepos`; `< 0` → error `-6`; `== 0` → `FUN_0014b450` end check
    (may set error `-5`).

`FUN_00148cb0` (ELF `0x138cb0`) selects the band count (10 for rate 8, else 16), the codebook
pointers, the post-filter tables and zeroes the codec scratch regions; it is a no-op when the
rate is unchanged.

### 4.3 Fixed-point conventions

Every stage keeps its scale explicitly; the port reproduces each one literally (32-bit wrapping,
arithmetic shifts, truncating 16-bit stores):

| stage | representation |
|---|---|
| range decoder | `code`/`range` are unsigned 32-bit; `range` is renormalised into `[2^16, 2^24)` (`≥2^24` → shift 16, no byte; else shift 8 and read a byte; `<2^16` → read two) |
| parse band amplitudes | `FUN_0014966c` maps a 0…0xf7f log index to a linear amplitude `2^(i>>7)·(i&0x7f + correction)`; the 16 amplitudes in `ctx+0x2bec` are int32 with `0x8000` as full scale |
| parse coefficients | int32; the sign pass multiplies by ±1, the escape pass appends low bits (`v = 2v + bit`) |
| dequant | band gain is **Q16** (`ctx[0x414] = 0x10000` = 1.0); the reciprocal/mix steps are Q16 products with `>>16` corrections |
| setup | scale-shift pairs `(short)(v*mult >> shift)` with `mult` derived from the band energy |
| gain (AGC) | per-sample gain is **Q12** (`0x1000` = 1.0), applied as `(short)(x*g >> 12)`, ramp clamped at `0x1000` |
| xform | transform scale `0x4000000` (2²⁶), Q31 twiddle `0x5a82799a` = sin(π/4)·2³¹; the IMDCT/Q15 state is int32 and the overlap-add output is clamped to int16 |
| output-rate conversion | the interpolator works on Q16 phase (`uVar5>>16` = sample index, low 16 bits = phase) against the 3-tap Q13 tables at `0x178894`/`0x178896`/`0x178898` |
| post | 2-tap filter, coefficients read as Q15 shorts from `0x17d2d4`/`0x17d2d8`, state 2 × int32, output `((uVar3 >> 12) + 1) >> 1` then clamped |

---

## 5. Stages 2–6 (per frame)

| stage | entry (ELF) | what it does | verification |
|---|---|---|---|
| dequant | `FUN_0014e4ec` `0x13e4ec` (+ `FUN_0014e29c`, `FUN_001507bc`) | 4 bands × 120 samples: normalises the band gain, derives a Q16 reciprocal from `ctx[0x414]`, scales the 16-word state (`ctx+0x1318`), mixes a 120-word spectrum chunk (`ctx+0x1538` → `ctx+0x1cb8`) and writes 120 int16 into `ctx+0x27f8`; after band 4 the 480 samples are copied to `samp` | `dequant.py` 55/55 |
| setup | `FUN_0014add4` `0x13add4` (+ `FUN_00149e34`, `FUN_0014a04c`) | builds the per-frame synthesis state (`ctx+0x3510…0x3568`), scale-shifts 5+16 shorts | `setup.py` 60/60 |
| gain | `FUN_00149e54` `0x139e54` (+ `FUN_0014d9b0` `0x13d9b0`, `FUN_00149d84` `0x139d84`) | AGC: energy sum of squares (`ctx[0x3544]` latch, `ctx[0x3550]/[0x3554]` mantissa/exponent), per-sample gain ramp `x*g >> 12` clamped at `0x1000` | `gain.py` 55/55 |
| xform | `FUN_0014dd18` `0x13dd18` (+ `FUN_0014dca4` `0x13dca4`, `f1496c0`, `FUN_0015027c` `0x14027c` / `FUN_00150028` `0x140028`) | per-band ramp update, band selection, `ctx[0x3500]` lerp, the inverse transform (16 bands → `FUN_0015027c`), overlap-add with `ctx+0x34c0` → 480 samples | `xform.py` 55/55 |
| post | `FUN_0014dafc` `0x13dafc` | 2-tap post filter over 480 samples, coefficient tables `0x17d2d4`/`0x17d2d8` (rate 24), state at `ctx+0x2bc8` | `post.py` 55/55 |

`xform` calls the shared DSP helpers in `dsp.py`: `f1496c0` (ELF `0x1396c0`) turns 16 int32
coefficients into 16 Q15 shorts via `f150a14` (`0x140a14`, cosine-table interpolation + a
Levinson recursion) and `f14f940` (`0x13f940`, one refinement pass), and `f14dc30`
(`0x13dc30`) scales samples in place.  `f150a14` reads a 129-entry Q13 table
(`0x2000·cos(π i/128)`) through the `.got` slot at `0x185db0` → ELF `0x17e354`.

---

## 6. Driver

`codec_spec.Spec` mirrors `FUN_00147c58` (ELF `0x137c58`) → `FUN_00147f74` (ELF `0x137f74`):

* a new packet resets the frame counter when `ctx[0x2c3c]==0`; the bit reader is (re)initialised
  when `ctx[0x2c34]==0`;
* per frame: `parse` → `ctx[0x2c34]++` → `dequant` → `setup(…, flag=0)` →
  `memcpy(ctx+0x2438, samp, 960)` , `ctx[0x350c]=0`, `ctx[0x2c2c]=0` → `gain` → `xform` → `post`;
* after each frame the continuation flag is recomputed: continuous while `ctx[0x2c30] ≥ 1`,
  `ctx[0x2c40] == 1` and `ctx[0x2c34] ≤ 4`; otherwise the packet ends (this is what makes a
  packet exactly 5 frames / 2400 samples);
* a 6th call is never made; `ns = 480` per frame.

**Output-rate conversion** (same function, `FUN_00147c58`): the codec always runs at
`ctx[0x2bd8]*1000 = 24000` Hz.  When the wrapper asks for a different rate the frame's 480 samples
are produced in a scratch buffer and then passed through the resampler at `ctx+0x2c44`
(`FUN_0014b668` reset, `FUN_0014b6d0` setup, `FUN_0014b4a8` per frame, ported in
`scripts/codec_parts/resample.py`), and the frame reports
`ns = divsi3(out_rate*480, 24000)` samples (441 for the shipped 22050 Hz voices).  The shipped OBBs
declare 22050, so `decode_unit.py --rate 22050` really is resampled and is **not** the same PCM as
`--rate 24000`; `codec_spec.py` defaults `--rate` to the OBB's declared rate (22050) and implements
the same conversion.  `--rate 24000` disables it and yields the codec-domain samples.

Per unit: reset (`FUN_0014e248`), feed every packet of the window, discard the first `Y`
samples, keep `ramp[N-1]` (zero-padded if the window is short) — matching
`decode_unit.py`/`FUN_00067a14`.

---

## 7. Verification

All numbers below are actual command output; the emulator oracle is `scripts/decode_unit.py`.

| check | command | result |
|---|---|---|
| setup | `~/venvs/re/bin/python scripts/codec_parts/test_setup.py` | `files=6 setup vectors=55 byte-identical=55 failed=0` |
| gain | `~/venvs/re/bin/python scripts/codec_parts/gain.py` (via `harness.check('gain', …)`) | `gain: vectors=55 byte-identical=55 failed=0` |
| post | `~/venvs/re/bin/python scripts/codec_parts/post.py` | `post: vectors=55 byte-identical=55 failed=0` |
| parse | `~/venvs/re/bin/python scripts/codec_parts/parse.py` | `parse: vectors=55 byte-identical=55 failed=0` |
| dequant | `~/venvs/re/bin/python scripts/codec_parts/dequant.py` | `dequant: vectors=55 byte-identical=55 failed=0` |
| xform | `~/venvs/re/bin/python scripts/codec_parts/xform.py` | `xform: vectors=55 byte-identical=55 failed=0` |
| output-rate conversion | `~/venvs/re/bin/python scripts/codec_parts/test_resample.py` | `kendra: 5/5 records bit-identical`, `amy: 5/5 records bit-identical` (24000 → 22050) |
| chained stages | `~/venvs/re/bin/python scripts/verify_codec.py` | `chained verification: files=6 steps=336 buffer-compares=1344 failed=0` |
| single-stage dump | `codec_spec.py --record 0 --dump-stage xform` vs `rec000000.pkl` | ctx 13680/13680, samp 8192/8192, frame_info 512/512 identical |
| **end-to-end, OBB rate 22050** | `~/venvs/re/bin/python scripts/compare_spec.py --voice kendra --count 60` | 59/59 bit-identical, 0 failed |
| **end-to-end, OBB rate 22050** | `~/venvs/re/bin/python scripts/compare_spec.py --voice amy --count 60` | 59/59 bit-identical, 0 failed |
| end-to-end, codec rate | `… --voice kendra --count 60 --rate 24000` | 59/59 bit-identical, 0 failed |
| end-to-end, codec rate | `… --voice amy --count 60 --rate 24000` | 59/59 bit-identical, 0 failed |

The per-stage checks compare the port's output **and the mutated context** against what the
engine left behind after the same function call (all 55 calls in every stage, across the six
recorded records 0/1/3/5/13/100).  `verify_codec.py` is stronger: it starts from a fresh reset
and carries the ported state through the whole chain, comparing every intermediate buffer after
every stage — so no divergence can be masked by a per-stage snapshot.

End-to-end acceptance — `codec_spec.py` PCM vs `decode_unit.py` PCM (the engine under Unicorn),
compared sample by sample over evenly spread records (0 → near the end of the index), including
records far into each file.  `decode_unit.py --rate 22050` (the OBB's declared rate) is the
acceptance configuration:

```
$ ~/venvs/re/bin/python scripts/compare_spec.py --voice kendra --count 60
OBB .../com.ivona.tts.voicebeta.eng.usa.kendra/main.199...obb  name=vox_en_us_kendra  recs=426991
checking 59 records
comparing at 22050 Hz
RESULT vox_en_us_kendra: picked=59 tested=59 bit-identical=59 failed=0  (266.0s)
  records: [0, 7239, 14475, ..., 412518, 419753]

$ ~/venvs/re/bin/python scripts/compare_spec.py --voice amy --count 60
OBB .../com.ivona.tts.voicebeta.eng.gbr.amy/main.199...obb  name=vox_en_gb_amy  recs=404847
checking 59 records
comparing at 22050 Hz
RESULT vox_en_gb_amy: picked=59 tested=59 bit-identical=59 failed=0  (239.9s)
  records: [0, 6866, 13724, ..., 391122, 397984]
```

and the same comparison at the codec's native rate (resampler disabled):

```
$ ~/venvs/re/bin/python scripts/compare_spec.py --voice kendra --count 60 --rate 24000
RESULT vox_en_us_kendra: picked=59 tested=59 bit-identical=59 failed=0  (158.2s)
$ ~/venvs/re/bin/python scripts/compare_spec.py --voice amy --count 60 --rate 24000
RESULT vox_en_gb_amy: picked=59 tested=59 bit-identical=59 failed=0  (150.3s)
```

| voice | rate | units tested | bit-identical | failed |
|---|---|---|---|---|
| `vox_en_us_kendra` | 22050 (declared) | 59 | **59** | 0 |
| `vox_en_gb_amy` | 22050 (declared) | 59 | **59** | 0 |
| `vox_en_us_kendra` | 24000 (codec) | 59 | **59** | 0 |
| `vox_en_gb_amy` | 24000 (codec) | 59 | **59** | 0 |

Also checked CLI-to-CLI, matching the acceptance command literally:

```
$ ~/venvs/re/bin/python scripts/codec_spec.py --record 0 --rate 22050 --out /tmp/spec.wav
$ ~/venvs/re/bin/python scripts/decode_unit.py --record 0 --rate 22050 --out /tmp/emu.wav
$ cmp /tmp/spec.wav /tmp/emu.wav && echo IDENTICAL
IDENTICAL
```

Every sampled unit is bit-identical at both rates, so there is **no residual divergence** and no
stage/condition left unexplained.  (The units differ in length — 1 415 to 8 732 samples across the
two voices — and come from every region of the index, including the far end; a few of the OBB's
index entries are out of range and `compare_spec.py` skips them.)

Note that the 22050 output is the engine's *resampled* signal (rms 2145 for unit 0 vs 916 at
24000), which is why the output-rate conversion had to be ported as well: `decode_unit.py --rate
22050` really does resample internally.

---

## 8. What still depends on emulation

Nothing in the decoding path.  The remaining emulator users are **verification-time only**:

* `scripts/decode_unit.py` + `emu/armemu.py` (Unicorn) — the reference decoder used by
  `compare_spec.py` and by `codec_probe.py` to record golden vectors;
* `scripts/codec_probe.py` — produced `out/codec/steps/rec*.pkl` (already on disk);
* `scripts/codec_tables.py` — one-time extraction of `out/codec/tables.bin` (+ `tables.json`,
  sha256 `ac5d586a…`) from the `.so`.  `codec_spec.py` only *reads* that dump.

Not ported (not exercised by any shipped voice, and unreachable for the shipped 24000 → 22050 pair):
the remaining polyphase converters `FUN_0014bf38`, `LAB_0014bdf8`, `DAT_0014ca68`, `LAB_0014be08`,
`LAB_0014cba8`, `LAB_0014ca6c` and the `0x13cba8` 2× filter for in-rates ≥ 24 001.  `resample.py`
selects them exactly like the engine does but raises `NotImplementedError` naming the branch and the
engine symbol (never a silent stub).  Every other rate pair out of the 140 combinations of
{8000…96000}² either reproduces the engine's setup struct byte-for-byte or takes those paths;
for pairs involving 24000 → 22050 the port is sample-exact (validated below).

## 9. Notes / deviations

* The ported modules use explicit 32-bit masking, truncated 16-bit stores and arithmetic right
  shifts to reproduce ARM semantics; `divsi3` replaces `__divsi3`.
* Ghidra under-states two stack arrays in `FUN_00148a20` (`local_11c[29]` + `iStack_a8` are one
  30-int array, `local_a4[30]` is read through `&iStack_a8+4`): the band *symbol* array drives
  `FUN_0014d100`, the *escape-count* array drives the extra-bit loop.  Getting this order right
  was required for bit-exactness.
* `FUN_0014d100`'s early bail-out paths write coefficients 0 and 1 as **zero** (they jump to a
  shared store), not "leave unchanged" — also load-bearing.
* `FUN_0014af88` reads stream bytes at `ctx+0x18+pos` while the packet copy starts at
  `ctx+0x14`; the first four bytes are consumed into `code` at init, so this is deliberate.
