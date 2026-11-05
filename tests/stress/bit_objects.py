#!/usr/bin/env python3
"""Packed masks, shared word bits and pinned original instruction extracts."""

# ruff: noqa: E402
import hashlib
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

SEED = 20020261114


def verify(program, frames, expected, work, name, source=None):
    def check(candidate, phase):
        machine = Machine(candidate)
        for i, (frame, row) in enumerate(zip(frames, expected)):
            got = machine.step(frame["inputs"])
            if got != row:
                raise AssertionError(f"{name} {phase} frame{i}: {got} != {row}")

    check(program, "IL")
    restored = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    check(restored, "JSON")
    normalized = normalize(program)
    check(normalized, "normalized")
    if source is not None and run_native(source, frames) != expected:
        raise AssertionError(name + " original C++ differs from mask oracle")
    reverse = work / (name + "_reverse.cpp")
    reverse.write_text(to_cpp(program))
    if run_native(reverse, frames) != expected:
        raise AssertionError(name + " reverse C++ differs from mask oracle")
    check(compile_source(reverse), "recompiled")
    dest = work / (name + ".smbp")
    write_project(program, ROOT / "tests/fixtures/synthetic.smbp", dest)
    check(load_project(dest), "XML")


def bits(value):
    return [bool(value & (1 << bit)) for bit in range(16)]


def original(manifest, identifier, folder, rung):
    entry = next(
        e
        for e in json.loads(manifest.read_text())["sources"]
        if e.get("id", e["file"]) == identifier
    )
    raw = (ROOT / "research/downloads" / folder / entry["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise AssertionError("original source digest changed")
    node = ET.fromstring(raw).findall(".//RungEntity")[rung]
    lines = [
        " ".join(n.text.split())
        for n in node.findall("InstructionLines/InstructionLineEntity/InstructionLine")
    ]
    return entry, lines


def main():
    rng = random.Random(SEED)
    values = [0, 1, 65535, 32768, 0xFFFFFF, 0x800000] + [
        rng.randrange(1 << 24) for _ in range(250)
    ]
    frames = [
        {"inputs": {bit: bool(value & (1 << bit)) for bit in range(24)}}
        for value in values
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="m200-bit-objects-") as directory:
        work = Path(directory)
        for kind, maximum in [("i16", 16), ("i32", 32)]:
            for count in range(1, maximum + 1):
                name = f"{kind}_{count}"
                source = work / (name + ".cpp")
                init = (
                    "plc::i16 v=plc::read_input_bits_i16(0,16);"
                    if kind == "i16"
                    else """plc::i32 v=plc::read_input_bits_i32(0,24);
if(plc::input(23)){v=plc::add_i32(v,-16777216);}"""
                )
                observe = (
                    "plc::write_output_bits_i16(0,16,r);"
                    if kind == "i16"
                    else """if(plc::input(22)){r=plc::shr_i32(r,16);}
plc::write_output_bits_i32(0,16,r);"""
                )
                source.write_text(
                    "#include <plc.hpp>\nvoid scan(){"
                    + init
                    + f"""
plc::write_m(495,true);plc::write_m(528,true);
plc::write_m_bits_{kind}(496,{count},v);
plc::{kind} r=plc::read_m_bits_{kind}(496,{count});
{observe}
plc::output(0,plc::output_state(0)^(!plc::read_m(495)||!plc::read_m(528)));}}"""
                )
                expected = []
                for value in values:
                    raw = (
                        value & 65535
                        if kind == "i16"
                        else value | (0xFF000000 if value & (1 << 23) else 0)
                    )
                    raw &= (1 << count) - 1
                    if kind == "i32" and value & (1 << 22):
                        raw >>= 16
                    expected.append(bits(raw))
                verify(compile_source(source), frames, expected, work, name, source)
                results.append(dict(case=name, scans=len(frames), status="pass"))
                print(f"PASS: {name} / {len(frames)} scans", flush=True)
        for bit in range(16):
            name = f"word_bit_{bit}"
            source = work / (name + ".cpp")
            source.write_text(f"""#include <plc.hpp>
void scan(){{plc::write_word(4000,plc::read_input_bits_i16(0,16));
plc::write_word_bit(4000,{bit},plc::input(16));
plc::write_output_bits_i16(0,16,plc::read_word(4000));
plc::output({bit},plc::read_word_bit(4000,{bit}));}}""")
            expected = [
                bits((v & 65535 & ~(1 << bit)) | (((v >> 16) & 1) << bit))
                for v in values
            ]
            verify(compile_source(source), frames, expected, work, name, source)
            results.append(dict(case=name, scans=len(frames), status="pass"))
            print(f"PASS: {name} / {len(frames)} scans", flush=True)

        source = work / "high_byte_alias.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){plc::write_dword(100,plc::read_input_bits_i32(0,24));"
            + "".join(
                f"plc::write_word_bit(101,{bit + 8},plc::input({bit + 8}));"
                for bit in range(8)
            )
            + """
plc::write_m_bits_i32(992,32,plc::read_dword(100));
plc::i32 v=plc::read_m_bits_i32(992,32);
if(plc::input(22)){v=plc::shr_i32(v,16);}
plc::write_output_bits_i32(0,16,v);}"""
        )
        expected = []
        for value in values:
            raw = value | (((value >> 8) & 255) << 24)
            expected.append(bits(raw >> 16 if value & (1 << 22) else raw))
        verify(
            compile_source(source), frames, expected, work, "high_byte_alias", source
        )
        results.append(dict(case="high_byte_alias", scans=len(frames), status="pass"))
        entry, lines = original(
            ROOT / "tests/public/control-flow-manifest.json",
            "flow-original-loop.smbp",
            "public-projects",
            1,
        )
        p = Program(
            [lines]
            + [[f"LD %MW0:X{bit}", f"ST %Q0.{bit}"] for bit in range(8)]
            + [["LD %M0", "ST %Q0.8"]]
        )
        expected = [bits((v & 255) | (256 if v & 255 else 0)) for v in values]
        verify(p, frames, expected, work, "public_packed_input")
        results.append(
            dict(
                case="public_packed_input",
                scans=len(frames),
                status="pass",
                original_sha256=entry["sha256"],
                rung=1,
                scope="complete isolated original rung; observations added; no CPU rewrite",
            )
        )
        entry, lines = original(
            ROOT / "docs/capabilities/INDEXED-SOURCES.json", "D", "indexed-sources", 9
        )
        segment = lines[2:8]
        if segment != [
            "LD 1",
            "AND %M77",
            "ST %MW2009:X0",
            "LD %MW2009:X0",
            "S %M31",
            "S %M32",
        ]:
            raise AssertionError("original selector segment changed")
        p = Program(
            [
                ["LD %I0.0", "ST %M77"],
                ["LD 1", "[%MW2009:=21844]"],
                segment,
                ["LD %M31", "ST %Q0.0"],
                ["LD %M32", "ST %Q0.1"],
                ["LD [%MW2009=21845]", "ST %Q0.2"],
            ]
        )
        held = False
        expected = []
        for v in values:
            active = bool(v & 1)
            held = held or active
            expected.append([held, held, active] + [False] * 13)
        verify(p, frames, expected, work, "public_word_selector")
        results.append(
            dict(
                case="public_word_selector",
                scans=len(frames),
                status="pass",
                original_sha256=entry["sha256"],
                rung=9,
                scope="exact contiguous instruction slice [2:8]; MULTIFB/timer portion excluded explicitly; adapters added",
            )
        )
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/public/control-flow-manifest.json",
        ROOT / "docs/capabilities/INDEXED-SOURCES.json",
    ]
    report = dict(
        seed=SEED,
        cases=results,
        scans=sum(r["scans"] for r in results),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        whole_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
    )
    (ROOT / "docs/validation/BIT-OBJECT-STRESS-RESULTS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; independent masks, C++, IL, JSON, reverse, normalization, XML and original extracts"
    )


if __name__ == "__main__":
    main()
