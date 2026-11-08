# Compiler Completion Implementation Plan

> **Release-goal override, 2026-11-06:** the user moved full parity to a future
> version. [GOAL.md](../../GOAL.md) defines the priority delivery and its exit
> criteria, retaining already implemented extras. This full plan is preserved
> history and future backlog, not an active instruction to pull unchecked tasks.
> The user requested pausing after the priority handoff. Deferred work does not block
> that release and must not restart automatically.

> **User execution override, 2026-11-06:** use the
> [parallel delivery policy](../../PARALLEL-DELIVERY.md): twenty isolated
> implementation lanes, three dedicated test agents, and a final batched
> official editor/simulator campaign. It supersedes the serial ownership and
> per-family test-first/native-gate sequence below. Existing results and the
> parity contract remain unchanged.

> **For agentic workers:** Use `superpowers:executing-plans` for the compiler lane; independent agents review bounded patches. Execute the unchecked task with the lowest number first.

**Goal:** Finish the TM200CE40T toolchain against the existing parity contract, with code optimization as the first release gate and explicit local/editor/hardware completion states.

**Architecture:** Keep the Clang frontend, typed IL, resource allocator, native Ladder/SMBP backend and real-program decompiler. Optimize generic compiler patterns; keep the benchmark C++ unchanged. Add missing capabilities through the same pipeline rather than substituting precomputed application states.

**Tech stack:** Python 3.9+, C++17 SDK, Clang, local unittest/stress/oracle programs, Machine Expert Basic 1.4 build 484 in the existing Wine lab.

**Spec:** [Functional parity contract](../../PARITY.md). This plan orders that contract; it does not reduce it to the current subset.

## Execution rules and stopping conditions

- Optimization is priority 0. Application/effect rewrites do not count as compiler improvements.
- Keep one compiler patch in progress and at most one independent review of it. A separate agent may maintain application benchmarks; the main agent owns the compiler.
- Freeze the exact source, compiler and template before a final validation run. Use targeted tests while editing, then one full local suite after review. Repeat it only after a change or an unresolved failure.
- Publish each accepted compiler increment. Do not postpone a working release for unrelated research or nicer documentation.
- Do not revisit a passed gate without a changed input, a regression or a concrete new counterexample. Keep optional improvements after the numbered release tasks.
- Research starts with one named missing behavior and ends with an implementable rule or an explicit unresolved question. Do not repeatedly collect equivalent manuals/screenshots.
- All builds/tests remain local. GitHub Actions stays disabled. Preserve original projects, user work and Git LFS hooks.
- Every capability has separate C++, SDK/IL, export/graphics, reverse, local, editor and hardware states. A hardware-dependent test does not keep unrelated local work running indefinitely.
- Local completion requires no unimplemented software row in the pinned target inventory. Final PLC compatibility additionally requires the future Windows/physical test gate. Neither status substitutes for the other.

## Review focus

1. Reads after writes, early exits and partial I/O updates preserve scan order and untouched channels — Tasks 1–2.
2. Removing temporaries must preserve flags, edge/timer calls, aliases, loop back edges and source maps — Task 2.
3. Reverse conversion reads actual native logic and configuration; source text in metadata is not a shortcut — Tasks 2 and 6.
4. Missing native modes must remain compiler gaps, rather than being reported as PLC impossibilities — Tasks 3–5.
5. Simulator or Wine faults must not be confused with compiler defects, nor with physical qualification — Tasks 6–7.

## Task 1: Ship the already validated optimization checkpoint

**Files:** `m200/{frontend,io_lowering,allocation,dead_stores}.py`, the corresponding tests, `docs/OPTIMIZATION.md`, `docs/validation/OPTIMIZATION-RESULTS.json`.

**Interface:** Existing `compile_source`, `write_project`, `load_project`, `to_cpp`; no source-language/API change.

- [x] Same frozen C++: 122→55 rungs, 261→126 IL; input-to-output wire becomes one rung; packed output is a native operation.
- [x] Final combined suite: 703 passed, zero skips; integrated compiler/test inputs match the tested copy.
- [x] Exact generated file accepted as Ladder, saved, and running in the official simulator. Record fresh reopen as pending for this candidate.
- [x] Saved project → C++ → project preserves 2461 sequence positions and 14 button-control cases locally; disclose reconstructed cost 72/165.
- [x] Publish this exact increment and verify remote commit and Actions-disabled setting: `13cfb9e4b6a864932c9365412a4fafe1def30c38` on remote `main`; Actions disabled.

**Done when:** The tested compiler, example, concise English usage and result manifest are on the personal public repository. No new optimization is folded silently into the 703-test checkpoint.

## Task 2: Close the current compiler optimization defects

**Files:** `m200/copy_fusion.py`, `m200/allocation.py`, `m200/dead_stores.py`, `tests/test_guard_fusion.py`, `tests/optimization/`, `tests/stress/optimization.py`. Keep separate result checkpoints in `docs/validation/{OPTIMIZATION,GUARD-FUSION}-RESULTS.json`.

**Interface:** `fuse(program, registers, members, groups, reference, live_out)` retains its signature; all optimized programs still pass `validate` and the existing exporter/decompiler.

- [x] Write a failing size regression for adjacent `G AND (G AND P)` lowering. Add semantic controls for false guards, a live temporary, aliasing and labels; preserve existing indexed/flag gates.
- [x] Implement the narrowly proved fusion. Preserve predicate evaluation exactly once, in its original position. Nine focused methods and independent review passed; same C++ now 51/114.
- [x] Add an explicit regression proving a dead pure private boolean read is eliminated, while numeric/indexed/edge/timer effects remain observable.
- [x] Audit the remaining 51 benchmark rungs once and classify their purpose; keep the fixed audit in `GUARD-FUSION-RESULTS.json`.
- [x] Resolve the two named emission overheads: one coalesced private i16 self-copy and two unread label scratch anchors. The unchanged source now emits 48/108. Keep indexed/shared/SR contexts and native M-edge anchors protected; retain terminal/consecutive label targets and real source origins. Final724 passed after the independently found M-edge regression was fixed.
- [x] Pin ten generic benchmarks in `tests/optimization/` for I/O, conditions, loops, early exits, aliases and SRs, with literal traces and explicit rung/IL/memory ceilings. The standalone runner also checks reverse conversion and rejects a deliberately impossible budget.
- [x] Check the unchanged application against four START phases and button cases; check actual forward/reverse programs locally. Loops remain actual control flow, without frame tables or one rung per application state.
- [x] Freeze and run local checks for the guard checkpoint: `make check` 712 PASS, `make examples` PASS, ten budget cases/44 positions PASS. Later changes to either named overhead require their own frozen validation checkpoint.
- [x] Open/save/fresh-reopen the exact 51/114 CLI output with No error; observe RUN, movement, STOP and held-START no-rearm in the official simulator. Record parser refusals separately from those bounded observations.
- [x] Publish the guard checkpoint and its portable size budgets: `ecdafe98b3fda9c6ac2eb0e1c4132b4a1f50ff62` verified on remote `main`, Actions disabled. The two named emission overheads above remain priority 0 afterwards.
- [x] Validate the exact 48/108 cleanup artifact: official save/fresh reopen No error, bounded RUN/Q0→Q5/STOP/held-START observations, saved reverse 55/123 with local trace parity. The backward-jump advisory remains; all 65536 phase values terminate in at most nine shifts under the local VM test, without a physical watchdog guarantee.
- [x] Publish the final724 cleanup checkpoint and its warning/bound evidence: `7ee136c2409b4b5620652123fa67e92c1af715d0` verified on remote main; Actions disabled.

### Required capacity follow-up discovered by the requested documentation study

This is a concrete capacity defect under this task's existing exception, not an open-ended size search: `BitMemory{1024}` plus `write_word(0,1)` currently fails because boolean constants require private M cells. The documented native form `LD 1; [%MW0:=1]` needs no M. It still needs authentic SHORT/OPEN graph capture in the installed profile.

- [x] Capture, save and freshly reopen the literal LD0/LD1 diagnostic as native Ladder; exact native saves bind Short/Open in ordinary series positions. Negated digit opcodes were rejected and are canonicalized before export.
- [x] Add a failing full-M-bank capacity regression and closed literal-contact graph tests; direct ordinary constants now emit zero scratch cells for that program. Preserve block/SR profile gates and evaluation effects; independent focused review passed.
- [x] Fixed budgets/examples and same-source9845+14 traces passed; independent review and final741-test frozen suite passed after correcting Modbus mixed-normalization admission. Exact46/103 saved/reopened and simulator RUN/movement/STOP passed; publication is the final step of this increment.

**Done when:** The named redundant patterns are eliminated, benchmark ceilings pass, same-source behavior and reverse conversion pass, and the frozen artifact passes the editor gate. Global optimality, a smaller program found by changing the application, and unmeasured physical scan time are not release criteria. Further optional optimizations move after Task 7; a capacity failure in a valid native program remains a required compiler defect.

## Task 3: Make the remaining coverage work finite

**Files:** `docs/capabilities/{instructions,hardware}.json`, `docs/capabilities/README.md`, `m200/capabilities.py`; create one `docs/capabilities/COMPLETION-MATRIX.json` and a consistency test.

**Interface:** Each existing capability ID maps to its target applicability, applicable modes/operands, implementation phases, test references and exact remaining blocker. Preserve original IDs and source references.

- [x] Pin the current official target/editor/functional-level/hardware profile from authentic fixtures. Record physical firmware as unknown until read from the actual PLC.
- [x] Reconcile the existing 161 instruction and 89 hardware records; merge overlapping work items without dropping their IDs. Enumerate modes under their parent item instead of inventing a percentage from record counts.
- [x] Reconcile actual implementation and evidence with the matrix; remove stale claims that SR or 10 ms timer export is entirely absent.
- [x] Add a test that every existing inventory ID is represented, phase values are valid and every claimed completed phase links to a real test/evidence file.

**Done when:** Every pinned in-scope item has an assigned task below and an explicit remaining test. An inapplicable item requires model-specific evidence; an unsupported feature is not silently removed.

## Task 4: Finish software language and native block families

**Files:** Existing `frontend`, `lower`, `il`, `numeric`, `arithmetic`, `conversions`, `timers`, `counters`, `register_*`, `subroutine_*`, `reverse`, SDK and associated tests; add separate native-family modules where absent.

**Interfaces:** Use the existing typed `Program`/SDK pipeline. Each family must provide configuration, operands/state, native instructions/graphics and reverse reconstruction together.

- [ ] Close numeric/system-flag/error-recovery and constant-table gaps identified by Task 3.
- [ ] Complete timer/counter modes, dynamic properties and lifecycle semantics in the pinned profile.
- [ ] Integrate FIFO/LIFO from the existing native evidence, then the remaining drum/step, RTC/schedule and PID families that the model actually supports.
- [ ] Complete supported SR layouts and stateful/control-flow contexts, then native functions, user blocks and Grafcet/state organization.
- [ ] For each family: write independent positive/boundary/collision/error tests first; implement the full forward/reverse path; run focused tests; review; freeze and run the full local suite; validate an exact exported candidate in the editor; publish.

**Done when:** Task 3 has no missing software-language/block phase. No stub may report success for an unimplemented native behavior.

### Register integration checkpoint

- [x] Native FIFO/LIFO configuration, four shared identities and sixteen internal i16 words; I/O words read/write and E/F read-only, with independent literal SDK/state tests.
- [x] Add typed Program JSON and operands, C++ methods, raw ordered R/I/O block parsing, pre-call pin snapshots, VM and actual reverse reconstruction.
- [x] Integrate canonical native I/M-contact graphs and typed Register XML with known omitted FIFO defaults; retain broader profile gates.
- [x] Exercise signed words, full/empty, held/refused/simultaneous requests, FIFO reset collisions, self-status, repeated/skipped local calls, all four IDs and atomic refusals across all forward/reverse routes.
- [x] Independent integration and capacity-fix reviews passed; examples and size budgets passed; frozen full local suite799PASS220.444s with330pinned inputs unchanged.
- [ ] Open/save/fresh-reopen the exact generated dual FIFO/LIFO program, execute native ordered-store/retrieve and button controls, preserve readback and publish the accepted increment.

## Task 5: Finish tasks, communication and hardware configuration

**Files:** Existing `config`, `communication`, `modbus`, `*_xml`, `project`, SDK and profile-specific modules/tests.

**Interfaces:** Typed target configuration and explicit resource ownership. Preserve the same memory and status semantics across C++, native execution and reverse conversion.

- [ ] Cover supported tasks/events, priorities, startup/STOP/RUN/retention and immediate I/O. Extend Task 1's direct-I/O assumptions explicitly when admitting new execution contexts.
- [ ] Complete serial/Ethernet/Modbus configuration, writable properties, status/error paths, shared-port arbitration and remaining native pin profiles.
- [ ] Complete FC/HSC, pulse/PWM/PTO/motion and expansion configuration actually available on CE40T. Check conflicts/capacities before writing output files.
- [ ] Run local protocol peers and official editor/simulator tests where supported. Put RF/electrical/timing/motion and physical communication checks into Task 7 with concrete expected observations.

**Done when:** All supported configuration/code paths exist and pass local/editor gates; only explicitly physical evidence remains pending. No physical test is fabricated by an SDK model.

## Task 6: Final interoperability and release audit

**Files:** `tests/public/`, `tests/stress/`, official fixtures, CLI, README, `docs/GETTING_STARTED.md`, `docs/validation/`.

- [ ] Run the fixed public/native corpus and composed programs spanning I/O, multiple timers, buttons, conditionals, loops, native blocks and Modbus; test actual reverse output as well.
- [ ] For each supported native family/profile, open, compile, display Ladder, save and freshly reopen the exact generated project. Compare saved instructions/configuration, not only screenshots.
- [ ] Resolve compiler failures. Route Wine-only failures to the existing runtime chat with exact bytes and steps; stop retries of unchanged failed cases until that runtime changes.
- [ ] Freeze the release; run the full local suite, fixed stress/corpus checks and examples. Update the matrix and publish English setup/API/limits/reproduction instructions.
- [ ] Publish a tagged local/editor-qualified release with exact tested revision and a finite Task 7 checklist.

**Done when:** All nonphysical phases in the completion matrix are complete and the clean-checkout workflow reproduces the release. End local implementation work here unless a new defect is demonstrated.

## Task 7: Future Windows and physical PLC acceptance

**Dependency:** User-provided Windows/SSH access, official software and the connected TM200CE40T. Follow `docs/validation/WINDOWS.md` and the concrete physical cases collected above.

- [ ] Read versions/model/options from the actual installation/controller and reconcile the pinned profile.
- [ ] Transfer through official software; verify digital ports, timing/clock behavior, multiple timers/buttons, lifecycle/retention and watchdog/error handling.
- [ ] Exercise real Modbus endpoints and configured hardware features with observable expected results.
- [ ] Bind observations to release hashes and close only the corresponding matrix rows. Fix and retest actual failures; do not reopen already passed software families without a related failure.

**Final done condition:** Every applicable matrix phase is complete, all failures have a disposition supported by evidence, the release opens in the official tool, forward/reverse behavior passes the fixed corpus, and the required physical cases pass. Until then the repository states its exact incomplete phases.

## Explicitly after this delivery

Additional lighting effects, benchmark-source redesigns, cosmetic refactors, editor/window/Wine polish and optional size improvements beyond Task 2 are outside the critical path. None may postpone the numbered release gates. A concrete correctness/capacity regression always returns to its owning task.
