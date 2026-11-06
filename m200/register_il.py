"""Register pin groups are evaluated before one atomic per-call update."""

import re
from .model import fail
from .registers import index

PIN_OPS = ("REG_R", "REG_I", "REG_O")


def body(rung):
    rung = [" ".join(line.split()) for line in rung]
    if not rung or not re.fullmatch(r"BLK %R[0-9]+", rung[0]):
        return None
    key = rung[0].split()[1]
    index(key)
    if rung[-1] != "END_BLK":
        fail("Register block must end with END_BLK")
    from .native_logic import decode, LOGIC, OPEN

    result, group, pin = [], [], 0
    for line in rung[1:-1]:
        if line in ("R", "I", "O"):
            if pin >= 3 or line != ("R", "I", "O")[pin] or not group:
                fail("Register requires ordered R/I/O input groups")
            instructions = decode(group + ["ST %M0"])
            if any(op not in (*LOGIC, *OPEN, "N", ")") for op, _ in instructions[:-1]):
                fail("Register inputs require pure balanced boolean expressions")
            result.extend(group)
            result.append(PIN_OPS[pin] + " " + key)
            pin += 1
            group = []
        else:
            group.append(line)
    if group or pin != 3:
        fail("Register requires exactly three R/I/O inputs")
    return result


def referenced_ids(rungs):
    from .registers import REFERENCE

    result = set()
    for rung in rungs:
        for line in rung:
            result.update(int(match[1]) for match in REFERENCE.finditer(line))
            match = re.fullmatch(r"BLK\s+(%R[0-9]+)", line)
            if match:
                result.add(index(match[1]))
    return result
