#!/usr/bin/env python3
"""Engine-matching prosody and unit selection for `refimpl/tts.py`.

Three pieces of the real synthesizer, wired to the shipped data:

1. **Linguistic analysis** — the phoneme chain becomes a Festival-style
   `Token/Phrase/Word/Syllable/Segment` structure (syllables, stress, word and
   phrase counts), which is what the engine's feature builder `FUN_00060ed4`
   reads.
2. **Duration model** — `zdur_cart` (`FUN_00048110`, evaluator in
   `scripts/prosody.py:Cart`) predicts every segment's duration; `duration_func`
   (`FUN_00048400`) turns it into the cumulative `end` feature, and that feeds the
   duration slot (0x00) of the context vectors *and* the engine's
   start/end boundary windows.
3. **Unit selection** — the Viterbi of `FUN_0005fc04` with the engine's own
   costs: the target cost `FUN_00031234` -> `FUN_000309a4` over 96-byte vectors
   (candidate side = `scripts/diphone_vec.py`, the `FUN_0005f1dc` port) and the
   five context-specific join costs of `FUN_00030214`
   (`scripts/prosody.py:join_cost_*`), searched by `scripts/select_units.py`.

What is exact and what is approximated is listed in `APPROXIMATIONS` below and
measured per field by `scripts/compare_context.py` against the engine's own
`FUN_00060ed4` dump (`out/oracle/unit_feature_vectors.tsv`).
"""

from __future__ import annotations

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                            # cdxv
sys.path.insert(0, os.path.join(ROOT, 'scripts'))   # prosody / select_units / phoneset / diphone_vec

import cdxv                                         # noqa: E402
import prosody                                      # noqa: E402
import select_units                                 # noqa: E402
from phoneset import PhoneSet                       # noqa: E402
from diphone_vec import record_decoder              # noqa: E402
from gpos_table import gpos_of as _gpos_of, load as _load_gpos_table   # noqa: E402

F = prosody.f
f2i = prosody.f2i

#: what the context-vector construction supplies exactly vs approximates.
APPROXIMATIONS = [
    ("exact", "0x54/0x58/0x5c ph_vc/ph_cvox/ph_ctype",
     "static phoneset table of the plug-in (scripts/phoneset.py)"),
    ("exact", "0x00 duration (this segment) + the target duration used by the "
     "pause-guard term", "zdur_cart CART + the FUN_00048400 pause rules"),
    ("exact", "0x04/0x08/0x0c/0x10/0x14 p.p/p/self/n/n.n phone names",
     "the phoneme chain"),
    ("computed", "0x18/0x19 pos_in_syl, 0x20/0x21 pos_in_word, 0x22/0x23 syl_in/out",
     "our syllabifier (maximal onset over the plug-in's own vowel class)"),
    ("computed", "0x1a/0x1d/0x2c stress", "lexicon/LTS digits (0 when absent)"),
    ("exact", "0x30/0x38/0x40 gpos (3 slots)",
     "the plug-in's own closed-class dictionary (word -> tag; default "
     "`content`), recovered from its .rodata and parsed by "
     "`scripts/gpos_table.py`; validated per word by scripts/validate_gpos.py"),
    ("exact", "0x24/0x25 ssyl_in/ssyl_out, 0x26/0x27 ssyl_from/ssyl_to",
     "stressed-syllable counts and, for 0x26/0x27, the recovered "
     "nearest-stressed-syllable distance (`ssyl_distance`, plug-in getters "
     "ELF 0x34b74/0x34afc; validated by scripts/validate_ssyl.py)"),
    ("approximated", "0x1b/0x1e/0x2d glottal_stop_pos",
     "not modelled: 0 (no glottal-stop insertion in our phone chain)"),
    ("approximated", "0x34/0x3c/0x44/0x45-0x48/0x50/0x51 phrase & word counts",
     "phrase = one sentence; counts derived from our syllables"),
    ("approximated", "0x49/0x4a pos_in_utt/num_phrases", "single phrase utterance"),
    ("approximated", "0x4c endtone",
     "the intonation stage's default (the plug-in's rule is unresolved, "
     "report_prosody.md 5.3)"),
    ("approximated", "syllable `position_type`/`syl_break`/`accented` (CART "
     "features only)", "derived from word/phrase-final position"),
]

#: the engine's value for a missing string slot (phoneset entry 0).
NIL = "0"

#: legal English onsets used by the syllabifier (phone names).
ONSETS = set("""b ch d dh f g hh jh k l m n ng p r s sh t th v w y z zh
pl pr bl br tr dr kl kr gl gr fl fr th r sh r sl sm sn sp st sw tw kw gw
spl spr str skr sk sl sm sn sp st sw skw""".split())


# ---------------------------------------------------------------- analysis ---
class Seg:
    __slots__ = ("name", "stress", "word", "syl", "pos_in_syl", "pau")

    def __init__(self, name, stress=0, word=-1, syl=-1, pos_in_syl=0, pau=False):
        self.name = name
        self.stress = stress
        self.word = word
        self.syl = syl
        self.pos_in_syl = pos_in_syl
        self.pau = pau


class Syllable:
    __slots__ = ("segs", "stress", "vowel", "word", "pos_in_word", "index",
                 "onset_len")

    def __init__(self, segs, vowel, word, pos_in_word, index):
        self.segs = segs                    # list of segment indices
        self.vowel = vowel                  # the nucleus phone name
        self.stress = 0
        self.word = word
        self.pos_in_word = pos_in_word
        self.index = index                  # position in the utterance
        self.onset_len = 0


#: the engine's own closed-class dictionary for the word feature `gpos`
#: (slots 0x30/0x38/0x40 of the 96-byte context vector).  It is *not* a
#: statistical tagger: the plug-in ships the word -> tag table in its `.rodata`
#: (group array at ELF 0x2eb860, string VALs at 0x2ebb04) and tags every word
#: that the table does not list as `content`; see `scripts/gpos_table.py`.
GPOS_TABLE = _load_gpos_table()[1]


def gpos_of(word: str) -> str:
    """The engine's `gpos` tag for *word* (`content` when unlisted).

    `gpos_table.load()` parses the plug-in's table.  The word is folded to lower
    case first, which is what the engine does: in `out/oracle/gpos_case/`
    (`"That can go to the market"`) the engine tags the capitalised `That` as
    `in` -- the tag of `that` -- and `scripts/validate_gpos.py` shows the same
    for every segment of that capture as well as 73/73 segments over
    `ref_nopunct`/`ref_lexclean`/`ref_default`.
    """
    return _gpos_of(word, GPOS_TABLE)


def ssyl_distance(syls, k, step):
    """`ssyl_from` / `ssyl_to` of syllable *k* (slots 0x26 / 0x27).

    Recovered from the plug-in's own feature getters (`FUN_00044b74` =
    `ssyl_from`, `FUN_00044afc` = `ssyl_to`; ELF vaddrs 0x34b74 / 0x34afc,
    registered in `FUN_00044460`, plug-in dump :18862-18863).  Both walk the
    *Syllable* sibling chain - `*(x+0xc)` backwards for `ssyl_from`,
    `*(x+8)` forwards for `ssyl_to` (`FUN_00028c20` / `FUN_00028c14`) - starting
    at the neighbouring syllable and counting 1, 2, ... until a syllable whose
    `stress` feature is > 0 is met; that count is the value.  If the chain ends
    first the getter returns the static string VAL `"0"` (ELF 0x2efb8c /
    0x2efba4, payload 0x1f1f5c = the nil symbol), which the engine's integer
    coercion turns into 0.

    Verified byte-exact against all 28 syllables of
    `ref_nopunct`/`ref_lexclean`/`ref_default`
    (`scripts/validate_ssyl.py`).
    """
    j, n = k + step, 1
    while 0 <= j < len(syls):
        if syls[j].stress > 0:
            return n
        n += 1
        j += step
    return 0


class Word:
    __slots__ = ("text", "segs", "syls", "gpos", "index")

    def __init__(self, text, index):
        self.text = text
        self.segs = []
        self.syls = []
        self.gpos = gpos_of(text)
        self.index = index


class Utterance:
    """The engine's item graph, reduced to what the cost model reads."""

    def __init__(self):
        self.segs = []
        self.syls = []
        self.words = []
        self.phrase_syls = 0
        self.phrase_words = 0

    # -- lookups -------------------------------------------------------------
    def seg_name(self, i):
        i = min(max(i, 0), len(self.segs) - 1)
        return self.segs[i].name

    def syl_of(self, i):
        s = self.segs[i].syl
        return self.syls[s] if 0 <= s < len(self.syls) else None

    def word_of(self, i):
        w = self.segs[i].word
        return self.words[w] if 0 <= w < len(self.words) else None


def syllabify(phones, stresses, ps: PhoneSet, word_index, first_syl_index):
    """Maximal-onset syllabification of one word's phones (see APPROXIMATIONS)."""
    nuclei = [i for i, p in enumerate(phones) if ps.get(p).get("vc") == "+"]
    if not nuclei:
        nuclei = [len(phones) - 1] if phones else []
    syls = []
    if not nuclei:
        return syls
    # split the consonant runs between adjacent nuclei by the longest legal onset
    bounds = []                            # (start, end) per syllable, end exclusive
    start = 0
    for k, nuc in enumerate(nuclei):
        if k + 1 < len(nuclei):
            nxt = nuclei[k + 1]
            cluster = phones[nuc + 1:nxt]
            onset = 0
            for size in range(len(cluster), 0, -1):
                cand = cluster[len(cluster) - size:]
                if tuple(cand) in ONSETS or (size == 1 and cand[0] not in
                                             [p for p in phones if ps.get(p).get("vc") == "+"]):
                    onset = size
                    break
            end = nxt - onset
        else:
            end = len(phones)
        syls.append((start, end, nuc, onset if k + 1 < len(nuclei) else 0))
        start = end
    out = []
    for k, (a, b, nuc, onset) in enumerate(syls):
        if b <= a:
            b = a + 1
        s = Syllable(list(range(a, b)), phones[nuc], word_index, k,
                     first_syl_index + len(out))
        r = stresses[nuc] if nuc < len(stresses) else 0
        # the engine's `stress`/`p.stress` features are 0/1
        # (`report_prosody.md` sec.3.2 question domains)
        s.stress = 1 if r else 0
        s.onset_len = onset
        out.append(s)
    return out


class ProsodyModel:
    """Linguistic analysis + the `zdur_cart` duration model + context vectors."""

    def __init__(self, cart, ps: PhoneSet, pause_base=0.0, endtone="L"):
        self.cart = cart
        self.ps = ps
        #: the voice's `pause_base_len` parameter (settings.txt: Kendra/Amy set 0;
        #: the engine's own default is 0.35, `FUN_00026e18(*params, "pause_base_len",
        #: 0x3eb33333)`).
        self.pause_base = pause_base
        self.endtone = endtone
        self.utt = None

    # -- build the item graph ------------------------------------------------
    def analyse(self, items):
        """`items` = [("word", text, phones, stresses) | ("pau",), ...] -> Utterance.

        The item list is the utterance's segment chain with the clause-boundary
        and utterance-edge pauses already inserted (the engine's pause-insertion
        stage); word items expand to their phones.
        """
        utt = Utterance()
        for it in items:
            if it[0] == "pau":
                utt.segs.append(Seg("pau", pau=True, word=-1))
                continue
            _, wtext, phones, stresses = it
            if not phones:
                continue
            w = Word(wtext, len(utt.words))
            utt.words.append(w)
            syls = syllabify(phones, stresses, self.ps, w.index, len(utt.syls))
            for s in syls:
                s.index = len(utt.syls)
                utt.syls.append(s)
                w.syls.append(s)
            base = len(utt.segs)
            for j, p in enumerate(phones):
                utt.segs.append(Seg(p, stresses[j]))
                w.segs.append(len(utt.segs) - 1)
            for s in w.syls:
                local = list(s.segs)                    # word-local indices
                s.segs = [base + k for k in local]
                for pos, si in enumerate(s.segs):
                    utt.segs[si].syl = s.index
                    utt.segs[si].pos_in_syl = pos
                for si in s.segs:
                    utt.segs[si].word = w.index
        utt.phrase_syls = len(utt.syls)
        utt.phrase_words = len(utt.words)
        self.utt = utt
        return utt

    # -- duration model (FUN_00048110 + FUN_00048400) -------------------------
    def durations(self, utt=None):
        """Per-segment duration in seconds + the cumulative `end` feature."""
        utt = utt or self.utt
        out = []
        end = 0.0
        for i, s in enumerate(utt.segs):
            if s.pau:
                prev_phrase = "BB" if i == len(utt.segs) - 1 else None
                d = prosody.pause_duration(prev_phrase, i > 0,
                                           i < len(utt.segs) - 1,
                                           base=self.pause_base)
            else:
                d = self.cart.predict(s.name, self._feat_fn(utt, i)) / 1000.0
            end = F(F(end) + F(d))
            out.append((d, end))
        return out

    def _feat_fn(self, utt, i):
        """`feat(path) -> (tag, value)` for the CART's Festival feature paths."""
        seg = utt.segs[i]
        syl = utt.syl_of(i)
        word = utt.word_of(i)
        ps = self.ps

        def cls(off, feat):
            j = i + off
            if j < 0:
                j = 0
            if j >= len(utt.segs):
                j = len(utt.segs) - 1
            return str(ps.get(utt.segs[j].name).get(feat, "0"))

        def syl_at(k):
            if 0 <= k < len(utt.syls):
                return utt.syls[k]
            return None

        def syl_break(s):
            """`syl_break` domain observed in the tree: 0/1/3/4."""
            if s is None:
                return 0
            w = utt.words[s.word] if 0 <= s.word < len(utt.words) else None
            if w is None:
                return 0
            if s.index == len(utt.syls) - 1:
                return 4
            if s.pos_in_word == len(w.syls) - 1:
                if w.index == len(utt.words) - 1:
                    return 3
                return 1
            return 0

        def position_type(s):
            """Domain: single / initial / mid / final."""
            w = utt.words[s.word] if 0 <= s.word < len(utt.words) else None
            if w is None or len(w.syls) <= 1:
                return "single"
            if s.pos_in_word == 0:
                return "initial"
            if s.pos_in_word == len(w.syls) - 1:
                return "final"
            return "mid"

        def value(path):
            if path == "name":
                return (5, seg.name)
            if path == "p.name":
                return (5, utt.seg_name(i - 1) if i > 0 else "")
            if path == "n.name":
                return (5, utt.seg_name(i + 1) if i + 1 < len(utt.segs) else "")
            if path == "pos_in_syl":
                return (1, seg.pos_in_syl)
            if path == "syl_final":
                return (1, 1 if (syl and syl.segs[-1] == i) else 0)
            if path == "p.seg_onsetcoda":
                return (5, self._onsetcoda(utt, i - 1))
            m = path.split(".")
            if path.startswith("ph_"):
                return (5, cls(0, path[3:]))
            if m[0] in ("p", "pp", "n", "nn") and len(m) > 1 and m[1].startswith("ph_"):
                off = {"p": -1, "pp": -2, "n": 1, "nn": 2}[m[0]]
                return (5, cls(off, m[1][3:]))
            if path.startswith("R:SylStructure.parent.R:Syllable."):
                rest = path[len("R:SylStructure.parent.R:Syllable."):]
                if syl is None:
                    return (1, 0)
                if rest.startswith("pp.syl_break"):
                    return (1, syl_break(syl_at(syl.index - 2)))
                if rest.startswith("p.syl_break"):
                    return (1, syl_break(syl_at(syl.index - 1)))
                if rest.startswith("n.accented"):
                    nxt = syl_at(syl.index + 1)
                    return (1, 1 if (nxt and nxt.stress > 0) else 0)
                return (1, 0)
            if path.startswith("R:SylStructure.parent.parent."):
                rest = path[len("R:SylStructure.parent.parent."):]
                if rest.startswith("pos_in_phrase"):
                    return (1, word.index if word else 0)
                if rest.startswith("gpos"):
                    return (5, word.gpos if word else "")
                return (5, "")
            if path.startswith("R:SylStructure.parent."):
                rest = path[len("R:SylStructure.parent."):]
                if syl is None:
                    return (1, 0)
                if rest == "position_type":
                    return (5, position_type(syl))
                if rest == "pos_in_word":
                    return (1, syl.pos_in_word)
                if rest == "stress":
                    return (1, syl.stress)
                if rest == "syl_break":
                    return (1, syl_break(syl))
                if rest == "syl_vowel":
                    return (5, syl.vowel)
                if rest == "syl_in":
                    return (1, syl.index)
                return (1, 0)
            return (1, 0)

        return value

    @staticmethod
    def _onsetcoda(utt, i):
        """`seg_onsetcoda` (string): the segment's role inside its syllable."""
        if i < 0 or i >= len(utt.segs):
            return "onset"
        s = utt.syl_of(i)
        if s is None:
            return "onset"
        if utt.segs[i].name == s.vowel or utt.segs[i].pos_in_syl == s.onset_len:
            return "nucleus"
        return "onset" if utt.segs[i].pos_in_syl < s.onset_len else "coda"

    # -- context vectors (FUN_00060ed4) --------------------------------------
    def context_vectors(self, utt=None, durations=None):
        """One 96-byte `Vec96` per segment, as `FUN_00060ed4` writes them.

        Slot roles, engine values and the resulting choices are documented in
        `APPROXIMATIONS`; every numeric slot here was fitted slot-by-slot against
        `out/oracle/*/unit_feature_vectors.tsv` (see
        `scripts/compare_selection.py`).
        """
        utt = utt or self.utt
        durations = durations or self.durations(utt)
        ps = self.ps
        n_syl = len(utt.syls)
        n_word = len(utt.words)
        ssyl_total = sum(1 for x in utt.syls if x.stress > 0)
        out = []
        for i, s in enumerate(utt.segs):
            end = durations[i][1]
            pend = durations[i - 1][1] if i > 0 else 0.0
            raw = bytearray(0x60)
            strs = {}
            struct.pack_into("<f", raw, 0x00, F(F(end) - F(pend)))
            # neighbour phone names; the engine's nil value is the boundary
            # symbol "0" (phoneset entry 0), not an empty string
            strs[0x04] = utt.seg_name(i - 2) if i >= 2 else NIL
            strs[0x08] = utt.seg_name(i - 1) if i >= 1 else NIL
            strs[0x0c] = s.name
            strs[0x10] = utt.seg_name(i + 1) if i + 1 < len(utt.segs) else NIL
            strs[0x14] = utt.seg_name(i + 2) if i + 2 < len(utt.segs) else NIL
            syl, word = utt.syl_of(i), utt.word_of(i)
            if not s.pau and syl is not None and word is not None:
                pw = self._word_at(utt, word.index - 1)      # p. word
                nw = self._word_at(utt, word.index + 1)      # n. word
                psyl = self._syl_in_word(utt, word, syl.pos_in_word - 1)
                nsyl = self._syl_in_word(utt, word, syl.pos_in_word + 1)
                raw[0x18] = (s.pos_in_syl + 1) & 0xFF
                raw[0x19] = ((1 - (s.pos_in_syl + 1)) + len(syl.segs)) & 0xFF
                raw[0x1a] = (psyl.stress if psyl else 0)           # p.stress
                raw[0x1c] = (len(psyl.segs) if psyl else 0)        # p.syl_num_phones
                raw[0x1d] = syl.stress & 0xFF
                raw[0x1f] = len(syl.segs) & 0xFF                   # syl_num_phones
                raw[0x20] = (syl.pos_in_word + 1) & 0xFF
                raw[0x21] = ((1 - (syl.pos_in_word + 1)) + len(word.syls)) & 0xFF
                raw[0x22] = (syl.index + 1) & 0xFF
                raw[0x23] = ((1 - (syl.index + 1)) + n_syl) & 0xFF
                before = sum(1 for x in utt.syls[:syl.index] if x.stress > 0)
                raw[0x24] = before & 0xFF                          # ssyl_in
                raw[0x25] = (ssyl_total - before -
                             (1 if syl.stress > 0 else 0)) & 0xFF  # ssyl_out
                # distance (in syllables) to the previous / next *stressed*
                # syllable; recovered from the plug-in getters, see
                # `validate_ssyl.py`
                raw[0x26] = ssyl_distance(utt.syls, syl.index, -1)   # ssyl_from
                raw[0x27] = ssyl_distance(utt.syls, syl.index, +1)   # ssyl_to
                strs[0x28] = syl.vowel
                raw[0x2c] = (nsyl.stress if nsyl else 0)
                raw[0x2e] = (len(nsyl.segs) if nsyl else 0)
                strs[0x30] = pw.gpos if pw else NIL
                raw[0x34] = (len(pw.syls) if pw else 0) & 0xFF
                strs[0x38] = word.gpos
                raw[0x3c] = len(word.syls) & 0xFF
                raw[0x3d] = (word.index + 1) & 0xFF                # pos_in_phrase+1
                raw[0x3e] = (n_word - word.index) & 0xFF
                strs[0x40] = nw.gpos if nw else NIL
                raw[0x44] = (len(nw.syls) if nw else 0) & 0xFF
                raw[0x47] = utt.phrase_syls & 0xFF
                raw[0x48] = utt.phrase_words & 0xFF
                raw[0x49] = 1
                raw[0x4a] = 1
                strs[0x4c] = self.endtone
            else:
                # `pau` branch of FUN_00060ed4: only the syllable/word slots
                # reached from the neighbouring segments, plus the phrase counts
                pm1 = self._syl_at_seg(utt, i - 1)
                pp1 = self._syl_at_seg(utt, i + 1)
                pw = self._word_at_seg(utt, i - 1)
                nw = self._word_at_seg(utt, i + 1)
                raw[0x1a] = (pm1.stress if pm1 else 0)
                raw[0x1c] = (len(pm1.segs) if pm1 else 0)
                raw[0x2c] = (pp1.stress if pp1 else 0)
                raw[0x2e] = (len(pp1.segs) if pp1 else 0)
                strs[0x30] = pw.gpos if pw else NIL
                raw[0x34] = (len(pw.syls) if pw else 0) & 0xFF
                strs[0x40] = nw.gpos if nw else NIL
                raw[0x44] = (len(nw.syls) if nw else 0) & 0xFF
                raw[0x45] = (utt.phrase_syls if pw else 0) & 0xFF
                raw[0x46] = (utt.phrase_words if pw else 0) & 0xFF
                raw[0x50] = (utt.phrase_syls if nw else 0) & 0xFF
                raw[0x51] = (utt.phrase_words if nw else 0) & 0xFF
                strs[0x4c] = NIL
                # The `pau` branch writes neither 0x28 (`syl_vowel`) nor 0x38
                # (word `gpos`), but the engine's own capture holds the nil
                # symbol "0" in both slots (engine nil string, ELF 0x148430 of
                # libttsivonavoice; see out/oracle/ref_nopunct/
                # unit_feature_vectors.tsv rows for the two `pau` items).  With
                # the slots empty every first/last-node target cost is 5-6
                # points low; with them set the edge nodes match exactly.
                strs[0x28] = NIL
                strs[0x38] = NIL
            pf = ps.get(s.name)
            strs[0x54] = str(pf.get("vc", "0"))
            strs[0x58] = str(pf.get("cvox", "0"))
            strs[0x5c] = str(pf.get("ctype", "0"))
            out.append(prosody.Vec96(bytes(raw), strs))
        return out

    # -- helpers -------------------------------------------------------------
    def _word_at(self, utt, k):
        return utt.words[k] if 0 <= k < len(utt.words) else None

    def _word_at_seg(self, utt, i):
        if not (0 <= i < len(utt.segs)) or utt.segs[i].pau:
            return None
        return utt.word_of(i)

    def _syl_at_seg(self, utt, i):
        if not (0 <= i < len(utt.segs)) or utt.segs[i].pau:
            return None
        return utt.syl_of(i)

    @staticmethod
    def _syl_in_word(utt, word, k):
        return word.syls[k] if 0 <= k < len(word.syls) else None

# ------------------------------------------------------------- selection ----
def join_fn_for(ctx: prosody.Vec96):
    """`FUN_00030214`'s per-node join-cost dispatch (decompiled plug-in :7875-7900).

    The dispatcher reads the node's *right* context vector: `ph_ctype` (0x5c),
    `ph_vc` (0x54), `ph_cvox` (0x58) and the segment `name` (0x0c).
    """
    ctype = ctx.ch(0x5C)
    if ctype == "r":                      # unreachable with the shipped phonesets
        return prosody.join_cost_r
    if ctx.ch(0x54) == "+":               # vowel right edge
        return prosody.join_cost_plus
    if ctype == "g" or ctx.st(0x0C) == "l":
        return prosody.join_cost_gl
    if ctx.ch(0x58) == "-":               # unvoiced right edge
        return prosody.join_cost_dash
    return prosody.join_cost_default


class EngineSelector:
    """The engine's lattice + `FUN_0005fc04` search over one OBB.

    The candidate build (`+`-context filter + target cost), the 51-bucket beam with
    its context exemptions, the two candidate flag bytes and the chunked search all
    live in `scripts/select_units.py`; this class supplies the engine's inputs --
    durations, context vectors, the per-node join variant, the phone names and the
    `tb_min_distance` boundaries -- and the diagnostics `refimpl/tts.py` reports.
    """

    def __init__(self, reader: cdxv.OBBReader, cart, ps: PhoneSet, beam=25,
                 tb_min_distance=6):
        self.r = reader
        self.cart = cart
        self.ps = ps
        self.beam = beam
        #: live value for the shipped Kendra voice (`out/oracle/*/settings.txt`);
        #: the plug-in default is -1, i.e. no forced nodes at all.
        self.tb_min_distance = tb_min_distance
        self.phones = reader.phonemes()
        self.names = {d.name: (d.start, d.count) for d in reader.diphones()}
        self.b = reader.diphone_units()
        self.dec = record_decoder(reader)
        self.pm = ProsodyModel(cart, ps)

    # -- engine helpers ------------------------------------------------------
    def phone_name(self, record, offset):
        """The phone name a record byte indexes, as `FUN_0005fc04` reads it.

        The engine compares `*(char**)(payload+0x1c) + record[offset]*0x20`
        (the plug-in's inline phone table, 32-byte records) with a context-slot
        string; `record[+3]` is the phone *before* a record's own phone and `+5`
        the phone after it.
        """
        i = record[offset]
        return self.phones[i] if 0 <= i < len(self.phones) else None

    def forced_nodes(self, ctxs, n_nodes):
        """`FUN_00030214` (plug-in :7868): the `tb_min_distance` chunk boundaries.

        A node is forced (`node+0xc8 = 1`) when its *right* phone
        (`ctx2+0x54 ph_vc`) is voiced-`-`, at least `tb_min_distance` nodes past
        the previous forced one and at least `tb_min_distance` nodes before the
        end, and either the right phone is unvoiced (`ctx2+0x58 == "-"`) or the
        gap exceeds `1.5*tb` (`FUN_00053df8` = dmul with the double 1.5), and the
        right phone's class is not one of `rplg` (`strchr`, 0x203e8).  For the
        shipped voice this selects exactly node 10 of the test sentence, which is
        why the oracle capture calls `FUN_0005fc04` twice.
        """
        tb = self.tb_min_distance
        out = [False] * n_nodes
        if not tb or tb <= 0:
            return out
        last = 0
        for i in range(n_nodes):
            c2 = ctxs[i + 1]
            if i - last < tb or n_nodes - i < tb or c2.ch(0x54) != "-":
                continue
            if i - last <= 2 * tb:
                if c2.ch(0x58) != "-" and (i - last) <= 1.5 * tb:
                    continue
                ctype = c2.st(0x5C)
                if not ctype or ctype[0] in "rplg":
                    continue
            out[i] = True
            last = i
        return out

    # -- lattice -------------------------------------------------------------
    def lattice(self, pairs, ctxs):
        """`FUN_0005fc04`'s candidate build for every diphone of `pairs`.

        Returns one `select_units.Node` per position, already context-filtered and
        target-scored, with its join variant (`node+0xc4`) and `tb_min_distance`
        flag (`node+0xc8`).
        """
        flags = self.forced_nodes(ctxs, len(pairs))
        nodes = []
        for i, name in enumerate(pairs):
            rng = self.names.get(name)
            if rng is None:
                return None
            start, count = rng
            units = self.b[start:start + count]
            ctx1, ctx2 = ctxs[i], ctxs[i + 1]
            kept = select_units.build_candidates(units, ctx1, ctx2, self.dec.vector)
            cands = []
            for u in kept:
                t = prosody.dispatch_cost(self.dec.vector(u), self.dec.vector(u + 1),
                                          ctx1, ctx2)
                cands.append(select_units.Candidate(u, self.r.c_record(u),
                                                    self.r.c_record(u + 1), target=t))
            nodes.append(select_units.Node(cands, ctx1, ctx2,
                                           join=join_fn_for(ctx2),
                                           forced=flags[i]))
        return nodes

    def select(self, utt, pairs, verbose=False):
        """Run the engine's search; returns (unit ids, diagnostics)."""
        ctxs = self.pm.context_vectors(utt)
        if len(utt.segs) != len(pairs) + 1:
            return None, dict(note="chain/segment mismatch")
        nodes = self.lattice(pairs, ctxs)
        if nodes is None:
            missing = [n for n in pairs if n not in self.names]
            return None, dict(missing=missing, note="chain/lattice mismatch")
        diag = dict(n_cand=[len(self.b[s:s + c]) for s, c in
                            (self.names[n] for n in pairs)],
                    beam=self.beam, target=[], join_variants=[],
                    forced=[n.forced for n in nodes])
        diag["join_variants"] = [n.join.__name__ for n in nodes]
        diag["target"] = [[(c.db_idx, c.target) for c in n.cands] for n in nodes]
        diag["n_filtered"] = [len(n.cands) for n in nodes]
        path, sdiag = select_units.search(nodes, beam=self.beam,
                                          phone_name=self.phone_name, diag=diag)
        diag["chosen"] = path
        diag["n_cand_used"] = sdiag["n_kept"]
        diag["chunks"] = sdiag["chunks"]
        diag["cost"] = sdiag["cost"]
        return path, diag
