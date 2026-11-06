"""Ignored prototype leaf contexts. No native graph/SMBP/frontend admission."""

import copy
import re
from .model import SubroutineDefinition, fail
from .flow import split_label, ENDS
from .native_logic import decode, LOGIC
from .subroutine_graph import _xml_text
from .indexed import ANY_INDEXED


def static_operand_view(program):
    """Return a nonexecuting union for static operand accounting only.

    This view is never validated or executed as a flattened program. Master
    and leaf control flow still use their original independent contexts.
    """
    if not program.subroutines:
        return program
    view = copy.copy(program)
    view.rungs = program.rungs + [
        rung for definition in program.subroutines.values() for rung in definition.rungs
    ]
    view.subroutines = {}
    view.metadata = {k: v for k, v in program.metadata.items() if k != "rung_origins"}
    return view


def call_target(raw):
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(line, str) or not line.strip() for line in raw)
    ):
        fail("prototype rungs must be nonempty instruction-string lists")
    _, body = split_label(raw)
    if not body:
        fail("prototype rung has no body")
    if not any(line.split(maxsplit=1)[0].startswith("SR") for line in body):
        return None
    match = re.fullmatch(r"SR(0|[1-9][0-9]*)", body[-1])
    if match is None or len(match[1]) > 2 or int(match[1]) >= 64 or len(body) < 2:
        fail("prototype supports only canonical terminal conditional SR0..SR63")
    for op, _ in decode(body[:-1] + ["ENDC"]):
        if op not in (*LOGIC, "N", "ENDC"):
            fail("SR call predicate must have balanced plain boolean operations")
    return int(match[1])


def decoded_rung(raw):
    _, body = split_label(raw)
    target = call_target(raw)
    return (
        decode(body)
        if target is None
        else decode(body[:-1] + ["ENDC"])[:-1] + [("CALL_SR", str(target))]
    )


def validate_contexts(program, validate_flat):
    if not isinstance(program.subroutines, dict):
        fail("invalid subroutine context mapping")
    if not program.subroutines:
        validate_flat(program)
        return
    if len(program.subroutines) > 64:
        fail("at most64native subroutine identities")
    if program.timers or program.counters or program.communications:
        fail("prototype SR stateful-resource closures are not implemented")
    names, sections = set(), set()
    if not isinstance(program.rungs, list):
        fail("prototype master rungs must be a list")
    count = sum(len(raw) if isinstance(raw, list) else 10001 for raw in program.rungs)
    for number, definition in program.subroutines.items():
        if (
            type(number) is not int
            or not 0 <= number < 64
            or not isinstance(definition, SubroutineDefinition)
            or type(definition.number) is not int
            or definition.number != number
        ):
            fail("invalid subroutine context identity")
        if (
            not isinstance(definition.name, str)
            or not _xml_text(definition.name).strip()
            or definition.name in names
            or type(definition.section_number) is not int
            or not 0 <= definition.section_number <= 2147483647
            or definition.section_number in sections
        ):
            fail("invalid or ambiguous subroutine identity metadata")
        names.add(definition.name)
        sections.add(definition.section_number)
        if not isinstance(definition.rungs, list) or not definition.rungs:
            fail("subroutine requires a nonempty rung sequence")
        if not isinstance(definition.origins, list):
            fail("prototype callee origins must be a list")
        for raw in definition.rungs:
            if isinstance(raw, list) and any(
                isinstance(line, str) and ANY_INDEXED.search(line) for line in raw
            ):
                fail("prototype indexed leaf guard transfers are not implemented")
            target = call_target(raw)
            label, body = split_label(raw)
            if label is not None or target is not None:
                fail("native nested SR/label transfers are outside prototype scope")
            instructions = decode(body)
            if len(instructions) != 1 and any(op == "END" for op, _ in instructions):
                fail(
                    "native unconditional END must be the sole instruction in its rung"
                )
            for op, _ in instructions:
                if op not in (
                    "LD",
                    "LDN",
                    "AND",
                    "ANDN",
                    "OR",
                    "ORN",
                    "XOR",
                    "XORN",
                    "N",
                    "ST",
                    "STN",
                    "S",
                    "R",
                    "NUM",
                    *ENDS,
                ):
                    fail(
                        "prototype supports direct stateless leaf memory/output operations only"
                    )
        flat = copy.copy(program)
        flat.subroutines = {}
        flat.rungs = definition.rungs
        flat.metadata = {
            k: v for k, v in program.metadata.items() if k != "rung_origins"
        }
        if definition.origins:
            flat.metadata["rung_origins"] = definition.origins
        validate_flat(flat)
        count += sum(map(len, definition.rungs))
    if count > 10000:
        fail("combined prototype context instruction budget exceeded")
    projected = []
    for raw in program.rungs:
        target = call_target(raw)
        if target is not None and target not in program.subroutines:
            fail("undefined SR target")
        projected.append(raw if target is None else raw[:-1] + ["ENDC"])
    flat = copy.copy(program)
    flat.subroutines = {}
    flat.rungs = projected
    validate_flat(flat)
