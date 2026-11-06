#!/usr/bin/env python3
"""Check the three-timer sequence locally; never controls GUI or hardware."""

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
from m200.ladder_lowering import normalize
from m200.model import Program
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from run import TEMPLATE, check_machine, decoded_memory, digest, word_indexes


def trace():
    frames = []

    def add(label, count, start=False, permit=True, stop=False, reset=False):
        frames.extend(
            dict(phase=label, controls=[start, permit, stop, reset], dt_ms=100)
            for _ in range(count)
        )

    add("initial_reset", 3, permit=False, reset=True)
    add("initial_idle", 3, permit=False)
    add("start_without_permissive", 3, start=True, permit=False)
    add("held_start_after_permission", 130, start=True)
    add("release_before_cycle1", 3)
    add("cycle1_complete_while_start_held", 330, start=True)
    add("held_start_does_not_repeat_completed_cycle", 30, start=True)
    add("release_before_cycle2", 3)
    add("cycle2_partial_ton", 40, start=True)
    add("stop_dominates_held_start", 3, start=True, stop=True)
    add("held_after_stop_does_not_restart", 30, start=True)
    add("release_before_cycle3", 3)
    add("cycle3_partial_ton", 40, start=True)
    add("permission_loss_aborts_ton", 3, start=True, permit=False)
    add("held_after_permission_returns", 30, start=True)
    add("release_before_cycle4", 3)
    add("cycle4_inside_tp", 125, start=True)
    add("release_while_tp_active", 2)
    add("fresh_start_rejected_while_active", 2, start=True)
    add("stop_during_tp", 3, start=True, stop=True)
    add("held_after_stop_until_tp_tof_settle", 130, start=True)
    add("release_before_cycle5", 3)
    add("cycle5_partial_ton", 40, start=True)
    add("reset_during_ton", 3, start=True, stop=True, reset=True)
    add("held_after_ton_reset", 130, start=True)
    add("release_before_cycle6", 3)
    add("cycle6_inside_tp", 125, start=True)
    add("reset_during_tp", 3, start=True, reset=True)
    add("release_while_internal_tp_draining", 2)
    add("fresh_start_rejected_while_tp_tof_busy", 2, start=True)
    add("held_after_internal_timers_drain", 130, start=True)
    add("release_before_cycle7", 3)
    add("cycle7_complete_after_fresh_edge", 330, start=True)
    add("release_before_cycle8", 3)
    add("cycle8_inside_tof", 225, start=True)
    add("stop_during_tof", 3, start=True, stop=True)
    add("held_until_tof_drains", 130, start=True)
    add("release_before_cycle9", 3)
    add("cycle9_complete_after_fresh_edge", 330, start=True)
    add("final_held_no_repeat", 30, start=True)
    return frames


def oracle(frames):
    """Independent elapsed-time/event specification, without m200 timer helpers."""
    now = 0
    state = accepted = completed = aborted = rejected = 0
    reason = 0
    previous_start = False
    warm_begin = pulse_begin = tail_begin = None
    pulse_previous_input = tail_previous_input = False
    tail_output = False
    pulse_expired_with_high_input = False
    milestones = [False] * 6  # warm, pulse, tail, complete, abort, rejected
    rows = []
    for frame in frames:
        start, permit, stop, reset = frame["controls"]
        edge, previous_start = start and not previous_start, start
        # A TP pulse expires by elapsed time, independently of its input level.
        pulse_busy_before = pulse_begin is not None and now < pulse_begin + 10000
        tail_busy_before = tail_output and (
            tail_begin is None or now < tail_begin + 10000
        )
        if reset:
            state = accepted = completed = aborted = rejected = 0
            milestones = [False] * 6
            reason = 4
        else:
            if stop or not permit:
                if state in (1, 2, 3):
                    state = 0
                    aborted += 1
                    milestones[4] = True
                    reason = 2 if stop else 3
            if edge:
                if (
                    permit
                    and not stop
                    and state in (0, 4)
                    and not pulse_busy_before
                    and not tail_busy_before
                ):
                    state = 1
                    accepted += 1
                    reason = 0
                else:
                    rejected += 1
                    milestones[5] = True
                    reason = 5

        safe = permit and not stop and not reset
        if state == 1 and safe:
            if warm_begin is None:
                warm_begin = now
            warm_value = min(10, (now - warm_begin) // 1000)
        else:
            warm_begin, warm_value = None, 0
        if state == 1 and warm_value == 10:
            milestones[0] = True
            state = 2

        pulse_input = state == 2 and safe
        if pulse_begin is not None and now >= pulse_begin + 10000:
            pulse_begin = None
            pulse_expired_with_high_input = pulse_previous_input
        if pulse_input and not pulse_previous_input and pulse_begin is None:
            pulse_begin = now
            pulse_expired_with_high_input = False
        pulse_active = pulse_begin is not None
        if pulse_active:
            pulse_value = (now - pulse_begin) // 1000
        else:
            pulse_value = 10 if pulse_expired_with_high_input and pulse_input else 0
        if not pulse_input:
            pulse_expired_with_high_input = False
        pulse_previous_input = pulse_input
        if state == 2:
            if pulse_active:
                milestones[1] = True
            else:
                state = 3

        tail_input = state == 2 and pulse_active and safe
        if tail_input:
            tail_begin, tail_output, tail_value = None, True, 0
        else:
            if tail_previous_input:
                tail_begin = now
            tail_value = (
                min(10, (now - tail_begin) // 1000) if tail_begin is not None else 0
            )
            if tail_begin is not None and now >= tail_begin + 10000:
                tail_output = False
        tail_previous_input = tail_input
        if state == 3 and safe:
            milestones[2] = True
            if not tail_output:
                state = 4
                completed += 1
                milestones[3] = True
                reason = 6

        warm_seen, pulse_seen, tail_seen, done_seen, abort_seen, reject_seen = (
            milestones
        )
        bits = [
            state == 0,
            state == 1 and safe,
            state == 2 and pulse_active and safe,
            state == 3 and tail_output and safe,
            done_seen,
            warm_seen,
            pulse_seen,
            tail_seen,
            abort_seen,
            reject_seen,
            permit,
            stop,
            reset,
            start,
            pulse_active,
            tail_output,
        ]
        rows.append(
            dict(
                bits=bits,
                memory={
                    "MW180": state,
                    "MW181": accepted,
                    "MW182": completed,
                    "MW183": aborted,
                    "MW184": rejected,
                    "MW185": warm_value,
                    "MW186": pulse_value,
                    "MW187": tail_value,
                    "MW188": int(pulse_active or tail_output),
                    "MW189": reason,
                    "MW190": 10,
                    "MW191": 10,
                    "MW192": 10,
                },
            )
        )
        now += frame["dt_ms"]
    return rows


def verify_contract(frames, rows):
    """Hand-computed settled checkpoints guard the independent oracle itself."""
    end = {f["phase"]: row for f, row in zip(frames, rows)}
    checkpoints = {
        # phase: (state, accepted, completed, aborted, rejected, reason)
        "held_start_after_permission": (0, 0, 0, 0, 1, 5),
        "cycle1_complete_while_start_held": (4, 1, 1, 0, 1, 6),
        "held_start_does_not_repeat_completed_cycle": (4, 1, 1, 0, 1, 6),
        "stop_dominates_held_start": (0, 2, 1, 1, 1, 2),
        "permission_loss_aborts_ton": (0, 3, 1, 2, 1, 3),
        "fresh_start_rejected_while_active": (2, 4, 1, 2, 2, 5),
        "held_after_stop_until_tp_tof_settle": (0, 4, 1, 3, 2, 2),
        "held_after_ton_reset": (0, 0, 0, 0, 0, 4),
        "fresh_start_rejected_while_tp_tof_busy": (0, 0, 0, 0, 1, 5),
        "held_after_internal_timers_drain": (0, 0, 0, 0, 1, 5),
        "cycle7_complete_after_fresh_edge": (4, 1, 1, 0, 1, 6),
        "cycle8_inside_tof": (3, 2, 1, 0, 1, 0),
        "stop_during_tof": (0, 2, 1, 1, 1, 2),
        "final_held_no_repeat": (4, 3, 2, 1, 1, 6),
    }
    for phase, expected in checkpoints.items():
        words = end[phase]["memory"]
        got = tuple(words[f"MW{i}"] for i in (180, 181, 182, 183, 184, 189))
        if got != expected:
            raise AssertionError(f"oracle checkpoint {phase}: {got} != {expected}")
    if end["final_held_no_repeat"]["bits"][4:10] != [True] * 6:
        raise AssertionError("final historical milestones must remain latched")


def native_rows(source, frames, memory_variant, fields, folder, tag):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ is required")
    indexes = word_indexes(fields)
    harness, binary = folder / (tag + "_harness.cpp"), folder / (tag + "_harness")
    bit_expr = (
        "plc::detail::memory[704+i]" if memory_variant else "plc::detail::outputs[i]"
    )
    harness.write_text(
        """#include <cstdio>
#define PLC_NATIVE
#include %s
int main(){unsigned dt,v;while(std::scanf("%%u",&dt)==1){
for(int i=0;i<24;++i){if(std::scanf("%%u",&v)!=1)return 2;plc::detail::inputs[i]=v!=0;}
for(int i=0;i<4;++i){if(std::scanf("%%u",&v)!=1)return 3;plc::detail::memory[800+i]=v!=0;}
plc::detail::begin_scan();scan();
for(int i=0;i<16;++i)std::putchar(%s?'1':'0');
%s
std::putchar('\\n');plc::detail::first_scan=false;plc::detail::now_ms+=dt;}}
"""
        % (
            json.dumps(str(source.resolve())),
            bit_expr,
            "".join(
                f'std::printf(" %u",(unsigned)plc::detail::words[{i}]);'
                for i in indexes
            ),
        )
    )
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
    inputs = []
    for frame in frames:
        controls = frame["controls"]
        physical = [False] * 24 if memory_variant else controls + [False] * 20
        memory = controls if memory_variant else [False] * 4
        inputs.append(
            " ".join(str(int(v)) for v in [frame["dt_ms"], *physical, *memory])
        )
    result = subprocess.run(
        [str(binary)],
        input="\n".join(inputs) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(f"native execution: {result.returncode} {result.stderr}")
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


def mutation_checks(source, frames, expected, memory_variant, folder):
    """Prove this trace rejects wrong timer duration, edge and reset priority."""
    original = source.read_text()
    edge, level = (
        ("plc::m_rising(800)", "plc::read_m(800)")
        if memory_variant
        else ("plc::input_rising(0)", "plc::input(0)")
    )
    mutations = {
        # Hide the preset change in diagnostics so elapsed behavior must catch it.
        "short_ton": [
            ("warmup{0, 1000, 10}", "warmup{0, 1000, 9}"),
            ("plc::write_word(190, warmup.preset());", "plc::write_word(190, 10);"),
        ],
        "start_level_instead_of_edge": [(edge, level)],
        "stop_overrides_reset": [("if (reset) {", "if (reset && !stop) {")],
    }
    rejected = {}
    for name, substitutions in mutations.items():
        changed = original
        for before, after in substitutions:
            if changed.count(before) != 1:
                raise AssertionError(f"mutation {name} does not have one exact site")
            changed = changed.replace(before, after)
        path = folder / ("mutation_" + name + ".cpp")
        path.write_text(changed)
        candidate = compile_source(path)
        try:
            check_machine(candidate, frames, expected, memory_variant, name)
        except AssertionError as error:
            rejected[name] = str(error)
        else:
            raise AssertionError(f"trace did not detect mutation {name}")
    return rejected


def run_case(memory_variant, output, frames, expected):
    case = "sequence_timers" + ("_memory" if memory_variant else "")
    source = ROOT / "examples/editor_validation" / (case + ".cpp")
    folder = output / case
    folder.mkdir()
    program = compile_source(source)
    for tag, candidate in [
        ("IL", program),
        ("JSON", Program.from_dict(json.loads(json.dumps(program.as_dict())))),
        ("normalized", normalize(program)),
    ]:
        check_machine(candidate, frames, expected, memory_variant, tag)
    native = native_rows(
        source, frames, memory_variant, expected[0]["memory"], folder, "original"
    )
    if native != expected:
        first = next(i for i, (a, e) in enumerate(zip(native, expected)) if a != e)
        raise AssertionError(
            f"{case} native original frame{first}: {native[first]} != {expected[first]}"
        )
    project = folder / "program.smbp"
    write_project(program, TEMPLATE, project)
    actual = load_project(project)
    check_machine(actual, frames, expected, memory_variant, "actual XML")
    exported = folder / "program.audit.cpp"
    exported.write_text(to_cpp(actual))
    native = native_rows(
        exported, frames, memory_variant, expected[0]["memory"], folder, "exported"
    )
    if native != expected:
        raise AssertionError(f"{case} exported native SDK differs")
    rebuilt = compile_source(exported)
    check_machine(rebuilt, frames, expected, memory_variant, "recompiled")
    repeated = folder / "recompiled.smbp"
    write_project(rebuilt, TEMPLATE, repeated)
    check_machine(
        load_project(repeated), frames, expected, memory_variant, "recompiled XML"
    )
    if memory_variant:
        instructions = [line for rung in actual.rungs for line in rung]
        if any("%I0." in line or "%Q0." in line for line in instructions):
            raise AssertionError("memory variant contains a physical I/O instruction")
    mutations_rejected = mutation_checks(
        source, frames, expected, memory_variant, folder
    )
    for name, data in [("trace.json", frames), ("expected.json", expected)]:
        (folder / name).write_text(json.dumps(data, indent=2) + "\n")
    phases = []
    for i, frame in enumerate(frames):
        if i + 1 < len(frames) and frames[i + 1]["phase"] == frame["phase"]:
            continue
        phases.append(
            dict(
                phase=frame["phase"],
                last_frame=i,
                controls=frame["controls"],
                indicators_on=[
                    f"M{704 + j}" if memory_variant else f"Q0.{j}"
                    for j, on in enumerate(expected[i]["bits"])
                    if on
                ],
                word_values=expected[i]["memory"],
            )
        )
    artifacts = [
        source,
        project,
        exported,
        repeated,
        folder / "trace.json",
        folder / "expected.json",
    ]
    result = dict(
        case=case,
        status="local_checks_passed",
        source=str(source.relative_to(ROOT)),
        project=str(project.relative_to(ROOT)),
        scans=len(frames),
        rungs=len(actual.rungs),
        instructions=sum(map(len, actual.rungs)),
        template=str(TEMPLATE.relative_to(ROOT)),
        template_sha256=digest(TEMPLATE),
        artifact_sha256={
            str(path.relative_to(ROOT)): digest(path) for path in artifacts
        },
        commands=[f"M{800 + i}" if memory_variant else f"I0.{i}" for i in range(4)],
        phases=phases,
        mutations_rejected=mutations_rejected,
        official_editor="pending",
        official_simulator="pending",
        physical_plc="pending",
    )
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"PASS {case}: {len(frames)} scans, {len(actual.rungs)} rungs", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/editor-validation/sequence-timers"
    )
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    frames = trace()
    expected = oracle(frames)
    verify_contract(frames, expected)
    if args.oracle_only:
        print(
            f"PASS independent oracle: {len(frames)} frames, 14 hand-computed checkpoints"
        )
        return
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("output must be under the repository for portable artifact paths")
    output.mkdir(parents=True, exist_ok=False)
    results = [run_case(memory, output, frames, expected) for memory in (False, True)]
    package = [
        ROOT / "tests/editor_validation/sequence_timers.py",
        ROOT / "tests/editor_validation/run.py",
        ROOT / "examples/editor_validation/sequence_timers.cpp",
        ROOT / "examples/editor_validation/sequence_timers_memory.cpp",
        TEMPLATE,
    ]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in package}
    report = dict(
        format="m200-sequence-timers-local-validation-v1",
        target="TM200CE40T",
        status="local_checks_passed",
        runner="tests/editor_validation/sequence_timers.py",
        cases=results,
        distinct_candidate_frames=len(frames) * 2,
        counting="Each (candidate, trace-position) once; comparison stages/repetitions are not additional frames.",
        comparison_stages=[
            "IL VM",
            "JSON VM",
            "normalized VM",
            "native SDK",
            "actual XML VM",
            "reconstructed native SDK",
            "recompiled VM",
            "recompiled XML VM",
        ],
        package_files_sha256=hashes,
        package_sha256=hashlib.sha256(
            json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        oracle_scope="Independent elapsed-time/event specification and 14 hand-computed settled checkpoints. Native SDK/VM and compiler conversions still share intended semantics and modules; this agreement is not independent Schneider proof.",
        memory_control_scope="M800..M803 injected before begin_scan; models external writes between scans. Actual official animation-table scheduling remains unverified.",
        timer_scope="Three non-retentive static native timers: TON0, TP1, TOF2 at 1second/preset10. Local 100ms frames are not simulator or hardware timing evidence. TP is not cancelled by reset/abort; app outputs are masked and busy restarts are rejected until timers drain.",
        official_editor="pending",
        official_simulator="pending",
        physical_plc="pending",
    )
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
