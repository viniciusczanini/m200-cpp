#!/usr/bin/env python3
"""Classify the one preserved run; never invokes product tests."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

GATE = Path(__file__).resolve().parent
def read(name):
    return json.loads((GATE/name).read_text())
def write(name, value):
    (GATE/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

command = read('command.json')
assert command['state'] == 'COMPLETED', 'Do not classify partial run'
freeze = read('freeze.json')
expected = set(freeze['known_pending_failures'])
log = (GATE/'make-check.log').read_text(errors='replace')
ran = re.search(r'^Ran (\d+) tests in ([0-9.]+)s$', log, re.M)
assert ran, 'No complete unittest count'
blocks = list(re.finditer(r'^={70}\n(FAIL|ERROR): (.*?)\n-{70}\n(.*?)(?=^={70}\n|^-{70}\nRan |\Z)', log, re.M|re.S))
(GATE/'failure-blocks').mkdir(exist_ok=True)
failures = []
for i, m in enumerate(blocks, 1):
    body=m.group(0)
    description=m.group(2)
    case_match = re.search(r'parallel_semantics\.[A-Za-z0-9_]+\.(?:vm|sdk)', description)
    case = case_match.group(0) if case_match else description.splitlines()[0]
    pending = case in expected and 'PendingOracleError:' in m.group(3) and m.group(1) == 'FAIL'
    category = 'native-oracle-pending' if pending else 'unexpected-result-requires-review'
    name=f'{i:02d}-'+re.sub(r'[^A-Za-z0-9_.-]+','_',case)+'.txt'
    (GATE/'failure-blocks'/name).write_text(body)
    failures.append({'case':case,'raw_status':m.group(1),'classification':category,
                     'block':'failure-blocks/'+name,'block_sha256':sha(GATE/'failure-blocks'/name),
                     'exception':next((line for line in m.group(3).splitlines() if 'PendingOracleError:' in line),None),
                     'meaning':'Native oracle remains unqualified; raw FAIL retained, no adapter execution or semantic PASS.' if pending else 'Outside authorized six expected pending failures; exact raw block requires review.'})
status = re.search(r'^(FAILED \(.*\)|OK(?: \(.*\))?)$',log,re.M)
assert status, 'No unittest final status'
detail_counts = {k:int(v) for k,v in re.findall(r'(failures|errors|skipped|expected failures|unexpected successes)=(\d+)',status.group(1))}
raw_fail_count=detail_counts.get('failures',0)
raw_error_count=detail_counts.get('errors',0)
skipped=detail_counts.get('skipped',0)
counts=Counter(x['classification'] for x in failures)
observed={x['case'] for x in failures}
audit=read('drift-audit.json')
selected=set(read('snapshot-input-pins-before.json'))
snapshot=GATE/'source'
actual_files={str(p.relative_to(snapshot)) for p in snapshot.rglob('*') if p.is_file() or p.is_symlink()}
unexpected_snapshot_files=sorted(actual_files-selected-{'output'})
write('snapshot-file-audit.json',{'unexpected_files':unexpected_snapshot_files,
    'output_symlink':str((snapshot/'output').readlink()),
    'excluded_helper_presence':{p:(snapshot/p).exists() for p in freeze['excluded_helpers']}})
missing=sorted(expected-observed)
unexpected=[f for f in failures if f['classification'] != 'native-oracle-pending']
problems=[]
if missing: problems.append('Expected pending failure identities missing')
if unexpected: problems.append('Unexpected failure/error blocks')
if len(failures)!=raw_fail_count+raw_error_count: problems.append('Failure block count does not match unittest summary')
if skipped or detail_counts.get('expected failures') or detail_counts.get('unexpected successes'): problems.append('Unexpected skip/xfail/xpass')
if audit['snapshot_drift']: problems.append('Immutable execution inputs changed')
if unexpected_snapshot_files: problems.append('Unexpected files inside snapshot')
if any((snapshot/p).exists() for p in freeze['excluded_helpers']): problems.append('Excluded helper exists inside snapshot')
if audit['core_root_drift']: problems.append('Root core/SDK changed during run')
if command['exit_code']!=2: problems.append('Unexpected make exit code')
root_non_doc_drift=[p for p in audit['root_drift_during_run'] if not (p.startswith('docs/') or p in ['README.md','TASK_QUEUE.md'])]
if root_non_doc_drift: problems.append('Root inputs outside allowed docs/evidence changed')
summary={
    'freeze_id':freeze['freeze_id'],'command':command,'raw_unittest_status':status.group(1),
    'counts':{'run':int(ran.group(1)),'pass':int(ran.group(1))-raw_fail_count-raw_error_count-skipped,
              'fail':raw_fail_count,'error':raw_error_count,'skip':skipped,
              'known_native_pending_fail':counts['native-oracle-pending'],'unexpected_blocks':len(unexpected)},
    'unittest_elapsed_seconds':float(ran.group(2)),
    'full_gate_status':'INCOMPLETE_RAW_FAIL_NATIVE_PENDING' if not problems else 'UNEXPECTED_PROBLEM',
    'scoped_executable_cases_status':'PASS' if not problems else 'REVIEW_REQUIRED',
    'new_observed_defects':0 if not problems else None,
    'known_pending_failures':sorted(expected),'missing_expected_pending':missing,
    'failures':failures,'problems':problems,
    'input_count':freeze['selected_count'],'input_bytes':freeze['bytes'],'core_sdk_count':freeze['core_count'],
    'snapshot_drift_count':len(audit['snapshot_drift']),
    'core_root_drift_count':len(audit['core_root_drift']),
    'root_doc_drift_paths':sorted(audit['root_drift_during_run']),
    'root_non_doc_drift':root_non_doc_drift,
    'unexpected_snapshot_files':unexpected_snapshot_files,
    'artifact_sha256':{name:sha(GATE/name) for name in ['make-check.log','freeze.json','snapshot-input-pins-before.json','snapshot-input-pins-after.json','compiler-sdk-pins.json','command.json','drift-audit.json']},
    'limits':['This is local compiler/VM/SDK/interop verification, not physical/native runtime equivalence.',
              'Six native oracle failures are retained; no whole-family or full gate PASS.',
              'No GUI, CI, standalone codec replay, additional benchmark, source or oracle edit, or retry.'],
}
write('classifications.json',failures)
write('summary.json',summary)
lines=[
    '# Final local G11 gate', '',
    f"Single command: `make check`; raw exit **{command['exit_code']}**; {command['elapsed_seconds']:.3f}s wall time.", '',
    f"**{summary['counts']['run']} tests: {summary['counts']['pass']} PASS, {raw_fail_count} FAIL, {raw_error_count} ERROR, {skipped} SKIP.**", '',
    'Full gate remains incomplete: the six known native PendingOracle failures remain visible as raw FAIL. No unexpected block or newly observed defect.' if not problems else 'Unexpected problems: '+ '; '.join(problems), '',
    f"Inputs: {freeze['selected_count']} files, {freeze['bytes']} bytes; {freeze['core_count']} compiler/SDK pins. Snapshot drift: {len(audit['snapshot_drift'])}; root core drift: {len(audit['core_root_drift'])}.", '',
    'Snapshot uses current tracked bytes plus only the authorized async header and two new G11 test/helper files. The named untracked G01/panel helpers are absent. Outputs were routed outside the snapshot.', '',
    'Root documentation changes during execution are recorded separately: '+(', '.join(sorted(audit['root_drift_during_run'])) or 'none')+'.', '',
    'Pending failures (VM and SDK for each):', '',
    '- G08 SC reset with active CD history: native priority/history oracle pending.',
    '- G01 cold/warm/STOP/RUN edge lifecycle: native oracle pending.',
    '- G08 unresolved SBR/SC/DR endpoint/collision domains: native oracle pending.', '',
    'The test discovery raises PendingOracleError before adapter invocation for these cases. Raw failure blocks and original expected literals remain preserved. G11 async adapter binding is not classified as pending.', '',
    'Evidence: `make-check.log`, `command.json`, `freeze.json`, `compiler-sdk-pins.json`, four before/after input inventories, `drift-audit.json`, `classifications.json`, and `failure-blocks/`.', '',
    'This finite local result does not prove physical PLC runtime equivalence. No expectations, source, or tested input were edited for the run; no rerun was performed.', '',
]
(GATE/'RESULTS.md').write_text('\n'.join(lines))
print(json.dumps({k:summary[k] for k in ['counts','full_gate_status','scoped_executable_cases_status','problems','snapshot_drift_count','core_root_drift_count','root_doc_drift_paths']},indent=2))
