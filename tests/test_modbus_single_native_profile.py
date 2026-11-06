"""Exact single-write SMBP profiles; local peer tests do not prove delivery."""

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


FIXTURES = Path(__file__).parent / "fixtures"
CASES = [
    ("single_coil", 4, 5, 107, 260),
    ("single_reg", 5, 6, 131, 280),
]


class ModbusSingleNativeProfileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def fixture(self, suffix):
        return FIXTURES / ("official_tm200ce40t_modbus_" + suffix + ".smbp")

    def save(self, tree):
        path = self.work / "modified.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def program(self, obj=4, **values):
        return Program(
            [["BLK %WRITE_VAR0", "LD %M11", "EXECUTE", "END_BLK"]],
            communications={
                "%WRITE_VAR0": ModbusConfig(
                    kind="WRITE_VAR",
                    obj_type=obj,
                    first_obj=107,
                    quantity=1,
                    index_data=260,
                    **values,
                )
            },
        )

    def test_exact_saved_single_write_profiles_import_one_word_buffers(self):
        for suffix, obj, function, first, index in CASES:
            with self.subTest(case=suffix):
                path = self.fixture(suffix)
                raw = path.read_bytes()
                provenance = json.loads(
                    path.with_suffix(".provenance.json").read_text()
                )
                self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance["sha256"])
                self.assertEqual(len(raw), provenance["bytes"])
                self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
                try:
                    program = load_project(path)
                except CompileError as error:
                    self.fail(
                        "Exact saved single-write profile must import: " + str(error)
                    )
                self.assertEqual(
                    program.communications,
                    {
                        "%WRITE_VAR0": ModbusConfig(
                            kind="WRITE_VAR",
                            obj_type=obj,
                            first_obj=first,
                            quantity=1,
                            index_data=index,
                        )
                    },
                )
                self.assertEqual(
                    program.rungs,
                    [["BLK %WRITE_VAR0", "LD %M11", "EXECUTE", "END_BLK"]],
                )
                self.assertEqual(
                    program.communications["%WRITE_VAR0"].function_code, function
                )
                self.assertEqual(program.communications["%WRITE_VAR0"].data_words, 1)

    def test_public_constructor_reverse_and_export_retain_single_function(self):
        for suffix, obj, function, first, index in CASES:
            with self.subTest(case=suffix):
                path = self.fixture(suffix)
                original = path.read_bytes()
                enum = "SingleCoil" if obj == 4 else "SingleRegister"
                source = self.work / "source.cpp"
                source.write_text(
                    "#include <plc.hpp>\n"
                    f"plc::WriteVar remote{{0,plc::Link::Serial1,1,100,"
                    f"plc::Object::{enum},{first},1,{index}}};\n"
                    "void scan(){remote.update(plc::read_m(11),false);}\n"
                )
                expected = ModbusConfig(
                    kind="WRITE_VAR",
                    obj_type=obj,
                    first_obj=first,
                    quantity=1,
                    index_data=index,
                )
                compiled = compile_source(source)
                self.assertEqual(compiled.communications, {"%WRITE_VAR0": expected})
                reverse = self.work / "reverse.cpp"
                reverse.write_text(to_cpp(load_project(path)))
                rebuilt = compile_source(reverse)
                self.assertEqual(rebuilt.communications, compiled.communications)
                for program in (compiled, rebuilt):
                    destination = self.work / "export.smbp"
                    write_project(program, path, destination)
                    actual = load_project(destination)
                    self.assertEqual(actual.communications, {"%WRITE_VAR0": expected})
                    self.assertEqual(memory_words_used(actual), {index})
                    self.assertEqual(
                        actual.communications["%WRITE_VAR0"].function_code, function
                    )
                    self.assertEqual(
                        ET.parse(destination).findtext(
                            ".//ObjType/Value/FBComObjTypeParameterEnums"
                        ),
                        "SINGLE_COIL" if obj == 4 else "SINGLE_REG",
                    )
                self.assertEqual(path.read_bytes(), original)

    def test_ignored_quantity_keeps_exactly_one_word_and_one_remote_address(self):
        for suffix, _, _, _, _ in CASES:
            for quantity in (0, 17, 65535):
                tree = ET.parse(self.fixture(suffix))
                tree.find(".//FirstObj/Value/int").text = "65535"
                tree.find(".//IndexData/Value/int").text = "7999"
                tree.find(".//Quantity/Value/int").text = str(quantity)
                tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "8000"
                with self.subTest(case=suffix, quantity=quantity):
                    program = load_project(self.save(tree))
                    self.assertEqual(memory_words_used(program), {7999})
                    self.assertEqual(
                        program.communications["%WRITE_VAR0"].data_words, 1
                    )
                    destination = self.work / "last_word.smbp"
                    write_project(program, self.fixture(suffix), destination)
                    self.assertEqual(
                        load_project(destination)
                        .communications["%WRITE_VAR0"]
                        .quantity,
                        quantity,
                    )
                    self.assertEqual(
                        ET.parse(destination).findtext(
                            ".//MemoryWordsMemoryAllocation/ForcedCount"
                        ),
                        "8000",
                    )

    def test_actual_level_is_authoritative_and_other_levels_stay_closed(self):
        for suffix, obj, _, _, _ in CASES:
            for level, message in [
                ("FunctLevelMan1_0", "single-write.*5.0"),
                ("FunctLevelMan7_0", "single-write.*5.0"),
                ("FunctLevelMan8_0", "single-write.*5.0"),
                ("FunctLevelMan9_0", "unverified single-write.*level"),
                ("FunctLevelMan11_0", "unverified single-write.*level"),
                ("FunctLevelMan20_0", "unverified single-write.*level"),
                ("FunctLevelMan99_0", "management-level"),
            ]:
                tree = ET.parse(self.fixture(suffix))
                tree.find("ManagementLevel").text = level
                template = self.save(tree)
                before = template.read_bytes()
                program = self.program(obj)
                program.metadata["ManagementLevel"] = "FunctLevelMan21_0"
                destination = self.work / "preserve.smbp"
                destination.write_bytes(b"PRESERVE")
                with self.subTest(case=suffix, level=level):
                    with self.assertRaisesRegex(CompileError, message):
                        load_project(template)
                    with self.assertRaisesRegex(CompileError, message):
                        write_project(program, template, destination)
                    self.assertEqual(template.read_bytes(), before)
                    self.assertEqual(destination.read_bytes(), b"PRESERVE")
            program.metadata["ManagementLevel"] = "FunctLevelMan1_0"
            write_project(program, self.fixture(suffix), destination)
            self.assertEqual(
                ET.parse(destination).findtext("ManagementLevel"), "FunctLevelMan21_0"
            )

    def test_actual_link_and_serial_configuration_cannot_be_forged_by_metadata(self):
        for suffix, obj, _, _, _ in CASES:
            tree = ET.parse(self.fixture(suffix))
            tree.find(".//Link/Value/FBComLinkParameterEnums").text = "EthernetLink"
            with (
                self.subTest(case=suffix, reason="actual link"),
                self.assertRaisesRegex(CompileError, "unverified single-write.*link"),
            ):
                load_project(self.save(tree))
            program = self.program(obj, link="ETH1")
            program.metadata.update(Link="SerialLine1", Addressing="MasterAddressing")
            destination = self.work / "preserve.smbp"
            destination.write_bytes(b"PRESERVE")
            with self.assertRaisesRegex(CompileError, "unverified single-write.*link"):
                write_project(program, self.fixture(suffix), destination)
            self.assertEqual(destination.read_bytes(), b"PRESERVE")
            tree = ET.parse(self.fixture(suffix))
            tree.find(
                "HardwareConfiguration/Plc/SerialLineConfiguration/Addressing"
            ).text = "SlaveAddressing"
            program = self.program(obj)
            program.metadata.update(Link="SerialLine1", Addressing="MasterAddressing")
            with self.assertRaisesRegex(CompileError, "master configuration"):
                write_project(program, self.save(tree), destination)
            self.assertEqual(destination.read_bytes(), b"PRESERVE")
            program.metadata.update(Link="EthernetLink", Addressing="SlaveAddressing")
            write_project(program, self.fixture(suffix), destination)
            self.assertEqual(
                load_project(destination).communications["%WRITE_VAR0"].link, "SL1"
            )

    def test_invalid_directions_and_out_of_range_scalars_are_rejected(self):
        for suffix, _, _, _, _ in CASES:
            tree = ET.parse(self.fixture(suffix))
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            block.set(
                "Type", block.get("Type").replace("WriteVarBasic", "ReadVarBasic")
            )
            block.find("Address").text = "%READ_VAR0"
            with (
                self.subTest(case=suffix, reason="direction"),
                self.assertRaisesRegex(CompileError, "ObjType for READ_VAR"),
            ):
                communication_xml.read_blocks(tree.find("SoftwareConfiguration"))
            for field, value in [
                ("IndexData", "8000"),
                ("FirstObj", "65536"),
                ("Quantity", "-1"),
                ("Quantity", "65536"),
                ("Timeout", "2147483648"),
            ]:
                tree = ET.parse(self.fixture(suffix))
                tree.find(".//" + field + "/Value/int").text = value
                with (
                    self.subTest(case=suffix, field=field, value=value),
                    self.assertRaises(CompileError),
                ):
                    load_project(self.save(tree))

    def test_imported_single_functions_use_literal_pdu_values_and_local_peer_only(self):
        for suffix, _, function, first, index in CASES:
            program = load_project(self.fixture(suffix))
            config = program.communications["%WRITE_VAR0"]
            values = (
                [
                    (0xFFFE, bytes.fromhex("05 00 6b 00 00")),
                    (1, bytes.fromhex("05 00 6b ff 00")),
                ]
                if function == 5
                else [(0xABCD, bytes.fromhex("06 00 83 ab cd"))]
            )
            for value, pdu in values:
                peer = MemoryModbusPeer(
                    coils=[True] * 133, holding_registers=[0x1234] * 133
                )
                machine = Machine(
                    program, communication_transport=MemoryTransport(peer)
                )
                machine.words[index] = value
                self.assertEqual(encode_request(config, machine.words), pdu)
                for enabled in (False, True, True):
                    machine.memory[11] = enabled
                    machine.step({}, 10)
                if function == 5:
                    self.assertEqual(peer.coils[first], bool(value & 1))
                    self.assertTrue(peer.coils[first - 1] and peer.coils[first + 1])
                    self.assertEqual(peer.holding_registers[first], 0x1234)
                else:
                    self.assertEqual(
                        peer.holding_registers[first - 1 : first + 2],
                        [0x1234, 0xABCD, 0x1234],
                    )
                    self.assertTrue(peer.coils[first])
                self.assertEqual(machine.words[index], value)

    def test_write_read_abort_and_connected_output_forms_remain_gated_atomically(self):
        program = self.program()
        sw = ET.parse(self.fixture("single_coil")).find("SoftwareConfiguration")
        original = ET.tostring(sw)
        program.communications["%WRITE_READ_VAR0"] = ModbusConfig(
            kind="WRITE_READ_VAR", index_data=300, index_data_in=400
        )
        program.rungs.append(["BLK %WRITE_READ_VAR0", "LD %M12", "EXECUTE", "END_BLK"])
        destination = self.work / "preserve.smbp"
        destination.write_bytes(b"PRESERVE")
        with self.assertRaises(CompileError):
            communication_xml.write_blocks(program, sw)
        self.assertEqual(ET.tostring(sw), original)
        with self.assertRaises(CompileError):
            write_project(program, self.fixture("single_coil"), destination)
        self.assertEqual(destination.read_bytes(), b"PRESERVE")
        program = self.program()
        program.rungs = [
            ["BLK %WRITE_VAR0", "LD %M11", "EXECUTE", "LD %M13", "ABORT", "END_BLK"]
        ]
        with self.assertRaisesRegex(CompileError, "ABORT"):
            write_project(program, self.fixture("single_coil"), destination)
        self.assertEqual(destination.read_bytes(), b"PRESERVE")
        tree = ET.parse(self.fixture("single_coil"))
        coil = ET.SubElement(tree.find(".//LadderElements"), "LadderEntity")
        for tag, value in [
            ("ElementType", "Coil"),
            ("Descriptor", "%M14"),
            ("Row", "0"),
            ("Column", "10"),
            ("ChosenConnection", "Left"),
        ]:
            ET.SubElement(coil, tag).text = value
        with self.assertRaises(CompileError):
            load_project(self.save(tree))

    def test_single_wrappers_unknown_fields_and_address_identity_remain_strict(self):
        for change in (
            "duplicate",
            "unknown",
            "wrapper",
            "index",
            "kind",
            "enum",
            "tail",
        ):
            tree = ET.parse(self.fixture("single_reg"))
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            if change == "duplicate":
                block.append(copy.deepcopy(block.find("Quantity")))
            elif change == "unknown":
                ET.SubElement(block, "SingleValue").text = "1"
            elif change == "wrapper":
                block.find("IndexData").set("Type", "System.Int32")
            elif change == "index":
                block.find("Index").text = "1"
            elif change == "kind":
                block.set(
                    "Type", block.get("Type").replace("WriteVarBasic", "ReadVarBasic")
                )
            elif change == "enum":
                block.find(
                    "ObjType/Value/FBComObjTypeParameterEnums"
                ).text = "SINGLE_REGISTER"
            else:
                block.find("ObjType").tail = "UNSUPPORTED MIXED TEXT"
            with self.subTest(change=change), self.assertRaises(CompileError):
                communication_xml.read_blocks(tree.find("SoftwareConfiguration"))

    def test_known_word_and_bit_objects_do_not_inherit_the_single_write_level_gate(
        self,
    ):
        for filename, level in [
            ("official_tm200ce40t_modbus_read_i.smbp", "FunctLevelMan7_0"),
            ("official_tm200ce40t_modbus_write_q.smbp", "FunctLevelMan9_0"),
        ]:
            tree = ET.parse(FIXTURES / filename)
            tree.find("ManagementLevel").text = level
            with self.subTest(filename=filename):
                program = load_project(self.save(tree))
                self.assertEqual(
                    next(iter(program.communications.values())).quantity, 17
                )
        tree = ET.parse(self.fixture("single_reg"))
        tree.find("ManagementLevel").text = "FunctLevelMan7_0"
        tree.find(".//ObjType/Value/FBComObjTypeParameterEnums").text = "MW"
        self.assertEqual(
            load_project(self.save(tree)).communications["%WRITE_VAR0"].function_code,
            16,
        )


if __name__ == "__main__":
    unittest.main()
