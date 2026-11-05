#!/usr/bin/env python3
"""Per-scan independent temporal oracles over every I0/M edge address."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bit_objects import verify, original
from m200.frontend import compile_source
from m200.model import Program

SEED = 20020261116


def trace(rng, count):
    values = (
        [0, (1 << 24) - 1]
        + [1 << i for i in range(24)]
        + [((1 << 24) - 1) ^ (1 << i) for i in range(24)]
    )
    values += [rng.randrange(1 << 24) for _ in range(count - len(values))]
    return values, [
        {"inputs": {i: bool(v & (1 << i)) for i in range(24)}} for v in values
    ]


def main():
    rng = random.Random(SEED)
    values, frames = trace(rng, 256)
    long_values, long_frames = trace(rng, 512)
    results = []
    memory_addresses = set()
    input_addresses = set()
    with tempfile.TemporaryDirectory(prefix="m200-native-edges-") as directory:
        work = Path(directory)
        for base in range(0, 1024, 16):
            name = f"memory_{base}"
            source = work / (name + ".cpp")
            source.write_text(
                "#include <plc.hpp>\nvoid scan(){"
                + "".join(
                    f"bool r{q}=plc::m_rising({base + q});bool f{q}=plc::m_falling({base + q});"
                    f"plc::write_m({base + q},plc::input({(base + q) % 23}));"
                    f"if(plc::input(23)){{plc::output({q},f{q});}}else{{plc::output({q},r{q});}}"
                    for q in range(16)
                )
                + "}"
            )
            previous = older = 0
            expected = []
            for value in values:
                rising = previous & ~older
                falling = older & ~previous
                selected = falling if value & (1 << 23) else rising
                expected.append(
                    [bool(selected & (1 << ((base + q) % 23))) for q in range(16)]
                )
                older, previous = previous, value
            verify(compile_source(source), frames, expected, work, name, source)
            memory_addresses.update(range(base, base + 16))
            results.append(dict(case=name, scans=len(frames), status="pass"))
            print(f"PASS: {name} / {len(frames)} scans", flush=True)
        for base in range(0, 24, 8):
            name = f"input_{base}"
            source = work / (name + ".cpp")
            source.write_text(
                "#include <plc.hpp>\nvoid scan(){"
                + "".join(
                    f"plc::output({2 * q},plc::input_rising({base + q}));plc::output({2 * q + 1},plc::input_falling({base + q}));"
                    for q in range(8)
                )
                + "}"
            )
            previous = 0
            expected = []
            for value in values:
                row = []
                for index in range(base, base + 8):
                    row.extend(
                        [
                            bool(value & ~previous & (1 << index)),
                            bool(previous & ~value & (1 << index)),
                        ]
                    )
                expected.append(row)
                previous = value
            verify(compile_source(source), frames, expected, work, name, source)
            input_addresses.update(range(base, base + 8))
            results.append(dict(case=name, scans=len(frames), status="pass"))
        for a in [0, 7, 15, 21]:
            b, c = (a + 1) % 24, (a + 2) % 24
            name = f"operators_{a}"
            p = Program(
                [
                    [f"LD %I0.{a}", "ST %M711"],
                    [
                        f"LDR %I0.{a}",
                        "MPS",
                        "ANDR %M711",
                        "ST %Q0.0",
                        "MPP",
                        f"ORF %I0.{b}",
                        "ST %Q0.1",
                    ],
                    [f"LD %I0.{c}", "XORR %M711", "ST %Q0.2"],
                    [
                        "LDF %M711",
                        "MPS",
                        "N",
                        "ST %Q0.3",
                        "MPP",
                        f"XORF %I0.{b}",
                        "ST %Q0.4",
                    ],
                    [f"LD %I0.{c}", "ANDR %M711", "ST %Q0.5"],
                    [f"LD %I0.{c}", "ORF %M711", "ST %Q0.6"],
                    [f"LDF %I0.{a}", "ST %Q0.7"],
                    [
                        f"LDR %I0.{a}",
                        "AND( %M711",
                        f"XORF %I0.{b}",
                        f"ORR %I0.{c}",
                        ")",
                        "ST %Q0.8",
                    ],
                    [f"LD %I0.{c}", "ANDF %M711", "ST %Q0.9"],
                ]
            )
            previous = older = 0
            expected = []
            for value in long_values:
                current = [bool(value & (1 << i)) for i in (a, b, c)]
                rise = [bool(value & ~previous & (1 << i)) for i in (a, b, c)]
                fall = [bool(previous & ~value & (1 << i)) for i in (a, b, c)]
                mr = bool(previous & ~older & (1 << a))
                mf = bool(older & ~previous & (1 << a))
                expected.append(
                    [
                        rise[0] and mr,
                        rise[0] or fall[1],
                        current[2] != mr,
                        not mf,
                        mf != fall[1],
                        current[2] and mr,
                        current[2] or mf,
                        fall[0],
                        rise[0] and ((current[0] != fall[1]) or rise[2]),
                        current[2] and mf,
                    ]
                    + [False] * 6
                )
                older, previous = previous, value
            verify(p, long_frames, expected, work, name)
            results.append(dict(case=name, scans=len(long_frames), status="pass"))
        entry, lines = original(
            ROOT / "tests/public/control-flow-manifest.json",
            "flow-original-loop.smbp",
            "public-projects",
            2,
        )
        p = Program(
            [
                ["LD 1", "[%MW0:=%I0.0:8]", "[%MW10:=-1]", "[%MW1:=7]"],
                ["LD %I0.0", "ST %M0"],
                lines,
                ["LD [%MW10=%MW0]", "ST %Q0.0"],
                ["LD [%MW1=0]", "ST %Q0.1"],
                ["LD %M0", "ST %Q0.2"],
            ]
        )
        previous = older = False
        expected = []
        for value in long_values:
            r = previous and not older
            expected.append([r, r, bool(value & 1)] + [False] * 13)
            older, previous = previous, bool(value & 1)
        verify(p, long_frames, expected, work, "public_memory_edge")
        results.append(
            dict(
                case="public_memory_edge",
                scans=len(long_frames),
                status="pass",
                original_sha256=entry["sha256"],
                rung=2,
                scope="complete isolated original rung; explicit M/word adapters; no CPU rewrite",
            )
        )
        entry, lines = original(
            ROOT / "tests/public/control-flow-manifest.json",
            "flow-original-jump.smbp",
            "public-projects",
            1,
        )
        if lines[1:3] != ["LDR %I0.2", "ORF %I0.2"]:
            raise AssertionError("original edge sequence changed")
        p = Program([lines[1:3] + ["ST %Q0.0"]])
        previous = False
        expected = []
        for value in long_values:
            current = bool(value & 4)
            expected.append([current != previous] + [False] * 15)
            previous = current
        verify(p, long_frames, expected, work, "public_input_edges")
        results.append(
            dict(
                case="public_input_edges",
                scans=len(long_frames),
                status="pass",
                original_sha256=entry["sha256"],
                rung=1,
                scope="exact contiguous [1:3] LDR/ORF slice with observation coil; original IW assignment excluded explicitly",
            )
        )
        entry, lines = original(
            ROOT / "docs/capabilities/INDEXED-SOURCES.json", "T", "indexed-sources", 6
        )
        p = Program(
            [
                ["LD 1", "S %M5", "[%MD10:=0]", "[%MD12:=0]", "[%MD14:=0]"],
                [
                    "LD 0",
                    "ST %M6",
                    "ST %Q0.3",
                    "ST %Q0.4",
                    "ST %Q0.7",
                    "ST %Q0.10",
                    "ST %Q0.11",
                ],
                lines,
            ]
        )
        previous = held = False
        expected = []
        for value in long_values:
            current = bool(value & 1)
            held = held or (current and not previous)
            expected.append([held] + [False] * 15)
            previous = current
        verify(p, long_frames, expected, work, "public_edge_groups")
        results.append(
            dict(
                case="public_edge_groups",
                scans=len(long_frames),
                status="pass",
                original_sha256=entry["sha256"],
                rung=6,
                scope="complete isolated original rung with explicit M/Q/MD harness; original parallel graphic not claimed verified",
            )
        )
    assert len(memory_addresses) == 1024 and len(input_addresses) == 24
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "tests/public/control-flow-manifest.json",
        ROOT / "docs/capabilities/INDEXED-SOURCES.json",
    ]
    report = dict(
        seed=SEED,
        target="TM200CE40T",
        cases=results,
        scans=sum(r["scans"] for r in results),
        memory_edge_addresses_tested=len(memory_addresses),
        input_edge_addresses_tested=len(input_addresses),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        whole_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
        input_phase_and_startup="local-model-pending-external-confirmation",
    )
    (ROOT / "docs/validation/NATIVE-EDGE-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans / all 24 I0 and 1024 M addresses; temporal oracle, C++, IL, JSON, normalization, reverse and XML"
    )


if __name__ == "__main__":
    main()
