"""Packed bit transfers and word selectors share memory and preserve neighbors."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.bits import memory_bits_used
from m200.cli import report
from m200.ladder_lowering import normalize


class BitObjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "bits.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected):
        p = self.compile(body)

        def rows(program):
            m = Machine(program)
            return [m.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]

        got = rows(p)
        self.assertEqual([r[: len(expected[0])] for r in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        reverse = self.work / "reverse.cpp"
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), got)
        self.assertEqual(rows(compile_source(reverse)), got)
        dest = self.work / "bits.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertEqual(rows(load_project(dest)), got)
        return p

    def test_word_bits_preserve_neighbors_and_dword_real_aliases(self):
        self.equivalent(
            """void scan(){plc::write_real(0,3.0f);plc::write_word_bit(1,15,true);
plc::output(0,plc::read_real(0)==-3.0f);plc::write_dword(8,65538);
plc::write_word_bit(8,0,true);plc::output(1,plc::read_dword(8)==65539);
plc::write_word_bit(8,1,false);plc::output(2,plc::read_dword(8)==65537);
plc::write_word(7999,0);plc::write_word_bit(7999,15,true);
plc::output(3,plc::read_word(7999)==-32768 && plc::read_word_bit(7999,15));}""",
            [{}] * 2,
            [[True] * 4] * 2,
        )

    def test_all_word_bits_can_be_read_and_written(self):
        body = "void scan(){plc::write_word(20,0);"
        for bit in range(16):
            body += f"plc::write_word_bit(20,{bit},true);"
        body += "plc::output(0,plc::read_word(20)==-1);"
        for bit in range(16):
            body += f"plc::write_word_bit(20,{bit},false);"
        body += "plc::output(1,plc::read_word(20)==0);}"
        self.equivalent(body, [{}], [[True, True]])

    def test_short_sequences_zero_extend_and_writes_preserve_neighbors(self):
        self.equivalent(
            """void scan(){plc::write_m(7,true);plc::write_m(16,true);
plc::write_m_bits_i16(8,8,255);plc::output(0,plc::read_m_bits_i16(8,8)==255);
plc::output(1,plc::read_m_bits_i32(8,8)==255);
plc::write_m_bits_i16(8,8,0);plc::output(2,plc::read_m(7)&&plc::read_m(16)&&!plc::read_m(8));}""",
            [{}] * 2,
            [[True] * 3] * 2,
        )

    def test_full_32_bit_representation_and_last_memory_region(self):
        self.equivalent(
            """void scan(){plc::write_m_bits_i32(992,32,-2147483647);
plc::output(0,plc::read_m_bits_i32(992,32)==-2147483647);
plc::output(1,plc::read_m(992)&&plc::read_m(1023)&&!plc::read_m(993));
plc::output(2,plc::read_m_bits_i16(992,16)==1);plc::write_m_bits_i32(0,16,65535);
plc::output(3,plc::read_m_bits_i32(0,16)==65535 && plc::read_m_bits_i16(0,16)==-1);}""",
            [{}] * 2,
            [[True] * 4] * 2,
        )

    def test_input_output_sequences_have_lsb_first_mapping(self):
        self.equivalent(
            """void scan(){plc::i16 inputs=plc::read_input_bits_i16(8,8);
plc::write_output_bits_i16(0,8,inputs);plc::output(8,true);
plc::output(9,plc::read_output_bits_i16(0,8)==inputs);
plc::output(10,plc::read_output_bits_i32(0,8)==0);}""",
            [{"inputs": {8: True, 10: True, 15: True}}, {}],
            [
                [
                    True,
                    False,
                    True,
                    False,
                    False,
                    False,
                    False,
                    True,
                    True,
                    True,
                    False,
                ],
                [False] * 8 + [True, True, True],
            ],
        )

    def test_overlap_copy_api_uses_a_snapshot(self):
        self.equivalent(
            """void scan(){plc::write_m_bits_i32(0,32,305419896);
plc::copy_m_bits(8,0,24);plc::output(0,plc::read_m_bits_i32(8,24)==3430008);
plc::output(1,plc::read_m_bits_i16(0,8)==120);plc::copy_m_bits(0,8,24);
plc::output(2,plc::read_m_bits_i32(0,24)==3430008);}""",
            [{}] * 2,
            [[True] * 3] * 2,
        )

    def test_conditional_write_and_indexed_rhs_do_not_run_inactive(self):
        self.equivalent(
            """plc::WordMemory image{16};void scan(){plc::clear_index_error();
plc::write_word(0,-32768);plc::write_m_bits_i16(0,8,7);
if(plc::input(0)){plc::write_m_bits_i16(0,8,plc::read_word_indexed(8,0));}
plc::output(0,plc::read_m_bits_i16(0,8)==7 && !plc::system(20));}""",
            [{}] * 2,
            [[True]] * 2,
        )

    def test_native_copy_between_string_and_word_indexed(self):
        p = Program(
            [
                ["LD 1", "[%MW0:=1]", "[%M8:8:=255]", "[%MW10[%MW0]:=%M8:8]"],
                ["LD [%MW11=255]", "ST %Q0.0"],
                ["LD 1", "[%MW0:=0]", "[%M16:8:=%MW11]"],
                ["LD %M16", "ST %Q0.1"],
                ["LD %M23", "ST %Q0.2"],
            ]
        )
        m = Machine(p)
        self.assertEqual(m.step()[:3], [True, True, True])
        source = self.work / "native.cpp"
        source.write_text(to_cpp(p))
        frames = [{}] * 2
        self.assertEqual([r[:3] for r in run_native(source, frames)], [[True] * 3] * 2)
        rebuilt = Machine(compile_source(source))
        self.assertEqual(rebuilt.step()[:3], [True] * 3)

    def test_region_is_reserved_even_when_only_written(self):
        p = self.equivalent(
            """void scan(){plc::write_m_bits_i32(496,32,-1);
bool x=plc::input(0);plc::output(0,x);plc::output(1,plc::read_m(527));}""",
            [{}, {"inputs": {0: True}}],
            [[False, True], [True, True]],
        )
        for code in p.symbols:
            if code.startswith("%M") and code[2:].isdigit():
                self.assertFalse(496 <= int(code[2:]) < 528)

    def test_output_sequences_preserve_neighbors_and_branch_state(self):
        self.equivalent(
            """void scan(){plc::output(0,plc::input(0));
plc::output(15,plc::input(1));if(plc::input(2)){plc::write_output_bits_i32(8,7,-1);}
plc::i32 a=plc::read_output_bits_i32(0,16);plc::write_m_bits_i32(0,16,a);
plc::output(1,plc::read_m(0));plc::output(2,plc::read_m(15));}""",
            [
                {"inputs": {0: True, 1: True, 2: True}},
                {"inputs": {0: True}},
                {"inputs": {1: True}},
            ],
            [
                [True, True, True] + [False] * 5 + [True] * 8,
                [True, True, False] + [False] * 5 + [True] * 7 + [False],
                [False, False, True] + [False] * 5 + [True] * 8,
            ],
        )

    def test_small_user_images_reject_full_region_and_word_selectors(self):
        for body in (
            "plc::WordMemory w{1};void scan(){plc::write_word_bit(1,0,true);}",
            "plc::BitMemory b{9};void scan(){plc::write_m_bits_i16(8,2,1);}",
            "plc::BitMemory b{9};void scan(){plc::copy_m_bits(8,0,2);}",
            "void scan(){plc::write_m_bits_i16(0,8,65535);}",
            "void scan(){plc::write_output_bits_i32(0,16,3.0f);}",
        ):
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)
        self.equivalent(
            """plc::WordMemory w{1};plc::BitMemory b{9};void scan(){
plc::write_word_bit(0,15,true);plc::write_m_bits_i16(8,1,1);
plc::output(0,plc::read_word(0)==-32768 && plc::read_m(8));}""",
            [{}],
            [[True]],
        )

    def test_native_normalization_and_reports_preserve_full_region(self):
        p = Program([["LD 1", "[%M496:32:=-1]", "LD %M527", "STN %Q0.0"]])
        self.assertEqual(memory_bits_used(p), set(range(496, 528)))
        self.assertEqual(report(p)["resources"]["memory_bits"], 32)
        normalized = normalize(p)
        for code in normalized.symbols:
            if code.startswith("%M") and code[2:].isdigit():
                self.assertFalse(496 <= int(code[2:]) < 528)
        self.assertEqual(Machine(p).step(), Machine(normalized).step())
        dest = self.work / "native.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertEqual(Machine(p).step(), Machine(load_project(dest)).step())

    def test_packed_extent_is_visible_to_indexed_bit_bounds(self):
        p = Program(
            [
                ["LD 1", "[%M512:32:=-1]", "[%MW0:=543]"],
                ["LD %M0[%MW0]", "ST %Q0.0"],
                ["LD %S20", "ST %Q0.1"],
            ]
        )
        self.assertEqual(Machine(p).step()[:2], [True, False])
        path = self.work / "indexed_extent.cpp"
        path.write_text(to_cpp(p))
        self.assertEqual(run_native(path, [{}])[0][:2], [True, False])
        self.assertEqual(Machine(compile_source(path)).step()[:2], [True, False])

    def test_invalid_ranges_readonly_and_unverified_native_aliases_fail(self):
        invalid = [
            "plc::read_word_bit(8000,0)",
            "plc::read_word_bit(0,16)",
            "plc::read_m_bits_i16(1,8)",
            "plc::read_m_bits_i16(0,0)",
            "plc::read_m_bits_i16(0,17)",
            "plc::read_m_bits_i32(1016,16)",
            "plc::read_input_bits_i32(16,16)",
            "plc::read_output_bits_i32(8,16)",
        ]
        for expr in invalid:
            with self.subTest(expr=expr), self.assertRaises(CompileError):
                self.compile("void scan(){auto x=" + expr + ";}")
        for line in [
            "[%I0.0:8:=1]",
            "[%M0:8:=%M8:16]",
            "[%M8:16:=%M0:16]",
            "[%MW0:=%M0:17]",
            "[%MF0:=%M0:8]",
        ]:
            with self.subTest(line=line), self.assertRaises(CompileError):
                validate(Program([["LD 1", line]]))
        for ref in ("%MW0:X16", "%MW8000:X0", "%MD0:X0", "%MW00:X0"):
            with self.subTest(ref=ref), self.assertRaises(CompileError):
                validate(Program([["LD " + ref, "ST %Q0.0"]]))


if __name__ == "__main__":
    unittest.main()
