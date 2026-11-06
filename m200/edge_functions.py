"""Stateful accumulator edge functions; identity is unique per static site."""

import re
from .model import fail

API = {"plc::rising": "RISING", "plc::falling": "FALLING"}


def parse(op):
    if not op.startswith(("RISING", "FALLING")):
        return None
    match = re.fullmatch(r"(RISING|FALLING)(0|[1-9][0-9]*)", op)
    if match is None or int(match[2]) >= 255:
        fail("invalid expression edge identity (0..254): " + op)
    return match[1], int(match[2])
