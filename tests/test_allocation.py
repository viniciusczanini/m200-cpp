"""Storage pressure tests assert observable programs, never allocator internals."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError
from m200.native import run_native
from m200.project import load_project, write_project
from m200.reverse import to_cpp
from m200.cli import report
from m200.allocation import Storage
from m200.model import Program


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "allocation.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def equivalent(self, body, frames, expected, reverse=True):
        p = self.compile(body)
        validate(p)
        m = Machine(p)
        got = [m.step(f.get("inputs", {})) for f in frames]
        self.assertEqual([v[: len(expected[0])] for v in got], expected)
        self.assertEqual(run_native(self.source, frames), got)
        destination = self.work / "allocation.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", destination)
        restored = Machine(load_project(destination))
        self.assertEqual([restored.step(f.get("inputs", {})) for f in frames], got)
        if reverse:
            source = self.work / "reverse.cpp"
            source.write_text(to_cpp(p))
            self.assertEqual(run_native(source, frames), got)
            rebuilt = Machine(compile_source(source))
            self.assertEqual([rebuilt.step(f.get("inputs", {})) for f in frames], got)
        return p

    def test_globals_can_use_more_than_half_the_bit_bank(self):
        p = self.equivalent(
            """bool a[600]={true};void scan(){a[599]=!a[599];
plc::output(0,a[0] && a[599]);plc::output(1,a[598]);}""",
            [{}] * 3,
            [[True, False], [False, False], [True, False]],
        )
        resources = report(p)["resources"]
        self.assertGreaterEqual(
            resources["compiler_allocatable_bits"], resources["memory_bits"]
        )

    def test_globals_can_use_more_than_half_the_shared_word_bank(self):
        p = self.equivalent(
            """plc::i32 a[2100]={1};void scan(){a[2099]=plc::add_i32(a[2099],1);
plc::output(0,a[0]==1 && a[2098]==0);plc::output(1,a[2099]==2);}""",
            [{}] * 3,
            [[True, False], [True, True], [True, False]],
            reverse=False,
        )
        resources = report(p)["resources"]
        self.assertGreaterEqual(
            resources["compiler_allocatable_words"], resources["memory_words"]
        )

    def test_dead_local_values_do_not_consume_one_bit_forever(self):
        body = "void scan(){" + "".join(
            f"bool b{i}=plc::input(0);" for i in range(1100)
        )
        self.equivalent(
            body + "plc::output(0,b1099);}",
            [{}, {"inputs": {0: True}}],
            [[False], [True]],
            reverse=False,
        )

    def test_many_sequential_temporaries_fit_and_reverse(self):
        body = "void scan(){" + "plc::write_m(0,!plc::read_m(0));" * 300
        self.equivalent(
            body + "plc::output(0,plc::read_m(0));}", [{}] * 2, [[False], [False]]
        )

    def test_loop_back_edges_and_conditional_state_survive_reuse(self):
        self.equivalent(
            """plc::i16 held=7;bool state=true;
void scan(){plc::i16 n=0;plc::i16 sum=0;
while(n<5){bool old=state;state=!state;
if(old){sum=plc::add_i16(sum,n);}n=plc::add_i16(n,1);}
if(plc::input(0)){held=sum;}
plc::output(0,sum==6);plc::output(1,held==6);plc::output(2,state);}""",
            [{"inputs": {0: True}}, {}, {}, {"inputs": {0: True}}],
            [
                [True, True, False],
                [False, True, True],
                [True, True, False],
                [False, False, True],
            ],
        )

    def test_explicit_aliases_and_reserved_initializers_survive_pressure(self):
        body = """void scan(){plc::write_dword(3999,65538);
plc::i16 a[2]={plc::read_word(4000)};
"""
        # Separate names keep this a real large scope without shadowing errors.
        body += "".join(f"bool d{i}=plc::input(0);" for i in range(550))
        body += "plc::output(0,a[0]==1 && a[1]==0 && plc::read_word(3999)==2); }"
        p = self.equivalent(body, [{}] * 2, [[True], [True]], reverse=False)
        for code in p.symbols:
            if code.startswith(("%MW", "%MD", "%MF")):
                width = 1 if code.startswith("%MW") else 2
                cells = set(range(int(code[3:]), int(code[3:]) + width))
                self.assertFalse(cells & {3999, 4000})

    def test_too_many_persistent_globals_are_still_rejected(self):
        source = "".join(f"bool g{i}=false;" for i in range(1100)) + "void scan(){}"
        with self.assertRaisesRegex(CompileError, "memory|allocation"):
            self.compile(source)

    def test_entire_communication_buffer_is_reserved_without_direct_reads(self):
        p = self.equivalent(
            """plc::ReadVar r{plc::Link::Ethernet,1,10,plc::Object::HoldingWords,0,125,4000};
void scan(){plc::i32 a=12;plc::i32 b=plc::add_i32(a,3);
plc::output(0,b==15);}""",
            [{}] * 2,
            [[True], [True]],
        )
        for code in p.symbols:
            if code.startswith(("%MW", "%MD", "%MF")):
                width = 1 if code.startswith("%MW") else 2
                self.assertFalse(
                    set(range(int(code[3:]), int(code[3:]) + width))
                    & set(range(4000, 4125))
                )

    def test_mixed_width_temporaries_preserve_values_while_aliases_change(self):
        self.equivalent(
            """void scan(){plc::write_real(0,1.5f);plc::write_dword(8,65538);
plc::f32 before=plc::read_real(0);plc::i32 wide=plc::read_dword(8);
plc::i16 low=plc::low_word(wide);plc::f32 twice=plc::add_f32(before,before);
plc::write_word(1,16384);
plc::output(0,before==1.5f && twice==3.0f);
plc::output(1,plc::read_real(0)==2.0f && low==2 && wide==65538);}""",
            [{}] * 3,
            [[True, True]] * 3,
        )

    def test_private_write_cannot_overwrite_a_later_read_in_the_same_rung(self):
        storage = Storage()
        a, b = storage.bit("a"), storage.bit("b")
        p = Program([["LD 0", "ST " + b], ["LD 1", "ST " + a, "AND " + b, "ST %Q0.0"]])
        allocated = storage.finalize(p, {})
        self.assertFalse(Machine(allocated).step()[0])

    def test_symbols_disclose_reuse_across_overlapping_word_types(self):
        p = self.compile("""void scan(){plc::i16 short_lived=3;
plc::output(0,short_lived==3);plc::i32 wide_lived=65538;
plc::output(1,wide_lived==65538);plc::f32 real_lived=1.5f;
plc::output(2,real_lived==1.5f);}""")
        entries = []
        for code, name in p.symbols.items():
            if code.startswith(("%MW", "%MD", "%MF")):
                width = 1 if code.startswith("%MW") else 2
                entries.append((set(range(int(code[3:]), int(code[3:]) + width)), name))
        overlaps = 0
        for i, (cells, name) in enumerate(entries):
            if any(cells & other for j, (other, _) in enumerate(entries) if i != j):
                overlaps += 1
                self.assertTrue(name.startswith("compiler_reused_"), name)
        self.assertGreater(overlaps, 0)

    def test_allocator_refuses_instruction_effects_it_does_not_model(self):
        storage = Storage()
        value = storage.bit("value")
        # LDR is modeled now; a still-unsupported accumulator edge block must
        # retain the fail-closed behavior this test exercises.
        p = Program([["LD 1", "RISING0", "ST " + value]])
        with self.assertRaisesRegex(CompileError, "unmodelled|unsupported"):
            storage.finalize(p, {})


if __name__ == "__main__":
    unittest.main()
