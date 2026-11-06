"""Closed asymmetric WRITE_READ_VAR binding and existing local-model oracles."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200 import communication_xml
from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError, Program
from m200.modbus import MemoryModbusPeer, MemoryTransport, ModbusConfig, encode_request
from m200.numeric import memory_words_used
from m200.project import load_project, write_project
from m200.reverse import to_cpp


FIXTURE = Path(__file__).parent / "fixtures/official_tm200ce40t_modbus_write_read.smbp"
XML_VALUES = {
    "Link": "SerialLine1",
    "RemoteDeviceId": "1",
    "Timeout": "100",
    "ObjType": "MW",
    "FirstWriteObj": "17",
    "WriteQuantity": "2",
    "IndexDataOut": "300",
    "FirstReadObj": "41",
    "ReadQuantity": "3",
    "IndexDataIn": "400",
}


class RecordingPeer(MemoryModbusPeer):
    def __init__(self):
        super().__init__(holding_registers=[0] * 70)
        self.holding_registers[41:44] = [0x8001, 0xFFFF, 0x1234]
        self.requests = []

    def handle_request(self, pdu):
        self.requests.append(pdu)
        return super().handle_request(pdu)


class ModbusWriteReadNativeProfileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def config(self, **changes):
        values = dict(
            kind="WRITE_READ_VAR",
            first_obj=17,
            quantity=2,
            index_data=300,
            first_read_obj=41,
            read_quantity=3,
            index_data_in=400,
        )
        values.update(changes)
        return ModbusConfig(**values)

    def program(self, **changes):
        return Program(
            [["BLK %WRITE_READ_VAR0", "LD %M12", "EXECUTE", "END_BLK"]],
            communications={"%WRITE_READ_VAR0": self.config(**changes)},
        )

    def save(self, tree):
        path = self.work / "modified.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def xml_values(self, root):
        block = root.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
        return {
            child.tag: list(child.find("Value"))[0].text
            for child in block
            if child.tag not in ("Address", "Index")
        }

    def assert_exact_graph(self, root, execute="%M12"):
        graph = root.find(".//RungEntity/LadderElements")
        actual = [
            (
                n.findtext("ElementType"),
                n.findtext("Descriptor"),
                n.findtext("Row"),
                n.findtext("Column"),
                n.findtext("ChosenConnection"),
            )
            for n in graph
        ]
        self.assertEqual(
            actual,
            [
                ("NormalContact", execute, "0", "0", "Left, Right"),
                ("WriteReadVarBasic", "%WRITE_READ_VAR0", "0", "1", "Left"),
            ],
        )

    def run_block(self, program, peer, words, *, latency=1):
        machine = Machine(
            program, communication_transport=MemoryTransport(peer, latency_ms=latency)
        )
        for index, value in words.items():
            machine.words[index] = value
        for enabled in (False, True, True):
            machine.memory[12] = enabled
            machine.step({}, 10)
        return machine

    def test_exact_saved_write_read_fixture_imports_all_asymmetric_fields(self):
        raw = FIXTURE.read_bytes()
        provenance = json.loads(FIXTURE.with_suffix(".provenance.json").read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance["sha256"])
        self.assertEqual(len(raw), 89601)
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
        try:
            program = load_project(FIXTURE)
        except CompileError as error:
            self.fail("Exact saved WRITE_READ_VAR binding must import: " + str(error))
        self.assertEqual(
            program.communications,
            {
                "%WRITE_READ_VAR0": ModbusConfig(
                    kind="WRITE_READ_VAR",
                    first_obj=17,
                    quantity=2,
                    index_data=300,
                    first_read_obj=41,
                    read_quantity=3,
                    index_data_in=400,
                )
            },
        )
        self.assertEqual(
            program.rungs,
            [["BLK %WRITE_READ_VAR0", "LD %M12", "EXECUTE", "END_BLK"]],
        )
        self.assertEqual(self.xml_values(ET.parse(FIXTURE)), XML_VALUES)
        self.assert_exact_graph(ET.parse(FIXTURE))
        self.assertEqual(memory_words_used(program), {300, 301, 400, 401, 402})

    def test_constructor_reverse_and_export_preserve_literal_fields_and_column_one(
        self,
    ):
        original = FIXTURE.read_bytes()
        source = self.work / "source.cpp"
        source.write_text(
            "#include <plc.hpp>\n"
            "plc::WriteReadVar remote{0,plc::Link::Serial1,1,100,17,2,300,41,3,400};\n"
            "void scan(){remote.update(plc::read_m(12),false);}\n"
        )
        compiled = compile_source(source)
        self.assertEqual(compiled.communications, {"%WRITE_READ_VAR0": self.config()})
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(load_project(FIXTURE)))
        rebuilt = compile_source(reverse)
        self.assertEqual(rebuilt.communications, {"%WRITE_READ_VAR0": self.config()})
        for program in (compiled, rebuilt, self.program()):
            destination = self.work / "export.smbp"
            write_project(program, FIXTURE, destination)
            root = ET.parse(destination)
            self.assertEqual(self.xml_values(root), XML_VALUES)
            block = root.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            self.assertEqual(
                block.get("Type"),
                ET.parse(FIXTURE)
                .find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
                .get("Type"),
            )
            self.assertEqual(
                load_project(destination).communications,
                {"%WRITE_READ_VAR0": self.config()},
            )
            self.assertEqual(
                memory_words_used(load_project(destination)), {300, 301, 400, 401, 402}
            )
        # A literal expected graph is independent of the reader/writer helper.
        write_project(self.program(), FIXTURE, destination)
        self.assert_exact_graph(ET.parse(destination))
        self.assertEqual(FIXTURE.read_bytes(), original)

    def test_per_kind_maps_require_exact_ten_fields_and_refuse_foreign_fields(self):
        for field in XML_VALUES:
            for change in ("missing", "duplicate"):
                tree = ET.parse(FIXTURE)
                block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
                node = block.find(field)
                block.remove(node) if change == "missing" else block.append(
                    copy.deepcopy(node)
                )
                with (
                    self.subTest(field=field, change=change),
                    self.assertRaises(CompileError),
                ):
                    communication_xml.read_blocks(tree.find("SoftwareConfiguration"))
        for tag in ("FirstObj", "Quantity", "IndexData", "CommError", "OperError"):
            tree = ET.parse(FIXTURE)
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            extra = copy.deepcopy(block.find("FirstWriteObj"))
            extra.tag = tag
            block.append(extra)
            with self.subTest(extra=tag), self.assertRaises(CompileError):
                communication_xml.read_blocks(tree.find("SoftwareConfiguration"))
        for filename in (
            "official_tm200ce40t_modbus_read_i.smbp",
            "official_tm200ce40t_modbus_write_q.smbp",
        ):
            tree = ET.parse(FIXTURE.parent / filename)
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            block.append(copy.deepcopy(ET.parse(FIXTURE).find(".//FirstReadObj")))
            with self.subTest(kind=filename), self.assertRaises(CompileError):
                communication_xml.read_blocks(tree.find("SoftwareConfiguration"))

    def test_identity_wrappers_and_canonical_scalars_remain_strict(self):
        for change in (
            "kind",
            "address",
            "index",
            "wrapper",
            "enum",
            "nested",
            "attribute",
            "tail",
            "integer",
        ):
            tree = ET.parse(FIXTURE)
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            if change == "kind":
                block.set(
                    "Type",
                    block.get("Type").replace("WriteReadVarBasic", "WriteVarBasic"),
                )
            elif change == "address":
                block.find("Address").text = "%WRITE_VAR0"
            elif change == "index":
                block.find("Index").text = "1"
            elif change == "wrapper":
                block.find("IndexDataIn").set("Type", block.find("ObjType").get("Type"))
            elif change == "enum":
                block.find("ObjType/Value/FBComObjTypeParameterEnums").text = "Q"
            elif change == "nested":
                ET.SubElement(block.find("ReadQuantity/Value/int"), "int").text = "3"
            elif change == "attribute":
                block.find("FirstReadObj/Value").set("Unused", "true")
            elif change == "tail":
                block.find("FirstWriteObj").tail = "MIXED CONTENT"
            else:
                block.find("WriteQuantity/Value/int").text = "02"
            with self.subTest(change=change), self.assertRaises(CompileError):
                communication_xml.read_blocks(tree.find("SoftwareConfiguration"))

    def test_literal_fc23_packet_and_separate_buffers_survive_xml_import(self):
        program = load_project(FIXTURE)
        config = program.communications["%WRITE_READ_VAR0"]
        words = [0] * 8000
        words[300:302] = [0x1234, 0xABCD]
        request = bytes.fromhex("17 0029 0003 0011 0002 04 1234 abcd")
        self.assertEqual(encode_request(config, words), request)
        peer = RecordingPeer()
        self.assertEqual(
            peer.handle_request(request), bytes.fromhex("17 06 8001 ffff 1234")
        )
        self.assertEqual(peer.holding_registers[17:19], [0x1234, 0xABCD])
        peer = RecordingPeer()
        machine = self.run_block(
            program,
            peer,
            {
                300: 0x1234,
                301: 0xABCD,
                399: 0x7777,
                400: 0xAAAA,
                401: 0xBBBB,
                402: 0xCCCC,
                403: 0x8888,
            },
        )
        self.assertEqual(peer.requests, [request])
        self.assertEqual(machine.words[300:302], [0x1234, 0xABCD])
        self.assertEqual(
            machine.words[399:404], [0x7777, 0x8001, 0xFFFF, 0x1234, 0x8888]
        )
        self.assertTrue(machine.read("%WRITE_READ_VAR0.DONE", {}))

    def test_overlap_uses_execute_snapshot_and_commits_inbound_only_on_completion(self):
        tree = ET.parse(FIXTURE)
        tree.find(".//FirstReadObj/Value/int").text = "18"
        tree.find(".//IndexDataIn/Value/int").text = "301"
        program = load_project(self.save(tree))
        peer = RecordingPeer()
        peer.holding_registers[19:21] = [0x8001, 0xFFFF]
        machine = Machine(
            program, communication_transport=MemoryTransport(peer, latency_ms=25)
        )
        machine.words[300:305] = [0x1234, 0xABCD, 0x1111, 0x2222, 0x3333]
        machine.memory[12] = False
        machine.step({}, 10)
        machine.memory[12] = True
        machine.step({}, 10)
        self.assertTrue(machine.read("%WRITE_READ_VAR0.BUSY", {}))
        machine.words[300:302] = [9, 9]
        for _ in range(2):
            machine.step({}, 10)
            self.assertEqual(machine.words[302:304], [0x1111, 0x2222])
        machine.step({}, 10)
        self.assertEqual(
            peer.requests, [bytes.fromhex("17 0012 0003 0011 0002 04 1234 abcd")]
        )
        self.assertEqual(peer.holding_registers[17:19], [0x1234, 0xABCD])
        self.assertEqual(machine.words[300:305], [9, 0xABCD, 0x8001, 0xFFFF, 0x3333])

    def test_both_complete_extents_maxima_and_invalid_ranges_are_checked(self):
        tree = ET.parse(FIXTURE)
        for tag, value in {
            "FirstWriteObj": 65415,
            "WriteQuantity": 121,
            "IndexDataOut": 600,
            "FirstReadObj": 65411,
            "ReadQuantity": 125,
            "IndexDataIn": 7500,
        }.items():
            tree.find(".//" + tag + "/Value/int").text = str(value)
        tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "7625"
        program = load_project(self.save(tree))
        self.assertEqual(
            memory_words_used(program), set(range(600, 721)) | set(range(7500, 7625))
        )
        packet = encode_request(program.communications["%WRITE_READ_VAR0"], [0] * 8000)
        self.assertEqual(
            packet, bytes.fromhex("17 ff83 007d ff87 0079 f2") + bytes(242)
        )
        self.assertEqual(len(packet), 252)
        for outbound, inbound, expected in [
            (7998, 10, {7998, 7999, 10, 11, 12}),
            (300, 7997, {300, 301, 7997, 7998, 7999}),
        ]:
            tree = ET.parse(FIXTURE)
            tree.find(".//IndexDataOut/Value/int").text = str(outbound)
            tree.find(".//IndexDataIn/Value/int").text = str(inbound)
            tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "8000"
            self.assertEqual(memory_words_used(load_project(self.save(tree))), expected)
        for tag, value in [
            ("WriteQuantity", 0),
            ("WriteQuantity", 122),
            ("ReadQuantity", 0),
            ("ReadQuantity", 126),
            ("FirstWriteObj", 65535),
            ("FirstReadObj", 65535),
            ("IndexDataOut", 7999),
            ("IndexDataIn", 7998),
            ("RemoteDeviceId", 0),
        ]:
            tree = ET.parse(FIXTURE)
            tree.find(".//" + tag + "/Value/int").text = str(value)
            with self.subTest(tag=tag, value=value), self.assertRaises(CompileError):
                load_project(self.save(tree))
        tree = ET.parse(FIXTURE)
        tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "402"
        with self.assertRaisesRegex(CompileError, "allocation"):
            load_project(self.save(tree))

    def test_actual_profile_authority_and_rejected_exports_preserve_files(self):
        for change, value, message in [
            ("ManagementLevel", "FunctLevelMan7_0", "unverified WRITE_READ_VAR.*level"),
            (
                "ManagementLevel",
                "FunctLevelMan20_0",
                "unverified WRITE_READ_VAR.*level",
            ),
            ("ManagementLevel", "FunctLevelMan99_0", "management-level"),
            (
                ".//Link/Value/FBComLinkParameterEnums",
                "EthernetLink",
                "unverified WRITE_READ_VAR.*link",
            ),
            (
                "HardwareConfiguration/Plc/SerialLineConfiguration/Addressing",
                "SlaveAddressing",
                "master configuration",
            ),
        ]:
            tree = ET.parse(FIXTURE)
            tree.find(change).text = value
            template = self.save(tree)
            original = template.read_bytes()
            with self.subTest(change=change, value=value):
                with self.assertRaisesRegex(CompileError, message):
                    load_project(template)
                for existing in (False, True):
                    program = self.program(
                        link="ETH1" if value == "EthernetLink" else "SL1"
                    )
                    program.metadata.update(
                        ManagementLevel="FunctLevelMan21_0",
                        Link="SerialLine1",
                        Addressing="MasterAddressing",
                    )
                    destination = self.work / (
                        "existing.smbp" if existing else "absent.smbp"
                    )
                    if existing:
                        destination.write_bytes(b"PRESERVE")
                    with self.assertRaisesRegex(CompileError, message):
                        write_project(program, template, destination)
                    self.assertEqual(template.read_bytes(), original)
                    self.assertEqual(
                        destination.read_bytes(), b"PRESERVE"
                    ) if existing else self.assertFalse(destination.exists())
        program = self.program()
        program.metadata.update(
            ManagementLevel="FunctLevelMan1_0",
            Link="EthernetLink",
            Addressing="SlaveAddressing",
        )
        destination = self.work / "valid.smbp"
        write_project(program, FIXTURE, destination)
        self.assertEqual(
            load_project(destination).communications,
            {"%WRITE_READ_VAR0": self.config()},
        )

    def test_exact_graph_closure_abort_full_pin_and_late_invalid_block_stay_closed(
        self,
    ):
        for change in (
            "column",
            "row",
            "connection",
            "descriptor",
            "line",
            "negated",
            "constant_false",
            "constant_true",
        ):
            tree = ET.parse(FIXTURE)
            graph = tree.find(".//LadderElements")
            contact, block = list(graph)
            if change == "column":
                block.find("Column").text = "2"
            elif change == "row":
                block.find("Row").text = "1"
            elif change == "connection":
                block.find("ChosenConnection").text = "Left, Right"
            elif change == "descriptor":
                block.find("Descriptor").text = "%WRITE_READ_VAR1"
            elif change == "line":
                line = ET.SubElement(graph, "LadderEntity")
                for tag, value in [
                    ("ElementType", "Line"),
                    ("Row", "0"),
                    ("Column", "2"),
                    ("ChosenConnection", "Left, Right"),
                ]:
                    ET.SubElement(line, tag).text = value
            elif change == "negated":
                contact.find("ElementType").text = "NegatedContact"
                tree.findall(".//InstructionLine")[1].text = "LDN %M12"
            else:
                value = "0" if change == "constant_false" else "1"
                contact.find("Descriptor").text = value
                tree.findall(".//InstructionLine")[1].text = "LD " + value
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(self.save(tree))
        destination = self.work / "preserve.smbp"
        destination.write_bytes(b"PRESERVE")
        abort = self.program()
        abort.rungs = [
            [
                "BLK %WRITE_READ_VAR0",
                "LD %M12",
                "EXECUTE",
                "LD %M13",
                "ABORT",
                "END_BLK",
            ]
        ]
        with self.assertRaisesRegex(CompileError, "ABORT"):
            write_project(abort, FIXTURE, destination)
        full = self.program()
        full.rungs = [
            [
                "BLK %WRITE_READ_VAR0",
                "LD %M10",
                "EXECUTE",
                "LD %M13",
                "ABORT",
                "OUT_BLK",
                "LD DONE",
                "ST %M14",
                "LD BUSY",
                "ST %M15",
                "LD ABORTED",
                "ST %M16",
                "LD ERROR",
                "ST %M17",
                "END_BLK",
            ]
        ]
        with self.assertRaises(CompileError):
            write_project(full, FIXTURE, destination)
        late = self.program(first_obj=19)
        late.communications["%READ_VAR1"] = ModbusConfig(kind="WRITE_VAR")
        late.rungs.append(["BLK %READ_VAR1", "LD %M0", "EXECUTE", "END_BLK"])
        sw = ET.parse(FIXTURE).find("SoftwareConfiguration")
        before = ET.tostring(sw)
        with self.assertRaises(CompileError):
            communication_xml.write_blocks(late, sw)
        self.assertEqual(ET.tostring(sw), before)
        with self.assertRaises(CompileError):
            write_project(late, FIXTURE, destination)
        self.assertEqual(destination.read_bytes(), b"PRESERVE")

    def test_bad_response_never_partially_overwrites_inbound_words(self):
        for response in [
            bytes.fromhex(s)
            for s in (
                "17 04 8001 ffff",
                "17 06 8001 ffff",
                "17 06 8001 ffff 1234 00",
                "03 06 8001 ffff 1234",
                "97 02",
                "",
            )
        ]:

            class FaultPeer(RecordingPeer):
                def handle_request(self, pdu):
                    super().handle_request(pdu)
                    return response

            peer = FaultPeer()
            machine = self.run_block(
                load_project(FIXTURE),
                peer,
                {
                    300: 0x1234,
                    301: 0xABCD,
                    400: 0xAAAA,
                    401: 0xBBBB,
                    402: 0xCCCC,
                },
            )
            self.assertEqual(machine.words[400:403], [0xAAAA, 0xBBBB, 0xCCCC])
            self.assertTrue(machine.read("%WRITE_READ_VAR0.ERROR", {}))
            self.assertEqual(peer.holding_registers[17:19], [0x1234, 0xABCD])


if __name__ == "__main__":
    unittest.main()
