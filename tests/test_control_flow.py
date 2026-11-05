"""Same-scan control flow, with native C++ and independent expected results."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class ControlFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "flow.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected):
        p = self.compile(body)
        validate(p)
        m = Machine(p)
        got = [m.step(f.get("inputs", {})) for f in frames]
        self.assertEqual([r[: len(expected[0])] for r in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), got)
        rebuilt = Machine(compile_source(reverse))
        self.assertEqual([rebuilt.step(f.get("inputs", {})) for f in frames], got)
        out = self.work / "flow.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", out)
        restored = Machine(load_project(out))
        self.assertEqual([restored.step(f.get("inputs", {})) for f in frames], got)
        return p, out

    def test_for_loop_finishes_all_iterations_in_one_scan(self):
        self.equivalent(
            """void scan(){plc::i16 sum=0;
for(plc::i16 i=0;i<5;i=plc::add_i16(i,1)){sum=plc::add_i16(sum,i);}
plc::output(0,sum==10);}""",
            [{}] * 3,
            [[True]] * 3,
        )

    def test_while_uses_runtime_condition_and_can_execute_zero_times(self):
        self.equivalent(
            """void scan(){plc::i16 left=0; plc::i16 sum=0;
if(plc::input(0)){left=7;}
while(left>0){sum=plc::add_i16(sum,left);left=plc::sub_i16(left,1);}
plc::output(0,sum==0);plc::output(1,sum==28);}""",
            [{}, {"inputs": {0: True}}, {}],
            [[True, False], [False, True], [True, False]],
        )

    def test_do_while_runs_once_and_continue_targets_its_condition(self):
        self.equivalent(
            """void scan(){plc::i16 i=0;plc::i16 sum=0;
do{i=plc::add_i16(i,1);if(i==2){continue;}if(i==4){break;}
sum=plc::add_i16(sum,i);}while(plc::input(0));
plc::output(0,i==1 && sum==1);plc::output(1,i==4 && sum==4);}""",
            [{}, {"inputs": {0: True}}, {}],
            [[True, False], [False, True], [True, False]],
        )

    def test_nested_break_and_continue_target_innermost_loop(self):
        self.equivalent(
            """void scan(){plc::i16 total=0;
for(plc::i16 i=0;i<3;i=plc::add_i16(i,1)){
 for(plc::i16 j=0;j<4;j=plc::add_i16(j,1)){
  if(j==1){continue;}if(i==1){break;}total=plc::add_i16(total,1);
 }}plc::output(0,total==6);}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_inactive_outer_branch_never_evaluates_loop_condition(self):
        self.equivalent(
            """void scan(){plc::i16 zero=0;
if(plc::input(0)){while(plc::div_i16(1,zero)>0){break;}}
plc::output(0,true);}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_for_without_condition_breaks_and_continue_runs_increment(self):
        self.equivalent(
            """void scan(){plc::i16 i=0;plc::i16 total=0;
for(;;i=plc::add_i16(i,1)){if(i>=5){break;}if(i==2){continue;}
total=plc::add_i16(total,i);}plc::output(0,i==5 && total==8);}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_source_goto_and_label_preserve_addressed_state(self):
        self.equivalent(
            """void scan(){plc::i16 n=0;
again: n=plc::add_i16(n,1);if(n<4){goto again;}
goto done;n=99;
done: plc::output(0,n==4);}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_goto_into_conditional_body_does_not_reapply_skipped_condition(self):
        self.equivalent(
            """void scan(){plc::i16 n=0;goto inside;
if(plc::input(0)){inside: n=plc::add_i16(n,1);}
plc::output(0,n==1);}""",
            [{}, {"inputs": {0: True}}],
            [[True], [True]],
        )

    def test_loop_reexecutes_local_array_initialization_and_timer_in_same_scan(self):
        self.equivalent(
            """plc::Ton timer{100};
void scan(){plc::i16 n=0;plc::i16 total=0;
while(n<3){plc::i16 a[2]={2};total=plc::add_i16(total,a[0]);
 a[0]=99;bool done=timer.update(plc::input(0));
 plc::output(1,done);n=plc::add_i16(n,1);}
plc::output(0,total==6);}""",
            [{"inputs": {0: True}}] * 12,
            [[True, False]] * 10 + [[True, True]] * 2,
        )

    def test_native_jmp_jmpcn_execute_and_reverse_without_original_source(self):
        p = Program(
            [
                ["%L7:", "LD [%MW0<4]", "JMPCN %L2"],
                ["LD 1", "[%MW0:=%MW0+1]"],
                ["JMP %L7"],
                ["%L2:", "LD [%MW0=4]", "ST %Q0.0"],
            ]
        )
        m = Machine(p)
        self.assertTrue(m.step()[0])
        self.assertEqual(m.words[0], 4)
        path = self.work / "from_native.cpp"
        path.write_text(to_cpp(p))
        self.assertTrue(run_native(path, [{}])[0][0])
        self.assertTrue(Machine(compile_source(path)).step()[0])

    def test_native_inc_dec_in_loop_preserve_accumulator_and_word_width(self):
        p = Program(
            [
                ["LD 1", "[%MW0:=5]"],
                ["%L0:", "LD [%MW0>0]", "[DEC %MW0]", "[INC %MD2]", "JMPC %L0"],
                ["LD [%MD2=5]", "ST %Q0.0"],
            ]
        )
        m = Machine(p)
        self.assertTrue(m.step()[0])
        self.assertEqual(m.words[:4], [0, 0, 5, 0])
        path = self.work / "inc_dec.cpp"
        path.write_text(to_cpp(p))
        self.assertTrue(run_native(path, [{}])[0][0])
        self.assertTrue(Machine(compile_source(path)).step()[0])

    def test_original_function_whitespace_is_accepted_without_joining_tokens(self):
        p = Program(
            [
                ["LD 1", "[ %MW10 := 12 ]", "[ %MW10 := SHR ( %MW10 , 1 ) ]"],
                ["LD [ %MW10 = 6 ]", "ST %Q0.0"],
            ]
        )
        self.assertTrue(Machine(p).step()[0])
        for line in (
            "[ %MW10 := S HR ( %MW10 , 1 ) ]",
            "[ %MW10 := SHR ( %MW1 0 , 1 ) ]",
        ):
            with self.subTest(line=line), self.assertRaises(CompileError):
                validate(Program([["LD 1", line]]))

    def test_infinite_loop_has_explicit_local_execution_limit(self):
        p = Program([["%L0:", "LD 1", "JMPC %L0"]])
        m = Machine(p, instruction_limit=50)
        with self.assertRaisesRegex(CompileError, "execution limit"):
            m.step()
        self.assertEqual(m.now, 0)

    def test_invalid_labels_targets_and_jump_placement_are_rejected(self):
        for rungs in (
            [["LD 1", "JMPC %L0"]],
            [["%L0:", "LD 1", "ST %M0"], ["%L0:", "LD 1", "ST %M1"]],
            [["%L64:", "LD 1", "JMPC %L64"]],
            [["%L0:"]],
            [["%L0:", "LD 1", "JMPC %L0", "ST %M0"]],
            [["%L0:", "LD 1", "JMPC %L0:"]],
            [["%L0:", "JMP %L1"], ["%L1:", "LD 1", "ST %M0"]],
        ):
            with self.subTest(rungs=rungs), self.assertRaises(CompileError):
                validate(Program(rungs))

    def test_xml_label_field_must_match_actual_instruction_label(self):
        p, out = self.equivalent(
            "void scan(){plc::i16 n=0;while(n<2){n=plc::add_i16(n,1);}plc::output(0,n==2);}",
            [{}],
            [[True]],
        )
        root = ET.parse(out)
        labels = root.findall(".//RungEntity/Label")
        label = next(n for n in labels if n.text)
        label.text = "%L63" if label.text != "%L63" else "%L62"
        root.write(out, encoding="utf-8", xml_declaration=True)
        with self.assertRaisesRegex(CompileError, "label"):
            load_project(out)


if __name__ == "__main__":
    unittest.main()
