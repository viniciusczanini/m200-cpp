"""Packed-write interop controls for immutable literals and mutable snapshots."""

import json
import re

from harness import Case, ROOT, equal, require, sha256


REFERENCE = "EIO0000003289.04 bit-string assignment/word widths; natal-combined-1b confirmed packed-reset reverse repro"
TEMPLATE = ROOT / "tests/fixtures/official_tm200ce40t_memory.smbp"
SERIAL = ROOT / "tests/fixtures/official_tm200ce40t_modbus_bare_abort_read.smbp"


def _routes(work, body, label, expected_mask, template=TEMPLATE, full_bank=False, snapshot_target=None, snapshot_source=None):
    from m200.frontend import compile_source
    from m200.il import Machine
    from m200.model import Program
    from m200.native import run_native
    from m200.numeric import instruction_operation, is_operation
    from m200.project import load_project, write_project
    from m200.reverse import to_cpp

    source = work / (label + ".cpp")
    source.write_text("#include <plc.hpp>\n" + body)
    program = compile_source(source)
    if full_bank:
        equal(program.metadata["allocation"]["allocated_words"], 0, "immutable packed literal must fit without scratch MW")
    if snapshot_target:
        copies = [instruction_operation(line) for rung in program.rungs for line in rung if is_operation(line)]
        values = [arguments[0].code for target, operation, arguments in copies if target == snapshot_target and operation == "copy"]
        require(values and any(re.fullmatch(r"%M[WD][0-9]+", value) for value in values), "mutable/overlapping packed source lost its private word snapshot: " + repr(values))
        require(any(target in values and target != snapshot_source and operation == "copy" and arguments[0].code == snapshot_source for target, operation, arguments in copies), "packed source was not captured before its write: " + repr(copies))
    frames = [{}, {}]
    expected = [[bool(expected_mask & (1 << index)) for index in range(16)]] * 2

    def observe(candidate):
        machine = Machine(candidate)
        return [machine.step({}) for _ in frames]

    equal(observe(program), expected, "forward VM literal mask")
    equal(run_native(source, frames), expected, "forward SDK literal mask")
    decoded = Program.from_dict(json.loads(json.dumps(program.as_dict())))
    equal(observe(decoded), expected)
    before = template.read_bytes()
    destination = work / (label + ".smbp")
    write_project(program, template, destination)
    equal(template.read_bytes(), before)
    restored = load_project(destination)
    equal(observe(restored), expected, "native XML readback mask")
    reverse = work / (label + "-reverse.cpp")
    reverse.write_text(to_cpp(restored))
    rebuilt = compile_source(reverse)
    if full_bank:
        equal(rebuilt.metadata["allocation"]["allocated_words"], 0, "actual reverse of immutable literal added scratch MW")
    equal(observe(rebuilt), expected, "actual reverse recompile mask")
    equal(run_native(reverse, frames), expected, "actual reverse SDK mask")
    second = work / (label + "-rebuilt.smbp")
    write_project(rebuilt, template, second)
    equal(observe(load_project(second)), expected)
    return {"literal_mask": expected_mask, "frames": 2, "forward_vm_sdk_json_native_project_actual_reverse_rebuilt_project": "PASS", "original_sha256": sha256(source), "project_sha256": sha256(destination), "reverse_sha256": sha256(reverse)}


def _reset_repro(work):
    body = "plc::WordMemory image{8000};plc::ReadVar r{plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};void scan(){r.set_property(plc::CommProperty::IndexData,100);r.update(plc::input(0),false);plc::output(0,r.done());plc::output(1,r.busy());}"
    result = _routes(work, body, "packed-reset-repro", 0, template=SERIAL, full_bank=True)
    result["scope"] = "no-transport idle/error policy only; no positive native transaction claimed"
    return result


def _literal_word_full_bank(work):
    return _routes(work, "plc::WordMemory all{8000};void scan(){plc::write_output_bits_i16(0,16,-32767);}", "literal-word-full-bank", 32769, full_bank=True)


def _literal_dword_full_bank(work):
    body = "plc::WordMemory all{8000};void scan(){plc::write_m_bits_i32(992,32,-2147483647);plc::output(0,plc::read_m(992));plc::output(1,plc::read_m(1023));plc::output(2,!plc::read_m(993));plc::output(3,!plc::read_m(1022));}"
    return _routes(work, body, "literal-dword-full-bank", 15, full_bank=True)


def _mutable_words(work):
    word = "void scan(){plc::write_word(0,21930);plc::write_m_bits_i16(16,16,plc::read_word(0));plc::write_word(0,0);plc::output(0,plc::read_m_bits_i16(16,16)==21930);plc::output(1,plc::read_word(0)==0);}"
    dword = "void scan(){plc::write_dword(0,305419896);plc::write_m_bits_i32(0,32,plc::read_dword(0));plc::write_dword(0,-1);plc::output(0,plc::read_m_bits_i32(0,32)==305419896);plc::output(1,plc::read_dword(0)==-1);}"
    return {"word": _routes(work, word, "mutable-word", 3, snapshot_target="%M16:16", snapshot_source="%MW0"), "dword": _routes(work, dword, "mutable-dword", 3, snapshot_target="%M0:32", snapshot_source="%MD0")}


def _overlapping_views(work):
    word = "void scan(){plc::write_m_bits_i16(0,16,-23206);plc::write_m_bits_i16(8,16,plc::read_m_bits_i16(0,16));plc::output(0,plc::read_m_bits_i16(8,16)==-23206);plc::output(1,plc::read_m_bits_i16(0,8)==90);}"
    dword = "void scan(){plc::write_m_bits_i32(0,32,305419896);plc::write_m_bits_i32(8,24,plc::read_m_bits_i32(0,24));plc::output(0,plc::read_m_bits_i32(8,24)==3430008);plc::output(1,plc::read_m_bits_i16(0,8)==120);}"
    return {"word_overlap": _routes(work, word, "overlap-word", 3, snapshot_target="%M8:16", snapshot_source="%M0:16"), "dword_overlap": _routes(work, dword, "overlap-dword", 3, snapshot_target="%M8:24", snapshot_source="%M0:24")}


def _literal_carrier_widths(work):
    results = []
    # Literal expected masks: Q0=first target bit, Q1=last target bit;
    # Q2/Q3 are the neighboring memory bits that the write must preserve.
    for width, value, mask in [(16, 65535, 15), (16, 65536, 12), (16, -32769, 13), (17, 65536, 14), (17, 131071, 15), (17, -1, 15), (32, -2147483647, 15), (32, 2147483647, 13)]:
        end = 104 + width
        body = f"plc::WordMemory all{{8000}};void scan(){{plc::write_m(103,true);plc::write_m({end},true);plc::write_m_bits_i32(104,{width},{value});plc::output(0,plc::read_m(104));plc::output(1,plc::read_m({end-1}));plc::output(2,plc::read_m(103));plc::output(3,plc::read_m({end}));}}"
        result = _routes(work, body, f"literal-width-{width}-{value}", mask, full_bank=True)
        results.append({"width": width, "i32_literal": value, **result})
    return {"carrier_controls": results, "scratch_MW_in_original_and_reverse": 0}


def _drum_set_step_repro(work):
    body = "plc::Drum d{0,3};void scan(){d.set_step(2);d.update(false,false);plc::output(0,d.step()==2);}"
    return _routes(work, body, "drum-set-step", 1)


def cases():
    result = [Case("INTEROP.packed." + suffix, "INTEROP", description, REFERENCE, run) for suffix, description, run in [
        ("reset_repro", "full-bank dynamic-buffer output reset reverse recompiles", _reset_repro),
        ("literal_word_full_bank", "immutable signed packed word fits all8000MW ownership", _literal_word_full_bank),
        ("literal_dword_full_bank", "immutable signed packed dword fits all8000MW ownership", _literal_dword_full_bank),
        ("mutable_snapshots", "mutable word/dword sources retain captured values", _mutable_words),
        ("overlap_snapshots", "overlapping packed word/dword views retain source snapshots", _overlapping_views),
        ("literal_carrier_widths", "i32 literals preserve low bits at16/17/32bits, signed values and full MW bank", _literal_carrier_widths),
    ]]
    result.append(Case("G08.repro.drum_set_step", "G08", "documented literalDR.S2 survives allocation/VM/SDK/XML/actual reverse", "G08 contract; Generic Functions pp147-151", _drum_set_step_repro))
    return result
