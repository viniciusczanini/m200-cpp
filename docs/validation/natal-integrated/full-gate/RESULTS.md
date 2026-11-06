# Final combined local regression gate

**Full gate incomplete.** The single `make check` run used default discovery:
1,017 tests, 1,009 passed, eight failed, zero errors and zero skips. It returned
exit code 2 after 300.120 seconds (299.866 seconds inside unittest). There were
no source or oracle changes, filters, retries, GUI operations or remote CI.

| Raw FAIL | Classification | Evidence |
| --- | --- | --- |
| 2 | SC immediate CD → exclusive reset: native oracle pending | Original request and provisional trace retained; separate neutral/reset VM/SDK controls passed |
| 2 | Edge cold/warm/STOP/RUN history: native oracle pending | Missing independent expectation raises before adapter invocation |
| 2 | Unresolved sequence endpoints/collisions: native oracle pending | Unknown outcomes remain visible |
| 2 | Asynchronous Modbus SDK binding unavailable | Registry admits VM only; no callback stub is counted as SDK success |

No new defect or obsolete assertion was identified in these eight blocks.
They remain raw failures. All 1,009 other methods logged success within their
exercised local scope; this does not close pending functionality or full parity.
The historical Register configuration test ran with its exact editor-save
fixtures and passed without an optional-fixture skip.

All 72 compiler/SDK pins and the complete input inventory of 968 files
(114,559,477 bytes) stayed unchanged. This included source, tests/fixtures,
documentation, examples and research, without an extension filter. The
[inventory policy](inventory-policy.json) names cache/output exclusions;
the [drift audit](drift-audit.json) records zero changes, additions or removals.

The [raw log](make-check.log), [command](command.json),
[failure blocks](failure-blocks.json), [classifications](failure-classifications.json)
and [summary](summary.json) preserve exact evidence and hashes. The separate
three-project native probe preparation supplies no runtime observations.
