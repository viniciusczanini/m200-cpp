"""Exact editor-saved/reopened 10ms binding, preserving other timer gates."""

import dataclasses
import hashlib
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError, Program, Timer
from m200.project import load_project, write_project

ROOT = Path(__file__).resolve().parents[1]
# Byte-exact official-editor save/reopen; provenance is adjacent to the fixture.
SAVED_10MS = ROOT / "tests/fixtures/official_tm200ce40t_timer_10ms.smbp"
SAVED_10MS_SHA256 = "934affc43bd7e3d918b529b5cbfaee5aabd6bc062006edcd5c3cacf0d7f2bc45"


class TimerXmlBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SAVED_10MS.is_file():
            raise RuntimeError("Pinned 10ms fixture is missing")
        cls.original = SAVED_10MS.read_bytes()
        if hashlib.sha256(cls.original).hexdigest() != SAVED_10MS_SHA256:
            raise RuntimeError("Pinned editor-saved 10ms fixture changed")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.work = Path(self.directory.name)

    def program(self):
        return Program(
            [
                ["BLK %TM0", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"],
                ["BLK %TM1", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"],
                ["BLK %TM2", "LD %M0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"],
            ],
            {
                0: Timer("TON", 50, 10, False, False),
                1: Timer("TOF", 50, 10, False, False),
                2: Timer("TP", 50, 10, False, False),
            },
        )

    def test_saved_10ms_import_preserves_three_types_preset_base_and_flags(self):
        loaded = load_project(SAVED_10MS)
        self.assertEqual(loaded.timers, self.program().timers)
        self.assertEqual(loaded.rungs, self.program().rungs)

    def test_10ms_export_uses_saved_binding_and_roundtrips_without_options(self):
        destination = self.work / "ten-ms.smbp"
        program = self.program()
        write_project(program, SAVED_10MS, destination)
        root = ET.parse(destination).getroot()
        timers = root.findall("./SoftwareConfiguration/Timers/TimerTM")
        self.assertEqual(
            [
                (
                    t.findtext("Type"),
                    t.findtext("Base"),
                    t.findtext("Preset"),
                    t.findtext("IsRetentive"),
                    t.findtext("IsDynamicPreset"),
                )
                for t in timers
            ],
            [
                ("TON", "TenMilliSeconds", "5", "false", "false"),
                ("TOF", "TenMilliSeconds", "5", "false", "false"),
                ("TP", "TenMilliSeconds", "5", "false", "false"),
            ],
        )
        self.assertEqual(root.findtext("ManagementLevel"), "FunctLevelMan21_0")
        self.assertEqual(load_project(destination).timers, program.timers)
        self.assertEqual(SAVED_10MS.read_bytes(), self.original)

    def test_unknown_base_is_rejected_without_mutating_the_input(self):
        root = ET.fromstring(self.original)
        root.find("./SoftwareConfiguration/Timers/TimerTM/Base").text = "TenMilliSecond"
        malformed = self.work / "unknown-base.smbp"
        malformed.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        before = malformed.read_bytes()
        with self.assertRaisesRegex(CompileError, "unsupported timer time base"):
            load_project(malformed)
        self.assertEqual(malformed.read_bytes(), before)
        self.assertEqual(SAVED_10MS.read_bytes(), self.original)

    def test_unverified_options_stay_blocked_and_preserve_existing_destination(self):
        for option in ("retentive", "dynamic_preset"):
            with self.subTest(option=option):
                program = self.program()
                program.timers[0] = dataclasses.replace(
                    program.timers[0], **{option: True}
                )
                destination = self.work / (option + ".smbp")
                destination.write_bytes(b"preserved user destination\n")
                with self.assertRaisesRegex(
                    CompileError, "timer.*functional.level.*unverified"
                ):
                    write_project(program, SAVED_10MS, destination)
                self.assertEqual(
                    destination.read_bytes(), b"preserved user destination\n"
                )
        self.assertEqual(SAVED_10MS.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
