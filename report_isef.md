# `ISEF` — the `lang_<code>[_<voice>].dat` lexicon container (solved)

Status: **broken and reproduced in pure Python** — `scripts/isef_decrypt.py` decrypts both shipped
files; verified by me on `out/obb/lang_en_us.dat` and `lang_en_gb.dat` (see §4).
Addresses below are *file offsets* of `libttsivonavoice.so` unless written as `FUN_…`, which are
Ghidra addresses of `out/ghidra_dump/libttsivonavoice.c` (Ghidra addr = ELF vaddr + 0x10000).

## 1. Container layout

| off | size | field |
|---|---|---|
| `0x00` | 4 | magic `"ISEF"` |
| `0x04` | 4 | `u32be` version — always **1** |
| `0x08` | 4 | `u32be` build id / timestamp — **`0x50992bcc`** in both shipped files (= 2012-11-07) |
| `0x0C` | 512 | RSA-4096 block: `c = s^e mod n` with `e = 65537`, PKCS#1 v1.5 **type 1** padding (`00 01 FF…FF 00 ‖ 64-byte blob`) |
| `0x20C` | … | AES-256-CBC ciphertext of the section table, PKCS#7-padded (74 144 B = 4 634 blocks) |

Sizes fit exactly: `74 656 = 512 + 74 144`, `74 144 = 16 × 4 634`, no trailing partial block.

## 2. Why it is reversible with public material only

The engine embeds only the **public** half: modulus `n` at file **`0x14bd78`** (512 bytes, big-endian)
and exponent `e = 65537` at file **`0x14bf78`**. The pipeline in `FUN_000346d4` is:

```
FUN_000b2684(&DAT_0015bd78, 0x200, 0)      ; BN_bin2bn(n)     — file 0x14bd78
FUN_000b2684(&DAT_0015bf78, 4, 0)          ; BN_bin2bn(e)     — file 0x14bf78
FUN_000b34fc(0x200, in, out, rsa, 1)       ; RSA primitive dispatch -> RSA_METHOD+8 == pub_dec
FUN_000b8fe0(ctx, &DAT_00192e04, 0, key=blob, iv=blob+0x20)   ; EVP_CipherInit(DECRYPT)
FUN_000b950c / FUN_000b974c                ; EVP_DecryptUpdate / EVP_DecryptFinal (PKCS#7)
```

The recovered 64-byte blob is used directly as **AES-256 key (32 B) ‖ IV (16 B)** (runner-up 16
bytes unused). The `EVP_CIPHER` object at file `0x182e04` has OpenSSL `nid 427` = **AES-256-CBC**
(OBJ entry at file `0x1890b4`, `block_size 16`, `key_len 32`, `iv_len 16`). So the file is
*signed/encrypted by the vendor with the private key* and *recovered by the engine with the public
key* — anyone holding the library can do it.

The library embeds a full OpenSSL subset (RSA/AES/CBC/SHA1/EVP/BIO — e.g. `AES` strings at file
`0x165618…`, `RSA` at `0x162a30…`, BIO read `FUN_000e5f00`); there is **no zlib**.

## 3. Decrypted payload = section table

Walked by `FUN_000345b0` (callers `FUN_00039300` / `FUN_000394b8`, i.e. the "open lang file" paths
reached from `tts_pls_load` / `tts_dict_load`):

```
repeat until EOF:
    char  name[16]      ; NUL-padded
    u32be size
    u8    data[size]
```

Each section is a **PCRE rewrite-rule dictionary**: UTF-8 text with a `#& encoding=UTF-8` directive
line, comment lines and `"pattern" "replacement"` rules (see `report_engine_synth.md` §2.4).

## 4. Verified output (my run, `python3 scripts/isef_decrypt.py out/obb/lang_en_us.dat --sections`)

```
ISEF v1, timestamp 0x50992bcc, 74137 bytes plaintext
sections (4):
  prm_lexicon             72722 bytes    660 rules
  prm_pre_lexicon           624 bytes
  prm_post_lexicon          666 bytes
  prm_lex_list               45 bytes    -> "prm_pre_lexicon\nprm_lexicon\nprm_post_lexicon"
```

`lang_en_gb.dat` decrypts to the same section names/sizes (its own 660-rule lexicon — en_GB
spelling/pronunciation rules differ in content). Plaintexts saved as
`out/obb/lang_en_us.dec.bin` / `lang_en_gb.dec.bin` (raw section table) and
`out/obb/lang_en_us.isef.dec`. Decrypted text begins:

```
prm_lexicon … #& encoding=UTF-8
#       The IVONA Text-To-Speech exceptions dictionary
#          -----------English language------------
#      Copyright (C) 2003-2011 IVONA Software Sp. z o.o.
# Lexicon version: $Rev$
# Lexicon langs: en_us en_gb en_gb_wls en_au
"(?<=^|[[:punct:][:space:]])(?-i)([A-Z])([0-9]) ([0-9])([A-Z])([A-Z])(?=[[:punct:][:space:]]|$)" "\1 \2 \3 \4 \5"
…
```

## 5. Script API

```
scripts/isef_decrypt.py FILE.dat [--sections] [--entries] [--dump SECTION] [-o OUT]
                                    [--key-from-so LIBTTSIVONAVOICE.SO]
```

Pure-stdlib Python 3 (RSA = one `pow()`; AES-256 implemented inline). `--key-from-so` re-extracts
`n`/`e` from the library, so the constants are not hard-coded to one build.

## 6. Consequences for reimplementation

* The lexicon/dictionary layer is now fully readable: a reimplementation can consume the shipped
  `lang_*.dat` files directly (RSA public-recover + AES-256-CBC + section walk), no secret required.
* The same OpenSSL crypto stack is present in the engine for the vox payload — the `ISEF` scheme is
  the template to test against the OBB "gap" payload (still open: see
  `report_gap_codec.md` / round-2 notes).
* Nothing in the Java layer touches these files; the flow is `patch.199.*.obb` (ZIP) → `lang_*.dat`
  written next to the OBB by `libtiver.so` → engine `tts_pls_load`/`tts_dict_load` open it by
  `lang_<code>_<voice>.dat` (fallback `lang_<code>.dat`).

## 7. Not determined

* the second 16 bytes of the recovered 64-byte blob (unused by the CBC init — possibly an HMAC key
  or build metadata);
* whether `Expiration`-style checks apply to this container (the certificate subsystem is separate,
  §4.4 of the entry doc);
* the exact PCRE dialect flags used at load time (rules themselves are plain text now).
