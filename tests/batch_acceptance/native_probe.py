"""Native observation bridge for public input/word frames, used after freeze.

This module does not execute anything on import. The generated harness uses the
SDK's ordinary native scan boundary and public word APIs; it supplies no network
transport and never substitutes expected values for program observations.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess


def observe_native(source, frames, watch_words, folder, sdk, *, rtc_seed=None, watch_bits=()):
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if compiler is None:
        raise RuntimeError("clang++ is required; missing native execution is not a pass")
    source = Path(source).resolve()
    include = str(source)
    if any(character in include for character in ('"', "\n", "\r")):
        raise ValueError("source path cannot be represented in the native harness")
    include = include.replace("\\", "\\\\")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    harness = folder / "harness.cpp"
    executable = folder / "native-probe"
    code = [
        "#include <cstdio>",
        "#define PLC_NATIVE",
        '#include "' + include + '"',
        "int main(){",
    ]
    if rtc_seed is not None:
        code.append("plc::detail::Calendar injected_calendar;")
        for field in ("year", "month", "day", "hours", "minutes", "seconds"):
            code.append("injected_calendar.%s=%d;" % (field, rtc_seed[field]))
        code.append("plc::detail::rtc_seed(injected_calendar,%s,%s);" % (
            "true" if rtc_seed["valid"] else "false",
            "true" if rtc_seed["available"] else "false",
        ))
    for frame in frames:
        levels = ",".join("true" if frame.get("inputs", {}).get(str(i), False) else "false" for i in range(24))
        code += ["{", "const bool levels[24]={" + levels + "};",
                 "for(int i=0;i<24;++i)plc::detail::inputs[i]=levels[i];"]
        for index, value in sorted(frame.get("words", {}).items(), key=lambda pair: int(pair[0])):
            code.append("plc::write_word(%s,%s);" % (index, value))
        code += [
            "plc::detail::begin_scan();scan();",
            "unsigned mask=0;for(int i=0;i<16;++i)if(plc::detail::outputs[i])mask|=1U<<i;",
            'std::printf("%u",mask);',
        ]
        for word in watch_words:
            code.append('std::printf(",%%d",(int)plc::read_word(%d));' % word)
        for bit in watch_bits:
            code.append('std::printf(",%%d",plc::read_m(%d)?1:0);' % bit)
        code += [
            'std::printf("\\n");',
            "plc::detail::first_scan=false;plc::detail::now_ms+=%d;" % frame.get("dt_ms", 10),
            "}",
        ]
    code += ["return 0;", "}"]
    harness.write_text("\n".join(code) + "\n")
    command = [compiler, "-std=c++17", "-O0", "-I", str(sdk), str(harness), "-o", str(executable)]
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (folder / "compile.log").write_text(compiled.stdout + compiled.stderr)
    (folder / "command.json").write_text(json.dumps(command, indent=2) + "\n")
    if compiled.returncode:
        raise RuntimeError("native probe compilation failed; see " + str(folder / "compile.log"))
    executed = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
    (folder / "stdout.txt").write_text(executed.stdout)
    (folder / "stderr.txt").write_text(executed.stderr)
    if executed.returncode:
        raise RuntimeError("native probe execution failed with code " + str(executed.returncode))
    lines = executed.stdout.splitlines()
    if len(lines) != len(frames):
        raise RuntimeError("native probe returned an incomplete frame sequence")
    rows = []
    for line in lines:
        try:
            values = [int(value) for value in line.split(",")]
        except ValueError as error:
            raise RuntimeError("malformed native observation") from error
        if len(values) != len(watch_words) + len(watch_bits) + 1 or not 0 <= values[0] <= 65535:
            raise RuntimeError("malformed native observation shape")
        word_values = values[1:1 + len(watch_words)]
        bit_values = values[1 + len(watch_words):]
        if any(not -32768 <= value <= 32767 for value in word_values):
            raise RuntimeError("native public word is outside i16")
        if any(value not in (0, 1) for value in bit_values):
            raise RuntimeError("native public memory bit is not BOOL")
        row = {"output_mask": values[0], "words": {str(word): value for word, value in zip(watch_words, word_values)}}
        if watch_bits:
            row["memory_bits"] = {str(bit): bool(value) for bit, value in zip(watch_bits, bit_values)}
        rows.append(row)
    return rows
