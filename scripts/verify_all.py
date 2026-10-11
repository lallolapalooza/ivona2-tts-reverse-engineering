#!/usr/bin/env python3
"""verify_all.py — run every layer verification in this repository and print one PASS/FAIL table.

Each check is the *same* test that was used to validate that layer during the reverse-engineering
session; nothing here re-implements logic, it only drives the existing tools so a third party (or a
reimplementation) can confirm the whole chain in one command.

Usage:
    python3 scripts/verify_all.py                # all checks (a few minutes)
    python3 scripts/verify_all.py --quick        # smaller sample sizes (~1 min)
    python3 scripts/verify_all.py --json out.json
    python3 scripts/verify_all.py --only codec,isef

Checks that need the emulation harness use ~/venvs/re/bin/python if it exists (it has unicorn +
pyelftools); everything else uses the current interpreter.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = os.path.expanduser('~/venvs/re/bin/python')
PY = VENV if os.path.exists(VENV) else sys.executable


def run(cmd, timeout=1800):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, shell=isinstance(cmd, str), capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, (p.stdout + p.stderr), time.time() - t0


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:                                        # noqa: BLE001
        ok, detail = False, f'{type(e).__name__}: {e}'
    return {'check': name, 'ok': bool(ok), 'detail': detail.strip()[:400]}


# ---------------------------------------------------------------- checks
def c_refimpl(quick):
    rc, out, _ = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'refimpl'])
    line = [l for l in out.splitlines() if l.startswith('Ran ') or l.strip() == 'OK']
    return rc == 0, ' | '.join(line)


def c_refimpl_syntax(quick):
    rc, out, _ = run([sys.executable, '-c',
                      'import ast,glob,sys;'
                      '[ast.parse(open(f).read()) for f in glob.glob("refimpl/*.py")];'
                      'print("all refimpl modules parse")'])
    return rc == 0, out.strip()


def _batch_verify(script, args, timeout=1800):
    rc, out, _ = run([PY, script] + args, timeout=timeout)
    tail = [l for l in out.splitlines() if l.strip()][-2:]
    ok = rc == 0 and ('FAIL' not in out) and ('failed' not in out.lower() or 'failed=0' in out)
    return ok, ' | '.join(tail)


def c_isef(quick):
    rc, out, _ = run([sys.executable, 'scripts/isef_decrypt.py', 'out/obb/lang_en_us.dat',
                      '--sections'])
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    ok = rc == 0 and '74137 bytes plaintext' in out and any('prm_lexicon' in l for l in lines)
    return ok, ' | '.join(lines[:3])


def c_codec_stages(quick):
    return _batch_verify('scripts/verify_codec.py', [])


def c_codec_e2e(quick):
    return _batch_verify('scripts/compare_spec.py', ['--voice', 'kendra', '--count',
                                                     '4' if quick else '12'])


def c_prosody(quick):
    return _batch_verify('scripts/probe_prosody.py', ['--n', '100' if quick else '600'])


def c_segmentation(quick):
    recs = '0,1' if quick else '0,1,3,10'
    return _batch_verify('scripts/segment_unit.py', ['--verify-engine', '--records', recs])


def c_splice(quick):
    recs = '0,1' if quick else '0,1,3,10'
    return _batch_verify('scripts/segment_unit.py', ['--verify-splice', '--records', recs])


def c_finalize(quick):
    return _batch_verify('scripts/segment_unit.py', ['--verify-finalize'])


def c_g2p(quick):
    rc, out, _ = run([PY, 'scripts/probe_g2p.py', 'hello', 'world', 'kendra'])
    want = ('hh ax l ow1' in out) and ('w er1 l d' in out) and ('eh1 n d r ax' in out)
    return rc == 0 and want, ' | '.join([l for l in out.splitlines() if l.strip()][-3:])


def c_codec_vs_emulator(quick):
    """Byte-compare the clean-room decoder against the emulation decoder for one record."""
    rec = '0'
    a, b = '/tmp/verify_all_spec.wav', '/tmp/verify_all_emu.wav'
    rc1, o1, _ = run([PY, 'scripts/codec_spec.py', '--record', rec, '--rate', '22050', '--out', a])
    rc2, o2, _ = run([PY, 'scripts/decode_unit.py', '--record', rec, '--rate', '22050', '--out', b])
    if rc1 or rc2:
        return False, f'decoder exit {rc1}/{rc2}'
    same = open(a, 'rb').read() == open(b, 'rb').read()
    return same, f'clean-room vs emulated WAV for record {rec}: ' + ('IDENTICAL' if same else 'DIFFER')


def c_pipeline(quick):
    rc, out, _ = run([PY, 'refimpl/tts.py', '--text', 'hello world', '--out',
                      '/tmp/verify_all_tts.wav'], timeout=1800)
    made = os.path.exists('/tmp/verify_all_tts.wav')
    ok = rc == 0 and made and 'committed samples' in out
    tail = [l for l in out.splitlines() if l.strip() and ('committed' in l or 'wav]' in l)][-2:]
    return ok, ' | '.join(tail) if tail else out.strip()[-200:]


CHECKS = [
    ('refimpl-tests', c_refimpl, True),
    ('refimpl-syntax', c_refimpl_syntax, True),
    ('isef-lexicon', c_isef, True),
    ('codec-stages', c_codec_stages, False),
    ('codec-end-to-end', c_codec_e2e, False),
    ('codec-vs-emulator', c_codec_vs_emulator, False),
    ('prosody-costs', c_prosody, False),
    ('segmentation', c_segmentation, False),
    ('splicing', c_splice, False),
    ('finalize', c_finalize, False),
    ('g2p', c_g2p, True),
    ('pipeline', c_pipeline, True),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--json')
    ap.add_argument('--only')
    args = ap.parse_args()

    only = set(args.only.split(',')) if args.only else None
    results = []
    for name, fn, cheap in CHECKS:
        if only and name not in only:
            continue
        if args.quick and not cheap and not only:
            results.append({'check': name, 'ok': None, 'detail': 'skipped (--quick)'})
            continue
        print(f'== {name} ...', flush=True)
        r = check(name, lambda fn=fn: fn(args.quick))
        results.append(r)
        print(f'   {"PASS" if r["ok"] else "FAIL" if r["ok"] is not None else "skip"}: {r["detail"]}',
              flush=True)

    print('\n================ summary ================')
    for r in results:
        state = 'PASS' if r['ok'] else ('skip' if r['ok'] is None else 'FAIL')
        print(f'{state:5s} {r["check"]}')
    failed = [r for r in results if r['ok'] is False]
    ran = [r for r in results if r['ok'] is not None]
    print(f'\n{len(ran) - len(failed)}/{len(ran)} checks passed'
          + ('' if not failed else f' — FAILED: {", ".join(r["check"] for r in failed)}'))
    if args.json:
        open(args.json, 'w').write(json.dumps(results, indent=1))
        print(f'wrote {args.json}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
