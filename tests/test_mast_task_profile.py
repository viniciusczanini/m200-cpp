"""The supported master profile must be explicit and cannot imply scheduling."""

# ruff: noqa: E402
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "m200/config.py").is_file()
)
sys.path.insert(0, str(ROOT))

from m200.model import CompileError, Program
from m200.project import load_project, write_project


FIXTURE = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
SYNTHETIC = ROOT / "tests/fixtures/synthetic.smbp"


class MastTaskProfileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def tree(self):
        return ET.parse(FIXTURE)

    def modified(self, *, mode="false", period="100"):
        tree = self.tree()
        tree.find("SoftwareConfiguration/MastTask/UsePeriodScanMode").text = mode
        tree.find("SoftwareConfiguration/MastTask/PeriodScan").text = period
        return tree

    def save(self, tree, name="candidate.smbp"):
        path = self.work / name
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def test_observed_inactive_master_profile_imports_and_is_preserved_on_export(self):
        for fixture in (FIXTURE, SYNTHETIC):
            with self.subTest(fixture=fixture.name):
                original = fixture.read_bytes()
                program = load_project(fixture)
                destination = self.work / "valid.smbp"
                write_project(program, fixture, destination)
                actual = ET.parse(destination)
                self.assertEqual(
                    actual.findtext("SoftwareConfiguration/MastTask/UsePeriodScanMode"),
                    "false",
                )
                self.assertEqual(
                    actual.findtext("SoftwareConfiguration/MastTask/PeriodScan"), "100"
                )
                self.assertEqual(load_project(destination).rungs, program.rungs)
                self.assertEqual(fixture.read_bytes(), original)

    def test_active_periodic_master_is_rejected_until_scheduling_is_implemented(self):
        for period in ("1", "10", "100", "150"):
            with (
                self.subTest(period=period),
                self.assertRaisesRegex(CompileError, "periodic master|MastTask"),
            ):
                load_project(self.save(self.modified(mode="true", period=period)))

    def test_master_mode_requires_canonical_boolean(self):
        for mode in ("", "True", "FALSE", "1", "0", " false", "false ", "unknown"):
            with self.subTest(mode=mode), self.assertRaises(CompileError):
                load_project(self.save(self.modified(mode=mode)))

    def test_master_period_rejects_malformed_and_out_of_range_numbers(self):
        for period in ("", "0", "-1", "151", "100.0", "+100", "0100", "١٠٠", "unknown"):
            with self.subTest(period=period), self.assertRaises(CompileError):
                load_project(self.save(self.modified(period=period)))

    def test_other_inactive_period_profiles_are_an_explicit_tool_gap(self):
        # These values are within the published range; refusal must not imply
        # the PLC itself cannot use them. Only false/100 is observed here.
        for period in ("1", "2", "10", "150"):
            with (
                self.subTest(period=period),
                self.assertRaisesRegex(
                    CompileError, "unverified.*(?:period|MastTask)|unsupported.*profile"
                ),
            ):
                load_project(self.save(self.modified(period=period)))

    def test_master_profile_and_both_fields_are_required(self):
        for field in ("MastTask", "MastTask/UsePeriodScanMode", "MastTask/PeriodScan"):
            tree = self.tree()
            software = tree.find("SoftwareConfiguration")
            parent_path, _, name = field.rpartition("/")
            parent = software.find(parent_path) if parent_path else software
            parent.remove(parent.find(name))
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(CompileError, "MastTask|master"),
            ):
                load_project(self.save(tree))

    def test_duplicate_master_profile_or_field_is_rejected(self):
        for path in ("MastTask", "MastTask/UsePeriodScanMode", "MastTask/PeriodScan"):
            tree = self.tree()
            software = tree.find("SoftwareConfiguration")
            parent_path, _, name = path.rpartition("/")
            parent = software.find(parent_path) if parent_path else software
            parent.append(copy.deepcopy(parent.find(name)))
            with self.subTest(path=path), self.assertRaises(CompileError):
                load_project(self.save(tree))

    def test_unknown_fields_attributes_and_nested_scalars_are_rejected(self):
        for change in ("field", "attribute", "nested"):
            tree = self.tree()
            master = tree.find("SoftwareConfiguration/MastTask")
            if change == "field":
                ET.SubElement(master, "Subroutine").text = "0"
            elif change == "attribute":
                master.set("Enabled", "true")
            else:
                ET.SubElement(master.find("PeriodScan"), "int").text = "100"
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(self.save(tree))

    def test_rejected_master_template_preserves_existing_and_absent_destinations(self):
        for mode, period in (("true", "100"), ("unknown", "100"), ("false", "-1")):
            template = self.save(self.modified(mode=mode, period=period))
            template_bytes = template.read_bytes()
            program = Program([["LD %M0", "ST %M1"]])
            for existing in (True, False):
                destination = self.work / (
                    "existing.smbp" if existing else "absent.smbp"
                )
                if existing:
                    destination.write_bytes(b"PRESERVE ORIGINAL PROJECT")
                with self.subTest(mode=mode, period=period, existing=existing):
                    with self.assertRaises(CompileError):
                        write_project(program, template, destination)
                    if existing:
                        self.assertEqual(
                            destination.read_bytes(), b"PRESERVE ORIGINAL PROJECT"
                        )
                    else:
                        self.assertFalse(destination.exists())
                    self.assertEqual(template.read_bytes(), template_bytes)

    def test_template_profile_is_authoritative_over_program_metadata(self):
        program = Program(
            [["LD %M0", "ST %M1"]],
            metadata={"MastTask": {"UsePeriodScanMode": "false", "PeriodScan": "100"}},
        )
        template = self.save(self.modified(mode="true"))
        destination = self.work / "preserve.smbp"
        destination.write_bytes(b"PRESERVE")
        with self.assertRaises(CompileError):
            write_project(program, template, destination)
        self.assertEqual(destination.read_bytes(), b"PRESERVE")
        program.metadata["MastTask"] = {"UsePeriodScanMode": "true", "PeriodScan": "-1"}
        write_project(program, FIXTURE, destination)
        self.assertEqual(
            ET.parse(destination).findtext(
                "SoftwareConfiguration/MastTask/UsePeriodScanMode"
            ),
            "false",
        )


if __name__ == "__main__":
    unittest.main()
