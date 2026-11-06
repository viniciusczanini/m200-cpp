"""Observed full-pin communication bodies and their exact native Ladder binding.

The execution IR remains the established six-line update followed by four
qualified status stores. This module never extends parse_block's return contract.
"""

from dataclasses import dataclass
import json
import re

from .communication import block_address, parse_block
from .flow import split_label
from .model import fail
from .jsonio import loads


STATUS_ORDER = ("DONE", "BUSY", "ABORTED", "ERROR")
CLASSES = {
    "READ_VAR": "ReadVarBasic",
    "WRITE_VAR": "WriteVarBasic",
    "WRITE_READ_VAR": "WriteReadVarBasic",
}
OBJECTS = {"READ_VAR": 1, "WRITE_VAR": 2, "WRITE_READ_VAR": 0}
ORIGIN_MARKER = "\nM200_CPP_FULL_PIN_ORIGINS="
ORIGIN_LIMIT = 65536


def _memory(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"%M(?:0|[1-9][0-9]{0,3})", value
    ):
        fail("unverified full-pin memory contact/coil profile")
    if int(value[2:]) >= 1024:
        fail("full-pin memory contact/coil exceeds target range")
    return value


@dataclass(frozen=True)
class FullBody:
    key: str
    execute: str
    abort: str
    outputs: tuple

    def native_lines(self):
        lines = [
            "BLK " + self.key,
            "LD " + self.execute,
            "EXECUTE",
            "LD " + self.abort,
            "ABORT",
            "OUT_BLK",
        ]
        for status, target in zip(STATUS_ORDER, self.outputs):
            lines.extend(["LD " + status, "ST " + target])
        return lines + ["END_BLK"]

    def canonical(self, label=None):
        first = [
            "BLK " + self.key,
            "LD " + self.execute,
            "EXECUTE",
            "LD " + self.abort,
            "ABORT",
            "END_BLK",
        ]
        if label is not None:
            first.insert(0, label + ":")
        return [first] + [
            ["LD " + self.key + "." + status, "ST " + target]
            for status, target in zip(STATUS_ORDER, self.outputs)
        ]


def full_candidate(raw):
    """Distinguish the new native surface from existing four/six-line imports."""
    _, lines = split_label(raw)
    if not lines or not lines[0].startswith("BLK %"):
        return False
    key = lines[0].split(maxsplit=1)[1]
    return key.startswith(("%READ_VAR", "%WRITE_VAR", "%WRITE_READ_VAR")) and (
        len(lines) not in (4, 6) or "OUT_BLK" in lines
    )


def parse_full_body(raw):
    _, lines = split_label(raw)
    if len(lines) != 15:
        fail("unsupported full-pin communication body length")
    first = lines[0].split(maxsplit=1)
    if len(first) != 2 or first[0] != "BLK":
        fail("invalid full-pin communication block")
    key = first[1]
    block_address(key)
    if (lines[2], lines[4], lines[5], lines[-1]) != (
        "EXECUTE",
        "ABORT",
        "OUT_BLK",
        "END_BLK",
    ):
        fail("unsupported full-pin communication control layout")

    def operand(line, op):
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or parts[0] != op:
            fail("unverified full-pin contact/coil action")
        return _memory(parts[1])

    execute, abort = operand(lines[1], "LD"), operand(lines[3], "LD")
    outputs = []
    for index, status in enumerate(STATUS_ORDER):
        if lines[6 + index * 2] != "LD " + status:
            fail("unsupported full-pin communication status order")
        outputs.append(operand(lines[7 + index * 2], "ST"))
    return FullBody(key, execute, abort, tuple(outputs))


def check_profile(root, configurations, body):
    if root.findtext("ManagementLevel") != "FunctLevelMan21_0":
        fail("unverified full-pin communication functional-level profile")
    kind, _ = block_address(body.key)
    config = configurations.get(body.key)
    if config is None or config.kind != kind:
        fail("undefined or mismatched full-pin communication configuration")
    if config.link != "SL1" or config.obj_type != OBJECTS[kind]:
        fail("unverified full-pin communication link/object profile")


def graphics(body):
    kind, _ = block_address(body.key)
    return (
        [
            ("NormalContact", body.execute, 0, 0, "Left, Right"),
            ("NormalContact", body.abort, 1, 0, "Left, Right"),
            (CLASSES[kind], body.key, 0, 1, "Left, Right"),
        ]
        + [
            ("Line", "", row, column, "Left, Right")
            for column in (5, 6, 7, 8, 9)
            for row in (0, 1, 2, 3)
        ]
        + [("Coil", target, row, 10, "Left") for row, target in enumerate(body.outputs)]
    )


def _plain(node):
    # The generic parser already rejects attributes/duplicate singletons. Keep
    # this newly owned shape strict about mixed content and scalar fields too.
    for child in node.iter():
        if child.attrib or (child.tail or "").strip():
            fail("unsupported full-pin XML attributes or mixed content")
        if len(child) and (child.text or "").strip():
            fail("unsupported full-pin XML mixed content")


def check_graph(rung_node, body):
    _plain(rung_node)
    if rung_node.findtext("IsLadderSelected") not in ("true", "false"):
        fail("invalid full-pin Ladder selection")
    graph = rung_node.find("LadderElements")
    if graph is None or len(graph) != 27:
        fail("full-pin communication requires its complete observed 27-entity graph")
    actual = []
    required = {"ElementType", "Descriptor", "Row", "Column", "ChosenConnection"}
    allowed = required | {"Comment", "Symbol"}
    for entity in graph:
        if entity.tag != "LadderEntity" or any(len(child) for child in entity):
            fail("unsupported full-pin Ladder entity")
        names = [child.tag for child in entity]
        if (
            len(names) != len(set(names))
            or set(names) - allowed
            or required - set(names)
        ):
            fail("unsupported full-pin Ladder entity fields")
        row, column = entity.findtext("Row"), entity.findtext("Column")
        if row not in ("0", "1", "2", "3") or column not in (
            "0",
            "1",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
        ):
            fail("unsupported full-pin Ladder coordinates")
        actual.append(
            (
                entity.findtext("ElementType"),
                entity.findtext("Descriptor") or "",
                int(row),
                int(column),
                entity.findtext("ChosenConnection"),
            )
        )
    if sorted(actual) != sorted(graphics(body)):
        fail("full-pin communication IL and Ladder graphics do not agree")


def import_rung(rung_node, raw, root, configurations):
    if not full_candidate(raw):
        return None
    body = parse_full_body(raw)
    check_profile(root, configurations, body)
    # Check original geometry/IL before any canonical representation can hide it.
    check_graph(rung_node, body)
    label, _ = split_label(raw)
    return body.canonical(label)


def import_origins(rung_node, fallback):
    """Recover provenance only; whole-program validation checks origin values."""
    comment = rung_node.findtext("MainComment", "")
    if ORIGIN_MARKER not in comment:
        return [
            {
                **fallback,
                "generated": fallback["generated"] + "; full-pin part " + str(i),
            }
            for i in range(5)
        ]
    if comment.count(ORIGIN_MARKER) != 1:
        fail("ambiguous full-pin source origin payload")
    payload = comment.split(ORIGIN_MARKER, 1)[1]
    if len(payload.encode("utf-8")) > ORIGIN_LIMIT:
        fail("full-pin source origin payload exceeds 64 KiB")
    origins = loads(payload)
    if not isinstance(origins, list) or len(origins) != 5:
        fail("invalid full-pin source origin mapping")
    return origins


def origin_comment(origins):
    payload = json.dumps(origins, separators=(",", ":"), ensure_ascii=True)
    if len(payload.encode("utf-8")) > ORIGIN_LIMIT:
        fail("full-pin source origin payload exceeds 64 KiB")
    return ORIGIN_MARKER + payload


def human_comment(rung_node):
    return rung_node.findtext("MainComment", "").split(ORIGIN_MARKER, 1)[0]


def source_human_comment(program, body):
    # A source comment is provenance only. Match by the actual unique FB key,
    # rather than trusting stale canonical indices after unrelated edits.
    groups = program.metadata.get("native_full_pin_groups", [])
    if isinstance(groups, list):
        for group in groups:
            if isinstance(group, dict) and group.get("key") == body.key:
                origin = group.get("origin")
                if isinstance(origin, dict) and isinstance(
                    origin.get("main_comment"), str
                ):
                    return origin["main_comment"]
    return ""


def serialized_rungs(program, root):
    """Yield views without mutating the caller or trusting origin metadata."""
    index = 0
    while index < len(program.rungs):
        raw = program.rungs[index]
        label, lines = split_label(raw)
        body = None
        if (
            len(lines) == 6
            and lines[0].startswith("BLK ")
            and lines[0].split(maxsplit=1)[1] in program.communications
            and index + 4 < len(program.rungs)
        ):
            key, execute, abort = parse_block(lines)
            outputs = []
            for offset, status in enumerate(STATUS_ORDER, 1):
                following = program.rungs[index + offset]
                # Interior labels are control entries even when currently unused.
                if (
                    len(following) != 2
                    or following[0] != "LD " + key + "." + status
                    or not following[1].startswith("ST ")
                ):
                    break
                outputs.append(following[1][3:])
            if len(outputs) == 4:
                if execute[0] != "LD" or abort[0] != "LD":
                    fail("unverified full-pin communication input contact profile")
                candidate = FullBody(
                    key,
                    _memory(execute[1]),
                    _memory(abort[1]),
                    tuple(_memory(target) for target in outputs),
                )
                check_profile(root, program.communications, candidate)
                body = candidate
        if body is None:
            yield index, raw, None, 1
            index += 1
        else:
            native = body.native_lines()
            if label is not None:
                native.insert(0, label + ":")
            yield index, native, body, 5
            index += 5
