import importlib
import json
import tempfile
import unittest
from pathlib import Path

from m200.model import CompileError


class CapabilityCatalogueTests(unittest.TestCase):
    """Source-backed inventory must never become an implicit support claim."""

    def api(self):
        try:
            return importlib.import_module("m200.capabilities")
        except ModuleNotFoundError:
            self.fail("The capability catalogue API is missing")

    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        source = Path(__file__).resolve().parents[1] / "docs" / "capabilities"
        for name in ("instructions.json", "hardware.json"):
            (directory / name).write_bytes((source / name).read_bytes())
        return directory

    def change(self, directory, filename, edit):
        path = directory / filename
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data))

    def test_loads_instruction_and_hardware_inventory_with_unique_ids(self):
        data = self.api().catalogue()
        self.assertEqual(data["target"], "TM200CE40T")
        entries = data["capabilities"]
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("integer.add", ids)
        self.assertIn("HW.PWM", ids)
        self.assertIn("user.udfb", ids)
        self.assertGreater(len(ids), 200)

    def test_all_entries_have_resolved_primary_evidence(self):
        data = self.api().catalogue()
        for entry in data["capabilities"]:
            with self.subTest(capability=entry["id"]):
                self.assertTrue(entry["evidence"])
                for ref in entry["evidence"]:
                    self.assertIn(ref["source"], data["sources"])
                    self.assertTrue(ref["pages"])

    def test_inventory_does_not_claim_frontend_or_external_validation(self):
        data = self.api().catalogue()
        expected = {
            "frontend": "missing",
            "il": "missing",
            "reverse": "missing",
            "smbp": "missing",
            "local": "missing",
            "editor": "pending",
            "physical": "pending",
        }
        for entry in data["capabilities"]:
            with self.subTest(capability=entry["id"]):
                self.assertEqual(entry["status"], expected)

    def test_summary_counts_every_stage_and_preserves_validation_boundary(self):
        result = self.api().summary()
        self.assertGreater(result["total"], 200)
        for stage in ("frontend", "il", "reverse", "smbp", "local"):
            self.assertEqual(result["stages"][stage]["missing"], result["total"])
            self.assertEqual(result["stages"][stage].get("implemented", 0), 0)
        for stage in ("editor", "physical"):
            self.assertEqual(result["stages"][stage]["pending"], result["total"])
        self.assertFalse(result["complete"])
        self.assertTrue(result["pending_external_validation"])

    def test_model_memory_and_hardware_limits_are_retained(self):
        data = self.api().catalogue()
        self.assertEqual(data["resources"]["MW"], 8000)
        self.assertEqual(data["resources"]["MD_or_MF_possible_start_addresses"], 7999)
        self.assertEqual(data["resources"]["TM"], 255)
        self.assertEqual(
            data["resources"]["PLS_PWM_PTO_FREQGEN_shared_hardware_channels"], 2
        )
        entry = self.api().lookup("HW.DIGITAL_INPUTS")
        self.assertEqual(entry["details"]["addresses"], "%I0.0..%I0.23")
        self.assertEqual(
            self.api().lookup("HW.DIGITAL_OUTPUTS")["details"]["addresses"],
            "%Q0.0..%Q0.15",
        )

    def test_unknown_capability_fails_with_actionable_m200_diagnostic(self):
        with self.assertRaisesRegex(
            CompileError, r"M200-E:.*unknown capability.*integer.ad"
        ):
            self.api().lookup("integer.ad")

    def test_wrong_requested_model_is_rejected(self):
        with self.assertRaisesRegex(CompileError, r"M200-E:.*TM200CE40T"):
            self.api().catalogue(model="TM200CE40R")

    def test_duplicate_id_in_research_data_is_rejected(self):
        directory = self.fixture()
        self.change(
            directory,
            "instructions.json",
            lambda data: data["capabilities"].append(data["capabilities"][0]),
        )
        with self.assertRaisesRegex(CompileError, r"M200-E:.*duplicate capability"):
            self.api().catalogue(directory=directory)

    def test_unresolved_evidence_is_rejected(self):
        directory = self.fixture()
        self.change(
            directory,
            "hardware.json",
            lambda data: data["capabilities"][0]["evidence"][0].update(
                source="UNKNOWN"
            ),
        )
        with self.assertRaisesRegex(CompileError, r"M200-E:.*source"):
            self.api().catalogue(directory=directory)

    def test_wrong_model_inside_research_data_is_rejected(self):
        directory = self.fixture()
        self.change(
            directory,
            "hardware.json",
            lambda data: data["capabilities"][0].update(model="TM200CE40R"),
        )
        with self.assertRaisesRegex(CompileError, r"M200-E:.*model"):
            self.api().catalogue(directory=directory)

    def test_missing_or_malformed_inventory_fails_closed(self):
        directory = self.fixture()
        (directory / "hardware.json").write_text("{")
        with self.assertRaisesRegex(CompileError, r"M200-E:.*hardware.json"):
            self.api().catalogue(directory=directory)
        (directory / "hardware.json").unlink()
        with self.assertRaisesRegex(CompileError, r"M200-E:.*hardware.json"):
            self.api().catalogue(directory=directory)

    def test_callers_cannot_mutate_later_results_to_claim_support(self):
        first = self.api().lookup("integer.add")
        first["status"]["physical"] = "implemented"
        first["sources"].clear()
        again = self.api().lookup("integer.add")
        self.assertEqual(again["status"]["physical"], "pending")
        self.assertTrue(again["sources"])


if __name__ == "__main__":
    unittest.main()
