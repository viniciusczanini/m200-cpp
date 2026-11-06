"""Isolated SR-call graph binding; no whole-project admission or execution."""

import copy
import hashlib
import itertools
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError
from m200.subroutine_graph import (
    SubroutineCall,
    graphics,
    parse_call,
    read_graph,
    write_graph,
)

ROOT = Path(__file__).resolve().parents[1]
SAVES = (
    (0, "sr0", "49438bcbed59cde889547869d8c033f377dfb7e60153136a57cb48e135b0e21a"),
    (63, "sr63", "ff05369c686e8bc1887612afdbfcfd57d24e0e4e1e51d8d2b2b443824a2fa652"),
)


def native_path(label):
    return (
        ROOT / "tests/fixtures" / ("official_tm200ce40t_subroutine_" + label + ".smbp")
    )


def rung(number=0, with_graph=True):
    node = ET.Element("RungEntity")
    if with_graph:
        ET.SubElement(node, "LadderElements")
    il = ET.SubElement(node, "InstructionLines")
    for text in ("LD %I0.0", "SR" + str(number)):
        entry = ET.SubElement(il, "InstructionLineEntity")
        ET.SubElement(entry, "InstructionLine").text = text
        ET.SubElement(entry, "Comment")
    for tag, text in [
        ("Name", "call"),
        ("MainComment", "operator note"),
        ("Label", ""),
        ("IsLadderSelected", "false"),
    ]:
        ET.SubElement(node, tag).text = text
    return node


class SubroutineGraphTests(unittest.TestCase):
    def reject_without_mutation(self, node, lines=("LD %I0.0", "SR0")):
        before = ET.tostring(node)
        with self.assertRaises(CompileError):
            read_graph(node)
        self.assertEqual(ET.tostring(node), before)
        with self.assertRaises(CompileError):
            write_graph(lines, node)
        self.assertEqual(ET.tostring(node), before)

    def test_literal_eleven_node_geometry_and_all_documented_identities(self):
        for number in range(64):
            with self.subTest(number=number):
                call = parse_call([" LD   %I0.0 ", "SR" + str(number)])
                self.assertEqual(call, SubroutineCall(number))
                expected = [("NormalContact", "%I0.0", 0, 0, "Left, Right")]
                expected += [
                    ("Line", "", 0, column, "Left, Right") for column in range(1, 10)
                ]
                expected += [("Jump", "SR" + str(number), 0, 10, "Left")]
                self.assertEqual(graphics(["LD %I0.0", "SR" + str(number)]), expected)

    def test_authentic_zero_and_last_saved_bindings_are_exact(self):
        for number, label, digest in SAVES:
            path = native_path(label)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            provenance = json.loads(path.with_suffix(".provenance.json").read_text())
            self.assertEqual(provenance["sha256"], digest)
            self.assertFalse(provenance["root_observation"]["fresh_reopen_pending"])
            self.assertEqual(
                provenance["password_fields"], {"count": 3, "all_blank": True}
            )
            (call,) = [
                n
                for n in ET.parse(path).findall(".//RungEntity")
                if any(
                    (x.text or "").strip() == "SR" + str(number)
                    for x in n.findall(
                        "InstructionLines/InstructionLineEntity/InstructionLine"
                    )
                )
            ]
            before = ET.tostring(call)
            self.assertEqual(read_graph(call), SubroutineCall(number))
            self.assertEqual(ET.tostring(call), before)

    def test_unknown_predicate_label_opcode_or_number_is_refused(self):
        bad = [[], ["SR0"], ["LD %I0.0", "SR0", "ST %M0"], ["%L0:", "LD %I0.0", "SR0"]]
        bad += [
            [first, last]
            for first, last in itertools.product(
                ("LDN %I0.0", "LD %I0.1", "LD %M1024", "LD 1"), ("SR0",)
            )
        ]
        bad += [
            ["LD %I0.0", value]
            for value in (
                "SR64",
                "SR00",
                "SR-1",
                "SR 0",
                "%SR0",
                "CAL SR0",
                "RET",
                "SR0 extra",
                "SR٠",
            )
        ]
        bad += [None, "LD %I0.0", [True, "SR0"]]
        for lines in bad:
            with self.subTest(lines=lines), self.assertRaises(CompileError):
                parse_call(lines)
        for number in (True, -1, 64, "0", None):
            with self.subTest(number=number), self.assertRaises(CompileError):
                SubroutineCall(number)

    def test_fill_absent_or_empty_graph_only_and_no_caller_alias(self):
        for present in (False, True):
            node = rung(63, present)
            before = copy.deepcopy(node)
            write_graph(["LD %I0.0", "SR63"], node)
            self.assertEqual(read_graph(node), SubroutineCall(63))
            graph = node.find("LadderElements")
            self.assertEqual(len(graph), 11)
            node.remove(graph)
            old = before.find("LadderElements")
            if old is not None:
                before.remove(old)
            self.assertEqual(ET.tostring(node), ET.tostring(before))

    def test_existing_valid_graph_and_scalar_annotations_are_preserved(self):
        node = rung()
        write_graph(["LD %I0.0", "SR0"], node)
        for entity in node.find("LadderElements"):
            ET.SubElement(entity, "Symbol").text = "human_symbol"
            comment = entity.find("Comment")
            if comment is None:
                comment = ET.SubElement(entity, "Comment")
            comment.text = "note"
        before = ET.tostring(node)
        write_graph(["LD %I0.0", "SR0"], node)
        self.assertEqual(ET.tostring(node), before)
        self.assertEqual(read_graph(node), SubroutineCall(0))

    def test_entity_order_is_not_executable_order(self):
        for shift in range(11):
            node = rung()
            write_graph(["LD %I0.0", "SR0"], node)
            graph = node.find("LadderElements")
            values = list(graph)
            graph[:] = values[shift:] + values[:shift]
            self.assertEqual(read_graph(node), SubroutineCall(0))

    def test_geometry_type_descriptor_and_missing_extra_entities_fail_atomically(self):
        mutations = [
            lambda g: setattr(g[0].find("Descriptor"), "text", "%M0"),
            lambda g: setattr(g[-1].find("Descriptor"), "text", "%L0"),
            lambda g: setattr(g[-1].find("Descriptor"), "text", "%SR0"),
            lambda g: setattr(g[-1].find("Descriptor"), "text", "SR63"),
            lambda g: setattr(g[-1].find("ElementType"), "text", "End"),
            lambda g: setattr(g[0].find("ElementType"), "text", "NegatedContact"),
            lambda g: setattr(g[1].find("Row"), "text", "1"),
            lambda g: setattr(g[1].find("Column"), "text", "01"),
            lambda g: setattr(g[-1].find("ChosenConnection"), "text", "Left, Right"),
            lambda g: g.remove(g[4]),
            lambda g: g.append(copy.deepcopy(g[-1])),
        ]
        for mutation in mutations:
            node = rung()
            write_graph(["LD %I0.0", "SR0"], node)
            mutation(node.find("LadderElements"))
            self.reject_without_mutation(node)

    def test_owned_attributes_namespaces_unknowns_and_duplicates_fail(self):
        for path in (
            ".",
            "LadderElements",
            "LadderElements/LadderEntity",
            "LadderElements/LadderEntity/Descriptor",
            "InstructionLines",
            "InstructionLines/InstructionLineEntity",
            "InstructionLines/InstructionLineEntity/InstructionLine",
        ):
            for action in ("attribute", "tail", "nested"):
                node = rung()
                write_graph(["LD %I0.0", "SR0"], node)
                target = node if path == "." else node.find(path)
                if action == "attribute":
                    target.set("active", "true")
                elif action == "tail":
                    target.tail = "active text"
                else:
                    ET.SubElement(target, "Unknown")
                self.reject_without_mutation(node)
        for field in ("Descriptor", "Row", "Column", "ElementType"):
            node = rung()
            write_graph(["LD %I0.0", "SR0"], node)
            entity = node.find("LadderElements/LadderEntity")
            entity.append(copy.deepcopy(entity.find(field)))
            self.reject_without_mutation(node)
        node = rung()
        write_graph(["LD %I0.0", "SR0"], node)
        node.find("LadderElements/LadderEntity").tag = "{x}LadderEntity"
        self.reject_without_mutation(node)

    def test_instruction_fields_and_mixed_text_are_closed(self):
        for path in (
            "InstructionLines",
            "InstructionLines/InstructionLineEntity",
            "LadderElements",
        ):
            node = rung()
            write_graph(["LD %I0.0", "SR0"], node)
            node.find(path).text = "uninterpreted active text"
            self.reject_without_mutation(node)
        node = rung()
        write_graph(["LD %I0.0", "SR0"], node)
        entry = node.find("InstructionLines/InstructionLineEntity")
        entry.append(copy.deepcopy(entry.find("InstructionLine")))
        self.reject_without_mutation(node)

    def test_il_and_metadata_cannot_forge_graph_binding(self):
        for path, value in [
            ("InstructionLines/InstructionLineEntity/InstructionLine", "LD %I0.1"),
            ("Label", "%L0"),
            ("IsLadderSelected", "True"),
        ]:
            node = rung()
            write_graph(["LD %I0.0", "SR0"], node)
            node.find(path).text = value
            self.reject_without_mutation(node)
        node = rung()
        node.find("MainComment").text = "SR63 M-contact allowed native validation=true"
        before = ET.tostring(node)
        with self.assertRaises(CompileError):
            write_graph(["LD %M0", "SR63"], node)
        self.assertEqual(ET.tostring(node), before)

    def test_writer_refuses_wrong_body_without_filling_graph(self):
        for lines in (
            ["LD %I0.0", "SR63"],
            ["LD %I0.1", "SR0"],
            ["LD %I0.0", "CAL SR0"],
        ):
            node = rung()
            before = ET.tostring(node)
            with self.assertRaises(CompileError):
                write_graph(lines, node)
            self.assertEqual(ET.tostring(node), before)

    def test_malformed_typed_text_and_oversized_numeric_identity_fail_closed(self):
        with self.assertRaises(CompileError):
            parse_call(["LD %I0.0", "SR" + "9" * 10000])
        for path, field in (
            ("LadderElements", "text"),
            ("InstructionLines", "tail"),
            ("Label", "text"),
        ):
            node = rung()
            setattr(node.find(path), field, 1)
            with self.assertRaises(CompileError):
                write_graph(["LD %I0.0", "SR0"], node)


if __name__ == "__main__":
    unittest.main()
