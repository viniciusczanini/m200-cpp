"""Documented timer admission with independent oracles and pinned scoped evidence."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.timer_profile import validate_options

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "tests/fixtures/official_tm200ce40t_timer_options_behavior.smbp"
SAVED_SHA = "5358e5334696e1838e8b34b9efaa84fafb2a7bd97802d2d2ee32ae94a7f52214"
LEVEL = "FunctLevelMan21_0"
LEGACY = ROOT / "tests/fixtures/official_tm200ce40t_timer_ret_ton_fl3_2.smbp"

# Written before admission. Literal local checkpoints are not GUI timing claims.
# dt advances time AFTER the current scan, in both independent native and VM APIs.
# columns: dt, enabled inputs, MW200..205, Q0..15.
TRACE = [
    (0, (), (0, 20, 0, 20, 0, 20), "0000000000001000"),
    (6000, (0,), (0, 20, 0, 20, 0, 20), "0001000000001000"),
    (0, (0,), (6, 20, 0, 20, 0, 20), "0001000010001100"),
    (10000, (), (6, 20, 0, 20, 0, 20), "0000000010001100"),
    (0, (), (6, 20, 0, 20, 0, 20), "0000000010001100"),
    (13000, (0,), (6, 20, 0, 20, 0, 20), "0001000010001100"),
    (1000, (0,), (19, 20, 0, 20, 0, 20), "0001000010001100"),
    (0, (0,), (20, 20, 0, 20, 0, 20), "1001000010001100"),
    (0, (), (0, 20, 0, 20, 0, 20), "0000000000001000"),
    (0, (1,), (0, 20, 0, 20, 0, 20), "0100100000001000"),
    (6000, (), (0, 20, 0, 20, 0, 20), "0100000000001000"),
    (0, (), (0, 20, 6, 20, 0, 20), "0100000001001010"),
    (10000, (1,), (0, 20, 6, 20, 0, 20), "0100100001001010"),
    (0, (1,), (0, 20, 6, 20, 0, 20), "0100100001001010"),
    (13000, (), (0, 20, 6, 20, 0, 20), "0100000001001010"),
    (1000, (), (0, 20, 19, 20, 0, 20), "0100000001001010"),
    (0, (), (0, 20, 20, 20, 0, 20), "0000000001001010"),
    (0, (1,), (0, 20, 0, 20, 0, 20), "0100100000001000"),
    (0, (1, 4), (0, 20, 0, 20, 0, 20), "0100100100001000"),
    (7000, (1, 2), (0, 20, 0, 20, 0, 20), "0100110000001000"),
    (0, (1, 2), (0, 20, 0, 20, 7, 20), "0100110000101001"),
    (999, (1, 2, 3), (0, 20, 0, 20, 7, 5), "0100111000110001"),
    (1, (1, 2, 3), (0, 20, 0, 20, 7, 5), "0100111000110001"),
    (0, (1, 2, 3), (0, 20, 0, 20, 7, 5), "0110111000110001"),
    (0, (1,), (0, 20, 0, 20, 0, 5), "0100100000010000"),
    (0, (1, 4), (0, 20, 0, 20, 0, 20), "0100100100001000"),
]
SOURCE = """#include <plc.hpp>
plc::Ton retained_on{0,1000,20,true,false};
plc::Tof retained_off{1,1000,20,true,false};
plc::Ton dynamic_on{2,1000,20,false,true};
void scan(){
 bool a=plc::input(0);bool b=plc::input(1);bool c=plc::input(2);
 bool set5=plc::input(3);bool set20=plc::input(4);
 if(set20){dynamic_on.set_preset(20);}else if(set5){dynamic_on.set_preset(5);}
 bool qa=retained_on.update(a);bool qb=retained_off.update(b);
 bool qc=dynamic_on.update(c);
 plc::write_word(200,retained_on.value());plc::write_word(201,retained_on.preset());
 plc::write_word(202,retained_off.value());plc::write_word(203,retained_off.preset());
 plc::write_word(204,dynamic_on.value());plc::write_word(205,dynamic_on.preset());
 plc::output(0,qa);plc::output(1,qb);plc::output(2,qc);
 plc::output(3,a);plc::output(4,b);plc::output(5,c);
 plc::output(6,set5);plc::output(7,set20);
 plc::output(8,retained_on.value()>=5);plc::output(9,retained_off.value()>=5);
 plc::output(10,dynamic_on.value()>=6);plc::output(11,dynamic_on.preset()==5);
 plc::output(12,dynamic_on.preset()==20);plc::output(13,retained_on.value()>0);
 plc::output(14,retained_off.value()>0);plc::output(15,dynamic_on.value()>0);
}
"""


class TimerOptionBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SAVED.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != SAVED_SHA:
            raise RuntimeError("The exact official saved fixture changed")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)

    def variant(self, edit, name="variant.smbp"):
        root = ET.fromstring(self.raw)
        edit(root)
        path = self.work / name
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        return path

    def small_program(self, kind="TON", base=1000, ret=True, dyn=False):
        return Program(
            [["BLK %TM0", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"]],
            {0: Timer(kind, 3 * base, base, ret, dyn)},
        )

    def check_trace(self, program):
        machine = Machine(program)
        for index, (dt, inputs, words, bits) in enumerate(TRACE):
            with self.subTest(frame=index):
                self.assertEqual(
                    machine.step({i: True for i in inputs}, dt),
                    [b == "1" for b in bits],
                )
                self.assertEqual(tuple(machine.words[200:206]), words)

    def test_exact_saved_fixture_import_preserves_three_separate_options(self):
        try:
            program = load_project(SAVED)
        except CompileError as exc:
            self.fail("The proven exact saved context must import: " + str(exc))
        self.assertEqual(
            program.timers,
            {
                0: Timer("TON", 20000, 1000, True, False),
                1: Timer("TOF", 20000, 1000, True, False),
                2: Timer("TON", 20000, 1000, False, True),
            },
        )
        self.check_trace(program)
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_cpp_xml_reverse_recompile_and_native_match_literal_oracle(self):
        source = self.work / "options.cpp"
        source.write_text(SOURCE)
        program = compile_source(source)
        frames = [
            {"dt_ms": dt, "inputs": {i: True for i in inputs}}
            for dt, inputs, _, _ in TRACE
        ]
        expected = [[b == "1" for b in bits] for _, _, _, bits in TRACE]
        self.check_trace(program)
        self.assertEqual(run_native(source, frames), expected)
        output = self.work / "options.smbp"
        try:
            write_project(program, SAVED, output)
        except CompileError as exc:
            self.fail(
                "Proven options must export under the actual Man21 template: "
                + str(exc)
            )
        actual = load_project(output)
        self.assertEqual(actual.timers, program.timers)
        self.check_trace(actual)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(actual))
        rebuilt = compile_source(reverse)
        self.assertEqual(rebuilt.timers, program.timers)
        self.check_trace(rebuilt)
        self.assertEqual(run_native(reverse, frames), expected)
        reexport = self.work / "reverse.smbp"
        write_project(rebuilt, SAVED, reexport)
        self.check_trace(load_project(reexport))
        root = ET.parse(output).getroot()
        self.assertEqual(root.findtext("ManagementLevel"), LEVEL)
        self.assertEqual(
            ET.tostring(root.find("HardwareConfiguration")),
            ET.tostring(ET.fromstring(self.raw).find("HardwareConfiguration")),
        )
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_each_verified_context_exports_independently(self):
        for kind, ret, dyn in (
            ("TON", True, False),
            ("TOF", True, False),
            ("TON", False, True),
        ):
            with self.subTest(kind=kind, ret=ret, dyn=dyn):
                p = self.small_program(kind, ret=ret, dyn=dyn)
                dest = self.work / "single.smbp"
                try:
                    write_project(p, SAVED, dest)
                except CompileError as exc:
                    self.fail("Verified independent context rejected: " + str(exc))
                self.assertEqual(load_project(dest).timers, p.timers)

    def test_documented_kind_base_and_option_combinations_serialize_and_run(self):
        # Literal native spellings/default, independent of production BASES.
        bases = {1: "OneMilliSeconds", 10: "TenMilliSeconds",
                 100: "OneHundredMilliSeconds", 1000: "OneSecond", 60000: None}
        # Each row is (elapsed bases AFTER scan, IN, V at scan, Q at scan).
        # These expected sequences are constants, not derived from TimerState.
        timelines = {
            "TON": [(1, True, 0, False), (1, True, 1, False),
                    (1, True, 2, False), (0, True, 3, True), (0, False, 0, False)],
            "TOF": [(0, True, 0, True), (1, False, 0, True),
                    (1, False, 1, True), (1, False, 2, True),
                    (0, False, 3, False), (0, True, 0, True)],
            "TP": [(1, True, 0, True), (1, True, 1, True),
                   (1, True, 2, True), (0, True, 3, False),
                   (0, True, 3, False), (0, False, 0, False), (0, True, 0, True)],
        }

        def check(program, rows, base):
            machine = Machine(program)
            for frame, (dt, enabled, value, done) in enumerate(rows):
                with self.subTest(frame=frame):
                    self.assertEqual(machine.step({0: enabled}, dt * base)[0], done)
                    self.assertEqual(tuple(machine.words[:2]), (value, 3))
                    self.assertEqual(machine.memory[1], done)

        for kind in ("TON", "TOF", "TP"):
            for ret, dyn in ((True, False), (False, True), (True, True)):
                for base, native_base in bases.items():
                    with self.subTest(kind=kind, base=base, ret=ret, dyn=dyn):
                        program = self.small_program(kind, base, ret, dyn)
                        dest = self.work / "combination.smbp"
                        dest.write_bytes(b"previous user output\n")
                        if kind == "TP" and ret:
                            # TP retention remains a genuine unsupported option,
                            # including a simultaneous dynamic flag at FL14.0.
                            with self.assertRaisesRegex(CompileError, "retentive TP is unsupported"):
                                write_project(program, SAVED, dest)
                            self.assertEqual(dest.read_bytes(), b"previous user output\n")
                            continue
                        program.rungs.insert(0, ["LD %I0.0", "ST %M0"])
                        program.rungs += [
                            ["LD %M1", "ST %Q0.0"],
                            ["LD 1", "[%MW0 := %TM0.V]"],
                            ["LD 1", "[%MW1 := %TM0.P]"],
                        ]
                        snapshot = copy.deepcopy(program.as_dict())
                        write_project(program, SAVED, dest)
                        actual = load_project(dest)
                        self.assertEqual(actual.timers, program.timers)
                        self.assertEqual(program.as_dict(), snapshot)
                        self.assertEqual(actual.metadata["official_editor"], "pending")
                        xml = ET.parse(dest)
                        timer = xml.find("./SoftwareConfiguration/Timers/TimerTM")
                        self.assertEqual(
                            tuple(timer.findtext(k) for k in ("Address", "Index", "Type", "Preset", "IsRetentive", "IsDynamicPreset")),
                            ("%TM0", "0", kind, "3", str(ret).lower(), str(dyn).lower()),
                        )
                        self.assertEqual(timer.findtext("Base"), native_base)
                        self.assertEqual(xml.findtext("ManagementLevel"), LEVEL)
                        self.assertEqual(
                            ET.tostring(xml.find("HardwareConfiguration")),
                            ET.tostring(ET.fromstring(self.raw).find("HardwareConfiguration")),
                        )
                        check(program, timelines[kind], base)
                        check(actual, timelines[kind], base)
                        # Seven type/flag combinations take the C++ path too;
                        # changing base alone is covered by all 35 VM/XML cases.
                        if base == 100:
                            reverse = self.work / "combination.cpp"
                            reverse.write_text(to_cpp(actual))
                            rebuilt = compile_source(reverse)
                            self.assertEqual(rebuilt.timers, program.timers)
                            check(rebuilt, timelines[kind], base)
                            frames = [{"dt_ms": dt * base, "inputs": {0: enabled}}
                                      for dt, enabled, _, _ in timelines[kind]]
                            self.assertEqual(
                                [bits[0] for bits in run_native(reverse, frames)],
                                [done for _, _, _, done in timelines[kind]],
                            )
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_actual_template_level_governs_not_program_metadata(self):
        # Hard-coded feature boundaries from O p55 and the pinned token map;
        # the production classifier is not used to choose expected success.
        level_cases = (
            ("FunctLevelMan6_0", False, False),   # FL3.3, disputed retention
            ("FunctLevelMan7_0", True, False),    # FL4.0
            ("FunctLevelMan17_0", True, False),   # FL11.0
            ("FunctLevelMan18_0", True, True),    # FL12.0
            ("FunctLevelMan20_0", True, True),    # FL13.0
            (LEVEL, True, True),                 # FL14.0
        )
        invalid_tokens = (None, "", "FunctLevelMan5_0", "FunctLevelMan22_0", LEVEL + " ", "21")
        for token, retention_allowed, dynamic_allowed in (
            *level_cases, *((token, False, False) for token in invalid_tokens)
        ):
            def edit(root):
                node = root.find("ManagementLevel")
                if token is None:
                    root.remove(node)
                else:
                    node.text = token

            template = self.variant(edit)
            original = template.read_bytes()
            for ret, dyn in ((True, False), (False, True), (True, True)):
                program = self.small_program(ret=ret, dyn=dyn)
                # A forged high evidence/level marker may neither admit a low
                # actual level nor block a valid actual token.
                program.metadata = {"ManagementLevel": LEVEL, "management_level": LEVEL,
                                    "official_editor": "verified"}
                snapshot = copy.deepcopy(program.as_dict())
                allowed = (not ret or retention_allowed) and (not dyn or dynamic_allowed)
                with self.subTest(token=token, ret=ret, dyn=dyn, allowed=allowed):
                    destination = self.work / "level.smbp"
                    destination.write_bytes(b"preserved")
                    if allowed:
                        write_project(program, template, destination)
                        actual = load_project(destination)
                        self.assertEqual(actual.timers, program.timers)
                        self.assertEqual(ET.parse(destination).findtext("ManagementLevel"), token)
                        self.assertEqual(actual.metadata["official_editor"], "pending")
                    else:
                        with self.assertRaises(CompileError):
                            write_project(program, template, destination)
                        self.assertEqual(destination.read_bytes(), b"preserved")
                    self.assertEqual(program.as_dict(), snapshot)
                    self.assertEqual(template.read_bytes(), original)
                    with self.assertRaises(CompileError):
                        write_project(program, template, template)
                    self.assertEqual(template.read_bytes(), original)
            # This ORIGINAL template still includes a dynamic TON as well as
            # retention: importing it requires BOTH features, unlike replacing
            # its program with only one retentive timer on export.
            with self.subTest(import_original_token=token):
                if retention_allowed and dynamic_allowed:
                    actual = load_project(template)
                    self.assertEqual(actual.timers, {
                        0: Timer("TON", 20000, 1000, True, False),
                        1: Timer("TOF", 20000, 1000, True, False),
                        2: Timer("TON", 20000, 1000, False, True),
                    })
                else:
                    with self.assertRaises(CompileError):
                        load_project(template)
                self.assertEqual(template.read_bytes(), original)
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_forged_metadata_cannot_block_verified_actual_level(self):
        program = self.small_program()
        program.metadata = {
            "ManagementLevel": "FunctLevelMan5_0",
            "official_editor": "pending",
        }
        destination = self.work / "real-level.smbp"
        try:
            write_project(program, SAVED, destination)
        except CompileError as exc:
            self.fail(
                "Metadata must not override the actual verified token: " + str(exc)
            )
        self.assertEqual(load_project(destination).timers, program.timers)

    def test_ordinary_modes_preserve_prior_level_and_base_behavior(self):
        for base in (1, 10, 100, 1000, 60000):
            with self.subTest(base=base):
                template = self.variant(
                    lambda r: setattr(
                        r.find("ManagementLevel"), "text", "FunctLevelMan5_0"
                    )
                )
                destination = self.work / "ordinary.smbp"
                program = self.small_program(base=base, ret=False)
                write_project(program, template, destination)
                self.assertEqual(load_project(destination).timers, program.timers)

    def test_legacy_low_level_fixture_stays_blocked(self):
        before = LEGACY.read_bytes()
        with self.assertRaisesRegex(
            CompileError, r"timer retention requires functional level >=4\.0.*3\.3/4\.0"
        ):
            load_project(LEGACY)
        self.assertEqual(LEGACY.read_bytes(), before)

    def test_bad_booleans_and_nested_or_duplicate_fields_stay_rejected(self):
        edits = []
        for value in ("True", "1", "true ", "false ", ""):
            edits.append(
                lambda r, v=value: setattr(
                    r.find("./SoftwareConfiguration/Timers/TimerTM/IsRetentive"),
                    "text",
                    v,
                )
            )
        edits.extend(
            (
                lambda r: r.find(
                    "./SoftwareConfiguration/Timers/TimerTM/IsRetentive"
                ).append(ET.Element("Value")),
                lambda r: r.find("./SoftwareConfiguration/Timers/TimerTM").append(
                    ET.Element("IsRetentive")
                ),
                lambda r: r.find("./SoftwareConfiguration/Timers").append(
                    copy.deepcopy(r.find("./SoftwareConfiguration/Timers/TimerTM"))
                ),
                lambda r: r.append(copy.deepcopy(r.find("ManagementLevel"))),
                lambda r: r.find("ManagementLevel").append(ET.Element("Value")),
            )
        )
        for index, edit in enumerate(edits):
            with self.subTest(case=index):
                malformed = self.variant(edit)
                before = malformed.read_bytes()
                with self.assertRaises(CompileError):
                    load_project(malformed)
                self.assertEqual(malformed.read_bytes(), before)

    def test_import_preserves_documented_config_changes_without_reinterpreting_graph(self):
        original = load_project(SAVED)
        for tag, value, expected in (
            ("Base", "TenMilliSeconds", Timer("TON", 200, 10, True, False)),
            ("Base", "OneHundredMilliSeconds", Timer("TON", 2000, 100, True, False)),
            ("IsDynamicPreset", "true", Timer("TON", 20000, 1000, True, True)),
        ):
            def edit(root):
                timer = root.find("./SoftwareConfiguration/Timers/TimerTM")
                node = timer.find(tag)
                if node is None:
                    node = ET.SubElement(timer, tag)
                node.text = value

            with self.subTest(tag=tag, value=value):
                path = self.variant(edit)
                before = path.read_bytes()
                actual = load_project(path)
                self.assertEqual(actual.timers[0], expected)
                self.assertEqual({i: t for i, t in actual.timers.items() if i != 0},
                                 {i: t for i, t in original.timers.items() if i != 0})
                self.assertEqual(actual.rungs, original.rungs)
                self.assertEqual(actual.metadata["official_editor"], "pending")
                self.assertEqual(
                    ET.tostring(ET.parse(path).find("./SoftwareConfiguration/Pous")),
                    ET.tostring(ET.fromstring(self.raw).find("./SoftwareConfiguration/Pous")),
                )
                self.assertEqual(path.read_bytes(), before)
        # Same unchanged program/ports, but retention is genuinely unavailable
        # for TP even at a sufficient actual level. A misspelled base is invalid.
        for tag, value in (("Type", "TP"), ("Base", "TenMilliSecond")):
            def edit(root):
                timer = root.find("./SoftwareConfiguration/Timers/TimerTM")
                node = timer.find(tag)
                if node is None:
                    node = ET.SubElement(timer, tag)
                node.text = value
            with self.subTest(invalid_tag=tag, invalid_value=value):
                path = self.variant(edit)
                before = path.read_bytes()
                with self.assertRaises(CompileError):
                    load_project(path)
                dest = self.work / "preserved_config.smbp"
                dest.write_bytes(b"keep config destination")
                # Export replaces the template program: test an actually
                # invalid candidate, not discarded old timer configuration.
                invalid = self.small_program(kind="TP") if tag == "Type" else self.small_program(base=2)
                with self.assertRaises(CompileError):
                    write_project(invalid, SAVED, dest)
                self.assertEqual(dest.read_bytes(), b"keep config destination")
                self.assertEqual(path.read_bytes(), before)
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_native_timer_identity_base_and_preset_boundaries_are_atomic(self):
        def program(index, base, preset):
            return Program(
                [[f"BLK %TM{index}", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"]],
                {index: Timer("TON", preset * base, base)},
            )
        for index, base, preset in ((0, 1, 0), (5, 1, 9999), (6, 10, 0), (254, 60000, 9999)):
            with self.subTest(valid=(index, base, preset)):
                p = program(index, base, preset)
                path = self.work / "boundary.smbp"
                write_project(p, SAVED, path)
                self.assertEqual(load_project(path).timers, p.timers)
        for index, base, preset in ((-1, 100, 3), (255, 100, 3), (6, 1, 3),
                                    (0, 2, 3), (0, 100, -1), (0, 100, 10000)):
            with self.subTest(invalid=(index, base, preset)):
                p = program(index, base, preset)
                snapshot = copy.deepcopy(p.as_dict())
                path = self.work / "invalid_boundary.smbp"
                path.write_bytes(b"keep boundary destination")
                with self.assertRaises(CompileError):
                    write_project(p, SAVED, path)
                self.assertEqual(path.read_bytes(), b"keep boundary destination")
                self.assertEqual(p.as_dict(), snapshot)
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_readonly_properties_and_invalid_presets_or_mode_types_fail_first(self):
        programs = [
            Program(
                [["LD 1", f"[%TM0.{prop} := 1]"]],
                {0: Timer("TON", 3000, 1000, True, False)},
            )
            for prop in ("V", "Q")
        ]
        programs += [self.small_program() for _ in range(5)]
        for p, timer in zip(
            programs[2:],
            (
                Timer("TON", -1000, 1000, True, False),
                Timer("TON", 10000000, 1000, True, False),
                Timer("TON", 3000, 1000, 1, False),
                Timer("TON", 3000, 1000, True, "false"),
                Timer("TP", 3000, 1000, True, False),
            ),
        ):
            p.timers[0] = timer
        for index, program in enumerate(programs):
            with self.subTest(case=index):
                with self.assertRaises(CompileError):
                    validate(program)
                destination = self.work / "invalid.smbp"
                destination.write_bytes(b"keep")
                with self.assertRaises(CompileError):
                    write_project(program, SAVED, destination)
                self.assertEqual(destination.read_bytes(), b"keep")

    def test_rejected_hardware_in_verified_option_template_is_preserved(self):
        template = self.variant(
            lambda r: setattr(
                r.find(
                    "./HardwareConfiguration/Plc/Cpu/PulseTrainOutputs/PulseTrainOutput/PtoObject/RefInput"
                ),
                "text",
                "%I0.0",
            )
        )
        before = template.read_bytes()
        dest = self.work / "hardware.smbp"
        dest.write_bytes(b"keep hardware destination")
        with self.assertRaises(CompileError):
            write_project(self.small_program(), template, dest)
        self.assertEqual(template.read_bytes(), before)
        self.assertEqual(dest.read_bytes(), b"keep hardware destination")

    def test_same_path_export_remains_rejected_without_mutating_template(self):
        destination = self.work / "in-place.smbp"
        destination.write_bytes(self.raw)
        with self.assertRaisesRegex(
            CompileError, "output must differ from the template"
        ):
            write_project(self.small_program(kind="TOF"), destination, destination)
        self.assertEqual(destination.read_bytes(), self.raw)
        self.assertEqual(SAVED.read_bytes(), self.raw)

    def test_verified_context_is_not_limited_to_observed_identity_or_preset(self):
        for kind, ret, dyn in (
            ("TON", True, False),
            ("TOF", True, False),
            ("TON", False, True),
        ):
            for preset in (0, 9999):
                with self.subTest(kind=kind, preset=preset):
                    p = Program(
                        [
                            [
                                "BLK %TM254",
                                "LD %M0",
                                "IN",
                                "OUT_BLK",
                                "LD Q",
                                "ST %M1",
                                "END_BLK",
                            ]
                        ],
                        {254: Timer(kind, preset * 1000, 1000, ret, dyn)},
                    )
                    dest = self.work / "sparse.smbp"
                    write_project(p, SAVED, dest)
                    self.assertEqual(load_project(dest).timers, p.timers)

    def test_pure_policy_requires_exact_actual_token_for_true_options(self):
        program = self.small_program()
        before = program.as_dict()
        for token in (None, False, 21, [], {}, "", LEVEL + " ", "FunctLevelMan22_0"):
            with self.subTest(token=token), self.assertRaises(CompileError):
                validate_options(program, token)
        validate_options(program, LEVEL)
        self.assertEqual(program.as_dict(), before)
        ordinary = self.small_program(ret=False)
        validate_options(ordinary)
        for malformed in (0, 1, "true", None):
            p = self.small_program()
            p.timers[0] = Timer("TON", 3000, 1000, malformed, False)
            with (
                self.subTest(flag=malformed),
                self.assertRaisesRegex(CompileError, "mode fields must be bool"),
            ):
                validate_options(p, LEVEL)


if __name__ == "__main__":
    unittest.main()
