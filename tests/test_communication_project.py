import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError
from m200.modbus import MemoryModbusPeer, MemoryTransport
from m200.modbus import LoopbackTCPTransport
from m200.project import write_project, load_project
from m200.reverse import to_cpp


class CommunicationProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def source(self, code):
        p = self.work / "code.cpp"
        p.write_text("#include <plc.hpp>\n" + code)
        return compile_source(p)

    def template(self, serial=True):
        tree = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp")
        if serial:
            node = ET.SubElement(
                tree.getroot().find("HardwareConfiguration/Plc"),
                "SerialLineConfiguration",
            )
            for tag, value in [
                ("Baud", "Baud19200"),
                ("Parity", "ParityEven"),
                ("DataBits", "DataBits8"),
                ("StopBits", "StopBits1"),
                ("ResponseTime", "5"),
                ("TimeBetweenFrames", "10"),
                ("PhysicalMedium", "PhysicalMediumRs485"),
                ("TransmissionMode", "TransmissionModeModbusRtu"),
                ("Addressing", "MasterAddressing"),
            ]:
                ET.SubElement(node, tag).text = value
        p = self.work / "template.smbp"
        tree.write(p)
        return p

    def test_serial_read_generates_typed_fb_ladder_and_roundtrip(self):
        program = self.source("""plc::ReadVar r{plc::Link::Serial1,1,100,plc::Object::HoldingWords,0,2,7998};
void scan(){bool done=r.update(plc::input(0),false);plc::output(0,done);plc::output(1,r.busy());plc::output(2,plc::read_word(7998)==123);}""")
        template = self.template()
        before = template.read_bytes()
        path = self.work / "candidate.smbp"
        write_project(program, template, path)
        self.assertEqual(template.read_bytes(), before)
        root = ET.parse(path).getroot()
        self.assertEqual(
            root.findtext("HardwareConfiguration/Plc/Cpu/Reference"), "TM200CE40T"
        )
        self.assertEqual(
            root.findtext(
                "SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"
            ),
            "8000",
        )
        self.assertTrue(
            any(
                e.findtext("ElementType") == "ReadVarBasic"
                for e in root.iter("LadderEntity")
            )
        )
        actual = load_project(path)
        self.assertEqual(actual.communications, program.communications)
        self.assertEqual(actual.rungs, program.rungs)
        peer = MemoryModbusPeer(holding_registers=[123, 456])
        machine = Machine(actual, communication_transport=MemoryTransport(peer))
        frames = [False, True, True, False]
        rows = [machine.step({0: value}, 10) for value in frames]
        self.assertTrue(rows[2][0] and rows[2][2])
        reverse = self.work / "audit.cpp"
        reverse.write_text(to_cpp(actual))
        rebuilt = Machine(
            compile_source(reverse),
            communication_transport=MemoryTransport(
                MemoryModbusPeer(holding_registers=[123, 456])
            ),
        )
        self.assertEqual([rebuilt.step({0: v}, 10) for v in frames], rows)

    def test_missing_channel_and_unknown_abort_graph_fail_before_file_write(self):
        for code, configured, reason in [
            (
                "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,1,100};void scan(){r.update(plc::input(0),false);}",
                False,
                "SL1|missing",
            ),
            (
                "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,1,100};void scan(){r.update(plc::input(0),plc::input(1));}",
                True,
                "ABORT",
            ),
        ]:
            program = self.source(code)
            path = self.work / "must-not-exist.smbp"
            with (
                self.subTest(reason=reason),
                self.assertRaisesRegex(CompileError, reason),
            ):
                write_project(program, self.template(configured), path)
            self.assertFalse(path.exists())

    def test_compiled_ethernet_read_uses_actual_loopback_tcp_and_generated_project(
        self,
    ):
        import socket
        import struct
        import threading
        import time

        program = self.source("""plc::ReadVar r{plc::Link::Ethernet,1,100,plc::Object::HoldingWords,0,2,100};
void scan(){bool done=r.update(plc::input(0),false);plc::output(0,done);plc::output(1,r.error());plc::output(2,plc::read_word(100)==4660 && plc::read_word(101)==-1);}""")
        template = self.template(False)
        tree = ET.parse(template)
        eth = ET.SubElement(
            tree.getroot().find("HardwareConfiguration/Plc/Cpu"),
            "EthernetConfiguration",
        )
        tcp = ET.SubElement(eth, "ModbusTcpSlave")
        devices = ET.SubElement(tcp, "Devices")
        remote = ET.SubElement(devices, "RemoteServer")
        for tag, value in [
            ("DeviceId", "0"),
            ("Address", ""),
            ("DeviceGeneralType", "IoScannerOther"),
            ("DeviceTypeName", "Generic Device"),
            ("DeviceTypeId", "23"),
            ("SlaveAddress", "127.0.0.1"),
            ("ResetVariable", ""),
            ("Name", "Local test peer"),
            ("InitRequestUnitId", "255"),
            ("ChannelUnitId", "255"),
            ("Timeout", "10"),
        ]:
            ET.SubElement(remote, tag).text = value
        tree.write(template)
        path = self.work / "ethernet.smbp"
        write_project(program, template, path)
        actual = load_project(path)
        failures = []
        requests = []
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(3)

            def serve():
                try:
                    with listener.accept()[0] as client:
                        client.settimeout(3)

                        def recv(n):
                            data = b""
                            while len(data) < n:
                                part = client.recv(n - len(data))
                                if not part:
                                    raise AssertionError("truncated request")
                                data += part
                            return data

                        header = recv(7)
                        tid, protocol, length, unit = struct.unpack(">HHHB", header)
                        pdu = recv(length - 1)
                        requests.append(pdu)
                        response = MemoryModbusPeer(
                            holding_registers=[4660, 65535]
                        ).handle_request(pdu)
                        client.sendall(
                            struct.pack(">HHHB", tid, protocol, len(response) + 1, unit)
                            + response
                        )
                except Exception as error:
                    failures.append(repr(error))

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            transport = LoopbackTCPTransport(
                port=listener.getsockname()[1], unit_id=255, remote_index=1
            )
            machine = Machine(actual, communication_transport=transport)
            machine.step({0: False}, 0)
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    got = machine.step({0: True}, 0)
                    if got[0] or got[1]:
                        break
                    time.sleep(0.001)
                self.assertEqual(got[:3], [True, False, True])
            finally:
                transport.close()
                thread.join(3)
        self.assertFalse(failures, failures)
        self.assertEqual(requests, [bytes.fromhex("03 0000 0002")])

    def test_status_before_update_roundtrips_without_moving_the_read(self):
        program = self.source("""plc::ReadVar r{plc::Link::Serial1,1,10,plc::Object::HoldingWords,0,1,100};
void scan(){plc::output(0,r.done());r.update(plc::input(0),false);plc::output(1,r.done());}""")
        path = self.work / "early-status.smbp"
        write_project(program, self.template(), path)
        actual = load_project(path)
        self.assertEqual(actual.rungs, program.rungs)
        machine = Machine(
            actual,
            communication_transport=MemoryTransport(
                MemoryModbusPeer(holding_registers=[9])
            ),
        )
        rows = [machine.step({0: v}, 10)[:2] for v in [False, True, True, True]]
        self.assertEqual(
            rows, [[False, False], [False, False], [False, True], [True, True]]
        )

    def test_fb_parameter_type_is_rejected_outside_its_typed_container(self):
        from m200.communication_xml import _INT_TYPE

        path = self.template(False)
        tree = ET.parse(path)
        eth = ET.SubElement(
            tree.getroot().find("HardwareConfiguration/Plc/Cpu"),
            "EthernetConfiguration",
        )
        node = ET.SubElement(
            ET.SubElement(eth, "ModbusTcpSlave"), "Timeout", Type=_INT_TYPE
        )
        node.text = "10"
        tree.write(path)
        with self.assertRaisesRegex(CompileError, "attribute|Type"):
            load_project(path)

    def test_import_rejects_manual_word_allocation_shorter_than_fb_buffer(self):
        program = self.source(
            "plc::ReadVar r{plc::Link::Serial1,1,10,plc::Object::HoldingWords,0,2,7998};void scan(){r.update(plc::input(0),false);}"
        )
        path = self.work / "allocation.smbp"
        write_project(program, self.template(), path)
        original = path.read_bytes()
        for value in ["1", "8001", "garbage"]:
            path.write_bytes(original)
            tree = ET.parse(path)
            tree.find(
                "SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"
            ).text = value
            tree.write(path)
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(CompileError, "allocation"),
            ):
                load_project(path)

    def test_candidate_validation_failure_preserves_existing_destination(self):
        from unittest.mock import patch

        program = self.source("void scan(){plc::output(0,plc::input(0));}")
        path = self.work / "existing.smbp"
        path.write_bytes(b"PRESERVE ORIGINAL")
        with patch(
            "m200.project.load_project",
            side_effect=CompileError("M200-E: forced candidate failure"),
        ):
            with self.assertRaisesRegex(CompileError, "forced candidate failure"):
                write_project(program, self.template(), path)
        self.assertEqual(path.read_bytes(), b"PRESERVE ORIGINAL")
