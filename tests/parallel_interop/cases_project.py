"""Actual-program reverse, native graph/config, atomicity and forged-input cases."""

import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from harness import Case, ROOT, equal, require, refused, sha256


FIXTURES = ROOT / "tests/fixtures"
MEMORY = FIXTURES / "official_tm200ce40t_memory.smbp"
SERIAL = FIXTURES / "official_tm200ce40t_modbus_bare_abort_read.smbp"
PARITY = "docs/PARITY.md: actual-IL reverse, semantic/config identity, unknown refusal, native graphics"


def _compile(work, source, name="source.cpp"):
    from m200.frontend import compile_source

    path = work / name
    path.write_text("#include <plc.hpp>\n" + source)
    return path, compile_source(path)


def _rows(program, frames):
    from m200.il import Machine

    machine = Machine(program)
    return [machine.step(frame.get("inputs", {}), frame.get("dt_ms", 10)) for frame in frames]


def _literal_rows(rows):
    return [list(row) + [False] * (16 - len(row)) for row in rows]


def _all_routes(work):
    from m200.model import Program
    from m200.native import run_native
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp
    from m200.frontend import compile_source

    source, program = _compile(work, """
plc::ReadVar read{7,plc::Link::Serial1,1,5,plc::Object::DiscreteInputs,0,1,7999};
void scan(){
  bool done=read.update(plc::input(0),plc::input(1));
  plc::output(0,done);plc::output(1,read.busy());plc::output(2,read.error());
  plc::output(3,read.comm_error()==255 && read.oper_error()==15);
}
""")
    frames = [{"inputs": {0: value}} for value in (True, False, True, True, False)]
    expected = _literal_rows([(0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 1, 1), (0, 0, 1, 1), (0, 0, 0, 0)])
    equal(set(program.communications), {"%READ_VAR7"})
    cfg = program.communications["%READ_VAR7"]
    equal([cfg.kind, cfg.link, cfg.id, cfg.timeout_100ms, cfg.obj_type, cfg.first_obj, cfg.quantity, cfg.index_data], ["READ_VAR", "SL1", 1, 5, 1, 0, 1, 7999])
    equal(_rows(program, frames), expected, "forward VM literal no-channel policy")
    equal(run_native(source, frames), expected, "forward native SDK literal no-channel policy")
    decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    equal(decoded.communications, program.communications)
    equal(_rows(decoded, frames), expected)
    template_before = SERIAL.read_bytes()
    destination = work / "generated.smbp"
    write_project(program, SERIAL, destination)
    equal(SERIAL.read_bytes(), template_before, "template must remain byte-identical")
    original_xml, generated_xml = ET.parse(SERIAL), ET.parse(destination)
    equal(ET.tostring(generated_xml.find("HardwareConfiguration")), ET.tostring(original_xml.find("HardwareConfiguration")))
    require(any(entry.findtext("ElementType") == "ReadVarBasic" for entry in generated_xml.iter("LadderEntity")), "generated project lacks a native communication graph")
    equal(generated_xml.findtext("SoftwareConfiguration/MemoryWordsMemoryAllocation/ForcedCount"), "8000")
    imported = load_project(destination)
    equal(imported.communications, program.communications)
    equal(_rows(imported, frames), expected)
    # Deliberately forged source-like metadata must not replace actual IL.
    imported.metadata["original_cpp"] = "plc::output(0,true); /* forged metadata */"
    reverse = work / "reverse.cpp"
    reverse.write_text(to_cpp(imported))
    require("forged metadata" not in reverse.read_text(), "reverse trusted an embedded source instead of IL")
    equal(run_native(reverse, frames), expected)
    rebuilt = compile_source(reverse)
    equal(rebuilt.communications, program.communications)
    equal(_rows(rebuilt, frames), expected)
    rewritten = work / "rewritten.smbp"
    write_project(rebuilt, SERIAL, rewritten)
    equal(_rows(load_project(rewritten), frames), expected)
    return {"literal_rows": expected, "generated_sha256": sha256(destination), "reverse_sha256": sha256(reverse), "scope": "error lifecycle only; no transport/native-device transaction claim"}


def _register_config_and_graph(work):
    from m200.project import load_project, write_project
    from m200.registers import RegisterConfig
    from m200.frontend import compile_source
    from m200.reverse import to_cpp
    from m200.native import run_native

    source, program = _compile(work, """
plc::Fifo fifo{0};plc::Lifo lifo{3};
void scan(){
  fifo.set_input(-32768);lifo.set_input(32767);
  fifo.update(plc::input(0),plc::input(1),plc::input(2));
  lifo.update(plc::input(0),plc::input(1),plc::input(2));
  plc::output(0,fifo.empty());plc::output(1,lifo.empty());
  plc::output(2,fifo.output()==-32768);plc::output(3,lifo.output()==32767);
}
""")
    frames = [{"inputs": value} for value in ({0: True}, {}, {1: True}, {}, {2: True})]
    expected = _literal_rows([(1, 1, 0, 0), (1, 1, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (1, 1, 1, 1)])
    equal(program.registers, {0: RegisterConfig("Fifo"), 3: RegisterConfig("Lifo")})
    equal(_rows(program, frames), expected)
    equal(run_native(source, frames), expected)
    destination = work / "registers.smbp"
    write_project(program, MEMORY, destination)
    root = ET.parse(destination)
    configs = [(entry.findtext("Address"), entry.findtext("Index"), entry.findtext("Type")) for entry in root.findall("SoftwareConfiguration/Registers/Register")]
    equal(configs, [("%R0", "0", "Fifo"), ("%R3", "3", "Lifo")])
    equal(sum(entry.findtext("ElementType") == "Register" for entry in root.iter("LadderEntity")), 2)
    imported = load_project(destination)
    equal(imported.registers, program.registers)
    equal(_rows(imported, frames), expected)
    reverse = work / "registers.reverse.cpp"
    reverse.write_text(to_cpp(imported))
    equal(_rows(compile_source(reverse), frames), expected)
    equal(run_native(reverse, frames), expected)
    return {"configs": configs, "literal_rows": expected, "project_sha256": sha256(destination)}


def _forged_graph(work):
    from m200.model import CompileError
    from m200.project import load_project

    fixture = FIXTURES / "official_tm200ce40t_register_fifo_three_ld.smbp"
    mutants = []
    for field, text in [("Descriptor", "%R3"), ("ChosenConnection", "Left, Right"), ("Column", "2"), ("ElementType", "Timer")]:
        tree = ET.parse(fixture)
        register = next(entry for entry in tree.iter("LadderEntity") if entry.findtext("ElementType") == "Register")
        register.find(field).text = text
        path = work / (field + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, field)
        mutants.append(field)
    return {"rejected_graph_mutants": mutants}


def _unknown_and_duplicates(work):
    from m200.model import CompileError
    from m200.project import load_project

    mutations = [
        ("unknown_software", lambda tree: ET.SubElement(tree.find("SoftwareConfiguration"), "UnboundExpertMode")),
        ("unknown_root", lambda tree: ET.SubElement(tree.getroot(), "OpaqueExecutableProgram")),
        ("duplicate_task", lambda tree: tree.find("SoftwareConfiguration").append(copy.deepcopy(tree.find("SoftwareConfiguration/MastTask")))),
        ("unknown_task_field", lambda tree: ET.SubElement(tree.find("SoftwareConfiguration/MastTask"), "ExecuteAfterStop")),
        ("unknown_master_mode", lambda tree: setattr(tree.find("SoftwareConfiguration/MastTask/UsePeriodScanMode"), "text", "UnknownScanPolicy")),
        ("other_cpu", lambda tree: setattr(tree.find("HardwareConfiguration/Plc/Cpu/Reference"), "text", "TM200CE40R")),
    ]
    for name, mutate in mutations:
        tree = ET.parse(MEMORY)
        mutate(tree)
        path = work / (name + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, name)
    return {"refused_mutants": [name for name, _ in mutations]}


def _atomic_refusal(work):
    from m200.model import CompileError, Program
    from m200.project import write_project
    from m200.registers import RegisterConfig

    invalid_template = work / "unknown-template.smbp"
    tree = ET.parse(MEMORY)
    ET.SubElement(tree.find("SoftwareConfiguration"), "UnknownOwnedPayload").text = "must not disappear"
    tree.write(invalid_template, encoding="utf-8", xml_declaration=True)
    destination = work / "previous.smbp"
    previous = b"PREVIOUS USER DESTINATION\n"
    destination.write_bytes(previous)
    template_before = invalid_template.read_bytes()
    program = Program(registers={3: RegisterConfig("Lifo")})
    refused(lambda: write_project(program, invalid_template, destination), CompileError, "unknown template field")
    equal(destination.read_bytes(), previous)
    equal(invalid_template.read_bytes(), template_before)
    refused(lambda: write_project(program, MEMORY, MEMORY), CompileError, "template and output same path")
    require(not list(work.glob(".m200-candidate-*")), "failed candidate left temporary directories")
    return {"previous_destination_sha256": sha256(destination), "template_preserved": True}


def _manual_allocation_and_profile(work):
    from m200.model import CompileError, Program
    from m200.project import load_project, write_project
    from m200.registers import RegisterConfig

    destination = work / "valid.smbp"
    write_project(Program(registers={3: RegisterConfig("Lifo")}), MEMORY, destination)
    for value, should_accept in [("4", True), ("3", False), ("0", False), ("5", False), ("04", False)]:
        tree = ET.parse(destination)
        allocation = tree.find("SoftwareConfiguration/RegistersMemoryAllocation")
        allocation.find("Allocation").text = "Manual"
        ET.SubElement(allocation, "ForcedCount").text = value
        path = work / ("count-" + value + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        if should_accept:
            equal(load_project(path).registers, {3: RegisterConfig("Lifo")})
        else:
            refused(lambda path=path: load_project(path), CompileError, "ForcedCount=" + value)
    for path, value in [("ManagementLevel", "FunctLevelMan20_0"), ("HardwareConfiguration/Plc/Cpu/TechnicalConfiguration/LfRegistersMax", "5")]:
        tree = ET.parse(destination)
        tree.find(path).text = value
        mutant = work / (path.rsplit("/", 1)[-1] + ".smbp")
        tree.write(mutant, encoding="utf-8", xml_declaration=True)
        refused(lambda mutant=mutant: load_project(mutant), CompileError, path)
    return {"valid_sparse_r3_count": 4, "refused_counts": [3, 0, 5, "04"]}


def _communication_unknown_fields(work):
    from m200.model import CompileError, Program
    from m200.project import load_project

    tree = ET.parse(SERIAL)
    block = tree.find("SoftwareConfiguration/FunctionBlocks/IFunctionBlock")
    require(block is not None, "authentic communication fixture lost its block")
    ET.SubElement(block, "UnboundTransactionPolicy").text = "RetryForever"
    path = work / "unknown-comm-field.smbp"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    refused(lambda: load_project(path), CompileError, "unknown native FB policy")
    program = load_project(SERIAL)
    data = program.as_dict()
    key = next(iter(data["communications"]))
    data["communications"][key]["unknown_retry_policy"] = 7
    before = copy.deepcopy(data)
    refused(lambda: Program.from_dict(data), (CompileError, ValueError), "unknown JSON communication field")
    equal(data, before, "failed decoding must not mutate caller configuration")
    return {"unknown_xml_and_json_refused": True}


def cases():
    return [
        Case("G11.project.all_routes", "G11", "sparse communication ID, real graph/config, literal VM/native/reverse errors", PARITY, _all_routes),
        Case("INTEROP.register.config_graph", "INTEROP", "mixed native modes/sparse identity and signed words across actual routes", PARITY, _register_config_and_graph),
        Case("INTEROP.refusal.forged_graph", "INTEROP", "native graph identity/pins cannot disagree with actual IL", PARITY, _forged_graph),
        Case("INTEROP.refusal.unknown_fields", "INTEROP", "unknown/duplicate task, root and profile fields fail explicitly", PARITY, _unknown_and_duplicates),
        Case("INTEROP.refusal.atomic_destination", "INTEROP", "failed export preserves destination/template and removes candidates", PARITY, _atomic_refusal),
        Case("INTEROP.bounds.sparse_allocation", "INTEROP", "sparse resource allocation and exact target-profile boundaries", PARITY, _manual_allocation_and_profile),
        Case("G11.refusal.unknown_config", "G11", "unknown communication XML/JSON is refused without caller mutation", PARITY, _communication_unknown_fields),
    ]
