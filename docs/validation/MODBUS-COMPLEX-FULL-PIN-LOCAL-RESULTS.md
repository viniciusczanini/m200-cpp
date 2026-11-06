# Complex full-pin Modbus local results

**PASS: three deterministic recipes, 74 distinct timeline positions and 19 exchange starts.** The [portable stress script](../../tests/stress/modbus_full_pin.py) completed the final standalone oracle-strengthening run in **13.125 seconds**, with all 47 inputs unchanged. This stage ran no full regression suite and adds no unit-test count.

The script embeds C++ sources and independent literal control/status/error/buffer/wire expectations. It requires only public repository modules, SDK and the three exact full-pin fixtures/provenances. Run locally:

```sh
python3 tests/stress/modbus_full_pin.py
# Or choose an output path that does not yet exist:
python3 tests/stress/modbus_full_pin.py --output /tmp/m200-full-pin-new-run
```

The default prints a fresh retained temporary directory. Existing destinations and Python `-O` are refused; both guards were checked. Python and the local `clang++` toolchain are required (`M200_CLANG` is honored). No socket, GUI, Wine, physical PLC or CI operation occurs.

| Recipe | Distinct positions | Starts | Canonical rungs / IL | Native rungs / IL |
|---|---:|---:|---:|---:|
| Three-instance READ I / WRITE Q / WR MW | 44 | 11 | 140 / 306 | 128 / 309 |
| Cascaded READ I with repeated output aliases | 23 | 7 | 92 / 201 | 84 / 203 |
| Labeled entry, skipped update and persistent DONE store | 7 | 1 | 36 / 78 | 36 / 78 |

All projects use actual Man21 (human14.0) and SL1 master. The base recipes retain their five native 15-line/27-entity full-pin groups. The new control-entry recipe uses one six-line/three-entity bare update and ordinary status rungs. All six source/reverse compiler bundles preserve template hardware; the ten base grouped source-origin sets remain exact.

The base traces check same-link refusal, held Execute without queued retries, request snapshots while source words change, Abort, timeout, exception, malformed reply and fresh-edge recovery. FC2/FC15 packets exercise17-bit packing; FC23 uses independent asymmetric read/write buffers and protected neighbors. Ordered shared output stores remain observable. First DONE can start a later READ in the same scan after link release. The19 starts produce14 completed responses and five cancelled pending exchanges (four Aborts and one timeout); one response is an injected exception.

The previously refused reordered quartet and interior-label entry are now positive safe-decomposition checks. The original executable rung/store/label order survives import, export and replay. A same-target BUSY-then-DONE variant proves the final DONE store wins. Three variants each replace an existing destination and create an absent destination: six successful complete-output checks, with caller/template preservation. Complete full-pin groups elsewhere remain full-pin groups. These checks reuse the44 base positions and do not inflate the distinct-position count.

The seven new positions actively jump past the update and DONE store. A request starts at10ms; skipped invocations retain BUSY, an explicit earlier TRUE store survives the jump, and the pending response is consumed only at the40ms invocation. DONE subsequently survives another skipped update while a separate ordinary store clears its diagnostic coil. Literal Q0..3 are `0000,0100,0100,1100,1010,0010,0000`; source/reverse native absent-transport literals are separate. The trace demonstrates persistence and control-flow order rather than simply requiring equal generated files.

Five real profile/bounds negatives remain: two actual unverified template levels despite forged metadata, actual SL1 slave mode, an unverified full-pin READ MW profile and an incomplete two-word buffer at MW7999. Four export scenarios preserve both existing and absent destinations (eight refusal checks); buffer extent fails during typed construction. Six malformed native graph imports are still refused: missing Abort contact, unknown field, extra output, wrong class, wrong connection and mismatched Abort descriptor. Original input bytes remain unchanged, now enforced by an explicit assertion as well as recorded in each result.

Independent review of the earlier `3337af` script found that the malformed-input helper recorded byte preservation without asserting it. An isolated append-then-refuse loader surrogate exposed that missing oracle check (RED). A single validation-script assertion now catches it (GREEN), while still requiring the original malformed graph CompileError. The real reader had preserved every input; no product corruption or admission defect was demonstrated. The targeted 74-position run and script-only Ruff checks then passed. Existing compiler/runtime modules and unit-test methods did not change.

The separate **602-test checkpoint** used the then-final `3337af` script in its exact historical 164-input snapshot. This later standalone script has SHA256 `98b443a7211d1269a637973f4438add6f0fc8522d1f18e2e0954cd044aabd409`; the other 163 review inputs remain unchanged. The 602-test suite was not repeated for this validation-only assertion. The original 11.064-second integration run, its public reports and the independent 10.850-second review run remain retained with their original hashes.

Distinct FC23 inbound sentinels `2468/1357/369C` survive the malformed response while the remote write is visible. The retained intentional bad-prefix surrogate must be caught first at MW400, scan34/430ms: actual `8001`, expected `2468`. Recovery succeeds at scan38. The earlier `972616` and strengthened `166bc26f` scripts/docs/runs remain immutable historical snapshots; their67-position claims and former export refusals have not been relabeled as this new stage. The old runner was first observed rejecting the new positive expectation, then only the validation artifact changed.

Five VM representations and source/reverse SDK paths repeat these same74 positions. **Native callbacks replay literal outcomes to test C++ composition; they do not independently implement transport or prove native lifecycle.** Protocol checks use the pure in-process VM transport reference. No official editor/runtime, serial timing or physical interoperability proof follows. The script passed Ruff check/format; [machine-readable results](MODBUS-COMPLEX-FULL-PIN-LOCAL-RESULTS.json) pin the current script, inputs, terminal log, literals, decomposition results and preserved history. No Makefile or CI configuration changed in this validation lane.
