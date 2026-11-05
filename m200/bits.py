"""Closed word-bit/packed-bit syntax and complete explicit M extents."""

import re
from .model import fail

DEC = r"(?:0|[1-9][0-9]*)"
WORD_BIT = re.compile(r"%MW(" + DEC + r"):X(" + DEC + r")")
STRING_PATTERN = r"%(?:M" + DEC + r"|I0\." + DEC + r"|Q0\." + DEC + r"):" + DEC
STRING = re.compile(r"%(M|I0\.|Q0\.)(" + DEC + r"):(" + DEC + r")")


def word_bit(text):
    m = WORD_BIT.fullmatch(text)
    if not m or int(m[1]) >= 8000 or int(m[2]) >= 16:
        fail("unsupported word bit address: " + text)
    return int(m[1]), int(m[2])


def is_string(text):
    return STRING.fullmatch(text) is not None


def bit_string(text, writable=False, width=32):
    m = STRING.fullmatch(text)
    if not m:
        fail("unsupported bit string: " + text)
    bank, start, count = m[1], int(m[2]), int(m[3])
    limit = {"M": 1024, "I0.": 24, "Q0.": 16}[bank]
    if start % 8 or not 1 <= count <= min(width, 32) or start + count > limit:
        fail("bit string alignment/range exceeds target/carrier: " + text)
    if writable and bank == "I0.":
        fail("input bit string is read-only")
    return bank, start, count


def references(text):
    bank, start, count = bit_string(text)
    return [f"%{bank}{start + i}" for i in range(count)]


def memory_bits_used(program):
    text = (
        " ".join(" ".join(r) for r in program.rungs) + " " + " ".join(program.symbols)
    )
    used = {int(n) for n in re.findall(r"%M([0-9]+)", text)}
    for m in STRING.finditer(text):
        bank, start, count = bit_string(m[0])
        if bank == "M":
            used.update(range(start, start + count))
    return used


def signed_pattern(raw, kind):
    width = 16 if kind == "i16" else 32
    raw &= (1 << width) - 1
    return raw - (1 << width) if raw & (1 << (width - 1)) else raw
