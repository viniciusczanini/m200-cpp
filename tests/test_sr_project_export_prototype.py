"""Genuine copied-pipeline SR export; no real product/editor claim."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError, Program, SubroutineDefinition
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.subroutine_graph import graphics, parse_call, read_graph, write_graph

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MEMORY = FIXTURES / "official_tm200ce40t_memory.smbp"
M20 = FIXTURES / "official_tm200ce40t_subroutine_sr0_m20.smbp"


def native_call():
    root = ET.parse(M20).getroot()
    return next(
        r
        for r in root.findall(
            "SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity"
        )
        if any(
            x.findtext("InstructionLine", "").startswith("SR")
            for x in r.find("InstructionLines")
        )
    )


def simple(number=63):
    return Program(
        rungs=[
            ["LD %I0.0", "ST %M20"],
            ["LD %M20", "SR" + str(number)],
            ["LD %M21", "ST %Q0.0"],
        ],
        subroutines={
            number: SubroutineDefinition(
                number,
                "distinct native name 🚦",
                2,
                [["LD %I0.1", "ST %M21"]],
                [{"file": "leaf.cpp", "line": 40}],
            )
        },
    )


class SubroutineProjectExport(unittest.TestCase):
    def refuse(self, program, mutate=None):
        before = copy.deepcopy(program.as_dict())
        with tempfile.TemporaryDirectory() as d:
            template = Path(d) / "template.smbp"
            root = ET.parse(MEMORY).getroot()
            if mutate:
                mutate(root)
            template.write_bytes(ET.tostring(root, encoding="utf-8"))
            original = template.read_bytes()
            for exists in (False, True):
                dest = Path(d) / ("existing.smbp" if exists else "absent.smbp")
                if exists:
                    dest.write_bytes(b"destination sentinel")
                expected = dest.read_bytes() if exists else None
                with self.assertRaises(CompileError):
                    write_project(program, template, dest)
                self.assertEqual(dest.read_bytes() if dest.exists() else None, expected)
                self.assertEqual(template.read_bytes(), original)
                self.assertEqual(program.as_dict(), before)
                self.assertFalse(list(Path(d).glob(".m200-candidate-*")))

    def test_actual_M20_fixture_and_literal_geometry_bind(self):
        self.assertEqual(
            hashlib.sha256(M20.read_bytes()).hexdigest(),
            "b850091e79c974dec8be14de36694428091d5a82ad6257a6ddfe5f1d882cc692",
        )
        call = read_graph(native_call())
        self.assertEqual((call.number, call.predicate), (0, "%M20"))
        imported = load_project(M20)
        self.assertIn(["LD %M20", "SR0"], imported.rungs)
        self.assertEqual(
            graphics(["LD %M20", "SR63"]),
            [("NormalContact", "%M20", 0, 0, "Left, Right")]
            + [("Line", "", 0, i, "Left, Right") for i in range(1, 10)]
            + [("Jump", "SR63", 0, 10, "Left")],
        )

    def test_M_domain_all_SR_ids_and_closed_predicate_negatives(self):
        for number in range(64):
            for predicate in ("%M0", "%M20", "%M1023", "%I0.0"):
                call = parse_call(["LD " + predicate, "SR" + str(number)])
                self.assertEqual((call.number, call.predicate), (number, predicate))
        for first in (
            "LD %M1024",
            "LD %M00",
            "LD %M-1",
            "LD %I0.1",
            "LDN %M20",
            "LD 1",
            "LD %Q0.0",
            "LD %MW0:X0",
            "LD %M２０",
        ):
            with self.subTest(first=first), self.assertRaises(CompileError):
                parse_call([first, "SR0"])
        for last in ("SR64", "SR00", "SR-1", "SRtrue", "SR１"):
            with self.subTest(last=last), self.assertRaises(CompileError):
                parse_call(["LD %M20", last])

    def test_present_native_graph_stays_authoritative_and_writer_atomic(self):
        for change in (
            lambda q: (
                q.find("LadderElements")[0]
                .find("Descriptor")
                .__setattr__("text", "%M21")
            ),
            lambda q: (
                q.find("LadderElements")[0]
                .find("ChosenConnection")
                .__setattr__("text", "Left")
            ),
            lambda q: q.find("LadderElements")[1].find("Row").__setattr__("text", "1"),
            lambda q: q.find("LadderElements")[1].set("unknown", "true"),
            lambda q: q.find("LadderElements").append(
                copy.deepcopy(q.find("LadderElements")[0])
            ),
        ):
            node = native_call()
            change(node)
            original = ET.tostring(node)
            with self.assertRaises(CompileError):
                read_graph(node)
            with self.assertRaises(CompileError):
                write_graph(["LD %M20", "SR0"], node)
            self.assertEqual(ET.tostring(node), original)

    def test_export_preserves_identity_leaf_and_literal_behavior(self):
        p = simple()
        original = copy.deepcopy(p.as_dict())
        template = MEMORY.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "candidate.smbp"
            write_project(p, MEMORY, target)
            loaded = load_project(target)
            s = loaded.subroutines[63]
            self.assertEqual(
                (s.number, s.name, s.section_number, s.rungs),
                (63, "distinct native name 🚦", 2, [["LD %I0.1", "ST %M21"]]),
            )
            self.assertNotEqual(s.origins, p.subroutines[63].origins)
            machine = Machine(loaded)
            for inputs, expected in [
                ({0: False, 1: True}, False),
                ({0: True, 1: True}, True),
                ({0: False, 1: False}, True),
                ({0: True, 1: False}, False),
            ]:
                self.assertEqual(machine.step(inputs, 17)[0], expected)
            self.assertEqual(machine.now, 68)
            root = ET.parse(target).getroot()
            self.assertEqual(
                ET.tostring(root.find("HardwareConfiguration")),
                ET.tostring(ET.fromstring(template).find("HardwareConfiguration")),
            )
            self.assertEqual(
                root.findtext(
                    "SoftwareConfiguration/Pous/ProgramOrganizationUnits/SectionNumber"
                ),
                "0",
            )
        self.assertEqual(p.as_dict(), original)
        self.assertEqual(MEMORY.read_bytes(), template)

    def test_genuine_Cpp_SMBP_reverse_recompile_native_literal_trace(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source.cpp"
            source.write_text("""#include <plc.hpp>
void leaf(){if(plc::input(1))plc::write_word(5,42);plc::output(1,plc::input(1));}
plc::Subroutine sr{63,leaf,"CPP identity",2};
void scan(){plc::write_word(5,7);plc::output(1,false);sr.call(plc::input(0)&&!plc::input(3));plc::output(0,plc::read_word(5)==42);}
""")
            p = compile_source(source)
            target = Path(d) / "export.smbp"
            write_project(p, MEMORY, target)
            imported = load_project(target)
            reverse = Path(d) / "reverse.cpp"
            reverse.write_text(to_cpp(imported))
            rebuilt = compile_source(reverse)
            frames = [
                {"inputs": {"0": a, "1": b, "3": c}, "dt_ms": 13}
                for a, b, c in ((0, 1, 0), (1, 1, 0), (1, 0, 0), (1, 1, 1), (0, 0, 0))
            ]
            literal = [
                [False, False],
                [True, True],
                [False, False],
                [False, False],
                [False, False],
            ]
            literal_words = [7, 42, 7, 7, 7]
            for program in (p, imported, rebuilt):
                machine = Machine(program)
                for frame, expected, word in zip(frames, literal, literal_words):
                    self.assertEqual(machine.step(frame["inputs"], 13)[:2], expected)
                    self.assertEqual(machine.words[5], word)
                self.assertEqual(machine.now, 65)
            for cpp in (source, reverse):
                self.assertEqual([row[:2] for row in run_native(cpp, frames)], literal)
            self.assertEqual(rebuilt.subroutines[63].name, "CPP identity")

    def test_actual_template_authority_capacity_and_ordinary_section(self):
        p = simple()
        p.metadata.update(
            {"functional_level": "FunctLevelMan21_0", "cpu": "TM200CE40T"}
        )
        for path, value in (
            ("ManagementLevel", "FunctLevelMan20_0"),
            ("ManagementLevel", "unknown"),
            ("HardwareConfiguration/Plc/Cpu/Reference", "TM221CE40T"),
            (
                "HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/SubroutinesMax",
                "63",
            ),
            ("SoftwareConfiguration/Pous/ProgramOrganizationUnits/SectionNumber", "1"),
        ):
            self.refuse(
                p,
                lambda q, path=path, value=value: q.find(path).__setattr__(
                    "text", value
                ),
            )

    def test_section_multi_leaf_and_nonserializable_body_refuse_atomically(self):
        for section in (0, 1, 42):
            p = simple()
            p.subroutines[63].section_number = section
            self.refuse(p)
        p = simple()
        p.subroutines[0] = SubroutineDefinition(0, "second", 3, [["END"]])
        self.refuse(p)
        for body in (
            [["LD 1", "ST %M1"]],
            [["LD %M0", "OR %M1", "ST %M2"]],
            [["LD %M0", "STN %M2"]],
            [["LD %M0", "END"]],
        ):
            p = simple()
            p.subroutines[63].rungs = body
            p.subroutines[63].origins = []
            self.refuse(p)

    def test_sole_and_conditional_END_in_leaf_stay_current_context(self):
        for terminal, second in ((["END"], True), (["LD %I0.1", "ENDC"], True)):
            p = simple()
            p.subroutines[63].rungs = [terminal, ["LD %I0.0", "ST %M21"]]
            p.subroutines[63].origins = []
            with tempfile.TemporaryDirectory() as d:
                dest = Path(d) / "end.smbp"
                write_project(p, MEMORY, dest)
                loaded = load_project(dest)
                m = Machine(loaded)
                m.step({0: True, 1: second}, 10)
                self.assertFalse(m.memory[21])
                self.assertFalse(m.outputs[0])
                self.assertEqual(loaded.subroutines[63].rungs, p.subroutines[63].rungs)
        p = simple()
        p.subroutines[63].rungs = [["LD %I0.1", "ENDCN"]]
        p.subroutines[63].origins = []
        self.refuse(p)

    def test_all_context_allocation_covers_high_callee_only_words(self):
        p = simple()
        p.subroutines[63].rungs = [
            ["LD %I0.1", "[%MW7999:=42]"],
            ["LD %I0.1", "ST %M1023"],
        ]
        p.subroutines[63].origins = []
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "bound.smbp"
            write_project(p, MEMORY, dest)
            q = ET.parse(dest).getroot()
            self.assertEqual(
                q.findtext(
                    "SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"
                ),
                "8000",
            )
            m = Machine(load_project(dest))
            m.step({0: True, 1: True}, 10)
            self.assertEqual(m.words[7999], 42)
            self.assertTrue(m.memory[1023])

    def test_active_template_refusal_preserves_absent_and_existing_output(self):
        for p in (simple(), Program(rungs=[["LD %M0", "ST %M1"]])):
            original = copy.deepcopy(p.as_dict())
            raw = M20.read_bytes()
            with tempfile.TemporaryDirectory() as d:
                for existing in (False, True):
                    dest = Path(d) / str(existing) / "result.smbp"
                    if existing:
                        dest.parent.mkdir()
                        dest.write_bytes(b"sentinel")
                    with self.assertRaises(CompileError):
                        write_project(p, M20, dest)
                    self.assertEqual(
                        dest.read_bytes() if dest.exists() else None,
                        b"sentinel" if existing else None,
                    )
                    self.assertEqual(dest.parent.exists(), existing)
            self.assertEqual(p.as_dict(), original)
            self.assertEqual(M20.read_bytes(), raw)

    def test_full_callee_roundtrip_semantics_checked_before_replace(self):
        real_loader = load_project
        for field in ("number", "name", "section_number", "rungs", "keys"):

            def tamper(path):
                p = real_loader(path)
                s = p.subroutines[63]
                if field == "keys":
                    p.subroutines[0] = SubroutineDefinition(0, "extra", 3, [["END"]])
                elif field == "number":
                    s.number = 0
                elif field == "name":
                    s.name = "changed"
                elif field == "section_number":
                    s.section_number = 42
                else:
                    s.rungs = [["END"]]
                return p

            with self.subTest(field=field), tempfile.TemporaryDirectory() as d:
                dest = Path(d) / "out.smbp"
                dest.write_bytes(b"sentinel")
                with (
                    patch("m200.project.load_project", side_effect=tamper),
                    self.assertRaises(CompileError),
                ):
                    write_project(simple(), MEMORY, dest)
                self.assertEqual(dest.read_bytes(), b"sentinel")
                self.assertFalse(list(Path(d).glob(".m200-candidate-*")))


if __name__ == "__main__":
    unittest.main()
