"""Regressions from public native projects; no third-party file needed to run.

Original byte-for-byte projects and commit/hash provenance live in the separate
downloaded corpus. These small cases isolate their instruction forms.
"""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import Program, Timer
from m200.native import run_native
from m200.project import check_graph, graphics
from m200.reverse import to_cpp


class PublicRegressions(unittest.TestCase):
    def test_foreign_model_diagnostic_identifies_actual_and_required_cpu(self):
        import xml.etree.ElementTree as ET
        from m200.project import load_project
        from m200.model import CompileError

        with tempfile.TemporaryDirectory() as d:
            root = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp").getroot()
            cpu = root.find("HardwareConfiguration/Plc/Cpu")
            cpu.find("Reference").text = "TM221CE16R"
            analog = ET.SubElement(cpu, "AnalogInputs")
            ET.SubElement(analog, "AnalogIO")
            ET.SubElement(analog, "AnalogIO")
            path = Path(d) / "foreign.smbp"
            ET.ElementTree(root).write(path)
            with self.assertRaisesRegex(CompileError, "TM221CE16R.*TM200CE40T"):
                load_project(path)

    def equivalent(self, program, frames):
        validate(program)
        machine = Machine(program)
        expected = [
            machine.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "native.cpp"
            source.write_text(to_cpp(program))
            self.assertEqual(run_native(source, frames), expected)
            rebuilt = Machine(compile_source(source))
            self.assertEqual(
                [rebuilt.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames],
                expected,
            )
        return machine, expected

    def test_native_inline_oper_preserves_accumulator_for_following_coil(self):
        p = Program(
            [
                ["LD %I0.0", "OPER [ %MW0 := 1 ]", "ST %Q0.1"],
                ["LD [ %MW0 > 1 ]", "ST %Q0.2"],
            ]
        )
        m, got = self.equivalent(p, [{}, {"inputs": {0: True}}, {}])
        self.assertEqual(
            [row[1:3] for row in got], [[False, False], [True, False], [False, False]]
        )
        self.assertEqual(m.words[0], 1)
        self.assertEqual(graphics(p.rungs[0])[1][0], "Comparison")

    def test_native_action_after_coil_uses_same_accumulator(self):
        p = Program([["LD %I0.0", "ST %Q0.0", "[ %MW600 := 1 ]"]])
        m, got = self.equivalent(p, [{}, {"inputs": {0: True}}, {}])
        self.assertEqual([row[0] for row in got], [False, True, False])
        self.assertEqual(m.words[600], 1)

    def test_native_timer_negated_input_and_scan_order(self):
        p = Program(
            [
                ["LD %M30", "ST %Q0.0"],
                [
                    "BLK %TM0",
                    "LDN %I0.0",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "ST %M30",
                    "END_BLK",
                ],
                ["LD %M30", "ST %Q0.1"],
            ],
            {0: Timer("TOF", 25000, 1000)},
        )
        _, got = self.equivalent(
            p,
            [
                {"dt_ms": 1000},
                {"inputs": {0: True}, "dt_ms": 25000},
                {"inputs": {0: True}},
                {"inputs": {0: False}},
            ],
        )
        self.assertEqual(
            [row[:2] for row in got],
            [[False, True], [True, True], [True, False], [False, True]],
        )

    def test_timer_graph_accepts_observed_two_column_positions(self):
        import xml.etree.ElementTree as ET

        for column in (2, 3):
            rung = [
                "BLK %TM0",
                "LDN %I0.0",
                "IN",
                "OUT_BLK",
                "LD Q",
                "ST %M30",
                "END_BLK",
            ]
            r = ET.Element("RungEntity")
            graph = ET.SubElement(r, "LadderElements")
            entries = [
                ("NegatedContact", "%I0.0", 0),
                ("Timer", "%TM0", column),
                ("Coil", "%M30", 10),
            ]
            entries += [
                ("Line", "", i) for i in range(1, 10) if i not in (column, column + 1)
            ]
            for typ, arg, col in entries:
                e = ET.SubElement(graph, "LadderEntity")
                for tag, value in [
                    ("ElementType", typ),
                    ("Descriptor", arg),
                    ("Row", "0"),
                    ("Column", str(col)),
                    ("ChosenConnection", "Left" if typ == "Coil" else "Left, Right"),
                ]:
                    ET.SubElement(e, tag).text = value
            with self.subTest(column=column):
                check_graph(r, rung)
        self.assertEqual(graphics(rung)[0][0], "NegatedContact")
