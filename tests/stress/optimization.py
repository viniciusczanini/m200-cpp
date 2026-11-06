"""Check frozen generic codegen budgets against independent literal traces."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.cli import report  # noqa: E402
from m200.frontend import compile_source  # noqa: E402
from m200.il import Machine  # noqa: E402
from m200.native import run_native  # noqa: E402
from m200.project import load_project, write_project  # noqa: E402
from m200.reverse import to_cpp  # noqa: E402


def mask(outputs):
    return sum(1 << i for i, value in enumerate(outputs) if value)


def check(cases_file, output):
    cases = json.loads(cases_file.read_text())["cases"]
    results = []
    for case in cases:
        source = cases_file.parent / case["source"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == case["source_sha256"]
        folder = output / case["name"]
        folder.mkdir(parents=True, exist_ok=True)
        program = compile_source(source)
        cost = {key: report(program)["resources"][key] for key in case["max_cost"]}
        for key, maximum in case["max_cost"].items():
            assert cost[key] <= maximum, (case["name"], key, cost[key], maximum)
        target = folder / "program.smbp"
        write_project(program, ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp", target)
        imported = load_project(target)
        recovered = folder / "recovered.cpp"
        recovered.write_text(to_cpp(imported))
        rebuilt = compile_source(recovered)
        for stage, candidate in (("IR", program), ("SMBP", imported), ("reverse", rebuilt)):
            machine = Machine(candidate)
            for index, frame in enumerate(case["frames"]):
                got = mask(machine.step(frame["inputs"], frame["dt_ms"]))
                assert got == frame["expected_mask"], (case["name"], stage, index, got)
                for address, expected in frame["expected_words_i16"].items():
                    word = machine.words[int(address)] & 65535
                    actual = word - 65536 if word >= 32768 else word
                    assert actual == expected, (case["name"], stage, index, address, actual)
        frames = [{"inputs": f["inputs"], "dt_ms": f["dt_ms"]} for f in case["frames"]]
        expected = [f["expected_mask"] for f in case["frames"]]
        for candidate in (source, recovered):
            assert [mask(row) for row in run_native(candidate, frames)] == expected, case["name"]
        results.append({"name": case["name"], "cost": cost, "positions": len(frames)})
    return {"status": "PASS", "cases": results, "distinct_positions": sum(r["positions"] for r in results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/optimization/cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "output/optimization")
    args = parser.parse_args()
    result = check(args.cases.resolve(), args.output.resolve())
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
