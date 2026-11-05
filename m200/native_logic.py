"""Closed native boolean structures; domain validation stays in the IL layer."""

import re

from .model import fail
from .numeric import is_operation
from .flow import JUMPS

STORES = ("ST", "STN", "S", "R")
LOGIC = ("LD", "LDN", "AND", "ANDN", "OR", "ORN", "XOR", "XORN")
STACK = ("MPS", "MRD", "MPP")
OPEN = ("AND(", "OR(")


def timer_index(arg):
    m = re.fullmatch(r"%TM(0|[1-9][0-9]*)", arg)
    if not m or int(m[1]) >= 255:
        fail("invalid native timer address: " + arg)
    return int(m[1])


def timer_body(rung):
    if any(not line.strip() for line in rung):
        fail("empty native instruction")
    if not rung or not rung[0].startswith("BLK %TM"):
        return None
    index = timer_index(rung[0].split(maxsplit=1)[1])
    if rung[-1] != "END_BLK" or rung.count("IN") != 1 or rung.count("OUT_BLK") != 1:
        fail("unsupported or non-reversible timer block")
    at = rung.index("IN")
    out = rung.index("OUT_BLK")
    if (
        at < 2
        or out != at + 1
        or rung[out + 1 : out + 2] != ["LD Q"]
        or out + 2 >= len(rung) - 1
    ):
        fail("unsupported or non-reversible timer block")
    before = rung[1:at]
    after = rung[out + 2 : -1]
    if any(
        line.split(maxsplit=1)[0] not in (*LOGIC, *OPEN, "N", ")") for line in before
    ):
        fail("unsupported timer input instruction")
    if any(
        line.split(maxsplit=1)[0] in (*JUMPS, "IN", "BLK", *STACK) for line in after
    ):
        fail("unsupported timer output instruction")
    return before + [f"IN %TM{index}", f"LD %TM{index}.Q"] + after


def decode(rung):
    if any(not line.strip() for line in rung):
        fail("empty native instruction")
    body = timer_body(rung)
    rung = body if body is not None else rung
    result = []
    stack = 0
    parentheses = 0
    for i, line in enumerate(rung):
        if is_operation(line):
            op, arg = "NUM", line
        else:
            parts = line.split(maxsplit=1)
            op = parts[0]
            arg = parts[1] if len(parts) == 2 else ""
        if i == 0 and op not in ("LD", "LDN") and not (len(rung) == 1 and op == "JMP"):
            fail("rung must begin with a supported load")
        if op in (*STACK, "N", ")"):
            if arg:
                fail("unexpected operand for " + op)
            if op in STACK:
                if parentheses:
                    fail("stack instruction inside parentheses")
                if op == "MPS":
                    stack += 1
                    if stack > 32:
                        fail(
                            "local boolean stack depth exceeds 32; native 11/32 conflict pending"
                        )
                elif not stack:
                    fail(op + " without MPS")
                elif op == "MPP":
                    stack -= 1
            elif op == ")":
                if not parentheses:
                    fail("unmatched close parenthesis")
                parentheses -= 1
        elif op in OPEN:
            if not arg:
                fail("parenthesis opener requires an operand")
            parentheses += 1
            if parentheses > 32:
                fail("parenthesis depth exceeds 32")
        elif op in (*STORES, *JUMPS, "IN", "NUM"):
            if parentheses:
                fail("action instruction inside parentheses")
            if op in JUMPS and (stack or i != len(rung) - 1):
                fail("jump must terminate a rung with balanced stacks")
            if (
                op == "IN"
                and i + 1 < len(rung)
                and rung[i + 1].split(maxsplit=1)[0] not in ("LD", "LDN")
            ):
                fail("IN accumulator effects before subsequent actions are unverified")
        elif op not in LOGIC:
            fail("unsupported IL instruction/order: " + line)
        if op in (*LOGIC, *STORES, *JUMPS, "IN") and not arg:
            fail("missing operand for " + op)
        result.append((op, arg))
    if stack or parentheses:
        fail("unbalanced boolean stack/parentheses")
    if not result or result[-1][0] not in (*STORES, *JUMPS, "IN", "NUM"):
        fail("rung has no terminal action")
    return result
