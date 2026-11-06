# Narrow timer-option policy results

The compiler now imports and exports three separate option contexts using the
**actual XML ManagementLevel**, with no timer-state or SDK implementation change.
The input/template must contain exact `FunctLevelMan21_0` and base 1000 ms:

| Timer | Retentive | Dynamic preset |
|---|---|---|
| TON | true | false |
| TOF | true | false |
| TON | false | true |

This is an exact-context admission, not a minimum-level rule. Ordinary
false/false timers retain prior behavior. Other bases, levels, dynamic TOF/TP,
combined options and retentive TP remain rejected. Program metadata cannot
promote or deny an actual template context. Rejected exports preserve existing
files; the existing source==destination refusal remains in force.

## Validation

The frozen combined local `make check` run passed **496 tests in 202.294 s**:
471 previous tests plus 15 timer-policy tests and 10 separate Modbus I/Q binding
tests. All 124 pinned inputs matched at start, finish and report verification.
The complete log SHA256 is
`c08664896d1597ea2c6d64cb071c761b9e1855a0168819d78788e32e61e40752`.

The timer-focused run passed 48 tests in 20.110 s: 15 new option tests, four 10 ms
binding tests, 12 mode tests, 10 property tests and seven inactive-alias tests.
The initial RED run showed seven blanket-gate failures in 13 tests. One initial
same-path success expectation was corrected to preserve the existing refusal;
the final file adds two policy/boundary tests. Existing test files were unchanged.

A literal local trace of 26 positions checks Q0–15 and VM MW200–205 through the
saved XML, original C++, supported XML generation, reverse C++ recompilation
and reexport. Native original/reverse C++ output bits also match those literal
expectations. Repeating comparison stages does not create additional frames.
Sparse TM254/P0/P9999 checks establish local binding preservation, not official
execution of those endpoint values.

Independent read-only review found no outstanding defects: 600 context cases,
12 template/forged-metadata exports, six sparse endpoint cases, malformed-token
and same-path controls passed. Its 26 focused test repetitions are separate
review activity, not additions to 496. Ruff checks passed on the three owned
Python files; no remote runners or GUI were used by this implementation lane.

## Evidence and next acceptance step

The byte-exact official save promoted to
[`official_tm200ce40t_timer_options_behavior.smbp`](../../tests/fixtures/official_tm200ce40t_timer_options_behavior.smbp)
is 471237 bytes, SHA256
`5358e5334696e1838e8b34b9efaa84fafb2a7bd97802d2d2ee32ae94a7f52214`.
Its [provenance](../../tests/fixtures/official_tm200ce40t_timer_options_behavior.provenance.json)
links the prior [settled official observations and flags-off control](TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.md).
Those records remain historical and are not rewritten by this policy change.

A new persistent candidate was generated with the supported compile CLI from
the exact original diagnostic C++ and ordinary authentic Man21 template,
without XML edits. It was decompiled/recompiled through the CLI and passed the
same 26 local positions. `timer_options_generated.smbp` is 452279 bytes, SHA256
`5f8594912d882a3f8631988d6b6653b567c6314f8ed353cab37ee0284c6fc312`.
Its source/IL/JSON/reverse/output pins and all result/log identities are in the
[JSON record](TIMER-OPTION-POLICY-RESULTS.json).

Official open/save/reopen/runtime acceptance of that newly generated candidate
is pending at this report checkpoint. This increment does not establish other
levels/bases/kinds, combined behavior, exact scan/tick timing, lifecycle behavior,
physical-controller compatibility or complete library parity.
