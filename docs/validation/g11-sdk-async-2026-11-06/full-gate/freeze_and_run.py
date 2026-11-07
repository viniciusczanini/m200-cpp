#!/usr/bin/env python3
"""One authorized final local run; immutable input inventory, external outputs."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time

ROOT = Path('/Users/tommy/Offline/projects/m200-cpp')
GATE = Path(__file__).resolve().parent
SOURCE = GATE / 'source'
EXTRAS = {
    'sdk/plc_modbus_async.hpp',
    'tests/test_modbus_sdk_async.py',
    'tests/parallel_semantics/g11_sdk_host.py',
}
EXCLUDED = {
    'tests/parallel_semantics/g01_fix4_cases.py',
    'tests/parallel_semantics/g01_fix4_report.py',
    'tests/christmas/read_panel.py',
    'tests/christmas/panel_geometry.json',
}
EXPECTED = {
    'sdk/plc.hpp': '0ab4b1f538c45282252b80ac4577974ede33b02f423860a40b16c4ed863d0067',
    'sdk/plc_modbus_async.hpp': '5e1279de801d649a64111b9fdaf4c568d4c00876566bd5716a8946576b06ae98',
    'tests/test_modbus_sdk_async.py': '50891659cf915ea5968f349359d84f6f131aa14256d2adfd9b85bdfac66ae810',
    'tests/parallel_semantics/g11_sdk_host.py': '16f14b80797cc87154bea326415aa67b1d23e34ffa6c1ce4a9e8c83de95fea8b',
    'tests/parallel_semantics/adapters.json': 'f0b3175743ce2ba049bccdf76820650e9a965266a83674312b7b2c6753509ef2',
}

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def save(name, value):
    (GATE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def pin(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        return {'type': 'symlink', 'target': target,
                'sha256': hashlib.sha256(os.fsencode(target)).hexdigest()}
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'Unsupported tracked input: {path}')
    data = path.read_bytes()
    return {'type': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def inventory(root, paths):
    return {p: pin(root / p) for p in paths}

def diff(before, after):
    return {p: {'before': before.get(p), 'after': after.get(p)}
            for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)}

if SOURCE.exists() or (GATE / 'command.json').exists():
    raise SystemExit('Refusing to reuse existing snapshot or retry an executed gate')
tracked_raw = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
(GATE / 'tracked-files.nul').write_bytes(tracked_raw)
tracked = {os.fsdecode(p) for p in tracked_raw.split(b'\0') if p}
paths = sorted((tracked | EXTRAS) - EXCLUDED)
assert not any(p.startswith('output/') for p in paths)
root_before = inventory(ROOT, paths)
save('root-input-pins-before.json', root_before)
for p, sha in EXPECTED.items():
    assert root_before[p]['sha256'] == sha, (p, root_before[p])
core_paths = sorted(p for p in paths if (p.startswith('m200/') and p.endswith('.py'))
                    or (p.startswith('sdk/') and p.endswith('.hpp')))
assert len(core_paths) == 74, len(core_paths)
for p in paths:
    src, dst = ROOT / p, SOURCE / p
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        dst.symlink_to(os.readlink(src))
    else:
        shutil.copy2(src, dst)
snapshot_before = inventory(SOURCE, paths)
root_after_copy = inventory(ROOT, paths)
copy_drift = diff(root_before, root_after_copy)
copy_errors = diff(root_before, snapshot_before)
save('root-input-pins-after-copy.json', root_after_copy)
save('snapshot-input-pins-before.json', snapshot_before)
save('copy-audit.json', {'root_drift': copy_drift, 'snapshot_differences': copy_errors})
assert not copy_drift and not copy_errors, 'Input changed while copying; no test run'
save('compiler-sdk-pins.json', {p: snapshot_before[p] for p in core_paths})
save('freeze.json', {
    'freeze_id': 'g11-final-gate-1', 'created_utc': now(),
    'source_root': str(ROOT), 'snapshot': str(SOURCE),
    'selection': 'current worktree bytes of git tracked paths plus exactly three untracked exceptions',
    'tracked_count': len(tracked), 'selected_count': len(paths),
    'bytes': sum(v.get('bytes', 0) for v in snapshot_before.values()),
    'core_count': len(core_paths), 'allowed_untracked': sorted(EXTRAS),
    'excluded_helpers': sorted(EXCLUDED), 'expected_integrated_hashes': EXPECTED,
    'input_pins_sha256': pin(GATE / 'snapshot-input-pins-before.json')['sha256'],
    'known_pending_failures': [f'parallel_semantics.{case}.{engine}'
        for case in ['G08_sc_middle_steps_and_exclusive_reset',
                     'G01_edge_cold_warm_stop_RUN_history_is_not_guessed',
                     'G08_unresolved_native_domains_remain_visible_gaps']
        for engine in ['vm', 'sdk']],
})
for name in ['runtime-output', 'tmp']:
    (GATE / name).mkdir()
(SOURCE / 'output').symlink_to(GATE / 'runtime-output', target_is_directory=True)
env = os.environ.copy()
env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', TMPDIR=str(GATE / 'tmp'))
env.pop('PYTHONPATH', None)
command = {'argv': ['make', 'check'], 'cwd': str(SOURCE), 'started_utc': now(),
           'state': 'RUNNING', 'authorized_runs': 1, 'attempt': 1,
           'environment_overrides': {k: env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTHONUNBUFFERED','TMPDIR']},
           'PYTHONPATH': 'unset', 'outputs': 'raw log and generated output/TMPDIR outside snapshot'}
save('command.json', command)
started = time.monotonic()
with (GATE / 'make-check.log').open('wb') as log:
    completed = subprocess.run(command['argv'], cwd=SOURCE, env=env,
                               stdout=log, stderr=subprocess.STDOUT)
command.update(state='COMPLETED', exit_code=completed.returncode,
               ended_utc=now(), elapsed_seconds=time.monotonic()-started)
save('command.json', command)
snapshot_after = inventory(SOURCE, paths)
root_after = inventory(ROOT, paths)
save('snapshot-input-pins-after.json', snapshot_after)
save('root-input-pins-after-run.json', root_after)
save('drift-audit.json', {
    'snapshot_drift': diff(snapshot_before, snapshot_after),
    'root_drift_during_run': diff(root_after_copy, root_after),
    'root_note': 'Root may update docs/evidence during run; immutable snapshot is execution authority.',
    'core_snapshot_drift': diff({p:snapshot_before[p] for p in core_paths},
                                {p:snapshot_after[p] for p in core_paths}),
    'core_root_drift': diff({p:root_after_copy[p] for p in core_paths},
                           {p:root_after[p] for p in core_paths}),
})
save('raw-result.json', {'command': command, 'log': pin(GATE / 'make-check.log'),
                         'freeze': pin(GATE / 'freeze.json')})
print(json.dumps({'state': 'COMPLETED', 'exit_code': completed.returncode,
                  'elapsed_seconds': command['elapsed_seconds'],
                  'input_count': len(paths), 'core_count': len(core_paths),
                  'snapshot_drift_count': len(diff(snapshot_before, snapshot_after))}))
