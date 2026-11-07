"""SW114 native unsigned-literal domain versus the public signed i16 API.

The official editor rejected SW114 assignment/comparison constants of -1 with
"-1 is out of authorized bounds (0...65535)". This evidence is specific to
SW114. Local round trips and SDK checks do not replace official acceptance.
"""

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from batch_acceptance.native_probe import observe_native
from m200.frontend import compile_source
from m200.il import Machine
from m200.model import CompileError, Program
from m200.project import load_project, write_project
from m200.reverse import to_cpp


ROOT = Path(__file__).resolve().parents[1]
MEMORY = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
SIGNED_MASKS = """#include <plc.hpp>
void scan(){
 plc::clear_arithmetic_error();
 plc::write_word(23,plc::add_i16(32767,1));
 if(plc::input(0)){plc::write_system_word(114,-1);}
 else if(plc::input(1)){plc::write_system_word(114,-32768);}
 else if(plc::input(2)){plc::write_system_word(114,0);}
 else{plc::write_system_word(114,32767);}
 plc::write_word(20,plc::read_system_word(114));
 plc::output(0,plc::read_system_word(114)==-1);
 plc::output(1,plc::read_system_word(114)!=-1);
 plc::output(2,plc::read_system_word(114)<0);
 plc::output(3,plc::read_system_word(114)>=0);
 plc::output(4,plc::read_system_word(114)>0);
 plc::output(5,plc::read_system_word(114)<=-1);
 plc::output(6,plc::read_system_word(114)==-32768);
 plc::output(7,-1<plc::read_system_word(114));
 plc::output(8,plc::read_system_word(114)<-1);
 plc::output(9,plc::read_system_word(114)<=32767);
 plc::output(10,plc::read_system_word(114)>=-32768);
 plc::output(11,plc::system(18));
 plc::clear_arithmetic_error();
 plc::write_word(21,plc::add_i16(plc::read_system_word(114),1));
 plc::output(12,plc::system(18));
}
"""


class NatalSW114Regressions(unittest.TestCase):
    def compile_text(self, folder, text):
        source = folder / "original.cpp"
        source.write_text(text)
        return source, compile_source(source)

    def assert_native_literal_domain(self, project):
        tree = ET.parse(project)
        values = [node.text or "" for tag in ("InstructionLine", "OperationExpression", "ComparisonExpression")
            for node in tree.findall(".//" + tag)]
        self.assertTrue(any("%SW114" in value for value in values))
        # Inspect actual native instructions and graphics, not an embedded C++
        # comment or inferred SDK type. Do not apply this rule to other SWs.
        literal = r"(?:16\#[0-9A-Fa-f]+|-?[0-9]+)"
        right = re.compile(r"%SW114(?![0-9])\s*(?::=|>=|<=|<>|=|>|<)\s*(" + literal + r")(?![0-9])")
        left = re.compile(r"(?<![0-9A-Za-z_.])(" + literal + r")\s*(?:>=|<=|<>|=|>|<)\s*%SW114(?![0-9])")
        for value in values:
            for pattern in (right, left):
                for match in pattern.finditer(value):
                    text = match[1]
                    number = int(text[3:], 16) if text.startswith("16#") else int(text)
                    self.assertGreaterEqual(number, 0, value)
                    self.assertLessEqual(number, 65535, value)
        for node in tree.findall(".//ComparisonExpression"):
            self.assertNotIn("%SW114", node.text or "", "Public i16 comparisons require a signed word carrier")
        for node in tree.findall(".//InstructionLine"):
            value = node.text or ""
            if re.match(r"(?:LD|LDN|AND|ANDN|OR|ORN|XOR|XORN)\s+\[", value):
                self.assertNotIn("%SW114", value, "Native comparison must use its signed word carrier")

    def pipeline(self, folder, text, frames, expected):
        source, program = self.compile_text(folder, text)
        before = copy.deepcopy(program.as_dict())
        decoded = Program.from_dict(json.loads(json.dumps(before)))
        project = folder / "generated.smbp"
        write_project(program, MEMORY, project)
        self.assert_native_literal_domain(project)
        imported = load_project(project)
        reverse = folder / "actual_project_reverse.cpp"
        reverse.write_text(to_cpp(imported))
        rebuilt = compile_source(reverse)
        rebuilt_project = folder / "rebuilt.smbp"
        write_project(rebuilt, MEMORY, rebuilt_project)
        self.assert_native_literal_domain(rebuilt_project)
        readback = load_project(rebuilt_project)
        self.assertEqual(program.as_dict(), before)
        words = sorted({int(key) for row in expected for key in row.get("words", {})})
        for candidate in (program, decoded, imported, rebuilt, readback):
            machine = Machine(candidate)
            actual = []
            for frame in frames:
                for index, value in frame.get("words", {}).items():
                    machine.words[int(index)] = value
                bits = machine.step(frame["inputs"], frame.get("dt_ms", 10))
                # Machine.words is the raw u16 image; the observed public
                # read_word API and native probe expose the same bits as i16.
                observed_words = {}
                for index in words:
                    raw = machine.words[index] & 65535
                    observed_words[str(index)] = raw - 65536 if raw >= 32768 else raw
                actual.append({"output_mask": sum(1 << i for i, value in enumerate(bits) if value),
                    "words": observed_words})
            self.assertEqual(actual, expected)
        for name, cpp in (("original-native", source), ("reverse-native", reverse)):
            self.assertEqual(observe_native(cpp, frames, words, folder / name, ROOT / "sdk"), expected)

    def test_signed_masks_and_relations_survive_native_project_and_reverse(self):
        frames = [{"inputs": controls} for controls in ({}, {"0": True}, {"1": True}, {"2": True}, {"0": True})]
        # Bits0..10 are comparisons, bit11 checks sticky S18 survives snapshots,
        # bit12 checks SW114+1 overflow. All expectations are independent literals.
        expected = [
            {"output_mask": 7834, "words": {"20": 32767, "21": -32768}},
            {"output_mask": 3621, "words": {"20": -1, "21": 0}},
            {"output_mask": 3942, "words": {"20": -32768, "21": -32767}},
            {"output_mask": 3722, "words": {"20": 0, "21": 1}},
            {"output_mask": 3621, "words": {"20": -1, "21": 0}},
        ]
        with tempfile.TemporaryDirectory() as d:
            self.pipeline(Path(d), SIGNED_MASKS, frames, expected)

    def test_exact_negative_assignment_and_equality_vendor_repro(self):
        source = """#include <plc.hpp>
void scan(){plc::write_system_word(114,-1);
 plc::output(0,plc::read_system_word(114)==-1);
 plc::output(1,plc::read_system_word(114)!=-1);
 plc::write_word(20,plc::read_system_word(114));}
"""
        with tempfile.TemporaryDirectory() as d:
            self.pipeline(Path(d), source, [{"inputs": {}}],
                [{"output_mask": 1, "words": {"20": -1}}])

    def test_dynamic_i16_write_and_comparison_keep_signed_order(self):
        source = """#include <plc.hpp>
void scan(){plc::write_system_word(114,plc::read_word(40));
 plc::write_word(20,plc::read_system_word(114));
 plc::output(0,plc::read_system_word(114)==plc::read_word(41));
 plc::output(1,plc::read_system_word(114)!=plc::read_word(41));
 plc::output(2,plc::read_system_word(114)<plc::read_word(41));
 plc::output(3,plc::read_system_word(114)>=plc::read_word(41));}
"""
        frames = [{"inputs": {}, "words": {"40": a, "41": b}}
            for a, b in ((-1, 0), (-32768, -1), (0, -1), (-1, -1))]
        expected = [
            {"output_mask": 6, "words": {"20": -1}},
            {"output_mask": 6, "words": {"20": -32768}},
            {"output_mask": 10, "words": {"20": 0}},
            {"output_mask": 9, "words": {"20": -1}},
        ]
        with tempfile.TemporaryDirectory() as d:
            self.pipeline(Path(d), source, frames, expected)

    def test_invalid_or_unmodeled_system_word_indices_refuse(self):
        for body in (
            "plc::write_system_word(-1,0);", "plc::write_system_word(115,0);",
            "plc::write_system_word(65536,0);", "plc::write_system_word(49,0);",
            "plc::write_word(20,plc::read_system_word(-1));",
            "plc::write_word(20,plc::read_system_word(115));",
        ):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as d:
                source = Path(d) / "invalid.cpp"
                source.write_text("#include <plc.hpp>\nvoid scan(){" + body + "}\n")
                with self.assertRaises(CompileError):
                    compile_source(source)

    def test_public_value_bounds_remain_i16_despite_native_unsigned_encoding(self):
        for value in (-32769, 32768, 65535, 65536):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as d:
                source = Path(d) / "invalid.cpp"
                source.write_text("#include <plc.hpp>\nvoid scan(){plc::write_system_word(114,"
                    + str(value) + ");}\n")
                with self.assertRaises(CompileError):
                    compile_source(source)


if __name__ == "__main__":
    unittest.main()
