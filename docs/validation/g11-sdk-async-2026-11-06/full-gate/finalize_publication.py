#!/usr/bin/env python3
"""Package existing gate evidence; does not run tests or alter source/oracles."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

G=Path(__file__).resolve().parent
ROOT=Path('/Users/tommy/Offline/projects/m200-cpp')
F=G/'followup-missing-corpus'
P=G/'publication-proposal'
assert not P.exists(), 'Do not overwrite publication proposal'
def load(p): return json.loads(p.read_text())
def save(p,d): p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def pin(p):
    b=p.read_bytes(); return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

s=load(G/'summary.json')
shutil.copy2(G/'summary.json',G/'preliminary-summary.json')
follow=load(F/'summary.json')
assert follow['status']=='PASS' and follow['command']['exit_code']==0
assert '\nRan 1 test in ' in (F/'unittest.log').read_text()
assert (F/'unittest.log').read_text().rstrip().endswith('OK')
raw=load(G/'raw-result.json')
assert pin(G/'make-check.log')['sha256']==raw['log']['sha256']
prov=load(F/'corpus-provenance.json')
cls=load(G/'classifications.json')
unexpected=[x for x in cls if x['classification']!='native-oracle-pending']
assert len(unexpected)==1 and unexpected[0]['case'].startswith('test_all_bases_complete_and_write_only_the_explicit_new_report ')
issue=unexpected[0]
issue.update(classification='missing-local-test-corpus',
    observed_exception='FileNotFoundError: research/downloads/indexed-sources/didim99__TSTU__425372b07a34.smbp',
    meaning='Real snapshot/test-input packaging gap: existing untracked public corpus was excluded by the authorized tracked-only selection. No compiler/SDK assertion failed; the original-case read could not begin.',
    static_evidence={'test':'tests/test_timer_property_stress.py:17-28',
        'read':'tests/stress/timer_properties.py:125-129',
        'manifest':'docs/capabilities/INDEXED-SOURCES.json:I1',
        'root_file_matches_manifest':True,'corpus_sha256':prov['manifest_entry']['sha256'],
        'root_file_was_untracked_at_gate_start':True},
    followup={'status':'PASS','command':'followup-missing-corpus/command.json',
        'log':'followup-missing-corpus/unittest.log','added_inputs':1,'source_or_oracle_edits':0,'full_gate_retry':False})
save(G/'classifications.json',cls)
attrdiff=''.join(difflib.unified_diff((G/'source/.gitattributes').read_text().splitlines(True),
    (ROOT/'.gitattributes').read_text().splitlines(True),fromfile='snapshot/.gitattributes',tofile='root/.gitattributes'))
(G/'root-publication-metadata.diff').write_text(attrdiff)
save(G/'classification-evidence.json',{
    'missing_input':prov,'root_metadata_change':{'path':'.gitattributes','diff':'root-publication-metadata.diff',
        'meaning':'Added raw-log whitespace/text preservation rule for docs/validation/g11-sdk-async-2026-11-06/**/*.log after snapshot creation; snapshot bytes unchanged.'},
    'native_pending_sources':['tests/parallel_semantics/source_cases.py:12-24,166-172',
        'tests/parallel_semantics/priority_cases.py:71-74,91-94',
        'tests/parallel_semantics/test_semantics.py:25-27'],
    'no_reexecution':'Static classification plus exactly one authorized affected-method follow-up; full raw log remains unchanged.'})
s.update(full_gate_status='RAW_FAIL_6_NATIVE_PENDING_PLUS_1_MISSING_CORPUS',
    scoped_executable_cases_status='1038_PASS_IN_FULL_RUN_PLUS_1_PASS_IN_AUTHORIZED_FOLLOWUP',
    new_observed_defects=0,new_observed_compiler_sdk_defects=0,
    test_input_packaging_gap_count=1,unbound_adapter_failures=0,obsolete_assertion_failures=0,
    failures=cls,
    problems=['Historical full run includes one missing-local-corpus failure; raw FAIL and exit 2 retained.',
        'Six native-oracle PendingOracle failures remain unqualified and visible.'],
    root_non_doc_drift_classification='Only .gitattributes raw-publication-log preservation rule; recorded separately from source/test/core drift.',
    authorized_followup={'run':1,'pass':1,'fail':0,'error':0,'skip':0,
        'exit_code':0,'elapsed_seconds':follow['command']['elapsed_seconds'],
        'added_inputs':1,'core_sdk_drift':0,'all_followup_input_drift':0,
        'summary':'followup-missing-corpus/summary.json','full_raw_log_unchanged':True},
    publication_interpretation='Full run: 1038 PASS / 7 FAIL. Separate affected-method follow-up: 1 PASS. Remaining semantic gaps are six native pending oracles; no whole/full gate PASS claim.',
    completed_work='Finite authorized verification and packaging complete; no additional validation started.')
save(G/'summary.json',s)
(G/'RESULTS.md').write_text('''# Final local G11 gate

One `make check`: **1,045 tests — 1,038 PASS, 7 FAIL, 0 ERROR, 0 SKIP**. Raw make exit **2**, wall time **334.358 s**. The raw log is preserved unchanged.

Six failures are the known native PendingOracle cases (VM + SDK for each): G01 cold/warm/STOP/RUN edge lifecycle; G08 SC reset with active CD history; G08 unresolved SBR/SC/DR endpoint/collision domains. Discovery fails explicitly before adapter invocation. These are not PASS.

The seventh failure is a test-input packaging gap. `test_timer_property_stress.TimerPropertyStressTests.test_all_bases_complete_and_write_only_the_explicit_new_report` completed its 15 generated Ton/Tof/Pulse controls, then could not read the untracked I1 corpus omitted by the authorized tracked-only snapshot. The local original matches the pinned manifest: 114,221 bytes, SHA256 `a4307729f0864133e414517ef49c37e6648f29d7403a8f9737e2f7367461a738`, Git blob `425372b07a34946b6363b78bd15a5fbf8727cc98`.

Root authorized one addendum: copy only that verified corpus and execute only the affected method once. **Follow-up: 1 PASS, exit 0, 35.063 s.** No source, test, expected value, or native oracle changed. No full-gate retry was performed. The raw full result remains 1,038/7; it was not rewritten as green.

Full snapshot: 1,076 inputs, 114,506,706 bytes; **74 core/SDK pins unchanged**. All selected execution inputs were unchanged through the full run. The follow-up has 1,077 inputs after the single documented corpus addition, with zero further input/core drift. Excluded G01 helper and panel-decoder files are absent. All runtime outputs are outside the snapshot.

Root changes during the full run were `docs/PARITY.md`, `docs/ROADMAP.md`, and a `.gitattributes` rule preserving raw publication logs. Exact drift is recorded; the tested snapshot was unaffected.

No newly observed compiler/SDK defect remains from this gate. Six native oracle gaps remain. This local result does not establish full parity or physical PLC runtime equivalence.

Publication proposal contains only logs, commands, classifications, provenance, pins and audits. It excludes the source snapshot, corpus bytes, binaries, temporary files, and generated runtime artifacts.
''')
basefiles=['make-check.log','command.json','summary.json','classifications.json','classification-evidence.json',
    'compiler-sdk-pins.json','freeze.json','copy-audit.json','raw-result.json','drift-audit.json',
    'root-input-pins-before.json','root-input-pins-after-copy.json','root-input-pins-after-run.json',
    'snapshot-input-pins-before.json','snapshot-input-pins-after.json','snapshot-file-audit.json',
    'root-publication-metadata.diff','RESULTS.md','freeze_and_run.py','classify.py','followup_once.py','finalize_publication.py']
for name in basefiles:
    dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(G/name,dest)
for sub in ['failure-blocks','followup-missing-corpus']:
    shutil.copytree(G/sub,P/sub)
files={str(p.relative_to(P)):pin(p) for p in sorted(P.rglob('*')) if p.is_file()}
assert pin(P/'make-check.log')==pin(G/'make-check.log')
assert not any(p.endswith(('.smbp','.o','.so','.dylib','.a','.exe')) for p in files)
save(P/'PACKAGE-MANIFEST.json',{'files':files,'file_count':len(files),
    'total_bytes':sum(v['bytes'] for v in files.values()),
    'raw_full_log_unchanged':True,'snapshot_included':False,'runtime_artifacts_included':False,
    'source_or_oracle_changes':False,'full_gate_runs':1,'authorized_followup_method_runs':1})
print(json.dumps({'publication_proposal':str(P),'files':len(files)+1,
    'bytes_excluding_manifest':sum(v['bytes'] for v in files.values()),
    'full_raw_counts':s['counts'],'followup_status':follow['status'],
    'full_log_sha256':pin(G/'make-check.log')['sha256'],
    'summary_sha256':pin(G/'summary.json')['sha256']},indent=2))
