"""Conservative SMBP subset reader and template-preserving candidate writer.

No public schema or official-editor verification is available. These outputs are
experimental, even when their IL/graph representations agree locally.
"""

import hashlib
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .il import validate
from .config import configuration, unique_tree
from .model import Program, Timer, address, fail
from .flow import split_label
from .indexed import has_indexed, direct_word_limit, has_indexed_bits
from .bits import memory_bits_used
from .edges import SERIES, contact_type
from .numeric import (
    word_address,
    comparison,
    operation,
    Number,
    is_operation,
    memory_words_used,
)
from .communication import parse_block
from .communication_xml import read_blocks, write_blocks, check_template_channels
from .counter_xml import (
    read_configs as read_counters,
    write_configs as write_counters,
    graphics as counter_graphics,
    check_graph as check_counter_graph,
)

TARGET = "TM200CE40T"
BASES = {1: "OneMilliSeconds", 100: "OneHundredMilliSeconds", 1000: "OneSecond"}
LEFT_ONLY = {
    "Coil",
    "SetCoil",
    "ResetCoil",
    "Operation",
    "ReadVarBasic",
    "WriteVarBasic",
    "Jump",
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
            if native_kind not in ("READ_VAR", "WRITE_VAR"):
                fail("SMBP graphical WRITE_READ_VAR layout is not verified")
            column = 2 if native_kind == "READ_VAR" else 3
            typ = "ReadVarBasic" if native_kind == "READ_VAR" else "WriteVarBasic"
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
        from .native_logic import timer_body, STORES

        body = timer_body(rung)
        if body is None:
            fail("unsupported function block graphics")
        at = next(i for i, line in enumerate(body) if line.startswith("IN "))
        inputs = body[:at]
        outputs = body[at + 2 :]
        if len(outputs) != 1 or outputs[0].split(maxsplit=1)[0] not in STORES:
            fail("Timer graphics require one supported output action")
        terminal, target = outputs[0].split(maxsplit=1)
        if terminal == "STN":
            fail("STN Timer graphics require native logic normalization")
        items = []
        width = 0
        for i, line in enumerate(inputs):
            parts = line.split(maxsplit=1)
            if len(parts) != 2 or parts[0] not in (
                ("LD", "LDN") if i == 0 else ("AND", "ANDN")
            ):
                fail("Timer input graphics require series contacts or normalization")
            op, arg = parts
            if arg.startswith("["):
                if op not in ("LD", "AND"):
                    fail("negated timer comparison graphics are unsupported")
                typ, arg, span = "Comparison", arg[1:-1].strip(), 2
            else:
                typ, span = (
                    ("NegatedContact" if op in ("LDN", "ANDN") else "NormalContact"),
                    1,
                )
            items.append((typ, arg, width))
            width += span
        if timer_column not in (1, 2, 3) or width > timer_column:
            fail("unverified Timer graphical position")
        items += [("Line", "", i) for i in range(width, timer_column)]
        items += [("Timer", descriptor, timer_column)]
        items += [("Line", "", i) for i in range(timer_column + 2, 10)]
        items.append(
            ({"ST": "Coil", "S": "SetCoil", "R": "ResetCoil"}[terminal], target, 10)
        )
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


def check_graph(rung_node, lines, program=None):
    _, lines = split_label(lines)
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
    actual = []
    rows = set()
    for e in graph:
        if e.tag != "LadderEntity":
            fail("unknown graphical element container")
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
        if e.findtext("ChosenConnection", "") != expected_connection:
            fail("unsupported Ladder connections")
        actual.append((typ, arg, column))
    if len(rows) != 1:
        fail("mixed Ladder rows are outside the supported series subset")
    timer_columns = [col for typ, _, col in actual if typ == "Timer"]
    comm_contact_column = 0
    if lines[0].startswith("BLK ") and any(
        t in ("ReadVarBasic", "WriteVarBasic") for t, _, _ in actual
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


def load_project(path):
    root = parse(path)
    sw = configuration(root)
    p = Program()
    p.counters = read_counters(sw)
    graph_nodes = []
    p.communications = read_blocks(sw)
    check_template_channels(root, p.communications)
    timer_nodes = sw.find("Timers")
    if timer_nodes is not None:
        for t in timer_nodes:
            if t.tag != "TimerTM" or any(
                x.tag
                not in (
                    "Address",
                    "Index",
                    "Type",
                    "Preset",
                    "Base",
                    "Comment",
                    "Symbol",
                    "IsRetentive",
                    "IsDynamicPreset",
                )
                for x in t
            ):
                fail("unsupported timer configuration")
            for child in t:
                if len(child):
                    fail("timer value must be scalar: " + child.tag)
            flags = []
            for tag in ("IsRetentive", "IsDynamicPreset"):
                value = t.findtext(tag, "false")
                if value not in ("true", "false"):
                    fail("unsupported timer boolean: " + tag)
                flags.append(value == "true")
            try:
                index = int(t.findtext("Index", "-1"))
                preset = int(t.findtext("Preset", "9999"))
            except ValueError:
                fail("invalid timer index/preset")
            if index in p.timers or t.findtext("Address") != "%TM" + str(index):
                fail("invalid or duplicate timer")
            base = t.findtext("Base", "")
            if base and base not in BASES.values():
                fail("unsupported timer time base: " + base)
            base_ms = {v: k for k, v in BASES.items()}.get(base, 60000)
            p.timers[index] = Timer(
                t.findtext("Type", "TON"), preset * base_ms, base_ms, *flags
            )
    pous = sw.find("Pous")
    if pous is not None:
        for section, pou in enumerate(pous, 1):
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
            for r in rungs:
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
                p.rungs.append(lines)
                graph_nodes.append((r, lines))
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
    validate(p)
    # Validate the complete IL before examining its graphics. A status may be
    # read before its configured FB is called later in the same scan.
    validate_allocations(sw, p)
    for node, lines in graph_nodes:
        check_graph(node, lines, p)
    p.metadata = {
        "official_editor": "pending",
        "physical_plc": "pending",
        "project_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "project_version": root.findtext("ProjectVersion", ""),
        "synthetic_template": root.findtext("Name", "").startswith("SYNTHETIC")
        or root.findtext("HardwareConfiguration/Plc/Cpu/Name", "").startswith(
            "SYNTHETIC"
        ),
    }
    return p


def validate_timer_profile(program):
    if any(t.retentive or t.dynamic_preset for t in program.timers.values()):
        fail("timer-mode functional-level mapping is unverified for SMBP")


def validate_allocations(sw, program):
    validate_timer_profile(program)
    if has_indexed_bits(program):
        fail("indexed-bit functional-level mapping is unverified for SMBP")
    bits = memory_bits_used(program)
    requirements = {
        "MemoryWordsMemoryAllocation": (
            8000,
            max(memory_words_used(program), default=-1) + 1,
        ),
        "MemoryBitsMemoryAllocation": (1024, max(bits, default=-1) + 1),
        "TimersMemoryAllocation": (255, max(program.timers, default=-1) + 1),
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
    if has_indexed(program):
        bound = direct_word_limit(program)
        words = sw.find("MemoryWordsMemoryAllocation")
        forced = words.findtext("ForcedCount") if words is not None else None
        mode = words.findtext("Allocation") if words is not None else None
        if mode not in ("Automatic", "Manual"):
            fail("indexed bound with an omitted/default allocation mode is unverified")
        if max(memory_words_used(program), default=-1) + 1 > bound or (
            mode == "Manual" and forced is not None and int(forced) != bound
        ):
            fail(
                "indexed bound from excess Manual allocation or symbol-only extent is unverified"
            )


def write_project(program, template, destination):
    validate(program)
    validate_timer_profile(program)
    if has_indexed_bits(program):
        fail("indexed-bit functional-level mapping is unverified for SMBP")
    from .ladder_lowering import normalize

    program = normalize(program)
    root = parse(template)
    sw = configuration(root)
    check_template_channels(root, program.communications)
    write_blocks(program, sw)
    write_counters(program, sw)
    for name in (
        "Pous",
        "Timers",
        "MemoryBits",
        "MemoryBitsMemoryAllocation",
        "TimersMemoryAllocation",
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
    element(pou, "SectionNumber", 1)
    rungs = element(pou, "Rungs")
    for i, lines in enumerate(program.rungs):
        r = element(rungs, "RungEntity")
        graph = element(r, "LadderElements")
        _, body = split_label(lines)
        items = (
            counter_graphics(body)
            if body[0].startswith("BLK %C")
            else [
                (t, a, 0, c, "Left" if t in LEFT_ONLY else "Left, Right")
                for t, a, c in graphics(lines)
            ]
        )
        for typ, arg, row, column, connection in items:
            e = element(graph, "LadderEntity")
            element(e, "ElementType", typ)
            if arg:
                field = {
                    "Comparison": "ComparisonExpression",
                    "Operation": "OperationExpression",
                }.get(typ, "Descriptor")
                element(e, field, arg)
                if field == "Descriptor":
                    element(e, "Comment", "")
                    element(e, "Symbol", "")
            element(e, "Row", row)
            element(e, "Column", column)
            element(
                e,
                "ChosenConnection",
                connection,
            )
        il = element(r, "InstructionLines")
        for line in lines:
            instruction = element(il, "InstructionLineEntity")
            element(instruction, "InstructionLine", line)
            element(instruction, "Comment", "")
        origin = program.metadata.get("rung_origins", [])
        location = origin[i] if i < len(origin) else {}
        source = "%s:%s:%s" % (
            location.get("file", "generated"),
            location.get("line", ""),
            location.get("column", ""),
        )
        element(r, "Name", "cpp_%04d" % i)
        element(
            r,
            "MainComment",
            source + " | Experimental generated logic; official validation pending",
        )
        label, _ = split_label(lines)
        element(r, "Label", label or "")
        element(r, "IsLadderSelected", "true")
    timers = element(sw, "Timers")
    for i, t in sorted(program.timers.items()):
        if t.base_ms not in (*BASES, 60000):
            fail(
                "SMBP serialization of the 10 ms timer base is not verified; use IL output until a vendor sample is available"
            )
        e = element(timers, "TimerTM")
        element(e, "Address", "%TM" + str(i))
        element(e, "Index", i)
        element(e, "Type", t.kind)
        element(e, "Preset", t.preset)
        if t.base_ms != 60000:
            element(e, "Base", BASES[t.base_ms])
        element(e, "IsRetentive", str(t.retentive).lower())
        element(e, "IsDynamicPreset", str(t.dynamic_preset).lower())
    bits = element(sw, "MemoryBits")
    numeric = {
        k: element(sw, k) for k in ("MemoryWords", "MemoryDoubleWords", "MemoryFloats")
    }
    for addr, symbol in sorted(program.symbols.items()):
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
    required = max(memory_words_used(program), default=-1) + 1
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
        ):
            fail("internal XML round trip changed program/configuration")
        os.replace(candidate, destination)
