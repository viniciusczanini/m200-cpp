"""Proposed test-only G01 external-image adapter. No expected data is accepted.

Only external IO values are supplied by callbacks. MW, KW and SW114 are owned
by the real VM/SDK providers. The generated scan reads every requested bit
before applying mutations, and the final MW0 observation uses the real word API.
"""
import json
from pathlib import Path
import re
import subprocess
import sys


def signed16(raw):
    if type(raw) is not int or not 0 <= raw <= 65535:
        raise ValueError("Explicit image values must be unsigned16")
    return raw - 65536 if raw >= 32768 else raw


def prepare(request):
    if request.get("scenario") != "word_bank_bit15_alias":
        raise ValueError("Unbound G01 prepared scenario")
    initial = request["initial_words"]
    reads = request["reads"]
    if not initial or any(type(n) is not int or not 0 <= n < 16 for n in reads):
        raise ValueError("Invalid finite word/bit observations")
    if len(initial)*len(reads) > 16 or "%MW0" not in initial:
        raise ValueError("Observation must fit the real Q image and include MW0")
    lines = ["#include <plc.hpp>"]
    external, writes, constants, word_indexes = {}, [], [], []
    for position, (bank, raw) in enumerate(initial.items()):
        value = signed16(raw)
        if re.fullmatch(r"%(?:IW|QW|IWS|QWS)(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", bank):
            lines.append("plc::BooleanWord image_"+str(position)+"{"+json.dumps(bank)+"};")
            external[bank] = raw
        elif re.fullmatch(r"%MW(?:0|[1-9][0-9]*)", bank):
            index = int(bank[3:]);word_indexes.append(index)
            writes.append("plc::write_word("+str(index)+","+str(value)+");")
        elif re.fullmatch(r"%KW(?:0|[1-9][0-9]*)", bank):
            constants.append((int(bank[3:]), value))
        elif bank == "%SW114":
            writes.append("plc::write_system_word(114,"+str(value)+");")
        else:
            raise ValueError("No real adapter binding for "+bank)
    if constants:
        lines.append("plc::ConstantMemory constant_image{"+str(max(n for n,_ in constants)+1)+"};")
        lines += ["plc::ConstantWord constant_"+str(n)+"{"+str(n)+","+str(v)+"};" for n,v in constants]
    if word_indexes:
        lines.append("plc::WordMemory word_image{"+str(max(word_indexes)+1)+"};")
    body = list(writes)
    for position, bank in enumerate(initial):
        for offset, bit in enumerate(reads):
            body.append("plc::output("+str(position*len(reads)+offset)+",plc::read_bit("+json.dumps(bank+":X"+str(bit)) + "));")
    for mutation in request["mutations"]:
        bank, bit, value = mutation["bank"], mutation["bit"], mutation["value"]
        if bank not in initial or not bank.startswith("%MW") or type(bit) is not int or not 0 <= bit < 16 or type(value) is not bool:
            raise ValueError("Unbound image mutation")
        body.append("plc::write_bit("+json.dumps(bank+":X"+str(bit))+","+("true" if value else "false")+");")
    lines.append("void scan(){"+"".join(body)+"}")
    return "\n".join(lines)+"\n", external, list(initial), reads


def external_images(*, engine, request, repo, work):
    repo, work = Path(repo), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    text, external, order, reads = prepare(request)
    source = work/"case.cpp";source.write_text(text)
    if engine == "vm":
        sys.path.insert(0, str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.numeric import Number
        calls = []
        def provider(action, address, value):
            calls.append([action,address,value])
            if action == "read_word" and address in external:
                return external[address]
            raise AssertionError("No invented external operation: "+repr((action,address,value)))
        program = compile_source(source)
        (work/"program.json").write_text(json.dumps(program.as_dict(),indent=2)+"\n")
        machine = Machine(program, boolean_runtime=provider)
        machine.step(dt_ms=0)
        observed = [bool(machine.outputs[n]) for n in range(len(order)*len(reads))]
        final = machine.read_number(Number("i16","%MW0")) & 65535
        (work/"provider-trace.json").write_text(json.dumps(calls,indent=2)+"\n")
    elif engine == "sdk":
        # Reuse the existing independently compiled SDK host helper; the
        # harness supplies literal external values and no PLC state machine.
        from parallel_semantics.g0108_adapters import run_sdk
        lines = ["#include <cstdio>","#include <cstring>","#define PLC_NATIVE","#include "+json.dumps(str(source))]
        lines.append("unsigned short image_provider(const char* address,bool write,unsigned short value){if(write)__builtin_trap();")
        for bank, value in external.items():
            lines.append("if(std::strcmp(address,"+json.dumps(bank)+")==0)return "+str(value)+";")
        lines.append("__builtin_trap();}")
        # argc=1 is the explicitly supplied provider; passing an argument runs
        # the identical binary with no provider installed for the guard control.
        lines.append("int main(int argc,char**){if(argc==1)plc::detail::boolean_word_hook=image_provider;plc::detail::begin_scan();scan();")
        for n in range(len(order)*len(reads)):
            lines.append('std::printf("%d ",plc::output_state('+str(n)+')?1:0);')
        lines.append('std::printf("%u\\n",(unsigned)(unsigned short)plc::read_word(0));}')
        rows = run_sdk(repo,work,"\n".join(lines)+"\n")
        if len(rows) != 1 or len(rows[0]) != len(order)*len(reads)+1:
            raise AssertionError("SDK alias observation width differs")
        observed, final = [bool(v) for v in rows[0][:-1]], rows[0][-1]
    else:
        raise ValueError("Unknown G01 image engine")
    return {"initial_bit15_bit0":{bank:observed[i*len(reads):(i+1)*len(reads)] for i,bank in enumerate(order)},
            "mutated_MW0_u16":final}


def no_provider_control(*, engine, repo, work):
    """Use the same compiled program/binary; absent hardware must not read zero."""
    repo, work = Path(repo), Path(work)
    if engine == "vm":
        sys.path.insert(0,str(repo))
        from m200.il import Machine
        from m200.model import Program, CompileError
        program = Program.from_dict(json.loads((work/"program.json").read_text()))
        try:
            Machine(program).step(dt_ms=0)
        except CompileError as error:
            (work/"no-provider-diagnostic.txt").write_text(str(error)+"\n")
            if "runtime adapter required" not in str(error):
                raise AssertionError("An unrelated error is not provider-guard evidence: "+str(error))
            return {"missing_provider_rejected":True}
        return {"missing_provider_rejected":False}
    if engine == "sdk":
        binary = work/"host"
        command = [str(binary),"no-provider"]
        result = subprocess.run(command,capture_output=True,text=True,timeout=15)
        (work/"no-provider-run.json").write_text(json.dumps({"command":command,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr},indent=2)+"\n")
        return {"missing_provider_rejected":result.returncode<0}
    raise ValueError("Unknown provider control engine")
