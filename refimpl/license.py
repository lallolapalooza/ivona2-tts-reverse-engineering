"""Embedded Certificate of Authenticity: XOR de-obfuscation + attribute parse.

From ``report_ttsivona.md`` §8 / ``IVONA2_REVERSE_ENGINEERING.md`` §4.4, the
certificate is stored XOR-obfuscated in ``libttsivona.so``.  With ``d`` the raw
``.rodata`` bytes and the three vaddrs (equal to file offsets in ``.rodata``)::

    KEY, D, D2 = 0x6d070, 0x6d079, 0x6d07d
    length = 0
    for i in range(4):
        length |= ((d[KEY+(i+5)%9] ^ d[KEY+i%9] ^ d[D+i]) & 0xff) << (8*i)   # == 1798
    out = bytes(d[D2+i] ^ d[KEY+(i+4)%9] for i in range(length))

The decoded text is the certificate; the reference dump lives at
``out/certs/ivona_certificate_decoded.txt``.  The signature block is 14 lines /
1040 hex chars = 520 bytes, i.e. RSA-4096 (``IVONA2_REVERSE_ENGINEERING.md`` §4.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

#: vaddrs == file offsets in ``.rodata`` (report_ttsivona.md §8).
KEY_OFFSET = 0x6D070
D_OFFSET = 0x6D079
D2_OFFSET = 0x6D07D

#: Decoded length asserted by the report (== 1798).
EXPECTED_LENGTH = 1798

SIGNATURE_BEGIN = "-----BEGIN SIGNATURE-----"
SIGNATURE_END = "-----END SIGNATURE-----"

#: Attribute keys observed in the decoded certificate.
KNOWN_ATTRIBUTES = (
    "Product",
    "Licensee",
    "Licensor",
    "Certificate-ID",
    "Num-threads",
    "Thread-speed",
    "Expiration-date",
    "Voices",
    "Extension-SSML",
)

UNLIMITED = "UNLIMITED"
NEVER = "NEVER"


class LicenseError(Exception):
    """Raised for malformed certificate data."""


def decode_certificate(
    data: bytes,
    key_offset: int = KEY_OFFSET,
    d_offset: int = D_OFFSET,
    d2_offset: int = D2_OFFSET,
) -> bytes:
    """De-XOR the embedded certificate from the raw ``libttsivona.so`` bytes."""
    length = 0
    for i in range(4):
        length |= (
            (data[key_offset + (i + 5) % 9] ^ data[key_offset + i % 9] ^ data[d_offset + i])
            & 0xFF
        ) << (8 * i)
    if d2_offset + length > len(data):
        raise LicenseError("certificate extends past end of file")
    return bytes(
        data[d2_offset + i] ^ data[key_offset + (i + 4) % 9] for i in range(length)
    )


@dataclass
class Certificate:
    attributes: Dict[str, str] = field(default_factory=dict)
    signature_hex: str = ""
    comments: List[str] = field(default_factory=list)
    raw: bytes = b""

    # -- semantic helpers --------------------------------------------------
    @property
    def signature_bytes(self) -> bytes:
        return bytes.fromhex(self.signature_hex)

    @property
    def thread_speed_unlimited(self) -> bool:
        return self.attributes.get("Thread-speed", "").strip().upper() == UNLIMITED

    @property
    def num_threads_unlimited(self) -> bool:
        return self.attributes.get("Num-threads", "").strip().upper() == UNLIMITED

    @property
    def expiration_never(self) -> bool:
        return self.attributes.get("Expiration-date", "").strip().upper() == NEVER

    @property
    def voices_all(self) -> bool:
        return self.attributes.get("Voices", "").strip().upper() == "ALL"

    @property
    def ssml_extension(self) -> bool:
        return self.attributes.get("Extension-SSML", "").strip().upper() == "TRUE"


def parse_certificate(text: str) -> Certificate:
    """Parse a decoded certificate into attributes + signature block.

    Lines beginning with ``#`` are comments; attribute lines are
    ``Key: value``; the signature block is delimited by ``-----BEGIN/END
    SIGNATURE-----``.  This mirrors the declaration block of the decoded file
    (``out/certs/ivona_certificate_decoded.txt``).
    """
    cert = Certificate()
    in_sig = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if stripped == SIGNATURE_BEGIN:
            in_sig = True
            continue
        if stripped == SIGNATURE_END:
            in_sig = False
            continue
        if in_sig:
            cert.signature_hex += stripped
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            cert.comments.append(stripped)
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            cert.attributes[key.strip()] = value.strip()
            continue
        raise LicenseError(f"unparsable certificate line: {raw_line!r}")
    return cert


def decode_and_parse(path: str) -> Certificate:
    """Read ``libttsivona.so`` and return the parsed certificate."""
    with open(path, "rb") as fh:
        data = fh.read()
    text = decode_certificate(data).decode("utf-8", "replace")
    cert = parse_certificate(text)
    cert.raw = text.encode("utf-8")
    return cert


def parse_decoded_file(path: str) -> Certificate:
    """Parse an already-decoded certificate text file (no XOR step)."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    cert = parse_certificate(text)
    cert.raw = text.encode("utf-8")
    return cert
