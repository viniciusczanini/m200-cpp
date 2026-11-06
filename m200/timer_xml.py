"""TimerTM configuration and series Ladder bindings using known native enums."""

import re
import xml.etree.ElementTree as ET
from collections import Counter

from .model import Timer, fail
from .timer_profile import BASES, MINUTE_BASE_MS
from .timer_il import index, body
from .levels import functional_level
from .edges import SERIES, contact_type
from .flow import split_label

FIELDS = {
    "Address", "Index", "Type", "Preset", "Base", "Comment", "Symbol",
    "IsRetentive", "IsDynamicPreset",
}


def read_configs(sw):
    node = sw.find("Timers")
    result = {}
    if node is None:
        return result
    if node.attrib or (node.text or "").strip():
        fail("unsupported timer configuration text/attributes")
    for child in node:
        if (
            child.tag != "TimerTM" or child.attrib or (child.text or "").strip()
            or (child.tail or "").strip()
            or any(c.tag not in FIELDS or len(c) or c.attrib or (c.tail or "").strip() for c in child)
        ):
            fail("unsupported timer configuration")
        if any(n != 1 for n in Counter(c.tag for c in child).values()):
            fail("duplicate timer configuration field")
        target = child.findtext("Address", "")
        i = index(target)
        if child.findtext("Index") != str(i) or i in result:
            fail("invalid or duplicate timer index")
        raw_preset = child.findtext("Preset", "9999")
        if re.fullmatch(r"0|[1-9][0-9]*", raw_preset) is None or int(raw_preset) > 9999:
            fail("invalid timer preset")
        native_base = child.findtext("Base", "")
        if native_base and native_base not in BASES.values():
            fail("unsupported timer time base: " + native_base)
        base = {v: k for k, v in BASES.items()}.get(native_base, MINUTE_BASE_MS)
        kind = child.findtext("Type", "TON")
        if kind not in ("TON", "TOF", "TP") or (base == 1 and i >= 6):
            fail("invalid timer kind/base for this target identity")
        flags = []
        for name in ("IsRetentive", "IsDynamicPreset"):
            raw = child.findtext(name, "false")
            if raw not in ("true", "false"):
                fail("unsupported timer boolean: " + name)
            flags.append(raw == "true")
        if kind == "TP" and flags[0]:
            fail("retentive TP is unsupported in the Basic timer profile")
        result[i] = Timer(kind, int(raw_preset) * base, base, *flags)
    return result


def write_configs(program, sw):
    old = sw.find("Timers")
    if old is not None:
        sw.remove(old)
    node = ET.SubElement(sw, "Timers")
    for i, cfg in sorted(program.timers.items()):
        child = ET.SubElement(node, "TimerTM")
        fields = [
            ("Address", f"%TM{i}"), ("Index", i), ("Type", cfg.kind),
            ("Preset", cfg.preset),
        ]
        if cfg.base_ms != MINUTE_BASE_MS:
            if cfg.base_ms not in BASES:
                fail("unsupported timer base for native serialization")
            fields.append(("Base", BASES[cfg.base_ms]))
        fields += [
            ("IsRetentive", str(cfg.retentive).lower()),
            ("IsDynamicPreset", str(cfg.dynamic_preset).lower()),
        ]
        for name, value in fields:
            ET.SubElement(child, name).text = str(value)


def series(rung, column=3):
    """Return the coherent 1-row binding, or fail for normalization.

    No OUT_BLK means an unwired Q port, never a fabricated output write.
    Input-only native graphs use the existing Timer/Left port names; acceptance
    of that previously unobserved combination remains explicitly unverified.
    """
    _, rung = split_label(rung)
    decoded = body(rung)
    if decoded is None:
        fail("timer graphics require a native timer block")
    at = next(i for i, line in enumerate(decoded) if line.startswith("IN "))
    inputs, outputs = decoded[:at], decoded[at + 1:]
    target = decoded[at].split(maxsplit=1)[1]
    items, width = [], 0
    for i, line in enumerate(inputs):
        parts = line.split(maxsplit=1)
        if (
            len(parts) != 2 or parts[0] not in SERIES
            or (i == 0 and not parts[0].startswith("LD"))
            or (i > 0 and parts[0].startswith("LD"))
            or parts[1] in ("0", "1")
        ):
            fail("timer series input requires normalization")
        op, arg = parts
        if arg.startswith("["):
            if op not in ("LD", "AND"):
                fail("timer negated/edge comparison requires normalization")
            typ, arg, span = "Comparison", arg[1:-1].strip(), 2
        else:
            typ, span = contact_type(op), 1
        items.append((typ, arg, 0, width, "Left, Right"))
        width += span
    if column not in (1, 2, 3) or width > column:
        fail("timer series input exceeds its graphical column; normalize")
    items += [("Line", "", 0, c, "Left, Right") for c in range(width, column)]
    if not outputs:
        return items + [("Timer", target, 0, column, "Left")]
    if len(outputs) != 2 or outputs[0] != "LD " + target + ".Q":
        fail("timer output logic requires normalization")
    action = outputs[1].split(maxsplit=1)
    if len(action) != 2 or action[0] not in ("ST", "S", "R"):
        fail("timer output action requires normalization")
    items += [("Timer", target, 0, column, "Left, Right")]
    items += [("Line", "", 0, c, "Left, Right") for c in range(column + 2, 10)]
    items.append(({"ST": "Coil", "S": "SetCoil", "R": "ResetCoil"}[action[0]], action[1], 0, 10, "Left"))
    return items


def simple(rung):
    try:
        series(rung)
    except ValueError:
        return False
    return True


def check_graph(node, lines, resources=None, level_token=None):
    from .timer_graph import verify

    graph = node.find("LadderElements")
    if graph is None or not len(graph):
        if node.findtext("IsLadderSelected", "false").lower() == "true":
            fail("selected Timer rung has no graphics")
        return
    allowed = {"ElementType", "Descriptor", "Comment", "Symbol", "Row", "Column", "ChosenConnection", "ComparisonExpression"}
    actual = []
    if graph.attrib or (graph.text or "").strip():
        fail("unsupported Timer graph text/attributes")
    for e in graph:
        if (
            e.tag != "LadderEntity" or e.attrib or (e.text or "").strip()
            or (e.tail or "").strip()
            or any(c.tag not in allowed or c.attrib or len(c) or (c.tail or "").strip() for c in e)
            or any(n != 1 for n in Counter(c.tag for c in e).values())
        ):
            fail("unsupported or duplicate Timer graphical field")
        try:
            row, col = int(e.findtext("Row", "0")), int(e.findtext("Column", "-1"))
        except ValueError:
            fail("invalid Timer graphical coordinates")
        typ = e.findtext("ElementType", "")
        expression = e.findtext("ComparisonExpression", "")
        descriptor = e.findtext("Descriptor", "")
        if expression and (typ != "Comparison" or descriptor):
            fail("unexpected Timer graphical expression field")
        actual.append((typ, expression if typ == "Comparison" else descriptor, row, col, e.findtext("ChosenConnection", "")))
    count = sum(typ == "Timer" for typ, _, _, _, _ in actual)
    if count > 1:
        if type(level_token) is not str:
            fail("multiple Timer graph blocks require the actual management-level token")
        if functional_level(level_token) < (10, 1):
            fail("multiple function blocks in one native rung require functional level >=10.1")
    return verify(actual, lines, resources)
