# Integration progress

Status: **2026-11-06 — bounded delivery handoff; historical and final gate results retained separately.**

All seven priority packages are connected in the working candidate. This is
implementation progress, not an official compatibility or whole-profile claim.
The [release goal](../GOAL.md) retains RTC and postpones thirteen other packages.

## Local evidence by frozen candidate

| Candidate | Evidence | Limit |
|---|---|---|
| `natal-combined-3` | 23 composed cases, 185 positions across seven forward/reverse/SDK routes: 1,295 matching observations. Examples and ten optimization budget cases passed. | Drum immediate step assignment exposed an allocator defect. |
| `natal-combined-3b` | The original Drum case passed after the allocator fix: 16 positions across seven routes. | Other passed cases were not rerun. |
| `natal-combined-3c` | Packed literal width/sign/full-bank controls, the original packed regression and two timer property tests passed. | Focused follow-up only; it does not replace the failed full run. |
| `natal-combined-4` | Original BooleanStack, first-scan and agenda repros passed. Canonical SR/no-op and typed configuration preservation controls passed. | New controls exposed two SDK address forms, legacy system aliases, SR sequence graph admission and literal conditional-return defects. |
| Contract review snapshots | 57 revised SR tests passed. Three prepared RTC cases passed in both engines. Numeric review ran 75 methods and isolated three S18 failures. | Each review used its own immutable source/test copy; no full-run claim. |
| `natal-combined-5` | The two affected numeric methods and 101 timer-module tests passed after review/integration, with independent boundary/sticky/atomicity controls. | Boolean/SR follow-ups are separate; system-bit alias runtime/action handling still needs correction. No full regression PASS. |
| `natal-combined-6` | 55 affected Boolean/system-alias checks passed; original request/oracle bytes retained. | Native lifecycle and primitive SDK poison propagation remain pending. |
| `natal-combined-7` | Full default discovery: **1,017 tests, 1,009 passed, eight failed, zero errors/skips**. All 72 compiler/SDK pins and 968 input files remained unchanged. | All eight failures are explicit pending cases; command exit2, whole gate incomplete. |

The unchanged Revoada source passed its sampled-clock checks in candidate 3:
four start phases, 9,845 timeline positions and 14 control positions. Its cost
remained **46 rungs / 103 IL instructions / 5 M bits / 7 distinct MW words**.
This preserves the documented clock sampling/phase tradeoff and does not prove
physical timing or an arbitrary missed-edge guarantee.

The final composition run repeated the closed workload on the final 72 compiler
hashes: **24 cases, 201 positions, seven routes and 1,407 matching observations**,
across 11 project profiles. All ten optimization budgets passed. The unchanged
Revoada source again passed its 9,845 positions and 14 controls, retaining the
same 46/103 cost. Each final command ran once. The documentary inventory remains
45 passed literal subsets, 41 pending IDs and 164 deferred IDs, not full parity.
[Final batch evidence](natal-integrated/final-batch/SUMMARY.md) records hashes,
ownership, generated projects and memory/code-size budgets. Three additional
sequence observation probes passed project/reverse preparation only; their
twelve native outcome questions remain pending.

## Earlier full local gate

The single final combined run completed in 300.120 seconds. Its eight raw
failures comprise six native-oracle cases (SC reset history, edge lifecycle
and unresolved sequence domains, each in VM/SDK) and two missing SDK asynchronous
communication bindings. No new defect or obsolete assertion was identified
in these eight blocks. All 1,009 other methods logged success. This distinction
does not convert missing functionality into a full-suite PASS.

[Raw results, commands, complete input pins and classifications](natal-integrated/full-gate/RESULTS.md)
are preserved with the [exact summary](natal-integrated/full-gate/summary.json).
The whole gate remains incomplete and `make check` returned2.

Fourteen portable regression methods were then added without changing those
72 compiler/SDK hashes: eight Boolean/image/alias tests and six SR/sequence/return
tests. Their focused results are separate from the 1,017-test run. A selector
error in the new SC test was corrected and only that affected method was rerun;
the original literal row/history expectations were retained.

## Earlier failed run and corrections

The first combined `make check` ran 1,007 tests and returned **123 failures,
4 errors and 1 skip**. The complete original log and classification are retained
locally. Several concrete defects have focused fixes; obsolete refusal assertions
are being reviewed against the expanded contracts. A changed assertion needs
independent allowed-behavior and genuine invalid/bound/atomicity controls.
Unresolved native observations and missing adapters remain visible gaps.
Prepared external-image and calendar adapters now have actual VM/SDK bindings;
native lifecycle and unresolved sequence endpoints are still pending.

The 72 compiler/SDK files did not change during that earlier full run. Four test
descriptor notice/compiler-pin fields did change; the final candidate7 above
used closed source and test inputs and recorded zero drift. No broad passing
claim is derived from the earlier run.

## Delivery handoff update

The fourteen-project official editor campaign is complete, including corrections
for native SW114 literals and omitted SBR/SC defaults. The finite simulator
campaign now has some runtime evidence for all eleven composed profiles. The
last four-profile session added 40 matching output checks, without claiming
complete timing, live reservation M values or successful native Modbus exchange.

The [independent asynchronous SDK backend](G11-SDK-ASYNC-RESULTS.md) closes the
two earlier G11 SDK-adapter gaps: the original cases passed on VM/SDK, alongside
43 distinct raw-PDU SDK stimuli and a separate compatibility gate. No original
oracle or VM-provider bytes were changed. Six unresolved native-oracle cases
remain explicit failures outside the admitted show profiles.

The [single final SDK integration regression](g11-sdk-async-2026-11-06/full-gate/RESULTS.md)
ran 1,045 tests: 1,038 PASS, seven FAIL, zero ERROR/SKIP. Six are those known
native-oracle cases. The other failure was a pinned public corpus omitted from
the tracked-only snapshot; restoring its verified bytes and rerunning only the
affected method passed. Raw full exit 2 and all failures remain preserved. All
74 compiler/SDK pins stayed unchanged; no full retry or new product fix ran.

The [delivery handoff](NATAL-DELIVERY.md) records the final combined regression,
exact artifacts and supported limits. The current global working scope includes
priority and already implemented extras; the full-controller backlog and thirteen
stopped lanes remain inactive. After publication, pause the older goal record as
requested. Physical ports/loads, transfer, retention and real peers remain later
external acceptance work.

The [machine-readable record](NATAL-INTEGRATION-PROGRESS.json) preserves candidate
hashes, historical results and source-evidence hashes. These local candidate
results do not promote new native layouts to official acceptance. All execution
is local; GitHub Actions remains disabled.
