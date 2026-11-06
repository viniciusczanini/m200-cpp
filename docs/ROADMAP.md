# TM200CE40T completion roadmap

Status: **2026-11-06 — working experimental toolchain; full parity unfinished.**

**Current delivery goal:** [Natal da Liberdade release](GOAL.md). The user moved
whole-controller parity to a future version; it is not the exit criterion for
this priority release. The full inventory below remains preserved as future work.

The goal remains unchanged: every algorithm and resource accepted for the
identified Schneider TM200CE40T profile must have a supported restricted-C++
expression, coherent native Ladder/SMBP output and equivalent reverse C++.
See the [parity contract](PARITY.md), [execution plan](superpowers/plans/2026-11-06-compiler-finish.md)
and [250-record capability matrix](capabilities/COMPLETION-MATRIX.json).

**Execution update:** remaining work now runs in twenty isolated implementation
lanes with three dedicated test agents. Implementation lanes do not execute
tests; local validation follows integration, and official editor/simulator
validation runs as one final campaign. See [parallel delivery](PARALLEL-DELIVERY.md).
This supersedes the per-increment native gate ordering below.
The user then narrowed active implementation to the Natal priority release: G01,
G02, G06, G07, G08, G09 (RTC explicitly retained) and G11. The other thirteen
lanes are stopped with their work preserved for a future version. Full parity
remains incomplete; this release priority does not erase the remaining inventory.

## Current checkpoint

- The preceding published checkpoint is `0144475`: native literal contacts,
  compiler optimizations and the scoped capability matrix, with741 passing tests.
- The integrated Register checkpoint has **799 passing tests**, zero skips, in
  220.444 s, with330 pinned inputs unchanged. Its exact dual output was saved and
  freshly reopened with No error; separate repeated-call FIFO runtime is recorded.
  [The report](validation/REGISTER-INTEGRATION-RESULTS.md) keeps the unfinished dual
  runtime and broader native contexts explicit for the final batch.
- The unchanged movement example fell from 122 rungs/261 IL to **46/103**.
  Ten generic programs enforce code-size and memory budgets.
- The new dual FIFO/LIFO example fell from 34/80 to **22/56**, using one M bit
  and no ordinary MW scratch. Its native queues use separate Register storage.

## Delivered and working

- Target/model and authentic-template checks; Clang-based restricted C++ frontend.
- Typed instructions, scan executor, resource allocation, diagnostics and source maps.
- Native Ladder/SMBP generation and reverse reconstruction from actual instructions.
- Ordinary embedded digital I/O, Boolean logic, fixed arrays, indexed access,
  loops, jumps, conditions and early exits within the documented profiles.
- Explicit i16/i32/f32 operations and conversions; implemented timer, edge and
  counter subsets; stateless subroutine support in the admitted native layout.
- Modbus READ/WRITE/WRITE_READ APIs, local protocol execution and multiple
  accepted native graph/configuration profiles.
- Real official-editor/simulator observations for selected exact generated
  projects, including I/O, sequences, timers, counters, numeric logic and movement.
- Local builds/tests and public version control. GitHub Actions stays disabled.

These are implemented subsets. For example, existing timer or Modbus support
does not complete every mode, lifecycle, configuration or transaction case.

## Ordered work remaining

| Order | Milestone | Current state | Exit criterion |
|---|---|---|---|
| 1 | Finish the current FIFO/LIFO increment | C++/SDK/VM/JSON/operands/graphics/reverse are integrated; local tests and independent review passed. Exact dual output opened, saved and freshly reopened with No error. A repeated-call FIFO product ran and showed full/empty transitions. | Publish the locally tested implementation and preserved observations; run the remaining dual runtime controls in the final batch. |
| 2 | Remaining native block families | SBR research and native diagnostics are prepared; SBR is not implemented. SC, drum, RTC/schedules and PID remain. | Implement each family's configuration, API, state, native code/graphics and reverse path, then pass local and official gates. |
| 3 | Complete language and data semantics | The core works; gaps remain in numeric/system flags, error recovery, ASCII/strings, native table instructions and operand domains. | Cover the remaining native algorithms, limits and error handling with independent references and forward/reverse tests. |
| 4 | Complete program organization | Restricted stateless SR support exists. Wider/stateful SR layouts, user functions/blocks and Grafcet remain. | Preserve shared state, call/return order and native organization across C++, native projects and reverse conversion. |
| 5 | Complete scheduling and lifecycle | The isolated normal MAST profile is admitted. Periodic/event tasks, priorities, preemption, immediate I/O, startup/INIT/STOP/RUN and retention remain. | Implement and qualify the distinct execution contexts and lifecycle transitions, including their memory/image rules. |
| 6 | Complete communication and peripheral configuration | Modbus subsets work. Remaining dynamic properties, message services, port arbitration, network roles/mappings, native transactions, digital modes, FC/HSC, pulses/PWM/PTO, motion and expansion remain. | Implement model-supported settings and operations, detect conflicts/capacity errors, preserve native configuration and test each admitted profile. |
| 7 | Final software interoperability release | Many regression/public-program checks exist; whole-profile closure is pending. | Run composed programs and the fixed corpus, qualify exact generated families in the official tool, reproduce from a clean checkout and publish a tagged software-qualified release. |
| 8 | Windows and physical TM200CE40T acceptance | Waiting for the future Windows/SSH/controller access described by the user. | Verify transfer, physical ports, timing/watchdog, retention, real communication and configured peripherals against release hashes. |

Milestones 2–6 contain substantial implementation work. This is not yet the final
testing stage. The Windows/controller dependency applies to milestone 8; it does
not prevent the remaining software implementation.

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
Further optional optimizations do not postpone the remaining feature milestones;
demonstrated correctness or capacity failures are fixed in their owning milestone.

Full completion requires closing every applicable phase in the capability
matrix and the physical acceptance cases. The goal stays active until then.
