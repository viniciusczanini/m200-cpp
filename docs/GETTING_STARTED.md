# Getting started

m200-cpp runs its compiler and local execution tools without a PLC. Generating an `.smbp` project is a separate, template-based step; accepting that project in the official editor and validating it on hardware are separate milestones.

## 1. Prepare the local tools

Use Python 3.9 or newer and a `clang++` executable with C++17 support. `make` is used by the repository's validation recipes. The Python code has no third-party runtime dependencies.

```sh
python3 --version
clang++ --version
./m200c --version
./m200c --help
```

Run commands from the repository root. The executable wrapper resolves its bundled Python module and SDK automatically. You can also use `python3 -m m200` from that directory.

If Clang is installed under a different name or location, select it explicitly:

```sh
export M200_CLANG=/path/to/clang++
```

The recorded local environment uses macOS and Apple Clang 21. This does not establish a tested Python/Clang/platform matrix for other systems. Windows is not a dependency of local compilation; official-editor validation has its own environment requirements.

## 2. Write scan logic

A program includes the bundled `<plc.hpp>` and defines `void scan()`:

```cpp
#include <plc.hpp>

plc::Clock blink{500};

void scan() {
    bool on = blink.update(true);
    plc::output(0, on);
}
```

Global application state persists between scans and is initialized by generated first-RUN logic. Local declarations execute when control reaches them. I/O calls use literal embedded indices: inputs `0..23`, outputs `0..15`. `output_state()` reads the current logical output image, including earlier writes within the same scan.

This is a restricted source language. Use `plc::i16`, `plc::i32`, and `plc::f32` for numeric state, and operations such as `plc::add_i16()` instead of ordinary C++ arithmetic. Use an `f` suffix for REAL literals. The [architecture guide](ARCHITECTURE.md) describes the accepted constructs and their limits.

The clock starts off; `update(false)` resets its timers and phase. It consumes two timers plus state and does not sleep or block the scan. Each half-period includes timer quantization and scan latency. Do not interpret the local model as a measured 500 ms waveform on hardware.

## 3. Compile without a template

```sh
./m200c compile examples/blink.cpp -o output/blink
```

The output directory contains:

| Artifact | Purpose |
|---|---|
| `program.m200.json` | Validated instruction model, configuration, symbols, and metadata; accepted by the local CLI |
| `program.il` | Human-readable IL listing for inspection |
| `program.audit.cpp` | C++ reconstructed from the instruction model |
| `source-map.json` | Source identity, rung origins, and allocated symbols |
| `report.json` | Resource counts, allocation metadata, hashes, and pending validation |

There is **no `program.smbp` without a template**. The standalone `.il` listing is not a CLI input format: use `program.m200.json` or a supported `.smbp` file with `inspect`, `simulate`, and `decompile`.

Compilation stages the artifacts before replacing an earlier compiler output. An unknown file in the destination, an invalid previous manifest, or an edited generated artifact blocks overwrite. Use a new output directory when preserving manual changes. This protection does not establish atomic recovery from every possible filesystem failure.

## 4. Check and simulate a trace

```sh
./m200c check examples/blink.cpp --trace examples/trace.json
./m200c simulate output/blink/program.m200.json --trace examples/trace.json
./m200c inspect output/blink/program.m200.json
```

`check` compiles and runs native C++ for the original source and reconstructed source, then compares both 16-output traces with the IL executor. It therefore executes local native code: use source files you trust. The command is not a sandbox or a general security verifier.

A successful result reports `local_differential_checks_passed`, the frame count, and both output comparisons. Official-editor and physical-PLC validation remain separate. The command does not compare every internal word or flag; the specialized regression and stress suites perform additional observations.

`simulate` returns one array of 16 boolean outputs per frame. `inspect` reports resources, configuration, and limitations without executing the program.

A trace is a JSON array of scan frames:

```json
[
  {"dt_ms": 100, "inputs": {"0": false}},
  {"dt_ms": 100, "inputs": {"0": true}},
  {"dt_ms": 100, "inputs": {"0": false}}
]
```

Each frame supplies the input image for one scan and advances the local clock by `dt_ms` after that scan. The first scan starts at time zero. Omitted inputs are false, including inputs that were true in an earlier frame. The defaults are an empty input image and `dt_ms: 10`. Traces allow `1..100000` frames, input keys `0..23` with boolean values, and integer elapsed times `0..3600000` ms. Only `inputs` and `dt_ms` are accepted as frame fields.

Local timing is deterministic. It does not reproduce measured scan jitter, electrical input timing, or all native timer lifecycle behavior.

## 5. Generate a candidate SMBP project

Use an authentic **TM200CE40T** project created in EcoStruxure Machine Expert Basic. Preserve its target, functional level, and required hardware/channel configuration. A project created for M221 or another M200 model is not a substitute.

The repository includes an [editor-created memory baseline](../tests/fixtures/official_tm200ce40t_memory.provenance.json), with a minimal `LD %M0` / `ST %M1` program. It was reopened in Machine Expert Basic 1.4 build 484 in a Wine-hosted local lab. That observation applies to the exact baseline, not every program generated from it.

```sh
./m200c compile examples/blink.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp \
  -o output/blink-project
```

For your own configuration, substitute `--template path/to/your-tm200ce40t.smbp`. The exporter preserves the template's hardware configuration and replaces its supported program and allocations. The original template is not modified. It adds `program.smbp` to the normal artifacts and records the generated project's resource counts in `report.json`.

`tests/fixtures/synthetic.smbp` exists solely to exercise parser and serialization tests. It was not created or validated by Schneider software and must not be used as a deployment template.

The parser is conservative: even an authentic blank template may contain defaults the tool does not yet recognize. Unknown active objects, tasks, execution attributes, ambiguous duplicate fields, and unsupported format variants are refused rather than silently discarded. Such a refusal may be an importer gap, not an invalid official project.

Some locally implemented operations intentionally cannot be exported yet. Examples include the unproved 10 ms timer enum, indexed-bit functional-level mapping, timer options requiring unresolved functional levels, and several Modbus graphical variants. See the [export gates](ARCHITECTURE.md#project-format-and-export-gates).

## 6. Reverse the actual program

For the template-free local path:

```sh
./m200c decompile output/blink/program.m200.json -o output/blink-audit.cpp
```

For a supported project:

```sh
./m200c decompile output/blink-project/program.smbp -o output/project-audit.cpp
./m200c inspect output/blink-project/program.smbp
```

The reverse compiler reads actual IL operands, instructions, and recognized configuration. It produces equivalent audit C++ with explicit addresses and native block identities where needed. Original variable names, array syntax, structured control flow, and formatting are not generally recoverable. The result is not a source backup embedded in project metadata.

Decompiling an `.smbp` also creates `project-audit.cpp.configuration.smbp`: an exact copy of the input for configuration outside the reconstructed code. Keep it with the audit source. The CLI does not automatically use that sidecar during a later compilation.

Choose a new destination each time. Existing output or sidecar files are refused, and input/output/sidecar paths must remain distinct, including resolved symlink aliases.

The reconstructed C++ may run correctly as a native audit reference while recompilation for the PLC exceeds the tool's instruction or memory budget. Compiler overhead is not proof that the original native program cannot fit.

## 7. Validate through the official software

The intended next steps for a generated candidate are:

1. Preserve the exact candidate and its SHA-256, editor version/build, target, and functional level.
2. Open it in Machine Expert Basic and record errors, warnings, repairs, or migrations.
3. Inspect the Ladder rungs, symbols, configuration, and instruction order; compile in the editor.
4. Save a separate copy, close, reopen, and compare the real instructions and configuration again.
5. Exercise the supported behavior in the official simulator, documenting what that simulator does not implement.
6. Validate physical timing, I/O, communications, RUN/STOP, and restart behavior separately on the actual controller.

Project loading, Ladder display, compilation, simulation, and hardware behavior are distinct results. None can be inferred solely from local XML consistency or round-trip tests. Transfer to a PLC belongs to the official software and an explicitly authorized hardware test session. The CLI provides no automatic PLC upload or firmware update.

The detailed [official validation plan](validation/WINDOWS.md) records the acceptance procedure. A Wine-hosted editor is another environment to document explicitly; it does not establish Windows driver or physical-controller compatibility.

## CLI reference

| Command | Input and result |
|---|---|
| `compile SOURCE -o DIR [--template PROJECT]` | Restricted C++ → artifacts; optional SMBP candidate |
| `check SOURCE --trace TRACE` | Original C++ / IL / reconstructed C++ output comparison |
| `simulate PROGRAM --trace TRACE` | Local execution of program JSON or supported SMBP |
| `inspect PROGRAM` | Resource/configuration report for program JSON or supported SMBP |
| `decompile PROGRAM -o SOURCE` | Reconstruct audit C++; preserve SMBP configuration in a sidecar |
| `capabilities [ID] [--all]` | Source-backed inventory and the implemented library subset |
| `certify` | Always fails while official validation is pending |

Use `./m200c COMMAND --help` for exact arguments. Rejected input returns a nonzero exit status, normally with an `M200-E` diagnostic. A successful local command is not a compatibility certificate.

## Local development checks

```sh
make check
make examples
make stress
```

Focused stress targets include `digital-io-stress`, `expression-edge-stress`, `counter-stress`, `counter-graph-stress`, `integer-flag-stress`, and `conversion-stress`. Stress scripts write reports and reproductions to new temporary directories outside the repository; they fail on unexpected differences.

Public-source fixtures are fetched explicitly from pinned manifests. `make public-check` and `make public-flow-check` perform local checks after their corresponding fetch targets. Additional indexed/counter fetch targets are listed in the Makefile. Fetched third-party projects are research inputs, not distributed deployment templates, and their full import may be unsupported.

Keep all tests and builds local. Do not introduce CI or remote runner workflows; GitHub Actions must remain disabled.
