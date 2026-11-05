import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def api(self, name):
        try:
            return importlib.import_module("m200." + name)
        except ImportError as exc:
            self.fail("Missing toolchain component: " + str(exc))

    def compile(self, body):
        source = self.work / "program.cpp"
        source.write_text("#include <plc.hpp>\n" + body)
        return self.api("frontend").compile_source(source)

    def run_program(self, program, frames):
        machine = self.api("il").Machine(program)
        return [
            machine.step(frame.get("inputs", {}), frame.get("dt_ms", 10))
            for frame in frames
        ]

    def rejects(self, body, code):
        with self.assertRaisesRegex(Exception, code):
            self.compile(body)

    def test_cli_compiles_without_claiming_official_validation(self):
        source = self.work / "source.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){plc::output(0, plc::input(0));}"
        )
        output = self.work / "out"
        r = subprocess.run(
            [sys.executable, "-m", "m200", "compile", str(source), "-o", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads((output / "report.json").read_text())
        self.assertEqual(report["validation"]["official_editor"], "pending")
        self.assertEqual(report["target"], "TM200CE40T")
        self.assertTrue((output / "program.il").exists())
        self.assertTrue((output / "program.audit.cpp").exists())
        mapping = json.loads((output / "source-map.json").read_text())
        self.assertTrue(any(r["origin"].get("line") == 2 for r in mapping["rungs"]))

    def test_digital_input_output_and_negation(self):
        p = self.compile(
            "void scan(){plc::output(0, plc::input(0) && !plc::input(1));}"
        )
        got = self.run_program(
            p, [{"inputs": {0: True}}, {"inputs": {0: True, 1: True}}, {}]
        )
        self.assertEqual([x[0] for x in got], [True, False, False])

    def test_assignment_order_toggle_and_branch_condition_snapshot(self):
        p = self.compile(
            "bool state=false; void scan(){if(!state){state=!state;plc::output(1,state);}else{state=false;plc::output(1,state);}plc::output(0,state);}"
        )
        got = self.run_program(p, [{}] * 4)
        self.assertEqual(
            [[x[0], x[1]] for x in got],
            [[True, True], [False, False], [True, True], [False, False]],
        )

    def test_output_reads_see_latest_assignment_in_same_scan(self):
        p = self.compile(
            "void scan(){plc::output(0,!plc::output_state(0));plc::output(1,plc::output_state(0));}"
        )
        got = self.run_program(p, [{}] * 3)
        self.assertEqual(
            [[x[0], x[1]] for x in got], [[True, True], [False, False], [True, True]]
        )

    def test_boolean_or_xor_equality_and_helper(self):
        p = self.compile(
            "bool gate(bool a,bool b){return (a||b) && (a!=b);} void scan(){plc::output(0,gate(plc::input(0),plc::input(1)));}"
        )
        got = self.run_program(
            p,
            [
                {"inputs": {0: a, 1: b}}
                for a, b in [(False, False), (False, True), (True, False), (True, True)]
            ],
        )
        self.assertEqual([x[0] for x in got], [False, True, True, False])

    def test_clock_has_documented_global_phase(self):
        p = self.compile("void scan(){plc::output(0,plc::clock_ms(1000));}")
        got = self.run_program(p, [{"dt_ms": 250}] * 5)
        self.assertEqual([x[0] for x in got], [False, False, True, True, False])

    def test_local_clock_library_resets_and_matches_native(self):
        p = self.compile(
            "plc::Clock blink{500};void scan(){bool q=blink.update(plc::input(0));plc::output(0,q);}"
        )
        frames = [{"inputs": {0: True}, "dt_ms": 100} for _ in range(14)]
        got = self.run_program(p, frames)
        self.assertEqual([x[0] for x in got], [False] * 5 + [True] * 6 + [False] * 3)
        self.assertEqual(
            self.api("native").run_native(self.work / "program.cpp", frames), got
        )
        reset_frames = [{"inputs": {0: True}, "dt_ms": 100} for _ in range(7)] + [
            {"inputs": {0: False}, "dt_ms": 100},
            {"inputs": {0: True}, "dt_ms": 100},
        ]
        self.assertEqual(
            [x[0] for x in self.run_program(p, reset_frames)][-2:], [False, False]
        )

    def test_rising_and_falling_edges_preserve_history(self):
        p = self.compile(
            "plc::RisingEdge rise; plc::FallingEdge fall; void scan(){bool r=rise.update(plc::input(0));bool f=fall.update(plc::input(0));plc::output(0,r);plc::output(1,f);}"
        )
        got = self.run_program(
            p, [{"inputs": {0: v}} for v in [False, True, True, False, False, True]]
        )
        self.assertEqual(
            [[x[0], x[1]] for x in got],
            [
                [False, False],
                [True, False],
                [False, False],
                [False, True],
                [False, False],
                [True, False],
            ],
        )

    def test_on_delay_and_reset(self):
        p = self.compile(
            "plc::Ton delay{20}; void scan(){bool q=delay.update(plc::input(0));plc::output(0,q);}"
        )
        got = self.run_program(
            p,
            [
                {"inputs": {0: v}, "dt_ms": 10}
                for v in [True, True, True, False, True, True, True]
            ],
        )
        self.assertEqual(
            [x[0] for x in got], [False, False, True, False, False, False, True]
        )

    def test_off_delay_and_pulse_timer(self):
        p = self.compile(
            "plc::Tof off{20}; plc::Pulse pulse{20}; void scan(){bool a=off.update(plc::input(0));bool b=pulse.update(plc::input(0));plc::output(0,a);plc::output(1,b);}"
        )
        got = self.run_program(
            p, [{"inputs": {0: v}} for v in [False, True, True, False, False, False]]
        )
        self.assertEqual(
            [[x[0], x[1]] for x in got],
            [
                [False, False],
                [True, True],
                [True, True],
                [True, False],
                [True, False],
                [False, False],
            ],
        )

    def test_native_original_il_and_reverse_agree(self):
        body = "bool state=false; plc::Ton timer{30}; plc::RisingEdge edge; void scan(){bool r=edge.update(plc::input(0));bool done=timer.update(plc::input(1));if(r){state=!state;}plc::output(0,state && !done);plc::output(1,plc::clock_ms(100));}"
        p = self.compile(body)
        import random

        rng = random.Random(47)
        frames = [
            {
                "inputs": {0: bool(rng.getrandbits(1)), 1: bool(rng.getrandbits(1))},
                "dt_ms": rng.choice([1, 5, 10, 20]),
            }
            for _ in range(200)
        ]
        expected = self.run_program(p, frames)
        native = self.api("native")
        self.assertEqual(native.run_native(self.work / "program.cpp", frames), expected)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(self.api("reverse").to_cpp(p))
        self.assertEqual(native.run_native(reverse, frames), expected)

    def test_recompiled_reverse_preserves_io_behavior(self):
        p = self.compile(
            "bool s=false; void scan(){if(plc::input(0)){s=!s;}plc::output(0,s);}"
        )
        reverse = self.work / "reverse.cpp"
        reverse.write_text(self.api("reverse").to_cpp(p))
        second = self.api("frontend").compile_source(reverse)
        frames = [{"inputs": {0: v}} for v in [False, True, True, False, True]]
        self.assertEqual(self.run_program(second, frames), self.run_program(p, frames))

    def test_rejects_unsupported_cpp_including_unused_declarations(self):
        for body in [
            "int value=0;void scan(){}",
            "struct Bad{int x;};void scan(){}",
            "void scan(){bool* p=nullptr;}",
            "void scan(){for(int i=0;i<2;i++){}}",
        ]:
            with self.subTest(body=body):
                self.rejects(body, "M200-E")

    def test_rejects_invalid_or_dynamic_io(self):
        for body in [
            "void scan(){plc::output(16,true);}",
            "void scan(){plc::output(0,plc::input(24));}",
            "void scan(){plc::output(plc::input(0),true);}",
        ]:
            with self.subTest(body=body):
                self.rejects(body, "M200-E")

    def test_rejects_unknown_calls_and_recursive_helpers(self):
        self.rejects("bool foreign();void scan(){plc::output(0,foreign());}", "M200-E")
        self.rejects(
            "bool f(bool a){return f(a);}void scan(){plc::output(0,f(true));}", "M200-E"
        )

    def test_rejects_conditional_or_duplicate_timer_update(self):
        for body in [
            "plc::Ton t{20};void scan(){if(plc::input(0)){bool q=t.update(true);}}",
            "plc::Ton t{20};void scan(){bool a=t.update(true);bool b=t.update(false);}",
            "plc::Ton t{20};void scan(){plc::output(0,plc::input(0)&&t.update(true));}",
        ]:
            with self.subTest(body=body):
                self.rejects(body, "M200-E")

    def test_rejects_unrepresentable_clock_and_timer_duration(self):
        self.rejects("void scan(){plc::output(0,plc::clock_ms(123));}", "M200-E")
        self.rejects(
            "plc::Ton t{999999999};void scan(){bool q=t.update(true);}", "M200-E"
        )

    def test_wrong_model_template_is_rejected(self):
        p = self.compile("void scan(){plc::output(0,true);}")
        template = self.work / "bad.smbp"
        template.write_text(
            "<ProjectDescriptor><HardwareConfiguration><Plc><Cpu><Reference>TM221CE16R</Reference></Cpu></Plc></HardwareConfiguration></ProjectDescriptor>"
        )
        with self.assertRaisesRegex(Exception, "M200-E"):
            self.api("project").write_project(p, template, self.work / "out.smbp")

    def test_project_roundtrip_preserves_hardware_and_reads_actual_il(self):
        p = self.compile("void scan(){plc::output(0,plc::input(0));}")
        project = self.api("project")
        destination = self.work / "out.smbp"
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", destination)
        import xml.etree.ElementTree as ET

        xml = ET.parse(destination)
        self.assertEqual(xml.findtext(".//Cpu/Name"), "SYNTHETIC_DO_NOT_DOWNLOAD")
        loaded = project.load_project(destination)
        self.assertEqual(loaded.rungs, p.rungs)
        self.assertEqual(self.run_program(loaded, [{"inputs": {0: True}}])[0][0], True)
        instruction = xml.find(".//InstructionLine")
        instruction.text = "JMP %L999"
        xml.write(destination, encoding="utf-8")
        with self.assertRaisesRegex(Exception, "M200-E"):
            project.load_project(destination)

    def test_il_graph_mismatch_is_rejected(self):
        p = self.compile("void scan(){plc::output(0,plc::input(0));}")
        project = self.api("project")
        dest = self.work / "out.smbp"
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        import xml.etree.ElementTree as ET

        tree = ET.parse(dest)
        tree.find(".//LadderEntity/Descriptor").text = "%I0.1"
        tree.write(dest)
        with self.assertRaisesRegex(Exception, "M200-E"):
            project.load_project(dest)

    def test_constant_outputs_have_real_address_contacts_and_stay_constant(self):
        p = self.compile("void scan(){plc::output(0,true);plc::output(1,false);}")
        dest = self.work / "constant.smbp"
        project = self.api("project")
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        import xml.etree.ElementTree as ET

        for contact in ET.parse(dest).findall(".//LadderEntity"):
            if contact.findtext("ElementType", "").endswith("Contact"):
                self.assertTrue(contact.findtext("Descriptor", "").startswith("%"))
        self.assertEqual(
            [
                [x[0], x[1]]
                for x in self.run_program(
                    project.load_project(dest), [{}, {"inputs": {0: True}}, {}]
                )
            ],
            [[True, False]] * 3,
        )

    def test_external_project_with_unmodeled_tasks_or_objects_is_rejected(self):
        import xml.etree.ElementTree as ET

        p = self.compile("void scan(){plc::output(0,true);}")
        project = self.api("project")
        dest = self.work / "unsupported.smbp"
        for tag in ["EventTasks", "UserFunctionPous", "UnknownSoftwareObject"]:
            project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
            tree = ET.parse(dest)
            ET.SubElement(tree.find("SoftwareConfiguration"), tag).append(
                ET.Element("Active")
            )
            tree.write(dest)
            with self.assertRaisesRegex(Exception, "M200-E"):
                project.load_project(dest)

    def test_unknown_il_fails_instead_of_being_ignored(self):
        model = self.api("model")
        with self.assertRaisesRegex(Exception, "M200-E"):
            self.api("il").Machine(model.Program(rungs=[["LD %I0.0", "MAGIC %Q0.0"]]))

    def test_memory_exhaustion_is_rejected(self):
        body = (
            "void scan(){"
            + "".join("bool b%d=plc::input(0);" % i for i in range(1100))
            + "plc::output(0,b1099);}"
        )
        self.rejects(body, "M200-E")

    def test_unused_helpers_and_attributes_are_still_checked(self):
        for body in [
            "bool unused(){return 7;}void scan(){}",
            "bool unused(int a){return a;}void scan(){}",
            "__attribute__((constructor)) void scan(){}",
        ]:
            with self.subTest(body=body):
                self.rejects(body, "M200-E")

    def test_first_scan_does_not_inherit_a_true_physical_output(self):
        p = self.compile("void scan(){if(plc::input(0)){plc::output(0,true);}}")
        machine = self.api("il").Machine(p)
        machine.outputs[0] = True
        self.assertFalse(machine.step({})[0])

    def test_mixed_ladder_rows_are_not_treated_as_series(self):
        import xml.etree.ElementTree as ET

        p = self.compile("void scan(){plc::output(0,plc::input(0));}")
        dest = self.work / "rows.smbp"
        project = self.api("project")
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        tree = ET.parse(dest)
        tree.find(".//LadderEntity/Row").text = "1"
        tree.write(dest)
        with self.assertRaisesRegex(Exception, "M200-E"):
            project.load_project(dest)

    def test_timer_project_and_reverse_match_native(self):
        p = self.compile(
            "plc::Ton t{25};void scan(){bool done=t.update(plc::input(0));plc::output(0,done);}"
        )
        dest = self.work / "timers.smbp"
        project = self.api("project")
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        loaded = project.load_project(dest)
        frames = [
            {"inputs": {0: v}, "dt_ms": 5} for v in [True] * 8 + [False] + [True] * 8
        ]
        self.assertEqual(self.run_program(loaded, frames), self.run_program(p, frames))
        reverse = self.work / "back.cpp"
        reverse.write_text(self.api("reverse").to_cpp(loaded))
        self.assertEqual(
            self.api("native").run_native(reverse, frames), self.run_program(p, frames)
        )

    def test_malformed_program_json_has_a_clean_diagnostic(self):
        path = self.work / "bad.json"
        path.write_text(
            json.dumps(
                {
                    "format": "m200-cpp-il-v1",
                    "target": "TM200CE40T",
                    "rungs": ["not a rung"],
                    "timers": {},
                }
            )
        )
        r = subprocess.run(
            [sys.executable, "-m", "m200", "inspect", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("M200-E", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_failed_template_export_keeps_previous_output_intact(self):
        source = self.work / "a.cpp"
        source.write_text("#include <plc.hpp>\nvoid scan(){plc::output(0,true);}")
        out = self.work / "compiled"
        command = [sys.executable, "-m", "m200", "compile", str(source), "-o", str(out)]
        first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        source.write_text("#include <plc.hpp>\nvoid scan(){plc::output(0,false);}")
        bad = self.work / "bad-template.smbp"
        bad.write_text("<wrong/>")
        second = subprocess.run(
            command + ["--template", str(bad)], cwd=ROOT, capture_output=True, text=True
        )
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)

    def test_rebuild_without_template_removes_stale_owned_project(self):
        source = self.work / "a.cpp"
        source.write_text("#include <plc.hpp>\nvoid scan(){plc::output(0,true);}")
        out = self.work / "compiled"
        command = [sys.executable, "-m", "m200", "compile", str(source), "-o", str(out)]
        first = subprocess.run(
            command + ["--template", str(ROOT / "tests/fixtures/synthetic.smbp")],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((out / "program.smbp").exists())
        second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse((out / "program.smbp").exists())

    def test_seventh_sub_10ms_timer_is_rejected(self):
        declarations = "".join("plc::Ton t%d{1};" % i for i in range(7))
        updates = "".join("bool d%d=t%d.update(true);" % (i, i) for i in range(7))
        self.rejects(declarations + "void scan(){" + updates + "}", "M200-E")

    def test_foreign_header_declarations_are_not_silently_ignored(self):
        (self.work / "other.hpp").write_text("inline int hidden_state=42;")
        self.rejects('#include "other.hpp"\nvoid scan(){}', "M200-E")

    def test_invalid_json_shapes_and_trace_have_clean_errors(self):
        for value in [
            [],
            {
                "format": "m200-cpp-il-v1",
                "target": "TM200CE40T",
                "rungs": [123],
                "timers": {},
            },
            {
                "format": "m200-cpp-il-v1",
                "target": "TM200CE40T",
                "rungs": [],
                "timers": {"0": {"kind": "TON", "milliseconds": "oops"}},
            },
        ]:
            path = self.work / "invalid.json"
            path.write_text(json.dumps(value))
            r = subprocess.run(
                [sys.executable, "-m", "m200", "inspect", str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("M200-E", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        source = self.work / "x.cpp"
        source.write_text("#include <plc.hpp>\nvoid scan(){}")
        trace = self.work / "trace.json"
        trace.write_text("[42]")
        r = subprocess.run(
            [sys.executable, "-m", "m200", "check", str(source), "--trace", str(trace)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("M200-E", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_unverified_timer_base_serialization_is_refused(self):
        decl = "".join("plc::Ton t%d{20};" % i for i in range(7))
        calls = "".join("bool b%d=t%d.update(true);" % (i, i) for i in range(7))
        p = self.compile(decl + "void scan(){" + calls + "}")
        with self.assertRaisesRegex(Exception, "M200-E"):
            self.api("project").write_project(
                p, ROOT / "tests/fixtures/synthetic.smbp", self.work / "out.smbp"
            )

    def test_section_order_is_validated_on_external_projects(self):
        import xml.etree.ElementTree as ET

        p = self.compile("void scan(){plc::output(0,true);}")
        dest = self.work / "section.smbp"
        project = self.api("project")
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        tree = ET.parse(dest)
        tree.find(".//ProgramOrganizationUnits/SectionNumber").text = "9"
        tree.write(dest)
        with self.assertRaisesRegex(Exception, "M200-E"):
            project.load_project(dest)

    def test_clock_zero_period_is_rejected(self):
        self.rejects("plc::Clock c{0};void scan(){bool v=c.update(true);}", "M200-E")

    def test_certification_cannot_succeed_without_the_official_editor(self):
        r = subprocess.run(
            [sys.executable, "-m", "m200", "certify"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pending", r.stderr)

    def test_macro_expanded_declarations_cannot_hide_executable_code(self):
        self.rejects(
            "#define HIDDEN __attribute__((constructor)) void before_scan(){plc::output(0,true);}\nHIDDEN\nvoid scan(){}",
            "M200-E",
        )
        self.rejects(
            "#define HIDDEN int unsupported=42;\nHIDDEN\nvoid scan(){}", "M200-E"
        )
        (self.work / "macros.hpp").write_text(
            "#define HIDDEN __attribute__((constructor)) void before_scan(){plc::output(0,true);}\n"
        )
        self.rejects('#include "macros.hpp"\nHIDDEN\nvoid scan(){}', "M200-E")

    def test_normal_macro_definitions_are_validated_as_cpp(self):
        p = self.compile(
            "#define STATE bool state=false;\nSTATE\n#define SCAN void scan(){state=!state;plc::output(0,state);}\nSCAN"
        )
        got = self.run_program(p, [{}] * 3)
        self.assertEqual([v[0] for v in got], [True, False, True])

    def test_unknown_active_configuration_and_real_io_entry_names_fail_closed(self):
        import xml.etree.ElementTree as ET

        p = self.compile("void scan(){plc::output(0,true);}")
        project = self.api("project")
        dest = self.work / "config.smbp"
        for parent, xml in [
            (
                "SoftwareConfiguration",
                "<MessageBlocks><UnknownActiveObject>true</UnknownActiveObject></MessageBlocks>",
            ),
            (
                "HardwareConfiguration/Plc/Cpu",
                "<UnknownExecutionObject><Enabled>true</Enabled></UnknownExecutionObject>",
            ),
            (
                "HardwareConfiguration/Plc/Cpu",
                "<DigitalInputs><DiscretInput><Address>%I0.0</Address><Index>0</Index><RunStop>true</RunStop></DiscretInput></DigitalInputs>",
            ),
            (
                "HardwareConfiguration/Plc/Cpu",
                "<HighSpeedCounters><HighSpeedCounter><Address>%HSC0</Address><Index>0</Index><ReflexOutputs><ReflexOutput><Index>0</Index><Activated>true</Activated></ReflexOutput></ReflexOutputs></HighSpeedCounter></HighSpeedCounters>",
            ),
        ]:
            with self.subTest(xml=xml):
                project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
                tree = ET.parse(dest)
                tree.find(parent).append(ET.fromstring(xml))
                tree.write(dest)
                with self.assertRaisesRegex(Exception, "M200-E"):
                    project.load_project(dest)
                with self.assertRaisesRegex(Exception, "M200-E"):
                    project.write_project(p, dest, self.work / "reexport.smbp")

    def test_duplicate_xml_singletons_cannot_hide_program_data(self):
        import xml.etree.ElementTree as ET

        p = self.compile(
            "plc::Ton t{20};void scan(){bool done=t.update(plc::input(0));plc::output(0,done);}"
        )
        project = self.api("project")
        dest = self.work / "duplicates.smbp"
        cases = [
            (
                "SoftwareConfiguration",
                "<Pous><UnknownActiveTask>true</UnknownActiveTask></Pous>",
            ),
            (
                ".//RungEntity",
                "<InstructionLines><InstructionLineEntity><InstructionLine>JMP %L999</InstructionLine></InstructionLineEntity></InstructionLines>",
            ),
            (".//TimerTM", "<Preset>9999</Preset>"),
            (".//LadderEntity", "<Column>9</Column>"),
            (
                ".//InstructionLineEntity",
                "<InstructionLine>JMP %L999</InstructionLine>",
            ),
        ]
        for parent, xml in cases:
            with self.subTest(parent=parent):
                project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
                tree = ET.parse(dest)
                tree.find(parent).append(ET.fromstring(xml))
                tree.write(dest)
                with self.assertRaisesRegex(Exception, "M200-E"):
                    project.load_project(dest)

    def test_unmodeled_xml_attributes_are_rejected(self):
        import xml.etree.ElementTree as ET

        p = self.compile("void scan(){plc::output(0,true);}")
        project = self.api("project")
        dest = self.work / "attributes.smbp"
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
        tree = ET.parse(dest)
        tree.find(".//RungEntity").set(
            "{http://www.w3.org/2001/XMLSchema-instance}type", "UnknownExecutableRung"
        )
        tree.write(dest)
        with self.assertRaisesRegex(Exception, "M200-E"):
            project.load_project(dest)

    def test_rebuild_does_not_delete_a_file_absent_from_old_manifest(self):
        source = self.work / "a.cpp"
        source.write_text("#include <plc.hpp>\nvoid scan(){}")
        out = self.work / "out"
        cmd = [sys.executable, "-m", "m200", "compile", str(source), "-o", str(out)]
        first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        manual = out / "program.smbp"
        manual.write_bytes(b"MY MANUAL PROJECT")
        again = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(again.returncode, 1)
        self.assertEqual(manual.read_bytes(), b"MY MANUAL PROJECT")

    def test_decompile_rejects_source_output_and_sidecar_aliases(self):
        project = self.api("project")
        p = self.compile("void scan(){plc::output(0,true);}")
        source = self.work / "original.smbp"
        project.write_project(p, ROOT / "tests/fixtures/synthetic.smbp", source)
        original = source.read_bytes()

        def run(dest):
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "m200",
                    "decompile",
                    str(source),
                    "-o",
                    str(dest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(run(source).returncode, 1)
        self.assertEqual(source.read_bytes(), original)
        alias = self.work / "alias.cpp"
        alias.symlink_to(source)
        self.assertEqual(run(alias).returncode, 1)
        self.assertEqual(source.read_bytes(), original)
        # The destination's sidecar is the input path in this case.
        source2 = self.work / "audit.cpp.configuration.smbp"
        source2.write_bytes(original)
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "m200",
                "decompile",
                str(source2),
                "-o",
                str(self.work / "audit.cpp"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1)
        self.assertEqual(source2.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
