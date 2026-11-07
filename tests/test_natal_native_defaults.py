"""Actual saved SBR/SC default omission; static import/reverse regression only.

The small fixture composes exact hashed vendor XML extracts with the existing
authentic CE40T memory template. It is not a separately vendor-saved project and
contains no expected endpoint, collision, lifecycle or runtime observations.
"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.frontend import compile_source
from m200.model import CompileError
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.sequences import ShiftBitRegisterConfig, StepCounterConfig


ROOT = Path(__file__).resolve().parents[1]
EXTRACTS = ROOT / "tests/fixtures/natal_native_defaults_saved_fragments.json"
FAMILIES = ("shift_bit_registers", "step_counters", "drums")


class NatalNativeDefaultTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(EXTRACTS.read_text())
        self.template = ROOT / self.fixture["base_template"]["path"]
        self.assertEqual(
            hashlib.sha256(self.template.read_bytes()).hexdigest(),
            self.fixture["base_template"]["sha256"],
            "Authentic base changed; review the vendor-derived fixture provenance",
        )
        for name, fragment in self.fixture["fragments"].items():
            self.assertEqual(
                hashlib.sha256(fragment["xml"].encode("utf-8")).hexdigest(),
                fragment["sha256"],
                "Exact vendor extract changed: " + name,
            )

    def fragment(self, name):
        # Namespace declarations belong to the source project root. The raw
        # element text/hash stays unchanged; this wrapper supplies only context.
        text = (
            '<extract xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            + self.fixture["fragments"][name]["xml"]
            + "</extract>"
        )
        return ET.fromstring(text)[0]

    def project(self, case):
        tree = ET.parse(self.template)
        sw = tree.find("SoftwareConfiguration")
        rungs = sw.find("Pous/ProgramOrganizationUnits/Rungs")
        for rung in list(rungs):
            rungs.remove(rung)
        for name in self.fixture["cases"][case]["rungs"]:
            rungs.append(self.fragment(name))
        for tag in ("ShiftBitRegisters", "StepCounters", "Drums"):
            old = sw.find(tag)
            position = list(sw).index(old)
            sw.remove(old)
            if tag == "Drums" and not self.fixture["cases"][case]["dr"]:
                replacement = ET.Element(tag)
            else:
                replacement = self.fragment("collection_" + tag)
            sw.insert(position, replacement)
        self.assertEqual(len(sw.find("ShiftBitRegisters")), 0)
        self.assertEqual(len(sw.find("StepCounters")), 0)
        return tree

    def write(self, tree, path):
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def assert_configs(self, program, case):
        expected = self.fixture["cases"][case]
        self.assertEqual(set(program.shift_bit_registers), set(expected["sbr"]))
        self.assertEqual(set(program.step_counters), set(expected["sc"]))
        self.assertEqual(set(program.drums), set(expected["dr"]))
        for config in program.shift_bit_registers.values():
            self.assertEqual(config, ShiftBitRegisterConfig())
        for config in program.step_counters.values():
            self.assertEqual(config, StepCounterConfig())
        if expected["dr"]:
            drum = self.fixture["expected_drum"]
            config = program.drums[drum["index"]]
            self.assertEqual(config.steps, drum["steps"])
            self.assertEqual(
                [dict(slot=c.slot, output=c.output, mask=c.mask) for c in config.cams],
                drum["cams"],
            )

    def test_actual_saved_default_omission_imports_reverses_and_rebuilds(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                actual = folder / "actual-native-extract.smbp"
                self.write(self.project(case), actual)
                before = actual.read_bytes()
                program = load_project(actual)
                self.assert_configs(program, case)
                reverse = folder / "actual-reverse.cpp"
                reverse.write_text(to_cpp(program))
                rebuilt = compile_source(reverse)
                self.assert_configs(rebuilt, case)
                target = folder / "rebuilt.smbp"
                write_project(rebuilt, actual, target)
                self.assert_configs(load_project(target), case)
                self.assertEqual(actual.read_bytes(), before)

    def test_out_of_range_native_properties_and_block_ids_are_refused(self):
        for case, old, invalid in [
            ("sbr_default", "%SBR0.0", "%SBR0.16"),
            ("sbr_default", "%SBR0", "%SBR8"),
            ("sc_default", "%SC0.0", "%SC0.256"),
            ("sc_default", "%SC0", "%SC8"),
        ]:
            with self.subTest(case=case, invalid=invalid), tempfile.TemporaryDirectory() as folder:
                tree = self.project(case)
                # Change IL and its actual graph together. A bounds failure must
                # not rely on a deliberately inconsistent graphical descriptor.
                for node in tree.iter():
                    if node.text:
                        node.text = node.text.replace(old, invalid)
                path = Path(folder) / "out-of-range.smbp"
                self.write(tree, path)
                before = path.read_bytes()
                with self.assertRaises(CompileError):
                    load_project(path)
                self.assertEqual(path.read_bytes(), before)

    def test_missing_meaningful_drum_configuration_is_not_synthesized(self):
        tree = self.project("mixed_defaults_and_meaningful_drum")
        sw = tree.find("SoftwareConfiguration")
        sw.remove(sw.find("Drums"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing-meaningful-drum.smbp"
            self.write(tree, path)
            before = path.read_bytes()
            with self.assertRaises(CompileError):
                load_project(path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
