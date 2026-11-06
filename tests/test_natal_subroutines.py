"""Portable regressions for G06 local returns and G08 graphs inside SRs.

Local compiler/SDK checks do not qualify editor, simulator or physical behavior.
"""

import copy
from dataclasses import fields
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from batch_acceptance.native_probe import observe_native
from m200.boolean_banks import BooleanConfig
from m200.counters import Counter
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import needed, normalize
from m200.model import CompileError, Program, SubroutineDefinition, Timer
from m200.project import load_project, write_project
from m200.registers import RegisterConfig
from m200.reverse import to_cpp
from m200.rtc import RtcConfig, ScheduleConfig
from m200.sequences import DrumCam, DrumConfig, ShiftBitRegisterConfig, StepCounterConfig
from m200.subroutine_contexts import context_view


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
MINIMAL = """#include <plc.hpp>
plc::StepCounter s{0};void body(){s.update_pins(2,false,plc::input(1),false);}
plc::Subroutine sr{0,body,"sequence",2};void scan(){sr.call(plc::input(0));}
"""
COMPOSED = """#include <plc.hpp>
plc::ShiftBitRegister shift{0};
plc::StepCounter step{1};
plc::Drum drum{2,3,
    plc::DrumCam{0,plc::DrumOutput::Memory,200,2}};
void sequence_body() {
    shift.update_pins(2,false,plc::input(1),false);
    step.update_pins(2,false,plc::input(2),false);
    drum.update_pins(2,false,plc::input(3));
}
plc::Subroutine sequences{7,sequence_body,"shared sequences",42};
void scan() {
    if (plc::system(13)) { shift.set_bit(4,true); }
    sequences.call(plc::input(0));
    sequences.call(plc::input(0));
    plc::output(0,shift.bit(5));
    plc::output(1,step.bit(1));
    plc::output(2,drum.step()==1);
    plc::output(3,plc::read_m(200));
    plc::write_word(0,drum.step());
}
"""


def literal_return(opcode, digit):
    return Program(
        rungs=[["LD 1", "[%MW0:=1]"], ["LD %M20", "SR0"], ["LD 1", "[%MW1:=30]"]],
        subroutines={0: SubroutineDefinition(0, "literal-return", 2,
            [["LD " + str(digit), opcode], ["LD 1", "[%MW0:=9]"]])},
    )


def drum_F(labelled=False):
    body = ["BLK %DR2", "LD %M10", "R", "LD %I0.3", "U",
            "OUT_BLK", "LD F", "ST %M201", "END_BLK"]
    if labelled:
        body.insert(0, "%L63:")
    return Program(
        rungs=[["LD %I0.0", "ST %M10"], ["LD %M20", "SR0"],
               ["LD 1", "[%MW0:=%DR2.S]"], ["LD %M201", "ST %Q0.0"]],
        subroutines={0: SubroutineDefinition(0, "Drum F", 2, [body])},
        drums={2: DrumConfig(3, [DrumCam(0, "%M200", 2)])},
    )


class NatalSubroutineRegressions(unittest.TestCase):
    def roundtrip(self, program, folder):
        before = copy.deepcopy(program.as_dict())
        project = folder / "generated.smbp"
        write_project(program, MEMORY, project)
        imported = load_project(project)
        reverse = folder / "actual_reverse.cpp"
        reverse.write_text(to_cpp(imported))
        rebuilt = compile_source(reverse)
        target = folder / "rebuilt.smbp"
        write_project(rebuilt, MEMORY, target)
        readback = load_project(target)
        self.assertEqual(program.as_dict(), before)
        for candidate in (imported, rebuilt, readback):
            for name in ("shift_bit_registers", "step_counters", "drums"):
                self.assertEqual(getattr(candidate, name), getattr(program, name))
            self.assertEqual(
                {k: (s.number, s.name, s.section_number) for k, s in candidate.subroutines.items()},
                {k: (s.number, s.name, s.section_number) for k, s in program.subroutines.items()},
            )
        return (program, imported, rebuilt, readback), reverse, project

    def assert_trace(self, programs, frames, expected, *, seed=False, project_SC=False):
        for program in programs:
            machine = Machine(program)
            for frame, wanted in zip(frames, expected):
                if seed:
                    machine.memory[20] = True  # Explicit external public input.
                bits = machine.step(frame["inputs"], frame.get("dt_ms", 10))
                mask = sum(1 << i for i, value in enumerate(bits) if value)
                if project_SC:
                    mask = int(machine.read("%SC0.1", {})) + 2 * int(machine.read("%SC0.2", {}))
                self.assertEqual(mask, wanted["output_mask"])
                self.assertEqual(
                    {key: machine.words[int(key)] for key in wanted.get("words", {})},
                    wanted.get("words", {}),
                )

    def native_source(self, source, folder, *, seed=False, SC=None):
        if not seed and SC is None:
            return source
        wrapper = folder / (source.stem + "_observed.cpp")
        before = "plc::write_m(20,true);" if seed else ""
        after = "" if SC is None else (
            "plc::output(0," + SC + ".bit(1));plc::output(1," + SC + ".bit(2));"
        )
        wrapper.write_text('#define scan natal_product_scan\n#include ' + json.dumps(str(source))
            + '\n#undef scan\nvoid scan(){' + before + 'natal_product_scan();' + after + '}\n')
        return wrapper

    def assert_native(self, source, frames, expected, folder):
        words = sorted({int(key) for row in expected for key in row.get("words", {})})
        self.assertEqual(observe_native(source, frames, words, folder, ROOT / "sdk"), expected)

    def test_literal_local_returns_export_reverse_and_resume_master(self):
        for opcode, digit, value in (("ENDC", 1, 1), ("ENDC", 0, 9), ("ENDCN", 0, 1), ("ENDCN", 1, 9)):
            with self.subTest(opcode=opcode, digit=digit), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                p = literal_return(opcode, digit)
                n = normalize(p)
                self.assertFalse(needed(context_view(n, n.subroutines[0]), _local_return=True))
                source = folder / "original.cpp"
                condition = str(bool(digit)).lower()
                if opcode == "ENDCN":
                    condition = "!" + condition
                source.write_text('#include <plc.hpp>\nvoid leaf(){if(' + condition
                    + ')return;plc::write_word(0,9);}\nplc::Subroutine sr{0,leaf,"literal-return",2};\n'
                    + 'void scan(){plc::write_word(0,1);sr.call(plc::read_m(20));plc::write_word(1,30);}\n')
                programs, reverse, _ = self.roundtrip(p, folder)
                frames = [{"inputs": {}, "dt_ms": 10}]
                expected = [{"output_mask": 0, "words": {"0": value, "1": 30}}]
                self.assert_trace((*programs, n, compile_source(source)), frames, expected, seed=True)
                for name, cpp in (("original", source), ("reverse", reverse)):
                    self.assert_native(self.native_source(cpp, folder, seed=True), frames, expected, folder / name)

    def test_minimal_step_counter_SR_keeps_partial_CU_row_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / "minimal.cpp"
            source.write_text(MINIMAL)
            programs, reverse, project = self.roundtrip(compile_source(source), folder)
            self.assertEqual(set(programs[0].step_counters), {0})
            block = next(r for r in ET.parse(project).findall(".//Subroutine/Rungs/RungEntity")
                if any(e.findtext("InstructionLine") == "BLK %SC0" for e in r.findall("InstructionLines/InstructionLineEntity")))
            contact = next(e for e in block.findall("LadderElements/LadderEntity")
                if e.findtext("ElementType") == "NormalContact")
            self.assertEqual(contact.findtext("Row"), "1")
            frames = [{"inputs": {"0": bool(a), "1": bool(b)}}
                for a, b in ((0, 1), (1, 1), (1, 1), (0, 0), (1, 0), (1, 1))]
            expected = [{"output_mask": mask, "words": {}} for mask in (0, 1, 1, 1, 1, 2)]
            self.assert_trace(programs, frames, expected, project_SC=True)
            # Observe public SC bits after the unchanged minimal scan; this is
            # test instrumentation, not a claim that the source writes Q.
            for name, cpp, resource in (("original", source, "s"), ("reverse", reverse, "sc_0")):
                self.assert_native(self.native_source(cpp, folder, SC=resource), frames, expected, folder / name)

    def test_composed_SBR_SC_Drum_in_repeated_SR_share_config_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / "composed.cpp"
            source.write_text(COMPOSED)
            programs, reverse, _ = self.roundtrip(compile_source(source), folder)
            self.assertEqual(set(programs[0].shift_bit_registers), {0})
            self.assertEqual(set(programs[0].step_counters), {1})
            self.assertEqual(programs[0].drums, {2: DrumConfig(3, [DrumCam(0, "%M200", 2)])})
            frames = [{"inputs": dict(zip(("0", "1", "2", "3"), map(bool, levels)))}
                for levels in ((0, 1, 1, 1), (1, 1, 1, 1), (1, 1, 1, 1), (0, 0, 0, 0), (1, 0, 0, 0), (1, 1, 1, 1))]
            expected = [{"output_mask": mask, "words": {"0": step}}
                for mask, step in ((0, 0), (15, 1), (15, 1), (15, 1), (15, 1), (0, 2))]
            self.assert_trace(programs, frames, expected)
            for name, cpp in (("original", source), ("reverse", reverse)):
                self.assert_native(cpp, frames, expected, folder / name)

    def test_Drum_F_graph_inside_labelled_and_unlabelled_SR(self):
        for labelled in (False, True):
            with self.subTest(labelled=labelled), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                source = folder / "original.cpp"
                source.write_text('''#include <plc.hpp>
plc::Drum drum{2,3,plc::DrumCam{0,plc::DrumOutput::Memory,200,2}};
void body(){drum.update(plc::read_m(10),plc::input(3));plc::write_m(201,drum.full());}
plc::Subroutine sr{0,body,"Drum F",2};
void scan(){plc::write_m(10,plc::input(0));sr.call(plc::read_m(20));plc::write_word(0,drum.step());plc::output(0,plc::read_m(201));}
''')
                programs, reverse, _ = self.roundtrip(drum_F(labelled), folder)
                frames = [{"inputs": inputs} for inputs in ({"0": True}, {}, {"3": True}, {"3": True}, {}, {"3": True})]
                expected = [{"output_mask": full, "words": {"0": step}}
                    for step, full in ((0, 0), (0, 0), (1, 0), (1, 0), (1, 0), (2, 1))]
                self.assert_trace(programs, frames, expected, seed=True)
                for name, cpp in (("original", source), ("reverse", reverse)):
                    self.assert_native(self.native_source(cpp, folder, seed=True), frames, expected, folder / name)

    def test_malformed_SR_sequence_and_return_graphs_refuse_atomically(self):
        def entity(tree, kind):
            return next(e for e in tree.findall(".//Subroutine/Rungs/RungEntity/LadderElements/LadderEntity")
                if e.findtext("ElementType") == kind)

        def rung(tree, block):
            return next(r for r in tree.findall(".//Subroutine/Rungs/RungEntity")
                if any(e.findtext("InstructionLine") == "BLK " + block for e in r.findall("InstructionLines/InstructionLineEntity")))

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / "composed.cpp"
            source.write_text(COMPOSED)
            composed = compile_source(source)
            cases = [
                (composed, lambda q: entity(q, "ShiftBitRegister").find("ElementType").__setattr__("text", "Counter")),
                (composed, lambda q: entity(q, "Drum").find("Descriptor").__setattr__("text", "%DR7")),
                (composed, lambda q: next(e for e in rung(q, "%SC1").findall("LadderElements/LadderEntity") if e.findtext("ElementType") == "NormalContact").find("Row").__setattr__("text", "0")),
                (composed, lambda q: rung(q, "%SBR0").remove(rung(q, "%SBR0").find("LadderElements"))),
                (composed, lambda q: q.find("SoftwareConfiguration/StepCounters").remove(q.find("SoftwareConfiguration/StepCounters/StepCounter"))),
                (literal_return("ENDC", 1), lambda q: entity(q, "End").find("ElementType").__setattr__("text", "EndCn")),
                (drum_F(), lambda q: entity(q, "Drum").find("ChosenConnection").__setattr__("text", "Left")),
            ]
            for index, (program, mutate) in enumerate(cases):
                with self.subTest(index=index):
                    valid = folder / (str(index) + ".smbp")
                    write_project(program, MEMORY, valid)
                    xml = ET.parse(valid).getroot()
                    mutate(xml)
                    forged = folder / (str(index) + "-forged.smbp")
                    raw = ET.tostring(xml, encoding="utf-8")
                    forged.write_bytes(raw)
                    with self.assertRaises(CompileError):
                        load_project(forged)
                    self.assertEqual(forged.read_bytes(), raw)
                    before, template = copy.deepcopy(program.as_dict()), MEMORY.read_bytes()
                    for exists in (False, True):
                        dest = folder / (str(index) + "-" + str(exists) + "-out.smbp")
                        if exists:
                            dest.write_bytes(b"destination sentinel")

                        def tamper_staged(path):
                            staged = ET.parse(path).getroot()
                            mutate(staged)
                            Path(path).write_bytes(ET.tostring(staged, encoding="utf-8"))
                            return load_project(path)

                        with patch("m200.project.load_project", side_effect=tamper_staged), self.assertRaises(CompileError):
                            write_project(program, MEMORY, dest)
                        self.assertEqual(dest.exists(), exists)
                        if exists:
                            self.assertEqual(dest.read_bytes(), b"destination sentinel")
                        self.assertEqual(program.as_dict(), before)
                        self.assertEqual(MEMORY.read_bytes(), template)
                        self.assertFalse(list(folder.glob(".m200-candidate-*")))

    def test_mixed_SR_normalization_keeps_typed_resource_configs(self):
        canonical = [["BLK %TM4", "LD %I0.0", "IN", "END_BLK"], ["LD %I0.1", "ENDC"]]
        p = Program(
            rungs=[["LD %I0.0", "ORN %I0.0", "[%MW0:=1]"], ["LD %M20", "SR0"], ["LD %M20", "SR63"]],
            subroutines={0: SubroutineDefinition(0, "canonical", 2, canonical),
                63: SubroutineDefinition(63, "literal", 42, [["LD 0", "ENDC"], ["LD 1", "ST %M500"]])},
            timers={4: Timer("TON", 20, 10)}, counters={2: Counter(3)},
            registers={1: RegisterConfig("Lifo")}, constants={23: 0x1234},
            shift_bit_registers={0: ShiftBitRegisterConfig()}, step_counters={1: StepCounterConfig()},
            drums={2: DrumConfig(3, [DrumCam(0, "%M200", 2)])}, rtcs={0: RtcConfig(1, 1, 2026)},
            schedules={15: ScheduleConfig("%M300", start_hour=12, end_hour=13)},
            boolean=BooleanConfig(input_image_stable=False),
        )
        before = copy.deepcopy(p.as_dict())
        n = normalize(p)
        self.assertIsNot(n, p)
        self.assertEqual(p.as_dict(), before)
        self.assertEqual(n.subroutines[0].rungs, canonical)
        self.assertNotEqual(n.subroutines[63].rungs, p.subroutines[63].rungs)
        for field in fields(p):
            if field.name not in {"rungs", "symbols", "metadata", "subroutines"}:
                self.assertEqual(getattr(n, field.name), getattr(p, field.name), field.name)


if __name__ == "__main__":
    unittest.main()
