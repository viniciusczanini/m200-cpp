"""Retentive/dynamic modes: explicit hand timelines and preserved config."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import write_project, load_project
from m200.reverse import to_cpp


class TimerModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "modes.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def probe(self, kind, retentive, dynamic, events, initial=5, skip=False):
        body = f"plc::{kind} t{{42,100,{initial},{str(retentive).lower()},{str(dynamic).lower()}}};void scan(){{\nplc::i16 p=0;bool q=false;\n"
        for b in range(3):
            body += f"if(plc::input({b + 2})){{p=plc::add_i16(p,{1 << b});}}\n"
        body += "if(plc::input(1)){t.set_preset(p);}\n"
        if skip:
            body += "if(plc::input(5)){goto observe;}\n"
        body += "q=t.update(plc::input(0));plc::output(1,q);\nobserve:;plc::output(0,t.done());\n"
        for b in range(3):
            body += f"plc::output({b + 2},plc::and_i16(t.value(),{1 << b})!=0);\n"
        body += "}"
        p = self.compile(body)
        frames = []
        expected = []
        wired = False
        for dt, enabled, preset, value, q, skipped in events:
            inputs = {0: enabled, 1: preset is not None, 5: skipped}
            inputs.update({b + 2: bool((preset or 0) & (1 << b)) for b in range(3)})
            frames.append({"dt_ms": dt, "inputs": inputs})
            if not skipped:
                wired = q
            expected.append(
                [q, wired] + [bool(value & (1 << b)) for b in range(3)] + [False] * 11
            )

        def check(candidate):
            m = Machine(candidate)
            self.assertEqual(
                [m.step(f["inputs"], f["dt_ms"]) for f in frames], expected
            )

        check(p)
        self.assertEqual(run_native(self.source, frames), expected)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), expected)
        rebuilt = compile_source(reverse)
        check(rebuilt)
        self.assertEqual(rebuilt.timers, p.timers)
        self.assertEqual(Program.from_dict(p.as_dict()).timers, p.timers)
        destination = self.work / "modes.smbp"
        destination.write_bytes(b"existing")
        with self.assertRaisesRegex(
            CompileError, "timer.*functional.level.*unverified"
        ):
            write_project(
                p, Path(__file__).parent / "fixtures/synthetic.smbp", destination
            )
        self.assertEqual(destination.read_bytes(), b"existing")
        return p

    def test_ton_retains_incomplete_value_then_resets_completed_activation(self):
        self.probe(
            "Ton",
            True,
            False,
            [
                (100, True, None, 0, False, False),
                (100, True, None, 1, False, False),
                (200, False, None, 2, False, False),
                (100, False, None, 2, False, False),
                (100, True, None, 2, False, False),
                (200, True, None, 3, False, False),
                (100, True, None, 5, True, False),
                (100, False, None, 0, False, False),
                (100, True, None, 0, False, False),
            ],
        )

    def test_tof_retains_on_rising_and_resumes_on_falling(self):
        self.probe(
            "Tof",
            True,
            False,
            [
                (100, True, None, 0, True, False),
                (100, False, None, 0, True, False),
                (200, False, None, 1, True, False),
                (100, True, None, 3, True, False),
                (100, False, None, 3, True, False),
                (200, False, None, 4, True, False),
                (100, False, None, 5, False, False),
                (100, True, None, 0, True, False),
            ],
        )

    def test_dynamic_decrease_waits_for_tick_and_does_not_clamp_value(self):
        self.probe(
            "Ton",
            False,
            True,
            [
                (100, True, None, 0, False, False),
                (100, True, None, 1, False, False),
                (50, True, None, 2, False, False),
                (0, True, 1, 2, False, False),
                (50, True, None, 2, False, False),
                (100, True, None, 2, True, False),
            ],
            initial=6,
        )

    def test_dynamic_growth_extends_active_ton(self):
        self.probe(
            "Ton",
            False,
            True,
            [
                (100, True, None, 0, False, False),
                (100, True, 4, 1, False, False),
                (100, True, None, 2, False, False),
                (100, True, None, 3, False, False),
                (100, True, None, 4, True, False),
            ],
            initial=2,
        )

    def test_dynamic_tof_decrease_preserves_value(self):
        self.probe(
            "Tof",
            False,
            True,
            [
                (100, True, None, 0, True, False),
                (100, False, None, 0, True, False),
                (100, False, None, 1, True, False),
                (50, False, None, 2, True, False),
                (50, False, 1, 2, True, False),
                (100, False, None, 2, False, False),
            ],
            initial=6,
        )

    def test_dynamic_pulse_growth_and_decrease_without_retrigger(self):
        self.probe(
            "Pulse",
            False,
            True,
            [
                (100, True, None, 0, True, False),
                (100, False, 6, 1, True, False),
                (50, True, None, 2, True, False),
                (50, True, 1, 2, True, False),
                (100, True, None, 2, False, False),
                (100, False, None, 0, False, False),
                (100, True, None, 0, True, False),
                (100, True, None, 1, False, False),
            ],
            initial=3,
        )

    def test_both_flags_reset_paused_value_only_when_preset_strictly_smaller(self):
        for kind in ("Ton", "Tof"):
            active = kind == "Ton"
            with self.subTest(kind=kind):
                self.probe(
                    kind,
                    True,
                    True,
                    [
                        (100, not active, None, 0, not active, False),
                        (200, active, None, 0, not active, False),
                        (0, not active, None, 2, not active, False),
                        (0, not active, 2, 2, not active, False),
                        (100, not active, 1, 0, not active, False),
                        (100, active, None, 0, not active, False),
                        (100, active, None, 1, active, False),
                    ],
                    initial=5,
                )

    def test_completed_dynamic_ton_does_not_restart_when_preset_grows(self):
        # Local policy; post-completion native boundary remains externally pending.
        self.probe(
            "Ton",
            False,
            True,
            [
                (100, True, None, 0, False, False),
                (100, True, None, 1, True, False),
                (100, True, 5, 1, True, False),
                (100, True, None, 1, True, False),
                (100, False, None, 0, False, False),
                (100, True, None, 0, False, False),
            ],
            initial=1,
        )

    def test_skipped_block_updates_internal_state_but_not_wired_output(self):
        self.probe(
            "Ton",
            True,
            True,
            [
                (100, True, None, 0, False, False),
                (100, False, None, 1, False, True),
                (100, False, 1, 2, False, True),
                (100, False, None, 2, True, True),
                (100, False, None, 0, False, False),
            ],
            initial=5,
            skip=True,
        )

    def test_legacy_json_defaults_and_strict_mode_types(self):
        p = Program([["LD %TM0.Q", "ST %Q0.0"]], {0: Timer("TON", 500, 100)})
        data = p.as_dict()
        data["timers"]["0"].pop("retentive", None)
        data["timers"]["0"].pop("dynamic_preset", None)
        restored = Program.from_dict(data)
        self.assertFalse(restored.timers[0].retentive)
        self.assertFalse(restored.timers[0].dynamic_preset)
        for key in ("retentive", "dynamic_preset"):
            for value in (1, "false", None):
                data = p.as_dict()
                data["timers"]["0"][key] = value
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(CompileError),
                ):
                    validate(Program.from_dict(data))

    def test_retained_pulse_and_nonliteral_flags_are_rejected(self):
        for body in [
            "plc::Pulse p{0,100,3,true,false};void scan(){bool q=p.update(true);}",
            "bool r=true;plc::Ton t{0,100,3,r,false};void scan(){}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)

    def test_import_keeps_options_and_reaches_explicit_profile_gate(self):
        source = self.compile("plc::Ton t{0,100,3};void scan(){bool q=t.update(true);}")
        dest = self.work / "plain.smbp"
        write_project(source, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        original = dest.read_text()
        for option in ("IsRetentive", "IsDynamicPreset"):
            dest.write_text(
                original.replace(
                    f"<{option}>false</{option}>", f"<{option}>true</{option}>"
                )
            )
            with (
                self.subTest(option=option),
                self.assertRaisesRegex(
                    CompileError, "timer.*functional.level.*unverified"
                ),
            ):
                load_project(dest)


if __name__ == "__main__":
    unittest.main()
