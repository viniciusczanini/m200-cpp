"""Register pipeline expectations from the bounded native observation records.

The traces are literal oracles, independent of both the VM and the native SDK.
Local agreement does not establish official-editor or physical-PLC acceptance.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError, Program


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
TEMPLATE = FIXTURES / "official_tm200ce40t_memory.smbp"


class RegisterToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="m200-register-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def source(self, body, name="program.cpp"):
        path = self.work / name
        path.write_text("#include <plc.hpp>\n" + body)
        return path

    def compile(self, body):
        from m200.frontend import compile_source

        path = self.source(body)
        return path, compile_source(path)

    def assert_trace(self, program, frames, expected):
        from m200.il import Machine

        machine = Machine(program)
        got = [machine.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]
        self.assertEqual(got, expected)
        return machine

    def assert_pipeline(self, body, frames, rows, modes):
        """Exercise generated XML and its actual reverse source, not an audit stub."""
        from m200.frontend import compile_source
        from m200.native import run_native
        from m200.project import load_project, write_project
        from m200.reverse import to_cpp

        expected = [list(row) + [False] * (16 - len(row)) for row in rows]
        source, program = self.compile(body)
        literal_config = {str(i): {"mode": mode} for i, mode in modes.items()}
        self.assertEqual(program.as_dict()["registers"], literal_config)
        encoded = json.loads(json.dumps(program.as_dict()))
        decoded = Program.from_dict(encoded)
        self.assertEqual(decoded.as_dict()["registers"], literal_config)
        self.assert_trace(program, frames, expected)
        self.assertEqual(run_native(source, frames), expected)

        destination = self.work / "generated.smbp"
        write_project(program, TEMPLATE, destination)
        generated = ET.parse(destination).getroot()
        original = ET.parse(TEMPLATE).getroot()
        self.assertEqual(
            ET.tostring(generated.find("HardwareConfiguration")),
            ET.tostring(original.find("HardwareConfiguration")),
        )
        imported = load_project(destination)
        self.assertEqual(imported.as_dict()["registers"], literal_config)
        self.assert_trace(imported, frames, expected)

        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(imported))
        self.assertEqual(run_native(reverse, frames), expected)
        rebuilt = compile_source(reverse)
        self.assertEqual(rebuilt.as_dict()["registers"], literal_config)
        self.assert_trace(rebuilt, frames, expected)
        rewritten = self.work / "rewritten.smbp"
        write_project(rebuilt, TEMPLATE, rewritten)
        self.assert_trace(load_project(rewritten), frames, expected)
        return program

    def test_fifo_lifo_literal_order_held_store_and_simultaneous_noop(self):
        # A held Store must not enqueue a changed I; fresh I+O must do neither.
        frames = [
            {"inputs": {0: True}},
            {"inputs": {4: True}},
            {"inputs": {2: True}},
            {},
            {"inputs": {1: True}},
            {"inputs": {1: True, 3: True}},
            {"inputs": {3: True}},
            {"inputs": {1: True, 3: True}},
            {},
            {"inputs": {1: True, 2: True}},
            {},
            {"inputs": {2: True}},
            {"inputs": {2: True}},
            {},
            {"inputs": {2: True}},
            {},
            {"inputs": {2: True}},
        ]
        for kind, mode, first, last in (
            ("Fifo", "Fifo", (0, 0, 0, 1, 0), (1, 0, 0, 0, 1)),
            ("Lifo", "Lifo", (0, 0, 0, 0, 1), (1, 0, 0, 1, 0)),
        ):
            with self.subTest(mode=mode):
                self.assert_pipeline(
                    "plc::" + kind + " r{0};void scan(){"
                    "if(plc::input(3)){r.set_input(22);}else{r.set_input(11);}"
                    "if(plc::input(4)){r.set_output(42);}"
                    "r.update(plc::input(0),plc::input(1),plc::input(2));"
                    "if(plc::input(0)){r.set_output(42);}"
                    "plc::output(0,r.empty());plc::output(1,r.full());"
                    "plc::output(2,r.output()==42);"
                    "plc::output(3,r.output()==11);plc::output(4,r.output()==22);}",
                    frames,
                    [
                        (1, 0, 1, 0, 0),
                        (1, 0, 1, 0, 0),
                        (1, 0, 1, 0, 0),
                        (1, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        (0, 0, 1, 0, 0),
                        first,
                        first,
                        first,
                        last,
                        last,
                        last,
                    ],
                    {0: mode},
                )

    def test_capacity_sixteen_ignored_full_store_and_held_retrieve(self):
        # Off-by-one capacity, overwrite and deferred full-Store edges all fail.
        frames = [{"inputs": {0: True}}, {}]
        rows = [(1, 0, 1, 0, 0)] * 2
        for _ in range(15):
            frames += [{"inputs": {1: True}}, {}]
            rows += [(0, 0, 1, 0, 0)] * 2
        frames += [{"inputs": {1: True}}, {}]
        rows += [(0, 1, 1, 0, 0)] * 2
        # I11 on full is refused. A new O while I remains high frees one slot;
        # the held I must not silently occupy it in the following call.
        frames += [
            {"inputs": {1: True, 3: True}},
            {"inputs": {1: True, 2: True, 3: True}},
            {"inputs": {1: True, 3: True}},
            {},
            {"inputs": {1: True, 3: True}},
            {},
        ]
        rows += [
            (0, 1, 1, 0, 0),
            (0, 0, 0, 1, 0),
            (0, 0, 0, 1, 0),
            (0, 0, 0, 1, 0),
            (0, 1, 0, 1, 0),
            (0, 1, 0, 1, 0),
        ]
        for kind, drain in (
            ("Fifo", [(0, 0, 0, 1, 0)] * 15 + [(1, 0, 0, 0, 1)]),
            ("Lifo", [(0, 0, 0, 0, 1)] + [(0, 0, 0, 1, 0)] * 14 + [(1, 0, 0, 1, 0)]),
        ):
            with self.subTest(mode=kind):
                drain_frames, drain_rows = [], []
                for row in drain:
                    drain_frames += [{"inputs": {2: True}}, {}]
                    drain_rows += [row, row]
                drain_frames += [{"inputs": {2: True}}, {"inputs": {2: True}}]
                drain_rows += [drain[-1]] * 2
                self.assert_pipeline(
                    "plc::" + kind + " r{0};void scan(){"
                    "if(plc::input(3)){r.set_input(11);}else{r.set_input(22);}"
                    "r.update(plc::input(0),plc::input(1),plc::input(2));"
                    "if(plc::input(0)){r.set_output(42);}"
                    "plc::output(0,r.empty());plc::output(1,r.full());"
                    "plc::output(2,r.output()==42);plc::output(3,r.output()==22);"
                    "plc::output(4,r.output()==11);}",
                    frames + drain_frames,
                    rows + drain_rows,
                    {0: kind},
                )

    def test_sparse_r3_words_are_signed_independent_and_output_write_keeps_queue(self):
        # Register data must stay separate from MW0 and from another resource.
        self.assert_pipeline(
            "plc::Fifo a{0};plc::Lifo b{3};void scan(){"
            "plc::write_word(0,-32768);a.set_input(plc::read_word(0));"
            "b.set_input(32767);"
            "a.update(plc::input(0),plc::input(1),plc::input(2));"
            "b.update(plc::input(0),plc::input(3),plc::input(4));"
            "if(plc::input(5)){a.set_output(-123);b.set_output(123);}"
            "plc::output(0,a.empty());plc::output(1,b.empty());"
            "plc::output(2,a.output()==-32768);plc::output(3,b.output()==32767);"
            "plc::output(4,a.output()==-123);plc::output(5,b.output()==123);"
            "plc::output(6,plc::read_word(0)==-32768);"
            "if(plc::input(0)){a.set_input(-32768);b.set_input(32767);}"
            "plc::output(7,a.input()==-32768);plc::output(8,b.input()==32767);}",
            [
                {"inputs": {0: True, 5: True}},
                {},
                {"inputs": {1: True, 3: True}},
                {},
                {"inputs": {5: True}},
                {"inputs": {2: True}},
                {},
                {"inputs": {4: True}},
            ],
            [
                (1, 1, 0, 0, 1, 1, 1, 1, 1),
                (1, 1, 0, 0, 1, 1, 1, 1, 1),
                (0, 0, 0, 0, 1, 1, 1, 1, 1),
                (0, 0, 0, 0, 1, 1, 1, 1, 1),
                (0, 0, 0, 0, 1, 1, 1, 1, 1),
                (1, 0, 1, 0, 0, 1, 1, 1, 1),
                (1, 0, 1, 0, 0, 1, 1, 1, 1),
                (1, 1, 1, 1, 0, 0, 1, 1, 1),
            ],
            {0: "Fifo", 3: "Lifo"},
        )

    def test_property_only_r3_preserves_configuration_without_reserved_queue_words(
        self,
    ):
        program = self.assert_pipeline(
            "plc::Fifo r{3};void scan(){r.set_input(-32768);r.set_output(32767);"
            "plc::output(0,r.input()==-32768);plc::output(1,r.output()==32767);"
            "plc::output(2,r.empty());plc::output(3,r.full());}",
            [{}, {}],
            [(1, 1, 1, 0), (1, 1, 1, 0)],
            {3: "Fifo"},
        )
        from m200.numeric import memory_words_used

        # Each i16 getter may snapshot its value in one ephemeral compiler word.
        # Two getters must not reserve sixteen ordinary words for the native queue.
        self.assertLessEqual(len(memory_words_used(program)), 2)

    def test_all_four_shared_id_slots_accept_mixed_modes(self):
        self.assert_pipeline(
            "plc::Fifo a{0};plc::Lifo b{1};plc::Fifo c{2};plc::Lifo d{3};"
            "void scan(){a.set_input(11);b.set_input(22);"
            "c.set_output(-11);d.set_output(-22);"
            "plc::output(0,a.input()==11);plc::output(1,b.input()==22);"
            "plc::output(2,c.output()==-11);plc::output(3,d.output()==-22);}",
            [{}, {}],
            [(1, 1, 1, 1), (1, 1, 1, 1)],
            {0: "Fifo", 1: "Lifo", 2: "Fifo", 3: "Lifo"},
        )

    def test_word_writes_and_shared_data_follow_source_order_around_call(self):
        # Moving the first input read past the MW write or losing O writes fails.
        self.assert_pipeline(
            "plc::Fifo r{0};void scan(){plc::write_word(0,11);"
            "r.set_input(plc::read_word(0));plc::write_word(0,22);"
            "r.update(plc::input(0),plc::input(1),plc::input(2));"
            "r.set_input(plc::read_word(0));"
            "if(plc::input(3)){r.set_output(42);}"
            "plc::write_word(0,r.output());"
            "plc::output(0,r.empty());plc::output(1,r.input()==22);"
            "plc::output(2,r.output()==42);plc::output(3,r.output()==11);"
            "plc::output(4,plc::read_word(0)==42);"
            "plc::output(5,plc::read_word(0)==11);}",
            [
                {"inputs": {0: True, 3: True}},
                {},
                {"inputs": {1: True}},
                {},
                {"inputs": {2: True}},
                {"inputs": {3: True}},
                {"inputs": {2: True}},
            ],
            [
                (1, 1, 1, 0, 1, 0),
                (1, 1, 1, 0, 1, 0),
                (0, 1, 1, 0, 1, 0),
                (0, 1, 1, 0, 1, 0),
                (1, 1, 0, 1, 0, 1),
                (1, 1, 1, 0, 1, 0),
                (1, 1, 1, 0, 1, 0),
            ],
            {0: "Fifo"},
        )

    def test_fifo_self_status_arguments_are_captured_before_update(self):
        self.assert_pipeline(
            "plc::Fifo r{0};void scan(){r.set_input(11);"
            "if(plc::input(4)){r.set_output(42);}"
            "r.update(plc::input(0),plc::input(1),plc::input(1)&&!r.empty());"
            "plc::output(0,r.empty());plc::output(1,r.full());"
            "plc::output(2,r.output()==42);plc::output(3,r.output()==11);}",
            [
                {"inputs": {0: True}},
                {"inputs": {4: True}},
                {},
                {"inputs": {1: True}},
                {"inputs": {1: True}},
                {"inputs": {1: True}},
                {},
            ],
            [
                (1, 0, 0, 0),
                (1, 0, 1, 0),
                (1, 0, 1, 0),
                (0, 0, 1, 0),
                (1, 0, 0, 1),
                (1, 0, 0, 1),
                (1, 0, 0, 1),
            ],
            {0: "Fifo"},
        )

    def test_fifo_reset_store_collision_then_reset_falls_with_store_held(self):
        # These exact FIFO pins/words follow the native collision observation.
        self.assert_pipeline(
            "plc::Fifo r{0};void scan(){r.set_input(11);"
            "if(plc::input(4)){r.set_output(42);}"
            "r.update(plc::input(0),plc::input(1),plc::input(2));"
            "plc::output(0,r.empty());plc::output(1,r.full());"
            "plc::output(2,r.input()==0);plc::output(3,r.output()==0);"
            "plc::output(4,r.output()==11);}",
            [
                {"inputs": {0: True}},
                {"inputs": {4: True}},
                {"inputs": {0: True, 1: True, 4: True}},
                {"inputs": {0: True, 1: True}},
                {"inputs": {1: True}},
                {"inputs": {1: True}},
                {},
                {"inputs": {1: True}},
                {},
                {"inputs": {2: True}},
                {},
                {"inputs": {2: True}},
                {},
                {"inputs": {2: True}},
            ],
            [
                (1, 0, 1, 1, 0),
                (1, 0, 0, 0, 0),
                (1, 0, 1, 1, 0),
                (1, 0, 1, 1, 0),
                (0, 0, 0, 1, 0),
                (0, 0, 0, 1, 0),
                (0, 0, 0, 1, 0),
                (0, 0, 0, 1, 0),
                (0, 0, 0, 1, 0),
                (0, 0, 0, 0, 1),
                (0, 0, 0, 0, 1),
                (1, 0, 0, 0, 1),
                (1, 0, 0, 0, 1),
                (1, 0, 0, 0, 1),
            ],
            {0: "Fifo"},
        )

    def test_repeated_calls_use_the_pins_captured_for_each_cpp_call(self):
        # Local C++ contract; native repeated-call observations remain pending.
        # The first call lowers both requests before the second call each scan.
        self.assert_pipeline(
            "plc::Fifo r{0};void scan(){r.set_input(11);"
            "r.update(plc::input(0),false,false);"
            "r.update(plc::input(0),plc::input(1),plc::input(2));"
            "if(plc::input(0)){r.set_output(42);}"
            "plc::output(0,r.empty());plc::output(1,r.output()==42);"
            "plc::output(2,r.output()==11);}",
            [
                {"inputs": {0: True}},
                {},
                {"inputs": {1: True}},
                {"inputs": {1: True}},
                {},
                {"inputs": {2: True}},
                {"inputs": {2: True}},
                {"inputs": {2: True}},
            ],
            [
                (1, 1, 0),
                (1, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (0, 0, 1),
                (1, 0, 1),
                (1, 0, 1),
            ],
            {0: "Fifo"},
        )

    def test_skipped_calls_keep_the_last_called_request_history(self):
        # Local C++ contract; unseen input transitions are not resource calls.
        self.assert_pipeline(
            "plc::Fifo r{0};void scan(){r.set_input(11);"
            "if(plc::input(3)){r.update(plc::input(0),plc::input(1),plc::input(2));}"
            "if(plc::input(0)){r.set_output(42);}"
            "plc::output(0,r.empty());plc::output(1,r.output()==42);"
            "plc::output(2,r.output()==11);}",
            [
                {"inputs": {0: True, 3: True}},
                {"inputs": {3: True}},
                {"inputs": {1: True}},
                {"inputs": {1: True, 3: True}},
                {},
                {"inputs": {1: True}},
                {"inputs": {1: True, 3: True}},
                {"inputs": {3: True}},
                {"inputs": {2: True, 3: True}},
                {"inputs": {2: True, 3: True}},
            ],
            [
                (1, 1, 0),
                (1, 1, 0),
                (1, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (0, 1, 0),
                (1, 0, 1),
                (1, 0, 1),
            ],
            {0: "Fifo"},
        )

    def test_register_constructor_calls_and_data_types_fail_closed(self):
        from m200.frontend import compile_source

        invalid = [
            "plc::Fifo r{4};void scan(){}",
            "plc::Lifo r{-1};void scan(){}",
            "plc::Fifo r{true};void scan(){}",
            "plc::Fifo r{plc::input(0)};void scan(){}",
            "plc::Fifo a{0};plc::Lifo b{0};void scan(){}",
            "plc::Fifo a{3};plc::Fifo b{3};void scan(){}",
            "void scan(){plc::Fifo r{0};r.update(false,false,false);}",
            "plc::Fifo r{0};void scan(){r.set_input(true);}",
            "plc::Fifo r{0};void scan(){r.set_output(1.0f);}",
            "plc::Fifo r{0};void scan(){plc::i32 n=11;r.set_input(n);}",
            "plc::Fifo r{0};void scan(){r.set_input(32768);}",
            "plc::Fifo r{0};void scan(){r.set_output(-32769);}",
            "plc::Fifo r{0};void scan(){r.update(1,false,false);}",
            "plc::Fifo r{0};void scan(){r.empty()=true;}",
            "plc::Fifo r{0};void scan(){r.full()=false;}",
            "plc::Fifo r{0};void scan(){r.set_empty(true);}",
            "plc::Fifo r{0};void scan(){plc::output(0,r.done());}",
            "plc::Fifo r{0};void scan(){plc::output(0,r.update(false,false,false));}",
        ]
        for body in invalid:
            with self.subTest(body=body):
                with self.assertRaises(CompileError):
                    compile_source(self.source(body, "invalid.cpp"))

    def test_json_register_map_is_config_only_and_rejects_malformed_values(self):
        data = Program().as_dict()
        data["registers"] = {"0": {"mode": "Fifo"}, "3": {"mode": "Lifo"}}
        restored = Program.from_dict(copy.deepcopy(data))
        self.assertEqual(restored.as_dict()["registers"], data["registers"])
        for registers in (
            None,
            [],
            {"4": {"mode": "Fifo"}},
            {"-1": {"mode": "Fifo"}},
            {"00": {"mode": "Fifo"}},
            {"+0": {"mode": "Fifo"}},
            {0: {"mode": "Fifo"}},
            {"0": {}},
            {"0": "Fifo"},
            {"0": {"mode": "FIFO"}},
            {"0": {"mode": "fifo"}},
            {"0": {"mode": "Lifo "}},
            {"0": {"mode": 1}},
            {"0": {"mode": True}},
            {"0": {"mode": {"value": "Fifo"}}},
            {"0": {"mode": "Fifo", "depth": 0}},
            {"0": {"mode": "Fifo", "queue": [11]}},
            {"0": {"mode": "Fifo", "input": 11}},
            {"0": {"mode": "Fifo", "unknown": 1}},
        ):
            with self.subTest(registers=registers):
                rejected = copy.deepcopy(data)
                rejected["registers"] = registers
                before = copy.deepcopy(rejected)
                with self.assertRaises(CompileError):
                    Program.from_dict(rejected)
                self.assertEqual(rejected, before)

    def test_duplicate_json_register_keys_and_mode_fields_are_rejected(self):
        from m200.jsonio import loads

        for raw in (
            '{"0":{"mode":"Fifo"},"0":{"mode":"Lifo"}}',
            '{"0":{"mode":"Fifo","mode":"Lifo"}}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(CompileError):
                    loads(raw)

    def test_raw_il_rejects_noncanonical_resource_and_status_writes(self):
        from m200.il import validate

        _, configured = self.compile(
            "plc::Fifo r{0};void scan(){r.update(false,false,false);}"
        )
        for rungs in (
            [["LD %R4.E", "ST %Q0.0"]],
            [["LD %R00.E", "ST %Q0.0"]],
            [["LD %R-1.E", "ST %Q0.0"]],
            [["LD %R1.E", "ST %Q0.0"]],
            [["LD %R0.Unknown", "ST %Q0.0"]],
            [["LD 1", "ST %R0.E"]],
            [["LD 1", "ST %R0.F"]],
            [["LD 1", "[%R0.E:=1]"]],
            [["LD 1", "[%R0.F:=1]"]],
            [["LD 1", "[%R0.I:=1.0]"]],
            [["BLK %R0", "LD 0", "R", "LD 0", "I", "END_BLK"]],
            [["BLK %R0", "LD 0", "R", "LD 0", "I", "LD 0", "O", "MAGIC", "END_BLK"]],
        ):
            with self.subTest(rungs=rungs):
                program = copy.deepcopy(configured)
                program.rungs = rungs
                with self.assertRaises(CompileError):
                    validate(program)

    def test_authentic_canonical_register_fixtures_import_and_execute(self):
        from m200.frontend import compile_source
        from m200.native import run_native
        from m200.project import load_project
        from m200.reverse import to_cpp

        frames = [
            {"inputs": {0: True}},
            {},
            {"inputs": {1: True}},
            {},
            {"inputs": {1: True, 3: True}},
            {},
            {"inputs": {2: True}},
            {},
            {"inputs": {2: True}},
        ]
        for kind, first, last in (
            ("fifo", (0, 0, 1, 0), (1, 0, 0, 1)),
            ("lifo", (0, 0, 0, 1), (1, 0, 1, 0)),
        ):
            with self.subTest(kind=kind):
                path = FIXTURES / (
                    "official_tm200ce40t_register_" + kind + "_three_ld.smbp"
                )
                before = path.read_bytes()
                program = load_project(path)
                self.assertEqual(
                    program.as_dict()["registers"],
                    {"0": {"mode": "Fifo" if kind == "fifo" else "Lifo"}},
                )
                # Add public observations to the imported native instructions.
                # The post-reset O write avoids claiming a LIFO reset-word rule.
                instrumented = copy.deepcopy(program)
                instrumented.rungs += [
                    ["LD %I0.0", "[%R0.O:=42]"],
                    ["LD [%R0.O=11]", "ST %Q0.2"],
                    ["LD [%R0.O=22]", "ST %Q0.3"],
                ]
                rows = [
                    (1, 0, 0, 0),
                    (1, 0, 0, 0),
                    (0, 0, 0, 0),
                    (0, 0, 0, 0),
                    (0, 0, 0, 0),
                    (0, 0, 0, 0),
                    first,
                    first,
                    last,
                ]
                expected = [list(row) + [False] * 12 for row in rows]
                self.assert_trace(instrumented, frames, expected)
                reverse = self.work / (kind + "-fixture.cpp")
                reverse.write_text(to_cpp(instrumented))
                self.assertEqual(run_native(reverse, frames), expected)
                self.assert_trace(compile_source(reverse), frames, expected)
                self.assertEqual(path.read_bytes(), before)

    def test_register_export_keeps_wrong_cpu_and_unknown_active_gates_atomic(self):
        from m200.project import load_project, write_project

        _, program = self.compile(
            "plc::Fifo r{0};void scan(){r.update(plc::input(0),plc::input(1),plc::input(2));}"
        )
        for mutation in ("cpu", "unknown", "register-mode", "register-address"):
            with self.subTest(mutation=mutation):
                tree = ET.parse(TEMPLATE)
                root = tree.getroot()
                if mutation == "cpu":
                    root.find(
                        "HardwareConfiguration/Plc/Cpu/Reference"
                    ).text = "TM221CE16R"
                elif mutation == "unknown":
                    ET.SubElement(
                        root.find("SoftwareConfiguration"), "UnknownActiveObject"
                    ).text = "true"
                else:
                    registers = root.find("SoftwareConfiguration/Registers")
                    row = ET.SubElement(registers, "Register")
                    for tag, value in (
                        ("Address", "%R1" if mutation == "register-address" else "%R0"),
                        ("Index", "0"),
                        ("Type", "Other" if mutation == "register-mode" else "Fifo"),
                    ):
                        ET.SubElement(row, tag).text = value
                bad = self.work / (mutation + ".smbp")
                tree.write(bad, encoding="utf-8")
                destination = self.work / "keep.smbp"
                destination.write_bytes(b"keep previous project\x00\xff")
                with self.assertRaises(CompileError):
                    load_project(bad)
                with self.assertRaises(CompileError):
                    write_project(program, bad, destination)
                self.assertEqual(
                    destination.read_bytes(), b"keep previous project\x00\xff"
                )

    def test_cli_failed_register_compile_preserves_all_previous_output_bytes(self):
        source = self.source(
            "plc::Fifo r{0};void scan(){r.set_input(11);"
            "r.update(plc::input(0),plc::input(1),plc::input(2));"
            "plc::output(0,r.empty());}"
        )
        out = self.work / "compiled"
        command = [
            sys.executable,
            "-m",
            "m200",
            "compile",
            str(source),
            "-o",
            str(out),
            "--template",
            str(TEMPLATE),
        ]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = {path.name: path.read_bytes() for path in out.iterdir()}
        self.source("plc::Fifo a{0};plc::Lifo b{0};void scan(){}")
        failed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("M200-E", failed.stderr)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertEqual(
            {path.name: path.read_bytes() for path in out.iterdir()}, before
        )


if __name__ == "__main__":
    unittest.main()
