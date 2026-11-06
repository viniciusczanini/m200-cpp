"""Isolated observed Register graph codec; not connected to the compiler.

Only the bare R/I/O body with three normal direct input contacts is admitted.
This foundation describes pin addresses and geometry, not Register execution,
FIFO/LIFO behavior, allocations, hardware qualification or whole-project support.
"""

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from .model import fail


def _index(value):
    if type(value) is not int or not 0 <= value < 4:
        fail("register graph index must be an integer in 0..3")


def _input(value):
    if not isinstance(value, str) or not re.fullmatch(r"%I0\.(?:0|[1-9][0-9]?)", value):
        fail("unverified Register contact domain; use a canonical direct I0 input")
    if int(value[4:]) >= 24:
        fail("Register contact exceeds the target input range")


@dataclass(frozen=True)
class RegisterInputs:
    """Addresses of Reset/Store/Retrieve pins, with no execution semantics."""

    index: int
    reset: str
    store: str
    retrieve: str

    def __post_init__(self):
        _index(self.index)
        for value in (self.reset, self.store, self.retrieve):
            _input(value)


def parse_block(lines):
    if (
        not isinstance(lines, (list, tuple))
        or len(lines) != 8
        or any(not isinstance(line, str) for line in lines)
    ):
        fail("Register graph requires the closed eight-line R/I/O body")
    body = [" ".join(line.split()) for line in lines]
    key = re.fullmatch(r"BLK %R([0-3])", body[0])
    if not key or (body[2], body[4], body[6], body[7]) != ("R", "I", "O", "END_BLK"):
        fail("unsupported Register block identity or pin order")
    values = []
    for position in (1, 3, 5):
        parts = body[position].split(maxsplit=1)
        if len(parts) != 2 or parts[0] != "LD":
            fail("unverified Register contact action; plain LD required")
        values.append(parts[1])
    return RegisterInputs(int(key[1]), *values)


def graphics(lines):
    inputs = parse_block(lines)
    return [
        ("NormalContact", inputs.reset, 0, 0, "Left, Right"),
        ("NormalContact", inputs.store, 1, 0, "Left, Right"),
        ("NormalContact", inputs.retrieve, 2, 0, "Left, Right"),
        ("Register", "%R" + str(inputs.index), 0, 1, "Left"),
    ]


def _container(node, tag):
    if (
        not isinstance(node, ET.Element)
        or node.tag != tag
        or node.attrib
        or (node.text or "").strip()
        or (node.tail or "").strip()
    ):
        fail("invalid Register graph container, attributes or mixed content: " + tag)


def _fields(node, allowed, required):
    if len(node) > len(allowed):
        fail("duplicate or unknown Register graph fields")
    result = {}
    for child in node:
        if child.tag not in allowed or child.tag in result:
            fail("duplicate or unknown Register graph field")
        result[child.tag] = child
    if required - result.keys():
        fail("missing Register graph fields")
    return result


def _scalar(node):
    if node.attrib or len(node) or (node.tail or "").strip():
        fail("Register graph values must be scalar and unattributed")
    return node.text or ""


def _rung(node):
    _container(node, "RungEntity")
    fields = _fields(
        node,
        {
            "LadderElements",
            "InstructionLines",
            "Name",
            "MainComment",
            "Label",
            "IsLadderSelected",
        },
        {"InstructionLines"},
    )
    for tag in ("Name", "MainComment", "Label", "IsLadderSelected"):
        if tag not in fields:
            continue
        value = _scalar(fields[tag])
        if tag == "Label" and value:
            fail("Register graph labels are outside this isolated profile")
        if tag == "IsLadderSelected" and value not in ("true", "false"):
            fail("invalid Register Ladder selection")
    instructions = fields["InstructionLines"]
    _container(instructions, "InstructionLines")
    if len(instructions) != 8:
        fail("Register graph requires exactly eight instruction entries")
    lines = []
    for entry in instructions:
        _container(entry, "InstructionLineEntity")
        values = _fields(entry, {"InstructionLine", "Comment"}, {"InstructionLine"})
        for value in values.values():
            _scalar(value)
        lines.append(values["InstructionLine"].text or "")
    inputs = parse_block(lines)
    graph = fields.get("LadderElements")
    if graph is not None:
        _container(graph, "LadderElements")
    return lines, inputs, graph


def _check_graph(graph, expected):
    if graph is None or len(graph) != 4:
        fail("Register requires its complete observed four-entity graph")
    actual = []
    required = {"ElementType", "Descriptor", "Row", "Column", "ChosenConnection"}
    for entry in graph:
        _container(entry, "LadderEntity")
        fields = _fields(entry, required | {"Comment", "Symbol"}, required)
        values = {tag: _scalar(value) for tag, value in fields.items()}
        row, column = values["Row"], values["Column"]
        if row not in ("0", "1", "2") or column not in ("0", "1"):
            fail("unverified or noncanonical Register graph coordinates")
        actual.append(
            (
                values["ElementType"],
                values["Descriptor"],
                int(row),
                int(column),
                values["ChosenConnection"],
            )
        )
    if sorted(actual) != sorted(expected):
        fail("Register instructions and graph do not agree")


def read_graph(rung):
    """Read only a complete matching graph/body, without changing its tree."""
    lines, inputs, graph = _rung(rung)
    _check_graph(graph, graphics(lines))
    return inputs


def write_graph(lines, rung):
    """Fill absent/empty graphics only after validating all owned source data.

    Existing complete graphs must match and are retained byte-for-byte at the
    tree level, including UI annotations. InstructionLines and other rung fields
    are never rewritten; a different body must be authored explicitly by caller.
    """
    inputs = parse_block(lines)
    stored_lines, stored_inputs, previous = _rung(rung)
    if inputs != stored_inputs:
        fail("Register graph writer cannot replace a different instruction body")
    expected = graphics(stored_lines)
    if previous is not None and len(previous):
        _check_graph(previous, expected)
        return
    fresh = ET.Element("LadderElements")
    for typ, descriptor, row, column, connection in expected:
        entry = ET.SubElement(fresh, "LadderEntity")
        for tag, value in (
            ("ElementType", typ),
            ("Descriptor", descriptor),
            ("Comment", ""),
            ("Row", str(row)),
            ("Column", str(column)),
            ("ChosenConnection", connection),
        ):
            ET.SubElement(entry, tag).text = value
    if previous is None:
        rung.insert(0, fresh)
    else:
        fresh.tail = previous.tail
        rung[list(rung).index(previous)] = fresh
