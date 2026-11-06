"""Ignored prototype checks; no real product/628-suite source changes."""

from pathlib import Path
import tempfile
import unittest
from m200.model import Program, SubroutineDefinition, CompileError
from m200.il import Machine, validate
from m200.native import run_native
from m200.reverse import to_cpp


def candidate(number=0, return_op=None):
    master = [
        ["LD 1", "[%MW0:=10]"],
        ["LD 1", "[%MW1:=0]"],
        ["LD 0", "ST %Q0.1"],
        ["LD 0", "ST %Q0.2"],
        ["LD 0", "ST %Q0.3"],
        ["LD %I0.0", "SR" + str(number)],
        ["LD 1", "[%MW2:=%MW0]"],
        ["LD 1", "[%MW0:=30]"],
        ["LD 1", "ST %Q0.2"],
        ["LD %I0.0", "ST %Q0.0"],
    ]
    leaf = [["LD 1", "[%MW0:=20]"], ["LD 1", "[%MW1:=1]"], ["LD 1", "ST %Q0.1"]]
    if return_op:
        leaf += [
            ["LD %I0.1", return_op],
            ["LD 1", "[%MW0:=25]"],
            ["LD 1", "[%MW1:=2]"],
            ["LD 1", "ST %Q0.3"],
            ["END"],
        ]
    return Program(
        rungs=master,
        subroutines={number: SubroutineDefinition(number, "leaf", 2, leaf)},
    )


class PrototypeContexts(unittest.TestCase):
    def test_v2_context_json_roundtrip_and_v1_unchanged(self):
        program = candidate(63, "ENDC")
        data = program.as_dict()
        self.assertEqual(data["format"], "m200-cpp-il-v2")
        self.assertEqual(Program.from_dict(data).as_dict(), data)
        self.assertEqual(Program().as_dict()["format"], "m200-cpp-il-v1")
        self.assertNotIn("subroutines", Program().as_dict())

    def test_implicit_return_shared_words_outputs_and_false_call(self):
        machine = Machine(candidate())
        expected = [
            ([30, 0, 10], [False, False, True, False]),
            ([30, 1, 20], [True, True, True, False]),
            ([30, 1, 20], [True, True, True, False]),
            ([30, 0, 10], [False, False, True, False]),
        ]
        for controls, (words, outputs) in zip(
            [(0, 0), (1, 0), (1, 1), (0, 1)], expected
        ):
            actual = machine.step({"0": controls[0], "1": controls[1]}, 13)
            self.assertEqual(machine.words[:3], words)
            self.assertEqual(actual[:4], outputs)
        self.assertEqual(machine.now, 52)
        self.assertFalse(machine.first)

    def test_end_endc_current_level_returns_to_master(self):
        machine = Machine(candidate(63, "ENDC"))
        for controls, words, bits in [
            ((0, 0), [30, 0, 10], [0, 0, 1, 0]),
            ((1, 0), [30, 2, 25], [1, 1, 1, 1]),
            ((1, 1), [30, 1, 20], [1, 1, 1, 0]),
        ]:
            self.assertEqual(
                machine.step({"0": controls[0], "1": controls[1]}, 10)[:4],
                list(map(bool, bits)),
            )
            self.assertEqual(machine.words[:3], words)
        self.assertEqual(machine.now, 30)

    def test_endcn_and_repeated_calls_use_one_scan_context(self):
        machine = Machine(candidate(63, "ENDCN"))
        machine.step({"0": True, "1": False}, 17)
        self.assertEqual(machine.words[:3], [30, 1, 20])
        machine.step({"0": True, "1": True}, 17)
        self.assertEqual(machine.words[:3], [30, 2, 25])
        self.assertEqual(machine.now, 34)
        p = Program(
            rungs=[["LD 1", "SR0"], ["LD 1", "SR0"]],
            subroutines={
                0: SubroutineDefinition(0, "twice", 2, [["LD 1", "[%MW7:=%MW7+1]"]])
            },
        )
        machine = Machine(p)
        machine.step({}, 13)
        self.assertEqual(machine.words[7], 2)
        self.assertEqual(machine.now, 13)

    def test_nested_missing_unused_invalid_and_duplicate_identity_refused(self):
        bad = []
        p = candidate()
        p.subroutines = {}
        bad.append(p)
        p = candidate()
        p.subroutines[0].rungs = [["LD 0", "SR0"]]
        bad.append(p)
        p = candidate()
        p.subroutines[63] = SubroutineDefinition(
            63, "unused", 3, [["LD 1", "[%MW8000:=1]"]]
        )
        bad.append(p)
        p = candidate()
        p.subroutines[63] = SubroutineDefinition(63, "leaf", 3, [["END"]])
        bad.append(p)
        for p in bad:
            with self.assertRaises(CompileError):
                validate(p)

    def test_unsupported_stateful_and_continuation_are_explicit(self):
        p = candidate()
        p.subroutines[0].rungs = [
            ["BLK %TM0", "LD %I0.0", "IN", "OUT_BLK", "LD Q", "ST %M1", "END_BLK"]
        ]
        with self.assertRaises(CompileError):
            validate(p)
        p = candidate()
        p.rungs[5].append("ST %M90")
        with self.assertRaises(CompileError):
            validate(p)
        p = candidate()
        p.subroutines[0].rungs = [["%L0:", "LD 1", "ST %M0"]]
        with self.assertRaises(CompileError):
            validate(p)

    def test_sdk_conditional_leaf_early_return_shares_native_scan_state(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "reference.cpp"
            source.write_text("""#include <plc.hpp>
void leaf(){plc::write_word(0,20);plc::write_word(1,1);plc::output(1,true);if(plc::input(1))return;plc::write_word(0,25);plc::write_word(1,2);plc::output(3,true);}
plc::Subroutine sr{63,leaf};
void scan(){plc::write_word(0,10);plc::write_word(1,0);plc::output(1,false);plc::output(2,false);plc::output(3,false);sr.call(plc::input(0));plc::write_word(2,plc::read_word(0));plc::write_word(0,30);plc::output(0,plc::input(0));plc::output(2,true);plc::output(4,plc::read_word(0)==30);}
""")
            rows = run_native(
                source,
                [
                    {"inputs": {"0": a, "1": b}, "dt_ms": 13}
                    for a, b in [(0, 0), (1, 0), (1, 1)]
                ],
            )
            self.assertEqual(
                [r[:5] for r in rows],
                [[0, 0, 1, 0, 1], [1, 1, 1, 1, 1], [1, 1, 1, 0, 1]],
            )

    def test_central_metadata_names_reject_non_xml_even_from_json(self):
        for name in (" ", "bad\x00name", "bad\ud800name", "bad\uffffname"):
            p = candidate()
            p.subroutines[0].name = name
            with self.assertRaises(CompileError):
                validate(p)

    def test_conservative_allocator_preserves_caller_live_value_across_context(self):
        from m200.allocation import Storage

        store = Storage()
        caller = store.bit("caller")
        callee = store.bit("callee")
        p = Program(
            rungs=[
                ["LD 1", "ST " + caller],
                ["LD 1", "SR0"],
                ["LD " + caller, "ST %Q0.0"],
            ],
            subroutines={
                0: SubroutineDefinition(0, "leaf", 2, [["LD 0", "ST " + callee]])
            },
        )
        p = store.finalize(p, {})
        validate(p)
        machine = Machine(p)
        self.assertTrue(machine.step({}, 10)[0])
        self.assertNotEqual(
            p.rungs[0][1].split()[1], p.subroutines[0].rungs[0][1].split()[1]
        )

    def test_native_sdk_nested_and_duplicate_descriptor_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "invalid.cpp"
            source.write_text(
                "#include <plc.hpp>\nvoid inner(){}\nplc::Subroutine b{1,inner};\nvoid outer(){b.call(true);}\nplc::Subroutine a{0,outer};\nvoid scan(){a.call(true);}"
            )
            with self.assertRaises(CompileError):
                run_native(source, [{"dt_ms": 10}])
            source.write_text(
                "#include <plc.hpp>\nvoid leaf(){}\nplc::Subroutine a{0,leaf};\nplc::Subroutine b{0,leaf};\nvoid scan(){}"
            )
            with self.assertRaises(CompileError):
                run_native(source, [{"dt_ms": 10}])

    def test_master_indexed_access_uses_resources_declared_in_callee(self):
        from m200.frontend import compile_source

        cases = [
            (
                [["LD 1", "[%MW2:=22]"]],
                [["LD 1", "[%MW1:=%MW0[%MW0]]"], ["LD [%MW1=22]", "ST %Q0.14"]],
            ),
            ([["LD 1", "ST %M2"]], [["LD %M0[%MW0]", "ST %Q0.0"]]),
        ]
        for index, (leaf, after) in enumerate(cases):
            before = [["LD 1", "[%MW0:=2]"]]
            after = after + [["LD %S20", "ST %Q0.15"]]
            inline = Machine(Program(rungs=before + leaf + after))
            program = Program(
                rungs=before + [["LD 1", "SR0"]] + after,
                subroutines={0: SubroutineDefinition(0, "direct", 2, leaf)},
            )
            called = Machine(program)
            expected = [False] * 16
            expected[14 if index == 0 else 0] = True
            expected_words = [2, 22, 22] if index == 0 else [2]
            observed_words = len(expected_words)
            self.assertEqual(inline.step({}, 10), expected)
            self.assertEqual(inline.words[:observed_words], expected_words)
            self.assertEqual(called.step({}, 10), expected)
            self.assertEqual(called.words[:observed_words], expected_words)
            self.assertEqual(called.index_error, inline.index_error)
            self.assertFalse(called.index_error)
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / "indexed.cpp"
                source.write_text(to_cpp(program))
                rebuilt = Machine(compile_source(source))
                self.assertEqual(rebuilt.step({}, 10), expected)
                self.assertEqual(rebuilt.words[:observed_words], expected_words)
                self.assertEqual(run_native(source, [{"dt_ms": 10}]), [expected])

    def test_indexed_leaf_refused_until_internal_guard_transfers_are_supported(self):
        for body in ([["LD 1", "[%MW1:=%MW0[%MW0]]"]], [["LD %M0[%MW0]", "ST %Q0.0"]]):
            p = Program(
                rungs=[["LD 1", "SR0"]],
                subroutines={0: SubroutineDefinition(0, "indexed", 2, body)},
            )
            for operation in (validate, Machine, to_cpp):
                with self.assertRaisesRegex(CompileError, "indexed leaf"):
                    operation(p)

    def test_native_unconditional_leaf_end_requires_its_own_rung(self):
        for body in (["END"], ["LD %I0.1", "ENDC"], ["LD %I0.1", "ENDCN"]):
            p = Program(
                rungs=[["LD %I0.0", "SR0"]],
                subroutines={0: SubroutineDefinition(0, "leaf", 2, [body])},
            )
            validate(p)
        for body in (["LD %I0.1", "END"], ["LDN %M0", "END"]):
            p = Program(
                rungs=[["LD %I0.0", "SR0"]],
                subroutines={0: SubroutineDefinition(0, "leaf", 2, [body])},
            )
            with self.assertRaisesRegex(CompileError, "END must be the sole"):
                validate(p)

    def test_cli_artifacts_source_maps_and_statistics_include_every_context(self):
        import json
        from m200.cli import build_artifacts, report

        p = candidate(63, "ENDC")
        p.metadata["rung_origins"] = [
            {"file": "master.cpp", "line": 100 + i} for i in range(10)
        ]
        p.subroutines[63].origins = [
            {"file": "callee.cpp", "line": 10 + i} for i in range(8)
        ]
        p.subroutines[1] = SubroutineDefinition(
            1, "unused", 3, [["LD %M100", "ST %M101"], ["LD 1", "[%MW7999:=3]"]]
        )
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "program"
            build_artifacts(p, output)
            text = (output / "program.il").read_text()
            self.assertIn("; MASTER", text)
            self.assertIn("; FREE POU SR63", text)
            self.assertIn("; FREE POU SR1", text)
            self.assertIn("[%MW7999:=3]", text)
            data = json.loads((output / "program.m200.json").read_text())
            self.assertEqual(set(data["subroutines"]), {"1", "63"})
            source = json.loads((output / "source-map.json").read_text())
            self.assertEqual(source["format"], "m200-cpp-source-map-v2")
            self.assertEqual(
                source["master"]["rungs"][0]["origin"]["file"], "master.cpp"
            )
            self.assertEqual(
                source["subroutines"]["63"]["rungs"][0]["origin"]["file"], "callee.cpp"
            )
            self.assertEqual(source["subroutines"]["63"]["section_number"], 2)
        resources = report(p)["resources"]
        self.assertEqual(resources["memory_bits"], 2)
        self.assertEqual(resources["memory_words"], 4)
        self.assertEqual(resources["required_word_allocation"], 8000)
        self.assertEqual(resources["rungs"], 20)
        self.assertEqual(resources["il_instructions"], 39)
        self.assertEqual(resources["master_rungs"], 10)
        self.assertEqual(resources["subroutine_definitions"], 2)

    def test_reverse_rebuild_preserves_identity_and_current_level_behavior(self):
        from m200.frontend import compile_source

        original = candidate(63, "ENDC")
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "reverse.cpp"
            source.write_text(to_cpp(original))
            rebuilt = compile_source(source)
        self.assertEqual(set(rebuilt.subroutines), {63})
        self.assertEqual(rebuilt.subroutines[63].name, "leaf")
        self.assertEqual(rebuilt.subroutines[63].section_number, 2)
        machine = Machine(rebuilt)
        for controls, words, bits in [
            ((0, 0), [30, 0, 10], [0, 0, 1, 0]),
            ((1, 0), [30, 2, 25], [1, 1, 1, 1]),
            ((1, 1), [30, 1, 20], [1, 1, 1, 0]),
        ]:
            self.assertEqual(
                machine.step({"0": controls[0], "1": controls[1]}, 13)[:4],
                list(map(bool, bits)),
            )
            self.assertEqual(machine.words[:3], words)
        self.assertEqual(machine.now, 39)


if __name__ == "__main__":
    unittest.main()
