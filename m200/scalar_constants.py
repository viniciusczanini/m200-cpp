"""Aliased KW/KD/KF scalar constants and native XML, G02.

512 shared constant words: P24-26, G27-29,49-54. XML entry names/fields
are present in research/downloads/public-projects/flow-original-{jump,loop}.smbp.
This is an implementation contract, not an editor acceptance observation.
"""

import math
import re
import struct
from xml.etree.ElementTree import SubElement

from .model import fail

PATTERN = r"%K[WDF](?:0|[1-9][0-9]*)(?:\[%MW(?:0|[1-9][0-9]*)\])?"
REFERENCE = re.compile(PATTERN)
READS = {"read_constant_word": "i16", "read_constant_dword": "i32", "read_constant_real": "f32"}
KINDS = {"W": "i16", "D": "i32", "F": "f32"}
WIDTHS = {"i16": 1, "i32": 2, "f32": 2}
CLASSES = {"ConstantWord": "i16", "ConstantDword": "i32", "ConstantReal": "f32"}
COLLECTIONS = (("ConstantWords", "ConstantWord", "W"),
               ("ConstantDoubleWords", "ConstantDoubleWord", "D"),
               ("ConstantMemoryFloats", "ConstantFloat", "F"))


def parse(text, writable=False):
    if not text.startswith("%K"):
        return None
    match = re.fullmatch(r"%K([WDF])(0|[1-9][0-9]*)(?:\[%MW(0|[1-9][0-9]*)\])?", text)
    if not match or writable:
        fail("invalid or read-only constant address: " + text)
    kind, index = KINDS[match[1]], int(match[2])
    if index + WIDTHS[kind] > 512 or (match[3] and int(match[3]) >= 8000):
        fail("constant address exceeds shared 512-word bank: " + text)
    return kind, index, int(match[3]) if match[3] is not None else None


def validate(constants):
    if not isinstance(constants, dict) or any(type(i) is not int or not 0 <= i < 512 or type(v) is not int or not 0 <= v <= 65535 for i, v in constants.items()):
        fail("constant image requires raw 16-bit cells indexed 0..511")


def put(constants, index, kind, value):
    width = WIDTHS[kind]
    if not 0 <= index <= 512 - width:
        fail("constant initializer exceeds shared 512-word bank")
    if kind == "f32":
        if not math.isfinite(value):
            fail("constant REAL initializer must be finite")
        try:
            raw = struct.unpack("<I", struct.pack("<f", value))[0]
        except OverflowError:
            fail("constant REAL initializer exceeds binary32")
    else:
        bound = 1 << (16 * width - 1)
        if not -bound <= value < bound:
            fail("constant initializer exceeds signed width")
        raw = int(value) & ((1 << (16 * width)) - 1)
    for offset in range(width):
        cell = (raw >> (16 * offset)) & 65535
        if index + offset in constants and constants[index + offset] != cell:
            fail("conflicting aliased constant initializers")
        constants[index + offset] = cell


def read_configs(sw):
    constants, symbols = {}, {}
    for collection, entry, prefix in COLLECTIONS:
        node = sw.find(collection)
        if node is None:
            continue
        if node.attrib or any(item.tag != entry for item in node):
            fail("unsupported constant collection shape")
        seen = set()
        for item in node:
            names = [part.tag for part in item]
            if item.attrib or len(names) != len(set(names)) or set(names) - {"Address", "Index", "Value", "Symbol", "Comment"} or any(len(part) or part.attrib for part in item):
                fail("unsupported native constant fields")
            addr = item.findtext("Address", "")
            parsed = parse(addr)
            if parsed is None or addr in seen or addr != "%K" + prefix + item.findtext("Index", "") or parsed[2] is not None:
                fail("invalid or duplicate native constant identity")
            seen.add(addr)
            text = item.findtext("Value", "0")
            try:
                value = float(text) if prefix == "F" else int(text)
            except (ValueError, OverflowError):
                fail("invalid native constant value")
            put(constants, parsed[1], parsed[0], value)
            if item.findtext("Symbol"):
                symbols[addr] = item.findtext("Symbol")
    return constants, symbols


def write_configs(program, sw):
    validate(program.constants)
    count = extent(program)
    allocation = sw.find("ConstantWordsMemoryAllocation")
    if allocation is not None:
        sw.remove(allocation)
    # Empty/default allocation is observed in both native reference projects.
    # Anchor the declared extent with a real KW object rather than guessing the
    # unobserved enum/binding of a forced constant allocation.
    SubElement(sw, "ConstantWordsMemoryAllocation")
    for collection, _, _ in COLLECTIONS:
        old = sw.find(collection)
        if old is not None:
            sw.remove(old)
    nodes = {prefix: SubElement(sw, collection) for collection, _, prefix in COLLECTIONS}
    # One canonical KW image suffices to preserve all aliased typed identities.
    # Typed views actually referenced by the program are emitted coherently too.
    text = " ".join(" ".join(r) for r in program.rungs) + " " + " ".join(program.symbols)
    for definition in program.subroutines.values():
        text += " " + " ".join(" ".join(r) for r in definition.rungs)
    identities = {(str(i), "W") for i in program.constants}
    if count:
        identities.add((str(count - 1), "W"))
    identities.update((m[2], m[1]) for m in re.finditer(r"%K([DF])([0-9]+)", text))
    for index_text, prefix in sorted(identities, key=lambda value: (int(value[0]), value[1])):
        index = int(index_text)
        kind = KINDS[prefix]
        raw = program.constants.get(index, 0)
        if kind != "i16":
            raw |= program.constants.get(index + 1, 0) << 16
        if kind == "f32":
            value = format(struct.unpack("<f", struct.pack("<I", raw))[0], ".9g")
            if not math.isfinite(float(value)):
                fail("non-finite aliased constant view cannot be serialized as native REAL metadata")
        else:
            width = 16 * WIDTHS[kind]
            value = str(raw - (1 << width) if raw >= (1 << (width - 1)) else raw)
        entry = {"W": "ConstantWord", "D": "ConstantDoubleWord", "F": "ConstantFloat"}[prefix]
        item = SubElement(nodes[prefix], entry)
        addr = "%K" + prefix + index_text
        for name, value_text in (("Address", addr), ("Index", index_text), ("Value", value)):
            SubElement(item, name).text = value_text
        if addr in program.symbols:
            SubElement(item, "Symbol").text = program.symbols[addr]


def cpp_declarations(constants):
    return ["plc::ConstantWord native_constant_%d{%d,%d};" % (i, i, v - 65536 if v >= 32768 else v) for i, v in sorted(constants.items())]


def extent(program):
    text = " ".join(" ".join(r) for r in program.rungs) + " " + " ".join(program.symbols)
    for definition in program.subroutines.values():
        text += " " + " ".join(" ".join(r) for r in definition.rungs)
    needed = max(program.constants, default=-1) + 1
    for match in REFERENCE.finditer(text):
        kind, index, _ = parse(match[0])
        needed = max(needed, index + WIDTHS[kind])
    explicit = program.metadata.get("constant_words")
    if explicit is not None and (type(explicit) is not int or not needed <= explicit <= 512 or explicit < 1):
        fail("constant allocation does not cover configured/referenced shared cells")
    return explicit if explicit is not None else needed


def has_indexed(program):
    rungs = program.rungs + [r for definition in program.subroutines.values() for r in definition.rungs]
    return any("[" in match[0] for rung in rungs for line in rung for match in REFERENCE.finditer(line))
