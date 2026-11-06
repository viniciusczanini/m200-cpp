"""Expression edge histories follow execution points, not scan samples."""

import copy
import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.ladder_lowering import normalize
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.cli import build_artifacts


class ExpressionEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        path = self.work / "source.cpp"
        path.write_text("#include <plc.hpp>\n" + body)
        return compile_source(path), path

    def equivalent(self, p, frames, expected, source=None):
        def rows(program):
            vm = Machine(program)
            return [vm.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]

        got = rows(p)
        self.assertEqual([r[: len(expected[0])] for r in got], expected)
        if source is not None:
            self.assertEqual(run_native(source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), got)
        rebuilt = compile_source(reverse)
        self.assertEqual(rows(rebuilt), got)
        before = copy.deepcopy(p.as_dict())
        normalized = normalize(p)
        self.assertEqual(rows(normalized), got)
        self.assertFalse(
            any(
                line.startswith(("RISING", "FALLING"))
                for rung in normalized.rungs
                for line in rung
            )
        )
        dest = self.work / "edges.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertEqual(rows(load_project(dest)), got)
        write_project(rebuilt, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertEqual(rows(load_project(dest)), got)
        self.assertEqual(p.as_dict(), before)
        return normalized

    def test_rising_and_falling_zero_have_independent_histories(self):
        p = Program(
            [["LD %I0.0", "RISING0", "ST %Q0.0"], ["LD %I0.0", "FALLING0", "ST %Q0.1"]]
        )
        self.equivalent(
            p,
            [{"inputs": {0: v}} for v in [0, 1, 1, 0, 0, 1]],
            [[0, 0], [1, 0], [0, 0], [0, 1], [0, 0], [1, 0]],
        )

    def test_expression_sees_current_write_while_contact_uses_scan_boundary(self):
        p = Program(
            [
                ["LD %I0.0", "ST %M0"],
                ["LD %M0", "RISING0", "ST %Q0.0"],
                ["LDR %M0", "ST %Q0.1"],
            ]
        )
        self.equivalent(
            p,
            [{"inputs": {0: v}} for v in [0, 1, 1, 0]],
            [[0, 0], [1, 0], [0, 1], [0, 0]],
        )

    def test_skipped_instruction_preserves_last_evaluated_value(self):
        p = Program(
            [
                ["LD 0", "ST %Q0.0", "ST %Q0.1"],
                ["LD %I0.1", "JMPC %L0"],
                ["LD %I0.0", "RISING0", "ST %Q0.0"],
                ["LD %I0.0", "FALLING0", "ST %Q0.1"],
                ["%L0:", "LD 0", "ST %M10"],
            ]
        )
        self.equivalent(
            p,
            [
                {"inputs": {0: a, 1: b}}
                for a, b in [(0, 0), (1, 1), (1, 0), (0, 1), (0, 0), (1, 1), (0, 0)]
            ],
            [[0, 0], [0, 0], [1, 0], [0, 0], [0, 1], [0, 0], [0, 0]],
        )

    def test_cpp_loops_advance_expression_history_on_each_call(self):
        p, source = self.compile("""void scan(){plc::i16 i=0;plc::i16 r=0;plc::i16 f=0;
while(i<3){if(plc::rising(0,plc::input(0))){r=plc::add_i16(r,1);}
if(plc::falling(0,plc::input(0))){f=plc::add_i16(f,1);}i=plc::add_i16(i,1);}
plc::output(0,r==1);plc::output(1,f==1);}""")
        self.equivalent(
            p,
            [{"inputs": {0: v}, "dt_ms": 0} for v in [0, 1, 1, 0, 1]],
            [[0, 0], [1, 0], [0, 0], [0, 1], [1, 0]],
            source,
        )

    def test_conditional_and_short_circuit_calls_hold_inactive_history(self):
        p, source = self.compile("""void scan(){bool a=false;
if(plc::input(1)){a=plc::rising(0,plc::input(0));}
bool b=plc::input(2)&&plc::falling(0,plc::input(0));plc::output(0,a);plc::output(1,b);}""")
        self.equivalent(
            p,
            [
                {"inputs": {0: a, 1: b, 2: c}}
                for a, b, c in [
                    (1, 0, 1),
                    (1, 1, 0),
                    (0, 0, 0),
                    (1, 1, 1),
                    (0, 1, 1),
                    (1, 1, 1),
                ]
            ],
            [[0, 0], [1, 0], [0, 0], [0, 0], [0, 1], [1, 0]],
            source,
        )

    def test_inactive_rhs_does_not_read_nan_or_set_index_error(self):
        p, source = (
            self.compile("""plc::WordMemory image{16};void scan(){plc::clear_index_error();
plc::write_dword(4,2143289344);plc::write_word(0,-32768);
if(plc::input(0)){bool x=plc::rising(0,plc::read_real(4)>0.0f);plc::output(0,x);}
bool k=plc::input(0)&&plc::falling(0,plc::read_word_indexed(8,0)>0);
plc::output(1,plc::system(20));plc::output(2,k);}""")
        )
        self.equivalent(p, [{}] * 2, [[0, 0, 0]] * 2, source)

    def test_nested_functions_evaluate_inner_before_outer(self):
        p, source = self.compile("""bool invert(bool v){return !v;}
void scan(){bool x=plc::rising(0,plc::falling(0,plc::input(0)));
plc::output(0,invert(!x));}""")
        self.equivalent(
            p,
            [{"inputs": {0: v}} for v in [1, 0, 0, 1, 0]],
            [[0], [1], [0], [0], [1]],
            source,
        )

    def test_stack_group_and_timer_keep_execution_point_and_sparse_ids(self):
        p = Program(
            [
                [
                    "LD %I0.0",
                    "MPS",
                    "RISING254",
                    "ST %Q0.0",
                    "MPP",
                    "FALLING254",
                    "ST %Q0.1",
                ],
                ["LD %I0.0", "AND( %I0.1", "RISING0", ")", "ST %Q0.2"],
                [
                    "BLK %TM0",
                    "LD %I0.0",
                    "FALLING0",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "ST %Q0.3",
                    "END_BLK",
                ],
            ],
            {0: Timer("TON", 0, 100)},
        )
        self.equivalent(
            p,
            [
                {"inputs": {0: a, 1: b}}
                for a, b in [(0, 0), (1, 1), (0, 1), (1, 1), (1, 0), (0, 1), (1, 1)]
            ],
            [
                [0, 0, 0, 0],
                [1, 0, 1, 0],
                [0, 1, 0, 1],
                [1, 0, 0, 0],
                [0, 0, 0, 0],
                [0, 1, 0, 1],
                [1, 0, 0, 0],
            ],
        )

    def test_homonymous_user_helper_remains_a_pure_helper(self):
        p, source = self.compile(
            "bool rising(bool v){return !v;}void scan(){plc::output(0,rising(plc::input(0)));}"
        )
        self.equivalent(p, [{}, {"inputs": {0: True}}], [[True], [False]], source)

    def test_all_255_identities_per_kind_keep_distinct_state(self):
        p = Program(
            [["LD %I0.0", f"RISING{i}", "ST %Q0.0"] for i in range(255)]
            + [["LD %I0.0", f"FALLING{i}", "ST %Q0.1"] for i in range(255)]
        )
        self.equivalent(
            p, [{"inputs": {0: v}} for v in [1, 0, 1]], [[1, 0], [0, 1], [1, 0]]
        )

    def test_output_alias_cannot_replace_input_history(self):
        p = Program(
            [
                ["LD %I0.0", "ST %M0", "ST %MW0:X0"],
                ["LD %M0", "RISING0", "ST %M0"],
                ["LD %M0", "ST %Q0.0"],
                ["LD %MW0:X0", "FALLING0", "ST %MW0:X0"],
                ["LD %MW0:X0", "ST %Q0.1"],
            ]
        )
        self.equivalent(
            p,
            [{"inputs": {0: v}} for v in [1, 1, 1, 0, 1]],
            [[1, 0], [0, 0], [0, 0], [0, 1], [1, 0]],
        )

    def test_accepted_function_whitespace_keeps_exportable_ir(self):
        p = Program(
            [
                ["LD %I0.0", "RISING0 \t", "ST %Q0.0"],
                ["LD %I0.0", "FALLING0 \t", "ST %Q0.1"],
            ]
        )
        self.equivalent(
            p, [{"inputs": {0: v}} for v in [1, 0, 1]], [[1, 0], [0, 1], [1, 0]]
        )

    def test_negated_comparison_before_function_has_supported_ladder(self):
        p = Program(
            [
                ["LD 1", "[%MW0:=0]"],
                ["LD %I0.0", "[%MW0:=1]"],
                ["LDN [%MW0>0]", "RISING0", "ST %Q0.0"],
                ["LDN [%MW0>0]", "FALLING0", "ST %Q0.1"],
            ]
        )
        self.equivalent(
            p,
            [{"inputs": {0: v}} for v in [0, 1, 0, 1]],
            [[1, 0], [0, 1], [1, 0], [0, 1]],
        )

    def test_artifact_report_includes_generated_project_expansion_resources(self):
        p, _ = self.compile("void scan(){plc::output(0,plc::rising(0,plc::input(0)));}")
        result = build_artifacts(
            p,
            self.work / "artifacts",
            Path(__file__).parent / "fixtures/synthetic.smbp",
        )
        self.assertEqual(result["resources"].get("rising_functions"), 1)
        self.assertEqual(result["resources"].get("falling_functions"), 0)
        actual = result.get("generated_project_resources", {})
        self.assertGreater(
            actual.get("memory_bits", 0), result["resources"]["memory_bits"]
        )
        self.assertEqual(actual.get("rising_functions"), 0)
        self.assertEqual(actual.get("falling_functions"), 0)

    def test_bad_indices_duplicate_sites_and_impure_helpers_fail(self):
        for op in [
            "RISING",
            "RISING00",
            "RISING255",
            "FALLING-1",
            "FALLING0 %M0",
            "RISING0 0",
            "FALLING01",
        ]:
            with self.subTest(op=op), self.assertRaises(CompileError):
                validate(Program([["LD %I0.0", op, "ST %Q0.0"]]))
        with self.assertRaises(CompileError):
            validate(Program([["RISING0", "ST %Q0.0"]]))
        with self.assertRaises(CompileError):
            validate(
                Program(
                    [
                        ["LD %I0.0", "RISING0", "ST %Q0.0"],
                        ["LD %I0.1", "RISING0", "ST %Q0.1"],
                    ]
                )
            )
        for body in [
            "void scan(){bool a=plc::rising(255,true);}",
            "void scan(){bool a=plc::falling(-1,true);}",
            "void scan(){bool a=plc::rising(0,true);bool b=plc::rising(0,false);}",
            "bool edge(bool v){return plc::rising(0,v);}void scan(){}",
            "void scan(){bool a=plc::rising(0,123);}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)


if __name__ == "__main__":
    unittest.main()
