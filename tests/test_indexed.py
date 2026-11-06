"""Indexed memory semantics and lowering, with independent boundary oracles."""

import copy
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program, Timer
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class IndexedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "indexed.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected):
        p = self.compile(body)
        validate(p)
        m = Machine(p)
        got = [m.step(f.get("inputs", {})) for f in frames]
        self.assertEqual([v[: len(expected[0])] for v in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), got)
        rebuilt = Machine(compile_source(reverse))
        self.assertEqual([rebuilt.step(f.get("inputs", {})) for f in frames], got)
        destination = self.work / "indexed.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", destination)
        restored = Machine(load_project(destination))
        self.assertEqual([restored.step(f.get("inputs", {})) for f in frames], got)
        return p

    def test_native_word_offsets_fallback_to_base_and_do_not_change_index(self):
        p = Program(
            [
                ["LD 1", "[%MW8:=99]", "[%MW10:=77]", "[%MW15:=0]"],
                ["LD 1", "[%MW1:=%MW8[%MW0]]"],
                ["LD %S20", "ST %Q0.0"],
            ]
        )
        for offset, value, error in [
            (2, 77, False),
            (-1, 0, False),
            (-9, 99, True),
            (8, 99, True),
            (-32768, 99, True),
        ]:
            with self.subTest(offset=offset):
                m = Machine(p)
                m.words[0] = offset & 65535
                self.assertEqual(m.step()[0], error)
                self.assertEqual(m.words[1], value)
                self.assertEqual(m.words[0], offset & 65535)

    def test_native_index_flag_is_sticky_and_only_reset_is_writable(self):
        p = Program(
            [
                ["LD 1", "[%MW15:=0]", "[%MW1:=%MW8[%MW0]]"],
                ["LD %S20", "ST %Q0.0"],
                ["LD %I0.0", "R %S20"],
                ["LD %S20", "ST %Q0.1"],
            ]
        )
        m = Machine(p)
        m.words[0] = 65527
        self.assertEqual(m.step()[:2], [True, True])
        m.words[0] = 0
        self.assertEqual(m.step()[:2], [True, True])
        self.assertEqual(m.step({0: True})[:2], [True, False])
        self.assertEqual(m.step()[:2], [False, False])
        for instruction in ("S %S20", "ST %S20"):
            with self.subTest(instruction=instruction), self.assertRaises(CompileError):
                validate(Program([["LD 1", instruction]]))

    def test_timer_output_cannot_write_index_error_flag(self):
        for op in ("ST", "STN", "S"):
            p = Program(
                [["BLK %TM0", "LD 1", "IN", "OUT_BLK", "LD Q", op + " %S20", "END_BLK"]],
                {0: Timer("TON", 0, 100)},
            )
            before = copy.deepcopy(p.as_dict())
            with self.subTest(op=op), self.assertRaisesRegex(
                CompileError, "system bit has no permission for " + op + ": %S20"
            ):
                validate(p)
            self.assertEqual(p.as_dict(), before)
            destination = self.work / "protected_timer_output.smbp"
            destination.write_bytes(b"protected destination")
            with self.assertRaises(CompileError):
                write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", destination)
            self.assertEqual(destination.read_bytes(), b"protected destination")
        for action in ("ST %M0", "ST %Q0.0", "R %S20"):
            with self.subTest(allowed_action=action):
                p = Program(
                    [["BLK %TM0", "LD 1", "IN", "OUT_BLK", "LD Q", action, "END_BLK"]],
                    {0: Timer("TON", 0, 100)},
                )
                validate(p)
                machine = Machine(p)
                machine.index_error = True
                machine.step(dt_ms=0)
                if action == "ST %M0":
                    self.assertTrue(machine.memory[0])
                elif action == "ST %Q0.0":
                    self.assertTrue(machine.outputs[0])
                else:
                    self.assertFalse(machine.index_error)

    def test_cpp_profile_limit_is_preserved_when_compiler_memory_is_higher(self):
        self.equivalent(
            """plc::WordMemory image{32};void scan(){
plc::clear_index_error();plc::write_word(8,99);plc::write_word(10,77);
plc::write_word(3,2);plc::i16 a=plc::read_word_indexed(8,3);
plc::write_word(3,25);plc::i16 b=plc::read_word_indexed(8,3);
plc::output(0,a==77);plc::output(1,b==99 && plc::system(20));
plc::output(2,plc::read_word(3)==25);}""",
            [{}] * 2,
            [[True, True, True]] * 2,
        )

    def test_indexed_dword_real_and_aliases_use_word_offsets(self):
        self.equivalent(
            """plc::WordMemory image{32};void scan(){
plc::write_word(0,1);plc::write_dword_indexed(10,0,65538);
plc::output(0,plc::read_word(11)==2 && plc::read_word(12)==1);
plc::write_real_indexed(15,0,1.5f);
plc::f32 before=plc::read_real_indexed(15,0);
plc::write_word(0,-1);plc::i32 wide=plc::read_dword_indexed(12,0);
plc::output(1,before==1.5f && wide==65538);
plc::output(2,!plc::system(20));}""",
            [{}] * 2,
            [[True, True, True]] * 2,
        )

    def test_indexed_write_aliases_its_index_word_using_old_offset(self):
        self.equivalent(
            """plc::WordMemory image{16};void scan(){
plc::write_word(1,1);plc::write_word_indexed(0,1,7);
plc::output(0,plc::read_word(1)==7 && plc::read_word(7)==0);}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_inactive_branches_and_short_circuit_do_not_raise_index_error(self):
        self.equivalent(
            """plc::WordMemory image{16};void scan(){
plc::clear_index_error();plc::write_word(0,-32768);
if(plc::input(0)){plc::i16 x=plc::read_word_indexed(8,0);}
bool a=false && plc::read_word_indexed(8,0)>0;
bool b=true || plc::read_word_indexed(8,0)>0;
plc::output(0,!a && b && !plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_logical_left_value_is_captured_before_index_sets_flag(self):
        self.equivalent(
            """plc::WordMemory image{16};void scan(){
plc::clear_index_error();plc::write_word(0,-32768);plc::write_word(8,3);
bool a=plc::system(20) || plc::read_word_indexed(8,0)>100;
plc::output(0,!a && plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_boolean_comparison_captures_left_flag_before_indexed_read(self):
        self.equivalent(
            """plc::WordMemory image{16};void scan(){
plc::clear_index_error();plc::write_word(0,-32768);plc::write_word(8,3);
bool a=plc::system(20)==(plc::read_word_indexed(8,0)>100);
plc::output(0,a && plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_malformed_indexed_addresses_are_rejected(self):
        for source in (
            "%MW8[%MW8000]",
            "%MD7999[%MW0]",
            "%MF8[%MD0]",
            "%MW8[%MW0[%MW1]]",
            "%MW8[%MW00]",
        ):
            with self.subTest(source=source), self.assertRaises(CompileError):
                validate(Program([["LD 1", "[%MW1:=" + source + "]"]]))

    def test_full_word_bank_works_for_direct_indexed_transfers(self):
        self.equivalent(
            """plc::WordMemory image{8000};void scan(){
plc::clear_index_error();plc::write_word(0,0);
plc::write_dword_indexed(7998,0,65538);plc::write_word(0,1);
plc::write_dword(10,plc::read_dword_indexed(7998,0));
plc::output(0,plc::read_dword(10)==65538 && plc::system(20));
plc::output(1,plc::read_word(0)==1);}""",
            [{}] * 2,
            [[True, True]] * 2,
        )

    def test_unverified_excess_manual_allocation_is_refused_on_import(self):
        self.equivalent(
            "plc::WordMemory image{32};void scan(){plc::write_word(0,0);plc::write_word(1,plc::read_word_indexed(8,0));plc::output(0,true);}",
            [{}],
            [[True]],
        )
        path = self.work / "indexed.smbp"
        original = path.read_bytes()
        for mode in ("Manual", None, ""):
            tree = ET.ElementTree(ET.fromstring(original))
            node = tree.find("SoftwareConfiguration/MemoryWordsMemoryAllocation")
            count = node.find("ForcedCount")
            count.text = str(int(count.text) + 1)
            allocation = node.find("Allocation")
            if mode is None:
                node.remove(allocation)
            else:
                allocation.text = mode
            tree.write(path, encoding="utf-8", xml_declaration=True)
            with (
                self.subTest(mode=mode),
                self.assertRaisesRegex(CompileError, "indexed"),
            ):
                load_project(path)

    def test_invalid_image_and_api_addresses_are_rejected(self):
        for body in (
            "plc::WordMemory m{0};void scan(){}",
            "plc::WordMemory m{8001};void scan(){}",
            "plc::WordMemory a{32};plc::WordMemory b{32};void scan(){}",
            "void scan(){plc::WordMemory m{32};}",
            "void scan(){plc::write_word(0,plc::read_word_indexed(8,1));}",
            "plc::WordMemory m{32};void scan(){plc::write_word(0,plc::read_word_indexed(32,1));}",
            "plc::WordMemory m{32};void scan(){plc::write_word(0,plc::read_word_indexed(8,32));}",
            "plc::WordMemory m{32};void scan(){plc::write_word(32,0);}",
        ):
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)

    def test_raw_indexed_contact_short_circuit_is_not_assumed(self):
        for operator in ("AND", "ANDN", "OR", "ORN"):
            with (
                self.subTest(operator=operator),
                self.assertRaisesRegex(
                    CompileError, "indexed.*short|indexed.*unverified"
                ),
            ):
                validate(
                    Program([["LD %I0.0", operator + " [%MW1>%MW8[%MW0]]", "ST %Q0.0"]])
                )


if __name__ == "__main__":
    unittest.main()
