# Natal experimental delivery

The restricted-C++ toolchain for **Schneider TM200CE40T** is available for
experimental testing. Compiler/SDK source is frozen at `77bba32`; this document
records acceptance evidence and outstanding work rather than full PLC parity.
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

The thirteen packages deferred by the user remain preserved for a future
version. Unknown constructs, unsupported native profiles and invalid resources
remain explicit errors. A compiler restriction is not presented as a physical
PLC limitation.

## Acceptance evidence

| Gate | Recorded result | Evidence boundary |
|---|---|---|
| Broad regression before the final native fixes | 1,009 PASS / 8 FAIL / 0 ERROR / 0 SKIP | The eight pending oracle/SDK-adapter cases remain failures; this is not a green full suite. |
| Final composed local batch | 24 cases, 201 positions across seven routes: 1,407 matching observations | Eleven isolated project profiles; local execution and round trips are separate from Schneider runtime. |
| Optimization | Ten budgets passed; the frozen compiler still emits Revoada at 46 rungs / 103 IL / 5 M bits / 7 distinct MW words | Exact ordered IL is unchanged after the two native fixes; physical timing is unqualified. |
| Official editor | Fourteen selected generated projects and official saves admitted; two schedule failures were corrected and rechecked | Visible Ladder, validation, official save and fresh reopen are distinct recorded observations. |
| Actual official-save readback | Native instructions/configuration preserved through import, actual reverse and rebuild within the recorded profiles | Fixed SBR/SC default omissions are resolved; meaningful missing Drum configuration remains rejected. |
| Final simulator campaign | 36 output points passed in six additional profiles; seven of eleven profiles have some runtime evidence including the supervisor | Four profiles were not executed in the bounded session; this is not complete profile qualification. |

The [integration record](NATAL-INTEGRATION-PROGRESS.md),
[native checkpoint](NATAL-NATIVE-CHECKPOINT.md),
[selected-project hashes](native-campaign-2026-11-06/checkpoint.json) and
[final unchanged-code-cost check](native-campaign-2026-11-06/final-cost-check.json)
retain the exact scopes. The native fixes have portable regression tests for
SW114 signed masks and vendor-derived default omissions. Historical failures
and the approved test-contract correction are preserved separately.

The [final runtime report](native-campaign-2026-11-06/RUNTIME-RESULTS.md) includes
subroutine outputs, repeated stateful calls, interior SBR/SC/Drum composition,
direct Drum outputs, the current calendar gate and SW114 schedule disable/enable.
Drum-clock lights, RTC-clock lights, schedule reservation and native Modbus were
not executed in that bounded session. Three observation probes remain pending.
The simulator was stopped; no process or TCP502 listener remained. No further
test round or feature implementation was started as part of this handoff.

## Outstanding qualification

- Broad cold/warm/STOP/RUN edge history and ambiguous sequence endpoints,
  reset/direction or pending-write collisions remain unqualified domains.
- Primitive SDK propagation of indeterminate arithmetic values remains
  unqualified beyond the documented guarded numeric paths.
- The independent asynchronous SDK Modbus backend remains unavailable. A
  callback or missing-transport error cannot qualify a successful exchange,
  active-request snapshot safety or late-response cancellation.
- RTC block bindings beyond the admitted calendar/system-word/schedule route
  and unobserved native timing require their own evidence.
- Windows/USB transfer, physical ports/loads, hardware timing, retention and
  real communication peers require the future controller access described by
  the user.

This frozen experimental delivery does not certify every controller capability.
All builds and tests are local. GitHub Actions remains disabled.
