# ruff: noqa: E402
#!/usr/bin/env python3
"""Independent deterministic IL truth-table/state properties, no production writes."""

import argparse
import json
import random
import resource
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--repo", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(a.repo))
resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
from m200.model import Program
from m200.il import Machine, validate
from m200.reverse import to_cpp
from m200.native import run_native
from m200.frontend import compile_source

rng = random.Random(20020261106)
records = []
start = time.time()
reads = (
    ["0", "1"]
    + ["%I0." + str(i) for i in range(8)]
    + ["%M" + str(i) for i in range(16)]
    + ["%Q0." + str(i) for i in range(4)]
    + ["%S4", "%S5", "%S6", "%S7", "%S13"]
)
writes = ["%M" + str(i) for i in range(16)] + ["%Q0." + str(i) for i in range(4)]
ops = ["AND", "ANDN", "OR", "ORN", "XOR", "XORN"]


# Independent oracle does not call Machine or reverse to calculate expected bits.
def oracle(program, frames):
    mem = {}
    outputs = {}
    now = 0
    history = []
    for index, f in enumerate(frames):

        def rd(s):
            if s in ["0", "1"]:
                return s == "1"
            if s.startswith("%I0."):
                return bool(f["inputs"].get(str(int(s[4:])), False))
            if s.startswith("%M"):
                return mem.get(int(s[2:]), False)
            if s.startswith("%Q0."):
                return outputs.get(int(s[4:]), False)
            if s == "%S13":
                return index == 0
            period = {"%S4": 10, "%S5": 100, "%S6": 1000, "%S7": 60000}[s]
            return ((now // (period // 2)) & 1) == 1

        for rung in program.rungs:
            value = None
            for line in rung:
                op, arg = line.split()
                if op in ["ST", "S", "R"]:
                    target = mem if arg.startswith("%M") else outputs
                    n = int(arg[2:] if arg.startswith("%M") else arg[4:])
                    if op == "ST":
                        target[n] = value
                    elif value:
                        target[n] = op == "S"
                else:
                    right = rd(arg)
                    if op.endswith("N"):
                        right = not right
                    if op.startswith("LD"):
                        value = right
                    elif op.startswith("AND"):
                        value = bool(value and right)
                    elif op.startswith("OR"):
                        value = bool(value or right)
                    elif op.startswith("XOR"):
                        value = bool(value) ^ right
        history.append([outputs.get(i, False) for i in range(16)])
        now += f["dt_ms"]
    return history


for seedcase in range(12):
    rungs = []
    for op in ops:
        for store in ["ST", "S", "R"]:
            rungs.append(
                [
                    rng.choice(["LD", "LDN"]) + " " + rng.choice(reads),
                    op + " " + rng.choice(reads),
                    store + " " + rng.choice(writes),
                ]
            )
    for _ in range(22):
        rungs.append(
            [rng.choice(["LD", "LDN"]) + " " + rng.choice(reads)]
            + [
                rng.choice(ops) + " " + rng.choice(reads)
                for _ in range(rng.randrange(4))
            ]
            + [rng.choice(["ST", "S", "R"]) + " " + rng.choice(writes)]
        )
    # Commit several arbitrary memory bits to make internal sequential state observable.
    rungs += [["LD %M" + str(i), "ST %Q0." + str(i % 4)] for i in range(16)]
    program = Program(rungs)
    validate(program)
    frames = [
        {
            "dt_ms": rng.choice([0, 1, 5, 10, 100, 1000, 60000]),
            "inputs": {str(i): bool(rng.getrandbits(1)) for i in range(8)},
        }
        for _ in range(1000)
    ]
    m = Machine(program)
    vm = [m.step(f["inputs"], f["dt_ms"]) for f in frames]
    expected = oracle(program, frames)
    s = a.output / ("il_%02d.cpp" % seedcase)
    s.write_text(to_cpp(program))
    native = run_native(s, frames)
    ok = vm == expected == native
    rec = dict(
        case=seedcase,
        status="PASS" if ok else "BUG",
        frames=len(frames),
        rungs=len(rungs),
        instructions=sum(map(len, rungs)),
    )
    records.append(rec)
    print(json.dumps(rec), flush=True)
    if not ok:
        i = next(
            i for i in range(len(frames)) if vm[i] != expected[i] or vm[i] != native[i]
        )
        (a.output / ("mismatch_%02d.json" % seedcase)).write_text(
            json.dumps(
                dict(
                    program=program.as_dict(),
                    trace=frames[: i + 1],
                    frame=i,
                    oracle=expected[i],
                    il=vm[i],
                    native=native[i],
                ),
                indent=2,
            )
        )
# Explicit compile-back coverage for all operations on a small, bounded program.
p = Program(
    [["LD %I0.0", op + " %I0.1", "ST %Q0." + str(i)] for i, op in enumerate(ops)]
)
s = a.output / "all_ops_recompile.cpp"
s.write_text(to_cpp(p))
try:
    q = compile_source(s)
    fs = [{"0": bool(x & 1), "1": bool(x & 2)} for x in range(4)] * 25
    m = Machine(p)
    n = Machine(q)
    ok = all(m.step(f) == n.step(f) for f in fs)
    records.append(
        dict(
            case="all_ops_reverse_recompile",
            status="PASS" if ok else "BUG",
            frames=len(fs),
        )
    )
except Exception as e:
    records.append(
        dict(case="all_ops_reverse_recompile", status="BLOCKED", reason=str(e))
    )
summary = dict(
    seed=20020261106, elapsed_seconds=round(time.time() - start, 3), results=records
)
(a.output / "results.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary), flush=True)
