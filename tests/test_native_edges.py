"""Native edge contacts sample scan boundaries, never consume on evaluation."""

import copy
import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.ladder_lowering import normalize
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project, graphics
from m200.reverse import to_cpp


class NativeEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def equivalent(self, program, frames, expected, source=None):
        def rows(p):
            m = Machine(p)
            return [m.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]

        got = rows(program)
        self.assertEqual([r[: len(expected[0])] for r in got], expected)
        if source is not None:
            self.assertEqual(run_native(source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(program))
        self.assertEqual(run_native(reverse, frames), got)
        self.assertEqual(rows(compile_source(reverse)), got)
        before = copy.deepcopy(program.as_dict())
        self.assertEqual(rows(normalize(program)), got)
        dest = self.work / "edges.smbp"
        write_project(program, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertEqual(rows(load_project(dest)), got)
        self.assertEqual(before, program.as_dict())
        return program

    def compile(self, body):
        source = self.work / "source.cpp"
        source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(source), source

    def test_all_eight_operators_use_current_input_event(self):
        p = Program(
            [["LDR %I0.0", "ST %Q0.0"], ["LDF %I0.0", "ST %Q0.1"]]
            + [
                ["LD %I0.1", op + " %I0.0", f"ST %Q0.{q}"]
                for op, q in [
                    ("ANDR", 2),
                    ("ANDF", 3),
                    ("ORR", 4),
                    ("ORF", 5),
                    ("XORR", 6),
                    ("XORF", 7),
                ]
            ]
        )
        frames = [
            {"inputs": {0: a, 1: b}, "dt_ms": 0}
            for a, b in [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (1, 1)]
        ]
        self.equivalent(
            p,
            frames,
            [
                [0] * 8,
                [1, 0, 0, 0, 1, 0, 1, 0],
                [0, 0, 0, 0, 1, 1, 1, 1],
                [0, 1, 0, 1, 1, 1, 1, 0],
                [0] * 8,
                [1, 0, 1, 0, 1, 1, 0, 1],
            ],
        )

    def test_memory_event_is_delayed_and_survives_same_scan_writes(self):
        p = Program(
            [
                ["LDR %M0", "ST %Q0.0"],
                ["LD %I0.0", "ST %M0"],
                ["LDR %M0", "ST %Q0.1"],
                ["LD 1", "R %M0"],
                ["LDR %M0", "ST %Q0.2"],
                ["LD %I0.0", "ST %M0"],
                ["LDF %M0", "ST %Q0.3"],
            ]
        )
        self.equivalent(
            p,
            [{"inputs": {0: x}} for x in [0, 1, 1, 0, 0, 1]],
            [
                [0, 0, 0, 0],
                [0, 0, 0, 0],
                [1, 1, 1, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 0, 0],
            ],
        )

    def test_cpp_apis_repeated_in_same_scan_loop_do_not_consume(self):
        p, source = self.compile("""void scan(){plc::i16 count=0;plc::i16 i=0;
while(i<3){if(plc::input_rising(0)){count=plc::add_i16(count,1);}i=plc::add_i16(i,1);}
plc::output(0,count==3);plc::output(1,plc::input_falling(0));
plc::output(2,plc::input_rising(0));}""")
        self.equivalent(
            p,
            [{"inputs": {0: x}} for x in [0, 1, 1, 0]],
            [[0, 0, 0], [1, 0, 1], [0, 0, 0], [0, 1, 0]],
            source,
        )

    def test_skipped_input_contact_does_not_queue_an_old_event(self):
        p = Program(
            [
                ["LD 0", "ST %Q0.0"],
                ["LD %I0.1", "JMPC %L0"],
                ["LDR %I0.0", "ST %Q0.0"],
                ["%L0:", "LDR %M0", "ST %Q0.1"],
                ["LD %I0.0", "ST %M0"],
            ]
        )
        self.equivalent(
            p,
            [
                {"inputs": {0: a, 1: b}}
                for a, b in [(0, 0), (1, 1), (1, 0), (0, 1), (1, 0)]
            ],
            [[0, 0], [0, 0], [0, 1], [0, 0], [1, 0]],
        )

    def test_pulse_between_memory_sampling_boundaries_has_no_event(self):
        p, source = self.compile("""void scan(){plc::write_m(1023,true);
plc::output(0,plc::m_rising(1023));plc::write_m(1023,false);
plc::output(1,plc::m_falling(1023));plc::output(2,plc::input_rising(23));}""")
        self.equivalent(
            p,
            [{"inputs": {23: x}} for x in [1, 1, 0, 1]],
            [[0, 0, 1], [0, 0, 0], [0, 0, 0], [0, 0, 1]],
            source,
        )

    def test_cpp_memory_edges_survive_helper_short_circuit_and_bit_image(self):
        p, source = self.compile("""plc::BitMemory image{1};
bool event(bool enabled){return enabled&&plc::m_rising(0);}
void scan(){plc::write_m(0,plc::input(0));plc::output(0,event(plc::input(1)));
plc::output(1,plc::m_falling(0));}""")
        self.equivalent(
            p,
            [
                {"inputs": {0: a, 1: b}}
                for a, b in [(1, 0), (1, 0), (1, 1), (0, 1), (0, 1)]
            ],
            [[0, 0], [0, 0], [0, 0], [0, 0], [0, 1]],
            source,
        )

    def test_stack_groups_and_timer_use_the_same_sampled_contact(self):
        p = Program(
            [
                ["LD %I0.0", "ST %M7"],
                [
                    "LDR %I0.0",
                    "MPS",
                    "N",
                    "ST %Q0.0",
                    "MPP",
                    "AND( %I0.1",
                    "OR %I0.2",
                    ")",
                    "ST %Q0.1",
                ],
                ["BLK %TM0", "LDR %M7", "IN", "OUT_BLK", "LD Q", "ST %Q0.2", "END_BLK"],
            ],
            {0: Timer("TON", 0, 100)},
        )
        self.equivalent(
            p,
            [{"inputs": {0: a, 1: True}} for a in [0, 1, 1, 0]],
            [[1, 0, 0], [0, 1, 0], [1, 0, 1], [1, 0, 0]],
        )

    def test_contact_graph_uses_observed_edge_tokens(self):
        self.assertEqual(
            graphics(["LDR %I0.0", "ANDF %M7", "ST %Q0.0"])[:2],
            [("RisingEdge", "%I0.0", 0), ("FallingEdge", "%M7", 1)],
        )

    def test_unqualified_helper_does_not_become_a_plc_edge_api(self):
        p, source = self.compile("""bool input_rising(bool enabled){return !enabled;}
void scan(){plc::output(0,input_rising(plc::input(0)));}""")
        self.equivalent(p, [{}, {"inputs": {0: True}}], [[True], [False]], source)

    def test_domain_and_api_bounds_are_closed(self):
        for ref in [
            "1",
            "%Q0.0",
            "%S4",
            "%MW0:X0",
            "%M0[%MW0]",
            "%I1.0",
            "%I0.24",
            "%M1024",
            "%M00",
            "[%MW0=0]",
        ]:
            for op in ("LDR", "LDF", "ANDR", "ANDF", "ORR", "ORF", "XORR", "XORF"):
                rung = ([] if op.startswith("LD") else ["LD 1"]) + [
                    op + " " + ref,
                    "ST %Q0.0",
                ]
                with self.subTest(ref=ref, op=op), self.assertRaises(CompileError):
                    validate(Program([rung]))
        for expr in [
            "plc::input_rising(24)",
            "plc::input_falling(-1)",
            "plc::m_rising(1024)",
            "plc::m_falling(-1)",
        ]:
            with self.subTest(expr=expr), self.assertRaises(CompileError):
                self.compile("void scan(){plc::output(0," + expr + ");}")
        with self.assertRaises(CompileError):
            self.compile(
                "plc::BitMemory m{1};void scan(){plc::output(0,plc::m_rising(1));}"
            )
        with self.assertRaises(CompileError):
            self.compile("bool x=plc::input_rising(0);void scan(){plc::output(0,x);}")
        for op in ["RISINGX", "FALLING255", "AND(R %M0", "OR(F %M0"]:
            with self.subTest(op=op), self.assertRaises(CompileError):
                validate(Program([["LD %M0", op, "ST %Q0.0"]]))


if __name__ == "__main__":
    unittest.main()
