"""Conservative SMBP subset reader and template-preserving candidate writer.

No public schema or official-editor verification is available. These outputs are
experimental, even when their IL/graph representations agree locally.
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .il import validate
from .config import configuration, unique_tree
from .model import Program, Timer, address, fail
from .numeric import word_address, comparison, operation, Number

TARGET = "TM200CE40T"
BASES = {1: "OneMilliSeconds", 100: "OneHundredMilliSeconds", 1000: "OneSecond"}


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
    unique_tree(root)
    if root.findtext("HardwareConfiguration/Plc/Cpu/Reference") != TARGET:
        fail("template/project must target " + TARGET)
    if len(root.findall("HardwareConfiguration/Plc/Cpu")) != 1:
        fail("project must contain exactly one CPU")
    return root


def graphics(rung):
    # Deliberately only series contacts, one action, and one optional Timer.
    # Compound expressions are split into boolean gates by the lowerer.
    if rung[0].startswith("BLK "):
        descriptor = rung[0].split()[1]
        items = [("NormalContact", rung[1].split()[1], 0), ("Timer", descriptor, 3)]
        items += [("Line", "", i) for i in (1, 2, 5, 6, 7, 8, 9)]
        items.append(("Coil", rung[5].split()[1], 10))
    else:
        items = []
        column = 0
        for line in rung[:-1]:
            op, arg = line.split(maxsplit=1)
            if op not in ("LD", "LDN", "AND", "ANDN"):
                fail("project graphics for this IL operator are not supported")
            if arg.startswith("["):
                if op not in ("LD", "AND"):
                    fail("negated numeric comparison graphics are unsupported")
                items.append(("Comparison", arg[1:-1].strip(), column))
                column += 2
                continue
            items.append(
                (
                    "NegatedContact" if op in ("LDN", "ANDN") else "NormalContact",
                    arg,
                    column,
                )
            )
            column += 1
        terminal_operation = rung[-1].startswith("[")
        end = 9 if terminal_operation else 10
        if column > end:
            fail("rung exceeds Ladder width")
        items += [("Line", "", i) for i in range(column, end)]
        if terminal_operation:
            items.append(("Operation", rung[-1][1:-1].strip(), 9))
        else:
            op, arg = rung[-1].split()
            items.append(
                ({"ST": "Coil", "S": "SetCoil", "R": "ResetCoil"}[op], arg, 10)
            )
    return items


def check_graph(rung_node, lines):
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
        expected_connection = (
            "Left"
            if typ in ("Coil", "SetCoil", "ResetCoil", "Operation")
            else "Left, Right"
        )
        if e.findtext("ChosenConnection", "") != expected_connection:
            fail("unsupported Ladder connections")
        actual.append((typ, arg, column))
    if len(rows) != 1:
        fail("mixed Ladder rows are outside the supported series subset")
    expected = [
        (t, numeric_graph(t, a) if t in ("Comparison", "Operation") else a, c)
        for t, a, c in graphics(lines)
    ]
    if sorted(actual) != sorted(expected):
        fail("IL and Ladder graphics do not agree")


def numeric_graph(typ, expression):
    # Parse token boundaries; removing whitespace could turn MW40 00 into MW4000.
    parsed = (
        comparison("[" + expression + "]")
        if typ == "Comparison"
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
            if (
                t.findtext("IsRetentive", "false").lower() != "false"
                or t.findtext("IsDynamicPreset", "false").lower() != "false"
            ):
                fail("retentive/dynamic timers are unsupported")
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
                t.findtext("Type", "TON"), preset * base_ms, base_ms
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
                if r.findtext("Label", ""):
                    fail("labeled rungs require unsupported control flow")
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
                p.rungs.append(lines)
                # Validate IL first so malformed instructions cannot be hidden by a graph.
                validate(
                    Program(
                        p.rungs,
                        {
                            i: t
                            for i, t in p.timers.items()
                            if any(rr[0] == "BLK %TM" + str(i) for rr in p.rungs)
                        },
                    )
                )
                check_graph(r, lines)
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


def write_project(program, template, destination):
    validate(program)
    root = parse(template)
    sw = configuration(root)
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
        for typ, arg, column in graphics(lines):
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
            element(e, "Row", 0)
            element(e, "Column", column)
            element(
                e,
                "ChosenConnection",
                "Left"
                if typ in ("Coil", "SetCoil", "ResetCoil", "Operation")
                else "Left, Right",
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
        element(r, "Label", "")
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
        element(e, "IsRetentive", "false")
        element(e, "IsDynamicPreset", "false")
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
    required = 0
    numeric_text = (
        " ".join(" ".join(r) for r in program.rungs) + " " + " ".join(program.symbols)
    )
    for prefix, index in re.findall(r"%M([WDF])(\d+)", numeric_text):
        required = max(required, int(index) + (1 if prefix == "W" else 2))
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
    destination.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    # This is an internal representation check only, never vendor acceptance.
    loaded = load_project(destination)
    if loaded.rungs != program.rungs:
        fail("internal XML round trip changed IL")
