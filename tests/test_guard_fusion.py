"""Repeated compiler guards must be compact without losing state or effects."""

from pathlib import Path
import tempfile
import unittest

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.lower import Lowerer
from m200.model import CompileError
from m200.native import run_native
from m200.numeric import Number
from m200.project import load_project, write_project
from m200.reverse import to_cpp


class GuardFusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def finish(self, lower):
        lower.program.rungs = lower.constant_rungs + lower.program.rungs
        program = lower.storage.finalize(lower.program, lower.constants)
        validate(program)
        return program

    def pair(self, lower, guard, predicate="[%MW0>=0]", temporary=None, other=None):
        temporary = temporary or lower.bit("guarded_predicate")
        result = lower.bit("nested_guard")
        lower.rung("LD " + guard, "AND " + predicate, "ST " + temporary)
        lower.rung("LD " + (other or guard), "AND " + temporary, "ST " + result)
        lower.assign("%Q0.0", result)
        return temporary

    def test_repeated_captured_guard_emits_one_rung_and_preserves_truth_table(self):
        lower = Lowerer(reserved_words={0})
        guard = lower.copy("%I0.0", "captured_guard")
        self.pair(lower, guard)
        program = self.finish(lower)
        # A native input contact, comparison and output coil suffice.
        self.assertEqual(len(program.rungs), 1)
        self.assertEqual(sum(map(len, program.rungs)), 3)
        saved = self.work / "compact.smbp"
        write_project(program, Path(__file__).parent / "fixtures/synthetic.smbp", saved)
        for candidate in (program, load_project(saved)):
            for enabled, word, expected in [
                (0, -1, 0),
                (0, 1, 0),
                (1, -1, 0),
                (1, 1, 1),
            ]:
                machine = Machine(candidate)
                machine.memory = [True] * 1024
                machine.words[0] = word
                self.assertEqual(machine.step({0: enabled})[0], expected)
        source = self.work / "recovered.cpp"
        source.write_text(to_cpp(program))
        frames = [{"inputs": {0: value}} for value in (0, 1, 0, 1)]
        self.assertEqual([q[0] for q in run_native(source, frames)], [0, 1, 0, 1])

    def test_predicate_keeps_prior_overflow_and_index_error_for_false_guard(self):
        lower = Lowerer(reserved_words={0, 1}, reserved={0})
        lower.rung("LD 1", "[%MW0:=32767]")
        lower.rung("LD 1", "[%MW0:=%MW0 + 1]")
        lower.rung("LD 1", "[%MW1:=-32768]")
        lower.copy("%M0[%MW1]", "index_effect")
        guard = lower.copy("%I0.0", "captured_guard")
        self.pair(lower, guard, "[%MW0<0]")
        lower.assign("%Q0.1", "%S18")
        lower.assign("%Q0.2", "%S20")
        program = self.finish(lower)
        for enabled in (0, 1):
            self.assertEqual(Machine(program).step({0: enabled})[:3], [enabled, 1, 1])
        source = self.work / "flags.cpp"
        source.write_text(to_cpp(program))
        frames = [{"inputs": {0: v}} for v in (0, 1)]
        self.assertEqual(
            [q[:3] for q in run_native(source, frames)], [[0, 1, 1], [1, 1, 1]]
        )

    def test_private_numeric_predicate_is_fused_before_physical_allocation(self):
        lower = Lowerer(reserved_words={0})
        value = lower.copy(Number("i16", "%MW0"), "numeric_snapshot")
        guard = lower.copy("%I0.0", "captured_guard")
        self.pair(lower, guard, "[" + value.code + ">=0]")
        program = self.finish(lower)
        # Native literal guard for the word snapshot and one fused
        # input/comparison/output rung; no constant-memory setup/copies.
        self.assertEqual(len(program.rungs), 2)
        self.assertEqual(sum(map(len, program.rungs)), 5)
        for enabled, word, expected in [(0, -1, 0), (0, 1, 0), (1, -1, 0), (1, 1, 1)]:
            machine = Machine(program)
            machine.words[0] = word
            self.assertEqual(machine.step({0: enabled})[0], expected)

    def test_temporary_read_again_survives_dirty_memory(self):
        lower = Lowerer(reserved_words={0})
        guard = lower.copy("%I0.0", "captured_guard")
        temporary = self.pair(lower, guard)
        lower.assign("%Q0.1", temporary)
        program = self.finish(lower)
        for enabled, word, expected in [(0, 1, 0), (1, -1, 0), (1, 1, 1)]:
            machine = Machine(program)
            machine.memory = [True] * 1024
            machine.words[0] = word
            self.assertEqual(machine.step({0: enabled})[:2], [expected, expected])

    def test_temporary_equal_to_guard_keeps_its_observable_write(self):
        lower = Lowerer(reserved_words={0})
        guard = lower.copy("%I0.0", "captured_guard")
        self.pair(lower, guard, temporary=guard)
        lower.assign("%Q0.1", guard)
        program = self.finish(lower)
        for enabled, word, expected in [(0, 1, 0), (1, -1, 0), (1, 1, 1)]:
            machine = Machine(program)
            machine.words[0] = word
            self.assertEqual(machine.step({0: enabled})[:2], [expected, expected])

    def test_consumer_label_entry_preserves_skipped_producer_state(self):
        lower = Lowerer(reserved_words={0})
        label = lower.new_label()
        lower.jump(label, "%I0.2")
        guard = lower.copy("%I0.0", "captured_guard")
        temporary, result = lower.bit(), lower.bit()
        lower.rung("LD " + guard, "AND [%MW0>=0]", "ST " + temporary)
        lower.rung("LD " + guard, "AND " + temporary, "ST " + result)
        lower.program.rungs[-1].insert(0, label + ":")
        lower.assign("%Q0.0", result)
        machine = Machine(self.finish(lower))
        machine.memory = [True] * 1024
        for inputs, expected in [
            ({2: 1}, 1),
            ({}, 0),
            ({2: 1}, 0),
            ({0: 1}, 1),
            ({2: 1}, 1),
        ]:
            self.assertEqual(machine.step(inputs)[0], expected)

    def test_different_guard_preserves_both_inputs(self):
        lower = Lowerer(reserved_words={0})
        first, second = lower.copy("%I0.0"), lower.copy("%I0.1")
        self.pair(lower, first, other=second)
        program = self.finish(lower)
        for a, b, expected in [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 1)]:
            self.assertEqual(Machine(program).step({0: a, 1: b})[0], expected)

    def test_indexed_series_contact_gate_is_not_relaxed_by_optimization(self):
        lower = Lowerer(reserved={0}, reserved_words={0})
        guard = lower.copy("%I0.0")
        self.pair(lower, guard, "%M0[%MW0]")
        with self.assertRaisesRegex(CompileError, "indexed"):
            self.finish(lower)

    def test_unused_pure_boolean_read_is_removed_without_removing_the_output(self):
        source = self.work / "unused.cpp"
        source.write_text(
            "#include <plc.hpp>\nvoid scan(){bool unused=plc::input(0);plc::output(0,true);}"
        )
        program = compile_source(source)
        self.assertGreater(
            program.metadata["dead_private_stores"]["eliminated_rungs"], 0
        )
        self.assertFalse(
            any("%I0.0" in line for rung in program.rungs for line in rung)
        )
        self.assertTrue(Machine(program).step({})[0])


if __name__ == "__main__":
    unittest.main()
