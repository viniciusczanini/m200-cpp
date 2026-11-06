#!/usr/bin/env python3
"""Raw Counter graph import, exhaustive predicate mutations and runtime roundtrips."""

# ruff: noqa: E402
import argparse
import copy
import hashlib
import itertools
import json
import random
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
from test_counter_graphs import node, lines
from counters import oracle, view
from expression_edges import verify
from m200.model import Program, CompileError
from m200.counters import Counter
from m200.counter_xml import check_graph, write_configs
from m200.project import load_project

SEED = 20020261119


def imported(rung, work, name, counters=None, configuration=None):
    tree = ET.parse(ROOT / "tests/fixtures/synthetic.smbp")
    sw = tree.getroot().find("SoftwareConfiguration")
    if configuration is None:
        write_configs(Program(counters=counters), sw)
    else:
        for tag in ["Counters", "CountersMemoryAllocation"]:
            old = sw.find(tag)
            if old is not None:
                sw.remove(old)
            item = configuration.find(tag)
            if item is not None:
                sw.append(copy.deepcopy(item))
    pous = sw.find("Pous")
    pous.clear()
    pou = ET.SubElement(pous, "ProgramOrganizationUnits")
    ET.SubElement(pou, "Name").text = "isolated graph test"
    ET.SubElement(pou, "SectionNumber").text = "1"
    ET.SubElement(pou, "Rungs").append(copy.deepcopy(rung))
    path = work / (name + "_raw_graph.smbp")
    tree.write(path)
    return load_project(path)


def truth(branches, values):
    return any(
        all(bool(values[key]) == positive for key, positive in branch)
        for branch in branches
    )


def generated(case):
    rng = random.Random(SEED + case)
    index = [0, 31, 254][case % 3]
    base = [0, 3, 8][case % 3]
    column = 2 + case % 5
    branch_count = 1 + case % 4
    fan = 1 + case // 4
    feedback = case % 2 == 1
    branches = []
    for branch in range(branch_count):
        terms = [
            (rng.randrange(6), bool(rng.getrandbits(1)))
            for _ in range(rng.randint(1, column - 1))
        ]
        if case % 3 == 1 and branch == 0:
            terms[0] = (7, bool(case % 2))
        if case % 7 == 0 and branch == 0:
            terms[0] = (6, True)
        branches.append(terms)

    def descriptor(key):
        return f"%I0.{key}" if key < 6 else "%Q0.0" if key == 6 else f"%C{index}.D"

    entities = [
        ("Counter", f"%C{index}", base, column, "Left"),
        ("NormalContact", "%I0.23", base, 0, "Left, Right"),
    ] + [("Line", "", base, c, "Left, Right") for c in range(1, column)]
    mutations = []
    for j, terms in enumerate(branches):
        row = base + 2 + j
        for k, (key, positive) in enumerate(terms):
            mutations.append((j, k, len(entities)))
            entities.append(
                (
                    "NormalContact" if positive else "NegatedContact",
                    descriptor(key),
                    row,
                    k,
                    "Left, Right",
                )
            )
        entities += [
            ("Line", "", row, c, "Left, Right") for c in range(len(terms), column - 1)
        ]
        connection = (
            "Left, Right"
            if branch_count == 1
            else "Down, Left, Right"
            if j == 0
            else "Up, Left"
            if j == branch_count - 1
            else "Up, Down, Left"
        )
        entities.append(
            ("Line" if j == 0 else "VerticalLine", "", row, column - 1, connection)
        )
    entities.append(
        (
            "NormalContact",
            "%Q0.0" if feedback else "%I0.17",
            base + 1,
            column + 2,
            "Left, Right",
        )
    )
    entities += [("Line", "", base + 1, c, "Left, Right") for c in range(column + 3, 9)]
    entities.append(
        ("Line", "", base + 1, 9, "Left, Right" if fan == 1 else "Down, Left, Right")
    )
    actions = []
    for q in range(fan):
        typ = (
            "ResetCoil"
            if feedback and q == 0
            else ["Coil", "SetCoil", "ResetCoil"][q % 3]
        )
        actions.append({"Coil": "ST", "SetCoil": "S", "ResetCoil": "R"}[typ])
        entities.append((typ, f"%Q0.{q}", base + 1 + q, 10, "Left"))
        if q:
            entities.append(
                (
                    "VerticalLine",
                    "",
                    base + 1 + q,
                    9,
                    "Up, Right" if q == fan - 1 else "Up, Down, Right",
                )
            )
    il = [f"BLK %C{index}", "LD %I0.23", "R"]
    for j, terms in enumerate(branches):
        key, positive = terms[0]
        prefix = "LD" if j == 0 else "OR("
        if j == 0:
            il.append(("LD " if positive else "LDN ") + descriptor(key))
        else:
            il.append(prefix + " " + descriptor(key))
            if not positive:
                il.append("N")
        il += [
            ("AND " if positive else "ANDN ") + descriptor(key)
            for key, positive in terms[1:]
        ]
        if j:
            il.append(")")
    il += ["CU", "OUT_BLK", "LD D", "AND " + ("%Q0.0" if feedback else "%I0.17")]
    if fan > 1:
        il.append("MPS")
    for q, action in enumerate(actions):
        if q:
            il.append("MPP" if q == fan - 1 else "MRD")
        il.append(action + f" %Q0.{q}")
    il.append("END_BLK")
    return node(il, entities), branches, mutations, index, actions, feedback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    args = parser.parse_args()
    rng = random.Random(SEED)
    values = (
        [0, (1 << 24) - 1]
        + [1 << i for i in range(24)]
        + [((1 << 24) - 1) ^ (1 << i) for i in range(24)]
    )
    values += [rng.randrange(1 << 24) for _ in range(512 - len(values))]
    all_frames = [
        {"inputs": {i: bool(raw & (1 << i)) for i in range(24)}} for raw in values
    ]
    results = []
    mutation_counts = {"equivalent": 0, "different": 0, "structurally_invalid": 0}
    truth_checks = 0
    assignments = list(itertools.product([False, True], repeat=8))
    with tempfile.TemporaryDirectory(prefix="m200-counter-graphs-") as folder:
        work = Path(folder)
        for case in range(32):
            name = f"generated_{case}"
            if args.case is not None and args.case != name:
                continue
            rung, branches, mutations, index, actions, feedback = generated(case)
            source = lines(rung)
            statistics = check_graph(rung, source)
            for branch, term, cell in mutations:
                changed = copy.deepcopy(branches)
                key, positive = changed[branch][term]
                changed[branch][term] = (key, not positive)
                matches = [
                    truth(branches, assignment) == truth(changed, assignment)
                    for assignment in assignments
                ]
                equivalent = all(matches)
                truth_checks += len(matches)
                altered = copy.deepcopy(rung)
                entry = altered.find("LadderElements")[cell]
                entry.find("ElementType").text = (
                    "NegatedContact" if positive else "NormalContact"
                )
                if equivalent:
                    check_graph(altered, source)
                    mutation_counts["equivalent"] += 1
                else:
                    try:
                        check_graph(altered, source)
                    except CompileError:
                        mutation_counts["different"] += 1
                    else:
                        raise AssertionError("accepted changed input truth function")
            for mutation in range(3):
                altered = copy.deepcopy(rung)
                graph = altered.find("LadderElements")
                if mutation == 0:
                    graph.append(copy.deepcopy(graph[0]))
                elif mutation == 1:
                    graph[1].find("ChosenConnection").text = "North"
                else:
                    graph.remove(
                        next(
                            e
                            for e in graph
                            if e.findtext("ElementType") == "Line"
                            and e.findtext("Row") == str([0, 3, 8][case % 3])
                            and e.findtext("Column") == "1"
                        )
                    )
                try:
                    check_graph(altered, source)
                except CompileError:
                    mutation_counts["structurally_invalid"] += 1
                else:
                    raise AssertionError("accepted malformed graph")
            graph = rung.find("LadderElements")
            entries = list(graph)
            rng.shuffle(entries)
            graph[:] = entries
            loaded = imported(rung, work, name, counters={index: Counter(1)})
            prefix = [
                ["LD %S13", f"S %Q0.{q}"]
                for q, action in enumerate(actions)
                if action == "R"
            ]
            p = Program(
                prefix + loaded.rungs + [["LD %I0.18", f"[%Q0.0:16:=%C{index}.V]"]],
                counters=loaded.counters,
            )
            expected = []
            outputs = [False] * 16
            current = 0
            previous = False
            for n, raw in enumerate(values[:256]):
                if n == 0:
                    for q, action in enumerate(actions):
                        if action == "R":
                            outputs[q] = True
                reset = bool(raw & (1 << 23))
                if reset:
                    current = 0
                done = current == 1 and not reset
                assignment = [bool(raw & (1 << bit)) for bit in range(6)] + [
                    outputs[0],
                    done,
                ]
                up = truth(branches, assignment)
                if up and not previous and not reset:
                    current += 1
                previous = up
                done = current == 1 and not reset
                power = done and (outputs[0] if feedback else bool(raw & (1 << 17)))
                for q, action in enumerate(actions):
                    outputs[q] = (
                        power
                        if action == "ST"
                        else (outputs[q] or power)
                        if action == "S"
                        else (outputs[q] and not power)
                    )
                if raw & (1 << 18):
                    outputs = [bool(current & (1 << i)) for i in range(16)]
                expected.append(list(outputs))
            verify(p, all_frames[:256], expected, work, name)
            results.append(dict(case=name, scans=256, status="pass", proof=statistics))
            print(f"PASS: {name} / 256 scans", flush=True)
        manifest = json.loads(
            (ROOT / "docs/capabilities/COUNTER-SOURCES.json").read_text()
        )
        for file, rung_index, name in [
            ("Project1_Part1B.smbp", 2, "public_B"),
            ("car_garage.smbp", 0, "public_C"),
            ("starting_motors.smbp", 12, "public_M"),
        ]:
            if args.case is not None and args.case != name:
                continue
            source = next(row for row in manifest["sources"] if row["file"] == file)
            raw = (ROOT / "research/downloads/counter-sources" / file).read_bytes()
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise AssertionError("original digest changed")
            root = ET.fromstring(raw)
            rung = root.findall(".//RungEntity")[rung_index]
            configuration = root.find("SoftwareConfiguration")
            loaded = imported(rung, work, name, configuration=configuration)
            state, command = oracle(loaded.counters[0].preset)
            expected = []
            if name == "public_B":
                suffix = [
                    ["LD %Q0.1"] + [f"AND %Q0.{i}" for i in range(2, 8)] + ["ST %M900"],
                    ["LD %Q0.1"] + [f"OR %Q0.{i}" for i in range(2, 8)] + ["ST %M901"],
                    ["LD 1", "[%Q0.0:16:=%C0.V]"],
                    ["LD %M900", "ST %Q0.14"],
                    ["LD %M901", "ST %Q0.15"],
                ]
                p = Program(loaded.rungs + suffix, counters=loaded.counters)
                for raw in values:
                    command("u", bool(raw & 1))
                    expected.append(view(state["v"], state["d"], state["d"]))
            elif name == "public_C":
                p = Program(
                    loaded.rungs
                    + [
                        ["LD 1", "[%Q0.0:16:=%C0.V]"],
                        ["LD %C0.D", "ST %Q0.14"],
                        ["LD %C0.E", "ST %Q0.15"],
                    ],
                    counters=loaded.counters,
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
                    ]
                    + loaded.rungs
                    + [
                        ["LD 1", "[%Q0.0:16:=%C0.V]"],
                        ["LD %M22", "ST %Q0.14"],
                        ["LD %C0.E", "ST %Q0.15"],
                    ],
                    counters=loaded.counters,
                )
                feedback = True
                for raw in values:
                    command("r", bool(raw & 1) and feedback)
                    command("u", bool(raw & 1) and bool(raw & 2))
                    feedback = state["d"]
                    expected.append(view(state["v"], feedback, state["e"]))
            verify(p, all_frames, expected, work, name)
            results.append(
                dict(
                    case=name,
                    scans=512,
                    status="pass",
                    source_sha256=source["sha256"],
                    rung=rung_index,
                    scope="complete original graph/IL imported in declared synthetic envelope; original CPU/file untouched; explicit runtime harness; Counter physical policy pending",
                )
            )
            print(f"PASS: {name} / 512 scans", flush=True)
    if args.case is not None and not results:
        raise AssertionError("unknown graph case")
    files = sorted((ROOT / "m200").glob("*.py")) + [
        ROOT / "sdk/plc.hpp",
        Path(__file__),
        ROOT / "tests/test_counter_graphs.py",
        ROOT / "tests/stress/counters.py",
        ROOT / "tests/stress/expression_edges.py",
        ROOT / "tests/stress/bit_objects.py",
        ROOT / "docs/capabilities/COUNTER-SOURCES.json",
        ROOT / "tests/fixtures/synthetic.smbp",
    ]
    report = dict(
        seed=SEED,
        target="TM200CE40T",
        cases=results,
        scans=sum(row["scans"] for row in results),
        predicate_mutations=mutation_counts,
        truth_assignments_checked=truth_checks,
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
        whole_foreign_projects_imported=0,
        originals_modified=False,
        official_editor="pending",
        physical_plc="pending",
        counter_semantics="same provisional policy; graph proof does not establish hardware flag behavior",
    )
    if args.case is None:
        (ROOT / "docs/validation/COUNTER-GRAPH-STRESS-RESULTS.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(
        f"PASS: {len(results)} cases / {report['scans']} scans; exact predicate mutations {mutation_counts}; raw graph import and real exported C++ roundtrip",
        flush=True,
    )


if __name__ == "__main__":
    main()
