#!/usr/bin/env python3
"""Map line numbers in a Ghidra dump to enclosing function headers.

Usage: fn_at.py <dump.c> <line> [<line> ...]
       fn_at.py <dump.c> --name <substr>   # list headers matching substr
       fn_at.py <dump.c> --first <line> --last <line>  # print header before line and next header
"""
import re, sys

def load_headers(path):
    hdrs = []
    with open(path, errors='replace') as f:
        for i, line in enumerate(f, 1):
            m = re.match(r'^// ----- ([0-9a-f]+) : (.+?) -----', line)
            if m:
                hdrs.append((i, int(m.group(1), 16), m.group(2)))
    return hdrs

def main():
    path = sys.argv[1]
    hdrs = load_headers(path)
    args = sys.argv[2:]
    if args and args[0] == '--name':
        pat = args[1].lower()
        for ln, addr, name in hdrs:
            if pat in name.lower():
                print(f'{ln}\t{addr:08x}\t{name}')
        return
    if args and args[0] == '--range':
        want = int(args[1])
        idx = None
        for k, (ln, addr, name) in enumerate(hdrs):
            if ln <= want:
                idx = k
            else:
                break
        if idx is None:
            print('before first header'); return
        ln, addr, name = hdrs[idx]
        nxt = hdrs[idx+1] if idx+1 < len(hdrs) else (None, None, None)
        print(f'FUNC {name} header={ln} addr=0x{addr:x} next={nxt[2]}@{nxt[0]}')
        return
    for a in args:
        want = int(a)
        idx = None
        for k, (ln, addr, name) in enumerate(hdrs):
            if ln <= want:
                idx = k
            else:
                break
        if idx is None:
            print(f'{want}: before first header')
        else:
            ln, addr, name = hdrs[idx]
            print(f'{want}: {name} (header line {ln}, addr 0x{addr:x})')

if __name__ == '__main__':
    main()
