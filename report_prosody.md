# Prosody and unit selection — cost terms, duration model, intonation

Scope: everything between phoneme strings and the chosen acoustic units — the **join/target
costs** of the Viterbi search, the **duration model**, the **intonation/pitch** stage and how
`dur_stretch` / `pitch_stretch` / `amplify` are applied.  Companion reports:
`report_engine_synth.md` (pipeline, §1.4/§1.5/§1.7), `report_frontend.md` (G2P),
`report_segmentation.md` (splicing), `report_cost_terms_main.md` (target cost, first pass).

**Status**

| item | state |
|---|---|
| join cost (5 context variants) | ✅ **reimplemented and validated bit-exactly** (`scripts/prosody.py`, `scripts/probe_prosody.py`) |
| context → variant dispatch | ✅ transcribed (`FUN_00030214`) |
| target cost (`FUN_00031234` / `FUN_000309a4`) | ✅ **reimplemented and validated bit-exactly** (1250/1250 vectors) |
| duration model (`zdur_cart` CART) | 🟡 blob decoded: per-phone means/σ, all question features, tree; evaluator implemented; **not** run end-to-end (same item prerequisite) |
| pause / break durations (`duration_func`) | ✅ transcribed |
| Viterbi / beam / backtrace | 🟡 structure read from `FUN_0005fc04`, implemented in `scripts/select_units.py`; not diffed against the engine |
| intonation | 🟡 stage identified (`endtone` assignment); plugin-side rule ambiguous (see §5.3) |
| pitch/duration transforms | 🟡 traced (`FUN_00063540`/`FUN_00062d14`/`FUN_00062c54`), time-domain sample duplication |

Addresses: `FUN_…` are **Ghidra** addresses of `out/ghidra_dump/libvoice_kendra.c` (voice plug-in) or
`out/ghidra_dump/libttsivonavoice.c` (engine), unless noted.  **ELF vaddr = Ghidra − 0x10000.**
`[INFERENCE]` marks what is not directly proven.

---

## 1. Join cost — solved and validated

### 1.1 Where it is called

The engine's Viterbi (`FUN_0005fc04`, engine dump `:43094`) holds, per utterance node, a candidate
list (`node+0xcc` pointer, `node+0xd0` count, 20-byte entries).  When relaxing an edge it calls the
function pointer stored at `node+0xc4`:

```c
iVar24 = (**(code **)(iVar8 + 0xc4))(                                   /* engine :43473 */
    *(int *)(*param_1 + 0x14) + (*(int *)(iVar23 + 0xc) + 1) * 0x24,     /* arg0 = rec[prev+1] */
    *(int *)(*param_1 + 0x14) + iVar19 * 0x24,                           /* arg1 = rec[cur]    */
    uVar7 - uVar22);                                                     /* arg2 = cost budget */
```

`*param_1 + 0x14` is the **36-byte diphonedb record table** (the `diphonedb` payload field 5,
`report_engine_synth.md` §3.3), so the join cost reads the *raw* OBB records, not the 96-byte
feature vector (that one is used by the target cost — §3).

The five possible implementations are installed by the plug-in's `diphone_graph_func`
(`FUN_00030214`, plug-in `:7838`), one per graph node, chosen from the pair's context strings:

| test (in order) | function | context | Ghidra |
|---|---|---|---|
| `*(char**)(ctx+0xbc) == "r"` | `FUN_0003055c` | `r` | `0x3055c` |
| `*(char**)(ctx+0xb4) == "+"` | `FUN_00031868` | `+` | `0x31868` |
| `char at ctx+0xbc == "g"` **or** `*ctx+0x6c == "l"` | `FUN_00031cb0` | `g`/`l` | `0x31cb0` |
| `*(char**)(ctx+0xb8) == "-"` | `FUN_000313d0` | `-` | `0x313d0` |
| otherwise | `FUN_000320f0` | default | `0x320f0` |

`FUN_00030214` also reads the voice parameter **`tb_min_distance`** (default −1, plug-in `:7851`)
and sets `node+0xc8 = 1` on a node when the constraint holds — see §1.5.

### 1.2 The 36-byte record fields used

| offset | type | used as |
|---|---|---|
| `+0x00` | u16 | duration in ms (`FUN_0005f1dc` decodes `i16(rec+0)/1000` → s) |
| `+0x08` | u16 | **class/position field** (the `ladder4` field, sign-extended) |
| `+0x0a` | u16 | duration-like field (only `+`/`g`/`l`/default use it) |
| `+0x0c` | i16 | signed field |
| `+0x0e` | u16 | field |
| `+0x10 .. +0x1f` | u8 ×16 | “spectral” distance bytes |
| `+0x20 .. +0x23` | — | not read by any join cost |

### 1.3 Shared building blocks (all five variants)

```text
duration penalty   d = |u16@10(a) − u16@10(b)|
                   p_dur = 0                     if 2d < 5
                         = 40·d − 50             otherwise          (0x28·d − 0x32)

duration ratio     a0 = u16@0(a)/1000, b0 = u16@0(b)/1000, s = a0 + b0      (binary32)
                   r  = trunc( (a0 − b0)·50 / s )        (f32 ops;  ARM f2iz truncates)
                   r  = |r|
                   p_ratio = r                    if r < 9 and r ≤ 5
                           = 3r − 10              if 5 < r < 9
                           = 5r − 32              if r ≥ 9
                   p_ratio = 100                  if s ≤ 0     (divide-by-zero guard)

class ladder       iVar1 = sign_extend16(u16@8(a)), j = sign_extend16(u16@8(b))
                   if iVar1 ≥ 20:      j ≤ 2        -> p4 = 1000000   (&DAT_000f4240)
                                       else          -> p4 = |iVar1−j|/5 + (200 if j==0 else 0)
                   elif iVar1 ≥ 3:                   -> p4 = |iVar1−j|/5 + (200 if j==0 else 0)
                   else (iVar1 < 3):   j > 19       -> p4 = 1000000
                                       iVar1 == 1    -> p4 = |iVar1−j|/5
                                       iVar1 ≤ 0     -> p4 = |iVar1−j|/5 + (200 if j≥2 else 0)
                                       else (==2)    -> p4 = |iVar1−j|/5 + (200 if j==0 else 0)
                   (1000000 is *added to the cost*, not an early return — verified)

field u16@12       d6 = |i16@12(a) − i16@12(b)|
                   p6 = 0 if d6 < 10 ;  d6/3 if 10..15 ;  d6 if 16..23 ;  2·d6 if 24..47 ;  4·d6 if ≥48

field u16@14       d7 = |u16@14(a) − u16@14(b)|, x = 2·d7
                   p7 = 0 if x ≤ 1 ;  6·d7 − 3 if 1 < x < 4 ;
                        20·d7 − 9 if 4 ≤ x < 16 ;  40·d7 if x ≥ 16

spectral distance  gA = Σ|Δ| over bytes {16,17,18}
                   gB = Σ|Δ| over {19,20,21} ;  gC over {22,23,24} ;  gD over {25..31}
                   S  = gA
                   S  = trunc(S + 0.75·gB)        # binary32, truncated back to int between groups
                   S  = trunc(S + 0.50·gC)        # (Ghidra: FUN_0006449c; FUN_00064b30; FUN_0006462c)
                   S  = trunc(S + 0.25·gD)
                   T  = trunc(1.5 · S)            # uVar11, before the variant rescale
```

The inter-group truncation is essential and was found by diffing single-byte sweeps
(`trunc(0.75·2)=1` ⇒ tail 1, not 2).

### 1.4 The five variants

| variant | cost | early exit | tail rescale | return |
|---|---|---|---|---|
| `FUN_0003055c` ("r") | `base = p4 + (p7≫1) + p6 + p_ratio` (**no** `p_dur`) | `9.6·base < budget` | `T>60 → 3T−120` | `trunc(9.6·(base+T'))` |
| `FUN_000313d0` ("-") | `acc = p6 + 0.6·p_ratio + 0.05·p_dur + p4` then **`acc = trunc(acc)`** | `0.8·acc < budget` | `T>90 → 5T−360` | `trunc(0.8·trunc(acc + 0.3·T'))` |
| `FUN_00031868` ("+") | `base = p4 + p7 + p6 + p_ratio + p_dur` | `2·base < budget` (uint) | `T>35 → 10T−315` | `2·(base+T')` |
| `FUN_00031cb0` ("g"/"l") | same as `+` | `4·base < budget` (uint) | `T>40 → 7T−240` | `4·(base+T')` |
| `FUN_000320f0` (default) | same as `+` | `0.8·base < budget` | `T>40 → 5T−160` | `trunc(0.8·(base+T'))` |

When the early-exit test fails the function returns the constant **`0xf4240` = 1 000 000**
(`&DAT_000f4240`), i.e. “pruned/infinite”.  `T'` is `T` after the rescale.

Note the `+`/`g`/`l`/default variants have *exactly* the same body except three constants
(multiplier 2/4/0.8, the rescale threshold, and the rescale coefficients) — proven by a
normalised textual diff of the three decompilations.

### 1.5 The helper primitives (verified by direct emulation)

Calling each helper under Unicorn settled the arithmetic that the decompilation leaves implicit
(`scripts/probe_prosody.py` uses them):

| function | semantics | evidence |
|---|---|---|
| `FUN_0006449c(a,b)` | **fadd** | `3.5,1.25 → 4.75`; `−2,5 → 3.0` |
| `FUN_00064498(a,b)` | **fsub** | `3.5,1.25 → 2.25`; `−2,5 → −7.0` |
| `FUN_000646e0(a,b)` | **fmul** | used with `0x447a0000`=1000.0, `0x3f4ccccd`=0.8… |
| `FUN_00064878(a,b)` | **fdiv** | `x/1000.0` in the duration term |
| `FUN_00064634(x)` | **int→float** (`__aeabi_i2f`) | sign handling present |
| `FUN_0006462c(x)` | **uint→float** | no sign handling |
| `FUN_00064ac0(a,b)` | **a > b** | `(1,0)→1, (2,2)→0, (0,1)→0` |
| `FUN_00064aac(a,b)` | **a ≥ b** | `(2,2)→1, (1,2)→0` |
| `FUN_00064a84(a,b)` | **a < b** | `(0,1)→1, (1,0)→0` |
| `FUN_00064ad4()` / `FUN_00064b30()` | fetch the float result in `r0` and **f2iz** it | used as the “truncate to int” step |

> This corrects `report_cost_terms_main.md` §4b, which guessed `FUN_00064498` = divide and
> `FUN_0006449c` = fabs, and `FUN_00064878` = “op + sign mask”.

### 1.6 Validation

`scripts/probe_prosody.py` calls the real plug-in functions under Unicorn
(`ArmLib` from `emu/armemu.py`) with random 36-byte records and seven budgets (join cost) and
with random 96-byte vectors (target cost), requiring bit-identical `int` results:

```
$ ~/venvs/re/bin/python scripts/probe_prosody.py --n 2500
FUN_000309a4: 1250/1250 match
FUN_00031234: 1250/1250 match
FUN_0003055c context 'r'  : 2500/2500 match
FUN_000313d0 context '-'  : 2500/2500 match
FUN_00031868 context '+'  : 2500/2500 match
FUN_00031cb0 context 'g/l': 2500/2500 match
FUN_000320f0 context ''   : 2500/2500 match
TOTAL 15000/15000 bit-identical
```

Reference vectors (engine vs model, budget `1 000 000 000`; record hex is the raw 36 bytes):

| variant | record_a | record_b | engine | model |
|---|---|---|---|---|
| `FUN_0003055c` | `eb028c7d7247342c1d0089001f003b00300a252e1808051d250a1d0c30233a2eb7b08716` | `8d00b56b8824577d20007e0017003000060e1314360831303b20010e222b0e25dbccb970` | 10003 | 10003 |
| `FUN_0003055c` | `af02e801865b36981700700084001c000f1f1c082b021d1c0009071d08042a096c669fcc` | `3300f86d43f27cf22200030017003b001e15343e3d1b330715300031213a24367f26e232` | 19488 | 19488 |
| `FUN_000313d0` | `090061976f1d1fa01d009f0090000600091b21102c081f2f2414382601260d1199eaa125` | `9803364f8b906baf02005b0035002b001f0d2d34131e14163403162a341f221441159dba` | 800719 | 800719 |
| `FUN_000313d0` | `2d0013f07166ebb31b00000085003b00192e37082a280f2627342933251018353bc56182` | `f9009acf009b926b0900a700b00000000d361c163b061f0f3a113b283836391463c4fdcc` | 621 | 621 |
| `FUN_00031868` | `c503847e8df87a8c16004c00c0001800351c3e1c22373e03312b33153b1003320ac2f403` | `dc01db45ec5d19851000c4005e000a000e14270d0327303219091f0d260f052c40f23a6f` | 16292 | 16292 |
| `FUN_00031868` | `5c0123ae06d7fa3611009800b30038002301180a1e343e1e3c3e39020b251c33f96cb584` | `ca02bcf2b0d9a9b40800a300c0001f000d01243c3d382b1706203d0e08333e098c171b95` | 7386 | 7386 |
| `FUN_00031cb0` | `48004c9b2b7f3cd50e004300a000250019360e1c1322120907152724380f3b26769390e8` | `d101fce02914dda505005000400014000e33003b3406182e3f38061a22102438fd93cd12` | 13360 | 13360 |
| `FUN_00031cb0` | `c9010e7a519f07d022007b0058001500303a29181e311d3405283c3031133f049098fa4c` | `2c0133e133e9074916005f006e0009001f341715160a301e3f121d3b203a20010e17a61c` | 12324 | 12324 |
| `FUN_000320f0` | `27035025e2b099d91c00080094001700100b2529351619102e2215203d252b0e4631149e` | `8d014873cbbb2eca1d005e00ab003c003513350c3e3423042f1b38381e2e0c2f3b317845` | 4816 | 4816 |
| `FUN_000320f0` | `0f01cb8d613ee82e03002000bd001a000e083c392e0d391c05263a03073d333679a50859` | `5303e32529a44b21050017006e0006002f10072a0f342d360624272d0d1b133d4ef2222e` | 2351 | 2351 |

### 1.7 `tb_min_distance` constraints (`FUN_00030214`, plug-in `:7868`)

After the per-node cost pointer, `FUN_00030214` may set `node+0xc8 = 1`:

```c
if (tb_min_distance > 0 && (i − last_flagged) ≥ tb_min_distance && tb_min_distance ≤ n
    && strcmp(ctx+0xb4, "-") == 0) {
    if ((i − last_flagged) ≤ 2·tb_min_distance) {
        if (strcmp(ctx+0xb8, "-") != 0) { float compare with 1.75f … }
        if (strchr("rplg", *(char*)(ctx+0xbc))) skip;      /* r/p/l/g excluded */
    }
    node+0xc8 = 1; last_flagged = i;                      /* mark a forced keep */
}
```

`node+0xc8` is the flag consumed by the engine’s beam histogram (candidate byte `+5`, “forced”),
so `tb_min_distance` enforces a minimum spacing between *kept* diphone indices.  **Correction (measured, supersedes the inference above):** the oracle's runtime parameter dump
(`out/oracle/ref_nopunct/settings.txt`) shows **`tb_min_distance = 6`** and
**`viterbi_beam = 25`** for the shipped Kendra voice — so this rule **is active** and any port
that reproduces the engine's unit choice must implement it. Other live parameters:
`eng_sentence_break = 0.4`, `eng_paragraph_break = 0.65`, `eng_max_sentence = 1000`,
`eng_max_word = 100`, `pause_base_len = 0`, `duration_stretch = pitch_stretch = amplify =
compress = 1.0`, `sample_rate = 22050`, `eng_version = 1.6.23`, `language_code = en-US`.

---

## 2. Target cost (`FUN_00031234` → `FUN_000309a4`)

The engine scores each candidate in the *other* call site (`FUN_0005fc04`, first pass):

```c
uVar2 = (*(code *)param_1[2])(auStack_88, auStack_e8, piVar16 + 1, piVar16 + 0x19);
/*                                    rec_left     rec_right   ctx_left      ctx_right   */
*(undefined4*)(candidate + iVar20) = uVar2;                     /* candidate+0 = cost */
```

`auStack_88`/`auStack_e8` are **96-byte records decoded by `FUN_0005f1dc`** (engine `:42602`),
and `piVar16+1` / `piVar16+0x19` are the graph node’s two **96-byte context vectors** produced by
`FUN_00060ed4` (engine `:43702`).  The graph object’s `+8` slot holds `FUN_00031234`
(set by `FUN_00030214`), which is the engine-visible cost entry point:

```c
int FUN_00031234(a, b, c, d) {                 /* plug-in :8511 */
    i = (int)FUN_000309a4(a, c);               /* target(record_left , ctx_left )  */
    i += (int)FUN_000309a4(b, d);              /* target(record_right, ctx_right) */
    /* + boolean corner penalties: see below */
    return i;
}
```

`FUN_000309a4` compares the *candidate record’s* prosodic slots with the *desired context’s*
slots.  `report_cost_terms_main.md` §1/§4b gives the full transcription (string-mismatch schedule
0/3/7/10 multiplied by 3/6 for “r” contexts, weighted numeric differences, tri-state byte
ladders, the `content` role ladder +50/+75/+10/+3, the `"L*"/"L"` ladder, the `"H"` +1000 hard
penalty, the `pau` float branch with thresholds 0.15/0.2/0.3/0.35/0.4 and scale factors
150/22.5, 120/24, 150/45, 300/120, 250, 360/126, and `return (float)cost · 0.4f`).

The extra terms added by `FUN_00031234` itself (plug-in `:8511-8577`) are:

```c
if (a[0x19]==1 && a[0x21]==1 && b[0x18]==1 && b[0x20]==1) {         /* both on a syllable edge */
    if (!(c[0x19]==1 && c[0x21]==1 && d[0x18]==1 && d[0x20]==1))
        cost += (*(char*)d[0x54] == '+') ? 500 : 350;
} else if (c[0x19]==1 && c[0x21]==1 && d[0x18]==1 && d[0x20]==1)
    cost += 5;
if (a[0x18]==1 && a[0x20]==1) … cost += (*(char*)c[0x54]=='+') ? 10 : 5      /* and its mirror */
if (b[0x19]==1 && b[0x21]==1) … cost += 5
```

**Slot map** (96-byte vector, from `FUN_00060ed4`): `0x00` float duration (`end − p.end`),
`0x04 p.p.name`, `0x08 p.name`, `0x0c` string, `0x10 n.name`, `0x14 n.n.name`,
`0x18 pos_in_syl+1`, `0x19 (1−pos_in_syl)+syl_num_phones`, `0x1a p.stress`, `0x1d stress`,
`0x20 pos_in_word+1`, `0x21 (1−pos_in_word)+word_num_syls`, `0x22 syl_in+1`, `0x23 syl_out+1`,
`0x24 ssyl_in`, `0x26 ssyl_from`, `0x2c n.stress`, `0x30 p.gpos`, `0x34 p.word_num_syls`,
`0x38` string, `0x3c word_num_syls`, `0x3d/0x3e` phrase syllable counts, `0x40 n.gpos`,
`0x44 n.word_num_syls`, `0x45-0x48` phrase counts, `0x49 pos_in_utt+1`,
`0x4a (1−pos_in_utt)+num_phrases`, `0x4c endtone`, `0x54 ph_vc`, `0x58 ph_cvox`, `0x5c ph_ctype`
(full list with writer branches in `report_cost_terms_main.md` §4c).

**Validated.** `FUN_000309a4` is a pure function of two 96-byte vectors: its only external reads
are `strcmp` on the string slots and the float helpers, so it can be driven with plain buffers
(the string words must point at valid guest memory).  `scripts/prosody.py:target_cost` /
`:dispatch_cost` reimplement it and `scripts/probe_prosody.py` diffs them against the real plug-in:

```
FUN_000309a4: 1250/1250 match
FUN_00031234: 1250/1250 match
```

Structural summary of `FUN_000309a4` (all terms integer unless stated; `A`/`B` are the two vectors):

```text
front schedule : mismatches of name strings at 0x04/0x08/0x10/0x14 -> 0/3/7/10,
                 ×3 if B[0x0c]=="r", ×3 or ×6 (if B[0x54][0]=='+') when B[0x08]/B[0x10]=="r"
numeric        : 3|Δ0x19| + 3|Δ0x18| + 3|Δ0x1a| ; +5 if A[0x1d]!=B[0x1d]
                 ; +1000 more if B[0x54][0]=='+' ; + 2(|Δ0x21| + |Δ0x20|)
tri-state      : ladder over (A[0x22],B[0x22]) x (A[0x23],B[0x23]) -> +2/+10/+3
scalar         : +1 each for Δ at 0x26, 0x27, 0x44, 0x48 ; +3|Δ0x2c| ; +3 if syl_vowel (0x28) differ
phrase ladder  : (A[0x3d],B[0x3d]) and (A[0x3e],B[0x3e]) -> +1/+2 ;  same for (0x49,0x4a)
"content"      : mismatches of the 0x38 slot -> +0x4b / +0x32 / +10 ;  0x30 / 0x40 vs "content" -> +3 each
tail (B[0x3e]==1): "L*"/"L" ladder 0/8/10 ; weights ×0xfa/×0x19/×0xf/×0x14/×0x28
                   plus +0x5dc/+0xfa/+0x96/+100/0 constants driven by (0x23,0x1d,0x54,0x19/0x19)
"+1000"        : if (A[0x3e]|A[0x3d] == 1) and B[0x23]>1 and B[0x22]>1 and A[0x4c]=="H"
pau-guard      : unless A[0x0c]=="pau": r = |(a0-b0)/(a0+b0)| over the float at +0
                 a0>=b0: trunc(150r) [+trunc(150r-22.5) if r>0.15] [+trunc(360r-126) if r>0.35]
                 a0< b0: trunc(250r) [+trunc(120r-24) if r>0.2] [+trunc(150r-45) if r>0.3]
                                     [+trunc(300r-120) if r>0.4]
return         : f2i(0.4 * cost)
```

`FUN_00031234` adds four boundary bonuses on top of `target(rec_l,ctx_l)+target(rec_r,ctx_r)`:
`+500` (or `+0x15e`) when the *record* pair sits on a syllable/word edge but the context does not,
`+5` for the mirror case, `+10`/`+5` on the left edge match, `+5` on the right edge match.

Reference vectors for `FUN_000309a4` (three random vector pairs; `engine` = the real plug-in
under Unicorn, `model` = `prosody.target_cost`):

| # | engine | model |
|---|---|---|
| 1 | 284 | 284 |
| 2 | 567 | 567 |
| 3 | 234 | 234 |

Reproducible spec (regenerate with RNG seed 2026 over the same `STR_OFFS`/`BYTE_OFFS`
draw order):

```
#1 a: float=0.0; strs: 04="L*" 08="-" 0c="-" 10="" 14="r" 28="pau" 30="a" 38="a" 40="-" 4c="H" 54="a" 58="-" 5c="+"; bytes: 18=4 19=3 1a=1 1d=0 20=4 21=0 22=0 23=2 26=0 27=3 2c=0 3c=5 3d=3 3e=5 48=2 49=1 4a=3
#1 b: float=1.0; strs: 04="L*" 08="L*" 0c="H" 10="-" 14="" 28="r" 30="L*" 38="r" 40="-" 4c="-" 54="L" 58="L" 5c="+"; bytes: 18=1 19=5 1a=5 1d=5 20=4 21=2 22=0 23=5 26=2 27=2 2c=3 3c=3 3d=0 3e=3 48=4 49=4 4a=3
#2 a: float=0.0; strs: 04="H" 08="-" 0c="a" 10="+" 14="H" 28="-" 30="L" 38="H" 40="a" 4c="+" 54="-" 58="-" 5c="x"; bytes: 18=4 19=1 1a=1 1d=0 20=5 21=4 22=5 23=0 26=5 27=4 2c=3 3c=3 3d=1 3e=3 48=1 49=0 4a=5
#2 b: float=2.0; strs: 04="" 08="+" 0c="-" 10="L" 14="-" 28="H" 30="" 38="L" 40="-" 4c="" 54="-" 58="+" 5c="H"; bytes: 18=3 19=1 1a=2 1d=2 20=0 21=0 22=1 23=5 26=4 27=3 2c=4 3c=3 3d=2 3e=1 48=2 49=5 4a=3
#3 a: float=2.0; strs: 04="-" 08="+" 0c="H" 10="-" 14="" 28="x" 30="L" 38="L*" 40="+" 4c="r" 54="+" 58="-" 5c="L"; bytes: 18=3 19=1 1a=3 1d=5 20=3 21=0 22=5 23=2 26=3 27=2 2c=0 3c=1 3d=5 3e=3 48=1 49=3 4a=0
#3 b: float=0.0; strs: 04="x" 08="+" 0c="a" 10="-" 14="r" 28="a" 30="pau" 38="pau" 40="r" 4c="a" 54="x" 58="-" 5c="L"; bytes: 18=5 19=5 1a=2 1d=1 20=0 21=2 22=5 23=4 26=4 27=3 2c=5 3c=5 3d=1 3e=4 48=1 49=3 4a=4
```


---

## 3. Duration model (`duration_func` = `FUN_00048400`, plug-in `:20353`)

### 3.1 Stage behaviour

```c
FUN_00048400(params) {
    if (zdur_cart absent)  cart = null,  use the `dur_stats` fallback (FUN_0004e5b4…)
    pause_base_len = float param "pause_base_len", default 0x3eb33333 = 0.35
    cumulative = 0
    for (seg = first Segment; seg; seg = next) {
        if (name == "pau")
            d = pause rule (below)
        else if (cart == null)
            d = cart_dur_stats(seg)                    /* FUN_0004fa3c / FUN_0004e5b4 */
        else
            d = (float)FUN_00048110(cart, seg) / 1000.0   /* ms -> s */
        cumulative = float32(cumulative + d);
        set_feature(seg, "end", cumulative);              /* cumulative end time, seconds */
    }
}
```

Pause rule (`pau`):

| condition (item = the `pau` Segment) | duration (s) |
|---|---|
| `item.prev == NULL` | `0.01` (`0x3c23d70a`) |
| phrase name reached from `item.prev` is `"BB"` | `pause_base_len + 0.05` = **0.40** |
| … **and** `item.next != NULL` | `+ 0.10` → **0.50** |
| otherwise | `0.20` (`0x3e4ccccd`) |

(The phrase name is read as `prev.R:SylStructure.parent.parent.R:Phrase.parent.name`,
`FUN_0003de24`, plug-in `:20390`; the `+0.10` test is `FUN_00028c14(item) != 0`, i.e. a
*next* segment exists.)

### 3.2 The `zdur_cart` blob (fully decoded)

`PTR_DAT_002f4024` (plug-in, ELF vaddr `0x2e4024`) holds a 3-word struct
`{phone_tbl, name_tbl, node_tbl}` = `{0x56ee0, 0x56ff0, 0x588b0}`.

* **name table** — 0x40-byte records, 420 entries: Festival feature paths and literal values.
  Entry format for a *question* is `<operator><path>` (only `=` occurs in Kendra’s font, plus the
  values compared).  Features actually used (from the decoded tree):

  `name`, `p.name`, `n.name`, `pp.ph_cvox`, `R:SylStructure.parent.R:Syllable.pp.syl_break`,
  `nn.ph_cplace`, `nn.ph_cvox`, `p.ph_ctype`, `n.ph_vfront`, `ph_ctype`, `n.ph_cplace`,
  `pp.ph_vrnd`, `ph_cplace`, `nn.ph_vheight`, `p.ph_cplace`, `n.ph_cvox`, `pos_in_syl`,
  `ph_vlng`, `R:SylStructure.parent.position_type`, `nn.ph_vc`, `R:…R:Syllable.p.syl_break`,
  `R:SylStructure.parent.parent.pos_in_phrase`, `nn.ph_vrnd`, `R:SylStructure.parent.parent.gpos`,
  `R:SylStructure.parent.pos_in_word`, `R:SylStructure.parent.stress`,
  `R:SylStructure.parent.syl_break`, `R:SylStructure.parent.syl_vowel`, `syl_final`,
  `R:SylStructure.parent.syl_in`, `R:SylStructure.parent.R:Syllable.n.accented`, `p.seg_onsetcoda`
  (plus the compared phone-name / literal entries).

* **node tree** — 4-byte cells at `node_tbl`:

  ```text
  node(off):
      p = node_tbl + off*4
      questions = []
      loop:
          q = byte[p]
          if q == 0xff:                       # leaf
              leaf16 = i16[p+2]
              return pack16( (leaf16*std + sign(leaf16)*500) / 1000 + mean )
          questions.append( (q, byte[p+1], u16[p+2]) )   # (feature, rhs, false-child)
          p += 4
      # any failed question jumps to  node_tbl + u16[p-2]*4
  ```

  Decoded size: **3951 nodes**, **1584 leaf nodes**; every question is an equality test whose
  LHS is the feature path from the name table and whose RHS is another name-table entry
  (a phone name, a class literal, or an integer).

* **phone table** — 6-byte records `{u8 nameIdx, u8 reserved, i16 mean_ms, i16 std_ms}`,
  terminated by `nameIdx == 0xff`; **44 entries** (the phone’s base mean and σ).  This is the
  “base durations per phoneme” reference table:

  | phone | mean ms | σ ms | phone | mean ms | σ ms | phone | mean ms | σ ms |
  |---|---|---|---|---|---|---|---|---|
  | `` | 175 | 52 | `aa` | 124 | 52 | `ae` | 106 | 48 |
  | `ah` | 79 | 37 | `ao` | 115 | 56 | `aw` | 174 | 61 |
  | `ax` | 52 | 28 | `ay` | 162 | 65 | `b` | 81 | 23 |
  | `ch` | 126 | 40 | `d` | 68 | 27 | `dh` | 58 | 24 |
  | `eh` | 81 | 39 | `er` | 122 | 54 | `ey` | 148 | 72 |
  | `f` | 101 | 32 | `g` | 89 | 24 | `hh` | 75 | 30 |
  | `ih` | 60 | 30 | `iy` | 118 | 58 | `j` | 101 | 40 |
  | `jh` | 112 | 37 | `k` | 93 | 25 | `l` | 102 | 43 |
  | `lx` | 136 | 46 | `m` | 91 | 30 | `n` | 78 | 33 |
  | `ng` | 113 | 36 | `nx` | 139 | 54 | `ow` | 140 | 75 |
  | `oy` | 215 | 65 | `p` | 91 | 24 | `pau` | 276 | 109 |
  | `r` | 87 | 39 | `s` | 121 | 38 | `sh` | 130 | 29 |
  | `t` | 70 | 27 | `th` | 103 | 33 | `uh` | 70 | 41 |
  | `uw` | 89 | 63 | `v` | 70 | 23 | `w` | 100 | 31 |
  | `z` | 102 | 35 | `??` | 112 | 37 |  |  |  |

  (Full machine-readable list: `scripts/prosody.py` `Cart.from_so(...).phones`.)

* **Leaf arithmetic** is the standard z-score decode: `ms = (leaf · σ)/1000 + mean`, with
  rounding `+500 / −500` by the leaf’s sign and a 16-bit sign-extended result
  (`… * 0x10000 >> 0x10`).

### 3.3 Implementing it

`scripts/prosody.py` provides:

```python
cart = prosody.Cart.from_so("out/libs/kendra/libvoice_en_us_kendra.so")
cart.phones                                # [(nameIdx, name, mean_ms, std_ms), …]
cart.predict("ah", feat)                   # feat(path) -> (tag, value);  tag 1=int, 5=str
prosody.pause_duration("BB", True, False)  # 0.40
prosody.duration_chain(cart, segments)     # cumulative "end" list (FUN_00048400)
```

**Gap**: `predict`/`duration_chain` were not run against the engine.  `FUN_00048110` evaluates
features on a Festival item (`FUN_00028dc0` for `"name"`, `FUN_0003da38` for paths with
`p`/`n`/`nn`/`pp`/`parent`/`daughter(n)`/`R:` steps, `FUN_00044460`-registered feature functions),
so driving it requires constructing an item graph plus the registered feature objects.  A first
attempt (calling the plug-in item constructor `FUN_00029200` and `FUN_00026b3c` to add a `"name"`
feature) created a plausible item but any feature lookup then jumped through an unset
feature-registry pointer and read unmapped memory — the harness needs the voice’s feature set
installed first.  The blob decode itself is verified implicitly by the phone table and tree
invariants (all questions resolvable, tree terminates, leaf values in a sane ms range).

---

## 4. Sentence / paragraph breaks, `rate`, `dur_stretch`

* **`sentence/paragraph_break`** are realised through the pause rule in §3.1: a `"BB"` phrase
  (sentence break) with a following segment gives 0.40 s; `+0.10` when the next phrase also
  breaks (paragraph) → 0.50 s.  `eng_sentence_break` default 0.4 s (engine `0x3ecccccd`,
  `report_engine_synth.md` §1.4) is the *splitter* threshold, separate from this emitted pause
  length.
* **SSML rate → `duration_stretch`**: at parse time each token gets
  `duration_stretch = clamp(1/rate, ≥ 0.05)` and `pitch_stretch = clamp(1/pitch, [0.9, 1.1])`
  (`FUN_00043bb0`, `report_engine_synth.md` §1.4 “Prosody”).  Voice-level values come from the
  plug-in (`duration_stretch` default `0x3f800000` = 1.0, plug-in `:7810`).
* **Application** (engine `FUN_0005d7c4`, `:42340-42400`): per unit, token×voice factors are
  fetched twice and multiplied, then
  `pitch_stretch → FUN_00063540`, `duration_stretch → FUN_00062d14`,
  `compress → FUN_00063850`, `amplify → FUN_00062c54`.
  The **pitch result is used to divide the duration factor** (`:42348-42356`), i.e. a pitch shift
  is compensated in length.
* The duration CART output is **not** multiplied by `duration_stretch`: `FUN_00048400` never
  reads that parameter.  The CART supplies the *target* segment boundaries (the `end`
  feature, used for pause padding and boundary windows), while `duration_stretch` (=1/rate)
  is applied later to the decoded waveform by `FUN_00062d14`.
* `FUN_00063540` (`:45506`) is a time-domain implementation: for each block of the unit it inserts
  `local_40 = ceil((pitch−1)·len)` duplicate samples while `(i+2)/(j+1) ≤ pitch`, then returns
  `samples/segments` as the achieved ratio.  `FUN_00062d14` (`:45135`) is the analogous
  sample-insertion/deletion stretcher for the duration factor.  These are **not** PSOLA — there
  is no F0 tracker in this path **[INFERENCE]**.

---

## 5. Intonation

### 5.1 Stage default (`intonation_func` = `FUN_00066554`, engine — re-decompiled)

Body (engine, see `out/intonation_decomp.c`):

```c
iVar1 = param_get(*param_1, "phrasesylendtone_func");
ensure_relation(param_1, "Phrase");
for (each Phrase p) {
    syl  = find(p, "daughtern.R:SylStructure.daughtern");
    if (syl == NULL) continue;
    tok  = find(p, "daughtern.R:Token.parent.endtone");
    if (tok != NULL) {
        s = str(tok);
        if (s == "H" || s == "L") { set_feature(syl, "endtone", tok); continue; }
    }
    if (iVar1 == 0) { set_feature(syl, "endtone", &DAT_0015737c); continue; }
    if ((*phrasesylendtone_func)(p) == 0) set_feature(syl, "endtone", &DAT_0015737c);
    else                                  set_feature(syl, "endtone", /* computed value */);
}
```

So the intonation stage **only assigns a phrase-final `endtone`**; it does not compute an F0
contour.  Priority: an explicit Token `endtone` of `H`/`L` → that value; otherwise the voice’s
`phrasesylendtone_func` decision; otherwise a default.

`DAT_0015737c` is not a printable string (bytes `f3 ff e8 be …`), so it is a VAL/typed value
rather than the literal `"NONE"` **[INFERENCE]**.

### 5.2 Where the pitch actually comes from

The shipped voices carry pitch inside the selected units — each decoded diphone (type `0x0e`)
holds its own waveform, and the engine never synthesises an F0 track.  `stress`/`accented`/
`accent`/`syl_vowel`/`endtone` are *selection features* (they appear both in `FUN_00060ed4`’s
96-byte vector and in the duration CART), and prosodic pitch variation enters through
`pitch_stretch` (§4).  Hence a port can reproduce pitch at `pitch=100 %` simply by concatenating
the chosen units; explicit F0 control would be a new feature, not a recovered one.

### 5.3 Open point

`FUN_0003256c` registers `phrasesylendtone_func = userdata(&DAT_00032d20)` (plug-in `:9502`).
Decompiling the function at plug-in Ghidra `0x32d20` (ELF `0x22d20`) yields what looks like a
*second voice-registration routine* (it sets `wordtosegments_func`, `postlex_func`, `phoneset`,
`tokentowords_func`, `phrasesylendtone_func`, … on its argument).  Either Ghidra started the
function at a wrong boundary (the preceding 16 bytes at `0x22d10` are a literal pool, and the
decompilation uses `unaff_r5/r6`), or `phrasesylendtone_func` really is that routine and the
engine’s call `(*fp)(phrase)` is a mis-read.  This is the one unresolved piece of the intonation
stage.  `FUN_00032b70` (immediately before, plug-in `:9508`) *is* a plausible intonation rule:
it locates the `"BB"` phrase and returns 1 when the phrase contains a `gpos == "wp"` word (or a
`cc` followed by `wp`) — i.e. a question/continuation detector.

---

## 6. Viterbi: beam, transition, backtrace (`FUN_0005fc04`, engine `:43094`)

Per utterance, `FUN_0005d7c4` calls `FUN_0005fc04(graph_state, chunk_samples)`.  State
(`param_1`): `[4]` = node array (stride **0xd4**), `[5]` = node count, `[6]` = current node,
`[7]` = “finished”, `[2]` = candidate cost fn, `[1]` = `dp_debug_func` (optional), `[0]` = the
diphonedb payload (records at `+0x14`, index table at `+0x10`, ext data `+0x18`, model blocks
`+0x1c`).  Each node: `+0x00` name ptr, `+0x04` ctx vector #1 (0x60), `+0x64` ctx vector #2,
`+0xc4` join-cost fn, `+0xc8` “forced” flag, `+0xcc` candidate array, `+0xd0` count.  A candidate
entry is **20 bytes**: `+0x00` target cost, `+0x04` flag, `+0x05` forced flag, `+0x08` accumulated
total (initialised to `1000000000`), `+0x0c` diphone index, `+0x10` back-pointer.

1. **Candidate build / target cost**: for each candidate the decoded records
   `FUN_0005f1dc(rec[idx])`, `FUN_0005f1dc(rec[idx+1])` and the node’s two context vectors are
   passed to `(*param_1[2])`; the result is stored at `candidate+0`.  A special path skips
   candidates whose context char is `"+"` unless a neighbour matches (`local_cb`/`local_6b`).
2. **Beam**: with the beam parameter `n` (`viterbi_beam`, plug-in 50; 25 at reduced quality;
   `-1` = off), the code builds a histogram of candidate costs in up to **51 buckets** (0x33),
   finds the smallest threshold under which ≤ 51 candidates remain, and drops the rest
   (a candidate whose byte `+5` (forced) is set, or which abuts a `pau` segment, is exempt).
   Then `qsort(candidates, 0x14, cmp)` orders them by cost (`LAB_0005fa64`).
3. **Transition** (the loop at `:43473`): for candidate *j* of node *k*, for each predecessor
   candidate *i* of node *k−1* with `prev_total < prev_total_min + …`, let
   `base = prev_total_i + target_j` and `budget = best_total_so_far − base`; if
   `prev.diphone_idx + 1 == j.diphone_idx` the transition cost is **0** (consecutive records share
   a joint waveform — matching the splice rule of `report_segmentation.md` §1.7), otherwise
   `trans = join_cost(rec[prev_idx+1], rec[j_idx], budget)`.  If `base + trans < best_total` the
   candidate’s total and back-pointer are updated.  The beam array also short-circuits the scan
   once `auStack_2028[n−1] ≤ base`.
4. **Backtrace**: when the last node is reached, the engine takes the sorted candidate array of
   the final node, keeps entries whose `+0x10` back-pointer equals the recorded best, and
   `FUN_0005faa0` walks the chain to emit the `diphone` attributes (`FUN_00058fcc(item,"diphone",…)`).

`scripts/select_units.py` reimplements this search with the validated join cost and a pluggable
target cost:

```python
from select_units import select
path, cost = select(lattice, prosody.join_cost_default)     # beam = 50 by default
```

It is **not** diffed against `FUN_0005fc04` (the oracle harness cannot yet load a voice — see
`report_oracle.md`), so treat the pruning specifics (51 buckets, forced-flag exemptions, the
beam short-circuit) as transcribed behaviour.

---

## 7. What could not be pinned down

1. **Duration CART — no end-to-end run.** Blob, features, tree, phone table and evaluator are
   decoded, but `FUN_00048110` needs the same item/feature-registry construction to execute.
2. **`phrasesylendtone_func` (plug-in `0x32d20`)** — decompilation ambiguous (§5.3).
3. **Viterbi** — structure transcribed, not diffed.
4. **`FUN_000313d0`’s intermediate truncation** is inferred from the decompiled
   `FUN_0006449c; FUN_00064b30; FUN_0006462c` sequence and confirmed by the emulator; the exact
   reason (a real `f2iz`/`i2f` round-trip) is not proven from source.
5. **Bytes `+0x20..+0x23` of the record** are not read by any join cost — their meaning is not
   established here (they are part of the record’s extended-data descriptor, `FUN_0005f1dc`).
6. **Full-engine oracle** is blocked (`tts_load_voice` fails, `report_oracle.md`), so no
   reference utterance PCM could be produced to cross-check the whole chain.

---

## 8. Reproduce

```sh
# join costs + target cost, bit-exact against the real plug-in (Unicorn)
~/venvs/re/bin/python scripts/probe_prosody.py --n 2500       # 15000/15000

# reference vectors for the report
~/venvs/re/bin/python scripts/probe_prosody.py --vectors

# duration CART blob (phone table / features / tree)
~/venvs/re/bin/python -c "import sys;sys.path.insert(0,'scripts');\
import prosody;c=prosody.Cart.from_so('out/libs/kendra/libvoice_en_us_kendra.so');\
print(len(c.phones), c.phones[:5])"

# unit selection
~/venvs/re/bin/python scripts/select_units.py --demo

# re-decompile the engine intonation default / plug-in endtone rule
/opt/ghidra/support/analyzeHeadless out/ghidra_v ivona_v -process libttsivonavoice.so \
  -scriptPath scripts/ghidra -postScript DecompAt.java out/intonation_decomp.c 0x66554 0x666c8 0x667e0 -noanalysis
```

Files added: `scripts/prosody.py` (join cost + target cost + duration CART + pause rules),
`scripts/probe_prosody.py` (bit-exact validator for all seven cost functions),
`scripts/select_units.py` (Viterbi), `out/intonation_decomp.c`, `out/phrase_endtone.c`, this
report.  Originals untouched.
