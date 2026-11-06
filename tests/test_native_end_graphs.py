"""Authentic END-family graph bindings; no simulator or hardware certification."""

import copy
import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp

FIXTURES = Path(__file__).parent / "fixtures"
PINS = {
    "END": (86370, "11b4772aab31b5759ebf5a0315125cd4f1f0005dd0bad943c64de9af9eb2ea31"),
    "ENDC": (86629, "10d49746b54f4b8ef14dee3a51e8f08607aabebc5e142ade76f3643a1369451f"),
    "ENDCN": (
        86644,
        "5c76b1dabede9dc85c2c155f01c00d981262d804c150ccb7a7efbc07ba0496dc",
    ),
}


def fixture(op):
    return FIXTURES / ("official_tm200ce40t_" + op.lower() + ".smbp")


def semantic(node):
    return (
        node.tag,
        sorted(node.attrib.items()),
        (node.text or "").strip(),
        [semantic(c) for c in node],
    )


class NativeEndGraphTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def tree(self, op="ENDC"):
        return ET.parse(fixture(op))

    def load(self, tree):
        path = self.work / "case.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return load_project(path)

    def rejected(self, tree):
        with self.assertRaises(CompileError):
            self.load(tree)

    def test_authentic_fixture_bytes_provenance_and_crlf_are_preserved(self):
        for op, (size, expected) in PINS.items():
            with self.subTest(op=op):
                path = fixture(op)
                data = path.read_bytes()
                provenance = json.loads(
                    path.with_suffix(".provenance.json").read_text()
                )
                self.assertEqual(len(data), size)
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected)
                self.assertEqual(provenance["sha256"], expected)
                self.assertEqual(provenance["bytes"], size)
                self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
                self.assertGreater(data.count(b"\r\n"), 2000)

    def test_all_three_authentic_official_saved_bindings_import(self):
        for op in PINS:
            with self.subTest(op=op):
                program = load_project(fixture(op))
                self.assertEqual(
                    program.rungs, [[op]] if op == "END" else [["LD %M0", op]]
                )
                self.assertFalse(program.metadata["synthetic_template"])

    def test_authentic_fixtures_retain_the_typed_hardware_tree(self):
        baseline = ET.parse(FIXTURES / "official_tm200ce40t_memory.smbp")
        hardware = semantic(baseline.find("HardwareConfiguration"))
        for op in PINS:
            with self.subTest(op=op):
                self.assertEqual(
                    semantic(self.tree(op).find("HardwareConfiguration")), hardware
                )

    def test_authentic_end_graphs_preserve_writes_reverse_cpp_and_jump_export(self):
        for op in PINS:
            with self.subTest(op=op):
                # Surround an untouched authentic END rung with existing graph forms.
                base = Program(
                    [
                        ["LD %I0.0", "ST %M0"],
                        ["LD %I0.1", "ST %Q0.0"],
                        ["LD %I0.1", "[INC %MW200]"],
                        ["LD %I0.1", "ST %Q0.1"],
                        ["LD %I0.1", "[INC %MW201]"],
                    ]
                )
                path = self.work / (op + ".smbp")
                write_project(base, fixture(op), path)
                tree = ET.parse(path)
                tree.find(".//Rungs").insert(
                    3, copy.deepcopy(self.tree(op).find(".//RungEntity"))
                )
                tree.write(path, encoding="utf-8", xml_declaration=True)
                program = load_project(path)
                exit_when = op != "ENDCN"
                frames = [
                    {"inputs": {0: gate, 1: payload}}
                    for gate, payload in (
                        (exit_when, True),
                        (not exit_when, True),
                        (exit_when, False),
                        (not exit_when, False),
                    )
                ]
                expected = [
                    [True, False],
                    [True, op != "END"],
                    [False, op != "END"],
                    [False, False],
                ]
                pre = [1, 2, 2, 2]
                post = [0, 0, 0, 0] if op == "END" else [0, 1, 1, 1]

                def check(candidate):
                    machine = Machine(candidate)
                    rows = []
                    for i, frame in enumerate(frames):
                        row = machine.step(frame["inputs"])
                        self.assertEqual(row, expected[i] + [False] * 14)
                        self.assertEqual(
                            (machine.words[200], machine.words[201]), (pre[i], post[i])
                        )
                        rows.append(row)
                    return rows

                rows = check(program)
                check(normalize(program))
                source = self.work / (op + ".cpp")
                source.write_text(to_cpp(program))
                self.assertEqual(run_native(source, frames), rows)
                # Observe exact small counter values outside the returning function.
                wrapper = self.work / (op + "_word_observer.cpp")
                wrapper.write_text(
                    "#define scan imported_scan\n#include "
                    + json.dumps(str(source))
                    + "\n#undef scan\nvoid scan(){imported_scan();"
                    + "plc::write_output_bits_i16(8,8,(plc::i16)(plc::read_word(200)"
                    + "|(plc::read_word(201)<<4)));}\n"
                )
                observed = [
                    row[:8]
                    + [bool(a & (1 << bit)) for bit in range(4)]
                    + [bool(b & (1 << bit)) for bit in range(4)]
                    for row, a, b in zip(rows, pre, post)
                ]
                self.assertEqual(run_native(wrapper, frames), observed)
                rebuilt = compile_source(source)
                check(rebuilt)
                exported = self.work / (op + "_exported.smbp")
                write_project(rebuilt, fixture(op), exported)
                check(load_project(exported))
                types = [n.text for n in ET.parse(exported).findall(".//ElementType")]
                self.assertIn("Jump", types)
                self.assertNotIn("End", types)
                self.assertNotIn("EndCn", types)

    def test_conditional_end_type_cannot_be_swapped(self):
        for op, forged in (("ENDC", "EndCn"), ("ENDCN", "End"), ("END", "EndCn")):
            with self.subTest(op=op):
                tree = self.tree(op)
                tree.find(".//LadderElements")[-1].find("ElementType").text = forged
                self.rejected(tree)

    def test_unconditional_opcode_cannot_hide_behind_a_conditional_graph(self):
        tree = self.tree()
        tree.findall(".//InstructionLine")[-1].text = "END"
        self.rejected(tree)
        tree = self.tree("END")
        instructions = tree.find(".//InstructionLines")
        item = ET.Element("InstructionLineEntity")
        ET.SubElement(item, "InstructionLine").text = "LD %M0"
        instructions.insert(0, item)
        instructions[-1].find("InstructionLine").text = "ENDC"
        self.rejected(tree)

    def test_condition_polarity_and_address_must_agree(self):
        for forged in ("LDN %M0", "LDR %M0", "LD %M1"):
            with self.subTest(instruction=forged):
                tree = self.tree()
                tree.findall(".//InstructionLine")[0].text = forged
                self.rejected(tree)

    def test_existing_series_contacts_compose_with_the_observed_terminal(self):
        for op in ("ENDC", "ENDCN"):
            with self.subTest(op=op):
                tree = self.tree(op)
                graph = tree.find(".//LadderElements")
                contact = copy.deepcopy(graph[0])
                contact.find("ElementType").text = "NegatedContact"
                contact.find("Descriptor").text = "%M1"
                contact.find("Column").text = "1"
                graph.remove(graph[1])
                graph.insert(1, contact)
                instructions = tree.find(".//InstructionLines")
                item = ET.Element("InstructionLineEntity")
                ET.SubElement(item, "InstructionLine").text = "ANDN %M1"
                instructions.insert(1, item)
                self.assertEqual(self.load(tree).rungs, [["LD %M0", "ANDN %M1", op]])

    def test_terminal_descriptor_must_be_empty(self):
        for op in PINS:
            for descriptor in ("%M0", "%L0", "ENDC", " "):
                with self.subTest(op=op, descriptor=descriptor):
                    tree = self.tree(op)
                    tree.find(".//LadderElements")[-1].find(
                        "Descriptor"
                    ).text = descriptor
                    self.rejected(tree)

    def test_terminal_connections_and_columns_are_closed(self):
        for field, value in (
            ("ChosenConnection", "Left, Right"),
            ("ChosenConnection", "Right"),
            ("Column", "9"),
            ("Column", "11"),
            ("Row", "1"),
        ):
            with self.subTest(field=field, value=value):
                tree = self.tree()
                tree.find(".//LadderElements")[-1].find(field).text = value
                self.rejected(tree)

    def test_wire_missing_duplicate_or_disconnected_is_rejected(self):
        for action in ("missing", "duplicate", "disconnected", "descriptor"):
            with self.subTest(action=action):
                tree = self.tree()
                graph = tree.find(".//LadderElements")
                if action == "missing":
                    graph.remove(graph[5])
                elif action == "duplicate":
                    graph.insert(5, copy.deepcopy(graph[5]))
                elif action == "disconnected":
                    graph[5].find("ChosenConnection").text = "Left"
                else:
                    graph[5].find("Descriptor").text = "%M0"
                self.rejected(tree)

    def test_whole_row_translation_remains_outside_observed_end_profile(self):
        tree = self.tree()
        for node in tree.findall(".//LadderEntity/Row"):
            node.text = "1"
        self.rejected(tree)

    def test_unknown_terminal_type_fields_and_attributes_are_rejected(self):
        for action in ("type", "field", "attribute", "scalar_attribute", "duplicate"):
            with self.subTest(action=action):
                tree = self.tree()
                terminal = tree.find(".//LadderElements")[-1]
                if action == "type":
                    terminal.find("ElementType").text = "EndC"
                elif action == "field":
                    ET.SubElement(terminal, "RuntimeMode").text = "ENDC"
                elif action == "attribute":
                    terminal.set("RuntimeMode", "ENDC")
                elif action == "scalar_attribute":
                    terminal.find("ElementType").set("Mode", "ENDC")
                else:
                    ET.SubElement(terminal, "Descriptor").text = "%M0"
                self.rejected(tree)

    def test_selected_false_does_not_bypass_nonempty_graph_consistency(self):
        tree = self.tree()
        tree.find(".//IsLadderSelected").text = "false"
        tree.find(".//LadderElements")[-1].find("ElementType").text = "EndCn"
        self.rejected(tree)

    def test_empty_graph_is_only_allowed_when_ladder_is_not_selected(self):
        for op in PINS:
            tree = self.tree(op)
            tree.find(".//LadderElements").clear()
            self.rejected(tree)
            tree.find(".//IsLadderSelected").text = "false"
            self.assertEqual(
                self.load(tree).rungs, [[op]] if op == "END" else [["LD %M0", op]]
            )

    def test_empty_unselected_graph_cannot_hide_unknown_attributes(self):
        for element in (".//RungEntity", ".//LadderElements"):
            with self.subTest(element=element):
                tree = self.tree()
                tree.find(".//LadderElements").clear()
                tree.find(".//IsLadderSelected").text = "false"
                tree.find(element).set("RuntimeMode", "ENDC")
                self.rejected(tree)

    def test_graph_terminal_cannot_be_coil_or_nonterminal_action_sequence(self):
        tree = self.tree()
        tree.find(".//LadderElements")[-1].find("ElementType").text = "Coil"
        self.rejected(tree)
        tree = self.tree()
        instructions = tree.find(".//InstructionLines")
        item = ET.SubElement(instructions, "InstructionLineEntity")
        ET.SubElement(item, "InstructionLine").text = "ST %M1"
        self.rejected(tree)
        tree = self.tree()
        tree.findall(".//InstructionLine")[-1].text = "ST %M1"
        self.rejected(tree)


if __name__ == "__main__":
    unittest.main()
