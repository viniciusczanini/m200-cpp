"""Conservative SMBP subset reader and template-preserving candidate writer.

No public schema or official-editor verification is available. These outputs are
experimental, even when their IL/graph representations agree locally.
"""

import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .il import validate
from .model import Program, Timer, address, fail

TARGET = "TM200CE40T"
BASES = {1: "OneMilliSeconds", 100: "OneHundredMilliSeconds", 1000: "OneSecond"}
KNOWN_SOFTWARE = set(
    ["Pous", "Subroutines", "WatchLists", "CustomSymbols", "ConstantWordsMemoryAllocation", "MemoryBitsMemoryAllocation", "MemoryWordsMemoryAllocation", "TimersMemoryAllocation", "CountersMemoryAllocation", "RegistersMemoryAllocation", "DrumsMemoryAllocation", "SbrsMemoryAllocation", "ScsMemoryAllocation", "FcsMemoryAllocation", "SchsMemoryAllocation", "HscsMemoryAllocation", "PtosMemoryAllocation", "MemoryBits", "SystemBits", "SystemWords", "GrafcetSteps", "MemoryWords", "MemoryDoubleWords", "MemoryFloats", "ConstantWords", "ConstantDoubleWords", "ConstantMemoryFloats", "Timers", "Counters", "FastCounters", "Registers", "Drums", "ShiftBitRegisters", "StepCounters", "ScheduleBlocks", "Pids", "MessageBlocks", "FunctionBlocks", "MotionTaskTables", "FastTask", "MastTask", "CpuBehavior", "TraceTimeBase", "UserFunctionPous", "UserFunctionBlockPous", "UserDefineFunctionBlocks"]
)
EMPTY_ONLY = set(
    ["Subroutines", "GrafcetSteps", "Counters", "FastCounters", "Registers", "Drums", "ShiftBitRegisters", "StepCounters", "ScheduleBlocks", "Pids", "FunctionBlocks", "MotionTaskTables", "UserFunctionPous", "UserFunctionBlockPous", "UserDefineFunctionBlocks"]
)


def element(parent, tag, text=None):
    child = ET.SubElement(parent, tag)
    if text is not None:
        child.text = str(text)
    return child


def parse(path):
    data = Path(path).read_bytes()
    if len(data) > 20_000_000:
        fail("project exceeds the experimental parser size limit")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        fail("DTD/entity declarations are not supported")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        fail("invalid XML: " + str(exc))
    if root.tag != "ProjectDescriptor":
        fail("unsupported project root or encrypted project")
    if root.findtext("HardwareConfiguration/Plc/Cpu/Reference") != TARGET:
        fail("template/project must target " + TARGET)
    if len(root.findall("HardwareConfiguration/Plc/Cpu")) != 1:
        fail("project must contain exactly one CPU")
    return root


def configuration(root):
    sw = root.find("SoftwareConfiguration")
    if sw is None:
        fail("missing SoftwareConfiguration")
    for child in sw:
        if child.tag not in KNOWN_SOFTWARE:
            fail("unknown software configuration: " + child.tag)
        if child.tag in EMPTY_ONLY and len(child):
            fail("unsupported active objects: " + child.tag)
    for tag in ("MemoryBitsMemoryAllocation", "TimersMemoryAllocation"):
        allocation = sw.find(tag)
        if allocation is not None and allocation.findtext("Allocation", "") not in (
            "",
            "Automatic",
            "Manual",
        ):
            fail("unsupported memory allocation mode")
    # Free POUs/event tasks could execute outside the scan we translate.
    pous = sw.find("Pous")
    if pous is not None and any(c.tag != "ProgramOrganizationUnits" for c in pous):
        fail("unsupported POU/task kind")
    fast = sw.find("FastTask")
    if fast is not None and any(c.tag != "Period" for c in fast):
        fail("active fast/event task is unsupported")
    mast = sw.find("MastTask")
    if mast is not None and any(
        c.tag not in ("UsePeriodScanMode", "PeriodScan") for c in mast
    ):
        fail("unsupported master task configuration")
    plc = root.find("HardwareConfiguration/Plc")
    if plc is not None:
        for c in plc:
            if c.tag != "Cpu" and len(c):
                fail("hardware expansion/configuration is unsupported: " + c.tag)
    cpu = root.find("HardwareConfiguration/Plc/Cpu")
    for tag in (
        "PulseTrainOutputs",
        "InputAssemblys",
        "OutputAssemblys",
        "InputRegisters",
        "HoldingRegisters",
    ):
        c = cpu.find(tag)
        if c is not None and len(c):
            fail("active peripheral/network objects are unsupported: " + tag)
    for io in cpu.findall("DigitalInputs/DigitalInput"):
        for c in io:
            if any(
                word in c.tag.lower() for word in ("runstop", "event", "latch")
            ) and c.text not in (None, "", "false", "False", "0"):
                fail("special input function is unsupported: " + c.tag)
    return sw


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
        for index, line in enumerate(rung[:-1]):
            op, arg = line.split()
            if op not in ("LD", "LDN", "AND", "ANDN"):
                fail("project graphics for this IL operator are not supported")
            items.append(
                (
                    "NegatedContact" if op in ("LDN", "ANDN") else "NormalContact",
                    arg,
                    index,
                )
            )
        if len(items) > 10:
            fail("rung exceeds Ladder width")
        items += [("Line", "", i) for i in range(len(items), 10)]
        op, arg = rung[-1].split()
        items.append(({"ST": "Coil", "S": "SetCoil", "R": "ResetCoil"}[op], arg, 10))
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
            )
            for c in e
        ):
            fail("unknown Ladder element fields")
        try:
            row = int(e.findtext("Row", "0"))
            column = int(e.findtext("Column", "-1"))
        except ValueError:
            fail("invalid Ladder coordinates")
        if row not in (0, 1):
            fail("parallel/multi-row Ladder is outside the supported import subset")
        rows.add(row)
        typ = e.findtext("ElementType", "")
        arg = e.findtext("Descriptor", "")
        expected_connection = (
            "Left" if typ in ("Coil", "SetCoil", "ResetCoil") else "Left, Right"
        )
        if e.findtext("ChosenConnection", "") != expected_connection:
            fail("unsupported Ladder connections")
        actual.append((typ, arg, column))
    if len(rows) != 1:
        fail("mixed Ladder rows are outside the supported series subset")
    if sorted(actual) != sorted(graphics(lines)):
        fail("IL and Ladder graphics do not agree")


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
                element(e, "Descriptor", arg)
                element(e, "Comment", "")
                element(e, "Symbol", "")
            element(e, "Row", 0)
            element(e, "Column", column)
            element(
                e,
                "ChosenConnection",
                "Left" if typ in ("Coil", "SetCoil", "ResetCoil") else "Left, Right",
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
    for addr, symbol in sorted(program.symbols.items()):
        e = element(bits, "MemoryBit")
        element(e, "Address", addr)
        element(e, "Index", int(addr[2:]))
        element(e, "Symbol", re.sub(r"[^A-Za-z0-9_]", "_", symbol) + "_" + addr[2:])
    allocation = element(sw, "MemoryBitsMemoryAllocation")
    element(allocation, "Allocation", "Automatic")
    allocation = element(sw, "TimersMemoryAllocation")
    element(allocation, "Allocation", "Automatic")
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
