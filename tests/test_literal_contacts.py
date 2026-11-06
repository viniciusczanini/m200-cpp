"""Native SHORT/OPEN constants must not consume user memory or hide effects."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


FIXTURES = Path(__file__).parent / "fixtures"
NATIVE = FIXTURES / "official_tm200ce40t_literal_contacts.smbp"


class LiteralContactTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)

    def compile(self, body):
        path = self.work / "source.cpp"
        path.write_text("#include <plc.hpp>\n" + body)
        return compile_source(path), path

    def test_official_save_has_exact_native_short_open_and_unchanged_hardware(self):
        data = NATIVE.read_bytes()
        provenance = json.loads(NATIVE.with_suffix(".provenance.json").read_text())
        self.assertEqual(len(data), 93663)
        self.assertEqual(hashlib.sha256(data).hexdigest(), provenance["sha256"])
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        tree = ET.parse(NATIVE)
        baseline = ET.parse(FIXTURES / "official_tm200ce40t_memory.smbp")
        self.assertEqual(
            ET.tostring(tree.find("HardwareConfiguration")),
            ET.tostring(baseline.find("HardwareConfiguration")),
        )
        program = load_project(NATIVE)
        self.assertEqual(
            program.rungs,
            [
                ["LD 1", "[ %MW0 := 123 ]"],
                ["LD 1", "ST %Q0.0"],
                ["LD 0", "ST %Q0.1"],
            ],
        )
        machine = Machine(program)
        machine.outputs[1] = True
        self.assertEqual(machine.step({})[:2], [True, False])
        self.assertEqual(machine.words[0], 123)

    def test_all_user_bits_remain_available_for_a_constant_word_write(self):
        program, source = self.compile(
            "plc::BitMemory all{1024};void scan(){plc::write_word(0,1);}"
        )
        self.assertEqual(program.rungs, [["LD 1", "[%MW0:=1]"]])
        self.assertEqual(program.metadata["allocation"]["allocated_bits"], 0)
        machine = Machine(program)
        machine.memory = [True] * 1024
        machine.step({})
        self.assertEqual(machine.words[0], 1)
        self.assertEqual(machine.memory, [True] * 1024)
        exported = self.work / "all.smbp"
        write_project(program, NATIVE, exported)
        self.assertEqual(load_project(exported).rungs, program.rungs)
        self.assertEqual(run_native(source, [{}])[0], [False] * 16)

    def test_authentic_series_save_binds_literal_contacts_in_both_columns(self):
        path = FIXTURES / "official_tm200ce40t_literal_series.smbp"
        data = path.read_bytes()
        self.assertEqual(len(data), 114394)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "f5b15a32a106c6845bc3edb1a123e5ac28d010ee93e6916947724144b7fce95f",
        )
        program = load_project(path)
        self.assertEqual(len(program.rungs), 8)
        machine = Machine(program)
        self.assertEqual(
            machine.step({0: False})[:8],
            [False, True, True, False, False, False, False, False],
        )
        self.assertEqual(
            machine.step({0: True})[:8],
            [False, True, True, False, False, True, True, False],
        )

    def test_constant_output_coils_clear_retained_state_without_scratch_bits(self):
        program, source = self.compile(
            "void scan(){plc::output(0,true);plc::output(1,false);}"
        )
        self.assertEqual(program.metadata["allocation"]["allocated_bits"], 0)
        self.assertEqual(program.rungs, [["LD 1", "ST %Q0.0"], ["LD 0", "ST %Q0.1"]])
        machine = Machine(program)
        machine.outputs = [True] * 16
        self.assertEqual(machine.step({})[:2], [True, False])
        self.assertEqual(
            run_native(source, [{}, {}]), [[True, False] + [False] * 14] * 2
        )

    def test_graph_and_reverse_round_trip_preserve_both_literal_values(self):
        program = Program([["LD 1", "ST %Q0.0"], ["LD 0", "ST %Q0.1"]])
        path = self.work / "constants.smbp"
        write_project(program, NATIVE, path)
        restored = load_project(path)
        types = [n.text for n in ET.parse(path).findall(".//ElementType")]
        self.assertEqual((types.count("Short"), types.count("Open")), (1, 1))
        source = self.work / "reverse.cpp"
        source.write_text(to_cpp(restored))
        rebuilt = compile_source(source)
        self.assertEqual(Machine(rebuilt).step({})[:2], [True, False])
        self.assertEqual(run_native(source, [{}])[0][:2], [True, False])

    def test_series_literal_truth_tables_survive_graph_and_cpp_round_trips(self):
        rungs = []
        for op in ("LD", "LDN", "AND", "ANDN"):
            for value in ("0", "1"):
                lines = [] if op.startswith("LD") else ["LD %I0.0"]
                rungs.append(lines + [f"{op} {value}", f"ST %Q0.{len(rungs)}"])
        program = Program(rungs)
        path = self.work / "series.smbp"
        write_project(program, NATIVE, path)
        restored = load_project(path)
        self.assertFalse(
            any(
                line in ("LDN 0", "LDN 1", "ANDN 0", "ANDN 1")
                for rung in restored.rungs
                for line in rung
            )
        )
        source = self.work / "series.cpp"
        source.write_text(to_cpp(restored))
        frames = [{"inputs": {0: value}} for value in (0, 1, 0, 1)]
        expected = [
            [False, True, True, False, False, bool(v), bool(v), False]
            for v in (0, 1, 0, 1)
        ]
        for candidate in (program, restored, compile_source(source)):
            machine = Machine(candidate)
            self.assertEqual([machine.step(f["inputs"])[:8] for f in frames], expected)
        self.assertEqual([q[:8] for q in run_native(source, frames)], expected)

    def test_full_output_group_write_needs_no_run_reset_or_constant_cells(self):
        program, _ = self.compile("void scan(){plc::write_output_bits_i16(0,16,3);}")
        self.assertEqual(
            program.metadata["io_lowering"]["run_initialization_outputs"], []
        )
        self.assertEqual(program.metadata["allocation"]["allocated_bits"], 0)
        self.assertTrue(all(rung[0] == "LD 1" for rung in program.rungs))
        self.assertTrue(program.rungs[-1][-1].startswith("[%Q0.0:16:="))
        machine = Machine(program)
        machine.outputs = [True] * 16
        self.assertEqual(machine.step({}), [True, True] + [False] * 14)

    def test_timer_pin_keeps_its_separately_bound_memory_contact_profile(self):
        for value in ("0", "1"):
            with self.subTest(value=value):
                program = Program(
                    [
                        [
                            "BLK %TM0",
                            "LD " + value,
                            "IN",
                            "OUT_BLK",
                            "LD Q",
                            "ST %Q0.0",
                            "END_BLK",
                        ]
                    ],
                    {0: Timer("TON", 100, 100)},
                )
                target = self.work / "timer.smbp"
                write_project(program, NATIVE, target)
                nodes = ET.parse(target).findall(".//LadderEntity")
                contacts = [
                    n.findtext("Descriptor", "")
                    for n in nodes
                    if n.findtext("ElementType") in ("NormalContact", "NegatedContact")
                ]
                self.assertTrue(contacts)
                self.assertFalse(set(contacts) & {"0", "1"})
                restored = Machine(load_project(target))
                expected = Machine(program)
                self.assertEqual(
                    [restored.step({}, 50) for _ in range(4)],
                    [expected.step({}, 50) for _ in range(4)],
                )

    def test_unrelated_normalization_cannot_admit_unbound_modbus_digit_pins(self):
        fixture = FIXTURES / "official_tm200ce40t_modbus_bare_abort_read.smbp"
        for predicate in ("LD 0", "LD 1", "LD %M24"):
            with self.subTest(predicate=predicate):
                program = load_project(fixture)
                program.metadata.pop("rung_origins", None)
                program.rungs[0][1] = predicate
                program.rungs.append(["LD %I0.0", "OR %I0.1", "ST %Q0.0"])
                before = copy.deepcopy(program.as_dict())
                destination = self.work / "mixed.smbp"
                destination.write_bytes(b"preserve previous output")
                if predicate == "LD %M24":
                    write_project(program, fixture, destination)
                    load_project(destination)
                else:
                    with self.assertRaises(CompileError):
                        write_project(program, fixture, destination)
                    self.assertEqual(
                        destination.read_bytes(), b"preserve previous output"
                    )
                self.assertEqual(program.as_dict(), before)

    def test_forged_literal_types_descriptors_and_connections_are_rejected(self):
        original = ET.parse(NATIVE)
        mutations = (
            (0, "ElementType", "Open"),
            (2, "ElementType", "Short"),
            (0, "Descriptor", "1"),
            (0, "ChosenConnection", "Left"),
            (0, "Column", "1"),
        )
        for rung, field, value in mutations:
            with self.subTest(rung=rung, field=field, value=value):
                tree = copy.deepcopy(original)
                node = tree.findall(".//RungEntity")[rung].find(
                    "LadderElements/LadderEntity"
                )
                node.find(field).text = value
                path = self.work / "forged.smbp"
                tree.write(path, encoding="utf-8", xml_declaration=True)
                with self.assertRaises(CompileError):
                    load_project(path)


if __name__ == "__main__":
    unittest.main()
