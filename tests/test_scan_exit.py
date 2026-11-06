"""END-family truth tables and C++ scan exits, without controller STOP semantics."""

import copy
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.ladder_lowering import normalize
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import check_graph, load_project, write_project
from m200.reverse import to_cpp


class ScanExitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def rows(self, program, frames):
        machine = Machine(program)
        return [
            machine.step(frame.get("inputs", {}), frame.get("dt_ms", 10))
            for frame in frames
        ]

    def equivalent(self, program, frames, expected, source=None):
        snapshot = copy.deepcopy(program.as_dict())
        wanted = [row + [False] * (16 - len(row)) for row in expected]
        self.assertEqual(self.rows(program, frames), wanted)
        restored = Program.from_dict(program.as_dict())
        self.assertEqual(self.rows(restored, frames), wanted)
        normalized = normalize(program)
        self.assertEqual(self.rows(normalized, frames), wanted)
        if source is not None:
            self.assertEqual(run_native(source, frames), wanted)
        reconstructed = self.work / "reverse.cpp"
        reconstructed.write_text(to_cpp(program))
        self.assertEqual(run_native(reconstructed, frames), wanted)
        self.assertEqual(self.rows(compile_source(reconstructed), frames), wanted)
        destination = self.work / "exit.smbp"
        write_project(
            program, Path(__file__).parent / "fixtures/synthetic.smbp", destination
        )
        self.assertEqual(self.rows(load_project(destination), frames), wanted)
        self.assertFalse(
            any(
                node.text in ("End", "EndCn", "Stop", "Return")
                for node in ET.parse(destination).findall(".//ElementType")
            )
        )
        self.assertEqual(program.as_dict(), snapshot)
        return normalized

    def cpp(self, body, frames, expected):
        source = self.work / "source.cpp"
        source.write_text("#include <plc.hpp>\n" + body)
        program = compile_source(source)
        self.equivalent(program, frames, expected, source)
        return program

    def test_end_unconditionally_skips_subsequent_rungs_with_false_accumulator(self):
        self.equivalent(
            Program([["LD %I0.0", "ST %Q0.0", "LD 0", "END"], ["LD 1", "ST %Q0.1"]]),
            [{"inputs": {0: state}} for state in (True, False, True)],
            [[True, False], [False, False], [True, False]],
        )

    def test_standalone_end_is_valid_and_next_scan_still_runs(self):
        self.equivalent(
            Program([["LD %I0.0", "ST %Q0.0"], ["END"], ["LD 1", "ST %Q0.1"]]),
            [{"inputs": {0: state}} for state in (False, True, False)],
            [[False, False], [True, False], [False, False]],
        )

    def test_conditional_end_truth_tables_retain_skipped_output_values(self):
        for op, exit_when in (("ENDC", True), ("ENDCN", False)):
            with self.subTest(op=op):
                frames = [
                    {"inputs": {0: exit_when, 1: True}},
                    {"inputs": {0: not exit_when, 1: True}},
                    {"inputs": {0: exit_when, 1: False}},
                    {"inputs": {0: not exit_when, 1: False}},
                ]
                self.equivalent(
                    Program([["LD %I0.0", op], ["LD %I0.1", "ST %Q0.0"]]),
                    frames,
                    [[False], [True], [True], [False]],
                )

    def test_conditional_end_preserves_actions_before_it_and_false_path_after_it(self):
        self.equivalent(
            Program([["LD %I0.0", "ST %Q0.0", "ENDC", "N", "ST %Q0.1"]]),
            [{"inputs": {0: v}} for v in (True, False, True, False)],
            [[True, False], [False, True], [True, True], [False, True]],
        )

    def test_end_completes_time_and_first_scan_bookkeeping(self):
        machine = Machine(Program([["LD %S13", "ST %Q0.0"], ["END"]]))
        self.assertTrue(machine.step(dt_ms=17)[0])
        self.assertEqual(machine.now, 17)
        self.assertFalse(machine.first)
        self.assertFalse(machine.step(dt_ms=23)[0])
        self.assertEqual(machine.now, 40)

    def test_local_execution_budget_does_not_count_instructions_skipped_by_endc(self):
        machine = Machine(
            Program([["LD 1", "ENDC", "LD 1", "ST %Q0.0", "ST %Q0.1"]]),
            instruction_limit=2,
        )
        self.assertEqual(machine.step(dt_ms=10), [False] * 16)
        self.assertEqual(machine.now, 10)
        machine = Machine(
            Program([["LD 0", "ENDC", "LD 1", "ST %Q0.0"]]), instruction_limit=2
        )
        with self.assertRaisesRegex(CompileError, "local execution limit"):
            machine.step()
        self.assertEqual(machine.now, 0)

    def test_cpp_unconditional_return_commits_earlier_output_writes(self):
        self.cpp(
            "void scan(){plc::output(0,plc::input(0));return;plc::output(0,false);plc::output(1,true);}",
            [{"inputs": {0: v}} for v in (True, False, True)],
            [[True, False], [False, False], [True, False]],
        )

    def test_cpp_conditional_return_commits_images_and_retains_skipped_outputs(self):
        self.cpp(
            "void scan(){plc::output(0,plc::input(1));if(plc::input(0)){return;}plc::output(1,plc::input(1));}",
            [
                {"inputs": {0: True, 1: True}},
                {"inputs": {0: False, 1: True}},
                {"inputs": {0: True, 1: False}},
                {"inputs": {0: False, 1: False}},
            ],
            [[True, False], [True, True], [False, True], [False, False]],
        )

    def test_cpp_nested_loop_return_exits_scan_not_only_loop(self):
        self.cpp(
            """void scan(){plc::output(0,false);plc::output(1,false);
for(plc::i16 i=0;i<3;i=plc::add_i16(i,1)){
 for(plc::i16 j=0;j<3;j=plc::add_i16(j,1)){
  if(i==1 && j==2){if(plc::input(0)){plc::output(0,true);return;}}
 }}plc::output(1,true);}""",
            [{"inputs": {0: v}} for v in (True, True, False, True)],
            [[True, False], [True, False], [False, True], [True, False]],
        )

    def test_cpp_goto_into_conditional_return_uses_actual_control_flow(self):
        self.cpp(
            """void scan(){plc::output(0,false);plc::output(1,false);
if(plc::input(0)){goto finish;}
if(plc::input(1)){finish:plc::output(0,true);return;}
plc::output(1,true);}""",
            [{"inputs": {0: bool(n & 1), 1: bool(n & 2)}} for n in range(4)],
            [[False, True], [True, False], [True, False], [True, False]],
        )

    def test_cpp_memory_before_return_is_visible_and_later_write_is_skipped(self):
        self.cpp(
            """void scan(){plc::output(2,plc::read_word(20)==7 && plc::read_m(20));
plc::write_word(20,7);plc::write_m(20,true);
if(plc::input(0)){return;}plc::write_word(20,9);plc::write_m(20,false);
plc::output(0,plc::read_word(20)==9 && !plc::read_m(20));}""",
            [{"inputs": {0: v}} for v in (True, False, True, True)],
            [
                [False, False, False],
                [True, False, True],
                [True, False, False],
                [True, False, True],
            ],
        )
        program = compile_source(self.work / "source.cpp")
        machine = Machine(program)
        machine.step({0: True})
        self.assertEqual(machine.words[20], 7)
        self.assertTrue(machine.memory[20])

    def test_early_exit_skips_timer_block_without_inventing_an_update(self):
        program = Program(
            [
                ["LD %I0.0", "ENDC"],
                [
                    "BLK %TM0",
                    "LD %I0.1",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "ST %Q0.0",
                    "END_BLK",
                ],
            ],
            {0: Timer("TON", 200, 100)},
        )
        self.equivalent(
            program,
            [
                {"inputs": {0: True, 1: True}, "dt_ms": 300},
                {"inputs": {1: True}, "dt_ms": 100},
                {"inputs": {0: True, 1: False}, "dt_ms": 300},
                {"inputs": {1: True}, "dt_ms": 100},
                {"inputs": {1: False}, "dt_ms": 100},
            ],
            [[False], [False], [False], [True], [False]],
        )

    def test_early_exit_distinguishes_sampled_input_edge_from_expression_history(self):
        self.equivalent(
            Program(
                [
                    ["LD %I0.0", "ENDC"],
                    ["LDR %I0.1", "ST %Q0.0"],
                    ["LD %I0.1", "RISING0", "ST %Q0.1"],
                ]
            ),
            [
                {"inputs": {0: True, 1: True}},
                {"inputs": {1: True}},
                {"inputs": {1: True}},
                {"inputs": {1: False}},
                {"inputs": {1: True}},
            ],
            [
                [False, False],
                [False, True],
                [False, False],
                [False, False],
                [True, True],
            ],
        )

    def test_end_family_rejects_operands_bad_nesting_and_post_end_instructions(self):
        for rungs in (
            [["END 1"]],
            [["ENDC"]],
            [["ENDCN"]],
            [["LD 1", "ENDC %M0"]],
            [["LD 1", "END", "ST %M0"]],
            [["LD 1", "AND( %M0", "ENDC", ")", "ST %M0"]],
            [["LD 1", "MPS", "ENDC", "MPP", "ST %M0"]],
            [["ENDT"]],
            [["STOP"]],
            [["%L0:", "END"]],
        ):
            with self.subTest(rungs=rungs), self.assertRaises(CompileError):
                validate(Program(rungs))

    def test_cpp_return_void_expression_remains_explicitly_outside_subset(self):
        source = self.work / "expression_return.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){return plc::output(0,true);}"
        )
        with self.assertRaisesRegex(CompileError, "bare return"):
            compile_source(source)

    def test_malformed_native_end_graph_stays_rejected_and_il_only_import_is_valid(
        self,
    ):
        for op, lines in (
            ("END", ["END"]),
            ("ENDC", ["LD %M0", "ENDC"]),
            ("ENDCN", ["LD %M0", "ENDCN"]),
        ):
            with self.subTest(op=op):
                rung = ET.fromstring(
                    "<RungEntity><LadderElements><LadderEntity><ElementType>End</ElementType><Row>0</Row><Column>10</Column><ChosenConnection>Left</ChosenConnection></LadderEntity></LadderElements><IsLadderSelected>true</IsLadderSelected></RungEntity>"
                )
                with self.assertRaises(CompileError):
                    check_graph(rung, lines)
                root = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp")
                pou = ET.SubElement(root.find(".//Pous"), "ProgramOrganizationUnits")
                ET.SubElement(pou, "SectionNumber").text = "1"
                rungs = ET.SubElement(pou, "Rungs")
                rung = ET.SubElement(rungs, "RungEntity")
                ET.SubElement(rung, "LadderElements")
                ET.SubElement(rung, "IsLadderSelected").text = "false"
                instructions = ET.SubElement(rung, "InstructionLines")
                for line in lines:
                    item = ET.SubElement(instructions, "InstructionLineEntity")
                    ET.SubElement(item, "InstructionLine").text = line
                path = self.work / "il_only.smbp"
                root.write(path, encoding="utf-8", xml_declaration=True)
                self.assertEqual(load_project(path).rungs, [lines])

    def test_cpp_scan_exit_label_overhead_is_not_reported_as_a_native_impossibility(
        self,
    ):
        source = self.work / "all_labels.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){"
            + "".join(f"label{i}:;" for i in range(64))
            + "return;}"
        )
        with self.assertRaisesRegex(CompileError, "scan exit.*compiler overhead"):
            compile_source(source)

    def test_scan_exit_lowering_label_overhead_fails_without_replacing_destination(
        self,
    ):
        program = Program(
            [[f"%L{i}:", "LD 1", "ST %M0"] for i in range(64)] + [["END"]]
        )
        validate(program)
        destination = self.work / "preserved.smbp"
        destination.write_bytes(b"preserve-existing")
        with self.assertRaisesRegex(CompileError, "scan exit.*compiler overhead"):
            write_project(
                program, Path(__file__).parent / "fixtures/synthetic.smbp", destination
            )
        self.assertEqual(destination.read_bytes(), b"preserve-existing")


if __name__ == "__main__":
    unittest.main()
