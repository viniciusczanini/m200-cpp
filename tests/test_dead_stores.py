"""Generic dead private stores preserve observable scan behavior and effects."""

from pathlib import Path
import tempfile
import unittest

from m200.frontend import compile_source
from m200.il import Machine
from m200.cli import report
from m200.model import CompileError, Program, SubroutineDefinition
from m200.ladder_lowering import normalize


class DeadPrivateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.cpp"

    def compile(self, source):
        self.source.write_text("#include <plc.hpp>\n" + source)
        return compile_source(self.source)

    def test_always_overwritten_outputs_drop_dead_initial_images(self):
        writes = "plc::output(0,plc::input(0));" + "".join(
            "plc::output(%d,false);" % i for i in range(1, 16)
        )
        program = self.compile("void scan(){" + writes + "}")
        snapshots = [r for r in program.rungs if r[0].startswith("LD %Q0.")]
        self.assertEqual(snapshots, [])
        machine = Machine(program)
        machine.outputs = [True] * 16
        machine.memory = [True] * 1024
        self.assertEqual(machine.step({0: False}), [False] * 16)
        self.assertEqual(machine.step({0: True}), [True] + [False] * 15)
        self.assertEqual(len(program.metadata["rung_origins"]), len(program.rungs))

    def warm(self, program):
        machine = Machine(program)
        machine.first = False
        machine.outputs = [True] * 16
        machine.memory = [True] * 1024
        return machine

    def test_early_return_preserves_prior_output_until_written(self):
        program = self.compile(
            "void scan(){if(plc::input(0))return;plc::output(0,false);plc::output(1,plc::output_state(0));}"
        )
        machine = self.warm(program)
        for control, expected in [
            (True, [True, True]),
            (False, [False, False]),
            (True, [False, False]),
        ]:
            self.assertEqual(machine.step({0: control})[:2], expected)

    def test_conditional_assignment_and_zero_iteration_loop_keep_old_image(self):
        cases = [
            "void scan(){if(plc::input(0))plc::output(0,false);plc::output(1,plc::output_state(0));}",
            "void scan(){plc::i16 i=0;while(i<plc::read_word(0)){plc::output(0,false);i=plc::add_i16(i,1);}plc::output(1,plc::output_state(0));}",
        ]
        for source in cases:
            machine = self.warm(self.compile(source))
            machine.words[0] = 0
            self.assertEqual(machine.step({0: False})[:2], [True, True])
            machine.words[0] = 1
            self.assertEqual(machine.step({0: True})[:2], [False, False])
            self.assertEqual(machine.step({0: False})[:2], [False, False])

    def test_packed_output_alias_is_read_before_overwrite(self):
        program = self.compile(
            "void scan(){plc::i16 old=plc::read_output_bits_i16(0,2);plc::output(0,false);plc::output(1,false);plc::write_word(10,old);}"
        )
        machine = self.warm(program)
        self.assertEqual(machine.step({})[:2], [False, False])
        self.assertEqual(machine.words[10], 3)
        machine.step({})
        self.assertEqual(machine.words[10], 0)

    def test_unused_index_and_arithmetic_values_retain_error_effects(self):
        for source, word, index in [
            (
                "plc::WordMemory memory{4};void scan(){plc::i16 ignored=plc::read_word_indexed(0,0);plc::output(0,plc::system(20));}",
                5,
                0,
            ),
            (
                "void scan(){plc::i16 ignored=plc::add_i16(plc::read_word(1),1);plc::output(0,plc::system(18));}",
                32767,
                1,
            ),
        ]:
            machine = Machine(self.compile(source))
            machine.words[index] = word
            self.assertTrue(machine.step({})[0])

    def test_discarded_timer_result_keeps_refresh_and_update(self):
        program = self.compile(
            "plc::Ton timer{0,1,10};void scan(){bool unused=timer.done();bool ignored=timer.update(plc::input(0));plc::output(0,timer.value()>=10);}"
        )
        self.assertTrue(
            any("%TM0.Q" in line for rung in program.rungs for line in rung)
        )
        self.assertTrue(any(rung[0] == "BLK %TM0" for rung in program.rungs))
        machine = Machine(program)
        self.assertFalse(machine.step({0: True}, 10)[0])
        self.assertTrue(machine.step({0: True}, 1)[0])

    def test_subroutine_side_effects_do_not_use_flat_dead_store_analysis(self):
        program = self.compile(
            'void leaf(){plc::output(0,false);}plc::Subroutine sr{0,leaf,"leaf",2};void scan(){sr.call(plc::input(0));plc::output(1,plc::output_state(0));}'
        )
        self.assertNotIn("dead_private_stores", program.metadata)
        machine = self.warm(program)
        self.assertEqual(machine.step({0: False})[:2], [True, True])
        self.assertEqual(machine.step({0: True})[:2], [False, False])

    def test_low_fit_preserves_explicit_words_complete_modbus_buffer_and_groups(self):
        program = self.compile("""plc::ReadVar remote{0,plc::Link::Serial1,1,100,plc::Object::HoldingWords,0,125,2};
plc::i32 state=7;bool flag=false;plc::i16 group[3]={1,2,3};
void scan(){plc::write_m(0,true);plc::write_dword(0,65538);remote.update(false,false);
state=plc::add_i32(state,1);flag=!flag;group[2]=plc::add_i16(group[0],group[1]);
plc::write_word(180,plc::low_word(state));plc::output(0,plc::read_m(0)&&flag&&group[2]==3&&plc::read_word(0)==2&&plc::read_word(1)==1);}""")
        self.assertEqual(report(program)["resources"]["required_word_allocation"], 181)
        machine = Machine(program)
        machine.memory = [True] * 1024
        machine.words = [0x2468] * 8000
        before = machine.words[2:127]
        self.assertTrue(machine.step({})[0])
        self.assertEqual(machine.words[180], 8)
        self.assertEqual(machine.words[:2], [2, 1])
        self.assertEqual(machine.words[2:127], before)
        self.assertFalse(machine.step({})[0])
        self.assertEqual(machine.words[180], 9)
        self.assertTrue(machine.memory[0])

    def test_low_fit_reserves_low_cells_used_only_in_callee_during_normalization(self):
        program = Program(
            rungs=[
                ["LD %I0.2", "ORN %I0.2", "[%MW10:=1]"],
                ["LD %I0.0", "SR0"],
                ["LD %I0.2", "ORN %I0.2", "ST %Q0.0"],
            ],
            subroutines={
                0: SubroutineDefinition(
                    0, "leaf", 2, [["LD 0", "ST %M0"], ["LD 1", "[%MW0:=22]"]]
                )
            },
        )
        machine = Machine(normalize(program))
        self.assertTrue(machine.step({0: True})[0])
        self.assertFalse(machine.memory[0])
        self.assertEqual(machine.words[0], 22)
        self.assertEqual(machine.words[10], 1)

    def test_low_fit_keeps_whole_memory_images_reserved_and_refuses_full_capacity(self):
        program = self.compile(
            "plc::WordMemory wm{128};plc::BitMemory bm{64};plc::i32 value=9;bool bit=false;void scan(){bit=!bit;value=plc::add_i32(value,1);plc::write_word(127,plc::low_word(value));plc::write_m(63,bit);plc::output(0,bit);}"
        )
        self.assertLessEqual(
            report(program)["resources"]["required_word_allocation"], 132
        )
        self.assertGreaterEqual(program.metadata["allocation"]["reserved_words"], 128)
        self.assertGreaterEqual(program.metadata["allocation"]["reserved_bits"], 64)
        machine = Machine(program)
        machine.memory = [True] * 1024
        machine.words = [0x1357] * 8000
        self.assertTrue(machine.step({})[0])
        self.assertEqual(machine.words[127], 10)
        self.assertEqual(machine.words[:127], [0x1357] * 127)
        self.assertEqual(machine.memory[:63], [True] * 63)
        for source in (
            "plc::WordMemory all{8000};plc::i16 value=1;void scan(){plc::output(0,value==1);}",
            "plc::BitMemory all{1024};bool value=false;void scan(){value=!value;plc::output(0,value);}",
        ):
            with self.assertRaises(CompileError):
                self.compile(source)


if __name__ == "__main__":
    unittest.main()
