"""Bind declared lane C++ APIs to the integrated root, never lane/source copies."""

import copy
import json
from pathlib import Path

from harness import PendingContract, ROOT, equal, refused, require


def _write(work, name, value):
    path = work / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return str(path)


def _compile(work, source, name):
    from m200.frontend import compile_source

    path = work / name
    path.write_text("#include <plc.hpp>\n" + source)
    return path, compile_source(path)


def _config(program, fields):
    encoded = program.as_dict()
    for field in fields:
        require(field in encoded, "descriptor silently omitted typed configuration: " + field)
    return {field: encoded[field] for field in fields}


def _roundtrip(work, source, name, fields):
    from m200.model import Program
    from m200.il import validate
    from m200.reverse import to_cpp

    path, program = _compile(work, source, name + ".cpp")
    original = _config(program, fields)
    decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    validate(decoded)
    equal(_config(decoded, fields), original, "JSON changed actual typed configuration")
    reverse_source = to_cpp(decoded)
    reverse_path, rebuilt = _compile(work, reverse_source, name + ".reverse.cpp")
    equal(_config(rebuilt, fields), original, "actual-IL reverse changed typed configuration")
    return path, program, reverse_path, rebuilt


def run_case(request, context):
    from m200.model import CompileError, Program

    work = Path(context["work"])
    scenario = request["scenario"]
    mode = scenario["mode"]
    fields = scenario.get("configuration_fields", [])
    if mode == "cpp_constraint":
        observations = []
        for index, source in enumerate(scenario["positive_sources"]):
            _, program, _, _ = _roundtrip(work, source, f"positive-{index}", fields)
            observations.append(_config(program, fields))
        for index, source in enumerate(scenario["negative_sources"]):
            refused(lambda source=source, index=index: _compile(work, source, f"negative-{index}.cpp"), CompileError, request["identity"])
        path = _write(work, "route-observations.json", observations)
        return {"observed": {"accepted": len(observations), "refused": len(scenario["negative_sources"])}, "evidence": {"forward": path, "json": path, "reverse": path}}
    if mode == "json_unknown":
        _, program, _, _ = _roundtrip(work, scenario["source"], "json-control", fields)
        data = copy.deepcopy(program.as_dict())
        node = data
        for key in scenario["path"]:
            node = node[key]
        node["unbound_executable_setting"] = "must not disappear"
        before = copy.deepcopy(data)
        refused(lambda: Program.from_dict(data), (CompileError, ValueError), "unknown nested typed config")
        equal(data, before)
        evidence = _write(work, "refused-json.json", data)
        return {"observed": {"unknown_refused": True, "caller_unchanged": True}, "evidence": {"forward": evidence, "json": evidence, "reverse": evidence}}
    if mode == "cpp_trace":
        from m200.il import Machine
        from m200.native import run_native

        source, program, reverse, rebuilt = _roundtrip(work, scenario["source"], "trace", fields)
        frames = scenario["frames"]
        width = scenario["output_width"]

        def observe(program):
            machine = Machine(program)
            return [machine.step(frame.get("inputs", {}), frame.get("dt_ms", 10))[:width] for frame in frames]

        rows = observe(program)
        equal(observe(rebuilt), rows, "actual reverse disagrees with forward trace")
        equal([row[:width] for row in run_native(source, frames)], rows, "native SDK disagrees with forward trace")
        equal([row[:width] for row in run_native(reverse, frames)], rows, "reverse native SDK disagrees with actual trace")
        evidence = _write(work, "literal-observations.json", {"rows": rows, "frames": frames})
        return {"observed": {"rows": rows}, "evidence": {"forward": str(source), "json": evidence, "reverse": str(reverse), "vm": evidence, "native": evidence}}
    if mode == "native_project":
        from m200.project import load_project, write_project
        from m200.reverse import to_cpp

        source, program = _compile(work, scenario["source"], "project.cpp")
        original = _config(program, fields)
        template = ROOT / scenario.get("template", "tests/fixtures/official_tm200ce40t_memory.smbp")
        before = template.read_bytes()
        destination = work / "candidate.smbp"
        try:
            write_project(program, template, destination)
        except CompileError as error:
            text = str(error)
            if any(word in text.lower() for word in ("unverified", "not implemented", "binding", "gated", "pending")):
                raise PendingContract("native project route remains unbound: " + text) from error
            raise
        equal(template.read_bytes(), before)
        imported = load_project(destination)
        equal(_config(imported, fields), original, "native project changed typed configuration")
        reverse, rebuilt = _compile(work, to_cpp(imported), "project.reverse.cpp")
        equal(_config(rebuilt, fields), original)
        return {"observed": {"native_configuration_preserved": True}, "evidence": {"forward": str(source), "project": str(destination), "graph": str(destination), "reverse": str(reverse)}}
    raise PendingContract("adapter scenario mode is not bound: " + mode)
