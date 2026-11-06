"""Closed SMBP communication serialization observed in authored public projects.

READ_VAR supports MW/I/IW/Q; WRITE_VAR supports MW/Q. Bit enum strings are
backed by exact TM200CE40T official-editor saved/reopened fixtures.
See docs/capabilities/MODBUS-FORMAT-RESEARCH.md for pinned sources and gaps.
This module never creates port settings or substitutes a controller profile.
"""

import ipaddress
import re
import xml.etree.ElementTree as ET

from .communication import block_address
from .model import fail
from .levels import functional_level
from .modbus import ModbusConfig, validate_config


_ASSEMBLY = "SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07"
_PREFIX = (
    "SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks."
)
_INT_TYPE = (
    _PREFIX
    + "FbParameterElementRangeType`1[[System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]], "
    + _ASSEMBLY
)
_BLOCK_TYPES = {
    k: _PREFIX + "Com." + v + ", " + _ASSEMBLY
    for k, v in [("READ_VAR", "ReadVarBasic"), ("WRITE_VAR", "WriteVarBasic")]
}
_LINKS = {"SerialLine1": "SL1", "EthernetLink": "ETH1"}
_OBJECTS = {"MW": 0, "I": 1, "Q": 2, "IW": 3}
_PARAMETERS = {
    "Link": "link",
    "RemoteDeviceId": "id",
    "Timeout": "timeout_100ms",
    "ObjType": "obj_type",
    "FirstObj": "first_obj",
    "Quantity": "quantity",
    "IndexData": "index_data",
}
_ENUMS = {"Link": "FBComLinkParameterEnums", "ObjType": "FBComObjTypeParameterEnums"}


def _enum_type(name):
    return (
        _PREFIX
        + "FbParameterElementEnumType`1[["
        + _PREFIX
        + "Enums."
        + name
        + ", "
        + _ASSEMBLY
        + "]], "
        + _ASSEMBLY
    )


def allowed_attribute(tag, name, value):
    """Recognize only the observed .NET Type attribute in its exact field."""
    if name != "Type":
        return False
    if tag == "IFunctionBlock":
        return value in _BLOCK_TYPES.values()
    if tag in _ENUMS:
        return value == _enum_type(_ENUMS[tag])
    return tag in _PARAMETERS and value == _INT_TYPE


def _guard(node):
    for name, value in node.attrib.items():
        if not allowed_attribute(node.tag, name, value):
            fail("unsupported communication XML attribute: " + node.tag + "/" + name)
    if len(node) and (node.text or "").strip():
        fail("mixed communication XML content: " + node.tag)
    for child in node:
        if (child.tail or "").strip():
            fail("mixed communication XML tail: " + child.tag)
        _guard(child)


def _children(node, allowed, required=(), repeated=()):
    if (node.text or "").strip():
        fail("communication container must not contain scalar text: " + node.tag)
    found = {}
    for child in node:
        if child.tag not in allowed:
            fail("unsupported communication XML field: " + node.tag + "/" + child.tag)
        if child.tag in found and child.tag not in repeated:
            fail("duplicate communication XML field: " + node.tag + "/" + child.tag)
        found[child.tag] = child
    if set(required) - set(found):
        fail("missing communication XML field in " + node.tag)
    return found


def _scalar(node):
    if len(node) or node.attrib:
        fail("communication XML value must be scalar: " + node.tag)
    return node.text or ""


def _integer(text, name, low=0, high=None):
    if not re.fullmatch(r"0|[1-9][0-9]*", text):
        fail("invalid communication integer: " + name)
    # Avoid Python's implementation-dependent huge-integer conversion limit.
    if len(text) > 18:
        fail("communication integer is too large: " + name)
    number = int(text)
    if number < low or high is not None and number > high:
        fail("communication value out of range: " + name)
    return number


def _parameter(node):
    enum = _ENUMS.get(node.tag)
    expected = _enum_type(enum) if enum else _INT_TYPE
    if node.attrib != {"Type": expected}:
        fail("incorrect communication parameter Type: " + node.tag)
    value = _children(node, {"Value"}, {"Value"})["Value"]
    if value.attrib:
        fail("unsupported communication Value attributes")
    child = _children(value, {enum or "int"}, {enum or "int"})[enum or "int"]
    text = _scalar(child)
    if enum:
        choices = _LINKS if node.tag == "Link" else _OBJECTS
        if text not in choices:
            fail("unproven communication XML enum: " + text)
        return choices[text]
    return _integer(text, node.tag, 0, 2147483647)


def _address(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"%(?:WRITE_READ_VAR|WRITE_VAR|READ_VAR)(?:0|[1-9][0-9]?)", value
    ):
        fail("communication XML address requires a bounded ASCII decimal index")
    return block_address(value)


def read_blocks(sw):
    """Read the closed FunctionBlocks subset into native ModbusConfig values."""
    if sw is None or sw.tag != "SoftwareConfiguration":
        fail("SoftwareConfiguration required for communication blocks")
    containers = sw.findall("FunctionBlocks")
    if len(containers) > 1:
        fail("duplicate FunctionBlocks")
    if not containers:
        return {}
    container = containers[0]
    _guard(container)
    if container.attrib:
        fail("unsupported FunctionBlocks attributes")
    _children(container, {"IFunctionBlock"}, repeated={"IFunctionBlock"})
    result = {}
    for node in container:
        fields = _children(
            node,
            {"Address", "Index"} | set(_PARAMETERS),
            {"Address", "Index"} | set(_PARAMETERS),
        )
        address = _scalar(fields["Address"])
        kind, index = _address(address)
        if node.attrib != {"Type": _BLOCK_TYPES.get(kind)}:
            fail("unsupported or mismatched communication block Type")
        if (
            _integer(_scalar(fields["Index"]), "Index", 0, 31) != index
            or address in result
        ):
            fail("mismatched or duplicate communication block index")
        values = {field: _parameter(fields[tag]) for tag, field in _PARAMETERS.items()}
        result[address] = ModbusConfig(kind=kind, **values)
    return result


def _checked_config(address, config):
    kind, index = _address(address)
    validate_config(config)
    if kind != config.kind:
        fail("communication address and configuration kind differ")
    return kind, index


def write_blocks(program, sw):
    """Replace FunctionBlocks atomically after validating all serialized values."""
    if sw is None or sw.tag != "SoftwareConfiguration":
        fail("SoftwareConfiguration required for communication blocks")
    if len(sw.findall("FunctionBlocks")) > 1:
        fail("duplicate FunctionBlocks")
    fresh = ET.Element("FunctionBlocks")
    for address, config in program.communications.items():
        kind, index = _checked_config(address, config)
        if kind not in _BLOCK_TYPES or config.obj_type not in _OBJECTS.values():
            fail(
                "communication block or object XML enum is not established by authored evidence"
            )
        node = ET.SubElement(fresh, "IFunctionBlock", Type=_BLOCK_TYPES[kind])
        ET.SubElement(node, "Address").text = address
        ET.SubElement(node, "Index").text = str(index)
        for tag, field in _PARAMETERS.items():
            enum = _ENUMS.get(tag)
            value = getattr(config, field)
            if enum:
                choices = _LINKS if tag == "Link" else _OBJECTS
                value = next(key for key, item in choices.items() if item == value)
            else:
                _integer(str(value), tag, 0, 2147483647)
            part = ET.SubElement(
                node, tag, Type=_enum_type(enum) if enum else _INT_TYPE
            )
            ET.SubElement(ET.SubElement(part, "Value"), enum or "int").text = str(value)
    previous = sw.find("FunctionBlocks")
    if previous is None:
        sw.append(fresh)
    else:
        index = list(sw).index(previous)
        sw.remove(previous)
        sw.insert(index, fresh)


_SERIAL_ENUMS = {
    "Baud": {"Baud9600", "Baud19200"},
    "ModemReference": {"No Modem"},
    "Parity": {"ParityEven", "ParityNone"},
    "DataBits": {"DataBits8"},
    "StopBits": {"StopBits1"},
    "PhysicalMedium": {"PhysicalMediumRs485"},
    "TransmissionMode": {"TransmissionModeModbusRtu"},
    "Addressing": {"MasterAddressing", "SlaveAddressing"},
}
_SERIAL_FIXED = {
    "StartCharacterEnabled": "false",
    "FirstEndCharacterEnabled": "true",
    "SecondEndCharacterEnabled": "false",
    "FrameLengthReceivedAvailable": "false",
    "FrameReceivedTimeoutAvailable": "false",
    "InitCommand": "",
    "SendFrameCharacter": "false",
    "StartCharacter": "0",
    "FirstEndCharacter": "10",
    "FrameLengthReceived": "0",
    "FrameReceivedTimeout": "0",
    "SecondEndCharacter": "0",
}
_SERIAL_NUMBERS = {
    "TimeBetweenFrames",
    "ResponseTime",
    "MinTimeBetweenFrames",
    "SlaveId",
}


def validate_serial(node):
    """Validate observed RS485/RTU settings, without silently enabling a master."""
    if node is None or node.tag != "SerialLineConfiguration" or node.attrib:
        fail("invalid SerialLineConfiguration")
    _guard(node)
    fields = _children(
        node,
        set(_SERIAL_ENUMS) | set(_SERIAL_FIXED) | _SERIAL_NUMBERS | {"Polarization"},
    )
    for tag, part in fields.items():
        if tag == "Polarization":
            if part.attrib:
                fail("invalid serial polarization attributes")
            values = _children(part, {"Value", "Name"}, {"Value", "Name"})
            pair = (_scalar(values["Value"]), _scalar(values["Name"]))
            if pair not in {("0", "No"), ("1", "Yes")}:
                fail("invalid serial polarization pair")
            continue
        text = _scalar(part)
        if tag in _SERIAL_ENUMS and text not in _SERIAL_ENUMS[tag]:
            fail("unproven serial setting: " + tag)
        if tag in _SERIAL_FIXED and text != _SERIAL_FIXED[tag]:
            fail("active or unknown serial character-mode setting: " + tag)
        if tag in _SERIAL_NUMBERS:
            _integer(
                text,
                tag,
                1 if tag == "SlaveId" else 0,
                247 if tag == "SlaveId" else 65535,
            )
    return fields


_REMOTE_FIELDS = set(
    "DeviceId Address DeviceGeneralType DeviceTypeName DeviceTypeId SlaveAddress ResetVariable Name InitRequestUnitId ChannelUnitId Timeout".split()
)


def validate_remotes(node):
    """Return one-based FB indexes mapped to observed remote-server settings."""
    if node is None or node.tag not in {"Devices", "RemoteServers"} or node.attrib:
        fail("invalid Modbus remote-server container")
    _guard(node)
    _children(node, {"RemoteServer"}, repeated={"RemoteServer"})
    result = {}
    for server in node:
        if server.attrib:
            fail("unsupported RemoteServer attributes")
        fields = _children(server, _REMOTE_FIELDS, _REMOTE_FIELDS)
        values = {tag: _scalar(part) for tag, part in fields.items()}
        for tag, value in {
            "Address": "",
            "ResetVariable": "",
            "DeviceGeneralType": "IoScannerOther",
            "DeviceTypeName": "Generic Device",
            "DeviceTypeId": "23",
        }.items():
            if values[tag] != value:
                fail("unproven or active remote-server setting: " + tag)
        index = _integer(values["DeviceId"], "DeviceId", 0, 15)
        if index + 1 in result:
            fail("duplicate Modbus remote-server index")
        try:
            ip = ipaddress.IPv4Address(values["SlaveAddress"])
        except (ValueError, TypeError):
            fail("remote server requires a numeric IPv4 address")
        if ip.is_multicast or ip.is_unspecified or str(ip) == "255.255.255.255":
            fail("remote server requires a unicast IPv4 address")
        result[index + 1] = {
            "device_id": index,
            "ip": str(ip),
            "unit_id": _integer(values["ChannelUnitId"], "ChannelUnitId", 0, 255),
            "init_unit_id": _integer(
                values["InitRequestUnitId"], "InitRequestUnitId", 0, 255
            ),
            "timeout": _integer(values["Timeout"], "remote Timeout", 0, 65535),
            # No remote port element was observed. SlavePort is the LOCAL server.
            "port": 502,
        }
    return result


def _find(root, path):
    node = root
    for tag in path.split("/"):
        parts = node.findall(tag)
        if len(parts) != 1:
            fail("missing or duplicate communication configuration: " + path)
        node = parts[0]
    return node


def check_template_channels(root, configs):
    """Require explicit, matching template ports; never synthesize settings."""
    if not configs:
        return
    level = _scalar(_find(root, "ManagementLevel"))
    budget = 32 if functional_level(level) >= (10, 1) else 16
    links = set()
    for address, config in configs.items():
        _, index = _checked_config(address, config)
        if index >= budget:
            fail("communication instance requires functional level >= 10.1")
        links.add(config.link)
    if "SL1" in links:
        node = _find(root, "HardwareConfiguration/Plc/SerialLineConfiguration")
        validate_serial(node)
        _children(
            node,
            set(_SERIAL_ENUMS)
            | set(_SERIAL_FIXED)
            | _SERIAL_NUMBERS
            | {"Polarization"},
            {"Baud", "Parity", "DataBits", "StopBits", "ResponseTime"},
        )
        for tag, value in [
            ("Addressing", "MasterAddressing"),
            ("TransmissionMode", "TransmissionModeModbusRtu"),
            ("PhysicalMedium", "PhysicalMediumRs485"),
        ]:
            if node.findtext(tag) != value:
                fail("SL1 requires explicit RS485 Modbus RTU master configuration")
    if "ETH1" in links:
        tcp = _find(
            root, "HardwareConfiguration/Plc/Cpu/EthernetConfiguration/ModbusTcpSlave"
        )
        containers = [node for node in tcp if node.tag in {"Devices", "RemoteServers"}]
        if len(containers) != 1:
            fail("ETH1 requires one explicit remote-server configuration")
        remotes = validate_remotes(containers[0])
        for config in configs.values():
            if config.link == "ETH1" and config.id not in remotes:
                fail("ETH1 remote-server index is not configured")
