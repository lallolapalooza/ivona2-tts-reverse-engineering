#!/usr/bin/env python3
"""isef_decrypt.py -- decrypt and mine IVONA 2 `lang_<code>[_<voice>].dat` ISEF containers.

The IVONA 2 voice engine (`libttsivonavoice.so`) reads a per-language lexicon file
`lang_<language_code>[_<voice_variant>].dat` (see `FUN_00039300`/`FUN_000394b8`,
which call `FUN_000346d4`).  The container is:

    off     size        field
    ------  ----------  ------------------------------------------------------
    0x00    4           magic "ISEF"                                  (FUN_000346d4)
    0x04    4           u32be version (=1)
    0x08    4           u32be timestamp/build id (shared by shipped files)
    0x0C    0x200 (512) RSA-4096 *public-decrypt* block:  c = s^e mod n,  e=65537
                        (n is the constant read at file 0x14BD78; PKCS#1 v1.5
                         type-1 padding -> 00 01 FF..FF 00 || 64-byte session blob)
    0x20C   ..          AES-256-CBC ciphertext, PKCS#7-padded, of the section table

The engine performs, in `FUN_000346d4`:
    FUN_000b2684(&DAT_0015bd78, 0x200, 0)  -> BIGNUM n         (file 0x14BD78)
    FUN_000b2684(&DAT_0015bf78, 4, 0)      -> BIGNUM e = 65537 (file 0x14BF78)
    FUN_000b34fc(0x200, in, out, rsa, 1)   -> dispatches RSA_METHOD +8 == rsa_pub_dec
    FUN_000b8fe0(ctx, &DAT_00192e04, 0, key=blob, iv=blob+0x20)  -> EVP_CipherInit(decrypt)
    FUN_000b950c / FUN_000b974c           -> EVP_DecryptUpdate / EVP_DecryptFinal (PKCS#7)
The EVP_CIPHER at file 0x182E04 has nid 427 = "AES-256-CBC" (OBJ table entry at
file 0x1890B4), block_size 16, key_len 32, iv_len 16.

Because the engine only ever uses the *public* half of the RSA key (and that half is
embedded in the library), the "encryption" is fully reversible with public material
alone -- see report_isef.md.  No private key is required.

Decrypted payload = section table, walked by FUN_000345b0:
    repeat: char name[16] (NUL padded) | u32be size | u8 data[size]

Dependencies: none.  Pure Python 3 (stdlib only).  RSA is a single pow(); AES-256 is
implemented below (FIPS-197).

Usage:
    python3 isef_decrypt.py FILE.dat                       # decrypt -> FILE.dat.dec
    python3 isef_decrypt.py FILE.dat -o out.bin            # explicit output path
    python3 isef_decrypt.py FILE.dat --sections            # list sections
    python3 isef_decrypt.py FILE.dat --dump prm_lexicon    # print a section
    python3 isef_decrypt.py FILE.dat --entries             # print lexicon entries
    python3 isef_decrypt.py FILE.dat --key-from-so X.so    # re-extract n,e from a .so
"""

import argparse
import struct
import sys

# --- RSA-4096 public modulus n, read from `libttsivonavoice.so` file offset 0x14BD78
#     (identical in every shipped build: amy, kendra).  Big-endian, 512 bytes.
RSA_N_HEX = (
    "d4d189a907aec5df6196b126c6a720170c9eec37a06f1c39f2a27b82e5251511"
    "d1d94a464d629d96d0aa910653cfbd95633cc7076a632d3522815fe0c4874a85"
    "d2a6370ed287fbcb7ec09f4f85f0deb46bfb807a7a78de1e17f4c244d1fd846a"
    "dc29a83d19b778e98ba3f503c3e0062dc13e35bf552464458b747df631eff265"
    "60c27cb95f5a894e553e7cdf9a462e9c05b91634e8b1f10e559fd0cf96d1cb49"
    "81495e8c7ffa3c4d95706f30aeb18496fb111d21953b3e8c7c27c5594b331304"
    "e30d1ceb9ea8b946dba3318e62bc68271387c9ee425a05da35b90dbeb0ca7018"
    "8131726001f541fe9094981035b4b627bd46907727cf7d87484b86501b6a16e1"
    "97970e94694d96fefa57fd80874fd042205fa8f1f57dc71f7198e9ff10e1231c"
    "e76c8eec0b32e19585b7063921af6d81673c9494aeae3ba99af8fc03514cdaa8"
    "2a47b7d65cc56c4c8bf63514c9ee9ab43a06bf0a759a7c187e767910f0caa326"
    "c8f8cd4866ded8a3e665f25a285dddc981d176e6f7ccec9b15c886920e5fe91d"
    "c705eb6d83dc25f9df42e04e60d8b1370dfd43047fd4626995fc2e412f993b5f"
    "cb94dd1a3327d83403df3d7a1d0a41473ec543d285d79fe718ae889ded29224f"
    "1a7d2dfae0338ecbc21906630428d1c3a725627322755038a1a3d7f5ce019e07"
    "f9a79bd7cbad3ff43129a52e0397fa6447bc0dfa38d0d55125156998580fd6c3"
)
RSA_E = 65537                     # from file 0x14BF78: 00 01 00 01

ISEF_MAGIC = b"ISEF"
HDR = 0x0C                        # magic + version + timestamp
RSA_BLOCK = 0x200                 # 512-byte wrapped session blob
SESSION_LEN = 0x40                # 64-byte blob = 32-byte AES key || 16-byte IV || 16 spare
AES_KEY_LEN = 32
AES_IV_LEN = 16
AES_BLOCK = 16                    # EVP_CIPHER: block_size=16, key_len=32, iv_len=16


# --------------------------------------------------------------------------- AES
def _build_tables():
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x ^= (x << 1) ^ ((x >> 7) * 0x11B) & 0xFF      # xtime in GF(2^8), poly x^8+x^4+x^3+x+1
        x &= 0xFF
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    sbox = [0] * 256
    for i in range(256):
        inv = 0 if i == 0 else exp[255 - log[i]]
        s = inv
        for _ in range(4):                             # affine transform
            inv = ((inv << 1) | (inv >> 7)) & 0xFF
            s ^= inv
        sbox[i] = s ^ 0x63
    inv_sbox = [0] * 256
    for i, v in enumerate(sbox):
        inv_sbox[v] = i
    mul = {}
    for c in (0x0E, 0x0B, 0x0D, 0x09):
        t = [0] * 256
        for i in range(256):
            t[i] = 0 if i == 0 else exp[(log[i] + log[c]) % 255]
        mul[c] = t
    return sbox, inv_sbox, mul


SBOX, INV_SBOX, MUL = _build_tables()


class AES:
    """Minimal AES-256 decryption primitive (CBC handled by the caller)."""

    def __init__(self, key):
        assert len(key) == AES_KEY_LEN, "AES-256 needs a 32-byte key"
        nk, nr = 8, 14
        w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
        rcon = 1
        for i in range(nk, 4 * (nr + 1)):
            temp = list(w[i - 1])
            if i % nk == 0:
                temp = temp[1:] + temp[:1]                 # RotWord
                temp = [SBOX[b] for b in temp]             # SubWord
                temp[0] ^= rcon
                rcon = ((rcon << 1) ^ ((rcon >> 7) * 0x1B)) & 0xFF
            elif nk > 6 and i % nk == 4:
                temp = [SBOX[b] for b in temp]
            w.append([a ^ b for a, b in zip(w[i - nk], temp)])
        self.rk = [bytes(b for word in w[4 * r:4 * r + 4] for b in word) for r in range(nr + 1)]

    def _add_rk(self, s, rk):
        return bytes(a ^ b for a, b in zip(s, rk))

    def decrypt_block(self, block):
        s = self._add_rk(block, self.rk[14])
        for r in range(13, 0, -1):
            s = bytes(INV_SBOX[b] for b in s)
            # InvShiftRows (state column-major: index = 4*col + row)
            t = bytearray(16)
            for c in range(4):
                for row in range(4):
                    t[4 * ((c + row) % 4) + row] = s[4 * c + row]
            s = bytes(t)
            s = self._add_rk(s, self.rk[r])
            # InvMixColumns
            out = bytearray(16)
            for c in range(4):
                col = s[4 * c:4 * c + 4]
                out[4 * c + 0] = MUL[0x0E][col[0]] ^ MUL[0x0B][col[1]] ^ MUL[0x0D][col[2]] ^ MUL[0x09][col[3]]
                out[4 * c + 1] = MUL[0x09][col[0]] ^ MUL[0x0E][col[1]] ^ MUL[0x0B][col[2]] ^ MUL[0x0D][col[3]]
                out[4 * c + 2] = MUL[0x0D][col[0]] ^ MUL[0x09][col[1]] ^ MUL[0x0E][col[2]] ^ MUL[0x0B][col[3]]
                out[4 * c + 3] = MUL[0x0B][col[0]] ^ MUL[0x0D][col[1]] ^ MUL[0x09][col[2]] ^ MUL[0x0E][col[3]]
            s = bytes(out)
        s = bytes(INV_SBOX[b] for b in s)
        t = bytearray(16)
        for c in range(4):
            for row in range(4):
                t[4 * ((c + row) % 4) + row] = s[4 * c + row]
        return self._add_rk(bytes(t), self.rk[0])


def aes256_cbc_decrypt(key, iv, data):
    assert len(data) % AES_BLOCK == 0
    aes = AES(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), AES_BLOCK):
        blk = data[i:i + AES_BLOCK]
        out += bytes(a ^ b for a, b in zip(aes.decrypt_block(blk), prev))
        prev = blk
    return bytes(out)


def pkcs7_unpad(data, block=AES_BLOCK):
    if not data or len(data) % block:
        raise ValueError("bad padded length")
    n = data[-1]
    if n == 0 or n > block or data[-n:] != bytes([n]) * n:
        raise ValueError("bad PKCS#7 padding (file corrupt / wrong key)")
    return data[:-n]


# ------------------------------------------------------------------ RSA (public)
def rsa_public_recover(block, n, e):
    """PKCS#1 v1.5 type-1 unpad of s^e mod n.  Returns the message bytes."""
    s = int.from_bytes(block, "big")
    m = pow(s, e, n).to_bytes((n.bit_length() + 7) // 8, "big")
    if m[:2] != b"\x00\x01":
        raise ValueError("not a PKCS#1 v1.5 signature block (00 01 expected)")
    sep = m.find(b"\x00", 2)
    if sep < 0:
        raise ValueError("no 0x00 separator in RSA block")
    if any(b != 0xFF for b in m[2:sep]):
        raise ValueError("PKCS#1 v1.5 padding is not all-FF")
    return m[sep + 1:]


def extract_key_from_so(path):
    """Read n (512 B at file offset 0x14BD78) and e (4 B at 0x14BF78) from a
    libttsivonavoice.so, accounting for its ELF program headers."""
    d = open(path, "rb").read()
    assert d[:4] == b"\x7fELF", "not an ELF file"
    e_phoff = struct.unpack_from("<I", d, 0x1C)[0]
    e_phentsize, e_phnum = struct.unpack_from("<HH", d, 0x2A)
    segs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, p_off, p_va, _pa, p_fsz = struct.unpack_from("<IIIII", d, o)
        if t == 1:                      # PT_LOAD
            segs.append((p_off, p_va, p_fsz))

    def v2f(v):
        for off, va, sz in segs:
            if va <= v < va + sz:
                return off + (v - va)
        raise ValueError("vaddr %#x not in any PT_LOAD" % v)

    n = int.from_bytes(d[v2f(0x14BD78):v2f(0x14BD78) + RSA_BLOCK], "big")
    e = int.from_bytes(d[v2f(0x14BF78):v2f(0x14BF78) + 4], "big")
    return n, e


# --------------------------------------------------------------------- container
def isef_decrypt(path, n=None, e=None):
    """Decrypt an ISEF container.  Returns (version, timestamp, session_blob, plaintext)."""
    n = n or int(RSA_N_HEX, 16)
    e = e or RSA_E
    data = open(path, "rb").read()
    if data[:4] != ISEF_MAGIC:
        raise ValueError("bad magic %r (expected ISEF)" % data[:4])
    version = struct.unpack_from(">I", data, 4)[0]
    timestamp = struct.unpack_from(">I", data, 8)[0]
    wrapped = data[HDR:HDR + RSA_BLOCK]
    if len(wrapped) < RSA_BLOCK:
        raise ValueError("file truncated in RSA block")
    blob = rsa_public_recover(wrapped, n, e)
    key, iv = blob[:AES_KEY_LEN], blob[AES_KEY_LEN:AES_KEY_LEN + AES_IV_LEN]
    ct = data[HDR + RSA_BLOCK:]
    pt = pkcs7_unpad(aes256_cbc_decrypt(key, iv, ct))
    return version, timestamp, blob, pt


def parse_sections(pt):
    """Walk the section table: {name[16], u32be size, data[size]} (FUN_000345b0)."""
    out = []
    cur = 0
    while cur + 0x14 <= len(pt):
        name = pt[cur:cur + 16].split(b"\x00", 1)[0]
        if not name:
            break
        size = struct.unpack_from(">I", pt, cur + 16)[0]
        data = pt[cur + 20:cur + 20 + size]
        if len(data) != size:
            raise ValueError("section %r overruns payload" % name)
        out.append((name.decode("ascii", "replace"), size, data))
        cur += 20 + size
    return out


def parse_lexicon(section_bytes):
    """Parse a lexicon section: '#& key=value' directives, then `pattern replacement`
    lines (blank and '#' lines skipped).  Returns (directives, [(pattern, replacement)])."""
    text = section_bytes.decode("utf-8", "replace")
    directives = {}
    entries = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("#&"):
            for kv in s[2:].split():
                if "=" in kv:
                    k, _, v = kv.partition("=")
                    directives[k] = v
        elif not s or s.startswith("#"):
            continue
        else:
            entries.append(line)
    return directives, entries


def split_entry(line):
    """A lexicon line is two whitespace-separated tokens; quoted with backslash escapes."""
    tokens = []
    i, n = 0, len(line)
    while i < n:
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            break
        if line[i] == '"':
            i += 1
            buf = []
            while i < n and line[i] != '"':
                if line[i] == "\\" and i + 1 < n:
                    i += 1
                buf.append(line[i])
                i += 1
            i += 1
            tokens.append("".join(buf))
        else:
            j = i
            while j < n and line[j] not in " \t":
                j += 1
            tokens.append(line[i:j])
            i = j
    return tokens


# --------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="Decrypt IVONA 2 ISEF lang_*.dat containers.")
    ap.add_argument("file", help="lang_*.dat input")
    ap.add_argument("-o", "--out", help="write raw decrypted payload here")
    ap.add_argument("--sections", action="store_true", help="list sections (name/size)")
    ap.add_argument("--dump", metavar="NAME", help="hexdump-free raw print of one section")
    ap.add_argument("--entries", action="store_true", help="print lexicon pattern/replacement pairs")
    ap.add_argument("--key-from-so", metavar="SO", help="re-extract n,e from a libttsivonavoice.so")
    ap.add_argument("--blob", action="store_true", help="print the recovered 64-byte session blob")
    args = ap.parse_args(argv)

    n = e = None
    if args.key_from_so:
        n, e = extract_key_from_so(args.key_from_so)
        print("n = %d bits, e = %d (from %s)" % (n.bit_length(), e, args.key_from_so))

    version, timestamp, blob, pt = isef_decrypt(args.file, n, e)
    print("%s: ISEF v%d, timestamp %#010x, %d bytes plaintext"
          % (args.file, version, timestamp, len(pt)))
    if args.blob:
        print("session blob (%d B): %s" % (len(blob), blob.hex()))

    if args.out:
        open(args.out, "wb").write(pt)
        print("wrote %s" % args.out)

    secs = parse_sections(pt)
    if args.sections or args.dump or args.entries:
        print("sections (%d):" % len(secs))
        for name, size, _ in secs:
            print("  %-20s %8d bytes" % (name, size))
    if args.dump:
        for name, size, data in secs:
            if name == args.dump:
                sys.stdout.buffer.write(data)
                break
        else:
            print("no such section: %s" % args.dump)
    if args.entries:
        for name, size, data in secs:
            if name == "prm_lex_list":            # the file list, not a lexicon
                continue
            directives, entries = parse_lexicon(data)
            print("--- %s: %d entries, directives=%s" % (name, len(entries), directives))
            for line in entries:
                t = split_entry(line)
                if len(t) >= 2:
                    print("  %s\t=> %s" % (t[0], t[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
