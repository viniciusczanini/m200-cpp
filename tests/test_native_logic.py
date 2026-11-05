"""Native boolean snapshots and equivalent canonical Ladder, never embedded C++."""

import copy
import json
import xml.etree.ElementTree as ET
import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project, check_graph, graphics
from m200.reverse import to_cpp


class NativeLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def equivalent(self, program, frames, expected, xml=True):
        validate(program)

        def rows(p):
            m = Machine(p)
            return [m.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]

        actual = rows(program)
        self.assertEqual([row[: len(expected[0])] for row in actual], expected)
        source = self.work / "reverse.cpp"
        source.write_text(to_cpp(program))
        self.assertEqual(run_native(source, frames), actual)
        rebuilt = compile_source(source)
        self.assertEqual(rows(rebuilt), actual)
        if xml:
            snapshot = copy.deepcopy(program.as_dict())
            dest = self.work / "native.smbp"
            write_project(
                program, Path(__file__).parent / "fixtures/synthetic.smbp", dest
            )
            self.assertEqual(rows(load_project(dest)), actual)
            self.assertEqual(program.as_dict(), snapshot)
        return actual

    def test_store_not_preserves_accumulator_and_not_inverts_it(self):
        self.equivalent(
            Program(
                [
                    ["LD %I0.0", "STN %M0", "ST %Q0.0", "N", "ST %Q0.1"],
                    ["LD %M0", "ST %Q0.2"],
                ]
            ),
            [{"inputs": {0: v}} for v in (False, True, False)],
            [[False, True, True], [True, False, False], [False, True, True]],
        )

    def test_stack_captures_value_before_source_is_overwritten(self):
        p = Program(
            [
                ["LD 1", "ST %M0"],
                [
                    "LD %M0",
                    "MPS",
                    "LD 0",
                    "ST %M0",
                    "MRD",
                    "ST %Q0.0",
                    "N",
                    "ST %Q0.1",
                    "MPP",
                    "ST %Q0.2",
                ],
                ["LD %M0", "ST %Q0.3"],
            ]
        )
        self.equivalent(p, [{}] * 3, [[True, False, True, False]] * 3)

    def test_nested_stack_uses_independent_lifo_values(self):
        p = Program(
            [
                [
                    "LD %I0.0",
                    "MPS",
                    "N",
                    "MPS",
                    "AND %I0.1",
                    "ST %Q0.0",
                    "MPP",
                    "ST %Q0.1",
                    "MPP",
                    "ST %Q0.2",
                ]
            ]
        )
        frames = [{"inputs": {0: bool(n & 1), 1: bool(n & 2)}} for n in range(4)]
        self.equivalent(
            p,
            frames,
            [
                [(not bool(n & 1)) and bool(n & 2), not bool(n & 1), bool(n & 1)]
                for n in range(4)
            ],
        )

    def test_parentheses_combine_completed_inner_expression(self):
        p = Program(
            [
                [
                    "LD %I0.0",
                    "AND( %I0.1",
                    "OR( %I0.2",
                    "AND %I0.3",
                    ")",
                    ")",
                    "ST %Q0.0",
                ],
                ["LD %I0.0", "OR( %I0.1", "N", ")", "ST %Q0.1"],
            ]
        )

        frames = [
            {"inputs": {b: bool(n & (1 << b)) for b in range(4)}} for n in range(16)
        ]
        self.equivalent(
            p,
            frames,
            [
                [
                    bool(n & 1) and (bool(n & 2) or (bool(n & 4) and bool(n & 8))),
                    bool(n & 1) or not bool(n & 2),
                ]
                for n in range(16)
            ],
        )

    def test_comparison_values_can_be_negated_or_joined_for_ladder(self):
        self.equivalent(
            Program(
                [
                    ["LD 0", "OR [%MW0=0]", "ST %Q0.0"],
                    ["LDN [%MW0=0]", "ST %Q0.1"],
                    ["LD 1", "ANDN [%MW0<>0]", "N", "ST %Q0.2"],
                ]
            ),
            [{}] * 2,
            [[True, False, False]] * 2,
        )

    def test_stack_and_parentheses_preserve_numeric_action_guards(self):
        p = Program(
            [
                [
                    "LD %I0.0",
                    "MPS",
                    "[%MW0:=1]",
                    "MPP",
                    "AND( %I0.1",
                    "OR %I0.2",
                    ")",
                    "[%MW0:=%MW0+2]",
                ],
                ["LD [%MW0=3]", "ST %Q0.0"],
                ["LD [%MW0=1]", "ST %Q0.1"],
            ]
        )
        frames = [{}, {"inputs": {0: True}}, {"inputs": {0: True, 2: True}}, {}]
        self.equivalent(
            p, frames, [[False, False], [False, True], [True, False], [True, False]]
        )

    def test_direct_timer_input_and_internal_q_read(self):
        p = Program(
            [["LD %I0.0", "IN %TM42"], ["LD %TM42.Q", "STN %Q0.0"]],
            {42: Timer("TON", 200, 100)},
        )
        frames = [{"dt_ms": 100, "inputs": {0: True}}] * 4 + [{"dt_ms": 100}]
        self.equivalent(p, frames, [[True], [True], [False], [False], [True]])

    def test_timer_composed_input_and_set_reset_outputs(self):
        p = Program(
            [
                [
                    "BLK %TM0",
                    "LDN %Q0.0",
                    "ANDN %I0.1",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "S %Q0.0",
                    "END_BLK",
                ],
                ["BLK %TM1", "LD %Q0.0", "IN", "OUT_BLK", "LD Q", "R %Q0.0", "END_BLK"],
            ],
            {0: Timer("TON", 200, 100), 1: Timer("TON", 200, 100)},
        )
        self.equivalent(
            p,
            [{"dt_ms": 100}] * 8,
            [[False], [False], [True], [True], [False], [False], [False], [True]],
        )

    def test_labels_survive_stack_normalization_and_jump(self):
        p = Program(
            [
                ["LD %I0.0", "JMPC %L7"],
                ["LD 0", "ST %Q0.0"],
                ["LD 1", "JMPC %L8"],
                ["%L7:", "LD 1", "MPS", "N", "ST %M0", "MPP", "ST %Q0.0"],
                ["%L8:", "LD %Q0.0", "ST %Q0.1"],
            ]
        )
        self.equivalent(
            p,
            [{}, {"inputs": {0: True}}, {}],
            [[False, False], [True, True], [False, False]],
        )

    def test_structural_errors_and_unverified_modifiers_are_rejected(self):
        invalid = [
            ["LD 1", "MRD", "ST %M0"],
            ["LD 1", "MPP", "ST %M0"],
            ["LD 1", "MPS", "ST %M0"],
            ["LD 1", ")", "ST %M0"],
            ["LD 1", "AND( 1", "ST %M0", ")", "ST %M1"],
            ["LD 1", "OR( 0", "MPS", "MPP", ")", "ST %M0"],
            ["LD 1", "AND(N 0", ")", "ST %M0"],
            ["LD 1", "MPS", "JMPC %L0", "MPP", "ST %M0"],
            ["LD 1", "N %M0", "ST %M0"],
        ]
        for rung in invalid:
            with self.subTest(rung=rung), self.assertRaises(CompileError):
                validate(Program([rung]))
        for target in ("%S20", "%TM0.Q"):
            with self.subTest(target=target), self.assertRaises(CompileError):
                validate(Program([["LD 1", "STN " + target]]))
        with self.assertRaisesRegex(CompileError, "IN.*accumulator.*unverified"):
            validate(
                Program([["LD 1", "IN %TM0", "ST %M0"]], {0: Timer("TON", 100, 100)})
            )

    def test_documented_local_depth_and_overflow(self):
        for nesting in ("stack", "parentheses"):

            def build(count):
                return (
                    ["LD 1"]
                    + (
                        ["MPS"] * count + ["MPP"] * count
                        if nesting == "stack"
                        else ["AND( 1"] * count + [")"] * count
                    )
                    + ["ST %Q0.0"]
                )

            with self.subTest(nesting=nesting):
                self.equivalent(Program([build(32)]), [{}], [[True]])
                with self.assertRaises(CompileError):
                    validate(Program([build(33)]))

    def test_empty_instructions_have_a_clean_diagnostic(self):
        for empty in ("", " "):
            for rung in (
                ["LD 1", empty, "ST %M0"],
                [
                    "BLK %TM0",
                    "LD 1",
                    empty,
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "ST %M0",
                    "END_BLK",
                ],
                [
                    "BLK %TM0",
                    "LD 1",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    empty,
                    "ST %M0",
                    "END_BLK",
                ],
            ):
                with self.subTest(rung=rung), self.assertRaises(CompileError):
                    validate(
                        Program(
                            [rung],
                            {0: Timer("TON", 100, 100)}
                            if rung[0].startswith("BLK")
                            else {},
                        )
                    )

    def test_normalization_does_not_read_inactive_nonfinite_comparison(self):
        for load, operator, expected in [
            ("1", "OR", True),
            ("1", "ORN", True),
            ("0", "AND", False),
            ("0", "ANDN", False),
        ]:
            with self.subTest(operator=operator):
                self.equivalent(
                    Program(
                        [
                            ["LD 1", "[%MD0:=2143289344]"],
                            ["LD " + load, operator + " [%MF0=0.0]", "ST %Q0.0"],
                            ["LD 1", "N", "ST %M0"],
                        ]
                    ),
                    [{}] * 2,
                    [[expected]] * 2,
                )

    def test_authentic_timer_graphs_match_composed_input_and_coils(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/native_timer_graphs.json").read_text()
        )
        for case in fixture["cases"]:
            with self.subTest(rung=case["rung"]):
                node = ET.fromstring(case["rung_xml"])
                check_graph(node, case["il"])
                descriptor = node.find("./LadderElements/LadderEntity/Descriptor")
                descriptor.text = "%M999"
                with self.assertRaises(CompileError):
                    check_graph(node, case["il"])

    def test_comparison_tabs_are_accepted_without_cache_miss(self):
        self.equivalent(
            Program(
                [
                    ["LD\t[%MW0=0]", "ST %Q0.0"],
                    ["LD 1", "AND(\t[%MW0=0]", ")", "ST %Q0.1"],
                ]
            ),
            [{}] * 2,
            [[True, True]] * 2,
        )

    def test_unknown_block_graphics_fail_with_compile_error(self):
        with self.assertRaises(CompileError):
            graphics(
                ["BLK %C0", "LD %I0.0", "IN", "OUT_BLK", "LD Q", "ST %Q0.0", "END_BLK"]
            )

    def test_canonical_timer_with_negated_comparison_is_normalized(self):
        self.equivalent(
            Program(
                [
                    [
                        "BLK %TM0",
                        "LDN [%MW0=0]",
                        "IN",
                        "OUT_BLK",
                        "LD Q",
                        "ST %Q0.0",
                        "END_BLK",
                    ]
                ],
                {0: Timer("TON", 100, 100)},
            ),
            [{}] * 2,
            [[False]] * 2,
        )


if __name__ == "__main__":
    unittest.main()
