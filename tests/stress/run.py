"""Run reproducible local audits and make unexpected results fail the command."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
output = Path(tempfile.mkdtemp(prefix="m200-stress-"))
print("Stress artifacts: " + str(output), flush=True)
allowed_rejections = {
    "sdk_macro_constructor_escape",
    "helper_variadic",
    "bool_aggregate_init",
}
frames = 0
for name in ("boolean_audit", "il_properties"):
    destination = output / name
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name(name + ".py")),
            "--repo",
            str(root),
            "--output",
            str(destination),
        ],
        timeout=600,
    )
    if result.returncode:
        raise SystemExit("Audit process failed: " + name)
    report = json.loads((destination / "results.json").read_text())
    failures = []
    for entry in report["results"]:
        status = entry.get("result", entry.get("status"))
        if status in ("BUG", "CRASH", "BLOCKED") or (
            status == "REJECT" and entry.get("name") not in allowed_rejections
        ):
            failures.append(entry)
        if status == "PASS":
            frames += entry.get("frames", 0)
    if failures:
        raise SystemExit("Audit findings: " + json.dumps(failures))
print(
    json.dumps(
        {
            "status": "passed",
            "frames_compared": frames,
            "artifacts": str(output),
            "official_editor": "pending",
            "physical_plc": "pending",
        }
    ),
    flush=True,
)
