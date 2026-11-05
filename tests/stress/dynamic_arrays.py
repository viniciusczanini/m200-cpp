#!/usr/bin/env python3
"""Computed indices with independent array/state and raw-bit oracles."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SEED = 20020261110


def verify(program, source, frames, expected, work, case, bit_profile):
    def check(candidate, name):
        machine = Machine(candidate)
        for i, (frame, row) in enumerate(zip(frames, expected)):
            if machine.step(frame["inputs"]) != row:
                raise AssertionError(f"{case} {name}: frame {i} differs from oracle")

    check(program, "IL")
    if run_native(source, frames) != expected:
        raise AssertionError(f"{case}: original native C++ differs from oracle")
    reverse = work / (case + "_reverse.cpp")
    reverse.write_text(to_cpp(program))
    if run_native(reverse, frames) != expected:
        raise AssertionError(f"{case}: reverse native C++ differs from oracle")
    rebuilt = compile_source(reverse)
    check(rebuilt, "reverse recompiled")
    destination = work / (case + ".smbp")
    if bit_profile:
        try:
            write_project(program, ROOT / "tests/fixtures/synthetic.smbp", destination)
        except CompileError as exc:
            if "indexed-bit" not in str(exc) or "unverified" not in str(exc):
                raise
        else:
            raise AssertionError("unverified indexed-bit profile was exported")
        if destination.exists():
            raise AssertionError("rejected bit export created a destination")
    else:
        write_project(program, ROOT / "tests/fixtures/synthetic.smbp", destination)
        check(load_project(destination), "XML")
        write_project(rebuilt, ROOT / "tests/fixtures/synthetic.smbp", destination)
        check(load_project(destination), "reverse XML")


def array_case(kind, persistent, frames):
    typename = "bool" if kind == "bool" else "plc::" + kind
    initial = (
        [True, False, True, False, False, True, True, False]
        if kind == "bool"
        else [i * 0.5 for i in range(8)]
        if kind == "f32"
        else [65538 + i for i in range(8)]
        if kind == "i32"
        else list(range(8))
    )
    values = [
        str(v).lower() if kind == "bool" else str(v) + ("f" if kind == "f32" else "")
        for v in initial
    ]
    declaration = typename + " a[8]={" + ",".join(values) + "};\n"
    index_type = "i16" if kind in ("bool", "i16") else "i32"
    scan = "void scan(){plc::clear_index_error();\n"
    if not persistent:
        scan += declaration
    scan += f"plc::{index_type} index=0;\n"
    for bit in range(3):
        scan += (
            f"if(plc::input({bit})){{index=plc::add_{index_type}(index,{1 << bit});}}\n"
        )
    if kind == "bool":
        scan += "bool before=a[index];a[index]=plc::input(3);\n"
        scan += "for(plc::i16 k=0;k<8;k=plc::add_i16(k,1)){if(plc::input(4)){a[k]=!a[k];}}\n"
        scan += "plc::output(0,before);\n"
        scan += "".join(f"plc::output({i + 1},a[{i}]);\n" for i in range(8))
    else:
        delta = "0.5f" if kind == "f32" else "1"
        scan += f"{typename} before=a[index];\nif(plc::input(3)){{a[index]=plc::add_{kind}(a[index],{delta});}}\n"
        scan += f"else{{a[index]=plc::sub_{kind}(a[index],{delta});}}\n"
        scan += "plc::output(0,a[index]!=before);\n"
        scan += "".join(f"plc::output({i + 1},a[{i}]>{values[i]});\n" for i in range(8))
    scan += "plc::output(9,!plc::system(20));}\n"
    body = (declaration if persistent else "") + scan
    array = initial.copy()
    rows = []
    for frame in frames:
        if not persistent:
            array = initial.copy()
        ins = frame["inputs"]
        index = sum(1 << b for b in range(3) if ins[b])
        before = array[index]
        if kind == "bool":
            array[index] = ins[3]
            if ins[4]:
                array = [not v for v in array]
            row = [before] + array
        else:
            delta = 0.5 if kind == "f32" else 1
            array[index] += delta if ins[3] else -delta
            row = [array[index] != before] + [
                v > initial[i] for i, v in enumerate(array)
            ]
        rows.append(row + [True] + [False] * 6)
    return body, rows


def raw_bit_case(limit, base, frames):
    body = f"plc::WordMemory w{{8}};plc::BitMemory bits{{{limit}}};void scan(){{\n"
    body += "plc::write_word(0,0);\n"
    for bit in range(5):
        body += f"if(plc::input({bit})){{plc::write_word(0,plc::add_i16(plc::read_word(0),{1 << bit}));}}\n"
    body += "plc::write_word(0,plc::sub_i16(plc::read_word(0),16));\n"
    body += "if(plc::input(5)){plc::write_word(0,-32768);}\nif(plc::input(6)){plc::write_word(0,32767);}\n"
    body += "if(plc::input(7)){plc::clear_index_error();}\n"
    body += f"bool before=plc::read_m_indexed({base},0);\n"
    body += f"plc::write_m_indexed({base},0,plc::input(8));\n"
    body += f"plc::output(0,before);plc::output(1,plc::read_m({base}));\n"
    body += (
        "plc::output(2,plc::system(20));plc::output(3,plc::read_word(0)==-32768);}\n"
    )
    memory = [False] * limit
    error = False
    rows = []
    for frame in frames:
        ins = frame["inputs"]
        offset = sum(1 << b for b in range(5) if ins[b]) - 16
        if ins[5]:
            offset = -32768
        if ins[6]:
            offset = 32767
        if ins[7]:
            error = False
        position = base + offset
        if not 0 <= position < limit:
            position = base
            error = True
        before = memory[position]
        memory[position] = ins[8]
        rows.append([before, memory[base], error, offset == -32768] + [False] * 12)
    return body, rows


def main():
    rng = random.Random(SEED)
    frames = [
        {"inputs": {b: bool(value & (1 << b)) for b in range(9)}}
        for value in list(range(512)) + [rng.randrange(512) for _ in range(512)]
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-array-stress-") as directory:
        work = Path(directory)
        cases = []
        for kind in ("i16", "i32", "f32", "bool"):
            for persistent in (False, True):
                case = f"{kind}_{'global' if persistent else 'local'}"
                body, rows = array_case(kind, persistent, frames)
                cases.append((case, body, rows, kind == "bool"))
        for limit, base in ((8, 4), (512, 504), (900, 0)):
            body, rows = raw_bit_case(limit, base, frames)
            cases.append((f"bits_{limit}_{base}", body, rows, True))
        for case, body, rows, bit_profile in cases:
            source = work / (case + ".cpp")
            source.write_text("#include <plc.hpp>\n" + body)
            program = compile_source(source)
            verify(program, source, frames, rows, work, case, bit_profile)
            results.append(
                dict(
                    case=case,
                    scans=len(frames),
                    xml="gated: indexed-bit profile unverified"
                    if bit_profile
                    else "pass",
                    status="pass",
                )
            )
            print(f"PASS: {case} / {len(frames)} scans", flush=True)
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
    ]
    report = dict(
        seed=SEED,
        cases=results,
        scans=len(frames) * len(results),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        official_editor="pending",
        physical_plc="pending",
        invalid_builtin_cpp_array="Not executed; undefined host-language domain. Raw indexed API errors tested separately.",
    )
    (ROOT / "docs/validation/DYNAMIC-ARRAY-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans / independent oracle, C++, IL and reverse; numeric XML, bit XML gate"
    )


if __name__ == "__main__":
    main()
