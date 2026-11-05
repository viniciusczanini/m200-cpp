#!/usr/bin/env python3
"""Reproducible native logic and authentic isolated IL against separate oracles."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project, check_graph
from m200.reverse import to_cpp

SEED = 20020261113


def verify(p, frames, expected, work, name):
    def check(candidate, label):
        m = Machine(candidate)
        for i, (f, row) in enumerate(zip(frames, expected)):
            got = m.step(f["inputs"], f["dt_ms"])
            if got != row:
                raise AssertionError(f"{name} {label} frame{i}: {got} != {row}")

    check(p, "native IL")
    before = json.dumps(p.as_dict(), sort_keys=True)
    normalized = normalize(p)
    check(normalized, "normalized")
    if json.dumps(p.as_dict(), sort_keys=True) != before:
        raise AssertionError("original IR mutated")
    for phase, candidate in [("original", p), ("normalized", normalized)]:
        path = work / (name + "_" + phase + ".cpp")
        path.write_text(to_cpp(candidate))
        if run_native(path, frames) != expected:
            raise AssertionError(name + " " + phase + " C++ differs")
        check(compile_source(path), phase + " recompiled")
    dest = work / (name + ".smbp")
    write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
    check(load_project(dest), "SMBP")


def generated(case, frames):
    a, b, c, d = [(case + i) % 8 for i in range(4)]
    group = "AND(" if case % 2 == 0 else "OR("
    inner = "OR" if case % 2 == 0 else "AND"
    p = Program(
        [
            [f"LD %I0.{a}", "ST %M500"],
            [f"LD %I0.{b}", "ST %M501"],
            [
                "LD %M500",
                "MPS",
                group + " %M501",
                inner + f" %I0.{c}",
                ")",
                "STN %Q0.0",
                "MPP",
                f"XOR %I0.{d}",
                "ST %Q0.1",
            ],
            ["LD %Q0.0", "ANDN %Q0.1", "ST %Q0.2"],
            [
                "LD %I0.4",
                "MPS",
                "[%MW100:=%MW100+1]",
                "MPP",
                "AND %I0.5",
                "[%MW100:=%MW100+2]",
            ],
            ["LD [%MW100>10]", "ST %Q0.3"],
            [
                "LD %M500",
                "MPS",
                "N",
                "ST %M500",
                "MRD",
                "ST %Q0.4",
                "MPP",
                "AND %M500",
                "ST %Q0.5",
            ],
            ["LD %I0.6", "S %M700"],
            ["LD %I0.7", "R %M700"],
            ["LD %M700", "ST %Q0.6"],
        ],
        symbols={
            "%M500": "user_a",
            "%M501": "user_b",
            "%M700": "user_state",
            "%MW100": "user_count",
        },
    )
    count = 0
    state = False
    rows = []
    for f in frames:
        ins = f["inputs"]
        outer = ins[a]
        other = ins[b] or ins[c] if case % 2 == 0 else ins[b] and ins[c]
        q0 = not (outer and other if case % 2 == 0 else outer or other)
        q1 = outer != ins[d]
        if ins[4]:
            count += 1 + (2 if ins[5] else 0)
        if ins[6]:
            state = True
        if ins[7]:
            state = False
        rows.append(
            [q0, q1, q0 and not q1, count > 10, outer, False, state] + [False] * 9
        )
    return p, rows


def main():
    rng = random.Random(SEED)
    results = []
    frames = [
        {
            "dt_ms": rng.choice((0, 10, 100)),
            "inputs": {b: bool(n & (1 << b)) for b in range(8)},
        }
        for n in list(range(256)) + [rng.randrange(256) for _ in range(256)]
    ]
    with tempfile.TemporaryDirectory(prefix="m200-native-logic-stress-") as directory:
        work = Path(directory)
        for case in range(6):
            p, rows = generated(case, frames)
            name = f"generated_{case}"
            verify(p, frames, rows, work, name)
            results.append(dict(case=name, scans=512, status="pass"))
            print(f"PASS: {name} / 512 scans", flush=True)
        p = Program(
            [
                ["LD 1", "[%MW0:=0]"],
                ["%L0:", "LD [%MW0<3]", "JMPC %L1"],
                ["LD 1", "JMP %L2"],
                [
                    "%L1:",
                    "LD %I0.0",
                    "MPS",
                    "N",
                    "ST %M10",
                    "MPP",
                    "AND %I0.1",
                    "ST %Q0.4",
                ],
                ["LD 1", "[%MW0:=%MW0+1]"],
                ["JMP %L0"],
                ["%L2:", "LD [%MW0=3]", "ST %Q0.0"],
                ["LD %M10", "ST %Q0.1"],
            ]
        )
        rows = [
            [True, not f["inputs"][0], False, False, f["inputs"][0] and f["inputs"][1]]
            + [False] * 11
            for f in frames
        ]
        verify(p, frames, rows, work, "loop")
        results.append(dict(case="loop", scans=512, status="pass"))
        # Pin both original files; originals remain foreign CPU and untouched.
        manifests = [
            ROOT / "tests/public/manifest.json",
            ROOT / "tests/public/control-flow-manifest.json",
        ]
        sources = [
            entry
            for path in manifests
            for entry in json.loads(path.read_text())["sources"]
        ]

        def original(filename, rung):
            entry = next(e for e in sources if e["file"] == filename)
            path = ROOT / "research/downloads/public-projects" / filename
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise AssertionError("original digest changed")
            tree = ET.fromstring(raw)
            node = tree.findall(".//RungEntity")[rung]
            lines = [
                " ".join(n.text.split())
                for n in node.findall(
                    "./InstructionLines/InstructionLineEntity/InstructionLine"
                )
            ]
            return entry, tree, lines

        entry, _, lines = original("01-XIC-XIO parallel.smbp", 1)
        p = Program([lines])
        rows = [
            [False, f["inputs"][0] and f["inputs"][2]] + [False] * 14 for f in frames
        ]
        verify(p, frames, rows, work, "public_parentheses")
        results.append(
            dict(
                case="public_parentheses",
                scans=512,
                status="pass",
                original_sha256=entry["sha256"],
                scope="isolated actual rung1; no graphical agreement/whole-project import",
            )
        )
        entry, tree, lines = original("flow-original-loop.smbp", 4)
        prefix = [[f"LD %I0.{i}", f"ST %M{i + 2}"] for i in range(3)]
        p = Program(prefix + [lines])
        rows = [
            [f["inputs"][0] and f["inputs"][1], f["inputs"][0] and f["inputs"][2]]
            + [False] * 14
            for f in frames
        ]
        verify(p, frames, rows, work, "public_stack")
        results.append(
            dict(
                case="public_stack",
                scans=512,
                status="pass",
                original_sha256=entry["sha256"],
                scope="isolated actual rung4 with explicit M input harness",
            )
        )
        _, _, lines = original("flow-original-loop.smbp", 8)
        node = next(
            t
            for t in tree.findall(".//Timers/TimerTM")
            if t.findtext("Address") == "%TM0"
        )
        assert (
            node.findtext("Type") == "TOF"
            and node.findtext("Base") == "OneHundredMilliSeconds"
        )
        cfg = Timer("TOF", int(node.findtext("Preset")) * 100, 100)
        p = Program([["LD %I0.0", "IN %TM0"], lines, ["LD %M2", "ST %Q0.0"]], {0: cfg})
        tf = [
            {"dt_ms": rng.choice((0, 100, 500, 1000)), "inputs": f["inputs"]}
            for f in frames
        ]
        q = False
        previous = False
        end = None
        now = 0
        rows = []
        for f in tf:
            active = f["inputs"][0]
            if active:
                q = True
                end = None
            elif previous:
                end = now + cfg.milliseconds
            if end is not None and now >= end:
                q = False
            rows.append([not q] + [False] * 15)
            previous = active
            now += f["dt_ms"]
        verify(p, tf, rows, work, "public_stn_timer")
        results.append(
            dict(
                case="public_stn_timer",
                scans=512,
                status="pass",
                original_sha256=entry["sha256"],
                scope="isolated actual STN rung8 and original explicit TOF config; constructed direct-IN harness",
            )
        )
        fixture = json.loads(
            (ROOT / "tests/fixtures/native_timer_graphs.json").read_text()
        )
        for item in fixture["cases"]:
            check_graph(ET.fromstring(item["rung_xml"]), item["il"])
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/public/manifest.json",
        ROOT / "tests/fixtures/native_timer_graphs.json",
    ]
    report = dict(
        seed=SEED,
        cases=results,
        scans=sum(r["scans"] for r in results),
        authentic_timer_graphs=[35, 36],
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        whole_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
    )
    (ROOT / "docs/validation/NATIVE-LOGIC-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; native IL, independent oracle, C++, normalization and XML; authentic isolated originals"
    )


if __name__ == "__main__":
    main()
