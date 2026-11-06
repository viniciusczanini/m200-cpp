"""Native SR wrapper codec, independent of whole-project graph/resource checks.

Only the four observed wrapper fields are owned. Rung XML is structurally closed
and its opcode syntax is decoded; this is not address/resource validation, graph
binding verification or execution. Whole-project admission separately validates
callee IL/configuration/graphs and return context.
"""

from collections.abc import Mapping
import copy
from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET

from .flow import split_label
from .model import fail
from .native_logic import decode
from .sequence_graph import is_block as sequence_block, check_graph as check_sequence_graph
from .subroutine_graph import (
    _container,
    _fields,
    _number,
    _rung_surface,
    _scalar,
    _xml_text,
)


def _section(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        fail("SR section identity must be a nonnegative Int32")


def _name(value):
    if not isinstance(value, str) or not _xml_text(value).strip():
        fail("SR name must be nonempty XML text")


def _body(rungs):
    if not isinstance(rungs, tuple) or not rungs:
        fail("SR body must be a nonempty tuple of rung XML nodes")
    count = 0
    for rung in rungs:
        fields, lines = _rung_surface(rung)
        label, body = split_label(lines)
        if (fields["Label"].text or "") != (label or ""):
            fail("SR rung label and actual IL disagree")
        if not body:
            fail("SR rung has no executable body")
        # Native leaf calls cannot nest, even in unused or guarded bodies.
        if any(re.fullmatch(r"SR[0-9]+(?:\s.*)?", line) for line in body):
            fail("native SR calls cannot be nested")
        if body[0].startswith(("BLK %READ_VAR", "BLK %WRITE_VAR", "BLK %WRITE_READ_VAR")):
            from .communication_graph import full_candidate, parse_full_body
            from .communication import parse_block

            if full_candidate(lines):
                parse_full_body(lines)
            else:
                parse_block(body)
        else:
            decode(body)
        graph = fields.get("LadderElements")
        if sequence_block(body):
            # Admit only the existing G08 canonical layout for this actual IL
            # block, including its native identity, present pins and optional
            # Drum F output. Do not whitelist sequence entities in other rungs.
            # Shared config/capacity checks remain owned by the project layer.
            check_sequence_graph(rung, body)
        elif graph is not None:
            for entity in graph:
                if entity.findtext("ElementType") not in {
                    "NormalContact",
                    "NegatedContact",
                    "Line",
                    "Operation",
                    "Coil",
                    "End",
                    "EndCn",
                    "SetCoil",
                    "ResetCoil",
                    "Comparison",
                    "RisingEdge",
                    "FallingEdge",
                    "Timer",
                    "Counter",
                    "Register",
                    "Jump",
                    "ReadVarBasic",
                    "WriteVarBasic",
                    "WriteReadVarBasic",
                    "Short",
                    "Open",
                }:
                    fail("unverified native SR body graph type")
        count += len(lines)
    if count > 10000:
        fail("SR body exceeds the local instruction budget")


@dataclass(frozen=True)
class Subroutine:
    number: int
    name: str
    section_number: int
    rungs: tuple

    def __post_init__(self):
        _number(self.number)
        _name(self.name)
        _section(self.section_number)
        _body(self.rungs)


def _collection(sw):
    if not isinstance(sw, ET.Element) or sw.tag != "SoftwareConfiguration":
        fail("SoftwareConfiguration required for SR wrappers")
    nodes = []
    for node in sw:
        if isinstance(node.tag, str) and node.tag.rsplit("}", 1)[-1] == "Subroutines":
            if node.tag != "Subroutines":
                fail("unsupported Subroutines namespace")
            nodes.append(node)
    if len(nodes) > 1:
        fail("duplicate Subroutines collection")
    return nodes[0] if nodes else None


def _decimal(text, name, maximum):
    if not isinstance(text, str) or re.fullmatch(r"0|[1-9][0-9]*", text) is None:
        fail("noncanonical SR " + name)
    if len(text) > len(str(maximum)):
        fail("SR " + name + " exceeds its bounded identity domain")
    value = int(text)
    if value > maximum:
        fail("SR " + name + " exceeds its bounded identity domain")
    return value


def _distinct(values):
    names, sections = set(), set()
    for value in values:
        if value.name in names or value.section_number in sections:
            fail("ambiguous duplicate SR name or section identity")
        names.add(value.name)
        sections.add(value.section_number)


def _read_collection(node):
    if node is None:
        return {}
    _container(node, "Subroutines")
    if len(node) > 64:
        fail("Subroutines collection exceeds 64 entries")
    result = {}
    for entry in node:
        _container(entry, "Subroutine")
        fields = _fields(
            entry,
            {"Name", "SectionNumber", "Rungs", "Number"},
            {"Name", "SectionNumber", "Rungs", "Number"},
        )
        name = _scalar(fields["Name"])
        number = _decimal(_scalar(fields["Number"]), "Number", 63)
        section = _decimal(
            _scalar(fields["SectionNumber"]), "SectionNumber", 2147483647
        )
        _container(fields["Rungs"], "Rungs")
        value = Subroutine(
            number,
            name,
            section,
            tuple(copy.deepcopy(rung) for rung in fields["Rungs"]),
        )
        if number in result:
            fail("duplicate native SR number")
        result[number] = value
    _distinct(result.values())
    return result


def read_subroutines(sw):
    """Read independent wrapper identities and copied, bounded rung XML."""
    return _read_collection(_collection(sw))


def write_subroutines(configs, sw):
    """Validate completely, then atomically replace only Subroutines."""
    previous = _collection(sw)
    _read_collection(previous)
    if not isinstance(configs, Mapping) or len(configs) > 64:
        fail("SR wrappers must be a mapping of at most 64 entries")
    for number, value in configs.items():
        _number(number)
        if not isinstance(value, Subroutine) or value.number != number:
            fail("SR wrapper key and typed identity disagree")
        # Frozen dataclasses do not make the contained XML immutable.
        _name(value.name)
        _section(value.section_number)
        _body(value.rungs)
    _distinct(configs.values())
    replacement = ET.Element("Subroutines")
    for number in sorted(configs):
        value = configs[number]
        entry = ET.SubElement(replacement, "Subroutine")
        ET.SubElement(entry, "Name").text = value.name
        ET.SubElement(entry, "SectionNumber").text = str(value.section_number)
        body = ET.SubElement(entry, "Rungs")
        body.extend(copy.deepcopy(rung) for rung in value.rungs)
        ET.SubElement(entry, "Number").text = str(number)
    if previous is None:
        sw.append(replacement)
    else:
        replacement.tail = previous.tail
        position = list(sw).index(previous)
        sw.remove(previous)
        sw.insert(position, replacement)
