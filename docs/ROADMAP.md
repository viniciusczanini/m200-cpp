# TM200CE40T completion roadmap

Status: **2026-11-06 — working experimental toolchain; full parity unfinished.**

**Current delivery goal:** [Natal da Liberdade release](GOAL.md). The user moved
whole-controller parity to a future version; it is not the exit criterion for
this priority release. The full inventory below remains preserved as future work.

The broader original requirements are preserved in the inactive
[future backlog](FUTURE-PARITY-BACKLOG.md). They do not extend this goal.

**Execution:** twenty lanes were initially dispatched. The seven Natal packages
were integrated; thirteen lanes were stopped and preserved. Implementation agents
did not run tests. Three dedicated testers split semantic/runtime/compatibility
checks, followed by a single combined local regression and the finite native
campaign. See [parallel delivery](PARALLEL-DELIVERY.md). This delivery retains RTC
and ends after publication; it does not restart the deferred lanes.

## Current checkpoint

- All seven Natal priority packages are integrated and published. Existing
  capabilities beyond the show's minimum needs remain part of the repository;
  the thirteen stopped packages are preserved, without new release obligations.
- The unchanged movement example fell from 122 rungs/261 IL to **46/103**.
  Ten generic programs enforce code-size and memory budgets. The dual FIFO/LIFO
  example fell from 34/80 to **22/56**, using one M bit and no ordinary MW scratch.
- Fourteen selected native projects passed official save and fresh reopen with
  **No error** after fixes for SW114 signed-mask emission and omitted SBR/SC
  defaults. Actual saved projects pass the documented reverse/rebuild profiles.
- The composed local batch passed 24 cases and 201 positions across seven routes:
  **1,407 matching observations**. The earlier broad regression retained eight
  explicit oracle/adapter failures; its raw record is preserved.
- The finite simulator campaign is closed. All eleven composed profiles have
  some runtime evidence. Its final four-profile follow-up passed 40 output
  checks, including observed DR/RTC phases and controls; this does not establish
  exact timing, live reservation M values or a successful native Modbus exchange.
- The independent asynchronous Modbus SDK now passes both original snapshot/abort
  cases on VM and SDK and 43 distinct SDK raw-PDU stimuli. Existing public API,
  legacy callback behavior and the tested native emission remain compatible.
- Final local regression and public evidence are recorded in the
  [experimental Natal handoff](validation/NATAL-DELIVERY.md). The user requested
  pausing the old global goal record after that publication.

## Delivered and working

- Target/model and authentic-template checks; Clang-based restricted C++ frontend.
- Typed instructions, scan executor, resource allocation, diagnostics and source maps.
- Native Ladder/SMBP generation and reverse reconstruction from actual instructions.
- Ordinary embedded digital I/O, Boolean logic, fixed arrays, indexed access,
  loops, jumps, conditions and early exits within the documented profiles.
- Explicit i16/i32/f32 operations and conversions; implemented timer, edge and
  counter subsets; multiple stateful subroutines, loops and local returns in
  the admitted native layout.
- Modbus READ/WRITE/WRITE_READ APIs, local protocol execution and multiple
  accepted native graph/configuration profiles.
- Real official-editor/simulator observations for selected exact generated
  projects, including I/O, sequences, timers, counters, numeric logic and movement.
- Local builds/tests and public version control. GitHub Actions stays disabled.

These are implemented subsets. For example, existing timer or Modbus support
does not complete every mode, lifecycle, configuration or transaction case.

## Ordered work remaining

### Current Natal release

| Step | Work | Disposition |
|---|---|---|
| 1 | Integrate G01/G02/G06/G07/G08/G09/G11; retain already implemented extras | Done; no deferred lane restarted |
| 2 | Local semantics, forward/reverse composition and optimization checks | Recorded; final SDK integration regression is part of the handoff, with pending native oracles explicit |
| 3 | One finite official editor/simulator campaign over the selected batch | Closed; fourteen editor saves and partial runtime evidence for eleven composed profiles |
| 4 | Publish source, examples, exact results and supported limits | Final experimental handoff; local execution only, Actions disabled |
| 5 | Stop this execution wave | Pause the old goal record after publication, as requested |

Physical acceptance remains a later external gate. The thirteen stopped packages
and unqualified domains outside the admitted show profiles do not block this
experimental Natal handoff. The inventory below is future work, not an active
queue and not a requirement to finish this goal.

### Preserved future work

The [future inventory](FUTURE-PARITY-BACKLOG.md) and [parity contract](PARITY.md)
are inactive references. They are excluded from the global working goal. Already
implemented code and partial work remain preserved; no stopped lane restarts
because an old contract contains unfinished requirements.

## Completion rules

Every newly supported family must pass the same chain:

1. C++ API and typed representation, with real target resource limits.
2. SDK/VM execution and independent positive, boundary, collision and error tests.
3. Coherent native configuration and visible Ladder, plus actual reverse C++.
4. Review, frozen local regression checks and exact editor save/reopen/runtime evidence.
5. Physical checks when the behavior requires them.

The 250 documentary records overlap and have different sizes; their count is not
a completion percentage. A passing suite is evidence for its cases, not proof
that every native feature is implemented. Unknown or missing compiler support
must remain explicit and must not be reported as a PLC impossibility.

Passed gates are not repeated without changed inputs or a concrete defect.
Optimization remains a release priority: preserve algorithmic native code and
the existing budgets, and fix demonstrated correctness or capacity failures.

The active goal ends with the finite Natal handoff in [GOAL.md](GOAL.md).
Physical access and the thirteen stopped packages remain later work.
