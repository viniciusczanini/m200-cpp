"""Native unsigned RTC word domains behind the existing public signed-i16 API.

Schneider c706f6b campaign, g09-schedule-memory cpp_0003/cpp_0007:
"-1 is out of authorized bounds (0...65535)." Both assignment and comparison
use an unsigned native SW114 object. Public API/VM values remain signed i16.
Generic Functions EIO0000003289.04 p25 permits word patterns16#0000..16#FFFF.
Only the actually observed SW114 domain is admitted here; no inferred SW ranges.
"""
import re


UNSIGNED_NATIVE_WORDS = frozenset(("%SW114",))
NEGATIVE_DECIMAL = re.compile(r"-[1-9][0-9]*")


def needs_signed_carrier(value):
    """A native MW copy gives comparisons/ALU the public signed word domain."""
    return value.kind == "i16" and value.code in UNSIGNED_NATIVE_WORDS


def assignment_source(target, value):
    """Render a negative i16 literal as its authorized unsigned word pattern.

    This changes native spelling, not the public value. Variables remain one
    native word copy, including negative i16 data produced at runtime. Parsing
    of the generated based literal already normalizes it to the same signed
    i16 in numeric.operand, so VM/reverse need no new interpretation or API.
    """
    if (
        target.kind == value.kind == "i16"
        and target.code in UNSIGNED_NATIVE_WORDS
        and NEGATIVE_DECIMAL.fullmatch(value.code) is not None
    ):
        return "16#%04X" % (int(value.code) & 65535)
    return value.code
