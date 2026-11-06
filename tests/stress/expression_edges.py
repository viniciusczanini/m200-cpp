#!/usr/bin/env python3
"""Conditional execution histories and real expression-edge rungs, local only."""

# ruff: noqa: E402
import argparse
import copy
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bit_objects import original
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SEED = 20020261117


def verify(p, frames, expected, work, name, source=None):
    def check(candidate, phase):
        vm = Machine(candidate)
        for i, (frame, row) in enumerate(zip(frames, expected)):
            got = vm.step(frame["inputs"], frame.get("dt_ms", 10))
            if got != row:
                raise AssertionError(f"{name} {phase} frame{i}: {got} != {row}")

    snapshot = copy.deepcopy(p.as_dict())
    check(p, "IL")
    check(Program.from_dict(json.loads(json.dumps(p.as_dict()))), "JSON")
    normalized = normalize(p)
    check(normalized, "normalized")
    if source is not None and run_native(source, frames) != expected:
        raise AssertionError(name + " source C++ differs")
    reverse = work / (name + "_reverse.cpp")
    reverse.write_text(to_cpp(p))
    if run_native(reverse, frames) != expected:
        raise AssertionError(name + " reverse C++ differs")
    rebuilt = compile_source(reverse)
    check(rebuilt, "rebuilt")
    dest = work / (name + ".smbp")
    for phase, candidate in [("original", p), ("rebuilt", rebuilt)]:
        write_project(candidate, ROOT / "tests/fixtures/synthetic.smbp", dest)
        loaded = load_project(dest)
        check(loaded, phase + " XML")
    exported = work / (name + "_exported.cpp")
    exported.write_text(to_cpp(loaded))
    if run_native(exported, frames) != expected:
        raise AssertionError(name + " actual exported IL to C++ differs")
    exported_rebuilt = compile_source(exported)
    check(exported_rebuilt, "actual exported C++ recompiled")
    write_project(exported_rebuilt, ROOT / "tests/fixtures/synthetic.smbp", dest)
    check(load_project(dest), "actual exported C++ new XML")
    if p.as_dict() != snapshot:
        raise AssertionError("original IR mutated")


def vectors():
    rng = random.Random(SEED)
    values = (
        [0, (1 << 24) - 1]
        + [1 << i for i in range(24)]
        + [((1 << 24) - 1) ^ (1 << i) for i in range(24)]
    )
    values += [rng.randrange(1 << 24) for _ in range(512 - len(values))]
    return values, [
        {"inputs": {i: bool(v & (1 << i)) for i in range(24)}} for v in values
    ]


def generated(base, rotation, values):
    def at(n):
        return (n + rotation) % 24

    body = f"""#include <plc.hpp>
bool invert(bool v){{return !v;}}
void scan(){{bool a=plc::input({at(0)})&&plc::rising({base},plc::input({at(1)}));
bool b=plc::input({at(2)})||plc::falling({base},plc::input({at(3)}));
bool c=false;bool d=false;if(plc::input({at(4)})){{c=plc::rising({base + 1},plc::input({at(5)}));}}
if(plc::input({at(6)})){{d=plc::falling({base + 1},plc::input({at(7)}));}}
bool e=plc::rising(254,plc::falling(254,plc::input({at(8)})));
bool f=(plc::input({at(9)})&&plc::input({at(10)}))||plc::falling(250,plc::input({at(11)}));
bool g=invert(plc::rising(251,plc::input({at(12)})));
plc::i16 i=0;plc::i16 count=0;while(i<4){{bool v=plc::input({at(14)});
if(i==1){{v=plc::input({at(15)});}}if(i==2){{v=plc::input({at(16)});}}if(i==3){{v=plc::input({at(17)});}}
if(plc::rising(249,v)){{count=plc::add_i16(count,1);}}i=plc::add_i16(i,1);}}
bool h=false;if(plc::input({at(19)})){{h=plc::rising(248,plc::input({at(18)}));}}
plc::write_m(0,plc::input({at(20)}));
plc::output(0,a);plc::output(1,b);plc::output(2,c);plc::output(3,d);plc::output(4,e);plc::output(5,f);plc::output(6,g);
plc::output(7,count>=2);plc::output(8,count==1);plc::output(9,count==0);
plc::output(10,plc::input_rising({at(18)}));plc::output(11,h);plc::output(12,plc::m_rising(0));
plc::output(13,plc::rising(247,plc::read_m(0)));plc::output(14,plc::falling(246,plc::read_m(0)));
plc::output(15,plc::rising(245,plc::output_state(0)));}}"""
    histories = {}
    previous = older = 0
    expected = []

    def edge(kind, index, value):
        old = histories.get((kind, index), False)
        value = bool(value)
        answer = {"R": (False, True, False, False), "F": (False, False, True, False)}[
            kind
        ][2 * int(old) + int(value)]
        histories[(kind, index)] = value
        return answer

    for raw in values:
        ins = [bool(raw & (1 << at(i))) for i in range(24)]
        a = ins[0] and edge("R", base, ins[1])
        b = ins[2] or edge("F", base, ins[3])
        c = edge("R", base + 1, ins[5]) if ins[4] else False
        d = edge("F", base + 1, ins[7]) if ins[6] else False
        e = edge("R", 254, edge("F", 254, ins[8]))
        f = (ins[9] and ins[10]) or edge("F", 250, ins[11])
        g = not edge("R", 251, ins[12])
        count = 0
        for value in ins[14:18]:
            count += int(edge("R", 249, value))
        h = edge("R", 248, ins[18]) if ins[19] else False
        contact = bool(raw & ~previous & (1 << at(18)))
        memory = bool(previous & ~older & (1 << at(20)))
        expected.append(
            [
                a,
                b,
                c,
                d,
                e,
                f,
                g,
                count >= 2,
                count == 1,
                count == 0,
                contact,
                h,
                memory,
                edge("R", 247, ins[20]),
                edge("F", 246, ins[20]),
                edge("R", 245, a),
            ]
        )
        older, previous = previous, raw
    return body, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    args = parser.parse_args()
    values, frames = vectors()
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-expression-edges-") as folder:
        work = Path(folder)

        def run(name, p, expected, source=None, **extra):
            if args.case is not None and args.case != name:
                return
            verify(p, frames, expected, work, name, source)
            results.append(dict(case=name, scans=len(frames), status="pass", **extra))
            print(f"PASS: {name} / {len(frames)} scans", flush=True)

        for rotation, base in enumerate([0, 30, 31, 32, 63, 127, 200, 252]):
            name = f"calls_{base}"
            if args.case is not None and args.case != name:
                continue
            body, expected = generated(base, rotation, values)
            source = work / (name + ".cpp")
            source.write_text(body)
            run(name, compile_source(source), expected, source)
        for rung, output, index, word in [
            (10, 0, 0, 10),
            (15, 4, 1, 12),
            (20, 11, 2, 14),
        ]:
            name = f"public_T_{rung}"
            if args.case is not None and args.case != name:
                continue
            entry, lines = original(
                ROOT / "docs/capabilities/INDEXED-SOURCES.json",
                "T",
                "indexed-sources",
                rung,
            )
            if lines != [
                "LD %S6",
                f"AND %Q0.{output}",
                f"RISING{index}",
                f"[ %MD{word} := %MD{word} + 1 ]",
            ]:
                raise AssertionError("original expression edge rung changed")
            p = Program(
                [
                    ["LD %S13", f"[%MD{word}:=0]"],
                    ["LD %I0.0", f"ST %Q0.{output}"],
                    lines,
                    ["LD 1", f"[%Q0.0:16:=%MD{word}]"],
                ]
            )
            old = False
            count = 0
            expected = []
            for n, value in enumerate(values):
                enabled = bool((n // 50) % 2) and bool(value & 1)
                if enabled and not old:
                    count += 1
                old = enabled
                expected.append([bool(count & (1 << bit)) for bit in range(16)])
            run(
                name,
                p,
                expected,
                original_sha256=entry["sha256"],
                rung=rung,
                scope="complete isolated original; explicit Q input, S6 local clock and MD cold-init/readback harness; original raw graph not emitted",
            )
        name = "full_capacity"
        if args.case is None or args.case == name:
            p = Program(
                [["LD 1", "[%MW0:=0]", "[%MW1:=0]"]]
                + [
                    [f"LD %I0.{i % 24}", f"RISING{i}", "[%MW0:=%MW0+1]"]
                    for i in range(255)
                ]
                + [
                    [f"LD %I0.{i % 24}", f"FALLING{i}", "[%MW1:=%MW1+1]"]
                    for i in range(255)
                ]
                + [["LD 1", "[%Q0.0:8:=%MW0]", "[%Q0.8:8:=%MW1]"]]
            )
            old = 0
            expected = []
            for value in values:
                up = sum(bool(value & ~old & (1 << (i % 24))) for i in range(255))
                down = sum(bool(old & ~value & (1 << (i % 24))) for i in range(255))
                expected.append(
                    [bool(up & (1 << bit)) for bit in range(8)]
                    + [bool(down & (1 << bit)) for bit in range(8)]
                )
                old = value
            run(
                name,
                p,
                expected,
                identities_per_kind=255,
                scope="every function result contributes to an observed counter; C++ and exported-project roundtrips required",
            )
    if args.case is not None and not results:
        raise AssertionError("unknown case")
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "tests/fixtures/synthetic.smbp",
        ROOT / "docs/capabilities/INDEXED-SOURCES.json",
    ]
    report = dict(
        seed=SEED,
        target="TM200CE40T",
        cases=results,
        scans=sum(r["scans"] for r in results),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        whole_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
        history_policy="local per-execution/initial-false, pending external confirmation",
    )
    if args.case is None:
        (ROOT / "docs/validation/EXPRESSION-EDGE-STRESS-RESULTS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; call-history truth-table oracle and actual exported C++ recompilation"
    )


if __name__ == "__main__":
    main()
