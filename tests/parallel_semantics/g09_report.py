#!/usr/bin/env python3
"""Run only the independent G09 frozen cases; compiler/SDK pins are mandatory."""
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
from parallel_semantics.g09_adapters import sequence
from parallel_semantics.g09_cases import CASES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--results", type=Path, required=True)
    p.add_argument("--selection", choices=["rtc", "schedule", "all"], required=True)
    p.add_argument("--engines", default="vm,sdk")
    p.add_argument("--case", action="append")
    a = p.parse_args()
    freeze = json.loads(a.freeze.read_text())
    if Path(freeze["source_root"]).resolve() != REPO.resolve():
        raise AssertionError("Refuse mutable or nonmatching source root")
    a.results.mkdir(parents=True, exist_ok=True)
    before = pinned(freeze, "before")
    (a.results / "pins-before.json").write_text(json.dumps(before, indent=2) + "\n")
    if before["status"] != "pass" or before["count"] != 62:
        raise AssertionError("62 compiler/SDK pins must match")
    rows = []
    start = time.monotonic()
    for case in CASES:
        schedule = "schedule_" in case.name
        if a.selection == "rtc" and schedule or a.selection == "schedule" and not schedule:
            continue
        if a.case and case.name not in a.case:
            continue
        for engine in a.engines.split(","):
            work = a.results / "cases" / case.name / engine
            work.mkdir(parents=True, exist_ok=True)
            (work / "request.json").write_text(json.dumps(case.request, indent=2) + "\n")
            (work / "expected.json").write_text(json.dumps(case.expected, indent=2) + "\n")
            row = {"case": case.name, "engine": engine, "basis": case.basis, "work": str(work)}
            try:
                if case.oracle_status != "prepared":
                    raise AssertionError("Pending oracle is not executable success")
                actual = sequence(engine=engine, request=case.adapter_input(), repo=REPO, work=work)
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
              "pins_before": before["status"], "pins_after": after["status"], "pin_count": 62,
              "checks": len(rows), "passed": sum(r["status"] == "pass" for r in rows),
              "failed": sum(r["status"] == "fail" for r in rows), "seconds": time.monotonic() - start,
              "results": rows, "native_acceptance": "pending; RTC_EXEC remains gated; no SMBP claim",
              "not_run": ["799 full suite", "G02/G07 replay", "GUI/Wine/CI", "G01/G08 additions"]}
    if not rows:
        raise AssertionError("Empty selection is not a pass")
    report["status"] = "pass" if report["failed"] == 0 and after["status"] == "pass" else "fail"
    (a.results / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("freeze_id", "checks", "passed", "failed", "pins_before", "pins_after", "status")}))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
