"""Isolated observed native SR call graph; not wired into the compiler.

The closed call is a normal M contact or exact I0.0 followed by SR0..SR63.
Exact CE40T saves establish I0.0 and M20 geometry; primary resource domains
bound M0..1023 and SR0..63. No other input or negated predicate is inferred.
"""

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from .model import fail


def _number(value):
    if type(value) is not int or not 0 <= value < 64:
        fail("subroutine number must be an integer in 0..63")


@dataclass(frozen=True)
class SubroutineCall:
    number: int
    predicate: str = "%I0.0"

    def __post_init__(self):
        _number(self.number)
        _predicate(self.predicate)


def _predicate(value):
    if value == "%I0.0":
        return
    match = (
        re.fullmatch(r"%M(0|[1-9][0-9]*)", value) if isinstance(value, str) else None
    )
    if match is None or len(match[1]) > 4 or int(match[1]) >= 1024:
        fail("unverified SR predicate; use a canonical normal M0..1023 or exact I0.0")


def parse_call(lines):
    if (
        not isinstance(lines, (list, tuple))
        or len(lines) != 2
        or any(not isinstance(line, str) for line in lines)
    ):
        fail("SR call graph requires the closed two-line call")
    body = [" ".join(line.split()) for line in lines]
    if not body[0].startswith("LD "):
        fail("SR graph requires a normal LD contact")
    predicate = body[0][3:]
    _predicate(predicate)
    match = re.fullmatch(r"SR(0|[1-9][0-9]*)", body[1])
    if match is None or len(match[1]) > 2:
        fail("invalid native SR call identity")
    return SubroutineCall(int(match[1]), predicate)


def graphics(lines):
    call = parse_call(lines)
    return (
        [("NormalContact", call.predicate, 0, 0, "Left, Right")]
        + [("Line", "", 0, column, "Left, Right") for column in range(1, 10)]
        + [("Jump", "SR" + str(call.number), 0, 10, "Left")]
    )


def _xml_text(value):
    if value is None:
        return ""
    if not isinstance(value, str) or any(
        not (
            ord(c) in (9, 10, 13)
            or 32 <= ord(c) <= 0xD7FF
            or 0xE000 <= ord(c) <= 0xFFFD
            or 0x10000 <= ord(c) <= 0x10FFFF
        )
        for c in value
    ):
        fail("SR values must contain valid XML text")
    return value


def _container(node, tag):
    if (
        not isinstance(node, ET.Element)
        or node.tag != tag
        or node.attrib
        or _xml_text(node.text).strip()
        or _xml_text(node.tail).strip()
    ):
        fail("invalid SR XML container, attributes or mixed content: " + tag)


def _fields(node, allowed, required=()):
    fields = {}
    for child in node:
        if child.tag not in allowed or child.tag in fields:
            fail("unknown or duplicate SR XML field")
        fields[child.tag] = child
    if set(required) - fields.keys():
        fail("missing SR XML field")
    return fields


def _scalar(node):
    if node.attrib or len(node) or _xml_text(node.tail).strip():
        fail("SR XML values must be scalar and unattributed")
    return _xml_text(node.text)


def _rung_surface(node):
    """Closed XML surface only; callers still own IL and graph semantics."""
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
        {"InstructionLines", "Name", "MainComment", "Label", "IsLadderSelected"},
    )
    for name in ("Name", "MainComment", "Label", "IsLadderSelected"):
        _scalar(fields[name])
    if fields["IsLadderSelected"].text not in ("true", "false"):
        fail("invalid SR rung Ladder selection")
    instructions = fields["InstructionLines"]
    _container(instructions, "InstructionLines")
    lines = []
    for entry in instructions:
        _container(entry, "InstructionLineEntity")
        values = _fields(
            entry, {"InstructionLine", "Comment"}, {"InstructionLine", "Comment"}
        )
        _scalar(values["Comment"])
        text = _scalar(values["InstructionLine"])
        if not text.strip():
            fail("empty SR instruction")
        lines.append(" ".join(text.split()))
    if not lines or len(lines) > 10000:
        fail("SR rung exceeds the bounded instruction surface")
    graph = fields.get("LadderElements")
    if graph is not None:
        _container(graph, "LadderElements")
        for entity in graph:
            _container(entity, "LadderEntity")
            values = _fields(
                entity,
                {
                    "ElementType",
                    "Descriptor",
                    "OperationExpression",
                    "ComparisonExpression",
                    "Comment",
                    "Symbol",
                    "Row",
                    "Column",
                    "ChosenConnection",
                },
                {"ElementType", "Row", "Column", "ChosenConnection"},
            )
            for value in values.values():
                _scalar(value)
    return fields, lines


def read_graph(node):
    fields, lines = _rung_surface(node)
    if fields["Label"].text:
        fail("labelled SR call graph is not in the observed profile")
    call = parse_call(lines)
    graph = fields.get("LadderElements")
    if graph is None or len(graph) != 11:
        fail("SR call requires the complete eleven-entity graph")
    actual = []
    for entity in graph:
        values = _fields(
            entity,
            {
                "ElementType",
                "Descriptor",
                "Row",
                "Column",
                "ChosenConnection",
                "Comment",
                "Symbol",
            },
            {"ElementType", "Descriptor", "Row", "Column", "ChosenConnection"},
        )
        row, column = values["Row"].text, values["Column"].text
        if row != "0" or column not in tuple(str(i) for i in range(11)):
            fail("unverified SR call graph coordinate")
        actual.append(
            (
                _scalar(values["ElementType"]),
                _scalar(values["Descriptor"]),
                0,
                int(column),
                _scalar(values["ChosenConnection"]),
            )
        )
    if sorted(actual) != sorted(graphics(lines)):
        fail("SR call IL and native graph do not agree")
    return call


def write_graph(lines, node):
    """Fill an absent/empty graph atomically; retain an existing valid one."""
    call = parse_call(lines)
    fields, actual = _rung_surface(node)
    if fields["Label"].text or parse_call(actual) != call:
        fail("SR graph writer body/label does not match its target")
    previous = fields.get("LadderElements")
    if previous is not None and len(previous):
        read_graph(node)
        return
    replacement = ET.Element("LadderElements")
    for typ, descriptor, row, column, connection in graphics(actual):
        entity = ET.SubElement(replacement, "LadderEntity")
        for key, value in (
            ("ElementType", typ),
            ("Descriptor", descriptor),
            ("Row", str(row)),
            ("Column", str(column)),
            ("ChosenConnection", connection),
        ):
            ET.SubElement(entity, key).text = value
    if previous is None:
        node.insert(0, replacement)
    else:
        replacement.tail = previous.tail
        position = list(node).index(previous)
        node.remove(previous)
        node.insert(position, replacement)
