"""Authentic M200 default profile, without accepting unknown active features."""

import copy
import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.config import configuration
from m200.il import Machine
from m200.model import CompileError, Program
from m200.project import load_project, write_project

FIXTURE = Path(__file__).parent / "fixtures/official_tm200ce40t_memory.smbp"
EDITOR_SAVED = (
    Path(__file__).parent / "fixtures/official_tm200ce40t_memory_editor_saved.smbp"
)


def semantic(node):
    return (
        node.tag,
        sorted(node.attrib.items()),
        (node.text or "").strip(),
        [semantic(c) for c in node],
    )


class OfficialProfileTests(unittest.TestCase):
    def tree(self):
        return ET.parse(FIXTURE)

    def load(self, tree):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "case.smbp"
            tree.write(p)
            return load_project(p)

    def test_original_identity_and_default_configuration(self):
        provenance = json.loads(FIXTURE.with_suffix(".provenance.json").read_text())
        self.assertEqual(FIXTURE.stat().st_size, provenance["bytes"])
        self.assertEqual(
            hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), provenance["sha256"]
        )
        configuration(self.tree().getroot())

    def test_original_zero_based_memory_rung_imports(self):
        p = load_project(FIXTURE)
        self.assertEqual(p.rungs, [["LD %M0", "ST %M1"]])
        self.assertFalse(p.metadata["synthetic_template"])
        vm = Machine(p)
        vm.memory[0] = True
        vm.step()
        self.assertTrue(vm.memory[1])

    def test_editor_saved_fixture_identity_and_default_configuration(self):
        provenance = json.loads(
            EDITOR_SAVED.with_suffix(".provenance.json").read_text()
        )
        self.assertEqual(EDITOR_SAVED.stat().st_size, provenance["bytes"])
        self.assertEqual(
            hashlib.sha256(EDITOR_SAVED.read_bytes()).hexdigest(), provenance["sha256"]
        )
        configuration(ET.parse(EDITOR_SAVED).getroot())

    def test_actual_editor_save_retains_memory_logic_with_normalized_profile(self):
        original = self.tree()
        saved_bytes = EDITOR_SAVED.read_bytes()
        saved = ET.parse(EDITOR_SAVED)
        self.assertEqual(
            saved.findtext(".//ProgramOrganizationUnits/SectionNumber"), "1"
        )
        self.assertEqual(
            original.findtext(".//ProgramOrganizationUnits/SectionNumber"), "0"
        )
        for tag in (
            "MemoryBitsMemoryAllocation",
            "MemoryWordsMemoryAllocation",
            "TimersMemoryAllocation",
        ):
            with self.subTest(allocation=tag):
                node = saved.find("SoftwareConfiguration/" + tag)
                self.assertIsNotNone(node)
                self.assertEqual(len(node), 0)
                self.assertFalse((node.text or "").strip())
        self.assertEqual(
            semantic(saved.find("HardwareConfiguration")),
            semantic(original.find("HardwareConfiguration")),
        )
        self.assertEqual(
            saved.findtext("ManagementLevel"), original.findtext("ManagementLevel")
        )
        before, after = load_project(FIXTURE), load_project(EDITOR_SAVED)
        self.assertEqual(after.rungs, before.rungs)
        self.assertEqual(after.rungs, [["LD %M0", "ST %M1"]])
        self.assertFalse(after.metadata["synthetic_template"])
        for program in (before, after):
            vm = Machine(program)
            for value in (False, True, True, False, True, False, False, True):
                vm.memory[0] = value
                vm.step()
                self.assertEqual(vm.memory[0], value)
                self.assertEqual(vm.memory[1], value)
        self.assertEqual(EDITOR_SAVED.read_bytes(), saved_bytes)

    def test_default_input_filter_and_latch_are_closed(self):
        for tag, value in [
            ("DIFiltering", "DIFilterings12ms"),
            ("DILatch", "DILatchYes"),
        ]:
            tree = self.tree()
            tree.find(".//DiscretInput/" + tag).text = value
            with self.subTest(tag=tag), self.assertRaises(CompileError):
                configuration(tree.getroot())
        tree = self.tree()
        ET.SubElement(tree.find(".//DiscretInput"), "UnknownInputMode").text = "Active"
        with self.assertRaises(CompileError):
            configuration(tree.getroot())

    def test_inactive_pulse_defaults_reject_activation_unknowns_and_bad_identity(self):
        changes = [
            ("Preset", "2"),
            ("Index", "2"),
            ("GlobalIndex", "1"),
            ("Address", "%PLS1/%PWM1/%PTO1/%FREQGEN1"),
            ("PtoObject/RefInput", "%I0.0"),
            ("PtoObject/ZPhaseInput", "%I0.1"),
            ("PtoObject/ProbeInput", "%I0.2"),
        ]
        for path, value in changes:
            tree = self.tree()
            tree.find(".//PulseTrainOutput/" + path).text = value
            with self.subTest(path=path), self.assertRaises(CompileError):
                configuration(tree.getroot())
        for path, tag in [
            (".//PulseTrainOutput", "Type"),
            (".//PtoObject", "UnknownAxisMode"),
        ]:
            tree = self.tree()
            ET.SubElement(tree.find(path), tag).text = "Active"
            with self.subTest(tag=tag), self.assertRaises(CompileError):
                configuration(tree.getroot())

    def test_collection_entries_and_nested_singletons_remain_unique(self):
        for path in [".//PulseTrainOutput/Index", ".//TechnicalConfiguration/UdfMax"]:
            tree = self.tree()
            node = tree.find(path)
            parent = next(n for n in tree.getroot().iter() if node in list(n))
            parent.append(copy.deepcopy(node))
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(CompileError, "duplicate XML singleton"),
            ):
                configuration(tree.getroot())
        tree = self.tree()
        entries = tree.find(".//PulseTrainOutputs")
        entries.append(copy.deepcopy(entries[0]))
        with self.assertRaises(CompileError):
            configuration(tree.getroot())

    def test_unknown_or_nested_technical_metadata_still_rejected(self):
        for nested in (False, True):
            tree = self.tree()
            node = tree.find(".//TechnicalConfiguration")
            if nested:
                ET.SubElement(node.find("UdfMax"), "ActiveCode").text = "x"
            else:
                ET.SubElement(node, "UnknownFirmwareFeature").text = "1"
            with self.subTest(nested=nested), self.assertRaises(CompileError):
                configuration(tree.getroot())

    def test_inactive_io_scanner_flag_is_a_scalar_not_a_collection(self):
        tree = self.tree()
        configuration(tree.getroot())
        tree.find(".//ModbusTcpSlave/IsIoScanner").text = "true"
        with self.assertRaisesRegex(CompileError, "active IOScanner"):
            configuration(tree.getroot())

    def test_both_observed_section_bases_and_only_contiguous_sequences(self):
        for base in (0, 1):
            tree = self.tree()
            pous = tree.find("SoftwareConfiguration/Pous")
            pous[0].find("SectionNumber").text = str(base)
            second = copy.deepcopy(pous[0])
            second.find("SectionNumber").text = str(base + 1)
            pous.append(second)
            with self.subTest(base=base):
                self.assertEqual(len(self.load(tree).rungs), 2)
            for wrong in (base, base + 2, 9):
                second.find("SectionNumber").text = str(wrong)
                with (
                    self.subTest(base=base, wrong=wrong),
                    self.assertRaises(CompileError),
                ):
                    self.load(tree)

    def test_writer_preserves_hardware_and_template_section_base(self):
        p = Program([["LD %M0", "ST %M1"], ["LD %M1", "ST %M2"]])
        for base in (0, 1):
            tree = self.tree()
            tree.find(".//ProgramOrganizationUnits/SectionNumber").text = str(base)
            with tempfile.TemporaryDirectory() as folder:
                source, dest = (
                    Path(folder) / "source.smbp",
                    Path(folder) / "candidate.smbp",
                )
                tree.write(source)
                original = source.read_bytes()
                write_project(p, source, dest)
                candidate = ET.parse(dest)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(
                    semantic(candidate.find("HardwareConfiguration")),
                    semantic(tree.find("HardwareConfiguration")),
                )
                self.assertEqual(
                    candidate.findtext(".//ProgramOrganizationUnits/SectionNumber"),
                    str(base),
                )
                self.assertEqual(load_project(dest).rungs, p.rungs)


if __name__ == "__main__":
    unittest.main()
