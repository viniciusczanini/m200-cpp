"""Explicit Boolean host adapters; all operations belong to the real engine."""
import json
import os
import shutil
import subprocess
import sys


def cycles(*, engine, request, repo, work):
    source = work / "case.cpp"
    source.write_text(request["source"])
    if engine == "vm":
        sys.path.insert(0, str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine
        from m200.rtc import RtcClock
        machine = Machine(compile_source(source), rtc=RtcClock(*request.get("clock", [2026, 1, 1, 0, 0, 0]), valid=True))
        rows = []
        for item in request["events"]:
            if "master" in item:
                machine.begin_master_cycle(item["master"])
            elif "scan" in item:
                machine.step(item["scan"], dt_ms=0, master_cycle=False)
                rows.append({"bits": [bool(machine.outputs[n]) for n in request["bits"]]})
            else:
                raise ValueError("Unknown master-cycle event")
        return rows
    if engine != "sdk":
        raise ValueError("Unknown Boolean cycle engine")
    y, m, d, h, minute, s = request.get("clock", [2026, 1, 1, 0, 0, 0])
    actions = ["plc::detail::rtc_seed(plc::detail::Calendar{" + ",".join(map(str, [d, m, y, h, minute, s])) + "});"]
    for item in request["events"]:
        image = item.get("master", item.get("scan"))
        actions.append("for(int n=0;n<24;++n)plc::detail::inputs[n]=false;")
        actions += ["plc::detail::inputs[" + str(n) + "]=" + ("true" if v else "false") + ";" for n, v in image.items()]
        if "master" in item:
            actions.append("plc::detail::begin_master_cycle();")
        else:
            actions.append("scan();")
            actions += ['std::printf("%d ",plc::output_state(' + str(n) + ')?1:0);' for n in request["bits"]]
            actions.append("std::putchar(10);")
    rows = run_sdk(repo, work, '#include <cstdio>\n#define PLC_NATIVE\n#include ' + json.dumps(str(source)) + '\nint main(){\n' + "\n".join(actions) + "\n}\n")
    return [{"bits": [bool(v) for v in row]} for row in rows]


def external(*, engine, request, repo, work):
    source = work / "case.cpp"
    source.write_text(request["source"])
    initial = request.get("external_words", {})
    keys = list(initial)
    if engine == "vm":
        sys.path.insert(0, str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine
        values = dict(initial)
        calls = []
        machine = None
        def callback(action, address, value):
            calls.append([action, address, value])
            if request.get("flip_input") and action == "read_bit" and address == "%S66":
                machine.current_inputs[0] = not machine.current_inputs.get(0, False)
                return True
            if action == "read_word" and address in values:
                return values[address]
            if action == "write_word" and address in values:
                values[address] = value
                return None
            raise AssertionError("Unbound external callback " + repr((action, address, value)))
        machine = Machine(compile_source(source), boolean_runtime=callback)
        result = []
        for frame in request["frames"]:
            machine.step(dict(frame), dt_ms=0)
            result.append({"bits": [bool(machine.outputs[n]) for n in request["bits"]], "external_words": [values[k] for k in keys]})
        (work / "callback-trace.json").write_text(json.dumps(calls, indent=2))
        return result
    if engine != "sdk":
        raise ValueError("Unknown Boolean callback engine")
    lines = ['#include <cstdio>', '#include <cstring>', '#define PLC_NATIVE', '#include ' + json.dumps(str(source))]
    for i, name in enumerate(keys):
        lines.append("static unsigned short image_" + str(i) + "=" + str(initial[name]) + ";")
    lines.append("unsigned short word_hook(const char* a,bool write,unsigned short v){")
    for i, name in enumerate(keys):
        lines.append("if(std::strcmp(a," + json.dumps(name) + ")==0){if(write)image_" + str(i) + "=v;return image_" + str(i) + ";}")
    lines.append("__builtin_trap();}")
    lines.append('bool bit_hook(const char* a,bool write,bool v){if(!write&&std::strcmp(a,"%S66")==0){plc::detail::inputs[0]=!plc::detail::inputs[0];return true;}__builtin_trap();}')
    lines.append("int main(){plc::detail::boolean_word_hook=word_hook;plc::detail::boolean_bit_hook=bit_hook;")
    for frame in request["frames"]:
        lines.append("for(int n=0;n<24;++n)plc::detail::inputs[n]=false;")
        lines += ["plc::detail::inputs[" + str(n) + "]=" + ("true" if value else "false") + ";" for n, value in frame.items()]
        lines.append("plc::detail::begin_scan();scan();")
        lines += ['std::printf("%d ",plc::output_state(' + str(n) + ')?1:0);' for n in request["bits"]]
        lines += ['std::printf("%d ",(int)image_' + str(i) + ');' for i in range(len(keys))]
        lines.append("std::putchar(10);plc::detail::first_scan=false;")
    lines.append("}")
    rows = run_sdk(repo, work, "\n".join(lines))
    n = len(request["bits"])
    return [{"bits": [bool(v) for v in row[:n]], "external_words": row[n:]} for row in rows]


def run_sdk(repo, work, code):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ required; never a skip")
    harness = work / "host.cpp"
    harness.write_text(code)
    binary = work / "host"
    command = [compiler, "-std=c++17", "-O0", "-I", str(repo / "sdk"), str(harness), "-o", str(binary)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (work / "compile.json").write_text(json.dumps({"command": command, "returncode": built.returncode, "stderr": built.stderr}, indent=2))
    if built.returncode:
        raise AssertionError("Boolean SDK harness failed to compile:\n" + built.stderr)
    ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    (work / "execution.json").write_text(json.dumps({"returncode": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr}, indent=2))
    if ran.returncode:
        raise AssertionError("Boolean SDK harness exit " + str(ran.returncode))
    return [[int(v) for v in line.split()] for line in ran.stdout.splitlines()]
