"""Compact S5-clock Revoada: sampled-clock contract, not absolute-time parity."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import compile_source  # noqa: E402
from m200.il import Machine  # noqa: E402
from m200.native import run_native  # noqa: E402
from m200.project import load_project, write_project  # noqa: E402
from m200.bits import memory_bits_used  # noqa: E402
from m200.numeric import memory_words_used  # noqa: E402
from check_movement import build_oracle, oracle, output_mask  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output/christmas/clock-check"
    )
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "examples/christmas/revoada20_clock_10.cpp"
    assert source.exists(), "Missing real compact clock/algorithm port"
    vector = next(
        v
        for v in json.loads(
            Path(__file__).with_name("oracle_vectors.json").read_text()
        )["cases"]
        if (v["effect"], v["outputs"]) == (20, 10)
    )
    masks = [mask for mask, duration in vector["frames"] for _ in range(duration)]
    assert (
        len(masks) == 20 and masks[0] == masks[1] == 1 and masks[10] == masks[11] == 512
    )
    if args.source_root:
        binary, _ = build_oracle(args.source_root, args.output)
        assert (
            oracle(binary, 20, 10, [600 * i for i in range(20)])["expected_masks"]
            == masks
        )
    program = compile_source(source)
    target = args.output / "program.smbp"
    write_project(
        program, ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp", target
    )
    imported = load_project(target)
    assert not imported.timers
    assert sum(line == "LD %S5" for rung in imported.rungs for line in rung) == 1, (
        "S5 must be captured once per scan"
    )
    phases = []
    for start, first in ((0, 550), (49, 550), (50, 550), (75, 650)):
        horizon = first + 600 * 40
        times = sorted(set(range(0, horizon + 1, 10)) | {start, start + 1, 49, 50, 75})
        frames = [
            {
                "inputs": {0: t == start},
                "dt_ms": times[i + 1] - t if i + 1 < len(times) else 0,
            }
            for i, t in enumerate(times)
        ]
        expected_phase = [
            0 if t < first else (1 + (t - first) // 600) % 20 for t in times
        ]
        expected = [0 if t < start else masks[u] for t, u in zip(times, expected_phase)]
        for candidate in (program, imported):
            machine = Machine(candidate)
            for i, (frame, mask, phase) in enumerate(
                zip(frames, expected, expected_phase)
            ):
                got = output_mask(machine.step(frame["inputs"], frame["dt_ms"]))
                assert (got, machine.words[180]) == (mask, phase), (
                    start,
                    i,
                    times[i],
                    got,
                    mask,
                    machine.words[180],
                    phase,
                )
                if got:
                    assert got & (got - 1) == 0 and got < 1024
        assert [output_mask(v) for v in run_native(source, frames)] == expected
        phases.append(
            {
                "START_ms": start,
                "first_quantum_ms": first - start,
                "later_quantum_ms": 600,
                "positions": len(times),
            }
        )
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
    wanted = [0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1]
    control_frames = [{"inputs": dict(enumerate(v)), "dt_ms": 10} for v in controls]
    for candidate in (program, imported):
        machine = Machine(candidate)
        assert [
            output_mask(machine.step(f["inputs"], 10)) for f in control_frames
        ] == wanted
    assert [output_mask(v) for v in run_native(source, control_frames)] == wanted
    # With no monotonic clock, missed complete periods are intentionally not inferred.
    machine = Machine(imported)
    assert output_mask(machine.step({0: True}, 10000)) == 1
    assert output_mask(machine.step({}, 0)) == 1 and machine.words[180] == 0
    m, w = memory_bits_used(imported), memory_words_used(imported)
    result = {
        "status": "PASS sampled-clock contract",
        "source": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "SMBP": str(target.relative_to(ROOT)),
        "SMBP_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "start_phase_cases": phases,
        "control_positions": len(controls),
        "onehot_order_double_endpoints_and_two_loops": True,
        "timers": len(imported.timers),
        "rungs": len(imported.rungs),
        "IL": sum(map(len, imported.rungs)),
        "M_unique": len(m),
        "M_span": max(m, default=-1) + 1,
        "MW_unique": len(w),
        "MW_span": max(w, default=-1) + 1,
        "tradeoff": "First quantum500..600ms depends on START/clock phase; later600ms only when all rising/falling levels sampled. No missed-edge/saturation/monotonic-time guarantee or absolute START-phase parity.",
    }
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
