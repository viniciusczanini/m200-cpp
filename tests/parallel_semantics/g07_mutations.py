#!/usr/bin/env python3
"""Semantic mutations in memory/Clang stdin; never edits frozen implementation."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import types
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"tests"));sys.path.insert(0,str(REPO))
from parallel_semantics.adapters import execute
from parallel_semantics.catalog import inventory
from parallel_semantics.g07_report import pinned


MUTANTS = [
    {"name":"paused_equality_is_not_smaller","case":"G07_retained_dynamic_TON_paused_equality_then_smaller",
     "python_old":"and value < self.current","python_new":"and value <= self.current",
     "cpp_old":"paused&&ticks<current","cpp_new":"paused&&ticks<=current"},
    {"name":"warm_restart_must_exclude_outage","case":"G07_TON_outage_preserves_fractional_phase",
     "python_old":"self.start += now - self.offline_since","python_new":"self.start += 0",
     "cpp_old":"started+=(long long)(detail::now_ms-(unsigned long long)offline_since);","cpp_new":"started+=0;"},
    {"name":"getters_must_freeze_during_power_off","case":"G07_TP_outage_does_not_complete_unpowered_pulse",
     "python_old":"if self.offline_since is not None:\n            return","python_new":"if False:\n            return",
     "cpp_old":"if(offline_since>=0)return;","cpp_new":"if(false)return;"},
    {"name":"dynamic_preset_must_update_at_next_tick","case":"G07_retention_and_dynamic_preset_are_separate_states",
     "python_old":"if self.dynamic:\n                    self.active_preset = self.preset","python_new":"if False:\n                    self.active_preset = self.preset",
     "cpp_old":"if(dynamic)active=configured;","cpp_new":"if(false)active=configured;"},
    {"name":"retention_cannot_be_ignored","case":"G07_retained_dynamic_TON_paused_equality_then_smaller",
     "python_old":"self.retentive = config.retentive","python_new":"self.retentive = False",
     "cpp_old":"retain(ret),dynamic(dyn)","cpp_new":"retain(false),dynamic(dyn)"},
    {"name":"TON_false_must_reset_current_activation","case":"G07_internal_Q_completes_while_skipped_wired_coil_holds",
     "python_old":"if not enabled:\n                if not self.retentive or self.completed:","python_new":"if False:\n                if not self.retentive or self.completed:",
     "cpp_old":"if(!enabled){if(!retain||completed)current=0;started=-1;result=false;completed=false;}","cpp_new":"if(false){if(!retain||completed)current=0;started=-1;result=false;completed=false;}"},
]


def altered(text,old,new):
    if text.count(old)!=1:
        raise AssertionError("Mutation anchor must match exactly once: "+old)
    return text.replace(old,new,1)


def first_difference(actual,expected):
    if isinstance(actual,list) and isinstance(expected,list):
        for n,(left,right) in enumerate(zip(actual,expected)):
            if left!=right:return {"position":n,"expected":right,"actual":left}
    return {"expected":expected,"actual":actual}


def python_mutant(case,binding,mutant,work):
    import m200.il as il
    text = (REPO/"m200/timers.py").read_text()
    changed = altered(text,mutant["python_old"],mutant["python_new"])
    module = types.ModuleType("m200._semantic_mutation")
    module.__package__="m200"
    exec(compile(changed,"<G07-memory-mutant>","exec"),module.__dict__)
    original = il.TimerState
    try:
        il.TimerState=module.TimerState
        return execute(binding,"vm",case.adapter_input(),REPO,work)
    finally:
        il.TimerState=original


def sdk_mutant(case,binding,mutant,work):
    header = (REPO/"sdk/plc.hpp").read_text()
    changed = altered(header,mutant["cpp_old"],mutant["cpp_new"])
    original_run = subprocess.run
    compiles = []
    def redirected(command,*args,**kwargs):
        positions = [n for n,value in enumerate(command) if isinstance(value,str) and value.endswith(".cpp")]
        if "-std=c++17" in command and positions:
            position = positions[0]
            body = Path(command[position]).read_text()
            def inline_source(match):
                target = Path(match[1])
                return target.read_text() if target.is_absolute() and target.is_file() else match[0]
            body = re.sub(r'#include "([^"\n]+)"',inline_source,body)
            body = body.replace("#include <plc.hpp>","")
            translation_unit = "#define PLC_NATIVE\n"+changed.replace("#pragma once", "",1)+"\n"+body
            edited=list(command)
            edited[position:position+1]=["-x","c++","-"]
            kwargs["input"]=translation_unit
            compiles.append({"translation_unit_sha256":hashlib.sha256(translation_unit.encode()).hexdigest(),"bytes":len(translation_unit.encode()),"command":edited})
            return original_run(edited,*args,**kwargs)
        return original_run(command,*args,**kwargs)
    with patch("subprocess.run",redirected):
        result=execute(binding,"sdk",case.adapter_input(),REPO,work)
    if not compiles:raise AssertionError("No real mutant SDK was compiled")
    (work/"stdin-compilations.json").write_text(json.dumps(compiles,indent=2)+"\n")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze",type=Path,required=True);parser.add_argument("--results",type=Path,required=True)
    args=parser.parse_args();freeze=json.loads(args.freeze.read_text())
    if Path(freeze["source_root"]).resolve()!=REPO.resolve():raise AssertionError("Wrong frozen source root")
    args.results.mkdir(parents=True,exist_ok=True)
    before=pinned(freeze,"before_mutations")
    if before["status"]!="pass":raise AssertionError("Source pins changed")
    by_name={case.name:(case,binding) for case,state,binding in inventory() if "G07" in case.groups}
    rows=[]
    for mutant in MUTANTS:
        case,binding=by_name[mutant["case"]]
        for engine,apply in [("vm",python_mutant),("sdk",sdk_mutant)]:
            directory=args.results/mutant["name"]/engine;directory.mkdir(parents=True,exist_ok=True)
            control=execute(binding,engine,case.adapter_input(),REPO,directory)
            if control!=case.expected:raise AssertionError("Unmutated positive control failed: "+case.name)
            actual=apply(case,binding,mutant,directory)
            caught=actual!=case.expected
            row={"mutation":mutant["name"],"case":case.name,"engine":engine,"control":"pass","status":"caught" if caught else "survived",
                 "kind":"Python class rebuilt in memory" if engine=="vm" else "SDK header altered only in Clang stdin",
                 "change":{"old":mutant["python_old"] if engine=="vm" else mutant["cpp_old"],"new":mutant["python_new"] if engine=="vm" else mutant["cpp_new"]}}
            if caught:row["first_difference"]=first_difference(actual,case.expected)
            (directory/"mutated-observation.json").write_text(json.dumps(actual,indent=2)+"\n")
            rows.append(row);print(row["status"].upper(),mutant["name"],engine,flush=True)
    after=pinned(freeze,"after_mutations")
    report={"freeze_id":freeze["freeze_id"],"mutation_count":len(rows),"caught":sum(r["status"]=="caught" for r in rows),"results":rows,
            "pins_before":before,"pins_after":after,"implementation_files_changed":False}
    report["status"]="pass" if report["caught"]==len(rows) and after["status"]=="pass" else "fail"
    (args.results/"results.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({key:report[key] for key in ["mutation_count","caught","status"]}))
    return 0 if report["status"]=="pass" else 1


if __name__=="__main__":raise SystemExit(main())
