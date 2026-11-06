# Native END and 10ms timer binding results

The working tree based on `bc1d565ffce9f9e96512c4fc8dfe836544035caa`
passed **462 regression tests in 154.393 seconds**. All 109 selected source, test and
fixture files still match the pin captured before that run. The complete log
SHA256 is `b7a2f159616b285c12aefe2f77f7a68588166a94855396edfe725a9bd881d143`.
Individual source, fixture, log and screenshot hashes are recorded in the
[manifest](NATIVE-END-TIMER-10MS-RESULTS.json).

The native-END focused selection passed 35 tests. The timer agent reported 73
focused tests passing in 25.619 seconds; that command's output was not persisted as a
separate log. The complete regression log independently contains all 73 of
those timer/modes/properties/toolchain cases passing. These selections overlap
the 462-test suite and must not be added to it. Independent review reported no
actionable defects after repeating 35 tests and checking 21 malformed probes.
Fresh Ruff check and format-check passed; 91 files were already formatted.

## Official editor evidence

The root agent converted each native-END diagnostic from IL to Ladder,
observed No error, and saved it. Exact CRLF fixtures establish these bindings:

| IL | Graph |
|---|---|
| END alone | Wire cells 0–9, then End |
| LD M0 / ENDC | NormalContact M0, wire cells 1–9, then End |
| LD M0 / ENDCN | NormalContact M0, wire cells 1–9, then EndCn |

All terminals are at row 0/column 10 with an empty descriptor and Left connection.
The importer now accepts these forms with strict IL/graph consistency checks.
The shared End enum does not erase the difference between unconditional and
conditional execution. Native-END runtime execution is not established by
these diagnostic captures. Export continues to use semantic Jump lowering.

The 10 ms fixture, SHA256
`934affc43bd7e3d918b529b5cbfaee5aabd6bc062006edcd5c3cacf0d7f2bc45`,
contains TON, TOF and TP with preset 5, Base=TenMilliSeconds and both option flags
false at FunctLevelMan21_0. It opened No error, was saved, and the exact saved
file freshly reopened No error after another project was loaded. The
[reopen capture](editor-evidence/timer-10ms-fresh-reopen.png) and three native-END
captures are pinned in the manifest. They show Not Connected in the existing
authorized Wine/.NET lab, including its visible Untrusted DLL detected banner.

Retentive/dynamic product gates are unchanged. New option-profile experiments
still in progress are excluded. No precise tick measurement, native runtime,
other functional-level combination, physical PLC operation or complete library
parity is claimed. Historical integration manifests remain untouched.
