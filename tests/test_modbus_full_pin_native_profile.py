"""Authentic full-pin bodies, exact graphics and ordered canonical semantics."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from m200.communication import parse_block
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import normalize
from m200.model import CompileError, Timer
from m200.modbus import MemoryModbusPeer, MemoryTransport, ModbusConfig
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    (
        "read",
        "READ_VAR",
        "8154e130ce73b6a1b6e90f5876264437ec36778207fc38c3a3661152059f9e50",
    ),
    (
        "write",
        "WRITE_VAR",
        "ae6ffad294a36e79656f36845f2a0bebf19df6f3e60b8aa7b82597b867b79af3",
    ),
    (
        "write_read",
        "WRITE_READ_VAR",
        "9e7a3359a99c433bdebe7eaca21235960de806fdfb8151a678e39345e4b3588f",
    ),
)


class RecordingTransport(MemoryTransport):
    def __init__(self, peer, latency_ms=20):
        super().__init__(peer, latency_ms)
        self.requests = []

    def start(self, config, pdu, now_ms):
        token = super().start(config, pdu, now_ms)
        self.requests.append(pdu)
        return token


class ModbusFullPinNativeProfileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)

    def fixture(self, suffix):
        return FIXTURES / ("official_tm200ce40t_modbus_full_pin_" + suffix + ".smbp")

    def save(self, tree):
        path = self.work / "modified.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path

    def graph(self, root):
        return [
            (
                n.findtext("ElementType"),
                n.findtext("Descriptor") or "",
                n.findtext("Row"),
                n.findtext("Column"),
                n.findtext("ChosenConnection"),
            )
            for n in root.findall(".//RungEntity/LadderElements/LadderEntity")
        ]

    def expected_graph(
        self,
        kind,
        execute="%M10",
        abort="%M13",
        outputs=("%M14", "%M15", "%M16", "%M17"),
    ):
        # Literal grid independently transcribed from the three official saves.
        typ = {
            "READ_VAR": "ReadVarBasic",
            "WRITE_VAR": "WriteVarBasic",
            "WRITE_READ_VAR": "WriteReadVarBasic",
        }[kind]
        return (
            [
                ("NormalContact", execute, "0", "0", "Left, Right"),
                ("NormalContact", abort, "1", "0", "Left, Right"),
                (typ, "%" + kind + "0", "0", "1", "Left, Right"),
            ]
            + [
                ("Line", "", str(row), str(column), "Left, Right")
                for column in (5, 6, 7, 8, 9)
                for row in (0, 1, 2, 3)
            ]
            + [("Coil", outputs[row], str(row), "10", "Left") for row in (0, 1, 2, 3)]
        )

    def assert_preserved_failure(self, program, template, message=None):
        before = copy.deepcopy(program.as_dict())
        template_bytes = template.read_bytes()
        for existing in (False, True):
            destination = self.work / ("existing.smbp" if existing else "absent.smbp")
            if existing:
                destination.write_bytes(b"PRESERVE")
            if message:
                context = self.assertRaisesRegex(CompileError, message)
            else:
                context = self.assertRaises(CompileError)
            with context:
                write_project(program, template, destination)
            self.assertEqual(template.read_bytes(), template_bytes)
            self.assertEqual(program.as_dict(), before)
            if existing:
                self.assertEqual(destination.read_bytes(), b"PRESERVE")
            else:
                self.assertFalse(destination.exists())

    def peer(self):
        peer = MemoryModbusPeer(
            holding_registers=[0] * 70,
            input_registers=[],
            coils=[False] * 120,
            discrete_inputs=[False] * 60,
        )
        for index in (17, 24, 32, 33):
            peer.discrete_inputs[index] = True
        peer.holding_registers[41:44] = [0x8001, 0xFFFF, 0x1234]
        peer.coils[72] = peer.coils[90] = True
        return peer

    def flags(self, machine):
        return [machine.memory[index] for index in (14, 15, 16, 17)]

    def test_exact_three_saves_import_all_four_ordered_status_stores(self):
        # Dropping a status, swapping its key, or skipping native-body normalization
        # must fail this independent, literal canonical expectation.
        for suffix, kind, digest in CASES:
            with self.subTest(kind=kind):
                path = self.fixture(suffix)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
                self.assertIn(b"\r\n", path.read_bytes())
                root = ET.parse(path)
                self.assertEqual(len(root.findall(".//InstructionLine")), 15)
                self.assertEqual(len(root.findall(".//LadderEntity")), 27)
                try:
                    program = load_project(path)
                except CompileError as error:
                    self.fail(
                        "Exact full-pin save must import without dropping outputs: "
                        + str(error)
                    )
                key = "%" + kind + "0"
                self.assertEqual(
                    program.rungs,
                    [
                        [
                            "BLK " + key,
                            "LD %M10",
                            "EXECUTE",
                            "LD %M13",
                            "ABORT",
                            "END_BLK",
                        ],
                        ["LD " + key + ".DONE", "ST %M14"],
                        ["LD " + key + ".BUSY", "ST %M15"],
                        ["LD " + key + ".ABORTED", "ST %M16"],
                        ["LD " + key + ".ERROR", "ST %M17"],
                    ],
                )

    def test_imported_asymmetric_configs_and_complete_memory_buffers_are_retained(self):
        expected = {
            "read": (
                "%READ_VAR0",
                ModbusConfig(
                    kind="READ_VAR",
                    obj_type=1,
                    first_obj=17,
                    quantity=17,
                    index_data=200,
                ),
            ),
            "write": (
                "%WRITE_VAR0",
                ModbusConfig(
                    kind="WRITE_VAR",
                    obj_type=2,
                    first_obj=73,
                    quantity=17,
                    index_data=240,
                ),
            ),
            "write_read": (
                "%WRITE_READ_VAR0",
                ModbusConfig(
                    kind="WRITE_READ_VAR",
                    first_obj=17,
                    quantity=2,
                    index_data=300,
                    first_read_obj=41,
                    read_quantity=3,
                    index_data_in=400,
                ),
            ),
        }
        from m200.numeric import memory_words_used

        for suffix, (key, config) in expected.items():
            with self.subTest(kind=suffix):
                program = load_project(self.fixture(suffix))
                self.assertEqual(program.communications, {key: config})
                self.assertEqual(
                    memory_words_used(program),
                    {200, 201}
                    if suffix == "read"
                    else {240, 241}
                    if suffix == "write"
                    else {300, 301, 400, 401, 402},
                )

    def test_canonical_export_emits_literal_fifteen_lines_and_all_27_entities(self):
        for suffix, kind, _ in CASES:
            with self.subTest(kind=kind):
                template = self.fixture(suffix)
                template_before = template.read_bytes()
                program = load_project(template)
                program.metadata["rung_origins"] = [
                    {"file": "authored.cpp", "line": n, "column": 1}
                    for n in (10, 20, 30, 40, 50)
                ]
                before = copy.deepcopy(program.as_dict())
                destination = self.work / (suffix + ".smbp")
                write_project(program, template, destination)
                root = ET.parse(destination)
                self.assertEqual(len(root.findall(".//RungEntity")), 1)
                self.assertEqual(
                    [
                        " ".join((n.text or "").split())
                        for n in root.findall(".//InstructionLine")
                    ],
                    [
                        "BLK %" + kind + "0",
                        "LD %M10",
                        "EXECUTE",
                        "LD %M13",
                        "ABORT",
                        "OUT_BLK",
                        "LD DONE",
                        "ST %M14",
                        "LD BUSY",
                        "ST %M15",
                        "LD ABORTED",
                        "ST %M16",
                        "LD ERROR",
                        "ST %M17",
                        "END_BLK",
                    ],
                )
                self.assertEqual(self.graph(root), self.expected_graph(kind))
                self.assertEqual(load_project(destination).rungs, program.rungs)
                self.assertEqual(
                    load_project(destination).metadata["rung_origins"],
                    program.metadata["rung_origins"],
                )
                self.assertEqual(program.as_dict(), before)
                self.assertEqual(template.read_bytes(), template_before)
                comment = root.findtext(".//RungEntity/MainComment")
                self.assertEqual(
                    json.loads(comment.split("\nM200_CPP_FULL_PIN_ORIGINS=", 1)[1]),
                    program.metadata["rung_origins"],
                )
                self.assertEqual(
                    ET.canonicalize(
                        ET.tostring(
                            root.find("HardwareConfiguration"), encoding="unicode"
                        ),
                        strip_text=True,
                    ),
                    ET.canonicalize(
                        ET.tostring(
                            ET.parse(template).find("HardwareConfiguration"),
                            encoding="unicode",
                        ),
                        strip_text=True,
                    ),
                )

    def test_public_cpp_reverse_recompile_and_or_composition_keep_complete_group(self):
        for suffix, kind, _ in CASES:
            with self.subTest(kind=kind):
                program = load_project(self.fixture(suffix))
                program.metadata.pop("rung_origins", None)
                program.rungs.append(["LD %M0", "OR %M1", "ST %M2"])
                source = self.work / (suffix + ".cpp")
                source.write_text(to_cpp(program))
                compiled = compile_source(source)
                self.assertEqual(compiled.communications, program.communications)
                destination = self.work / (suffix + ".smbp")
                write_project(compiled, self.fixture(suffix), destination)
                root = ET.parse(destination)
                full = [
                    r
                    for r in root.findall(".//RungEntity")
                    if r.findtext(
                        "InstructionLines/InstructionLineEntity/InstructionLine", ""
                    ).startswith("BLK")
                ]
                self.assertEqual(len(full), 1)
                self.assertEqual(len(full[0].find("InstructionLines")), 15)
                self.assertEqual(len(full[0].find("LadderElements")), 27)
                imported = load_project(destination)
                self.assertEqual(imported.communications, program.communications)
                expected_stores = [
                    ["LD %" + kind + "0." + name, "ST %M" + str(14 + i)]
                    for i, name in enumerate(("DONE", "BUSY", "ABORTED", "ERROR"))
                ]
                at = next(
                    i
                    for i, rung in enumerate(imported.rungs)
                    if rung[0].startswith("BLK")
                )
                self.assertEqual(imported.rungs[at + 1 : at + 5], expected_stores)

    def test_graph_corruption_is_rejected_before_output_normalization(self):
        load_project(self.fixture("write_read"))  # Valid admission is the control.
        for change in (
            "missing",
            "duplicate",
            "row",
            "column",
            "connection",
            "coil_swap",
            "class",
            "input",
            "coil_action",
            "line_gap",
            "line_extra",
            "coordinate_lexeme",
            "field",
            "nested",
            "tail",
            "empty",
            "unselected_empty",
        ):
            tree = ET.parse(self.fixture("write_read"))
            graph = tree.find(".//RungEntity/LadderElements")
            if change == "missing":
                graph.remove(graph[-1])
            elif change == "duplicate":
                graph.append(copy.deepcopy(graph[-1]))
            elif change == "row":
                graph[2].find("Row").text = "1"
            elif change == "column":
                graph[2].find("Column").text = "2"
            elif change == "connection":
                graph[2].find("ChosenConnection").text = "Left"
            elif change == "coil_swap":
                graph[-1].find("Descriptor").text = "%M14"
            elif change == "class":
                graph[2].find("ElementType").text = "WriteVarBasic"
            elif change == "input":
                graph[0].find("Descriptor").text = "%M11"
            elif change == "coil_action":
                graph[-1].find("ElementType").text = "SetCoil"
            elif change == "line_gap":
                graph.remove(graph[13])
            elif change == "line_extra":
                graph.append(copy.deepcopy(graph[13]))
            elif change == "coordinate_lexeme":
                graph[2].find("Column").text = "01"
            elif change == "field":
                ET.SubElement(graph[2], "Unknown").text = "true"
            elif change == "nested":
                ET.SubElement(graph[2].find("Row"), "int").text = "0"
            elif change == "tail":
                graph[2].find("Row").tail = "unexpected mixed content"
            else:
                graph.clear()
                if change == "unselected_empty":
                    tree.find(".//RungEntity/IsLadderSelected").text = "false"
            path = self.save(tree)
            before = path.read_bytes()
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(path)
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_native_pin_layouts_and_unverified_operands_fail_closed(self):
        load_project(self.fixture("read"))
        for index, text in (
            (2, "EXECUTE %M10"),
            (4, "DONE"),
            (5, "OUT_BLK %READ_VAR0"),
            (6, "LD BUSY"),
            (7, "S %M14"),
            (8, "LD DONE"),
            (10, "LD %READ_VAR0.ABORTED"),
            (14, "END"),
            (1, "LDN %M10"),
            (1, "LD 0"),
            (1, "LD %I0.0"),
            (3, "LD %M00"),
            (7, "ST %I0.0"),
            (7, "ST %Q0.0"),
            (7, "ST %M1024"),
        ):
            tree = ET.parse(self.fixture("read"))
            tree.findall(".//InstructionLine")[index].text = text
            with self.subTest(index=index, text=text), self.assertRaises(CompileError):
                load_project(self.save(tree))
        for count_change in ("drop", "extra"):
            tree = ET.parse(self.fixture("read"))
            instructions = tree.find(".//InstructionLines")
            if count_change == "drop":
                instructions.remove(instructions[5])
            else:
                instructions.append(copy.deepcopy(instructions[-1]))
            with (
                self.subTest(count_change=count_change),
                self.assertRaises(CompileError),
            ):
                load_project(self.save(tree))
        # The established parser must never accept fifteen lines and omit outputs.
        raw = [
            " ".join((n.text or "").split())
            for n in ET.parse(self.fixture("read")).findall(".//InstructionLine")
        ]
        with self.assertRaises(CompileError):
            parse_block(raw)

    def test_actual_full_pin_level_object_and_link_authority_cannot_be_forged(self):
        program = load_project(self.fixture("read"))
        program.metadata["functional_level"] = "FunctLevelMan21_0"
        for change in ("lower", "unknown", "other_object", "slave"):
            tree = ET.parse(self.fixture("read"))
            if change == "lower":
                tree.find("ManagementLevel").text = "FunctLevelMan20_0"
            elif change == "unknown":
                tree.find("ManagementLevel").text = "FunctLevelMan99_0"
            elif change == "other_object":
                tree.find(".//ObjType/Value/FBComObjTypeParameterEnums").text = "MW"
            else:
                tree.find(
                    "HardwareConfiguration/Plc/SerialLineConfiguration/Addressing"
                ).text = "SlaveAddressing"
            template = self.save(tree)
            with self.subTest(change=change), self.assertRaises(CompileError):
                load_project(template)
            if change != "other_object":
                self.assert_preserved_failure(program, template)
        program.communications["%READ_VAR0"] = ModbusConfig(
            kind="READ_VAR", first_obj=17, quantity=17, index_data=200
        )
        self.assert_preserved_failure(program, self.fixture("read"))
        program = load_project(self.fixture("read"))
        program.metadata.update(
            functional_level="FunctLevelMan1_0", serial_addressing="SlaveAddressing"
        )
        destination = self.work / "allowed.smbp"
        write_project(program, self.fixture("read"), destination)
        self.assertEqual(load_project(destination).rungs, program.rungs)

    def test_unsafe_partial_groups_and_late_failures_preserve_all_inputs(self):
        valid = load_project(self.fixture("write_read"))
        valid.metadata.pop("rung_origins", None)
        for change in (
            "missing",
            "interior_label",
            "interior_entry",
            "reordered",
            "other_key",
            "interleaved",
            "set_coil",
            "Q_coil",
            "negated_input",
            "constant_input",
        ):
            program = copy.deepcopy(valid)
            if change == "missing":
                program.rungs.pop()
            elif change == "interior_label":
                program.rungs[2].insert(0, "%L3:")
            elif change == "interior_entry":
                program.rungs[2].insert(0, "%L3:")
                program.rungs.insert(0, ["LD %M0", "JMPC %L3"])
            elif change == "reordered":
                program.rungs[1], program.rungs[2] = program.rungs[2], program.rungs[1]
            elif change == "other_key":
                program.rungs[2][0] = "LD %WRITE_READ_VAR1.BUSY"
            elif change == "interleaved":
                program.rungs.insert(2, ["LD %M0", "ST %M1"])
            elif change == "set_coil":
                program.rungs[2][1] = "S %M15"
            elif change == "Q_coil":
                program.rungs[2][1] = "ST %Q0.0"
            elif change == "negated_input":
                program.rungs[0][1] = "LDN %M10"
            else:
                program.rungs[0][1] = "LD 1"
            with self.subTest(change=change):
                self.assert_preserved_failure(program, self.fixture("write_read"))
        late = copy.deepcopy(valid)
        late.communications["%WRITE_READ_VAR1"] = copy.deepcopy(
            late.communications["%WRITE_READ_VAR0"]
        )
        late.rungs += [
            [line.replace("%WRITE_READ_VAR0", "%WRITE_READ_VAR1") for line in rung]
            for rung in valid.rungs[:-1]
        ]
        self.assert_preserved_failure(late, self.fixture("write_read"))

    def test_labelled_block_and_jump_around_full_group_preserve_skipped_coils(self):
        program = load_project(self.fixture("read"))
        program.metadata.pop("rung_origins", None)
        program.rungs[0].insert(0, "%L0:")
        program.rungs.insert(0, ["LD %M9", "JMPC %L1"])
        program.rungs.append(["%L1:", "LD %M14", "ST %M20"])
        before = copy.deepcopy(program.as_dict())
        destination = self.work / "flow.smbp"
        write_project(program, self.fixture("read"), destination)
        imported = load_project(destination)
        self.assertEqual(imported.rungs, program.rungs)
        self.assertEqual(program.as_dict(), before)
        machine = Machine(imported)
        for index, value in {
            9: True,
            10: True,
            13: False,
            14: True,
            15: True,
            16: True,
            17: True,
        }.items():
            machine.memory[index] = value
        machine.step({}, 10)
        self.assertEqual([machine.memory[i] for i in (14, 15, 16, 17, 20)], [True] * 5)
        machine.memory[9] = False
        machine.memory[10] = False
        machine.step({}, 10)
        self.assertEqual([machine.memory[i] for i in (14, 15, 16, 17, 20)], [False] * 5)

    def test_grouped_origins_keep_following_index_and_original_human_comment(self):
        tree = ET.parse(self.fixture("read"))
        tree.find(
            ".//MainComment"
        ).text = "Operator note: keep this exact native comment."
        program = load_project(self.save(tree))
        program.rungs.insert(0, ["LD %M4", "ST %M5"])
        program.rungs.append(["LD %M6", "ST %M7"])
        origins = (
            [{"file": "before.cpp", "line": 1}]
            + [
                {"file": "block.cpp", "line": i, "generated": "part" + str(i)}
                for i in (10, 20, 30, 40, 50)
            ]
            + [{"file": "after.cpp", "line": 99}]
        )
        program.metadata["rung_origins"] = origins
        before = copy.deepcopy(program.as_dict())
        destination = self.work / "origins.smbp"
        write_project(program, self.fixture("read"), destination)
        rungs = ET.parse(destination).findall(".//RungEntity")
        self.assertEqual(len(rungs), 3)
        comment = rungs[1].findtext("MainComment")
        self.assertEqual(
            comment.split("\nM200_CPP_FULL_PIN_ORIGINS=", 1)[0],
            "Operator note: keep this exact native comment.",
        )
        self.assertEqual(
            json.loads(comment.split("\nM200_CPP_FULL_PIN_ORIGINS=", 1)[1]),
            origins[1:6],
        )
        self.assertIn("after.cpp:99:", rungs[2].findtext("MainComment"))
        imported = load_project(destination)
        self.assertEqual(imported.metadata["rung_origins"][1:6], origins[1:6])
        second = self.work / "origins-second.smbp"
        write_project(imported, self.fixture("read"), second)
        self.assertEqual(
            ET.parse(second).findall(".//RungEntity")[1].findtext("MainComment"),
            comment,
        )
        self.assertEqual(program.as_dict(), before)

    def test_complex_tail_normalization_preserves_the_five_original_group_origins(self):
        program = load_project(self.fixture("read"))
        program.rungs.append(["LD %M0", "OR %M1", "ST %M2"])
        origins = [
            {"file": "group.cpp", "line": n, "column": 3} for n in (10, 20, 30, 40, 50)
        ] + [{"file": "tail.cpp", "line": 99}]
        program.metadata["rung_origins"] = origins
        before = copy.deepcopy(program.as_dict())
        destination = self.work / "complex-origins.smbp"
        write_project(program, self.fixture("read"), destination)
        full = next(
            r
            for r in ET.parse(destination).findall(".//RungEntity")
            if len(r.find("InstructionLines")) == 15
        )
        payload = full.findtext("MainComment").split("\nM200_CPP_FULL_PIN_ORIGINS=", 1)[
            1
        ]
        self.assertEqual(json.loads(payload), origins[:5])
        self.assertEqual(program.as_dict(), before)

    def test_normalization_keeps_before_after_and_expanded_source_origins(self):
        program = load_project(self.fixture("read"))
        program.rungs.insert(0, ["LD %M4", "ST %M5"])
        program.rungs.extend([["LD %M6", "ST %M7"], ["LD %M0", "OR %M1", "ST %M2"]])
        origins = (
            [{"file": "before.cpp", "line": 1}]
            + [{"file": "group.cpp", "line": n} for n in (10, 20, 30, 40, 50)]
            + [{"file": "after.cpp", "line": 99}, {"file": "expanded.cpp", "line": 120}]
        )
        program.metadata["rung_origins"] = origins
        before = copy.deepcopy(program.as_dict())
        normalized = normalize(program)
        self.assertEqual(normalized.metadata["rung_origins"][:7], origins[:7])
        expanded = normalized.metadata["rung_origins"][7:]
        self.assertGreater(len(expanded), 1)
        self.assertTrue(all(origin == origins[7] for origin in expanded))
        without_origins = copy.deepcopy(program)
        without_origins.metadata.pop("rung_origins")
        self.assertEqual(normalize(without_origins).rungs, normalized.rungs)
        self.assertEqual(program.as_dict(), before)

    def test_normalization_without_source_origins_retains_generated_fallback(self):
        program = load_project(self.fixture("read"))
        program.metadata.pop("rung_origins")
        program.rungs.append(["LD %M0", "OR %M1", "ST %M2"])
        normalized = normalize(program)
        origins = normalized.metadata["rung_origins"]
        self.assertEqual(
            origins[:5],
            [{"generated": "native logic source rung " + str(i)} for i in range(5)],
        )
        self.assertGreater(len(origins[5:]), 1)
        self.assertTrue(
            all(
                origin == {"generated": "native logic source rung 5"}
                for origin in origins[5:]
            )
        )

    def test_origin_audit_payload_is_closed_bounded_and_never_program_authority(self):
        program = load_project(self.fixture("read"))
        path = self.work / "audit.smbp"
        write_project(program, self.fixture("read"), path)
        valid = ET.parse(path)
        marker = "\nM200_CPP_FULL_PIN_ORIGINS="
        for payload in (
            "{}",
            "[]",
            '[{"file":"x","file":"y"},{},{},{},{}]',
            '[{"rungs":["END"]},{},{},{},{}]',
            '[{"line":true},{},{},{},{}]',
            '[{"column":0},{},{},{},{}]',
            '[{"file":1},{},{},{},{}]',
            "[{}, {}, {}, {}, {}]" + marker + "[]",
            '[{"generated":"' + "x" * 65536 + '"},{},{},{},{}]',
        ):
            tree = copy.deepcopy(valid)
            tree.find(".//MainComment").text = marker + payload
            with self.subTest(payload=payload[:70]), self.assertRaises(CompileError):
                load_project(self.save(tree))
        tree = copy.deepcopy(valid)
        tree.find(".//MainComment").text = marker + json.dumps(
            [{"generated": "pretend %L3: END SL1 slave Man1"}] * 5
        )
        self.assertEqual(load_project(self.save(tree)).rungs, program.rungs)

    def test_original_instruction_and_graph_mixed_tails_cannot_hide_during_normalization(
        self,
    ):
        load_project(self.fixture("read"))
        for path in (
            ".//InstructionLines",
            ".//InstructionLineEntity",
            ".//InstructionLine",
            ".//InstructionLineEntity/Comment",
            ".//LadderElements",
            ".//LadderEntity",
            ".//LadderEntity/Descriptor",
        ):
            tree = ET.parse(self.fixture("read"))
            tree.find(path).tail = "uninterpreted active text"
            with self.subTest(path=path), self.assertRaises(CompileError):
                load_project(self.save(tree))

    def test_four_line_updates_and_separate_status_rungs_retain_ordinary_export(self):
        for suffix, kind, _ in CASES:
            with self.subTest(kind=kind):
                program = load_project(self.fixture(suffix))
                program.rungs[0] = [
                    "BLK %" + kind + "0",
                    "LD %M10",
                    "EXECUTE",
                    "END_BLK",
                ]
                destination = self.work / (suffix + "-execute-only.smbp")
                write_project(program, self.fixture(suffix), destination)
                root = ET.parse(destination)
                self.assertEqual(len(root.findall(".//RungEntity")), 5)
                self.assertEqual(len(root.find(".//RungEntity/InstructionLines")), 4)
                self.assertNotIn(
                    "ABORT", [n.text for n in root.findall(".//InstructionLine")]
                )
                self.assertEqual(load_project(destination).rungs, program.rungs)

    def test_local_peer_literal_packets_and_all_four_output_coils_follow_timing(self):
        requests = {
            "read": bytes.fromhex("02 0011 0011"),
            "write": bytes.fromhex("0f 0049 0011 03 818001"),
            "write_read": bytes.fromhex("17 0029 0003 0011 0002 04 1234abcd"),
        }
        table = [
            (True, True, [False, False, False, False]),
            (False, False, [False, False, False, False]),
            (True, False, [False, True, False, False]),
            (False, False, [False, True, False, False]),
            (False, False, [True, False, False, False]),
        ]
        for suffix, _, _ in CASES:
            with self.subTest(kind=suffix):
                program = load_project(self.fixture(suffix))
                peer = self.peer()
                transport = RecordingTransport(peer, latency_ms=20)
                machine = Machine(program, communication_transport=transport)
                machine.words[199:203] = [0x7777, 0xAAAA, 0xBBBB, 0x8888]
                machine.words[240:242] = [0x8081, 0xFFFF]
                machine.words[300:302] = [0x1234, 0xABCD]
                machine.words[399:404] = [0x7777, 0xAAAA, 0xBBBB, 0xCCCC, 0x8888]
                machine.memory[18] = True
                for execute, abort, want in table:
                    machine.memory[10] = execute
                    machine.memory[13] = abort
                    machine.step({}, 10)
                    self.assertEqual(self.flags(machine), want)
                    self.assertTrue(machine.memory[18])
                self.assertEqual(transport.requests, [requests[suffix]])
                if suffix == "read":
                    self.assertEqual(
                        machine.words[199:203], [0x7777, 0x8081, 1, 0x8888]
                    )
                elif suffix == "write":
                    self.assertEqual(
                        peer.coils[73:90],
                        [
                            True,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            True,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            False,
                            True,
                            True,
                        ],
                    )
                    self.assertTrue(peer.coils[72] and peer.coils[90])
                    self.assertEqual(machine.words[240:242], [0x8081, 0xFFFF])
                else:
                    self.assertEqual(machine.words[300:302], [0x1234, 0xABCD])
                    self.assertEqual(
                        machine.words[399:404], [0x7777, 0x8001, 0xFFFF, 0x1234, 0x8888]
                    )

    def test_input_output_aliases_use_sampled_inputs_and_ordered_last_store(self):
        program = load_project(self.fixture("read"))
        program.rungs[1][1] = "ST %M10"
        program.rungs[2][1] = "ST %M13"
        program.rungs[3][1] = "ST %M13"
        destination = self.work / "aliases.smbp"
        write_project(program, self.fixture("read"), destination)
        root = ET.parse(destination)
        self.assertEqual(
            self.graph(root),
            self.expected_graph("READ_VAR", outputs=("%M10", "%M13", "%M13", "%M17")),
        )
        transport = RecordingTransport(self.peer(), latency_ms=20)
        machine = Machine(load_project(destination), communication_transport=transport)
        machine.step({}, 10)
        machine.memory[10] = True
        machine.step({}, 10)
        self.assertTrue(machine.read("%READ_VAR0.BUSY", {}))
        self.assertEqual(
            [machine.memory[i] for i in (10, 13, 17)], [False, False, False]
        )
        self.assertEqual(len(transport.requests), 1)
        machine.step({}, 10)
        machine.step({}, 10)
        self.assertTrue(machine.read("%READ_VAR0.DONE", {}))
        self.assertEqual(
            [machine.memory[i] for i in (10, 13, 17)], [True, False, False]
        )
        self.assertEqual(len(transport.requests), 1)
        machine.step({}, 10)
        self.assertTrue(machine.read("%READ_VAR0.BUSY", {}))
        self.assertEqual(len(transport.requests), 2)

    def test_abort_timeout_simultaneous_edges_and_absent_transport_are_not_success(
        self,
    ):
        for scenario in ("abort", "timeout", "simultaneous", "absent"):
            tree = ET.parse(self.fixture("write_read"))
            tree.find(".//Timeout/Value/int").text = "1"
            program = load_project(self.save(tree))
            transport = RecordingTransport(self.peer(), latency_ms=1000)
            machine = Machine(
                program,
                communication_transport=None if scenario == "absent" else transport,
            )
            machine.step({}, 10)
            machine.memory[10] = True
            if scenario == "simultaneous":
                machine.memory[13] = True
            machine.step({}, 100 if scenario == "timeout" else 10)
            if scenario == "abort":
                machine.memory[13] = True
                machine.step({}, 10)
                want = [False, False, True, False]
            elif scenario == "timeout":
                machine.memory[10] = False
                machine.step({}, 10)
                want = [False, False, False, True]
            elif scenario == "absent":
                want = [False, False, False, True]
            else:
                want = [False, False, False, False]
            with self.subTest(scenario=scenario):
                self.assertEqual(self.flags(machine), want)
                self.assertFalse(machine.read("%WRITE_READ_VAR0.DONE", {}))
                self.assertEqual(
                    len(transport.requests),
                    0 if scenario in ("simultaneous", "absent") else 1,
                )

    def test_native_sdk_and_vm_observe_full_pin_stores_without_fabricated_transport(
        self,
    ):
        program = load_project(self.fixture("write_read"))
        program.metadata.pop("rung_origins", None)
        program.rungs = (
            [["LD %I0.0", "ST %M10"], ["LD %I0.1", "ST %M13"]]
            + program.rungs
            + [[f"LD %M{14 + i}", f"ST %Q0.{i}"] for i in range(4)]
        )
        source = self.work / "native.cpp"
        source.write_text(to_cpp(program))
        frames = [
            {"inputs": {"0": v}, "dt_ms": 10} for v in (True, False, True, True, False)
        ]
        expected = [
            [False] * 4,
            [False] * 4,
            [False, False, False, True],
            [False, False, False, True],
            [False] * 4,
        ]
        self.assertEqual([row[:4] for row in run_native(source, frames)], expected)
        machine = Machine(program)
        self.assertEqual(
            [machine.step(frame["inputs"], frame["dt_ms"])[:4] for frame in frames],
            expected,
        )
        compiled = compile_source(source)
        destination = self.work / "native.smbp"
        write_project(compiled, self.fixture("write_read"), destination)
        imported = load_project(destination)
        machine = Machine(imported)
        self.assertEqual(
            [machine.step(frame["inputs"], frame["dt_ms"])[:4] for frame in frames],
            expected,
        )

    def test_last_memory_bits_words_and_instance31_are_fully_allocated(self):
        tree = ET.parse(self.fixture("read"))
        for node in tree.findall(".//InstructionLine"):
            text = " ".join((node.text or "").split())
            for old, new in (
                ("%READ_VAR0", "%READ_VAR31"),
                ("%M10", "%M1023"),
                ("%M13", "%M1022"),
                ("%M14", "%M1021"),
                ("%M15", "%M1020"),
                ("%M16", "%M1019"),
                ("%M17", "%M1018"),
            ):
                text = text.replace(old, new)
            node.text = text
        for node in tree.findall(".//LadderEntity/Descriptor"):
            node.text = {
                "%READ_VAR0": "%READ_VAR31",
                "%M10": "%M1023",
                "%M13": "%M1022",
                "%M14": "%M1021",
                "%M15": "%M1020",
                "%M16": "%M1019",
                "%M17": "%M1018",
            }.get(node.text, node.text)
        tree.find(".//IFunctionBlock/Address").text = "%READ_VAR31"
        tree.find(".//IFunctionBlock/Index").text = "31"
        tree.find(".//IndexData/Value/int").text = "7998"
        tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "8000"
        program = load_project(self.save(tree))
        destination = self.work / "limits.smbp"
        write_project(program, self.fixture("read"), destination)
        self.assertEqual(load_project(destination).rungs, program.rungs)
        self.assertEqual(
            ET.parse(destination).findtext(
                ".//MemoryWordsMemoryAllocation/ForcedCount"
            ),
            "8000",
        )
        tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "7999"
        with self.assertRaises(CompileError):
            load_project(self.save(tree))
        tree.find(".//MemoryWordsMemoryAllocation/ForcedCount").text = "8000"
        tree.find(".//IndexData/Value/int").text = "7999"
        with self.assertRaises(CompileError):
            load_project(self.save(tree))

    def test_conditional_end_and_following_timer_do_not_move_the_update_or_coils(self):
        program = load_project(self.fixture("read"))
        program.metadata.pop("rung_origins", None)
        program.rungs.insert(0, ["LD %M30", "ENDC"])
        program.timers[0] = Timer("TON", 20, 10)
        program.rungs.append(
            ["BLK %TM0", "LD %M31", "IN", "OUT_BLK", "LD Q", "ST %M34", "END_BLK"]
        )
        destination = self.work / "exit-timer.smbp"
        write_project(program, self.fixture("read"), destination)
        imported = load_project(destination)
        for candidate in (program, imported):
            transport = RecordingTransport(self.peer())
            machine = Machine(candidate, communication_transport=transport)
            for index in (14, 15, 16, 17, 30, 31, 34):
                machine.memory[index] = True
            machine.memory[10] = True
            machine.step({}, 10)
            self.assertEqual(self.flags(machine), [True] * 4)
            self.assertTrue(machine.memory[34])
            self.assertEqual(transport.requests, [])
            machine.memory[30] = False
            machine.memory[10] = False
            machine.step({}, 10)
            self.assertEqual(self.flags(machine), [False] * 4)
            machine.memory[30] = True
            machine.memory[10] = True
            machine.step({}, 10)
            self.assertEqual(self.flags(machine), [False] * 4)
            self.assertEqual(transport.requests, [])
            machine.memory[30] = False
            machine.step({}, 10)
            self.assertEqual(self.flags(machine), [False, True, False, False])
            self.assertEqual(transport.requests, [bytes.fromhex("02 0011 0011")])

    def test_public_cpp_loop_before_full_group_preserves_native_and_imported_results(
        self,
    ):
        source = self.work / "loop.cpp"
        source.write_text("""#include <plc.hpp>
plc::ReadVar remote{0,plc::Link::Serial1,1,100,plc::Object::DiscreteInputs,17,17,200};
void scan(){
  plc::i16 sum=0;
  for(plc::i16 i=1;i<=3;i=plc::add_i16(i,1)){sum=plc::add_i16(sum,i);}
  plc::write_word(20,sum);
  remote.update(plc::read_m(10),plc::read_m(13));
  plc::write_m(14,remote.done()); plc::write_m(15,remote.busy());
  plc::write_m(16,remote.aborted()); plc::write_m(17,remote.error());
  plc::output(0,sum==6);
}
""")
        program = compile_source(source)
        destination = self.work / "loop.smbp"
        write_project(program, self.fixture("read"), destination)
        imported = load_project(destination)
        frames = [{"dt_ms": 10}] * 3
        expected = [[True] + [False] * 15] * 3
        self.assertEqual(run_native(source, frames), expected)
        for candidate in (program, imported):
            machine = Machine(candidate)
            self.assertEqual([machine.step({}, 10) for _ in frames], expected)
            self.assertEqual(machine.words[20], 6)

    def test_malformed_response_sets_error_coil_without_partial_inbound_commit(self):
        class TruncatedPeer(MemoryModbusPeer):
            def handle_request(self, pdu):
                return super().handle_request(pdu)[:-1]

        peer = TruncatedPeer(
            holding_registers=[0] * 70, input_registers=[], coils=[], discrete_inputs=[]
        )
        peer.holding_registers[41:44] = [0x8001, 0xFFFF, 0x1234]
        transport = RecordingTransport(peer, latency_ms=0)
        machine = Machine(
            load_project(self.fixture("write_read")), communication_transport=transport
        )
        machine.words[300:302] = [0x1234, 0xABCD]
        machine.words[399:404] = [0x7777, 0xAAAA, 0xBBBB, 0xCCCC, 0x8888]
        machine.step({}, 10)
        machine.memory[10] = True
        machine.step({}, 10)
        self.assertEqual(self.flags(machine), [False, True, False, False])
        machine.step({}, 10)
        self.assertEqual(self.flags(machine), [False, False, False, True])
        self.assertEqual(
            machine.words[399:404], [0x7777, 0xAAAA, 0xBBBB, 0xCCCC, 0x8888]
        )
        self.assertEqual(peer.holding_registers[17:19], [0x1234, 0xABCD])
        self.assertEqual(
            transport.requests, [bytes.fromhex("17 0029 0003 0011 0002 04 1234abcd")]
        )


if __name__ == "__main__":
    unittest.main()
