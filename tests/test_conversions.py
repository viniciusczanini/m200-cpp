"""Native conversions with decimal/byte oracles and complete artifact paths."""

import json
import random
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.arithmetic import ArithmeticState
from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.ladder_lowering import normalize
from m200.model import CompileError, Program
from m200.native import run_native
from m200.numeric import evaluate
from m200.project import load_project, write_project
from m200.reverse import to_cpp

ROOT = Path(__file__).resolve().parents[1]


def signed(raw, width):
    return int.from_bytes(raw.to_bytes(width // 8, "little"), "little", signed=True)


class ConversionTests(unittest.TestCase):
    def compile(self, source):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.cpp"
            path.write_text("#include <plc.hpp>\n" + source)
            return compile_source(path)

    def equivalent(self, program, expected, frames=None, source=None, template=None):
        frames = frames or [{}] * len(expected)
        expected = [row + [False] * (16 - len(row)) for row in expected]

        def check(p):
            machine = Machine(p)
            self.assertEqual(
                [machine.step(f.get("inputs", {})) for f in frames], expected
            )

        check(program)
        check(Program.from_dict(json.loads(json.dumps(program.as_dict()))))
        check(normalize(program))
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            template = template or ROOT / "tests/fixtures/synthetic.smbp"
            cpp = folder / "source.cpp"
            if source:
                cpp.write_text("#include <plc.hpp>\n" + source)
                self.assertEqual(run_native(cpp, frames), expected)
            cpp.write_text(to_cpp(program))
            self.assertEqual(run_native(cpp, frames), expected)
            rebuilt = compile_source(cpp)
            check(rebuilt)
            dest = folder / "conversions.smbp"
            for candidate in (program, rebuilt):
                write_project(candidate, template, dest)
                check(load_project(dest))
            cpp.write_text(to_cpp(load_project(dest)))
            self.assertEqual(run_native(cpp, frames), expected)
            write_project(compile_source(cpp), template, dest)
            check(load_project(dest))

    def test_manual_examples_and_negative_bcd_carriers_preserve_flags(self):
        for name, kind, a, expected in [
            ("bcd_to_int", "i16", 0x2450, 2450),
            ("int_to_bcd", "i16", 2450, 0x2450),
            ("bcd_to_int", "i16", -26215, 9999),
            ("int_to_bcd", "i16", 9999, -26215),
            ("bcd_to_dint", "i32", -1717986919, 99999999),
            ("dint_to_bcd", "i32", 99999999, -1717986919),
        ]:
            for old_error in (False, True):
                with self.subTest(name=name, old_error=old_error):
                    state = ArithmeticState()
                    state.carry, state.overflow = True, old_error
                    self.assertEqual(evaluate(name, [a], kind, flags=state), expected)
                    self.assertTrue(state.carry)
                    self.assertEqual(state.overflow, old_error)

    def test_all_65536_word_bti_carriers_with_independent_decimal_oracle(self):
        accepted = 0
        for raw in range(65536):
            digits = f"{raw:04x}"
            state = ArithmeticState()
            state.carry = True
            if any(c in "abcdef" for c in digits):
                with self.assertRaisesRegex(CompileError, "BCD"):
                    evaluate("bcd_to_int", [signed(raw, 16)], "i16", flags=state)
                self.assertTrue(state.overflow)
            else:
                self.assertEqual(
                    evaluate("bcd_to_int", [signed(raw, 16)], "i16", flags=state),
                    int(digits),
                )
                self.assertFalse(state.overflow)
                accepted += 1
            self.assertTrue(state.carry)
        self.assertEqual(accepted, 10000)

    def test_all_10000_word_itb_values_without_sign_bit_overflow(self):
        for value in range(10000):
            state = ArithmeticState()
            state.overflow = bool(value % 2)
            expected = signed(int(f"{value:04d}", 16), 16)
            self.assertEqual(
                evaluate("int_to_bcd", [value], "i16", flags=state), expected
            )
            self.assertEqual(state.overflow, bool(value % 2))

    def test_all_word_widening_values_follow_explicit_signed_local_policy(self):
        for raw in range(65536):
            value = signed(raw, 16)
            state = ArithmeticState()
            state.carry, state.overflow = bool(raw & 1), bool(raw & 2)
            self.assertEqual(
                evaluate("int_to_dint", [value], "i32", flags=state), value
            )
            self.assertEqual(
                (state.carry, state.overflow), (bool(raw & 1), bool(raw & 2))
            )

    def test_concat_all_byte_positions_and_seeded_pairs(self):
        rng = random.Random(20261106)
        pairs = [(0, 0), (-1, 0), (0, -1), (-1, -1), (-20536, 0)]
        pairs += [
            (signed(1 << b, 16), signed(1 << c, 16))
            for b in range(16)
            for c in range(16)
        ]
        pairs += [
            (rng.randint(-32768, 32767), rng.randint(-32768, 32767)) for _ in range(256)
        ]
        for low, high in pairs:
            state = ArithmeticState()
            state.carry = state.overflow = True
            expected = int.from_bytes(
                (low % 65536).to_bytes(2, "little")
                + (high % 65536).to_bytes(2, "little"),
                "little",
                signed=True,
            )
            self.assertEqual(
                evaluate("concat_words", [low, high], "i32", flags=state), expected
            )
            self.assertTrue(state.carry and state.overflow)

    def test_eight_digit_boundaries_and_seeded_roundtrips(self):
        rng = random.Random(20261107)
        values = [0, 1, 9, 10, 9999, 10000, 79999999, 80000000, 99999999]
        values += [rng.randrange(100000000) for _ in range(1024)]
        for value in values:
            state = ArithmeticState()
            encoded = evaluate("dint_to_bcd", [value], "i32", flags=state)
            self.assertEqual(encoded, signed(int(f"{value:08d}", 16), 32))
            self.assertEqual(
                evaluate("bcd_to_dint", [encoded], "i32", flags=state), value
            )
            self.assertFalse(state.overflow)

    def test_each_invalid_nibble_and_binary_domain_sets_error(self):
        for kind, width, name in [
            ("i16", 16, "bcd_to_int"),
            ("i32", 32, "bcd_to_dint"),
        ]:
            for position in range(width // 4):
                for digit in range(10, 16):
                    state = ArithmeticState()
                    with self.assertRaisesRegex(CompileError, "BCD"):
                        evaluate(
                            name,
                            [signed(digit << (4 * position), width)],
                            kind,
                            flags=state,
                        )
                    self.assertTrue(state.overflow)
        for name, kind, values in [
            ("int_to_bcd", "i16", [-32768, -1, 10000, 32767]),
            ("dint_to_bcd", "i32", [-2147483648, -1, 100000000, 2147483647]),
        ]:
            for value in values:
                state = ArithmeticState()
                with self.assertRaisesRegex(CompileError, "BCD"):
                    evaluate(name, [value], kind, flags=state)
                self.assertTrue(state.overflow)

    def test_unknown_bcd_result_fails_before_destination_write(self):
        for bank, expression, initial in [
            ("MW", "BTI(%MW0)", 10),
            ("MW", "ITB(%MW0)", -1),
            ("MD", "BTI(%MD0)", 10),
            ("MD", "ITB(%MD0)", 100000000),
        ]:
            p = Program(
                [
                    [
                        "LD 1",
                        f"[%{bank}0:={initial}]",
                        f"[%{bank}4:=123]",
                        f"[%{bank}4:={expression}]",
                    ]
                ]
            )
            vm = Machine(p)
            vm.arithmetic.carry = True
            with self.assertRaisesRegex(CompileError, "BCD"):
                vm.step()
            self.assertTrue(vm.arithmetic.overflow and vm.arithmetic.carry)
            self.assertEqual(vm.words[4], 123)

    def test_all_six_cpp_intrinsics_and_literal_snapshots_export(self):
        body = """void scan(){
plc::i16 a=plc::bcd_to_int(-26215);plc::i16 b=plc::int_to_bcd(9999);
plc::i32 c=plc::bcd_to_dint(-1717986919);plc::i32 d=plc::dint_to_bcd(99999999);
plc::i32 e=plc::concat_words(-20536,0);plc::i32 f=plc::int_to_dint(-32768);
plc::output(0,a==9999);plc::output(1,b==-26215);plc::output(2,c==99999999);
plc::output(3,d==-1717986919);plc::output(4,e==45000);plc::output(5,f==-32768);
plc::output(6,!plc::system(18));plc::output(7,!plc::system(17));}
"""
        self.equivalent(self.compile(body), [[True] * 8] * 3, source=body)

    def test_overlapping_native_concat_and_immediates_export(self):
        p = Program(
            [
                ["LD 1", "[%MW2:=-32768]", "[%MW3:=-1]", "[%MD2:=CONCATW(%MW2,%MW3)]"],
                ["LD [%MD2=-32768]", "ST %Q0.0"],
                ["LD 1", "[%MD10:=CONCATW(-1,0)]"],
                ["LD [%MD10=65535]", "ST %Q0.1"],
                ["LD 1", "[%MD12:=CONCATW(0,-32768)]"],
                ["LD [%MD12=-2147483648]", "ST %Q0.2"],
                ["LD 1", "[%MW2:=1]", "[%MW3:=2]", "[%MD2:=CONCATW(%MW3,%MW2)]"],
                ["LD [%MD2=65538]", "ST %Q0.3"],
            ]
        )
        self.equivalent(p, [[True, True, True, True]] * 3)

    def test_guards_loops_and_sticky_flags_across_valid_conversions(self):
        body = """plc::i16 n=0;void scan(){
if(plc::input(0)){plc::clear_arithmetic_error();}
if(plc::input(1)){plc::i16 seed=plc::add_i16(32767,1);}
plc::i16 bad=10;bool skipped=false;
if(plc::input(2)){skipped=plc::bcd_to_int(bad)==0;}
bool ok=plc::input(2)&&plc::bcd_to_int(bad)==0;
plc::i16 i=0;while(i<3){n=plc::bcd_to_int(plc::int_to_bcd(n));n=plc::add_i16(n,1);i=plc::add_i16(i,1);}
plc::output(0,!skipped&&!ok);plc::output(1,plc::system(18));plc::output(2,n==3);}
"""
        frames = [{"inputs": {1: True}}, {}, {"inputs": {0: True}}, {}]
        self.equivalent(
            self.compile(body),
            [
                [True, True, True],
                [True, True, False],
                [True, False, False],
                [True, False, False],
            ],
            frames,
            body,
        )

    def test_literal_bcd_faults_remain_runtime_refusals_before_destination_write(self):
        # Removing compile-time arithmetic evaluation does not complete the
        # deferred G03 recovery domain. Preserve the genuine runtime negative.
        for writer, expression in [
            ("word", "plc::bcd_to_int(10)"),
            ("word", "plc::int_to_bcd(-1)"),
            ("dword", "plc::dint_to_bcd(100000000)"),
            ("dword", "plc::bcd_to_dint(10)"),
        ]:
            with self.subTest(expression=expression):
                vm = Machine(self.compile(
                    "void scan(){plc::write_word(100,123);"
                    "plc::write_word(101,456);plc::write_" + writer
                    + "(100," + expression + ");plc::output(0,true);}"
                ))
                vm.arithmetic.carry = True
                with self.assertRaisesRegex(CompileError, "BCD"):
                    vm.step()
                self.assertTrue(vm.arithmetic.overflow and vm.arithmetic.carry)
                self.assertEqual(vm.words[100:102], [123, 456])
                self.assertIsNone(vm.indeterminate.read(100, 2))
                self.assertFalse(vm.outputs[0])

    def test_invalid_types_arity_literals_and_unknown_operators_fail(self):
        for expression in [
            "plc::int_to_dint(plc::read_dword(0))",
            "plc::concat_words(plc::read_dword(0),1)",
            "plc::concat_words(1)",
        ]:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                self.compile("void scan(){plc::output(0," + expression + "==0);}")
        for line in [
            "[%MD0:=CONCATW(%MD2,0)]",
            "[%MW0:=CONCATW(%MW2,0)]",
            "[%MW0:=BTI(%MD2)]",
            "[%MD0:=DWORD(1)]",
            "[%MD0:=CONCATW(%MW2,0,0)]",
            "[%MW0:=BCD_UNKNOWN(%MW1)]",
        ]:
            with self.subTest(line=line), self.assertRaises(CompileError):
                validate(Program([["LD 1", line]]))

    def test_global_helpers_with_intrinsic_names_keep_namespace(self):
        names = [
            "bcd_to_int",
            "bcd_to_dint",
            "int_to_bcd",
            "dint_to_bcd",
            "concat_words",
            "int_to_dint",
            "add_i16",
        ]
        body = "".join(f"bool {name}(bool a){{return !a;}}" for name in names)
        body += "void scan(){" + "".join(
            f"plc::output({i},{name}(plc::input(0)));" for i, name in enumerate(names)
        )
        body += "plc::output(7,plc::concat_words(-20536,0)==45000);plc::output(8,plc::int_to_bcd(9999)==-26215);plc::output(9,plc::int_to_dint(-32768)==-32768);}"
        self.equivalent(
            self.compile(body),
            [[True] * 10, [False] * 7 + [True] * 3],
            [{}, {"inputs": {0: True}}],
            body,
        )

    def test_native_word_conversions_reject_unsupported_property_and_string_sources(
        self,
    ):
        from m200.model import Timer
        from m200.counters import Counter

        for expression in [
            "CONCATW(%C0.P,%TM0.V)",
            "DWORD(%TM0.V)",
            "CONCATW(%I0.0:16,0)",
            "DWORD(%I0.0:16)",
        ]:
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                validate(
                    Program(
                        [["LD 1", f"[%MD4:={expression}]"]],
                        timers={0: Timer("TON", 1000, 100)},
                        counters={0: Counter(12)},
                    )
                )

    def test_cpp_communication_word_conversion_materializes_supported_sources(self):
        from m200.numeric import instruction_operation

        body = """plc::ReadVar remote{plc::Link::Serial1,1,10,plc::Object::HoldingWords,0,1,0};
void scan(){remote.update(false,false);plc::output(0,plc::int_to_dint(remote.comm_error())==0);
plc::output(1,plc::concat_words(remote.comm_error(),0)==0);}
"""
        p = self.compile(body)
        for rung in p.rungs:
            for line in rung:
                if ":=DWORD(" in line or ":=CONCATW(" in line:
                    _, _, operands = instruction_operation(line)
                    self.assertTrue(
                        all(
                            v.code.startswith("%MW") or not v.code.startswith("%")
                            for v in operands
                        )
                    )
        with tempfile.TemporaryDirectory() as folder:
            tree = ET.parse(ROOT / "tests/fixtures/synthetic.smbp")
            serial = ET.SubElement(
                tree.getroot().find("HardwareConfiguration/Plc"),
                "SerialLineConfiguration",
            )
            for key, value in [
                ("Baud", "Baud19200"),
                ("Parity", "ParityEven"),
                ("DataBits", "DataBits8"),
                ("StopBits", "StopBits1"),
                ("ResponseTime", "5"),
                ("TimeBetweenFrames", "10"),
                ("PhysicalMedium", "PhysicalMediumRs485"),
                ("TransmissionMode", "TransmissionModeModbusRtu"),
                ("Addressing", "MasterAddressing"),
            ]:
                ET.SubElement(serial, key).text = value
            template = Path(folder) / "template.smbp"
            tree.write(template)
            self.equivalent(p, [[True, True]] * 3, source=body, template=template)

    def test_bcd_native_block_properties_remain_supported(self):
        from m200.model import Timer
        from m200.counters import Counter

        p = Program(
            [
                ["LD 1", "[%MW4:=BTI(%C0.P)]", "[%MW5:=ITB(%TM0.V)]"],
                ["LD [%MW4=12]", "ST %Q0.0"],
                ["LD [%MW5=0]", "ST %Q0.1"],
            ],
            timers={0: Timer("TON", 1000, 100)},
            counters={0: Counter(18)},
        )
        self.equivalent(p, [[True, True]] * 3)


if __name__ == "__main__":
    unittest.main()
