"""Integer flag policies, instruction order and recoverable overflow paths."""

import json
import tempfile
import unittest
from pathlib import Path

from m200.model import Program, CompileError
from m200.il import Machine, validate
from m200.numeric import evaluate

ROOT = Path(__file__).resolve().parents[1]


class IntegerFlagTests(unittest.TestCase):
    def state(self):
        from m200.arithmetic import ArithmeticState

        return ArithmeticState()

    def equivalent(self, p, frames, expected, source=None):
        from m200.frontend import compile_source
        from m200.ladder_lowering import normalize
        from m200.native import run_native
        from m200.project import load_project, write_project
        from m200.reverse import to_cpp

        def rows(candidate):
            vm = Machine(candidate)
            return [vm.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]

        got = rows(p)
        self.assertEqual([row[: len(expected[0])] for row in got], expected)
        self.assertEqual(
            rows(Program.from_dict(json.loads(json.dumps(p.as_dict())))), got
        )
        self.assertEqual(rows(normalize(p)), got)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.cpp"
            if source is not None:
                path.write_text("#include <plc.hpp>\n" + source)
                self.assertEqual(run_native(path, frames), got)
            path.write_text(to_cpp(p))
            self.assertEqual(run_native(path, frames), got)
            rebuilt = compile_source(path)
            self.assertEqual(rows(rebuilt), got)
            dest = Path(folder) / "flags.smbp"
            for candidate in [p, rebuilt]:
                write_project(candidate, ROOT / "tests/fixtures/synthetic.smbp", dest)
                self.assertEqual(rows(load_project(dest)), got)
        return got

    def compile(self, source):
        from m200.frontend import compile_source

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.cpp"
            path.write_text("#include <plc.hpp>\n" + source)
            return compile_source(path)

    def test_published_saturation_example_preserves_raw_result_and_error(self):
        p = Program(
            [
                ["LD 1", "ST %M0", "[%MW1:=23241]", "[%MW2:=21853]"],
                ["LD %M0", "[%MW0:=%MW1+%MW2]"],
                ["LDN %S18", "[%MW10:=%MW0]"],
                ["LD %S18", "[%MW10:=32767]"],
                ["LD [%MW0=-20442]", "ST %Q0.0"],
                ["LD [%MW10=32767]", "ST %Q0.1"],
                ["LD %S18", "ST %Q0.2"],
            ]
        )
        self.equivalent(p, [{}], [[1, 1, 1]])

    def test_integer_alu_overflow_is_modular_and_sticky_in_context(self):
        for kind, width in [("i16", 16), ("i32", 32)]:
            low = -(1 << (width - 1))
            high = (1 << (width - 1)) - 1
            for name, function in [
                ("add", lambda a, b: a + b),
                ("sub", lambda a, b: a - b),
                ("mul", lambda a, b: a * b),
            ]:
                for a, b in [
                    (high, 1),
                    (low, 1),
                    (low, -1),
                    (high, 2),
                    (-1, -1),
                    (0, 0),
                ]:
                    with self.subTest(kind=kind, name=name, a=a, b=b):
                        state = self.state()
                        raw = function(a, b)
                        expected = int.from_bytes(
                            (raw % (1 << width)).to_bytes(width // 8, "little"),
                            "little",
                            signed=True,
                        )
                        self.assertEqual(
                            evaluate(name + "_" + kind, [a, b], kind, flags=state),
                            expected,
                        )
                        self.assertEqual(state.overflow, not low <= raw <= high)
                        previous = state.overflow
                        evaluate("add_" + kind, [0, 0], kind, flags=state)
                        self.assertEqual(state.overflow, previous)

    def test_minimum_division_remainder_and_abs_follow_explicit_local_policy(self):
        for kind, low in [("i16", -32768), ("i32", -2147483648)]:
            for name, expected in [("div", low), ("rem", 0)]:
                state = self.state()
                self.assertEqual(
                    evaluate(name + "_" + kind, [low, -1], kind, flags=state), expected
                )
                self.assertTrue(state.overflow)
        state = self.state()
        self.assertEqual(
            evaluate("abs_i32", [-2147483648], "i32", flags=state), -2147483648
        )
        self.assertTrue(state.overflow)

    def test_every_shift_distance_updates_last_bit_including_zero(self):
        for kind, width in [("i16", 16), ("i32", 32)]:
            for stem in ["shl", "shr", "rol", "ror"]:
                for n in range(1, width + 1):
                    for value in [
                        0,
                        1,
                        -1,
                        -2,
                        -(1 << (width - 1)),
                        (1 << (width - 1)) - 1,
                    ]:
                        state = self.state()
                        state.carry = True
                        state.overflow = True
                        evaluate(stem + "_" + kind, [value, n], kind, flags=state)
                        raw = value % (1 << width)
                        bit = width - n if stem in ["shl", "rol"] else n - 1
                        self.assertEqual(state.carry, bool(raw & (1 << bit)))
                        self.assertTrue(state.overflow)

    def test_flags_survive_scans_success_and_conditional_clears(self):
        p = Program(
            [
                ["LD %S13", "[%MW0:=32767]", "[%MW2:=-32768]"],
                ["LD 1", "[%MW0:=%MW0+1]"],
                ["LD %I0.0", "R %S18"],
                ["LD %I0.2", "[%MW2:=0]"],
                ["LD %I0.1", "[%MW1:=SHL(%MW2,1)]"],
                ["LD %S17", "ST %Q0.0"],
                ["LD %S18", "ST %Q0.1"],
            ]
        )
        frames = [{"inputs": v} for v in [{1: True}, {}, {0: True}, {1: True, 2: True}]]
        self.equivalent(p, frames, [[1, 1], [1, 1], [1, 0], [0, 0]])

    def test_copy_bitwise_and_float_success_do_not_clear_integer_flags(self):
        state = self.state()
        state.carry = state.overflow = True
        for name, args, kind in [
            ("copy", [1], "i16"),
            ("and_i16", [15, 3], "i16"),
            ("low_word", [2147483647], "i16"),
            ("add_f32", [1.0, 2.0], "f32"),
            ("int_to_real", [3], "f32"),
        ]:
            evaluate(name, args, kind, flags=state)
            self.assertTrue(state.carry and state.overflow)

    def test_indeterminate_integer_fault_sets_error_but_does_not_fabricate_result(self):
        for setup, operation in [
            (["[%MW0:=7]", "[%MW1:=0]"], "[%MW10:=%MW0/%MW1]"),
            (["[%MW0:=-1]"], "[%MW10:=SQRT(%MW0)]"),
        ]:
            vm = Machine(
                Program([["LD 1"] + setup + ["[%MW10:=123]"], ["LD 1", operation]])
            )
            with self.assertRaisesRegex(CompileError, "arithmetic"):
                vm.step()
            self.assertTrue(vm.arithmetic.overflow)
            self.assertEqual(vm.words[10], 123)

    def test_only_reset_writes_arithmetic_flags(self):
        for flag in [17, 18]:
            validate(Program([[f"LD %S{flag}", f"R %S{flag}"]]))
            for op in ["ST", "STN", "S"]:
                with self.subTest(flag=flag, op=op), self.assertRaises(CompileError):
                    validate(Program([["LD 1", f"{op} %S{flag}"]]))

    def test_cpp_overflow_literals_and_snapshots_are_real_runtime_effects(self):
        source = """void scan(){
plc::clear_arithmetic_error();plc::clear_shift_carry();
bool before=plc::system(18);plc::i16 n=plc::add_i16(32767,1);
bool captured=plc::system(18);plc::clear_arithmetic_error();
plc::i16 a=plc::shl_i16(-32768,1);bool left=plc::system(17);
plc::i16 b=plc::shr_i16(2,1);bool right=plc::system(17);
plc::output(0,!before&&captured&&!plc::system(18));
plc::output(1,n==-32768&&a==0&&b==1);plc::output(2,left&&!right);
}"""
        self.equivalent(self.compile(source), [{}], [[1, 1, 1]], source)

    def test_cpp_inactive_and_short_circuit_numeric_calls_leave_flags_unchanged(self):
        source = """void scan(){plc::clear_arithmetic_error();
bool a=plc::system(18)&&plc::add_i16(32767,1)<0;
bool b=!plc::system(18)||plc::add_i16(32767,1)<0;
if(plc::input(0)){plc::i32 n=plc::mul_i32(2147483647,2);plc::output(1,n==-2);}
plc::output(0,!a&&b);plc::output(2,plc::system(18));}"""
        self.equivalent(
            self.compile(source),
            [{"inputs": {0: False}}, {"inputs": {0: True}}],
            [[1, 0, 0], [1, 1, 1]],
            source,
        )

    def test_cpp_flag_read_precedes_arithmetic_on_comparison_right(self):
        source = """void scan(){plc::clear_arithmetic_error();
bool equal=plc::system(18)==(plc::add_i16(32767,1)==-32768);
plc::output(0,!equal&&plc::system(18));}"""
        self.equivalent(self.compile(source), [{}], [[1]], source)

    def test_counter_graph_reset_of_arithmetic_flag_preserves_snapshot(self):
        from m200.counters import Counter

        p = Program(
            [
                ["LD 1", "[%MW0:=32767]", "[%MW0:=%MW0+1]"],
                [
                    "BLK %C0",
                    "LD %S18",
                    "CU",
                    "OUT_BLK",
                    "LD D",
                    "MPS",
                    "R %S18",
                    "MPP",
                    "ST %Q0.0",
                    "END_BLK",
                ],
                ["LD %S18", "ST %Q0.1"],
            ],
            counters={0: Counter(1)},
        )
        self.equivalent(p, [{}], [[1, 0]])

    def test_literal_division_remainder_and_abs_overflows_compile_with_flags(self):
        source = """void scan(){plc::clear_arithmetic_error();
plc::i32 a=plc::div_i32(-2147483648,-1);
plc::i16 b=plc::rem_i16(-32768,-1);
plc::i32 c=plc::abs_i32(-2147483648);
plc::output(0,a==-2147483648&&b==0&&c==-2147483648&&plc::system(18));}"""
        self.equivalent(self.compile(source), [{}], [[1]], source)

    def test_unused_result_still_sets_error_and_helper_calls_keep_flag_effect(self):
        source = """bool shifted(bool enabled){return enabled&&plc::shl_i16(-32768,1)==0;}
void scan(){plc::clear_arithmetic_error();plc::clear_shift_carry();
plc::i16 unused=plc::add_i16(32767,1);
bool a=shifted(plc::input(0));bool before=plc::system(17);
plc::clear_shift_carry();bool b=shifted(false);
plc::output(0,plc::system(18));plc::output(1,a&&before&&!b&&!plc::system(17));}"""
        self.equivalent(
            self.compile(source),
            [{"inputs": {0: False}}, {"inputs": {0: True}}],
            [[1, 0], [1, 1]],
            source,
        )

    def test_loop_can_detect_and_recover_overflow_inside_same_scan(self):
        source = """void scan(){plc::clear_arithmetic_error();plc::i16 x=32766;plc::i16 count=0;
while(!plc::system(18)){x=plc::add_i16(x,1);count=plc::add_i16(count,1);}
bool error=plc::system(18);if(error){x=32767;plc::clear_arithmetic_error();}
plc::output(0,error&&x==32767&&count==2&&!plc::system(18));}"""
        self.equivalent(self.compile(source), [{}], [[1]], source)

    def test_short_circuit_captures_carry_before_rhs_changes_it(self):
        source = """void scan(){plc::clear_shift_carry();
plc::i16 seed=plc::shl_i16(-32768,1);
bool a=plc::system(17)&&(plc::shl_i16(0,1)==0);
bool b=plc::system(17)||(plc::shl_i16(-32768,1)!=0);
plc::output(0,a&&!b&&plc::system(17));}"""
        self.equivalent(self.compile(source), [{}], [[1]], source)

    def test_arithmetic_and_index_error_flags_clear_independently(self):
        source = """plc::WordMemory words{20};void scan(){
plc::clear_arithmetic_error();plc::clear_index_error();plc::write_word(0,10);
plc::i16 index=plc::add_i16(32767,1);plc::write_word(19,index);
plc::i16 value=plc::read_word_indexed(0,19);bool both=plc::system(18)&&plc::system(20);
plc::clear_arithmetic_error();plc::output(0,both&&value==10&&plc::system(20)&&!plc::system(18));
plc::clear_index_error();plc::output(1,!plc::system(20)&&!plc::system(18));}"""
        self.equivalent(self.compile(source), [{}], [[1, 1]], source)

    def test_raw_counter_graph_accepts_reset_of_arithmetic_flag(self):
        from test_counter_graphs import node
        from m200.counter_xml import check_graph

        source = [
            "BLK %C0",
            "LD %S18",
            "CU",
            "OUT_BLK",
            "LD D",
            "MPS",
            "R %S18",
            "MPP",
            "ST %Q0.0",
            "END_BLK",
        ]
        entities = [
            ("Counter", "%C0", 0, 2, "Left"),
            ("NormalContact", "%S18", 2, 0, "Left, Right"),
            ("Line", "", 2, 1, "Left, Right"),
        ]
        entities += [("Line", "", 1, c, "Left, Right") for c in range(4, 9)]
        entities += [
            ("Line", "", 1, 9, "Down, Left, Right"),
            ("ResetCoil", "%S18", 1, 10, "Left"),
            ("VerticalLine", "", 2, 9, "Up, Right"),
            ("Coil", "%Q0.0", 2, 10, "Left"),
        ]
        check_graph(node(source, entities), source)
