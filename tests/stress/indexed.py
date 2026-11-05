#!/usr/bin/env python3
"""Indexed-word differential checks with an independent raw-word oracle."""

# ruff: noqa: E402
import hashlib
import json
import random
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SEED = 20020261109


def signed(raw):
    return raw - 65536 if raw >= 32768 else raw


def case_program(kind, base, observe):
    prefix = [["LD 1", "[%MW0:=0]"]]
    prefix += [[f"LD %I0.{i}", f"[%MW0:=%MW0+{1 << i}]"] for i in range(5)]
    prefix += [
        ["LD 1", "[%MW0:=%MW0-16]"],
        ["LD %I0.5", "[%MW0:=-32768]"],
        ["LD %I0.6", "[%MW0:=32767]"],
        ["LD %I0.7", "R %S20"],
    ]
    data = {}
    if kind == "MW":
        data = {
            address: (address * 37 - 2048) & 65535
            for address in range(base, min(base + 16, 80))
        }
    else:
        values = [-32.0, -0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 1024.0]
        for i in range(16):
            low, high = struct.unpack("<HH", struct.pack("<f", values[i % 8]))
            data[16 + i * 2], data[17 + i * 2] = low, high
    prefix += [["LD 1", f"[%MW{a}:={signed(v)}]"] for a, v in data.items()]
    # Read-only reference anchors the documented direct extent, without
    # pretending Manual excess has a proven relationship with %S20.
    prefix.append(["LD [%MW79=0]", "ST %M10"])
    prefix.append(["LD 1", f"[%{kind}2:=%{kind}{base}[%MW0]]"])
    source = 3 if observe == "high" else 2
    count = 15 if observe == "flag" else 16
    for bit in range(count):
        mask = signed(1 << bit)
        prefix += [
            ["LD 1", f"[%MW79:=%MW{source} AND {mask}]"],
            ["LD [%MW79<>0]", f"ST %Q0.{bit}"],
        ]
    if observe == "flag":
        prefix.append(["LD %S20", "ST %Q0.15"])
    return Program(prefix), data


def expected_frames(kind, base, observe, data, frames):
    words = [0] * 80
    error = False
    rows, states = [], []
    width = 1 if kind == "MW" else 2
    for frame in frames:
        inputs = frame["inputs"]
        offset = sum((1 << b) for b in range(5) if inputs[b]) - 16
        if inputs[5]:
            offset = -32768
        if inputs[6]:
            offset = 32767
        if inputs[7]:
            error = False
        words[0] = offset & 65535
        for a, value in data.items():
            words[a] = value
        effective = base + offset
        if effective < 0 or effective + width > 80:
            error = True
            effective = base
        # Snapshot before a destination aliases its source.
        payload = words[effective : effective + width]
        words[2 : 2 + width] = payload
        source = 3 if observe == "high" else 2
        count = 15 if observe == "flag" else 16
        row = [bool(words[source] & (1 << b)) for b in range(count)]
        if observe == "flag":
            row.append(error)
        rows.append(row)
        states.append((words[0], words[2], words[3], error))
        words[79] = words[source] & (1 << (count - 1))
    return rows, states


def check_machine(program, frames, rows, states, name):
    m = Machine(program)
    for i, (frame, row, state) in enumerate(zip(frames, rows, states)):
        got = m.step(frame["inputs"])
        if got != row or (m.words[0], m.words[2], m.words[3], m.index_error) != state:
            raise AssertionError(f"{name}: frame {i} differs from independent oracle")


def main():
    rng = random.Random(SEED)
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-indexed-stress-") as directory:
        work = Path(directory)
        configs = [("MW", base, mode) for base in (8, 66) for mode in ("low", "flag")]
        configs += [
            (kind, 32, mode)
            for kind in ("MD", "MF")
            for mode in ("low", "high", "flag")
        ]
        for case, (kind, base, observe) in enumerate(configs):
            program, data = case_program(kind, base, observe)
            frames = [
                {"inputs": {b: bool(n & (1 << b)) for b in range(8)}}
                for n in list(range(256)) + [rng.randrange(256) for _ in range(768)]
            ]
            rows, states = expected_frames(kind, base, observe, data, frames)
            check_machine(program, frames, rows, states, "native IL")
            source = work / f"case_{case}.cpp"
            source.write_text(to_cpp(program))
            if run_native(source, frames) != rows:
                raise AssertionError(f"case {case}: native C++ differs from oracle")
            rebuilt = compile_source(source)
            check_machine(rebuilt, frames, rows, states, "recompiled C++")
            reverse = work / f"reverse_{case}.cpp"
            reverse.write_text(to_cpp(rebuilt))
            if run_native(reverse, frames) != rows:
                raise AssertionError(
                    f"case {case}: second reverse C++ differs from oracle"
                )
            destination = work / f"case_{case}.smbp"
            write_project(rebuilt, ROOT / "tests/fixtures/synthetic.smbp", destination)
            check_machine(load_project(destination), frames, rows, states, "SMBP")
            results.append(
                dict(
                    case=case,
                    kind=kind,
                    base=base,
                    observe=observe,
                    scans=1024,
                    status="pass",
                )
            )
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
    ]
    report = dict(
        seed=SEED,
        cases=results,
        scans=10240,
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        model="signed offset in words; direct extent80; two-word width check; sticky %S20; no Manual/default inference",
        official_editor="pending",
        physical_plc="pending",
    )
    (ROOT / "docs/validation/INDEXED-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "PASS: 10 indexed cases / 10240 scans / independent raw-word oracle, C++, IL, reverse and XML"
    )


if __name__ == "__main__":
    main()
