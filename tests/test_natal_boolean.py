"""Portable G01 regressions; local SDK/VM checks do not qualify PLC lifecycle."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT)]

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.rtc import RtcClock
from parallel_semantics.adapters import source_pipeline
from parallel_semantics.g0108_adapters import cycles, run_sdk


class NatalBooleanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="natal-boolean-")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def folder(self, name):
        path = self.work / name
        path.mkdir()
        return path

    def compile(self, body):
        path = self.work / "source.cpp"
        path.write_text("#include <plc.hpp>\n" + body)
        return compile_source(path)

    def both_cycles(self, request, expected):
        for engine in ("vm", "sdk"):
            with self.subTest(engine=engine):
                actual = cycles(engine=engine, request=request, repo=ROOT,
                                work=self.folder(engine))
                self.assertEqual(actual, expected)

    def test_balanced_push_if_pop_loop_keeps_literal_results(self):
        request = {
            "source": """#include <plc.hpp>
void scan(){plc::BooleanStack s;plc::write_word(0,0);
 if(plc::input(0)){s.push(true);plc::output(0,s.pop());}
 else{s.push(false);plc::output(0,s.pop());}
 plc::i16 i=0;while(i<4){s.push(plc::input(0));
 if(s.pop()){plc::inc_word(0);}i=plc::add_i16(i,1);}}
""",
            "frames": [{"inputs": {0: value}, "dt_ms": 0} for value in (False, True)],
            "observe": {"words": [0], "bits": [0]},
        }
        expected = [{"words_u16": [0], "bits": [False]},
                    {"words_u16": [4], "bits": [True]}]
        for engine in ("vm", "sdk"):
            with self.subTest(engine=engine):
                actual = source_pipeline(engine=engine, request=request, repo=ROOT,
                                         work=self.folder(engine))
                self.assertEqual(actual, expected)

    def test_stack_arms_and_short_circuit_mutations_cannot_leak(self):
        bodies = [
            "if(plc::input(0)){s.push(true);}",
            "if(plc::input(0)){s.push(true);}else{plc::output(0,s.pop());}",
            "s.push(true);bool a=plc::input(0)&&s.pop();plc::output(0,a);",
            "s.push(true);bool a=plc::input(0)||s.pop();plc::output(0,a);",
            "s.push(true);if(plc::input(0)){return;}plc::output(0,s.pop());",
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "BooleanStack"):
                self.compile("void scan(){plc::BooleanStack s;" + body + "}")

    def test_S13_belongs_to_first_explicit_master_interval(self):
        request = {
            "source": "#include <plc.hpp>\nvoid scan(){plc::output(0,plc::system(13));}",
            "bits": [0],
            "events": [{"master": {}}, {"scan": {}}, {"scan": {}},
                       {"master": {}}, {"scan": {}}, {"scan": {}},
                       {"master": {}}, {"scan": {}}],
        }
        self.both_cycles(request, [{"bits": [v]} for v in (True, True, False, False, False)])

    def test_nonmaster_calls_do_not_reapply_schedule_or_repeat_S13_init(self):
        request = {
            "source": """#include <plc.hpp>
plc::Schedule schedule{0,1,0,1,1,12,0,31,12,13,0,127};
void scan(){if(plc::input(0)){plc::output(0,false);}
 plc::output(1,plc::output_state(0));}
""",
            "clock": [2026, 11, 9, 12, 30, 0],
            "bits": [0, 1],
            "events": [{"master": {}}, {"scan": {0: True}}, {"scan": {}},
                       {"master": {}}, {"scan": {}}],
        }
        self.both_cycles(request, [{"bits": row} for row in
                                  ([False, False], [False, False], [True, True])])

    def test_IO_module_channel_aliases_trap_before_provider(self):
        for address, valid in (("%IW01.0", False), ("%IW1.00", False), ("%IW1.0", True)):
            with self.subTest(address=address):
                work = self.folder(address.replace("%", "").replace(".", "_"))
                source = work / "case.cpp"
                source.write_text("#include <plc.hpp>\nplc::BooleanWord image{" +
                                  json.dumps(address) + "};\nvoid scan(){plc::output(0,plc::read_bit(" +
                                  json.dumps(address + ":X15") + "));}\n")
                if valid:
                    def provider(action, name, value):
                        self.assertEqual((action, name), ("read_word", "%IW1.0"))
                        return 32768
                    machine = Machine(compile_source(source), boolean_runtime=provider)
                    self.assertTrue(machine.step(dt_ms=0)[0])
                else:
                    with self.assertRaisesRegex(CompileError, "canonical"):
                        compile_source(source)
                harness = """#include <cstdio>
#define PLC_NATIVE
#include SOURCE
unsigned short provider(const char*,bool,unsigned short){
 std::fputs("PROVIDER\\n",stderr);std::fflush(stderr);return 32768;}
int main(){plc::detail::boolean_word_hook=provider;
 plc::detail::begin_scan();scan();std::printf("%d\\n",plc::output_state(0)?1:0);}
""".replace("SOURCE", json.dumps(str(source)))
                if valid:
                    self.assertEqual(run_sdk(ROOT, work, harness), [[1]])
                else:
                    with self.assertRaisesRegex(AssertionError, "Boolean SDK harness exit"):
                        run_sdk(ROOT, work, harness)
                execution = json.loads((work / "execution.json").read_text())
                self.assertEqual("PROVIDER" in execution["stderr"], valid)
                self.assertEqual(execution["returncode"] == 0, valid)

    def test_legacy_S050_project_reverse_keeps_RTC_semantics(self):
        program = Program([["LD %I0.00", "ST %S050"]])
        original = copy.deepcopy(program.rungs)
        template = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
        first = self.work / "first.smbp"
        write_project(program, template, first)
        imported = load_project(first)
        self.assertEqual(imported.rungs, original)
        source = self.work / "reverse.cpp"
        source.write_text(to_cpp(imported))
        self.assertNotIn('"%S050"', source.read_text())
        rebuilt = compile_source(source)
        second = self.work / "second.smbp"
        write_project(rebuilt, template, second)
        values = [False, True, True, False]
        expected = [[int(v), 0, 0] for v in values]
        for stage in (program, imported, rebuilt, load_project(second)):
            with self.subTest(rungs=stage.rungs):
                machine = Machine(stage, rtc=RtcClock(2026, 11, 6, 12, 34, 56, valid=True))
                actual = []
                for value in values:
                    machine.step({0: value}, dt_ms=0)
                    actual.append([int(machine.read("%S" + str(n), {})) for n in (50, 51, 52)])
                self.assertEqual(actual, expected)
        lines = ["#include <cstdio>", "#define PLC_NATIVE", "#include " + json.dumps(str(source)),
                 "int main(){plc::detail::rtc_seed(plc::detail::Calendar{6,11,2026,12,34,56});"]
        for value in values:
            lines.append("plc::detail::inputs[0]=" + ("true" if value else "false") + ";" +
                         'plc::detail::begin_scan();scan();std::printf("%d %d %d\\n",' +
                         'plc::system(50)?1:0,plc::system(51)?1:0,plc::system(52)?1:0);' +
                         "plc::detail::first_scan=false;")
        lines.append("}")
        self.assertEqual(run_sdk(ROOT, self.folder("legacy-sdk"), "\n".join(lines)), expected)
        self.assertEqual(program.rungs, original)
        with self.assertRaisesRegex(CompileError, "canonical"):
            self.compile('void scan(){plc::write_bit("%S050",true);}')

    def test_R_S018_clears_only_when_its_accumulator_is_true(self):
        for operand in ("%S18", "%S018"):
            for active in (False, True):
                with self.subTest(operand=operand, active=active):
                    program = Program([["LD " + str(int(active)), "R " + operand]])
                    original = copy.deepcopy(program.rungs)
                    machine = Machine(program)
                    machine.arithmetic.overflow = True
                    machine.step(dt_ms=0)
                    self.assertEqual(machine.read("%S18", {}), not active)
                    self.assertEqual(machine.read("%S018", {}), not active)
                    self.assertEqual(program.rungs, original)

    def test_alias_cannot_bypass_clear_only_action_permissions(self):
        for operand in ("%S18", "%S018"):
            for action in ("S", "ST", "STN"):
                with self.subTest(operand=operand, action=action):
                    with self.assertRaisesRegex(CompileError, "permission|only"):
                        validate(Program([["LD 1", action + " " + operand]]))


if __name__ == "__main__":
    unittest.main()
