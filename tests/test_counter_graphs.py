"""Exact graph/IL reconciliation, including aliases and observation order."""

import copy
import itertools
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.model import CompileError
from m200.counter_xml import check_graph

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    return json.loads(
        (ROOT / "tests/fixtures/native_counter_branch_graphs.json").read_text()
    )


def node(lines, entities):
    rung = ET.Element("RungEntity")
    graph = ET.SubElement(rung, "LadderElements")
    for typ, arg, row, col, connection in entities:
        item = ET.SubElement(graph, "LadderEntity")
        for k, v in [
            ("ElementType", typ),
            ("Descriptor", arg),
            ("Row", row),
            ("Column", col),
            ("ChosenConnection", connection),
        ]:
            ET.SubElement(item, k).text = str(v)
    il = ET.SubElement(rung, "InstructionLines")
    for line in lines:
        ET.SubElement(
            ET.SubElement(il, "InstructionLineEntity"), "InstructionLine"
        ).text = line
    ET.SubElement(rung, "IsLadderSelected").text = "true"
    return rung


def lines(rung):
    return [
        " ".join((e.text or "").split())
        for e in rung.findall("InstructionLines/InstructionLineEntity/InstructionLine")
    ]


class BooleanProofTests(unittest.TestCase):
    def test_bdd_operations_match_truth_tables_and_logical_equivalence(self):
        from m200.boolean_bdd import BDD

        b = BDD()
        x, y, z = [b.atom(i) for i in range(3)]
        expression = b.combine(
            "|", b.combine("&", x, b.negate(y)), b.combine("^", y, z)
        )
        for values in itertools.product([False, True], repeat=3):
            expected = (values[0] and not values[1]) or (values[1] != values[2])
            self.assertEqual(b.value(expression, dict(enumerate(values))), expected)
        self.assertEqual(
            b.negate(b.combine("&", x, y)), b.combine("|", b.negate(x), b.negate(y))
        )
        self.assertEqual(b.combine("^", x, x), 0)
        self.assertEqual(b.combine("|", x, b.negate(x)), 1)

    def test_deep_proof_does_not_depend_on_python_recursion_limit(self):
        from m200.boolean_bdd import BDD

        b = BDD()
        expression = 1
        for i in range(1500):
            expression = b.combine("&", expression, b.atom(i))
        negated = b.negate(expression)
        self.assertEqual(b.combine("|", expression, negated), 1)
        values = {i: True for i in range(1500)}
        self.assertTrue(b.value(expression, values))
        values[750] = False
        self.assertFalse(b.value(expression, values))
        self.assertTrue(b.value(negated, values))

    def test_proof_budget_is_an_explicit_tool_limitation(self):
        from m200.boolean_bdd import BDD

        b = BDD(node_limit=3)
        x = b.atom("x")
        y = b.atom("y")
        b.combine("&", x, y)
        with self.assertRaisesRegex(CompileError, "tool|prototype"):
            b.atom("z")


class CounterGraphTests(unittest.TestCase):
    def test_authentic_fanout_shared_prefix_and_independent_inputs_are_verified(self):
        for fixture in fixtures():
            with self.subTest(source=fixture["file"]):
                rung = ET.fromstring(fixture["rung_xml"])
                before = ET.tostring(rung)
                check_graph(rung, lines(rung))
                self.assertEqual(ET.tostring(rung), before)

    def test_raw_native_graph_import_to_cpp_and_export_is_real(self):
        from m200.project import load_project, write_project
        from m200.reverse import to_cpp
        from m200.frontend import compile_source

        for fixture in fixtures():
            with (
                self.subTest(source=fixture["file"]),
                tempfile.TemporaryDirectory() as folder,
            ):
                tree = ET.parse(ROOT / "tests/fixtures/synthetic.smbp")
                sw = tree.getroot().find("SoftwareConfiguration")
                configuration = ET.fromstring(fixture["configuration_xml"])
                for tag in ["Counters", "CountersMemoryAllocation"]:
                    old = sw.find(tag)
                    if old is not None:
                        sw.remove(old)
                    sw.append(configuration.find(tag))
                pous = sw.find("Pous")
                pous.clear()
                pou = ET.SubElement(pous, "ProgramOrganizationUnits")
                ET.SubElement(pou, "Name").text = "isolated original"
                ET.SubElement(pou, "SectionNumber").text = "1"
                rungs = ET.SubElement(pou, "Rungs")
                rungs.append(ET.fromstring(fixture["rung_xml"]))
                source = Path(folder) / "isolated.smbp"
                tree.write(source)
                program = load_project(source)
                self.assertEqual(program.rungs, [lines(rungs[0])])
                cpp = Path(folder) / "actual.cpp"
                cpp.write_text(to_cpp(program))
                rebuilt = compile_source(cpp)
                output = Path(folder) / "output.smbp"
                write_project(rebuilt, ROOT / "tests/fixtures/synthetic.smbp", output)
                self.assertEqual(load_project(output).counters, program.counters)

    def test_element_order_and_row_column_translations_do_not_change_logic(self):
        for fixture in fixtures():
            rung = ET.fromstring(fixture["rung_xml"])
            graph = rung.find("LadderElements")
            graph[:] = list(reversed(graph))
            for e in graph:
                e.find("Row").text = str(int(e.findtext("Row")) + 4)
            check_graph(rung, lines(rung))

    def test_unknown_overlapping_broken_and_logically_changed_graphs_fail(self):
        original = ET.fromstring(fixtures()[0]["rung_xml"])
        source = lines(original)

        def modify(field, value, kind=None):
            r = copy.deepcopy(original)
            e = next(
                e
                for e in r.find("LadderElements")
                if kind is None or e.findtext("ElementType") == kind
            )
            e.find(field).text = value
            return r

        cases = [
            modify("Descriptor", "%I0.1", "NormalContact"),
            modify("ElementType", "OpaqueCell"),
            modify("ChosenConnection", "North"),
            modify("Descriptor", "%C1", "Counter"),
            modify("Row", "-1"),
            modify("Column", "11"),
        ]
        duplicate = copy.deepcopy(original)
        duplicate.find("LadderElements").append(
            copy.deepcopy(duplicate.find("LadderElements")[0])
        )
        cases.append(duplicate)
        broken = copy.deepcopy(original)
        graph = broken.find("LadderElements")
        graph.remove(
            next(
                e
                for e in graph
                if e.findtext("Row") == "1" and e.findtext("Column") == "8"
            )
        )
        cases.append(broken)
        for i, rung in enumerate(cases):
            with self.subTest(mutation=i), self.assertRaises(CompileError):
                check_graph(rung, source)

    def test_shared_contact_before_reset_coil_is_not_reread_after_write(self):
        entities = [
            ("Counter", "%C0", 0, 2, "Left"),
            ("NormalContact", "%I0.0", 2, 0, "Left, Right"),
            ("Line", "", 2, 1, "Left, Right"),
            ("NormalContact", "%M0", 1, 4, "Left, Right"),
        ]
        entities += [("Line", "", 1, c, "Left, Right") for c in range(5, 9)]
        entities += [
            ("Line", "", 1, 9, "Down, Left, Right"),
            ("VerticalLine", "", 2, 9, "Up, Right"),
            ("ResetCoil", "%M0", 1, 10, "Left"),
            ("Coil", "%Q0.0", 2, 10, "Left"),
        ]
        good = [
            "BLK %C0",
            "LD %I0.0",
            "CU",
            "OUT_BLK",
            "LD D",
            "AND %M0",
            "MPS",
            "R %M0",
            "MPP",
            "ST %Q0.0",
            "END_BLK",
        ]
        check_graph(node(good, entities), good)
        bad = [
            "BLK %C0",
            "LD %I0.0",
            "CU",
            "OUT_BLK",
            "LD D",
            "AND %M0",
            "R %M0",
            "LD D",
            "AND %M0",
            "ST %Q0.0",
            "END_BLK",
        ]
        with self.assertRaises(CompileError):
            check_graph(node(bad, entities), bad)

    def test_shared_counter_flag_is_a_snapshot_across_counter_actions(self):
        entities = [
            ("Counter", "%C0", 0, 2, "Left"),
            ("NormalContact", "%C0.D", 0, 0, "Left, Right"),
            ("Line", "", 0, 1, "Down, Left, Right"),
            ("VerticalLine", "", 1, 1, "Up, Down"),
            ("VerticalLine", "", 2, 1, "Up, Right"),
        ]
        good = ["BLK %C0", "LD %C0.D", "MPS", "R", "MPP", "CU", "END_BLK"]
        check_graph(node(good, entities), good)
        bad = ["BLK %C0", "LD %C0.D", "R", "LD %C0.D", "CU", "END_BLK"]
        with self.assertRaises(CompileError):
            check_graph(node(bad, entities), bad)

    def test_counter_allocation_covers_sparse_native_identity_without_enum(self):
        from m200.counters import Counter
        from m200.model import Program
        from m200.project import write_project, load_project
        from m200.cli import report

        for counters, required in [
            ({}, 0),
            ({0: Counter(5)}, 1),
            ({0: Counter(5), 254: Counter(0)}, 255),
        ]:
            rung = (
                ["LD 1", "CU %C" + str(max(counters))]
                if counters
                else ["LD 1", "ST %Q0.0"]
            )
            p = Program([rung], counters=counters)
            with (
                self.subTest(required=required),
                tempfile.TemporaryDirectory() as folder,
            ):
                dest = Path(folder) / "allocation.smbp"
                write_project(p, ROOT / "tests/fixtures/synthetic.smbp", dest)
                allocation = (
                    ET.parse(dest)
                    .getroot()
                    .find("SoftwareConfiguration/CountersMemoryAllocation")
                )
                self.assertEqual(
                    allocation.findtext("ForcedCount"),
                    str(required) if required else None,
                )
                self.assertIsNone(allocation.find("Allocation"))
                self.assertEqual(load_project(dest).counters, counters)
                self.assertEqual(
                    report(p)["resources"].get("required_counter_allocation"), required
                )

    def test_absorbed_graph_resource_must_be_defined_in_actual_project(self):
        from m200.project import load_project

        source = ["BLK %C0", "LD %I0.0", "ANDN %I0.0", "CU", "END_BLK"]
        entities = [
            ("Counter", "%C0", 0, 6, "Left"),
            ("NormalContact", "%I0.0", 2, 0, "Left, Right"),
            ("NegatedContact", "%I0.0", 2, 1, "Left, Right"),
            ("NormalContact", "%C1.D", 2, 2, "Left, Right"),
        ] + [("Line", "", 2, i, "Left, Right") for i in range(3, 6)]

        def root(defined):
            tree = ET.parse(ROOT / "tests/fixtures/synthetic.smbp")
            sw = tree.getroot().find("SoftwareConfiguration")
            counters = sw.find("Counters")
            for index in range(2 if defined else 1):
                counter = ET.SubElement(counters, "Counter")
                for k, v in [
                    ("Address", f"%C{index}"),
                    ("Index", index),
                    ("Preset", 1),
                ]:
                    ET.SubElement(counter, k).text = str(v)
            pous = sw.find("Pous")
            pous.clear()
            pou = ET.SubElement(pous, "ProgramOrganizationUnits")
            ET.SubElement(pou, "Name").text = "isolated"
            ET.SubElement(pou, "SectionNumber").text = "1"
            ET.SubElement(pou, "Rungs").append(node(source, entities))
            return tree

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.smbp"
            root(False).write(path)
            with self.assertRaisesRegex(CompileError, "undefined|configuration"):
                load_project(path)
            root(True).write(path)
            self.assertEqual(len(load_project(path).counters), 2)

    def test_unknown_graph_text_is_never_discarded_by_proof(self):
        fixture = fixtures()[0]
        for mode in ["empty", "container", "entity", "tail"]:
            r = ET.fromstring(fixture["rung_xml"])
            graph = r.find("LadderElements")
            if mode == "empty":
                graph.clear()
                graph.text = "UNKNOWN_GRAPH"
                r.find("IsLadderSelected").text = "false"
            elif mode == "container":
                graph.text = "UNKNOWN_GRAPH"
            elif mode == "entity":
                graph[0].text = "UNKNOWN_GRAPH"
            else:
                graph[0].tail = "UNKNOWN_GRAPH"
            with self.subTest(mode=mode), self.assertRaises(CompileError):
                check_graph(r, lines(r))

    def test_output_contact_observes_preceding_coil_and_bit_alias(self):
        entities = [
            ("Counter", "%C0", 0, 2, "Left"),
            ("NormalContact", "%I0.0", 2, 0, "Left, Right"),
            ("Line", "", 2, 1, "Left, Right"),
        ]
        entities += [("Line", "", 1, c, "Left, Right") for c in range(4, 7)]
        entities += [
            ("Line", "", 1, 7, "Down, Left, Right"),
            ("Line", "", 1, 8, "Left, Right"),
            ("Line", "", 1, 9, "Left, Right"),
            ("Coil", "%M00", 1, 10, "Left"),
            ("VerticalLine", "", 2, 7, "Up, Right"),
            ("NormalContact", "%M0", 2, 8, "Left, Right"),
            ("Line", "", 2, 9, "Left, Right"),
            ("Coil", "%Q0.0", 2, 10, "Left"),
        ]
        good = [
            "BLK %C0",
            "LD %I0.0",
            "CU",
            "OUT_BLK",
            "LD D",
            "ST %M0",
            "AND %M0",
            "ST %Q0.0",
            "END_BLK",
        ]
        check_graph(node(good, entities), good)
        bad = good.copy()
        bad[7] = "ANDN %M0"
        with self.assertRaises(CompileError):
            check_graph(node(bad, entities), bad)

    def test_parallel_branches_can_prove_xor_without_matching_il_spelling(self):
        entities = [
            ("Counter", "%C0", 0, 6, "Left"),
            ("NormalContact", "%I0.0", 2, 0, "Left, Right"),
            ("NegatedContact", "%I0.1", 2, 1, "Left, Right"),
            ("NegatedContact", "%I0.0", 3, 0, "Left, Right"),
            ("NormalContact", "%I0.1", 3, 1, "Left, Right"),
        ]
        entities += [
            ("Line", "", row, col, "Left, Right")
            for row in (2, 3)
            for col in range(2, 5)
        ]
        entities += [
            ("Line", "", 2, 5, "Down, Left, Right"),
            ("VerticalLine", "", 3, 5, "Up, Left"),
        ]
        good = ["BLK %C0", "LD %I0.0", "XOR %I0.1", "CU", "END_BLK"]
        check_graph(node(good, entities), good)
        bad = good.copy()
        bad[2] = "OR %I0.1"
        with self.assertRaises(CompileError):
            check_graph(node(bad, entities), bad)

    def test_unconnected_wire_cycle_is_not_ignored_as_decoration(self):
        r = ET.fromstring(fixtures()[0]["rung_xml"])
        graph = r.find("LadderElements")
        extra = node(
            [],
            [
                ("Line", "", 20, 4, "Down, Right"),
                ("Line", "", 20, 5, "Down, Left"),
                ("VerticalLine", "", 21, 4, "Up, Right"),
                ("VerticalLine", "", 21, 5, "Up, Left"),
            ],
        )
        graph.extend(extra.find("LadderElements"))
        with self.assertRaisesRegex(CompileError, "unused|unpowered"):
            check_graph(r, lines(r))

    def test_comparison_effects_remain_explicitly_gated(self):
        r = ET.fromstring(fixtures()[2]["rung_xml"])
        graph = r.find("LadderElements")
        e = next(e for e in graph if e.findtext("ElementType") == "NormalContact")
        e.find("ElementType").text = "Comparison"
        e.find("Descriptor").text = ""
        ET.SubElement(e, "ComparisonExpression").text = "%MW0[%MW1]>0"
        with self.assertRaisesRegex(CompileError, "comparison|normaliz"):
            check_graph(r, lines(r))

    def test_communication_bool_contacts_remain_supported_in_counter_graphs(self):
        from m200.counter_xml import graphics
        from m200.counters import Counter
        from m200.model import Program
        from m200.modbus import ModbusConfig
        from m200.project import write_project, load_project
        from test_communication_xml import serial

        for kind in ["READ_VAR", "WRITE_VAR", "WRITE_READ_VAR"]:
            for field in ["DONE", "BUSY", "ABORTED", "ERROR"]:
                source = ["BLK %C0", f"LD %{kind}0.{field}", "CU", "END_BLK"]
                check_graph(node(source, graphics(source)), source)
        source = ["BLK %C0", "LD %READ_VAR0.DONE", "CU", "END_BLK"]
        p = Program(
            [["BLK %READ_VAR0", "LD %I0.0", "EXECUTE", "END_BLK"], source],
            counters={0: Counter(1)},
            communications={"%READ_VAR0": ModbusConfig()},
        )
        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder) / "template.smbp"
            dest = Path(folder) / "result.smbp"
            tree = ET.parse(ROOT / "tests/fixtures/synthetic.smbp")
            tree.getroot().find("HardwareConfiguration/Plc").append(serial())
            tree.write(template)
            write_project(p, template, dest)
            self.assertEqual(load_project(dest).communications, p.communications)

    def test_absorbed_communication_status_still_requires_its_configuration(self):
        source = ["BLK %C0", "LD %I0.0", "ANDN %I0.0", "CU", "END_BLK"]
        entities = [
            ("Counter", "%C0", 0, 6, "Left"),
            ("NormalContact", "%I0.0", 2, 0, "Left, Right"),
            ("NegatedContact", "%I0.0", 2, 1, "Left, Right"),
            ("NormalContact", "%READ_VAR0.DONE", 2, 2, "Left, Right"),
        ] + [("Line", "", 2, i, "Left, Right") for i in range(3, 6)]
        with self.assertRaises(CompileError):
            check_graph(node(source, entities), source, {("C", 0)})
        check_graph(node(source, entities), source, {("C", 0), ("COMM", "%READ_VAR0")})


class BooleanOperationBudgetTests(unittest.TestCase):
    def test_simplified_operations_obey_the_same_proof_budget(self):
        from m200.boolean_bdd import BDD

        b = BDD(operation_limit=1)
        x = b.atom("x")
        self.assertEqual(b.combine("&", x, 1), x)
        with self.assertRaisesRegex(CompileError, "tool|prototype"):
            b.combine("|", x, 0)
