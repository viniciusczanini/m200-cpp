"""Standalone native SR wrapper codec; whole projects must remain gated."""

import copy
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError
from m200.subroutine_xml import Subroutine, read_subroutines, write_subroutines

ROOT = Path(__file__).resolve().parents[1]


def body():
    rung = ET.Element("RungEntity")
    ET.SubElement(rung, "LadderElements")
    lines = ET.SubElement(rung, "InstructionLines")
    for value in ("LD %M0", "ST %M1"):
        entry = ET.SubElement(lines, "InstructionLineEntity")
        ET.SubElement(entry, "InstructionLine").text = value
        ET.SubElement(entry, "Comment")
    for tag, value in [
        ("Name", "leaf"),
        ("MainComment", "note"),
        ("Label", ""),
        ("IsLadderSelected", "false"),
    ]:
        ET.SubElement(rung, tag).text = value
    return rung


def software(number=0, section=2, name="leaf"):
    sw = ET.Element("SoftwareConfiguration")
    collection = ET.SubElement(sw, "Subroutines")
    entry = ET.SubElement(collection, "Subroutine")
    for tag, value in [("Name", name), ("SectionNumber", str(section))]:
        ET.SubElement(entry, tag).text = value
    ET.SubElement(entry, "Rungs").append(body())
    ET.SubElement(entry, "Number").text = str(number)
    return sw


class SubroutineXmlTests(unittest.TestCase):
    def refuse_read_and_write(self, sw):
        before = ET.tostring(sw)
        with self.assertRaises(CompileError):
            read_subroutines(sw)
        self.assertEqual(ET.tostring(sw), before)
        with self.assertRaises(CompileError):
            write_subroutines({}, sw)
        self.assertEqual(ET.tostring(sw), before)

    def test_absent_and_empty_collection(self):
        sw = ET.Element("SoftwareConfiguration")
        self.assertEqual(read_subroutines(sw), {})
        ET.SubElement(sw, "Subroutines")
        self.assertEqual(read_subroutines(sw), {})

    def test_number_section_and_name_are_independent(self):
        for number, section in ((0, 2), (63, 2), (1, 42), (4, 3)):
            value = read_subroutines(software(number, section, "açúcar"))[number]
            self.assertEqual(
                (value.number, value.section_number, value.name),
                (number, section, "açúcar"),
            )
            self.assertEqual(len(value.rungs), 1)

    def test_exact_native_saved_wrappers_and_bodies_roundtrip(self):
        for label, number, expected_name, count in [
            ("sr0", 0, "LAB_SR0_LEAF", 3),
            ("sr63", 63, "LAB_SR63_CONDITIONAL_RETURN", 8),
        ]:
            path = (
                ROOT
                / "tests/fixtures"
                / ("official_tm200ce40t_subroutine_" + label + ".smbp")
            )
            sw = ET.parse(path).find("SoftwareConfiguration")
            original = ET.tostring(sw)
            configs = read_subroutines(sw)
            value = configs[number]
            self.assertEqual(
                (value.name, value.section_number, len(value.rungs)),
                (expected_name, 2, count),
            )
            self.assertEqual(ET.tostring(sw), original)
            target = ET.Element("SoftwareConfiguration")
            write_subroutines(configs, target)
            reread = read_subroutines(target)[number]
            self.assertEqual(
                (reread.name, reread.section_number), (value.name, value.section_number)
            )
            self.assertEqual(
                [ET.tostring(r) for r in reread.rungs],
                [ET.tostring(r) for r in value.rungs],
            )

    def test_sixty_four_unique_ids_and_sections(self):
        sw = ET.Element("SoftwareConfiguration")
        values = {
            i: Subroutine(i, "leaf_" + str(i), 2 + i, (body(),)) for i in range(64)
        }
        write_subroutines(values, sw)
        self.assertEqual(set(read_subroutines(sw)), set(range(64)))
        sw.find("Subroutines").append(copy.deepcopy(sw.find("Subroutines")[0]))
        self.refuse_read_and_write(sw)

    def test_noncanonical_or_out_of_range_numbers_sections_and_empty_names_fail(self):
        for tag, values in [
            ("Number", ("64", "-1", "00", "+1", " 0", "0 ", "٠")),
            ("SectionNumber", ("-1", "02", "+2", " 2", "2147483648", "2.0")),
            ("Name", ("",)),
        ]:
            for value in values:
                sw = software()
                sw.find("Subroutines/Subroutine/" + tag).text = value
                self.refuse_read_and_write(sw)

    def test_wrapper_missing_duplicate_unknown_and_active_fields_fail(self):
        for tag in ("Name", "SectionNumber", "Rungs", "Number"):
            for change in ("missing", "duplicate"):
                sw = software()
                entry = sw.find("Subroutines/Subroutine")
                target = entry.find(tag)
                if change == "missing":
                    entry.remove(target)
                else:
                    entry.append(copy.deepcopy(target))
                self.refuse_read_and_write(sw)
        for tag in ("LinkedEvent", "IsFastTask", "IsMastTask", "IsGrafcet", "Unknown"):
            sw = software()
            ET.SubElement(sw.find("Subroutines/Subroutine"), tag).text = "false"
            self.refuse_read_and_write(sw)

    def test_duplicate_id_name_or_section_is_rejected(self):
        for field in ("Number", "Name", "SectionNumber"):
            sw = software()
            second = software(1, 3, "other").find("Subroutines/Subroutine")
            second.find(field).text = sw.find("Subroutines/Subroutine/" + field).text
            sw.find("Subroutines").append(second)
            self.refuse_read_and_write(sw)

    def test_namespace_attributes_mixed_text_and_scalar_nesting_are_rejected(self):
        for path in (
            "Subroutines",
            "Subroutines/Subroutine",
            "Subroutines/Subroutine/Name",
            "Subroutines/Subroutine/SectionNumber",
            "Subroutines/Subroutine/Rungs",
            "Subroutines/Subroutine/Number",
        ):
            for action in ("attribute", "tail", "nested"):
                sw = software()
                target = sw.find(path)
                if action == "attribute":
                    target.set("active", "true")
                elif action == "tail":
                    target.tail = "active text"
                else:
                    ET.SubElement(target, "Unknown")
                self.refuse_read_and_write(sw)
        sw = software()
        sw.find("Subroutines").tag = "{x}Subroutines"
        self.refuse_read_and_write(sw)
        sw = software()
        sw.append(copy.deepcopy(sw.find("Subroutines")))
        self.refuse_read_and_write(sw)

    def test_owned_rung_surface_and_unknown_or_nested_call_are_not_opaque(self):
        for change in (
            "unknown_field",
            "nested_scalar",
            "unknown_opcode",
            "nested_sr",
            "tail",
        ):
            sw = software()
            node = sw.find(".//RungEntity")
            if change == "unknown_field":
                ET.SubElement(node, "Active")
            elif change == "nested_scalar":
                ET.SubElement(
                    node.find("InstructionLines/InstructionLineEntity/InstructionLine"),
                    "Value",
                )
            elif change in ("unknown_opcode", "nested_sr"):
                node.find(
                    "InstructionLines/InstructionLineEntity/InstructionLine"
                ).text = "SR0" if change == "nested_sr" else "CAL SR0"
            else:
                node.find("InstructionLines").tail = "active text"
            self.refuse_read_and_write(sw)

    def test_writer_only_replaces_owned_collection_and_preserves_input_values(self):
        sw = software()
        marker = ET.SubElement(sw, "WatchLists")
        ET.SubElement(marker, "AnyUI").text = "preserve"
        before_ui = ET.tostring(marker)
        values = read_subroutines(sw)
        before_rungs = [ET.tostring(r) for r in values[0].rungs]
        write_subroutines(values, sw)
        self.assertEqual(ET.tostring(sw.find("WatchLists")), before_ui)
        self.assertEqual([ET.tostring(r) for r in values[0].rungs], before_rungs)
        self.assertEqual(read_subroutines(sw)[0].name, "leaf")

    def test_reader_and_writer_deep_copy_rung_nodes(self):
        sw = software()
        before = ET.tostring(sw)
        values = read_subroutines(sw)
        values[0].rungs[0].find("Name").text = "local-only"
        self.assertEqual(ET.tostring(sw), before)
        target = ET.Element("SoftwareConfiguration")
        write_subroutines(values, target)
        values[0].rungs[0].find("Name").text = "changed-again"
        self.assertEqual(target.findtext(".//RungEntity/Name"), "local-only")

    def test_invalid_mapping_is_atomic_for_existing_or_absent_collection(self):
        good = Subroutine(0, "leaf", 2, (body(),))
        invalid = [
            None,
            [],
            {True: good},
            {"0": good},
            {1: good},
            {64: good},
            {0: object()},
        ]
        for values in invalid:
            for existing in (False, True):
                sw = software() if existing else ET.Element("SoftwareConfiguration")
                before = ET.tostring(sw)
                with self.assertRaises(CompileError):
                    write_subroutines(values, sw)
                self.assertEqual(ET.tostring(sw), before)
        for values in [
            (True, "x", 2, (body(),)),
            (0, "", 2, (body(),)),
            (0, "x", True, (body(),)),
            (0, "x", 2, []),
            (0, "x", 2, ("unknown",)),
        ]:
            with self.assertRaises(CompileError):
                Subroutine(*values)

    def test_whole_project_gate_remains_closed(self):
        from m200.project import load_project

        path = ROOT / "tests/fixtures/official_tm200ce40t_subroutine_sr0.smbp"
        with self.assertRaises(CompileError):
            load_project(path)

    def test_invalid_xml_characters_and_oversized_decimal_are_refused(self):
        for name in ("bad\x00name", "bad\ud800name", "bad\uffffname"):
            with self.assertRaises(CompileError):
                Subroutine(0, name, 2, (body(),))
        sw = software()
        sw.find("Subroutines/Subroutine/Number").text = "9" * 10000
        with self.assertRaises(CompileError):
            read_subroutines(sw)


if __name__ == "__main__":
    unittest.main()
