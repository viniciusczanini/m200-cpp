"""Packed decimal and word conversions; no invented invalid BCD results."""

import re

from .model import fail

NUMERIC_CONVERSIONS = {
    "bcd_to_int": ("i16", ("i16",), "BTI", "function"),
    "bcd_to_dint": ("i32", ("i32",), "BTI", "function"),
    "int_to_bcd": ("i16", ("i16",), "ITB", "function"),
    "dint_to_bcd": ("i32", ("i32",), "ITB", "function"),
    "concat_words": ("i32", ("i16", "i16"), "CONCATW", "function"),
    "int_to_dint": ("i32", ("i16",), "DWORD", "function"),
}


def needs_word_snapshot(token, code):
    return (
        token in ("DWORD", "CONCATW")
        and code.startswith("%")
        and not re.fullmatch(r"%[MK]W(?:0|[1-9][0-9]*)", code)
    )


def signed_bits(value, width):
    raw = value % (1 << width)
    return raw - (1 << width) if raw >= (1 << (width - 1)) else raw


def evaluate_conversion(name, values):
    if name == "concat_words":
        return signed_bits((values[0] & 65535) | ((values[1] & 65535) << 16), 32)
    if name == "int_to_dint":
        # Explicit local policy: native DWORD's negative sign extension is not
        # established by G59-60; acceptance/semantics still require editor/PLC.
        return values[0]
    width = 16 if name in ("bcd_to_int", "int_to_bcd") else 32
    digits = width // 4
    value = values[0]
    if name.startswith("bcd_to_"):
        raw = value % (1 << width)
        result, place = 0, 1
        for _ in range(digits):
            digit = raw & 15
            if digit > 9:
                fail("numeric arithmetic error: invalid BCD digit; result unmodeled")
            result += digit * place
            place *= 10
            raw >>= 4
        return result
    if not 0 <= value < 10**digits:
        fail(
            "numeric arithmetic error: binary value outside BCD range; result unmodeled"
        )
    result = 0
    for shift in range(0, width, 4):
        result |= (value % 10) << shift
        value //= 10
    return signed_bits(result, width)
