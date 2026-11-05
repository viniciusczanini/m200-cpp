import tempfile
import unittest
from pathlib import Path

from m200.frontend import compile_source
from m200.il import Machine, validate
from m200.model import Program, CompileError
from m200.modbus import MemoryModbusPeer, MemoryTransport
from m200.native import run_native
from m200.reverse import to_cpp


class CommunicationCompilerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "communication.cpp"

    def compile(self, body):
        self.source.write_text("#include <plc.hpp>\n" + body)
        return compile_source(self.source)

    def test_cpp_read_var_emits_real_block_and_reads_reply_buffer(self):
        p = self.compile("""plc::ReadVar read{plc::Link::Ethernet,1,5,plc::Object::HoldingWords,0,2,4000};
void scan(){bool done=read.update(plc::input(0),false);plc::output(0,done);plc::output(1,read.busy());plc::output(2,read.error());plc::output(3,plc::read_word(4000)==123);}""")
        self.assertIn("%READ_VAR0", p.communications)
        self.assertTrue(any(r[0] == "BLK %READ_VAR0" for r in p.rungs))
        # Destination4000/4001 must be reserved before temporaries are allocated.
        self.assertFalse(
            any(a in p.symbols for a in ["%MW4000", "%MW4001", "%MD4000", "%MF4000"])
        )
        peer = MemoryModbusPeer(holding_registers=[123, 456])
        m = Machine(p, communication_transport=MemoryTransport(peer, latency_ms=1))
        rows = [m.step({0: v}, 10) for v in [False, True, True, True, False]]
        self.assertEqual(
            [r[:4] for r in rows],
            [
                [False, False, False, False],
                [False, True, False, False],
                [True, False, False, True],
                [True, False, False, True],
                [False, False, False, True],
            ],
        )
        self.assertEqual(m.words[4000:4002], [123, 456])
        from m200.cli import report

        self.assertEqual(report(p)["resources"]["memory_words"], 2)
        validate(Program.from_dict(p.as_dict()))

    def test_native_single_input_communication_graph(self):
        import xml.etree.ElementTree as ET
        from m200.project import check_graph

        for kind, typ, col in [
            ("READ_VAR", "ReadVarBasic", 2),
            ("WRITE_VAR", "WriteVarBasic", 3),
        ]:
            key = "%" + kind + "0"
            lines = ["BLK " + key, "LD %M3", "EXECUTE", "END_BLK"]
            root = ET.Element("RungEntity")
            graph = ET.SubElement(root, "LadderElements")
            items = [("NormalContact", "%M3", 0), (typ, key, col)] + [
                ("Line", "", i) for i in range(1, col)
            ]
            for t, descriptor, column in items:
                e = ET.SubElement(graph, "LadderEntity")
                for tag, v in [
                    ("ElementType", t),
                    ("Descriptor", descriptor),
                    ("Row", "0"),
                    ("Column", str(column)),
                    ("ChosenConnection", "Left" if t == typ else "Left, Right"),
                ]:
                    ET.SubElement(e, tag).text = v
            with self.subTest(kind=kind):
                check_graph(root, lines)
            if kind == "WRITE_VAR":
                for entry in graph:
                    if entry.findtext("ElementType") == "NormalContact":
                        entry.find("Column").text = "1"
                    elif (
                        entry.findtext("ElementType") == "Line"
                        and entry.findtext("Column") == "1"
                    ):
                        entry.find("Column").text = "0"
                check_graph(root, lines)

    def test_write_and_write_read_use_shared_word_buffers(self):
        p = self.compile("""plc::WriteReadVar x{plc::Link::Ethernet,1,10,0,2,200,0,2,300};
void scan(){plc::write_word(200,42);plc::write_word(201,-1);bool done=x.update(plc::input(0),false);plc::output(0,done);plc::output(1,plc::read_word(300)==42);plc::output(2,plc::read_word(301)==-1);}""")
        peer = MemoryModbusPeer(holding_registers=[0, 0])
        m = Machine(p, communication_transport=MemoryTransport(peer))
        for value in [False, True, True]:
            got = m.step({0: value}, 10)
        self.assertEqual(got[:3], [True, True, True])
        self.assertEqual(peer.holding_registers, [42, 65535])

    def test_no_transport_has_explicit_error_and_reverse_matches_native(self):
        p = self.compile("""plc::ReadVar r{plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};
void scan(){bool done=r.update(plc::input(0),plc::input(1));plc::output(0,done);plc::output(1,r.error());plc::output(2,r.comm_error()==255 && r.oper_error()==15);}""")
        frames = [{"inputs": {0: v}} for v in [True, False, True, True, False]]
        m = Machine(p)
        expected = [m.step(f["inputs"]) for f in frames]
        self.assertEqual([r[1] for r in expected], [False, False, True, True, False])
        self.assertEqual(run_native(self.source, frames), expected)
        reverse = self.source.with_name("reverse.cpp")
        reverse.write_text(to_cpp(p))
        self.assertEqual(run_native(reverse, frames), expected)
        q = Machine(compile_source(reverse))
        self.assertEqual([q.step(f["inputs"]) for f in frames], expected)

    def test_invalid_modbus_construction_and_update_are_compile_errors(self):
        for body in [
            "plc::ReadVar r{plc::Link::Ethernet,17,1,plc::Object::HoldingWords,0,1,0};void scan(){}",
            "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,126,0};void scan(){}",
            "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,2,7999};void scan(){}",
            "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,1,0};void scan(){if(plc::input(0)){bool d=r.update(true,false);}}",
            "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,1,0};void scan(){bool a=r.update(false,false);bool b=r.update(true,false);}",
            "plc::ReadVar r{plc::Link::Serial1,1,1,plc::Object::HoldingWords,0,1,0};void scan(){plc::output(0,r.busy());}",
        ]:
            with self.subTest(body=body), self.assertRaises(CompileError):
                self.compile(body)

    def test_reverse_preserves_sparse_native_communication_indices(self):
        from m200.modbus import ModbusConfig

        p = Program(
            [
                ["BLK %READ_VAR7", "LD 0", "EXECUTE", "END_BLK"],
                ["BLK %READ_VAR21", "LD 0", "EXECUTE", "END_BLK"],
            ],
            communications={
                "%READ_VAR7": ModbusConfig(index_data=100),
                "%READ_VAR21": ModbusConfig(index_data=200),
            },
        )
        self.source.write_text(to_cpp(p))
        q = compile_source(self.source)
        self.assertEqual(q.communications, p.communications)

    def test_native_identifiers_do_not_accept_unicode_digits(self):
        from m200.modbus import ModbusConfig

        for p in [
            Program(
                [["BLK %READ_VAR1١", "LD 0", "EXECUTE", "END_BLK"]],
                communications={"%READ_VAR1١": ModbusConfig()},
            ),
            Program([["LD [%MW1١=1]", "ST %Q0.0"]]),
        ]:
            with self.subTest(program=p), self.assertRaises(CompileError):
                validate(p)
