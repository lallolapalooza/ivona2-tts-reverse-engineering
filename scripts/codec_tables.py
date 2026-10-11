#!/usr/bin/env python3
"""codec_tables.py -- one-time extraction of the codec's static tables from the
original ARM library into a portable data file under `out/codec/`.

The decoder (`scripts/codec_spec.py`) never touches the .so: it loads the file
produced here plus the manifest, and reads static data by *ELF virtual address*
(the same addresses the code used, since the library is mapped at its link-time
vaddrs).  Re-running this yields byte-identical output.

The library has two PT_LOAD segments; only two windows are needed:

  W0  0x144000 .. 0x17e558   .rodata (all codebooks, windows, constants)
  W1  0x17f678 .. 0x194df8   .data.rel.ro.local + .data + .bss (pointer/struct
                             tables with absolute addresses; relocation base is 0,
                             so the values equal the link-time vaddrs)

Outputs
  out/codec/tables.bin    concatenation of the windows
  out/codec/tables.json   {windows:[{base,size,off}], sha256, ...}

Usage:  ~/venvs/re/bin/python scripts/codec_tables.py
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'emu'))

WINDOWS = [(0x144000, 0x17E558),      # .rodata
           (0x17F678, 0x194DF8)]      # .data.rel.ro.local/.data/.bss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lib', default=os.path.join(ROOT, 'out', 'libs', 'kendra',
                                                  'libttsivonavoice.so'))
    ap.add_argument('--out-dir', default=os.path.join(ROOT, 'out', 'codec'))
    args = ap.parse_args()

    from armemu import ArmLib
    lib = ArmLib(args.lib, verbosity=0)
    os.makedirs(args.out_dir, exist_ok=True)
    blob = bytearray()
    wins = []
    for base, end in WINDOWS:
        data = lib.rd(base, end - base)
        wins.append({'base': base, 'size': end - base, 'off': len(blob)})
        blob += data
    path = os.path.join(args.out_dir, 'tables.bin')
    with open(path, 'wb') as fh:
        fh.write(blob)
    man = {'lib': os.path.relpath(args.lib, ROOT), 'windows': wins,
           'size': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}
    with open(os.path.join(args.out_dir, 'tables.json'), 'w') as fh:
        json.dump(man, fh, indent=1)
    print('wrote %s (%d bytes)' % (path, len(blob)))
    for w in wins:
        print('  window base=%#x size=%#x off=%#x' % (w['base'], w['size'], w['off']))
    print('sha256', man['sha256'])


if __name__ == '__main__':
    main()
