#!/usr/bin/env python3
"""Complete word domains, full-width conversion tables and SDK UBSan oracle."""

# ruff: noqa: E402
import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from expression_edges import verify
from integer_flags import array_case, frames_for, samples
from m200.frontend import compile_source
from m200.model import Program

SEED = 20020261120


def signed(raw, width):
    return int.from_bytes(raw.to_bytes(width // 8, "little"), "little", signed=True)


def bcd(value, width):
    return signed(int(f"{value:0{width // 4}d}", 16), width)


def native_sdk(work):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ required")
    target = work / "sdk-oracle"
    command = [
        compiler,
        "-std=c++17",
        "-O2",
        "-DPLC_NATIVE",
        "-fsanitize=undefined",
        "-fno-sanitize-recover=undefined",
        "-I",
        str(ROOT / "sdk"),
        str(ROOT / "tests/stress/conversion_sdk.cpp"),
        "-o",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise AssertionError(result.stderr)
    start = time.monotonic()
    result = subprocess.run([str(target)], capture_output=True, text=True, timeout=180)
    if result.returncode or result.stderr:
        raise AssertionError(f"SDK oracle failed{result.returncode}: {result.stderr}")
    report = json.loads(result.stdout)
    if report != dict(
        status="pass",
        word_widen_concat_vectors=65536,
        bcd_word_vectors=10000,
        bcd_dword_vectors=100000000,
        hardware_proof=False,
    ):
        raise AssertionError("unexpected SDK oracle counts")
    report.update(
        seconds=round(time.monotonic() - start, 3),
        compiler=compiler,
        compile_flags=command[1:6],
        oracle="decimal-corrected packed-digit increment, independent of SDK divide/modulo codec; volatile value prevents constant propagation",
        counted_as_scan_frames=False,
    )
    return report


def dense_word(kind):
    values = list(range(10000))
    frames, rows = [], []
    for n in values:
        payload = int(f"{n:04d}", 16) if kind == "BTI" else n
        raw_input = payload | ((n % 4) << 16)
        frames.append({"inputs": {b: bool(raw_input & (1 << b)) for b in range(24)}})
        result = n if kind == "BTI" else int(f"{n:04d}", 16)
        rows.append([bool(result & (1 << b)) for b in range(16)])
    if kind == "BTI":
        # Exact G59 rung0; other rungs are the declared harness.
        p = Program(
            [
                ["LD 1", "R %S17", "R %S18", "[%MW10:=%I0.0:16]"],
                ["LD %I0.16", "[%MW20:=-32768]", "[%MW20:=SHL(%MW20,1)]"],
                ["LD %I0.17", "[%MW20:=32767]", "[%MW20:=%MW20+1]"],
                ["LD 1", "ST %M0"],
                ["LD %M0", "[%MW0:=BTI(%MW10)]"],
                ["LD 1", "[%Q0.0:16:=%MW0]"],
            ]
        )
        return frames, rows, None, p
    body = """#include <plc.hpp>
void scan(){
plc::clear_shift_carry();plc::clear_arithmetic_error();
if(plc::input(16)){plc::i16 c=plc::shl_i16(-32768,1);}
if(plc::input(17)){plc::i16 e=plc::add_i16(32767,1);}
plc::i16 value=plc::int_to_bcd(plc::read_input_bits_i16(0,16));
plc::write_output_bits_i16(0,16,value);}
"""
    return frames, rows, body, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    args = parser.parse_args()
    results = []
    sdk = None
    controls, frames = frames_for(512)
    with tempfile.TemporaryDirectory(prefix="m200-conversions-") as folder:
        work = Path(folder)

        def run(name, trace, rows, body=None, program=None, **extra):
            if args.case and args.case != name:
                return
            source = None
            if body:
                source = work / (name + ".cpp")
                source.write_text(body)
                program = compile_source(source)
            verify(program, trace, rows, work, name, source)
            results.append(dict(case=name, scans=len(trace), status="pass", **extra))
            print(f"PASS: {name} / {len(trace)} scans", flush=True)

        for kind in ("BTI", "ITB"):
            name = "word_domain_" + kind
            if args.case and args.case != name:
                continue
            trace, rows, body, p = dense_word(kind)
            run(
                name,
                trace,
                rows,
                body,
                p,
                scope="all10000 valid word values; whole16-bit results observed directly. Flags checked independently in table cases/SDK to avoid masking a wrong result. BTI includes exact G59 rung with explicit harness",
            )
        for typ, width, decode, encode in [
            ("i16", 16, "bcd_to_int", "int_to_bcd"),
            ("i32", 32, "bcd_to_dint", "dint_to_bcd"),
        ]:
            rng = random.Random(SEED + width)
            limit = 10 ** (width // 4)
            values = [0, 1, 9, 10, limit - 1, 8 * (limit // 10), 7 * (limit // 10)]
            values += [rng.randrange(limit) for _ in range(128 - len(values))]
            packed = [bcd(v, width) for v in values]
            for name, operands, expected in [
                (decode, packed, values),
                (encode, values, packed),
            ]:
                if args.case and args.case != name:
                    continue
                body, rows = array_case(
                    typ,
                    operands,
                    None,
                    [(v, None, False) for v in expected],
                    f"plc::{name}(values[index])",
                    controls,
                )
                run(
                    name,
                    frames,
                    rows,
                    body=body,
                    scope="fullwidth expected tables, inactive calls and flags before/after clears",
                )
        rng = random.Random(SEED)
        low = samples(16)
        high = samples(16)
        rng.shuffle(high)
        for mode in ("pair", "swap", "same"):
            name = "concat_" + mode
            if args.case and args.case != name:
                continue
            a, b = (
                (high, low)
                if mode == "swap"
                else (low, low if mode == "same" else high)
            )
            expected = [
                int.from_bytes(
                    (x % 65536).to_bytes(2, "little")
                    + (y % 65536).to_bytes(2, "little"),
                    "little",
                    signed=True,
                )
                for x, y in zip(a, b)
            ]
            body, rows = array_case(
                "i32",
                a,
                b,
                [(v, None, False) for v in expected],
                "plc::concat_words(values[index],others[index])",
                controls,
                operand_kind="i16",
            )
            run(
                name,
                frames,
                rows,
                body=body,
                scope="low/high byte oracle, walking bits, fullwidth tables and flags",
            )
        name = "signed_widen"
        if args.case is None or args.case == name:
            a = samples(16)
            body, rows = array_case(
                "i32",
                a,
                None,
                [(v, None, False) for v in a],
                "plc::int_to_dint(values[index])",
                controls,
                operand_kind="i16",
            )
            run(
                name,
                frames,
                rows,
                body=body,
                scope="explicit local sign-extension policy, not independent physical DWORD proof",
            )
        if args.case is None or args.case == "sdk":
            sdk = native_sdk(work)
            print(
                "PASS: SDK UBSan /100075536 finite-domain vectors (not scan frames)",
                flush=True,
            )
    if not results and sdk is None:
        raise AssertionError("unknown case")
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/conversion_sdk.cpp",
        ROOT / "tests/stress/integer_flags.py",
        ROOT / "tests/stress/expression_edges.py",
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "tests/fixtures/synthetic.smbp",
    ]
    report = dict(
        seed=SEED,
        target="TM200CE40T",
        cases=results,
        scans=sum(r["scans"] for r in results),
        sdk_exhaustive=sdk,
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        policy="CONCATW low-first corroborated by official FAQ; signed DWORD is local emulation policy requiring external proof; invalid BCD sets S18 and stops local model without fabricated result",
        whole_original_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
    )
    if args.case is None:
        (ROOT / "docs/validation/CONVERSION-STRESS-RESULTS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; independent decimal/byte oracle and actual exported C++ recompilation"
    )


if __name__ == "__main__":
    main()
