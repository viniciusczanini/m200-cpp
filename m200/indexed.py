"""Closed native indexed-word references and the local documented-bound model."""

import re

from .model import fail

WORD_PATTERN = r"%(?:MW|MD|MF)(?:0|[1-9][0-9]*)(?:\[%MW(?:0|[1-9][0-9]*)\])?"
INDEXED = re.compile(r"%(MW|MD|MF)(0|[1-9][0-9]*)\[%MW(0|[1-9][0-9]*)\]")
BIT_INDEXED = re.compile(r"%M(0|[1-9][0-9]*)\[%MW(0|[1-9][0-9]*)\]")
ANY_INDEXED = re.compile(r"%M(?:W|D|F)?(?:0|[1-9][0-9]*)\[%MW(?:0|[1-9][0-9]*)\]")
KINDS = {"MW": "i16", "MD": "i32", "MF": "f32"}
WIDTHS = {"i16": 1, "i32": 2, "f32": 2}


def is_indexed(text):
    return INDEXED.fullmatch(text) is not None


def is_bit_indexed(text):
    return BIT_INDEXED.fullmatch(text) is not None


def parse_bit(text):
    match = BIT_INDEXED.fullmatch(text)
    if match is None:
        fail("unsupported indexed bit address: " + text)
    base, index = map(int, match.groups())
    if base >= 1024 or index >= 8000:
        fail("indexed bit/word address outside target memory: " + text)
    return base, index


def parse(text):
    match = INDEXED.fullmatch(text)
    if match is None:
        fail("unsupported indexed address: " + text)
    prefix, base, index = match.groups()
    kind, base, index = KINDS[prefix], int(base), int(index)
    if base + WIDTHS[kind] > 8000 or index >= 8000:
        fail("indexed address outside shared 8000-word memory: " + text)
    return kind, base, index


def direct_word_limit(program):
    # Include the static base and the index MW, but not an invented range of
    # possible offsets. Symbol-only/Manual excess needs separate acceptance.
    used = []
    for rung in program.rungs:
        for line in rung:
            for prefix, number in re.findall(r"%(MW|MD|MF)([0-9]+)", line):
                used.append(int(number) + WIDTHS[KINDS[prefix]])
    return max(used, default=0)


def has_indexed(program):
    return any(ANY_INDEXED.search(line) for rung in program.rungs for line in rung)


def has_indexed_bits(program):
    return any(BIT_INDEXED.search(line) for rung in program.rungs for line in rung)


def direct_bit_limit(program):
    return max(
        (
            int(n) + 1
            for rung in program.rungs
            for line in rung
            for n in re.findall(r"%M([0-9]+)", line)
        ),
        default=0,
    )


def resolve_bit(text, words, limit):
    base, index = parse_bit(text)
    raw = words[index]
    offset = raw - 65536 if raw >= 32768 else raw
    position = base + offset
    error = not 0 <= position < limit
    return base if error else position, error


def resolve(text, words, limit):
    kind, base, index = parse(text)
    raw = words[index]
    offset = raw - 65536 if raw >= 32768 else raw
    position = base + offset
    error = position < 0 or position + WIDTHS[kind] > limit
    return kind, base if error else position, error
