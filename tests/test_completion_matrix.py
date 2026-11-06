"""Portable consistency checks for the scoped implementation/evidence matrix."""

import copy
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/capabilities/COMPLETION-MATRIX.json"
PHASES = {
    "cpp_sdk",
    "il_vm",
    "smbp_graph",
    "reverse",
    "local_oracle",
    "editor",
    "simulator",
    "physical",
}
STATES = {
    "covered_subset",
    "source_equivalent_subset",
    "lowered_form_only",
    "native_opcode_not_implemented",
    "not_implemented",
    "not_applicable",
    "standalone_foundation_only",
    "codec_only",
    "handbuilt_diagnostic_only",
    "observed_subset",
    "pending",
    "not_transaction_validated",
    "inactive_defaults_only",
    "refusal_only",
    "target_eligibility_unresolved",
    "unassessed_row_specific",
}
CLAIMED = {
    "covered_subset",
    "source_equivalent_subset",
    "lowered_form_only",
    "standalone_foundation_only",
    "codec_only",
    "handbuilt_diagnostic_only",
    "observed_subset",
    "refusal_only",
    "inactive_defaults_only",
}


def canonical_hash(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def catalogue_rows(root):
    rows = {}
    for domain, name in (("instruction", "instructions"), ("hardware", "hardware")):
        document = json.loads((root / f"docs/capabilities/{name}.json").read_text())
        for row in document["capabilities"]:
            if row["id"] in rows:
                raise ValueError("duplicate source ID")
            rows[row["id"]] = (domain, row)
    return rows


def validate_matrix(matrix, root=ROOT):
    """Validate documentary closure; this does not execute or certify the compiler."""

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def existing(relative):
        require(isinstance(relative, str), "reference must be a string")
        path = root / relative
        require(
            not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            "reference must be repository-relative",
        )
        require(path.is_file(), "missing reference: " + relative)
        return path

    require(matrix["schema"] == "m200.completion-matrix.v1", "schema")
    require(matrix["target"]["model"] == "TM200CE40T", "model")
    sources = catalogue_rows(root)
    rows = matrix["records"]
    identifiers = [row["id"] for row in rows]
    require(len(rows) == len(set(identifiers)) == len(sources) == 250, "250 unique IDs")
    require(set(identifiers) == set(sources), "source ID set")
    require(set(matrix["phases"]) == PHASES, "phase names")
    require(set(matrix["states"]) == STATES, "state names")
    require("completion_percentage" not in matrix, "no record-count percentage")

    for pin in matrix["pinned_inputs"]:
        path = existing(pin["path"])
        data = path.read_bytes()
        require(len(data) == pin["bytes"], "pinned byte count: " + pin["path"])
        require(
            hashlib.sha256(data).hexdigest() == pin["sha256"],
            "pinned hash: " + pin["path"],
        )
    pinned = {p["path"] for p in matrix["pinned_inputs"]}
    require(
        {"docs/capabilities/instructions.json", "docs/capabilities/hardware.json"}
        <= pinned,
        "source catalogues must be pinned",
    )

    profiles = matrix["profiles"]
    for key, profile in profiles.items():
        require(
            profile["scope"].strip() and profile["remaining"].strip(), "profile scope"
        )
        require(profile["next_test"].strip(), "finite next test")
        require(set(profile["phases"]) == PHASES, "profile phases")
        require(set(profile["phases"].values()) <= STATES, "profile state")
        require(profile["whole_record_complete"] is False, "unproved family completion")
        for category in ("code", "tests", "evidence"):
            for path in profile[category]:
                existing(path)
        for phase, state in profile["phases"].items():
            if state not in CLAIMED:
                continue
            proof = profile["phase_evidence"].get(phase, [])
            require(proof, "missing phase evidence: " + key + "/" + phase)
            for path in proof:
                existing(path)
            if phase in {"editor", "simulator"}:
                require(
                    all(path in pinned for path in proof),
                    "unpinned observation evidence",
                )
            else:
                require(
                    any(
                        path.startswith("tests/") or path.startswith("docs/validation/")
                        for path in proof
                    ),
                    "source-only implementation promotion",
                )
        require(
            profile["phases"]["physical"]
            in {
                "pending",
                "not_applicable",
                "target_eligibility_unresolved",
            },
            "no physical observation recorded",
        )

    members = []
    for group, package in matrix["work_packages"].items():
        require(package["next_test"].strip(), "work package test")
        require(package["release_task"] in {3, 4, 5}, "finite task assignment")
        members.extend(package["ids"])
        require(
            all(
                row["work_package"] == group
                for row in rows
                if row["id"] in package["ids"]
            ),
            "work package identity",
        )
    require(
        len(members) == len(set(members)) == 250 and set(members) == set(sources),
        "work package partition",
    )
    for row in rows:
        domain, source = sources[row["id"]]
        require(row["domain"] == domain, "source domain")
        require(
            row["source_record_sha256"] == canonical_hash(source), "source record drift"
        )
        require(row["profile"] in profiles, "unknown profile")
        require(row["work_package"] in matrix["work_packages"], "unknown work package")
        require(
            row["applicability"]
            == source.get("applicability", "target_documented_with_record_constraints"),
            "model applicability",
        )
        if row["profile"] == "absence":
            require(
                row["id"] == "HW.ANALOG_EMBEDDED"
                and source["applicability"] == "unsupported_embedded",
                "unproved model absence",
            )
    return matrix


class CompletionMatrixTests(unittest.TestCase):
    def matrix(self):
        self.assertTrue(MATRIX.is_file(), "authoritative completion matrix is missing")
        return json.loads(MATRIX.read_text())

    def test_exact_inventory_closure_scopes_and_evidence(self):
        matrix = validate_matrix(self.matrix())
        self.assertEqual(
            sum(r["domain"] == "instruction" for r in matrix["records"]), 161
        )
        self.assertEqual(sum(r["domain"] == "hardware" for r in matrix["records"]), 89)

    def test_authentic_target_and_hardware_pin(self):
        matrix = self.matrix()
        target = matrix["target"]
        root = ET.parse(ROOT / target["fixture"]).getroot()
        self.assertEqual(
            root.findtext("HardwareConfiguration/Plc/Cpu/Reference"), target["model"]
        )
        self.assertEqual(
            root.findtext("ManagementLevel"), target["functional_level_token"]
        )
        self.assertEqual(target["physical_firmware"], "unknown")
        self.assertEqual(
            target["editor"], "EcoStruxure Machine Expert Basic1.4 build484"
        )
        self.assertIn(target["fixture"], {p["path"] for p in matrix["pinned_inputs"]})
        self.assertEqual(
            canonical_hash(xml_value(root.find("HardwareConfiguration"))),
            target["hardware_semantic_sha256"],
        )

    def test_supported_profiles_do_not_promote_other_modes(self):
        matrix = self.matrix()
        profiles = matrix["profiles"]
        self.assertEqual(
            profiles["subroutine"]["phases"]["smbp_graph"], "covered_subset"
        )
        self.assertEqual(
            profiles["timer"]["variants"]["base10ms"]["editor"],
            "saved_and_freshly_reopened",
        )
        self.assertEqual(
            profiles["timer_retention"]["admitted_native_contexts"],
            [
                ["TON", True, False, 1000, "FunctLevelMan21_0"],
                ["TOF", True, False, 1000, "FunctLevelMan21_0"],
            ],
        )
        self.assertEqual(
            profiles["timer_dynamic"]["admitted_native_contexts"],
            [
                ["TON", False, True, 1000, "FunctLevelMan21_0"],
            ],
        )
        self.assertEqual(
            profiles["register_foundation"]["phases"]["cpp_sdk"], "covered_subset"
        )
        self.assertEqual(
            profiles["register_foundation"]["phases"]["smbp_graph"],
            "covered_subset",
        )
        self.assertEqual(
            profiles["communication"]["phases"]["simulator"],
            "not_transaction_validated",
        )
        self.assertEqual(
            profiles["source_structures"]["phases"]["il_vm"],
            "native_opcode_not_implemented",
        )

    def test_dropped_extra_and_duplicate_ids_are_rejected(self):
        for edit in (
            lambda m: m["records"].pop(),
            lambda m: m["records"].append(copy.deepcopy(m["records"][0])),
            lambda m: m["records"][0].update(id="invented.capability"),
        ):
            matrix = self.matrix()
            edit(matrix)
            with self.assertRaises(ValueError):
                validate_matrix(matrix)

    def test_unknown_phase_state_profile_and_bad_partition_are_rejected(self):
        edits = [
            lambda m: m["profiles"]["timer"]["phases"].update(
                invented="covered_subset"
            ),
            lambda m: m["profiles"]["timer"]["phases"].update(editor="complete"),
            lambda m: m["records"][0].update(profile="invented"),
            lambda m: m["work_packages"]["G01"]["ids"].pop(),
        ]
        for edit in edits:
            matrix = self.matrix()
            edit(matrix)
            with self.assertRaises(ValueError):
                validate_matrix(matrix)

    def test_forged_completion_and_source_only_phase_proof_are_rejected(self):
        edits = [
            lambda m: m["profiles"]["timer"].update(whole_record_complete=True),
            lambda m: m["profiles"]["timer"]["phase_evidence"].update(
                cpp_sdk=["m200/timers.py"]
            ),
            lambda m: m["profiles"]["timer"]["phases"].update(
                physical="observed_subset"
            ),
            lambda m: m.update(completion_percentage=100),
        ]
        for edit in edits:
            matrix = self.matrix()
            edit(matrix)
            with self.assertRaises(ValueError):
                validate_matrix(matrix)

    def test_missing_evidence_and_catalogue_drift_are_rejected(self):
        edits = [
            lambda m: m["profiles"]["timer"]["phase_evidence"].update(editor=[]),
            lambda m: m["profiles"]["timer"]["tests"].append("tests/does_not_exist.py"),
            lambda m: m["records"][0].update(source_record_sha256="0" * 64),
            lambda m: m["pinned_inputs"][0].update(sha256="0" * 64),
        ]
        for edit in edits:
            matrix = self.matrix()
            edit(matrix)
            with self.assertRaises(ValueError):
                validate_matrix(matrix)


def xml_value(node):
    return [
        node.tag,
        sorted(node.attrib.items()),
        (node.text or "").strip(),
        [xml_value(child) for child in node],
    ]


if __name__ == "__main__":
    unittest.main()
