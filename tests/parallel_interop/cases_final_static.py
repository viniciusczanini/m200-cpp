"""Prepared static G01/G08/G09 interop; execute only after coordinator freeze.

Independent native field/port/permission oracles supplement route equivalence.
This file does not claim native RTC_EXEC binding or qualified lifecycle/timing.
"""

import copy
import json
import re
import xml.etree.ElementTree as ET

from harness import Case, PendingContract, ROOT, equal, require, refused, sha256


TEMPLATE = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
SERIAL = ROOT / "tests/fixtures/official_tm200ce40t_modbus_bare_abort_read.smbp"
RTC_REF = "EIO0000003289.04 pp158-166,207-211; EIO0000002019.06 pp322-324,329-334; G09 DELIVERY.md"
SEQ_REF = "EIO0000003289.04 pp141-158; EIO0000002019.06 pp21,25; G08 static metadata provenance"
BOOL_REF = "EIO0000003289.04 pp20,27,37-48,82-83; EIO0000002019.06 pp22-26,321-340; G01/G02 shared images"


def _compile(work, text, name):
    from m200.frontend import compile_source

    path = work / (name + ".cpp")
    path.write_text("#include <plc.hpp>\n" + text)
    return path, compile_source(path)


def _static_routes(work, text, name, fields=(), template=TEMPLATE, program=None):
    from m200.frontend import compile_source
    from m200.il import validate
    from m200.model import Program
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    if program is None:
        source, program = _compile(work, text, name)
    else:
        validate(program)
        source = work / (name + "-actual-source.cpp")
        source.write_text(to_cpp(program))
        reconstructed = compile_source(source)
        for field in fields:
            equal(reconstructed.as_dict().get(field), program.as_dict().get(field), "actual native config source representation: " + field)
    encoded = program.as_dict()
    expected = {field: encoded.get(field) for field in fields}
    decoded = Program.from_dict(json.loads(json.dumps(encoded)))
    validate(decoded)
    for field in fields:
        equal(decoded.as_dict().get(field), expected[field], "JSON config changed: " + field)
    template_bytes = template.read_bytes()
    destination = work / (name + ".smbp")
    write_project(program, template, destination)
    equal(template.read_bytes(), template_bytes, "template changed")
    restored = load_project(destination)
    for field in fields:
        equal(restored.as_dict().get(field), expected[field], "native project changed config: " + field)
    # Source-like metadata must not become a reverse implementation shortcut.
    restored.metadata["original_cpp"] = "FORGED_SOURCE_MUST_NOT_REPLACE_ACTUAL_PROGRAM"
    reverse = work / (name + "-reverse.cpp")
    reverse.write_text(to_cpp(restored))
    require("FORGED_SOURCE_MUST_NOT_REPLACE_ACTUAL_PROGRAM" not in reverse.read_text(), "reverse trusted source payload")
    rebuilt = compile_source(reverse)
    for field in fields:
        equal(rebuilt.as_dict().get(field), expected[field], "actual reverse changed config: " + field)
    rebuilt_project = work / (name + "-rebuilt.smbp")
    write_project(rebuilt, template, rebuilt_project)
    readback = load_project(rebuilt_project)
    for field in fields:
        equal(readback.as_dict().get(field), expected[field])
    observation = {"executed_routes": ["C++", "JSON", "SMBP/graph", "actual reverse", "recompiled SMBP"], "project_sha256": sha256(destination), "reverse_sha256": sha256(reverse), "runtime_or_editor_claim": "none"}
    return program, destination, reverse, observation


RTC_SOURCE = """
void scan(){
  plc::rtc_snapshot(100);
  plc::i16 hhmm=plc::read_system_word(51);
  plc::i16 mmdd=plc::read_system_word(52);
  plc::output(0,!plc::system(51) && mmdd>=0x1101 && mmdd<=0x1231 && hhmm>=0x1800 && hhmm<0x2300);
  if(plc::input(0)){
    plc::write_system(50,true);
    plc::write_system_word(50,0x0058);plc::write_system_word(51,0x1759);
    plc::write_system_word(52,0x1106);plc::write_system_word(53,0x2026);
    plc::write_system(50,false);
  }
  plc::output(1,plc::system(52));
}
"""


def _rtc_system_route(work):
    from m200.native_logic import decode
    from m200.flow import split_label

    program, project, reverse, observation = _static_routes(work, RTC_SOURCE, "rtc-system-route", fields=("rtcs", "schedules"))
    equal(getattr(program, "rtcs"), {})
    equal(getattr(program, "schedules"), {})
    source_lines = [line for rung in program.rungs for line in rung]
    require(not any("RTC_EXEC" in line for line in source_lines), "S/SW route accidentally depends on internal RTC opcode")
    for address in ("%SW49", "%SW50", "%SW51", "%SW52", "%SW53", "%S50", "%S51", "%S52"):
        require(any(address in line for line in source_lines), "documented native RTC service missing: " + address)
    tree = ET.parse(project)
    lines = [node.text or "" for node in tree.iter("InstructionLine")]
    require(not any("RTC_EXEC" in line for line in lines), "native file contains internal RTC opcode")
    for raw in program.rungs:
        decode(split_label(raw)[1])  # Only real supported native boolean/numeric grammar.
    require("write_system_word" in reverse.read_text() and "rtc_snapshot" not in reverse.read_text(), "actual scalar snapshot reverse was not reconstructed")
    return observation


SCHEDULE_SOURCE = """
plc::Schedule first{0,0,0,1,11,18,0,31,12,23,0,65};
plc::Schedule last{15,1,15,29,2,23,0,1,3,2,0,2};
bool marker=false;
void scan(){marker=plc::input(0);plc::output(0,marker);if(plc::input(1)){first.set_end_hour(22);plc::write_system_word(114,-1);}}
"""


def _schedule_config(work):
    from m200.model import CompileError

    program, project, _, observation = _static_routes(work, SCHEDULE_SOURCE, "schedule-config", fields=("schedules",))
    expected = {
        "0": {"output": "%M0", "start_day": 1, "start_month": 11, "start_hour": 18, "start_min": 0, "end_day": 31, "end_month": 12, "end_hour": 23, "end_min": 0, "dow": 65},
        "15": {"output": "%Q0.15", "start_day": 29, "start_month": 2, "start_hour": 23, "start_min": 0, "end_day": 1, "end_month": 3, "end_hour": 2, "end_min": 0, "dow": 2},
    }
    equal(program.as_dict()["schedules"], expected)
    require("marker" not in program.symbols.get("%M0", ""), "schedule output collided with compiler/global Boolean storage")
    tree = ET.parse(project)
    actual = {node.findtext("Index"): node for node in tree.findall("SoftwareConfiguration/ScheduleBlocks/ScheduleBlock")}
    equal(set(actual), {"0", "15"})
    equal(actual["0"].findtext("OutputBit"), "%M0")
    equal(actual["0"].findtext("StartDate"), "2012-11-01T18:00:00")
    equal(actual["0"].findtext("EndDate"), "2012-12-31T23:00:00")
    equal(actual["0"].findtext("Monday"), "true")
    equal(actual["0"].findtext("Sunday"), "true")
    equal(actual["0"].findtext("Tuesday", "false"), "false")
    equal(actual["15"].findtext("StartDate"), "2012-02-29T23:00:00")
    equal(actual["15"].findtext("Tuesday"), "true")
    for index, text in enumerate(("plc::Schedule s{16,0,0,1,1,0,0,31,12,23,59,127};void scan(){}", "plc::Schedule s{15,1,16,1,1,0,0,31,12,23,59,127};void scan(){}")):
        refused(lambda text=text, index=index: _compile(work, text, "schedule-limit-invalid-" + str(index)), CompileError, "schedule real bound after positive constructor control")
    observation["endpoint_and_lifecycle"] = "pending final official batch; no runtime timing oracle here"
    return observation


def _rtc_permissions(work):
    from m200.model import CompileError

    _, valid = _compile(work, "void scan(){plc::write_system(50,true);plc::write_system_word(50,0);plc::write_system_word(51,0x1200);plc::write_system_word(52,0x1106);plc::write_system_word(53,0x2026);plc::write_system(50,false);}", "permission-control")
    require(valid.rungs, "valid S50/SW write sibling missing")
    _, last_snapshot = _compile(work, "void scan(){plc::rtc_snapshot(7995);}", "snapshot-last-valid")
    require(last_snapshot.rungs, "last valid five-word RTC snapshot span missing")
    invalid = [
        "void scan(){plc::write_system(52,true);}",
        "void scan(){plc::write_system_word(49,1);}",
        "void scan(){plc::write_system_word(54,1);}",
        "void scan(){plc::rtc_snapshot(7996);}",
        "void scan(){plc::rtc_snapshot(-1);}",
    ]
    for index, text in enumerate(invalid):
        refused(lambda text=text, index=index: _compile(work, text, "permission-invalid-" + str(index)), CompileError)
    return {"valid_calendar_write_route": True, "invalid_permission_or_span_controls": len(invalid), "runtime_commit_atomicity": "not tested by static corpus"}


def _rtc_exec_gate(work):
    from m200.model import CompileError
    from m200.project import write_project

    _, program = _compile(work, "plc::Rtc c{1,29,2,2028,12,0,0};void scan(){c.update(true,plc::input(0),plc::input(1));}", "rtc-exec-internal")
    require(any("RTC_EXEC" in line for rung in program.rungs for line in rung), "internal RTC execution was silently omitted")
    output = work / "must-preserve.smbp"
    output.write_bytes(b"PREVIOUS DESTINATION\n")
    try:
        write_project(program, TEMPLATE, output)
    except CompileError as error:
        require("RTC_EXEC" in str(error) and ("binding" in str(error) or "pin order" in str(error)), "RTC export refused for unrelated reason: " + str(error))
    else:
        raise AssertionError("internal RTC_EXEC was emitted as unproven native IL")
    equal(output.read_bytes(), b"PREVIOUS DESTINATION\n")
    (work / "rtc-exec-gate-observation.json").write_text(json.dumps({"refusal_guard_verified": True, "RTC_EXEC_native_binding": "PENDING", "destination_preserved": True, "coverage_promotion": "none"}, indent=2) + "\n")
    raise PendingContract("RTC_EXEC native binding remains PENDING; explicit refusal and destination preservation verified, not native block support")


def _schedule_forged_xml(work):
    from m200.model import CompileError, Program
    from m200.project import load_project

    program, project, _, _ = _static_routes(work, SCHEDULE_SOURCE, "schedule-forgery-control", fields=("schedules",))
    for index, mutation in enumerate(("unknown", "duplicate", "inactive_payload", "bad_date", "wrong_output", "noncanonical_id", "bad_dow_boolean")):
        tree = ET.parse(project)
        node = tree.find("SoftwareConfiguration/ScheduleBlocks/ScheduleBlock")
        if mutation == "unknown":
            ET.SubElement(node, "HiddenCyclePolicy").text = "run"
        elif mutation == "duplicate":
            node.append(copy.deepcopy(node.find("Index")))
        elif mutation == "inactive_payload":
            node.find("Configured").text = "false"
        elif mutation == "bad_date":
            node.find("StartDate").text = "2012-02-30T18:00:00"
        elif mutation == "wrong_output":
            node.find("OutputBit").text = "%S52"
        elif mutation == "noncanonical_id":
            node.find("Index").text = "00"
        else:
            node.find("Monday").text = "True"
        path = work / ("schedule-forged-" + str(index) + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, mutation)
    data = program.as_dict()
    data["schedules"]["15"]["runtime_active"] = True
    refused(lambda: Program.from_dict(data), CompileError, "runtime state is not config")
    return {"forged_xml_controls": 7, "runtime_json_field_refused": True}


def _sequence_program():
    from m200.model import Program
    from m200.sequences import ShiftBitRegisterConfig, StepCounterConfig, DrumConfig, DrumCam

    return Program(
        [["BLK %SBR7", "LD %I0.0", "CU", "END_BLK"], ["BLK %SC6", "LD %I0.1", "CU", "END_BLK"], ["BLK %DR5", "LD %I0.2", "U", "OUT_BLK", "LD F", "ST %Q0.1", "END_BLK"]],
        shift_bit_registers={7: ShiftBitRegisterConfig()}, step_counters={6: StepCounterConfig()},
        drums={5: DrumConfig(3, [DrumCam(0, "%M0", 130), DrumCam(15, "%Q0.15", 4)])},
    )


def _sequence_canonical(work):
    fields = ("shift_bit_registers", "step_counters", "drums")
    body = "plc::ShiftBitRegister s{7};plc::StepCounter c{6};plc::Drum d{5,3,plc::DrumCam{0,plc::DrumOutput::Memory,0,130},plc::DrumCam{15,plc::DrumOutput::Output,15,4}};void scan(){s.update_pins(2,false,plc::input(0),false);c.update_pins(2,false,plc::input(1),false);d.update_pins(2,false,plc::input(2));}"
    source_program, _, _, cpp_observation = _static_routes(work, body, "sequence-cpp", fields=fields)
    expected = _sequence_program()
    for field in fields:
        equal(source_program.as_dict()[field], expected.as_dict()[field], field)
    program, project, reverse, raw_observation = _static_routes(work, None, "sequence-canonical", fields=fields, program=expected)
    tree = ET.parse(project)
    expectations = {
        "%SBR7": [("NormalContact", "%I0.0", "1", "0", "Left, Right"), ("ShiftBitRegister", "%SBR7", "0", "1", "Left")],
        "%SC6": [("NormalContact", "%I0.1", "1", "0", "Left, Right"), ("StepCounter", "%SC6", "0", "1", "Left")],
    }
    for rung in tree.iter("RungEntity"):
        block = next((line.text.split()[1] for line in rung.iter("InstructionLine") if (line.text or "").startswith("BLK ")), None)
        if block in expectations:
            actual = [(e.findtext("ElementType"), e.findtext("Descriptor", ""), e.findtext("Row"), e.findtext("Column"), e.findtext("ChosenConnection")) for e in rung.findall("LadderElements/LadderEntity")]
            equal(sorted(actual), sorted(expectations[block]), "canonical independent pin geometry")
    drum = tree.find("SoftwareConfiguration/Drums/Drum")
    equal(drum.findtext("StepsNumber"), "3")
    cams = drum.findall("Bits/BitForDrum")
    equal(len(cams), 16)
    equal(len(cams[0].findall("Steps/Step")), 8)
    equal(cams[0].findtext("Steps/Step[8]/Used"), "true", "inactive cam bit must remain config data")
    equal(cams[0].findtext("Steps/Step[8]/Available"), "false")
    require("update_pins(2," in reverse.read_text().replace(" ", ""), "reverse lost absent pin mask")
    return {"cpp": cpp_observation, "canonical_native": raw_observation, "new_native_graph_editor_acceptance": "pending"}


def _sequence_forged(work):
    from m200.model import CompileError
    from m200.project import load_project, write_project

    program = _sequence_program()
    project = work / "sequence-forgery-control.smbp"
    write_project(program, TEMPLATE, project)
    for index, mutation in enumerate(("unknown_config", "duplicate_config", "invalid_nil", "missing_symbol", "bad_cam_mask_shape", "wrong_descriptor", "wrong_pin_row", "wrong_port", "wrong_coil")):
        tree = ET.parse(project)
        if mutation == "unknown_config":
            ET.SubElement(tree.find("SoftwareConfiguration/StepCounters/StepCounter"), "HiddenStepRule").text = "advance"
        elif mutation == "duplicate_config":
            node = tree.find("SoftwareConfiguration/ShiftBitRegisters/ShiftBitRegister")
            node.append(copy.deepcopy(node.find("Index")))
        elif mutation == "invalid_nil":
            node = tree.find("SoftwareConfiguration/ShiftBitRegisters/ShiftBitRegister/BitSymbols/string")
            node.set("{http://www.w3.org/2001/XMLSchema-instance}nil", "false")
        elif mutation == "missing_symbol":
            node = tree.find("SoftwareConfiguration/StepCounters/StepCounter/StepSymbols")
            node.remove(list(node)[-1])
        elif mutation == "bad_cam_mask_shape":
            node = tree.find("SoftwareConfiguration/Drums/Drum/Bits/BitForDrum/Steps")
            node.remove(list(node)[-1])
        else:
            typ = "Drum" if mutation == "wrong_coil" else "ShiftBitRegister"
            rung = next(r for r in tree.iter("RungEntity") if any(e.findtext("ElementType") == typ for e in r.iter("LadderEntity")))
            entity = next(e for e in rung.iter("LadderEntity") if e.findtext("ElementType") == ("Coil" if mutation == "wrong_coil" else "NormalContact" if mutation == "wrong_pin_row" else typ))
            field, value = {"wrong_descriptor": ("Descriptor", "%SBR6"), "wrong_pin_row": ("Row", "0"), "wrong_port": ("ChosenConnection", "Right"), "wrong_coil": ("Descriptor", "%Q0.2")}[mutation]
            entity.find(field).text = value
        path = work / ("sequence-forged-" + str(index) + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, mutation)
    for count, accept in (("8", True), ("7", False)):
        tree = ET.parse(project)
        sw = tree.find("SoftwareConfiguration")
        node = sw.find("SbrsMemoryAllocation")
        if node is None:
            node = ET.SubElement(sw, "SbrsMemoryAllocation")
        node.clear()
        ET.SubElement(node, "Allocation").text = "Manual"
        ET.SubElement(node, "ForcedCount").text = count
        path = work / ("sparse-count-" + count + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        if accept:
            equal(load_project(path).shift_bit_registers, program.shift_bit_registers)
        else:
            refused(lambda path=path: load_project(path), CompileError, "sparseSBR7 requires8slots")
    return {"forged_controls": 9, "sparse_allocation_valid_sibling": 8, "insufficient_count_refused": 7}


SHARED_SOURCE = """
plc::ConstantMemory image{512};plc::ConstantDword shared{510,-2147483647};
plc::BooleanContext context{true,true};
void scan(){
  plc::write_system_word(17,0);plc::write_bit("%SW17:X2",true);
  plc::write_system_word(60,1);
  plc::output(0,plc::read_bit("%KW510:X0"));
  plc::output(1,plc::read_bit("%KW511:X15"));
  plc::output(2,plc::read_constant_word(511)==-32768);
  plc::output(3,plc::read_constant_dword(510)==-2147483647);
  plc::output(4,plc::read_system_word(17)==4);
  plc::output(5,plc::read_bit("%SW17:X2"));
  plc::output(6,plc::rising(0,plc::input(0)));
}
"""


def _shared_boolean_constants(work):
    program, project, reverse, observation = _static_routes(work, SHARED_SOURCE, "shared-boolean-constants", fields=("constants", "boolean"))
    equal(program.constants, {510: 1, 511: 32768}, "KW/KD raw image must be one shared512-word image")
    text = reverse.read_text()
    require("%KW511:X15" in text and "read_system_word(17)" in text and "write_system_word(60" in text, "reverse lost owner-specific Boolean/RTC/scalar dispatch")
    tree = ET.parse(project)
    require(any("%KW511:X15" in (node.text or "") for node in tree.iter("InstructionLine")), "shared KW bit was not emitted as a real native operand")
    return observation


def _boolean_permissions_and_graph(work):
    from m200.model import CompileError
    from m200.project import load_project, write_project

    body = "plc::BooleanContext context{true,true};void scan(){plc::output(0,plc::rising(31,plc::input(0)));}"
    program, project, _, observation = _static_routes(work, body, "native-edge", fields=("boolean",))
    tree = ET.parse(project)
    edge = next(e for e in tree.iter("LadderEntity") if e.findtext("ElementType") == "RisingEdgeBlock")
    equal(edge.findtext("Descriptor"), "31")
    equal(edge.findtext("Column"), "1")
    edge.find("Descriptor").text = "30"
    forged = work / "edge-forged.smbp"
    tree.write(forged, encoding="utf-8", xml_declaration=True)
    refused(lambda: load_project(forged), CompileError, "native edge identity must match actualIL")
    for index, text in enumerate(('plc::ConstantWord c{511,-32768};void scan(){plc::write_bit("%KW511:X15",true);}', 'void scan(){plc::write_bit("%MW0:X16",true);}', 'void scan(){plc::read_bit("%KW512:X0");}', 'void scan(){plc::write_bit("%S52",true);}', 'void scan(){plc::write_bit("%SW49:X0",true);}')):
        refused(lambda text=text, index=index: _compile(work, text, "boolean-invalid-" + str(index)), CompileError)
    for token, accept in (("FunctLevelMan11_0", True), ("FunctLevelMan10_0", False)):
        template = ET.parse(TEMPLATE)
        template.find("ManagementLevel").text = token
        path = work / (token + ".template.smbp")
        template.write(path, encoding="utf-8", xml_declaration=True)
        output = work / (token + ".smbp")
        if accept:
            write_project(program, path, output)
        else:
            refused(lambda: write_project(program, path, output), CompileError, "native edges beforeFL6")
    return {**observation, "readonly_and_bound_controls": 5, "graph_identity_refused": True, "native_edge_graph_editor_acceptance": "pending"}


def _sr_services_properties(work):
    from m200.communication_properties import has_buffer_writes

    body = """
plc::WordMemory words{8000};plc::ConstantMemory image{512};plc::ConstantDword shared{510,-2147483647};
plc::ReadVar sample{7,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};
void services(){sample.set_property(plc::CommProperty::IndexData,plc::read_word(0));sample.set_property(plc::CommProperty::Id,7);plc::write_system_word(60,1);plc::write_bit("%SW17:X2",true);plc::write_bit("%M5",plc::read_bit("%KW511:X15"));}
plc::Subroutine leaf{0,services,"services",2};
void scan(){leaf.call(plc::input(2));sample.update(plc::input(0),false);}
"""
    program, _, reverse, observation = _static_routes(work, body, "sr-services-properties", fields=("constants", "communications"), template=SERIAL)
    require(program.subroutines and has_buffer_writes(program), "SR property effects lost after provider integration")
    equal(program.constants, {510: 1, 511: 32768})
    text = reverse.read_text()
    equal(len(re.findall(r"plc::WordMemory\b", text)), 1)
    require("{8000}" in text, "SR dynamic buffer reverse lost full image ownership")
    lines = [line for definition in program.subroutines.values() for rung in definition.rungs for line in rung]
    for operand in ("%READ_VAR7.INDEXDATA", "%SW60", "%SW17:X2", "%KW511:X15"):
        require(any(operand in line for line in lines), "SR provider omitted actual native operand: " + operand)
    return observation


def _rtc_scalar_constants_sr(work):
    from m200.communication_properties import has_buffer_writes

    body = """
plc::WordMemory words{8000};plc::ConstantMemory image{512};plc::ConstantDword shared{510,-2147483647};
plc::ReadVar sample{7,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};
void services(){sample.set_property(plc::CommProperty::IndexData,plc::read_word(0));sample.set_property(plc::CommProperty::Id,7);plc::write_system_word(17,4);plc::write_system_word(60,1);plc::write_m(5,plc::read_constant_word(511)==-32768);}
plc::Subroutine leaf{0,services,"services",2};
void scan(){leaf.call(plc::input(2));sample.update(plc::input(0),false);}
"""
    program, _, reverse, observation = _static_routes(work, body, "rtc-scalar-constants-sr", fields=("constants", "communications"), template=SERIAL)
    equal(program.constants, {510: 1, 511: 32768})
    require(program.subroutines and has_buffer_writes(program), "SR buffer effects omitted during RTC/scalar composition")
    lines = [line for definition in program.subroutines.values() for rung in definition.rungs for line in rung]
    for operand in ("%READ_VAR7.INDEXDATA", "%SW17", "%SW60", "%KW511"):
        require(any(operand in line for line in lines), "actual SR operand lost: " + operand)
    text = reverse.read_text()
    equal(len(re.findall(r"plc::WordMemory\b", text)), 1)
    require("{8000}" in text, "dynamic buffer SR lost full image ownership")
    require("write_system_word(17," in text and "write_system_word(60," in text, "scalar/RTC system word dispatch collided")
    observation["G01_dependency"] = "none; uses G02 scalar words/constants and G09 RTC words only"
    return observation


def cases():
    return [Case(identity, lane, description, reference, run) for identity, lane, description, reference, run in [
        ("G09.static.system_route", "G09", "exportable RTC S/SW calendar route and scalar actual reverse", RTC_REF, _rtc_system_route),
        ("G09.static.schedule_config", "G09", "independent sparse schedule/date/DOW/output native configuration", RTC_REF, _schedule_config),
        ("G09.guard.permissions", "G09", "RTC word/bit permissions, snapshot span and schedule output domains", RTC_REF, _rtc_permissions),
        ("G09.pending.rtc_exec_unbound", "G09", "internalRTC_EXEC native binding remains PENDING even when refusal guard works", RTC_REF, _rtc_exec_gate),
        ("G09.guard.schedule_xml", "G09", "forged schedule XML/JSON refuses without silent loss", RTC_REF, _schedule_forged_xml),
        ("G08.static.canonical", "G08", "SBR/SC/DR partial pins, sparse config, inactive cams and canonical geometry", SEQ_REF, _sequence_canonical),
        ("G08.guard.xml_graph_allocation", "G08", "strict nil/vectors/config/graph fields and sparse allocation", SEQ_REF, _sequence_forged),
        ("G01.static.shared_images", "G01", "one G02 KW/KD image with G01 Boolean bits and G09/G02 SW dispatch", BOOL_REF, _shared_boolean_constants),
        ("G01.guard.permissions_graph", "G01", "native edge field/level controls and read-only/bounded bits", BOOL_REF, _boolean_permissions_and_graph),
        ("INTEROP.final.sr_services", "INTEROP", "SR property writes retain ownership plus shared RTC/Boolean/constants", BOOL_REF + "; " + RTC_REF, _sr_services_properties),
        ("INTEROP.rtc.scalar_constants_sr", "INTEROP", "RTC SW60/scalarSW17/constants/shared communication SR without G01", RTC_REF + "; G02/G06/G11 contracts", _rtc_scalar_constants_sr),
    ]]
