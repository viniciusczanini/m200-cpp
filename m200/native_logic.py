"""Closed native boolean structures; domain validation stays in the IL layer."""

import re

from .model import fail
from .numeric import is_operation
from .flow import JUMPS, ENDS
from .edges import OPS as EDGE_OPS, LOADS
from .edge_functions import parse as expression_edge
from .counters import body as counter_body, ACTIONS as COUNTER_ACTIONS
from . import timer_il

STORES = ("ST", "STN", "S", "R")
LOGIC = ("LD", "LDN", "AND", "ANDN", "OR", "ORN", "XOR", "XORN", *EDGE_OPS)
STACK = ("MPS", "MRD", "MPP")
OPEN = ("AND(", "OR(")
# Compatibility names used by the other native backends.
timer_index = timer_il.index
timer_body = timer_il.body


def decode(rung):
    if any(not line.strip() for line in rung):
        fail("empty native instruction")
    from .register_il import body as register_body, PIN_OPS

    from .sequences import parse_body as sequence_body, INTERNAL_PINS
    sequence = sequence_body(rung)
    register = register_body(rung)
    body = counter_body(rung) if register is None else register
    body = timer_body(rung) if body is None else body
    body = sequence if sequence is not None else body
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
        if i == 0 and op not in LOADS and not (len(rung) == 1 and op in ("JMP", "END")):
            fail("rung must begin with a supported load")
        if op in ENDS:
            if arg:
                fail("unexpected operand for " + op)
            if parentheses or stack:
                fail(
                    "END inside parentheses or an open stack is outside the reversible subset"
                )
            if op == "END" and i != len(rung) - 1:
                fail("instructions after unconditional END in the same rung")
        elif expression_edge(op) is not None:
            if arg:
                fail("expression edge function takes no operand")
        elif op in (*STACK, "N", ")"):
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
        elif op in (*STORES, *JUMPS, "IN", "NUM", "RTC_EXEC", *COUNTER_ACTIONS, *PIN_OPS, *INTERNAL_PINS):
            if op == "RTC_EXEC" and i != len(rung) - 1:
                fail("internal RTC_EXEC must terminate its rung")
            if op in INTERNAL_PINS and sequence is None:
                fail("internal sequence action outside native block")
            if op in PIN_OPS and register is None:
                fail("internal Register action outside a native Register block")
            if parentheses:
                fail("action instruction inside parentheses")
            if op in JUMPS and (stack or i != len(rung) - 1):
                fail("jump must terminate a rung with balanced stacks")
            if (
                op == "IN"
                and i + 1 < len(rung)
                and rung[i + 1].split(maxsplit=1)[0] not in LOADS
            ):
                fail("IN accumulator effects before subsequent actions are unverified")
        elif op not in LOGIC:
            fail("unsupported IL instruction/order: " + line)
        if (
            op in (*LOGIC, *STORES, *JUMPS, "IN", *COUNTER_ACTIONS, *PIN_OPS, *INTERNAL_PINS)
            and not arg
        ):
            fail("missing operand for " + op)
        result.append((op, arg))
    if stack or parentheses:
        fail("unbalanced boolean stack/parentheses")
    if not result or result[-1][0] not in (
        *STORES,
        *JUMPS,
        *ENDS,
        "IN",
        "NUM",
        "RTC_EXEC",
        *COUNTER_ACTIONS,
        *PIN_OPS,
        *INTERNAL_PINS,
    ):
        fail("rung has no terminal action")
    return result
