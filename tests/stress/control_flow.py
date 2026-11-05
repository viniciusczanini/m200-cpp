#!/usr/bin/env python3
"""Seeded loop composition checks against closed-form independent expectations."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from m200.frontend import compile_source
from m200.il import Machine
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SEED = 20020261108


def main():
    rng = random.Random(SEED)
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-flow-stress-") as directory:
        work = Path(directory)
        for case in range(12):
            mode, skip, stop = case % 3, rng.randrange(16), rng.randrange(1, 18)
            setup = "plc::i16 n=0;plc::i16 i=0;plc::i16 total=0;"
            for bit in range(4):
                setup += f"if(plc::input({bit})){{n=plc::add_i16(n,{1 << bit});}}"
            body = f"if(i=={stop}){{break;}}if(i=={skip}){{continue;}}total=plc::add_i16(total,i);"
            increment = "i=plc::add_i16(i,1);"
            if mode == 0:
                loop = "for(;i<n;" + increment[:-1] + "){" + body + "}"
            elif mode == 1:
                loop = "while(i<n){" + increment + body + "}"
            else:
                loop = "do{" + increment + body + "}while(i<n);"
            observe = "".join(
                f"plc::output({bit},plc::and_i16(total,{1 << bit})!=0);"
                for bit in range(7)
            )
            source = work / f"case_{case}.cpp"
            source.write_text(
                "#include <plc.hpp>\nvoid scan(){" + setup + loop + observe + "}\n"
            )
            program = compile_source(source)
            frames, expected = [], []
            for n in list(range(16)) * 16:
                frames.append(
                    {"inputs": {bit: bool(n & (1 << bit)) for bit in range(4)}}
                )
                if mode == 0:
                    end = min(n, stop)
                    total = end * (end - 1) // 2
                    if skip < end:
                        total -= skip
                else:
                    end = min(n if mode == 1 else max(1, n), stop - 1)
                    total = end * (end + 1) // 2
                    if 1 <= skip <= end:
                        total -= skip
                expected.append(
                    [bool(total & (1 << bit)) for bit in range(7)] + [False] * 9
                )
            machine = Machine(program)
            got = [machine.step(f["inputs"]) for f in frames]
            if got != expected or run_native(source, frames) != expected:
                raise AssertionError(
                    f"case {case}: original C++/IL differs from formula"
                )
            reverse = work / f"reverse_{case}.cpp"
            reverse.write_text(to_cpp(program))
            rebuilt = Machine(compile_source(reverse))
            if (
                run_native(reverse, frames) != expected
                or [rebuilt.step(f["inputs"]) for f in frames] != expected
            ):
                raise AssertionError(
                    f"case {case}: reverse C++/IL differs from formula"
                )
            destination = work / f"case_{case}.smbp"
            write_project(program, ROOT / "tests/fixtures/synthetic.smbp", destination)
            restored = Machine(load_project(destination))
            if [restored.step(f["inputs"]) for f in frames] != expected:
                raise AssertionError(f"case {case}: XML changed execution")
            results.append(
                dict(
                    case=case,
                    loop=("for", "while", "do/while")[mode],
                    skip=skip,
                    stop=stop,
                    scans=len(frames),
                    status="pass",
                )
            )
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
        official_editor="pending",
        physical_plc="pending",
    )
    (ROOT / "docs/validation/CONTROL-FLOW-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "PASS: 12 loop compositions / 3072 scans / original and reverse C++, IL and synthetic XML"
    )


if __name__ == "__main__":
    main()
