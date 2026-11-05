"""Lower actual native IL into existing series Ladder rungs with private bits."""

import copy
import hashlib
import json

from .flow import JUMPS, split_label, destinations
from .lower import Lowerer
from .native_logic import decode, STORES, OPEN, timer_index
from .numeric import memory_words_used
from .indexed import has_indexed_bits
from .model import fail
from .bits import memory_bits_used
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, SERIES, LOADS


def needed(program):
    for raw in program.rungs:
        _, rung = split_label(raw)
        if rung[0].startswith("BLK "):
            if rung[0].split(maxsplit=1)[1] in program.communications:
                continue
            input_parts = rung[1].split(maxsplit=1) if len(rung) > 1 else []
            negated_comparison = (
                len(input_parts) == 2
                and input_parts[0] == "LDN"
                and input_parts[1].startswith("[")
            )
            if (
                len(rung) == 7
                and rung[5].startswith("ST ")
                and not negated_comparison
                and not any(line.split(maxsplit=1)[0] in EDGE_OPS for line in rung)
            ):
                continue
            return True
        instructions = decode(rung)
        if any(
            op in ("LDN", "ANDN") and arg.startswith("[") for op, arg in instructions
        ):
            return True
        if any(
            op not in (*SERIES, "ST", "S", "R", "NUM", "JMPC")
            or (i and op in LOADS)
            or (i < len(instructions) - 1 and op in (*STORES, "NUM"))
            for i, (op, _) in enumerate(instructions)
        ):
            return True
    return False


def normalize(program):
    from .il import validate

    validate(program)
    if not needed(program):
        return program
    if has_indexed_bits(program):
        fail("indexed-bit normalization bounds/profile are unverified")
    bits = memory_bits_used(program)
    lower = Lowerer(bits, memory_words_used(program))
    used_labels = set(destinations(program))
    free_labels = iter(f"%L{i}" for i in range(64) if f"%L{i}" not in used_labels)

    def new_guard_label():
        result = next(free_labels, None)
        if result is None:
            fail(
                "normalization needs a spare label for safe comparison evaluation; compiler overhead limitation"
            )
        return result

    lower.program.timers = copy.deepcopy(program.timers)
    lower.program.communications = copy.deepcopy(program.communications)
    lower.program.metadata = copy.deepcopy(program.metadata)
    acc = lower.bit("native_accumulator")
    for index, raw in enumerate(program.rungs):
        label, rung = split_label(raw)
        first = len(lower.program.rungs)
        lower.origin = {"generated": f"native logic source rung {index}"}
        if (
            rung[0].startswith("BLK ")
            and rung[0].split(maxsplit=1)[1] in program.communications
        ):
            lower.rung(*rung)
        else:
            saved = []
            groups = []
            for op, arg in decode(rung):
                if op in EDGE_OPS:
                    sample = lower.bit("native_edge_snapshot")
                    lower.rung(
                        ("LDR " if op[-1] == "R" else "LDF ") + arg, "ST " + sample
                    )
                    op, arg = EDGE_BASE[op], sample
                if op == "NUM":
                    lower.rung("LD " + acc, arg)
                elif op in ("LD", "LDN"):
                    if op == "LDN" and arg.startswith("["):
                        arg = lower.copy(arg, "native_comparison")
                    lower.rung(op + " " + arg, "ST " + acc)
                elif op in ("AND", "ANDN", "OR", "ORN", "XOR", "XORN"):
                    skip = None
                    if arg.startswith("[") and not op.startswith("XOR"):
                        skip = new_guard_label()
                        lower.jump(skip, acc, negate=op.startswith("AND"))
                    if arg.startswith("["):
                        arg = lower.copy(arg, "native_comparison")
                    value = lower.neg(arg) if op.endswith("N") else arg
                    operator = (
                        "&&"
                        if op.startswith("AND")
                        else "||"
                        if op.startswith("OR")
                        else "^"
                    )
                    lower.assign(acc, lower.binary(operator, acc, value))
                    if skip is not None:
                        lower.label(skip)
                elif op == "N":
                    lower.assign(acc, lower.neg(acc))
                elif op == "MPS":
                    saved.append(lower.copy(acc, "native_stack"))
                elif op in ("MRD", "MPP"):
                    lower.assign(acc, saved[-1])
                    if op == "MPP":
                        saved.pop()
                elif op in OPEN:
                    groups.append((op, lower.copy(acc, "native_group")))
                    lower.assign(acc, arg)
                elif op == ")":
                    operator, outer = groups.pop()
                    lower.assign(
                        acc,
                        lower.binary("&&" if operator == "AND(" else "||", outer, acc),
                    )
                elif op == "IN":
                    i = timer_index(arg)
                    lower.timer(i, program.timers[i], acc)
                elif op in STORES:
                    value = lower.neg(acc) if op == "STN" else acc
                    lower.rung("LD " + value, ("ST" if op == "STN" else op) + " " + arg)
                elif op in JUMPS:
                    lower.rung(
                        (
                            "LD 1"
                            if op == "JMP"
                            else ("LDN " if op == "JMPCN" else "LD ") + acc
                        ),
                        "JMPC " + arg,
                    )
        if label:
            lower.program.rungs[first].insert(0, label + ":")
    prefix = lower.constant_rungs
    lower.program.rungs = prefix + lower.program.rungs
    lower.program.metadata["rung_origins"] = [
        {"generated": "native logic constants"} for _ in prefix
    ] + lower.origins
    lower.program.symbols.update(program.symbols)
    normalized = lower.storage.finalize(lower.program, lower.constants)
    normalized.metadata["native_logic_normalization"] = {
        "original_rungs": len(program.rungs),
        "expanded_rungs": len(normalized.rungs),
        "original_il_sha256": hashlib.sha256(
            json.dumps(program.rungs, separators=(",", ":")).encode()
        ).hexdigest(),
        "method": "explicit accumulator/stack snapshots; existing series contacts, coils and Timer blocks",
    }
    validate(normalized)
    return normalized
