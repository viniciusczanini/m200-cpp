#!/usr/bin/env python3
"""Execute only integrated G07 cases with exact before/after compiler/SDK pins."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"tests"))
sys.path.insert(0,str(REPO))
from parallel_semantics.adapters import execute
from parallel_semantics.catalog import inventory
from parallel_semantics.contracts import PendingOracleError


def pinned(freeze,phase):
    source = Path(freeze["source_root"])
    rows = []
    for name,want in freeze["compiler_sdk"].items():
        path = source/name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        rows.append({"path":name,"expected":want,"actual":actual,"match":actual==want})
    return {"phase":phase,"freeze_id":freeze["freeze_id"],"count":len(rows),"pins":rows,
            "status":"pass" if all(r["match"] for r in rows) else "fail"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze",type=Path,required=True)
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--case",action="append")
    parser.add_argument("--engines",default="vm,sdk")
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text())
    if Path(freeze["source_root"]).resolve()!=REPO.resolve():
        raise AssertionError("Refuse execution outside the explicitly frozen source root")
    args.results.mkdir(parents=True,exist_ok=True)
    before = pinned(freeze,"before")
    (args.results/"run-pins-before.json").write_text(json.dumps(before,indent=2)+"\n")
    if before["status"]!="pass":
        raise AssertionError("Compiler/SDK pins changed before execution")
    engines = args.engines.split(",")
    if set(engines)-{"vm","sdk"}:
        raise ValueError("Unknown backend")
    rows = []
    start = time.monotonic()
    for case,disposition,binding in inventory():
        if "G07" not in case.groups or disposition=="DEFERRED_VERSION":
            continue
        if args.case and case.name not in args.case:
            continue
        for engine in engines:
            work = args.results/"cases"/case.name/engine
            work.mkdir(parents=True,exist_ok=True)
            (work/"request.json").write_text(json.dumps(case.request,indent=2)+"\n")
            (work/"expected.json").write_text(json.dumps(case.expected,indent=2)+"\n")
            row = {"case":case.name,"engine":engine,"basis":case.basis,"adapter":case.adapter,"work":str(work)}
            case_start = time.monotonic()
            try:
                if case.oracle_status!="prepared" or case.expected is None:
                    raise PendingOracleError(case.oracle_status)
                actual = execute(binding,engine,case.adapter_input(),REPO,work)
                (work/"actual.json").write_text(json.dumps(actual,indent=2)+"\n")
                if actual!=case.expected:
                    raise AssertionError("Independent literal expectation differs; see expected.json and actual.json")
                row["status"]="pass"
            except Exception as error:
                row.update(status="fail",error_type=type(error).__name__,error=str(error))
                (work/"failure.txt").write_text(traceback.format_exc())
            row["seconds"]=time.monotonic()-case_start
            rows.append(row)
            print(row["status"].upper(),case.name,engine,flush=True)
    after = pinned(freeze,"after")
    (args.results/"run-pins-after.json").write_text(json.dumps(after,indent=2)+"\n")
    report = {"freeze_id":freeze["freeze_id"],"source_root":str(REPO),"timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "scope":"G07 and baseline only; no future packages, 799 suite, GUI, Wine, CI or implementation edits",
              "pin_count":before["count"],"pins_before":before["status"],"pins_after":after["status"],
              "checks":len(rows),"passed":sum(r["status"]=="pass" for r in rows),"failed":sum(r["status"]=="fail" for r in rows),
              "seconds":time.monotonic()-start,"results":rows,
              "pending_other_groups":["G01-expanded","G02-new","G06-expanded","G08-new","G09","G11-new"]}
    if not rows:
        raise AssertionError("No G07 cases selected; empty run is not success")
    report["status"]="pass" if report["failed"]==0 and after["status"]=="pass" else "fail"
    (args.results/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in ["freeze_id","checks","passed","failed","pins_before","pins_after","seconds","status"]}))
    return 0 if report["status"]=="pass" else 1


if __name__=="__main__":
    raise SystemExit(main())
