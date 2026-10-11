#!/usr/bin/env python3
"""Replay every ``setup`` golden vector through ``codec_parts.setup``."""
import copy
import glob
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import setup as setup_mod  # noqa: E402

STEPS = os.path.join(ROOT, 'out', 'codec', 'steps', 'rec*.pkl')


def main():
    files = sorted(glob.glob(STEPS))
    assert files, 'no vectors at %s' % STEPS
    total = 0
    checked = 0
    failed = 0
    for path in files:
        d = pickle.load(open(path, 'rb'))
        for r in d['seq']:
            if r['step'] != 'setup':
                continue
            total += 1
            before = r['before']
            after = r['after']
            ctx = bytearray(before['ctx'])
            frame_info = bytearray(before['frame_info'])
            samp = bytearray(before['samp'])
            n = r['args'][3]
            flag = r['args'][4]
            setup_mod.setup(ctx, frame_info, samp, n, flag)
            for name, got in (('ctx', ctx), ('frame_info', frame_info), ('samp', samp)):
                exp = after[name]
                if bytes(got) != exp:
                    failed += 1
                    bad = next((i for i in range(min(len(got), len(exp)))
                                if got[i] != exp[i]), None)
                    print('FAIL pkt=%d frame=%d %s off=%s exp=%r got=%r' % (
                        r['pkt'], r['frame'], name, hex(bad) if bad is not None else 'len',
                        exp[bad:bad + 4] if bad is not None else '?',
                        bytes(got)[bad:bad + 4] if bad is not None else '?'))
                    break
            else:
                checked += 1
    print('files=%d setup vectors=%d byte-identical=%d failed=%d' % (
        len(files), total, checked, failed))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
