"""Local black-box SDK and compiler/VM adapters; not independent oracles.

This file deliberately imports no compiler module until a case is executed.
Unknown future APIs need an explicit binding in adapters.json after DELIVERY.md
is reviewed. There is no name guessing, fallback model, success stub or skip.
"""

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .contracts import PendingAdapterError


def execute(binding, engine, request, repo, work):
    entrypoint = binding.get("entrypoint")
    if binding.get("status") != "prepared" or not entrypoint:
        raise PendingAdapterError(
            "Pending adapter: " + binding["key"] + "; review " + binding["delivery"]
        )
    if engine not in binding.get("engines", ["vm", "sdk"]):
        raise PendingAdapterError(binding["key"] + " has no independent " + engine + " host binding yet")
    module, name = entrypoint.split(":", 1)
    if not module.startswith("parallel_semantics."):
        raise PendingAdapterError("Adapter must be explicit test-owned code: " + entrypoint)
    provider = getattr(importlib.import_module(module), name)
    return provider(engine=engine, request=request, repo=Path(repo), work=Path(work))


def source_pipeline(*, engine, request, repo, work):
    if engine not in ("sdk", "vm"):
        raise ValueError("Unknown semantic test backend: " + engine)
    source = work / "case.cpp"
    source.write_text(request["source"])
    frames, observe = request["frames"], request["observe"]
    if engine == "vm":
        sys.path.insert(0, str(repo))
        from m200.frontend import compile_source
        from m200.il import Machine

        machine = Machine(compile_source(source))
        result = []
        for item in frames:
            machine.step(item.get("inputs", {}), item.get("dt_ms", 10))
            row = {
                "words_u16": [machine.words[index] & 65535 for index in observe.get("words", [])],
                "bits": [bool(machine.outputs[index]) for index in observe.get("bits", [])],
            }
            if observe.get("flags"):
                row["flags"] = {
                    str(index): bool(machine.read("%S" + str(index), {}))
                    for index in observe["flags"]
                }
            result.append(row)
        return result
    compiler = os.environ.get("M200_CLANG") or shutil.which("clang++")
    if compiler is None:
        raise AssertionError("clang++ is required; missing tool is not a skip")
    words, bits, flags = (observe.get(key, []) for key in ("words", "bits", "flags"))
    if any(type(n) is not int or not 0 <= n < 8000 for n in words):
        raise ValueError("Invalid test observation word")
    if any(type(n) is not int or not 0 <= n < 16 for n in bits):
        raise ValueError("Invalid test observation output")
    if any(n not in (17, 18, 20) for n in flags):
        raise ValueError("Only stable post-call S17/S18/S20 flags are observed here")
    prints = [f'std::printf("%u ",(unsigned)plc::detail::words[{n}]);' for n in words]
    prints += [f'std::printf("%d ",plc::detail::outputs[{n}]?1:0);' for n in bits]
    prints += [f'std::printf("%d ",plc::system({n})?1:0);' for n in flags]
    harness = work / "harness.cpp"
    harness.write_text(
        "#include <cstdio>\n#define PLC_NATIVE\n#include " + json.dumps(str(source)) + "\n"
        "int main(){unsigned dt,value;while(std::scanf(\"%u\",&dt)==1){"
        "for(int n=0;n<24;++n){if(std::scanf(\"%u\",&value)!=1)return 2;"
        "plc::detail::inputs[n]=value!=0;}plc::detail::begin_scan();scan();\n"
        + "\n".join(prints)
        + "\nstd::putchar(10);plc::detail::first_scan=false;plc::detail::now_ms+=dt;}return 0;}\n"
    )
    binary = work / "sdk-case"
    compiled = subprocess.run(
        [compiler, "-std=c++17", "-O0", "-I", str(repo / "sdk"), str(harness), "-o", str(binary)],
        capture_output=True, text=True, timeout=60,
    )
    if compiled.returncode:
        raise AssertionError("SDK case failed to compile:\n" + compiled.stderr)
    commands = []
    for item in frames:
        inputs = item.get("inputs", {})
        commands.append(" ".join([str(item.get("dt_ms", 10))] + [
            "1" if inputs.get(n, inputs.get(str(n), False)) else "0" for n in range(24)
        ]))
    completed = subprocess.run(
        [str(binary)], input="\n".join(commands) + "\n",
        capture_output=True, text=True, timeout=30,
    )
    if completed.returncode:
        raise AssertionError("SDK case exited with " + str(completed.returncode) + ":\n" + completed.stderr)
    lines = completed.stdout.splitlines()
    if len(lines) != len(frames):
        raise AssertionError("SDK observation count mismatch")
    result = []
    for line in lines:
        values = [int(item) for item in line.split()]
        if len(values) != len(words) + len(bits) + len(flags):
            raise AssertionError("SDK observation width mismatch")
        row = {"words_u16": values[:len(words)], "bits": [bool(v) for v in values[len(words):len(words) + len(bits)]]}
        if flags:
            row["flags"] = {str(n): bool(values[len(words) + len(bits) + i]) for i, n in enumerate(flags)}
        result.append(row)
    return result
