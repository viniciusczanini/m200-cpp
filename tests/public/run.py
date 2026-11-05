#!/usr/bin/env python3
"""Audit pinned, unmodified public projects and execute isolated original IL.

No network access, CPU substitution, project rewriting, or hardware access.
Expected outputs come from the small analytical oracles below, never the VM.
"""

# ruff: noqa: E402
import argparse
import hashlib
import json
import operator
import random
import struct
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from fetch import DEFAULT_CORPUS, verified_bytes
from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import check_graph, load_project
from m200.reverse import to_cpp

SEED = 20020261105
BASES = {"OneMilliSeconds": 1, "OneHundredMilliSeconds": 100, "OneSecond": 1000}
WARNINGS = {
    1: [
        "Parallel rung 1 contains parenthesized IL outside the executable subset; only rung 0 has a runtime oracle."
    ],
    3: [
        "Filename says floats multiply, but original executable logic assigns integer MW0=1; no float multiplication coverage."
    ],
    4: [
        "Five original timer blocks reference TM0..4, but original Timers is empty. Defaults are unknown; no timer type/preset is invented and no runtime timer pass is claimed."
    ],
    5: [
        "Filename says Counters1, but only LD M0 / ST M0 exists. No native counter instruction was tested."
    ],
    6: [
        "Original includes analog input words, parallel graphics and non-reversible/retentive timer forms outside this isolated runtime test."
    ],
    7: [
        "Runtime covers rungs 0..5. READ_VAR/WRITE_VAR blocks require communication configuration; checking an isolated rung without that context does not test or disprove configured Modbus support."
    ],
    8: [
        "All original LadderElements are empty; simple IL comparisons pass without a graphical agreement claim. Compound comparison expressions are explicitly refused."
    ],
    9: [
        "All six logic rungs execute in isolation, including original explicit TOF configuration. Original graph mismatches in rungs 0/1 and foreign CPU still prevent whole-project compatibility claims."
    ],
}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def original_tree(data):
    # verified_bytes() runs before this independent, foreign-CPU XML inspection.
    if len(data) > 20_000_000 or b"\x00" in data:
        raise ValueError("unsafe XML size/encoding")
    data.decode("utf-8-sig")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("DTD/entity declarations are forbidden")
    root = ET.fromstring(data)
    if root.tag != "ProjectDescriptor":
        raise ValueError("unexpected XML root")
    pending = [(root, 0)]
    while pending:
        node, depth = pending.pop()
        if depth > 64:
            raise ValueError("XML depth exceeds 64")
        pending.extend((child, depth + 1) for child in node)
    return root


def instruction_lines(node):
    container = node.find("InstructionLines")
    if container is None:
        raise ValueError("missing original IL")
    lines = []
    for child in container:
        if child.tag != "InstructionLineEntity":
            raise ValueError("unknown instruction container")
        text = child.findtext("InstructionLine")
        if text is None:
            raise ValueError("missing original instruction text")
        # Whitespace normalization only. The original file is never rewritten.
        lines.append(" ".join(text.split()))
    return lines


def explicit_timers(root):
    timers = {}
    unresolved = []
    for node in root.findall("SoftwareConfiguration/Timers/TimerTM"):
        required = ("Index", "Address", "Type", "Preset", "Base")
        if any(node.findtext(key) is None for key in required):
            unresolved.append(
                {
                    "index": node.findtext("Index"),
                    "reason": "implicit timer defaults not inferred",
                }
            )
            continue
        if node.findtext("Base") not in BASES:
            unresolved.append(
                {"index": node.findtext("Index"), "reason": "unrecognized timer base"}
            )
            continue
        if node.findtext("IsRetentive", "false").lower() != "false":
            unresolved.append(
                {
                    "index": node.findtext("Index"),
                    "reason": "retentive timer outside this extraction",
                }
            )
            continue
        if node.findtext("IsDynamicPreset", "false").lower() != "false":
            unresolved.append(
                {
                    "index": node.findtext("Index"),
                    "reason": "dynamic timer outside this extraction",
                }
            )
            continue
        index = int(node.findtext("Index"))
        if index in timers or node.findtext("Address") != "%TM" + str(index):
            raise ValueError("invalid/duplicate timer identity")
        base = BASES[node.findtext("Base")]
        timers[index] = Timer(
            node.findtext("Type"), int(node.findtext("Preset")) * base, base
        )
    return timers, unresolved


def used_timers(rungs, timers):
    return {
        index: timer
        for index, timer in timers.items()
        if any(rung[0] == "BLK %TM" + str(index) for rung in rungs)
    }


def result_of(function):
    try:
        function()
        return {"status": "PASS"}
    except CompileError as error:
        return {"status": "REFUSED", "error": str(error)}


def inventory(source, corpus):
    path = corpus / source["file"]
    data = verified_bytes(path, source)
    root = original_tree(data)
    model = root.findtext("HardwareConfiguration/Plc/Cpu/Reference")
    if model != source["cpu"]:
        raise AssertionError("unexpected original CPU")
    nodes = root.findall(
        "SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity"
    )
    if len(nodes) != source["rungs"]:
        raise AssertionError("original rung count changed")
    rungs = [instruction_lines(node) for node in nodes]
    timers, unresolved = explicit_timers(root)
    imported = result_of(lambda: load_project(path))
    if imported.get("error") != source["expected_full_import_error"]:
        raise AssertionError(
            "unexpected whole-project import outcome: " + str(imported)
        )
    checks = []
    for index, (node, lines) in enumerate(zip(nodes, rungs)):
        il = result_of(lambda: validate(Program([lines], used_timers([lines], timers))))
        graph = result_of(lambda: check_graph(node, lines))
        absent = node.find("LadderElements") is None or not len(
            node.find("LadderElements")
        )
        if graph["status"] == "PASS" and absent:
            graph = {
                "status": "ABSENT",
                "reason": "original contains no Ladder elements; no graphical agreement claimed",
            }
        wanted_il = source["expected_il_errors"].get(str(index))
        wanted_graph = source["expected_graph_errors"].get(str(index))
        if il.get("error") != wanted_il or graph.get("error") != wanted_graph:
            raise AssertionError(
                "unexpected original validation outcome in %s rung %d: %s %s"
                % (source["file"], index, il, graph)
            )
        if absent != (index in source["expected_graph_absent"]):
            raise AssertionError("unexpected original graphics presence")
        checks.append(
            {"rung": index, "original_il": lines, "il": il, "graphics": graph}
        )
    report = {
        "source": source,
        "original_cpu": model,
        "whole_project_import": imported,
        "extraction_method": "hash-verified original XML; IL whitespace only; no CPU/header replacement",
        "timer_configurations_explicit": {str(k): vars(v) for k, v in timers.items()},
        "timer_configurations_unresolved": unresolved,
        "warnings": WARNINGS.get(source["id"], []),
        "rung_checks": checks,
    }
    return {"rungs": rungs, "timers": timers, "report": report}


def row(**outputs):
    value = [False] * 16
    for index, bit in outputs.items():
        value[int(index)] = bool(bit)
    return value


def inputs(frame, index):
    return bool(frame["inputs"].get(str(index), False))


def random_frames(count, bits, seed, durations=(0, 1, 10, 100, 1000)):
    rng = random.Random(seed)
    return [
        {
            "dt_ms": rng.choice(durations),
            "inputs": {str(bit): bool(rng.getrandbits(1)) for bit in bits},
        }
        for _ in range(count)
    ]


def cases_for(corpus):
    """Build adapters separately; selected instruction lists come from originals."""
    cases = []

    def add(
        name, source, selected, frames, oracle, before=None, after=None, notes=None
    ):
        original = [corpus[source]["rungs"][index] for index in selected]
        before = before or []
        after = after or []
        cases.append(
            {
                "name": name,
                "source": source,
                "selected_rungs": selected,
                "original_rungs": original,
                "before": before,
                "after": after,
                "adapter_notes": notes or [],
                "frames": frames,
                "program": Program(
                    before + original + after,
                    used_timers(original, corpus[source]["timers"]),
                ),
                "oracle": oracle,
            }
        )

    truth = [
        {
            "dt_ms": 10,
            "inputs": {str(bit): bool(combination & (1 << bit)) for bit in range(3)},
        }
        for combination in range(8)
    ] * 64
    add(
        "xic_xio_series",
        0,
        [0, 1],
        truth,
        lambda fs: [
            row(
                **{
                    "0": not inputs(f, 0) and not inputs(f, 2),
                    "1": inputs(f, 1) and inputs(f, 0) and inputs(f, 2),
                }
            )
            for f in fs
        ],
        notes=[
            "All 8 combinations of 3 inputs, repeated 64 times. Repeated contacts reduce to the stated Boolean equations."
        ],
    )
    add(
        "parallel_series_rung_only",
        1,
        [0],
        truth,
        lambda fs: [row(**{"0": not inputs(f, 0) and not inputs(f, 2)}) for f in fs],
        notes=[
            "Only rung 0 executes. Original parenthesized parallel rung 1 is refused independently; no whole-project pass."
        ],
    )

    def increments(fs):
        word = 0
        result = []
        for frame in fs:
            word += 2 if inputs(frame, 0) else 0
            result.append([bool(word & (1 << bit)) for bit in range(16)])
        return result

    observers = []
    for bit in range(16):
        mask = 1 << bit if bit < 15 else -32768
        observers += [
            ["LD 1", f"[ %MW200 := %MW1 AND {mask} ]"],
            ["LD [ %MW200 <> 0 ]", f"ST %Q0.{bit}"],
        ]
    add(
        "duplicate_equations_increment_twice",
        2,
        [0, 1],
        random_frames(4096, [0], SEED + 2),
        increments,
        after=observers,
        notes=[
            "MW1 starts at zero; each enabled scan executes BOTH original increments. All 16 bits are exposed in Q0.0..15 via scratch MW200 after original rungs.",
            "4096 frames keep arithmetic below signed16 overflow; no hardware overflow behavior is inferred.",
        ],
    )
    add(
        "filename_multiply_actual_integer_assignment",
        3,
        [0, 1],
        random_frames(128, [0], SEED + 3),
        lambda fs: [row(**{"1": True, "2": False}) for _ in fs],
        notes=[
            "Despite its filename, the original contains integer MW0 := 1, not float multiplication. Inline OPER must preserve its true accumulator for Q0.1."
        ],
    )
    add(
        "filename_counters_actual_memory_identity",
        5,
        [0],
        random_frames(128, [0], SEED + 5),
        lambda fs: [row(**{"15": inputs(f, 0)}) for f in fs],
        before=[["LD %I0.0", "ST %M0"]],
        after=[["LD %M0", "ST %Q0.15"]],
        notes=[
            "Adapter seeds M0 from input 0 each scan and observes it at Q0.15. Original is a self-copy; no counter instruction exists and no native counter claim is made."
        ],
    )

    def action_after_coil(fs):
        assigned = False
        result = []
        for frame in fs:
            enabled = not inputs(frame, 13) or inputs(frame, 1)
            assigned = assigned or enabled
            result.append(row(**{"4": enabled, "15": assigned}))
        return result

    action_frames = [
        {"dt_ms": 10, "inputs": {"13": True, "1": False}},
        {"dt_ms": 10, "inputs": {"13": False, "1": False}},
        {"dt_ms": 10, "inputs": {"13": True, "1": False}},
        {"dt_ms": 10, "inputs": {"13": True, "1": True}},
    ] + random_frames(2044, [13, 1], SEED + 6)
    add(
        "correto_action_after_or_coil",
        6,
        [4],
        action_frames,
        action_after_coil,
        before=[["LD %I0.1", "ST %M4"]],
        after=[["LD [ %MW604 = 1 ]", "ST %Q0.15"]],
        notes=[
            "Adapter supplies external M4 through input 1 and observes persistent MW604 in Q0.15. Q0.4 = !I13 || I1. Original graphics for this rung are refused separately."
        ],
    )

    def latch(fs):
        running = False
        word10 = False
        result = []
        for frame in fs:
            running = (inputs(frame, 0) or running) and inputs(frame, 1)
            word10 = word10 or not inputs(frame, 16)
            result.append(row(**{"0": running, "15": word10}))
        return result

    latch_frames = [
        {"dt_ms": 10, "inputs": {"0": start, "1": permit, "16": inhibit_word}}
        for start, permit, inhibit_word in [
            (False, False, True),
            (True, True, True),
            (False, True, True),
            (False, False, False),
            (False, True, True),
            (True, False, True),
            (True, True, True),
        ]
    ] + random_frames(2041, [0, 1, 16], SEED + 7)
    add(
        "ladder_code_latch_and_word_actions",
        7,
        list(range(6)),
        latch_frames,
        latch,
        after=[["LD [ %MW10 = 1 ]", "ST %Q0.15"]],
        notes=[
            "Executes original rungs 0..5 in scan order. Oracle propagates the latch through MW11 and M1 to Q0.0; observes persistent MW10 at Q0.15.",
            "Other rungs include communication/timer configuration outside this isolated test; the entire project is not imported or executed.",
        ],
    )

    # Independent IEEE754 fixture calculation, without m200.numeric.read/write.
    # MF1 occupies words 1,2 and MF2 occupies words 2,3: these addresses overlap.
    image = bytearray(8)
    image[2:6] = struct.pack("<f", 1.0)
    image[4:8] = struct.pack("<f", 1.0)
    float1 = struct.unpack("<f", image[2:6])[0]
    float2 = struct.unpack("<f", image[4:8])[0]
    if (float1, float2) != (0.0, 1.0):
        raise AssertionError("independent float alias fixture failed")
    comparisons = {
        1: (operator.le, float2),
        2: (operator.gt, float2),
        3: (operator.ge, float2),
        4: (operator.ne, float2),
        5: (operator.eq, float2),
        21: (operator.lt, 1.0),
        22: (operator.le, 1.0),
        23: (operator.gt, 1.0),
        24: (operator.ge, 1.0),
        25: (operator.eq, 1.0),
        26: (operator.ne, 1.0),
    }
    for index, (compare, right) in comparisons.items():
        outcome = compare(float1, right)
        add(
            "float_comparison_rung_%02d" % index,
            8,
            [index],
            random_frames(512, [0], SEED + 800 + index),
            lambda fs, outcome=outcome: [
                row(**{"0": inputs(f, 0) and outcome, "15": True}) for f in fs
            ],
            before=[["LD 1", "[ %MF1 := 1.0 ]"], ["LD 1", "[ %MF2 := 1.0 ]"]],
            after=[["LD [ %MF1 = 0.0 ]", "ST %Q0.15"]],
            notes=[
                "Each scan adapter writes MF1=1.0 THEN MF2=1.0 at ORIGINAL word addresses. Shared word 2 makes MF1=0.0, MF2=1.0 (independent struct.pack/unpack oracle); Q0.15 observes that alias.",
                "Only the selected simple comparison executes; compound expressions are checked and refused independently.",
            ],
        )

    def generator(fs):
        q = False
        was_enabled = False
        deadline = None
        now = 0
        result = []
        for frame in fs:
            # Original Q0.0/Q0.1 read M30 BEFORE original timer rung 3 updates it.
            observed = row(
                **{
                    "0": inputs(frame, 1) and q,
                    "1": inputs(frame, 2) and q,
                    "2": inputs(frame, 3),
                    "4": inputs(frame, 4),
                    "5": inputs(frame, 5),
                }
            )
            enabled = not inputs(frame, 0)
            if enabled:
                q, deadline = True, None
            elif was_enabled:
                deadline = now + 25000
            if deadline is not None and now >= deadline:
                q, deadline = False, None
            observed[15] = q
            result.append(observed)
            was_enabled = enabled
            now += frame["dt_ms"]
        return result

    controlled = []
    for disabled, dt in [
        (True, 0),
        (False, 0),
        (True, 24999),
        (True, 1),
        (True, 0),
        (False, 0),
        (True, 25000),
        (True, 1),
    ]:
        controlled.append(
            {
                "dt_ms": dt,
                "inputs": {str(i): disabled if i == 0 else True for i in range(6)},
            }
        )
    frames = controlled + random_frames(
        1024 - len(controlled),
        range(6),
        SEED + 9,
        (0, 1, 10, 999, 1000, 24999, 25000, 25001, 3600000),
    )
    before = [
        [f"LD %I0.{source}", f"ST %M{target}"]
        for source, target in enumerate((40, 0, 10, 60, 4, 5))
    ]
    add(
        "power_generator_original_six_rungs_tof",
        9,
        list(range(6)),
        frames,
        generator,
        before=before,
        after=[["LD %M30", "ST %Q0.15"]],
        notes=[
            "All SIX original logic rungs execute with explicit original TM0 TOF, preset 25, base OneSecond (25000 ms). This is isolated logic, not whole-project import.",
            "Adapter seeds M40/M0/M10/M60/M4/M5 from inputs 0..5. Q0.15 observes M30 after timer update; Q0.0/Q0.1 retain original one-scan ordering.",
            "Controlled cases exercise initial disabled state, enable, falling edge, 24999/25000 ms expiry and restart, followed by seeded irregular scans. dt_ms advances time after the scan.",
        ],
    )
    return cases


def execute_case(case, output):
    destination = output / case["name"]
    destination.mkdir()
    program, frames = case["program"], case["frames"]
    validate(program)
    expected = case["oracle"](frames)
    source = destination / "reversed.cpp"
    source.write_text(to_cpp(program))
    write_json(destination / "isolated.il.json", program.as_dict())
    write_json(destination / "trace.json", frames)
    machine = Machine(program)
    vm = [machine.step(frame["inputs"], frame["dt_ms"]) for frame in frames]
    native = run_native(source, frames)
    rebuilt = compile_source(source)
    write_json(destination / "recompiled.il.json", rebuilt.as_dict())
    recompiled = Machine(rebuilt)
    roundtrip = [recompiled.step(frame["inputs"], frame["dt_ms"]) for frame in frames]
    observations = {
        "oracle": expected,
        "original_il_vm": vm,
        "reversed_cpp_native": native,
        "recompiled_il_vm": roundtrip,
    }
    write_json(destination / "observations.json", observations)
    mismatch = next(
        (
            index
            for index in range(len(frames))
            if any(
                observations[name][index] != expected[index] for name in observations
            )
        ),
        None,
    )
    report = {
        key: case[key]
        for key in (
            "name",
            "source",
            "selected_rungs",
            "original_rungs",
            "before",
            "after",
            "adapter_notes",
        )
    }
    report.update(
        {
            "status": "PASS" if mismatch is None else "FAIL",
            "frames": len(frames),
            "outputs_compared_per_frame": 16,
            "engines": list(observations),
            "first_mismatch": mismatch,
            "artifacts": str(destination),
            "meaning": "isolated original IL with explicit adapters; not whole-project/hardware validation",
        }
    )
    write_json(destination / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        args.output = Path(tempfile.mkdtemp(prefix="m200-public-"))
    elif args.output.exists() and any(args.output.iterdir()):
        parser.error(
            "--output must be absent or empty; original downloads are never an output directory"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    print("Public audit artifacts: " + str(args.output), flush=True)
    started = time.monotonic()
    report = {
        "format": "m200-public-results-v1",
        "status": "FAIL",
        "seed": SEED,
        "target": "TM200CE40T",
        "network_access": False,
        "originals_modified": False,
        "official_editor": "NOT TESTED",
        "physical_plc": "NOT TESTED",
        "sources": [],
        "cases": [],
        "failures": [],
    }
    manifest = json.loads((HERE / "manifest.json").read_text())
    corpus = {}
    try:
        for source in manifest["sources"]:
            item = inventory(source, args.corpus)
            corpus[source["id"]] = item
            report["sources"].append(item["report"])
        for case in cases_for(corpus):
            try:
                result = execute_case(case, args.output)
            except Exception as error:
                result = {
                    "name": case["name"],
                    "source": case["source"],
                    "selected_rungs": case["selected_rungs"],
                    "status": "FAIL",
                    "error": type(error).__name__ + ": " + str(error),
                    "frames": 0,
                }
            report["cases"].append(result)
            print(
                json.dumps({key: result[key] for key in ("name", "status", "frames")}),
                flush=True,
            )
        failed_cases = [
            case["name"] for case in report["cases"] if case["status"] != "PASS"
        ]
        if failed_cases:
            report["failures"].append({"runtime_cases": failed_cases})
        if (
            len(report["sources"]) != 10
            or sum(source["source"]["rungs"] for source in report["sources"]) != 119
        ):
            report["failures"].append("source/rung inventory coverage changed")
        if (
            len(report["cases"]) != 19
            or sum(case["frames"] for case in report["cases"]) != 16128
        ):
            report["failures"].append(
                "required 19 cases / 16128 frames were not executed"
            )
    except Exception as error:
        report["failures"].append(type(error).__name__ + ": " + str(error))
    finally:
        # Always repeat all original hashes, even after a runtime failure.
        identity = []
        for source in manifest["sources"]:
            try:
                data = verified_bytes(args.corpus / source["file"], source)
                identity.append(
                    {
                        "file": source["file"],
                        "status": "UNCHANGED",
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
            except Exception as error:
                report["failures"].append(
                    "final original identity check: " + str(error)
                )
        report["final_original_identity"] = identity
    report["frames_compared"] = sum(
        case["frames"] for case in report["cases"] if case["status"] == "PASS"
    )
    report["whole_projects_imported"] = 0
    report["whole_project_expected_import_refusals"] = len(report["sources"])
    report["whole_project_foreign_cpus"] = sum(
        source["original_cpu"] != report["target"] for source in report["sources"]
    )
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["status"] = "PASS" if not report["failures"] else "FAIL"
    write_json(args.output / "results.json", report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "frames_compared": report["frames_compared"],
                "whole_projects_imported": 0,
                "artifacts": str(args.output),
                "failures": report["failures"],
            }
        ),
        flush=True,
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
