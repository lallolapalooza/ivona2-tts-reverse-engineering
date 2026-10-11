"""Replay the ``codec_probe.py`` golden vectors through a port module.

A probe pickle holds, for every stage call, a ``before`` and ``after`` snapshot
of the buffers ``ctx / frame_info / coeffs / samp / info / nsp``.  ``check``
rebuilds the ``before`` state and runs the port's implementation of one stage,
then compares every named buffer with ``after`` -- exactly the method that
proved the ``setup`` stage.

Usage from a part module's self-test::

    from harness import check
    def call(st, r):                       # st: dict of bytearrays
        gain(st['ctx'], st['frame_info'], st['samp'], r['args'][3])
    check('gain', call)
"""
import glob
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STEPS = os.path.join(ROOT, 'out', 'codec', 'steps')

BUFS = ('ctx', 'frame_info', 'coeffs', 'samp', 'info', 'nsp')


def step_files(records=None):
    pats = [os.path.join(STEPS, 'rec*.pkl')]
    if records:
        pats = [os.path.join(STEPS, 'rec%06d.pkl' % r) for r in records]
    files = []
    for p in pats:
        files += sorted(glob.glob(p))
    return sorted(set(files))


def check(step, call, compare=BUFS, files=None, quiet=False, limit=None):
    """Run ``call(state, record)`` for every `step` vector and diff the buffers.

    Returns (vectors, failed).  ``call`` mutates a dict of bytearrays built from
    the record's ``before`` snapshot; ``compare`` lists the buffers that must
    then equal ``after``.
    """
    files = files or step_files()
    assert files, 'no golden vectors under %s' % STEPS
    total = 0
    failed = 0
    fails = []
    for path in files:
        with open(path, 'rb') as fh:
            d = pickle.load(fh)
        for r in d['seq']:
            if r['step'] != step:
                continue
            total += 1
            st = {k: bytearray(r['before'][k]) for k in BUFS}
            try:
                call(st, r)
            except Exception as exc:                      # noqa: BLE001
                failed += 1
                fails.append((os.path.basename(path), r['pkt'], r['frame'],
                              'EXC', repr(exc)))
                continue
            ok = True
            for name in compare:
                got = bytes(st[name])
                exp = r['after'][name]
                if got != exp:
                    failed += 1
                    ok = False
                    bad = next((i for i in range(min(len(got), len(exp)))
                                if got[i] != exp[i]), None)
                    fails.append((os.path.basename(path), r['pkt'], r['frame'],
                                  name,
                                  'off=%s exp=%r got=%r' % (
                                      hex(bad) if bad is not None else 'len',
                                      exp[bad:bad + 4], got[bad:bad + 4])))
                    break
            if ok and not quiet:
                pass
            if limit and total >= limit:
                break
        if limit and total >= limit:
            break
    if not quiet:
        for f in fails[:24]:
            print('FAIL %s pkt=%s frame=%s %s %s' % f)
        print('%s: vectors=%d byte-identical=%d failed=%d'
              % (step, total, total - failed, failed))
    return total, failed


def main(argv):
    step = argv[1] if len(argv) > 1 else None
    print(__doc__)
    print('available step vectors: %r' % (step,))


if __name__ == '__main__':
    main(sys.argv)
