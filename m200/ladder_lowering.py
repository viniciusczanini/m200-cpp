"""Lower actual native IL into existing series Ladder rungs with private bits."""

import copy
import hashlib
import json
import re

from .flow import JUMPS, ENDS, split_label, destinations
from .lower import Lowerer
from .native_logic import decode, STORES, OPEN, timer_index
from .numeric import memory_words_used
from .indexed import has_indexed_bits
from .model import fail
from .bits import memory_bits_used
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, SERIES, LOADS
from .edge_functions import parse as expression_edge
from .counter_xml import simple as simple_counter
from .subroutine_contexts import call_target, decoded_rung, static_operand_view


def needed(program):
    for raw in program.rungs:
        label, rung = split_label(raw)
        if call_target(rung) is not None:
            if (
                label is None
                and len(rung) == 2
                and (
                    rung[0] == "LD %I0.0"
                    or re.fullmatch(r"LD %M(?:0|[1-9][0-9]*)", rung[0])
                )
            ):
                continue
            return True
        if rung[0].startswith("BLK "):
            if rung[0].startswith("BLK %TM") and any(
                len(parts) == 2
                and parts[0] in ("LD", "LDN", "AND", "ANDN")
                and parts[1] in ("0", "1")
                for line in rung
                for parts in [line.split(maxsplit=1)]
            ):
                return True  # Timer-pin SHORT/OPEN graphs are not yet bound.
            if rung[0].startswith("BLK %C"):
                if simple_counter(rung):
                    continue
                return True
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
                and not any(
                    line.split(maxsplit=1)[0] in EDGE_OPS
                    or expression_edge(line.split(maxsplit=1)[0]) is not None
                    for line in rung
                )
            ):
                continue
            return True
        instructions = decode(rung)
        if any(
            op in ("R", "S", "CU", "CD") and arg.startswith("%C") and "." not in arg
            for op, arg in instructions
        ):
            return True
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
    original_rungs = program.rungs
    # LDN/ANDN digit operands are valid in the local IR, but the installed
    # editor accepts native SHORT/OPEN only with positive LD/AND opcodes.
    canonical = []
    for rung in program.rungs:
        lines = []
        for line in rung:
            parts = line.split()
            if (
                len(parts) == 2
                and parts[0] in ("LDN", "ANDN")
                and parts[1] in ("0", "1")
            ):
                parts = [parts[0][:-1], "1" if parts[1] == "0" else "0"]
            lines.append(" ".join(parts))
        canonical.append(lines)
    if canonical != program.rungs:
        program = copy.deepcopy(program)
        program.rungs = canonical
    if not needed(program):
        return program
    if has_indexed_bits(program):
        fail("indexed-bit normalization bounds/profile are unverified")
    resources = static_operand_view(program)
    bits = memory_bits_used(resources)
    lower = Lowerer(
        bits,
        memory_words_used(resources),
        materialize_constants=bool(program.subroutines),
    )
    used_labels = set(destinations(program))
    free_labels = iter(f"%L{i}" for i in range(64) if f"%L{i}" not in used_labels)

    def new_guard_label(purpose="safe comparison evaluation"):
        result = next(free_labels, None)
        if result is None:
            fail(
                f"normalization needs a spare label for {purpose}; compiler overhead limitation"
            )
        return result

    lower.program.timers = copy.deepcopy(program.timers)
    lower.program.counters = copy.deepcopy(program.counters)
    lower.program.communications = copy.deepcopy(program.communications)
    lower.program.metadata = copy.deepcopy(program.metadata)
    lower.program.subroutines = copy.deepcopy(program.subroutines)
    acc = lower.bit("native_accumulator")
    expression_states = {}
    resets = []
    exit_label = None
    exit_count = 0

    def expression_state(op):
        if op not in expression_states:
            expression_states[op] = lower.bit(
                "expression_history_" + op, persistent=True
            )
            resets.append(["LD %S13", "R " + expression_states[op]])
        return expression_states[op]

    for index, raw in enumerate(program.rungs):
        label, rung = split_label(raw)
        rung = [" ".join(line.split()) for line in rung]
        first = len(lower.program.rungs)
        origins = program.metadata.get("rung_origins")
        lower.origin = (
            copy.copy(origins[index])
            if origins is not None
            else {"generated": f"native logic source rung {index}"}
        )
        probe = copy.copy(program)
        probe.rungs = [raw]
        if (
            rung[0].startswith("BLK ")
            and rung[0].split(maxsplit=1)[1] in program.communications
        ):
            # Native communication pin profiles remain authoritative. A copied
            # raw digit must not become an accepted M contact just because an
            # unrelated expression requires whole-program normalization.
            lower.append(rung)
        elif not needed(probe):
            # Each rung begins with a load/block, so its accumulator is not
            # live into the next one. Preserve already-canonical rungs.
            lower.rung(*rung)
        elif (
            len(rung) == 3
            and rung[0].split(maxsplit=1)[0] in LOADS
            and not rung[0].startswith("LDN [")
            and expression_edge(rung[1]) is not None
            and rung[2].split(maxsplit=1)[0] in ("ST", "S", "R")
        ):
            state = expression_state(rung[1])
            snapshot = lower.bit("expression_edge_input")
            lower.rung(rung[0], "ST " + snapshot)
            rising = rung[1].startswith("RISING")
            lower.rung(
                "LD " + (snapshot if rising else state),
                "ANDN " + (state if rising else snapshot),
                rung[2],
            )
            lower.rung("LD " + snapshot, "ST " + state)
        else:
            saved = []
            groups = []
            for op, arg in decoded_rung(rung):
                if op == "CALL_SR":
                    # The call ends its source rung. Its predicate is captured
                    # before the leaf can mutate shared words/bits or outputs.
                    lower.rung("LD " + acc, "SR" + arg)
                    continue
                if op in ENDS:
                    if exit_label is None:
                        exit_label = new_guard_label("scan exit lowering")
                    lower.jump(
                        exit_label, "1" if op == "END" else acc, negate=op == "ENDCN"
                    )
                    exit_count += 1
                    continue
                if expression_edge(op) is not None:
                    state = expression_state(op)
                    result = lower.bit("expression_edge_result")
                    rising = op.startswith("RISING")
                    lower.rung(
                        "LD " + (acc if rising else state),
                        "ANDN " + (state if rising else acc),
                        "ST " + result,
                    )
                    lower.assign(state, acc)
                    lower.assign(acc, result)
                    continue
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
                elif (
                    op in ("R", "S", "CU", "CD")
                    and arg.startswith("%C")
                    and "." not in arg
                ):
                    lower.rung("BLK " + arg, "LD " + acc, op, "END_BLK")
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
    if exit_label is not None:
        lower.origin = {"generated": "scan exit anchor after all source rungs"}
        lower.label(exit_label)
    prefix = lower.constant_rungs + resets
    lower.program.rungs = prefix + lower.program.rungs
    lower.program.metadata["rung_origins"] = [
        {"generated": "native logic constants/state initialization"} for _ in prefix
    ] + lower.origins
    lower.program.symbols.update(program.symbols)
    normalized = lower.storage.finalize(lower.program, lower.constants)
    normalized.metadata["native_logic_normalization"] = {
        "original_rungs": len(original_rungs),
        "expanded_rungs": len(normalized.rungs),
        "original_il_sha256": hashlib.sha256(
            json.dumps(original_rungs, separators=(",", ":")).encode()
        ).hexdigest(),
        "method": "explicit accumulator/stack snapshots; existing series contacts, coils and Timer blocks",
    }
    if exit_count:
        normalized.metadata["scan_exit_lowering"] = {
            "end_instructions": exit_count,
            "method": "conditional Jump to one final scan-exit anchor",
            "native_end_graph_binding": "unverified",
            "scope": "current master task; no controller STOP or task scheduling model",
        }
    if expression_states:
        normalized.metadata["expression_edge_expansion"] = {
            "rising": sum(op.startswith("RISING") for op in expression_states),
            "falling": sum(op.startswith("FALLING") for op in expression_states),
            "persistent_memory_bits": len(expression_states),
            "initial_history": False,
            "policy": "snapshot input before output/state writes; history advances per execution",
        }
    validate(normalized)
    return normalized
