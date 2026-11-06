# Parallel completion and batch acceptance

Execution policy changed by the user on 2026-11-06. This policy supersedes
per-family serial execution and simulator gates in the earlier execution plan.
The functional parity contract and evidence requirements are unchanged.

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

- One isolated implementation lane for each of the twenty work packages G01–G20
  in the capability matrix. Each lane implements its remaining supported scope,
  including the C++/SDK, typed model, native configuration/graphics and reverse
  paths. Existing working features remain intact.
- Implementation lanes do not run tests, builds, Wine or the official editor.
  They return actual source changes, an API contract, sources and explicit gaps.
- Three dedicated test agents prepare independent cases in parallel: composed
  batch programs; semantic/boundary oracles; project/reverse/configuration and
  communication interoperability.
- The coordinator integrates the isolated changes and resolves shared-file
  conflicts. Source changes do not become validated because they were merged.

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
