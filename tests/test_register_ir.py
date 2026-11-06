"""Register raw IL must preserve pre-call pin evaluation and native resources."""

from pathlib import Path
import tempfile
import unittest

from m200.il import Machine, validate
from m200.model import Program, CompileError
from m200.registers import RegisterConfig
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.frontend import compile_source


class RegisterIRTests(unittest.TestCase):
    def self_status(self):
        return Program(
            rungs=[
                ["LD 1", "[%R0.I:=11]"],
                ["LD %I0.4", "[%R0.O:=42]"],
                [
                    "BLK %R0",
                    "LD %I0.0",
                    "R",
                    "LD %I0.1",
                    "I",
                    "LD %I0.1",
                    "ANDN %R0.E",
                    "O",
                    "END_BLK",
                ],
                ["LD %R0.E", "ST %Q0.0"],
                ["LD 1", "[%MW0:=%R0.O]"],
            ],
            registers={0: RegisterConfig()},
        )

    def check_self_status(self, program):
        machine = Machine(program)
        actual = []
        for frame in ({0: 1}, {}, {4: 1}, {}, {1: 1}, {1: 1}, {}):
            q = machine.step(frame)
            actual.append((q[0], machine.words[0]))
        self.assertEqual(
            actual,
            [
                (True, 0),
                (True, 0),
                (True, 42),
                (True, 42),
                (False, 42),
                (True, 11),
                (True, 11),
            ],
        )

    def test_pre_call_self_status_matches_the_native_latched_observation(self):
        self.check_self_status(self.self_status())

    def test_complex_raw_pins_normalize_and_reverse_without_eager_status_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "self.smbp"
            write_project(
                self.self_status(),
                Path(__file__).parent / "fixtures/official_tm200ce40t_memory.smbp",
                project,
            )
            restored = load_project(project)
            self.check_self_status(restored)
            source = Path(directory) / "self.cpp"
            source.write_text(to_cpp(restored))
            self.check_self_status(compile_source(source))

    def test_unused_explicit_config_and_property_only_instances_are_valid(self):
        program = Program(
            [["LD 1", "[%R3.O:=-7]"], ["LD %R3.E", "ST %Q0.0"]],
            registers={3: RegisterConfig("Lifo")},
        )
        machine = Machine(Program.from_dict(program.as_dict()))
        self.assertTrue(machine.step({})[0])
        self.assertEqual(machine.registers[3].read("O"), -7)

    def test_cli_reports_native_queue_resources_separately_from_mw_memory(self):
        from m200.cli import report

        resources = report(Program(registers={3: RegisterConfig("Lifo")}))["resources"]
        self.assertEqual(resources["registers"], 1)
        self.assertEqual(resources["register_capacity"], 4)
        self.assertEqual(resources["required_register_allocation"], 4)
        self.assertEqual(resources["register_queue_words"], 16)
        self.assertEqual(resources["memory_words"], 0)

    def compile_body(self, body):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "capacity.cpp"
            source.write_text("#include <plc.hpp>\n" + body)
            return compile_source(source)

    def test_native_input_pins_work_with_the_entire_user_bit_bank_reserved(self):
        program = self.compile_body(
            "plc::BitMemory all{1024};plc::Fifo r{0};void scan(){"
            "r.update(plc::input(0),plc::input(1),plc::input(2));}"
        )
        self.assertEqual(program.metadata["allocation"]["allocated_bits"], 0)
        self.assertEqual(
            program.rungs,
            [["BLK %R0", "LD %I0.0", "R", "LD %I0.1", "I", "LD %I0.2", "O", "END_BLK"]],
        )

    def test_native_word_comparison_works_with_the_entire_mw_bank_reserved(self):
        program = self.compile_body(
            "plc::WordMemory all{8000};plc::Fifo r{0};void scan(){"
            "plc::output(0,r.output()==0);}"
        )
        self.assertEqual(program.metadata["allocation"]["allocated_words"], 0)
        self.assertIn(["LD [%R0.O=0]", "ST %Q0.0"], program.rungs)
        machine = Machine(program)
        machine.words = [1234] * 8000
        self.assertTrue(machine.step({})[0])
        self.assertEqual(machine.words, [1234] * 8000)

    def test_captured_numeric_value_survives_a_later_register_mutation(self):
        program = self.compile_body(
            "plc::Fifo r{0};void scan(){r.set_output(11);"
            "plc::i16 before=r.output();r.set_output(22);"
            "plc::output(0,before==11);plc::output(1,r.output()==22);}"
        )
        self.assertEqual(Machine(program).step({})[:2], [True, True])

    def test_undefined_properties_status_writes_and_malformed_blocks_are_rejected(self):
        for rungs, configs in (
            ([["LD %R0.E", "ST %Q0.0"]], {}),
            ([["LD 1", "ST %R0.E"]], {0: RegisterConfig()}),
            (
                [["BLK %R0", "LD 0", "R", "LD 0", "O", "LD 0", "I", "END_BLK"]],
                {0: RegisterConfig()},
            ),
            ([["LD 1", "[%R0.O:=1.5]"]], {0: RegisterConfig()}),
        ):
            with self.subTest(rungs=rungs), self.assertRaises(CompileError):
                validate(Program(rungs, registers=configs))


if __name__ == "__main__":
    unittest.main()
