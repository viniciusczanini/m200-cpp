"""Strict DR/SBR/SC native persistence, grounded in installed entity metadata.

Default rows: authored Material Handling M200.smbe. Active properties/defaults:
Entities.dll Drum StepsNumber=8, BitForDrum.Outputs='', Step.Used=false and
Available=true. Native acceptance of new active CE40T rows is pending.
"""
import xml.etree.ElementTree as ET
from .model import fail
from .sequences import (
    ShiftBitRegisterConfig, StepCounterConfig, DrumConfig, DrumCam, identity,
    FAMILIES, CONFIGS,
)

COLLECTIONS = {"SBR": ("ShiftBitRegisters", "ShiftBitRegister"), "SC": ("StepCounters", "StepCounter"), "DR": ("Drums", "Drum")}
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


def _container(node):
    if node.attrib or (node.text or "").strip() or (node.tail or "").strip():
        fail("unsupported sequence XML attributes/mixed content: " + node.tag)


def _fields(node, allowed, required=()):
    _container(node)
    result = {}
    for child in node:
        if child.tag not in allowed or child.tag in result:
            fail("duplicate/unknown sequence XML field: " + child.tag)
        result[child.tag] = child
    if set(required) - result.keys():
        fail("missing sequence XML field")
    return result


def _text(node):
    if node.attrib or len(node) or (node.tail or "").strip():
        fail("sequence XML scalar required")
    return node.text or ""


def _symbols(node, count):
    _container(node)
    if len(node) != count:
        fail("incorrect native symbol vector length")
    values = []
    for item in node:
        if item.tag != "string" or len(item) or (item.tail or "").strip():
            fail("invalid sequence symbol XML")
        if item.attrib == {NIL: "true"} and not (item.text or "").strip():
            values.append(None)
        elif not item.attrib:
            values.append(item.text or "")
        else:
            fail("unsupported sequence symbol XML attributes")
    return values


def _number(node, low, high, default=None):
    text = str(default) if node is None and default is not None else _text(node) if node is not None else ""
    if text not in tuple(str(i) for i in range(low, high + 1)):
        fail("noncanonical sequence configuration integer")
    return int(text)


def _boolean(node, default):
    if node is None:
        return default
    value = _text(node)
    if value not in ("true", "false"):
        fail("invalid sequence configuration boolean")
    return value == "true"


def read_sequences(sw):
    result = {name: {} for name in FAMILIES.values()}
    for family, (collection, entry_type) in COLLECTIONS.items():
        nodes = sw.findall(collection)
        if len(nodes) > 1:
            fail("duplicate native sequence collection")
        if not nodes:
            continue
        _container(nodes[0])
        for node in nodes[0]:
            if node.tag != entry_type:
                fail("unknown native sequence entry")
            allowed = {"Address", "Index"} | ({"Bits", "StepsNumber"} if family == "DR" else {"BitSymbols", "LastWritenBit"} if family == "SBR" else {"StepSymbols"})
            fields = _fields(node, allowed, ("Address", "Index"))
            index = _number(fields["Index"], 0, 7)
            if _text(fields["Address"]) != "%" + family + str(index) or index in result[FAMILIES[family]]:
                fail("invalid or duplicate native sequence Address/Index")
            if family == "SBR":
                cfg = ShiftBitRegisterConfig(
                    _symbols(fields["BitSymbols"], 16) if "BitSymbols" in fields else [None] * 16,
                    _number(fields.get("LastWritenBit"), 0, 0, 0),
                )
            elif family == "SC":
                cfg = StepCounterConfig(_symbols(fields["StepSymbols"], 256) if "StepSymbols" in fields else [None] * 256)
            else:
                count = _number(fields.get("StepsNumber"), 1, 8, 8)
                cams = []
                bits = fields.get("Bits")
                if bits is None or len(bits) != 16:
                    fail("Drum requires sixteen native cam records")
                _container(bits)
                slots = set()
                for bit in bits:
                    if bit.tag != "BitForDrum":
                        fail("invalid native Drum cam")
                    values = _fields(bit, {"Index", "Steps", "Outputs"}, ("Index", "Steps"))
                    slot = _number(values["Index"], 0, 15)
                    if slot in slots:
                        fail("duplicate native Drum cam index")
                    slots.add(slot)
                    steps = values["Steps"]
                    _container(steps)
                    if len(steps) != 8:
                        fail("Drum cam requires eight native Step entries")
                    mask = 0
                    for i, step in enumerate(steps):
                        if step.tag != "Step":
                            fail("invalid native Drum Step")
                        state = _fields(step, {"Used", "Available"})
                        used = _boolean(state.get("Used"), False)
                        available = _boolean(state.get("Available"), True)
                        if available != (i < count):
                            # Installed ctor default has all available for eight
                            # steps; non-default counts need matching UI flags.
                            fail("Drum Available flags disagree with StepsNumber")
                        mask |= int(used) << i
                    output = _text(values["Outputs"]) if "Outputs" in values else ""
                    if output:
                        cams.append(DrumCam(slot, output, mask))
                    elif mask:
                        fail("unbound nonzero Drum cam cannot be silently discarded")
                cfg = DrumConfig(count, cams)
            result[FAMILIES[family]][index] = cfg
    return result


def write_sequences(program, sw):
    # Validate existing owned configuration before replacement. Stage all three
    # collections first; unknown data never disappears behind a successful write.
    read_sequences(sw)
    fresh = []
    for family, (collection, entry_type) in COLLECTIONS.items():
        node = ET.Element(collection)
        for index, cfg in sorted(getattr(program, FAMILIES[family]).items()):
            identity("%" + family + str(index))
            if type(cfg) is not CONFIGS[family]:
                fail("wrong native sequence configuration type")
            entry = ET.SubElement(node, entry_type)
            ET.SubElement(entry, "Address").text = "%" + family + str(index)
            ET.SubElement(entry, "Index").text = str(index)
            if family in ("SBR", "SC"):
                if family == "SBR":
                    if cfg.last_writen_bit != 0:
                        fail("nonzero SBR LastWritenBit has no established persistence semantics")
                    ET.SubElement(entry, "LastWritenBit").text = "0"
                symbols = ET.SubElement(entry, "BitSymbols" if family == "SBR" else "StepSymbols")
                for value in cfg.bit_symbols if family == "SBR" else cfg.step_symbols:
                    child = ET.SubElement(symbols, "string")
                    if value is None:
                        child.set(NIL, "true")
                    else:
                        child.text = value
            else:
                ET.SubElement(entry, "StepsNumber").text = str(cfg.steps)
                bits = ET.SubElement(entry, "Bits")
                cams = {c.slot: c for c in cfg.cams}
                for slot in range(16):
                    bit = ET.SubElement(bits, "BitForDrum")
                    ET.SubElement(bit, "Index").text = str(slot)
                    steps = ET.SubElement(bit, "Steps")
                    cam = cams.get(slot)
                    for i in range(8):
                        step = ET.SubElement(steps, "Step")
                        if cam and cam.mask & (1 << i):
                            ET.SubElement(step, "Used").text = "true"
                        if i >= cfg.steps:
                            ET.SubElement(step, "Available").text = "false"
                    if cam:
                        ET.SubElement(bit, "Outputs").text = cam.output
        fresh.append(node)
    for node in fresh:
        previous = sw.find(node.tag)
        if previous is None:
            sw.append(node)
        else:
            node.tail = previous.tail
            sw[list(sw).index(previous)] = node
