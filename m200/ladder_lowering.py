"""Lower actual native IL into existing series Ladder rungs with private bits."""

import copy
import hashlib
import json
import re
from dataclasses import fields as program_fields

from .flow import JUMPS, ENDS, split_label, destinations
from .sequences import INTERNAL_PINS as SEQUENCE_PINS, PINS as SEQUENCE_INPUTS, identity as sequence_identity
from .sequence_graph import is_block as sequence_block, parse_block as sequence_graph_parse
from .register_graph import parse_block as register_graph_parse
from .lower import Lowerer
from .native_logic import decode, STORES, OPEN, timer_index
from .numeric import memory_words_used
from .indexed import has_indexed_bits
from .model import fail
from .bits import memory_bits_used
from .edges import OPS as EDGE_OPS, BASE as EDGE_BASE, SERIES, LOADS
from .edge_functions import parse as expression_edge
from .boolean_banks import config as boolean_config
from .boolean_graph import expression_series
from .counter_xml import simple as simple_counter
from .timer_xml import simple as simple_timer
from .subroutine_contexts import call_target, decoded_rung, static_operand_view


def _direct_local_return(instructions):
    """Match the existing native End/EndCn series graph, within one SR.

    Literal predicates still need a materialized contact for conditional END.
    Master END has a different exit-lowering contract and never uses this path.
    """
    if instructions == [("END", "")]:
        return True
    if not instructions or instructions[-1][0] not in ("ENDC", "ENDCN"):
        return False
    contacts = instructions[:-1]
    if not contacts:
        return False
    width = 0
    for index, (op, arg) in enumerate(contacts):
        allowed = ("LD", "LDN", "LDR", "LDF") if index == 0 else (
            "AND", "ANDN", "ANDR", "ANDF"
        )
        if op not in allowed or arg in ("0", "1"):
            return False
        if arg.startswith("[") and op not in ("LD", "AND"):
            return False
        width += 2 if arg.startswith("[") else 1
    return width <= 10


def needed(program, *, _local_return=False):
    for raw in program.rungs:
        label, rung = split_label(raw)
        if boolean_config(program).native_expression_edges and expression_series(raw) is not None:
            continue
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
        if sequence_block(rung):
            try:
                sequence_graph_parse(rung)
                continue
            except ValueError:
                return True
        if rung[0].startswith("BLK "):
            if re.fullmatch(r"BLK %R[0-9]+", rung[0]):
                try:
                    register_graph_parse(rung)
                    continue
                except ValueError:
                    return True
            if rung[0].startswith("BLK %TM"):
                if simple_timer(rung):
                    continue
                return True
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
        if _local_return and _direct_local_return(instructions):
            continue
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
        # A native IL predicate may be wider than one eleven-column Ladder
        # row. Materialize its accumulator rather than rejecting the algorithm
        # or drawing overlapping contacts/actions.
        width = sum(2 if arg.startswith("[") else 1
                    for op, arg in instructions[:-1] if op in SERIES)
        if width > (9 if instructions[-1][0] == "NUM" else 10):
            return True
    return False


def normalize(
    program, *, _local_return=False, _reserved=None, _reserved_labels=(),
    _contexts_done=False,
):
    from .il import validate, _validate_flat

    def validate_current(value):
        if _local_return:
            _validate_flat(value, require_resource_use=False)
        else:
            validate(value)

    validate_current(program)
    if program.subroutines and not _contexts_done:
        from .subroutine_lowering import normalize_contexts

        return normalize_contexts(program, normalize)
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
    if not needed(program, _local_return=_local_return):
        return program
    if has_indexed_bits(program):
        fail("indexed-bit normalization bounds/profile are unverified")
    resources = static_operand_view(program)
    bits = memory_bits_used(resources)
    words = memory_words_used(resources)
    if _reserved is not None:
        bits = bits | set(_reserved[0])
        words = words | set(_reserved[1])
    context_materialize_constants = (
        bool(program.subroutines) or boolean_config(program).native_expression_edges
    )
    lower = Lowerer(
        bits,
        words,
        # Ordinary SR rungs support the same SHORT/OPEN contacts as Master.
        # Lowerer.rung still materializes literals for BLK/ENDC/ENDCN; SR call
        # predicates retain the existing Master materialization policy.
        materialize_constants=context_materialize_constants,
    )
    used_labels = set(destinations(program))
    used_labels.update(_reserved_labels)
    if program.subroutines:
        from .subroutine_contexts import context_views

        for _, view in context_views(program):
            used_labels.update(destinations(view))
    free_labels = iter(f"%L{i}" for i in range(64) if f"%L{i}" not in used_labels)

    def new_guard_label(purpose="safe comparison evaluation"):
        result = next(free_labels, None)
        if result is None:
            fail(
                f"normalization needs a spare label for {purpose}; compiler overhead limitation"
            )
        return result

    # Rebuilding rungs must preserve every typed resource/configuration image,
    # including constants and families added by other compiler providers.
    for field in program_fields(program):
        if field.name not in {"rungs", "symbols", "metadata", "subroutines"}:
            setattr(lower.program, field.name, copy.deepcopy(getattr(program, field.name)))
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
        # Decomposing LD 0/1; ENDC(N) into an accumulator copy is insufficient:
        # copy fusion can forward that digit back into the native return. Use
        # real constant contacts throughout a return-bearing source rung, while
        # keeping ordinary SR SHORT/OPEN rungs on their existing compact path.
        lower.materialize_constants = context_materialize_constants or (
            _local_return
            and any(line.split(maxsplit=1)[0] in ENDS for line in rung)
        )
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
        elif not needed(probe, _local_return=_local_return):
            # Each rung begins with a load/block, so its accumulator is not
            # live into the next one. Preserve already-canonical rungs.
            lower.rung(*rung)
        elif (
            not boolean_config(program).native_expression_edges
            and len(rung) == 3
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
            register_pins = []
            sequence_pins = {}
            for op, arg in decoded_rung(rung):
                if op in SEQUENCE_PINS:
                    if op == "SEQ_COMMIT":
                        family, _ = sequence_identity(arg)
                        lines = ["BLK " + arg]
                        for pin in SEQUENCE_INPUTS[family]:
                            if pin in sequence_pins:
                                lines += ["LD " + sequence_pins[pin], pin]
                        lower.rung(*lines, "END_BLK")
                        sequence_pins = {}
                    else:
                        sequence_pins[op[4:]] = lower.copy(acc, "sequence_pin")
                    continue
                if op in ("REG_R", "REG_I", "REG_O"):
                    register_pins.append(lower.copy(acc, "register_pin"))
                    if op == "REG_O":
                        lower.rung(
                            "BLK " + arg,
                            "LD " + register_pins[0],
                            "R",
                            "LD " + register_pins[1],
                            "I",
                            "LD " + register_pins[2],
                            "O",
                            "END_BLK",
                        )
                    continue
                if op == "CALL_SR":
                    # The call ends its source rung. Its predicate is captured
                    # before the leaf can mutate shared words/bits or outputs.
                    lower.rung("LD " + acc, "SR" + arg)
                    continue
                if op in ENDS:
                    if _local_return:
                        if op == "END":
                            lower.rung("END")
                        else:
                            lower.rung("LD " + acc, op)
                        continue
                    if exit_label is None:
                        exit_label = new_guard_label("scan exit lowering")
                    lower.jump(
                        exit_label, "1" if op == "END" else acc, negate=op == "ENDCN"
                    )
                    exit_count += 1
                    continue
                if expression_edge(op) is not None:
                    if boolean_config(program).native_expression_edges:
                        lower.rung("LD " + acc, op, "ST " + acc)
                        continue
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
                if op == "RTC_EXEC":
                    lower.rung("LD " + acc, "RTC_EXEC " + arg)
                elif op == "NUM":
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
                    lower.timer(i, program.timers[i], acc, capture=False)
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
    prefix = lower.constant_rungs + ([] if _local_return else resets)
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
    if _local_return and resets:
        # A skipped first-scan call must not suppress RUN initialization. The
        # owner places these in Master, independent of the call predicate.
        # Rewrite the virtual state refs using the allocator's physical symbols.
        states = {
            name: ref for ref, name in normalized.symbols.items()
            if name.startswith("expression_history_")
        }
        normalized.metadata["subroutine_run_initializers"] = [
            ["LD %S13", "R " + states["expression_history_" + op]]
            for op in expression_states
        ]
    validate_current(normalized)
    return normalized
