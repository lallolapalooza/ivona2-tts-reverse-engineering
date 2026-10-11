# `FUN_00062d14` — SOLA restretch of a unit (transcribed)

Context: this is the only remaining engine behaviour the pipeline does not reproduce. It is **not**
reached by `duration_stretch`/`pitch_stretch` (all 1.0 for the shipped voices) — it is reached from
`FUN_00063350` when a `pau` window has to be **shortened to a target length** (the pause rules), which is
why only the two `pau` windows of each utterance differ between our PCM and the engine's.

Addresses: Ghidra `00062d14` (ELF `0x52d14`), decompilation `out/ghidra_dump/libttsivonavoice.c:45137-45386`.
Signature in the engine: `float FUN_00062d14(unit_obj *obj, int from_seg, int to_seg, float factor)` —
`obj = {+4 rate, +8 N, +0xc int32 pms[N], +0x10 int16* block[N]}`, returns the **achieved** factor.

## Algorithm (read from the decompiled body)

```
if (factor == 1.0) return 1.0

N0        = obj.N                 # original segment count
upper     = to_seg                # moving bound (decreases as blocks are removed)
pass_target_acc = 1.0             # accumulated per-pass targets        (local_64)
achieved_acc    = 1.0             # accumulated achieved factors        (local_40)

# ---- choose the next pass target -------------------------------------------------
loop:
    half = pass_target_acc * 0.5
    if (half < factor)  pass = factor / pass_target_acc       # final pass: exactly the remainder
    else                pass = 0.5                            # halving pass
    if (pass >= 1.0) -> done (return achieved_acc)

    # ---- one deletion pass -------------------------------------------------------
    new_pms = [] , new_blocks = [] , skipped = 0 , i = 0
    new_pms[0] = pms[0]
    for i in from_seg .. :
        len_i  = FUN_000624c8(obj, i)                     # = pms[i] - pms[i-1]  (segment length)
        # both ratios are normalised by the OLD length run (window start .. this segment) —
        # this is load-bearing: a naive normalisation that does not do this deletes nothing.
        old_so_far = pms[i] - FUN_000624b0(obj, from_seg)        # pms_old[i] - pms_old[from-1]
        new_so_far = (cur - new_pms_at_window_start) + len_i     # what the new array holds
        f_keep = new_so_far / old_so_far
        # the drop option is evaluated on the NEXT segment (i+1):
        len_next = FUN_000624c8(obj, i + 1)
        f_drop   = ((len_next <= len_i ? len_next + (cur - new_pms_at_window_start) : len_next)
                    / (len_next + old_so_far))                   # see :45260-45278
        if |pass - f_drop| < |pass - f_keep|:                    # floats, abs via & 0x7fffffff
            # JOIN: crossfade this block onto the previous one and free it
            n = FUN_00062bd4(dst = previous_block, len_prev, src = block_i, len_i)
            new_pms[-1] = previous_pms + n                # crossfade length replaces both
            free(block_i); skipped += len_i
            # (array is compacted; the block pointers array is rebuilt)
        else:
            # KEEP: copy the segment through unchanged
            new_blocks.append(block_i)
            new_pms.append(cur + len_i)
            skipped = 0
    # ---- end of pass -------------------------------------------------------------
    realized =  (len(new_pms) related sum) / (original corresponding sum)   # float division of
              #  "samples in the new run" / "samples in the old run" (uVar6/uVar12 at :45284-45290)
    achieved_acc *= realized
    pass_target_acc *= pass
    if (factor == pass_target_acc) return achieved_acc
    upper += (new_count - N0)                              # array shrank: move the bound
    goto loop
```

## Notes that matter for an implementation

* **The primitive is the crossfade you already have.** The join is `FUN_00062bd4(dst, dst_len, src,
  src_len)` — the same function used by the splice layer and already implemented (and engine-verified)
  as `segment_unit.crossfade`, with the 17-point raised-cosine window. `n = min(dst_len, src_len)`
  samples are blended, so deleting a segment removes `src_len − n` samples.
* **My first rough formulation of the ratios was wrong** (it normalised by the segment length, which
  never fires): an independent implementation of it on unit 294435 deleted nothing (17 blocks / 2507
  samples, realised 1.0) instead of the engine's 8 blocks / 1176. The definitions above are the ones read
  from the decompile — normalise by the **old** run length and evaluate the drop option on the **next**
  segment. Treat these two details as the parts to validate first against `scripts/probe_stretch.py`.
* **Deletion is whole-segment** (pitch-period granularity: `pms[i] − pms[i−1]`), chosen per segment by
  comparing `|pass − f_drop|` against `|pass − f_keep|`; that is the "SOLA deletes whole pitch periods"
  behaviour already observed in the probe (`17 segments / 2507 samples → 8 blocks / 1176 samples of 147`).
* **Multi-pass, halving by default**: if `0.5 · pass_target_acc ≥ factor` the pass target is exactly
  `0.5`; otherwise it is the remaining ratio `factor / pass_target_acc`, which makes the last pass
  exact. The returned value is the **product of realized per-pass factors**, not `factor` itself — the
  caller (`FUN_00063350`) uses it to adjust the segment bound it passes in next.
* The `factor > 1.0` branch (`LAB_00063030`, **not** exercised by our captures) duplicates segments the
  same way instead of deleting them.
* Float arithmetic throughout (`__aeabi_fcmplt`/`fcmpeq`, `mulsf3`, `divsf3`) — keep float32 semantics
  when porting, the comparisons are strict (`<`) and decide the fold.
* `local_78`/`upper` and the loop bound bookkeeping: the pass compacts the arrays in place
  (`*(obj+0xc) = new_pms; *(obj+0x10) = new_blocks; obj.N = new_count`), and `upper` is corrected by
  `(new_count − N0)` before the next pass.

## Suggested verification

`scripts/probe_stretch.py` is already the oracle (it drives the emulator on the real function): the agent
reported `--unit 294435 --from 0 --to 16 --target 2507 --raw-factor 0.5` → `8 blocks / 1176 samples of 147`,
which is exactly one halving pass under the rules above. Implement the pass in Python, run it on the same
window, and require bit-identical `pms`/samples before wiring it into the pipeline.

## Residual scope

With this implemented, the two `pau` windows become sample-exact and the whole-utterance comparison
should reach `sample_diffs = 0` (the agent's measurements show every non-`pau` sample is already
identical modulo the 2360-sample leading-window offset).
