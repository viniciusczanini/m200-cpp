# Priority delivery

The restricted-C++ toolchain for **Schneider TM200CE40T** is available for
provisional testing. The native-project archive is frozen at `77bba32`; the
subsequent SDK update adds independently tested asynchronous Modbus execution.
This document records acceptance evidence within the [current priority goal](../GOAL.md).
It is not a fully qualified release: incomplete acceptance remains explicit.

The [native-project ZIP](native-campaign-2026-11-06/native-projects-77bba32.zip)
contains the fourteen exact official-saved SMBP files, their hashes and unchanged
C++ examples. Open those projects in the official editor for inspection and
experiments. Packaging was checked byte-for-byte against the admitted saves.

Start with the [README workflow](../../README.md#quick-start): compile C++ using
an authentic target template, open the generated `.smbp` in Machine Expert Basic,
inspect Ladder and validate it there. Actual-project reverse conversion produces
equivalent restricted C++ from the imported program/configuration. Transfer to
the physical controller remains a later acceptance stage.

## Delivered software

The seven priority packages cover ordinary Boolean/digital I/O and edges,
integer/bitwise logic and flags, multiple stateful subroutines and local loops,
timers/clocks, counters and native sequences, RTC/calendar/schedules, and the
documented Modbus block profiles. Their exact supported domains and refusals are
listed in the [coverage guides](../../README.md#current-coverage).

Already implemented capabilities beyond the show's minimum needs are retained.
The thirteen packages deferred by the user remain preserved for a future
version and do not block this delivery. Unknown constructs, unsupported native profiles and invalid resources
remain explicit errors. A compiler restriction is not presented as a physical
PLC limitation.

## Acceptance evidence

| Gate | Recorded result | Evidence boundary |
|---|---|---|
| Historical regression before the final native fixes | 1,009 PASS / 8 FAIL / 0 ERROR / 0 SKIP | The original eight-failure record is preserved; its two SDK-adapter gaps are closed by the subsequent backend. |
| Final SDK integration regression | 1,045 tests: 1,038 PASS / 7 FAIL / 0 ERROR / 0 SKIP; one affected-method follow-up PASS | Six native-oracle cases remain FAIL. The seventh was a missing pinned corpus input; only that method was rerun after restoring its verified bytes. The raw full run remains exit 2. |
| Final composed local batch | 24 cases, 201 positions across seven routes: 1,407 matching observations | Eleven isolated project profiles; local execution and round trips are separate from Schneider runtime. |
| Optimization | Ten budgets passed; the frozen compiler still emits Revoada at 46 rungs / 103 IL / 5 M bits / 7 distinct MW words | Exact ordered IL is unchanged after the two native fixes; physical timing is unqualified. |
| Official editor | Fourteen selected generated projects and official saves admitted; two schedule failures were corrected and rechecked | Visible Ladder, validation, official save and fresh reopen are distinct recorded observations. |
| Actual official-save readback | Native instructions/configuration preserved through import, actual reverse and rebuild within the recorded profiles | Fixed SBR/SC default omissions are resolved; meaningful missing Drum configuration remains rejected. |
| First bounded simulator session | 36 output points passed in six additional profiles, alongside the supervisor | Its four timeboxed profiles remain recorded as unexecuted in that historical report. |
| Remaining four simulator profiles | 40 further output checks passed, zero observed mismatches; all eleven composed profiles now have some runtime evidence | DR/RTC phases and controls observed, no period measurement; reservation live M values and successful native Modbus exchange remain unqualified. |
| Independent asynchronous Modbus SDK | Both original cases pass VM/SDK; six new methods cover 43 distinct SDK stimuli across nine function codes | Raw-PDU codec/state/cancellation tests are separate from native or physical transactions. |

The [integration record](NATAL-INTEGRATION-PROGRESS.md),
[native checkpoint](NATAL-NATIVE-CHECKPOINT.md),
[selected-project hashes](native-campaign-2026-11-06/checkpoint.json) and
[final unchanged-code-cost check](native-campaign-2026-11-06/final-cost-check.json)
retain the exact scopes. The native fixes have portable regression tests for
SW114 signed masks and vendor-derived default omissions. Historical failures
and the approved test-contract correction are preserved separately.

The [first runtime report](native-campaign-2026-11-06/RUNTIME-RESULTS.md) includes
subroutine outputs, repeated stateful calls, interior SBR/SC/Drum composition,
direct Drum outputs, the current calendar gate and SW114 schedule disable/enable.
The [four-profile follow-up](native-campaign-2026-11-06/runtime-remaining-4/SUMMARY.md)
records Drum-clock lights, RTC-clock lights, schedule reservation and the native
Modbus READ error path. Existing online Ladder showed COMMERROR=6/OPERERROR=0;
the numeric expected value is null and its cause is unknown. This is not a
successful exchange or a guessed timeout. Three observation probes remain
pending. Every simulator was stopped with no remaining process or TCP502 listener.

The [SDK report](G11-SDK-ASYNC-RESULTS.md) records the new independent backend,
legacy compatibility and exact unchanged native Modbus emission. The public
API needs an explicitly installed raw transport; no physical peer is created.
The [final local gate](g11-sdk-async-2026-11-06/full-gate/RESULTS.md) preserves the
single full run, all seven raw failure blocks and the successful corpus addendum.
The test setup now documents the explicit public-fixture preparation command.
All 74 compiler/SDK pins stayed unchanged through both executions. No new
compiler/SDK defect was observed; this is not a green whole-profile suite.

## Outstanding qualification

- Broad cold/warm/STOP/RUN edge history and ambiguous sequence endpoints,
  reset/direction or pending-write collisions remain unqualified domains.
- Primitive SDK propagation of indeterminate arithmetic values remains
  unqualified beyond the documented guarded numeric paths.
- Native or physical Modbus interoperability remains unqualified. SDK snapshot,
  atomic receive and cancellation checks passed with literal raw-PDU stimuli;
  the simulator error path supplies separate, narrower native evidence.
- RTC block bindings beyond the admitted calendar/system-word/schedule route
  and unobserved native timing require their own evidence.
- Windows/USB transfer, physical ports/loads, hardware timing, retention and
  real communication peers require the future controller access described by
  the user.

These limits are preserved explicitly; they do not restart the thirteen deferred
packages or require whole-controller parity to close the priority handoff. The user
requested pausing the older global goal record after publication.

This provisional delivery does not certify every controller capability.
All builds and tests are local. GitHub Actions remains disabled.
