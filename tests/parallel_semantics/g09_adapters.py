"""Frozen G09 host bindings. Requests carry no expected values.

Source cases traverse Clang/frontend/IL/VM separately from PLC_NATIVE SDK.
Schedule source cases use the corrected 12-argument constructor on freeze 2b.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sequence(*, engine, request, repo, work):
    if engine == "sdk":
        return sdk_sequence(request, repo, work)
    if engine != "vm":
        raise ValueError("Unknown RTC backend")
    sys.path.insert(0, str(repo))
    from m200.frontend import compile_source
    from m200.il import Machine
    from m200.rtc import RtcClock

    source = work / "case.cpp"
    source.write_text(source_text(request))
    program = compile_source(source)
    seed = request.get("clock", [2026, 1, 1, 0, 0, 0])
    machine = Machine(program, rtc=RtcClock(*seed, valid=request.get("valid", True), available=request.get("available", True)))
    result = []
    for event in request["events"]:
        if "seed" in event:
            machine.rtc.clock = RtcClock(*event["seed"], valid=event.get("valid", True), available=event.get("available", True))
        elif "advance_ms" in event:
            machine.advance_time(event["advance_ms"])
        elif "timer_event" in event:
            machine.timer_event(event["timer_event"])
        elif "reset" in event:
            machine.rtc.reset(cold=event["reset"] == "cold")
        elif "stop" in event:
            machine.rtc.stop(event["stop"])
        elif "write_sw" in event:
            index, value = event["write_sw"]
            machine.write_number("%SW" + str(index), value)
        elif "write_bit" in event:
            index, value = event["write_bit"]
            machine.write("%S" + str(index), value)
        elif "schedule_set" in event:
            index, field, value = event["schedule_set"]
            machine.rtc.write(("schedule", index, field), value)
        elif "scan" in event:
            machine.step(event["scan"], dt_ms=0)
            result.append(observe_vm(machine, request["observe"]))
        elif "probe" in event:
            result.append(observe_vm(machine, request["observe"]))
        else:
            raise ValueError("Unbound RTC event: " + repr(event))
    return result


def observe_vm(machine, observation):
    from m200.numeric import Number
    out = {}
    for key, indexes in observation.items():
        if key == "calendar":
            c = machine.rtc.clock.fields()
            out[key] = [c[n] for n in ("year", "month", "day", "hours", "minutes", "seconds")]
        elif key == "words":
            out[key] = [machine.read_number(Number("i16", "%MW" + str(n))) & 65535 for n in indexes]
        elif key == "system_words":
            out[key] = [machine.read_number(Number("i16", "%SW" + str(n))) & 65535 for n in indexes]
        elif key == "system_bits":
            out[key] = [bool(machine.read("%S" + str(n), {})) for n in indexes]
        elif key == "bits":
            out[key] = [bool(machine.outputs[n]) for n in indexes]
        elif key == "memory":
            out[key] = [bool(machine.memory[n]) for n in indexes]
        else:
            raise ValueError("Unbound RTC observation: " + key)
    return out


def source_text(request):
    body = request.get("source", "#include <plc.hpp>\nvoid scan(){}\n")
    if request.get("mode") == "schedule_source":
        lines = ["#include <plc.hpp>"]
        names = ("start_day", "start_month", "start_hour", "start_min", "end_day", "end_month", "end_hour", "end_min", "dow")
        for index, config in request["schedules"].items():
            output = config["output"]
            bank, address = (1, int(output[4:])) if output.startswith("%Q0.") else (0, int(output[2:]))
            values = [int(index), bank, address] + [config[n] for n in names]
            lines.append("plc::Schedule schedule_" + index + "{" + ",".join(map(str, values)) + "};")
        body = "\n".join(lines) + "\nvoid scan(){}\n"
    return body


def sdk_sequence(request, repo, work):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if not compiler:
        raise AssertionError("clang++ missing; never a skip")
    source = work / "case.cpp"
    source.write_text(source_text(request))
    observation = request["observe"]
    fields, conversions = [], []
    for key, indexes in observation.items():
        if key == "calendar":
            fields += ["plc::detail::rtc_calendar." + n for n in ("year", "month", "day", "hours", "minutes", "seconds")]
            conversions.append((key, 6, False))
        else:
            provider = {"words": "plc::read_word", "system_words": "plc::read_system_word", "system_bits": "plc::system", "bits": "plc::output_state", "memory": "plc::read_m"}[key]
            fields += [provider + "(" + str(n) + ")" for n in indexes]
            conversions.append((key, len(indexes), key in ("system_bits", "bits", "memory")))
    # Calendars are ordinary positive integers; words preserve exact u16 patterns.
    print_code = []
    position = 0
    for key, count, boolean in conversions:
        for expression in fields[position:position + count]:
            if key in ("words", "system_words"):
                expression = "(unsigned short)(" + expression + ")"
            print_code.append('std::printf("%d ",(int)(' + expression + '));')
        position += count
    show = "".join(print_code) + "std::putchar(10);"
    literal = lambda x: "true" if x else "false"
    def seed(c, valid=True, available=True):
        y, m, d, h, minute, s = c
        return "plc::detail::rtc_seed(plc::detail::Calendar{" + ",".join(map(str, (d, m, y, h, minute, s))) + "}," + literal(valid) + "," + literal(available) + ");"
    actions = [seed(request.get("clock", [2026, 1, 1, 0, 0, 0]), request.get("valid", True), request.get("available", True))]
    setters = {"STARTDAY": "start_day", "STARTMONTH": "start_month", "STARTHOUR": "start_hour", "STARTMIN": "start_min", "ENDDAY": "end_day", "ENDMONTH": "end_month", "ENDHOUR": "end_hour", "ENDMIN": "end_min", "DOW": "dow"}
    for event in request["events"]:
        if "seed" in event:
            actions.append(seed(event["seed"], event.get("valid", True), event.get("available", True)))
        elif "advance_ms" in event:
            actions.append("plc::detail::timer_advance_time(" + str(event["advance_ms"]) + ");")
        elif "timer_event" in event:
            actions.append("plc::detail::timer_event(plc::detail::TimerEvent::" + event["timer_event"] + ");")
        elif "reset" in event:
            actions.append("plc::detail::rtc_reset(" + literal(event["reset"] == "cold") + ");")
        elif "stop" in event:
            actions.append("plc::detail::rtc_stop(" + str(event["stop"]) + ");")
        elif "write_sw" in event:
            n, v = event["write_sw"]
            actions.append("plc::write_system_word(" + str(n) + ",(plc::i16)" + str(v) + ");")
        elif "write_bit" in event:
            n, v = event["write_bit"]
            actions.append("plc::write_system(" + str(n) + "," + literal(v) + ");")
        elif "schedule_set" in event:
            i, field, v = event["schedule_set"]
            actions.append("schedule_" + str(i) + ".set_" + setters[field] + "(" + str(v) + ");")
        elif "scan" in event:
            actions.append("for(int i=0;i<24;++i)plc::detail::inputs[i]=false;")
            for i, value in event["scan"].items():
                actions.append("plc::detail::inputs[" + str(i) + "]=" + literal(value) + ";")
            actions.append("if(plc::detail::timer_running){plc::detail::begin_scan();scan();plc::detail::first_scan=false;}" + show)
        elif "probe" in event:
            actions.append(show)
        else:
            raise ValueError("Unbound SDK RTC event")
    harness = work / "harness.cpp"
    harness.write_text("#include <cstdio>\n#define PLC_NATIVE\n#include " + json.dumps(str(source)) + "\nint main(){\n" + "\n".join(actions) + "\n}\n")
    binary = work / "rtc-case"
    command = [compiler, "-std=c++17", "-O0", "-I", str(repo / "sdk"), str(harness), "-o", str(binary)]
    built = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (work / "compile.json").write_text(json.dumps({"command": command, "returncode": built.returncode, "stderr": built.stderr}, indent=2))
    if built.returncode:
        raise AssertionError("SDK RTC harness compile failure:\n" + built.stderr)
    ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
    (work / "run.json").write_text(json.dumps({"returncode": ran.returncode, "stdout": ran.stdout, "stderr": ran.stderr}, indent=2))
    if ran.returncode:
        raise AssertionError("SDK RTC runtime exit " + str(ran.returncode) + ": " + ran.stderr)
    rows = []
    for line in ran.stdout.splitlines():
        values = list(map(int, line.split()))
        if len(values) != len(fields):
            raise AssertionError("SDK observation width differs")
        row, offset = {}, 0
        for key, count, boolean in conversions:
            row[key] = [bool(v) if boolean else v for v in values[offset:offset + count]]
            offset += count
        rows.append(row)
    return rows
