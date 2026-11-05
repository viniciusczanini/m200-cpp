# Local M200 Toolchain Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. User authorized maximum local experimental work; Windows validation is explicitly deferred.

**Goal:** Deliver a strict experimental C++/IL/SMBP toolchain with reverse C++ and independent native execution checks.

**Architecture:** Clang AST frontend, boolean scan IR lowered to reversible IL, template-preserving XML backend, independent IL executor, native C++ SDK and reverse translator. Unknown syntax/configurations fail. No official-compatibility status may be emitted.

**Tech Stack:** Python standard library, C++17, installed Clang. No remote CI or VM installation.

**Spec:** `docs/superpowers/specs/2026-11-05-m200-cpp-design.md`, including the user's experimental/SSH and reverse-conversion amendments.

## Global Constraints

- Target TM200CE40T only; 24 digital inputs, 16 digital outputs, 1024 memory bits, 255 timers.
- All builds/tests local. No CI, firmware writes, PLC communication, purchases or publication.
- Require exact target template for project output; synthetic fixture only exercises XML locally.
- Supported initial source: booleans, sequential assignment, conditionals, pure helpers, digital I/O, standard clocks, edge detectors and native timers.
- Every unsupported construct/instruction errors. Integer arithmetic and loops remain explicitly unsupported in this prototype.
- Valid XML, local tests and reverse conversion never confer official compatibility.

## Review Focus

- Assignment order, including toggling a variable and writing/reading outputs in the same scan.
- Side-effect calls under conditionals/short-circuit, multiple timer updates and hidden unsupported declarations.
- Resource allocation overlapping explicit addresses, exhaustion and the six 1 ms timer slots.
- External XML with IL/graphics mismatch, unknown instructions, wrong target, tasks or active unsupported objects.
- False compatibility claims and the distinction between real templates and synthetic fixtures.

### Task 1: Strict frontend, model, boolean IL and SDK

Files: `m200/model.py`, `m200/frontend.py`, `m200/lower.py`, `sdk/plc.hpp`, `tests/test_toolchain.py`.

Interfaces: `compile_source(Path) -> Program`; Program has `rungs`, `timers`, `symbols`, `metadata`; lowerer emits only approved instructions and checks physical/resource bounds.

- [x] Write CLI/integration and hand-derived IL tests for I/O, assignment order, branches, rejection, clocks and timers; run RED.
- [x] Implement AST validation and the shared model/lowerer; unsupported syntax errors with source location.
- [x] Run the relevant tests GREEN and record scope/limitations in the ledger.

### Task 2: IL executor, reverse C++ and native reference runner

Files: `m200/il.py`, `m200/reverse.py`, `m200/native.py`, SDK runtime.

Interfaces: `Machine(Program).step(inputs, dt_ms) -> list[bool]`; `to_cpp(Program) -> str`; `run_native(source, frames) -> outputs`.

- [x] Add RED tests with literal temporal/stateful expectations and native C++ differential checks.
- [x] Implement strict IL interpretation and reverse translation reading the actual instructions.
- [x] Compare original native C++, emitted IL and reconstructed native C++ across deterministic and random traces; run the full suite.

### Task 3: Template-preserving project I/O and CLI

Files: `m200/project.py`, `m200/__main__.py`, `m200/cli.py`, `tests/fixtures/synthetic.smbp`.

Interfaces: `load_project(Path) -> Program`; `write_project(Program, template, destination)`; CLI compile/decompile/check/inspect.

- [x] Add RED tests for target/config rejection, IL/graphic mismatches and preservation of the template's hardware.
- [x] Implement conservative XML handling and explicit experimental outputs/reports. Refuse certification.
- [x] Run full suite plus actual example CLI builds and reverse/native checks.

### Task 4: Documentation, examples and final review

Files: README, examples, Windows validation checklist, Makefile, CLI smoke tests.

- [x] Document exact supported subset, unknowns, clocks/timer semantics, compile/decompile commands and deferred Windows proof.
- [x] Run `make check`, build examples and inspect generated reports/projects.
- [x] Commit locally, obtain one fresh implementation review, fix important findings with RED/GREEN tests, rerun the suite.
- [x] Leave all work local, with official editor and physical tests explicitly pending.
