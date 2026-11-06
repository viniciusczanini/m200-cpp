#!/usr/bin/env python3
"""Timer property timelines against an event oracle and pinned original IL."""

# ruff: noqa: E402
import argparse
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
from m200.model import Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project, BASES
from m200.reverse import to_cpp

SEED = 20020261111


class EventOracle:
    """Store activation events/end times; do not call the production state engine."""

    def __init__(self, kind, base, preset):
        self.kind, self.base, self.preset = kind, base, preset
        self.event = None
        self.last_input = False
        self.q = False
        self.wired = False
        self.value = 0

    def observe(self, now):
        if self.event is not None:
            start, ticks = self.event
            end = start + ticks * self.base
            self.value = min(ticks, (now - start) // self.base)
            self.q = now >= end if self.kind == "Ton" else now < end
            if self.kind == "Pulse" and now >= end and not self.last_input:
                self.value = 0

    def scan(self, now, inputs):
        self.observe(now)
        chosen = sum(1 << b for b in range(3) if inputs[b])
        if not inputs[6]:
            self.preset = chosen
        if not inputs[5]:
            enabled = inputs[4]
            if self.kind == "Ton":
                if not enabled:
                    self.event = None
                    self.q = False
                    self.value = 0
                elif not self.last_input:
                    self.event = (now, self.preset)
            elif self.kind == "Tof":
                if enabled:
                    self.event = None
                    self.q = True
                    self.value = 0
                elif self.last_input:
                    self.event = (now, self.preset)
            elif enabled and not self.last_input:
                if (
                    self.event is None
                    or now >= self.event[0] + self.event[1] * self.base
                ):
                    self.event = (now, self.preset)
            self.last_input = enabled
            self.observe(now)
            self.wired = self.q
            if inputs[6]:
                self.preset = chosen
        self.observe(now)
        row = [self.q, self.wired]
        row += [bool(self.value & (1 << b)) for b in range(3)]
        row += [bool(self.preset & (1 << b)) for b in range(3)]
        return row + [False] * 8


def verify(program, source, frames, expected, work, name):
    def check(p, label):
        machine = Machine(p)
        for i, (frame, row) in enumerate(zip(frames, expected)):
            got = machine.step(frame["inputs"], frame["dt_ms"])
            if got != row:
                raise AssertionError(f"{name} {label}: frame {i}: {got} != {row}")

    check(program, "IL")
    if run_native(source, frames) != expected:
        raise AssertionError(name + " native C++ differs")
    reverse = work / (name + "_reverse.cpp")
    reverse.write_text(to_cpp(program))
    if run_native(reverse, frames) != expected:
        raise AssertionError(name + " reverse C++ differs")
    rebuilt = compile_source(reverse)
    check(rebuilt, "recompiled")
    if rebuilt.timers != program.timers:
        raise AssertionError(name + " lost timer identity/configuration")
    destination = work / (name + ".smbp")
    write_project(program, ROOT / "tests/fixtures/synthetic.smbp", destination)
    check(load_project(destination), "XML")
    write_project(rebuilt, ROOT / "tests/fixtures/synthetic.smbp", destination)
    check(load_project(destination), "reverse XML")


def generated_source(kind, index, base):
    body = (
        f"plc::{kind} t{{{index},{base},3}};void scan(){{\nplc::i16 p=0;bool q=false;\n"
    )
    for b in range(3):
        body += f"if(plc::input({b})){{p=plc::add_i16(p,{1 << b});}}\n"
    body += "if(!plc::input(6)){t.set_preset(p);}\nif(plc::input(5)){goto observe;}\n"
    body += "q=t.update(plc::input(4));plc::output(1,q);\nif(plc::input(6)){t.set_preset(p);}\nobserve:;plc::output(0,t.done());\n"
    for b in range(3):
        body += f"plc::output({b + 2},plc::and_i16(t.value(),{1 << b})!=0);\n"
        body += f"plc::output({b + 5},plc::and_i16(t.preset(),{1 << b})!=0);\n"
    return "#include <plc.hpp>\n" + body + "}\n"


def original_case(work, rng):
    manifest = json.loads((ROOT / "docs/capabilities/INDEXED-SOURCES.json").read_text())
    entry = next(e for e in manifest["sources"] if e["id"] == "I1")
    path = ROOT / "research/downloads/indexed-sources" / entry["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise AssertionError("original digest differs")
    tree = ET.parse(path)
    line = next(
        n.text
        for n in tree.findall(".//InstructionLine")
        if n.text and "%TM1.P" in n.text and "%MW20[%MW10]" in n.text
    )
    node = next(
        n for n in tree.findall(".//Timers/TimerTM") if n.findtext("Address") == "%TM1"
    )
    base = {v: k for k, v in BASES.items()}[node.findtext("Base")]
    config = Timer(
        node.findtext("Type", "TON"), int(node.findtext("Preset")) * base, base
    )
    rungs = [["LD 1", "[%MW10:=0]"]]
    rungs += [[f"LD %I0.{b}", f"[%MW10:=%MW10+{1 << b}]"] for b in range(3)]
    rungs += [["LD 1", f"[%MW{20 + i}:={7 - i}]"] for i in range(8)]
    rungs += [["LD 1", line.strip()]]
    # Observe P without inventing the surrounding unsupported native algorithm.
    rungs += [[f"LD [%TM1.P={7 - i}]", f"ST %Q0.{i}"] for i in range(8)]
    program = Program(rungs, {1: config})
    frames = [
        {"dt_ms": 100, "inputs": {b: bool(value & (1 << b)) for b in range(7)}}
        for value in list(range(128)) + [rng.randrange(128) for _ in range(384)]
    ]
    expected = []
    for f in frames:
        index = sum(1 << b for b in range(3) if f["inputs"][b])
        expected.append([i == index for i in range(8)] + [False] * 8)
    source = work / "original.cpp"
    source.write_text(to_cpp(program))
    verify(program, source, frames, expected, work, "original_indexed_timer_preset")
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise AssertionError("original changed")
    return dict(
        case="original_indexed_timer_preset",
        scans=len(frames),
        status="pass",
        original_sha256=entry["sha256"],
        original_cpu=entry["cpu"],
        original_line=line,
        scope="isolated executable assignment and original TM1 configuration; no CPU rewrite or whole-project import",
        xml="synthetic-profile pass",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a fresh report here instead of updating the historical report",
    )
    args = parser.parse_args(argv)
    output = args.output or ROOT / "docs/validation/TIMER-PROPERTY-STRESS-RESULTS.json"
    if args.output is not None and output.exists():
        parser.error("explicit output already exists; choose a fresh report path")
    rng = random.Random(SEED)
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-timer-property-stress-") as directory:
        work = Path(directory)
        for kind in ("Ton", "Tof", "Pulse"):
            for base in (1, 10, 100, 1000, 60000):
                index = 4 if base == 1 else 42
                name = f"{kind}_{base}"
                frames = [
                    {
                        "dt_ms": rng.choice((0, max(1, base // 2), base, base * 3)),
                        "inputs": {b: bool(value & (1 << b)) for b in range(7)},
                    }
                    for value in list(range(128))
                    + [rng.randrange(128) for _ in range(384)]
                ]
                oracle = EventOracle(kind, base, 3)
                now = 0
                expected = []
                for frame in frames:
                    expected.append(oracle.scan(now, frame["inputs"]))
                    now += frame["dt_ms"]
                source = work / (name + ".cpp")
                source.write_text(generated_source(kind, index, base))
                program = compile_source(source)
                verify(program, source, frames, expected, work, name)
                results.append(
                    dict(
                        case=name,
                        scans=len(frames),
                        status="pass",
                        xml="synthetic-profile pass",
                    )
                )
                print(f"PASS: {name} / {len(frames)} scans", flush=True)
        results.append(original_case(work, rng))
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
    ]
    report = dict(
        seed=SEED,
        cases=results,
        scans=sum(r["scans"] for r in results),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        model="nondynamic, nonretentive; activation-relative time quantization; independent event/end-time oracle",
        official_editor="pending",
        physical_plc="pending",
    )
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        output.write_text(data)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as report_file:
            report_file.write(data)
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; original indexed assignment isolated; no whole-project import or official acceptance"
    )


if __name__ == "__main__":
    main()
