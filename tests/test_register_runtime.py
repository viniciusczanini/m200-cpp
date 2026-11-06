"""Literal local Register policy checks; these are not PLC certification.

The observed native FIFO/LIFO traces support ordinary order, capacity, held
requests and sentinel retention. Reset/collision history was observed for FIFO
only. First-call and repeated-call behavior below is an explicit local policy;
skipped-call, lifecycle and broader native collision cases remain unqualified.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from m200.model import CompileError


class RegisterContractTests(unittest.TestCase):
    def registers(self):
        self.assertIsNotNone(
            importlib.util.find_spec("m200.registers"), "Register runtime is missing"
        )
        from m200 import registers

        return registers

    def test_config_defaults_to_exact_fifo_and_rejects_other_modes(self):
        registers = self.registers()
        self.assertEqual(registers.RegisterConfig().mode, "Fifo")
        self.assertEqual(registers.RegisterConfig("Lifo").mode, "Lifo")
        for mode in ["FIFO", "fifo", "LIFO", "", None, 1, True]:
            with self.subTest(mode=mode), self.assertRaises(CompileError):
                registers.RegisterConfig(mode)

    def test_index_is_canonical_and_bounded_to_one_four_slot_pool(self):
        registers = self.registers()
        self.assertEqual(registers.index("%R0"), 0)
        self.assertEqual(registers.index("%R3"), 3)
        for address in ["%R4", "%R00", "%R03", "%R-1", "%R+1", "%R0.I", "%r0"]:
            with self.subTest(address=address), self.assertRaises(CompileError):
                registers.index(address)

    def test_only_data_words_are_writable_and_numeric(self):
        registers = self.registers()
        for field in "IOEF":
            self.assertEqual(registers.reference("%R3." + field), (3, field))
        for field in "IO":
            self.assertEqual(registers.reference("%R0." + field, True), (0, field))
            self.assertIsNotNone(
                re.fullmatch(registers.NUMERIC_PATTERN, "%R0." + field)
            )
        for field in "EF":
            with self.assertRaises(CompileError):
                registers.reference("%R0." + field, True)
            self.assertIsNone(re.fullmatch(registers.NUMERIC_PATTERN, "%R0." + field))

    def test_reference_rejects_register_typos_without_claiming_r_prefixed_families(
        self,
    ):
        registers = self.registers()
        for address in [
            "%R4.I",
            "%R00.I",
            "%R03.O",
            "%R-1.I",
            "%R+1.I",
            "%R0",
            "%R0.P",
            "%R0.D",
            "%R0.I.extra",
            "%R0.i",
            "%R0. I",
            "%R",
        ]:
            with self.subTest(address=address), self.assertRaises(CompileError):
                registers.reference(address)
        for address in [
            "%READ_VAR0.D",
            "%READ_VAR0",
            "%RTC0",
            "%RTC0.Q",
            "%MW0",
            "%TM0.Q",
        ]:
            with self.subTest(address=address):
                self.assertIsNone(registers.reference(address))


class RegisterPolicyCases:
    """The expected snapshots are literal I/O/E/F observations, never a queue oracle."""

    def test_signed_order_and_changing_input_during_held_store(self):
        for mode, first, second in [("Fifo", -32768, 32767), ("Lifo", 32767, -32768)]:
            with self.subTest(mode=mode):
                self.check_trace(
                    mode,
                    [
                        ("I", -32768, (-32768, 0, True, False)),
                        ("U", (False, True, False), (-32768, 0, False, False)),
                        ("I", 32767, (32767, 0, False, False)),
                        ("U", (False, True, False), (32767, 0, False, False)),
                        ("U", (False, False, False), (32767, 0, False, False)),
                        ("U", (False, True, False), (32767, 0, False, False)),
                        ("U", (False, False, False), (32767, 0, False, False)),
                        ("U", (False, False, True), (32767, first, False, False)),
                        ("U", (False, False, False), (32767, first, False, False)),
                        ("U", (False, False, True), (32767, second, True, False)),
                        ("U", (False, False, True), (32767, second, True, False)),
                    ],
                )

    def test_output_sentinel_write_changes_no_queued_value_and_empty_pop_retains_it(
        self,
    ):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                self.check_trace(
                    mode,
                    [
                        ("O", 42, (0, 42, True, False)),
                        ("U", (False, False, True), (0, 42, True, False)),
                        ("U", (False, False, False), (0, 42, True, False)),
                        ("I", -123, (-123, 42, True, False)),
                        ("U", (False, True, False), (-123, 42, False, False)),
                        ("O", 32767, (-123, 32767, False, False)),
                        ("U", (False, False, True), (-123, -123, True, False)),
                        ("O", -32768, (-123, -32768, True, False)),
                        ("U", (False, False, False), (-123, -32768, True, False)),
                        ("U", (False, False, True), (-123, -32768, True, False)),
                    ],
                )

    def test_simultaneous_new_requests_are_noop_and_both_edges_are_consumed(self):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                self.check_trace(
                    mode,
                    [
                        ("I", 11, (11, 0, True, False)),
                        ("U", (False, True, False), (11, 0, False, False)),
                        ("U", (False, False, False), (11, 0, False, False)),
                        ("O", 42, (11, 42, False, False)),
                        ("I", 22, (22, 42, False, False)),
                        ("U", (False, True, True), (22, 42, False, False)),
                        ("U", (False, True, True), (22, 42, False, False)),
                        ("U", (False, True, False), (22, 42, False, False)),
                        ("U", (False, True, True), (22, 11, True, False)),
                        ("U", (False, False, True), (22, 11, True, False)),
                        ("U", (False, True, True), (22, 11, False, False)),
                        ("U", (False, False, False), (22, 11, False, False)),
                        ("U", (False, False, True), (22, 22, True, False)),
                    ],
                )

    def test_unsuccessful_empty_request_is_consumed_until_a_fresh_retrieve(self):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                self.check_trace(
                    mode,
                    [
                        ("O", 42, (0, 42, True, False)),
                        ("U", (False, False, True), (0, 42, True, False)),
                        ("I", 22, (22, 42, True, False)),
                        ("U", (False, True, True), (22, 42, False, False)),
                        ("U", (False, False, True), (22, 42, False, False)),
                        ("U", (False, False, True), (22, 42, False, False)),
                        ("U", (False, False, False), (22, 42, False, False)),
                        ("U", (False, False, True), (22, 22, True, False)),
                    ],
                )

    def test_capacity_is_exactly_sixteen_and_seventeenth_store_is_discarded(self):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                steps = [("I", 22, (22, 0, True, False))]
                for _ in range(15):
                    steps += [
                        ("U", (False, True, False), (22, 0, False, False)),
                        ("U", (False, False, False), (22, 0, False, False)),
                    ]
                steps += [
                    ("U", (False, True, False), (22, 0, False, True)),
                    ("U", (False, False, False), (22, 0, False, True)),
                    ("I", 11, (11, 0, False, True)),
                    ("U", (False, True, False), (11, 0, False, True)),
                    ("U", (False, False, False), (11, 0, False, True)),
                    ("U", (False, True, True), (11, 0, False, True)),
                    ("U", (False, False, False), (11, 0, False, True)),
                ]
                for _ in range(15):
                    steps += [
                        ("U", (False, False, True), (11, 22, False, False)),
                        ("U", (False, False, False), (11, 22, False, False)),
                    ]
                steps += [
                    ("U", (False, False, True), (11, 22, True, False)),
                    ("U", (False, False, False), (11, 22, True, False)),
                    ("U", (False, False, True), (11, 22, True, False)),
                ]
                self.check_trace(mode, steps)

    def test_unsuccessful_full_store_is_consumed_when_retrieval_frees_space(self):
        for mode, later in [("Fifo", 22), ("Lifo", 11)]:
            with self.subTest(mode=mode):
                steps = [("I", 22, (22, 0, True, False))]
                for _ in range(15):
                    steps += [
                        ("U", (False, True, False), (22, 0, False, False)),
                        ("U", (False, False, False), (22, 0, False, False)),
                    ]
                steps += [
                    ("U", (False, True, False), (22, 0, False, True)),
                    ("U", (False, False, False), (22, 0, False, True)),
                    ("I", 11, (11, 0, False, True)),
                    ("U", (False, True, False), (11, 0, False, True)),
                    ("U", (False, True, True), (11, 22, False, False)),
                    ("U", (False, True, False), (11, 22, False, False)),
                    ("U", (False, True, False), (11, 22, False, False)),
                    ("U", (False, False, False), (11, 22, False, False)),
                    ("U", (False, True, False), (11, 22, False, True)),
                    ("U", (False, False, True), (11, later, False, False)),
                ]
                self.check_trace(mode, steps)

    def test_reset_clears_words_queue_flags_and_wins_against_new_requests(self):
        # FIFO collision snapshots are native-observed. Applying the same reset
        # policy to LIFO and other preparations remains local pending proof.
        for mode in ["Fifo", "Lifo"]:
            for pins in [(True, True, False), (True, False, True), (True, True, True)]:
                with self.subTest(mode=mode, pins=pins):
                    self.check_trace(
                        mode,
                        [
                            ("I", 11, (11, 0, True, False)),
                            ("U", (False, True, False), (11, 0, False, False)),
                            ("U", (False, False, False), (11, 0, False, False)),
                            ("O", 42, (11, 42, False, False)),
                            ("U", pins, (0, 0, True, False)),
                            ("I", 22, (22, 0, True, False)),
                            ("O", 42, (22, 42, True, False)),
                            ("U", pins, (0, 0, True, False)),
                            ("U", (False, False, False), (0, 0, True, False)),
                            ("U", (False, False, True), (0, 0, True, False)),
                        ],
                    )

    def test_full_reset_drops_old_values_and_held_store_can_enqueue_after_reset(self):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                steps = [("I", 22, (22, 0, True, False))]
                for _ in range(15):
                    steps += [
                        ("U", (False, True, False), (22, 0, False, False)),
                        ("U", (False, False, False), (22, 0, False, False)),
                    ]
                steps += [
                    ("U", (False, True, False), (22, 0, False, True)),
                    ("O", 42, (22, 42, False, True)),
                    ("U", (True, True, False), (0, 0, True, False)),
                    ("U", (True, True, False), (0, 0, True, False)),
                    ("I", 11, (11, 0, True, False)),
                    ("U", (False, True, False), (11, 0, False, False)),
                    ("U", (False, True, False), (11, 0, False, False)),
                    ("U", (False, False, False), (11, 0, False, False)),
                    ("U", (False, False, True), (11, 11, True, False)),
                    ("U", (False, False, False), (11, 11, True, False)),
                    ("U", (False, False, True), (11, 11, True, False)),
                ]
                self.check_trace(mode, steps)

    def test_reset_retrieve_history_does_not_leave_an_empty_request_pending(self):
        for mode in ["Fifo", "Lifo"]:
            with self.subTest(mode=mode):
                self.check_trace(
                    mode,
                    [
                        ("U", (True, False, True), (0, 0, True, False)),
                        ("U", (False, False, True), (0, 0, True, False)),
                        ("I", 22, (22, 0, True, False)),
                        ("U", (False, True, True), (22, 0, False, False)),
                        ("U", (False, False, True), (22, 0, False, False)),
                        ("U", (False, False, False), (22, 0, False, False)),
                        ("U", (False, False, True), (22, 22, True, False)),
                    ],
                )


class RegisterStateTests(RegisterPolicyCases, unittest.TestCase):
    def state(self, mode="Fifo"):
        from m200 import registers

        self.assertTrue(hasattr(registers, "RegisterState"), "RegisterState is missing")
        return registers.RegisterState(registers.RegisterConfig(mode))

    def check_trace(self, mode, steps):
        state = self.state(mode)
        self.assertEqual(tuple(state.read(f) for f in "IOEF"), (0, 0, True, False))
        for field in "EF":
            self.assertIs(type(state.read(field)), bool)
        for number, (op, value, want) in enumerate(steps):
            if op == "U":
                self.assertIsNone(state.update(*value))
            else:
                state.write(op, value)
            with self.subTest(step=number, action=(op, value)):
                self.assertEqual(tuple(state.read(f) for f in "IOEF"), want)
                for field in "EF":
                    self.assertIs(type(state.read(field)), bool)

    def test_data_word_type_and_status_write_failures_preserve_state(self):
        state = self.state()
        state.write("I", -7)
        state.write("O", 42)
        for field, value in [
            ("I", -32769),
            ("I", 32768),
            ("I", True),
            ("I", 1.5),
            ("I", "11"),
            ("O", -32769),
            ("O", 32768),
            ("O", False),
            ("O", None),
            ("E", False),
            ("F", True),
            ("P", 1),
        ]:
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(CompileError),
            ):
                state.write(field, value)
            self.assertEqual(
                tuple(state.read(f) for f in "IOEF"), (-7, 42, True, False)
            )
        with self.assertRaises(CompileError):
            state.read("D")

    def test_local_first_call_repeated_calls_and_precall_self_status(self):
        # This is the ordinary per-call policy, not a claim about native skipped
        # calls, repeated calls, INIT, warm restart or STOP retention.
        state = self.state()
        state.write("I", 11)
        state.write("O", 42)
        state.update(False, True, not state.read("E"))
        self.assertEqual(tuple(state.read(f) for f in "IOEF"), (11, 42, False, False))
        state.update(False, True, not state.read("E"))
        self.assertEqual(tuple(state.read(f) for f in "IOEF"), (11, 11, True, False))
        state.update(False, True, not state.read("E"))
        self.assertEqual(tuple(state.read(f) for f in "IOEF"), (11, 11, True, False))


class RegisterSDKTests(RegisterPolicyCases, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
        if not cls.compiler:
            raise AssertionError("clang++ is required for local Register SDK checks")
        cls.work = tempfile.TemporaryDirectory(prefix="m200-register-sdk-")
        cls.addClassCleanup(cls.work.cleanup)
        cls.directory = Path(cls.work.name)
        cls.sdk = Path(__file__).resolve().parents[1] / "sdk"
        cls.binary = cls.directory / "register-runtime"
        source = cls.directory / "runtime.cpp"
        source.write_text(r"""#define PLC_NATIVE
#include <plc.hpp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <type_traits>
template<class R> void show(const R& r){
  std::printf("%d %d %d %d\n",(int)r.input(),(int)r.output(),r.empty(),r.full());
}
template<class R> int run(){
  R r{3};
  static_assert(std::is_same<decltype(r.input()),plc::i16>::value);
  static_assert(std::is_same<decltype(r.output()),plc::i16>::value);
  static_assert(std::is_same<decltype(r.empty()),bool>::value);
  static_assert(std::is_same<decltype(r.full()),bool>::value);
  static_assert(std::is_same<decltype(r.update(false,false,false)),void>::value);
  for(int n=0;n<8000;++n)plc::write_word(n,(plc::i16)(n-4000));
  show(r);
  char op; int value, reset, store, retrieve;
  while(std::scanf(" %c",&op)==1){
    if(op=='U'){
      if(std::scanf("%d%d%d",&reset,&store,&retrieve)!=3)return 2;
      r.update(reset!=0,store!=0,retrieve!=0);
    }else{
      if(std::scanf("%d",&value)!=1)return 3;
      if(op=='I')r.set_input((plc::i16)value);
      else if(op=='O')r.set_output((plc::i16)value);
      else return 4;
    }
    for(int n=0;n<8000;++n)if(plc::read_word(n)!=n-4000)return 5;
    show(r);
  }
  return 0;
}
int main(int argc,char** argv){
  if(argc<2)return 6;
  if(!std::strcmp(argv[1],"Fifo"))return run<plc::Fifo>();
  if(!std::strcmp(argv[1],"Lifo"))return run<plc::Lifo>();
  if(!std::strcmp(argv[1],"duplicate-fifo")){plc::Fifo a{0};plc::Fifo b{0};}
  else if(!std::strcmp(argv[1],"duplicate-lifo")){plc::Lifo a{0};plc::Lifo b{0};}
  else if(!std::strcmp(argv[1],"duplicate-cross")){plc::Fifo a{0};plc::Lifo b{0};}
  else if(!std::strcmp(argv[1],"duplicate-cross-reverse")){plc::Lifo a{0};plc::Fifo b{0};}
  else if(!std::strcmp(argv[1],"range-fifo")){plc::Fifo r{std::atoi(argv[2])};}
  else if(!std::strcmp(argv[1],"range-lifo")){plc::Lifo r{std::atoi(argv[2])};}
  else if(!std::strcmp(argv[1],"all-slots")){
    plc::Fifo a{0};plc::Lifo b{1};plc::Fifo c{2};plc::Lifo d{3};
    a.set_input(-1);b.set_input(2);c.set_input(-3);d.set_input(4);
    a.update(false,true,false);b.update(false,true,false);
    c.update(false,true,false);d.update(false,true,false);
    a.update(false,false,true);b.update(false,false,true);
    c.update(false,false,true);d.update(false,false,true);
    std::printf("%d %d %d %d\n",a.output(),b.output(),c.output(),d.output());
  }else if(!std::strcmp(argv[1],"self-status")){
    plc::Fifo r{0};r.set_input(11);r.set_output(42);
    r.update(false,true,!r.empty());show(r);
    r.update(false,true,!r.empty());show(r);
    r.update(false,true,!r.empty());show(r);
  }else return 7;
  return 0;
}
""")
        result = subprocess.run(
            [
                cls.compiler,
                "-std=c++17",
                "-O0",
                "-I",
                str(cls.sdk),
                str(source),
                "-o",
                str(cls.binary),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            raise AssertionError("Register SDK does not compile:\n" + result.stderr)

    def check_trace(self, mode, steps):
        commands = []
        for op, value, _ in steps:
            args = " ".join(str(int(v)) for v in value) if op == "U" else str(value)
            commands.append(op + " " + args)
        result = subprocess.run(
            [str(self.binary), mode],
            input="\n".join(commands) + "\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        got = [tuple(map(int, line.split())) for line in result.stdout.splitlines()]
        self.assertEqual(got, [(0, 0, True, False)] + [want for _, _, want in steps])

    def test_both_modes_share_identity_pool_and_reject_duplicate_and_out_of_range_ids(
        self,
    ):
        for scenario in [
            "duplicate-fifo",
            "duplicate-lifo",
            "duplicate-cross",
            "duplicate-cross-reverse",
        ]:
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [str(self.binary), scenario], capture_output=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0)
        for mode in ["range-fifo", "range-lifo"]:
            for index in ["-1", "4"]:
                with self.subTest(mode=mode, index=index):
                    result = subprocess.run(
                        [str(self.binary), mode, index], capture_output=True, timeout=10
                    )
                    self.assertNotEqual(result.returncode, 0)
        result = subprocess.run(
            [str(self.binary), "all-slots"], capture_output=True, text=True, timeout=10
        )
        self.assertEqual((result.returncode, result.stdout), (0, "-1 2 -3 4\n"))

    def test_local_precall_self_status_matches_literal_trace(self):
        result = subprocess.run(
            [str(self.binary), "self-status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            (result.returncode, result.stdout), (0, "11 42 0 0\n11 11 1 0\n11 11 1 0\n")
        )

    def test_declaration_only_surface_accepts_const_getters_and_exact_call_types(self):
        source = self.directory / "declarations.cpp"
        source.write_text("""#include <plc.hpp>
#include <type_traits>
plc::Fifo fifo{0};plc::Lifo lifo{3};
template<class R> void check(R& r,const R& c){
  static_assert(std::is_same<decltype(c.input()),plc::i16>::value);
  static_assert(std::is_same<decltype(c.output()),plc::i16>::value);
  static_assert(std::is_same<decltype(c.empty()),bool>::value);
  static_assert(std::is_same<decltype(c.full()),bool>::value);
  static_assert(std::is_same<decltype(r.set_input((plc::i16)-32768)),void>::value);
  static_assert(std::is_same<decltype(r.set_output((plc::i16)32767)),void>::value);
  static_assert(std::is_same<decltype(r.update(false,true,false)),void>::value);
}
void scan(){check(fifo,fifo);check(lifo,lifo);}
""")
        result = subprocess.run(
            [
                self.compiler,
                "-std=c++17",
                "-fsyntax-only",
                "-I",
                str(self.sdk),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
