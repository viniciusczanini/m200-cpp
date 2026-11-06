"""Independent native SR contexts, sharing one controller resource image.

SR0..63 are Free POUs, not inline source functions. Native nested calls are
forbidden (EIO0000003289.04 pp65–66); labels and END remain local to a POU.
"""

import copy
import re
from .model import SubroutineDefinition, fail
from .flow import split_label, destinations
from .native_logic import decode, LOGIC
from .subroutine_graph import _xml_text


def context_view(program, definition=None, *, resources=False):
    """A single executable context; optionally select its referenced FB configs.

    The resource-filtered form is for the existing flat validator/reverse emitter
    only. Runtime and project allocation always use the original shared maps.
    """
    view = copy.copy(program)
    view.rungs = program.rungs if definition is None else definition.rungs
    view.subroutines = {}
    view.metadata = dict(program.metadata)
    if definition is not None:
        view.metadata.pop("rung_origins", None)
        if definition.origins:
            view.metadata["rung_origins"] = definition.origins
        view.metadata.pop("native_full_pin_groups", None)
        groups = program.metadata.get("subroutine_full_pin_groups", {})
        if isinstance(groups, dict) and str(definition.number) in groups:
            view.metadata["native_full_pin_groups"] = groups[str(definition.number)]
    if resources:
        timer_ids = set()
        communication_ids = set()
        for rung in view.rungs:
            for line in rung:
                timer_ids.update(int(i) for i in re.findall(r"%TM([0-9]+)(?:\b|\.)", line))
                communication_ids.update(re.findall(r"%(?:READ_VAR|WRITE_VAR|WRITE_READ_VAR)[0-9]+", line))
        view.timers = {i: cfg for i, cfg in program.timers.items() if i in timer_ids}
        view.communications = {
            key: cfg for key, cfg in program.communications.items()
            if key in communication_ids
        }
    return view


def context_views(program, *, resources=False):
    yield None, context_view(program, resources=resources)
    for number, definition in program.subroutines.items():
        yield number, context_view(program, definition, resources=resources)


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
        fail("SR contexts require nonempty instruction-string lists")
    _, body = split_label(raw)
    if not body:
        fail("SR context rung has no body")
    if not any(line.split(maxsplit=1)[0].startswith("SR") for line in body):
        return None
    match = re.fullmatch(r"SR(0|[1-9][0-9]*)", body[-1])
    if match is None or len(match[1]) > 2 or int(match[1]) >= 64 or len(body) < 2:
        fail("SR calls require canonical terminal conditional SR0..SR63")
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
    if any(not isinstance(value, dict) for value in (
        program.timers, program.counters, program.registers,
        program.communications, program.metadata,
        program.shift_bit_registers, program.step_counters, program.drums,
        program.constants, program.rtcs, program.schedules,
    )):
        fail("invalid shared SR resource or metadata mapping")
    if len(program.subroutines) > 64:
        fail("at most 64 native subroutine identities")
    names, sections = set(), set()
    if not isinstance(program.rungs, list):
        fail("master rungs must be a list")
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
            fail("callee origins must be a list")
        for raw in definition.rungs:
            target = call_target(raw)
            if target is not None:
                fail("native SR nesting is prohibited by the controller profile")
        count += sum(map(len, definition.rungs))
    if count > 10000:
        fail("combined SR context instruction budget exceeded (tool limit 10000)")
    projected = []
    for raw in program.rungs:
        target = call_target(raw)
        if target is not None and target not in program.subroutines:
            fail("undefined SR target")
        projected.append(raw if target is None else raw[:-1] + ["ENDC"])
    # Per-context label resolution must precede any union used for accounting.
    # The flat validator normally requires every FB config to be used. Check
    # those uses across the complete shared application instead of each body.
    used_timers, used_communications, expression_ids = set(), set(), set()
    for number, flat in context_views(program):
        if number is None:
            flat.rungs = projected
        validate_flat(flat, require_resource_use=False)
        references = context_view(program, None if number is None else program.subroutines[number], resources=True)
        used_timers.update(references.timers)
        used_communications.update(references.communications)
        from .edge_functions import parse as expression_edge
        for raw in flat.rungs:
            _, body = split_label(raw)
            # Communication blocks have their own closed decoder.
            if body[0].startswith("BLK ") and body[0].split(maxsplit=1)[1] in flat.communications:
                continue
            for op, _ in decode(body):
                if expression_edge(op) is not None:
                    if op in expression_ids:
                        fail("duplicate expression edge instruction identity across SR contexts: " + op)
                    expression_ids.add(op)
    if used_timers != program.timers.keys():
        fail("unused timer configuration is unsupported across SR contexts")
    if used_communications != program.communications.keys():
        fail("unused communication configuration is unsupported across SR contexts")
    # Communication admission still requires unique update locations. Timer
    # visits follow the G07 shared-identity policy across all contexts/sites.
    communication_updates = set()
    for _, flat in context_views(program):
        for raw in flat.rungs:
            _, body = split_label(raw)
            key = body[0].split(maxsplit=1)[1] if body[0].startswith("BLK ") else None
            if key in program.communications:
                if key in communication_updates:
                    fail("multiply updated communication block across SR contexts")
                communication_updates.add(key)
                continue
    if communication_updates != program.communications.keys():
        fail("unused communication configuration is unsupported across SR contexts")
    declared_labels = set()
    for _, view in context_views(program):
        labels = set(destinations(view))
        if labels & declared_labels:
            fail("native label identities must be unique across the application")
        declared_labels.update(labels)
