#!/usr/bin/env python3
"""Mode composition against an independent, one-event-per-tick oracle."""

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
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import write_project
from m200.reverse import to_cpp

SEED = 20020261112


class TickOracle:
    def __init__(self, kind, ret, dyn, base, preset):
        self.kind, self.ret, self.dyn, self.base = kind, ret, dyn, base
        self.p = self.limit = preset
        self.v = 0
        self.q = False
        self.wired = False
        self.last = False
        self.next = None
        self.completed = False

    def finish(self):
        self.completed = True
        self.q = self.kind == "Ton"
        self.next = None

    def advance(self, now):
        while self.next is not None and self.next <= now:
            if self.dyn:
                self.limit = self.p
            if self.v < self.limit:
                self.v += 1
            if self.v >= self.limit:
                self.finish()
            else:
                self.next += self.base
        if self.kind == "Pulse" and self.next is None and not self.last:
            self.v = 0

    def write(self, value):
        self.p = value
        inactive = not self.last if self.kind == "Ton" else self.last
        if self.ret and self.dyn and self.next is None and inactive and value < self.v:
            self.v = 0

    def begin(self, now):
        self.limit = self.p
        self.completed = False
        if not self.ret:
            self.v = 0
        self.next = now + self.base
        if self.v >= self.limit:
            self.finish()

    def scan(self, now, ins):
        self.advance(now)
        chosen = sum(1 << b for b in range(3) if ins[b])
        if ins[3] and not ins[6]:
            self.write(chosen)
        if not ins[5]:
            enabled = ins[4]
            if self.kind == "Ton":
                if not enabled:
                    if not self.ret or self.completed:
                        self.v = 0
                    self.next = None
                    self.completed = False
                    self.q = False
                elif self.next is None and not self.completed:
                    self.begin(now)
            elif self.kind == "Tof":
                if enabled:
                    if not self.ret or self.completed:
                        self.v = 0
                    self.next = None
                    self.completed = False
                    self.q = True
                elif self.last:
                    self.begin(now)
            elif enabled and not self.last and self.next is None:
                self.q = True
                self.begin(now)
            self.last = enabled
            if self.kind == "Pulse" and self.next is None and not enabled:
                self.v = 0
            self.wired = self.q
            if ins[3] and ins[6]:
                self.write(chosen)
        row = [self.q, self.wired]
        row += [bool(self.v & (1 << b)) for b in range(3)]
        row += [bool(self.p & (1 << b)) for b in range(3)]
        return row + [False] * 8


def source_for(kind, index, base, preset, ret, dyn):
    s = f"#include <plc.hpp>\nplc::{kind} t{{{index},{base},{preset},{str(ret).lower()},{str(dyn).lower()}}};\nvoid scan(){{plc::i16 p=0;bool q=false;\n"
    for b in range(3):
        s += f"if(plc::input({b})){{p=plc::add_i16(p,{1 << b});}}\n"
    s += "if(plc::input(3) && !plc::input(6)){t.set_preset(p);}\nif(plc::input(5)){goto observe;}\n"
    s += "q=t.update(plc::input(4));plc::output(1,q);\nif(plc::input(3) && plc::input(6)){t.set_preset(p);}\nobserve:;plc::output(0,t.done());\n"
    for b in range(3):
        s += f"plc::output({b + 2},plc::and_i16(t.value(),{1 << b})!=0);\n"
        s += f"plc::output({b + 5},plc::and_i16(t.preset(),{1 << b})!=0);\n"
    return s + "}\n"


def check_case(work, name, kind, index, base, preset, ret, dyn, rng):
    source = work / (name + ".cpp")
    source.write_text(source_for(kind, index, base, preset, ret, dyn))
    program = compile_source(source)
    frames = [
        {
            "dt_ms": rng.choice((0, max(1, base // 2), base, base * 3)),
            "inputs": {b: bool(value & (1 << b)) for b in range(7)},
        }
        for value in list(range(128)) + [rng.randrange(128) for _ in range(384)]
    ]
    oracle = TickOracle(kind, ret, dyn, base, preset)
    now = 0
    expected = []
    for frame in frames:
        expected.append(oracle.scan(now, frame["inputs"]))
        now += frame["dt_ms"]

    def check(p, label):
        m = Machine(p)
        for i, (f, row) in enumerate(zip(frames, expected)):
            got = m.step(f["inputs"], f["dt_ms"])
            if got != row:
                raise AssertionError(f"{name} {label} frame{i}: {got} != {row}")

    check(program, "IL")
    check(Program.from_dict(program.as_dict()), "JSON")
    if run_native(source, frames) != expected:
        raise AssertionError(name + " original SDK differs")
    reverse = work / (name + "_reverse.cpp")
    reverse.write_text(to_cpp(program))
    if run_native(reverse, frames) != expected:
        raise AssertionError(name + " reverse SDK differs")
    rebuilt = compile_source(reverse)
    check(rebuilt, "recompiled")
    if rebuilt.timers != program.timers:
        raise AssertionError("timer configuration/identity changed")
    dest = work / (name + ".smbp")
    dest.write_bytes(b"existing project")
    try:
        write_project(program, ROOT / "tests/fixtures/synthetic.smbp", dest)
    except CompileError as exc:
        if "timer-mode functional-level mapping is unverified" not in str(exc):
            raise
    else:
        raise AssertionError("unverified timer-mode profile exported")
    if dest.read_bytes() != b"existing project":
        raise AssertionError("rejected export changed destination")
    return dict(
        case=name,
        kind=kind,
        base_ms=base,
        retentive=ret,
        dynamic_preset=dyn,
        scans=len(frames),
        status="pass",
        xml="gated: functional-level mapping unverified",
    )


def main():
    rng = random.Random(SEED)
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-timer-mode-stress-") as directory:
        work = Path(directory)
        configs = [
            (kind, ret, dyn)
            for kind in ("Ton", "Tof")
            for ret, dyn in ((True, False), (False, True), (True, True))
        ] + [("Pulse", False, True)]
        for kind, ret, dyn in configs:
            for base in (1, 10, 100, 1000, 60000):
                name = f"{kind}_{int(ret)}_{int(dyn)}_{base}"
                result = check_case(
                    work, name, kind, 4 if base == 1 else 42, base, 5, ret, dyn, rng
                )
                results.append(result)
                print(f"PASS: {name} / 512 scans", flush=True)
        manifest = json.loads((ROOT / "tests/public/manifest.json").read_text())
        entry = next(e for e in manifest["sources"] if e["file"] == "06-correto.smbp")
        original = ROOT / "research/downloads/public-projects" / entry["file"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != entry["sha256"]:
            raise AssertionError("original digest mismatch")
        tree = ET.parse(original)
        node = next(
            n
            for n in tree.findall(".//Timers/TimerTM")
            if n.findtext("IsRetentive") == "true"
        )
        if node.findtext("Base") != "OneSecond":
            raise AssertionError("unexpected source base")
        result = check_case(
            work,
            "original_retained_tm3_config",
            {"TON": "Ton", "TOF": "Tof", "TP": "Pulse"}[node.findtext("Type", "TON")],
            int(node.findtext("Index")),
            1000,
            int(node.findtext("Preset")),
            True,
            False,
            rng,
        )
        result.update(
            original_sha256=entry["sha256"],
            original_cpu=entry["cpu"],
            scope="actual isolated TimerTM configuration; constructed input/observation harness; no original executable TM3 use found, no whole-project import, no CPU rewrite",
        )
        results.append(result)
        if hashlib.sha256(original.read_bytes()).hexdigest() != entry["sha256"]:
            raise AssertionError("original bytes changed")
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
        model="activation/resume-relative ticks; integer retention; preset applies next tick; preserved V above reduced P; completion latched",
        official_editor="pending",
        physical_plc="pending",
    )
    (ROOT / "docs/validation/TIMER-MODE-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; tick-event oracle / SDK / VM / JSON / reverse / recompile; XML gate"
    )


if __name__ == "__main__":
    main()
