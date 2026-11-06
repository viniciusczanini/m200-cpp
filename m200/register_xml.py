"""Isolated native Register configuration codec, not wired into the compiler.

This foundation does not enable whole-project Register import/export, C++/IR/SDK
support, graphics or execution. It validates only the owned Registers collection,
not allocations or hardware. Actual CE40T saves establish an omitted FIFO default
and an explicit Lifo row; the mode evidence is in REGISTER-IMPLEMENTATION-PLAN.md.
"""

from collections.abc import Mapping
from enum import Enum
import xml.etree.ElementTree as ET

from .model import fail


class RegisterMode(Enum):
    FIFO = "Fifo"
    LIFO = "Lifo"


def _index(value):
    if type(value) is not int or not 0 <= value < 4:
        fail("register index must be an integer in 0..3")
    return value


def _collection(sw):
    if not isinstance(sw, ET.Element) or sw.tag != "SoftwareConfiguration":
        fail("SoftwareConfiguration required for register configuration")
    nodes = []
    for node in sw:
        if isinstance(node.tag, str) and node.tag.rsplit("}", 1)[-1] == "Registers":
            if node.tag != "Registers":
                fail("unsupported register configuration namespace")
            nodes.append(node)
    if len(nodes) > 1:
        fail("duplicate Registers collection")
    return nodes[0] if nodes else None


def _read_collection(node):
    result = {}
    if node is None:
        return result
    if node.attrib or (node.text or "").strip():
        fail("unsupported Registers attributes or text")
    for entry in node:
        if (
            entry.tag != "Register"
            or entry.attrib
            or (entry.text or "").strip()
            or (entry.tail or "").strip()
        ):
            fail("unsupported Register entry")
        fields = {}
        for value in entry:
            if value.tag not in ("Address", "Index", "Type"):
                fail("unknown register configuration field")
            if value.tag in fields:
                fail("duplicate register configuration field")
            if value.attrib or len(value) or (value.tail or "").strip():
                fail("register configuration fields must be scalar and unattributed")
            fields[value.tag] = value.text or ""
        raw_index = fields.get("Index")
        if raw_index not in ("0", "1", "2", "3"):
            fail("register Index requires canonical ASCII decimal 0..3")
        index = int(raw_index)
        if fields.get("Address") != "%R" + raw_index or index in result:
            fail("invalid or duplicate register Address/Index")
        try:
            result[index] = RegisterMode(fields.get("Type", "Fifo"))
        except ValueError:
            fail("unsupported or noncanonical register Type")
    return result


def read_registers(sw, referenced_ids=()):
    """Return explicit modes plus known FIFO defaults for referenced valid IDs.

    Duplicate references are natural and are deduplicated. Explicit configuration
    wins over defaults. Neither the input tree nor the caller's values is modified.
    """
    result = _read_collection(_collection(sw))
    try:
        references = iter(referenced_ids)
    except TypeError:
        fail("referenced register IDs must be iterable")
    for index in references:
        result.setdefault(_index(index), RegisterMode.FIFO)
    return result


def write_registers(configs, sw):
    """Stage and replace Registers only, retaining explicit modes and identities.

    Modes must be RegisterMode members. Existing unknown owned data is refused,
    never silently discarded. Explicit Fifo is accepted by the native editor but
    may be omitted by its canonical save; referenced IDs restore that default.
    """
    previous = _collection(sw)
    _read_collection(previous)
    if not isinstance(configs, Mapping):
        fail("register configurations must be an index-to-mode mapping")
    checked = {}
    for index, mode in configs.items():
        _index(index)
        if type(mode) is not RegisterMode:
            fail("register mode must be a RegisterMode member")
        if index in checked:
            fail("duplicate register configuration index")
        checked[index] = mode
    fresh = ET.Element("Registers")
    for index, mode in sorted(checked.items()):
        entry = ET.SubElement(fresh, "Register")
        ET.SubElement(entry, "Address").text = "%R" + str(index)
        ET.SubElement(entry, "Index").text = str(index)
        ET.SubElement(entry, "Type").text = mode.value
    if previous is None:
        sw.append(fresh)
    else:
        position = list(sw).index(previous)
        fresh.tail = previous.tail
        sw.remove(previous)
        sw.insert(position, fresh)
