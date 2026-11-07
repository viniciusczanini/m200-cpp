"""Conservative SMBP subset reader and template-preserving candidate writer.

No public schema or official-editor verification is available. These outputs are
experimental, even when their IL/graph representations agree locally.
"""

import hashlib
import copy
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .il import validate
from .config import configuration, unique_tree
from .model import Program, SubroutineDefinition, address, fail
from .subroutine_xml import read_subroutines, write_subroutines, Subroutine
from .subroutine_contexts import call_target, context_view, context_views, static_operand_view
from .subroutine_native import origin_comment as sr_origin_comment, import_origins as sr_import_origins
from .subroutine_graph import (
    read_graph as check_subroutine_call_graph,
    graphics as subroutine_call_graphics,
    _rung_surface,
)
from .timer_profile import BASES, validate_options
from .timer_xml import (
    read_configs as read_timers, write_configs as write_timers,
    series as timer_graphics, check_graph as check_timer_graph,
)
from .flow import ENDS, split_label
from .indexed import has_indexed, direct_word_limit, has_indexed_bits
from .bits import memory_bits_used
from .edges import SERIES, contact_type
from .boolean_graph import graphics as expression_graphics, validate_profile as validate_boolean_profile
from .boolean_banks import BooleanConfig, config as boolean_config
from .edge_functions import parse as expression_edge
from .numeric import (
    word_address,
    comparison,
    operation,
    Number,
    is_operation,
    memory_words_used,
)
from .communication import parse_block
from .communication_xml import read_blocks, write_blocks, check_template_channels, check_dynamic_channels
from .communication_graph import (
    import_rung as import_full_communication,
    import_origins as import_full_communication_origins,
    origin_comment as full_communication_origin_comment,
    human_comment as full_communication_human_comment,
    source_human_comment as full_communication_source_human_comment,
    serialized_rungs as communication_serialized_rungs,
    graphics as full_communication_graphics,
)
from .counter_xml import (
    read_configs as read_counters,
    write_configs as write_counters,
    graphics as counter_graphics,
    check_graph as check_counter_graph,
)
from .registers import RegisterConfig
from .sequence_xml import read_sequences, write_sequences
from .sequence_graph import is_block as sequence_block, graphics as sequence_graphics, check_graph as check_sequence_graph
from .sequences import FAMILIES as SEQUENCE_FAMILIES, referenced_ids as sequence_ids
from .register_xml import read_registers, write_registers, RegisterMode
from .register_graph import (
    graphics as register_graphics,
    check_graph as check_register_graph,
)
from .register_il import referenced_ids as register_ids

TARGET = "TM200CE40T"
LEFT_ONLY = {
    "Coil",
    "SetCoil",
    "ResetCoil",
    "Operation",
    "ReadVarBasic",
    "WriteVarBasic",
    "WriteReadVarBasic",
    "Jump",
    "End",
    "EndCn",
}


def element(parent, tag, text=None):
    child = ET.SubElement(parent, tag)
    if text is not None:
        child.text = str(text)
    return child


def parse(path):
    data = Path(path).read_bytes()
    if len(data) > 20_000_000:
        fail("project exceeds the experimental parser size limit")
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError:
        fail("project XML must use UTF-8 encoding")
    if b"\x00" in data:
        fail("project XML must use UTF-8 encoding")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        fail("DTD/entity declarations are not supported")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        fail("invalid XML: " + str(exc))
    if root.tag != "ProjectDescriptor":
        fail("unsupported project root or encrypted project")
    pending = [(root, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 64:
            fail("project XML depth exceeds 64")
        pending.extend((child, depth + 1) for child in node)
    if len(root.findall("HardwareConfiguration/Plc/Cpu")) != 1:
        fail("project must contain exactly one CPU")
    references = root.findall("HardwareConfiguration/Plc/Cpu/Reference")
    if len(references) != 1 or len(references[0]):
        fail("CPU reference must be one scalar")
    actual = references[0].text or "unknown"
    if actual != TARGET:
        fail("source CPU " + actual + "; template/project must target " + TARGET)
    unique_tree(root)
    return root


def graphics(rung, timer_column=3, communication_contact_column=0):
    # Deliberately only series contacts, one action, and one optional Timer.
    # Compound expressions are split into boolean gates by the lowerer.
    _, rung = split_label(rung)
    expression = expression_graphics(rung)
    if expression is not None:
        return expression
    end_type = None
    if any(line.split(maxsplit=1)[0] in ENDS for line in rung):
        # Exact official saves distinguish power-rail END from conditional End:
        # END alone has ten wire cells; ENDC/ENDCN have a preceding predicate.
        if rung == ["END"]:
            return [("Line", "", i) for i in range(10)] + [("End", "", 10)]
        if len(rung) < 2 or rung[-1] not in ("ENDC", "ENDCN"):
            fail("native END graph requires a standalone END or terminal ENDC/ENDCN")
        for i, line in enumerate(rung[:-1]):
            parts = line.split(maxsplit=1)
            allowed = (
                ("LD", "LDN", "LDR", "LDF")
                if i == 0
                else ("AND", "ANDN", "ANDR", "ANDF")
            )
            if len(parts) != 2 or parts[0] not in allowed or parts[1] in ("0", "1"):
                fail(
                    "unverified native END predicate graph; use supported series contacts"
                )
        end_type = "End" if rung[-1] == "ENDC" else "EndCn"
    if any(line.split(maxsplit=1)[0] in ("JMP", "JMPCN") for line in rung):
        fail("SMBP graphics for JMP/JMPCN are unverified; generate a contact and JMPC")
    if rung[0].startswith("BLK "):
        descriptor = rung[0].split()[1]
        if descriptor.startswith(("%READ_VAR", "%WRITE_VAR", "%WRITE_READ_VAR")):
            key, execute, _ = parse_block(rung)
            if len(rung) != 4:
                fail(
                    "SMBP graphical ABORT wiring is not verified; IL output remains available"
                )
            native_kind = key[1:].rstrip("0123456789")
            typ, column = {
                "READ_VAR": ("ReadVarBasic", 2),
                "WRITE_VAR": ("WriteVarBasic", 3),
                "WRITE_READ_VAR": ("WriteReadVarBasic", 1),
            }[native_kind]
            if native_kind == "WRITE_READ_VAR" and (
                execute[0] != "LD" or execute[1] in ("0", "1")
            ):
                fail("unverified WRITE_READ_VAR Execute contact graph")
            if communication_contact_column not in range(column):
                fail("communication contact must precede its block")
            if execute[1].startswith("["):
                fail("SMBP communication comparison input wiring is not verified")
            return (
                [
                    (
                        "NegatedContact" if execute[0] == "LDN" else "NormalContact",
                        execute[1],
                        communication_contact_column,
                    )
                ]
                + [
                    ("Line", "", i)
                    for i in range(column)
                    if i != communication_contact_column
                ]
                + [(typ, key, column)]
            )
        return [(typ, arg, col) for typ, arg, _, col, _ in timer_graphics(rung, timer_column)]
    else:
        items = []
        column = 0
        for line in rung[:-1]:
            if line.startswith("OPER "):
                items.append(
                    ("Comparison", line.split(maxsplit=1)[1][1:-1].strip(), column)
                )
                column += 2
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                fail("project graphics require native logic normalization")
            op, arg = parts
            if op not in SERIES:
                fail("project graphics for this IL operator are not supported")
            if arg.startswith("["):
                if op not in ("LD", "AND"):
                    fail("negated numeric comparison graphics are unsupported")
                items.append(("Comparison", arg[1:-1].strip(), column))
                column += 2
                continue
            if arg in ("0", "1") and op in ("LD", "LDN", "AND", "ANDN"):
                if op.endswith("N"):
                    fail("native literal contacts require positive LD/AND opcodes")
                items.append(("Short" if arg == "1" else "Open", "", column))
                column += 1
                continue
            items.append(
                (
                    contact_type(op),
                    arg,
                    column,
                )
            )
            column += 1
        terminal_operation = is_operation(rung[-1])
        end = 9 if terminal_operation else 10
        if column > end:
            fail("rung exceeds Ladder width")
        items += [("Line", "", i) for i in range(column, end)]
        if terminal_operation:
            expression = (
                rung[-1].split(maxsplit=1)[1]
                if rung[-1].startswith("OPER ")
                else rung[-1]
            )
            items.append(("Operation", expression[1:-1].strip(), 9))
        elif end_type is not None:
            items.append((end_type, "", 10))
        else:
            op, arg = rung[-1].split()
            items.append(
                (
                    {"ST": "Coil", "S": "SetCoil", "R": "ResetCoil", "JMPC": "Jump"}[
                        op
                    ],
                    arg,
                    10,
                )
            )
    return items


def check_graph(rung_node, lines, program=None, level_token=None):
    label, lines = split_label(lines)
    if sequence_block(lines):
        check_sequence_graph(rung_node, lines)
        return
    if re.fullmatch(r"BLK %R[0-9]+", lines[0]):
        if label is not None:
            # The wrapper owns label validation. Register geometry is the
            # unchanged block graph, independent of the enclosing POU label.
            rung_node = copy.deepcopy(rung_node)
            rung_node.find("Label").text = ""
            instructions = rung_node.find("InstructionLines")
            instructions.remove(instructions[0])
        check_register_graph(rung_node, lines)
        return
    if program is not None and program.subroutines:
        _rung_surface(rung_node)
        if call_target(lines) is not None:
            check_subroutine_call_graph(rung_node)
            return
        if _check_observed_subroutine_tautology(rung_node, lines):
            return
    native_timer_graph = any(
        e.findtext("ElementType") == "Timer" for e in rung_node.findall("LadderElements/LadderEntity")
    )
    if lines[0].startswith("BLK %TM") or native_timer_graph:
        resources = (
            None if program is None else {("C", i) for i in program.counters}
            | {("TM", i) for i in program.timers}
            | {("COMM", key) for key in program.communications}
        )
        check_timer_graph(rung_node, lines, resources, level_token)
        return
    if lines[0].startswith("BLK %C"):
        resources = (
            None
            if program is None
            else {("C", i) for i in program.counters}
            | {("TM", i) for i in program.timers}
            | {("COMM", key) for key in program.communications}
        )
        check_counter_graph(rung_node, lines, resources)
        return
    graph = rung_node.find("LadderElements")
    if graph is None or not len(graph):
        if rung_node.findtext("IsLadderSelected", "false").lower() == "true":
            fail("selected Ladder rung has no graphics")
        return
    native_end = any(line.split(maxsplit=1)[0] in ENDS for line in lines)
    if native_end and (rung_node.attrib or graph.attrib):
        fail("unknown native END graph attributes")
    actual = []
    rows = set()
    for e in graph:
        if e.tag != "LadderEntity":
            fail("unknown graphical element container")
        if native_end and (e.attrib or any(c.attrib for c in e)):
            fail("unknown native END graph attributes")
        if any(
            c.tag
            not in (
                "ElementType",
                "Descriptor",
                "Comment",
                "Symbol",
                "Row",
                "Column",
                "ChosenConnection",
                "ComparisonExpression",
                "OperationExpression",
            )
            for c in e
        ):
            fail("unknown Ladder element fields")
        for child in e:
            if len(child):
                fail("Ladder value must be scalar: " + child.tag)
        try:
            row = int(e.findtext("Row", "0"))
            column = int(e.findtext("Column", "-1"))
        except ValueError:
            fail("invalid Ladder coordinates")
        if row not in (0, 1):
            fail("parallel/multi-row Ladder is outside the supported import subset")
        if native_end and row != 0:
            fail("unverified native END graph row; observed bindings use row zero")
        rows.add(row)
        typ = e.findtext("ElementType", "")
        expr_field = {
            "Comparison": "ComparisonExpression",
            "Operation": "OperationExpression",
        }.get(typ, "Descriptor")
        arg = e.findtext(expr_field, "")
        for field in ("Descriptor", "ComparisonExpression", "OperationExpression"):
            if field != expr_field and e.findtext(field, ""):
                fail("unexpected Ladder expression field")
        if typ in ("Comparison", "Operation"):
            arg = numeric_graph(typ, arg)
        expected_connection = "Left" if typ in LEFT_ONLY else "Left, Right"
        observed_operation_connection = (
            typ == "Operation"
            and column == 9
            and is_operation(lines[-1])
            and e.findtext("ChosenConnection", "") == "Left, Right"
        )
        if (
            e.findtext("ChosenConnection", "") != expected_connection
            and not observed_operation_connection
        ):
            fail("unsupported Ladder connections")
        actual.append((typ, arg, column))
    if len(rows) != 1:
        fail("mixed Ladder rows are outside the supported series subset")
    timer_columns = [col for typ, _, col in actual if typ == "Timer"]
    comm_contact_column = 0
    if lines[0].startswith("BLK ") and any(
        t in ("ReadVarBasic", "WriteVarBasic", "WriteReadVarBasic")
        for t, _, _ in actual
    ):
        contacts = [
            col for t, _, col in actual if t in ("NormalContact", "NegatedContact")
        ]
        if len(contacts) != 1:
            fail("communication block requires one series input contact")
        comm_contact_column = contacts[0]
    if timer_columns and (len(timer_columns) != 1 or not lines[0].startswith("BLK ")):
        fail("unexpected Timer graphical element")
    expected = [
        (t, numeric_graph(t, a) if t in ("Comparison", "Operation") else a, c)
        for t, a, c in graphics(
            lines, timer_columns[0] if timer_columns else 3, comm_contact_column
        )
    ]
    if sorted(actual) != sorted(expected):
        fail("IL and Ladder graphics do not agree")


def _check_observed_subroutine_tautology(node, lines):
    """Only the actual SR fixture's parallel I1/NOT I1 shape, not general LD."""
    if len(lines) != 3 or lines[:2] != ["LD %I0.1", "ORN %I0.1"]:
        return False
    graph = node.find("LadderElements")
    if graph is None or not len(graph):
        return False  # Existing ordinary IL-only handling still applies.
    if is_operation(lines[-1]):
        typ, end, connection = "Operation", 9, "Left, Right"
        target = numeric_graph(typ, lines[-1][1:-1])
    elif lines[-1].startswith("ST "):
        typ, end, connection = "Coil", 10, "Left"
        target = lines[-1].split(maxsplit=1)[1]
    else:
        fail("unverified SR parallel terminal action")
    expected = [
        ("NormalContact", "%I0.1", "0", "0", "Down, Left, Right"),
        ("NegatedContact", "%I0.1", "1", "0", "Up, Left"),
        *[("Line", "", "0", str(i), "Left, Right") for i in range(1, end)],
        (typ, target, "0", str(end), connection),
    ]
    actual = []
    for entity in graph:
        element_type = entity.findtext("ElementType", "")
        field = "OperationExpression" if element_type == "Operation" else "Descriptor"
        value = entity.findtext(field, "")
        for other in ("Descriptor", "OperationExpression", "ComparisonExpression"):
            if other != field and entity.findtext(other, ""):
                fail("unverified SR parallel graph expression field")
        if element_type == "Operation":
            value = numeric_graph(element_type, value)
        actual.append(
            (
                element_type,
                value,
                entity.findtext("Row"),
                entity.findtext("Column"),
                entity.findtext("ChosenConnection"),
            )
        )
    if sorted(actual) != sorted(expected):
        fail("SR parallel IL and observed native graph do not agree")
    return True


def _resource_context_views(program):
    """Nonexecuting operand/allocation views; never flatten execution contexts."""
    for _, view in context_views(program):
        yield view


def numeric_graph(typ, expression):
    # Parse token boundaries; removing whitespace could turn MW40 00 into MW4000.
    parsed = (
        comparison("[" + expression + "]")
        if typ == "Comparison" and ":=" not in expression
        else operation("[" + expression + "]")
    )

    def freeze(value):
        if isinstance(value, Number):
            return (value.kind, value.code)
        if isinstance(value, list):
            return tuple(freeze(v) for v in value)
        return value

    return tuple(freeze(v) for v in parsed)


def section_base(pous):
    """Native editor uses zero; earlier observed files use one-based sections."""
    if pous is None or not len(pous):
        return 1
    value = pous[0].findtext("SectionNumber")
    if value not in ("0", "1"):
        fail("POU section order is unsupported or inconsistent")
    return int(value)


def load_project(path):
    root = parse(path)
    sw = configuration(root)
    p = Program()
    from .scalar_constants import read_configs as read_constants
    p.constants, constant_symbols = read_constants(root.find("SoftwareConfiguration"))
    p.symbols.update(constant_symbols)
    constant_allocation = sw.find("ConstantWordsMemoryAllocation")
    if constant_allocation is not None and constant_allocation.findtext("Allocation") == "Manual":
        count = constant_allocation.findtext("ForcedCount", "")
        if re.fullmatch(r"[1-9][0-9]{0,2}", count) is None:
            fail("invalid constant memory allocation")
        p.metadata["constant_words"] = int(count)
    p.counters = read_counters(sw)
    from .rtc_xml import read_rtcs, read_schedules
    p.rtcs = read_rtcs(sw)
    p.schedules = read_schedules(sw)
    graph_nodes = []
    origins = []
    full_groups = []
    p.communications = read_blocks(sw)
    check_template_channels(root, p.communications)
    native_subroutines = read_subroutines(sw)
    if native_subroutines:
        pous = sw.find("Pous")
        if (
            root.findtext("ManagementLevel") != "FunctLevelMan21_0"
            or root.findtext(
                "HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/SubroutinesMax"
            )
            != "64"
        ):
            fail("unverified native SR functional-level/capacity profile")
        if (
            pous is None
            or len(pous) != 1
            or pous[0].findtext("SectionNumber") != "0"
        ):
            fail(
                "native SR import requires one Master section 0"
            )
        for number, definition in native_subroutines.items():
            if definition.section_number == 0:
                fail("native SR section identity collides with its master")
            context_lines, context_origins, context_groups = [], [], []
            for native_index, node in enumerate(definition.rungs):
                _, lines = _rung_surface(node)
                origin = {
                    "file": Path(path).name,
                    "generated": "native SR%s section %s rung %s | %s"
                    % (
                        number,
                        definition.section_number,
                        native_index,
                        node.findtext("Name", ""),
                    ),
                }
                canonical = import_full_communication(node, lines, root, p.communications)
                if canonical is None:
                    context_lines.append(lines)
                    context_origins.extend(sr_import_origins(node, origin))
                    graph_nodes.append((node, lines))
                elif len(canonical) == 1:
                    context_lines.extend(canonical)
                    context_origins.extend(sr_import_origins(node, origin))
                else:
                    group_origins = import_full_communication_origins(node, origin)
                    context_groups.append({
                        "key": split_label(lines)[1][0].split(maxsplit=1)[1],
                        "canonical_start": len(context_lines),
                        "canonical_rungs": 5,
                        "source_instruction_lines": len(lines),
                        "origin": {"section": definition.section_number,
                            "native_rung": native_index,
                            "name": node.findtext("Name", ""),
                            "main_comment": full_communication_human_comment(node)},
                        "source_origins": group_origins,
                    })
                    context_lines.extend(canonical)
                    context_origins.extend(group_origins)
            p.subroutines[number] = SubroutineDefinition(
                number,
                definition.name,
                definition.section_number,
                context_lines,
                context_origins,
            )
            if context_groups:
                p.metadata.setdefault("subroutine_full_pin_groups", {})[str(number)] = context_groups
    p.timers = read_timers(sw)
    pous = sw.find("Pous")
    if pous is not None:
        for section, pou in enumerate(pous, section_base(pous)):
            if pou.findtext("SectionNumber") != str(section):
                fail("POU section order is unsupported or inconsistent")
            if any(c.tag not in ("Name", "SectionNumber", "Rungs") for c in pou):
                fail("unsupported POU properties")
            for child in pou:
                if child.tag != "Rungs" and len(child):
                    fail("POU value must be scalar: " + child.tag)
            rungs = pou.find("Rungs")
            if rungs is None:
                continue
            for native_index, r in enumerate(rungs):
                if r.tag != "RungEntity" or any(
                    c.tag
                    not in (
                        "LadderElements",
                        "InstructionLines",
                        "Name",
                        "MainComment",
                        "Label",
                        "IsLadderSelected",
                    )
                    for c in r
                ):
                    fail("unsupported rung properties")
                for child in r:
                    if child.tag not in ("LadderElements", "InstructionLines") and len(
                        child
                    ):
                        fail("rung value must be scalar: " + child.tag)
                instructions = r.find("InstructionLines")
                if instructions is None:
                    fail("rung has no IL representation")
                lines = []
                for instruction in instructions:
                    if instruction.tag != "InstructionLineEntity" or any(
                        c.tag not in ("InstructionLine", "Comment") for c in instruction
                    ):
                        fail("unknown instruction fields")
                    for child in instruction:
                        if len(child):
                            fail("instruction value must be scalar: " + child.tag)
                    text = instruction.findtext("InstructionLine", "").strip()
                    lines.append(" ".join(text.split()))
                label, _ = split_label(lines)
                if r.findtext("Label", "") != (label or ""):
                    fail("rung label field and actual instruction label disagree")
                native_origin = {
                    "section": section,
                    "native_rung": native_index,
                    "name": r.findtext("Name", ""),
                    "main_comment": full_communication_human_comment(r),
                }
                origin = {
                    "file": Path(path).name,
                    "generated": "native section %s rung %s | %s"
                    % (section, native_index, native_origin["name"]),
                }
                canonical = import_full_communication(r, lines, root, p.communications)
                if canonical is None:
                    p.rungs.append(lines)
                    origins.append(origin)
                    graph_nodes.append((r, lines))
                elif len(canonical) == 1:
                    # An observed bare Execute/Abort graph is already canonical:
                    # one update, one source origin, no full-pin audit payload.
                    p.rungs.extend(canonical)
                    origins.append(origin)
                else:
                    group_origins = import_full_communication_origins(r, origin)
                    full_groups.append(
                        {
                            "key": split_label(lines)[1][0].split(maxsplit=1)[1],
                            "canonical_start": len(p.rungs),
                            "canonical_rungs": 5,
                            "source_instruction_lines": len(lines),
                            "origin": native_origin,
                            "source_origins": group_origins,
                        }
                    )
                    p.rungs.extend(canonical)
                    origins.extend(group_origins)
    for bit in sw.findall("MemoryBits/MemoryBit"):
        addr = bit.findtext("Address", "")
        address(addr, True)
        p.symbols[addr] = bit.findtext("Symbol", "")
    for collection, entry in (
        ("MemoryWords", "MemoryWord"),
        ("MemoryDoubleWords", "MemoryDoubleWord"),
        ("MemoryFloats", "MemoryFloat"),
    ):
        for word in sw.findall(collection + "/" + entry):
            p.symbols[word.findtext("Address")] = word.findtext("Symbol", "")
    if full_groups or p.subroutines:
        p.metadata["rung_origins"] = origins
    if full_groups:
        p.metadata["native_full_pin_groups"] = full_groups
    p.registers = {
        i: RegisterConfig(mode.value)
        for i, mode in read_registers(sw, register_ids(static_operand_view(p).rungs)).items()
    }
    if any(expression_edge(line.split(maxsplit=1)[0]) is not None for rung in static_operand_view(p).rungs for line in rung if line.strip()):
        p.boolean = BooleanConfig(native_expression_edges=True)
    validate_boolean_profile(p, root.findtext("ManagementLevel"))
    sequence_rungs = static_operand_view(p).rungs
    for name, configs in read_sequences(
        sw,
        referenced_sbrs=sequence_ids(sequence_rungs, "SBR"),
        referenced_scs=sequence_ids(sequence_rungs, "SC"),
    ).items():
        setattr(p, name, configs)
    _sequence_profile(p, root)
    _register_profile(p, root)
    from .rtc_xml import profile as rtc_profile
    rtc_profile(p, root)
    validate(p)
    check_dynamic_channels(root, p)
    # Validate the complete IL before examining its graphics. A status may be
    # read before its configured FB is called later in the same scan.
    validate_allocations(sw, p, root.findtext("ManagementLevel"))
    for node, lines in graph_nodes:
        check_graph(node, lines, p, root.findtext("ManagementLevel"))
    p.metadata.update(
        {
            "official_editor": "pending",
            "physical_plc": "pending",
            "project_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "project_version": root.findtext("ProjectVersion", ""),
            "synthetic_template": root.findtext("Name", "").startswith("SYNTHETIC")
            or root.findtext("HardwareConfiguration/Plc/Cpu/Name", "").startswith(
                "SYNTHETIC"
            ),
        }
    )
    return p


def _sequence_profile(program, root):
    maxima = {"SBR": "ShiftBitRegistersMax", "SC": "StepCountersMax", "DR": "DrumsMax"}
    for family, name in SEQUENCE_FAMILIES.items():
        if getattr(program, name) and (root.findtext("ManagementLevel") != "FunctLevelMan21_0" or root.findtext("HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/" + maxima[family]) != "8"):
            fail("native sequence export requires identified CE40T/Man21 capacity8; active acceptance pending")


def _register_profile(program, root):
    if program.registers and (
        root.findtext("ManagementLevel") != "FunctLevelMan21_0"
        or root.findtext(
            "HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/LfRegistersMax"
        )
        != "4"
    ):
        fail(
            "unverified native Register profile; require observed Man21 and four-register CE40T capacity"
        )


def validate_timer_profile(program, level_token=None):
    validate_options(program, level_token)


def validate_allocations(sw, program, level_token=None):
    validate_timer_profile(program, level_token)
    views = list(_resource_context_views(program))
    if any(has_indexed_bits(view) for view in views):
        fail("indexed-bit functional-level mapping is unverified for SMBP")
    bits = set().union(*(memory_bits_used(view) for view in views))
    words_used = set().union(*(memory_words_used(view) for view in views))
    from .scalar_constants import extent as constant_extent
    requirements = {
        "ConstantWordsMemoryAllocation": (512, constant_extent(program)),
        "MemoryWordsMemoryAllocation": (
            8000,
            max(words_used, default=-1) + 1,
        ),
        "MemoryBitsMemoryAllocation": (1024, max(bits, default=-1) + 1),
        "TimersMemoryAllocation": (255, max(program.timers, default=-1) + 1),
        "RegistersMemoryAllocation": (4, max(program.registers, default=-1) + 1),
        "SchsMemoryAllocation": (16, max(program.schedules, default=-1) + 1),
        "DrumsMemoryAllocation": (8, max(program.drums, default=-1) + 1),
        "SbrsMemoryAllocation": (8, max(program.shift_bit_registers, default=-1) + 1),
        "ScsMemoryAllocation": (8, max(program.step_counters, default=-1) + 1),
    }
    for tag, (capacity, required) in requirements.items():
        node = sw.find(tag)
        if node is None:
            continue
        count = node.findtext("ForcedCount")
        if count is not None and (
            not re.fullmatch(r"0|[1-9][0-9]{0,3}", count) or int(count) > capacity
        ):
            fail("invalid " + tag + " allocation count")
        if node.findtext("Allocation") == "Manual" and (
            count is None or int(count) < required
        ):
            fail(tag + " allocation does not cover all referenced memory/buffers")
    resources = static_operand_view(program)
    if has_indexed(resources):
        bound = direct_word_limit(resources)
        words = sw.find("MemoryWordsMemoryAllocation")
        forced = words.findtext("ForcedCount") if words is not None else None
        mode = words.findtext("Allocation") if words is not None else None
        if mode not in ("Automatic", "Manual"):
            fail("indexed bound with an omitted/default allocation mode is unverified")
        if max(memory_words_used(resources), default=-1) + 1 > bound or (
            mode == "Manual" and forced is not None and int(forced) != bound
        ):
            fail(
                "indexed bound from excess Manual allocation or symbol-only extent is unverified"
            )


def _subroutine_semantics(program):
    # Generated native-file origins differ; every executable/identity field is
    # authoritative and must survive staged readback.
    return {
        number: (value.number, value.name, value.section_number, value.rungs)
        for number, value in program.subroutines.items()
    }


def _leaf_graphics(lines):
    _, body = split_label(lines)
    if sequence_block(body):
        return sequence_graphics(body)
    if body and body[0].startswith("BLK %TM"):
        return timer_graphics(body)
    if body and body[0].startswith("BLK %C"):
        return counter_graphics(body)
    if body and re.fullmatch(r"BLK %R[0-9]+", body[0]):
        return register_graphics(body)
    # END variants remain native returns in this context. Other logic has been
    # normalized with the same supported serializers as Master, without inlining.
    return [
        (t, a, 0, c, "Left" if t in LEFT_ONLY else "Left, Right")
        for t, a, c in graphics(lines)
    ]


def _sr_export_profile(program, root, sw):
    if not program.subroutines:
        return
    pous = sw.find("Pous")
    if (
        root.findtext("ManagementLevel") != "FunctLevelMan21_0"
        or root.findtext(
            "HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/SubroutinesMax"
        )
        != "64"
        or pous is None
        or len(pous) != 1
        or pous[0].findtext("SectionNumber") != "0"
    ):
        fail(
            "unverified native SR export profile; require Man21, Master0 and 64-SR capacity"
        )
    if any(value.section_number == 0 for value in program.subroutines.values()):
        fail("native SR section identity collides with Master section 0")


def _write_rung_body(rung, lines, items, explicit_descriptors=False):
    graph = element(rung, "LadderElements")
    for typ, arg, row, column, connection in items:
        entity = element(graph, "LadderEntity")
        element(entity, "ElementType", typ)
        if arg or explicit_descriptors:
            field = {
                "Comparison": "ComparisonExpression",
                "Operation": "OperationExpression",
            }.get(typ, "Descriptor")
            element(entity, field, arg)
            if field == "Descriptor":
                element(entity, "Comment", "")
                element(entity, "Symbol", "")
        element(entity, "Row", row)
        element(entity, "Column", column)
        element(entity, "ChosenConnection", connection)
    il = element(rung, "InstructionLines")
    for line in lines:
        instruction = element(il, "InstructionLineEntity")
        element(instruction, "InstructionLine", line)
        element(instruction, "Comment", "")


def write_project(program, template, destination):
    validate(program)
    cfg = boolean_config(program)
    if cfg.word_objects:
        fail("Boolean IO word image SMBP binding belongs to active module configuration; no synthetic hardware is emitted")
    if has_indexed_bits(program):
        fail("indexed-bit functional-level mapping is unverified for SMBP")
    from .ladder_lowering import normalize

    root = parse(template)
    sw = configuration(root)
    _register_profile(program, root)
    from .rtc_xml import profile as rtc_profile
    rtc_profile(program, root)
    _sequence_profile(program, root)
    _sr_export_profile(program, root, sw)
    validate_timer_profile(program, root.findtext("ManagementLevel"))
    validate_boolean_profile(program, root.findtext("ManagementLevel"))
    program = normalize(program)
    first_section = section_base(sw.find("Pous"))
    check_template_channels(root, program.communications)
    from .scalar_constants import write_configs as write_constants
    write_constants(program, sw)
    check_dynamic_channels(root, program)
    write_blocks(program, sw)
    from .rtc_xml import write_rtcs, write_schedules
    write_rtcs(program, sw)
    write_schedules(program, sw)
    write_counters(program, sw)
    write_sequences(program, sw)
    write_registers(
        {i: RegisterMode(cfg.mode) for i, cfg in program.registers.items()}, sw
    )
    for name in (
        "Pous",
        "Timers",
        "MemoryBits",
        "MemoryBitsMemoryAllocation",
        "TimersMemoryAllocation",
        "RegistersMemoryAllocation",
        "DrumsMemoryAllocation",
        "SbrsMemoryAllocation",
        "ScsMemoryAllocation",
        "MemoryWords",
        "MemoryDoubleWords",
        "MemoryFloats",
        "MemoryWordsMemoryAllocation",
    ):
        old = sw.find(name)
        if old is not None:
            sw.remove(old)
    pous = element(sw, "Pous")
    pou = element(pous, "ProgramOrganizationUnits")
    element(pou, "Name", "Generated C++ - EXPERIMENTAL")
    element(pou, "SectionNumber", first_section)
    rungs = element(pou, "Rungs")
    for i, lines, full_communication, consumed in communication_serialized_rungs(
        program, root
    ):
        r = element(rungs, "RungEntity")
        _, body = split_label(lines)
        items = (
            full_communication_graphics(full_communication)
            if full_communication is not None
            else subroutine_call_graphics(body)
            if program.subroutines and call_target(body) is not None
            else timer_graphics(body)
            if body[0].startswith("BLK %TM")
            else sequence_graphics(body)
            if sequence_block(body)
            else counter_graphics(body)
            if body[0].startswith("BLK %C")
            else register_graphics(body)
            if re.fullmatch(r"BLK %R[0-9]+", body[0])
            else [
                (t, a, 0, c, "Left" if t in LEFT_ONLY else "Left, Right")
                for t, a, c in graphics(lines)
            ]
        )
        _write_rung_body(
            r,
            lines,
            items,
            full_communication is not None
            or (bool(program.subroutines) and call_target(body) is not None),
        )
        origin = program.metadata.get("rung_origins", [])
        source = "; ".join(
            "%s:%s:%s"
            % (
                location.get("file", "generated"),
                location.get("line", ""),
                location.get("column", ""),
            )
            for location in (
                origin[j] if j < len(origin) else {} for j in range(i, i + consumed)
            )
        )
        element(r, "Name", "cpp_%04d" % i)
        comment = (
            full_communication_source_human_comment(program, full_communication)
            + full_communication_origin_comment(
                [origin[j] if j < len(origin) else {} for j in range(i, i + consumed)]
            )
            if full_communication is not None and consumed == 5
            else source + " | Experimental generated logic; official validation pending"
        )
        element(r, "MainComment", comment)
        label, _ = split_label(lines)
        element(r, "Label", label or "")
        element(r, "IsLadderSelected", "true")
    if program.subroutines:
        wrappers = {}
        for number, definition in program.subroutines.items():
            nodes = []
            view = context_view(program, definition)
            for i, lines, full_communication, consumed in communication_serialized_rungs(view, root):
                node = ET.Element("RungEntity")
                label, body = split_label(lines)
                items = (
                    full_communication_graphics(full_communication)
                    if full_communication is not None
                    else timer_graphics(body)
                    if body[0].startswith("BLK %TM")
                    else counter_graphics(body)
                    if body[0].startswith("BLK %C")
                    else register_graphics(body)
                    if re.fullmatch(r"BLK %R[0-9]+", body[0])
                    else _leaf_graphics(lines)
                )
                _write_rung_body(node, lines, items, full_communication is not None)
                element(node, "Name", "cpp_sr%s_%04d" % (number, i))
                origins = [
                    definition.origins[j] if j < len(definition.origins)
                    else {"generated": "SR%s source rung %s" % (number, j)}
                    for j in range(i, i + consumed)
                ]
                element(
                    node,
                    "MainComment",
                    (
                        full_communication_source_human_comment(view, full_communication)
                        + full_communication_origin_comment(origins)
                        if full_communication is not None and consumed == 5
                        else "Experimental generated SR; official validation pending"
                        + sr_origin_comment(origins)
                    ),
                )
                element(node, "Label", label or "")
                element(node, "IsLadderSelected", "true")
                nodes.append(node)
            wrappers[number] = Subroutine(
                number, definition.name, definition.section_number, tuple(nodes)
            )
        write_subroutines(wrappers, sw)
    else:
        # Replace supported template SRs; do not retain hidden executable POUs.
        write_subroutines({}, sw)
    write_timers(program, sw)
    bits = element(sw, "MemoryBits")
    numeric = {
        k: element(sw, k) for k in ("MemoryWords", "MemoryDoubleWords", "MemoryFloats")
    }
    for addr, symbol in sorted(program.symbols.items()):
        if addr.startswith("%K"):
            continue  # Family serializer owns constant metadata.
        if addr.startswith(("%MW", "%MD", "%MF")):
            kind, index = word_address(addr)
            collection, entry = {
                "i16": ("MemoryWords", "MemoryWord"),
                "i32": ("MemoryDoubleWords", "MemoryDoubleWord"),
                "f32": ("MemoryFloats", "MemoryFloat"),
            }[kind]
            e = element(numeric[collection], entry)
            element(e, "Address", addr)
            element(e, "Index", index)
            element(e, "Symbol", re.sub(r"[^A-Za-z0-9_]", "_", symbol) + "_" + addr[1:])
            continue
        e = element(bits, "MemoryBit")
        element(e, "Address", addr)
        element(e, "Index", int(addr[2:]))
        element(e, "Symbol", re.sub(r"[^A-Za-z0-9_]", "_", symbol) + "_" + addr[2:])
    allocation = element(sw, "MemoryBitsMemoryAllocation")
    element(allocation, "Allocation", "Automatic")
    allocation = element(sw, "TimersMemoryAllocation")
    element(allocation, "Allocation", "Automatic")
    allocation = element(sw, "RegistersMemoryAllocation")
    element(allocation, "Allocation", "Automatic")
    for family, tag in (("SBR", "SbrsMemoryAllocation"), ("SC", "ScsMemoryAllocation"), ("DR", "DrumsMemoryAllocation")):
        allocation = element(sw, tag)
        element(allocation, "Allocation", "Automatic")
    required = (
        max(
            set().union(
                *(memory_words_used(view) for view in _resource_context_views(program))
            ),
            default=-1,
        )
        + 1
    )
    if required:
        # Manual/ForcedCount is observed for this exact collection. Do not infer
        # a separate enum from the allocation of bits or timers.
        allocation = element(sw, "MemoryWordsMemoryAllocation")
        element(allocation, "Allocation", "Manual")
        element(allocation, "ForcedCount", required)
    name = root.find("Name")
    if name is not None:
        name.text = "m200-cpp EXPERIMENTAL"
    full = root.find("FullName")
    if full is not None:
        full.text = str(Path(destination).name)
    destination = Path(destination)
    if destination.resolve() == Path(template).resolve():
        fail("output must differ from the template")
    ET.indent(root, space="  ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".m200-candidate-", dir=str(destination.parent)
    ) as temporary:
        candidate = Path(temporary) / "candidate.smbp"
        candidate.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        # Internal validation precedes replacement; never vendor acceptance.
        loaded = load_project(candidate)
        if (
            loaded.rungs != program.rungs
            or loaded.communications != program.communications
            or loaded.timers != program.timers
            or loaded.counters != program.counters
            or loaded.registers != program.registers
            or any(loaded.constants.get(i, 0) != program.constants.get(i, 0) for i in range(512))
            or loaded.rtcs != program.rtcs
            or loaded.schedules != program.schedules
            or loaded.shift_bit_registers != program.shift_bit_registers
            or loaded.step_counters != program.step_counters
            or loaded.drums != program.drums
            or _subroutine_semantics(loaded) != _subroutine_semantics(program)
        ):
            fail("internal XML round trip changed program/configuration")
        os.replace(candidate, destination)
