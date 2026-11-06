#!/usr/bin/env python3
"""Local-only corpus. No test/compiler/runtime import occurs without --run."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import fnmatch
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from harness import PendingContract, future_cases, sha256  # noqa: E402
from cases_modbus import cases as modbus_cases  # noqa: E402
from cases_project import cases as project_cases  # noqa: E402


def source_hashes():
    watched = sorted((ROOT / "m200").rglob("*.py"))
    watched += sorted((ROOT / "sdk").rglob("*.[hc]pp"))
    watched += sorted((ROOT / "tests/fixtures").glob("*"))
    watched += sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.json"))
    watched += sorted((ROOT / "output/parallel-implementation-2026-11-06/lanes").glob("G*/DELIVERY.md"))
    return {str(path.relative_to(ROOT)): sha256(path) for path in watched if path.is_file()}


def relocate_paths(value, old, new):
    if isinstance(value, dict):
        return {key: relocate_paths(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [relocate_paths(item, old, new) for item in value]
    if isinstance(value, str) and (value == str(old) or value.startswith(str(old) + "/")):
        return str(new) + value[len(str(old)):]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list only; no tests or builds")
    parser.add_argument("--run", action="store_true", help="execute after the integration freeze")
    parser.add_argument("--freeze-id", help="explicit integration freeze identifier from coordinator")
    parser.add_argument("--select", default="*", help="case identity glob")
    parser.add_argument("--existing-only", action="store_true", help="omit future-lane adapter scenarios")
    parser.add_argument("--timer-g07", action="store_true", help="include static Timer project/config/reverse controls")
    parser.add_argument("--modbus-g11", action="store_true", help="include integrated scoped Modbus property controls")
    parser.add_argument("--packed-controls", action="store_true", help="include packed-write literal/full-bank and mutable-snapshot controls")
    parser.add_argument("--final-static", action="store_true", help="include prepared G01/G08/G09 static interop controls after final freeze")
    parser.add_argument("--include-deferred", action="store_true", help="list future-version corpus only; execution remains disabled")
    parser.add_argument("--output", type=Path, help="write a JSON result with hashes and pending records")
    args = parser.parse_args()
    if args.run and not args.freeze_id:
        parser.error("--run requires the coordinator's --freeze-id; preparation never runs tests")
    if args.run and args.list:
        parser.error("choose --list or --run")
    if args.run and args.include_deferred:
        parser.error("DEFERRED_VERSION cases are not authorized for this release")
    all_cases = modbus_cases() + project_cases()
    if not args.existing_only:
        all_cases += future_cases(args.include_deferred)
    if args.timer_g07:
        from cases_timer_g07 import cases as timer_cases

        all_cases += timer_cases()
    if args.modbus_g11:
        from cases_modbus_g11 import cases as integrated_modbus_cases

        all_cases += integrated_modbus_cases()
    if args.packed_controls:
        from cases_packed_controls import cases as packed_cases

        all_cases += packed_cases()
    if args.final_static:
        from cases_final_static import cases as final_static_cases

        all_cases += final_static_cases()
    cases = [case for case in all_cases if fnmatch.fnmatchcase(case.identity, args.select)]
    if not cases:
        parser.error("selector matched no cases")
    if not args.run:
        for case in cases:
            print(f"PREPARED {case.identity} [{case.lane}] {case.description}")
        print(f"{len(cases)} prepared cases; none executed")
        return 0

    # Hash source/SDK/fixtures and lane contracts before and after execution.
    start_hashes = source_hashes()
    report = {
        "freeze_id": args.freeze_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "local corpus only; no official-editor, device, RF, electrical or PLC timing proof",
        "source_hashes": start_hashes,
        "cases": [],
    }
    for case in cases:
        started = time.monotonic()
        entry = {"identity": case.identity, "lane": case.lane, "reference": case.reference}
        with tempfile.TemporaryDirectory(prefix="m200-parallel-interop-") as folder:
            work = Path(folder)
            try:
                entry["observations"] = case.run(work)
                entry["status"] = "PASS"
            except PendingContract as error:
                entry.update(status="PENDING", detail=str(error))
            except AssertionError as error:
                entry.update(status="FAIL", detail=str(error))
            except Exception as error:
                entry.update(status="ERROR", detail=str(error), traceback=traceback.format_exc())
            # Persist generated repro/evidence next to results when requested.
            if args.output:
                import shutil

                target = args.output.parent / (args.output.stem + "-artifacts") / case.identity
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(work, target, dirs_exist_ok=True)
                entry = relocate_paths(entry, work, target.resolve())
                entry["artifact_directory"] = str(target.resolve())
        entry["elapsed_seconds"] = round(time.monotonic() - started, 4)
        report["cases"].append(entry)
        print(f"{entry['status']} {case.identity}" + (f": {entry['detail']}" if "detail" in entry else ""), flush=True)
    end_hashes = source_hashes()
    report["source_changed_during_run"] = start_hashes != end_hashes
    report["counts"] = dict(Counter(entry["status"] for entry in report["cases"]))
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["counts"], sort_keys=True))
    if report["source_changed_during_run"]:
        print("ERROR: integration bytes changed during the run", file=sys.stderr)
        return 3
    if report["counts"].get("FAIL") or report["counts"].get("ERROR"):
        return 1
    if report["counts"].get("PENDING"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
