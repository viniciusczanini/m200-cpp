import math
import random
import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import CompileError, Program
from m200.native import run_native
from m200.reverse import to_cpp
from m200.numeric import Number, compare, comparison, memory_words_used
from m200.scalar_numeric import Indeterminate


class NumericTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def compile(self, body):
        p = self.work / "numeric.cpp"
        p.write_text("#include <plc.hpp>\n" + body)
        return compile_source(p)

    def equivalent(self, body, frames):
        program = self.compile(body)
        validate(program)
        machine = Machine(program)
        got = [machine.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames]
        self.assertEqual(run_native(self.work / "numeric.cpp", frames), got)
        audit = self.work / "audit.cpp"
        audit.write_text(to_cpp(program))
        self.assertEqual(run_native(audit, frames), got)
        rebuilt = compile_source(audit)
        other = Machine(rebuilt)
        self.assertEqual(
            [other.step(f.get("inputs", {}), f.get("dt_ms", 10)) for f in frames], got
        )
        return machine, got

    def test_i16_state_arithmetic_and_comparison_roundtrip(self):
        _, got = self.equivalent(
            """plc::i16 count=0;
void scan(){
  count=plc::add_i16(count,1);
  if(count>=7){count=0;}
  plc::write_word(0,count);
  plc::output(0,plc::read_word(0)==3);
}""",
            [{}] * 20,
        )
        self.assertEqual([i for i, row in enumerate(got) if row[0]], [2, 9, 16])

    def test_shared_word_dword_float_aliases(self):
        machine, got = self.equivalent(
            """void scan(){
plc::write_dword(0,65538);
plc::output(0,plc::read_word(0)==2 && plc::read_word(1)==1);
plc::write_real(2,1.0f);
plc::output(1,plc::read_dword(2)==1065353216);
}""",
            [{}],
        )
        self.assertEqual(got[0][:2], [True, True])
        self.assertEqual(machine.words[:4], [2, 1, 0, 16256])

    def test_integer_boundaries_bit_logic_and_shifts(self):
        _, got = self.equivalent(
            """void scan(){
plc::i16 a=-32768;
plc::i16 b=plc::shr_i16(a,16);
plc::i16 c=plc::rol_i16(a,1);
plc::i32 d=plc::sub_i32(-2147483647,1);
plc::output(0,b==0 && c==1 && d==-2147483648);
plc::output(1,plc::xor_i16(plc::and_i16(-1,255),15)==240);
}""",
            [{}],
        )
        self.assertEqual(got[0][:2], [True, True])

    def test_float32_rounding_and_conversion_ties_even(self):
        _, got = self.equivalent(
            """void scan(){
plc::f32 a=plc::add_f32(16777216.0f,1.0f);
plc::i16 b=plc::real_to_int(10.5f);
plc::i32 c=plc::real_to_dint(-11.5f);
plc::f32 d=plc::sqrt_f32(4.0f);
plc::output(0,a==16777216.0f && b==10 && c==-12 && d==2.0f);
}""",
            [{}],
        )
        self.assertTrue(got[0][0])

    def test_sequential_guarded_writes_capture_values(self):
        rng = random.Random(0x200CE40)
        frames = [
            {"inputs": {0: bool(rng.randrange(2)), 1: bool(rng.randrange(2))}}
            for _ in range(300)
        ]
        self.equivalent(
            """plc::i32 n=0; void scan(){
if(plc::input(0)){n=plc::add_i32(n,3);}else{n=plc::sub_i32(n,2);}
if(plc::input(1)){plc::write_dword(10,n);}
plc::output(0,n<0);plc::output(1,plc::read_dword(10)==n);
}""",
            frames,
        )

    def test_numeric_type_bounds_and_promotions_are_rejected(self):
        for body in [
            "void scan(){plc::i16 a=32768;}",
            "void scan(){plc::i16 a=1; a=a+1;}",
            "void scan(){plc::i16 a=1;plc::i32 b=2;plc::i16 c=plc::add_i16(a,b);}",
            "void scan(){plc::i16 a=1;if(a){plc::output(0,true);}}",
            "void scan(){plc::write_dword(7999,0);}",
            "void scan(){plc::i16 a=plc::shl_i16(1,0);}",
            "void scan(){plc::i16 a=plc::shl_i16(1,17);}",
            "void scan(){plc::write_word(0,plc::read_real(1));}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)

    def test_il_numeric_unknown_or_mixed_operations_are_rejected(self):
        for operation in [
            "[%MW0:=%MF2+1]",
            "[%MW8000:=1]",
            "[%MD7999:=2]",
            "[%MW0:=DO_STUFF(%MW1)]",
        ]:
            with self.subTest(operation=operation), self.assertRaises(CompileError):
                validate(Program([["LD 1", operation]]))

    def test_integer_fault_values_remain_unknown_until_repaired(self):
        for initial, expression in [
            ("0", "plc::div_i16(2,a)"),
            ("-1", "plc::sqrt_i16(a)"),
        ]:
            with self.subTest(expression=expression):
                program = self.compile(
                    "void scan(){plc::i16 a=" + initial
                    + ";plc::i16 n=" + expression
                    + ";plc::write_word(0,n);plc::output(0,plc::system(18));}"
                )
                machine = Machine(program)
                self.assertTrue(machine.step()[0])
                self.assertTrue(machine.arithmetic.overflow)
                self.assertIsInstance(
                    machine.read_number(Number("i16", "%MW0")), Indeterminate
                )
                # Copy/storage may carry the unknown value. Observation is the
                # failure point; the destination must never become a valid zero.
                with self.assertRaisesRegex(CompileError, "indeterminate.*before recovery"):
                    compare(machine.words, comparison("[%MW0=0]"), machine.read_number)
                machine.write_number("%MW0", 23)
                machine.write("%S18", False)
                self.assertEqual(machine.read_number(Number("i16", "%MW0")), 23)
                self.assertIsNone(machine.indeterminate.read(0, 1))
                self.assertFalse(machine.arithmetic.overflow)

    def test_literal_faults_are_runtime_effects_with_distinct_result_contracts(self):
        for kind, expression in [
            ("i16", "plc::div_i16(1,0)"),
            ("f32", "plc::sqrt_f32(-1.0f)"),
            ("i16", "plc::real_to_int(32768.0f)"),
        ]:
            with self.subTest(expression=expression):
                writer = "real" if kind == "f32" else "word"
                # Admission is no longer an arithmetic evaluation. An invalid
                # typed literal itself (e.g. i16=32768) is still rejected above.
                program = self.compile(
                    "void scan(){plc::write_word(10,123);"
                    "plc::write_word(11,456);plc::write_" + writer
                    + "(10," + expression + ");plc::output(0,true);}"
                )
                machine = Machine(program)
                if expression.startswith("plc::real_to_int"):
                    # G03 is deferred: keep this real-to-integer domain refusal
                    # and its before-write atomicity, merely at runtime now.
                    with self.assertRaisesRegex(CompileError, "arithmetic"):
                        machine.step()
                    self.assertEqual(machine.words[10:12], [123, 456])
                    self.assertFalse(machine.outputs[0])
                    # G3289 p72 requires S18 even when this local conversion
                    # path still refuses execution. Keep the real source gap
                    # visible; do not turn the missing flag into a new oracle.
                    self.assertTrue(machine.arithmetic.overflow)
                else:
                    self.assertTrue(machine.step()[0])
                    self.assertTrue(machine.arithmetic.overflow)
                    result = machine.read_number(Number(kind, "%M" + ("F" if kind == "f32" else "W") + "10"))
                    if kind == "i16":
                        self.assertIsInstance(result, Indeterminate)
                        with self.assertRaisesRegex(CompileError, "indeterminate"):
                            compare(machine.words, comparison("[%MW10=0]"), machine.read_number)
                        self.assertEqual(machine.arithmetic.float_status, 0)
                    else:
                        self.assertTrue(math.isnan(result))
                        self.assertEqual(machine.arithmetic.float_status, 1)

    def test_inactive_branches_and_short_circuit_do_not_evaluate_arithmetic(self):
        self.equivalent(
            """void scan(){
plc::i16 zero=0;
if(plc::input(0)){plc::i16 n=plc::div_i16(1,zero);}
bool a=zero!=0 && plc::div_i16(1,zero)>0;
bool b=zero==0 || plc::div_i16(1,zero)>0;
plc::output(0,!a && b);
}""",
            [{}] * 3,
        )

    def test_report_counts_shared_words_and_cli_exposes_inventory(self):
        import json
        import subprocess
        import sys
        from m200.cli import report

        program = self.compile(
            "void scan(){plc::write_dword(0,1);plc::write_real(1,2.0f);}"
        )
        # The raw ranges overlap: MD0 uses 0/1; MF1 uses 1/2.
        self.assertEqual(report(program)["resources"]["memory_words"], 3)
        r = subprocess.run(
            [sys.executable, "-m", "m200", "capabilities"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["total"], 250)
        self.assertFalse(data["complete"])
        self.assertIn("add_i16", data["library"]["numeric_intrinsics"])

    def test_numeric_ladder_xml_and_reverse_preserve_actual_operations(self):
        import xml.etree.ElementTree as ET
        from m200.project import write_project, load_project

        program = self.compile("""plc::i16 n=0;void scan(){
n=plc::add_i16(n,1);plc::write_dword(20,65538);plc::write_real(30,1.5f);
plc::output(0,n>2);if(n>=5){n=0;}
}""")
        project = self.work / "numeric.smbp"
        write_project(
            program, Path(__file__).parent / "fixtures/synthetic.smbp", project
        )
        root = ET.parse(project).getroot()
        operations = [
            e
            for e in root.iter("LadderEntity")
            if e.findtext("ElementType") == "Operation"
        ]
        comparisons = [
            e
            for e in root.iter("LadderEntity")
            if e.findtext("ElementType") == "Comparison"
        ]
        self.assertTrue(operations)
        self.assertTrue(comparisons)
        allocation = root.find("SoftwareConfiguration/MemoryWordsMemoryAllocation")
        self.assertEqual(allocation.findtext("Allocation"), "Manual")
        required = max(memory_words_used(program), default=-1) + 1
        self.assertGreaterEqual(int(allocation.findtext("ForcedCount")), required)
        self.assertGreaterEqual(int(allocation.findtext("ForcedCount")), 32)
        self.assertTrue(
            all(
                e.findtext("Column") == "9"
                and e.find("OperationExpression") is not None
                for e in operations
            )
        )
        self.assertTrue(
            all(e.find("ComparisonExpression") is not None for e in comparisons)
        )
        loaded = load_project(project)
        self.assertEqual(loaded.rungs, program.rungs)
        original, actual = Machine(program), Machine(loaded)
        self.assertEqual(
            [original.step() for _ in range(20)], [actual.step() for _ in range(20)]
        )
        comparisons[0].find("ComparisonExpression").text = "%MW0=123"
        ET.ElementTree(root).write(project)
        with self.assertRaisesRegex(CompileError, "graphics.*agree"):
            load_project(project)
