"""Speech-mark records: 20-byte layout, type table, ownership flags, bitmask.

Documented in ``report_ttsivona.md`` §10, ``report_engine_synth.md`` §4.2/§4.3
and ``report_engine_api.md`` §6.3.

Record layout produced by the voice engine (stride ``0x14`` = 20 bytes)::

    +0x00 int   type          (0..4)
    +0x04 char* name (NUL-terminated; 0 -> Java null)
    +0x08 int   startTextOffset
    +0x0c int   endTextOffset
    +0x10 int   sampleOffset   (added to the running sample counter)

Engine ``type`` -> Android ``SpeechMark.TYPE_*`` constant (bridge table
``libttsivona.so`` file ``0x70ea0``; strings at ``0x6cd37``/``0x6cd44``/
``0x6cd4e``/``0x6cd5c``/``0x6cd66``):

    ====== ================= ============================
    type   engine meaning    Android constant
    ====== ================= ============================
    0      phoneme (unused)  TYPE_PHONEME
    1      word/token        TYPE_WORD
    2      sentence          TYPE_SENTENCE
    3      SSML <mark>       TYPE_SSML
    4      viseme            TYPE_VISEME
    ====== ================= ============================

The requested-type bitmask comes from the Java param
``com.ivona.tts.oem.GENERATE_MARKS``; bit ``N`` enables type ``N``
(``IVONA2_REVERSE_ENGINEERING.md`` §6, ``report_engine_api.md`` §6.3).

The ownership table ``{0, 1, 1, 0, 1}`` for types 0..4 lives at file
``0x14bfc8`` of ``libttsivonavoice.so`` as a u32 array
(``report_engine_synth.md`` §4.2): value 1 (types 1, 2, 4) means the name
pointer is used as-is / never freed (NULL, static ``"sil"``, static viseme
class), value 0 (types 0, 3) means a heap copy that ``tts_wave_delete`` frees.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Callable, Iterator, Optional, Tuple

MARK_RECORD_SIZE = 0x14  # report_ttsivona.md §10
# type (u32), name pointer (u32), start (s32), end (s32), sample (s32)
MARK_RECORD_STRUCT = "<IIiii"

#: file offsets of the bridge's mark-type static-field name strings.
TYPE_NAME_OFFSETS = (0x6CD37, 0x6CD44, 0x6CD4E, 0x6CD5C, 0x6CD66)

#: file offset of the u32 ownership table in ``libttsivonavoice.so``.
OWNERSHIP_TABLE_OFFSET = 0x14BFC8

#: engine type -> (engine short name, Android SpeechMark constant).
MARK_TYPES = {
    0: ("phoneme", "TYPE_PHONEME"),
    1: ("word", "TYPE_WORD"),
    2: ("sentence", "TYPE_SENTENCE"),
    3: ("ssml", "TYPE_SSML"),
    4: ("viseme", "TYPE_VISEME"),
}


class MarkError(Exception):
    """Raised for malformed mark data."""


@dataclass(frozen=True)
class Mark:
    type: int
    name_ptr: int
    start_text_offset: int
    end_text_offset: int
    sample_offset: int
    name: Optional[str] = None

    @property
    def android_constant(self) -> str:
        if self.type not in MARK_TYPES:
            raise MarkError(f"unknown mark type {self.type}")
        return MARK_TYPES[self.type][1]


def parse_mark(
    data: bytes,
    offset: int = 0,
    resolve_name: Optional[Callable[[int], Optional[str]]] = None,
) -> Mark:
    """Parse one 20-byte mark record.

    ``resolve_name`` (optional) maps ``name_ptr`` to a string; when absent the
    parsed :class:`Mark` keeps ``name=None`` (the pointer itself is retained in
    ``name_ptr``).
    """
    if offset + MARK_RECORD_SIZE > len(data):
        raise MarkError("buffer too small for a 20-byte mark record")
    mtype, name_ptr, start, end, sample = struct.unpack_from(
        MARK_RECORD_STRUCT, data, offset
    )
    name = resolve_name(name_ptr) if (resolve_name and name_ptr) else None
    return Mark(mtype, name_ptr, start, end, sample, name)


def iter_marks(
    data: bytes,
    count: int,
    resolve_name: Optional[Callable[[int], Optional[str]]] = None,
) -> Iterator[Mark]:
    """Iterate ``count`` packed 20-byte records."""
    for i in range(count):
        yield parse_mark(data, i * MARK_RECORD_SIZE, resolve_name)


def mark_enabled(mask: int, mtype: int) -> bool:
    """``bit N`` of the GENERATE_MARKS mask enables type ``N``."""
    return bool(mask & (1 << mtype))


def enabled_types(mask: int) -> Tuple[int, ...]:
    return tuple(t for t in MARK_TYPES if mark_enabled(mask, t))


def mask_for_types(types) -> int:
    mask = 0
    for t in types:
        mask |= 1 << t
    return mask


def read_ownership_table(voice_lib_bytes: bytes, offset: int = OWNERSHIP_TABLE_OFFSET) -> Tuple[int, ...]:
    """Read the 5-dword name-ownership table from ``libttsivonavoice.so``."""
    return tuple(
        struct.unpack_from("<5I", voice_lib_bytes, offset)
    )


def read_type_names(bridge_bytes: bytes) -> Tuple[str, ...]:
    """Read the 5 ``TYPE_*`` name strings from ``libttsivona.so``."""
    names = []
    for off in TYPE_NAME_OFFSETS:
        end = bridge_bytes.index(b"\x00", off)
        names.append(bridge_bytes[off:end].decode("ascii"))
    return tuple(names)


def owns_name(mtype: int, ownership) -> bool:
    """True when the engine aliases (never frees) the name pointer for ``mtype``
    (``report_engine_synth.md`` §4.2)."""
    if mtype < 0 or mtype >= len(ownership):
        raise MarkError(f"ownership flag undefined for type {mtype}")
    return ownership[mtype] != 0
