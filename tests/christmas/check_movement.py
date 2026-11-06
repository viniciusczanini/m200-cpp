"""Portable local movement checks; optional direct original-Natal native oracle."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import compile_source  # noqa: E402
from m200.il import Machine  # noqa: E402
from m200.native import run_native  # noqa: E402
from m200.project import load_project, write_project  # noqa: E402

NAMES = {
    19: "alternado19",
    20: "revoada20_compact",
    21: "marcha21",
    22: "mare22",
    23: "estrela23",
}
VECTORS = Path(__file__).with_name("oracle_vectors.json")
HEADERS = ("single_box_movement.hpp", "single_box_extras.hpp")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_oracle(source_root, output):
    include = source_root / "packages/show-core/include"
    pins = {
        "packages/show-core/include/natal/" + h: sha(include / "natal" / h)
        for h in HEADERS
    }
    binary = output / "original-oracle"
    subprocess.run(
        [
            shutil.which("clang++"),
            "-std=c++17",
            "-O2",
            "-I",
            str(include),
            str(Path(__file__).with_name("original_oracle.cpp")),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return binary, pins


def oracle(binary, effect, outputs, times):
    rows = subprocess.run(
        [str(binary), str(effect), str(outputs)],
        input="\n".join(map(str, times)) + "\n",
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    period, count, units = map(int, rows[0].split())
    frames = [list(map(int, row.split())) for row in rows[1 : count + 1]]
    masks = list(map(int, rows[count + 1 :]))
    assert sum(duration for _, duration in frames) == units and len(masks) == len(times)
    return {
        "effect": effect,
        "outputs": outputs,
        "period_ms": period,
        "units": units,
        "frames": frames,
        "times_ms": times,
        "expected_masks": masks,
    }


def timeline(sequence):
    period, units = sequence["period_ms"], sequence["units"]
    unit = period // units
    assert unit * units == period
    boundaries, elapsed = [0], 0
    for _, duration in sequence["frames"]:
        elapsed += duration * unit
        boundaries.append(elapsed)
    times = {0, 1}
    for cycle in range(3):
        for edge in boundaries:
            for offset in (-1, 0, 1):
                if cycle * period + edge + offset >= 0:
                    times.add(cycle * period + edge + offset)
    horizon = 3 * period + 1
    times.update(
        range(0, horizon, 1337)
    )  # Uneven service tests timer-window overshoot.
    return sorted(t for t in times if t <= horizon)


def regenerate(binary, pins):
    cases = []
    for effect in range(19, 24):
        for outputs in (10, 11):
            sequence = oracle(binary, effect, outputs, [])
            cases.append(oracle(binary, effect, outputs, timeline(sequence)))
    data = {
        "format": 1,
        "origin": "Directly compiled original Natal renderer; default requested period0",
        "original_header_sha256": pins,
        "oracle_source_sha256": sha(Path(__file__).with_name("original_oracle.cpp")),
        "cases": cases,
    }
    VECTORS.write_text(json.dumps(data, indent=2) + "\n")


def output_mask(values):
    return sum(1 << bit for bit, value in enumerate(values) if value)


def evaluate(program, frames, expected):
    machine = Machine(program)
    for index, (frame, want) in enumerate(zip(frames, expected)):
        got = output_mask(machine.step(frame["inputs"], frame["dt_ms"]))
        assert got == want, (index, machine.now, got, want)
    return machine


def check_case(vector, output, port=None):
    effect, count = vector["effect"], vector["outputs"]
    source = (
        port.resolve()
        if port
        else ROOT / "examples/christmas" / f"{NAMES[effect]}_{count}.cpp"
    )
    assert source.exists(), f"Missing requested PLC movement port: {source.name}"
    times, expected = vector["times_ms"], vector["expected_masks"]
    assert times == timeline(vector)
    frames = [
        {
            "inputs": {0: index == 0},
            "dt_ms": times[index + 1] - time if index + 1 < len(times) else 0,
        }
        for index, time in enumerate(times)
    ]
    program = compile_source(source)
    evaluate(program, frames, expected)
    target = output / (source.stem + ".smbp")
    write_project(
        program, ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp", target
    )
    imported = load_project(target)
    evaluate(imported, frames, expected)
    assert [output_mask(row) for row in run_native(source, frames)] == expected
    controls = [
        (0, 0, 0),
        (1, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (1, 0, 0),
        (0, 0, 0),
        (1, 0, 0),
        (1, 0, 1),
        (1, 0, 0),
        (0, 0, 0),
        (1, 1, 0),
        (1, 0, 0),
        (0, 0, 0),
        (1, 0, 0),
    ]
    first = vector["frames"][0][0]
    wanted = [0, first, first, 0, 0, 0, first, 0, 0, 0, 0, 0, 0, first]
    control_frames = [{"inputs": dict(enumerate(row)), "dt_ms": 10} for row in controls]
    for candidate in (program, imported):
        evaluate(candidate, control_frames, wanted)
    assert [output_mask(row) for row in run_native(source, control_frames)] == wanted
    fault_frames = [
        {"inputs": {0: 1}, "dt_ms": 10000},
        {"inputs": {}, "dt_ms": 1},
        {"inputs": {0: 1}, "dt_ms": 1},
        {"inputs": {0: 1, 2: 1}, "dt_ms": 1},
        {"inputs": {0: 1}, "dt_ms": 1},
        {"inputs": {}, "dt_ms": 1},
        {"inputs": {0: 1}, "dt_ms": 1},
    ]
    for candidate in (program, imported):
        evaluate(candidate, fault_frames, [first, 0, 0, 0, 0, 0, first])
    assert [output_mask(row) for row in run_native(source, fault_frames)] == [
        first,
        0,
        0,
        0,
        0,
        0,
        first,
    ]
    return {
        "effect": effect,
        "outputs": count,
        "period_ms": vector["period_ms"],
        "units": vector["units"],
        "unit_ms": vector["period_ms"] // vector["units"],
        "original_native_boundary_positions": len(times),
        "control_positions": len(controls),
        "saturation_positions": len(fault_frames),
        "source": str(source.relative_to(ROOT)),
        "source_sha256": sha(source),
        "SMBP": str(target.relative_to(ROOT)),
        "SMBP_sha256": sha(target),
        "rungs": len(imported.rungs),
        "IL": sum(map(len, imported.rungs)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        "--natal-root",
        dest="source_root",
        type=Path,
        help="Optional original Natal checkout for direct native recheck/regeneration",
    )
    parser.add_argument("--regenerate-vectors", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--port",
        type=Path,
        help="Optional alternate CPP for the selected effect/output vector",
    )
    parser.add_argument("--effect", type=int, choices=range(19, 24), default=20)
    parser.add_argument("--outputs", type=int, choices=(10, 11), default=10)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/christmas/local-check"
    )
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    binary, pins = (
        build_oracle(args.source_root, args.output)
        if args.source_root
        else (None, None)
    )
    if args.regenerate_vectors:
        assert binary, "--regenerate-vectors requires --source-root"
        regenerate(binary, pins)
    vectors = json.loads(VECTORS.read_text())
    chosen = [
        v
        for v in vectors["cases"]
        if args.all or (v["effect"], v["outputs"]) == (args.effect, args.outputs)
    ]
    if binary:
        assert pins == vectors["original_header_sha256"], (
            "Original headers differ from frozen oracle"
        )
        for vector in chosen:
            assert (
                oracle(binary, vector["effect"], vector["outputs"], vector["times_ms"])
                == vector
            )
    assert not (args.all and args.port), "--port selects one effect/output variant"
    results = [check_case(vector, args.output, args.port) for vector in chosen]
    if pins:
        assert all(
            sha(args.source_root / path) == value for path, value in pins.items()
        )
    result = {
        "status": "PASS",
        "oracle_vectors_sha256": sha(VECTORS),
        "original_native_checked_directly": bool(binary),
        "original_header_sha256": vectors["original_header_sha256"],
        "cases": results,
        "limits": "Local original-oracle/SDK/VM/XML proof; official GUI, native simulator and physical PLC are separate.",
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
