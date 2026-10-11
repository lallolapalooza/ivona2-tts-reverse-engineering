# Unit segmentation, splicing and finalisation — solved and verified

Scope: how a decoded acoustic unit becomes stream PCM — `ramp[]` semantics, per-segment slicing,
the crossfade splice, the "pending tail" bookkeeping, and the finalisation call.
Status: **`ramp[]` is no longer an open question**; everything below is verified against the real
library running under the Unicorn harness (`emu/armemu.py`, `emu/run.py`).
Tool: `scripts/segment_unit.py` (pure-Python re-implementation + `--verify-engine`,
`--verify-splice`, `--verify-finalize`).

Addresses: `LAB_…`/`FUN_…` are **ELF** vaddrs (what the emulator uses); Ghidra addr = ELF + 0x10000
(dump `out/ghidra_dump/libttsivonavoice.c`). File offsets are of the Kendra `main.199.*.obb`.

---

## 1. `ramp[]` semantics (was the flagged unknown)

A unit record is `{u16 N; u16 ramp[N]; u16 Y; u32 gap_off; u32 gap_len}` (`len == 2N + 12`).
`LAB_00067db8` (ELF `0x57db8`, the `type=14` decode callback, vtable `+0x0f`) decodes
`ramp[N−1]` samples of PCM (warm-up `Y` discarded) and then builds the engine's *segment object*:

| field | meaning |
|---|---|
| `obj+0x04` | sample rate (copied from `cdxv+0x0c` by `FUN_0005ef70`) |
| `obj+0x08` | `N` — number of segments |
| `obj+0x0c` | `int32 pms[N]` — **exactly `ramp[]`** |
| `obj+0x10` | `int16* block[N]` — block `i` = `PCM[ramp[i−1] : ramp[i]]` |

`ramp[]` is therefore a list of **cumulative sample marks** (the engine's own debug printer
`FUN_00062550` calls them `pms`), not lengths:

```
segment i  : start = (i == 0) ? 0 : pms[i-1]        # FUN_000624b0(i)
             length = (i == 0) ? pms[0] : pms[i] - pms[i-1]   # FUN_000624c8(i)
total unit : ramp[N-1] samples, and block N-1 ends exactly at the decoded length
```

Verified (`--verify-engine --records 0,1,3,10`): for real units the engine's `pms[]` equals the
record's `ramp[]`, every block equals `PCM[ramp[i−1]:ramp[i]]`, and concatenating the blocks
reproduces the decoded PCM exactly:

```
[engine] rec 0    N=32   pms==ramp:True  blocks==PCM[ramp] :True  concat==PCM:True  rate=22050 OK
[engine] segmentation verification: PASS
```

Design implication: `ramp[]` marks the unit's internal sub-units (per-period marks). A
reimplementation needs them only for *pitch-synchronous* handling (e.g. duration/pitch modification);
plain concatenation of whole units does not need them.

## 2. Decoding rate

The codec is **rate-parameterised**: the wrapper field `wrapper+0x04` is the target rate the codec
synthesises at, not a post-resample target. Decoding record 3 at two rates yields the *same* sample
count (`ramp[2] = 5121`) but different sample values (rms 2842.6 @ 22 050 vs 2910.3 @ 24 000), i.e.
the transform scales internally — there is no separate 24 k→22.05 k resampler in this path.
The shipped voices use **22 050 Hz** (`--rate 22050` is the faithful configuration;
`resample_wave FUN_00059958` is a different, optional stage).

## 3. Splicing — `FUN_00061620` (ELF `0x61620`)

State: `streamer{rate, cap, pos, tail, total, out[]}`; `pos` = committed sample count,
`tail` = samples written at `pos` but **not yet committed** (the held-back last segment of the
previous unit), `total` = samples returned to the caller so far.

```
splice(streamer, obj, flag):
    need = len(obj.blocks[N-1])
    grow buffer if cap - pos < need                     # +max(rate*5, need) samples
    written = 0
    if N >= 2:
        if tail >= 1:                                   # crossfade the held tail with block 0
            written += crossfade(out, pos, tail, blocks[0], len(blocks[0]))
        else:
            out[pos : pos+len(blocks[0])] = blocks[0]; written += len(blocks[0])
        for i in 1 .. N-2:                              # plain copy of the middle segments
            out[pos+written : ...] = blocks[i]; written += len(blocks[i])
    pos += written
    if flag != 0:                                       # normal unit
        tail = len(blocks[N-1]); out[pos : pos+tail] = blocks[N-1]      # held, not committed
    else:                                               # last unit of the utterance
        tail = 0                                        # last segment NOT written here
    total += written
```

Crossfade length rule (verified): `L = min(previous tail, len(blocks[0]))`; the crossfade uses the
**last `L` samples of block 0** (earlier samples of block 0 are dropped).

```
measured: L(rec 0 -> rec 1) = min(113, 113) = 113
          L(rec 1 -> rec 3) = min(148, 103) = 103
          L(rec 3 -> rec 10) = min(196, 160) = 160
```

## 4. Crossfade — `FUN_00062bd4` (ELF `0x62bd4`) and window `FUN_00062b6c` (ELF `0x62b6c`)

Window tables are in `.rodata` at ELF `0x152718` (17 floats) and `0x15275c` (16 floats), embedded
bit-exactly in `scripts/segment_unit.py` (`WIN_TAB1_HEX`, `WIN_SLOPE_HEX`):

* `tab1[i] = round(0.5·(1 + cos(π·i/16)), 5)`, `i = 0…16` (1.0 → 0.0) — a raised cosine;
* `tab2[i] = tab1[i] − tab1[i+1]` (slope), `i = 0…15`.

```
w(k, L) = tab1[i] + frac·tab2[i],   t = (16·k)/L (float32), i = trunc(t), frac = t − i

out[off+k] = int16( s + int32( w(k,L) · (int32(buf[off+k]) − int32(s)) ) )
             where s = src[src_len − L + k]
```

with float32 arithmetic and `__fixsfsi` (truncate toward zero) exactly as the ARM code; the result
is a single crossfade **from the old buffer content (w = 1 at k = 0) to the incoming block's tail
(w = 0 at k = L−1)**.

## 5. Finalisation — `FUN_000618a8` (ELF `0x618a8`)

```
finalize(streamer, want):
    if pos == 0: return []
    n = (0 < want <= pos) ? want : pos          # want <= 0 means "everything"
    res = out[:n]; slide the remaining buffer down; pos -= n
    return res                                  # the uncommitted `tail` is NOT included
```

Verified with an empty event list (`streamer+0x1c == 0`): `flag=1, want=0` → 6991 samples;
`flag=1, want=7` → 7; `flag=0, want=0` → 6991; engine and model agree with **0 sample
differences**.

## 6. Verification commands (reproducible)

```sh
~/venvs/re/bin/python scripts/segment_unit.py --record 1 --show          # one unit, segments
~/venvs/re/bin/python scripts/segment_unit.py --verify-engine --records 0,1,3,10    # PASS
~/venvs/re/bin/python scripts/segment_unit.py --verify-splice --records 0,1,3,10    # PASS, 0 diffs
~/venvs/re/bin/python scripts/segment_unit.py --verify-finalize                     # PASS, 0 diffs
```

All three verifications compare the Python model against the **real library** driven through the
emulator (segment objects, streamer state, committed sample counts and every sample).

## 7. Consequences for a reimplementation

* Whole-unit concatenation needs only: decode unit → PCM (`report_gap_codec.md`), then splice with
  the rule-set above. A two-unit example: `L = min(len(prev_last_segment), len(next_block0))`.
* A unit's last segment is always held back as `tail` unless it is the last unit (`flag = 0`), in
  which case it is not emitted by `splice` at all — callers must either follow with another unit or
  account for it explicitly when reproducing the engine's stream length.
* Always keep float32 semantics with truncation toward zero in the crossfade: rounding differences
  are audible in a bit-exact comparison and will fail the diff.

## 8. Still open (and why it does not block unit-level synthesis)

* **Pitch/duration modification**: the transforms named in `report_engine_synth.md`
  (`pitch_stretch`, `dur_stretch`, `compress`, gain) are applied somewhere between unit selection
  and `FUN_00061620`; they are **not** exercised by the verification above (which splices
  unmodified units). Where they enter — and their exact arithmetic — still needs the trace
  described in that report. Reimplementations can omit them and still produce correct speech at
  rate 100 % / pitch 100 %, or apply their own equivalent (PSOLA-style) processing.
* **`resample_wave` (`FUN_00059958`)**: not needed for the shipped voices (the codec decodes at
  22 050 directly, §2); its use for other rate combinations is untraced.
* **Utterance-level buffer/event handling** in `FUN_000618a8` when `streamer+0x1c != 0`
  (marks/events pending) is not covered — the verification used the empty-event case that the
  bridge exercises for plain synthesis.
