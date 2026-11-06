"""Prepare a finite acceptance batch, then execute it only after root freeze.

No compiler/SDK/GUI is invoked by import or by the `prepare` action. `run` is
an explicit local acceptance action and is intentionally not a unittest-discovery
module. Pending catalogue IDs remain visible and fail the default coverage gate.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import traceback
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples/batch_acceptance"
MAX_CASE_FRAMES = 256
EXPECTED_IDS = 250
ACTIVE_PACKAGES = {"G01", "G02", "G06", "G07", "G08", "G09", "G11"}
DEFERRED_ID_PREFIXES = ("float.",)


def active_for_version(row):
    return row["work_package"] in ACTIVE_PACKAGES and not row["id"].startswith(DEFERRED_ID_PREFIXES)


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def inside_root(name):
    path = (ROOT / name).resolve()
    if ROOT not in path.parents or not path.is_file():
        raise ValueError("batch inputs must be existing repository files: " + str(name))
    return path


def canonical_index(value, maximum):
    return isinstance(value, str) and value.isascii() and value.isdecimal() and str(int(value)) == value and 0 <= int(value) <= maximum


def validate_case(case, variants, catalogue_ids):
    if set(case) - {"id", "variant", "selector", "oracle", "scope", "coverage_ids", "frames", "rtc_seed"}:
        raise ValueError("unknown case fields: " + str(case.get("id")))
    if not isinstance(case.get("id"), str) or not case["id"] or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in case["id"]):
        raise ValueError("invalid case identity")
    if case.get("variant") not in variants:
        raise ValueError("case has no declared compatible variant: " + case["id"])
    if not case.get("oracle") or not case.get("scope"):
        raise ValueError("case requires an independent oracle and bounded scope")
    if "rtc_seed" in case:
        seed = case["rtc_seed"]
        fields = {"year", "month", "day", "hours", "minutes", "seconds", "valid", "available"}
        if not isinstance(seed, dict) or set(seed) != fields:
            raise ValueError("RTC observations require an explicit calendar and validity/availability")
        if any(type(seed[key]) is not int for key in fields - {"valid", "available"}) or any(type(seed[key]) is not bool for key in ("valid", "available")):
            raise ValueError("RTC seed fields must be literal integers and BOOLs")
        if not 2000 <= seed["year"] <= 9999:
            raise ValueError("RTC test calendar uses the documented host representation2000..9999")
        datetime(seed["year"], seed["month"], seed["day"], seed["hours"], seed["minutes"], seed["seconds"])
        if variants[case["variant"]].get("observation_adapter") != "rtc_seed_v1":
            raise ValueError("RTC seed requires the explicitly declared rtc_seed_v1 adapter")
    coverage = case.get("coverage_ids")
    if not isinstance(coverage, list) or len(coverage) != len(set(coverage)) or set(coverage) - catalogue_ids:
        raise ValueError("case has unknown or duplicate capability IDs")
    frames = case.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_CASE_FRAMES:
        raise ValueError("case must have1..256 literal frames")
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) - {"label", "dt_ms", "inputs", "words", "expect"}:
            raise ValueError("unsupported frame shape")
        if not frame.get("label"):
            raise ValueError("frame requires a reviewable action label")
        dt = frame.get("dt_ms", 10)
        if type(dt) is not int or not 0 <= dt <= 3600000:
            raise ValueError("invalid virtual scan interval")
        inputs, words = frame.get("inputs", {}), frame.get("words", {})
        if not isinstance(inputs, dict) or any(not canonical_index(k, 23) or type(v) is not bool for k, v in inputs.items()):
            raise ValueError("input levels require canonical ports0..23 and literal BOOLs")
        if not isinstance(words, dict) or any(not canonical_index(k, 7999) or type(v) is not int or not -32768 <= v <= 32767 for k, v in words.items()):
            raise ValueError("word stimuli require canonical public MW addresses and literal i16 values")
        expected = frame.get("expect")
        if not isinstance(expected, dict) or set(expected) - {"output_mask", "words", "memory_bits"}:
            raise ValueError("every frame requires literal expected observations")
        if type(expected.get("output_mask")) is not int or not 0 <= expected["output_mask"] <= 65535:
            raise ValueError("every frame requires an explicit16-output mask")
        for key, value in expected.get("words", {}).items():
            if not canonical_index(key, 7999) or type(value) is not int or not -32768 <= value <= 32767:
                raise ValueError("invalid literal expected public word")
        for key, value in expected.get("memory_bits", {}).items():
            if not canonical_index(key, 1023) or type(value) is not bool:
                raise ValueError("invalid literal expected public memory bit")


def load_inputs():
    matrix_path = ROOT / "docs/capabilities/COMPLETION-MATRIX.json"
    matrix = read_json(matrix_path)
    records = matrix["records"]
    catalogue_ids = {row["id"] for row in records}
    if len(records) != EXPECTED_IDS or len(catalogue_ids) != EXPECTED_IDS:
        raise ValueError("catalogue identity changed; review all finite250 row classifications")
    plan = read_json(HERE / "coverage_plan.json")
    classified = {row["id"]: row for row in plan["records"]}
    if len(classified) != EXPECTED_IDS or set(classified) != catalogue_ids:
        raise ValueError("coverage plan must classify every catalogue ID exactly once")
    profiles = read_json(EXAMPLES / "profiles.json")
    variants = {row["id"]: row for row in profiles["variants"]}
    if len(variants) != len(profiles["variants"]):
        raise ValueError("duplicate resource profile")
    cases = read_json(EXAMPLES / "cases.json")["cases"]
    input_files = [matrix_path, HERE / "coverage_plan.json", EXAMPLES / "profiles.json", EXAMPLES / "cases.json"]
    for descriptor in sorted((HERE / "integrations").glob("*.json")):
        data = read_json(descriptor)
        if data.get("work_package") not in ACTIVE_PACKAGES:
            raise ValueError("DEFERRED_VERSION integration is outside the Natal acceptance scope: " + str(descriptor))
        notice = data.get("main_integration", {})
        if notice.get("status") != "confirmed" or not notice.get("notice") or not notice.get("compiler_pins"):
            raise ValueError("lane delivery is not proof of main integration: " + str(descriptor))
        for path, expected in notice["compiler_pins"].items():
            if digest(inside_root(path)) != expected:
                raise ValueError("integrated API/compiler pin changed: " + path)
        variant = data["variant"]
        if variant["id"] in variants:
            raise ValueError("integration cannot replace an existing variant")
        if variant.get("local_transport", "none") != "none":
            raise ValueError("new transport/event contracts require a reviewed observation bridge")
        variants[variant["id"]] = variant
        new_cases_path = inside_root(data["cases"])
        new_cases = read_json(new_cases_path)["cases"]
        if "case_ids" in data:
            selected = data["case_ids"]
            if not isinstance(selected, list) or any(not isinstance(value, str) for value in selected) or len(selected) != len(set(selected)):
                raise ValueError("integration case_ids requires unique explicit identities")
            available = {case["id"] for case in new_cases}
            if not selected or set(selected) - available:
                raise ValueError("integration selected missing literal cases")
            new_cases = [case for case in new_cases if case["id"] in selected]
        if any(case["variant"] != variant["id"] for case in new_cases):
            raise ValueError("integration cases must belong to their own resource profile")
        cases += new_cases
        input_files += [descriptor, new_cases_path]
    identities = set()
    for case in cases:
        validate_case(case, variants, catalogue_ids)
        if case["id"] in identities:
            raise ValueError("duplicate scenario identity")
        identities.add(case["id"])
    for name, variant in variants.items():
        for key in ("source", "template"):
            input_files.append(inside_root(variant[key]))
        matching = {case["id"] for case in cases if case["variant"] == name}
        if not matching or matching != set(variant["scenarios"]):
            raise ValueError("variant scenario manifest differs from its literal cases: " + name)
        if variant["local_transport"] not in ("none", "none; expected error255/15 is not a successful transaction"):
            raise ValueError("undeclared observation transport")
    return matrix_path, records, classified, variants, cases, input_files


def prepare(output, selected_variants=None):
    matrix_path, records, classified, variants, cases, input_files = load_inputs()
    if selected_variants:
        selected = set(selected_variants)
        if selected - set(variants):
            raise ValueError("selected unknown resource variants: " + repr(sorted(selected - set(variants))))
        variants = {name: variant for name, variant in variants.items() if name in selected}
        cases = [case for case in cases if case["variant"] in selected]
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("batch destination already exists; preserve it and choose a new path")
    output.mkdir(parents=True)
    by_id = {row["id"]: [] for row in records}
    for case in cases:
        for capability in case["coverage_ids"]:
            by_id[capability].append(case["id"])
    inventory = []
    for row in records:
        planned = classified[row["id"]]
        disposition = planned["disposition"]
        if not active_for_version(row):
            disposition = "DEFERRED_VERSION"
        elif by_id[row["id"]] and disposition == "pending_case_or_contract":
            disposition = "prepared_source_subset"
        inventory.append({
            **row,
            "disposition": disposition,
            "scenarios": by_id[row["id"]],
            "local": "DEFERRED_VERSION" if disposition == "DEFERRED_VERSION" else "not_run",
            "editor": "DEFERRED_VERSION" if disposition == "DEFERRED_VERSION" else "not_run",
            "simulator": "DEFERRED_VERSION" if disposition == "DEFERRED_VERSION" else "not_run",
            "physical": "DEFERRED_VERSION" if disposition == "DEFERRED_VERSION" else "pending",
        })
    products = []
    for name, variant in variants.items():
        directory = output / name
        directory.mkdir()
        source = inside_root(variant["source"])
        local_source = directory / source.name
        local_source.write_bytes(source.read_bytes())
        selected = [case for case in cases if case["variant"] == name]
        dump(directory / "cases.json", {"schema": "m200.batch-acceptance.cases.v1", "cases": selected})
        products.append({
            **variant,
            "source_original": variant["source"],
            "source": str(local_source),
            "source_sha256": digest(local_source),
            "template_sha256": digest(inside_root(variant["template"])),
            "case_file": str(directory / "cases.json"),
            "case_file_sha256": digest(directory / "cases.json"),
            "project": str(directory / "generated.smbp"),
            "local": "not_run", "smbp": "not_generated", "editor": "not_run", "simulator": "not_run",
        })
    pin_files = set(input_files) | set((ROOT / "m200").glob("*.py")) | {ROOT / "sdk/plc.hpp", ROOT / "m200c", HERE / "batch.py", HERE / "native_probe.py"}
    pins = {str(path.relative_to(ROOT)): digest(path) for path in sorted(pin_files)}
    deliveries = []
    lanes = ROOT / "output/parallel-implementation-2026-11-06/lanes"
    for pattern in ("*/CONTRACT.md", "*/DELIVERY.md"):
        for path in sorted(lanes.glob(pattern)):
            deliveries.append({"path": str(path.relative_to(ROOT)), "sha256": digest(path), "status": "seen_not_assumed_integrated"})
    manifest = {
        "schema": "m200.batch-acceptance.manifest.v1",
        "status": "prepared_not_executed",
        "target": "TM200CE40T",
        "inventory_count": len(inventory),
        "active_work_packages": sorted(ACTIVE_PACKAGES),
        "deferred_id_prefixes": list(DEFERRED_ID_PREFIXES),
        "deferred_ids": [row["id"] for row in inventory if row["disposition"] == "DEFERRED_VERSION"],
        "full_parity": "incomplete; deferred resources are not accepted or removed",
        "matrix_sha256": digest(matrix_path),
        "baseline": {"tests": 799, "status": "historical_root_frozen_pass", "rerun_by_preparation": False, "reference": "output/register-integration-2026-11-06/full/result.json"},
        "phase_rules": {"local": "only explicit run can set results", "editor": "root final native batch only", "simulator": "distinct exact-artifact runtime observations", "physical": "never inferred from local/editor/simulator agreement"},
        "input_pins": pins,
        "lane_documents": deliveries,
        "products": products,
        "selected_variant_ids": list(variants),
        "inventory": inventory,
    }
    dump(output / "manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "products": len(products), "inventory_count": len(inventory), "manifest": str(output / "manifest.json")}, indent=2))


def signed_word(value):
    raw = value & 65535
    return raw - 65536 if raw >= 32768 else raw


def observe_machine(program, frames, watch_words, *, rtc_seed=None, watch_bits=()):
    from m200.il import Machine
    if rtc_seed is None:
        machine = Machine(program)
    else:
        from m200.rtc import RtcClock
        machine = Machine(program, rtc=RtcClock(**rtc_seed))
    observed = []
    for frame in frames:
        for index, value in frame.get("words", {}).items():
            machine.words[int(index)] = value
        levels = machine.step(frame.get("inputs", {}), frame.get("dt_ms", 10))
        row = {"output_mask": sum(1 << i for i, value in enumerate(levels) if value), "words": {str(index): signed_word(machine.words[index]) for index in watch_words}}
        if watch_bits:
            row["memory_bits"] = {str(index): bool(machine.memory[index]) for index in watch_bits}
        observed.append(row)
    return observed


def compare(case, observed):
    if len(observed) != len(case["frames"]):
        raise AssertionError("incomplete observation sequence: " + case["id"])
    for number, (frame, actual) in enumerate(zip(case["frames"], observed), 1):
        expected = frame["expect"]
        if actual["output_mask"] != expected["output_mask"]:
            raise AssertionError("%s frame%d %s: Q expected%d, got%d" % (case["id"], number, frame["label"], expected["output_mask"], actual["output_mask"]))
        for word, value in expected.get("words", {}).items():
            if actual["words"].get(word) != value:
                raise AssertionError("%s frame%d %s: MW%s expected%d, got%s" % (case["id"], number, frame["label"], word, value, actual["words"].get(word)))
        for bit, value in expected.get("memory_bits", {}).items():
            if actual.get("memory_bits", {}).get(bit) is not value:
                raise AssertionError("%s frame%d %s: M%s expected%s, got%s" % (case["id"], number, frame["label"], bit, value, actual.get("memory_bits", {}).get(bit)))


def changed_pins(pins):
    return [name for name, expected in pins.items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]


def compare_resource_shape(program, expected):
    actual = {
        "timer_ids": sorted(program.timers),
        "subroutine_sections": {str(number): definition.section_number for number, definition in sorted(program.subroutines.items())},
        "shift_bit_register_ids": sorted(getattr(program, "shift_bit_registers", {})),
        "step_counter_ids": sorted(getattr(program, "step_counters", {})),
        "drum_ids": sorted(getattr(program, "drums", {})),
        "rtc_ids": sorted(getattr(program, "rtcs", {})),
        "schedule_ids": sorted(getattr(program, "schedules", {})),
    }
    for key, value in expected.items():
        if key not in actual or actual[key] != value:
            raise AssertionError("shared native resource shape differs: %s expected%s, got%s" % (key, value, actual.get(key)))


def run(output, allow_incomplete):
    from m200.frontend import compile_source
    from m200.model import Program
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp
    from native_probe import observe_native

    output = Path(output).resolve()
    manifest = read_json(output / "manifest.json")
    if manifest["status"] != "prepared_not_executed":
        raise ValueError("batch already executed; prepare a new frozen batch")
    changes = changed_pins(manifest["input_pins"])
    if changes:
        raise ValueError("batch inputs changed after preparation: " + repr(changes))
    results = {"schema": "m200.batch-acceptance.results.v1", "status": "running", "variants": {}, "editor": "not_run", "simulator": "not_run", "physical": "pending"}
    failed_cases = set()
    completed_cases = set()
    for variant in manifest["products"]:
        name = variant["id"]
        result = {"status": "running", "cases": {}}
        results["variants"][name] = result
        folder = output / name
        try:
            source = Path(variant["source"])
            if digest(source) != variant["source_sha256"]:
                raise ValueError("prepared source changed")
            if digest(variant["case_file"]) != variant["case_file_sha256"]:
                raise ValueError("prepared literal cases/oracles changed")
            program = compile_source(source)
            decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
            dump(folder / "program.m200.json", program.as_dict())
            project = Path(variant["project"])
            write_project(program, inside_root(variant["template"]), project)
            imported = load_project(project)
            reverse = folder / "actual_project_reverse.cpp"
            reverse.write_text(to_cpp(imported))
            rebuilt = compile_source(reverse)
            rebuilt_project = folder / "rebuilt.smbp"
            write_project(rebuilt, inside_root(variant["template"]), rebuilt_project)
            readback = load_project(rebuilt_project)
            for shape_candidate in (program, decoded, imported, rebuilt, readback):
                compare_resource_shape(shape_candidate, variant.get("expected_resources", {}))
            result["generated_project"] = {"bytes": project.stat().st_size, "sha256": digest(project)}
            result["rebuilt_project"] = {"bytes": rebuilt_project.stat().st_size, "sha256": digest(rebuilt_project)}
            for case in read_json(variant["case_file"])["cases"]:
                case_result = {"status": "running", "routes": {}}
                result["cases"][case["id"]] = case_result
                try:
                    frames = case["frames"]
                    rtc_seed = case.get("rtc_seed")
                    watch_words = sorted({int(word) for frame in frames for word in frame["expect"].get("words", {})})
                    watch_bits = sorted({int(bit) for frame in frames for bit in frame["expect"].get("memory_bits", {})})
                    routes = {
                        "compiled_machine": lambda: observe_machine(program, frames, watch_words, rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "json_machine": lambda: observe_machine(decoded, frames, watch_words, rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "project_readback_machine": lambda: observe_machine(imported, frames, watch_words, rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "recompiled_reverse_machine": lambda: observe_machine(rebuilt, frames, watch_words, rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "rebuilt_project_readback_machine": lambda: observe_machine(readback, frames, watch_words, rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "original_cpp_native": lambda: observe_native(source, frames, watch_words, folder / case["id"] / "original-native", ROOT / "sdk", rtc_seed=rtc_seed, watch_bits=watch_bits),
                        "actual_project_reverse_native": lambda: observe_native(reverse, frames, watch_words, folder / case["id"] / "reverse-native", ROOT / "sdk", rtc_seed=rtc_seed, watch_bits=watch_bits),
                    }
                    for route, callback in routes.items():
                        observed = callback()
                        compare(case, observed)
                        case_result["routes"][route] = {"status": "passed", "frames": len(frames), "observations": observed}
                    case_result["status"] = "passed_literal_subset"
                    completed_cases.add(case["id"])
                except Exception as error:
                    case_result.update(status="failed", error=str(error), traceback=traceback.format_exc())
                    failed_cases.add(case["id"])
            result["status"] = "failed" if any(case["status"] == "failed" for case in result["cases"].values()) else "passed_literal_subset"
        except Exception as error:
            result.update(status="failed", error=str(error), traceback=traceback.format_exc())
            failed_cases.update(variant["scenarios"])
        dump(output / "results.json", results)
    pending = []
    for row in manifest["inventory"]:
        scenarios = set(row["scenarios"])
        if row["disposition"] == "DEFERRED_VERSION":
            row["local"] = "DEFERRED_VERSION"
        elif scenarios & failed_cases:
            row["local"] = "failed"
        elif scenarios and scenarios <= completed_cases:
            row["local"] = "passed_literal_subset"
        else:
            row["local"] = "not_run_pending_case_or_contract"
            pending.append(row["id"])
    changes = changed_pins(manifest["input_pins"])
    results.update(
        pending_ids=pending,
        deferred_ids=manifest["deferred_ids"],
        full_parity="incomplete",
        failed_cases=sorted(failed_cases),
        changed_input_pins=changes,
        all_pinned_inputs_unchanged=not changes,
        status="failed" if failed_cases or changes else "passed_prepared_subset_with_pending_ids" if pending else "passed_declared_natal_subsets_full_parity_incomplete",
    )
    manifest["status"] = results["status"]
    dump(output / "results.json", results)
    dump(output / "manifest.json", manifest)
    dump(output / "native-batch.json", {"status": "not_run", "target": "official_local_simulator_only", "products": [{"variant": row["id"], "project": row["project"], "cases": row["case_file"], "project_sha256": results["variants"][row["id"]].get("generated_project", {}).get("sha256"), "local_status": results["variants"][row["id"]]["status"], "ready_for_final_native_batch": results["variants"][row["id"]]["status"] == "passed_literal_subset", "editor": "not_run", "simulator": "not_run", "physical": "pending"} for row in manifest["products"]]})
    print(json.dumps({"status": results["status"], "failed_cases": results["failed_cases"], "pending_id_count": len(pending), "all_pinned_inputs_unchanged": not changes, "results": str(output / "results.json")}, indent=2))
    return 1 if failed_cases or changes else 2 if pending and not allow_incomplete else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    preparing = sub.add_parser("prepare", help="Write a frozen finite manifest/source/trace batch; no build or execution")
    preparing.add_argument("--output", required=True)
    preparing.add_argument("--variant", action="append", help="Prepare only explicitly selected variants; keep every catalogue ID classified")
    running = sub.add_parser("run", help="Run local compiler/native acceptance only after explicit root freeze")
    running.add_argument("--batch", required=True)
    running.add_argument("--allow-incomplete", action="store_true", help="Allow a successful prepared subset to return0 while preserving all pending IDs in the report")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(args.output, args.variant)
            return 0
        return run(args.batch, args.allow_incomplete)
    except Exception as error:
        print("BATCH-E: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
