"""Standalone Register config foundation; compiler/project R admission stays gated."""

import copy
import hashlib
import importlib
from pathlib import Path
from types import MappingProxyType
import unittest
import xml.etree.ElementTree as ET

from m200.model import CompileError

ROOT = Path(__file__).resolve().parents[1]
LAB_SAVES = (
    ROOT / "output/editor-validation/native-register-shared-request/editor-saved"
)


def software(entries=""):
    return ET.fromstring(
        '<SoftwareConfiguration marker="preserve"><Timers><Unrelated /></Timers>'
        + "<Registers>"
        + entries
        + "</Registers><RegistersMemoryAllocation><ForcedCount>4</ForcedCount>"
        + '</RegistersMemoryAllocation><OpaqueSibling keep="yes" /></SoftwareConfiguration>'
    )


def register(index="0", mode="Lifo", address=None):
    return (
        "<Register><Address>"
        + ("%R" + index if address is None else address)
        + "</Address><Index>"
        + index
        + "</Index>"
        + ("" if mode is None else "<Type>" + mode + "</Type>")
        + "</Register>"
    )


class RegisterXmlTests(unittest.TestCase):
    def setUp(self):
        try:
            self.codec = importlib.import_module("m200.register_xml")
        except ModuleNotFoundError as exc:
            if exc.name != "m200.register_xml":
                raise
            self.fail("The isolated native Register configuration codec is missing")
        self.FIFO = self.codec.RegisterMode.FIFO
        self.LIFO = self.codec.RegisterMode.LIFO

    def assert_read_rejected_unchanged(self, sw, referenced_ids=()):
        before = ET.tostring(sw)
        with self.assertRaises(CompileError):
            self.codec.read_registers(sw, referenced_ids)
        self.assertEqual(ET.tostring(sw), before)

    def test_mode_values_are_two_literal_native_lexemes(self):
        self.assertEqual(self.FIFO.value, "Fifo")
        self.assertEqual(self.LIFO.value, "Lifo")
        self.assertEqual(len(self.codec.RegisterMode), 2)

    def test_empty_collection_adds_only_referenced_defaults_without_mutation(self):
        sw = software()
        before = ET.tostring(sw)
        self.assertEqual(self.codec.read_registers(sw), {})
        self.assertEqual(
            self.codec.read_registers(sw, [3, 0, 3]), {0: self.FIFO, 3: self.FIFO}
        )
        self.assertEqual(ET.tostring(sw), before)

    def test_absent_collection_resolves_referenced_default(self):
        sw = ET.fromstring(
            "<SoftwareConfiguration><Unrelated /></SoftwareConfiguration>"
        )
        before = ET.tostring(sw)
        self.assertEqual(self.codec.read_registers(sw, (1,)), {1: self.FIFO})
        self.assertIsNone(sw.find("Registers"))
        self.assertEqual(ET.tostring(sw), before)

    def test_explicit_modes_and_omitted_type_preserve_all_configured_ids(self):
        sw = software(
            register("0", "Lifo") + register("1", "Fifo") + register("3", None)
        )
        self.assertEqual(
            self.codec.read_registers(sw, (0, 2)),
            {0: self.LIFO, 1: self.FIFO, 2: self.FIFO, 3: self.FIFO},
        )
        for mode in self.codec.read_registers(sw).values():
            self.assertIs(type(mode), self.codec.RegisterMode)

    def test_all_four_ids_are_one_bounded_family(self):
        sw = software(
            "".join(register(str(i), "Lifo" if i % 2 else "Fifo") for i in range(4))
        )
        self.assertEqual(
            self.codec.read_registers(sw),
            {0: self.FIFO, 1: self.LIFO, 2: self.FIFO, 3: self.LIFO},
        )

    def test_exact_actual_editor_saves_read_config_only_and_stay_product_gated(self):
        paths = [
            LAB_SAVES / ("register_" + mode + "_editor_saved.smbp")
            for mode in ("fifo", "lifo")
        ]
        if not all(path.is_file() for path in paths):
            self.skipTest(
                "Optional pinned local editor saves are not present; no fixture was promoted"
            )
        from m200.project import load_project

        for path, sha, mode, entries in (
            (
                paths[0],
                "85219725709cbe90641e25bedddd6bfa4f13011a55e01be4ba087f8f42b09189",
                self.FIFO,
                0,
            ),
            (
                paths[1],
                "8d04a2bc22bc2466a928ea185d41641f53c5493e26a2a19d690ef8e55822c1ab",
                self.LIFO,
                1,
            ),
        ):
            with self.subTest(path=path.name):
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), sha)
                sw = ET.fromstring(raw).find("SoftwareConfiguration")
                self.assertEqual(len(sw.find("Registers")), entries)
                self.assertEqual(self.codec.read_registers(sw, (0,)), {0: mode})
                self.assertEqual(
                    self.codec.read_registers(sw), {} if entries == 0 else {0: mode}
                )
                with self.assertRaises(CompileError):
                    load_project(path)
                self.assertEqual(path.read_bytes(), raw)

    def test_reference_ids_require_real_bounded_integers(self):
        for invalid in (-1, 4, True, False, 0.0, "0", None):
            with self.subTest(value=invalid):
                self.assert_read_rejected_unchanged(software(), (invalid,))
        for invalid in (None, 0, "0"):
            with self.subTest(sequence=invalid):
                self.assert_read_rejected_unchanged(software(), invalid)

    def test_wrong_roots_have_controlled_errors(self):
        for sw in (None, "SoftwareConfiguration", ET.Element("Registers")):
            with self.subTest(root=sw):
                with self.assertRaises(CompileError):
                    self.codec.read_registers(sw)
                with self.assertRaises(CompileError):
                    self.codec.write_registers({}, sw)

    def test_duplicate_collection_entries_and_fields_are_rejected(self):
        variants = []
        sw = software()
        sw.append(ET.Element("Registers"))
        variants.append(sw)
        variants.append(software(register() + register(mode="Fifo")))
        for field in ("Address", "Index", "Type"):
            sw = software(register())
            node = sw.find("Registers/Register")
            node.append(copy.deepcopy(node.find(field)))
            variants.append(sw)
        for sw in variants:
            with self.subTest(xml=ET.tostring(sw)):
                self.assert_read_rejected_unchanged(sw)

    def test_noncanonical_address_and_index_forms_are_rejected(self):
        for index, address in (
            ("-1", "%R-1"),
            ("4", "%R4"),
            ("00", "%R00"),
            ("+0", "%R+0"),
            ("0 ", "%R0"),
            (" 0", "%R0"),
            ("０", "%R０"),
            ("0", "%R1"),
            ("0", "%R00"),
            ("0", "%r0"),
            ("0", "%READ_VAR0"),
            ("0", "%RTC0"),
            ("0", "R0"),
        ):
            with self.subTest(index=index, address=address):
                self.assert_read_rejected_unchanged(
                    software(register(index, address=address))
                )
        for missing in ("Address", "Index"):
            sw = software(register())
            node = sw.find("Registers/Register")
            node.remove(node.find(missing))
            self.assert_read_rejected_unchanged(sw)

    def test_unknown_or_noncanonical_type_is_not_a_default(self):
        for mode in (
            "FIFO",
            "LIFO",
            "fifo",
            "lifo",
            "Fifo ",
            " Lifo",
            "0",
            "1",
            "",
            "Other",
        ):
            with self.subTest(mode=mode):
                self.assert_read_rejected_unchanged(software(register(mode=mode)))

    def test_unknown_nested_or_attributed_owned_fields_are_rejected(self):
        variants = []
        for path in (
            "Registers",
            "Registers/Register",
            "Registers/Register/Address",
            "Registers/Register/Index",
            "Registers/Register/Type",
        ):
            sw = software(register())
            sw.find(path).set("Unknown", "1")
            variants.append(sw)
        for tag in ("Address", "Index", "Type"):
            sw = software(register())
            ET.SubElement(sw.find("Registers/Register/" + tag), "Value")
            variants.append(sw)
        for tag in ("Input", "Output", "Empty", "Full", "Preset", "Symbol", "Comment"):
            sw = software(register())
            ET.SubElement(sw.find("Registers/Register"), tag).text = "opaque"
            variants.append(sw)
        sw = software(register())
        sw.find("Registers/Register").tag = "RegisterOther"
        variants.append(sw)
        sw = software()
        ET.SubElement(sw, "{urn:unknown}Registers")
        variants.append(sw)
        for sw in variants:
            with self.subTest(xml=ET.tostring(sw)):
                self.assert_read_rejected_unchanged(sw)

    def test_mixed_owned_text_and_tails_are_rejected(self):
        for path, attribute in (
            ("Registers", "text"),
            ("Registers/Register", "text"),
            ("Registers/Register", "tail"),
            ("Registers/Register/Type", "tail"),
        ):
            sw = software(register())
            setattr(sw.find(path), attribute, "unexpected")
            with self.subTest(path=path, attribute=attribute):
                self.assert_read_rejected_unchanged(sw)

    def test_write_preserves_explicit_modes_sparse_ids_and_literal_shape(self):
        sw = software(register("2", "Lifo"))
        configs = {3: self.LIFO, 0: self.FIFO}
        before = dict(configs)
        self.codec.write_registers(MappingProxyType(configs), sw)
        self.assertEqual(configs, before)
        self.assertEqual(
            [(n.tag, [(c.tag, c.text) for c in n]) for n in sw.find("Registers")],
            [
                ("Register", [("Address", "%R0"), ("Index", "0"), ("Type", "Fifo")]),
                ("Register", [("Address", "%R3"), ("Index", "3"), ("Type", "Lifo")]),
            ],
        )
        self.assertEqual(self.codec.read_registers(sw), configs)

    def test_write_only_replaces_owned_collection_preserving_siblings_order_and_tail(
        self,
    ):
        sw = software(register())
        previous = sw.find("Registers")
        previous.tail = "\n  "
        siblings = [(n, ET.tostring(n)) for n in sw if n is not previous]
        original_order = [n.tag for n in sw]
        self.codec.write_registers({2: self.FIFO}, sw)
        self.assertEqual([n.tag for n in sw], original_order)
        self.assertIsNot(sw.find("Registers"), previous)
        self.assertEqual(sw.find("Registers").tail, "\n  ")
        self.assertEqual(sw.attrib, {"marker": "preserve"})
        for n, raw in siblings:
            self.assertIn(n, list(sw))
            self.assertEqual(ET.tostring(n), raw)
        self.assertEqual(previous.findtext("Register/Type"), "Lifo")

    def test_write_empty_and_absent_collections_are_explicit_and_readable(self):
        sw = software(register())
        self.codec.write_registers({}, sw)
        self.assertEqual(len(sw.find("Registers")), 0)
        self.assertEqual(self.codec.read_registers(sw, (3,)), {3: self.FIFO})
        sw = ET.Element("SoftwareConfiguration")
        unrelated = ET.SubElement(sw, "Unrelated")
        self.codec.write_registers({1: self.LIFO}, sw)
        self.assertIs(sw[0], unrelated)
        self.assertEqual(self.codec.read_registers(sw), {1: self.LIFO})

    def test_invalid_new_configs_preserve_entire_tree(self):
        invalids = [
            None,
            [],
            [(0, self.FIFO)],
            {True: self.FIFO},
            {"0": self.FIFO},
            {-1: self.FIFO},
            {4: self.FIFO},
            {0.5: self.FIFO},
            {0: "Fifo"},
            {0: "Lifo"},
            {0: None},
            {0: self.FIFO, 3: "unverified"},
        ]
        for configs in invalids:
            sw = software(register())
            before = ET.tostring(sw)
            with self.subTest(configs=configs), self.assertRaises(CompileError):
                self.codec.write_registers(configs, sw)
            self.assertEqual(ET.tostring(sw), before)

    def test_malformed_existing_collection_is_not_silently_discarded(self):
        variants = []
        sw = software(register())
        ET.SubElement(sw.find("Registers/Register"), "Opaque").text = "keep"
        variants.append(sw)
        sw = software(register())
        sw.append(ET.Element("Registers"))
        variants.append(sw)
        variants.append(software(register(mode="Unknown")))
        sw = software(register())
        sw.find("Registers").set("Vendor", "keep")
        variants.append(sw)
        for sw in variants:
            before = ET.tostring(sw)
            with self.subTest(xml=before), self.assertRaises(CompileError):
                self.codec.write_registers({1: self.FIFO}, sw)
            self.assertEqual(ET.tostring(sw), before)


if __name__ == "__main__":
    unittest.main()
