"""G11 scoped Modbus interop: literal peers, actual native config and reverse.

EXCH/MSG/ASCII/SMS are DEFERRED_VERSION, not provided or certified by this suite.
The native hook below is an explicit local peer adapter, never a native device.
"""

import copy
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from harness import Case, ROOT, ScriptedTransport, equal, require, refused, state, sha256


REFERENCE = "EIO0000003289.04 pp171-187,204-205; Modbus V1.1b3; G11 scoped CONTRACT.md"
SERIAL = ROOT / "tests/fixtures/official_tm200ce40t_modbus_bare_abort_read.smbp"
IDLE = [False, False, False, False, 0, 0]
BUSY = [False, True, False, False, 0, 0]
DONE = [True, False, False, False, 0, 0]


def _compile(work, text, name):
    from m200.frontend import compile_source

    path = work / (name + ".cpp")
    path.write_text("#include <plc.hpp>\n" + text)
    return path, compile_source(path)


def _both_channels(work):
    tree = ET.parse(SERIAL)
    cpu = tree.find("HardwareConfiguration/Plc/Cpu")
    ethernet = cpu.find("EthernetConfiguration")
    if ethernet is None:
        ethernet = ET.SubElement(cpu, "EthernetConfiguration")
    tcp = ethernet.find("ModbusTcpSlave")
    if tcp is None:
        tcp = ET.SubElement(ethernet, "ModbusTcpSlave")
    devices = tcp.find("Devices")
    if devices is None:
        devices = ET.SubElement(tcp, "Devices")
    devices.clear()
    remote = ET.SubElement(devices, "RemoteServer")
    for tag, value in [("DeviceId", "0"), ("Address", ""), ("DeviceGeneralType", "IoScannerOther"), ("DeviceTypeName", "Generic Device"), ("DeviceTypeId", "23"), ("SlaveAddress", "127.0.0.1"), ("ResetVariable", ""), ("Name", "Explicit local peer"), ("InitRequestUnitId", "1"), ("ChannelUnitId", "1"), ("Timeout", "10")]:
        ET.SubElement(remote, tag).text = value
    path = work / "both-channels.template.smbp"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def _surface(work):
    from m200.il import Machine, validate
    from m200.model import CompileError, Program
    from m200.modbus import CommunicationEngine, ModbusConfig
    from m200.native import run_native
    from m200.reverse import to_cpp

    declaration = "plc::ReadVar r{7,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};"
    source, program = _compile(work, declaration + "void scan(){plc::output(0,r.property(plc::CommProperty::Link)==1);r.set_property(plc::CommProperty::Id,7);r.set_property(plc::CommProperty::FirstObj,-1);r.update(plc::input(0),false);plc::output(1,r.property(plc::CommProperty::Id)==7);plc::output(2,r.property(plc::CommProperty::FirstObj)==-1);}", "surface")
    frames = [{"inputs": {0: False}}, {"inputs": {0: True}}]
    expected = [[True, True, True], [True, True, True]]
    machine = Machine(program)
    equal([machine.step(frame["inputs"])[:3] for frame in frames], expected)
    equal([row[:3] for row in run_native(source, frames)], expected)
    reverse, rebuilt = _compile(work, to_cpp(program), "surface-reverse")
    equal(rebuilt.communications, program.communications)
    equal([row[:3] for row in run_native(reverse, frames)], expected)
    invalid = [
        declaration + "void scan(){r.set_property(plc::CommProperty::FirstReadObj,1);r.update(false,false);}",
        declaration + "void scan(){r.property(plc::CommProperty::WriteQuantity);r.update(false,false);}",
        declaration + "void scan(){r.busy()=true;r.update(false,false);}",
        "plc::WriteReadVar r{0,plc::Link::Serial1,1,5,0,1,100,0,1,200};void scan(){r.set_property(plc::CommProperty::FirstObj,1);r.update(false,false);}",
    ]
    for index, text in enumerate(invalid):
        refused(lambda text=text, index=index: _compile(work, text, "surface-invalid-" + str(index)), CompileError)
    for field in ("COMMERROR", "OPERERROR", "HIDDENPROPERTY"):
        forged = copy.deepcopy(program)
        forged.rungs.insert(0, ["LD 1", f"[%READ_VAR7.{field}:=1]"])
        forged.metadata.pop("rung_origins", None)
        refused(lambda forged=forged: validate(forged), CompileError, field)
    engine = CommunicationEngine()
    config = ModbusConfig(first_obj=65535)
    engine.define("r", config)
    equal(engine.read_property("r", "FIRSTOBJ"), -1)
    equal(engine.read_property("r", "LINK"), 1)
    engine.define("e", ModbusConfig(link="ETH1"))
    equal(engine.read_property("e", "LINK"), 3)
    return {"literal_rows": expected, "signed_u16_first_object": -1, "native_links": {"SL1": 1, "ETH1": 3}, "wrong_family_or_readonly_controls": 7}


def _channels(work):
    from m200.communication_xml import check_dynamic_channels
    from m200.il import validate
    from m200.model import CompileError, Program
    from m200.modbus import ModbusConfig
    from m200.project import write_project, load_project

    both = _both_channels(work)
    blocks = [["BLK %READ_VAR7", "LD %M20", "EXECUTE", "END_BLK"]]
    for value in ("1", "3", "%MW10"):
        program = Program([["LD 1", f"[%READ_VAR7.LINK:={value}]"]] + blocks, communications={"%READ_VAR7": ModbusConfig()})
        validate(program)
        check_dynamic_channels(ET.parse(both).getroot(), program)
        destination = work / ("channels-" + value.replace("%", "") + ".smbp")
        write_project(program, both, destination)
        equal(load_project(destination).communications, program.communications)
        if value != "1":
            destination.write_bytes(b"PREVIOUS\n")
            try:
                write_project(program, SERIAL, destination)
            except CompileError as error:
                require("Ethernet" in str(error) or "remote" in str(error), "refused for unrelated reason: " + str(error))
            else:
                raise AssertionError("dynamic alternate Ethernet channel was silently synthesized")
            equal(destination.read_bytes(), b"PREVIOUS\n")
    # A future runtime single-write object must use the actual selected level.
    from m200.communication_xml import check_template_channels
    lower = ET.parse(both)
    lower.find("ManagementLevel").text = "FunctLevelMan8_0"  # actual4.1, below5.0.
    for value in ("4", "%MW10"):
        program = Program([["LD 1", f"[%WRITE_VAR0.OBJTYPE:={value}]"], ["BLK %WRITE_VAR0", "LD %M20", "EXECUTE", "END_BLK"]], communications={"%WRITE_VAR0": ModbusConfig(kind="WRITE_VAR")})
        check_template_channels(lower.getroot(), program.communications)  # Valid static sibling.
        refused(lambda: check_dynamic_channels(lower.getroot(), program), CompileError, "dynamic single-write beforeFL5")
    return {"literal_or_variable_link_channels_checked": 3, "missing_alternate_channel_preserves_destination": True, "actual_pre5_dynamic_single_write_refused": True}


SNAPSHOT_SOURCE = """
plc::WordMemory image{8000};
plc::ReadVar r{7,plc::Link::Serial1,1,10,plc::Object::HoldingWords,0,2,100};
void scan(){
  if(plc::input(3)){
    r.set_property(plc::CommProperty::Link,3);r.set_property(plc::CommProperty::Id,1);
    r.set_property(plc::CommProperty::Timeout,1);r.set_property(plc::CommProperty::FirstObj,3);
    r.set_property(plc::CommProperty::IndexData,200);
  }else{
    r.set_property(plc::CommProperty::Link,1);r.set_property(plc::CommProperty::Id,1);
    r.set_property(plc::CommProperty::Timeout,10);r.set_property(plc::CommProperty::FirstObj,0);
    r.set_property(plc::CommProperty::IndexData,100);
  }
  r.update(plc::input(0),false);
  plc::output(0,r.done());plc::output(1,r.busy());plc::output(2,r.error());
}
"""
FRAMES = [{"inputs": value} for value in ({}, {0: True}, {0: True, 3: True}, {0: True, 3: True}, {0: True, 3: True}, {3: True}, {0: True, 3: True}, {0: True, 3: True}, {0: True, 3: True}, {0: True, 3: True})]
SNAPSHOT_ROWS = [[False, False, False], [False, True, False], [False, True, False], [False, True, False], [True, False, False], [False, False, False], [False, True, False], [False, True, False], [False, True, False], [True, False, False]]


def _peer_trace(program):
    from m200.il import Machine

    transport = ScriptedTransport([bytes.fromhex("03 04 1234 ffff"), bytes.fromhex("03 04 0007 0008")], latency_ms=30)
    machine = Machine(program, communication_transport=transport)
    machine.words = [99] * 8000
    rows, banks = [], []
    for frame in FRAMES:
        rows.append(machine.step(frame["inputs"], 10)[:3])
        banks.append([machine.words[i] for i in (100, 101, 200, 201)])
    equal(rows, SNAPSHOT_ROWS)
    equal([entry[1] for entry in transport.started], [bytes.fromhex("03 0000 0002"), bytes.fromhex("03 0003 0002")])
    equal([(entry[0].link, entry[0].id, entry[0].timeout_100ms, entry[0].index_data) for entry in transport.started], [("SL1", 1, 10, 100), ("ETH1", 1, 1, 200)])
    equal(banks[:4], [[99, 99, 99, 99]] * 4)
    equal(banks[4:9], [[4660, 65535, 99, 99]] * 5)
    equal(banks[9], [4660, 65535, 7, 8])
    return {"rows": rows, "banks": banks, "request_hex": [entry[1].hex() for entry in transport.started]}


def _peer_snapshot_routes(work):
    from m200.model import Program, CompileError
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    source, program = _compile(work, SNAPSHOT_SOURCE, "snapshot")
    expected_config = program.communications.copy()
    results = {"forward": _peer_trace(program)}
    decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    results["json"] = _peer_trace(decoded)
    both = _both_channels(work)
    before = both.read_bytes()
    destination = work / "snapshot.smbp"
    write_project(program, both, destination)
    equal(both.read_bytes(), before)
    imported = load_project(destination)
    equal(imported.communications, expected_config)
    results["project"] = _peer_trace(imported)
    reverse_text = to_cpp(imported)
    equal(len(re.findall(r"plc::WordMemory\b", reverse_text)), 1)
    require("8000" in reverse_text, "dynamic buffer reverse lost full word-image ownership")
    reverse, rebuilt = _compile(work, reverse_text, "snapshot-reverse")
    equal(rebuilt.communications, expected_config)
    results["actual_reverse"] = _peer_trace(rebuilt)
    root = ET.parse(destination)
    operations = [node for node in root.iter("OperationExpression") if "READ_VAR7" in (node.text or "")]
    require(any("INDEXDATA" in node.text for node in operations), "real native operation block omitted dynamic buffer store")
    operations[0].text = "%READ_VAR7.HIDDENPROPERTY := 1"
    forged = work / "forged-property-graph.smbp"
    root.write(forged, encoding="utf-8", xml_declaration=True)
    refused(lambda: load_project(forged), CompileError, "forged property native graph")
    (work / "peer-route-observations.json").write_text(json.dumps(results, indent=2) + "\n")
    return {"routes": len(results), "frames_per_route": len(FRAMES), "native_config_sha256": sha256(destination), "requests": results["forward"]["request_hex"], "scope": "positive explicit local peer only; no device transaction"}


def _native_hook(source, work, label):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    require(compiler is not None, "clang++ missing")
    driver = work / (label + "-driver.cpp")
    driver.write_text("#include <cstdio>\n#define PLC_NATIVE\n#include \"" + str(source) + "\"\n" + r'''
static bool armed=false,old_execute=false,active=false,done=false;
static unsigned long long started=0;
static int transaction=0;
static plc::detail::CommunicationConfig captured{};
static plc::detail::CommunicationResult peer(const plc::detail::CommunicationConfig& c,int index,bool execute,bool abort,unsigned long long now,unsigned short* words){
  if(index!=7||abort)__builtin_trap();
  if(active){
    if(c.link!=captured.link||c.timeout!=captured.timeout||c.index!=captured.index||c.first!=captured.first)__builtin_trap();
    if(now-started>=30){words[captured.index]=transaction==1?0x1234:7;words[captured.index+1]=transaction==1?0xffff:8;active=false;done=true;}
  }else if(armed&&execute&&!old_execute){
    ++transaction;captured=c;started=now;active=true;done=false;
    if(transaction==1&&(c.link!=1||c.timeout!=10||c.first!=0||c.index!=100))__builtin_trap();
    if(transaction==2&&(c.link!=2||c.timeout!=1||c.first!=3||c.index!=200))__builtin_trap();
    if(transaction>2)__builtin_trap();
  }else if(!execute){done=false;}
  armed=true;old_execute=execute;
  plc::detail::CommunicationResult result{};result.busy=active;result.done=done;return result;
}
int main(){
  for(int i=0;i<8000;++i)plc::detail::words[i]=99;
  plc::detail::communication_hook=peer;
  const bool execute[]={false,true,true,true,true,false,true,true,true,true};
  for(int frame=0;frame<10;++frame){
    plc::detail::inputs[0]=execute[frame];plc::detail::inputs[3]=frame>=2;
    plc::detail::begin_scan();scan();
    std::printf("%d %d %d %u %u %u %u\n",plc::detail::outputs[0],plc::detail::outputs[1],plc::detail::outputs[2],plc::detail::words[100],plc::detail::words[101],plc::detail::words[200],plc::detail::words[201]);
    plc::detail::first_scan=false;plc::detail::now_ms+=10;
  }
  return transaction==2?0:3;
}
''')
    binary = work / (label + "-native-peer")
    build = subprocess.run([compiler, "-std=c++17", "-O0", "-I", str(ROOT / "sdk"), str(driver), "-o", str(binary)], capture_output=True, text=True, timeout=60)
    (work / (label + "-build.log")).write_text(build.stdout + build.stderr)
    equal(build.returncode, 0, build.stderr)
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
    (work / (label + "-native.log")).write_text(result.stdout + result.stderr)
    equal(result.returncode, 0, "explicit native peer rejected captured config")
    rows = [[int(value) for value in line.split()] for line in result.stdout.splitlines()]
    banks = [[99, 99, 99, 99]] * 4 + [[4660, 65535, 99, 99]] * 5 + [[4660, 65535, 7, 8]]
    equal(rows, [list(map(int, status)) + bank for status, bank in zip(SNAPSHOT_ROWS, banks)])
    return rows


def _native_callback_snapshot(work):
    from m200.reverse import to_cpp

    source, program = _compile(work, SNAPSHOT_SOURCE, "native-hook")
    reverse, _ = _compile(work, to_cpp(program), "native-hook-reverse")
    original = _native_hook(source, work, "original")
    rebuilt = _native_hook(reverse, work, "reverse")
    equal(original, rebuilt)
    return {"native_routes": 2, "literal_frames_each": 10, "positive_transport": "explicit local callback; no physical/native PLC transaction"}


def _protocol_property_errors(work):
    from m200.modbus import CommunicationEngine, ModbusConfig

    checks = []
    for obj, quantity, first, expected in [(5, 0, 65535, "06 ffff abcd"), (4, 0, 7, "05 0007 ff00"), (0, 2, 5, "10 0005 0002 04 abcd 0002")]:
        reply = bytes.fromhex(expected)[:5]
        transport = ScriptedTransport([reply])
        engine = CommunicationEngine(transport)
        config = ModbusConfig(kind="WRITE_VAR", index_data=7998)
        words = [0] * 8000
        words[7998:] = [0xABCD, 2]
        engine.define("w", config)
        for field, value in [("OBJTYPE", obj), ("QUANTITY", quantity), ("FIRSTOBJ", first)]:
            engine.write_property("w", field, value)
        engine.update("w", config, False, False, 0, words)
        equal(state(engine.update("w", config, True, False, 1, words)), BUSY)
        equal(transport.started[0][1], bytes.fromhex(expected))
        equal(state(engine.update("w", config, True, False, 2, words)), DONE)
        checks.append(expected)
    # FC23 copies outgoing shared words before committing a valid reply to an overlapping input span.
    config = ModbusConfig(kind="WRITE_READ_VAR", quantity=2, index_data=7998, read_quantity=2, index_data_in=7998)
    transport = ScriptedTransport([bytes.fromhex("17 04 1111 2222")])
    engine, words = CommunicationEngine(transport), [0] * 8000
    words[7998:] = [42, 65535]
    engine.define("x", config)
    engine.write_property("x", "FIRSTWRITEOBJ", 5)
    engine.write_property("x", "FIRSTREADOBJ", 9)
    engine.update("x", config, False, False, 0, words)
    equal(state(engine.update("x", config, True, False, 1, words)), BUSY)
    equal(transport.started[0][1], bytes.fromhex("17 0009 0002 0005 0002 04 002a ffff"))
    equal(state(engine.update("x", config, True, False, 2, words)), DONE)
    equal(words[7998:], [0x1111, 0x2222])
    for field, value in [("LINK", 2), ("LINK", 4), ("QUANTITY", 0), ("INDEXDATA", 8000)]:
        transport = ScriptedTransport([])
        engine = CommunicationEngine(transport)
        config = ModbusConfig()
        engine.define("bad", config)
        engine.write_property("bad", field, value)
        engine.update("bad", config, False, False, 0, words)
        equal(state(engine.update("bad", config, True, False, 1, words)), [False, False, False, True, 6, 0])
        equal(transport.started, [], "bad effective parameters must not issue a request")
    return {"dynamic_function_requests": checks, "overlapping_fc23_reply": [4369, 8738], "invalid_effective_configs_refused_before_peer": 4}


def _dynamic_buffer_reverse(work):
    from m200.frontend import compile_source
    from m200.il import validate
    from m200.model import CompileError, Program
    from m200.modbus import ModbusConfig
    from m200.reverse import to_cpp

    declaration = "plc::ReadVar r{7,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};"
    for field in ("IndexData", "Quantity", "ObjType"):
        text = declaration + f"void scan(){{r.set_property(plc::CommProperty::{field},plc::read_word(10));r.update(plc::input(0),false);}}"
        try:
            _compile(work, text, "ownership-invalid-" + field)
        except CompileError as error:
            require("WordMemory{8000}" in str(error), "unexpected ownership refusal: " + str(error))
        else:
            raise AssertionError("dynamic buffer/count/type accepted without declared memory ownership")
        _, program = _compile(work, "plc::WordMemory all{8000};" + text, "ownership-valid-" + field)
        source = to_cpp(program)
        equal(len(re.findall(r"plc::WordMemory\b", source)), 1)
        _, rebuilt = _compile(work, source, "ownership-reverse-" + field)
        equal(rebuilt.communications, program.communications)
    # A separate indexed access shares the same one image declaration in reverse.
    program = Program([["LD 1", "[%READ_VAR7.INDEXDATA:=200]"], ["LD 1", "[%MW10:=%MW0[%MW1]]"], ["BLK %READ_VAR7", "LD %M20", "EXECUTE", "END_BLK"]], communications={"%READ_VAR7": ModbusConfig()})
    validate(program)
    source = to_cpp(program)
    equal(len(re.findall(r"plc::WordMemory\b", source)), 1)
    require("{8000}" in source, "indexed+dynamic reverse lost whole-bank extent")
    _, rebuilt = _compile(work, source, "indexed-and-dynamic-reverse")
    equal(rebuilt.communications, program.communications)
    return {"ownership_controls": 3, "reverse_word_images_per_program": 1, "indexed_and_dynamic_reverse": "rebuilt", "restriction_scope": "current compiler capacity/ownership contract, not PLC impossibility"}


def _sr_property_contexts(work):
    from m200.communication_properties import has_buffer_writes
    from m200.communication_xml import check_dynamic_channels
    from m200.model import CompileError
    from m200.numeric import memory_words_used
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    declaration = "plc::WordMemory all{8000};plc::ReadVar r{7,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};"
    body = declaration + 'void relocate(){r.set_property(plc::CommProperty::IndexData,plc::read_word(0));r.set_property(plc::CommProperty::Link,plc::read_word(1));}plc::Subroutine leaf{0,relocate,"relocate",2};void scan(){leaf.call(plc::input(2));r.update(plc::input(0),false);}'
    source, program = _compile(work, body, "sr-properties")
    require(program.subroutines and has_buffer_writes(program), "SR-only buffer property write was omitted")
    equal(len(memory_words_used(program)), 8000)
    reverse_text = to_cpp(program)
    equal(len(re.findall(r"plc::WordMemory\b", reverse_text)), 1)
    require("{8000}" in reverse_text, "SR-only write lost full memory extent in reverse")
    _, rebuilt = _compile(work, reverse_text, "sr-properties-reverse")
    require(has_buffer_writes(rebuilt), "reverse lost SR property write")
    equal(rebuilt.communications, program.communications)
    try:
        check_dynamic_channels(ET.parse(SERIAL).getroot(), program)
    except CompileError as error:
        require("Ethernet" in str(error) or "remote" in str(error), "SR channel refused for unrelated reason")
    else:
        raise AssertionError("SR-only variable LINK bypassed alternate-channel check")
    template = _both_channels(work)
    check_dynamic_channels(ET.parse(template).getroot(), program)
    destination = work / "sr-properties.smbp"
    write_project(program, template, destination)
    restored = load_project(destination)
    require(has_buffer_writes(restored), "native SR readback lost buffer property effects")
    equal(restored.communications, program.communications)
    return {"SR_only_buffer_write_detected": True, "full_bank_reserved": 8000, "alternate_channel_required_from_SR": True, "native_project_sha256": sha256(destination)}


def _unknown_property_guard(work):
    from m200.il import Machine
    from m200.model import CompileError, Program
    from m200.modbus import ModbusConfig
    from m200.native import run_native
    from m200.reverse import to_cpp

    rungs = [["LD 1", "[%MW0:=1/0]"], ["LD 1", "[%READ_VAR7.ID:=%MW0]"], ["BLK %READ_VAR7", "LD 0", "EXECUTE", "END_BLK"], ["LD [%READ_VAR7.ID=7]", "ST %Q0.0"]]
    program = Program(rungs, communications={"%READ_VAR7": ModbusConfig()})
    transport = ScriptedTransport([])
    machine = Machine(program, communication_transport=transport)
    try:
        machine.step({})
    except CompileError as error:
        require("indeterminate integer result observed before recovery" in str(error), "unknown property failed for unrelated reason: " + str(error))
    else:
        raise AssertionError("unknown numeric value was silently coerced into CommProperty")
    equal(machine.communication.read_property("%READ_VAR7", "ID"), 1, "unknown setter partly changed property")
    equal(transport.started, [])
    source, _ = _compile(work, to_cpp(program), "unknown-property-reverse")
    try:
        run_native(source, [{}])
    except CompileError as error:
        require("native reference execution failed" in str(error), "unknown source did not compile before rejection")
    else:
        raise AssertionError("native unknown word reached communication setter")
    recovered = copy.deepcopy(program)
    recovered.rungs.insert(1, ["LD 1", "[%MW0:=7]"])
    equal(Machine(recovered).step({})[0], True)
    source, _ = _compile(work, to_cpp(recovered), "recovered-property-reverse")
    equal(run_native(source, [{}])[0][0], True)
    return {"unknown_rejected_before_property_mutation": True, "known_recovery_control": True, "peer_calls_on_unknown": 0}


def cases():
    return [Case("G11.integrated." + suffix, "G11", description, REFERENCE, run) for suffix, description, run in [
        ("property_surface", "kind/field/status guards, signed words and actual reverse", _surface),
        ("native_channels", "native Link codes and actual alternate-channel/functional-level checks", _channels),
        ("peer_snapshot_routes", "literal positive peer through source/JSON/XML/graph/actual reverse", _peer_snapshot_routes),
        ("native_callback_snapshot", "original/reverse SDK see captured config via explicit local peer hook", _native_callback_snapshot),
        ("protocol_property_errors", "dynamic FC5/6/16/23 bytes, overlap, invalid snapshots before peer", _protocol_property_errors),
        ("dynamic_buffer_reverse", "ownership refusals and one combined dynamic/indexed word image", _dynamic_buffer_reverse),
        ("sr_property_contexts", "SR-only property writes participate in memory/channel/native checks", _sr_property_contexts),
        ("unknown_property_guard", "unknown numeric result cannot mutate communication properties", _unknown_property_guard),
    ]]
