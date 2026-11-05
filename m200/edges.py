"""Closed native edge-contact domain; events belong to addresses and scans."""

import re
from .model import fail

BASE = {
    stem + suffix: stem for stem in ("LD", "AND", "OR", "XOR") for suffix in ("R", "F")
}
OPS = tuple(BASE)
LOADS = ("LD", "LDN", "LDR", "LDF")
SERIES = ("LD", "LDN", "LDR", "LDF", "AND", "ANDN", "ANDR", "ANDF")
API = {
    f"{bank}_{edge}": (bank, edge)
    for bank in ("input", "m")
    for edge in ("rising", "falling")
}


def operand(text):
    m = re.fullmatch(r"%(I0\.|M)(0|[1-9][0-9]*)", text)
    if m is None or int(m[2]) >= (24 if m[1] == "I0." else 1024):
        fail("native edge contacts require direct I0/M within target bounds: " + text)
    return m[1], int(m[2])


def cpp(op, text):
    bank, index = operand(text)
    return f"plc::{'input' if bank == 'I0.' else 'm'}_{'rising' if op[-1] == 'R' else 'falling'}({index})"


def contact_type(op):
    if op in ("LDR", "ANDR"):
        return "RisingEdge"
    if op in ("LDF", "ANDF"):
        return "FallingEdge"
    return "NegatedContact" if op in ("LDN", "ANDN") else "NormalContact"
