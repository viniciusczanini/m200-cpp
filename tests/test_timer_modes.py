"""Retentive/dynamic modes: explicit hand timelines and preserved config."""

import copy
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
        # G07 admits documented combinations using the ACTUAL template level.
        # Keep all existing literal V/Q/wired-output timelines unchanged and
        # apply them to the serialized native program as well.
        template = Path(__file__).parent / "fixtures/official_tm200ce40t_timer_options_behavior.smbp"
        before = template.read_bytes()
        destination = self.work / "modes.smbp"
        write_project(p, template, destination)
        actual = load_project(destination)
        self.assertEqual(actual.timers, p.timers)
        check(actual)
        self.assertEqual(actual.metadata["official_editor"], "pending")
        native_timer = ET.parse(destination).find("./SoftwareConfiguration/Timers/TimerTM")
        self.assertEqual(
            tuple(native_timer.findtext(k) for k in ("Address", "Index", "Type", "Base", "Preset", "IsRetentive", "IsDynamicPreset")),
            ("%TM42", "42", {"Ton": "TON", "Tof": "TOF", "Pulse": "TP"}[kind],
             "OneHundredMilliSeconds", str(initial), str(retentive).lower(), str(dynamic).lower()),
        )
        native_reverse = self.work / "native_reverse.cpp"
        native_reverse.write_text(to_cpp(actual))
        rebuilt_native = compile_source(native_reverse)
        self.assertEqual(rebuilt_native.timers, p.timers)
        check(rebuilt_native)
        self.assertEqual(template.read_bytes(), before)
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

    def test_import_keeps_documented_options_without_changing_actual_il(self):
        source = self.compile("plc::Ton t{0,100,3};void scan(){bool q=t.update(true);}")
        template = Path(__file__).parent / "fixtures/official_tm200ce40t_timer_options_behavior.smbp"
        before = template.read_bytes()
        dest = self.work / "plain.smbp"
        write_project(source, template, dest)
        original = dest.read_bytes()
        original_program = load_project(dest)
        for option in ("IsRetentive", "IsDynamicPreset"):
            with self.subTest(option=option):
                tree = ET.fromstring(original)
                tree.find("./SoftwareConfiguration/Timers/TimerTM/" + option).text = "true"
                dest.write_bytes(ET.tostring(tree))
                mutated = dest.read_bytes()
                actual = load_project(dest)
                self.assertEqual(actual.timers, {0: Timer("TON", 300, 100,
                    option == "IsRetentive", option == "IsDynamicPreset")})
                self.assertEqual(actual.rungs, original_program.rungs)
                self.assertEqual(actual.metadata["official_editor"], "pending")
                self.assertEqual(dest.read_bytes(), mutated)
        self.assertEqual(template.read_bytes(), before)

    def test_option_levels_fail_atomically_even_with_forged_metadata(self):
        for ret, dyn, token, message in (
            (True, False, "FunctLevelMan6_0", r"timer retention requires functional level >=4\.0"),
            (False, True, "FunctLevelMan17_0", r"timer dynamic preset requires functional level >=12\.0"),
            (True, True, "FunctLevelMan17_0", r"timer dynamic preset requires functional level >=12\.0"),
        ):
            with self.subTest(ret=ret, dyn=dyn, token=token):
                program = Program(
                    [["BLK %TM0", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"]],
                    {0: Timer("TON", 300, 100, ret, dyn)},
                )
                program.metadata = {"ManagementLevel": "FunctLevelMan21_0", "official_editor": "verified"}
                tree = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp")
                tree.find("ManagementLevel").text = token
                template = self.work / "low_level.smbp"
                tree.write(template)
                before = template.read_bytes()
                snapshot = copy.deepcopy(program.as_dict())
                destination = self.work / "preserved.smbp"
                destination.write_bytes(b"existing destination")
                with self.assertRaisesRegex(CompileError, message):
                    write_project(program, template, destination)
                self.assertEqual(destination.read_bytes(), b"existing destination")
                self.assertEqual(template.read_bytes(), before)
                self.assertEqual(program.as_dict(), snapshot)


if __name__ == "__main__":
    unittest.main()
