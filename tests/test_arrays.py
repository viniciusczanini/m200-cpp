"""Array behavior: execution references are compiled C++ and hand-derived outputs."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class ArrayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "arrays.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected):
        program = self.compile(body)
        validate(program)
        machine = Machine(program)
        got = [machine.step(f.get("inputs", {})) for f in frames]
        self.assertEqual([row[: len(expected[0])] for row in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(program))
        self.assertEqual(run_native(reverse, frames), got)
        rebuilt = Machine(compile_source(reverse))
        self.assertEqual([rebuilt.step(f.get("inputs", {})) for f in frames], got)
        template = Path(__file__).parent / "fixtures/synthetic.smbp"
        destination = self.work / "arrays.smbp"
        write_project(program, template, destination)
        restored = Machine(load_project(destination))
        self.assertEqual([restored.step(f.get("inputs", {})) for f in frames], got)
        return machine

    def test_global_arrays_persist_and_partial_initializers_zero_fill(self):
        self.equivalent(
            """bool bits[3]={true};
plc::i16 values[3]={2,5};
void scan(){
  bits[2]=bits[0]; bits[0]=!bits[0];
  values[2]=plc::add_i16(values[2],values[0]);
  plc::output(0,bits[2]); plc::output(1,bits[1]);
  plc::output(2,values[2]==4 && values[1]==5);
}""",
            [{}] * 4,
            [
                [True, False, False],
                [False, False, True],
                [True, False, False],
                [False, False, False],
            ],
        )

    def test_local_arrays_reset_and_runtime_initializers_evaluate_in_order(self):
        self.equivalent(
            """void scan(){
  plc::i32 data[3]={plc::read_dword(0),7};
  bool bits[2]={plc::input(0)};
  plc::write_dword(0,plc::add_i32(data[0],1));
  plc::output(0,data[0]==1 && data[1]==7 && data[2]==0);
  plc::output(1,bits[0] && !bits[1]);
  data[2]=99; bits[1]=true;
}""",
            [{}, {"inputs": {0: True}}, {}],
            [[False, False], [True, True], [False, False]],
        )

    def test_real_and_dword_elements_are_independent_and_writes_are_guarded(self):
        self.equivalent(
            """plc::f32 real[2]={1.5f,2.5f};
plc::i32 wide[2]={65537,-2147483647};
void scan(){
  if(plc::input(0)){real[0]=real[1]; wide[1]=wide[0];}
  plc::output(0,real[0]==2.5f && real[1]==2.5f);
  plc::output(1,wide[0]==65537 && wide[1]==65537);
}""",
            [{}, {"inputs": {0: True}}, {}],
            [[False, False], [True, True], [True, True]],
        )

    def test_global_uninitialized_and_local_empty_braces_are_zero(self):
        self.equivalent(
            """bool global[2]; plc::i32 words[2];
void scan(){bool local[2]={};plc::f32 reals[2]={};
  plc::output(0,!global[0] && !global[1] && words[0]==0 && words[1]==0);
  plc::output(1,!local[1] && reals[0]==0.0f && reals[1]==0.0f);
}""",
            [{}] * 2,
            [[True, True], [True, True]],
        )

    def test_initializer_can_read_preceding_element(self):
        self.equivalent(
            """void scan(){plc::i16 a[3]={2,plc::add_i16(a[0],3),a[1]};
plc::output(0,a[0]==2 && a[1]==5 && a[2]==5);}""",
            [{}] * 2,
            [[True], [True]],
        )

    def test_invalid_or_unimplemented_arrays_are_explicitly_rejected(self):
        for body in (
            "void scan(){bool a[2]={};plc::output(0,a[2]);}",
            "void scan(){bool a[2]={};a[-1]=true;}",
            "void scan(){plc::i16 a[2];plc::output(0,a[0]==0);}",
            "bool a[0]={}; void scan(){}",
            "bool a[1025]={};void scan(){}",
            "plc::i32 a[4001]={};void scan(){}",
            "void scan(){bool a[2]={};bool *p=a;plc::output(0,p[0]);}",
            "void scan(){static bool a[2]={};}",
        ):
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)

    def test_extern_array_is_not_fabricated_or_reinitialized(self):
        for body in (
            "extern bool a[2];void scan(){plc::output(0,a[0]);}",
            "bool a[2]={true};extern bool a[2];void scan(){plc::output(0,a[0]);}",
        ):
            with (
                self.subTest(body=body),
                self.assertRaisesRegex(CompileError, "extern"),
            ):
                self.compile(body)


if __name__ == "__main__":
    unittest.main()
