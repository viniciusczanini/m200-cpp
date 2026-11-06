#!/usr/bin/env python3
"""Run only independent G01/G08 frozen cases; compiler/SDK pins are mandatory."""
import argparse
import datetime
import json
from pathlib import Path
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "tests"), str(REPO)]
from parallel_semantics.combined_report import pinned
from parallel_semantics.adapters import source_pipeline
from parallel_semantics.combined_adapters import constant_bounds
from parallel_semantics.g0108_adapters import cycles, external
from parallel_semantics.g0108_cases import CASES, PENDING
ADAPTERS={"source_pipeline":source_pipeline,"G0108_bounds":constant_bounds,"G0108_cycles":cycles,"G0108_external":external}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--selection", choices=["source", "bounds", "cycles", "external", "all"], required=True)
    p.add_argument("--engines", default="vm,sdk")
    p.add_argument("--case", action="append")
    a = p.parse_args()
    freeze = json.loads(a.freeze.read_text())
    if Path(freeze["source_root"]).resolve() != REPO.resolve():
        raise AssertionError("Refuse mutable or nonmatching source root")
    a.results.mkdir(parents=True, exist_ok=True)
    before = pinned(freeze, "before")
    (a.results / "pins-before.json").write_text(json.dumps(before, indent=2) + "\n")
    if before["status"] != "pass" or before["count"] != 72:
        raise AssertionError("72 compiler/SDK pins must match")
    rows = []
    start = time.monotonic()
    for case in CASES:
        category={"source_pipeline":"source","G0108_bounds":"bounds","G0108_cycles":"cycles","G0108_external":"external"}[case.adapter]
        if a.selection!="all" and category!=a.selection:
            continue
        if a.case and case.name not in a.case:
            continue
        for engine in a.engines.split(","):
            if engine not in case.request.get("engines",["vm","sdk"]):
                continue
            work = a.results / "cases" / case.name / engine
            work.mkdir(parents=True, exist_ok=True)
            (work / "request.json").write_text(json.dumps(case.request, indent=2) + "\n")
            (work / "expected.json").write_text(json.dumps(case.expected, indent=2) + "\n")
            row = {"case": case.name, "engine": engine, "basis": case.basis, "work": str(work)}
            try:
                if case.oracle_status != "prepared":
                    raise AssertionError("Pending oracle is not executable success")
                actual = ADAPTERS[case.adapter](engine=engine, request=case.adapter_input(), repo=REPO, work=work)
                (work / "actual.json").write_text(json.dumps(actual, indent=2) + "\n")
                if actual != case.expected:
                    raise AssertionError("Literal expectation differs; inspect actual.json and expected.json")
                row["status"] = "pass"
            except Exception as error:
                row.update(status="fail", error_type=type(error).__name__, error=str(error))
                (work / "failure.txt").write_text(traceback.format_exc())
            rows.append(row)
            print(row["status"].upper(), case.name, engine, flush=True)
    after = pinned(freeze, "after")
    (a.results / "pins-after.json").write_text(json.dumps(after, indent=2) + "\n")
    report = {"freeze_id": freeze["freeze_id"], "source_root": str(REPO), "selection": a.selection,
              "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "pins_before": before["status"], "pins_after": after["status"], "pin_count": 72,
              "checks": len(rows), "passed": sum(r["status"] == "pass" for r in rows),
              "failed": sum(r["status"] == "fail" for r in rows), "seconds": time.monotonic() - start,
              "results": rows, "native_acceptance": "pending; no graph/SMBP/physical PLC claim",
              "pending_native_questions":len(PENDING),
              "not_run": ["799 full suite", "G02/G07 replay", "GUI/Wine/CI", "G02/G07/G09 replay except affected composition"]}
    if not rows:
        raise AssertionError("Empty selection is not a pass")
    report["status"] = "pass" if report["failed"] == 0 and after["status"] == "pass" else "fail"
    (a.results / "pending-native.json").write_text(json.dumps(PENDING,indent=2)+"\n")
    (a.results / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("freeze_id", "checks", "passed", "failed", "pins_before", "pins_after", "status")}))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
