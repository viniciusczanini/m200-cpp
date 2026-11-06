"""Removing emission overhead must preserve flags, labels and memory images."""

from pathlib import Path
import re
import tempfile
import unittest

from m200.frontend import compile_source
from m200.allocation import Storage
from m200.il import Machine, validate
from m200.lower import Lowerer
from m200.model import CompileError, Program
from m200.native import run_native
from m200.numeric import Number, literal
from m200.project import load_project, write_project
from m200.reverse import to_cpp


SELF_COPY = re.compile(r"\[(%MW[0-9]+):=\1\]")


class EmissionCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def finish(self, lower):
        lower.program.rungs = lower.constant_rungs + lower.program.rungs
        lower.program.metadata.setdefault(
            "rung_origins",
            [{"generated": f"source_{i}"} for i in range(len(lower.program.rungs))],
        )
        program = lower.storage.finalize(lower.program, lower.constants)
        validate(program)
        self.assertEqual(len(program.metadata["rung_origins"]), len(program.rungs))
        return program

    def private_copy(self, lower):
        first = lower.word("i16", "first")
        lower.numeric_assign(first, literal(7, "i16"))
        lower.assign("%Q0.0", "%I0.0")
        second = lower.copy(first, "second")
        lower.assign("%Q0.1", "%I0.1")
        lower.numeric_assign(Number("i16", "%MW0"), second)

    def self_copies(self, program):
        return [
            line for rung in program.rungs for line in rung if SELF_COPY.fullmatch(line)
        ]

    def test_private_coalesced_word_copy_is_absent_and_values_survive_dirty_storage(
        self,
    ):
        lower = Lowerer(reserved_words={0})
        self.private_copy(lower)
        program = self.finish(lower)
        self.assertEqual(self.self_copies(program), [])
        frames = [{"inputs": {0: a, 1: b}} for a, b in [(0, 0), (1, 0), (0, 1), (1, 1)]]
        destination = self.work / "copy.smbp"
        write_project(
            program, Path(__file__).parent / "fixtures/synthetic.smbp", destination
        )
        recovered = self.work / "copy.cpp"
        recovered.write_text(to_cpp(load_project(destination)))
        for candidate in (
            program,
            load_project(destination),
            compile_source(recovered),
        ):
            machine = Machine(candidate)
            machine.memory = [True] * 1024
            machine.words = [0x2468] * 8000
            for frame, expected in zip(frames, [[0, 0], [1, 0], [0, 1], [1, 1]]):
                self.assertEqual(machine.step(frame["inputs"])[:2], expected)
                self.assertEqual(machine.words[0], 7)
        self.assertEqual(
            [q[:2] for q in run_native(recovered, frames)],
            [[0, 0], [1, 0], [0, 1], [1, 1]],
        )

    def test_public_word_self_store_is_preserved(self):
        lower = Lowerer(reserved_words={0})
        lower.numeric_assign(Number("i16", "%MW0"), Number("i16", "%MW0"))
        program = self.finish(lower)
        self.assertEqual(self.self_copies(program), ["[%MW0:=%MW0]"])
        machine = Machine(program)
        machine.words[0] = 0xF123
        machine.step({})
        self.assertEqual(machine.words[0] & 65535, 0xF123)

    def test_float_self_copy_still_observes_invalid_numeric_data_when_enabled(self):
        lower = Lowerer()
        value = lower.word("f32", "invalid_if_enabled")
        guard = lower.copy("%I0.0")
        lower.numeric_assign(value, value, guard)
        program = self.finish(lower)
        line = next(line for rung in program.rungs for line in rung if ":=" in line)
        address = int(re.search(r"%MF([0-9]+)", line)[1])
        machine = Machine(program)
        machine.words[address : address + 2] = [0, 0x7FC0]
        machine.step({0: False})
        with self.assertRaisesRegex(CompileError, "non-finite|numeric"):
            machine.step({0: True})

    def test_private_copy_cleanup_keeps_carry_and_overflow(self):
        lower = Lowerer(reserved_words={0, 1})
        lower.rung("LD 1", "[%MW1:=-32768]")
        lower.rung("LD 1", "[%MW1:=SHL(%MW1,1)]")
        lower.rung("LD 1", "[%MW1:=32767]")
        lower.rung("LD 1", "[%MW1:=%MW1 + 1]")
        self.private_copy(lower)
        lower.assign("%Q0.2", "%S17")
        lower.assign("%Q0.3", "%S18")
        program = self.finish(lower)
        self.assertEqual(Machine(program).step({})[:4], [0, 0, 1, 1])
        source = self.work / "flags.cpp"
        source.write_text(to_cpp(program))
        self.assertEqual(run_native(source, [{}])[0][:4], [0, 0, 1, 1])

    def test_label_attaches_to_the_real_statement_and_keeps_its_origin(self):
        lower = Lowerer()
        target = lower.new_label()
        lower.jump(target)
        lower.label(target)
        lower.assign("%Q0.0", "%I0.0")
        program = self.finish(lower)
        labelled = [r for r in program.rungs if r[0] == target + ":"]
        self.assertEqual(labelled, [[target + ":", "LD %I0.0", "ST %Q0.0"]])
        index = program.rungs.index(labelled[0])
        self.assertEqual(
            program.metadata["rung_origins"][index], {"generated": "source_4"}
        )
        destination = self.work / "label.smbp"
        write_project(
            program, Path(__file__).parent / "fixtures/synthetic.smbp", destination
        )
        for candidate in (program, load_project(destination)):
            machine = Machine(candidate)
            self.assertEqual(
                [machine.step({0: bit})[0] for bit in (0, 1, 0)], [0, 1, 0]
            )

    def test_loop_back_edges_and_exit_labels_keep_all_iterations_in_one_scan(self):
        source = self.work / "loop.cpp"
        source.write_text("""#include <plc.hpp>
void scan(){plc::i16 n=0;plc::i16 sum=0;
while(n<5){sum=plc::add_i16(sum,n);n=plc::add_i16(n,1);}
plc::write_word(0,sum);plc::output(0,sum==10);}
""")
        program = compile_source(source)
        machine = Machine(program)
        for _ in range(3):
            self.assertTrue(machine.step({})[0])
            self.assertEqual(machine.words[0], 10)
        self.assertEqual([q[0] for q in run_native(source, [{}, {}, {}])], [1, 1, 1])

    def test_terminal_label_stays_a_valid_target_without_changing_retained_output(self):
        lower = Lowerer()
        target = lower.new_label()
        lower.jump(target, "%I0.0")
        lower.assign("%Q0.0", "%I0.1")
        lower.label(target)
        program = self.finish(lower)
        self.assertEqual(program.rungs[-1][0], target + ":")
        machine = Machine(program)
        self.assertEqual(
            [machine.step(v)[0] for v in ({1: 1}, {0: 1}, {}, {0: 1})], [1, 1, 0, 0]
        )

    def test_consecutive_labels_remain_distinct_valid_entry_points(self):
        lower = Lowerer()
        first, second = lower.new_label(), lower.new_label()
        lower.jump(first, "%I0.0")
        lower.jump(second)
        lower.label(first)
        lower.label(second)
        lower.assign("%Q0.0", "%I0.1")
        program = self.finish(lower)
        self.assertEqual(
            {r[0] for r in program.rungs if r[0].startswith("%L")},
            {first + ":", second + ":"},
        )
        machine = Machine(program)
        self.assertEqual(
            [machine.step(v)[0] for v in ({1: 1}, {0: 1}, {0: 1, 1: 1}, {})],
            [1, 0, 1, 0],
        )

    def test_an_anchor_whose_private_value_is_read_is_not_discarded(self):
        lower = Lowerer()
        label = lower.new_label()
        lower.label(label)
        lower.assign("%Q0.0", lower.label_scratch)
        machine = Machine(self.finish(lower))
        machine.memory = [True] * 1024
        self.assertFalse(machine.step({})[0])

    def test_indexed_program_keeps_private_copy_extent_and_label_anchors(self):
        lower = Lowerer(reserved_words={0, 1, 2})
        first = lower.word("i16")
        guard = lower.copy("%I0.0")
        lower.numeric_assign(first, first, guard)
        label = lower.new_label()
        lower.label(label)
        lower.numeric_assign(Number("i16", "%MW2"), Number("i16", "%MW1[%MW0]"))
        lower.assign("%Q0.0", "%S20")
        lower.rung("LD [%MW2=42]", "ST %Q0.1")
        program = self.finish(lower)
        self.assertTrue(self.self_copies(program))
        anchor = next(r for r in program.rungs if r[0] == label + ":")
        self.assertTrue(anchor[-1].startswith("ST %M"))
        machine = Machine(program)
        machine.words[0], machine.words[1], machine.words[3] = 2, 7, 42
        self.assertEqual(machine.step({})[:2], [0, 1])
        self.assertEqual(machine.words[2], 42)

    def test_malformed_anchor_load_is_not_hidden_by_cleanup(self):
        storage = Storage()
        scratch = storage.bit("scratch")
        program = Program([["%L0:", "LD ", "ST " + scratch], ["LD %I0.0", "ST %Q0.0"]])
        with self.assertRaisesRegex(CompileError, "operand|instruction|load|unknown"):
            validate(storage.finalize(program, {}))

    def test_native_memory_edge_history_survives_a_coalesced_anchor(self):
        # Native M edges sample the physical cell across scans. A different
        # virtual root can share that cell even when the scratch has no reads.
        for opcode in ("LDR", "LDF"):
            lower = Lowerer()
            value = lower.copy("%I0.0", "edge_source")
            lower.rung(opcode + " " + value, "ST %Q0.0")
            lower.label(lower.new_label())
            lower.assign("%Q0.1", "%I0.1")
            machine = Machine(self.finish(lower))
            self.assertEqual(
                [machine.step({0: bit})[0] for bit in (1, 1, 1, 0, 0)],
                [0, 0, 0, 0, 0],
                opcode,
            )


if __name__ == "__main__":
    unittest.main()
