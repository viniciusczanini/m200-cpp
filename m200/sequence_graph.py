"""Canonical native sequence graphs derived from installed static metadata.

Entities.dll ProgramElementTypes: SC=19, SBR=21, Drum=22.
ProgramElementTypeHelper.GetWidth/Height and LadderFunctionBlockProgramElement:
all width2; SBR/SC height3, Drum height2. Manuals define ordered input rows.
This is static provenance, not an official saved/accepted active CE40T graph.
"""
import re
from .model import address, fail
from .sequences import identity, PINS, CLASSES, parse_body


def is_block(lines):
    return bool(lines and re.fullmatch(r"BLK %(?:SBR|SC|DR)[0-7]", lines[0]))


def parse_block(lines):
    if not is_block(lines):
        fail("canonical native sequence block required")
    parse_body(lines)
    family, index = identity(lines[0][4:])
    pins = []
    cursor = 1
    while cursor < len(lines) - 1 and lines[cursor] != "OUT_BLK":
        if cursor + 1 >= len(lines) - 1 or not lines[cursor].startswith("LD ") or lines[cursor + 1] not in PINS[family]:
            fail("canonical sequence graph requires a direct LD per present pin")
        arg = lines[cursor][3:]
        if address(arg)[0] not in ("I0.", "M"):
            fail("canonical sequence pins require direct I0/M contacts; normalize expressions")
        pins.append((lines[cursor + 1], arg))
        cursor += 2
    outputs = []
    if cursor < len(lines) - 1:
        if family != "DR" or len(lines) - cursor != 4 or lines[cursor:cursor + 2] != ["OUT_BLK", "LD F"]:
            fail("canonical Drum output requires LD F and one plain coil")
        parts = lines[cursor + 2].split()
        if len(parts) != 2 or parts[0] not in ("ST", "S", "R") or address(parts[1], True)[0] not in ("M", "Q0."):
            fail("unsupported canonical Drum output coil")
        outputs.append((parts[0], parts[1]))
    return family, index, pins, outputs


def graphics(lines):
    family, index, pins, outputs = parse_block(lines)
    result = [("NormalContact", arg, PINS[family].index(pin), 0, "Left, Right") for pin, arg in pins]
    result.append((CLASSES[family], "%" + family + str(index), 0, 1, "Left"))
    if outputs:
        result[-1] = (*result[-1][:-1], "Left, Right")
        result += [("Line", "", 0, col, "Left, Right") for col in range(3, 10)]
        op, target = outputs[0]
        result.append(({"ST": "Coil", "S": "SetCoil", "R": "ResetCoil"}[op], target, 0, 10, "Left"))
    return result


def check_graph(rung, lines):
    # Exact canonical field equality is independent of XML ordering. Unknown
    # branch/port forms fail, rather than being treated as decorative graphics.
    from .register_graph import _container, _fields, _scalar
    _container(rung, "RungEntity")
    fields = _fields(rung, {"LadderElements", "InstructionLines", "Name", "MainComment", "Label", "IsLadderSelected"}, {"LadderElements", "InstructionLines"})
    stored = []
    _container(fields["InstructionLines"], "InstructionLines")
    for entry in fields["InstructionLines"]:
        _container(entry, "InstructionLineEntity")
        values = _fields(entry, {"InstructionLine", "Comment"}, {"InstructionLine"})
        stored.append(_scalar(values["InstructionLine"]))
    from .flow import split_label
    _, stored = split_label(stored)
    if stored != list(lines):
        fail("native sequence graph body mismatch")
    graph = fields["LadderElements"]
    _container(graph, "LadderElements")
    actual = []
    required = {"ElementType", "Row", "Column", "ChosenConnection"}
    for entry in graph:
        _container(entry, "LadderEntity")
        values = {k: _scalar(v) for k, v in _fields(entry, required | {"Descriptor", "Comment", "Symbol"}, required).items()}
        if not re.fullmatch(r"0|[1-9][0-9]*", values["Row"]) or not re.fullmatch(r"0|[1-9][0-9]*", values["Column"]):
            fail("noncanonical sequence graph coordinates")
        actual.append((values["ElementType"], values.get("Descriptor", ""), int(values["Row"]), int(values["Column"]), values["ChosenConnection"]))
    if sorted(actual) != sorted(graphics(lines)):
        fail("native sequence graph/IL port mismatch")
