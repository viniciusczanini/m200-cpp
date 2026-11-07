"""One unchanged existing default-no-transport program; no raw async peer."""

import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
BASE = OUT.parent
SOURCE = OUT / "source"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / "tests/batch_acceptance"))
from m200.frontend import compile_source
from m200.model import Program
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from native_probe import observe_native

spec = importlib.util.spec_from_file_location("compat_default_batch", SOURCE / "tests/batch_acceptance/batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)
ARTIFACT = Path("/Users/tommy/Offline/projects/m200-cpp/output/parallel-implementation-2026-11-06/integration/batch-final-1/test-batch/batch/modbus-no-transport")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


source = SOURCE / "examples/batch_acceptance/modbus.cpp"
require(source.read_bytes() == (ARTIFACT / "modbus.cpp").read_bytes(), "unchanged source differs from pinned native emission artifact")
program = compile_source(source)
folder = OUT / "native-emission"
folder.mkdir(exist_ok=True)
project = folder / "generated.smbp"
template = SOURCE / "tests/fixtures/official_tm200ce40t_modbus_full_pin_read.smbp"
write_project(program, template, project)
fields = ["ElementType", "Descriptor", "OperationExpression", "ComparisonExpression", "Row", "Column", "ChosenConnection"]
shape = {"rungs": program.rungs, "communications": program.as_dict()["communications"], "graphs": [[[e.findtext(f, "") for f in fields] for e in rung.findall("LadderElements/LadderEntity")] for rung in ET.parse(project).iter("RungEntity")]}
baseline = json.loads((BASE / "baseline-native-emission-shape.json").read_text())
require(shape == baseline, "native IL/config/graph changed under host-only async SDK patch")
(OUT / "native-emission-shape.json").write_text(json.dumps(shape, indent=2, sort_keys=True) + "\n")
restored = load_project(project)
require(restored.communications == program.communications, "generated native config changed")
reverse = folder / "actual-reverse.cpp"
reverse.write_text(to_cpp(restored))
rebuilt = compile_source(reverse)
target = folder / "rebuilt.smbp"
write_project(rebuilt, template, target)
readback = load_project(target)
require(readback.communications == program.communications, "actual reverse native index/config changed")
decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
cases = json.loads((ARTIFACT / "cases.json").read_text())["cases"]
require(len(cases) == 1 and cases[0]["id"] == "modbus-default-error", "case selection changed")
case = cases[0]
frames = case["frames"]
words = sorted({int(k) for frame in frames for k in frame["expect"].get("words", {})})
observations = {}
for name, candidate in [("compiled_VM", program), ("JSON_VM", decoded), ("native_project_VM", restored), ("reverse_compiled_VM", rebuilt), ("rebuilt_project_VM", readback)]:
    actual = batch.observe_machine(candidate, frames, words)
    batch.compare(case, actual)
    observations[name] = actual
for name, cpp in [("original_SDK", source), ("reverse_SDK", reverse)]:
    actual = observe_native(cpp, frames, words, folder / name, SOURCE / "sdk")
    batch.compare(case, actual)
    observations[name] = actual
report = {"case": case["id"], "frames_per_route": len(frames), "routes": observations, "native_IL_config_graph_equal_to_pinned_baseline": True, "public_constructors": ["ReadVar auto0", "WriteVar auto0", "WriteReadVar auto0"], "transport": "NONE; explicit error255/15 only; no raw async peer or native PLC transaction", "status": "PASS"}
(OUT / "native-emission-results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print("PASS: native IL/config/graph unchanged; modbus-default-error10frames x7localroutes; no raw async transaction")
