from pathlib import Path
import tempfile
import unittest

from m200.frontend import compile_source
from m200.il import Machine
from m200.native import run_native


class DirectIO(unittest.TestCase):
    def build(self, body):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "program.cpp"
        path.write_text("#include <plc.hpp>\nvoid scan(){" + body + "}\n")
        return path, compile_source(path)

    def test_simple_wire_is_one_native_rung(self):
        path, p = self.build("plc::output(0,plc::input(0));")
        self.assertEqual(p.rungs, [["LD %I0.0", "ST %Q0.0"]])
        frames = [{"inputs": {"0": x}, "dt_ms": 10} for x in (0, 1, 0)]
        m = Machine(p)
        self.assertEqual(
            [m.step(f["inputs"], 10) for f in frames], run_native(path, frames)
        )

    def test_packed_output_is_one_assignment(self):
        path, p = self.build("plc::write_output_bits_i16(0,16,plc::read_word(10));")
        self.assertEqual(
            sum("%Q0.0:16:=" in line.replace(" ", "") for r in p.rungs for line in r), 1
        )
        self.assertFalse(any(line.startswith("ST %Q") for r in p.rungs for line in r))
        m = Machine(p)
        m.words[10] = 0x8241
        m.outputs = [True] * 16
        self.assertEqual(m.step({}, 10), [bool(0x8241 & (1 << i)) for i in range(16)])

    def test_same_scan_scalar_and_packed_reads_observe_last_write(self):
        path, p = self.build(
            "plc::output(0,true);plc::write_word(0,plc::read_output_bits_i16(0,16));plc::output(0,false);plc::output(1,plc::output_state(0));plc::output(2,plc::read_word(0)==1);"
        )
        frames = [{"dt_ms": 10}] * 3
        m = Machine(p)
        m.outputs = [True] * 16
        for f, native in zip(frames, run_native(path, frames)):
            self.assertEqual(m.step({}, 10), native)
        self.assertEqual(m.words[0], 1)

    def test_conditional_return_retains_prior_writes_and_initialization(self):
        path, p = self.build("if(plc::input(0))return;plc::output(0,plc::input(1));")
        frames = [
            {"inputs": {"0": a, "1": b}, "dt_ms": 10}
            for a, b in [(1, 1), (0, 1), (1, 0), (0, 0)]
        ]
        m = Machine(p)
        m.outputs[0] = True
        self.assertEqual(
            [m.step(f["inputs"], 10) for f in frames], run_native(path, frames)
        )

    def test_read_before_write_and_toggle_initialize_on_first_scan(self):
        path, p = self.build("plc::output(0,!plc::output_state(0));")
        m = Machine(p)
        m.outputs[0] = True
        frames = [{"dt_ms": 10}] * 4
        self.assertEqual([m.step({}, 10) for _ in frames], run_native(path, frames))

    def test_packed_overlap_and_partial_write_preserve_other_bits(self):
        path, p = self.build(
            "plc::write_output_bits_i16(0,16,10837);plc::write_output_bits_i16(8,8,plc::read_output_bits_i16(0,8));plc::write_output_bits_i16(0,10,3);plc::write_word(0,plc::read_output_bits_i16(0,16));"
        )
        m = Machine(p)
        frames = [{"dt_ms": 10}] * 3
        self.assertEqual([m.step({}, 10) for _ in frames], run_native(path, frames))
        self.assertEqual(m.words[0], 0x5403)

    def test_conditional_packed_write_preserves_prior_output_image(self):
        path, p = self.build(
            "if(plc::input(0)){plc::write_output_bits_i16(0,16,21845);}plc::write_word(0,plc::read_output_bits_i16(0,16));"
        )
        frames = [{"inputs": {"0": x}, "dt_ms": 10} for x in (0, 1, 0, 1)]
        m = Machine(p)
        m.outputs = [True] * 16
        self.assertEqual(
            [m.step(f["inputs"], 10) for f in frames], run_native(path, frames)
        )
        self.assertEqual(m.words[0], 21845)

    def test_shared_subroutine_output_image_and_early_leaf_return(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "sr.cpp"
        path.write_text(
            '#include <plc.hpp>\nvoid leaf(){plc::output(0,true);if(plc::input(1))return;plc::output(1,true);}plc::Subroutine sr{0,leaf,"leaf",2};void scan(){plc::output(0,false);plc::output(1,false);sr.call(plc::input(0));plc::output(2,plc::output_state(0));}'
        )
        p = compile_source(path)
        m = Machine(p)
        m.outputs[:3] = [True] * 3
        frames = [
            {"inputs": {"0": a, "1": b}, "dt_ms": 10}
            for a, b in [(0, 0), (1, 0), (1, 1), (0, 1)]
        ]
        self.assertEqual(
            [m.step(f["inputs"], 10) for f in frames], run_native(path, frames)
        )

    def test_run_initialization_does_not_touch_undeclared_output_holes(self):
        _, p = self.build("if(plc::input(0))plc::output(3,true);")
        m = Machine(p)
        m.outputs = [True] * 16
        result = m.step({"0": False}, 10)
        self.assertEqual(result, [i != 3 for i in range(16)])
        self.assertEqual(m.step({"0": True}, 10), [True] * 16)


if __name__ == "__main__":
    unittest.main()
