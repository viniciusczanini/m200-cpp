# Parallel completion and batch acceptance

Execution policy changed by the user on 2026-11-06. This policy supersedes
per-family serial execution and simulator gates in the earlier execution plan.
The evidence requirements remain in force. The later Natal scope revision below
sets the current release boundary.

## Natal da Liberdade priority release

The user subsequently requested a smaller active set to reduce token use and
stop work unnecessary for the show. RTC/calendar/schedules were explicitly
retained. The full parity inventory remains the future objective.

| Execution | Packages | Focus |
|---|---|---|
| Active, narrowed to the show | G01, G02 | Ordinary Boolean/digital I/O, edges, useful memory/constant handling, integer/bitwise logic, flags and limits |
| Active | G06, G07, G08 | Useful subroutines, multiple timers, counters, FIFO/LIFO and shift/step/drum sequences |
| Active | G09, G11 | RTC/calendar/schedules and Modbus communication |
| Stopped; files preserved for a future version | G03, G04, G05, G10, G12–G20 except G11 | Additional conversions/ASCII/native structures, immediate I/O, Grafcet, special digital modes, motion/expansion, advanced network/storage/tasks/drive services and unresolved eligibility research |

The three test agents remain assigned to the priority release and the existing
regression suite. Deferred inventory entries are reported explicitly; they
cannot count as passing coverage or whole-profile completion. Paused lanes are
not restarted automatically, and partial source is not merged as validated work.

## Work allocation

- The initial dispatch created twenty isolated implementation lanes. Only the
  seven Natal packages remain eligible for this release; thirteen are stopped.
- Implementation lanes do not run tests, builds, Wine or the official editor.
  They return actual source changes, an API contract, sources and explicit gaps.
- Three dedicated test agents prepare independent cases in parallel: composed
  batch programs; semantic/boundary oracles; project/reverse/configuration and
  communication interoperability.
- The coordinator integrates the isolated changes and resolves shared-file
  conflicts. Source changes do not become validated because they were merged.

### Parallel correction round

| Owner | Bounded deliverable | Handoff |
|---|---|---|
| G01 chat | BooleanStack branch balance, explicit master-cycle first-scan lifetime, canonical string addresses | Six-file combined G01/G06 correction frozen for focused validation |
| G06 chat | Preserve canonical SR returns and avoid unnecessary leaf normalization | Same frozen correction; no changed regression expectations |
| G02 chat | Review numeric legacy assertions, flags/indeterminate results and INC/DEC stress vectors | Isolated test proposal; coordinator reviews before test execution |
| G07 chat | Review timer option/level assertions and genuine invalid/atomicity controls | Isolated test proposal; no observed profile promoted to editor acceptance |
| G11 chat | Review obsolete single/stateless-SR restrictions while retaining native nesting and malformed-graph checks | Isolated SR test proposal; no Modbus scope expansion |
| G09 chat | Bind prepared calendar tests to the implemented RTC host API | Isolated adapter proposal; unresolved native answers remain pending |
| G08 chat | Prepare finite sequence probes and ordered observations for the final native batch | Text artifacts only; no early simulator execution |
| Test agent 1 | SR normalization and composed-program regression | Local focused execution |
| Test agent 2 | Boolean/scan SDK-versus-VM semantics and negative controls | Local focused execution |
| Test agent 3 | Native graph, configuration and reverse interoperability | Local focused execution; sole final regression runner |
| Coordinator | Review proposals, merge disjoint changes, close test inputs and prepare the final simulator batch | One integrated release candidate |

Implementation and test authors edit separate private candidates. Test agents
execute frozen source copies. The final regression starts only after its test
inputs are closed; focused reruns are limited to defects or changed contracts.
The current combined implementation has not passed its full regression gate:
the first combined run exposed real defects and assertions requiring contract
review. Historical failures remain recorded until independently resolved.

The correction deliveries and final local runs are now recorded in
[integration evidence](validation/NATAL-INTEGRATION-PROGRESS.md): 1,009 tests
passed, eight explicit pending cases remain raw failures, and the final
24-case/seven-route composition and ten budgets passed. Two agents preserve
portable regressions for the fixed bugs; a separate Wine chat handles editor
visibility before the coordinator resumes the finite native batch.

## Gates

1. Implement the remaining packages in parallel; prepare tests concurrently.
2. Integrate completed packages and freeze their source/API manifests. Paused
   lanes keep their partial work without being restarted by the coordinator.
3. Test agents execute local checks for integrated packages while other lanes
   continue implementation. Fix concrete failures and rerun affected checks;
   freeze the combined candidate for its final regression gate.
4. Produce a finite batch of exact generated projects and expected traces.
   Run the official editor/simulator acceptance campaign after implementation
   and integration, rather than interrupting each family for GUI work.
5. Publish the tested software and its exact scope. Physical/controller-only
   checks retain their concrete future acceptance cases.

The batch uses several configurations when resources or pin ownership conflict;
one oversized program cannot exercise mutually exclusive hardware modes.
Missing implementations, adapters or observations are reported as pending or
failed, never as skipped successes. A simulator advisory alone does not reject
a loop whose bounded behavior is observed.

## Existing checkpoint

The Register integration has 799 previously passing local tests. It is kept as
the implementation baseline. Its unfinished dual FIFO/LIFO native runtime
observations move to the final batch; historical results remain unchanged.
No tests or simulator observations are claimed for the new parallel changes
until their corresponding gates actually run.

The live dispatch ledger is local under
`output/parallel-implementation-2026-11-06/`. This document describes execution,
not completion. GitHub Actions remains disabled; all validation is local.
