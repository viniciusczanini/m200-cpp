import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError
from m200.model import Program
from m200.il import validate
from m200.native import run_native


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.cpp"

    def code(self, body):
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def test_unsigned_promotions_are_rejected_instead_of_changing_comparison(self):
        for typ in ["i16", "i32"]:
            with (
                self.subTest(typ=typ),
                self.assertRaisesRegex(CompileError, "unsigned"),
            ):
                self.code("void scan(){plc::" + typ + " a=-1;plc::output(0,a<1u);}")

    def test_float_truncation_preserves_negative_zero_bits(self):
        p = self.code(
            "void scan(){plc::write_real(0,plc::trunc_f32(-0.25f));plc::output(0,plc::read_dword(0)==-2147483648);}"
        )
        got = Machine(p).step()
        self.assertTrue(got[0])
        self.assertEqual(run_native(self.source, [{}]), [got])

    def test_short_circuit_does_not_read_nonfinite_real(self):
        p = self.code(
            "void scan(){plc::write_dword(0,2139095040);plc::output(0,plc::input(0)&&plc::read_real(0)>0.0f);}"
        )
        got = Machine(p).step()
        self.assertFalse(got[0])
        self.assertEqual(run_native(self.source, [{}]), [got])

    def test_repeated_literal_negation_is_numeric_not_text_concatenation(self):
        p = self.code("void scan(){plc::i16 a=- -1;plc::output(0,a==1);}")
        got = Machine(p).step()
        self.assertTrue(got[0])
        self.assertEqual(run_native(self.source, [{}]), [got])

    def test_invalid_metadata_is_rejected_before_serialization(self):
        for symbols, metadata in [
            ({"%M0": []}, {}),
            ({"%I0.0": "input"}, {}),
            ({}, {"rung_origins": [7]}),
        ]:
            with (
                self.subTest(symbols=symbols),
                self.assertRaisesRegex(CompileError, "metadata|symbol"),
            ):
                validate(
                    Program([["LD 1", "ST %Q0.0"]], symbols=symbols, metadata=metadata)
                )

    def test_active_nonfinite_read_uses_ieee_comparison_without_arithmetic_error(self):
        for raw, greater, equal_self in [
            (2139095040, True, True),       # +infinity
            (-8388608, False, True),       # -infinity
            (2143294004, False, False),    # quiet NaN, payload 0x1234
        ]:
            with self.subTest(raw=raw):
                p = self.code(
                    "void scan(){plc::write_dword(0," + str(raw) + ");"
                    "plc::output(0,plc::read_real(0)>0.0f);"
                    "plc::output(1,plc::read_real(0)==plc::read_real(0));"
                    "plc::output(2,!plc::system(18));"
                    "plc::output(3,plc::floating_status()==0);"
                    "plc::output(4,plc::read_dword(0)==" + str(raw) + ");}"
                )
                machine = Machine(p)
                expected = [greater, equal_self, True, True, True] + [False] * 11
                self.assertEqual(machine.step(), expected)
                self.assertFalse(machine.arithmetic.overflow)
                self.assertEqual(machine.arithmetic.float_status, 0)
                self.assertEqual(machine.words[0] | machine.words[1] << 16, raw & 0xFFFFFFFF)
                self.assertEqual(run_native(self.source, [{}]), [expected])

    def test_graph_whitespace_cannot_merge_numeric_tokens(self):
        import xml.etree.ElementTree as ET
        from m200.project import write_project, load_project

        p = self.code(
            "void scan(){plc::write_word(4000,1);plc::output(0,plc::read_word(4000)==1);}"
        )
        path = self.source.with_suffix(".smbp")
        fixture = Path(__file__).parent / "fixtures/synthetic.smbp"
        write_project(p, fixture, path)
        root = ET.parse(path).getroot()
        expr = root.find(".//OperationExpression")
        self.assertIn("%MW4000", expr.text)
        before = expr.text
        expr.text = expr.text.replace("%MW4000", "%MW40 00")
        self.assertNotEqual(expr.text, before)
        ET.ElementTree(root).write(path)
        with self.assertRaisesRegex(CompileError, "numeric|operation|mixed"):
            load_project(path)
