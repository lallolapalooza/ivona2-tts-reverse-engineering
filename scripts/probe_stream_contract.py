#!/usr/bin/env python3
"""Diff the engine's streamer state machine against `scripts/segment_unit.py`.

Source of truth: `out/oracle/<capture>/stream_trace.txt`, written by
`emu/tts_run.py --stream-probe`, which snapshots the streamer struct
(`+0x10 pos`, `+0x14 tail`, `+0x18 total`) around every

  * `FUN_00061620(streamer, unit_obj, flag)`  -- splice      (`splice #k ...`)
  * `FUN_000618a8(streamer, want, events)`    -- finalize    (`finalize ...`)
  * `FUN_00061804(streamer, buf, n)`          -- silence pad (`pad ...`)
  * `FUN_00063350` / `FUN_00062718`           -- pau trim    (`trim ...`)

and also logs the unit object's `{+8 N, +0xc int32 pms[N]}` at splice time.

The model side decodes each unit of the trace's own chain with the clean-room
codec (`scripts/codec_spec.py`) at the codec rate, segments it by `ramp[]`
(`segment_unit.segment_pcm`) and replays `segment_unit.splice` **from the
engine's own state** at every call, so the first line whose `written`/`pos`
differs names the rule the Python model gets wrong.

    python3 scripts/probe_stream_contract.py out/oracle/stream_nopunct
"""
from __future__ import annotations

import argparse
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))
sys.path.insert(0, os.path.join(ROOT, 'refimpl'))

import codec_spec                                   # noqa: E402
import decode_unit as du                            # noqa: E402
import segment_unit as su                           # noqa: E402

SPLICE = re.compile(
    r"splice #(\d+) unit=(-?\d+) flag=(-?\d+) N=(-?\d+) pos=(-?\d+) tail=(-?\d+) "
    r"total=(-?\d+) pms=\[([0-9, ]*)\]")
SPLICE_OUT = re.compile(r"\s*-> written=(-?\d+) pos=(-?\d+) tail=(-?\d+) total=(-?\d+)")
FINAL = re.compile(
    r"finalize want=(-?\d+) pos0=(-?\d+) tail0=(-?\d+) -> n=(-?\d+) pos=(-?\d+) "
    r"tail=(-?\d+) total=(-?\d+)")
PAD = re.compile(r"pad\s+#(\d+) n=(-?\d+) pos=(-?\d+) tail=(-?\d+) total=(-?\d+)")


def parse(path):
    """-> (calls, finals, pads); a call is a dict of the engine's own numbers."""
    calls, finals, pads = [], [], []
    cur = None
    for line in open(path):
        m = SPLICE.match(line)
        if m:
            cur = dict(k=int(m.group(1)), unit=int(m.group(2)), flag=int(m.group(3)),
                       N=int(m.group(4)), pos0=int(m.group(5)), tail0=int(m.group(6)),
                       total0=int(m.group(7)),
                       pms=[int(x) for x in m.group(8).replace(" ", "").split(',') if x])
            continue
        m = SPLICE_OUT.match(line)
        if m and cur is not None:
            cur.update(written=int(m.group(1)), pos=int(m.group(2)),
                       tail=int(m.group(3)), total=int(m.group(4)))
            calls.append(cur)
            cur = None
            continue
        m = FINAL.match(line)
        if m:
            finals.append(dict(want=int(m.group(1)), pos0=int(m.group(2)),
                               tail0=int(m.group(3)), n=int(m.group(4)),
                               pos=int(m.group(5)), tail=int(m.group(6)),
                               total=int(m.group(7))))
            continue
        m = PAD.match(line)
        if m:
            pads.append(dict(k=int(m.group(1)), n=int(m.group(2)), pos=int(m.group(3)),
                             tail=int(m.group(4)), total=int(m.group(5))))
    return calls, finals, pads


def model_chain(obb_path, units, rate):
    """Decode + segment the given unit ids exactly as `refimpl/tts.py` does."""
    ob = du.Obb(obb_path)
    codec = codec_spec.Spec(out_rate=rate)
    out = []
    for uid in units:
        rec = ob.record(uid)
        pcm = codec.decode_window(ob.cksum, ob.window(rec), rec['Y'], rec['samples'])
        out.append(dict(unit=uid, pms=list(rec['ramp']), blocks=su.segment_pcm(pcm, rec),
                        samples=rec['samples'], N=rec['N']))
    return out


def model_stream(obb_path, units, rate):
    """Decode + segment the chain and splice it with the *engine* flag rule."""
    import tts as pipeline
    chain = model_chain(obb_path, units, rate)
    flags = pipeline.unit_flags(chain)
    cap = sum(u['samples'] for u in chain) + 5 * rate
    st = dict(rate=rate, cap=cap, pos=0, tail=0, total=0, out=[0] * cap)
    for u, fl in zip(chain, flags):
        su.splice(st, dict(pms=u['pms'], blocks=u['blocks']), flag=fl)
    return su.finalize(st, 0), flags, chain


def read_wav(path):
    import wave
    w = wave.open(path)
    n = w.getnframes()
    return list(struct.unpack('<%dh' % n, w.readframes(n)))


def pcm_compare(capture, engine_pcm, our_pcm, rate, max_report=12):
    """Align the engine's PCM against ours and report the residual regions.

    The engine's stream is our committed stream with the `pau` restretch windows
    excised, so the two agree at a constant sample offset outside those windows.
    The offset is *measured* (the shift with the most equal samples), then the
    differing runs are printed.
    """
    E = read_wav(engine_pcm)
    M = read_wav(our_pcm)
    best = (0, 0)
    for sh in range(0, 4001):
        n = min(len(E), len(M) - sh)
        if n <= 0:
            break
        eq = sum(1 for i in range(n) if E[i] == M[i + sh])
        if eq > best[1]:
            best = (sh, eq)
    sh = best[0]
    n = min(len(E), len(M) - sh)
    runs = []
    for i in range(n):
        if E[i] != M[i + sh]:
            if runs and i == runs[-1][1] + 1:
                runs[-1][1] = i
            else:
                runs.append([i, i])
    nd = sum(r[1] - r[0] + 1 for r in runs)
    print('[pcm]   engine %d samples, ours %d, measured shift +%d samples'
          % (len(E), len(M), sh))
    print('[pcm]   %d/%d samples differ (%.3f%%) in %d run(s)'
          % (nd, n, 100.0 * nd / n, len(runs)))
    for r in runs[:max_report]:
        print('[pcm]     engine[%d:%d] (%d samples) vs ours[%d:%d]'
              % (r[0], r[1] + 1, r[1] - r[0] + 1, r[0] + sh, r[1] + 1 + sh))
    if len(runs) > max_report:
        print('[pcm]     ... %d more runs' % (len(runs) - max_report))
    return nd


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('capture', help='e.g. out/oracle/stream_nopunct')
    ap.add_argument('--rate', type=int, default=24000)
    ap.add_argument('--obb', default=None, help='override the OBB path')
    ap.add_argument('--pcm', default=None,
                    help='our WAV to align against out/oracle/<capture>/kendra_hello.wav; '
                         'replays the whole chain (decode + flag rule + splice) and '
                         'prints the residual regions')
    ap.add_argument('--max-report', type=int, default=40)
    args = ap.parse_args()

    trace = os.path.join(args.capture, 'stream_trace.txt')
    if not os.path.exists(trace):
        raise SystemExit('no %s (run emu/tts_run.py --stream-probe)' % trace)
    calls, finals, pads = parse(trace)
    print('[trace] %s: %d splice calls, %d finalize, %d pad'
          % (trace, len(calls), len(finals), len(pads)))
    if not calls:
        return 1
    # NB: the trace's `pms=[...]` column is informational only -- the model
    # re-decodes the chain below with the clean-room codec, because the object
    # fields are reallocated by the `pau` restretch (`FUN_00062688`) and the
    # column then shows whichever array the object pointed at when it was read.

    # OBB: the oracle dir's sibling captures do not record it, so take the voice
    # expansion file from the pipeline's own voice table.
    obb = args.obb
    if obb is None:
        import tts as pipeline
        obb = pipeline._resolve(pipeline.VOICES['kendra']['obb'])

    if args.pcm:
        stream, flags, chain = model_stream(obb, [c['unit'] for c in calls], args.rate)
        eng_flags = [c['flag'] for c in calls]
        nd = pcm_compare(args.capture, os.path.join(args.capture, 'kendra_hello.wav'),
                         args.pcm, args.rate, args.max_report)
        nf = sum(1 for a, b in zip(flags, eng_flags) if a != b)
        print('[pcm]   flag rule (next unit id == this + 1): %d/%d transitions agree '
              'with the engine' % (len(flags) - nf, len(flags)))
        print('[pcm]   our committed stream = %d samples (engine %d)'
              % (len(stream), sum(c['written'] for c in calls)))
        return 0 if nd == 0 else 1

    chain = model_chain(obb, [c['unit'] for c in calls], args.rate)

    st = dict(rate=args.rate, cap=sum(u['samples'] for u in chain) + 5 * args.rate,
              pos=0, tail=0, total=0, out=[0] * (sum(u['samples'] for u in chain) +
                                                 5 * args.rate))
    bad = 0
    for i, (c, u) in enumerate(zip(calls, chain)):
        # keep the model in lock-step with the engine's own state before the call
        st['pos'], st['tail'], st['total'] = c['pos0'], c['tail0'], c['total0']
        st['out'] = [0] * st['cap']
        w = su.splice(st, dict(pms=u['pms'], blocks=u['blocks']), flag=c['flag'])
        ok = (w == c['written'] and st['pos'] == c['pos'] and st['tail'] == c['tail']
              and st['total'] == c['total'])
        pms_ok = list(c['pms']) == u['pms']
        if not (ok and pms_ok):
            bad += 1
            if bad <= args.max_report:
                print('DIFF #%-2d unit=%-7d flag=%d' % (i, c['unit'], c['flag']))
                if not pms_ok:
                    print('   pms   engine %s' % c['pms'])
                    print('   pms   model  %s' % u['pms'])
                    print('   pms   delta  %d samples' % (sum(u['pms']) - sum(c['pms'])))
                if not ok:
                    print('   written engine=%-5d model=%-5d | pos engine=%-6d model=%-6d'
                          '| tail engine=%-4d model=%-4d'
                          % (c['written'], w, c['pos'], st['pos'], c['tail'], st['tail']))
    print('[model] %d/%d splice calls reproduce the engine exactly; %d diverge'
          % (len(calls) - bad, len(calls), bad))
    if finals:
        tot_n = sum(f['n'] for f in finals)
        print('[finalize] %d calls, want=%s, n=%s (sum %d)'
              % (len(finals), sorted({f['want'] for f in finals}),
                 [f['n'] for f in finals][:8], tot_n))
    if pads:
        print('[pad] %d calls, total %d samples (pos %d -> %d)'
              % (len(pads), sum(p['n'] for p in pads), pads[0]['pos'], pads[-1]['pos']))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
