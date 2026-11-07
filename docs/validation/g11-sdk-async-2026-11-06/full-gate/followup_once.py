#!/usr/bin/env python3
"""Authorized one-method follow-up after adding one verified existing corpus."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time

ROOT=Path('/Users/tommy/Offline/projects/m200-cpp')
GATE=Path(__file__).resolve().parent
SOURCE=GATE/'source'
OUT=GATE/'followup-missing-corpus'
OUT.mkdir(exist_ok=True)
assert not (OUT/'command.json').exists(), 'Refuse second focused attempt'
def pin(p):
    data=p.read_bytes()
    return {'type':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
def save(n,d):
    (OUT/n).write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def inventory(paths,root=SOURCE):
    return {p:pin(root/p) for p in paths}
def diff(a,b):
    return {p:{'before':a.get(p),'after':b.get(p)} for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)}
def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

base=json.loads((GATE/'snapshot-input-pins-after.json').read_text())
core=json.loads((GATE/'compiler-sdk-pins.json').read_text())
assert not diff(base,inventory(base)), 'Base snapshot changed before authorized addendum'
assert not diff(core,inventory(core,ROOT)), 'Root core differs from full gate'
manifest_path='docs/capabilities/INDEXED-SOURCES.json'
assert pin(ROOT/manifest_path)==pin(SOURCE/manifest_path)
manifest=json.loads((SOURCE/manifest_path).read_text())
entry=next(e for e in manifest['sources'] if e['id']=='I1')
rel='research/downloads/indexed-sources/'+entry['file']
data=(ROOT/rel).read_bytes()
blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
assert hashlib.sha256(data).hexdigest()==entry['sha256']
assert len(data)==entry['bytes'] and blob==entry['git_blob']
assert not (SOURCE/rel).exists()
save('corpus-provenance.json',{'manifest_path':manifest_path,'manifest_pin':pin(ROOT/manifest_path),
    'manifest_entry':entry,'local_root_path':str(ROOT/rel),'root_pin_before':pin(ROOT/rel),
    'computed_git_blob':blob,'verification':'Existing local bytes match pinned manifest size/SHA256/Git blob; no download or network verification.',
    'dependency_inventory':'original_case reads only manifest I1; synthetic.smbp and all code dependencies already exist in tracked snapshot.',
    'scope':'isolated indexed timer-preset assignment from TM221 project; not whole original project or TM200 native validation.'})
(SOURCE/rel).parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(ROOT/rel,SOURCE/rel)
assert pin(SOURCE/rel)==pin(ROOT/rel)
paths=sorted(set(base)|{rel})
before=inventory(paths)
save('input-pins-before.json',before)
save('core-pins-before.json',inventory(core))
raw_before=pin(GATE/'make-check.log')
save('addition.json',{'added_paths':[rel],'added_count':1,'added_pin':pin(SOURCE/rel),
    'base_input_count':len(base),'followup_input_count':len(paths),
    'base_freeze_pin':pin(GATE/'freeze.json'),'base_raw_log_pin':raw_before,
    'base_changed_paths':diff(base,{p:before[p] for p in base})})
env=os.environ.copy()
env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',TMPDIR=str(GATE/'tmp'),PYTHONPATH=str(SOURCE/'tests'))
argv=['python3','-m','unittest','-v','test_timer_property_stress.TimerPropertyStressTests.test_all_bases_complete_and_write_only_the_explicit_new_report']
command={'argv':argv,'cwd':str(SOURCE),'started_utc':now(),'state':'RUNNING','attempt':1,
    'authorization':'Parent authorized one missing-corpus addition and one affected-method follow-up; no full gate rerun.',
    'environment_overrides':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED','TMPDIR','PYTHONPATH']}}
save('command.json',command)
started=time.monotonic()
with (OUT/'unittest.log').open('wb') as log:
    result=subprocess.run(argv,cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT)
command.update(state='COMPLETED',ended_utc=now(),elapsed_seconds=time.monotonic()-started,exit_code=result.returncode)
save('command.json',command)
after=inventory(paths)
save('input-pins-after.json',after)
save('core-pins-after.json',inventory(core))
audit={'snapshot_input_drift':diff(before,after),'core_snapshot_drift':diff(core,inventory(core)),
    'root_core_drift':diff(core,inventory(core,ROOT)),
    'root_corpus_unchanged':pin(ROOT/rel)==before[rel],
    'raw_full_log_unchanged':pin(GATE/'make-check.log')==raw_before}
save('drift-audit.json',audit)
save('summary.json',{'status':'PASS' if result.returncode==0 and not audit['snapshot_input_drift'] and not audit['root_core_drift'] and audit['raw_full_log_unchanged'] else 'FAIL',
    'command':command,'input_count':len(paths),'added_corpus_count':1,'core_count':len(core),
    'log_pin':pin(OUT/'unittest.log'),'audits':audit,
    'historical_full_gate':'Unchanged: 1045 tests, 1038 PASS, 7 FAIL, 0 ERROR/SKIP; six native pending plus missing corpus.',
    'interpretation':'One focused follow-up only; full gate raw exit/log not replaced or promoted to PASS.'})
print((OUT/'summary.json').read_text())
