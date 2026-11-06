#!/usr/bin/env python3
"""Independent integer/shift flags, full-width values and pinned native IL."""

# ruff: noqa: E402
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bit_objects import original
from expression_edges import verify
from m200.frontend import compile_source
from m200.model import Program

SEED = 20020261119


def signed(value, width):
    raw = value % (1 << width)
    return raw - (1 << width) if raw >= (1 << (width - 1)) else raw


def frames_for(count):
    # Each array element executes once in each pair of rounds, while all seven
    # control bits are exhaustive. Other input bits exercise unused-pin isolation.
    rng = random.Random(SEED)
    values = [
        ((n % 128) ^ (8 if (n // 128) % 2 else 0)) | (rng.randrange(1 << 17) << 7)
        for n in range(count)
    ]
    return values, [
        {"inputs": {b: bool(v & (1 << b)) for b in range(24)}} for v in values
    ]


def samples(width):
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    values = [0, 1, -1, lo, hi, -2]
    values += [signed(1 << b, width) for b in range(width)]
    values += [signed(~(1 << b), width) for b in range(width)]
    rng = random.Random(SEED + width)
    values += [rng.randint(lo, hi) for _ in range(128 - len(values))]
    return values


def shift_result(stem, value, width, distance):
    raw, mask = value % (1 << width), (1 << width) - 1
    left = stem in ("shl", "rol")
    carry = bool(raw & (1 << (width - distance if left else distance - 1)))
    if stem == "shl":
        result = raw << distance
    elif stem == "shr":
        result = raw >> distance
    elif stem == "rol":
        result = ((raw << distance) | (raw >> (width - distance))) & mask
    else:
        result = ((raw >> distance) | (raw << (width - distance))) & mask
    return signed(result, width), carry, False


def alu_result(stem, a, b, width):
    lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
    if stem in ("div", "rem"):
        quotient = abs(a) // abs(b)
        if (a < 0) != (b < 0):
            quotient = -quotient
        raw = quotient if stem == "div" else a - quotient * b
        error = not lo <= quotient <= hi
    else:
        raw = {
            "add": lambda: a + b,
            "sub": lambda: a - b,
            "mul": lambda: a * b,
            "sqrt": lambda: math.isqrt(a),
            "abs": lambda: abs(a),
        }[stem]()
        error = not lo <= raw <= hi
    return signed(raw, width), None, error


def array_case(kind, a, b, results, operation, controls):
    # A separate expected-value table makes all32 result bits observable, instead
    # of comparing only the low output byte or sharing the operation's evaluator.
    arrays = f"plc::{kind} values[128]={{" + ",".join(map(str, a)) + "};\n"
    if b is not None:
        arrays += f"plc::{kind} others[128]={{" + ",".join(map(str, b)) + "};\n"
    arrays += (
        f"plc::{kind} expected[128]={{" + ",".join(str(v[0]) for v in results) + "};\n"
    )
    body = (
        "#include <plc.hpp>\n"
        + arrays
        + f"""
plc::i16 index=0;plc::{kind} last=0;plc::{kind} reference=0;
void scan(){{
if(plc::input(0)){{plc::clear_arithmetic_error();}}
if(plc::input(6)){{plc::i16 error_seed=plc::add_i16(32767,1);}}
if(plc::input(1)){{plc::i16 carry_seed=plc::shl_i16(-32768,1);}}
if(plc::input(2)){{plc::clear_shift_carry();}}
if(plc::input(3)){{last={operation};reference=expected[index];}}
bool c=plc::system(17);bool e=plc::system(18);
if(plc::input(4)){{plc::clear_shift_carry();}}
if(plc::input(5)){{plc::clear_arithmetic_error();}}
plc::output(0,last==reference);plc::output(1,c);plc::output(2,e);
plc::output(3,plc::system(17));plc::output(4,plc::system(18));
plc::output(5,last<0);plc::output(6,last==0);plc::output(7,!plc::system(20));
index=plc::add_i16(index,1);if(index==128){{index=0;}}
}}"""
    )
    carry = error = False
    last = 0
    rows = []
    for n, raw in enumerate(controls):
        if raw & 1:
            error = False
        if raw & 64:
            error = True
        if raw & 2:
            carry = True
        if raw & 4:
            carry = False
        if raw & 8:
            last, next_carry, overflow = results[n % 128]
            if next_carry is not None:
                carry = next_carry
            error |= overflow
        c, e = carry, error
        if raw & 16:
            carry = False
        if raw & 32:
            error = False
        rows.append([True, c, e, carry, error, last < 0, last == 0, True] + [False] * 8)
    return body, rows


def mixed_case(rotation, values):
    def at(n):
        return (n + rotation) % 24

    body = f"""#include <plc.hpp>
plc::i16 n=32767;
void scan(){{
if(plc::input({at(0)})){{plc::clear_arithmetic_error();}}
if(plc::input({at(1)})){{plc::clear_shift_carry();}}
bool a=plc::system(17)&&(plc::shl_i16(0,1)==0);
bool b=plc::system(17)||(plc::shl_i16(-32768,1)!=0);
bool c=plc::system(18)==(plc::add_i16(32767,1)==-32768);
if(plc::input({at(2)})){{plc::clear_arithmetic_error();}}
plc::i16 i=0;while(i<3){{bool up=plc::input({at(3)});
if(i==1){{up=plc::input({at(4)});}}if(i==2){{up=plc::input({at(5)});}}
if(up){{n=plc::add_i16(n,1);}}else{{n=plc::sub_i16(n,1);}}
i=plc::add_i16(i,1);}}
bool error=plc::system(18);if(plc::input({at(6)})){{plc::clear_arithmetic_error();}}
plc::output(0,a&&!b);plc::output(1,c);plc::output(2,error);
plc::output(3,plc::system(18));plc::output(4,plc::system(17));
plc::output(5,n<0);plc::output(6,n==32767);plc::write_output_bits_i16(8,8,n);
}}"""
    n, carry, error = 32767, False, False
    rows = []
    for value in values:
        ins = [bool(value & (1 << at(i))) for i in range(7)]
        if ins[0]:
            error = False
        if ins[1]:
            carry = False
        a = carry
        # First expression conditionally ejects0. Second then always ejects1,
        # and has false comparison. Comparison's LHS precedes overflowing RHS.
        c = error
        carry, error = True, True
        if ins[2]:
            error = False
        for up in ins[3:6]:
            raw = n + (1 if up else -1)
            error |= not -32768 <= raw <= 32767
            n = signed(raw, 16)
        before = error
        if ins[6]:
            error = False
        rows.append(
            [a, c, before, error, carry, n < 0, n == 32767, False]
            + [bool(n & (1 << b)) for b in range(8)]
        )
    return body, rows


def probes(word, error="%S18"):
    return [
        [f"LD [%{word}<0]", "ST %Q0.0"],
        [f"LD {error}", "ST %Q0.1"],
        ["LD 1", f"[%Q0.8:8:=%{word}]"],
    ]


def native_cases(values):
    # Published G55 example, not presented as a downloaded original SMBP.
    p = Program(
        [
            ["LD %S13", "[%MW1:=23241]", "[%MW2:=21853]"],
            ["LD %I0.0", "ST %M0"],
            ["LD %I0.1", "R %S18"],
            ["LD %M0", "[%MW0:=%MW1+%MW2]"],
            ["LDN %S18", "[%MW10:=%MW0]"],
            ["LD %S18", "[%MW10:=32767]"],
            ["LD [%MW0=-20442]", "ST %Q0.0"],
            ["LD [%MW10=32767]", "ST %Q0.1"],
            ["LD %S18", "ST %Q0.2"],
            ["LD [%MW10<0]", "ST %Q0.3"],
            ["LD 1", "[%Q0.8:8:=%MW10]"],
        ]
    )
    raw = 0
    error = False
    rows = []
    for v in values:
        if v & 2:
            error = False
        if v & 1:
            raw, error = -20442, True
        shown = 32767 if error else raw
        rows.append(
            [raw == -20442, shown == 32767, error, shown < 0]
            + [False] * 4
            + [bool(shown & (1 << b)) for b in range(8)]
        )
    yield (
        "manual_G55",
        p,
        rows,
        dict(
            source="EIO0000003289.04 p55",
            scope="published three rungs plus explicit input/init/readback harness",
        ),
    )

    for rung, output, word in [(10, 0, 10), (15, 4, 12), (20, 11, 14)]:
        entry, lines = original(
            ROOT / "docs/capabilities/INDEXED-SOURCES.json",
            "T",
            "indexed-sources",
            rung,
        )
        if lines != [
            "LD %S6",
            f"AND %Q0.{output}",
            f"RISING{(rung - 10) // 5}",
            f"[ %MD{word} := %MD{word} + 1 ]",
        ]:
            raise AssertionError("original increment rung changed")
        p = Program(
            [
                ["LD %S13", f"[%MD{word}:=2147483647]"],
                ["LD %I0.0", f"ST %Q0.{output}"],
                ["LD %I0.1", "R %S18"],
                lines,
            ]
            + probes(f"MD{word}")
        )
        count, old, error = 2147483647, False, False
        rows = []
        for n, v in enumerate(values):
            if v & 2:
                error = False
            enabled = bool((n // 50) % 2) and bool(v & 1)
            if enabled and not old:
                raw = count + 1
                error |= raw > 2147483647
                count = signed(raw, 32)
            old = enabled
            row = [False] * 16
            row[output] = bool(v & 1)
            row[0], row[1] = count < 0, error
            row[8:] = [bool(count & (1 << b)) for b in range(8)]
            rows.append(row)
        yield (
            f"public_T_{rung}",
            p,
            rows,
            dict(
                original_sha256=entry["sha256"],
                rung=rung,
                scope="complete isolated original IL, explicit cold-init/Q/flag/readback harness; source raw graph not emitted",
            ),
        )

    entry, lines = original(
        ROOT / "tests/public/control-flow-manifest.json",
        "flow-original-loop.smbp",
        "public-projects",
        3,
    )
    if lines != [
        "%L0:",
        "LD %M0",
        "AND [ %MW10 > 0 ]",
        "[ INC %MW1 ]",
        "[ %MW10 := SHR ( %MW10 , 1 ) ]",
        "JMPC %L0",
    ]:
        raise AssertionError("original loop rung changed")
    p = Program(
        [
            ["LD 1", "[%MW10:=%I0.0:16]", "[%MW1:=0]"],
            ["LD %I0.16", "ST %M0"],
            ["LD %I0.17", "[%MW1:=32767]"],
            ["LD %I0.18", "R %S18"],
            ["LD %I0.19", "R %S17"],
            lines,
            ["LD [%MW10=0]", "ST %Q0.0"],
            ["LD %S17", "ST %Q0.1"],
            ["LD %S18", "ST %Q0.2"],
            ["LD [%MW1<0]", "ST %Q0.3"],
            ["LD 1", "[%Q0.8:8:=%MW1]"],
        ]
    )
    carry = error = False
    rows = []
    for v in values:
        if v & (1 << 18):
            error = False
        if v & (1 << 19):
            carry = False
        word = signed(v, 16)
        iterations = word.bit_length() if word > 0 and v & (1 << 16) else 0
        count = 32767 if v & (1 << 17) else 0
        if iterations:
            carry = True
            error |= count == 32767
            count = signed(count + iterations, 16)
            word = 0
        rows.append(
            [word == 0, carry, error, count < 0]
            + [False] * 4
            + [bool(count & (1 << b)) for b in range(8)]
        )
    yield (
        "public_flow_loop",
        p,
        rows,
        dict(
            original_sha256=entry["sha256"],
            rung=3,
            scope="whole original shift/INC/JMPC rung with explicit input/seed/flag/readback harness; raw graph not emitted",
        ),
    )


def execute_case(job):
    name, frames, rows, body, program, extra = job
    with tempfile.TemporaryDirectory(prefix="m200-integer-flags-") as folder:
        work = Path(folder)
        source = None
        if body is not None:
            source = work / (name + ".cpp")
            source.write_text(body)
            program = compile_source(source)
        verify(program, frames, rows, work, name, source)
    return dict(case=name, scans=len(frames), status="pass", **extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    results = []
    jobs = []
    controls, frames = frames_for(512)

    def run(name, frames, rows, body=None, program=None, **extra):
        if args.case is not None and args.case != name:
            return
        jobs.append((name, frames, rows, body, program, extra))

    for kind, width in [("i16", 16), ("i32", 32)]:
        a = samples(width)
        for stem in ("shl", "shr", "rol", "ror"):
            for distance in range(1, width + 1):
                name = f"{stem}_{kind}_{distance}"
                if args.case is not None and args.case != name:
                    continue
                oracle = [shift_result(stem, v, width, distance) for v in a]
                body, rows = array_case(
                    kind,
                    a,
                    None,
                    oracle,
                    f"plc::{stem}_{kind}(values[index],{distance})",
                    controls[:256],
                )
                run(
                    name,
                    frames[:256],
                    rows,
                    body=body,
                    shift_distance=distance,
                    operand_width=width,
                )
        lo, hi = -(1 << (width - 1)), (1 << (width - 1)) - 1
        pairs = [
            (hi, 1),
            (lo, -1),
            (lo, 1),
            (hi, 2),
            (lo, 2),
            (-1, -1),
            (0, 1),
            (1, -1),
        ]
        rng = random.Random(SEED + width)
        pairs += [
            (rng.randint(lo, hi), rng.randint(lo, hi) or 1)
            for _ in range(128 - len(pairs))
        ]
        for stem in ("add", "sub", "mul", "div", "rem", "sqrt") + (
            ("abs",) if kind == "i32" else ()
        ):
            name = f"{stem}_{kind}"
            if args.case is not None and args.case != name:
                continue
            aa = (
                [abs(x) if x != lo else hi for x, _ in pairs]
                if stem == "sqrt"
                else [x for x, _ in pairs]
            )
            bb = [y for _, y in pairs]
            oracle = [alu_result(stem, x, y, width) for x, y in zip(aa, bb)]
            unary = stem in ("sqrt", "abs")
            operation = f"plc::{stem}_{kind}(values[index]" + (
                ")" if unary else ",others[index])"
            )
            body, rows = array_case(
                kind, aa, None if unary else bb, oracle, operation, controls
            )
            run(name, frames, rows, body=body, operand_width=width)

    rng = random.Random(SEED)
    values = (
        [0, (1 << 24) - 1]
        + [1 << b for b in range(24)]
        + [((1 << 24) - 1) ^ (1 << b) for b in range(24)]
    )
    values += [rng.randrange(1 << 24) for _ in range(512 - len(values))]
    mixed_frames = [
        {"inputs": {b: bool(v & (1 << b)) for b in range(24)}} for v in values
    ]
    for rotation in range(8):
        body, rows = mixed_case(rotation, values)
        run(f"mixed_{rotation}", mixed_frames, rows, body=body)
    for name, program, rows, extra in native_cases(values):
        run(name, mixed_frames, rows, program=program, **extra)
    if not jobs:
        raise AssertionError("unknown case")
    workers = min(args.workers, len(jobs))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(execute_case, jobs):
            results.append(result)
            print(f"PASS: {result['case']} / {result['scans']} scans", flush=True)
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/stress/expression_edges.py",
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "tests/fixtures/synthetic.smbp",
        ROOT / "docs/capabilities/INDEXED-SOURCES.json",
        ROOT / "tests/public/control-flow-manifest.json",
    ]
    report = dict(
        seed=SEED,
        local_workers=workers,
        target="TM200CE40T",
        cases=results,
        scans=sum(r["scans"] for r in results),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        manuals_sha256={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                ROOT / "research/downloads/manuals/EIO0000003289.pdf",
                ROOT / "research/downloads/manuals/EIO0000002019.pdf",
            )
        },
        result_policy="signed modular local policy; G55 proves ADDword example, other nonsignificant overflow bits unverified on physical PLC",
        unknown_domain="integer DIV0/SQRTnegative still stop local model after S18; no fabricated result; float/SW17 not covered",
        whole_projects_imported=0,
        official_editor="pending",
        physical_plc="pending",
    )
    if args.case is None:
        (ROOT / "docs/validation/INTEGER-FLAG-STRESS-RESULTS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; independent modular/last-bit oracle and actual exported C++ recompilation"
    )


if __name__ == "__main__":
    main()
