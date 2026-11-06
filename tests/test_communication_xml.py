import copy
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.model import CompileError, Program
from m200.modbus import ModbusConfig

try:
    from m200 import communication_xml as comm
except ImportError:
    comm = None


ASSEMBLY = "SchneiderElectric.SoMachineBasic.Entities, Version=1.0.0.0, Culture=neutral, PublicKeyToken=5beddbc0114a5f07"
PREFIX = (
    "SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks."
)
INT_TYPE = (
    PREFIX
    + "FbParameterElementRangeType`1[[System.Int32, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089]], "
    + ASSEMBLY
)


def enum_type(name):
    return (
        PREFIX
        + "FbParameterElementEnumType`1[["
        + PREFIX
        + "Enums."
        + name
        + ", "
        + ASSEMBLY
        + "]], "
        + ASSEMBLY
    )


def block(kind="READ_VAR", index=0, link="SerialLine1", obj="MW"):
    node = ET.Element(
        "IFunctionBlock",
        Type=PREFIX
        + "Com."
        + {"READ_VAR": "ReadVarBasic", "WRITE_VAR": "WriteVarBasic"}[kind]
        + ", "
        + ASSEMBLY,
    )
    ET.SubElement(node, "Address").text = "%" + kind + str(index)
    ET.SubElement(node, "Index").text = str(index)
    for tag, value in [
        ("Link", link),
        ("RemoteDeviceId", "1"),
        ("Timeout", "100"),
        ("ObjType", obj),
        ("FirstObj", "0"),
        ("Quantity", "1"),
        ("IndexData", "100"),
    ]:
        enum = {
            "Link": "FBComLinkParameterEnums",
            "ObjType": "FBComObjTypeParameterEnums",
        }.get(tag)
        part = ET.SubElement(node, tag, Type=enum_type(enum) if enum else INT_TYPE)
        ET.SubElement(ET.SubElement(part, "Value"), enum or "int").text = value
    return node


def software(*blocks):
    sw = ET.Element("SoftwareConfiguration")
    fb = ET.SubElement(sw, "FunctionBlocks")
    fb.extend(blocks)
    return sw


def serial():
    values = dict(
        Baud="Baud19200",
        ModemReference="No Modem",
        Parity="ParityEven",
        DataBits="DataBits8",
        StopBits="StopBits1",
        TimeBetweenFrames="10",
        ResponseTime="5",
        StartCharacterEnabled="false",
        FirstEndCharacterEnabled="true",
        SecondEndCharacterEnabled="false",
        FrameLengthReceivedAvailable="false",
        FrameReceivedTimeoutAvailable="false",
        InitCommand="",
        SendFrameCharacter="false",
        StartCharacter="0",
        FirstEndCharacter="10",
        FrameLengthReceived="0",
        FrameReceivedTimeout="0",
        SecondEndCharacter="0",
        PhysicalMedium="PhysicalMediumRs485",
        TransmissionMode="TransmissionModeModbusRtu",
        SlaveId="1",
        Addressing="MasterAddressing",
    )
    node = ET.Element("SerialLineConfiguration")
    for tag, value in values.items():
        ET.SubElement(node, tag).text = value
    pol = ET.SubElement(node, "Polarization")
    ET.SubElement(pol, "Value").text = "1"
    ET.SubElement(pol, "Name").text = "Yes"
    return node


def remotes(index=0):
    devices = ET.Element("Devices")
    node = ET.SubElement(devices, "RemoteServer")
    for tag, value in [
        ("DeviceId", str(index)),
        ("Address", ""),
        ("DeviceGeneralType", "IoScannerOther"),
        ("DeviceTypeName", "Generic Device"),
        ("DeviceTypeId", "23"),
        ("SlaveAddress", "10.0.0.3"),
        ("ResetVariable", ""),
        ("Name", "Device 0"),
        ("InitRequestUnitId", "255"),
        ("ChannelUnitId", "255"),
        ("Timeout", "10"),
    ]:
        ET.SubElement(node, tag).text = value
    return devices


def root():
    node = ET.Element("ProjectDescriptor")
    ET.SubElement(node, "ManagementLevel").text = "FunctLevelMan15_0"
    plc = ET.SubElement(ET.SubElement(node, "HardwareConfiguration"), "Plc")
    plc.append(serial())
    tcp = ET.SubElement(
        ET.SubElement(ET.SubElement(plc, "Cpu"), "EthernetConfiguration"),
        "ModbusTcpSlave",
    )
    tcp.append(remotes())
    return node


class CommunicationXMLTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(comm, "communication XML implementation is missing")

    def test_read_observed_serial_and_ethernet_wrappers(self):
        sw = software(block(), block("WRITE_VAR", 1, link="EthernetLink"))
        got = comm.read_blocks(sw)
        self.assertEqual(got["%READ_VAR0"], ModbusConfig(index_data=100))
        self.assertEqual(
            got["%WRITE_VAR1"],
            ModbusConfig(kind="WRITE_VAR", link="ETH1", index_data=100),
        )
        self.assertEqual(
            comm.read_blocks(software(block(obj="IW")))["%READ_VAR0"].function_code, 4
        )
        self.assertEqual(comm.read_blocks(ET.Element("SoftwareConfiguration")), {})

    def test_attributes_are_contextual_exact_type_allowlist(self):
        b = block()
        self.assertTrue(comm.allowed_attribute("IFunctionBlock", "Type", b.get("Type")))
        self.assertTrue(comm.allowed_attribute("Timeout", "Type", INT_TYPE))
        for tag, name, value in [
            ("int", "Type", INT_TYPE),
            ("Link", "Type", INT_TYPE),
            ("Quantity", "Type", enum_type("FBComLinkParameterEnums")),
            ("IFunctionBlock", "type", b.get("Type")),
            ("IFunctionBlock", "Type", b.get("Type") + " "),
            ("Timeout", "Type", INT_TYPE.replace("System.Int32", "System.Int64")),
        ]:
            with self.subTest(tag=tag, name=name):
                self.assertFalse(comm.allowed_attribute(tag, name, value))

    def test_read_rejects_duplicates_unknown_fields_and_malformed_wrappers(self):
        def duplicate(b):
            b.append(copy.deepcopy(b.find("Timeout")))

        def nested_duplicate(b):
            b.find("Timeout/Value").append(ET.Element("int"))

        def missing(b):
            b.remove(b.find("Link"))

        def index(b):
            b.find("Index").text = "1"

        def mismatched_type(b):
            b.set("Type", block("WRITE_VAR").get("Type"))

        def bad_type(b):
            b.find("Timeout").set("Type", "System.Int32")

        def unknown(b):
            ET.SubElement(b, "RemotePort").text = "502"

        def unknown_attribute(b):
            b.find("Timeout/Value/int").set("anything", "1")

        def noncanonical(b):
            b.find("Quantity/Value/int").text = "01"

        def nonascii(b):
            b.find("Quantity/Value/int").text = "1١"

        def mixed_text(b):
            b.find("Timeout").text = "garbage"

        def invalid_config(b):
            b.find("Quantity/Value/int").text = "126"

        for mutate in [
            duplicate,
            nested_duplicate,
            missing,
            index,
            mismatched_type,
            bad_type,
            unknown,
            unknown_attribute,
            noncanonical,
            nonascii,
            mixed_text,
            invalid_config,
        ]:
            b = block()
            mutate(b)
            with self.subTest(mutate=mutate.__name__), self.assertRaises(CompileError):
                comm.read_blocks(software(b))
        with self.assertRaises(CompileError):
            comm.read_blocks(software(block(), block()))
        sw = software()
        ET.SubElement(sw, "FunctionBlocks")
        with self.assertRaises(CompileError):
            comm.read_blocks(sw)

    def test_write_replaces_blocks_and_emits_observed_types(self):
        sw = software(block())
        ET.SubElement(sw, "MastTask")
        p = Program(
            communications={
                "%READ_VAR2": ModbusConfig(link="ETH1", obj_type=3, index_data=321),
                "%WRITE_VAR0": ModbusConfig(kind="WRITE_VAR", index_data=20),
            }
        )
        comm.write_blocks(p, sw)
        self.assertEqual(comm.read_blocks(sw), p.communications)
        self.assertEqual(len(sw.findall("FunctionBlocks")), 1)
        self.assertIsNotNone(sw.find("MastTask"))
        b = sw.find("FunctionBlocks/IFunctionBlock")
        self.assertEqual(
            b.find("Link/Value/FBComLinkParameterEnums").text, "EthernetLink"
        )
        self.assertEqual(b.find("ObjType/Value/FBComObjTypeParameterEnums").text, "IW")
        self.assertEqual(b.find("IndexData").get("Type"), INT_TYPE)

    def test_unproven_enum_or_block_export_fails_without_mutation(self):
        for cfg in [
            ModbusConfig(kind="WRITE_READ_VAR"),
        ]:
            sw = software(block())
            before = ET.tostring(sw)
            with self.subTest(cfg=cfg), self.assertRaises(CompileError):
                comm.write_blocks(
                    Program(communications={"%" + cfg.kind + "0": cfg}), sw
                )
            self.assertEqual(ET.tostring(sw), before)
        with self.assertRaises(CompileError):
            comm.read_blocks(software(block(obj="Coils")))
        with self.assertRaises(CompileError):
            comm.write_blocks(
                Program(communications={"%WRITE_VAR0": ModbusConfig()}), software()
            )

    def test_serial_validator_accepts_observed_master_and_inactive_empty(self):
        comm.validate_serial(serial())
        comm.validate_serial(ET.Element("SerialLineConfiguration"))
        n = serial()
        n.find("Addressing").text = "SlaveAddressing"
        n.find("Baud").text = "Baud9600"
        n.find("Parity").text = "ParityNone"
        n.find("Polarization/Value").text = "0"
        n.find("Polarization/Name").text = "No"
        comm.validate_serial(n)

    def test_serial_rejects_active_unknown_or_ambiguous_fields(self):
        for tag, value in [
            ("TransmissionMode", "Anything"),
            ("PhysicalMedium", "RS232"),
            ("Addressing", "Auto"),
            ("StartCharacterEnabled", "true"),
            ("SlaveId", "248"),
            ("Baud", "19200"),
            ("InitCommand", "AT"),
        ]:
            n = serial()
            n.find(tag).text = value
            with self.subTest(tag=tag), self.assertRaises(CompileError):
                comm.validate_serial(n)
        for path in ["Baud", "Polarization/Value"]:
            n = serial()
            part = n.find(path)
            n.find("Polarization").append(
                copy.deepcopy(part)
            ) if "/" in path else n.append(copy.deepcopy(part))
            with self.subTest(path=path), self.assertRaises(CompileError):
                comm.validate_serial(n)
        n = serial()
        n.find("Polarization/Name").text = "No"
        with self.assertRaises(CompileError):
            comm.validate_serial(n)
        n = serial()
        ET.SubElement(n, "Extra").text = "1"
        with self.assertRaises(CompileError):
            comm.validate_serial(n)

    def test_remote_device_index_and_unit_id_remain_distinct(self):
        got = comm.validate_remotes(remotes())
        self.assertEqual(
            got,
            {
                1: {
                    "device_id": 0,
                    "ip": "10.0.0.3",
                    "unit_id": 255,
                    "init_unit_id": 255,
                    "timeout": 10,
                    "port": 502,
                }
            },
        )
        n = remotes(15)
        n.tag = "RemoteServers"
        self.assertEqual(comm.validate_remotes(n)[16]["device_id"], 15)

    def test_remote_rejects_duplicate_fields_devices_and_unknown_port(self):
        for tag, value in [
            ("SlaveAddress", "host.invalid"),
            ("SlaveAddress", "::1"),
            ("DeviceId", "16"),
            ("ChannelUnitId", "256"),
            ("DeviceTypeId", "24"),
            ("ResetVariable", "%M0"),
            ("Address", "%MW0"),
        ]:
            n = remotes()
            n.find("RemoteServer/" + tag).text = value
            with self.subTest(tag=tag, value=value), self.assertRaises(CompileError):
                comm.validate_remotes(n)
        for tag in ["SlaveAddress", "Port"]:
            n = remotes()
            ET.SubElement(n.find("RemoteServer"), tag).text = "502"
            with self.subTest(tag=tag), self.assertRaises(CompileError):
                comm.validate_remotes(n)
        n = remotes()
        n.append(copy.deepcopy(n[0]))
        with self.assertRaises(CompileError):
            comm.validate_remotes(n)
        n = remotes()
        n[0].remove(n.find("RemoteServer/Timeout"))
        with self.assertRaises(CompileError):
            comm.validate_remotes(n)

    def test_channel_checks_require_present_matching_port_configuration(self):
        cfg = {
            "%READ_VAR0": ModbusConfig(),
            "%WRITE_VAR0": ModbusConfig(kind="WRITE_VAR", link="ETH1"),
        }
        comm.check_template_channels(root(), cfg)
        for path in [
            "HardwareConfiguration/Plc/SerialLineConfiguration",
            "HardwareConfiguration/Plc/Cpu/EthernetConfiguration/ModbusTcpSlave/Devices",
        ]:
            n = root()
            parent, tag = path.rsplit("/", 1)
            n.find(parent).remove(n.find(path))
            with self.subTest(path=path), self.assertRaises(CompileError):
                comm.check_template_channels(n, cfg)
        n = root()
        n.find(".//SerialLineConfiguration/Addressing").text = "SlaveAddressing"
        with self.assertRaises(CompileError):
            comm.check_template_channels(n, cfg)
        n = root()
        n.find(".//RemoteServer/DeviceId").text = "1"
        with self.assertRaises(CompileError):
            comm.check_template_channels(n, cfg)

    def test_instance_budget_is_gated_at_functional_level_10_1(self):
        n = root()
        cfg = {"%READ_VAR16": ModbusConfig()}
        n.find("ManagementLevel").text = "FunctLevelMan14_0"
        with self.assertRaises(CompileError):
            comm.check_template_channels(n, cfg)
        n.find("ManagementLevel").text = "FunctLevelMan15_0"
        comm.check_template_channels(n, cfg)
        n.find("ManagementLevel").text = "FunctLevelMan9_0"
        comm.check_template_channels(n, {"%READ_VAR15": ModbusConfig()})
        with self.assertRaises(CompileError):
            comm.check_template_channels(root(), {"%READ_VAR32": ModbusConfig()})

    def test_real_management_level_tokens_are_mapped_before_instance_gate(self):
        for token in ("FunctLevelMan11_0", "FunctLevelMan13_0", "FunctLevelMan14_0"):
            n = root()
            n.find("ManagementLevel").text = token
            with self.subTest(token=token), self.assertRaises(CompileError):
                comm.check_template_channels(n, {"%READ_VAR16": ModbusConfig()})
            comm.check_template_channels(n, {"%READ_VAR15": ModbusConfig()})
        for token in ("FunctLevelMan15_0", "FunctLevelMan18_0", "FunctLevelMan21_0"):
            n = root()
            n.find("ManagementLevel").text = token
            comm.check_template_channels(n, {"%READ_VAR31": ModbusConfig()})
        for token in (
            "FunctLevelMan10_1",
            "FunctLevelMan22_0",
            "FunctLevelMan014_0",
            "FunctLevelMan14_1",
        ):
            n = root()
            n.find("ManagementLevel").text = token
            with self.subTest(unknown=token), self.assertRaises(CompileError):
                comm.check_template_channels(n, {"%READ_VAR0": ModbusConfig()})

    def test_all_observed_level_tokens_match_independent_editor_resources(self):
        from m200.levels import FUNCTIONAL_LEVELS

        path = Path(__file__).parents[1] / "docs/capabilities/EDITOR-INTEROP-FACTS.json"
        rows = json.loads(path.read_text())["management_levels"]["rows"]
        self.assertEqual(len(rows), 21)
        self.assertEqual(
            FUNCTIONAL_LEVELS, {row["token"]: tuple(row["human_level"]) for row in rows}
        )
        for row in rows:
            n = root()
            n.find("ManagementLevel").text = row["token"]
            comm.check_template_channels(n, {"%READ_VAR15": ModbusConfig()})
            if tuple(row["human_level"]) >= (10, 1):
                comm.check_template_channels(n, {"%READ_VAR31": ModbusConfig()})
            else:
                with self.subTest(token=row["token"]), self.assertRaises(CompileError):
                    comm.check_template_channels(n, {"%READ_VAR16": ModbusConfig()})

    def test_container_text_is_not_an_empty_configuration(self):
        for node, call in [
            (ET.Element("FunctionBlocks"), None),
            (ET.Element("Devices"), comm.validate_remotes),
            (ET.Element("SerialLineConfiguration"), comm.validate_serial),
        ]:
            node.text = "uninterpreted"
            with self.subTest(tag=node.tag), self.assertRaises(CompileError):
                if call:
                    call(node)
                else:
                    sw = ET.Element("SoftwareConfiguration")
                    sw.append(node)
                    comm.read_blocks(sw)

    def test_int32_wrapper_rejects_values_that_cannot_be_serialized(self):
        b = block()
        b.find("Timeout/Value/int").text = "2147483648"
        with self.assertRaises(CompileError):
            comm.read_blocks(software(b))
        sw = software(block())
        before = ET.tostring(sw)
        with self.assertRaises(CompileError):
            comm.write_blocks(
                Program(
                    communications={
                        "%READ_VAR0": ModbusConfig(timeout_100ms=2147483648)
                    }
                ),
                sw,
            )
        self.assertEqual(ET.tostring(sw), before)

    def test_used_serial_port_requires_explicit_line_format(self):
        for tag in ["Baud", "Parity", "DataBits", "StopBits", "ResponseTime"]:
            n = root()
            s = n.find(".//SerialLineConfiguration")
            s.remove(s.find(tag))
            with self.subTest(tag=tag), self.assertRaises(CompileError):
                comm.check_template_channels(n, {"%READ_VAR0": ModbusConfig()})

    def test_xml_addresses_use_bounded_ascii_decimal_indexes(self):
        for address in ["%READ_VAR1١", "%READ_VAR" + "1" * 5000, "%READ_VAR00"]:
            b = block()
            b.find("Address").text = address
            with self.subTest(address=address[:40]), self.assertRaises(CompileError):
                comm.read_blocks(software(b))
            with self.subTest(write=address[:40]), self.assertRaises(CompileError):
                comm.write_blocks(
                    Program(communications={address: ModbusConfig()}), software()
                )


if __name__ == "__main__":
    unittest.main()
