import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from . import __version__
from .frontend import compile_source
from .il import Machine, validate, validate_frames
from .model import CompileError, Program, fail
from .native import run_native
from .project import load_project, write_project
from .reverse import to_cpp
from .jsonio import loads
from .capabilities import summary as capability_summary, catalogue, lookup
from .numeric import OPS, READS, WRITES, TYPES

ARTIFACTS = {
    "program.m200.json",
    "program.il",
    "program.audit.cpp",
    "program.smbp",
    "report.json",
    "source-map.json",
}


def build_artifacts(program, output, template=None):
    out = Path(output)
    if out.exists():
        if not out.is_dir() or any(
            p.name not in ARTIFACTS or not p.is_file() for p in out.iterdir()
        ):
            fail(
                "output contains files not owned by this compiler; choose another directory"
            )
        if any(out.iterdir()) and not (out / "report.json").exists():
            fail("existing output has no compiler report; choose another directory")
        if (out / "report.json").exists():
            previous = loads((out / "report.json").read_text())
            if not isinstance(previous, dict) or previous.get("tool") != "m200-cpp":
                fail("output report is not owned by this compiler")
            owned = previous.get("artifacts", {})
            if not isinstance(owned, dict):
                fail("invalid previous artifact manifest")
            if any(
                p.name != "report.json" and p.name not in owned for p in out.iterdir()
            ):
                fail(
                    "existing file is absent from the previous artifact manifest; choose another output directory"
                )
            for name, digest in owned.items():
                if name not in ARTIFACTS:
                    fail("invalid previous artifact manifest")
                path = out / name
                if (
                    path.exists()
                    and hashlib.sha256(path.read_bytes()).hexdigest() != digest
                ):
                    fail(
                        "an existing generated file was modified; choose another output directory"
                    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".m200-build-", dir=str(out.parent)) as d:
        stage = Path(d)
        (stage / "program.m200.json").write_text(
            json.dumps(program.as_dict(), indent=2) + "\n"
        )
        (stage / "program.il").write_text(
            "\n\n".join(
                "; Rung %d\n%s" % (n, "\n".join(r)) for n, r in enumerate(program.rungs)
            )
            + "\n"
        )
        (stage / "program.audit.cpp").write_text(to_cpp(program))
        origins = program.metadata.get("rung_origins", [])
        (stage / "source-map.json").write_text(
            json.dumps(
                {
                    "source": program.metadata.get("source"),
                    "source_sha256": program.metadata.get("source_sha256"),
                    "rungs": [
                        {"rung": i, "origin": origins[i] if i < len(origins) else {}}
                        for i in range(len(program.rungs))
                    ],
                    "symbols": program.symbols,
                },
                indent=2,
            )
            + "\n"
        )
        if template:
            write_project(program, template, stage / "program.smbp")
        result = report(program)
        result["project_generated"] = bool(template)
        result["artifacts"] = {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(stage.iterdir())
        }
        (stage / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        out.mkdir(exist_ok=True)
        staged = {p.name for p in stage.iterdir()}
        for old in out.iterdir():
            if old.name not in staged:
                old.unlink()
        for f in stage.iterdir():
            os.replace(f, out / f.name)
    return result


def decompile_file(source, output):
    source = Path(source)
    output = Path(output)
    sidecar = (
        Path(str(output) + ".configuration.smbp")
        if source.suffix.lower() == ".smbp"
        else None
    )
    paths = [source.resolve(), output.resolve()] + (
        [sidecar.resolve()] if sidecar else []
    )
    if len(set(paths)) != len(paths):
        fail("decompile input, output and configuration sidecar must be distinct paths")
    destinations = [output] + ([sidecar] if sidecar else [])
    if any(p.exists() or p.is_symlink() for p in destinations):
        fail("decompile output already exists; choose a new output path")
    original = source.read_bytes()
    program = read_program(source)
    if source.read_bytes() != original:
        fail("source project changed while being read")
    code = to_cpp(program).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    # Stage both payloads before creating any destination. Exclusive opens also
    # protect files created by another process between the check and the write.
    with tempfile.TemporaryDirectory(
        prefix=".m200-decompile-", dir=str(output.parent)
    ) as d:
        stage = Path(d)
        (stage / "program.cpp").write_bytes(code)
        if sidecar:
            (stage / "original.smbp").write_bytes(original)
        try:
            for destination, data in [
                (output, (stage / "program.cpp").read_bytes())
            ] + (
                [(sidecar, (stage / "original.smbp").read_bytes())] if sidecar else []
            ):
                with destination.open("xb") as f:
                    created.append(destination)
                    f.write(data)
        except OSError:
            for p in created:
                p.unlink(missing_ok=True)
            raise


def read_program(path):
    path = Path(path)
    if path.suffix.lower() == ".smbp":
        return load_project(path)
    p = Program.from_dict(loads(path.read_text()))
    validate(p)
    return p


def report(program):
    text = "\n".join(" ".join(r) for r in program.rungs)
    addresses = set(re.findall(r"%M\d+", text))
    words = set()
    for prefix, index in re.findall(r"%M([WDF])(\d+)", text):
        start = int(index)
        words.update(range(start, start + (1 if prefix == "W" else 2)))
    return {
        "tool": "m200-cpp",
        "version": __version__,
        "target": "TM200CE40T",
        "status": "experimental",
        "resources": {
            "memory_bits": len(addresses),
            "memory_capacity": 1024,
            "compiler_allocatable_bits": 524,
            "memory_words": len(words),
            "shared_word_capacity": 8000,
            "compiler_allocatable_words": 4000,
            "timers": len(program.timers),
            "timer_capacity": 255,
            "rungs": len(program.rungs),
            "il_instructions": sum(map(len, program.rungs)),
        },
        "validation": {
            "official_editor": "pending",
            "physical_plc": "pending",
            "timing_on_hardware": "pending",
        },
        "metadata": program.metadata,
        "limitations": [
            "Only the documented boolean and explicit typed-numeric C++ subsets are implemented.",
            "No vendor schema/editor validation has been run.",
            "Native timers require official simulation/hardware timing checks.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Experimental C++ / IL / SMBP toolchain for TM200CE40T"
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile")
    c.add_argument("source")
    c.add_argument("-o", "--output", required=True)
    c.add_argument("--template")
    d = sub.add_parser("decompile")
    d.add_argument("project")
    d.add_argument("-o", "--output", required=True)
    s = sub.add_parser("simulate")
    s.add_argument("program")
    s.add_argument("--trace", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("program")
    k = sub.add_parser("check")
    k.add_argument("source")
    k.add_argument("--trace", required=True)
    caps = sub.add_parser(
        "capabilities",
        help="Source-backed inventory; implementation is a separate subset",
    )
    caps.add_argument("id", nargs="?")
    caps.add_argument("--all", action="store_true")
    sub.add_parser(
        "certify", help="Always refuses: official validation is not available yet"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            data = (
                lookup(args.id)
                if args.id
                else catalogue()
                if args.all
                else capability_summary()
            )
            data["library"] = {
                "status": "experimental_subset",
                "complete": False,
                "numeric_types": list(TYPES),
                "numeric_intrinsics": sorted(OPS),
                "numeric_memory_api": sorted(READS | WRITES),
                "boolean_api": [
                    "input",
                    "output",
                    "output_state",
                    "read_m",
                    "write_m",
                    "system",
                    "clock_ms",
                ],
                "stateful_types": [
                    "Ton",
                    "Tof",
                    "Pulse",
                    "Clock",
                    "RisingEdge",
                    "FallingEdge",
                ],
                "note": "Inventory stages are deliberately unpromoted documentary records. This library list names the locally implemented subset; editor and physical validation are pending.",
            }
            print(json.dumps(data, indent=2))
            return 0
        if args.command == "certify":
            fail(
                "official editor/PLC validation is pending; certification is unavailable"
            )
        if args.command == "compile":
            p = compile_source(args.source)
            validate(p)
            result = build_artifacts(p, args.output, args.template)
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "decompile":
            decompile_file(args.project, args.output)
            print(
                "Experimental C++ reconstructed from actual IL; official validation pending."
            )
            return 0
        if args.command == "inspect":
            print(json.dumps(report(read_program(args.program)), indent=2))
            return 0
        frames = validate_frames(loads(Path(args.trace).read_text()))
        if args.command == "simulate":
            machine = Machine(read_program(args.program))
            print(
                json.dumps(
                    [
                        machine.step(f.get("inputs", {}), f.get("dt_ms", 10))
                        for f in frames
                    ]
                )
            )
            return 0
        p = compile_source(args.source)
        machine = Machine(p)
        emitted = [
            machine.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames
        ]
        original = run_native(args.source, frames)
        with tempfile.TemporaryDirectory(prefix="m200-audit-") as d:
            reverse = Path(d) / "audit.cpp"
            reverse.write_text(to_cpp(p))
            reconstructed = run_native(reverse, frames)
        if original != emitted or reconstructed != emitted:
            fail("differential execution mismatch")
        print(
            json.dumps(
                {
                    "status": "local_differential_checks_passed",
                    "frames": len(frames),
                    "original_cpp_vs_il": True,
                    "reverse_cpp_vs_il": True,
                    "official_editor": "pending",
                    "physical_plc": "pending",
                },
                indent=2,
            )
        )
        return 0
    except (CompileError, OSError, ValueError, KeyError) as exc:
        print(
            str(exc) if isinstance(exc, CompileError) else "M200-E: " + str(exc),
            file=sys.stderr,
        )
        return 1
