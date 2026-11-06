"""Independent static Timer interop controls, separate from runtime timing tests.

Documented admission and historical GUI observations are different predicates.
Synthetic graphs below prove local IL/port consistency only, never editor support.
"""

import copy
import json
import xml.etree.ElementTree as ET

from harness import Case, ROOT, equal, require, refused, sha256


REFERENCE = "EIO0000003289.04 pp103-104,107-119; EIO0000003281.04 pp49-50,55; EIO0000002019.06 pp24-26"
TEMPLATE = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
BASE_ENUM = {1: "OneMilliSeconds", 10: "TenMilliSeconds", 100: "OneHundredMilliSeconds", 1000: "OneSecond", 60000: None}


def _source(work, text, name):
    from m200.frontend import compile_source

    path = work / (name + ".cpp")
    path.write_text("#include <plc.hpp>\n" + text)
    return path, compile_source(path)


def _input_program(kind="TON", index=0, base=100, preset=2, ret=False, dyn=False):
    from m200.model import Program, Timer

    return Program([[f"BLK %TM{index}", "LD %I0.0", "IN", "END_BLK"]], timers={index: Timer(kind, base * preset, base, ret, dyn)})


def _template(work, token, name):
    tree = ET.parse(TEMPLATE)
    node = tree.find("ManagementLevel")
    if token is None:
        tree.getroot().remove(node)
    else:
        node.text = token
    path = work / (name + ".template.smbp")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def _all_static_modes(work):
    from m200.project import load_project, write_project
    from m200.model import Program
    from m200.reverse import to_cpp

    checked = []
    for ret, dyn in ((False, False), (False, True), (True, False), (True, True)):
        declarations, calls, expected = [], [], {}
        cursor = 20
        for kind, api, fast_index in (("TON", "Ton", 0), ("TOF", "Tof", 1), ("TP", "Pulse", 2)):
            if kind == "TP" and ret:
                continue
            for base in BASE_ENUM:
                index = fast_index if base == 1 else cursor
                cursor += base != 1
                name = "t" + str(index)
                declarations.append(f"plc::{api} {name}{{{index},{base},2,{str(ret).lower()},{str(dyn).lower()}}};")
                calls.append(name + ".execute(plc::input(0));")
                expected[str(index)] = {"kind": kind, "milliseconds": base * 2, "base_ms": base, "retentive": ret, "dynamic_preset": dyn}
        label = f"modes-{int(ret)}-{int(dyn)}"
        _, program = _source(work, "".join(declarations) + "void scan(){" + "".join(calls) + "}", label)
        equal(program.as_dict()["timers"], expected, "forward exact static configuration")
        equal(Program.from_dict(json.loads(json.dumps(program.as_dict()))).as_dict()["timers"], expected)
        destination = work / (label + ".smbp")
        write_project(program, TEMPLATE, destination)
        tree = ET.parse(destination)
        actual = {}
        for entry in tree.findall("SoftwareConfiguration/Timers/TimerTM"):
            key = entry.findtext("Index")
            cfg = expected[key]
            equal(entry.findtext("Address"), "%TM" + key)
            equal(entry.findtext("Type"), cfg["kind"])
            equal(entry.findtext("Preset"), "2")
            equal(entry.findtext("Base"), BASE_ENUM[cfg["base_ms"]], "minute base must be omitted, not guessed")
            equal(entry.findtext("IsRetentive"), str(ret).lower())
            equal(entry.findtext("IsDynamicPreset"), str(dyn).lower())
            actual[key] = cfg
        equal(actual, expected)
        restored = load_project(destination)
        equal(restored.as_dict()["timers"], expected)
        reverse_text = to_cpp(restored)
        require(".execute(" in reverse_text, "actual-IN reverse lost execute API")
        _, rebuilt = _source(work, reverse_text, label + "-reverse")
        equal(rebuilt.as_dict()["timers"], expected)
        checked.append({"retentive": ret, "dynamic": dyn, "configurations": len(expected), "project_sha256": sha256(destination)})
    equal(sum(row["configurations"] for row in checked), 50)
    return {"static_configurations": 50, "groups": checked, "native_editor": "not_run"}


def _feature_levels(work):
    from m200.model import CompileError
    from m200.project import load_project, write_project

    cases = [
        ("TON", True, False, "FunctLevelMan7_0", True),
        ("TOF", True, False, "FunctLevelMan7_0", True),
        ("TON", True, False, "FunctLevelMan6_0", False),
        ("TON", False, True, "FunctLevelMan18_0", True),
        ("TOF", False, True, "FunctLevelMan18_0", True),
        ("TP", False, True, "FunctLevelMan18_0", True),
        ("TON", True, True, "FunctLevelMan18_0", True),
        ("TOF", True, True, "FunctLevelMan18_0", True),
        ("TON", False, True, "FunctLevelMan17_0", False),
        ("TP", False, True, "FunctLevelMan17_0", False),
        ("TON", True, False, "FunctLevelMan999_0", False),
        ("TON", True, False, None, False),
    ]
    observed = []
    for position, (kind, ret, dyn, level, admitted) in enumerate(cases):
        program = _input_program(kind=kind, base=10, ret=ret, dyn=dyn)
        program.metadata["functional_level"] = "FunctLevelMan21_0"  # Cannot override actual template.
        template = _template(work, level, f"level-{position}")
        output = work / f"level-{position}.smbp"
        if admitted:
            write_project(program, template, output)
            equal(load_project(output).timers, program.timers)
        else:
            output.write_bytes(b"PRESERVE PREVIOUS\n")
            refused(lambda: write_project(program, template, output), CompileError, str((kind, level)))
            equal(output.read_bytes(), b"PRESERVE PREVIOUS\n")
        observed.append({"kind": kind, "retentive": ret, "dynamic": dyn, "actual_level": level, "admitted": admitted})
    return {"level_controls": observed, "retention_3_3_note": "conservative documented conflict; not a proved PLC impossibility"}


def _evidence_is_separate(work):
    from m200.model import Timer
    from m200.timer_profile import OPTION_CONTEXTS, evidence_context

    expected = {
        ("TON", True, False, 1000, "FunctLevelMan21_0"),
        ("TOF", True, False, 1000, "FunctLevelMan21_0"),
        ("TON", False, True, 1000, "FunctLevelMan21_0"),
    }
    equal(set(OPTION_CONTEXTS), expected)
    for kind, ret, dyn, base, level in expected:
        equal(evidence_context(Timer(kind, base * 2, base, ret, dyn), level), "observed_subset")
    for kind, ret, dyn, base, level in [("TP", False, True, 10, "FunctLevelMan21_0"), ("TON", True, True, 1000, "FunctLevelMan21_0"), ("TOF", True, False, 1000, "FunctLevelMan7_0")]:
        equal(evidence_context(Timer(kind, base * 2, base, ret, dyn), level), "unverified_combination")
    return {"historical_observed_contexts": len(expected), "new_combinations_observed": False}


def _real_limits_and_permissions(work):
    from m200.model import CompileError, Program, Timer
    from m200.il import validate
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    for index, base, preset in [(5, 1, 0), (254, 60000, 9999)]:
        program = _input_program(index=index, base=base, preset=preset)
        destination = work / f"valid-{index}.smbp"
        write_project(program, TEMPLATE, destination)
        equal(load_project(destination).timers, program.timers)
        _, rebuilt = _source(work, to_cpp(load_project(destination)), f"boundary-{index}")
        equal(rebuilt.timers, program.timers)
    for program in [
        _input_program(index=255), _input_program(index=6, base=1),
        _input_program(preset=-1), _input_program(preset=10000),
        _input_program(base=7), _input_program(kind="TP", ret=True),
        _input_program(ret=1), _input_program(dyn="false"),
        Program([["LD 1", "[%TM0.V:=1]"]], timers={0: Timer("TON", 100, 100)}),
        Program([["LD 1", "ST %TM0.Q"]], timers={0: Timer("TON", 100, 100)}),
        Program([["BLK %TM0", "LD %I0.0", "IN", "IN", "END_BLK"]], timers={0: Timer("TON", 100, 100)}),
    ]:
        refused(lambda program=program: validate(program), CompileError, repr(program.as_dict()))
    return {"last_1ms_id": 5, "last_timer_id": 254, "max_preset": 9999, "invalid_controls": 11}


def _forged_configuration(work):
    from m200.model import CompileError
    from m200.project import load_project, write_project

    original = work / "config-control.smbp"
    write_project(_input_program(base=1), TEMPLATE, original)
    mutations = [("Index", "00"), ("Address", "%TM255"), ("Base", "InventedTimerUnit"), ("Preset", "-1"), ("Preset", "10000"), ("Preset", "001"), ("IsRetentive", "True"), ("IsDynamicPreset", " false")]
    for position, (field, value) in enumerate(mutations):
        tree = ET.parse(original)
        node = tree.find("SoftwareConfiguration/Timers/TimerTM/" + field)
        node.text = value
        path = work / f"config-mutant-{position}.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, field + "=" + value)
    for position, mutation in enumerate(("unknown", "duplicate", "retentive_tp")):
        tree = ET.parse(original)
        timer = tree.find("SoftwareConfiguration/Timers/TimerTM")
        if mutation == "unknown":
            ET.SubElement(timer, "HiddenTimerAction").text = "execute"
        elif mutation == "duplicate":
            timer.append(copy.deepcopy(timer.find("Preset")))
        else:
            timer.find("Type").text = "TP"
            timer.find("IsRetentive").text = "true"
        path = work / f"config-extra-{position}.smbp"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, mutation)
    return {"forged_configs_refused": len(mutations) + 3}


def _forged_graph(work):
    from m200.model import CompileError
    from m200.project import load_project, write_project

    original = work / "graph-control.smbp"
    write_project(_input_program(), TEMPLATE, original)
    for position, mutation in enumerate(("target", "input", "port", "body_overlap", "unknown", "duplicate", "unpaired")):
        tree = ET.parse(original)
        graph = tree.find("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity/LadderElements")
        timer = next(e for e in graph if e.findtext("ElementType") == "Timer")
        contact = next(e for e in graph if e.findtext("ElementType") == "NormalContact")
        if mutation == "target":
            timer.find("Descriptor").text = "%TM1"
        elif mutation == "input":
            contact.find("Descriptor").text = "%I0.1"
        elif mutation == "port":
            timer.find("ChosenConnection").text = "Right"
        elif mutation == "body_overlap":
            contact.find("Column").text = timer.findtext("Column")
        elif mutation == "unknown":
            ET.SubElement(timer, "UnboundPort").text = "RUN"
        elif mutation == "duplicate":
            timer.append(copy.deepcopy(timer.find("ChosenConnection")))
        else:
            dangling = copy.deepcopy(contact)
            dangling.find("Row").text = "8"
            dangling.find("Column").text = "6"
            graph.append(dangling)
        path = work / ("graph-mutant-" + str(position) + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        refused(lambda path=path: load_project(path), CompileError, mutation)
    return {"forged_graphs_refused": 7, "native_editor": "not_run"}


def _input_only_repeated_sites(work):
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp
    from m200.native_logic import decode
    from m200.flow import split_label

    source = "plc::Ton t{254,60000,9999};void scan(){t.execute(plc::input(0));t.execute(plc::input(1));}"
    _, program = _source(work, source, "input-only")
    equal(set(program.timers), {254})
    instructions = [instruction for rung in program.rungs for instruction in decode(split_label(rung)[1])]
    equal(sum(op == "IN" and arg == "%TM254" for op, arg in instructions), 2)
    require(not any("%TM254.Q" in arg for _, arg in instructions), "execute generated an unwanted Q read")
    destination = work / "input-only.smbp"
    write_project(program, TEMPLATE, destination)
    tree = ET.parse(destination)
    elements = list(tree.iter("LadderEntity"))
    equal(sum(e.findtext("ElementType") == "Timer" for e in elements), 2)
    timer_rungs = [rung for rung in tree.iter("RungEntity") if any(e.findtext("ElementType") == "Timer" for e in rung.iter("LadderEntity"))]
    require(not any(e.findtext("ElementType") in ("Coil", "SetCoil", "ResetCoil") for rung in timer_rungs for e in rung.iter("LadderEntity")), "input-only Timer rung fabricated a wired Q/result coil")
    imported = load_project(destination)
    text = to_cpp(imported)
    require(text.count(".execute(") == 2 and ".update(" not in text, "reverse changed input-only update sites")
    _, rebuilt = _source(work, text, "input-only-reverse")
    equal(rebuilt.timers, program.timers)
    return {"native_identity_count": 1, "ordered_IN_sites": 2, "wired_Q_or_result_coils": 0, "separate_IN_capture_coils": sum(e.findtext("ElementType") == "Coil" for e in elements)}


def _output_actions_actual_reverse(work):
    from m200.model import Program, Timer
    from m200.il import Machine
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp
    from m200.native import run_native

    program = Program([
        ["LD 1", "ST %M1"],
        ["BLK %TM0", "LD %I0.0", "IN", "OUT_BLK", "LD Q", "ST %Q0.0", "STN %Q0.1", "S %M0", "R %M1", "END_BLK"],
        ["LD %M0", "ST %Q0.2"], ["LD %M1", "ST %Q0.3"],
    ], timers={0: Timer("TON", 0, 10)})
    destination = work / "output-actions.smbp"
    write_project(program, TEMPLATE, destination)
    restored = load_project(destination)
    text = to_cpp(restored)
    source, rebuilt = _source(work, text, "output-actions-reverse")
    frames = [{"inputs": {0: value}} for value in (False, True, False)]
    expected = [[False, True, False, True], [True, False, True, False], [False, True, True, True]]
    for candidate in (program, restored, rebuilt):
        machine = Machine(candidate)
        equal([machine.step(frame["inputs"])[:4] for frame in frames], expected)
    equal([row[:4] for row in run_native(source, frames)], expected)
    return {"literal_zero_preset_rows": expected, "static_actions": ["ST", "STN", "S", "R"], "timing_claim": "none"}


def _multi_timer_graph_level_and_identity(work):
    from m200.model import CompileError, Program, Timer
    from m200.project import load_project, write_project

    program = Program([
        ["BLK %TM0", "LD %I0.0", "IN", "END_BLK"],
        ["BLK %TM1", "LD %I0.1", "IN", "END_BLK"],
    ], timers={0: Timer("TON", 100, 100), 1: Timer("TOF", 100, 100)})
    generated = work / "two-separate.smbp"
    write_project(program, TEMPLATE, generated)
    control = ET.parse(generated)
    rungs = control.find("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs")
    first, second = list(rungs)
    graph = first.find("LadderElements")
    for entry in second.find("LadderElements"):
        entry = copy.deepcopy(entry)
        entry.find("Row").text = str(int(entry.findtext("Row")) + 1)
        graph.append(entry)
    instructions = first.find("InstructionLines")
    instructions.clear()
    lines = ["LD %I0.0", "IN %TM0", "LD %I0.1", "IN %TM1"]
    for line in lines:
        entry = ET.SubElement(instructions, "InstructionLineEntity")
        ET.SubElement(entry, "InstructionLine").text = line
        ET.SubElement(entry, "Comment")
    rungs.remove(second)
    for level, accept in (("FunctLevelMan15_0", True), ("FunctLevelMan14_0", False)):
        tree = copy.deepcopy(control)
        tree.find("ManagementLevel").text = level
        path = work / ("two-" + level + ".smbp")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        if accept:
            equal(load_project(path).timers, program.timers)
        else:
            refused(lambda path=path: load_project(path), CompileError, "multiple Timer actualFL<10.1")
    control.find("ManagementLevel").text = "FunctLevelMan15_0"
    instruction_lines = control.findall("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity/InstructionLines/InstructionLineEntity/InstructionLine")
    instruction_lines[1].text = "IN %TM1"
    instruction_lines[3].text = "IN %TM0"
    forged = work / "two-swapped-identities.smbp"
    control.write(forged, encoding="utf-8", xml_declaration=True)
    refused(lambda: load_project(forged), CompileError, "graph IN identities swapped against conditions")
    return {"synthetic_two_timer_graph": "local consistency accepted at10.1, refused at10.0", "forged_swapped_inputs_refused": True, "official_editor": "not_run"}


def cases():
    return [Case("G07.static." + suffix, "G07", description, REFERENCE, run) for suffix, description, run in [
        ("all_modes", "50 allowed type/base/flag configurations preserve XML/JSON/actual reverse", _all_static_modes),
        ("feature_levels", "documented actual feature levels admit new combinations; metadata cannot override", _feature_levels),
        ("observation_scope", "three historical observed contexts stay separate from admission", _evidence_is_separate),
        ("real_limits", "actual Timer ID/base/preset boundaries and read-only fields", _real_limits_and_permissions),
        ("forged_configuration", "malformed/duplicate/unknown timer config is refused", _forged_configuration),
        ("forged_graph", "mismatched pins/identities/ports and unpaired native graph cells refuse", _forged_graph),
        ("input_only_sites", "repeated input-only sites retain one timer without fake Q/coil wiring", _input_only_repeated_sites),
        ("output_actions", "actual reverse preserves ST/STN/S/R order at zero preset", _output_actions_actual_reverse),
        ("multi_graph", "actual10.1 multi-block level and per-input timer identity agreement", _multi_timer_graph_level_and_identity),
    ]]
