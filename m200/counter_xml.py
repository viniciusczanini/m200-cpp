"""Observed Counter configuration and conservative, unbranched input layouts."""

import re
import xml.etree.ElementTree as ET
from collections import Counter as Counts
from .model import fail
from .counters import Counter, index, ACTIONS
from .edges import SERIES, contact_type
from .flow import split_label

FIELDS = {"Address", "Index", "Preset", "Comment", "Symbol"}
GRAPH_FIELDS = {
    "ElementType",
    "Descriptor",
    "Comment",
    "Symbol",
    "Row",
    "Column",
    "ChosenConnection",
    "ComparisonExpression",
}
ROWS = {"R": 0, "S": 1, "CU": 2, "CD": 3}


def read_configs(sw):
    node = sw.find("Counters")
    result = {}
    if node is not None:
        if (node.text or "").strip():
            fail("unsupported counter configuration text")
        for child in node:
            if (
                (child.text or "").strip()
                or (child.tail or "").strip()
                or any((c.tail or "").strip() for c in child)
            ):
                fail("unsupported counter configuration text")
            if child.tag != "Counter" or any(
                x.tag not in FIELDS or len(x) for x in child
            ):
                fail("unsupported counter configuration")
            if any(n != 1 for n in Counts(x.tag for x in child).values()):
                fail("duplicate counter configuration field")
            address = child.findtext("Address", "")
            i = index(address)
            if child.findtext("Index") != str(i) or i in result:
                fail("invalid or duplicate counter configuration")
            raw = child.findtext("Preset", "9999")
            if re.fullmatch(r"0|[1-9][0-9]*", raw) is None:
                fail("invalid counter preset")
            result[i] = Counter(int(raw))
    allocation = sw.find("CountersMemoryAllocation")
    if allocation is not None:
        if (
            (allocation.text or "").strip()
            or any(c.tag != "ForcedCount" or len(c) for c in allocation)
            or len(allocation) > 1
        ):
            fail("unsupported counter allocation; enum mapping unverified")
        count = allocation.findtext("ForcedCount")
        if count is not None and (
            re.fullmatch(r"0|[1-9][0-9]*", count) is None
            or not max(result, default=-1) + 1 <= int(count) <= 255
        ):
            fail("counter allocation count does not cover configuration")
    return result


def write_configs(program, sw):
    for name in ("Counters", "CountersMemoryAllocation"):
        old = sw.find(name)
        if old is not None:
            sw.remove(old)
    node = ET.SubElement(sw, "Counters")
    for i, c in sorted(program.counters.items()):
        child = ET.SubElement(node, "Counter")
        for name, value in [("Address", f"%C{i}"), ("Index", i), ("Preset", c.preset)]:
            ET.SubElement(child, name).text = str(value)
    ET.SubElement(sw, "CountersMemoryAllocation")


def simple(rung):
    return (
        len(rung) == 4
        and rung[0].startswith("BLK %C")
        and rung[2] in ACTIONS
        and rung[3] == "END_BLK"
        and rung[1].split(maxsplit=1)[0] in ("LD", "LDN")
        and "[" not in rung[1]
    )


def graphics(raw, column=2):
    _, rung = split_label(raw)
    rung = [" ".join(line.split()) for line in rung]
    if not rung[0].startswith("BLK %C") or rung[-1] != "END_BLK":
        fail("invalid counter graphics structure")
    target = rung[0].split()[1]
    index(target)
    if column not in (2, 6):
        fail("unverified counter graphical position")
    items = []
    series = []
    seen = set()
    for line in rung[1:-1]:
        if line not in ACTIONS:
            series.append(line)
            continue
        if line in seen or not series:
            fail("unsupported counter input wiring")
        seen.add(line)
        row = ROWS[line]
        width = 0
        for i, contact in enumerate(series):
            parts = contact.split(maxsplit=1)
            if (
                len(parts) != 2
                or parts[0] not in SERIES
                or (i == 0 and not parts[0].startswith("LD"))
                or (i and parts[0].startswith("LD"))
            ):
                fail(
                    "counter graphics require independent series inputs; normalize native logic"
                )
            op, arg = parts
            if arg.startswith("["):
                fail("counter comparison input must be normalized")
            items.append((contact_type(op), arg, row, width, "Left, Right"))
            width += 1
        if width > column:
            fail("counter input exceeds block column")
        items.extend(("Line", "", row, i, "Left, Right") for i in range(width, column))
        series = []
    if series or not seen:
        fail("counter output/branch graphics require normalization")
    items.append(("Counter", target, 0, column, "Left"))
    return items


def check_graph(node, lines):
    graph = node.find("LadderElements")
    if graph is None or not len(graph):
        if node.findtext("IsLadderSelected", "false").lower() == "true":
            fail("selected Counter rung has no graphics")
        return
    actual = []
    for e in graph:
        if e.tag != "LadderEntity" or any(
            c.tag not in GRAPH_FIELDS or len(c) for c in e
        ):
            fail("unsupported counter graphic fields")
        if any(n != 1 for n in Counts(c.tag for c in e).values()):
            fail("duplicate counter graphic field")
        try:
            row = int(e.findtext("Row", "0"))
            col = int(e.findtext("Column", "-1"))
        except ValueError:
            fail("invalid counter graphical coordinates")
        if e.findtext("ComparisonExpression", ""):
            fail("counter comparison input must be normalized")
        actual.append(
            (
                e.findtext("ElementType", ""),
                e.findtext("Descriptor", ""),
                row,
                col,
                e.findtext("ChosenConnection", ""),
            )
        )
    blocks = [x for x in actual if x[0] == "Counter"]
    if len(blocks) != 1:
        fail("counter graph must contain one block")
    if sorted(actual) != sorted(graphics(lines, blocks[0][3])):
        fail("Counter IL and Ladder graphics do not agree")
