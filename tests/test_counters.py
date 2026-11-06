"""Native counter pipeline; ambiguous hardware behavior remains a local policy."""

import json
import tempfile
import unittest
from pathlib import Path

from m200.model import CompileError, Program


class CounterTests(unittest.TestCase):
    def state(self, preset):
        from m200.counters import Counter, CounterState

        return CounterState(Counter(preset))

    def test_reset_and_set_override_equality_for_zero_preset(self):
        c = self.state(0)
        self.assertEqual([c.read(f) for f in "VEDF"], [0, False, False, False])
        c.action("S", True)
        self.assertEqual(c.read("V"), 0)
        self.assertTrue(c.read("D"))
        c.action("R", True)
        self.assertEqual([c.read(f) for f in "VEDF"], [0, False, False, False])
        c.action("CU", True)
        self.assertEqual(c.read("V"), 0)
        c.action("R", False)
        self.assertEqual(c.read("V"), 0)  # S remains active
        self.assertTrue(c.read("D"))

    def test_up_and_down_are_edges_with_circular_domain_and_local_flags(self):
        c = self.state(9999)
        c.action("S", True)
        c.action("S", False)
        c.action("CU", True)
        self.assertEqual([c.read(f) for f in "VDF"], [0, False, True])
        c.action("CU", True)
        self.assertEqual(c.read("V"), 0)
        c.action("CD", True)
        self.assertEqual([c.read(f) for f in "VEDF"], [9999, True, True, True])
        c.action("CD", False)
        c.action("CD", True)
        self.assertEqual([c.read(f) for f in "VEDF"], [9998, False, False, True])
        c.action("CU", False)
        c.action("CU", True)
        self.assertEqual([c.read(f) for f in "VDF"], [9999, True, False])

    def test_masked_edge_consumption_and_no_stale_other_pin_event(self):
        c = self.state(4)
        c.action("R", True)
        c.action("CU", True)
        c.action("R", False)
        c.action("CU", True)
        self.assertEqual(c.read("V"), 0)
        c.action("CU", False)
        c.action("CU", True)
        c.action("CD", False)
        self.assertEqual(c.read("V"), 1)
        c.action("CD", True)
        self.assertEqual(c.read("V"), 0)
        c.action("CU", True)
        self.assertEqual(c.read("V"), 0)

    def test_preset_write_does_not_modify_value_and_invalid_write_is_atomic(self):
        c = self.state(2)
        c.action("S", True)
        c.action("S", False)
        c.set_preset(3)
        self.assertEqual([c.read(f) for f in "PVD"], [3, 2, True])
        c.action("CU", True)
        self.assertEqual([c.read(f) for f in "PVD"], [3, 3, True])
        c.action("CU", True)
        self.assertEqual(c.read("V"), 3)
        c.set_preset(4)
        self.assertTrue(c.read("D"))
        c.action("CU", True)
        self.assertFalse(c.read("D"))
        for invalid in [-1, 10000, True, 1.5]:
            with self.assertRaises(CompileError):
                c.set_preset(invalid)
            self.assertEqual(c.read("P"), 4)

    def test_json_preserves_configuration_and_rejects_invalid_counter_map(self):
        from m200.counters import Counter

        p = Program(counters={0: Counter(5), 254: Counter(0)})
        data = json.loads(json.dumps(p.as_dict()))
        self.assertEqual(Program.from_dict(data).counters, p.counters)
        for invalid in [
            [],
            {"00": {"preset": 5}},
            {"0": {"preset": True}},
            {"255": {"preset": 5}},
            {"1": {"preset": 5, "mode": "single"}},
        ]:
            data["counters"] = invalid
            with self.assertRaises(CompileError):
                Program.from_dict(data)

    def test_il_specific_block_short_outputs_and_numeric_properties(self):
        from m200.counters import Counter
        from m200.il import Machine

        p = Program(
            [
                [
                    "BLK %C8",
                    "LD %I0.1",
                    "R",
                    "LD %I0.0",
                    "CU",
                    "OUT_BLK",
                    "LD D",
                    "ST %Q0.0",
                    "END_BLK",
                ],
                ["LD [%C8.V=2]", "ST %Q0.1"],
                ["LD 1", "[%MW0:=%C8.V]"],
            ],
            counters={8: Counter(2)},
        )
        m = Machine(p)
        got = [
            m.step({0: u, 1: r})[:2]
            for u, r in [(0, 0), (1, 0), (1, 0), (0, 0), (1, 0), (1, 1), (1, 0)]
        ]
        self.assertEqual(got, [[0, 0], [0, 0], [0, 0], [0, 0], [1, 1], [0, 0], [0, 0]])
        self.assertEqual(m.words[0], 0)

    def test_il_counter_identity_properties_and_writable_domains_are_closed(self):
        from m200.counters import Counter
        from m200.il import validate

        for rungs, counters in [
            ([["LD 1", "CU %C0"]], {}),
            ([["LD %C1.D", "ST %Q0.0"]], {0: Counter(1)}),
            ([["LD 1", "[%C0.V:=1]"]], {0: Counter(1)}),
            ([["LD 1", "ST %C0.D"]], {0: Counter(1)}),
            ([["LD 1", "CU %C255"]], {255: Counter(1)}),
            ([["LD 1", "CU %C00"]], {0: Counter(1)}),
            (
                [["BLK %C0", "LD 1", "CU", "OUT_BLK", "LD Q", "ST %Q0.0", "END_BLK"]],
                {0: Counter(1)},
            ),
            ([["LD 1", "[%C0.P:=10000]"]], {0: Counter(1)}),
        ]:
            with self.subTest(rungs=rungs), self.assertRaises(CompileError):
                validate(Program(rungs, counters=counters))

    def test_cpp_actions_guards_multiple_calls_and_reverse_keep_order(self):
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.native import run_native
        from m200.reverse import to_cpp

        source = """#include <plc.hpp>
plc::Counter c{254,2};
void scan(){
 c.reset(plc::input(1)); c.set(false);
 if(plc::input(2)){c.count_up(plc::input(0));}
 plc::output(0,c.done()); plc::output(1,c.value()==1);
 c.count_down(plc::input(3));
 plc::output(2,c.value()==0); plc::output(3,c.empty());
}"""
        frames = [
            {"inputs": {0: u, 1: r, 2: e, 3: d}}
            for u, r, e, d in [
                (0, 0, 1, 0),
                (1, 0, 1, 0),
                (0, 0, 0, 0),
                (1, 0, 1, 0),
                (0, 0, 1, 0),
                (1, 0, 1, 0),
                (1, 0, 1, 1),
                (0, 1, 1, 0),
            ]
        ]
        expected = [
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 1, 0, 0],
            [0, 1, 0, 0],
            [0, 1, 0, 0],
            [1, 0, 0, 0],
            [1, 0, 0, 0],
            [0, 0, 1, 0],
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.cpp"
            path.write_text(source)
            p = compile_source(path)
            m = Machine(p)
            got = [m.step(f["inputs"]) for f in frames]
            self.assertEqual([r[:4] for r in got], expected)
            self.assertEqual(run_native(path, frames), got)
            reverse = Path(folder) / "reverse.cpp"
            reverse.write_text(to_cpp(p))
            self.assertEqual(run_native(reverse, frames), got)
            rebuilt = compile_source(reverse)
            vm = Machine(rebuilt)
            self.assertEqual([vm.step(f["inputs"]) for f in frames], got)
            self.assertEqual(
                Program.from_dict(json.loads(json.dumps(p.as_dict()))).counters,
                p.counters,
            )

    def test_normalization_and_xml_keep_state_and_each_counter_action(self):
        from m200.counters import Counter
        from m200.il import Machine
        from m200.ladder_lowering import normalize
        from m200.project import write_project, load_project
        from m200.reverse import to_cpp
        from m200.frontend import compile_source

        p = Program(
            [
                [
                    "BLK %C0",
                    "LD %I0.0",
                    "MPS",
                    "AND %I0.1",
                    "R",
                    "MPP",
                    "ANDN %I0.1",
                    "CU",
                    "END_BLK",
                ],
                ["LD %I0.2", "S %C0"],
                ["LD %I0.3", "CD %C0"],
                ["LD 1", "[%Q0.0:16:=%C0.V]"],
                ["LD %C0.D", "ST %Q0.14"],
                ["LD %C0.E", "ST %Q0.15"],
            ],
            counters={0: Counter(4), 254: Counter(0)},
        )
        frames = [
            {0: u, 1: r, 2: s, 3: d}
            for u, r, s, d in [
                (0, 0, 0, 0),
                (1, 0, 0, 0),
                (0, 0, 0, 0),
                (1, 0, 0, 0),
                (1, 1, 0, 0),
                (0, 0, 1, 0),
                (0, 0, 0, 0),
                (1, 0, 0, 1),
            ]
        ]

        def rows(q):
            vm = Machine(q)
            return [vm.step(f) for f in frames]

        expected = rows(p)
        normalized = normalize(p)
        self.assertEqual(normalized.counters, p.counters)
        self.assertEqual(rows(normalized), expected)
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "counter.smbp"
            template = Path(__file__).parent / "fixtures/synthetic.smbp"
            write_project(p, template, dest)
            loaded = load_project(dest)
            self.assertEqual(loaded.counters, p.counters)
            self.assertEqual(rows(loaded), expected)
            cpp = Path(folder) / "from_export.cpp"
            cpp.write_text(to_cpp(loaded))
            rebuilt = compile_source(cpp)
            self.assertEqual(rows(rebuilt), expected)
            write_project(rebuilt, template, dest)
            self.assertEqual(rows(load_project(dest)), expected)

    def test_authentic_counter_configuration_and_graph_are_hash_pinned(self):
        import hashlib
        import xml.etree.ElementTree as ET
        from m200.counter_xml import read_configs, check_graph

        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "docs/capabilities/COUNTER-SOURCES.json").read_text()
        )
        fixtures = json.loads(
            (root / "tests/fixtures/native_counter_graphs.json").read_text()
        )
        by_name = {s["file"]: s for s in manifest["sources"]}
        for fixture in fixtures:
            source = by_name[fixture["source"]]
            self.assertEqual(fixture["sha256"], source["sha256"])
            path = root / "research/downloads/counter-sources" / source["file"]
            if path.exists():
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"]
                )
            sw = ET.fromstring(fixture["counter_configuration_xml"])
            configs = read_configs(sw)
            self.assertTrue(configs)
            if source["file"] == "car_garage.smbp":
                node = ET.fromstring(fixture["rung0_xml"])
                lines = [
                    " ".join((x.text or "").split())
                    for x in node.findall(
                        "InstructionLines/InstructionLineEntity/InstructionLine"
                    )
                ]
                check_graph(node, lines)

    def test_counter_configuration_unknown_fields_and_graph_mismatch_fail(self):
        import xml.etree.ElementTree as ET
        from m200.counter_xml import read_configs, check_graph, graphics

        for field in [
            "<Type>SINGLE</Type>",
            "<Preset>10000</Preset>",
            "<Index>255</Index>",
            "<Preset><x /></Preset>",
        ]:
            xml = (
                "<SoftwareConfiguration><Counters><Counter><Address>%C0</Address><Index>0</Index><Preset>1</Preset>"
                + field
                + "</Counter></Counters></SoftwareConfiguration>"
            )
            with self.assertRaises(CompileError):
                read_configs(ET.fromstring(xml))
        lines = ["BLK %C0", "LD %I0.0", "CU", "END_BLK"]
        node = ET.Element("RungEntity")
        graph = ET.SubElement(node, "LadderElements")
        for typ, arg, row, col, conn in graphics(lines):
            e = ET.SubElement(graph, "LadderEntity")
            for k, v in [
                ("ElementType", typ),
                ("Descriptor", arg),
                ("Row", row),
                ("Column", col),
                ("ChosenConnection", conn),
            ]:
                ET.SubElement(e, k).text = str(v)
        check_graph(node, lines)
        graph[0].find("Row").text = "0"
        with self.assertRaises(CompileError):
            check_graph(node, lines)

    def test_native_counter_whitespace_is_canonicalized_without_changing_source(self):
        import copy
        from m200.counters import Counter
        from m200.il import Machine
        from m200.ladder_lowering import normalize

        p = Program(
            [["BLK\t%C0", "LD\t1", "CU  ", "END_BLK"]], counters={0: Counter(1)}
        )
        original = copy.deepcopy(p.as_dict())
        vm = Machine(p)
        self.assertTrue(vm.step({})[0] is False)
        result = normalize(p)
        self.assertEqual(p.as_dict(), original)
        self.assertEqual(Machine(result).step({}), [False] * 16)

    def test_cpp_update_preset_and_multiple_loop_calls_preserve_observations(self):
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.native import run_native
        from m200.reverse import to_cpp

        source = """#include <plc.hpp>
plc::Counter c{0,0};
void scan(){
 bool before=c.done();bool after=c.update(plc::input(0),plc::input(1),false,false);
 plc::output(0,before);plc::output(1,after);c.set_preset(2);
 plc::i16 i=0;while(i<3){c.count_up(false);c.count_up(true);i=plc::add_i16(i,1);}
 plc::output(2,c.value()==3);plc::output(3,c.value()==2);plc::output(4,c.done());
}"""
        frames = [{"inputs": {0: r, 1: s}} for r, s in [(0, 0), (1, 0), (0, 1), (0, 0)]]
        expected = [[0, 0, 1, 0, 0], [0, 0, 0, 0, 0], [0, 1, 0, 1, 1], [1, 1, 0, 0, 0]]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "update.cpp"
            path.write_text(source)
            p = compile_source(path)
            m = Machine(p)
            got = [m.step(f["inputs"]) for f in frames]
            self.assertEqual([r[:5] for r in got], expected)
            self.assertEqual(run_native(path, frames), got)
            path.write_text(to_cpp(p))
            self.assertEqual(run_native(path, frames), got)
            vm = Machine(compile_source(path))
            self.assertEqual([vm.step(f["inputs"]) for f in frames], got)

    def test_cpp_counter_ids_presets_helpers_and_types_fail_closed(self):
        from m200.frontend import compile_source

        bodies = [
            "plc::Counter c{255,1};void scan(){c.count_up(true);}",
            "plc::Counter c{0,10000};void scan(){}",
            "plc::Counter c{0,1};plc::Counter d{0,2};void scan(){}",
            "void scan(){plc::Counter c{0,1};c.count_up(true);}",
            "plc::Counter c{0,1};bool bad(bool x){return c.update(false,false,x,false);}void scan(){}",
            "plc::Counter c{0,1};void scan(){c.set_preset(-1);}",
            "plc::Counter c{0,1};void scan(){c.set_preset(1.0f);}",
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.cpp"
            for body in bodies:
                with self.subTest(body=body):
                    path.write_text("#include <plc.hpp>\n" + body)
                    with self.assertRaises(CompileError):
                        compile_source(path)

    def test_counter_resource_report_includes_actual_native_configurations(self):
        from m200.counters import Counter
        from m200.cli import build_artifacts

        p = Program([["LD 1", "CU %C254"]], counters={254: Counter(1)})
        with tempfile.TemporaryDirectory() as folder:
            report = build_artifacts(
                p,
                Path(folder) / "output",
                Path(__file__).parent / "fixtures/synthetic.smbp",
            )
            self.assertEqual(report["resources"].get("counters"), 1)
            self.assertEqual(report["generated_project_resources"].get("counters"), 1)

    def test_writer_rejects_unknown_counter_template_configuration_atomically(self):
        import xml.etree.ElementTree as ET
        from m200.counters import Counter
        from m200.project import write_project

        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder) / "template.smbp"
            dest = Path(folder) / "result.smbp"
            tree = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp")
            counter = ET.SubElement(
                tree.getroot().find("SoftwareConfiguration/Counters"), "Counter"
            )
            for k, v in [
                ("Address", "%C0"),
                ("Index", "0"),
                ("Preset", "1"),
                ("Type", "SINGLE"),
            ]:
                ET.SubElement(counter, k).text = v
            tree.write(template)
            dest.write_text("keep")
            with self.assertRaises(CompileError):
                write_project(
                    Program([["LD 1", "CU %C0"]], counters={0: Counter(1)}),
                    template,
                    dest,
                )
            self.assertEqual(dest.read_text(), "keep")

    def test_unknown_counter_container_text_is_rejected_and_destination_preserved(self):
        import xml.etree.ElementTree as ET
        from m200.project import load_project, write_project
        from m200.model import Program

        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder) / "text.smbp"
            dest = Path(folder) / "result.smbp"
            dest.write_text("keep")
            tree = ET.parse(Path(__file__).parent / "fixtures/synthetic.smbp")
            tree.getroot().find(
                "SoftwareConfiguration/Counters"
            ).text = "UNRECOGNIZED_ACTIVE_COUNTER_CONFIGURATION"
            tree.write(template)
            with self.assertRaises(CompileError):
                load_project(template)
            with self.assertRaises(CompileError):
                write_project(Program([["LD 1", "ST %Q0.0"]]), template, dest)
            self.assertEqual(dest.read_text(), "keep")
