"""Observed inactive PTO aliases do not authorize active or forged resources."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.config import configuration
from m200.model import CompileError, Program
from m200.project import load_project, write_project

FIXTURES = Path(__file__).parent / "fixtures"
SAVED = FIXTURES / "official_tm200ce40t_timer_ret_ton_fl3_2.smbp"
CURRENT = FIXTURES / "official_tm200ce40t_memory.smbp"
SAVED_SHA256 = "35a9d891711ff3eb74d745f30c14cbb3574b7cd61b0cec876320263e28a1fbd6"
ALIASES = (
    ("%PLS0/%PWM0/%PTO0", "%PLS1/%PWM1/%PTO1"),
    ("%PLS0/%PWM0/%PTO0/%FREQGEN0", "%PLS1/%PWM1/%PTO1/%FREQGEN1"),
)


class InactivePulseAliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = SAVED.read_bytes()
        if hashlib.sha256(cls.original).hexdigest() != SAVED_SHA256:
            raise RuntimeError("Pinned editor-saved inactive PTO fixture changed")
        provenance = json.loads(SAVED.with_suffix(".provenance.json").read_text())
        if provenance["sha256"] != SAVED_SHA256 or provenance["bytes"] != 87336:
            raise RuntimeError("Pinned inactive PTO provenance changed")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)

    def alias_tree(self, addresses):
        root = ET.parse(CURRENT).getroot()
        for output, address in zip(root.findall(".//PulseTrainOutput"), addresses):
            output.find("Address").text = address
        return root

    def test_exact_saved_legacy_profile_configuration_passes_without_mutation(self):
        root = ET.fromstring(self.original)
        before = ET.tostring(root)
        self.assertIs(configuration(root), root.find("SoftwareConfiguration"))
        self.assertEqual(ET.tostring(root), before)
        self.assertEqual(SAVED.read_bytes(), self.original)

    def test_exact_saved_profile_reaches_conservative_retention_level_gate(self):
        with self.assertRaisesRegex(
            CompileError, r"timer retention requires functional level >=4\.0.*3\.3/4\.0"
        ):
            load_project(SAVED)
        self.assertEqual(SAVED.read_bytes(), self.original)
        # Paired control: the same actual FL3.2 and inactive aliases are valid
        # when retention is off. Do not promote a stored flag to execution proof.
        tree = ET.fromstring(self.original)
        tree.find("./SoftwareConfiguration/Timers/TimerTM/IsRetentive").text = "false"
        path = self.work / "ordinary_low_level.smbp"
        path.write_bytes(ET.tostring(tree))
        before = path.read_bytes()
        actual = load_project(path)
        self.assertFalse(actual.timers[0].retentive)
        self.assertEqual((actual.timers[0].kind, actual.timers[0].base_ms, actual.timers[0].preset), ("TON", 100, 5))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(SAVED.read_bytes(), self.original)

    def test_current_and_legacy_aliases_both_validate_disabled_channels(self):
        for addresses in ALIASES:
            with self.subTest(addresses=addresses):
                root = self.alias_tree(addresses)
                before = ET.tostring(root)
                configuration(root)
                self.assertEqual(ET.tostring(root), before)

    def test_both_alias_forms_keep_active_and_incomplete_axes_rejected(self):
        changes = (
            ("Preset", "2"),
            ("PtoObject/RefInput", "%I0.0"),
            ("PtoObject/ZPhaseInput", "%I0.1"),
            ("PtoObject/ProbeInput", "%I0.2"),
        )
        for addresses in ALIASES:
            for path, value in changes:
                for index in (0, 1):
                    with self.subTest(addresses=addresses, path=path, index=index):
                        root = self.alias_tree(addresses)
                        root.findall(".//PulseTrainOutput")[index].find(
                            path
                        ).text = value
                        with self.assertRaises(CompileError):
                            configuration(root)
            for missing in ("PtoObject", "PtoObject/ProbeInput"):
                with self.subTest(addresses=addresses, missing=missing):
                    root = self.alias_tree(addresses)
                    output = root.find(".//PulseTrainOutput")
                    parent = (
                        output if missing == "PtoObject" else output.find("PtoObject")
                    )
                    parent.remove(output.find(missing))
                    with self.assertRaises(CompileError):
                        configuration(root)
            for path, field in ((".", "Type"), ("PtoObject", "UnknownAxisMode")):
                with self.subTest(addresses=addresses, field=field):
                    root = self.alias_tree(addresses)
                    output = root.find(".//PulseTrainOutput")
                    ET.SubElement(output.find(path), field).text = "Active"
                    with self.assertRaises(CompileError):
                        configuration(root)

    def test_both_alias_forms_keep_closed_address_and_index_identity(self):
        for addresses in ALIASES:
            for field, value in (
                ("Index", "2"),
                ("Index", "01"),
                ("GlobalIndex", "1"),
                ("Address", "%PLS1/%PWM1/%PTO1"),
                ("Address", "%PLS0/%PWM1/%PTO0"),
                ("Address", "%PLS0/%PWM0/%PTO1"),
                ("Address", "%PLS0/%PWM0/%PTO0/%FREQGEN1"),
                ("Address", "%PLS0/%PWM0/%PTO0/%UNKNOWN0"),
                ("Address", "%PLS0/%PWM0/%PTO0/%FREQGEN0/extra"),
                ("Address", "%PTO0"),
                ("Address", " %PLS0/%PWM0/%PTO0"),
            ):
                with self.subTest(addresses=addresses, field=field, value=value):
                    root = self.alias_tree(addresses)
                    root.find(".//PulseTrainOutput/" + field).text = value
                    with self.assertRaises(CompileError):
                        configuration(root)
            for duplicate in ("entry", "Address"):
                with self.subTest(addresses=addresses, duplicate=duplicate):
                    root = self.alias_tree(addresses)
                    outputs = root.find(".//PulseTrainOutputs")
                    if duplicate == "entry":
                        outputs.append(copy.deepcopy(outputs[0]))
                    else:
                        outputs[0].append(copy.deepcopy(outputs[0].find("Address")))
                    with self.assertRaises(CompileError):
                        configuration(root)

    def test_ordinary_export_preserves_the_saved_inactive_hardware_profile(self):
        program = Program([["LD %M0", "ST %M1"]])
        destination = self.work / "ordinary.smbp"
        write_project(program, SAVED, destination)
        loaded = load_project(destination)
        self.assertEqual(loaded.rungs, [["LD %M0", "ST %M1"]])
        self.assertEqual(loaded.timers, {})
        before = ET.fromstring(self.original)
        after = ET.parse(destination).getroot()
        self.assertEqual(after.findtext("ManagementLevel"), "FunctLevelMan5_0")
        self.assertEqual(
            ET.canonicalize(
                ET.tostring(after.find("HardwareConfiguration")), strip_text=True
            ),
            ET.canonicalize(
                ET.tostring(before.find("HardwareConfiguration")), strip_text=True
            ),
        )
        self.assertEqual(SAVED.read_bytes(), self.original)

    def test_invalid_legacy_template_cannot_replace_an_existing_destination(self):
        program = Program([["LD %M0", "ST %M1"]])
        for path, value, message in (
            (
                "Address",
                "%PLS0/%PWM0/%PTO0/%UNKNOWN0",
                "unsupported pulse output defaults",
            ),
            ("PtoObject/RefInput", "%I0.0", "active pulse axis"),
        ):
            with self.subTest(path=path):
                root = ET.fromstring(self.original)
                root.find(".//PulseTrainOutput/" + path).text = value
                template = self.work / "invalid-template.smbp"
                template.write_bytes(ET.tostring(root))
                source_before = template.read_bytes()
                destination = self.work / "preserved.smbp"
                destination.write_bytes(b"preserve existing user project\n")
                with self.assertRaisesRegex(CompileError, message):
                    write_project(program, template, destination)
                self.assertEqual(template.read_bytes(), source_before)
                self.assertEqual(
                    destination.read_bytes(), b"preserve existing user project\n"
                )
        self.assertEqual(SAVED.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
