#!/usr/bin/env python3
"""End-to-end text -> WAV synthesis on the shipped IVONA 2 voice data.

Pipeline
--------
    text
      -> (light normalisation / tokenisation)
      -> words
      -> phoneme strings        [packed lexicon, else letter-to-sound FSM]
      -> phoneme sequence       (words chained; "pau" at clause boundaries)
      -> "L-R" diphone names    (snprintf("%s-%s", left, right))
      -> candidate unit ids     [section A name table (20 B) -> section B (u32) slice]
      -> one unit id per diphone [heuristic over the section-C 36-byte records]
      -> per-unit PCM           [clean-room format-14 codec, scripts/codec_spec.py]
      -> stream splice          [ramp[] segmentation + FUN_00061620 crossfade,
                                 scripts/segment_unit.py]
      -> 16-bit mono WAV

Rates: the codec synthesises at 24 000 Hz (`--codec-rate`, engine-exact -- see
CODEC_RATE below); the shipped container declares 22 050 Hz, so the default
`--rate 22050` output is converted 24 k -> 22.05 k by the codec's own
output-rate converter (`scripts/codec_parts/resample.py`, the engine's
`FUN_0014b4a8`/`FUN_0014c494`); `--rate 24000` writes the raw codec-rate stream.
The decoder is the clean-room, stdlib-only `scripts/codec_spec.py` -- no Unicorn
is imported on the runtime path (`--verify-engine` uses the emulator for
validation only).

What this is: a *functional* demonstration that the text->speech path is
reimplementable from the shipped data.  What it is not: a bit-exact clone of the
engine.  The Viterbi unit selection, the prosody (pitch/duration) model and the
ISEF post-lexical rewrite rules are not implemented here -- see report_pipeline.md
for the exact deviations.

Usage
-----
    ~/venvs/re/bin/python refimpl/tts.py --text "hello world" --out out/tts_demo/hello.wav
    ~/venvs/re/bin/python refimpl/tts.py --text "..." --voice amy --out out/tts_demo/x.wav
    ~/venvs/re/bin/python refimpl/tts.py --phones "hello world"      # phone sequence only
    ~/venvs/re/bin/python refimpl/tts.py --text "..." --align        # unit alignment summary
    ~/venvs/re/bin/python refimpl/tts.py --check-tables              # A/B/C chain integrity
    ~/venvs/re/bin/python refimpl/tts.py --check-g2p "hello kendra"  # front-end regression
"""
from __future__ import annotations

import argparse
import os
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                            # cdxv
sys.path.insert(0, os.path.join(ROOT, 'scripts'))   # lex_decode / lts_decode / codec_spec / segment_unit
sys.path.insert(0, os.path.join(ROOT, 'emu'))       # armemu (only for --verify-engine)
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'codec_parts'))

import cdxv                                         # noqa: E402
import lex_decode                                   # noqa: E402
import lts_decode                                   # noqa: E402
import decode_unit as du                            # noqa: E402
import codec_spec                                   # noqa: E402  clean-room gap decoder (no Unicorn)
import resample as codec_resample                   # noqa: E402  the codec's output-rate converter
import segment_unit as su                           # noqa: E402
import symbol_names                                 # noqa: E402  plug-in symbol -> spoken name
import prosody                                      # noqa: E402
from phoneset import PhoneSet                       # noqa: E402
import engine_prosody                               # noqa: E402

DEFAULT_RATE = 22050        # output WAV rate (the rate the container declares)
CODEC_RATE = 24000          # the codec's true synthesis rate (see report_emulation.md)
# The OBB header (+0x24) says 22050, but format-14 init FUN_00067f94 remaps the
# 0x5622 sentinel to 24000, so libttsivonavoice.so always synthesises 24 kHz PCM;
# the per-unit `dur_ms` metadata agrees (median ramp[-1]/dur_ms = 24.14 ~ 24 kHz).
# A wave object tagged 22050 then carries 24 kHz data and the (untraced)
# `resample_wave FUN_00059958` stage converts it downstream.

# ---------------------------------------------------------------------------
# voice configuration
# ---------------------------------------------------------------------------
# `obb`: glob (relative to the repo root) of the voice expansion file.
# `g2p`: the voice plug-in that owns the packed lexicon + letter-to-sound FSM.
#
# NOTE on `amy`: her plug-in (libvoice_en_gb_amy.so) was checked to embed the
# *same* 75-entry phoneme table and the *same* packed lexicon pronunciations as
# the en-US plug-in (identical results for colour, tomato, vase, advertisement,
# hello, kendra, ...), so the en-US front-end is used for both voices.  Only the
# acoustic data (OBB, diphone table) is voice-specific.  See report_pipeline.md.
VOICES = {
    'kendra': {
        'obb': 'IVONA 2/*kendra*/Android/obb/*/main.199.*.obb',
        'g2p': 'out/libs/kendra/libvoice_en_us_kendra.so',
        'pkg': 'com.ivona.tts.voicebeta.eng.usa.kendra',
        # sources of the engine-matching prosody model (`--select viterbi`)
        'pset_so': 'out/libs/kendra/libvoice_en_us_kendra.so',
        'pset': 'x-ivona-en_us',
        'zdur_so': 'out/libs/kendra/libvoice_en_us_kendra.so',
        # voice parameters in force (out/oracle/*/settings.txt):
        # viterbi_beam 25, pause_base_len 0, tb_min_distance 6
        'beam': 25, 'pause_base': 0.0, 'tb_min_distance': 6,
    },
    'amy': {
        'obb': 'IVONA 2/*amy*/Android/obb/*/main.199.*.obb',
        'g2p': 'out/libs/kendra/libvoice_en_us_kendra.so',
        'pkg': 'com.ivona.tts.voicebeta.eng.gbr.amy',
        'pset_so': 'out/libs/amy/libvoice_en_gb_amy.so',
        'pset': 'x-ivona-en_gb',
        'zdur_so': 'out/libs/amy/libvoice_en_gb_amy.so',
        'beam': 25, 'pause_base': 0.0, 'tb_min_distance': 6,
    },
}

# The format-14 codec lives in libttsivonavoice.so, which is byte-identical for
# both voices (md5 2274b82e216f8dd4123deea94e00511c); decode_unit.SO is fine.
ENGINE_SO = du.SO


def _resolve(pattern: str) -> str:
    """Case-insensitive glob of `pattern` relative to the repo root.

    The shipped tree mixes cases (`IVONA 2/IVONA Kendra US English ...`), so an
    ordinary glob with a lower-case voice name would miss it.
    """
    parts = [p for p in pattern.split(os.sep) if p]
    cur = [ROOT]
    for part in parts:
        rx = re.compile(re.escape(part).replace(r'\*', '.*').replace(r'\?', '.') + '$',
                        re.IGNORECASE)
        nxt = []
        for base in cur:
            try:
                entries = sorted(os.listdir(base))
            except OSError:
                continue
            nxt += [os.path.join(base, e) for e in entries if rx.match(e)]
        cur = nxt
        if not cur:
            break
    hits = [p for p in cur if not p.endswith(os.sep)]
    if not hits:
        raise SystemExit("no file matches %r" % pattern)
    return hits[0]


# ---------------------------------------------------------------------------
# 1. text normalisation + tokenisation
# ---------------------------------------------------------------------------
DIGIT_WORDS = {
    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
}
# A word token (letters / digits / apostrophe) or a single non-space character.
TOKEN_RE = re.compile(r"[A-Za-z0-9']+|\S")
STRESS_RE = re.compile(r'[0-9]$')
SKIP_PHONES = {'_epsilon_', 'epsilon', ''}


def clauses_of(text: str):
    """Split text into clauses; each clause -> list of pronounceable "words".

    Words are spelled normally; **punctuation and other symbols are spoken by
    name** using the plug-in's printable-ASCII table (`scripts/symbol_names.py`),
    e.g. `,` -> ``comma`` (``k aa m ax``) and `.` -> ``dot`` (``d aa t``) -- the
    engine's "symbol without a reading" fallback, verified against
    `out/oracle/ref_default/diphone_lookups.tsv`.  A *sentence-final* symbol
    (`. ! ?`) also closes a clause (the engine's `eng_sentence_break`); other
    punctuation (`, ; :`) is only spoken, never a pause, matching the oracle.

    Digits are spelled out with `DIGIT_WORDS` (the demo's convention; the
    plug-in table names them ``oh``/``one``/..).  This is deliberately minimal --
    the engine's full ISEF rewrite pipeline (report_isef.md) is not applied (see
    report_pipeline.md).
    """
    out = []
    cur = []
    for tok in TOKEN_RE.findall(text.lower()):
        if len(tok) == 1:
            name = symbol_names.spoken_name(tok)
            if name is not None:
                cur.append(name)
                if symbol_names.is_sentence_end(tok):
                    out.append(cur)
                    cur = []
                continue
        w = ''.join(DIGIT_WORDS.get(c, c) for c in tok)
        if w:
            cur.append(w)
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# 2. grapheme -> phoneme (packed lexicon, letter-to-sound fallback)
# ---------------------------------------------------------------------------
class G2P:
    def __init__(self, so: str):
        self.lx = lex_decode.Lexicon(so=so)
        self.lts = lts_decode.Lts(so=so)

    def word(self, w: str):
        """Return the base-phone string for one word (stress digits stripped)."""
        phones = self.lx.lookup(w)
        src = 'lex'
        if phones is None:
            try:
                phones = self.lts.lts(w)
            except Exception:
                phones = []
            src = 'lts'
        out = [STRESS_RE.sub('', p) for p in phones if p not in SKIP_PHONES]
        return out, src

    def word_stressed(self, w: str):
        """`word()` but keeping the stress digits (they are item features).

        Returns (base_phones, stress_levels, source); `stress_levels[i]` is the
        digit the lexicon/LTS attached to `base_phones[i]` (0 when absent), i.e.
        the `stress` / `p.stress` features of the engine's item graph.
        """
        phones = self.lx.lookup(w)
        src = 'lex'
        if phones is None:
            try:
                phones = self.lts.lts(w)
            except Exception:
                phones = []
            src = 'lts'
        base, st = [], []
        for p in phones:
            if p in SKIP_PHONES:
                continue
            m = STRESS_RE.search(p)
            base.append(STRESS_RE.sub('', p))
            st.append(int(m.group(0)) if m else 0)
        return base, st, src


def phone_items(g2p: G2P, text: str, diphone_names: dict, sep='pau'):
    """The engine's segment chain: word items + explicit pause items.

    Same chain as `phone_sequence` (identical diphone pairs) but preserving the
    word/stress structure the prosody model needs.
    """
    items, detail = [], []
    last_phone = None
    for words in clauses_of(text):
        clause = []
        for w in words:
            ph, st, src = g2p.word_stressed(w)
            if not ph:
                continue
            clause.append(("word", w, ph, st))
            detail.append((w, src, ph))
        if not clause:
            continue
        if items and last_phone is not None:
            first = clause[0][2][0]
            if ('%s-%s' % (last_phone, sep)) in diphone_names and \
               ('%s-%s' % (sep, first)) in diphone_names:
                items.append(("pau",))
        items += clause
        last_phone = clause[-1][2][-1]
    flat = items_phones(items)
    if not flat:
        return [], detail
    if ('%s-%s' % (sep, flat[0])) in diphone_names:
        items.insert(0, ("pau",))
    if ('%s-%s' % (flat[-1], sep)) in diphone_names:
        items.append(("pau",))
    return items, detail


def items_phones(items):
    """Flatten an item list to the segment chain (pauses included)."""
    out = []
    for it in items:
        if it[0] == "pau":
            out.append("pau")
        else:
            out.extend(it[2])
    return out


def phone_sequence(g2p: G2P, text: str, diphone_names: dict, sep='pau'):
    """words -> phoneme sequence, with `sep` between clauses when both diphones exist.

    Returns (phones, per-word detail).  Because sections A/B are *attested*
    transitions rather than a full cross-product, a boundary symbol is only
    inserted when both `X-sep` and `sep-Y` are present in the name table.
    """
    detail = []
    seq = []
    for ci, words in enumerate(clauses_of(text)):
        clause = []
        for w in words:
            ph, src = g2p.word(w)
            detail.append((w, src, ph))
            clause += ph
        if not clause:
            continue
        if seq:                                     # clause boundary
            if ('%s-%s' % (seq[-1], sep)) in diphone_names and \
               ('%s-%s' % (sep, clause[0])) in diphone_names:
                seq.append(sep)
        seq += clause
    if not seq:
        return [], detail
    # optional utterance edges
    if ('%s-%s' % (sep, seq[0])) in diphone_names:
        seq = [sep] + seq
    if ('%s-%s' % (seq[-1], sep)) in diphone_names:
        seq = seq + [sep]
    return seq, detail


# ---------------------------------------------------------------------------
# 3. diphone pairing + unit selection
# ---------------------------------------------------------------------------
def diphone_pairs(phones):
    return ['%s-%s' % (phones[i], phones[i + 1]) for i in range(len(phones) - 1)]


class UnitSelector:
    """Pick one recorded instance per diphone from section A (names) + B (ids).

    The engine (report_engine_synth.md sec.1.5) builds `"L-R"` keys, binary-searches
    the 20-byte name table, takes the section-B slice as the candidate set, and runs
    a Viterbi search whose cost callback consumes the 36-byte section-C records
    (phone ids at bytes 2-6, feature u16s at bytes 8/10/12/14).  We implement a cheap
    stand-in:

      * candidates      = B[start : start+count] (section-A slice, ascending unit id)
      * identity gate   = bytes 4,5 (the record's own diphone phone ids) must match the
                          requested diphone; a non-matching candidate is only used if
                          no matching one exists (verified to never happen: 418 495/418 495
                          Kendra and 396 683/396 683 Amy instances match)
      * context match   = bytes 2,3,6 must equal the requested neighbouring phone ids
                          (-2, -1, +1 around the diphone), padded with the "0" symbol;
                          the score is how many of the three agree (0..3)
      * ordering        = (identity, -context score, lowest unit id)
      * `mode='first'`  = ignore the context score (pure "first candidate per diphone")

    Section C bytes 4,5 carry the unit's own diphone phone ids; they are checked
    against the name-table diphone as a structural assertion (and reported).
    """

    def __init__(self, reader: cdxv.OBBReader):
        self.r = reader
        self.names = {d.name: (d.start, d.count) for d in reader.diphones()}
        self.b = reader.diphone_units()
        self.phon = reader.phonemes()
        self.pid = {p: i for i, p in enumerate(self.phon)}
        self.cache = {}

    def c_record(self, uid: int):
        if uid not in self.cache:
            self.cache[uid] = self.r.c_record(uid)
        return self.cache[uid]

    def candidates(self, name: str):
        try:
            start, count = self.names[name]
        except KeyError:
            return None
        return self.b[start:start + count]

    def variant(self, name: str, uid: int):
        """Position of `uid` inside its diphone's section-B slice (engine: variant)."""
        try:
            start, count = self.names[name]
        except KeyError:
            return None
        sl = self.b[start:start + count]
        lo, hi = 0, len(sl)
        while lo < hi:                        # the slices are sorted ascending
            mid = (lo + hi) // 2
            if sl[mid] < uid:
                lo = mid + 1
            else:
                hi = mid
        return lo if lo < len(sl) and sl[lo] == uid else None

    def select(self, name: str, phones, i, mode='context'):
        """Select the unit for phones[i]-phones[i+1].  Returns a dict."""
        cand = self.candidates(name)
        if cand is None:
            return None
        pid = self.pid

        def p(idx):
            if 0 <= idx < len(phones):
                return pid.get(phones[idx], 0)
            return pid.get('0', 0)

        want = (p(i - 2), p(i - 1), p(i + 2))
        own = (p(i), p(i + 1))
        best = None
        own_ok = 0
        for uid in cand:
            c = self.c_record(uid)
            ids = (c[2], c[3], c[4], c[5], c[6])
            match = (ids[2], ids[3]) == own
            own_ok += match
            score = 0
            if mode == 'context':
                ctx = (ids[0], ids[1], ids[4])
                score = sum(1 for a, b in zip(ctx, want) if a == b)
            key = (0 if match else 1, -score, uid)
            if best is None or key < best[0]:
                best = (key, uid, ids, c)
        key, uid, ids, c = best
        return dict(name=name, unit=uid, n_cand=len(cand), score=-key[1],
                    ids=ids, own_ids=own, own_ok=(own_ok, len(cand)),
                    dur_ms=(c[0] | (c[1] << 8)), feats=(c[8], c[10], c[12], c[14]))


# ---------------------------------------------------------------------------
# 4. decode + splice
# ---------------------------------------------------------------------------
def resample(pcm, src_rate, dst_rate):
    """Rate conversion by the codec's own output-rate converter.

    The engine's unit decode is bit-exact at the codec rate (24 000 Hz; the
    clean-room `codec_spec.Spec` reproduces `decode_unit.Codec` byte-for-byte at
    both 24 000 and 22 050).  The shipped container declares 22 050 Hz, and the
    engine converts the committed codec-rate stream through its output-rate
    converter (`FUN_0014b4a8` / `FUN_0014c494`, ported as
    `scripts/codec_parts/resample.py`).  This replaces the former Hamming-sinc
    stand-in: same goal, but the arithmetic is the engine's own and is verified
    sample-exact for the 24 000 -> 22 050 pair (`test_resample.py`).  Not used
    when `src_rate == dst_rate`.
    """
    if src_rate == dst_rate:
        return list(pcm)
    return codec_resample.Resampler(src_rate, dst_rate).run(list(pcm))


def _engine_select(g2p, text, sel, cx, voice, beam=50):
    """Run the engine's duration CART + target/join-cost Viterbi for `text`.

    Returns a dict with the per-diphone `align` entries (same shape as
    `UnitSelector.select`), the CART durations per segment, and the lattice /
    cost diagnostics of `engine_prosody.EngineSelector.select`.
    """
    cfg = VOICES[voice]
    ps = PhoneSet.from_so(_resolve(cfg['pset_so']), cfg['pset'])
    cart = prosody.Cart.from_so(_resolve(cfg['zdur_so']))
    items, _detail = phone_items(g2p, text, sel.names)
    phones = items_phones(items)
    pairs = diphone_pairs(phones)
    esel = engine_prosody.EngineSelector(cx, cart, ps, beam=beam,
                                        tb_min_distance=cfg['tb_min_distance'])
    esel.pm.pause_base = cfg['pause_base']
    utt = esel.pm.analyse(items)
    durs = esel.pm.durations(utt)
    path, diag = esel.select(utt, pairs)
    if path is None:
        raise SystemExit("engine selection failed: %r" % (diag,))
    align = []
    pid = {p: i for i, p in enumerate(cx.phonemes())}
    p0 = pid.get('0', 0)

    def ph(k):
        return pid.get(phones[k], p0) if 0 <= k < len(phones) else p0

    for i, (name, uid) in enumerate(zip(pairs, path)):
        c = cx.c_record(uid)
        ids = (c[2], c[3], c[4], c[5], c[6])
        want = (ph(i - 2), ph(i - 1), ph(i + 2))
        ctx = (ids[0], ids[1], ids[4])
        score = sum(1 for x, y in zip(ctx, want) if x == y)
        cart_diphone = (durs[i][0] + durs[i + 1][0]) * 1000.0
        align.append(dict(name=name, unit=uid, n_cand=diag['n_cand'][i], score=score,
                          ids=ids, own_ids=(ph(i), ph(i + 1)), own_ok=(1, 1),
                          dur_ms=(c[0] | (c[1] << 8)),
                          feats=(c[8], c[10], c[12], c[14]),
                          variant=sel.variant(name, uid),
                          target_cost=dict(diag['target'][i])[uid],
                          cart_left_ms=durs[i][0] * 1000.0,
                          cart_right_ms=durs[i + 1][0] * 1000.0,
                          cart_diphone_ms=cart_diphone,
                          join_variant=diag['join_variants'][i]))
    return dict(align=align, diag=diag, durations=durs, utt=utt, ps=ps, cart=cart,
                items=items, phones=phones, pairs=pairs,
                approximations=engine_prosody.APPROXIMATIONS)


def synth(text: str, voice: str = 'kendra', rate: int = DEFAULT_RATE,
          codec_rate: int = CODEC_RATE, mode: str = 'context', beam: int = 50,
          resample_out: bool = False):
    """Run the whole pipeline; return (pcm_out, info dict).

    `mode` = 'viterbi' (the engine's own duration CART + target/join-cost Viterbi,
    `refimpl/engine_prosody.py`) or the historical `context` / `first` heuristics.
    `codec_rate` is the codec's synthesis rate (see CODEC_RATE); `rate` is the
    rate written into the WAV header, i.e. the voice's own `sample_rate`.
    `resample_out` converts the committed stream from `codec_rate` to `rate` with
    the codec's own output-rate converter (`scripts/codec_parts/resample.py`); it
    is **off by default because the engine does not convert**: the shipped voice
    defines no `resample_wave` parameter, so `FUN_0005d7c4`'s conditional
    `FUN_00059958` never runs and the wave carries 24 kHz samples labelled
    22 050 Hz (verified sample-exactly against `out/oracle/ref_*/kendra_hello.pcm`).
    """
    cfg = VOICES[voice]
    obb_path = _resolve(cfg['obb'])
    g2p_so = _resolve(cfg['g2p'])

    t0 = time.time()
    ob = du.Obb(obb_path)                       # unit records + gap windows
    cx = cdxv.OBBReader(obb_path)               # section A/B/C/E tables
    sel = UnitSelector(cx)

    g2p = G2P(g2p_so)
    phones, detail = phone_sequence(g2p, text, sel.names)
    if not phones:
        raise SystemExit("no pronounceable words in %r" % text)
    pairs = diphone_pairs(phones)

    eng = None
    if mode == 'viterbi':
        eng = _engine_select(g2p, text, sel, cx, voice, beam)

    # --- select + decode the units ----------------------------------------
    # Clean-room, stdlib-only gap decoder (scripts/codec_spec.py).  It is
    # bit-exact to the emulated `decode_unit.Codec` at the codec rate and
    # implements the engine's own output-rate branch for other rates, so no
    # Unicorn enters the runtime path and no resampler stand-in is needed.
    codec = codec_spec.Spec(out_rate=codec_rate)
    units = []                                   # decoded, spliced-ready
    align = []
    missing = []
    for i, name in enumerate(pairs):
        if eng is not None:
            info = eng['align'][i]
        else:
            info = sel.select(name, phones, i, mode=mode)
        if info is None or info['own_ok'][0] == 0:
            missing.append(name)
            continue
        rec = ob.record(info['unit'])
        if rec is None:
            missing.append(name)
            continue
        pcm = codec.decode_window(ob.cksum, ob.window(rec), rec['Y'], rec['samples'])
        blocks = su.segment_pcm(pcm, rec)
        units.append(dict(pms=list(rec['ramp']), blocks=blocks,
                          name=name, samples=rec['samples'], N=rec['N'],
                          dur_ms=info['dur_ms'], unit=info['unit']))
        align.append(dict(info, samples=rec['samples'], N=rec['N'],
                          segs=[len(b) for b in blocks]))
    if not units:
        raise SystemExit("no diphone unit could be selected")

    # The `pau` silence-alignment windows the engine applies *before* the splice:
    # `FUN_00063350(obj, frm, to, target)` -> `FUN_00062d14` (the SOLA restretch).
    # `segment_unit.stretch` reproduces it sample-exactly -- verified against the
    # engine at every pass depth (1..4) of the leading window and for all four
    # windows of the captures, and the committed streams are then byte-identical
    # to `out/oracle/ref_*/kendra_hello.pcm`.
    pauses = pause_align(units, eng['durations'], rate) if eng is not None else []
    for p in pauses:
        u = units[p['k']]
        factor = f32(f32(p['target']) / f32(p['cur']))
        u['pms'], u['blocks'] = su.stretch(list(u['pms']), u['blocks'], p['frm'],
                                           p['to'], factor)
        p['after'] = (len(u['pms']), u['pms'][-1])
        align[p['k']].setdefault('pause_align', []).append(p)

    # --- splice with the engine rule-set (unit_flags + segment_unit.splice) ----
    cap = sum(u['samples'] for u in units) + 5 * codec_rate
    st = dict(rate=codec_rate, cap=cap, pos=0, tail=0, total=0, out=[0] * cap)
    flags = unit_flags(units)
    for k, (u, fl) in enumerate(zip(units, flags)):
        su.splice(st, dict(pms=u['pms'], blocks=u['blocks']), flag=fl)
        align[k]['concat_flag'] = fl
        align[k]['pos_after'] = st['pos']
        align[k]['tail_after'] = st['tail']
    pos_committed = st['pos']                    # `finalize` resets st['pos']
    tail_pending = st['tail']
    total_committed = st['total']
    raw = su.finalize(st, 0)
    raw_stream = raw                             # codec-domain (24 000 Hz) stream

    info = dict(obb=obb_path, rate=rate, codec_rate=codec_rate, phones=phones,
                pairs=pairs, words=detail, units=units, align=align,
                missing=missing, pos=pos_committed, tail=tail_pending,
                total=total_committed, flags=flags, pause_align=pauses,
                sum_samples=sum(u['samples'] for u in units),
                elapsed=time.time() - t0, cap=cap, resampled=False,
                pcm_raw=raw_stream, prosody=None)
    if eng is not None:
        info['prosody'] = eng
    # The engine's wave object is the *codec-domain* stream labelled with the
    # voice's rate: the shipped voice defines no `resample_wave` parameter
    # (out/oracle/*/settings.txt / the plug-in key list), so `FUN_0005d7c4`'s
    # conditional `FUN_00059958` never runs and the committed samples reach the
    # bridge untouched.  `--resample` opts back in to a genuine conversion.
    if resample_out and rate != codec_rate:
        raw = resample(raw, codec_rate, rate)
        info['resampled'] = True
    return raw, info


def unit_flags(units):
    """The concat flag each unit is spliced with (`FUN_0005d7c4`:42382-42400).

    flag 0 <=> a next unit exists whose `diphone` feature value -- the voxdb
    record index, i.e. our `unit` -- is this unit's + 1.  Consecutive section-B
    records share a joint waveform, so that seam is *not* crossfaded.  flag 1
    otherwise, including the utterance's last unit (its "next" item is NULL).

    Verified against the instrumented engine on 67/68 transitions of the three
    captures (`out/oracle/stream_*/stream_trace.txt`); the single exception is
    `ref_default` unit 237953 (flag 1 although the next unit is 237954), where
    the following item is not a plain diphone item.  That exception is
    output-neutral for the capture: unit 237954's block 0 is 147 samples, the
    same length as the held tail, so either flag commits the same samples.
    """
    out = []
    for k, u in enumerate(units):
        fl = 0 if (k + 1 < len(units) and units[k + 1]['unit'] == u['unit'] + 1) else 1
        out.append(fl)
    return out


def f32(x):
    """Round to IEEE-754 single precision (the engine's soft-float arithmetic)."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


def segment_index(pms, k):
    """`FUN_00062500(obj, k)`: the segment whose marks bracket sample `k`.

    The engine returns the first `i < N-1` with `k <= pms[i] and k < pms[i+1]`,
    `0` for `k == 0` and `-1` when no segment matches (k at or past pms[N-2]).
    """
    if k == 0:
        return 0
    for i in range(len(pms) - 1):
        if k <= pms[i] and k < pms[i + 1]:
            return i
    return -1


def pause_align(units, ends, rate):
    """The `pau` silence-alignment windows the engine applies *before* the splice.

    `FUN_0005d7c4`:42256-42400, once per unit, on the freshly decoded record
    object (`obj+0x0c` -> the cumulative `pms[]` marks):

      * `k = (int)((dur_ms/1000 * 0.5) * rate)`, `i = FUN_00062500(obj, k)`; then
        `i -= 1` when `(double)(0.5*dur_ms/1000) <= 0.5 * (float)(pms[i-1]+pms[i])/rate`
        (the boundary is snapped to the nearer side of the mark range);
      * L phone == `pau` -> `FUN_00063350(obj, 0, i, target)`;
      * R phone == `pau` -> `FUN_00063350(obj, i+1, N-1, target)`;
      * `target = (int)(rate * (end(seg) - end(prev(seg))))`, halved when the
        segment has both neighbours; `end` is the prosody model's cumulative
        segment end (the `pau` increments come from `scripts.prosody.pause_duration`).

    Everything else is left untouched: the four prosody transforms
    (`duration_stretch`/`pitch_stretch`/`compress`/`amplify`) all read 1.0 for
    this voice, so the `pau` alignment is the *only* pre-splice modification.

    `ends` = [(duration_s, cumulative_end_s), ...] per segment of the chain
    (`engine_prosody.ProsodyModel.durations`), segment `k` being the L phone of
    unit `k`.  Returns a list of dicts `{k, frm, to, target, cur}` in units.
    """
    out = []
    nseg = len(ends)
    for k, u in enumerate(units):
        lft, rgt = u['name'].split('-', 1)
        if 'pau' not in (lft, rgt):
            continue
        pms = u['pms']
        dur = f32(u['dur_ms'])
        kk = int(f32(f32(f32(dur / 1000.0) * 0.5) * f32(rate)))
        i = segment_index(pms, kk)
        if i > 0:
            t_prev = f32(f32(pms[i - 1]) / f32(rate))
            t_i = f32(f32(pms[i]) / f32(rate))
            mid = f32(t_prev + t_i) * 0.5
            if f32(dur / 1000.0) * 0.5 <= mid:
                i -= 1
        for side, seg in (('L', k), ('R', k + 1)):
            if (lft if side == 'L' else rgt) != 'pau':
                continue
            frm, to = (0, i) if side == 'L' else (i + 1, len(pms) - 1)
            if to <= frm:
                continue
            prev_end = ends[seg - 1][1] if seg - 1 >= 0 else 0.0
            target = f32(ends[seg][1] - prev_end)
            if 0 < seg < nseg - 1:
                target = f32(target * 0.5)
            cur = pms[to] - (pms[frm - 1] if frm else 0)
            out.append(dict(k=k, side=side, frm=frm, to=to, split=i,
                            target=int(f32(f32(rate) * target)), cur=cur))
    return out


def stream_chunks(info, chunk=None):
    """Per-`tts_streamer_synth0` frame counts, as the engine's caller sees them.

    `tts_streamer_synth0(streamer, buf, n)` (0x4b460) loops `FUN_0004ae28`
    (`remaining = n - written`) until the caller's buffer is full or the producer
    returns 0; the bridge's scratch buffer is `n = 0.3 * tts_voice_sample_rate` =
    6615 frames (report_engine_api.md sec.2.4).  The pump keeps appending units
    until `pos >= want`, `FUN_000618a8` copies `min(want, pos)` and slides the
    buffer down (pos -= n), and the *pending tail* rides along with the slide;
    when the item list is exhausted the loop finalises the remainder, so the last
    call returns `total mod chunk`.  `trace.log` for the three captures shows
    exactly this: 6615 x 5 + 5708 (`ref_nopunct`), 6615 x 8 + 729
    (`ref_default`), 6615 x 7 + 2987 (`ref_lexclean`).
    """
    total = info['pos']
    chunk = chunk or int(0.3 * info['rate'])
    out = []
    while total > 0:
        n = min(chunk, total)
        out.append(n)
        total -= n
    return out or [0]


def stream_len_model(info):
    """Predicted committed length for the engine's rule-set.

    Every unit emits blocks 0..N-2: block 0 is crossfaded with the pending tail
    (`min(tail, len(block0))` samples, the earlier samples of block 0 dropped)
    when a tail is pending, otherwise copied whole.  The concat flag decides the
    fate of the unit's *last* block: flag 1 holds it as the tail (a pending tail
    is uncommitted and is overwritten by the next unit's crossfade), flag 0 drops
    it.  The tail pending when the utterance ends is never committed, because
    `FUN_000618a8` copies only `pos`.
    """
    pos = 0
    tail = 0
    total = 0
    for k, u in enumerate(info['units']):
        blocks = u['blocks']
        N = len(blocks)
        written = 0
        if N >= 2:
            if tail >= 1:
                written += min(tail, len(blocks[0]))
            else:
                written += len(blocks[0])
            for j in range(1, N - 1):
                written += len(blocks[j])
        pos += written
        tail = len(blocks[-1]) if info['flags'][k] else 0
        total += written
    return pos, tail, total


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------
def write_wav(path, pcm, rate):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    du.write_wav(path, pcm, rate)


def check_tables(voice='kendra'):
    """Validate the A -> B -> index -> C chain used by unit selection.

    For every one of the 418 495 / 396 683 diphone instances, the section-C record's
    own diphone phone ids (bytes 4,5) must equal the phone ids of the section-A name
    whose section-B slice contains that unit.
    """
    cfg = VOICES[voice]
    r = cdxv.OBBReader(_resolve(cfg['obb']))
    pid = {p: i for i, p in enumerate(r.phonemes())}
    B = r.diphone_units()
    t0 = time.time()
    bad = tot = 0
    for d in r.diphones():
        a, b = d.name.split('-', 1)
        want = (pid[a], pid[b])
        for uid in B[d.start:d.start + d.count]:
            c = r.c_record(uid)
            tot += 1
            bad += (c[4], c[5]) != want
    print("[tables] section C bytes 4,5 == (L,R) phone ids for %d/%d diphone instances "
          "(%d bad) [%.1fs]" % (tot - bad, tot, bad, time.time() - t0))
    print("[tables] diphones %d, B entries %d, phonemes %d"
          % (len(r.diphones()), len(B), len(r.phonemes())))
    return bad == 0


def check_g2p(voice, words):
    """Regression check on the front-end: our word -> phones vs the reference scripts."""
    cfg = VOICES[voice]
    cx = cdxv.OBBReader(_resolve(cfg['obb']))
    g2p = G2P(_resolve(cfg['g2p']))
    lx = lex_decode.Lexicon(so=_resolve(cfg['g2p']))
    lt = lts_decode.Lts(so=_resolve(cfg['g2p']))
    names = {d.name for d in cx.diphones()}
    bad = 0
    for w in words:
        ours, src = g2p.word(w)
        ref = lx.lookup(w)
        if ref is None:
            ref = lt.lts(w)
        ref = [STRESS_RE.sub('', p) for p in ref if p not in SKIP_PHONES]
        ok = ours == ref
        bad += not ok
        print("%-16s %-4s ours=%-26s ref=%-26s %s"
              % (w, src, " ".join(ours), " ".join(ref), "OK" if ok else "DIFF"))
    print("[g2p] %d/%d words match scripts/lex_decode.py || scripts/lts_decode.py"
          % (len(words) - bad, len(words)))
    # diphone coverage of a chained sequence
    phones, _ = phone_sequence(g2p, " ".join(words), names)
    pairs = diphone_pairs(phones)
    absent = [p for p in pairs if p not in names]
    print("[g2p] chained sequence: %s" % " ".join(phones))
    print("[g2p] %d diphone pairs, %d absent from section A %s"
          % (len(pairs), len(absent), absent or ""))
    return bad == 0


def print_alignment(info):
    viterbi = info.get('align') and 'cart_diphone_ms' in info['align'][0]
    if viterbi:
        print("%-4s %-9s %-8s %6s %6s %6s %7s %7s %8s %-8s %s"
              % ("#", "diphone", "unit", "cand", "var", "cart", "db_ms", "tgt",
                 "segs", "join", "N/samp"))
    else:
        print("%-4s %-10s %-8s %6s %5s %6s %6s %6s  %-18s %s"
              % ("#", "diphone", "unit", "cand", "ctx", "N", "samp", "seg0",
                 "ctx ids(l2,l1,L,R,r1)", "feat(8,10,12,14)"))
    prev = None
    adj = 0
    for k, a in enumerate(info['align']):
        if prev is not None and a['unit'] == prev + 1:
            adj += 1
        prev = a['unit']
        if viterbi:
            print("%-4d %-9s %-8d %6d %6s %6.0f %7d %7d %8d %-8s %d/%d"
                  % (k, a['name'], a['unit'], a['n_cand'], a.get('variant'),
                     a['cart_diphone_ms'], a['dur_ms'], a['target_cost'],
                     a['segs'][0], a.get('join_variant', '').replace('join_cost_', ''),
                     a['N'], a['samples']))
        else:
            print("%-4d %-10s %-8d %6d %5d %6d %6d %6d  %-18s %s"
                  % (k, a['name'], a['unit'], a['n_cand'], a['score'], a['N'],
                     a['samples'], a['segs'][0], str(a['ids']),
                     str(a['feats'])))
    if info['align']:
        scores = [a['score'] for a in info['align']]
        tot = len(info['align'])
        print("selection: %d units, mean context match %.2f/3, %d/%d units are the "
              "successor of the previous one (same recorded token)"
              % (tot, sum(scores) / float(tot), adj, max(0, tot - 1)))
    if info.get('prosody'):
        print("prosody: Σcart %.0f ms vs Σrecord %.0f ms (acoustic length is the "
              "recorded unit: duration_stretch = 1)"
              % (sum(a['cart_diphone_ms'] for a in info['align']),
                 sum(a['dur_ms'] for a in info['align'])))
    if info['missing']:
        print("missing diphones (skipped): %s" % info['missing'])


def dump_json(path, info, text, voice):
    """Write the alignment / selection summary consumed by scripts/analyze_tts.py."""
    import json
    obj = dict(text=text, voice=voice, rate=info['rate'],
               codec_rate=info['codec_rate'], resampled=info['resampled'],
               obb=info['obb'], engine_so=ENGINE_SO, samples=info['pos'],
               tail=info['tail'], sum_samples=info['sum_samples'],
               concat_flags=info['flags'],
               pause_align=info['pause_align'],
               stream_chunks=stream_chunks(info),
               duration_s=info['pos'] / float(info['codec_rate']),
               phones=info['phones'], pairs=info['pairs'], missing=info['missing'],
               words=[dict(word=w, source=s, phones=p) for w, s, p in info['words']],
               units=[dict(diphone=a['name'], unit=a['unit'], n_cand=a['n_cand'],
                           ctx_score=a['score'], ctx_ids=list(a['ids']),
                           feats=list(a['feats']), dur_ms=a['dur_ms'],
                           N=a['N'], samples=a['samples'], segs=a['segs'],
                           pos_after=a['pos_after'], tail_after=a['tail_after'],
                           variant=a.get('variant'),
                           cart_left_ms=a.get('cart_left_ms'),
                           cart_right_ms=a.get('cart_right_ms'),
                           cart_diphone_ms=a.get('cart_diphone_ms'),
                           target_cost=a.get('target_cost'),
                           join_variant=a.get('join_variant'))
                      for a in info['align']])
    eng = info.get('prosody')
    if eng:
        obj['prosody'] = dict(
            durations=[[d, e] for d, e in eng['durations']],
            segments=[s.name for s in eng['utt'].segs],
            n_cand=eng['diag']['n_cand'], n_cand_used=eng['diag']['n_cand_used'],
            beam=eng['diag']['beam'], path_cost=eng['diag']['cost'],
            join_variants=eng['diag']['join_variants'],
            approximations=[list(a) for a in eng['approximations']])
    with open(path, 'w') as f:
        json.dump(obj, f, indent=1)


def verify_against_engine(info):
    """Splice the *same* unit chain through the real library and compare sample-exactly.

    Validates the acoustic stage end to end -- codec decode -> `ramp[]`
    segmentation -> crossfade splice -> concat flags -> chunked commit -- for the
    chain this pipeline chose.  The comparison uses the chain's *raw* units
    (re-decoded with the clean-room codec here): `info['pcm_raw']` carries the
    `pau` restretch windows, which are implemented from `FUN_00063350`/
    `FUN_00062d14` and verified against the real function per pass with
    `scripts/probe_stretch.py` (driving the engine's own composite restretch here
    would cost ~10 minutes per window).
    """
    ob = du.Obb(info['obb'])
    codec = codec_spec.Spec(out_rate=info['codec_rate'])
    raw_units = []
    for u in info['units']:
        rec = ob.record(u['unit'])
        pcm = codec.decode_window(ob.cksum, ob.window(rec), rec['Y'], rec['samples'])
        raw_units.append(dict(pms=list(rec['ramp']), blocks=su.segment_pcm(pcm, rec)))
    cap = sum(len(b) for u in raw_units for b in u['blocks']) + 5 * info['codec_rate']
    st = dict(rate=info['codec_rate'], cap=cap, pos=0, tail=0, total=0, out=[0] * cap)
    for u, fl in zip(raw_units, info['flags']):
        su.splice(st, dict(pms=u['pms'], blocks=u['blocks']), flag=fl)
    pcm = su.finalize(st, 0)

    eng = su.Engine(info['obb'])
    st = eng.new_streamer(cap=cap)
    for u, fl in zip(info['units'], info['flags']):
        w, _obj = eng.unit(u['unit'])
        eng.splice_call(st, w, fl)
    eng.mark_sync(st)
    got = eng.read_out(st, st['pos'])
    nd = sum(1 for a, b in zip(got, pcm) if a != b) + abs(len(got) - len(pcm))
    print("[engine] same chain via libttsivonavoice.so: %d samples (ours %d), "
          "sample diffs = %d -> %s" % (len(got), len(pcm), nd,
                                       "BIT-EXACT" if nd == 0 else "MISMATCH"))
    return nd == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--text')
    ap.add_argument('--phones', metavar='TEXT',
                    help='only print the phoneme sequence for TEXT (compare with '
                         'scripts/lex_decode.py / lts_decode.py)')
    ap.add_argument('--voice', default='kendra', choices=sorted(VOICES))
    ap.add_argument('--out')
    ap.add_argument('--rate', type=int, default=DEFAULT_RATE,
                    help='output WAV sample rate (default %d)' % DEFAULT_RATE)
    ap.add_argument('--codec-rate', type=int, default=CODEC_RATE,
                    help='codec synthesis rate; %d is engine-exact (default)' % CODEC_RATE)
    ap.add_argument('--select', default='viterbi',
                    choices=('viterbi', 'context', 'first'),
                    help="unit selection: 'viterbi' = the engine's own duration "
                         "CART + target/join-cost search (default), or the legacy "
                         "'context'/'first' heuristics")
    ap.add_argument('--resample', action='store_true',
                    help='convert the committed stream from --codec-rate to --rate '
                         '(off by default: the engine does not convert -- the voice '
                         'defines no resample_wave, so the wave carries the codec-rate '
                         'samples labelled with the voice rate)')
    ap.add_argument('--beam', type=int, default=25,
                    help='Viterbi beam (engine: viterbi_beam=50; <=0 disables)')
    ap.add_argument('--align', action='store_true', help='print the unit alignment table')
    ap.add_argument('--json', metavar='PATH',
                    help='write the alignment/selection summary as JSON')
    ap.add_argument('--verify-engine', action='store_true',
                    help='re-splice the chosen unit chain through the real .so and compare')
    ap.add_argument('--check-tables', action='store_true',
                    help='validate the diphone name/index/record chain and exit')
    ap.add_argument('--check-g2p', metavar='WORDS',
                    help='compare word->phones with scripts/lex_decode.py|lts_decode.py and exit')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    if args.check_tables:
        sys.exit(0 if check_tables(args.voice) else 1)
    if args.check_g2p:
        sys.exit(0 if check_g2p(args.voice, args.check_g2p.split()) else 1)

    if args.phones is not None:
        cfg = VOICES[args.voice]
        cx = cdxv.OBBReader(_resolve(cfg['obb']))
        sel = UnitSelector(cx)
        g2p = G2P(_resolve(cfg['g2p']))
        phones, detail = phone_sequence(g2p, args.phones, sel.names)
        for w, src, ph in detail:
            print("%-16s %-4s %s" % (w, src, " ".join(ph)))
        print("sequence: %s" % " ".join(phones))
        for name in diphone_pairs(phones):
            cand = sel.candidates(name)
            print("  %-10s %s" % (name, "ABSENT" if cand is None
                                  else "count=%d" % len(cand)))
        return

    if not args.text:
        ap.error("--text or --phones is required")
    pcm, info = synth(args.text, args.voice, args.rate, args.codec_rate, args.select,
                      args.beam, args.resample)
    out = args.out or os.path.join(ROOT, 'out', 'tts_demo', 'tts.wav')
    write_wav(out, pcm, args.rate)

    if not args.quiet:
        print("[g2p]    %s" % " ".join(info['phones']))
        print("[words]  %s" % " ".join("%s%s" % (w, '' if s == 'lex' else '*')
                                       for w, s, _ in info['words']))
        eng = info.get('prosody')
        if eng:
            print("[prosody] durations from zdur_cart (%d segments): %s"
                  % (len(eng['durations']),
                     " ".join("%.0f" % (d * 1000.0) for d, _e in eng['durations'])))
            print("[cost]   candidate counts %s -> beam %d kept %s"
                  % (eng['diag']['n_cand'], eng['diag']['beam'],
                     eng['diag']['n_cand_used']))
            print("[cost]   join variants  %s" % " ".join(eng['diag']['join_variants']))
            print("[cost]   total path cost %d" % eng['diag']['cost'])
        print("[diphones] %d units (%d missing), %d decoded samples total"
              % (len(info['units']), len(info['missing']), info['sum_samples']))
        model_pos, model_tail, model_total = stream_len_model(info)
        print("[stream] committed samples = %d == model %d ? %s  (held tail=%d, "
              "committed total=%d)" % (info['pos'], model_pos,
                                       info['pos'] == model_pos, info['tail'],
                                       info['total']))
        print("[stream] %d units decoded to %d samples; crossfade/splice drop = %d"
              % (len(info['units']), info['sum_samples'],
                 info['sum_samples'] - info['pos']))
        if info['pause_align']:
            for p in info['pause_align']:
                u = info['units'][p['k']]
                print("[pau]    unit %d (%s, %s phone) setlen seg[%d..%d] = %d "
                      "samples (was %d, factor %.4f) -> N=%d, %d samples "
                      "-- FUN_00063350/FUN_00062d14"
                      % (p['k'], u['name'], p['side'], p['frm'], p['to'],
                         p['target'], p['cur'], p['target'] / float(p['cur']),
                         p['after'][0], p['after'][1]))
        chunks = stream_chunks(info)
        print("[pull]   tts_streamer_synth0 chunks (0.3 s = %d frames): %s -> %d calls"
              % (chunks[0], " ".join(str(c) for c in chunks), len(chunks)))
        print("[wav]    %s  %d samples  %.4f s @ %d Hz%s"
              % (out, len(pcm), len(pcm) / float(args.rate), args.rate,
                 "" if not info['resampled'] else
                 "  (resampled from %d Hz; duration = %d/%d = %.4f s)"
                 % (info['codec_rate'], info['pos'], info['codec_rate'],
                    info['pos'] / float(info['codec_rate']))))
        if not info['resampled']:
            print("[wav]    codec-domain stream: %d samples = %.4f s at the %d Hz "
                  "synthesis rate, labelled %d Hz (the engine's own convention: the "
                  "voice defines no resample_wave)"
                  % (len(pcm), len(pcm) / float(info['codec_rate']),
                     info['codec_rate'], args.rate))
        print("[time]   %.1fs" % info['elapsed'])
    if args.align:
        print_alignment(info)
    if args.json:
        dump_json(args.json, info, args.text, args.voice)
    if args.verify_engine:
        verify_against_engine(info)


if __name__ == '__main__':
    main()
