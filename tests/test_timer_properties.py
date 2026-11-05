"""Timer properties: hand timelines, explicit identity and actual IL reversal."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class TimerPropertyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "timers.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected):
        p = self.compile(body)

        def rows(program):
            machine = Machine(program)
            return [
                machine.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames
            ]

        got = rows(p)
        self.assertEqual([r[: len(expected[0])] for r in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), got)
        rebuilt = compile_source(reverse)
        self.assertEqual(rows(rebuilt), got)
        destination = self.work / "timers.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", destination)
        self.assertEqual(rows(load_project(destination)), got)
        self.assertEqual(rebuilt.timers, p.timers)
        return p

    def timeline(self, kind, inputs, values, results, presets):
        body = f"plc::{kind} t{{42,100,3}};void scan(){{\n"
        body += "if(plc::input(1)){t.set_preset(1);}\nbool q=t.update(plc::input(0));\n"
        body += "plc::output(0,q);plc::output(1,t.done());\n"
        body += "".join(f"plc::output({i + 2},t.value()=={i});" for i in range(4))
        body += "plc::output(6,t.preset()==1);}"
        frames = [
            {"dt_ms": 100, "inputs": {0: enabled, 1: setp}} for enabled, setp in inputs
        ]
        expected = [
            [q, q] + [value == i for i in range(4)] + [preset == 1]
            for q, value, preset in zip(results, values, presets)
        ]
        return self.equivalent(body, frames, expected)

    def test_ton_preset_write_waits_until_next_activation(self):
        p = self.timeline(
            "Ton",
            [
                (True, False),
                (True, True),
                (True, False),
                (True, False),
                (False, False),
                (True, False),
                (True, False),
            ],
            [0, 1, 2, 3, 0, 0, 1],
            [False, False, False, True, False, False, True],
            [3, 1, 1, 1, 1, 1, 1],
        )
        self.assertEqual(set(p.timers), {42})
        self.assertEqual(p.timers[42], Timer("TON", 300, 100))

    def test_tof_falling_edge_captures_preset_and_rising_resets_value(self):
        self.timeline(
            "Tof",
            [
                (True, False),
                (False, False),
                (False, True),
                (False, False),
                (False, False),
                (True, False),
                (False, False),
                (False, False),
            ],
            [0, 0, 1, 2, 3, 0, 0, 1],
            [True, True, True, True, False, True, True, False],
            [3, 3, 1, 1, 1, 1, 1, 1],
        )

    def test_pulse_ignores_retrigger_while_running_and_resets_after_finish(self):
        self.timeline(
            "Pulse",
            [
                (True, False),
                (False, True),
                (True, False),
                (True, False),
                (False, False),
                (True, False),
                (False, False),
            ],
            [0, 1, 2, 3, 0, 0, 0],
            [True, True, True, False, False, True, False],
            [3, 1, 1, 1, 1, 1, 1],
        )

    def test_jump_does_not_freeze_internal_timer_or_write_wired_output(self):
        self.equivalent(
            """plc::Ton t{9,100,2};void scan(){bool q=false;
if(plc::input(1)){goto observe;}q=t.update(plc::input(0));plc::output(0,q);
observe:;plc::output(1,t.done());plc::output(2,t.value()==2);}""",
            [
                {"dt_ms": 100, "inputs": {0: True}},
                {"dt_ms": 100, "inputs": {1: True}},
                {"dt_ms": 100, "inputs": {1: True}},
                {"dt_ms": 100, "inputs": {0: True}},
            ],
            [
                [False, False, False],
                [False, False, False],
                [False, True, True],
                [True, True, True],
            ],
        )

    def test_indexed_preset_rhs_and_inactive_write_preserve_flags(self):
        self.equivalent(
            """plc::WordMemory image{32};plc::Ton t{4,100,3};
void scan(){plc::clear_index_error();plc::write_word(0,1);plc::write_word(21,7);
t.set_preset(plc::read_word_indexed(20,0));
plc::write_word(0,-32768);if(plc::input(0)){t.set_preset(plc::read_word_indexed(20,0));}
bool q=t.update(false);plc::output(0,t.preset()==7 && !q && !plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_sparse_native_il_preserves_base_and_timer_property_destinations(self):
        p = Program(
            [
                ["LD 1", "[%TM254.P:=7]"],
                [
                    "BLK %TM254",
                    "LD %I0.0",
                    "IN",
                    "OUT_BLK",
                    "LD Q",
                    "ST %M0",
                    "END_BLK",
                ],
                ["LD [%TM254.P=7]", "ST %Q0.0"],
                ["LD %TM254.Q", "ST %Q0.1"],
            ],
            {254: Timer("TON", 300, 100)},
        )
        source = self.work / "native.cpp"
        source.write_text(to_cpp(p))
        rebuilt = compile_source(source)
        self.assertEqual(rebuilt.timers, p.timers)
        frames = [{"dt_ms": 100, "inputs": {0: True}}] * 9
        machine = Machine(p)
        expected = [machine.step(f["inputs"], 100) for f in frames]
        self.assertEqual(run_native(source, frames), expected)
        machine = Machine(rebuilt)
        self.assertEqual([machine.step(f["inputs"], 100) for f in frames], expected)

    def test_property_only_timer_is_configured_without_forcing_an_update(self):
        self.equivalent(
            """plc::Ton t{20,100,3};void scan(){t.set_preset(7);
plc::output(0,t.preset()==7 && t.value()==0 && !t.done());}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_known_invalid_native_preset_literal_fails_validation(self):
        for value in (-1, 10000):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(CompileError, "preset"),
            ):
                validate(
                    Program(
                        [["LD 1", f"[%TM0.P:={value}]"]], {0: Timer("TON", 100, 100)}
                    )
                )

    def test_auto_and_explicit_timers_compose_with_clock_in_declared_order(self):
        self.equivalent(
            """plc::Ton first{0,100,2};plc::Clock clock{100};plc::Tof last{200};
void scan(){bool a=first.update(plc::input(0));bool b=clock.update(plc::input(0));
bool c=last.update(plc::input(0));plc::output(0,a);plc::output(1,b);plc::output(2,c);
plc::output(3,first.preset()==2 && last.preset()==200);}""",
            [{"dt_ms": 100, "inputs": {0: True}}] * 4,
            [
                [False, False, True, True],
                [False, True, True, True],
                [True, True, True, True],
                [True, False, True, True],
            ],
        )

    def test_invalid_constructors_properties_and_readonly_targets_fail(self):
        for body in [
            "plc::Ton t{255,100,3};void scan(){}",
            "plc::Ton t{6,1,3};void scan(){}",
            "plc::Ton t{0,100,-1};void scan(){}",
            "plc::Ton t{0,100,10000};void scan(){}",
            "plc::Ton t{0,2,3};void scan(){}",
            "plc::Ton a{0,100,3};plc::Tof b{0,100,4};void scan(){}",
            "plc::Ton a{100};plc::Ton b{0,100,3};void scan(){}",
            "plc::Ton t{100};void scan(){t.set_preset(10000);}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)
        for line in ["[%TM0.V:=1]", "[%TM0.Q:=1]", "[%TM255.P:=1]", "[%TM00.P:=1]"]:
            with self.subTest(line=line), self.assertRaises(CompileError):
                validate(Program([["LD 1", line]], {0: Timer("TON", 100, 100)}))
        for ref in ["%TM0.Q", "%TM0.V"]:
            with self.subTest(ref=ref), self.assertRaises(CompileError):
                validate(Program([["LD 1", "ST " + ref]], {0: Timer("TON", 100, 100)}))
        with self.assertRaises(CompileError):
            validate(Program([["LD %TM1.Q", "ST %Q0.0"]]))


if __name__ == "__main__":
    unittest.main()
