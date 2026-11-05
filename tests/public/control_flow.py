#!/usr/bin/env python3
"""Execute byte-verified original jumps/loop rungs; no CPU substitution or network."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from fetch import DEFAULT_CORPUS, verified_bytes
from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import load_project
from m200.reverse import to_cpp

SEED = 20020261107


def lines(rung):
    return [
        " ".join(n.text.split())
        for n in rung.findall("InstructionLines/InstructionLineEntity/InstructionLine")
    ]


def verify(program, frames, expected, work, name):
    vm = Machine(program)
    got = [vm.step(f["inputs"]) for f in frames]
    if got != expected:
        raise AssertionError(name + ": original IL differs from independent oracle")
    source = work / (name + ".cpp")
    source.write_text(to_cpp(program))
    if run_native(source, frames) != expected:
        raise AssertionError(name + ": reverse native C++ differs from oracle")
    rebuilt = Machine(compile_source(source))
    if [rebuilt.step(f["inputs"]) for f in frames] != expected:
        raise AssertionError(name + ": recompiled IL differs from oracle")
    return vm


def main():
    manifest = json.loads((HERE / "control-flow-manifest.json").read_text())
    originals = []
    for item in manifest["sources"]:
        path = DEFAULT_CORPUS / item["file"]
        data = verified_bytes(path, item)
        # Demonstrate that no foreign project is accepted as the target model.
        try:
            load_project(path)
        except CompileError as error:
            if "source CPU " + item["cpu"] not in str(error):
                raise
        else:
            raise AssertionError("foreign CPU was accepted")
        root = ET.fromstring(data)
        originals.append(
            root.findall(
                "SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity"
            )
        )
    rng = random.Random(SEED)
    with tempfile.TemporaryDirectory(prefix="m200-public-flow-") as temporary:
        work = Path(temporary)
        # Explicit input and observation adapters surround the original rung.
        # Every instruction of the original loop is retained, including INC.
        prefix = [["LD %I0.0", "ST %M0"], ["LD 1", "[%MW10:=0]"], ["LD 1", "[%MW1:=0]"]]
        for bit in range(15):
            prefix.append([f"LD %I0.{bit + 1}", f"[%MW10:=%MW10+{1 << bit}]"])
        observations = []
        for bit in range(4):
            observations.extend(
                [
                    ["LD 1", f"[%MW2:=%MW1 AND {1 << bit}]"],
                    ["LD [%MW2<>0]", f"ST %Q0.{bit}"],
                ]
            )
        observations.append(["LD [%MW10=0]", "ST %Q0.4"])
        loop = Program(prefix + [lines(originals[0][3])] + observations)
        frames, expected = [], []
        values = [0, 1, 2, 3, 255, 256, 16384, 32767] + [
            rng.randrange(32768) for _ in range(1016)
        ]
        for seed in values:
            enabled = bool(rng.getrandbits(1))
            frames.append(
                {
                    "inputs": {
                        0: enabled,
                        **{bit + 1: bool(seed & (1 << bit)) for bit in range(15)},
                    }
                }
            )
            count = seed.bit_length() if enabled else 0
            row = [bool(count & (1 << bit)) for bit in range(4)]
            row += [enabled or seed == 0] + [False] * 11
            expected.append(row)
        verify(loop, frames, expected, work, "original_loop")
        # Original jump and its original target, with a visible adapter between.
        jump = Program(
            [
                ["LD 0", "ST %Q0.6"],
                lines(originals[1][0]),
                ["LD 1", "ST %Q0.6"],
                lines(originals[1][5]),
            ]
        )
        frames = [{"inputs": {4: bool(rng.getrandbits(1))}} for _ in range(1024)]
        expected = []
        for f in frames:
            row = [False] * 16
            row[4], row[5], row[6] = f["inputs"][4], True, not f["inputs"][4]
            expected.append(row)
        verify(jump, frames, expected, work, "original_jump")
    report = {
        "target": "TM200CE40T",
        "seed": SEED,
        "sources": manifest["sources"],
        "cases": 2,
        "scans": 2048,
        "originals_modified": False,
        "checks": [
            "independent oracle",
            "original isolated IL",
            "reverse native C++",
            "recompiled IL",
        ],
        "official_editor": "pending",
        "physical_plc": "pending",
        "scope": "Foreign CPU projects are refused whole; only original rungs execute with explicit adapters. Original parallel Ladder is not declared supported.",
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "m200").glob("*.py"))
            + [
                ROOT / "sdk/plc.hpp",
                Path(__file__),
                HERE / "fetch.py",
                HERE / "control-flow-manifest.json",
            ]
        },
    }
    destination = ROOT / "docs/validation/PUBLIC-CONTROL-FLOW-RESULTS.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        "PASS: 2 authentic isolated flow cases / 2048 scans; official editor and PLC pending"
    )


if __name__ == "__main__":
    main()
