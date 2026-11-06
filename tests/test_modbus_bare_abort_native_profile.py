"""Observed bare Execute/Abort graphs and safe separate status-rung export.

These are editor binding and local-model checks, not native transaction proof.
"""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError
from m200.modbus import MemoryModbusPeer, MemoryTransport, ModbusConfig
from m200.native import run_native
from m200.numeric import memory_words_used
from m200.project import load_project, write_project
from m200.reverse import to_cpp


FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    (
        "read",
        "READ_VAR",
        "222de155bd4061649a017859f8775322974c3e06b3a85204ff85ae015e35b3e4",
        88863,
    ),
    (
        "write",
        "WRITE_VAR",
        "1489ad6bdcdde1101708088d37ee2eacb326ee23a3c6ac8c0d91cbe25f51fb7d",
        88872,
    ),
    (
        "write_read",
        "WRITE_READ_VAR",
        "ce46d988bcdaf5e9f0add2d17daff51deb0074240a937ca5f85aeed933ea8890",
        90288,
    ),
)


class RecordingTransport(MemoryTransport):
    def __init__(self, peer):
        super().__init__(peer, latency_ms=20)
        self.requests = []

    def start(self, config, pdu, now_ms):
        self.requests.append(pdu)
        return super().start(config, pdu, now_ms)


class ModbusBareAbortNativeProfileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def fixture(self, suffix="write_read"):
        return FIXTURES / ("official_tm200ce40t_modbus_bare_abort_" + suffix + ".smbp")

    def save(self, tree):
        path = self.work / "modified.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def program(self, suffix="write_read"):
        # The established IL-only import supplies IR independently of the new
        # native graph admission. It must remain available without that graph.
        tree = ET.parse(self.fixture(suffix))
        tree.find(".//RungEntity/LadderElements").clear()
        tree.find(".//RungEntity/IsLadderSelected").text = "false"
        return load_project(self.save(tree))

    def native_rungs(self, path):
        return ET.parse(path).findall(".//RungEntity")

    def import_observed(self, path):
        try:
            return load_project(path)
        except CompileError as error:
            self.fail("Observed bare editor graph must import: " + str(error))

    def il(self, rung):
        return [
            " ".join((node.text or "").split())
            for node in rung.findall(
                "InstructionLines/InstructionLineEntity/InstructionLine"
            )
        ]

    def graph(self, rung):
        return [
            tuple(
                node.findtext(tag) or ""
                for tag in (
                    "ElementType",
                    "Descriptor",
                    "Row",
                    "Column",
                    "ChosenConnection",
                )
            )
            for node in rung.findall("LadderElements/LadderEntity")
        ]

    def expected_graph(self, kind):
        # Literal three-node geometry transcribed from actual editor saves.
        execute, abort = {
            "READ_VAR": ("%M20", "%M21"),
            "WRITE_VAR": ("%M22", "%M23"),
            "WRITE_READ_VAR": ("%M24", "%M25"),
        }[kind]
        typ = {
            "READ_VAR": "ReadVarBasic",
            "WRITE_VAR": "WriteVarBasic",
            "WRITE_READ_VAR": "WriteReadVarBasic",
        }[kind]
        return [
            ("NormalContact", execute, "0", "0", "Left, Right"),
            ("NormalContact", abort, "1", "0", "Left, Right"),
            (typ, "%" + kind + "0", "0", "1", "Left"),
        ]

    def export(self, program, suffix="write_read"):
        before = copy.deepcopy(program.as_dict())
        template = self.fixture(suffix)
        original = template.read_bytes()
        destination = self.work / (suffix + "-export.smbp")
        try:
            write_project(program, template, destination)
        except CompileError as error:
            self.fail(
                "Observed bare graph must export without losing rungs: " + str(error)
            )
        self.assertEqual(program.as_dict(), before)
        self.assertEqual(template.read_bytes(), original)
        return destination

    def assert_atomic_failure(self, program, template):
        before = copy.deepcopy(program.as_dict())
        original = template.read_bytes()
        for existing in (False, True):
            destination = self.work / ("present.smbp" if existing else "absent.smbp")
            if existing:
                destination.write_bytes(b"PRESERVE")
            with self.assertRaises(CompileError):
                write_project(program, template, destination)
            self.assertEqual(program.as_dict(), before)
            self.assertEqual(template.read_bytes(), original)
            if existing:
                self.assertEqual(destination.read_bytes(), b"PRESERVE")
            else:
                self.assertFalse(destination.exists())

    def test_exact_saved_fixture_imports_one_six_line_update_without_status_stores(
        self,
    ):
        # A reader that rejects the observed graph, invents OUT_BLK or expands a
        # bare block into five rungs fails this literal native expectation.
        for suffix, kind, digest, size in CASES:
            with self.subTest(kind=kind):
                fixture = self.fixture(suffix)
                data = fixture.read_bytes()
                self.assertEqual(len(data), size)
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                self.assertIn(b"\r\n", data)
                provenance = json.loads(
                    fixture.with_suffix(".provenance.json").read_text()
                )
                self.assertEqual(provenance["sha256"], digest)
                self.assertFalse(provenance["root_observation"]["fresh_reopen_pending"])
                native = self.native_rungs(fixture)
                self.assertEqual(len(native), 1)
                self.assertEqual(self.graph(native[0]), self.expected_graph(kind))
                execute, abort = {
                    "READ_VAR": ("%M20", "%M21"),
                    "WRITE_VAR": ("%M22", "%M23"),
                    "WRITE_READ_VAR": ("%M24", "%M25"),
                }[kind]
                expected = [
                    "BLK %" + kind + "0",
                    "LD " + execute,
                    "EXECUTE",
                    "LD " + abort,
                    "ABORT",
                    "END_BLK",
                ]
                self.assertEqual(self.il(native[0]), expected)
                imported = self.import_observed(fixture)
                self.assertEqual(imported.rungs, [expected])
                self.assertNotIn("native_full_pin_groups", imported.metadata)

    def test_export_emits_only_three_nodes_and_retains_both_complete_buffers(self):
        expected_configs = {
            "read": ModbusConfig(
                kind="READ_VAR", obj_type=1, first_obj=17, quantity=17, index_data=200
            ),
            "write": ModbusConfig(
                kind="WRITE_VAR", obj_type=2, first_obj=73, quantity=17, index_data=240
            ),
            "write_read": ModbusConfig(
                kind="WRITE_READ_VAR",
                first_obj=17,
                quantity=2,
                index_data=300,
                first_read_obj=41,
                read_quantity=3,
                index_data_in=400,
            ),
        }
        for suffix, kind, _, _ in CASES:
            with self.subTest(kind=kind):
                program = self.program(suffix)
                destination = self.export(program, suffix)
                native = self.native_rungs(destination)
                self.assertEqual(len(native), 1)
                self.assertEqual(self.il(native[0]), program.rungs[0])
                self.assertEqual(self.graph(native[0]), self.expected_graph(kind))
                self.assertNotIn(
                    "M200_CPP_FULL_PIN_ORIGINS=", native[0].findtext("MainComment")
                )
                imported = load_project(destination)
                self.assertEqual(imported.rungs, program.rungs)
                self.assertEqual(imported.communications, program.communications)
                self.assertEqual(
                    imported.communications,
                    {"%" + kind + "0": expected_configs[suffix]},
                )
                self.assertEqual(
                    memory_words_used(imported),
                    {
                        "read": {200, 201},
                        "write": {240, 241},
                        "write_read": {300, 301, 400, 401, 402},
                    }[suffix],
                )

    def test_public_constructor_without_getters_and_reverse_keep_bare_update(self):
        source = self.work / "bare.cpp"
        source.write_text(
            "#include <plc.hpp>\n"
            "plc::WriteReadVar remote{0,plc::Link::Serial1,1,100,17,2,300,41,3,400};\n"
            "void scan(){remote.update(plc::read_m(24),plc::read_m(25));}\n"
        )
        compiled = compile_source(source)
        destination = self.export(compiled)
        blocks = [
            r
            for r in self.native_rungs(destination)
            if self.il(r)[0].startswith("BLK ")
        ]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(self.il(blocks[0])), 6)
        self.assertEqual(len(self.graph(blocks[0])), 3)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(load_project(destination)))
        rebuilt = compile_source(reverse)
        second = self.export(rebuilt)
        self.assertEqual(load_project(second).communications, compiled.communications)
        self.assertFalse(
            any("OUT_BLK" in self.il(r) for r in self.native_rungs(second))
        )

    def test_partial_reordered_and_interleaved_status_rungs_remain_separate(self):
        # Failing to match the complete quartet is not permission to discard,
        # reorder or reject otherwise ordinary executable status rungs.
        suffixes = (
            [["LD %WRITE_READ_VAR0.DONE", "ST %M30"]],
            [
                ["LD %WRITE_READ_VAR0.BUSY", "ST %M30"],
                ["LD %WRITE_READ_VAR0.DONE", "ST %M31"],
            ],
            [
                ["LD %WRITE_READ_VAR0.DONE", "ST %M30"],
                ["LD %M5", "ST %M6"],
                ["LD %WRITE_READ_VAR0.ERROR", "ST %M31"],
            ],
            [["%L3:", "LD %WRITE_READ_VAR0.DONE", "ST %M30"]],
            [
                ["LD %WRITE_READ_VAR0.BUSY", "S %M30"],
                ["LD %WRITE_READ_VAR0.ERROR", "R %M31"],
            ],
            [["LD %WRITE_READ_VAR0.DONE", "ST %Q0.0"]],
            # A complete quartet with a Q destination is ordinary decomposition,
            # not an observed direct full-pin Q-coil graph.
            [
                ["LD %WRITE_READ_VAR0." + s, "ST " + t]
                for s, t in zip(
                    ("DONE", "BUSY", "ABORTED", "ERROR"),
                    ("%M30", "%M31", "%M32", "%Q0.0"),
                )
            ],
        )
        for following in suffixes:
            with self.subTest(following=following):
                program = self.program()
                program.rungs += copy.deepcopy(following)
                destination = self.export(program)
                native = self.native_rungs(destination)
                self.assertEqual(len(native), 1 + len(following))
                self.assertEqual(len(self.graph(native[0])), 3)
                self.assertEqual([self.il(r) for r in native], program.rungs)
                self.assertEqual(load_project(destination).rungs, program.rungs)

    def test_complete_ordered_quartet_still_prefers_fifteen_line_full_graph(self):
        program = self.program()
        program.rungs += [
            ["LD %WRITE_READ_VAR0." + status, "ST %M" + str(30 + i)]
            for i, status in enumerate(("DONE", "BUSY", "ABORTED", "ERROR"))
        ]
        destination = self.export(program)
        native = self.native_rungs(destination)
        self.assertEqual(len(native), 1)
        self.assertEqual(len(self.il(native[0])), 15)
        self.assertEqual(len(self.graph(native[0])), 27)
        self.assertEqual(load_project(destination).rungs, program.rungs)

    def test_bare_graph_corruption_and_mixed_content_fail_before_canonical_import(self):
        self.import_observed(
            self.fixture()
        )  # A reject-everything implementation is not a control.
        for change in (
            "missing",
            "extra",
            "class",
            "address",
            "row",
            "column",
            "wire",
            "swapped",
            "field",
            "duplicate",
            "nested",
            "attribute",
            "coordinate",
            "empty",
        ):
            tree = ET.parse(self.fixture())
            graph = tree.find(".//RungEntity/LadderElements")
            if change == "missing":
                graph.remove(graph[1])
            elif change == "extra":
                graph.append(copy.deepcopy(graph[0]))
            elif change == "class":
                graph[2].find("ElementType").text = "ReadVarBasic"
            elif change == "address":
                graph[2].find("Descriptor").text = "%WRITE_READ_VAR1"
            elif change == "row":
                graph[1].find("Row").text = "0"
            elif change == "column":
                graph[2].find("Column").text = "2"
            elif change == "wire":
                graph[2].find("ChosenConnection").text = "Left, Right"
            elif change == "swapped":
                graph[0].find("Descriptor").text = "%M25"
            elif change == "field":
                ET.SubElement(graph[0], "Unknown").text = "true"
            elif change == "duplicate":
                graph[0].append(copy.deepcopy(graph[0].find("Descriptor")))
            elif change == "nested":
                ET.SubElement(graph[0].find("Descriptor"), "Value").text = "%M24"
            elif change == "attribute":
                graph[0].set("enabled", "true")
            elif change == "coordinate":
                graph[2].find("Column").text = "01"
            else:
                graph.clear()
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(self.save(tree))
        for path in (
            ".//InstructionLines",
            ".//InstructionLineEntity",
            ".//InstructionLine",
            ".//InstructionLineEntity/Comment",
            ".//LadderElements",
            ".//LadderEntity",
            ".//LadderEntity/Descriptor",
        ):
            tree = ET.parse(self.fixture())
            tree.find(path).tail = "uninterpreted active text"
            with self.subTest(path=path), self.assertRaises(CompileError):
                load_project(self.save(tree))

    def test_il_only_negated_and_constant_imports_do_not_admit_new_native_graphs(self):
        self.import_observed(self.fixture())
        for predicate, typ, descriptor in (
            ("LDN %M24", "NegatedContact", "%M24"),
            ("LD 0", "NormalContact", "0"),
            ("LD 1", "NormalContact", "1"),
            ("LD %I0.0", "NormalContact", "%I0.0"),
        ):
            tree = ET.parse(self.fixture())
            tree.findall(".//InstructionLine")[1].text = predicate
            graph = tree.find(".//LadderElements")
            graph[0].find("ElementType").text = typ
            graph[0].find("Descriptor").text = descriptor
            with self.subTest(predicate=predicate), self.assertRaises(CompileError):
                load_project(self.save(tree))
            graph.clear()
            tree.find(".//IsLadderSelected").text = "false"
            program = load_project(self.save(tree))
            self.assertEqual(program.rungs[0][1], predicate)
            self.assert_atomic_failure(program, self.fixture())

    def test_actual_level_link_authority_and_late_failures_preserve_destinations(self):
        valid = self.program()
        self.export(valid)
        valid.metadata.update(
            functional_level="FunctLevelMan21_0", serial_addressing="MasterAddressing"
        )
        for change in ("lower", "unknown", "slave"):
            tree = ET.parse(self.fixture())
            if change == "lower":
                tree.find("ManagementLevel").text = "FunctLevelMan20_0"
            elif change == "unknown":
                tree.find("ManagementLevel").text = "FunctLevelMan99_0"
            else:
                tree.find(
                    "HardwareConfiguration/Plc/SerialLineConfiguration/Addressing"
                ).text = "SlaveAddressing"
            template = self.save(tree)
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(template)
            self.assert_atomic_failure(valid, template)
        invalid = copy.deepcopy(valid)
        invalid.communications["%WRITE_READ_VAR1"] = copy.deepcopy(
            valid.communications["%WRITE_READ_VAR0"]
        )
        invalid.rungs += [
            [
                "BLK %WRITE_READ_VAR1",
                "LDN %M26",
                "EXECUTE",
                "LD %M27",
                "ABORT",
                "END_BLK",
            ]
        ]
        self.assert_atomic_failure(invalid, self.fixture())
        forged = self.program()
        forged.metadata.update(
            functional_level="FunctLevelMan1_0",
            serial_addressing="SlaveAddressing",
            native_full_pin_groups=[{"key": "%WRITE_READ_VAR0", "canonical_rungs": 5}],
        )
        destination = self.export(forged)
        self.assertEqual(len(self.native_rungs(destination)), 1)
        self.assertEqual(len(self.graph(self.native_rungs(destination)[0])), 3)

    def test_labels_allow_entry_to_separate_status_without_calling_update(self):
        program = self.program()
        program.rungs.insert(0, ["LD %M9", "JMPC %L3"])
        program.rungs += [["%L3:", "LD %WRITE_READ_VAR0.DONE", "ST %M30"]]
        destination = self.export(program)
        imported = load_project(destination)
        self.assertEqual(imported.rungs, program.rungs)
        peer = MemoryModbusPeer(holding_registers=[0] * 60)
        transport = RecordingTransport(peer)
        machine = Machine(imported, communication_transport=transport)
        machine.step({}, 10)  # Establish the FB's initial false input state.
        machine.memory[9] = machine.memory[24] = True
        machine.memory[30] = True
        machine.step({}, 10)
        self.assertFalse(machine.memory[30])
        self.assertEqual(transport.requests, [])
        machine.memory[9] = False
        machine.step({}, 10)
        self.assertEqual(
            transport.requests, [bytes.fromhex("17 0029 0003 0011 0002 04 00000000")]
        )

    def test_reordered_alias_stores_keep_last_write_and_next_invocation_inputs(self):
        program = self.program()
        program.rungs += [
            ["LD %WRITE_READ_VAR0.BUSY", "ST %M25"],
            ["LD %WRITE_READ_VAR0.DONE", "ST %M24"],
            ["LD %WRITE_READ_VAR0.ABORTED", "ST %M25"],
        ]
        destination = self.export(program)
        imported = load_project(destination)
        self.assertEqual(imported.rungs, program.rungs)
        peer = MemoryModbusPeer(holding_registers=[0] * 60)
        peer.holding_registers[41:44] = [0x8001, 0x1234, 0xABCD]
        transport = RecordingTransport(peer)
        machine = Machine(imported, communication_transport=transport)
        machine.words[300:302] = [0x1234, 0xABCD]
        machine.step({}, 10)
        machine.memory[24] = True
        machine.step({}, 10)
        self.assertTrue(machine.read("%WRITE_READ_VAR0.BUSY", {}))
        self.assertEqual([machine.memory[i] for i in (24, 25)], [False, False])
        machine.step({}, 10)
        machine.step({}, 10)
        self.assertTrue(machine.read("%WRITE_READ_VAR0.DONE", {}))
        self.assertEqual([machine.memory[i] for i in (24, 25)], [True, False])
        self.assertEqual(machine.words[400:403], [0x8001, 0x1234, 0xABCD])
        self.assertEqual(
            transport.requests, [bytes.fromhex("17 0029 0003 0011 0002 04 1234abcd")]
        )
        machine.step({}, 10)
        self.assertEqual(len(transport.requests), 2)

    def test_bare_audit_looking_comment_cannot_expand_five_origins_or_change_program(
        self,
    ):
        expected = self.program().rungs
        for payload in (
            "[]",
            "malformed",
            json.dumps([{"generated": "%L3: END Man1 slave"}] * 5),
        ):
            tree = ET.parse(self.fixture())
            tree.find(".//MainComment").text = (
                "Operator note\nM200_CPP_FULL_PIN_ORIGINS=" + payload
            )
            imported = self.import_observed(self.save(tree))
            self.assertEqual(imported.rungs, expected)
            self.assertNotIn("native_full_pin_groups", imported.metadata)
            destination = self.export(imported)
            self.assertEqual(len(self.il(self.native_rungs(destination)[0])), 6)

    def test_bare_origins_do_not_consume_following_rungs_during_or_normalization(self):
        program = self.program()
        program.rungs.insert(0, ["LD %M4", "ST %M5"])
        program.rungs += [
            ["LD %M6", "ST %M7"],
            ["LD %M0", "OR %M1", "ST %M2"],
        ]
        program.metadata["rung_origins"] = [
            {"file": "before.cpp", "line": 1},
            {"file": "bare.cpp", "line": 20},
            {"file": "after.cpp", "line": 99},
            {"file": "expanded.cpp", "line": 120},
        ]
        # Stale audit metadata must not select a full group or overwrite the
        # ordinary following-rung origin.
        program.metadata["native_full_pin_groups"] = [
            {
                "key": "%WRITE_READ_VAR0",
                "canonical_start": 1,
                "canonical_rungs": 5,
                "origin": {"main_comment": "FORGED END %L3: unverified full group"},
                "source_origins": [{"file": "forged.cpp"}] * 5,
            }
        ]
        destination = self.export(program)
        native = self.native_rungs(destination)
        self.assertIn("before.cpp:1:", native[0].findtext("MainComment"))
        self.assertIn("bare.cpp:20:", native[1].findtext("MainComment"))
        self.assertIn("after.cpp:99:", native[2].findtext("MainComment"))
        self.assertEqual(len(self.graph(native[1])), 3)
        self.assertNotIn(
            "M200_CPP_FULL_PIN_ORIGINS=", native[1].findtext("MainComment")
        )
        self.assertNotIn("FORGED", native[1].findtext("MainComment"))

    def test_native_partial_pin_bodies_remain_distinct_from_ordinary_status_rungs(self):
        self.import_observed(self.fixture())
        full = FIXTURES / "official_tm200ce40t_modbus_full_pin_write_read.smbp"
        for count in (1, 2, 3):
            tree = ET.parse(full)
            instructions = tree.find(".//InstructionLines")
            for index in range(13, 5 + count * 2, -1):
                instructions.remove(instructions[index])
            self.assertEqual(len(instructions), 7 + count * 2)
            # A 9/11/13-line body may never become a six-line call that silently
            # discards its native status stores, even with unselected graphics.
            tree.find(".//LadderElements").clear()
            tree.find(".//IsLadderSelected").text = "false"
            with self.subTest(status_count=count), self.assertRaises(CompileError):
                load_project(self.save(tree))

    def test_last_instance_inputs_and_both_full_buffer_extents_export_without_hash_dispatch(
        self,
    ):
        program = self.program()
        program.communications = {
            "%WRITE_READ_VAR31": ModbusConfig(
                kind="WRITE_READ_VAR",
                first_obj=65534,
                quantity=2,
                index_data=7998,
                first_read_obj=65533,
                read_quantity=3,
                index_data_in=7997,
            )
        }
        program.rungs = [
            [
                "BLK %WRITE_READ_VAR31",
                "LD %M1023",
                "EXECUTE",
                "LD %M1022",
                "ABORT",
                "END_BLK",
            ]
        ]
        destination = self.export(program)
        imported = load_project(destination)
        self.assertEqual(imported.communications, program.communications)
        self.assertEqual(imported.rungs, program.rungs)
        self.assertEqual(memory_words_used(imported), {7997, 7998, 7999})
        for bad in ("LD %M1024", "LD %M010", "LD %Q0.0"):
            invalid = copy.deepcopy(program)
            invalid.rungs[0][1] = bad
            self.assert_atomic_failure(invalid, self.fixture())

    def test_native_sdk_vm_and_reverse_keep_separate_status_reads_without_transport(
        self,
    ):
        program = self.program()
        program.rungs = (
            [
                ["LD %I0.0", "ST %M24"],
                ["LD %I0.1", "ST %M25"],
            ]
            + program.rungs
            + [
                ["LD %WRITE_READ_VAR0.ERROR", "ST %Q0.0"],
                ["LD %WRITE_READ_VAR0.DONE", "ST %Q0.1"],
                ["LD %WRITE_READ_VAR0.BUSY", "ST %Q0.2"],
                ["LD %WRITE_READ_VAR0.ABORTED", "ST %Q0.3"],
            ]
        )
        source = self.work / "native.cpp"
        source.write_text(to_cpp(program))
        frames = [
            {"inputs": {"0": value}, "dt_ms": 10}
            for value in (True, False, True, True, False)
        ]
        expected = [
            [False, False, False, False],
            [False, False, False, False],
            [True, False, False, False],
            [True, False, False, False],
            [False, False, False, False],
        ]
        self.assertEqual([row[:4] for row in run_native(source, frames)], expected)
        machine = Machine(program)
        self.assertEqual(
            [machine.step(frame["inputs"], 10)[:4] for frame in frames], expected
        )
        compiled = compile_source(source)
        destination = self.export(compiled)
        imported = load_project(destination)
        self.assertEqual(
            [
                len(self.il(r))
                for r in self.native_rungs(destination)
                if self.il(r)[0].startswith("BLK ")
            ],
            [6],
        )
        machine = Machine(imported)
        self.assertEqual(
            [machine.step(frame["inputs"], 10)[:4] for frame in frames], expected
        )


if __name__ == "__main__":
    unittest.main()
