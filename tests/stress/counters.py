#!/usr/bin/env python3
"""Native %C paths against a separate oracle of the explicitly provisional policy."""

# ruff: noqa: E402
import argparse
import hashlib
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bit_objects import original
from expression_edges import verify
from m200.counter_xml import read_configs
from m200.frontend import compile_source
from m200.model import Program

SEED = 20020261118


def oracle(preset):
    state = {
        "v": 0,
        "p": preset,
        "e": False,
        "d": False,
        "f": False,
        "r": False,
        "s": False,
        "u": False,
        "c": False,
    }

    def command(pin, value):
        value = bool(value)
        prior = state[pin]
        state[pin] = value
        event = int(value and not prior)
        if state["r"]:
            state.update(v=0, e=False, d=False, f=False)
        elif state["s"]:
            state.update(v=state["p"], d=True)
        elif pin in ("u", "c") and value:
            direction = {"u": 1, "c": -1}[pin]
            state["v"] = (state["v"] + direction * event) % 10000
            if event:
                state[{"u": "f", "c": "e"}[pin]] = (
                    state["v"] == {"u": 0, "c": 9999}[pin]
                )
            state["d"] = state["v"] == state["p"]

    return state, command


def view(value, left, right):
    return [bool(value & (1 << i)) for i in range(14)] + [bool(left), bool(right)]


def generated(index, preset, values):
    source = f"""#include <plc.hpp>
plc::Counter c{{{index},{preset}}};
void scan(){{
 c.reset(plc::input(0));c.set(plc::input(1));
 if(plc::input(2)){{c.count_up(plc::input(3));}}
 c.count_down(plc::input(4));
 if(plc::input(6)){{if(plc::input(7)){{c.set_preset(9999);}}else{{c.set_preset({preset});}}}}
 if(plc::input(8)){{plc::i16 i=0;while(i<4){{bool v=plc::input(9);
 if(i==1){{v=plc::input(10);}}if(i==2){{v=plc::input(11);}}if(i==3){{v=plc::input(12);}}
 c.count_up(v);i=plc::add_i16(i,1);}}}}
 if(plc::input(13)){{bool done=c.update(false,false,plc::input(14),plc::input(15));plc::output(14,done);}}
 plc::write_output_bits_i16(0,16,c.value());
 if(plc::input(5)){{plc::output(14,c.done());}}else{{plc::output(14,c.full());}}
 plc::output(15,c.empty());
}}"""
    state, command = oracle(preset)
    expected = []
    for raw in values:
        b = [bool(raw & (1 << i)) for i in range(24)]
        command("r", b[0])
        command("s", b[1])
        if b[2]:
            command("u", b[3])
        command("c", b[4])
        if b[6]:
            state["p"] = 9999 if b[7] else preset
        if b[8]:
            for value in b[9:13]:
                command("u", value)
        if b[13]:
            for pin, value in zip("rsuc", [False, False, b[14], b[15]]):
                command(pin, value)
        expected.append(
            view(state["v"], state["d"] if b[5] else state["f"], state["e"])
        )
    return source, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    args = parser.parse_args()
    rng = random.Random(SEED)
    values = [
        0,
        2,
        0,
        12,
        20,
        4,
        31,
        12,
        4,
        192,
        2,
        0,
        12,
        20,
        4,
        64,
        8192 | 16384,
        8192 | 32768,
    ]
    values += [1 << i for i in range(24)] + [
        ((1 << 24) - 1) ^ (1 << i) for i in range(24)
    ]
    values += [rng.randrange(1 << 24) for _ in range(512 - len(values))]
    frames = [{"inputs": {i: bool(v & (1 << i)) for i in range(24)}} for v in values]
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-counters-") as folder:
        work = Path(folder)

        def run(name, p, expected, source=None, **extra):
            if args.case is not None and name != args.case:
                return
            verify(p, frames, expected, work, name, source)
            results.append(dict(case=name, scans=len(frames), status="pass", **extra))
            print(f"PASS: {name} / {len(frames)} scans", flush=True)

        for index in [0, 1, 31, 32, 63, 127, 200, 254]:
            for preset in [0, 1, 2, 9998, 9999]:
                name = f"counter_{index}_{preset}"
                if args.case is not None and args.case != name:
                    continue
                body, expected = generated(index, preset, values)
                source = work / (name + ".cpp")
                source.write_text(body)
                run(name, compile_source(source), expected, source)
        manifest = ROOT / "docs/capabilities/COUNTER-SOURCES.json"
        for name, file, rung in [
            ("public_B", "Project1_Part1B.smbp", 2),
            ("public_C", "car_garage.smbp", 0),
            ("public_M", "starting_motors.smbp", 12),
        ]:
            if args.case is not None and args.case != name:
                continue
            entry, lines = original(manifest, file, "counter-sources", rung)
            configs = read_configs(
                ET.parse(ROOT / "research/downloads/counter-sources" / file)
                .getroot()
                .find("SoftwareConfiguration")
            )
            preset = configs[0].preset
            state, command = oracle(preset)
            expected = []
            if name == "public_B":
                p = Program(
                    [
                        lines,
                        ["LD %Q0.1"]
                        + [f"AND %Q0.{i}" for i in range(2, 8)]
                        + ["ST %M900"],
                        ["LD %Q0.1"]
                        + [f"OR %Q0.{i}" for i in range(2, 8)]
                        + ["ST %M901"],
                        ["LD 1", "[%Q0.0:16:=%C0.V]"],
                        ["LD %M900", "ST %Q0.14"],
                        ["LD %M901", "ST %Q0.15"],
                    ],
                    counters=configs,
                )
                for raw in values:
                    command("u", bool(raw & 1))
                    expected.append(view(state["v"], state["d"], state["d"]))
            elif name == "public_C":
                p = Program(
                    [
                        lines,
                        ["LD 1", "[%Q0.0:16:=%C0.V]"],
                        ["LD %C0.D", "ST %Q0.14"],
                        ["LD %C0.E", "ST %Q0.15"],
                    ],
                    counters=configs,
                )
                for raw in values:
                    command("r", bool(raw & 4))
                    command("u", bool(raw & 1) and not state["d"])
                    command("c", bool(raw & 2))
                    expected.append(view(state["v"], state["d"], state["e"]))
            else:
                p = Program(
                    [
                        ["LD %S13", "S %M22"],
                        ["LD %I0.0", "ST %M32"],
                        ["LD %I0.1", "ST %M21"],
                        lines,
                        ["LD 1", "[%Q0.0:16:=%C0.V]"],
                        ["LD %M22", "ST %Q0.14"],
                        ["LD %C0.E", "ST %Q0.15"],
                    ],
                    counters=configs,
                )
                feedback = True
                for raw in values:
                    command("r", bool(raw & 1) and feedback)
                    command("u", bool(raw & 1) and bool(raw & 2))
                    feedback = state["d"]
                    expected.append(view(state["v"], feedback, state["e"]))
            run(
                name,
                p,
                expected,
                original_sha256=entry["sha256"],
                rung=rung,
                scope="whole isolated original rung; explicit input/readback harness; local state policy; raw graph/foreign whole CPU not imported",
            )
        name = "public_L_preset_specific_down"
        if args.case is None or args.case == name:
            file = "Lab-07-M221-autoOperator.smbp"
            entry, setup = original(manifest, file, "counter-sources", 15)
            _, down = original(manifest, file, "counter-sources", 18)
            segment = setup[5:7]
            if segment != ["[ %C0.P := %MW10 ]", "S %C0"]:
                raise AssertionError("original preset/set segment changed")
            configs = read_configs(
                ET.parse(ROOT / "research/downloads/counter-sources" / file)
                .getroot()
                .find("SoftwareConfiguration")
            )
            p = Program(
                [
                    ["LD %I0.1", "ST %M1"],
                    ["LD %I0.2", "ST %M0"],
                    ["LD 1", "[%MW10:=%I0.8:4]"],
                    ["LD %I0.3"] + segment,
                    down,
                    ["LD 1", "[%Q0.0:16:=%C0.V]"],
                    ["LD %C0.D", "ST %Q0.14"],
                    ["LD %C0.E", "ST %Q0.15"],
                ],
                counters=configs,
            )
            state, command = oracle(configs[0].preset)
            expected = []
            older = previous = 0
            for raw in values:
                if raw & 8:
                    state["p"] = (raw >> 8) & 15
                command("s", bool(raw & 8))
                falling = bool(older & ~previous & 4)
                command(
                    "c", bool(raw & 1) and bool(raw & 2) and falling and state["v"] > 0
                )
                expected.append(view(state["v"], state["d"], state["e"]))
                older, previous = previous, raw
            run(
                name,
                p,
                expected,
                original_sha256=entry["sha256"],
                rung18="whole original",
                rung15_segment=[5, 7],
                scope="original P assignment/S contiguous pair and full CD rung; ELSE/numeric/Timer portions of rung15 explicitly excluded; explicit MW/M/native-edge/readback harness",
            )
        name = "full_capacity"
        if args.case is None or args.case == name:
            body = "#include <plc.hpp>\n" + "".join(
                f"plc::Counter c{i}{{{i},9999}};\n" for i in range(255)
            )
            body += (
                "void scan(){plc::i16 total=0;"
                + "".join(
                    f"c{i}.count_up(plc::input({i % 24}));total=plc::add_i16(total,c{i}.value());"
                    for i in range(255)
                )
                + "plc::write_output_bits_i16(0,16,total);}"
            )
            source = work / (name + ".cpp")
            source.write_text(body)
            expected = []
            counts = [0] * 24
            old = 0
            for raw in values:
                for bit in range(24):
                    counts[bit] += int(bool(raw & ~old & (1 << bit)))
                total = sum(counts[i % 24] for i in range(255))
                expected.append([bool(total & (1 << bit)) for bit in range(16)])
                old = raw
            run(
                name,
                compile_source(source),
                expected,
                source,
                identities=255,
                scope="every counter value contributes to observed sum; native counter states, no M/MW emulation",
            )
    if args.case is not None and not results:
        raise AssertionError("unknown counter case")
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/expression_edges.py",
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "docs/capabilities/COUNTER-SOURCES.json",
        ROOT / "tests/fixtures/synthetic.smbp",
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
        counter_policy="provisional G122-based E/F; retained levels, masked edges and per-instruction processing require external confirmation",
    )
    if args.case is None:
        (ROOT / "docs/validation/COUNTER-STRESS-RESULTS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; independent provisional-policy oracle and actual-exported C++ recompilation",
        flush=True,
    )


if __name__ == "__main__":
    main()
