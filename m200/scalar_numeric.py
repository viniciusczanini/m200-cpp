"""Scalar extensions and documented invalid-result domains (G02).

Primary sources: EIO0000003289.04 pp27-28,53-57,67-70;
EIO0000002019.06 pp322-323,331. No firmware precision claim is made by
using host libm. Unspecified integer results are values, never fake successes.
"""

import math
import struct
from dataclasses import dataclass

from .model import fail

OPS = {}
for kind in ("i16", "i32"):
    for stem in ("inc", "dec"):
        OPS[stem + "_" + kind] = (kind, (kind,), stem.upper(), "inplace")

DIRECT_UNARY = {
    stem + "_" + bank: (stem + "_" + kind, kind)
    for bank, kind in (("word", "i16"), ("dword", "i32"))
    for stem in ("inc", "dec")
}
DIRECT_RECOVERY = {
    stem + "_" + bank: (stem + "_" + kind, kind)
    for bank, kind in (("word", "i16"), ("dword", "i32"))
    for stem in ("div", "rem", "sqrt")
}
SYSTEM_WORD_PATTERN = r"%SW17"


def system_word(text, writable=False):
    # Provider ownership only: return False for other families, so the general
    # system-word dispatch can compose with RTC/diagnostic providers (G09).
    return text == "%SW17"


@dataclass(frozen=True)
class Indeterminate:
    reason: str

    def __bool__(self):
        fail("indeterminate integer result observed: " + self.reason)


def known(value):
    if isinstance(value, Indeterminate):
        fail("indeterminate integer result observed before recovery: " + value.reason)
    return value


class Real32(float):
    """Carry the stored IEEE bits through copies, including NaN payloads."""

    def __new__(cls, raw):
        result = super().__new__(cls, struct.unpack("<f", struct.pack("<I", raw))[0])
        result.raw = raw
        return result


def real32(value):
    if isinstance(value, Real32):
        return value
    try:
        raw = struct.unpack("<I", struct.pack("<f", value))[0]
    except OverflowError:
        raw = 0xFF800000 if value < 0 else 0x7F800000
    return Real32(raw)


def floating_result(value, flags, error=0):
    result = real32(value)
    if not error:
        error = 1 if math.isnan(result) else 8 if math.isinf(result) else 0
    if error:
        if flags is None:
            fail("numeric arithmetic error: REAL32 invalid result")
        flags.floating_error(error)
    return result


def evaluate_float(stem, values, flags):
    """Evaluate an instruction; status is sticky and independent of S17.

    Domain decisions precede host math so Python exceptions do not abort a scan.
    """
    a = values[0]
    b = values[1] if len(values) > 1 else None
    if stem == "copy":
        return real32(a)
    if any(math.isnan(v) for v in values):
        return floating_result(math.nan, flags, 1)
    error = 0
    try:
        if stem == "add":
            result = a + b
        elif stem == "sub":
            result = a - b
        elif stem == "mul":
            result = a * b
        elif stem == "div":
            if b == 0:
                result = math.nan if a == 0 else math.copysign(math.inf, a * math.copysign(1.0, b))
                error = 1 if a == 0 else 4
            else:
                result = a / b
        elif stem == "sqrt":
            result = math.sqrt(a)
        elif stem == "abs":
            result = abs(a)
        elif stem == "trunc":
            result = a if math.isinf(a) else math.copysign(float(math.trunc(a)), a)
        elif stem in ("log", "ln"):
            if a == 0:
                result, error = -math.inf, 4
            else:
                result = math.log10(a) if stem == "log" else math.log(a)
        elif stem == "exp":
            result = math.exp(a)
        elif stem in ("sin", "cos", "tan"):
            if not math.isfinite(a) or abs(a) > 4096 * math.pi:
                result, error = math.nan, 1
            else:
                result = getattr(math, stem)(a)
        elif stem in ("asin", "acos", "atan"):
            result = getattr(math, stem)(a)
        elif stem in ("int_to_real", "dint_to_real"):
            result = a
        else:
            fail("unmodeled floating operation: " + stem)
    except ValueError:
        result, error = math.nan, 1
    except OverflowError:
        result, error = math.inf, 8
    return floating_result(result, flags, error)



class IndeterminateMemory:
    """Sparse bit masks: no reserved PLC cells and exact partial overwrite kills."""

    def __init__(self):
        self.words = {}

    def read(self, index, width):
        for cell in range(index, index + width):
            entry = self.words.get(cell)
            if entry:
                return Indeterminate(entry[1])
        return None

    def write(self, index, width, value):
        for cell in range(index, index + width):
            if isinstance(value, Indeterminate):
                self.words[cell] = (65535, value.reason)
            else:
                self.words.pop(cell, None)

    def read_bit(self, word, bit):
        entry = self.words.get(word)
        if entry and entry[0] & (1 << bit):
            known(Indeterminate(entry[1]))

    def write_bit(self, word, bit):
        entry = self.words.get(word)
        if entry:
            mask = entry[0] & ~(1 << bit)
            if mask:
                self.words[word] = (mask, entry[1])
            else:
                self.words.pop(word)
