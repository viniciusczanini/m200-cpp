"""SR frontend/reverse contracts, including G06 loop and shared-resource support."""

import tempfile
from pathlib import Path
import unittest
from m200.frontend import compile_source
from m200.model import CompileError, Program
from m200.il import Machine
from m200.native import run_native
from m200.reverse import to_cpp

SOURCE = """#include <plc.hpp>
void leaf(){plc::write_word(0,20);plc::write_word(1,1);plc::output(1,true);if(plc::input(1))return;plc::write_word(0,25);plc::write_word(1,2);plc::output(3,true);}
plc::Subroutine sr{63,leaf};
void scan(){plc::write_word(0,10);plc::write_word(1,0);plc::output(1,false);plc::output(2,false);plc::output(3,false);sr.call(plc::input(0));plc::write_word(2,plc::read_word(0));plc::write_word(0,30);plc::output(0,plc::input(0));plc::output(2,true);plc::output(4,plc::read_word(0)==30);}
"""
FRAMES = [
    {"inputs": {"0": a, "1": b}, "dt_ms": 13}
    for a, b in [(0, 0), (1, 0), (1, 1), (0, 1), (1, 0)]
]
WORDS = [[30, 0, 10], [30, 2, 25], [30, 1, 20], [30, 0, 10], [30, 2, 25]]
BITS = [
    [0, 0, 1, 0, 1],
    [1, 1, 1, 1, 1],
    [1, 1, 1, 0, 1],
    [0, 0, 1, 0, 1],
    [1, 1, 1, 1, 1],
]


class SourceReversePrototype(unittest.TestCase):
    def build(self, source, folder, name="source.cpp"):
        p = Path(folder) / name
        p.write_text(source)
        return p, compile_source(p)

    def check_trace(self, p):
        machine = Machine(p)
        for frame, words, bits in zip(FRAMES, WORDS, BITS):
            self.assertEqual(
                machine.step(frame["inputs"], frame["dt_ms"])[:5], list(map(bool, bits))
            )
            self.assertEqual(machine.words[:3], words)
        self.assertEqual(machine.now, 65)

    def test_cpp_implicit_and_conditional_return_match_literals_native_and_vm(self):
        with tempfile.TemporaryDirectory() as d:
            source, p = self.build(SOURCE, d)
            self.assertEqual(set(p.subroutines), {63})
            self.assertEqual(
                (p.subroutines[63].name, p.subroutines[63].section_number), ("leaf", 2)
            )
            self.assertEqual(p.as_dict()["format"], "m200-cpp-il-v2")
            self.check_trace(p)
            self.assertEqual(
                [x[:5] for x in run_native(source, FRAMES)],
                [list(map(bool, b)) for b in BITS],
            )
            self.check_trace(Program.from_dict(p.as_dict()))

    def test_reverse_recompile_preserves_identity_and_literal_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            _, p = self.build(SOURCE, d)
            p.subroutines[63].name = "Native açúcar 🙂"
            p.subroutines[63].section_number = 42
            rev = to_cpp(p)
            self.assertIn('"Native açúcar 🙂",42', rev)
            self.assertNotIn("\\ud83d", rev)
            path, q = self.build(rev, d, "reverse.cpp")
            self.assertEqual(
                (q.subroutines[63].name, q.subroutines[63].section_number),
                ("Native açúcar 🙂", 42),
            )
            self.check_trace(q)
            self.assertEqual(
                [x[:5] for x in run_native(path, FRAMES)],
                [list(map(bool, b)) for b in BITS],
            )

    def test_two_resources_repeated_calls_and_shared_word_identity(self):
        source = """#include <plc.hpp>
void first(){plc::write_word(7,plc::add_i16(plc::read_word(7),1));}
void second(){plc::write_word(8,plc::read_word(7));}
plc::Subroutine a{0,first,"first native",99};plc::Subroutine b{63,second,"second native",2};
void scan(){plc::write_word(7,0);plc::write_word(8,0);a.call(plc::input(0));a.call(plc::input(0));b.call(plc::input(1));plc::output(0,plc::read_word(7)==2);plc::output(1,plc::read_word(8)==2);}
"""
        with tempfile.TemporaryDirectory() as d:
            path, p = self.build(source, d)
            frames = [
                {"inputs": {"0": a, "1": b}, "dt_ms": 7}
                for a, b in [(0, 0), (1, 0), (1, 1), (0, 1)]
            ]
            expected = [[0, 0], [1, 0], [1, 1], [0, 0]]
            for candidate in [p, Program.from_dict(p.as_dict())]:
                machine = Machine(candidate)
                self.assertEqual(
                    [machine.step(f["inputs"], 7)[:2] for f in frames],
                    [list(map(bool, x)) for x in expected],
                )
                self.assertEqual(machine.now, 28)
            self.assertEqual(
                [x[:2] for x in run_native(path, frames)],
                [list(map(bool, x)) for x in expected],
            )
            rev, q = self.build(to_cpp(p), d, "reverse.cpp")
            self.assertEqual(
                (q.subroutines[0].section_number, q.subroutines[63].section_number),
                (99, 2),
            )
            self.assertEqual(
                [x[:2] for x in run_native(rev, frames)],
                [list(map(bool, x)) for x in expected],
            )

    def test_guarded_call_and_leaf_return_do_not_end_master_or_use_leaf_labels(self):
        s = SOURCE.replace(
            "sr.call(plc::input(0));", "if(plc::input(0)){sr.call(true);}"
        )
        with tempfile.TemporaryDirectory() as d:
            _, p = self.build(s, d)
            self.check_trace(p)
            self.assertTrue(
                any(x.endswith("ENDC") for r in p.subroutines[63].rungs for x in r)
            )
            self.assertFalse(
                any(x.startswith("%L") for r in p.subroutines[63].rungs for x in r)
            )

    def test_false_registered_call_does_not_evaluate_leaf_side_effect(self):
        s = """#include <plc.hpp>
void leaf(){plc::output(0,true);plc::write_word(0,99);}
plc::Subroutine sr{0,leaf};void scan(){plc::output(0,false);plc::write_word(0,7);sr.call(false);plc::output(1,plc::read_word(0)==7);}
"""
        with tempfile.TemporaryDirectory() as d:
            path, p = self.build(s, d)
            self.assertEqual(Machine(p).step({}, 10)[:2], [False, True])
            self.assertEqual(run_native(path, [{}])[0][:2], [False, True])

    def test_invalid_metadata_or_nested_leaf_refuses(self):
        bad = [
            SOURCE.replace("63,leaf", "64,leaf"),
            SOURCE.replace("63,leaf", '63,leaf,"",2'),
            SOURCE.replace("63,leaf", '63,leaf,"bad\\0name",2'),
            SOURCE.replace("63,leaf", '63,leaf,"name",-1'),
            SOURCE.replace("63,leaf", '63,leaf,"name",2147483648'),
            SOURCE.replace("63,leaf", "63,leaf,plc::read_word(0),2"),
        ]
        nested = """#include <plc.hpp>
void other(){}plc::Subroutine b{1,other};void leaf(){b.call(false);}plc::Subroutine a{0,leaf};void scan(){a.call(true);}
"""
        bad.append(nested)
        with tempfile.TemporaryDirectory() as d:
            for i, s in enumerate(bad):
                with self.subTest(i=i), self.assertRaises(CompileError):
                    self.build(s, d, "bad" + str(i) + ".cpp")

    def test_bounded_loop_and_local_goto_have_real_leaf_control_flow(self):
        sources = [
            """#include <plc.hpp>
void leaf(){plc::i16 visits=0;while(visits<3){visits=plc::add_i16(visits,1);}plc::write_word(7,visits);}
plc::Subroutine sr{0,leaf};void scan(){plc::write_word(7,0);sr.call(plc::input(0));plc::write_word(8,77);plc::output(0,plc::read_word(7)==3);}
""",
            """#include <plc.hpp>
void leaf(){goto local;plc::write_word(7,99);local:plc::write_word(7,3);}
plc::Subroutine sr{0,leaf};void scan(){plc::write_word(7,0);sr.call(plc::input(0));plc::write_word(8,77);plc::output(0,plc::read_word(7)==3);}
""",
        ]
        frames = [{"inputs": {"0": value}, "dt_ms": 11} for value in (False, True, False)]
        for index, source in enumerate(sources):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as d:
                path, p = self.build(source, d)
                self.assertTrue(any(line.startswith("%L") for rung in p.subroutines[0].rungs for line in rung))
                self.assertTrue(any(line == "SR0" for rung in p.rungs for line in rung))
                reverse, rebuilt = self.build(to_cpp(p), d, "reverse.cpp")
                for program in (p, Program.from_dict(p.as_dict()), rebuilt):
                    machine = Machine(program, instruction_limit=1000)
                    for frame, value in zip(frames, (0, 3, 0)):
                        self.assertEqual(machine.step(frame["inputs"], 11)[0], value == 3)
                        self.assertEqual(machine.words[7:9], [value, 77])
                    self.assertEqual(machine.now, 33)
                for cpp in (path, reverse):
                    self.assertEqual([row[0] for row in run_native(cpp, frames)], [False, True, False])

    def test_legacy_cpp_and_reverse_remain_v1(self):
        with tempfile.TemporaryDirectory() as d:
            _, p = self.build(
                "#include <plc.hpp>\nvoid scan(){plc::output(0,plc::input(0));}", d
            )
            self.assertEqual(p.as_dict()["format"], "m200-cpp-il-v1")
            self.assertNotIn("Subroutine", to_cpp(p))

    def test_caller_live_temporaries_and_global_image_survive_leaf_and_master_return(
        self,
    ):
        s = """#include <plc.hpp>
bool shared=false;
void leaf(){bool local=plc::input(1);plc::write_m(20,local);shared=local;plc::output(1,local);return;plc::output(3,true);}
plc::Subroutine sr{0,leaf};
void scan(){bool saved=!plc::input(0);plc::output(3,false);shared=false;sr.call(plc::input(2));plc::output(0,saved);plc::output(2,shared);if(plc::input(3))return;plc::output(4,plc::input(1));}
"""
        frames = [
            {"inputs": {str(i): b for i, b in enumerate(v)}, "dt_ms": 19}
            for v in [(0, 1, 1, 0), (1, 0, 1, 0), (0, 0, 0, 1), (1, 1, 1, 1)]
        ]
        expected = [[1, 1, 1, 0, 1], [0, 0, 0, 0, 0], [1, 0, 0, 0, 0], [0, 1, 1, 0, 0]]
        with tempfile.TemporaryDirectory() as d:
            source, p = self.build(s, d)
            for candidate in [p, Program.from_dict(p.as_dict())]:
                m = Machine(candidate)
                self.assertEqual(
                    [m.step(f["inputs"], 19)[:5] for f in frames],
                    [list(map(bool, x)) for x in expected],
                )
                self.assertEqual(m.now, 76)
            self.assertEqual(
                [x[:5] for x in run_native(source, frames)],
                [list(map(bool, x)) for x in expected],
            )
            reverse, q = self.build(to_cpp(p), d, "reverse.cpp")
            m = Machine(q)
            self.assertEqual(
                [m.step(f["inputs"], 19)[:5] for f in frames],
                [list(map(bool, x)) for x in expected],
            )
            self.assertEqual(
                [x[:5] for x in run_native(reverse, frames)],
                [list(map(bool, x)) for x in expected],
            )

    def test_forward_declaration_empty_leaf_and_default_section_ordinal(self):
        s = """#include <plc.hpp>
void leaf();void other(){}plc::Subroutine a{63,leaf};plc::Subroutine b{0,other};void leaf(){plc::output(0,true);}void scan(){a.call(plc::input(0));b.call(true);}
"""
        with tempfile.TemporaryDirectory() as d:
            _, p = self.build(s, d)
            self.assertEqual(
                (p.subroutines[63].section_number, p.subroutines[0].section_number),
                (2, 3),
            )
            self.assertEqual(p.subroutines[0].rungs, [["END"]])
            self.assertEqual(Machine(p).step({"0": True}, 10)[0], True)

    def test_literal_metadata_escapes_and_duplicate_independent_identities(self):
        good = SOURCE.replace("63,leaf", '63,leaf,"line\\tname\\\\quote\\"",2147483647')
        with tempfile.TemporaryDirectory() as d:
            _, p = self.build(good, d)
            self.assertEqual(p.subroutines[63].name, 'line\tname\\quote"')
            _, q = self.build(to_cpp(p), d, "reverse.cpp")
            self.assertEqual(q.subroutines[63].name, p.subroutines[63].name)
            for args in [
                '63,leaf,"bad\\uFFFF",2',
                "true,leaf",
                '63,leaf,"name",true',
                '63,leaf,"name",2.5',
                "63,nullptr",
                "63,scan",
            ]:
                with self.subTest(args=args), self.assertRaises(CompileError):
                    self.build(SOURCE.replace("63,leaf", args), d, "bad.cpp")
            for descriptor in [
                'plc::Subroutine duplicate{63,other,"different",3};',
                'plc::Subroutine duplicate{0,other,"leaf",3};',
                'plc::Subroutine duplicate{0,other,"different",2};',
            ]:
                s = SOURCE.replace(
                    "void leaf(){", "void other(){}\nvoid leaf(){"
                ).replace("void scan(){", descriptor + "\nvoid scan(){")
                with (
                    self.subTest(descriptor=descriptor),
                    self.assertRaises(CompileError),
                ):
                    self.build(s, d, "duplicate.cpp")

    def test_shared_timer_and_native_edge_leaf_have_literal_traces_and_reverse(self):
        cases = [
            ("""#include <plc.hpp>
plc::Ton timer{0,10,2};void leaf(){bool q=timer.update(plc::input(0));plc::output(0,q);}
plc::Subroutine sr{0,leaf};void scan(){sr.call(true);sr.call(true);plc::output(1,timer.done());}
""", (False, True, True, True, True),
             [[False, False], [False, False], [False, False], [True, True], [True, True]]),
            ("""#include <plc.hpp>
void leaf(){plc::output(0,plc::input_rising(0));}plc::Subroutine sr{0,leaf};void scan(){sr.call(true);}
""", (False, True, True, False, True),
             [[False], [True], [False], [False], [True]]),
        ]
        for index, (source, inputs, expected) in enumerate(cases):
            frames = [{"inputs": {"0": value}, "dt_ms": 10} for value in inputs]
            with self.subTest(index=index), tempfile.TemporaryDirectory() as d:
                path, p = self.build(source, d)
                if index == 0:
                    self.assertEqual(set(p.timers), {0})
                    self.assertEqual(sum(line == "BLK %TM0" for rung in p.subroutines[0].rungs for line in rung), 1)
                    self.assertFalse(any(line == "BLK %TM0" for rung in p.rungs for line in rung))
                    self.assertEqual(to_cpp(p).count("plc::Ton timer_0{"), 1)
                else:
                    self.assertTrue(any(line.startswith("LDR %I0.0") for rung in p.subroutines[0].rungs for line in rung))
                reverse, rebuilt = self.build(to_cpp(p), d, "reverse.cpp")
                self.assertEqual(rebuilt.timers, p.timers)
                for program in (p, Program.from_dict(p.as_dict()), rebuilt):
                    machine = Machine(program)
                    self.assertEqual([machine.step(frame["inputs"], 10)[:len(expected[0])] for frame in frames], expected)
                    self.assertEqual(machine.now, 50)
                for cpp in (path, reverse):
                    self.assertEqual([row[:len(expected[0])] for row in run_native(cpp, frames)], expected)


if __name__ == "__main__":
    unittest.main()
