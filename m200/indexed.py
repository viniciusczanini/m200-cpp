"""Closed native indexed-word references and the local documented-bound model."""

import re

from .model import fail

WORD_PATTERN = r"%(?:MW|MD|MF)(?:0|[1-9][0-9]*)(?:\[%MW(?:0|[1-9][0-9]*)\])?"
INDEXED = re.compile(r"%(MW|MD|MF)(0|[1-9][0-9]*)\[%MW(0|[1-9][0-9]*)\]")
KINDS = {"MW": "i16", "MD": "i32", "MF": "f32"}
WIDTHS = {"i16": 1, "i32": 2, "f32": 2}


def is_indexed(text):
    return INDEXED.fullmatch(text) is not None


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
    return any(INDEXED.search(line) for rung in program.rungs for line in rung)


def resolve(text, words, limit):
    kind, base, index = parse(text)
    raw = words[index]
    offset = raw - 65536 if raw >= 32768 else raw
    position = base + offset
    error = position < 0 or position + WIDTHS[kind] > limit
    return kind, base if error else position, error
