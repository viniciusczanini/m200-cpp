"""Closed bit-object XML bindings backed by exact official-editor saves.

Memory peer checks are local model tests, not official communication proof.
"""

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
from m200.modbus import MemoryModbusPeer, MemoryTransport, ModbusConfig
from m200.numeric import memory_words_used
from m200.project import load_project, write_project
from m200.reverse import to_cpp


FIXTURES = Path(__file__).parent / "fixtures"
CASES = [
    ("read_i", "READ_VAR", 1, 2, 17, 200, "%M10"),
    ("read_q", "READ_VAR", 2, 1, 41, 220, "%M10"),
    ("write_q", "WRITE_VAR", 2, 15, 73, 240, "%M11"),
]


class BitCommunicationXMLTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def fixture(self, suffix):
        return FIXTURES / ("official_tm200ce40t_modbus_" + suffix + ".smbp")

    def modified(self, suffix, **values):
        tree = ET.parse(self.fixture(suffix))
        for path, value in values.items():
            tree.find(path).text = str(value)
        return tree

    def load_tree(self, tree):
        path = self.work / "modified.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return load_project(path)

    def run_memory_block(self, program, peer, execute, words):
        machine = Machine(program, communication_transport=MemoryTransport(peer))
        for index, value in words.items():
            machine.words[index] = value
        for value in (False, True, True):
            machine.memory[execute] = value
            machine.step({}, 10)
        return machine

    def test_exact_editor_saved_bit_bindings_import_objects_and_two_word_buffers(self):
        for suffix, kind, obj, function, first, index, execute in CASES:
            with self.subTest(case=suffix):
                path = self.fixture(suffix)
                provenance = json.loads(
                    path.with_suffix(".provenance.json").read_text()
                )
                self.assertEqual(path.stat().st_size, provenance["bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), provenance["sha256"]
                )
                try:
                    program = load_project(path)
                except CompileError as error:
                    self.fail(
                        "Exact editor-saved bit binding must import: " + str(error)
                    )
                key = "%" + kind + "0"
                self.assertEqual(
                    program.communications,
                    {
                        key: ModbusConfig(
                            kind=kind,
                            obj_type=obj,
                            first_obj=first,
                            quantity=17,
                            index_data=index,
                        )
                    },
                )
                self.assertEqual(
                    program.rungs,
                    [["BLK " + key, "LD " + execute, "EXECUTE", "END_BLK"]],
                )
                self.assertEqual(program.communications[key].function_code, function)
                self.assertEqual(program.communications[key].data_words, 2)

    def test_cpp_constructor_reverse_and_export_retain_bit_configuration(self):
        for suffix, kind, obj, function, first, index, _ in CASES:
            with self.subTest(case=suffix):
                path = self.fixture(suffix)
                original = path.read_bytes()
                expected = ModbusConfig(
                    kind=kind,
                    obj_type=obj,
                    first_obj=first,
                    quantity=17,
                    index_data=index,
                )
                cls = "ReadVar" if kind == "READ_VAR" else "WriteVar"
                enum = "DiscreteInputs" if obj == 1 else "Coils"
                source = self.work / "constructor.cpp"
                source.write_text(
                    "#include <plc.hpp>\n"
                    f"plc::{cls} fb{{0,plc::Link::Serial1,1,100,"
                    f"plc::Object::{enum},{first},17,{index}}};\n"
                    "void scan(){fb.update(plc::input(0),false);}\n"
                )
                compiled = compile_source(source)
                key = "%" + kind + "0"
                self.assertEqual(compiled.communications, {key: expected})
                saved = load_project(path)
                reverse = self.work / "reverse.cpp"
                reverse.write_text(to_cpp(saved))
                rebuilt = compile_source(reverse)
                self.assertEqual(rebuilt.communications, {key: expected})
                for candidate in (compiled, rebuilt):
                    destination = self.work / "export.smbp"
                    write_project(candidate, path, destination)
                    imported = load_project(destination)
                    self.assertEqual(imported.communications, {key: expected})
                    self.assertEqual(
                        imported.communications[key].function_code, function
                    )
                    self.assertEqual(memory_words_used(imported), {index, index + 1})
                    actual = ET.parse(destination)
                    self.assertEqual(
                        actual.findtext(".//ObjType/Value/FBComObjTypeParameterEnums"),
                        "I" if obj == 1 else "Q",
                    )
                    self.assertEqual(
                        ET.canonicalize(
                            ET.tostring(
                                actual.find("HardwareConfiguration"), encoding="unicode"
                            ),
                            strip_text=True,
                        ),
                        ET.canonicalize(
                            ET.tostring(
                                ET.parse(path).find("HardwareConfiguration"),
                                encoding="unicode",
                            ),
                            strip_text=True,
                        ),
                    )
                self.assertEqual(path.read_bytes(), original)

    def test_imported_reads_pack_seventeen_bits_from_the_selected_remote_space(self):
        pattern = [bool(0xA55A & (1 << bit)) for bit in range(16)] + [True]
        for suffix, _, obj, _, first, index, _ in CASES[:2]:
            with self.subTest(case=suffix):
                selected = [False] * (first + 18)
                selected[first : first + 17] = pattern
                other = [not value for value in selected]
                peer = MemoryModbusPeer(
                    coils=selected if obj == 2 else other,
                    discrete_inputs=selected if obj == 1 else other,
                )
                machine = self.run_memory_block(
                    load_project(self.fixture(suffix)),
                    peer,
                    10,
                    {
                        index - 1: 0x1234,
                        index: 0xFFFF,
                        index + 1: 0xFFFF,
                        index + 2: 0x5678,
                    },
                )
                self.assertEqual(
                    machine.words[index - 1 : index + 3],
                    [0x1234, 0xA55A, 1, 0x5678],
                )

    def test_imported_write_uses_two_packed_words_and_preserves_remote_neighbors(self):
        peer = MemoryModbusPeer(coils=[True] * 92, discrete_inputs=[False] * 92)
        machine = self.run_memory_block(
            load_project(self.fixture("write_q")),
            peer,
            11,
            {239: 0x1234, 240: 0xA55A, 241: 0xFFFE, 242: 0x5678},
        )
        self.assertEqual(
            peer.coils[73:90],
            [bool(0xA55A & (1 << bit)) for bit in range(16)] + [False],
        )
        self.assertTrue(peer.coils[72] and peer.coils[90])
        self.assertEqual(peer.discrete_inputs, [False] * 92)
        self.assertEqual(machine.words[239:243], [0x1234, 0xA55A, 0xFFFE, 0x5678])

    def test_seventeen_bits_fit_exactly_in_the_last_two_words(self):
        for suffix, kind, obj, _, _, _, _ in CASES:
            with self.subTest(case=suffix):
                tree = self.modified(
                    suffix,
                    **{
                        ".//FirstObj/Value/int": 65519,
                        ".//IndexData/Value/int": 7998,
                        ".//MemoryWordsMemoryAllocation/ForcedCount": 8000,
                    },
                )
                program = self.load_tree(tree)
                self.assertEqual(memory_words_used(program), {7998, 7999})
                self.assertEqual(
                    program.communications["%" + kind + "0"],
                    ModbusConfig(
                        kind=kind,
                        obj_type=obj,
                        first_obj=65519,
                        quantity=17,
                        index_data=7998,
                    ),
                )
                destination = self.work / "last_words.smbp"
                write_project(program, self.fixture(suffix), destination)
                self.assertEqual(
                    ET.parse(destination).findtext(
                        "SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"
                    ),
                    "8000",
                )
                self.assertEqual(
                    load_project(destination).communications, program.communications
                )

    def test_bit_extents_and_manual_allocation_cannot_truncate_the_buffer(self):
        for suffix, kind, _, _, _, _, _ in CASES:
            for field, value in [
                (".//FirstObj/Value/int", 65520),
                (".//IndexData/Value/int", 7999),
                (".//Quantity/Value/int", 2001 if kind == "READ_VAR" else 1969),
                (
                    ".//MemoryWordsMemoryAllocation/ForcedCount",
                    201 if suffix == "read_i" else 221 if suffix == "read_q" else 241,
                ),
            ]:
                with (
                    self.subTest(case=suffix, field=field),
                    self.assertRaises(CompileError),
                ):
                    self.load_tree(self.modified(suffix, **{field: value}))

    def test_words_remain_supported_and_invalid_object_directions_fail(self):
        for suffix, spelling, function in [
            ("read_i", "MW", 3),
            ("read_i", "IW", 4),
            ("write_q", "MW", 16),
        ]:
            with self.subTest(case=suffix, obj=spelling):
                tree = self.modified(
                    suffix,
                    **{
                        ".//ObjType/Value/FBComObjTypeParameterEnums": spelling,
                        ".//Quantity/Value/int": 1,
                    },
                )
                config = next(iter(self.load_tree(tree).communications.values()))
                self.assertEqual(config.function_code, function)
        for suffix, spelling in [
            ("write_q", "I"),
            ("write_q", "IW"),
            ("read_i", "SINGLE_COIL"),
            ("read_q", "SINGLE_REG"),
        ]:
            with (
                self.subTest(case=suffix, obj=spelling),
                self.assertRaises(CompileError),
            ):
                self.load_tree(
                    self.modified(
                        suffix,
                        **{".//ObjType/Value/FBComObjTypeParameterEnums": spelling},
                    )
                )

    def test_bit_configuration_rejects_unknown_duplicate_or_mismatched_fields(self):
        for change in ("duplicate", "unknown", "wrapper", "index", "kind", "enum"):
            tree = ET.parse(self.fixture("read_i"))
            block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
            if change == "duplicate":
                block.append(copy.deepcopy(block.find("ObjType")))
            elif change == "unknown":
                ET.SubElement(block, "BitIndexData").text = "200"
            elif change == "wrapper":
                block.find("IndexData").set("Type", block.find("ObjType").get("Type"))
            elif change == "index":
                block.find("Index").text = "1"
            elif change == "kind":
                block.set(
                    "Type",
                    ET.parse(self.fixture("write_q"))
                    .find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
                    .get("Type"),
                )
            else:
                block.find("ObjType/Value/FBComObjTypeParameterEnums").text = "Coils"
            with self.subTest(change=change), self.assertRaises(CompileError):
                self.load_tree(tree)

    def test_mismatched_kind_and_abort_preserve_existing_output(self):
        valid = ModbusConfig(obj_type=1, first_obj=17, quantity=17, index_data=200)
        for cfg in (
            ModbusConfig(kind="WRITE_READ_VAR", index_data=300, index_data_in=400),
        ):
            key = "%WRITE_VAR0"
            program = Program(
                [
                    ["BLK %READ_VAR0", "LD %M10", "EXECUTE", "END_BLK"],
                    ["BLK " + key, "LD %M11", "EXECUTE", "END_BLK"],
                ],
                communications={"%READ_VAR0": valid, key: cfg},
            )
            destination = self.work / "preserve.smbp"
            destination.write_bytes(b"PRESERVE EXISTING PROJECT")
            sw = ET.parse(self.fixture("read_i")).find("SoftwareConfiguration")
            before = ET.tostring(sw)
            with self.subTest(kind=cfg.kind, obj=cfg.obj_type):
                with self.assertRaises(CompileError):
                    communication_xml.write_blocks(program, sw)
                self.assertEqual(ET.tostring(sw), before)
                with self.assertRaises(CompileError):
                    write_project(program, self.fixture("read_i"), destination)
                self.assertEqual(destination.read_bytes(), b"PRESERVE EXISTING PROJECT")
        abort = Program(
            [["BLK %READ_VAR0", "LD %M10", "EXECUTE", "LD %M13", "ABORT", "END_BLK"]],
            communications={"%READ_VAR0": valid},
        )
        with self.assertRaisesRegex(CompileError, "ABORT"):
            write_project(abort, self.fixture("read_i"), destination)
        self.assertEqual(destination.read_bytes(), b"PRESERVE EXISTING PROJECT")

    def test_connected_output_graph_is_rejected_instead_of_silently_dropped(self):
        tree = ET.parse(self.fixture("read_q"))
        graph = tree.find(".//RungEntity/LadderElements")
        coil = ET.SubElement(graph, "LadderEntity")
        for tag, value in [
            ("ElementType", "Coil"),
            ("Descriptor", "%M14"),
            ("Row", "0"),
            ("Column", "10"),
            ("ChosenConnection", "Left"),
        ]:
            ET.SubElement(coil, tag).text = value
        with self.assertRaises(CompileError):
            self.load_tree(tree)


if __name__ == "__main__":
    unittest.main()
