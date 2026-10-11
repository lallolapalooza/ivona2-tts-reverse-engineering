"""Voice-package discovery contract (Android + ``libtiver`` side).

Implements the documented facts from:

* ``report_engine_app.md`` §5 (package discovery, ``getVoicesApiVersion`` string
  format, ``ivona_pkgs.csv`` columns, selection-file naming, data-root probe
  order);
* ``report_libtiver.md`` (§1-§7: the ``v``/``h`` contract, the 42-row table,
  ``main.<N>.<pkg>.obb`` / ``patch.199.<pkg>.obb`` naming, exact size gates);
* ``IVONA2_REVERSE_ENGINEERING.md`` §3 (engine-side gate on the ``v()`` struct).

The 42-row table is read from ``scripts/table_full.json`` (decoded in
``report_libtiver.md`` §4) when present.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

#: Package-name prefix of every IVONA 2 voice pack.
PACKAGE_PREFIX = "com.ivona.tts.voicebeta"

#: Patch OBB version is the hardcoded C literal 199, independent of the main
#: OBB's ``N`` (report_libtiver.md §3.1 / §7.1).
PATCH_VERSION = 199

#: Main-OBB versions observed in the table (report_libtiver.md §4).
MAIN_VERSIONS = (183, 199, 422)

#: Data roots probed by ``h(pkg, base)`` in order; the engine tries legacy
#: ``<sdcard>/ivona/`` first, then the Play expansion ``<sdcard>/Android/obb/``
#: (report_libtiver.md §5, report_engine_app.md §5.3/§5.6).
DATA_ROOT_PROBE_ORDER = ("ivona/", "Android/obb/")

#: ``dataLocation`` code reported in the 5th ``getVoicesApiVersion`` field
#: (report_libtiver.md §5, report_engine_app.md §5.3).
DATA_LOCATION_NONE = 0
DATA_LOCATION_IVONA = 1
DATA_LOCATION_ANDROID_OBB = 2

#: ``fstate`` mapping consumed by ``packages.b.a(int)`` (report_engine_app.md §5.3).
FSTATE_FULL_INSTALLED = 0
FSTATE_APK_INSTALLED = 1
FSTATE_FILES_WITHOUT_APK = 2
FSTATE_MAP = {
    FSTATE_FULL_INSTALLED: "FULL_INSTALLED",
    FSTATE_APK_INSTALLED: "APK_INSTALLED",
    FSTATE_FILES_WITHOUT_APK: "FILES_WITHOUT_APK",
}


class VoiceError(Exception):
    """Raised for malformed voice metadata."""


# ---------------------------------------------------------------------------
# Package-name grammar (report_engine_app.md §5.6 item 1)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VoicePackage:
    package: str
    lang3: str      # ISO 639-3 language, e.g. "eng"
    country3: str   # ISO 3166-3 country, e.g. "gbr"
    voice: str      # short voice name, e.g. "amy"

    @property
    def locale(self) -> Tuple[str, str, str]:
        return self.lang3, self.country3, self.voice

    def selection_file_name(self) -> str:
        """``"." + iso3lang.lower() + "_" + iso3country.lower()`` (report_engine_app.md §5.7)."""
        return selection_file_name(self.lang3, self.country3)


def parse_package_name(pkg: str) -> VoicePackage:
    """``com.ivona.tts.voicebeta.<lang3>.<country3>.<voice>`` -> locale triple.

    The grammar is exactly seven dot-separated parts (report_engine_app.md §5.6:
    "a package name ``com.ivona.tts.voicebeta.<iso3lang>.<iso3country>.<voice>``
    (7 dot parts)").
    """
    parts = pkg.split(".")
    if len(parts) != 7 or parts[:4] != ["com", "ivona", "tts", "voicebeta"]:
        raise VoiceError(f"not an IVONA 2 voice package name: {pkg!r}")
    return VoicePackage(pkg, parts[4], parts[5], parts[6])


def selection_file_name(lang3: str, country3: str) -> str:
    """Per-locale selection file name (report_engine_app.md §5.7)."""
    return "." + lang3.lower() + "_" + country3.lower()


# ---------------------------------------------------------------------------
# libtiver ``v()`` info struct (report_libtiver.md §1.1/§2, §7.2)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VStruct:
    abi: int            # struct[0], engine gate: > 0x13
    api_version: int    # struct[1], engine gate: < 3
    build_stamp: str    # struct[2], passed through verbatim
    stride: int         # struct[3], engine gate: > 0x2f
    accessor: Optional[int] = None  # struct[4], entry_by_index()


def v_struct_gate(struct: VStruct) -> bool:
    """Engine-side acceptance test (report_libtiver.md §5, §7.2)::

        0x13 < struct[0] && 0x2f < struct[3] && struct[1] < 3

    A struct failing any test is skipped (``dlclose``); the real build returns
    ``VStruct(20, 2, "20130201_150739", 48, accessor)``.
    """
    return struct.abi > 0x13 and struct.stride > 0x2F and struct.api_version < 3


def accessor_entry_index(i: int) -> Optional[int]:
    """``entry(i) = i <= 43 ? table[i] : NULL`` (report_libtiver.md §2).

    Returns the table index for ``i <= 43`` else ``None``; the caller resolves
    it against :func:`load_table`.
    """
    return i if 0 <= i <= 43 else None


# ---------------------------------------------------------------------------
# getVoicesApiVersion report string (report_libtiver.md §5, report_engine_app §5.3)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VoiceReport:
    api_version: int
    fstate: int
    display_name: str
    stamp: str
    data_location: int

    def to_string(self) -> str:
        return (
            f"{self.api_version};{self.fstate};{self.display_name};"
            f"{self.stamp};{self.data_location}"
        )


def format_voice_report(
    api_version: int,
    fstate: int,
    display_name: str,
    stamp: str,
    data_location: int,
) -> str:
    """Emit ``"apiVer;fstate;displayName;stamp;dataLocation"`` (5 fields)."""
    return VoiceReport(api_version, fstate, display_name, stamp, data_location).to_string()


def parse_voice_report(s: str) -> VoiceReport:
    fields = s.split(";")
    if len(fields) != 5:
        raise VoiceError(f"expected 5 ';'-separated fields, got {len(fields)}: {s!r}")
    return VoiceReport(int(fields[0]), int(fields[1]), fields[2], fields[3], int(fields[4]))


def resolve_data_location(h_results: Sequence[int]) -> int:
    """Fold the two ``h()`` probe results into the ``dataLocation`` code.

    ``h`` is tried on each root in :data:`DATA_ROOT_PROBE_ORDER`; the winner is
    ``1`` (``/ivona/``) or ``2`` (``/Android/obb/``) else ``0``
    (report_libtiver.md §5, report_engine_app.md §5.3). ``0`` == success.
    """
    for code, result in zip((DATA_LOCATION_IVONA, DATA_LOCATION_ANDROID_OBB), h_results):
        if result == 0:
            return code
    return DATA_LOCATION_NONE


# ---------------------------------------------------------------------------
# ivona_pkgs.csv (report_engine_app.md §5.3)
# ---------------------------------------------------------------------------
#: Data line: ``pkg;versionCode;apiVer;fstate;displayName;stamp;dataLocation``.
CSV_COLUMNS = (
    "package",
    "versionCode",
    "apiVersion",
    "fstate",
    "displayName",
    "stamp",
    "dataLocation",
)


@dataclass(frozen=True)
class CacheRow:
    package: str
    version_code: int
    api_version: int
    fstate: int
    display_name: str
    stamp: str
    data_location: int


def read_packages_csv(path: str) -> Tuple[int, List[CacheRow]]:
    """Read ``ivona_pkgs.csv``; returns ``(timestamp_millis, rows)``.

    Line 1 is a ``System.currentTimeMillis()`` timestamp; data lines have 7
    ``;``-separated fields (report_engine_app.md §5.3). The reader ignores lines
    with fewer than 6 fields just like the Java reader.
    """
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    if not lines:
        raise VoiceError("empty ivona_pkgs.csv")
    timestamp = int(lines[0].strip() or "0")
    rows: List[CacheRow] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split(";")
        if len(fields) < 6:
            continue
        while len(fields) < 7:
            fields.append("")
        rows.append(
            CacheRow(
                fields[0],
                int(fields[1]),
                int(fields[2]),
                int(fields[3]),
                fields[4],
                fields[5],
                int(fields[6]) if fields[6] != "" else 0,
            )
        )
    return timestamp, rows


def write_packages_csv(path: str, timestamp: int, rows: Sequence[CacheRow]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"{timestamp}\n")
        for r in rows:
            fh.write(
                f"{r.package};{r.version_code};{r.api_version};{r.fstate};"
                f"{r.display_name};{r.stamp};{r.data_location}\n"
            )


# ---------------------------------------------------------------------------
# libtiver package -> OBB table (report_libtiver.md §4)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TableRow:
    lang: str
    country: str
    name: str
    display_name: str
    package: str
    voice_lib: str
    voice_lib_size: int
    size2: int
    main_obb: str
    obb_size: int
    lexicon: str
    trial_message: str = ""

    @property
    def obb_version(self) -> int:
        # "main.<N>.<pkg>.obb" -> N
        return int(self.main_obb.split(".")[1])


def load_table(path: str) -> List[TableRow]:
    """Load the decoded 42-row table (``scripts/table_full.json``)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    rows: List[TableRow] = []
    for r in data:
        rows.append(
            TableRow(
                lang=r[0],
                country=r[1],
                name=r[2],
                display_name=r[3],
                package=r[4],
                voice_lib=r[5],
                voice_lib_size=r[6],
                size2=r[7],
                main_obb=r[8],
                obb_size=r[9],
                lexicon=r[10],
                trial_message=r[11] if len(r) > 11 else "",
            )
        )
    return rows


def find_row(rows: Sequence[TableRow], package: str) -> Optional[TableRow]:
    for r in rows:
        if r.package == package:
            return r
    return None


# ---------------------------------------------------------------------------
# OBB naming + size gate (report_libtiver.md §3, §6, §7)
# ---------------------------------------------------------------------------
def main_obb_name(n: int, package: str) -> str:
    """``main.<N>.<pkg>.obb`` (report_libtiver.md §6)."""
    return f"main.{n}.{package}.obb"


def patch_obb_name(package: str) -> str:
    """``patch.199.<pkg>.obb`` — 199 is hardcoded (report_libtiver.md §3.1)."""
    return f"patch.{PATCH_VERSION}.{package}.obb"


def obb_path(base: str, package: str, name: str) -> str:
    """``<base><package>/<name>`` with no normalisation (report_libtiver.md §6)."""
    if not base.endswith("/"):
        base = base + "/"
    return f"{base}{package}/{name}"


def size_gate(path: str, expected: int) -> bool:
    """``st_size`` low 32 bits == expected and high half == 0
    (report_libtiver.md §3 step 4 / §7.1)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return False
    return (size & 0xFFFFFFFF) == (expected & 0xFFFFFFFF) and (size >> 32) == 0


def check_package(
    package: str,
    base: str,
    rows: Sequence[TableRow],
) -> int:
    """Reimplementation of ``FUN_000169b8`` for a *installed* package
    (report_libtiver.md §3): returns ``0`` size-OK else ``1``.

    (Patch extraction/return codes ``-1``/``-2`` are handled by
    :func:`extract_patch`.)
    """
    row = find_row(rows, package)
    if row is None:
        return 1  # unknown package -> table terminator row (UB in the original)
    path = obb_path(base, package, row.main_obb)
    if not size_gate(path, row.obb_size):
        return 1
    return 0


def extract_patch(package: str, base: str, rows: Sequence[TableRow]) -> int:
    """Reimplementation of ``FUN_000166e8`` (report_libtiver.md §3.1).

    Returns ``0`` = all entries extracted, ``-1`` = patch open/read/write error,
    ``-2`` = NULL args (never here). Entries with ``/`` or ``\\`` in their name
    are skipped; extraction is unconditional (the observed skip predicate
    compares a file size against the entry-name length and never triggers).
    """
    row = find_row(rows, package)
    if row is None:
        return -1
    patch = obb_path(base, package, patch_obb_name(package))
    if not os.path.exists(patch):
        return -1
    import zipfile

    try:
        with zipfile.ZipFile(patch) as zf:
            for info in zf.infolist():
                if "/" in info.filename or "\\" in info.filename:
                    continue
                target = obb_path(base, package, info.filename)
                with zf.open(info) as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(8192)
                        if not chunk:
                            break
                        dst.write(chunk)
    except (OSError, zipfile.BadZipFile):
        return -1
    return 0
