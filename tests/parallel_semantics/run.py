#!/usr/bin/env python3
"""Local coordinator entrypoint. Preparation is not execution evidence."""

import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT))
from parallel_semantics.catalog import inventory
from parallel_semantics.test_semantics import suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups",help="Comma-separated priority groups")
    parser.add_argument("--engines",default="vm,sdk",help="Explicit vm,sdk selection")
    parser.add_argument("--case",action="append",help="Exact case identity; repeatable")
    parser.add_argument("--repo",type=Path,default=ROOT)
    parser.add_argument("--inventory",action="store_true",help="List prepared/deferred/pending inventory; does not execute a case")
    args = parser.parse_args()
    if args.inventory:
        rows = [{"case":case.name,"groups":case.groups,"covers":case.covers,"disposition":state,
                 "oracle":case.oracle_status,"adapter":case.adapter,"adapter_status":binding["status"],
                 "bound_engines":binding.get("engines",[]),"basis":case.basis} for case,state,binding in inventory()]
        print(json.dumps({"execution":"NOT_EXECUTED","cases":rows},indent=2))
        return 0
    engines = tuple(args.engines.split(","))
    if not engines or set(engines)-{"vm","sdk"}:
        parser.error("--engines must name vm and/or sdk")
    groups = None if not args.groups else set(args.groups.split(","))
    selected = suite(groups,engines,args.repo,None if args.case is None else set(args.case))
    result = unittest.TextTestRunner(verbosity=2).run(selected)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
