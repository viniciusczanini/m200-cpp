"""Experimental bit indexing; SMBP profile mapping remains explicitly gated."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.native import run_native
from m200.project import write_project
from m200.reverse import to_cpp


class IndexedBitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "bits.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, expected):
        program = self.compile(body)
        frames = [{}] * len(expected)
        machine = Machine(program)
        got = [machine.step() for _ in frames]
        self.assertEqual([row[: len(expected[0])] for row in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        source = self.work / "reverse.cpp"
        source.write_text(to_cpp(program))
        self.assertEqual(run_native(source, frames), got)
        rebuilt = Machine(compile_source(source))
        self.assertEqual([rebuilt.step() for _ in frames], got)
        return program

    def test_raw_profile_and_signed_offsets_preserve_flag_and_index(self):
        self.equivalent(
            """plc::WordMemory words{16};plc::BitMemory bits{8};
void scan(){plc::clear_index_error();plc::write_m(3,true);plc::write_m(4,true);
plc::write_word(0,-1);bool valid=plc::read_m_indexed(4,0);
plc::write_m_indexed(4,0,false);
plc::output(0,valid && !plc::read_m(3) && !plc::system(20));
plc::write_word(0,4);bool invalid=plc::read_m_indexed(4,0);
plc::output(1,invalid && plc::system(20) && plc::read_word(0)==4);
plc::write_m_indexed(4,0,false);
plc::output(2,!plc::read_m(4) && plc::system(20));
plc::write_word(0,0);bool fallback=plc::read_m_indexed(4,0);
plc::output(3,!fallback && plc::system(20));plc::clear_index_error();
plc::output(4,!plc::system(20));}""",
            [[True] * 5] * 2,
        )

    def test_no_inactive_read_or_write_sets_flag(self):
        self.equivalent(
            """plc::WordMemory words{8};plc::BitMemory bits{8};
void scan(){plc::clear_index_error();plc::write_word(0,-32768);
if(plc::input(0)){plc::write_m_indexed(4,0,true);}
bool a=false && plc::read_m_indexed(4,0);
bool b=true || plc::read_m_indexed(4,0);
plc::output(0,!a && b && !plc::system(20) && !plc::read_m(4));}""",
            [[True]] * 2,
        )

    def test_native_bit_extent_false_stores_and_sticky_error(self):
        p = Program(
            [
                ["LD 1", "ST %M4", "ST %M7"],
                ["LD 0", "ST %M4[%MW0]"],
                ["LD %M4", "ST %Q0.0"],
                ["LD %M7", "ST %Q0.1"],
                ["LD %S20", "ST %Q0.2"],
            ]
        )
        for offset, expected in [
            (3, [True, False, False]),
            (4, [False, True, True]),
            (-5, [False, True, True]),
        ]:
            with self.subTest(offset=offset):
                machine = Machine(p)
                machine.words[0] = offset & 65535
                self.assertEqual(machine.step()[:3], expected)
                self.assertEqual(machine.words[0], offset & 65535)

    def test_unknown_bit_profile_cannot_replace_destination(self):
        p = self.compile("""plc::WordMemory words{8};plc::BitMemory bits{8};
void scan(){plc::output(0,plc::read_m_indexed(4,0));}""")
        destination = self.work / "protected.smbp"
        destination.write_bytes(b"preserve existing destination")
        with self.assertRaisesRegex(CompileError, "indexed.bit.*unverified"):
            write_project(
                p, Path(__file__).parent / "fixtures/synthetic.smbp", destination
            )
        self.assertEqual(destination.read_bytes(), b"preserve existing destination")

    def test_invalid_profiles_and_addresses_fail_explicitly(self):
        for body in [
            "plc::BitMemory b{0};void scan(){}",
            "plc::BitMemory b{1025};void scan(){}",
            "plc::BitMemory a{8};plc::BitMemory b{8};void scan(){}",
            "void scan(){plc::BitMemory b{8};}",
            "void scan(){plc::output(0,plc::read_m_indexed(0,0));}",
            "plc::BitMemory b{8};void scan(){plc::output(0,plc::read_m_indexed(0,0));}",
            "plc::WordMemory w{8};plc::BitMemory b{8};void scan(){plc::output(0,plc::read_m_indexed(8,0));}",
            "plc::WordMemory w{8};plc::BitMemory b{8};void scan(){plc::write_m_indexed(0,8,true);}",
            "plc::BitMemory b{8};void scan(){plc::write_m(8,true);}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)
        for ref in ("%M1024[%MW0]", "%M1[%MW8000]", "%M1[%MD0]", "%M1[%MW00]"):
            with self.subTest(ref=ref), self.assertRaises(CompileError):
                validate(Program([["LD " + ref, "ST %Q0.0"]]))


if __name__ == "__main__":
    unittest.main()
