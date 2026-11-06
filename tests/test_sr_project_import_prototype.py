"""Native SR import contracts; fixture authority and G06 replacement behavior."""

import copy
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
from m200.model import CompileError, Program, SubroutineDefinition
from m200.project import load_project, write_project
from m200.il import Machine
from m200.reverse import to_cpp
from m200.frontend import compile_source
from m200.native import run_native

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CASES = [
    ("sr0", 0, "49438bcbed59cde889547869d8c033f377dfb7e60153136a57cb48e135b0e21a"),
    ("sr63", 63, "ff05369c686e8bc1887612afdbfcfd57d24e0e4e1e51d8d2b2b443824a2fa652"),
]


def source(label):
    return FIXTURES / ("official_tm200ce40t_subroutine_" + label + ".smbp")


def callee(root):
    return root.find("SoftwareConfiguration/Subroutines/Subroutine")


def body(root):
    return callee(root).find("Rungs")


def master(root):
    return root.find("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs")


class NativeProjectImport(unittest.TestCase):
    def mutated(self, label, change, folder):
        q = E.parse(source(label)).getroot()
        change(q)
        p = Path(folder) / "mutated.smbp"
        p.write_bytes(E.tostring(q, encoding="utf-8", xml_declaration=True))
        return p

    def refuse(self, change, label="sr0"):
        with tempfile.TemporaryDirectory() as d:
            p = self.mutated(label, change, d)
            raw = p.read_bytes()
            with self.assertRaises(CompileError):
                load_project(p)
            self.assertEqual(p.read_bytes(), raw)

    def test_exact_native_fixtures_import_separate_contexts_and_origins(self):
        for label, number, digest in CASES:
            raw = source(label).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            p = load_project(source(label))
            self.assertEqual(source(label).read_bytes(), raw)
            self.assertEqual(len(p.rungs), 10)
            self.assertEqual(set(p.subroutines), {number})
            s = p.subroutines[number]
            self.assertEqual((s.number, s.section_number), (number, 2))
            self.assertEqual(len(s.rungs), 3 if number == 0 else 8)
            self.assertEqual(len(s.origins), len(s.rungs))
            self.assertEqual(len(p.metadata["rung_origins"]), 10)
            self.assertTrue(
                all("SR" + str(number) in x["generated"] for x in s.origins)
            )
            self.assertEqual(Program.from_dict(p.as_dict()).as_dict(), p.as_dict())
            self.assertNotIn("SR" + str(number), [x for r in s.rungs for x in r])

    def test_native_IL_literal_behavior_and_reverse_pipeline(self):
        for label, number, _ in CASES:
            p = load_project(source(label))
            m = Machine(p)
            controls = [(0, 0), (1, 0), (1, 1), (0, 1)]
            expected0 = [
                ([30, 0, 10], [0, 0, 1, 0]),
                ([30, 1, 20], [1, 1, 1, 0]),
                ([30, 1, 20], [1, 1, 1, 0]),
                ([30, 0, 10], [0, 0, 1, 0]),
            ]
            expected63 = [
                ([30, 0, 10], [0, 0, 1, 0]),
                ([30, 2, 25], [1, 1, 1, 1]),
                ([30, 1, 20], [1, 1, 1, 0]),
                ([30, 0, 10], [0, 0, 1, 0]),
            ]
            expected = expected0 if number == 0 else expected63
            for (a, b), (words, bits) in zip(controls, expected):
                self.assertEqual(
                    m.step({"0": a, "1": b}, 13)[:4], list(map(bool, bits))
                )
                self.assertEqual(m.words[:3], words)
            self.assertEqual(m.now, 52)
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "reverse.cpp"
                f.write_text(to_cpp(p))
                q = compile_source(f)
                self.assertEqual(
                    (q.subroutines[number].name, q.subroutines[number].section_number),
                    (p.subroutines[number].name, 2),
                )
                m = Machine(q)
                for (a, b), (words, bits) in zip(controls, expected):
                    self.assertEqual(
                        m.step({"0": a, "1": b}, 13)[:4], list(map(bool, bits))
                    )
                    self.assertEqual(m.words[:3], words)
                self.assertEqual(
                    [
                        x[:4]
                        for x in run_native(
                            f,
                            [
                                {"inputs": {"0": a, "1": b}, "dt_ms": 13}
                                for a, b in controls
                            ],
                        )
                    ],
                    [list(map(bool, b)) for w, b in expected],
                )

    def test_call_target_graph_and_predicate_must_match_even_when_IL_selected(self):
        def call(q):
            return master(q)[5]

        for tag, value in [
            ("Descriptor", "SR63"),
            ("ElementType", "End"),
            ("ChosenConnection", "Left, Right"),
            ("Column", "09"),
        ]:

            def change(q, tag=tag, value=value):
                n = call(q)
                n.find("IsLadderSelected").text = "false"
                n.find("LadderElements")[-1].find(tag).text = value

            self.refuse(change)
        self.refuse(lambda q: call(q).find("LadderElements").clear())

        def m_contact(q):
            n = call(q)
            n.find(
                "InstructionLines/InstructionLineEntity/InstructionLine"
            ).text = "LDN %M20"
            n.find("LadderElements")[0].find("Descriptor").text = "%M20"
            n.find("MainComment").text = "official M binding approved=true"

        self.refuse(m_contact)

    def test_callee_parallel_graph_cannot_disagree_or_hide_active_fields(self):
        for change in [
            lambda r: setattr(r.find("IsLadderSelected"), "text", "false"),
            lambda r: None,
        ]:

            def bad(q, change=change):
                r = body(q)[0]
                change(r)
                r.find("LadderElements")[-1].find(
                    "OperationExpression"
                ).text = "%MW0 := 99"

            self.refuse(bad)
        for path, tag, value in [
            ("LadderElements/LadderEntity", "Descriptor", "%I0.2"),
            ("LadderElements/LadderEntity", "ChosenConnection", "Left, Right"),
        ]:
            self.refuse(
                lambda q, path=path, tag=tag, value=value: setattr(
                    body(q)[0].find(path + "/" + tag), "text", value
                )
            )
        self.refuse(
            lambda q: E.SubElement(
                body(q)[0].find("LadderElements")[-1], "Unknown"
            ).__setattr__("text", "active")
        )

    def test_invalid_callee_address_resource_or_nested_call_never_imports_opaque(self):
        for line in ["[%MW8000:=1]", "LD %TM0.Q", "SR0", "CAL SR0"]:
            self.refuse(
                lambda q, line=line: setattr(
                    body(q)[0].find(
                        "InstructionLines/InstructionLineEntity/InstructionLine"
                    ),
                    "text",
                    line,
                )
            )

    def test_callee_only_word_and_bit_extent_is_checked_against_actual_allocation(self):
        def word(q):
            n = body(q)[0]
            n.find("InstructionLines")[-1].find(
                "InstructionLine"
            ).text = "[%MW3000:=20]"
            n.find("LadderElements")[-1].find(
                "OperationExpression"
            ).text = "%MW3000 := 20"

        def bit(q):
            n = body(q)[2]
            n.find("InstructionLines")[-1].find("InstructionLine").text = "ST %M700"
            n.find("LadderElements")[-1].find("Descriptor").text = "%M700"

        self.refuse(word)
        self.refuse(bit)

    def test_actual_level_capacity_section_and_scheduler_authority(self):
        self.refuse(
            lambda q: setattr(q.find("ManagementLevel"), "text", "FunctLevelMan20_0")
        )
        self.refuse(
            lambda q: setattr(
                q.find(
                    "HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/SubroutinesMax"
                ),
                "text",
                "0",
            )
        )
        self.refuse(lambda q: setattr(callee(q).find("SectionNumber"), "text", "0"))
        self.refuse(
            lambda q: E.SubElement(callee(q), "IsFastTask").__setattr__("text", "false")
        )
        self.refuse(
            lambda q: E.SubElement(
                q.find("SoftwareConfiguration/UserFunctionPous"), "Unknown"
            )
        )
        self.refuse(
            lambda q: setattr(
                q.find("SoftwareConfiguration/MastTask/UsePeriodScanMode"),
                "text",
                "true",
            )
        )

    def test_independent_incoming_identity_metadata_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.mutated(
                "sr63",
                lambda q: (
                    setattr(callee(q).find("Name"), "text", "Native independente"),
                    setattr(callee(q).find("SectionNumber"), "text", "42"),
                ),
                d,
            )
            value = load_project(p).subroutines[63]
            self.assertEqual(
                (value.name, value.section_number), ("Native independente", 42)
            )

    def test_imported_program_reexports_preserving_context_identity_and_behavior(self):
        p = load_project(source("sr0"))
        p.metadata["native_M_contact_approved"] = True
        original = copy.deepcopy(p.as_dict())
        template = source("sr0").read_bytes()
        with tempfile.TemporaryDirectory() as d:
            for exists in (False, True):
                dest = Path(d) / ("existing.smbp" if exists else "absent.smbp")
                if exists:
                    dest.write_bytes(b"original sentinel")
                write_project(p, source("sr0"), dest)
                loaded = load_project(dest)
                self.assertEqual(set(loaded.subroutines), {0})
                for field in ("number", "name", "section_number"):
                    self.assertEqual(getattr(loaded.subroutines[0], field), getattr(p.subroutines[0], field))
                machine = Machine(loaded)
                for controls, words in (((False, False), [30, 0, 10]),
                                        ((True, False), [30, 1, 20])):
                    machine.step({0: controls[0], 1: controls[1]}, 13)
                    self.assertEqual(machine.words[:3], words)
                reverse = Path(d) / "reverse.cpp"
                reverse.write_text(to_cpp(loaded))
                rebuilt = compile_source(reverse)
                machine = Machine(rebuilt)
                machine.step({0: True}, 13)
                self.assertEqual(machine.words[:3], [30, 1, 20])
                self.assertFalse(any(Path(d).glob(".m200-candidate-*")))
        self.assertEqual(p.as_dict(), original)
        self.assertEqual(source("sr0").read_bytes(), template)

    def test_no_SR_legacy_memory_stays_v1(self):
        p = load_project(FIXTURES / "official_tm200ce40t_memory.smbp")
        self.assertEqual(p.subroutines, {})
        self.assertEqual(p.as_dict()["format"], "m200-cpp-il-v1")

    def test_valid_callee_only_extent_uses_union_and_exact_manual_boundary(self):
        def change(q):
            n = body(q)[0]
            n.find("InstructionLines")[-1].find(
                "InstructionLine"
            ).text = "[%MW1500:=20]"
            n.find("LadderElements")[-1].find(
                "OperationExpression"
            ).text = "%MW1500 := 20"
            q.find(
                "SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"
            ).text = "1501"

        with tempfile.TemporaryDirectory() as d:
            p = load_project(self.mutated("sr0", change, d))
            m = Machine(p)
            m.step({"0": True}, 10)
            self.assertEqual(m.words[1500], 20)
            self.assertEqual(m.words[1499], 0)
            self.assertEqual(m.words[1501], 0)

    def test_decompile_sidecar_and_artifacts_include_all_contexts_without_SMBP(self):
        from m200.cli import decompile_file, build_artifacts

        for label, number, _ in CASES:
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "native.cpp"
                original = source(label).read_bytes()
                decompile_file(source(label), f)
                self.assertEqual(
                    Path(str(f) + ".configuration.smbp").read_bytes(), original
                )
                p = compile_source(f)
                out = Path(d) / "build"
                build_artifacts(p, out)
                ir = json.loads((out / "program.m200.json").read_text())
                mapping = json.loads((out / "source-map.json").read_text())
                self.assertEqual(ir["format"], "m200-cpp-il-v2")
                self.assertEqual(set(ir["subroutines"]), {str(number)})
                self.assertEqual(
                    mapping["subroutines"][str(number)]["section_number"], 2
                )
                self.assertIn(
                    "FREE POU SR" + str(number), (out / "program.il").read_text()
                )
                self.assertFalse((out / "program.smbp").exists())
                self.assertEqual(source(label).read_bytes(), original)

    def test_multiple_independent_SR_wrappers_import_and_execute_in_order(self):
        def extra(q):
            c = copy.deepcopy(callee(q))
            c.find("Number").text = "63"
            c.find("Name").text = "second"
            c.find("SectionNumber").text = "3"
            first = c.find("Rungs")[0]
            first.find("InstructionLines")[-1].find("InstructionLine").text = "[%MW0:=31]"
            first.find("LadderElements")[-1].find("OperationExpression").text = "%MW0 := 31"
            q.find("SoftwareConfiguration/Subroutines").append(c)
            call = copy.deepcopy(master(q)[5])
            call.find("InstructionLines")[-1].find("InstructionLine").text = "SR63"
            call.find("LadderElements")[-1].find("Descriptor").text = "SR63"
            master(q).insert(6, call)

        with tempfile.TemporaryDirectory() as d:
            path = self.mutated("sr0", extra, d)
            raw = path.read_bytes()
            p = load_project(path)
            self.assertEqual(set(p.subroutines), {0, 63})
            self.assertEqual((p.subroutines[63].name, p.subroutines[63].section_number), ("second", 3))
            self.assertIn(["LD %I0.0", "SR63"], p.rungs)
            reverse = Path(d) / "reverse.cpp"
            reverse.write_text(to_cpp(p))
            rebuilt = compile_source(reverse)
            for program in (p, Program.from_dict(p.as_dict()), rebuilt):
                machine = Machine(program)
                for enabled, expected in ((False, [30, 0, 10]), (True, [30, 1, 31])):
                    machine.step({0: enabled}, 13)
                    self.assertEqual(machine.words[:3], expected)
            self.assertEqual(path.read_bytes(), raw)

    def test_multiple_master_POUs_and_mismatched_return_graph_remain_refused(self):
        # Multiple SR wrappers are supported; additional Master POUs are not.
        def extra_master(q):
            pous = q.find("SoftwareConfiguration/Pous")
            extra = copy.deepcopy(pous[0])
            extra.find("SectionNumber").text = "1"
            extra.find("Name").text = "unrequested master"
            pous.append(extra)

        self.refuse(extra_master)

        def end(q):
            n = body(q)[3]
            n.find("IsLadderSelected").text = "false"
            n.find("LadderElements")[-1].find("ElementType").text = "EndCn"

        self.refuse(end, "sr63")

    def test_no_SR_program_replaces_active_SR_templates_and_removes_inherited_code(self):
        program = Program(rungs=[["LD %M0", "ST %M1"]])
        before_program = copy.deepcopy(program.as_dict())
        for label, _, _ in CASES:
            original = source(label).read_bytes()
            for existing in (False, True):
                with self.subTest(label=label, existing=existing):
                    with tempfile.TemporaryDirectory() as d:
                        parent = Path(d) / "destination-parent"
                        dest = parent / "candidate.smbp"
                        if existing:
                            parent.mkdir()
                            dest.write_bytes(b"existing destination sentinel")
                        write_project(program, source(label), dest)
                        loaded = load_project(dest)
                        self.assertEqual(loaded.subroutines, {})
                        self.assertEqual(loaded.rungs, program.rungs)
                        self.assertEqual(loaded.as_dict()["format"], "m200-cpp-il-v1")
                        self.assertTrue(parent.exists())
                        machine = Machine(loaded)
                        machine.memory[0] = True
                        self.assertEqual(machine.step({}, 10), [False] * 16)
                        self.assertTrue(machine.memory[1])
                        self.assertEqual(machine.words[:3], [0, 0, 0])
                        q = E.parse(dest).getroot()
                        self.assertEqual(len(q.find("SoftwareConfiguration/Subroutines")), 0)
                        self.assertEqual(source(label).read_bytes(), original)
                        self.assertEqual(program.as_dict(), before_program)
        # The ordinary empty template retains the same legacy program route.
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "ordinary.smbp"
            write_project(program, FIXTURES / "official_tm200ce40t_memory.smbp", dest)
            self.assertEqual(load_project(dest).subroutines, {})
            self.assertEqual(program.as_dict(), before_program)

    def test_staged_readback_refuses_unrequested_SR_as_defense_in_depth(self):
        program = Program(rungs=[["LD %M0", "ST %M1"]])
        real_loader = load_project

        def unrequested_context(path):
            loaded = real_loader(path)
            loaded.subroutines = {
                0: SubroutineDefinition(0, "unexpected", 2, [["END"]])
            }
            return loaded

        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as d:
                dest = Path(d) / "candidate.smbp"
                if existing:
                    dest.write_bytes(b"preserved destination")
                before = dest.read_bytes() if existing else None
                with patch(
                    "m200.project.load_project", side_effect=unrequested_context
                ) as loader:
                    with self.assertRaises(CompileError):
                        write_project(
                            program, FIXTURES / "official_tm200ce40t_memory.smbp", dest
                        )
                    self.assertEqual(loader.call_count, 1)
                self.assertEqual(dest.read_bytes() if dest.exists() else None, before)
                self.assertFalse(any(Path(d).glob(".m200-candidate-*")))


if __name__ == "__main__":
    unittest.main()
