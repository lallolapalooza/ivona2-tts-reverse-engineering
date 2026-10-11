"""CDXV voice-data container (``main.<N>.<pkg>.obb``) reader.

Pure-stdlib reimplementation of the container layout documented in
``report_obb_format.md`` (all citations below are to that report unless stated
otherwise) and summarised in ``IVONA2_REVERSE_ENGINEERING.md`` §5.1.

Top-level map of ``main.obb`` (report_obb_format.md §1)::

    0x00000000  header, 0x68 (104) bytes
    0x00000068  index: N x 8 bytes (u32 file_offset, u32 length)
    0x00341FE0  section A  diphone table         (20-byte records)
    0x00349CF8  section B  unit-id lists         (u32 array)
    0x004E27F8  section C  unit records          (36 bytes/unit)
    0x0138B598  section D  word/chunk blocks     (variable byte pool)
    0x0182E198  section E  phoneme-name table    (32-byte records)
    0x0182E8D8  high-entropy payload ("gap")
    ...         unit records region (index targets) to EOF

The seven ``(offset, length)`` header pairs at ``+0x30`` are, in order
(report_obb_format.md §2): index, payload-region (length 0), A, B, C, D, E.
Note the naming difference between reports called out in
``IVONA2_REVERSE_ENGINEERING.md`` §5.1: this module uses the
``report_obb_format.md`` letters A-E.

Everything here is little-endian (report_obb_format.md §15).
"""

from __future__ import annotations

import mmap
import os
import struct
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

MAGIC = b"CDXV"                 # report_obb_format.md §2 (u32 LE 0x56584443)
HEADER_SIZE = 0x68              # report_obb_format.md §2
SAMPLE_RATE_OFF = 0x24          # report_obb_format.md §2
FORMAT_ID_OFF = 0x28            # report_obb_format.md §2
CHECKSUM_OFF = 0x2C             # report_obb_format.md §2
NAME_OFF, NAME_LEN = 0x04, 32   # report_obb_format.md §2
PAIRS_OFF = 0x30                # report_obb_format.md §2
N_PAIRS = 7                     # report_obb_format.md §2

SECTION_A_REC = 20              # report_obb_format.md §4
SECTION_C_REC = 36              # report_obb_format.md §6
SECTION_E_REC = 32              # report_obb_format.md §8

# Accepted format ids per the plugin validator documented in
# IVONA2_REVERSE_ENGINEERING.md §4.5 ("accepted values 2, 8, 12, 14").
ACCEPTED_FORMAT_IDS = (2, 8, 12, 14)


class CDXVError(Exception):
    """Raised for malformed containers / out-of-range reads."""


@dataclass(frozen=True)
class Header:
    magic: bytes
    name: str               # NUL-padded char[32] @0x04
    sample_rate: int        # u32 @0x24
    format_id: int          # u32 @0x28, dispatch value
    checksum: int           # u32 @0x2C
    pairs: Tuple[Tuple[int, int], ...]  # 7 x (offset, length) @0x30..0x64

    @property
    def index_pair(self) -> Tuple[int, int]:
        return self.pairs[0]

    @property
    def payload_pair(self) -> Tuple[int, int]:
        return self.pairs[1]

    def section_pair(self, letter: str) -> Tuple[int, int]:
        idx = {"A": 2, "B": 3, "C": 4, "D": 5, "E": 6}[letter]
        return self.pairs[idx]


@dataclass(frozen=True)
class IndexEntry:
    offset: int
    length: int

    @property
    def is_null(self) -> bool:
        return self.offset == 0 and self.length == 0


@dataclass(frozen=True)
class Diphone:
    name: str
    start: int      # index into section B
    count: int      # number of B entries (unit numbers)


@dataclass(frozen=True)
class UnitRecord:
    """Tail unit record, ``2N + 12`` bytes (report_obb_format.md §9)::

        u16  N            // count of ramp values
        u16  ramp[N]      // non-decreasing positions
        u16  Y            // unresolved scalar
        u32  gap_offset   // absolute offset into the gap
        u32  gap_length   // byte length of the window
    """

    N: int
    ramp: Tuple[int, ...]
    Y: int
    gap_offset: int
    gap_length: int

    @property
    def size(self) -> int:
        return 2 * self.N + 12

    @property
    def ramp_monotone(self) -> bool:
        return all(self.ramp[i] <= self.ramp[i + 1] for i in range(len(self.ramp) - 1))


@dataclass
class Validation:
    """Aggregated invariant-check results (report_obb_format.md §4-§9, §12)."""

    n_entries: int = 0
    n_null: int = 0
    first_record_offset: int = 0
    last_record_end: int = 0
    file_size: int = 0
    contiguity_anomalies: List[int] = field(default_factory=list)
    section_c_len_ok: bool = False
    section_c_expected_len: int = 0
    section_c_actual_len: int = 0
    diphone_count: int = 0
    diphone_sum_count: int = 0
    section_b_len_u32: int = 0
    diphone_sum_matches_b: bool = False
    diphone_chain_anomalies: int = 0
    diphone_names_without_nul: int = 0
    b_is_permutation: bool = False
    b_duplicates: int = 0
    b_invalid_ids: int = 0
    missing_ids: int = 0
    record_size_violations: int = 0
    ramp_violations: int = 0
    window_outside_gap: int = 0
    max_window_end: int = 0
    min_gap_offset: int = 0
    sum_gap_lengths: int = 0
    gap_start: int = 0
    gap_end: int = 0
    distinct_gap_offsets: int = 0
    phoneme_count: int = 0
    N_range: Tuple[int, int] = (0, 0)
    sum_N: int = 0

    @property
    def ok(self) -> bool:
        return (
            not self.contiguity_anomalies
            and self.section_c_len_ok
            and self.diphone_sum_matches_b
            and self.diphone_chain_anomalies == 0
            and self.diphone_names_without_nul == 0
            and self.b_is_permutation
            and self.record_size_violations == 0
            and self.ramp_violations == 0
            and self.window_outside_gap == 0
            and self.last_record_end == self.file_size
        )


class OBBReader:
    """Read-only random-access reader for a ``main.<N>.<pkg>.obb``."""

    def __init__(self, path: str):
        self.path = path
        self.file_size = os.path.getsize(path)
        if self.file_size < HEADER_SIZE:
            raise CDXVError("file smaller than the 0x68-byte header")
        self._fh = open(path, "rb")
        self._mm = mmap.mmap(self._fh.fileno(), 0, access=mmap.ACCESS_READ)
        self.header = self._parse_header()
        self.index = self._parse_index()

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self._mm.close()
        self._fh.close()

    def __enter__(self) -> "OBBReader":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- low-level access --------------------------------------------------
    def read(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 0 or offset + length > self.file_size:
            raise CDXVError(
                f"read out of range: offset={offset} length={length} "
                f"file_size={self.file_size}"
            )
        return self._mm[offset:offset + length]

    # -- header / index ----------------------------------------------------
    def _parse_header(self) -> Header:
        hdr = self.read(0, HEADER_SIZE)
        magic = hdr[0:4]
        if magic != MAGIC:
            raise CDXVError(f"bad magic {magic!r}, expected {MAGIC!r}")
        name = hdr[NAME_OFF:NAME_OFF + NAME_LEN].split(b"\x00", 1)[0].decode(
            "ascii", "replace"
        )
        sample_rate = struct.unpack_from("<I", hdr, SAMPLE_RATE_OFF)[0]
        format_id = struct.unpack_from("<I", hdr, FORMAT_ID_OFF)[0]
        checksum = struct.unpack_from("<I", hdr, CHECKSUM_OFF)[0]
        pairs = tuple(
            struct.unpack_from("<II", hdr, PAIRS_OFF + 8 * i) for i in range(N_PAIRS)
        )
        return Header(magic, name, sample_rate, format_id, checksum, pairs)

    def _parse_index(self) -> List[IndexEntry]:
        off, length = self.header.index_pair
        if off != HEADER_SIZE:
            raise CDXVError(f"index does not start at 0x68 (got {off:#x})")
        if length % 8 != 0:
            raise CDXVError("index length is not a multiple of 8")
        raw = self.read(off, length)
        n = length // 8
        flat = struct.unpack(f"<{2 * n}I", raw)
        return [IndexEntry(flat[2 * i], flat[2 * i + 1]) for i in range(n)]

    @property
    def n_entries(self) -> int:
        return len(self.index)

    @property
    def n_null(self) -> int:
        return sum(1 for e in self.index if e.is_null)

    # -- sections ----------------------------------------------------------
    def _section_bytes(self, letter: str) -> bytes:
        off, length = self.header.section_pair(letter)
        return self.read(off, length)

    def diphones(self) -> List[Diphone]:
        """Section A, 20-byte records ``char name[12]; u32 start; u32 count``.

        (report_obb_format.md §4)
        """
        raw = self._section_bytes("A")
        if len(raw) % SECTION_A_REC != 0:
            raise CDXVError("section A length is not a multiple of 20")
        out: List[Diphone] = []
        for i in range(len(raw) // SECTION_A_REC):
            rec = raw[i * SECTION_A_REC:(i + 1) * SECTION_A_REC]
            name = rec[0:12].split(b"\x00", 1)[0].decode("ascii", "replace")
            start, count = struct.unpack_from("<II", rec, 12)
            out.append(Diphone(name, start, count))
        return out

    def diphone_units(self) -> List[int]:
        """Section B as a flat u32 list (report_obb_format.md §5)."""
        raw = self._section_bytes("B")
        if len(raw) % 4 != 0:
            raise CDXVError("section B length is not a multiple of 4")
        return list(struct.unpack(f"<{len(raw) // 4}I", raw))

    def c_record(self, i: int) -> bytes:
        """Raw 36-byte section-C record for index entry *i* (report_obb_format.md §6)."""
        off, _ = self.header.section_pair("C")
        return self.read(off + i * SECTION_C_REC, SECTION_C_REC)

    def d_pool(self) -> bytes:
        """Section D byte pool (loaded whole; report_obb_format.md §7)."""
        return self._section_bytes("D")

    def phonemes(self) -> List[str]:
        """Section E, 32-byte NUL-padded names; id = record index (report_obb_format.md §8)."""
        raw = self._section_bytes("E")
        if len(raw) % SECTION_E_REC != 0:
            raise CDXVError("section E length is not a multiple of 32")
        return [
            raw[i * SECTION_E_REC:(i + 1) * SECTION_E_REC]
            .split(b"\x00", 1)[0]
            .decode("ascii", "replace")
            for i in range(len(raw) // SECTION_E_REC)
        ]

    def gap_bounds(self) -> Tuple[int, int]:
        """``(start, end)`` of the high-entropy payload region (report_obb_format.md §8).

        The start is header pair @0x38 (== end of section E); the end is the first
        index-record offset (== first non-null index entry offset).
        """
        start = self.header.payload_pair[0]
        end = next(
            (e.offset for e in self.index if not e.is_null), None
        )
        if end is None:
            raise CDXVError("no non-null index entries; cannot determine gap end")
        return start, end

    # -- unit records ------------------------------------------------------
    def parse_unit_record(self, offset: int, length: int) -> UnitRecord:
        """Parse one tail record of exactly ``2N + 12`` bytes (report_obb_format.md §9)."""
        if length < 12:
            raise CDXVError(f"record too short: {length}")
        raw = self.read(offset, length)
        (n,) = struct.unpack_from("<H", raw, 0)
        expect = 2 * n + 12
        if length != expect:
            raise CDXVError(
                f"record size violation at {offset:#x}: len={length} != 2N+12={expect}"
            )
        ramp = struct.unpack_from(f"<{n}H", raw, 2) if n else ()
        y = struct.unpack_from("<H", raw, 2 + 2 * n)[0]
        gap_off, gap_len = struct.unpack_from("<II", raw, 4 + 2 * n)
        return UnitRecord(n, ramp, y, gap_off, gap_len)

    def unit_records(self) -> Iterator[Optional[UnitRecord]]:
        """Yield a record per index entry (``None`` for ``(0,0)`` null slots)."""
        for entry in self.index:
            if entry.is_null:
                yield None
            else:
                yield self.parse_unit_record(entry.offset, entry.length)

    # -- validation --------------------------------------------------------
    def validate(self, check_b_permutation: bool = True) -> Validation:
        """Check every invariant asserted in report_obb_format.md.

        O(1) passes over the index and records; the B-permutation test allocates
        a set of the ~420k non-null entry numbers (may be skipped).
        """
        v = Validation()
        v.file_size = self.file_size
        idx = self.index
        gap_start, gap_end = self.gap_bounds()
        v.gap_start, v.gap_end = gap_start, gap_end

        # Index contiguity (report_obb_format.md §3): non-null records must tile
        # [first_offset, EOF) with offset[i+1] == offset[i] + length[i].
        expected = None
        first = None
        last = None
        n_null = 0
        distinct_gap = set()
        for entry in idx:
            if entry.is_null:
                n_null += 1
                continue
            if first is None:
                first = entry.offset
            if expected is not None and entry.offset != expected:
                v.contiguity_anomalies.append(entry.offset)
            expected = entry.offset + entry.length
            last = expected
        v.n_entries = len(idx)
        v.n_null = n_null
        v.first_record_offset = first or 0
        v.last_record_end = last or 0

        # Section C positional length (report_obb_format.md §6).
        c_off, c_len = self.header.section_pair("C")
        v.section_c_actual_len = c_len
        v.section_c_expected_len = SECTION_C_REC * len(idx)
        v.section_c_len_ok = c_len == v.section_c_expected_len

        # Section A chain + B equivalence to len(B)/4 (report_obb_format.md §4).
        diphones = self.diphones()
        v.diphone_count = len(diphones)
        b = self.diphone_units()
        v.section_b_len_u32 = len(b)
        total = 0
        for i, d in enumerate(diphones):
            total += d.count
            if i + 1 < len(diphones):
                nxt = diphones[i + 1]
                if nxt.start != d.start + d.count:
                    v.diphone_chain_anomalies += 1
        v.diphone_sum_count = total
        v.diphone_sum_matches_b = total == len(b)

        # B is a permutation of the non-null index-entry numbers
        # (report_obb_format.md §5).
        if check_b_permutation:
            valid_ids = {i for i, e in enumerate(idx) if not e.is_null}
            seen = set()
            dups = 0
            invalid = 0
            for x in b:
                if x in seen:
                    dups += 1
                elif x not in valid_ids:
                    invalid += 1
                seen.add(x)
            v.b_duplicates = dups
            v.b_invalid_ids = invalid
            v.missing_ids = len(valid_ids - seen)
            v.b_is_permutation = (
                dups == 0 and invalid == 0 and len(seen) == len(valid_ids)
            )

        # Per-record checks (report_obb_format.md §9): size, ramp monotonicity,
        # window inside the gap region.
        size_viol = 0
        ramp_viol = 0
        outside = 0
        max_end = 0
        min_gap = None
        sum_gap_len = 0
        sum_n = 0
        n_min, n_max = None, None
        for entry in idx:
            if entry.is_null:
                continue
            try:
                rec = self.parse_unit_record(entry.offset, entry.length)
            except CDXVError:
                size_viol += 1
                continue
            sum_n += rec.N
            n_min = rec.N if n_min is None else min(n_min, rec.N)
            n_max = rec.N if n_max is None else max(n_max, rec.N)
            if not rec.ramp_monotone:
                ramp_viol += 1
            end = rec.gap_offset + rec.gap_length
            max_end = max(max_end, end)
            min_gap = rec.gap_offset if min_gap is None else min(min_gap, rec.gap_offset)
            sum_gap_len += rec.gap_length
            distinct_gap.add(rec.gap_offset)
            if rec.gap_offset < gap_start or end > gap_end:
                outside += 1
        v.record_size_violations = size_viol
        v.ramp_violations = ramp_viol
        v.window_outside_gap = outside
        v.max_window_end = max_end
        v.min_gap_offset = min_gap or 0
        v.sum_gap_lengths = sum_gap_len
        v.distinct_gap_offsets = len(distinct_gap)
        v.sum_N = sum_n
        v.N_range = (n_min or 0, n_max or 0)
        v.phoneme_count = len(self.phonemes())
        v.diphone_names_without_nul = self._count_names_without_nul()
        return v

    def _count_names_without_nul(self) -> int:
        raw = self._section_bytes("A")
        bad = 0
        for i in range(len(raw) // SECTION_A_REC):
            if b"\x00" not in raw[i * SECTION_A_REC:i * SECTION_A_REC + 12]:
                bad += 1
        return bad
