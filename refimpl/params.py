"""``tts_voice_param`` command grammar and key table.

Source: ``report_engine_api.md`` §8 (parser ``0x00049f78``; table base
``DAT_00194fbc``).  Grammar::

    cmd = "set" | "get", colon-separated
    set:KEY            -> value = *ptr (in)
    get:KEY            -> *ptr = value (out)
    set:KEY:min|max|def-> set to limit/default
    get:KEY:min|max|def-> *ptr = limit/default

Unknown cmd/KEY/qualifier -> errno 8, return 0.  The 3rd argument is always a
``void*`` (int / uint / float-bits / ``char*`` depending on the key).

The float-valued keys (``volume``, ``dur_stretch``, ``pitch_stretch``) use an
integer 1..99 XOR-mapped onto the float range (handler ``FUN_000494a4``) with
``salt = active_cert_context[+0x2c]`` (0 if no context).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

#: XOR mask used by the float mapping (report_engine_api.md §8).
FLOAT_MASK = 0xE6AA80C7


class ParamError(Exception):
    """Raised for invalid commands / values.

    ``errno`` follows the report: 8 = unknown cmd/KEY/qualifier, 6 = value out
    of range / invalid.
    """

    def __init__(self, errno: int, message: str):
        super().__init__(message)
        self.errno = errno


#: value kinds used by the table.
KIND_INT = "int"
KIND_FLOAT = "float"        # int 1..99 mapped to a float range
KIND_STRING = "string"
KIND_POINTER = "pointer"


@dataclass(frozen=True)
class ParamSpec:
    key: str
    prop: str                    # property name stored in the .vox
    kind: str
    value_min: Optional[int] = None
    value_max: Optional[int] = None
    default: Optional[int] = None
    float_min: Optional[float] = None
    float_def: Optional[float] = None
    float_max: Optional[float] = None
    string_default: Optional[str] = None


#: The command table (report_engine_api.md §8).
PARAM_TABLE: Dict[str, ParamSpec] = {
    "volume": ParamSpec(
        "volume", "amplify", KIND_FLOAT, 1, 99, None,
        float_min=0.0, float_def=1.0, float_max=1.6,
    ),
    "dur_stretch": ParamSpec(
        "dur_stretch", "duration_stretch", KIND_FLOAT, 1, 99, None,
        float_min=0.25, float_def=1.0, float_max=1.5,
    ),
    "pitch_stretch": ParamSpec(
        "pitch_stretch", "pitch_stretch", KIND_FLOAT, 1, 99, None,
        float_min=0.9, float_def=1.0, float_max=1.1,
    ),
    # contrast: set 1 -> compress=4.0f, set 0 -> compress=1.0f; min/def -> 0, max -> 1
    "contrast": ParamSpec(
        "contrast", "eng_contrast", KIND_INT, 0, 1, 0,
    ),
    # quality: 1..10; def stores the seeded half-beam (= level 1)
    "quality": ParamSpec(
        "quality", "viterbi_beam", KIND_INT, 1, 10, 1,
    ),
    # responsiveness: set requires < 2; min stores -1, max/def store 6,
    # get returns 1 iff stored == 6.
    "responsiveness": ParamSpec(
        "responsiveness", "tb_min_distance", KIND_INT, 0, 1, 1,
    ),
    "sentence_break": ParamSpec(
        "sentence_break", "eng_sentence_break", KIND_INT, 0, 60000, 400,
    ),
    "paragraph_break": ParamSpec(
        "paragraph_break", "eng_paragraph_break", KIND_INT, 0, 60000, 650,
    ),
    "max_sentence_length": ParamSpec(
        "max_sentence_length", "eng_max_sentence", KIND_INT, 1, 0x7FFFFFFF, 1000,
    ),
    "max_word_length": ParamSpec(
        "max_word_length", "eng_max_word", KIND_INT, 1, 0x7FFFFFFF, 100,
    ),
    "text_encoding": ParamSpec(
        "text_encoding", "eng_text_encoding", KIND_STRING, string_default="UTF-8",
    ),
    "base_uri": ParamSpec(
        "base_uri", "eng_ssml_base_uri", KIND_STRING, string_default="",
    ),
    "input_type": ParamSpec(
        "input_type", "eng_input_type", KIND_STRING, string_default="",
    ),
    "fetch_function": ParamSpec(
        "fetch_function", "eng_fetch_function", KIND_POINTER, default=0,
    ),
    "fetch_user_data": ParamSpec(
        "fetch_user_data", "eng_fetch_user_data", KIND_POINTER, default=0,
    ),
    "dict_insert_id": ParamSpec(
        "dict_insert_id", "eng_dict_insert_id", KIND_STRING, string_default="",
    ),
}

VALID_OPS = ("set", "get")
VALID_QUALIFIERS = ("min", "max", "def")


def parse_command(cmd: str) -> Tuple[str, str, Optional[str]]:
    """Split ``cmd`` into ``(op, key, qualifier)``; validates against grammar.

    Raises :class:`ParamError` (errno 8) for unknown op/key/qualifier.
    """
    parts = cmd.split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ParamError(8, f"malformed command: {cmd!r}")
    op, key = parts[0], parts[1]
    qualifier = parts[2] if len(parts) == 3 else None
    if op not in VALID_OPS:
        raise ParamError(8, f"unknown op: {op!r}")
    if key not in PARAM_TABLE:
        raise ParamError(8, f"unknown key: {key!r}")
    if qualifier is not None and qualifier not in VALID_QUALIFIERS:
        raise ParamError(8, f"unknown qualifier: {qualifier!r}")
    return op, key, qualifier


def validate_int_value(key: str, value: int) -> int:
    """Range-check an integer value; errno 6 when out of range
    (report_engine_api.md §8)."""
    spec = PARAM_TABLE[key]
    if spec.value_min is not None and value < spec.value_min:
        raise ParamError(6, f"{key}={value} below min {spec.value_min}")
    if spec.value_max is not None and value > spec.value_max:
        raise ParamError(6, f"{key}={value} above max {spec.value_max}")
    return value


# ---------------------------------------------------------------------------
# Float-key encoding (FUN_000494a4)
# ---------------------------------------------------------------------------
def encode_float(value: int, fmin: float, fmax: float, salt: int = 0) -> float:
    """int 1..99 -> float range (report_engine_api.md §8)."""
    if not 1 <= value <= 99:
        raise ParamError(6, f"float-key value {value} outside 1..99")
    return fmin + (((value - 1) ^ FLOAT_MASK ^ salt) % 99) * (fmax - fmin) / 99


def _round_up_if(frac: float, threshold: float = 0.75) -> int:
    floor = math.floor(frac)
    if (frac - floor) >= threshold:
        return floor + 1
    return int(math.floor(frac + 0.5))  # round half up


def decode_float(value: float, fmin: float, fmax: float, salt: int = 0) -> int:
    """float -> int 1..99 (report_engine_api.md §8; rounds up when frac >= 0.75)."""
    n = _round_up_if((value - fmin) * 99 / (fmax - fmin))
    return (n ^ FLOAT_MASK ^ salt) % 99 + 1


#: SSML ``input_type`` MIME values (report_engine_api.md §8).
INPUT_TYPES = ("", "text/plain", "application/ssml+xml")

#: Supported ``base_uri`` schemes (report_engine_api.md §8).
URI_SCHEMES = ("file://", "http://")


def uri_scheme_supported(uri: str) -> bool:
    return uri == "" or uri.lower().startswith(URI_SCHEMES)
