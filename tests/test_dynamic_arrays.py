"""Computed array indices: source C++ is the reference only in its valid domain."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class DynamicArrayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "dynamic_arrays.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(
        self, body, frames, expected, reverse=True, bit_profile_pending=False
    ):
        program = self.compile(body)
        machine = Machine(program)
        got = [machine.step(f.get("inputs", {})) for f in frames]
        self.assertEqual([v[: len(expected[0])] for v in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        if reverse:
            path = self.work / "reverse.cpp"
            path.write_text(to_cpp(program))
            self.assertEqual(run_native(path, frames), got)
            rebuilt = Machine(compile_source(path))
            self.assertEqual([rebuilt.step(f.get("inputs", {})) for f in frames], got)
        destination = self.work / "dynamic_arrays.smbp"
        if bit_profile_pending:
            with self.assertRaisesRegex(CompileError, "indexed.bit.*unverified"):
                write_project(
                    program,
                    Path(__file__).parent / "fixtures/synthetic.smbp",
                    destination,
                )
            self.assertFalse(destination.exists())
            return program
        write_project(
            program, Path(__file__).parent / "fixtures/synthetic.smbp", destination
        )
        restored = Machine(load_project(destination))
        self.assertEqual([restored.step(f.get("inputs", {})) for f in frames], got)
        return program

    def test_global_word_array_is_updated_in_runtime_loop(self):
        self.equivalent(
            """plc::i16 a[5]={1,2,3};
void scan(){for(plc::i16 i=0;i<5;i=plc::add_i16(i,1)){
a[i]=plc::add_i16(a[i],1);}
plc::output(0,a[0]==2 && a[4]==1);
plc::output(1,a[0]==3 && a[4]==2);
plc::output(2,!plc::system(20));}""",
            [{}] * 3,
            [[True, False, True], [False, True, True], [False, False, True]],
        )

    def test_i32_indices_and_two_word_elements_have_correct_stride(self):
        self.equivalent(
            """void scan(){plc::i32 a[3]={65538,-1};plc::i32 i=0;
plc::i32 total=0;while(i<3){total=plc::add_i32(total,a[i]);
a[i]=plc::add_i32(a[i],10);i=plc::add_i32(i,1);}
plc::output(0,total==65537 && a[0]==65548 && a[1]==9 && a[2]==10);
plc::output(1,!plc::system(20));}""",
            [{}] * 2,
            [[True, True]] * 2,
        )

    def test_local_real_array_reinitializes_each_iteration(self):
        self.equivalent(
            """void scan(){plc::i16 i=0;plc::f32 sum=0.0f;
while(i<3){plc::f32 a[3]={1.5f,2.5f};sum=plc::add_f32(sum,a[i]);
a[i]=99.0f;i=plc::add_i16(i,1);}
plc::output(0,sum==4.0f && !plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_rhs_read_sets_flag_before_boolean_lvalue_index_is_evaluated(self):
        self.equivalent(
            """plc::WordMemory image{16};plc::i16 a[2]={5,7};
void scan(){plc::clear_index_error();plc::write_word(0,-32768);
plc::write_word(8,42);a[plc::system(20)]=plc::read_word_indexed(8,0);
plc::output(0,a[0]==5 && a[1]==42 && plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_inactive_array_access_never_evaluates_division_or_index(self):
        self.equivalent(
            """void scan(){plc::clear_index_error();plc::i16 zero=0;
if(plc::input(0)){plc::f32 a[3]={1.5f};
plc::i16 index=plc::div_i16(1,zero);plc::f32 value=a[index];}
plc::output(0,!plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_large_dynamic_group_stays_inside_word_bank(self):
        program = self.equivalent(
            """plc::i32 big[2100]={1};void scan(){plc::i16 i=2099;
big[i]=plc::add_i32(big[i],1);plc::output(0,big[0]==1 && big[2098]==0);
plc::output(1,big[i]==2);}""",
            [{}] * 3,
            [[True, False], [True, True], [True, False]],
            reverse=False,
        )
        positions = {
            name: int(code[3:])
            for code, name in program.symbols.items()
            if name.startswith("big_")
        }
        self.assertEqual(positions["big_2099"] - positions["big_0"], 4198)
        self.assertLessEqual(positions["big_2099"] + 2, 8000)

    def test_runtime_invalid_indices_have_explicit_model_fallback(self):
        # Built-in C++ [] is undefined here: do not execute the original on host.
        for index in (-1, 3, 32767, 2147483647, -2147483648):
            with self.subTest(index=index):
                p = self.compile(f"""plc::i32 a[3]={{42,7,9}};plc::i32 index={index};
void scan(){{plc::clear_index_error();plc::i32 value=a[index];
plc::output(0,value==42 && plc::system(20));}}""")
                self.assertTrue(Machine(p).step()[0])
                path = self.work / "fallback.cpp"
                path.write_text(to_cpp(p))
                self.assertTrue(run_native(path, [{}])[0][0])

    def test_literal_invalid_index_remains_compile_error(self):
        for index in (-1, 3):
            with self.subTest(index=index), self.assertRaises(CompileError):
                self.compile(
                    f"void scan(){{plc::i16 a[3]={{}};plc::output(0,a[{index}]==0);}}"
                )

    def test_global_boolean_array_uses_runtime_index_and_preserves_state(self):
        self.equivalent(
            """bool a[4]={true,false,true};void scan(){
for(plc::i16 i=0;i<4;i=plc::add_i16(i,1)){a[i]=!a[i];}
plc::output(0,!a[0] && a[1] && !a[2] && a[3]);
plc::output(1,!plc::system(20));}""",
            [{}] * 3,
            [[True, True], [False, True], [True, True]],
            bit_profile_pending=True,
        )

    def test_boolean_false_stores_and_local_partial_initializers(self):
        self.equivalent(
            """void scan(){bool a[4]={plc::input(0),true};plc::i16 count=0;
for(plc::i32 i=0;i<4;i=plc::add_i32(i,1)){
if(a[i]){count=plc::add_i16(count,1);}a[i]=false;}
plc::output(0,count==1);plc::output(1,count==2);
plc::output(2,!a[0] && !a[1] && !a[2] && !a[3]);}""",
            [{}, {"inputs": {0: True}}, {}],
            [[True, False, True], [False, True, True], [True, False, True]],
            bit_profile_pending=True,
        )

    def test_boolean_rhs_is_captured_before_indexed_lvalue_raises_flag(self):
        self.equivalent(
            """plc::WordMemory image{16};bool a[2]={false,true};void scan(){
plc::clear_index_error();plc::write_word(0,-32768);plc::write_word(8,1);
a[plc::read_word_indexed(8,0)]=plc::system(20);
plc::output(0,!a[1] && plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
            bit_profile_pending=True,
        )

    def test_inactive_boolean_index_never_sets_error(self):
        self.equivalent(
            """void scan(){plc::clear_index_error();bool a[2]={true};
plc::i32 bad=2147483647;
if(plc::input(0)){bool x=a[bad];}
bool c=false && a[bad];bool d=true || a[bad];
plc::output(0,!c && d && !plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
            bit_profile_pending=True,
        )

    def test_runtime_invalid_boolean_index_uses_model_fallback(self):
        p = self.compile("""bool a[3]={true};plc::i32 i=-1;
void scan(){plc::clear_index_error();bool value=a[i];
plc::output(0,value && plc::system(20));}""")
        self.assertTrue(Machine(p).step()[0])
        source = self.work / "bool_fallback.cpp"
        source.write_text(to_cpp(p))
        self.assertTrue(run_native(source, [{}])[0][0])

    def test_large_boolean_group_is_contiguous_and_reverses(self):
        p = self.equivalent(
            """bool large[900]={true};void scan(){plc::i16 i=899;
large[i]=!large[i];plc::output(0,large[0] && large[i]);}""",
            [{}] * 3,
            [[True], [False], [True]],
            bit_profile_pending=True,
        )
        positions = {
            name: int(code[2:])
            for code, name in p.symbols.items()
            if name.startswith("large_")
        }
        self.assertEqual(positions["large_899"] - positions["large_0"], 899)
        self.assertLess(positions["large_899"], 1024)

    def test_local_group_partial_false_store_preserves_other_members(self):
        self.equivalent(
            """void scan(){bool a[5]={true,true,true,true,true};
plc::i16 index=2;a[index]=false;bool scratch=!plc::input(0);
plc::output(0,a[0] && a[1] && !a[index] && a[3] && a[4]);
plc::output(1,scratch);}""",
            [{}, {"inputs": {0: True}}],
            [[True, True], [True, False]],
            bit_profile_pending=True,
        )

    def test_initializers_read_previous_members_and_shadowed_arrays(self):
        self.equivalent(
            """plc::i16 a[3]={2,3};void scan(){plc::i16 index=1;
plc::i32 b[3]={65538,plc::add_i32(b[0],1),plc::add_i32(b[1],1)};
{plc::i16 a[3]={9,a[0],7};plc::output(0,a[index]==9);}
plc::output(1,a[index]==3 && b[index]==65539 && b[2]==65540);}""",
            [{}] * 2,
            [[True, True]] * 2,
        )

    def test_groups_do_not_overlap_explicit_aliases_or_modbus_buffer(self):
        p = self.equivalent(
            """plc::ReadVar r{plc::Link::Ethernet,1,10,
plc::Object::HoldingWords,0,125,4000};
void scan(){plc::write_dword(3998,65538);plc::i32 a[9]={11,12};
plc::f32 b[9]={1.5f,2.5f};plc::i16 i=1;
a[i]=plc::add_i32(a[i],2);b[i]=plc::add_f32(b[i],0.5f);
plc::output(0,a[0]==11 && a[i]==14 && b[0]==1.5f && b[i]==3.0f);
plc::output(1,plc::read_dword(3998)==65538);}""",
            [{}] * 2,
            [[True, True]] * 2,
        )
        for code in p.symbols:
            if code.startswith(("%MW", "%MD", "%MF")):
                width = 1 if code.startswith("%MW") else 2
                self.assertFalse(
                    set(range(int(code[3:]), int(code[3:]) + width))
                    & set(range(3998, 4125))
                )


if __name__ == "__main__":
    unittest.main()
