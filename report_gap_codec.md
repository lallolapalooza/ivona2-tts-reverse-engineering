# The OBB "gap" payload (`main.199.*.obb`) — decoded

Status: **solved and reproduced**. `scripts/decode_unit.py` decodes any unit of either shipped
voice (`vox_en_us_kendra`, `vox_en_gb_amy`) to PCM and writes a WAV whose sample count is exactly
the record's own `ramp[N-1]` field. No secret key is required: the payload is **not encrypted**, it
is a continuous stream of length-prefixed packets protected only by a *self-keyed XOR obfuscation*
whose key is derived from a public header field (the `checksum`) plus the packet's own tail bytes.

Address convention: `FUN_…` addresses are **Ghidra addresses** of
`out/ghidra_dump/libttsivonavoice.c`; **ELF addr = Ghidra addr − 0x10000** (used by the emulator).
Byte offsets are *file offsets* of `IVONA 2/…kendra…/main.199….obb` unless stated.

---

## 1. What the gap actually is

The "gap" region (Kendra `[0x182E8D8, 0x7FABF03)`, 108 516 907 B) is **one continuous stream of
packets**:

```
packet := u16le len ; u8 payload[len]
```

* **Verified**: parsing the stream from the gap start, every one of the first 15 015 unit records'
  `gap_off` lands exactly on a packet boundary (`scripts` run; `→ 15015/15015`), and for every
  sampled record the walk of its window (`gap_len` bytes) consumed exactly `gap_len` bytes (no
  partial trailing packet). Records therefore reference **overlapping windows of whole packets**.

Example — record 0 (Kendra), record bytes at `0x7FABF03`:

```
N=32  ramp[32] (u16le, last = 4537)  Y=2948  gap_off=0x182E8D8  gap_len=574   (len == 2N+12 = 76)
window packets: (len 50, 51, 93, 372)  → offsets 0, 52, 105, 200  → end 574 == gap_len
```

Record 1 (`gap_off=0x182E941` = gap start + 105) starts exactly on record 0's third packet
(`105`), and its window `[105, 105+821)` continues past record 0's end. Each record's window is
therefore the codec context it needs (see §5), not an independent container.

## 2. De-obfuscation (reversible, no secret)

Every packet payload `p` (length `n`) is XOR-obfuscated with an 8-byte repeating key:

```
m   = n & ~3                                    # multiple of 4
key = u32le(header+0x2C /*checksum*/)  ‖  (p[m:n] zero-padded to 4 bytes)
p[i] ^= key[i % 8]     for i = 0 .. m-1         # the last n&3 bytes are left untouched
```

* **Verified byte-exact**: hooking the decoder entry `FUN_00147c58` (ELF `0x137c58`) and comparing
  the memory it receives against the Python transform — 4/4 packets of record 0 match
  (`scripts/decode_unit.py --record 0 --dump-packets`, and the earlier probe run).
* Key example, record 0: `checksum = 0x4F7C7A18` → key for packet 0 =
  `18 7a 7c 4f d3 7f 00 00` (first 4 bytes = the checksum; last 4 = the packet's own bytes 48–49 +
  zero padding).
* The `checksum` is a plain field of the public OBB header (Kendra `0x4F7C7A18`, Amy `0x4F8D77D2`);
  the tail bytes come from the packet itself. **No key material is hidden and no external secret is
  needed.**

This is the transform hand-written at **`FUN_00067a14` (ELF `0x57a14`)** — for packets with
`n%4∈{1,2,3}` it first copies `p[m:n]` into the key slot at `state+0x1c`, zero-fills `state+0x18+…`,
and XORs the first `m` bytes with the 8-byte key at `state+0x18` modulo 8 (see the decompiled body,
dump lines ≈47 373–47 420). The same block appears in the sibling format-12 decoder
`FUN_000685c4` (dump ≈47 780–47 810), i.e. the obfuscation is shared by all container variants.

## 3. Where the engine consumes `gap_off` / `gap_len`

`FUN_0005f49c` (ELF `0x4f49c`) opens the file (`fread(hdr,0x68,1)`, magic `0x56584443` = `"CDXV"`),
parses the 7 `(u32 off,u32 len)` header pairs, and `switch`es on **header+0x28 = container type**.
Kendra/Amy both store **14** (`0e 00 00 00`), so case `0xe` installs the callbacks:

| vtable slot | function | role |
|---|---|---|
| `+0x0d` (init) | `FUN_00067f94` (ELF `0x57f94`) | build codec wrapper |
| `+0x0e` (dtor) | `LAB_000679e0` | free |
| `+0x0f` (decode) | **`LAB_00067db8`** (ELF `0x57db8`) | **record → window → PCM** |

*(For other voices/`type=0xc` the equivalent is `FUN_000685c4` (ELF `0x685c4`), the function the
main agent traced; `type=8` uses `FUN_00068378` + Vorbis-family headers. The shipped Kendra/Amy files
are `type=14` and take the `LAB_00067db8` path.)*

`LAB_00067db8` (ARM, disassembled at file `0x57db8`) reads, from the raw record `param_2`:

```
r4  = u16le [rec+0]              -> N
      fseek offset = u32le [rec+2N+4]   -> gap_off
      fread  length = u32le [rec+2N+8]  -> gap_len
      sb  = u16 at [rec+2N]             -> ramp[N-1] = total unit samples
      Y   = u16le [rec+2N+2]            -> codec-delay skip
```

then `malloc(gap_len)`, `malloc(2*samples)`, `fseek(file, gap_off,0)` (`FUN_0005b2cc`),
`fread(buf,1,gap_len,file)` (`FUN_0005b338`, the string `"**Error: voxdb read"`), and calls
`FUN_00067a14(wrapper, buf, gap_len, Y, pcm, samples)`. The returned PCM is then sliced into `N`
segments using `ramp[]` (`FUN_00062608/062688/0624c8/0624b0/062668`, `FUN_00027efc`) — i.e. `ramp`
are the intra-unit boundaries (pitch marks / periods); this slicing is *not* needed to obtain the
unit waveform.

### Crypto callers — none touch the gap (task item 2)

All call sites of the crypto primitives were enumerated in `out/ghidra_dump/libttsivonavoice.c`:

| primitive | application-level callers | purpose |
|---|---|---|
| `FUN_000b2684` (BN_bin2bn) | `FUN_000346d4` (≈12682/12685), `FUN_00052154` (≈32113/32115) | ISEF pubkey `n,e`; certificate pubkey `DAT_0015c154` |
| `FUN_000b34fc` (RSA) | `FUN_000346d4` (≈12697), `FUN_00051c70` (≈68109, OpenSSL `rsa_sign.c`) | ISEF block; certificate signature |
| `FUN_000b8fe0` (EVP_CipherInit) | `FUN_000346d4` (≈12702) — **only** | ISEF AES-256-CBC |
| `FUN_000b950c` / `FUN_000b974c` | ≈12714/12716 (`FUN_000346d4`), ≈70385/70403 (`FUN_000b8dc4`/`FUN_000b8e40`, OpenSSL EVP dispatch) | ISEF decrypt; OpenSSL internals |

The only two *application* users are the `ISEF` lexicon decryption (`report_isef.md`) and the
certificate signature verifier; the gap path is absent from both. **The gap is not RSA/AES-encrypted.**

## 4. The codec

The de-obfuscated packets are pushed into an embedded **proprietary fixed-point transform codec**:

* context is `0x3570` bytes (`FUN_0014794c`, ELF `0x13794c`, stores `0x3570`); reset/init
  `FUN_0014e248` (ELF `0x13e248`);
* frame decode `FUN_00147c58` (ELF `0x137c58`) → `FUN_00147f74` → parse `FUN_00148190`,
  synthesis `FUN_0014add4` / `FUN_00149e54` / `FUN_0014dd18` / `FUN_0014dafc`;
* bit/Huffman reader `FUN_0014af88` (ELF `0x14af88`) reads codebook indices from **static tables in
  `.rodata`** (`DAT_0018d334`, `DAT_0018d4ec/d690/d898/dba0` selected by a block/channel-type enum
  `{8,12,0x10}`, `PTR_DAT_00195514/9552c`, `DAT_00188bf4 + idx*0x82`);
* an integer MDCT/butterfly with Q31 twiddles (constant `0x5a82799a` = sin(π/4)·2³¹);
* native rate index `ctx[0xaf6] = 24` → **24 000 Hz** (set by the reset path), matching the
  wrapper's target rate, so **no resampling happens inside the decoder**.

Observations:

* each packet yields **2400 samples** (5 codec frames × 480 samples = 100 ms at 24 kHz);
* the codec is **inter-frame stateful**: the same packet decoded after different preceding packets
  gives different samples (record 0's packets 2/3 vs. record 1's first two packets — same bytes,
  only 2163/2400 and 2011/2400 samples equal). This is exactly why records reference *overlapping*
  windows and why `Y` (≈2 500–4 700 samples of warm-up) is discarded.

**[INFERENCE]** the static-codebook + integer-MDCT + block/channel-type structure resembles
RealAudio "Cook"/G2, but it is **not** identified with certainty; it is **not** deflate/zlib/gzip/
bz2/lzma (all fail), not Ogg-Vorbis (all packets would need a header type bit; none do), and not
MP3/AAC (no sync/ADTS; codebooks are static, not in-stream). The decoder is best reproduced by
**emulating** `FUN_00147c58` (as this tool does) rather than re-implementing it.

## 5. Decoder: `scripts/decode_unit.py`

Run with the project venv (needs `pyelftools` + `unicorn`, see `emu/armemu.py`):

```sh
~/venvs/re/bin/python scripts/decode_unit.py --record 3 --out out/gap/kendra_unit3.wav
~/venvs/re/bin/python scripts/decode_unit.py --record 0 --dump-packets          # show packets+keys
~/venvs/re/bin/python scripts/decode_unit.py --record 13 --verify               # engine vs python
~/venvs/re/bin/python scripts/decode_unit.py --list                             # first non-empty recs
~/venvs/re/bin/python scripts/decode_unit.py --record 1 --python-decode         # pure front-end
~/venvs/re/bin/python scripts/decode_unit.py --obb <amy obb> --record 1 --out amy1.wav
```

Options: `--obb`, `--record N`, `--out FILE.wav`, `--rate HZ` (default **24000** = codec rate),
`--python-decode`, `--verify`, `--dump-packets`, `--list`.

The script:
1. parses the `CDXV` header + index + the chosen unit record;
2. emulates `FUN_00067a14` (`--python-decode` instead drives `FUN_00147c58` directly with the
   Python front-end of §2); `--verify` compares the two and exits non-zero on any difference;
3. writes a mono 16-bit WAV and prints `samples / ramp_last / rms / min / max / nonzero`.

### Verified results

* **Length is explained by the record**: decoded sample count == `ramp[N-1]` for every tested
  record (Kendra 0–14, 100, 1000, 10000, 100000 — 15/15; Amy 0,1,2,3,5,10,100,100000 — all).
* **Front-end + driver are bit-faithful**: `--verify` reports *identical* for records
  0,1,2,5,13,100,1000 (e.g. `rec 0 … 4537/4537`); the Python front-end also matches the engine's
  per-packet input byte-for-byte.
* **The output is voiced speech**: `out/gap/kendra_unit3.wav` (5121 samples, 0.213 s) gives a
  dominant F0 ≈ 138 Hz (autocorrelation peak 0.76) and the attached spectrogram
  `out/gap/kendra_unit3_spectrogram.png` shows a clean harmonic stack with formant bands.
* Output artifacts: `out/gap/kendra_unit{0,1,3,5}.wav`, `out/gap/amy_unit1.wav`,
  `out/gap/kendra_unit3_spectrogram.png`.

## 6. Cross-check: single continuous decode vs per-window decode

Because the gap is one stream we tested whether a single-pass decode is equivalent. Decoding
`T0…T4` continuously and aligning record 1's window output gives its **predicted** offset
`2400·(packets before T2) + Y = 4800 + 2572 = 7372` as the best alignment, but only **2260/2715
(83.2 %)** samples are equal. The codec therefore does not fully converge inside the `Y`-sample
warm-up, so the engine's **per-window** decode (reset + `Y` skip) is the faithful semantics and is
what this tool reproduces. *(A single-pass decode of the whole 108 MB would be faster but is
[INFERENCE] slightly different from the engine in each window's early samples.)*

## 7. Not determined

* **Codec identity** — proprietary; a clean-room port would need the whole `0x147xxx` family.
  Not required: the reimplementation can link the original decode path or use this emulator.
* **`ramp[]` semantics / segmentation** — the per-unit split performed by `LAB_00067db8` after
  decoding (`FUN_000624c8/0624b0/062668/`…): needed to place units in synthesis, not to get PCM.
* **Output-rate conversion** — the decoder runs at 24 000 Hz while the OBB declares 22050; the
  engine presumably resamples later (`resample_wave FUN_00059958`) — not traced end-to-end.
* Exact list of `type`-14 vs other container types (`2/8/0xc`) and their codecs.
