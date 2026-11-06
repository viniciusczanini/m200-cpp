"""Canonical Register graphs grounded in exact portable native saves."""

import copy
import hashlib
import importlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError


FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    (
        "fifo",
        "f6198b7054f1f1b6dbd016f6df756ef2ebd150a99d26bc59e86069944d000fa4",
        105416,
    ),
    (
        "lifo",
        "a82e4dd97f37c469dae5d30f68b12cf3d11f55f0131f171d7e6b0a3b5c37cf0a",
        105554,
    ),
)
LINES = ["BLK %R0", "LD %I0.0", "R", "LD %I0.1", "I", "LD %I0.2", "O", "END_BLK"]
M_LINES = ["BLK %R0", "LD %M20", "R", "LD %M21", "I", "LD %M22", "O", "END_BLK"]
M_FIXTURE = FIXTURES / "official_tm200ce40t_register_fifo_m_contacts.smbp"


class RegisterGraphTests(unittest.TestCase):
    def setUp(self):
        try:
            self.codec = importlib.import_module("m200.register_graph")
        except ModuleNotFoundError as error:
            if error.name != "m200.register_graph":
                raise
            self.fail("The isolated native Register graph codec is missing")

    def fixture(self, kind):
        return FIXTURES / ("official_tm200ce40t_register_" + kind + "_three_ld.smbp")

    def bare(self, root):
        return next(
            rung
            for rung in root.findall(".//RungEntity")
            if any(
                " ".join((n.text or "").split()).startswith("BLK %R")
                for n in rung.findall(
                    "InstructionLines/InstructionLineEntity/InstructionLine"
                )
            )
        )

    def rung(self, lines=None, graph=True):
        root = ET.Element("RungEntity")
        if graph:
            node = ET.SubElement(root, "LadderElements")
            node.tail = "\n  "
        instructions = ET.SubElement(root, "InstructionLines")
        for text in LINES if lines is None else lines:
            item = ET.SubElement(instructions, "InstructionLineEntity")
            ET.SubElement(item, "InstructionLine").text = text
            ET.SubElement(item, "Comment").text = "Keep instruction note"
        for tag, text in (
            ("Name", "Keep name"),
            ("MainComment", "Keep human note"),
            ("Label", ""),
            ("IsLadderSelected", "false"),
        ):
            ET.SubElement(root, tag).text = text
        return root

    def loaded(self):
        return self.bare(ET.parse(self.fixture("fifo")))

    def assert_read_rejected(self, node):
        before = ET.tostring(node) if isinstance(node, ET.Element) else None
        with self.assertRaises(CompileError):
            self.codec.read_graph(node)
        if before is not None:
            self.assertEqual(ET.tostring(node), before)

    def assert_write_rejected(self, lines, node):
        before = ET.tostring(node) if isinstance(node, ET.Element) else None
        source = copy.deepcopy(lines)
        with self.assertRaises(CompileError):
            self.codec.write_graph(lines, node)
        self.assertEqual(lines, source)
        if before is not None:
            self.assertEqual(ET.tostring(node), before)

    def test_exact_two_editor_saves_read_same_plain_RIO_graph(self):
        for kind, digest, size in CASES:
            with self.subTest(kind=kind):
                path = self.fixture(kind)
                raw = path.read_bytes()
                self.assertEqual(len(raw), size)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
                self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
                root = ET.fromstring(raw)
                rung = self.bare(root)
                before = ET.tostring(rung)
                expected = self.codec.RegisterInputs(0, "%I0.0", "%I0.1", "%I0.2")
                self.assertEqual(self.codec.read_graph(rung), expected)
                self.assertEqual(self.codec.parse_block(LINES), expected)
                self.assertEqual(
                    self.codec.graphics(LINES),
                    [
                        ("NormalContact", "%I0.0", 0, 0, "Left, Right"),
                        ("NormalContact", "%I0.1", 1, 0, "Left, Right"),
                        ("NormalContact", "%I0.2", 2, 0, "Left, Right"),
                        ("Register", "%R0", 0, 1, "Left"),
                    ],
                )
                self.assertEqual(ET.tostring(rung), before)
                self.assertEqual(path.read_bytes(), raw)

    def test_both_portable_fixtures_keep_modes_separate(self):
        from m200.register_xml import read_registers, RegisterMode

        for kind, _, _ in CASES:
            with self.subTest(kind=kind):
                path = self.fixture(kind)
                original = path.read_bytes()
                provenance = json.loads(
                    path.with_suffix(".provenance.json").read_text()
                )
                self.assertEqual(
                    provenance["sha256"], hashlib.sha256(original).hexdigest()
                )
                root = ET.fromstring(original)
                self.assertEqual(len(root.findall(".//RungEntity")), 6)
                self.assertEqual(len(root.findall(".//InstructionLine")), 18)
                self.assertEqual(
                    [
                        len(r.find("LadderElements"))
                        for r in root.findall(".//RungEntity")
                    ],
                    [10, 10, 10, 4, 11, 11],
                )
                inputs = self.codec.read_graph(self.bare(root))
                mode = RegisterMode.FIFO if kind == "fifo" else RegisterMode.LIFO
                self.assertEqual(
                    read_registers(root.find("SoftwareConfiguration"), (inputs.index,)),
                    {0: mode},
                )
                self.assertEqual(path.read_bytes(), original)

    def test_exact_native_M_contacts_read_without_modifying_authentic_saved_bytes(self):
        raw = M_FIXTURE.read_bytes()
        self.assertEqual(len(raw), 117097)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "e05bf55077084557c9cc11a5237cdb677611c9cedff3cf22f921f19716932639",
        )
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf<?xml"))
        self.assertEqual(raw.count(b"\r\n"), raw.count(b"\n"))
        root = ET.fromstring(raw)
        self.assertEqual(root.findtext("ManagementLevel"), "FunctLevelMan21_0")
        self.assertEqual(
            root.findtext("HardwareConfiguration/Plc/Cpu/Reference"), "TM200CE40T"
        )
        self.assertEqual(len(root.findall(".//RungEntity")), 9)
        self.assertEqual(len(root.findall(".//InstructionLine")), 24)
        self.assertEqual(
            [len(r.find("LadderElements")) for r in root.findall(".//RungEntity")],
            [10, 10, 10, 11, 11, 11, 4, 11, 11],
        )
        node = self.bare(root)
        before = ET.tostring(node)
        expected = self.codec.RegisterInputs(0, "%M20", "%M21", "%M22")
        self.assertEqual(self.codec.read_graph(node), expected)
        self.assertEqual(self.codec.check_graph(node, M_LINES), expected)
        self.codec.write_graph(M_LINES, node)
        self.assertEqual(ET.tostring(node), before)
        self.assertEqual(
            self.codec.graphics(M_LINES),
            [
                ("NormalContact", "%M20", 0, 0, "Left, Right"),
                ("NormalContact", "%M21", 1, 0, "Left, Right"),
                ("NormalContact", "%M22", 2, 0, "Left, Right"),
                ("Register", "%R0", 0, 1, "Left"),
            ],
        )
        self.assertEqual(M_FIXTURE.read_bytes(), raw)

    def test_native_M_fixture_preserves_parent_hardware_and_historical_static_evidence(
        self,
    ):
        raw = M_FIXTURE.read_bytes()
        parent = self.fixture("fifo").read_bytes()

        def subtree(data, tag):
            start = data.index(("<" + tag).encode())
            finish = ("</" + tag + ">").encode()
            opening_end = data.index(b">", start) + 1
            if data[opening_end - 2 : opening_end] == b"/>":
                return data[start:opening_end]
            return data[start : data.index(finish, start) + len(finish)]

        hardware = subtree(raw, "HardwareConfiguration")
        self.assertEqual(hardware, subtree(parent, "HardwareConfiguration"))
        self.assertEqual(len(hardware), 24116)
        self.assertEqual(
            hashlib.sha256(hardware).hexdigest(),
            "e4b356c22950df5da97a1c380e150891394bf5b6dc9f7f4b110198e312a4e629",
        )
        allocations = [
            n.tag
            for n in ET.fromstring(parent).find("SoftwareConfiguration")
            if n.tag.endswith("MemoryAllocation")
        ]
        self.assertEqual(len(allocations), 13)
        for tag in allocations:
            with self.subTest(tag=tag):
                self.assertEqual(subtree(raw, tag), subtree(parent, tag))
        self.assertEqual(subtree(raw, "Registers"), subtree(parent, "Registers"))
        provenance = json.loads(M_FIXTURE.with_suffix(".provenance.json").read_text())
        self.assertEqual(provenance["sha256"], hashlib.sha256(raw).hexdigest())
        historical = provenance["root_GUI_observation"]
        self.assertEqual(historical["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertTrue(historical["fresh_reopen_root_personally_viewed"])
        self.assertEqual(
            historical["fresh_reopen_Programming_status"], "No error / Not Connected"
        )
        self.assertTrue(historical["not_compiler_output"])
        self.assertTrue(historical["runtime_not_tested"])

    def test_canonical_M_bounds_and_mixed_I_M_pins_keep_literal_port_positions(self):
        for value in range(1024):
            operand = "%M" + str(value)
            self.codec.RegisterInputs(0, operand, "%I0.0", "%M1023")
        for index in range(4):
            for reset in ("%I0.23", "%M0"):
                for store in ("%I0.0", "%M1023"):
                    for retrieve in ("%I0.1", "%M22"):
                        lines = [
                            "BLK %R" + str(index),
                            "LD " + reset,
                            "R",
                            "LD " + store,
                            "I",
                            "LD " + retrieve,
                            "O",
                            "END_BLK",
                        ]
                        with self.subTest(lines=lines):
                            node = self.rung(lines)
                            self.codec.write_graph(lines, node)
                            expected = self.codec.RegisterInputs(
                                index, reset, store, retrieve
                            )
                            self.assertEqual(self.codec.read_graph(node), expected)
                            self.assertEqual(
                                self.codec.check_graph(node, lines), expected
                            )
                            self.assertEqual(
                                [
                                    (
                                        n.findtext("Descriptor"),
                                        n.findtext("Row"),
                                        n.findtext("Column"),
                                    )
                                    for n in node.find("LadderElements")
                                ],
                                [
                                    (reset, "0", "0"),
                                    (store, "1", "0"),
                                    (retrieve, "2", "0"),
                                    ("%R" + str(index), "0", "1"),
                                ],
                            )

    def test_M_contacts_reject_noncanonical_out_of_range_or_foreign_predicates(self):
        for value in (
            "%M1024",
            "%M9999",
            "%M-1",
            "%M+1",
            "%M00",
            "%M01",
            "%M0000",
            "%M١",
            "%M 0",
            "%M1.0",
            "%M1:2",
            "%M1[%MW0]",
            "%MW0",
            "%M",
            "%M" + "9" * 5000,
        ):
            for position in (1, 3, 5):
                lines = M_LINES.copy()
                lines[position] = "LD " + value
                with self.subTest(value=value[:30], position=position):
                    with self.assertRaises(CompileError):
                        self.codec.parse_block(lines)
                    self.assert_write_rejected(lines, self.rung(lines))
                    node = self.bare(ET.parse(M_FIXTURE))
                    contact = node.find("LadderElements")[(position - 1) // 2]
                    contact.find("Descriptor").text = value
                    self.assert_read_rejected(node)
        for value in (" %M0", "%M1023 ", None, 0, True):
            with self.subTest(value=value), self.assertRaises(CompileError):
                self.codec.RegisterInputs(0, value, "%M21", "%M22")

    def test_native_M_graph_rejects_type_pin_row_swaps_connections_and_IL_mismatch(
        self,
    ):
        mutations = (
            (0, "ElementType", "NegatedContact"),
            (0, "ElementType", "RisingEdge"),
            (0, "Descriptor", "%I0.0"),
            (1, "Descriptor", "%M22"),
            (2, "Descriptor", "%R0.E"),
            (0, "Row", "1"),
            (1, "Column", "1"),
            (2, "ChosenConnection", "Right"),
            (3, "Descriptor", "%R1"),
            (3, "ElementType", "Counter"),
            (3, "Row", "1"),
            (3, "Column", "2"),
            (3, "ChosenConnection", "Left, Right"),
        )
        for index, tag, value in mutations:
            node = self.bare(ET.parse(M_FIXTURE))
            node.find("LadderElements")[index].find(tag).text = value
            with self.subTest(index=index, tag=tag, value=value):
                self.assert_read_rejected(node)
                self.assert_write_rejected(M_LINES, node)
        for tag in ("Descriptor", "Row"):
            node = self.bare(ET.parse(M_FIXTURE))
            graph = node.find("LadderElements")
            first, second = graph[0].find(tag), graph[1].find(tag)
            first.text, second.text = second.text, first.text
            with self.subTest(swap=tag):
                self.assert_read_rejected(node)
                self.assert_write_rejected(M_LINES, node)
        for position, text in ((1, "LD %M21"), (2, "I"), (3, "LDN %M21")):
            node = self.bare(ET.parse(M_FIXTURE))
            node.find("InstructionLines")[position].find("InstructionLine").text = text
            with self.subTest(position=position, text=text):
                self.assert_read_rejected(node)
                self.assert_write_rejected(M_LINES, node)

    def test_project_checker_compares_supplied_body_to_graph_and_preserves_rejections(
        self,
    ):
        for lines in (LINES, M_LINES[:3] + ["LD %M23"] + M_LINES[4:], M_LINES[:-1]):
            node = self.bare(ET.parse(M_FIXTURE))
            original = ET.tostring(node)
            with self.subTest(lines=lines), self.assertRaises(CompileError):
                self.codec.check_graph(node, lines)
            self.assertEqual(ET.tostring(node), original)

    def test_parameterized_indices_and_direct_inputs_map_to_the_literal_rows(self):
        for index in (0, 1, 2, 3):
            lines = [
                "BLK %R" + str(index),
                "LD %I0.23",
                "R",
                "LD %I0.0",
                "I",
                "LD %I0.23",
                "O",
                "END_BLK",
            ]
            with self.subTest(index=index):
                expected = self.codec.RegisterInputs(index, "%I0.23", "%I0.0", "%I0.23")
                self.assertEqual(self.codec.parse_block(tuple(lines)), expected)
                self.assertEqual(
                    self.codec.graphics(lines),
                    [
                        ("NormalContact", "%I0.23", 0, 0, "Left, Right"),
                        ("NormalContact", "%I0.0", 1, 0, "Left, Right"),
                        ("NormalContact", "%I0.23", 2, 0, "Left, Right"),
                        ("Register", "%R" + str(index), 0, 1, "Left"),
                    ],
                )
                node = self.rung(lines)
                self.codec.write_graph(lines, node)
                self.assertEqual(self.codec.read_graph(node), expected)

    def test_native_spacing_is_normalized_without_changing_original_IL_or_comments(
        self,
    ):
        node = self.loaded()
        raw = [
            n.text
            for n in node.findall(
                "InstructionLines/InstructionLineEntity/InstructionLine"
            )
        ]
        original = ET.tostring(node)
        self.assertEqual(self.codec.parse_block(raw), self.codec.parse_block(LINES))
        self.codec.write_graph(raw, node)
        self.assertEqual(ET.tostring(node), original)
        self.assertEqual(
            raw,
            [
                n.text
                for n in node.findall(
                    "InstructionLines/InstructionLineEntity/InstructionLine"
                )
            ],
        )

    def test_unknown_pin_order_actions_extra_operations_and_labels_are_rejected(self):
        changes = (
            (0, "BLK %R0.F"),
            (0, "%L0:"),
            (1, "LDN %I0.0"),
            (1, "LDR %I0.0"),
            (2, "I"),
            (2, "R %R0"),
            (4, "O"),
            (6, "ST %I0.2"),
            (7, "OUT_BLK"),
            (7, "END"),
        )
        for index, text in changes:
            lines = LINES.copy()
            lines[index] = text
            with self.subTest(index=index, text=text):
                with self.assertRaises(CompileError):
                    self.codec.parse_block(lines)
                self.assert_write_rejected(lines, self.rung())
        for lines in (
            LINES[:-1],
            LINES + ["END_BLK"],
            LINES[:2] + ["AND %I0.3"] + LINES[2:],
            ["%L0:"] + LINES,
        ):
            with self.subTest(lines=lines), self.assertRaises(CompileError):
                self.codec.parse_block(lines)

    def test_only_canonical_register_identity_zero_through_three_is_admitted(self):
        for value in (
            "%R4",
            "%R00",
            "%R-1",
            "%R+1",
            "%R1.0",
            "%R 0",
            "%R٣",
            "%R0.I",
            "%RTC0",
            "%READ_VAR0",
            "%R99999999999999999999999",
        ):
            lines = LINES.copy()
            lines[0] = "BLK " + value
            with self.subTest(value=value), self.assertRaises(CompileError):
                self.codec.parse_block(lines)
        for index in (-1, 4, True, False, 0.0, "0", None):
            with self.subTest(index=index), self.assertRaises(CompileError):
                self.codec.RegisterInputs(index, "%I0.0", "%I0.1", "%I0.2")

    def test_contact_operands_are_canonical_and_limited_to_the_observed_input_domain(
        self,
    ):
        invalid = (
            "%I0.24",
            "%I0.-1",
            "%I0.00",
            "%I00.0",
            "%I0.٠",
            "%I0.1 ",
            " %I0.1",
            "%I0.1:2",
            "%Q0.0",
            "%S13",
            "%R0.F",
            "%TM0.Q",
            "%C0.D",
            "0",
            "1",
            "[%MW0=1]",
            "%I0.1[%MW2]",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(CompileError):
                self.codec.RegisterInputs(0, value, "%I0.1", "%I0.2")
            if value.strip() == value:
                lines = LINES.copy()
                lines[3] = "LD " + value
                with self.subTest(value=value), self.assertRaises(CompileError):
                    self.codec.parse_block(lines)

    def test_bad_instruction_containers_and_element_roots_have_controlled_errors(self):
        for lines in (
            None,
            0,
            True,
            "\n".join(LINES),
            iter(LINES),
            [None] * 8,
            [True] * 8,
        ):
            with self.subTest(lines=repr(lines)), self.assertRaises(CompileError):
                self.codec.parse_block(lines)
        for node in (
            None,
            "RungEntity",
            ET.Element("ProjectDescriptor"),
            ET.Element("LadderElements"),
            ET.Element("{ns}RungEntity"),
        ):
            with self.subTest(node=repr(node)):
                self.assert_read_rejected(node)
                self.assert_write_rejected(LINES, node)

    def test_missing_duplicate_unknown_and_namespaced_rung_fields_are_rejected(self):
        for change in (
            "missing_IL",
            "duplicate_IL",
            "duplicate_graph",
            "unknown",
            "namespace",
            "label",
            "selection",
        ):
            node = self.loaded()
            if change == "missing_IL":
                node.remove(node.find("InstructionLines"))
            elif change == "duplicate_IL":
                node.append(copy.deepcopy(node.find("InstructionLines")))
            elif change == "duplicate_graph":
                node.append(copy.deepcopy(node.find("LadderElements")))
            elif change == "unknown":
                ET.SubElement(node, "OtherActivePin").text = "true"
            elif change == "namespace":
                node.find("InstructionLines").tag = "{ns}InstructionLines"
            elif change == "label":
                node.find("Label").text = "%L0"
            else:
                node.find("IsLadderSelected").text = "True"
            with self.subTest(change=change):
                self.assert_read_rejected(node)
                self.assert_write_rejected(LINES, node)

    def test_attributes_nested_values_and_significant_text_tails_are_closed(self):
        paths = (
            ".",
            "LadderElements",
            "LadderElements/LadderEntity",
            "LadderElements/LadderEntity/Descriptor",
            "InstructionLines",
            "InstructionLines/InstructionLineEntity",
            "InstructionLines/InstructionLineEntity/InstructionLine",
            "InstructionLines/InstructionLineEntity/Comment",
            "Name",
            "MainComment",
        )
        for path in paths:
            for change in ("attribute", "tail", "nested"):
                node = self.loaded()
                target = node if path == "." else node.find(path)
                if change == "attribute":
                    target.set("Unknown", "active")
                elif change == "tail":
                    target.tail = "significant data"
                else:
                    ET.SubElement(target, "UnknownChild").text = "active"
                with self.subTest(path=path, change=change):
                    self.assert_read_rejected(node)
                    self.assert_write_rejected(LINES, node)
        for path in (
            ".",
            "LadderElements",
            "LadderElements/LadderEntity",
            "InstructionLines",
            "InstructionLines/InstructionLineEntity",
        ):
            node = self.loaded()
            (
                node if path == "." else node.find(path)
            ).text = "significant container text"
            with self.subTest(text=path):
                self.assert_read_rejected(node)

    def test_exact_graph_identity_rows_columns_connections_and_contact_actions_are_checked(
        self,
    ):
        mutations = (
            (0, "ElementType", "NegatedContact"),
            (0, "Descriptor", "%I0.1"),
            (0, "Row", "1"),
            (0, "Column", "1"),
            (0, "ChosenConnection", "Left"),
            (1, "Row", "01"),
            (2, "Row", "-1"),
            (3, "ElementType", "Counter"),
            (3, "Descriptor", "%R1"),
            (3, "Descriptor", "%R00"),
            (3, "Row", "1"),
            (3, "Column", "2"),
            (3, "ChosenConnection", "Left, Right"),
        )
        for index, tag, value in mutations:
            node = self.loaded()
            node.find("LadderElements")[index].find(tag).text = value
            with self.subTest(index=index, tag=tag, value=value):
                self.assert_read_rejected(node)
                self.assert_write_rejected(LINES, node)

    def test_partial_extra_duplicate_entities_and_unknown_graph_field_forms_refuse(
        self,
    ):
        for change in (
            "missing",
            "extra",
            "duplicate_position",
            "unknown_entity",
            "missing_field",
            "duplicate_field",
            "unknown_field",
            "namespace",
            "expression",
        ):
            node = self.loaded()
            graph = node.find("LadderElements")
            if change == "missing":
                graph.remove(graph[2])
            elif change == "extra":
                graph.append(copy.deepcopy(graph[2]))
            elif change == "duplicate_position":
                graph[1].find("Row").text = "0"
            elif change == "unknown_entity":
                graph[1].tag = "RegisterContact"
            elif change == "missing_field":
                graph[0].remove(graph[0].find("ChosenConnection"))
            elif change == "duplicate_field":
                graph[0].append(copy.deepcopy(graph[0].find("Row")))
            elif change == "unknown_field":
                ET.SubElement(graph[0], "PinValue").text = "1"
            elif change == "namespace":
                graph[0].find("Descriptor").tag = "{ns}Descriptor"
            else:
                ET.SubElement(graph[0], "ComparisonExpression").text = "%MW0=1"
            with self.subTest(change=change):
                self.assert_read_rejected(node)
                self.assert_write_rejected(LINES, node)

    def test_instruction_entry_fields_and_graph_IL_disagreement_cannot_be_ignored(self):
        for change in (
            "missing_line",
            "duplicate_line",
            "duplicate_comment",
            "unknown",
            "empty",
            "extra_entry",
            "wrong_entry",
            "coherent_action_change",
        ):
            node = self.loaded()
            instructions = node.find("InstructionLines")
            if change == "missing_line":
                instructions[0].remove(instructions[0].find("InstructionLine"))
            elif change == "duplicate_line":
                instructions[0].append(
                    copy.deepcopy(instructions[0].find("InstructionLine"))
                )
            elif change == "duplicate_comment":
                instructions[0].append(copy.deepcopy(instructions[0].find("Comment")))
            elif change == "unknown":
                ET.SubElement(instructions[0], "Expression").text = "END"
            elif change == "empty":
                instructions[1].find("InstructionLine").text = ""
            elif change == "extra_entry":
                instructions.append(copy.deepcopy(instructions[-1]))
            elif change == "wrong_entry":
                instructions[0].tag = "ILLine"
            else:
                instructions[1].find("InstructionLine").text = "LDN %I0.0"
                node.find("LadderElements")[0].find(
                    "ElementType"
                ).text = "NegatedContact"
            with self.subTest(change=change):
                self.assert_read_rejected(node)
                self.assert_write_rejected(LINES, node)

    def test_graph_reader_requires_the_complete_shape_even_if_Ladder_is_unselected(
        self,
    ):
        for present in (False, True):
            node = self.rung(graph=present)
            self.assert_read_rejected(node)

    def test_graph_only_writer_fills_empty_or_absent_graph_and_preserves_other_fields(
        self,
    ):
        for present in (False, True):
            node = self.rung(graph=present)
            before = [ET.tostring(c) for c in node if c.tag != "LadderElements"]
            lines = LINES.copy()
            source = lines.copy()
            old = node.find("LadderElements")
            tail = old.tail if old is not None else None
            self.codec.write_graph(lines, node)
            self.assertEqual(lines, source)
            self.assertEqual(
                [ET.tostring(c) for c in node if c.tag != "LadderElements"], before
            )
            self.assertEqual(node.find("LadderElements").tail, tail)
            self.assertEqual(node.findtext("IsLadderSelected"), "false")
            self.assertEqual(
                self.codec.read_graph(node),
                self.codec.RegisterInputs(0, "%I0.0", "%I0.1", "%I0.2"),
            )
            self.assertEqual(
                [
                    (
                        n.findtext("ElementType"),
                        n.findtext("Descriptor"),
                        n.findtext("Row"),
                        n.findtext("Column"),
                        n.findtext("ChosenConnection"),
                    )
                    for n in node.find("LadderElements")
                ],
                [
                    ("NormalContact", "%I0.0", "0", "0", "Left, Right"),
                    ("NormalContact", "%I0.1", "1", "0", "Left, Right"),
                    ("NormalContact", "%I0.2", "2", "0", "Left, Right"),
                    ("Register", "%R0", "0", "1", "Left"),
                ],
            )

    def test_valid_existing_graph_is_not_rewritten_or_stripped_of_UI_annotations(self):
        node = self.loaded()
        for i, entry in enumerate(node.find("LadderElements")):
            entry.find("Comment").text = "Retain entity note" + str(i)
            ET.SubElement(entry, "Symbol").text = "KnownScalarUI" + str(i)
        before = ET.tostring(node)
        self.codec.write_graph(LINES, node)
        self.assertEqual(ET.tostring(node), before)
        self.assertEqual(self.codec.read_graph(node), self.codec.parse_block(LINES))

    def test_writer_does_not_repair_a_mismatched_body_by_discarding_data(self):
        node = self.loaded()
        changed = LINES.copy()
        changed[3] = "LD %I0.3"
        self.assert_write_rejected(changed, node)
        node = self.rung(graph=False)
        self.assert_write_rejected(changed, node)
        node = self.rung()
        node.find("LadderElements").text = "Unknown graph state"
        self.assert_write_rejected(LINES, node)

    def test_writer_refuses_invalid_inputs_before_adding_or_replacing_any_graph(self):
        for lines in (None, "invalid", LINES[:-1], LINES + ["END"], [None] * 8):
            for present in (False, True):
                with self.subTest(lines=repr(lines), present=present):
                    self.assert_write_rejected(lines, self.rung(graph=present))
        node = self.loaded()
        node.find("LadderElements")[2].find("Descriptor").text = "%R0.F"
        self.assert_write_rejected(LINES, node)

    def test_other_five_fixture_rungs_are_not_misclassified_as_Register_bodies(self):
        for kind, _, _ in CASES:
            root = ET.parse(self.fixture(kind))
            rungs = root.findall(".//RungEntity")
            for index in (0, 1, 2, 4, 5):
                with self.subTest(kind=kind, index=index):
                    self.assert_read_rejected(rungs[index])
                    self.assert_write_rejected(LINES, rungs[index])


if __name__ == "__main__":
    unittest.main()
