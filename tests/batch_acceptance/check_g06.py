"""Focused frozen G06 pipeline and connected/unwired Timer graph controls."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from batch import compare, compare_resource_shape, observe_machine
from native_probe import observe_native


INPUT_ONLY_CPP = """#include <plc.hpp>
plc::Ton timer{4,10,2};
void leaf(){timer.execute(plc::input(0));}
plc::Subroutine sr{0,leaf,"REPRO_TIMER_SR",2};
void scan(){sr.call(true);}
"""

CONNECTED_CPP = """#include <plc.hpp>
plc::Ton timer{4,10,2};
void update_leaf(){bool q=timer.update(plc::input(0));plc::write_m(200,q);}
void observe_leaf(){plc::output(0,timer.done());plc::output(1,plc::read_m(200));}
plc::Subroutine update_sr{0,update_leaf,"CONNECTED_TIMER_SR",2};
plc::Subroutine observe_sr{63,observe_leaf,"OBSERVE_TIMER_SR",42};
void scan(){update_sr.call(true);observe_sr.call(true);}
"""

CONNECTED_CASE = {
    "id": "connected-timer-multiple-sr-control",
    "oracle": "One shared TON20ms on10ms scan starts; Q and wired M200 are both false,false,false,true,false. Two separate SRs share the same timer and image.",
    "frames": [
        {"label": "disabled", "dt_ms": 10, "inputs": {}, "expect": {"output_mask": 0}},
        {"label": "enable-t0", "dt_ms": 10, "inputs": {"0": True}, "expect": {"output_mask": 0}},
        {"label": "enable-t10", "dt_ms": 10, "inputs": {"0": True}, "expect": {"output_mask": 0}},
        {"label": "enable-t20", "dt_ms": 10, "inputs": {"0": True}, "expect": {"output_mask": 3}},
        {"label": "release", "dt_ms": 10, "inputs": {}, "expect": {"output_mask": 0}},
    ],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def check_pins(freeze):
    changed = [name for name, expected in freeze["compiler_sdk"].items() if not (ROOT / name).is_file() or digest(ROOT / name) != expected]
    return {"count": len(freeze["compiler_sdk"]), "changed": changed, "unchanged": not changed}


def graph_connections(project, expected):
    found = [
        {"descriptor": node.findtext("Descriptor"), "connection": node.findtext("ChosenConnection")}
        for node in ET.parse(project).findall(".//LadderEntity")
        if node.findtext("ElementType") == "Timer"
    ]
    if found != [{"descriptor": "%TM4", "connection": expected}]:
        raise AssertionError("Timer graph connection expected%s, got%s" % (expected, found))
    return found


def pipeline(name, source, case, output, template):
    from m200.frontend import compile_source
    from m200.model import Program
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    folder = output / name
    folder.mkdir()
    program = compile_source(source)
    decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    project = folder / "generated.smbp"
    write_project(program, template, project)
    imported = load_project(project)
    first_connections = graph_connections(project, "Left, Right")
    reverse = folder / "actual_project_reverse.cpp"
    reverse.write_text(to_cpp(imported))
    rebuilt = compile_source(reverse)
    rebuilt_project = folder / "rebuilt.smbp"
    write_project(rebuilt, template, rebuilt_project)
    readback = load_project(rebuilt_project)
    rebuilt_connections = graph_connections(rebuilt_project, "Left")
    shape = {"timer_ids": [4], "subroutine_sections": {"0": 2, "63": 42}}
    for candidate in (program, decoded, imported, rebuilt, readback):
        compare_resource_shape(candidate, shape)
    frames = case["frames"]
    watch = sorted({int(word) for frame in frames for word in frame["expect"].get("words", {})})
    routes = {
        "compiled_machine": lambda: observe_machine(program, frames, watch),
        "json_machine": lambda: observe_machine(decoded, frames, watch),
        "generated_project_machine": lambda: observe_machine(imported, frames, watch),
        "recompiled_reverse_machine": lambda: observe_machine(rebuilt, frames, watch),
        "rebuilt_project_machine": lambda: observe_machine(readback, frames, watch),
        "original_cpp_native": lambda: observe_native(source, frames, watch, folder / "original-native", ROOT / "sdk"),
        "actual_project_reverse_native": lambda: observe_native(reverse, frames, watch, folder / "reverse-native", ROOT / "sdk"),
    }
    result = {
        "case": case["id"], "frames": len(frames), "source_sha256": digest(source),
        "oracle": case["oracle"], "resource_shape": shape,
        "generated_project": {"bytes": project.stat().st_size, "sha256": digest(project), "timer_connections": first_connections},
        "rebuilt_project": {"bytes": rebuilt_project.stat().st_size, "sha256": digest(rebuilt_project), "timer_connections": rebuilt_connections},
        "routes": {},
    }
    for route, action in routes.items():
        observed = action()
        compare(case, observed)
        result["routes"][route] = {"status": "passed", "observations": observed}
    result["status"] = "passed_literal_subset"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    freeze = json.loads(Path(args.freeze).read_text())
    if Path(freeze["source_root"]).resolve() != ROOT:
        raise ValueError("execute only inside the explicitly frozen source copy")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {"freeze_id": freeze["freeze_id"], "status": "running", "pins_before": check_pins(freeze), "cases": {}, "gui": "not_run", "full_799_suite": "not_rerun"}
    started = time.monotonic()
    try:
        if not result["pins_before"]["unchanged"]:
            raise AssertionError("compiler/SDK pins changed before execution")
        from m200.frontend import compile_source
        from m200.project import write_project
        template = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
        minimal = output / "repro_sr_timer_input_only.cpp"
        minimal.write_text(INPUT_ONLY_CPP)
        minimal_project = output / "repro-sr-timer-input-only.smbp"
        write_project(compile_source(minimal), template, minimal_project)
        result["minimal_repro"] = {"status": "passed", "connections": graph_connections(minimal_project, "Left"), "source_sha256": digest(minimal), "project_sha256": digest(minimal_project)}
        data = json.loads((ROOT / "examples/batch_acceptance/cases.json").read_text())
        case = next(row for row in data["cases"] if row["id"] == "subroutine-stateful-liveness")
        write_json(output / "g06-literal-case.json", case)
        result["cases"][case["id"]] = pipeline("g06", ROOT / "examples/batch_acceptance/subroutine_stateful.cpp", case, output, template)
        control_source = output / "connected_timer_multiple_sr.cpp"
        control_source.write_text(CONNECTED_CPP)
        write_json(output / "connected-literal-case.json", CONNECTED_CASE)
        result["cases"][CONNECTED_CASE["id"]] = pipeline("connected-control", control_source, CONNECTED_CASE, output, template)
        result["status"] = "passed_scoped_G06_and_graph_controls"
    except Exception as error:
        result.update(status="failed", error=str(error), traceback=traceback.format_exc())
    finally:
        result["pins_after"] = check_pins(freeze)
        result["seconds"] = time.monotonic() - started
        if not result["pins_after"]["unchanged"]:
            result["status"] = "failed_changed_compiler_sdk_pins"
        write_json(output / "results.json", result)
    print(json.dumps({"status": result["status"], "pins_before": result["pins_before"], "pins_after": result["pins_after"], "cases": {name: {"status": case["status"], "frames": case["frames"], "routes": len(case["routes"])} for name, case in result["cases"].items()}, "seconds": round(result["seconds"], 3), "error": result.get("error"), "results": str(output / "results.json")}, indent=2))
    return 0 if result["status"] == "passed_scoped_G06_and_graph_controls" else 1


if __name__ == "__main__":
    raise SystemExit(main())
