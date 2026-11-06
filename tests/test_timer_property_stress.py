"""Exercise the stress CLI and its actual 10ms XML/reverse round trips."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/stress/timer_properties.py"
HISTORICAL = ROOT / "docs/validation/TIMER-PROPERTY-STRESS-RESULTS.json"


class TimerPropertyStressTests(unittest.TestCase):
    def test_all_bases_complete_and_write_only_the_explicit_new_report(self):
        original = HISTORICAL.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "new results/report.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(report)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(report.is_file(), "Explicit report was not created")
            evidence = json.loads(report.read_text())
            self.assertEqual(evidence["scans"], 8192)
            self.assertEqual(len(evidence["cases"]), 16)
            self.assertEqual(
                {
                    case["case"]: (case["status"], case["xml"])
                    for case in evidence["cases"]
                    if case["case"] in {"Ton_10", "Tof_10", "Pulse_10"}
                },
                {
                    "Ton_10": ("pass", "synthetic-profile pass"),
                    "Tof_10": ("pass", "synthetic-profile pass"),
                    "Pulse_10": ("pass", "synthetic-profile pass"),
                },
            )
            self.assertEqual(evidence["official_editor"], "pending")
            self.assertEqual(evidence["physical_plc"], "pending")
            self.assertEqual(
                evidence["source_sha256"]["tests/stress/timer_properties.py"],
                hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            )
        self.assertEqual(HISTORICAL.read_bytes(), original)

    def test_existing_explicit_report_is_rejected_without_replacement(self):
        original = HISTORICAL.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "preserve.json"
            report.write_bytes(b"preserve existing diagnostic evidence\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(report)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(
                report.read_bytes(), b"preserve existing diagnostic evidence\n"
            )
        self.assertEqual(HISTORICAL.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
