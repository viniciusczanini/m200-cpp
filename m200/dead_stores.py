"""Discard dead pure stores to compiler-private scalar bits, never PLC effects."""

from .copy_fusion import PURE_BIT
from .model import fail

READ_OPS = frozenset(("LD", "LDN", "AND", "ANDN", "OR", "ORN", "XOR", "XORN"))


def eliminate(program, registers, members, groups, reference, live_out):
    if program.subroutines:
        return 0  # A single CFG has no callee read/write summaries.
    origins = program.metadata.get("rung_origins")
    if origins is not None and (
        not isinstance(origins, list) or len(origins) != len(program.rungs)
    ):
        fail("invalid source map metadata")
    removed = []
    for index, rung in enumerate(program.rungs):
        if len(rung) < 2 or rung[0].startswith("%L"):
            continue
        parts = [line.split(maxsplit=1) for line in rung]
        if any(len(value) != 2 for value in parts):
            continue
        action, target = parts[-1]
        reg = registers.get(target)
        if (
            action not in ("ST", "S", "R")
            or reg is None
            or reg.kind != "bool"
            or reg.persistent
            or reg.width != 1
            or target in groups
            or members.get(target) != (target, 0)
            or target in live_out[index]
        ):
            continue
        if all(
            op in READ_OPS and (arg in ("0", "1") or PURE_BIT.fullmatch(arg))
            for op, arg in parts[:-1]
        ):
            removed.append(index)
    if not removed:
        return 0
    dropped = set(removed)
    before = sum(map(len, program.rungs))
    program.rungs = [r for i, r in enumerate(program.rungs) if i not in dropped]
    if origins is not None:
        program.metadata["rung_origins"] = [
            origin for i, origin in enumerate(origins) if i not in dropped
        ]
    used = {
        members.get(ref, (ref, 0))[0]
        for rung in program.rungs
        for line in rung
        for ref in reference.findall(line)
    }
    dead = {
        ref
        for ref, reg in registers.items()
        if not reg.persistent and ref not in groups and ref not in used
    }
    for ref in dead:
        registers.pop(ref)
    for ref, (owner, _) in list(members.items()):
        if owner in dead:
            members.pop(ref)
            program.symbols.pop(ref, None)
    program.metadata["dead_private_stores"] = {
        "eliminated_rungs": len(removed),
        "instructions_before": before,
        "instructions_after": sum(map(len, program.rungs)),
        "method": "CFG dead-after proof; pure direct bit reads; private complete scalar writes only; single batch",
    }
    return len(removed)
