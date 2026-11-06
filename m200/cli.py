import argparse
import hashlib
import json
import os
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
from .numeric import OPS, READS, WRITES, TYPES, memory_words_used
from .bits import memory_bits_used
from .edge_functions import parse as expression_edge
from .communication import KINDS

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
        if template:
            result["generated_project_resources"] = report(
                load_project(stage / "program.smbp")
            )["resources"]
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
    addresses = memory_bits_used(program)
    words = memory_words_used(program)
    functions = []
    for rung in program.rungs:
        for line in rung:
            parts = line.split(maxsplit=1)
            function = expression_edge(parts[0]) if parts else None
            if function is not None:
                functions.append(function)
    return {
        "tool": "m200-cpp",
        "version": __version__,
        "target": "TM200CE40T",
        "status": "experimental",
        "resources": {
            "memory_bits": len(addresses),
            "memory_capacity": 1024,
            "compiler_allocatable_bits": 1024,
            "memory_words": len(words),
            "shared_word_capacity": 8000,
            "compiler_allocatable_words": 8000,
            "required_word_allocation": max(words, default=-1) + 1,
            "timers": len(program.timers),
            "timer_capacity": 255,
            "counters": len(program.counters),
            "required_counter_allocation": max(program.counters, default=-1) + 1,
            "counter_capacity_model": 255,
            "counter_semantics": "experimental local policy; E conflict, input interactions and lifecycle require external confirmation",
            "communication_blocks": len(program.communications),
            "communication_capacity_per_kind": 32,
            "rising_functions": sum(kind == "RISING" for kind, _ in functions),
            "falling_functions": sum(kind == "FALLING" for kind, _ in functions),
            "expression_function_index_model": "0..254 per kind; native functional-level mapping pending; SMBP expands to private M",
            "rungs": len(program.rungs),
            "il_instructions": sum(map(len, program.rungs)),
        },
        "validation": {
            "official_editor": "pending",
            "physical_plc": "pending",
            "timing_on_hardware": "pending",
        },
        "metadata": program.metadata,
        "communications": {k: v.to_dict() for k, v in program.communications.items()},
        "limitations": [
            "Only the documented boolean, typed-numeric, fixed-array, control-flow, experimental native-counter and statically configured communication C++ subsets are implemented.",
            "Conservative allocation and compiler overhead can still reject a program that has a smaller native implementation.",
            "No vendor schema/editor validation has been run.",
            "Native timers require official simulation/hardware timing checks.",
            "Integer S17/S18 and modular overflow are modeled locally; unspecified arithmetic results and float SW17 recovery remain gaps, with physical semantics unverified.",
            "Communication endpoints must be configured explicitly; successful local Modbus exchanges do not establish physical PLC compatibility.",
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
                "indexed_memory_api": [
                    "read_word_indexed",
                    "read_dword_indexed",
                    "read_real_indexed",
                    "write_word_indexed",
                    "write_dword_indexed",
                    "write_real_indexed",
                    "read_m_indexed",
                    "write_m_indexed",
                ],
                "memory_profile_types": ["WordMemory", "BitMemory"],
                "word_bit_api": ["read_word_bit", "write_word_bit"],
                "packed_bit_api": [
                    "read_m_bits_i16",
                    "read_m_bits_i32",
                    "read_input_bits_i16",
                    "read_input_bits_i32",
                    "read_output_bits_i16",
                    "read_output_bits_i32",
                    "write_m_bits_i16",
                    "write_m_bits_i32",
                    "write_output_bits_i16",
                    "write_output_bits_i32",
                    "copy_m_bits",
                ],
                "packed_bit_scope": "MW:X0..15 and M/I0/Q0 byte-aligned regions, length 1..32 within carrier/bank. Typed snapshots preserve aliases, neighbors and same-scan output image. Other banks, unequal/overlapping native string assignments and official acceptance remain gated/pending.",
                "array_indices": ["literal", "bool", "i16", "i32"],
                "native_edge_contacts": {
                    "api": ["input_rising", "input_falling", "m_rising", "m_falling"],
                    "il": ["LDR", "LDF", "ANDR", "ANDF", "ORR", "ORF", "XORR", "XORF"],
                    "scope": "Direct embedded I0/M; events sampled per address at scan start, unaffected by repeated/skipped contacts; M writes appear next scan. Input phase/startup/restart and official acceptance pending. Expression functions are modeled separately; raw edge-block XML and R/F parenthesis modifiers remain gaps.",
                },
                "expression_edge_functions": {
                    "api": ["rising(index,bool)", "falling(index,bool)"],
                    "il": ["RISINGn", "FALLINGn"],
                    "scope": "Unique static IDs0..254 per kind; local per-execution histories, conditional/short-circuit/loop calls. SMBP expands to persistent private M and gates, not raw edge-block enums. Phase/startup/repetition and official profile remain unverified; expansion overhead is a compiler limitation.",
                },
                "native_logic_ir": [
                    "STN",
                    "N",
                    "MPS",
                    "MRD",
                    "MPP",
                    "AND(",
                    "OR(",
                    ")",
                    "IN timer (terminal/before load)",
                    "Timer composed input and ST/STN/S/R output",
                ],
                "native_logic_ladder": "Complex native rungs normalize to existing series contacts/coils/Timer blocks with reserved private snapshots. Native MPS11/32 conflict and official validation pending.",
                "indexed_scope": "Contiguous computed arrays and explicit word/bit images; signed MW offsets, sticky S20/reset. Indexed-bit SMBP functional-level mapping, Manual/default ambiguity and official validation remain gated/pending",
                "boolean_api": [
                    "input",
                    "output",
                    "output_state",
                    "read_m",
                    "write_m",
                    "system",
                    "clock_ms",
                    "clear_index_error",
                    "clear_shift_carry",
                    "clear_arithmetic_error",
                ],
                "integer_flags": {
                    "read": "system(17/18)",
                    "reset": ["clear_shift_carry", "clear_arithmetic_error"],
                    "scope": "S17 assigned the last ejected bit on shifts/rotates; S18 sticky signed integer overflow with explicit reset, snapshots and guarded execution. Modular overflow bits beyond G55 ADDword are a local policy. DIV0/SQRTnegative stop local model after S18; float SW17 and unknown-result recovery remain gaps. Official editor/PLC pending.",
                },
                "word_conversions": {
                    "api": [
                        "bcd_to_int",
                        "bcd_to_dint",
                        "int_to_bcd",
                        "dint_to_bcd",
                        "concat_words",
                        "int_to_dint",
                    ],
                    "il": ["BTI", "ITB", "CONCATW", "DWORD"],
                    "scope": "Four/eight unsigned BCD digits in signed carriers; valid conversions preserve S17/S18. Invalid BCD sets S18 and stops local model without inventing a result; recovery remains a gap. CONCATW low-first has official corroboration. DWORD negative sign extension is a local policy still requiring editor/PLC proof. Other operand banks and nested native expressions remain gaps.",
                },
                "stateful_types": [
                    "Ton",
                    "Tof",
                    "Pulse",
                    "Clock",
                    "RisingEdge",
                    "FallingEdge",
                ],
                "timer_properties": {
                    "types": ["Ton", "Tof", "Pulse"],
                    "methods": ["preset", "value", "done", "set_preset"],
                    "explicit_constructor": "native_index, base_ms, preset_ticks",
                    "mode_constructor": "native_index, base_ms, preset_ticks, retentive, dynamic_preset (literal bool flags)",
                    "scope": "Retentive TON/TOF and dynamic preset TON/TOF/TP in local C++/IL/configuration/VM/reverse. TP retention rejected. True-mode SMBP functional-level mapping, native tick phase and lifecycle validation pending.",
                },
                "native_counters": {
                    "type": "Counter(native_index,preset)",
                    "methods": [
                        "reset",
                        "set",
                        "count_up",
                        "count_down",
                        "update",
                        "preset",
                        "value",
                        "done",
                        "empty",
                        "full",
                        "set_preset",
                    ],
                    "scope": "Native %C configuration/IL/SDK/reverse; IDs0..254, preset0..9999; explicit allocation extent. Pure raw Counter branch/output graphs reconcile by ports and exact ordered Boolean proof, including configured communication BOOL status contacts; comparisons/index effects remain gated. Export normalizes to separate rungs. Local per-instruction state model, E conflict, lifecycle and official profile/editor/hardware remain unverified.",
                },
                "communication_types": list(KINDS),
                "modbus_client_function_codes": [1, 2, 3, 4, 5, 6, 15, 16, 23],
                "modbus_xml_scope": "READ_VAR/WRITE_VAR word profiles and proved port enums only; unknown XML variants fail explicitly",
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
