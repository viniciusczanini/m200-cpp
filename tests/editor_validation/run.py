#!/usr/bin/env python3
"""Prepare deterministic complex candidates; never operates editor or hardware."""

# ruff: noqa: E402
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import SDK, compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import Program
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SOURCES = ROOT / "examples/editor_validation"
TEMPLATE = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trace_for(name):
    phases = []

    def add(label, controls, count):
        phases.append((label, list(controls) + [False] * (3 - len(controls)), count))

    add("initial", [], 4)
    if name == "state_arrays":
        for batch in range(1, 5):
            add(f"pulse_{batch}", [True], 3)
            add(f"release_{batch}", [], 2)
        add("reset_while_held", [True, True], 3)
        add("held_after_reset_no_new_edge", [True], 3)
        add("release_after_reset", [], 2)
        add("fresh_pulse_after_reset", [True], 3)
        add("final", [], 2)
    elif name == "timed_counter":
        add("premature_pulse_ignored", [True], 2)
        add("held_while_timer_becomes_ready_no_new_edge", [True, True], 12)
        add("release_enabled", [False, True], 2)
        for count in range(1, 5):
            add(f"qualified_pulse_{count}", [True, True], 3)
            add(f"qualified_release_{count}", [False, True], 2)
        add("reset_dominates", [True, True, True], 3)
        add("held_after_reset_no_new_edge", [True, True], 12)
        add("release_after_reset", [False, True], 2)
        add("fresh_qualified_pulse", [True, True], 3)
        add("disable_timer_while_input_held", [True], 4)
        add("release_disabled", [], 3)
        add("final_reset", [False, False, True], 3)
        add("final", [], 3)
    else:
        add("high_bcd_carriers", [True], 4)
        add("lower_bcd_carriers", [], 4)
        for i in range(12):
            add(f"alternate_{i}", [bool(i % 2)], 1)
        add("final_high", [True], 4)
    frames = []
    for label, controls, count in phases:
        frames += [
            dict(phase=label, controls=controls, dt_ms=100) for _ in range(count)
        ]
    return frames


def oracle(name, frames):
    rows = []
    previous = False
    balances, batches = [1000, -2000, 3000, 4000], 0
    now, start, count, latched = 0, None, 0, False
    for frame in frames:
        a, b, c = frame["controls"]
        rise, previous = a and not previous, a
        if name == "state_arrays":
            if b:
                balances, batches = [1000, -2000, 3000, 4000], 0
            if rise and not b and batches < 3:
                balances = [v + 250 * (i + 1) for i, v in enumerate(balances)]
                batches += 1
            checksum = sum(v * (i + 1) for i, v in enumerate(balances))
            code = checksum // 250
            bits = [checksum == v for v in (22000, 29500, 37000, 44500)]
            bits += [batches == v for v in range(4)]
            bits += [bool(code & (1 << i)) for i in range(8)]
            memory = {
                "MD100": checksum,
                "MW102": batches,
                "MD104": balances[0],
                "MD106": balances[3],
            }
        elif name == "timed_counter":
            if b and not c:
                if start is None:
                    start = now
                timer_value = min(5, (now - start) // 100)
            else:
                start, timer_value = None, 0
            qualified = timer_value == 5
            if c:
                count, latched = 0, False
            elif rise and qualified:
                count += 1
            complete = count == 3
            latched |= complete
            bits = [
                qualified,
                count == 1,
                count == 2,
                complete,
                latched,
                count == 0,
                b,
                c,
            ]
            bits += [bool(count & (1 << i)) for i in range(4)]
            bits += [timer_value > 0, True, True, True]
            memory = {
                "MW120": count,
                "MW121": timer_value,
                "MW122": 5,
                "MW123": 3,
                "MW124": int(latched),
            }
        else:
            decimal, long_decimal = (9999, 99999999) if a else (2450, 81234567)
            packed = int(str(decimal), 16)
            long_packed = int(str(long_decimal), 16)
            memory = {
                "MW140": -20442,
                "MW141": 32767,
                "MW142": packed - 65536 if packed >= 32768 else packed,
                "MW143": decimal,
                "MD146": long_packed - (1 << 32),
                "MD148": long_decimal,
                "MD150": (4660 << 16) | packed,
                "MD160": (4660 << 16) | packed,
            }
            bits = [True] * 16
        rows.append(dict(bits=bits, memory=memory))
        now += frame["dt_ms"]
    return rows


def word_indexes(memory):
    return sorted(
        {
            int(key[2:]) + offset
            for key in memory
            for offset in range(2 if key.startswith("MD") else 1)
        }
    )


def decoded_memory(raw_words, fields):
    values = {}
    for field in fields:
        index = int(field[2:])
        width = 32 if field.startswith("MD") else 16
        raw = raw_words[index]
        if width == 32:
            raw |= raw_words[index + 1] << 16
        values[field] = raw - (1 << width) if raw >= (1 << (width - 1)) else raw
    return values


def native_rows(source, frames, memory_variant, fields, folder, tag):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ is required")
    indexes = word_indexes(fields)
    harness = folder / (tag + "_harness.cpp")
    binary = folder / (tag + "_harness")
    bit_expr = (
        "plc::detail::memory[704+i]" if memory_variant else "plc::detail::outputs[i]"
    )
    code = """#include <cstdio>
#define PLC_NATIVE
#include %s
int main(){unsigned dt,v;while(std::scanf("%%u",&dt)==1){
for(int i=0;i<24;++i){if(std::scanf("%%u",&v)!=1)return 2;plc::detail::inputs[i]=v!=0;}
for(int i=0;i<3;++i){if(std::scanf("%%u",&v)!=1)return 3;plc::detail::memory[800+i]=v!=0;}
plc::detail::begin_scan();scan();
for(int i=0;i<16;++i)std::putchar(%s?'1':'0');
%s
std::putchar('\\n');plc::detail::first_scan=false;plc::detail::now_ms+=dt;}}
""" % (
        json.dumps(str(source.resolve())),
        bit_expr,
        "".join(
            f'std::printf(" %u",(unsigned)plc::detail::words[{i}]);' for i in indexes
        ),
    )
    harness.write_text(code)
    result = subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O0",
            "-I",
            str(SDK),
            str(harness),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    trace = []
    for frame in frames:
        controls = frame["controls"]
        inputs = [False] * 24 if memory_variant else controls + [False] * 21
        memory = controls if memory_variant else [False] * 3
        trace.append(" ".join(str(int(v)) for v in [frame["dt_ms"], *inputs, *memory]))
    result = subprocess.run(
        [str(binary)],
        input="\n".join(trace) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(
            f"native execution failed: {result.returncode} {result.stderr}"
        )
    rows = []
    for line in result.stdout.splitlines():
        bits, *words = line.split()
        if len(bits) != 16 or len(words) != len(indexes):
            raise AssertionError("invalid native observation row")
        rows.append(
            dict(
                bits=[v == "1" for v in bits],
                memory=decoded_memory(dict(zip(indexes, map(int, words))), fields),
            )
        )
    if len(rows) != len(frames):
        raise AssertionError("native frame count mismatch")
    return rows


def check_machine(program, frames, expected, memory_variant, tag):
    vm = Machine(program)
    indexes = word_indexes(expected[0]["memory"])
    for n, (frame, wanted) in enumerate(zip(frames, expected)):
        inputs = {} if memory_variant else dict(enumerate(frame["controls"]))
        if memory_variant:
            for i, state in enumerate(frame["controls"]):
                vm.memory[800 + i] = state
        outputs = vm.step(inputs, frame["dt_ms"])
        actual = dict(
            bits=list(vm.memory[704:720]) if memory_variant else outputs,
            memory=decoded_memory({i: vm.words[i] for i in indexes}, wanted["memory"]),
        )
        if actual != wanted:
            raise AssertionError(
                f"{tag} frame{n} {frame['phase']}: {actual} != {wanted}"
            )


def run_case(name, memory_variant, output):
    case = name + ("_memory" if memory_variant else "")
    folder = output / case
    folder.mkdir()
    source = SOURCES / (case + ".cpp")
    frames, expected = trace_for(name), oracle(name, trace_for(name))
    p = compile_source(source)
    for phase, candidate in [
        ("IL", p),
        ("JSON", Program.from_dict(json.loads(json.dumps(p.as_dict())))),
        ("normalized", normalize(p)),
    ]:
        check_machine(candidate, frames, expected, memory_variant, phase)
    fields = expected[0]["memory"]
    if (
        native_rows(source, frames, memory_variant, fields, folder, "original")
        != expected
    ):
        raise AssertionError(case + " original SDK differs")
    project = folder / "program.smbp"
    write_project(p, TEMPLATE, project)
    actual = load_project(project)
    check_machine(actual, frames, expected, memory_variant, "actual XML")
    exported = folder / "program.audit.cpp"
    exported.write_text(to_cpp(actual))
    if (
        native_rows(exported, frames, memory_variant, fields, folder, "exported")
        != expected
    ):
        raise AssertionError(case + " exported SDK differs")
    rebuilt = compile_source(exported)
    check_machine(rebuilt, frames, expected, memory_variant, "recompiled")
    repeated = folder / "recompiled.smbp"
    write_project(rebuilt, TEMPLATE, repeated)
    check_machine(
        load_project(repeated), frames, expected, memory_variant, "recompiled XML"
    )
    (folder / "trace.json").write_text(json.dumps(frames, indent=2) + "\n")
    (folder / "expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    phases = []
    for i, frame in enumerate(frames):
        if i + 1 < len(frames) and frames[i + 1]["phase"] == frame["phase"]:
            continue
        bits = expected[i]["bits"]
        phases.append(
            dict(
                phase=frame["phase"],
                last_frame=i,
                controls=frame["controls"],
                indicators_on=[
                    (f"M{704 + b}" if memory_variant else f"Q0.{b}")
                    for b, v in enumerate(bits)
                    if v
                ],
                word_values=expected[i]["memory"],
            )
        )
    result = dict(
        case=case,
        status="local_checks_passed",
        source=str(source),
        source_sha256=digest(source),
        scans=len(frames),
        rungs=len(actual.rungs),
        instructions=sum(map(len, actual.rungs)),
        project=str(project),
        project_sha256=digest(project),
        repeated_project_sha256=digest(repeated),
        template_sha256=digest(TEMPLATE),
        controls=[f"M{800 + i}" if memory_variant else f"I0.{i}" for i in range(3)],
        phases=phases,
        official_editor="pending",
        official_simulator="pending",
        physical_plc="pending",
        timing_scope="local oracle at100ms frames; manual timer test should wait at least2s for settled states; no physical timing proof",
    )
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"PASS {case}: {len(frames)} scans, {len(actual.rungs)} rungs", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/editor-validation/complex"
    )
    parser.add_argument("--memory-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = [
        run_case(name, memory, args.output)
        for name in ("state_arrays", "timed_counter", "numeric_diagnostics")
        for memory in ([True] if args.memory_only else [False, True])
    ]
    report = dict(
        status="local_checks_passed",
        cases=results,
        candidate_frames=sum(x["scans"] for x in results),
        counting="each candidate trace once; comparison stages not additional frames",
        editor="pending",
        simulator="pending",
        physical_plc="pending",
    )
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
