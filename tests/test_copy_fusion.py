"""Copy elimination must preserve live aliases, evaluation order and CFG."""

import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.lower import Lowerer
from m200.native import run_native
from m200.numeric import literal
from m200.reverse import to_cpp
from m200.project import write_project, load_project


class CopyFusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        self.source = self.work / "source.cpp"
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def rows(self, p, frames):
        m = Machine(p)
        return [m.step(f.get("inputs", {})) for f in frames]

    def test_large_copy_chain_emits_a_small_observably_correct_program(self):
        body = (
            "void scan(){plc::i16 a0=1;"
            + "".join(f"plc::i16 a{i}=a{i - 1};" for i in range(1, 6001))
            + "plc::output(0,a6000==1);}"
        )
        p = self.compile(body)
        self.assertEqual(self.rows(p, [{}])[0][0], True)
        self.assertLess(sum(map(len, p.rungs)), 10000)
        self.assertEqual(run_native(self.source, [{}]), self.rows(p, [{}]))

    def test_numeric_value_with_future_uses_survives_copy_and_guarded_overwrite(self):
        p = self.compile("""void scan(){plc::i16 b=plc::add_i16(plc::read_word(0),1);
plc::i16 a=b;if(plc::input(0)){a=7;}plc::output(0,b==1);
plc::output(1,a==1);plc::output(2,a==7);plc::write_word(0,b);}""")
        frames = [{}, {"inputs": {0: True}}, {}]
        got = self.rows(p, frames)
        self.assertEqual([r[:3] for r in got], [[1, 1, 0], [0, 0, 1], [0, 0, 0]])
        self.assertEqual(run_native(self.source, frames), got)

    def test_boolean_redefinition_preserves_self_operands_and_old_value(self):
        p = self.compile("""void scan(){bool x=plc::input(0);bool old=x;x=x&&plc::input(1);
bool y=plc::input(0);y=y&&!y;plc::output(0,x);plc::output(1,old);plc::output(2,y);}""")
        frames = [{"inputs": {0: a, 1: b}} for a, b in [(0, 0), (1, 0), (1, 1), (0, 1)]]
        got = self.rows(p, frames)
        self.assertEqual(
            [r[:3] for r in got], [[0, 0, 0], [0, 1, 0], [1, 1, 0], [0, 0, 0]]
        )
        self.assertEqual(run_native(self.source, frames), got)

    def test_single_use_load_keeps_index_error_before_following_flag_read(self):
        lower = Lowerer({0}, {0})
        lower.rung("LD 1", "ST %M0")
        lower.rung("LD 1", "[%MW0:=-32768]")
        loaded = lower.copy("%M0[%MW0]")
        out = lower.binary("&&", loaded, "%S20")
        lower.assign("%Q0.0", out)
        self.assertTrue(self.rows(self.finalize(lower), [{}])[0][0])

    def test_values_live_around_loop_back_edges_are_not_forwarded_away(self):
        p = self.compile("""void scan(){bool b=plc::input(0);bool old=false;plc::i16 i=0;
while(i<3){old=b;b=!b;if(old){plc::output(0,!plc::output_state(0));}i=plc::add_i16(i,1);}
plc::output(1,b);plc::output(2,old);}""")
        frames = [{}, {"inputs": {0: True}}, {}]
        got = self.rows(p, frames)
        self.assertEqual([r[:3] for r in got], [[1, 1, 0], [1, 0, 1], [0, 1, 0]])
        self.assertEqual(run_native(self.source, frames), got)

    def test_jump_entry_does_not_move_a_copy_across_its_label(self):
        p = self.compile("""void scan(){bool b=false;bool saved=false;
if(plc::input(0)){goto Use;}b=plc::input(1);Use:saved=b;plc::output(0,saved);}""")
        frames = [{"inputs": {0: 1, 1: 1}}, {"inputs": {1: 1}}, {}]
        got = self.rows(p, frames)
        self.assertEqual([r[:1] for r in got], [[0], [1], [0]])
        self.assertEqual(run_native(self.source, frames), got)

    def test_comparison_forwarding_does_not_exceed_ladder_column_limit(self):
        lower = Lowerer()
        comparison = lower.copy("[%MW0=0]")
        out = lower.bit()
        lower.rung("LD " + comparison, *[f"AND %I0.{i}" for i in range(9)], "ST " + out)
        lower.assign("%Q0.0", out)
        p = self.finalize(lower)
        dest = self.work / "bounded.smbp"
        write_project(p, Path(__file__).parent / "fixtures/synthetic.smbp", dest)
        self.assertTrue(
            self.rows(load_project(dest), [{"inputs": {i: True for i in range(9)}}])[0][
                0
            ]
        )

    def finalize(self, lower):
        lower.program.rungs = lower.constant_rungs + lower.program.rungs
        p = lower.storage.finalize(lower.program, lower.constants)
        validate(p)
        return p

    def test_word_bit_alias_counts_as_a_future_use_of_dword(self):
        lower = Lowerer()
        value = lower.numeric("add_i32", [literal(65536, "i32"), literal(1, "i32")])
        view = lower.storage.word_bit(value, 16)
        target = lower.word("i32")
        lower.assign(target, value)
        lower.rung("LD " + view, "ST %Q0.0")
        self.assertTrue(self.rows(self.finalize(lower), [{}])[0][0])

    def test_not_snapshot_stays_before_indexed_contact_that_sets_s20(self):
        lower = Lowerer({0}, {0})
        lower.rung("LD 1", "ST %M0")
        lower.rung("LD 1", "[%MW0:=-32768]")
        old_error = lower.neg("%S20")
        out = lower.binary("&&", "%M0[%MW0]", old_error)
        lower.assign("%Q0.0", out)
        lower.rung("LD %S20", "ST %Q0.1")
        p = self.finalize(lower)
        got = self.rows(p, [{}])
        self.assertEqual(got[0][:2], [True, True])
        source = self.work / "reverse.cpp"
        source.write_text(to_cpp(p))
        self.assertEqual(run_native(source, [{}]), got)


if __name__ == "__main__":
    unittest.main()
