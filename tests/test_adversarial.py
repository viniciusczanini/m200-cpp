"""Regression cases discovered by independent adversarial audit."""

import tempfile
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from m200.frontend import compile_source
from m200.model import CompileError
from m200.model import Program
from m200.project import load_project


class AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def test_macro_cannot_inject_executable_sdk_declarations(self):
        p = self.work / "injected.cpp"
        p.write_text("""#define input(x) input(x); void output(int,bool); __attribute__((constructor)) inline void before_scan(){output(0,true);} bool ignored(x)
#include <plc.hpp>
#undef input
void scan(){}
""")
        with self.assertRaisesRegex(CompileError, "macro.*SDK|SDK.*macro"):
            compile_source(p)

    def test_scalar_xml_cannot_hide_nested_configuration(self):
        fixture = Path(__file__).parent / "fixtures/synthetic.smbp"
        for branch, scalar, value in [
            ("SoftwareConfiguration/FastTask", "Period", "255"),
            ("SoftwareConfiguration/CpuBehavior", "WatchdogPeriod", "250"),
        ]:
            with self.subTest(branch=branch):
                root = ET.parse(fixture).getroot()
                node = root.find(branch)
                if node is None:
                    node = ET.SubElement(root.find("SoftwareConfiguration"), "FastTask")
                field = node.find(scalar)
                if field is None:
                    field = ET.SubElement(node, scalar)
                field.text = value
                ET.SubElement(field, "Hidden").text = "active"
                path = self.work / "hidden.smbp"
                ET.ElementTree(root).write(path)
                with self.assertRaisesRegex(CompileError, "scalar"):
                    load_project(path)

    def test_deep_xml_is_reported_as_compile_error(self):
        path = self.work / "deep.smbp"
        path.write_text(
            "<ProjectDescriptor>"
            + "<x>" * 1500
            + "</x>" * 1500
            + "</ProjectDescriptor>"
        )
        with self.assertRaisesRegex(CompileError, "depth"):
            load_project(path)

    def test_utf16_cannot_bypass_dtd_rejection(self):
        p = self.work / "entity.smbp"
        p.write_bytes(
            (
                '<?xml version="1.0" encoding="UTF-16"?>\n<!DOCTYPE ProjectDescriptor [<!ENTITY X "TM200CE40T">]><ProjectDescriptor><HardwareConfiguration><Plc><Cpu><Reference>&X;</Reference></Cpu></Plc></HardwareConfiguration><SoftwareConfiguration/></ProjectDescriptor>'
            ).encode("utf-16")
        )
        with self.assertRaisesRegex(CompileError, "UTF-8|DTD"):
            load_project(p)

    def test_json_timer_indexes_are_canonical_and_unknown_fields_fail(self):
        p = Program().as_dict()
        p["timers"] = {
            "0": {"kind": "TON", "milliseconds": 0},
            "00": {"kind": "TOF", "milliseconds": 0},
        }
        with self.assertRaisesRegex(CompileError, "canonical"):
            Program.from_dict(p)

    def test_deep_and_duplicate_json_have_controlled_cli_errors(self):
        for payload in [
            '{"format":"m200-cpp-il-v1","target":"TM200CE40T","rungs":[],"timers":{},"metadata":'
            + "[" * 1300
            + "0"
            + "]" * 1300
            + "}",
            '{"format":"m200-cpp-il-v1","target":"TM200CE40T","rungs":[],"rungs":[["LD 1","ST %Q0.0"]],"timers":{}}',
        ]:
            p = self.work / "bad.json"
            p.write_text(payload)
            r = subprocess.run(
                [sys.executable, "-m", "m200", "inspect", str(p)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("M200-E:", r.stderr)
            self.assertNotIn("Traceback", r.stderr)

    def test_variadic_helpers_are_outside_the_explicit_parameter_contract(self):
        p = self.work / "variadic.cpp"
        p.write_text("#include <plc.hpp>\nbool f(bool a,...){return a;}void scan(){}")
        with self.assertRaisesRegex(CompileError, "variadic"):
            compile_source(p)
        p = Program().as_dict()
        p["hidden_program"] = "active"
        with self.assertRaisesRegex(CompileError, "unknown"):
            Program.from_dict(p)
