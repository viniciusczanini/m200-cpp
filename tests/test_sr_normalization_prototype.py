"""Copied Master normalization only; real source and native evidence stay separate."""

import copy
from pathlib import Path
import tempfile
import unittest

from m200.flow import destinations
from m200.frontend import compile_source
from m200.il import Machine
from m200.ladder_lowering import needed, normalize
from m200.model import Program, SubroutineDefinition
from m200.native import run_native


class SubroutineNormalization(unittest.TestCase):
    def test_master_normalization_preserves_leaf_return_and_private_extents(self):
        leaf = [
            ["LD 1", "[%MW0:=20]"],
            ["LD 1", "[%MW1:=1]"],
            ["LD 1", "ST %Q0.1"],
            ["LD 0", "ST %M500"],
            ["LD 1", "ST %M501"],
            ["LD %I0.1", "ENDC"],
            ["LD 1", "[%MW0:=25]"],
            ["LD 1", "[%MW1:=2]"],
            ["LD 1", "ST %Q0.3"],
            ["END"],
        ]
        origins = [{"file": "leaf.cpp", "line": i + 20} for i in range(len(leaf))]
        master = [
            ["LD %I0.2", "ORN %I0.2", "[%MW0:=10]"],
            ["LD 1", "[%MW1:=0]"],
            ["LD 0", "ST %Q0.1"],
            ["LD 0", "ST %Q0.3"],
            ["LD %I0.0", "SR63"],
            ["LD %I0.2", "ORN %I0.2", "[%MW2:=%MW0]"],
            ["LD 1", "[%MW0:=30]"],
            ["LD 1", "ST %Q0.2"],
            ["LD %I0.0", "ST %Q0.0"],
        ]
        p = Program(
            rungs=master,
            subroutines={63: SubroutineDefinition(63, "native leaf", 2, leaf, origins)},
        )
        before = copy.deepcopy(p.as_dict())
        n = normalize(p)
        self.assertEqual(p.as_dict(), before)
        self.assertEqual(n.subroutines, p.subroutines)
        self.assertEqual(n.subroutines[63].rungs, leaf)
        self.assertFalse(
            any(
                line.startswith("JMPC")
                for rung in n.subroutines[63].rungs
                for line in rung
            )
        )
        self.assertEqual(len(n.metadata["rung_origins"]), len(n.rungs))
        machine = Machine(n)
        for controls, words, bits in [
            ((0, 0), [30, 0, 10], [0, 0, 1, 0]),
            ((1, 0), [30, 2, 25], [1, 1, 1, 1]),
            ((1, 1), [30, 1, 20], [1, 1, 1, 0]),
        ]:
            self.assertEqual(
                machine.step({"0": controls[0], "1": controls[1]}, 17)[:4],
                list(map(bool, bits)),
            )
            self.assertEqual(machine.words[:3], words)
        self.assertEqual(machine.memory[500:502], [False, True])
        self.assertEqual(machine.now, 51)

    def test_canonical_call_and_separate_leaf_are_not_needlessly_rewritten(self):
        p = Program(
            rungs=[["LD %M20", "SR0"]],
            subroutines={
                0: SubroutineDefinition(0, "leaf", 2, [["LD %M20", "ST %M21"]])
            },
        )
        self.assertFalse(needed(p))
        self.assertIs(normalize(p), p)

    def test_master_label_stays_outside_native_call_graph(self):
        p = Program(
            rungs=[["%L0:", "LD %M20", "SR0"]],
            subroutines={0: SubroutineDefinition(0, "leaf", 2, [["END"]])},
        )
        n = normalize(p)
        self.assertIn("%L0", destinations(n))
        call = next(r for r in n.rungs if r[-1] == "SR0")
        self.assertEqual(len(call), 2)
        self.assertNotIn("%L0:", call)
        self.assertTrue(call[0].startswith("LD %M"))
        self.assertEqual(n.subroutines[0].rungs, [["END"]])

    def test_cpp_lowered_program_normalizes_with_literal_native_oracle(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source.cpp"
            source.write_text("""#include <plc.hpp>
void leaf(){plc::write_word(0,20);plc::write_word(1,1);plc::output(1,true);if(plc::input(1))return;plc::write_word(0,25);plc::write_word(1,2);plc::output(3,true);}
plc::Subroutine sr{63,leaf,"independent native identity",2};
void scan(){plc::write_word(0,10);plc::write_word(1,0);plc::output(1,false);plc::output(3,false);sr.call(plc::input(0));plc::write_word(2,plc::read_word(0));plc::write_word(0,30);plc::output(0,plc::input(0));plc::output(2,true);}
""")
            p = compile_source(source)
            before = copy.deepcopy(p.as_dict())
            n = normalize(p)
            self.assertEqual(p.as_dict(), before)
            expected_bits = [[0, 0, 1, 0], [1, 1, 1, 1], [1, 1, 1, 0]]
            expected_words = [[30, 0, 10], [30, 2, 25], [30, 1, 20]]
            frames = [
                {"inputs": {"0": a, "1": b}, "dt_ms": 13}
                for a, b in [(0, 0), (1, 0), (1, 1)]
            ]
            self.assertEqual(
                [row[:4] for row in run_native(source, frames)], expected_bits
            )
            for program in (p, n):
                machine = Machine(program)
                for frame, bits, words in zip(frames, expected_bits, expected_words):
                    self.assertEqual(machine.step(frame["inputs"], 13)[:4], bits)
                    self.assertEqual(machine.words[:3], words)
                self.assertEqual(machine.now, 39)


if __name__ == "__main__":
    unittest.main()
