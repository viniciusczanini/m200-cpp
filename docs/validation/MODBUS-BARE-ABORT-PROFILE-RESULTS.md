# Bare Execute/Abort Modbus profiles

2026-11-06. **602 tests passed in 290.617 seconds**, with zero skips and all **164 source/input pins unchanged**. This adds 15 regression methods to the published 587-test checkpoint. The focused communication cohort passed 93 methods in 9.923 seconds. Ruff check and formatting passed for all 106 pinned Python files; `git diff --check` passed. Independent review found no actionable defect in the bounded binding and local-model scope and separately verified the terminal full-run evidence without repeating the suite. Historical reports remain unchanged.

## Admitted binding

[communication_graph.py](../../m200/communication_graph.py) now imports and exports the independently observed **six-line, three-entity** Execute/Abort form. The established four/six-line `communication.parse_block` contract is unchanged. Narrow [project.py](../../m200/project.py) adapters retain one canonical rung for a bare update and keep the original complete fifteen-line/27-entity full-pin import and export path.

The initial bare profile is actual XML **`FunctLevelMan21_0` (human 14.0), SL1 master**, with canonical normal direct M Execute/Abort contacts:

| Kind/object | Function | Captured inputs | Complete captured buffers |
|---|---:|---|---|
| READ_VAR I | FC2 | M20 / M21 | Remote17/count17 → MW200–201 |
| WRITE_VAR Q | FC15 | M22 / M23 | MW240–241 → remote73/count17 |
| WRITE_READ_VAR MW | FC23 | M24 / M25 | MW300–301 → remote17/count2; remote41/count3 → MW400–402 |

Both contacts use column0, rows0/1, **Left,Right**. The matching native block uses row0/column1, **Left**. No OUT_BLK, attached status coil, filler line or synthetic status destination is added. The original rung, IL and graph are checked before canonical import, including significant mixed text/tails, attributes, unknown/duplicate fields, exact descriptors, coordinates, class/key and connections. Parameterized admission uses actual configuration and existing full-buffer bounds; it does not dispatch on fixture hashes or fixed addresses.

Actual template level, link/master settings, typed configuration and allocation remain authoritative. Metadata cannot enable another profile. Unselected empty-graph IL-only imports retain their established behavior, including predicates that remain unverified for native graph export. Selected empty graphics still fail.

## Safe status decomposition and full-form preference

An adjacent, complete, ordered same-key DONE/BUSY/ABORTED/ERROR quartet of `ST M` rungs still prefers the original full15/27 representation. The update may have a label; the four interior status rungs cannot be separately entered or labelled for that collapse.

When that exact grouping is unsafe, an admitted update can now remain **bare**, with every following ordinary rung retained in place. Partial or reordered statuses, interleaved assignments, labels/control entries, ordinary S/R actions and ordinary Q stores are preserved without being turned into an unobserved directly wired partial/full graph. Repeated destinations retain last-write order. Status stores feeding Execute or Abort affect the next invocation; no output is moved before the update.

Direct native 9/11/13-line partial-pin bodies remain refused, including their unselected IL-only forms. Other bare objects/links/levels, negated/constant/direct-I/Q native input contacts and further native pin forms remain tool gaps. Existing Execute-only word/single-value profiles remain available within their own gates. Undefined status keys, invalid fields, unverified active configuration and late failures still preserve both present and absent destinations atomically.

A bare update consumes one source origin. It neither reads the full form's five-origin audit suffix nor uses stale `native_full_pin_groups` metadata to construct a graph or consume following rungs. Ordinary sidecar/source-location behavior remains; full-group five-origin recovery and original human-comment preservation are unchanged. Tests cover before/bare/after locations during complex-tail normalization and mixed bare/full/bare imports.

## Exact native fixtures

The three root-operated conversion/Ctrl+S saves and fresh saved-clone Programming reopens **No error** are preserved byte-for-byte, including CRLF. Each contains one rung, six lexical IL lines and three entities. Adjacent provenance records candidate/saved identities, six capture hashes, unchanged hardware/configuration and the actual save/filesystem-clone procedure. Existing Modbus `-text` coverage applies; each fixture has three blank password fields.

| Fixture | Bytes | SHA256 |
|---|---:|---|
| [READ I](../../tests/fixtures/official_tm200ce40t_modbus_bare_abort_read.smbp) | 88863 | `222de155bd4061649a017859f8775322974c3e06b3a85204ff85ae015e35b3e4` |
| [WRITE Q](../../tests/fixtures/official_tm200ce40t_modbus_bare_abort_write.smbp) | 88872 | `1489ad6bdcdde1101708088d37ee2eacb326ee23a3c6ac8c0d91cbe25f51fb7d` |
| [WRITE_READ MW](../../tests/fixtures/official_tm200ce40t_modbus_bare_abort_write_read.smbp) | 90288 | `ce46d988bcdaf5e9f0add2d17daff51deb0074240a937ca5f85aeed933ea8890` |

See the separate [native observation record](MODBUS-BARE-ABORT-NATIVE-OBSERVATIONS.md) for official captures and exact XML deltas. These controlled inputs were hand-built IL-only derivatives before official conversion; they are not genuine compiler-product acceptance or communication execution proof.

## Verification and evidence limits

TDD first produced 24 expected assertion/subtest failures across the 15 new methods on all three final fixtures: existing mixed-row import and graphical Abort export refusals. The existing full15/27 control passed. The final focused cohort exercises public constructors without getters, reverse/recompile, original graph closure, actual level/link authority, complete buffers, instance31/M1023 boundaries, metadata forgery, atomic late failure, labels, aliases and local FC23 packet/timing expectations. A test setup was corrected to establish the FB's existing initial false input state before exercising a skipped update; no execution semantics changed.

Only obsolete negative rows were revised: normal-M READ I/WR bare Abort and otherwise valid separate status decompositions. They now have positive retention/ordering checks or genuine unverified-predicate replacements. Single-value Abort, unsupported word-object profiles, malformed native bodies and unknown attached output graphs remain negative controls. SDK, frontend, reverse, IL/VM, protocol/runtime, communication XML configuration and general Ladder normalization code are byte-unchanged in this increment.

Independent review passed three authentic round-trips, 36 bounded parameter exports, 18 graph permutations, 138 malformed/mixed-content refusals, all 24 status permutations, eight ordinary decompositions, nine audit-comment controls, 63 atomic destination refusals and literal FC2/FC15/FC23 recipes. Supplementary probes covered nine partial-native refusals, fifteen full-order/geometry refusals, nine bare-opcode refusals, three mixed origin round-trips, six late atomic failures and four absent-transport SDK/VM/reverse/import representations. A reviewer-only OR-normalization identity assumption was corrected to exact-origin plus independent truth-table checks; the initial helper log is preserved, with no product finding or source edit.

The separately maintained [portable complex stress record](MODBUS-COMPLEX-FULL-PIN-LOCAL-RESULTS.md) now retains positive reordered/control-entry decomposition checks: 74 timeline positions and 19 starts. Its then-final script hash is pinned in the historical 164-input full-suite snapshot. Those positions, repeated comparison stages and independent review cases are not added to the 602 unit methods or historical frame totals.

The single full regression used `python3 -m unittest discover -s tests -v` after source freeze. All 164 exact inputs were retained and checked before/after; Ruff covered all 106 pinned Python files. The earlier optional authentic Register CONFIG test ran here with its recorded local inputs; its documented public-checkout skip remains applicable. Exact commands, hashes, logs, source pins and review evidence are in [MODBUS-BARE-ABORT-PROFILE-RESULTS.json](MODBUS-BARE-ABORT-PROFILE-RESULTS.json).

After that exact checkpoint, independent stress review found one missing assertion: the malformed-graph helper recorded rejected-input byte preservation without enforcing it. An append-then-refuse surrogate reproduced the oracle gap; one standalone validation-script assertion now catches it while retaining the real CompileError requirement. The final targeted stress run passed 74 positions/19 starts in 13.125 seconds with all 47 inputs unchanged, followed by script-only Ruff checks. No product bug was demonstrated. The 602-test snapshot retains the then-final `3337af` stress script and its unchanged-at-run-end 164 pins; current script `98b443a7211d1269a637973f4438add6f0fc8522d1f18e2e0954cd044aabd409` is the later test-only strengthening. The other 163 review inputs remain byte-identical. No 602-test rerun or additional unit-test count is claimed for that assertion.

No official transaction, native instruction timing, serial delivery, cancellation under real communication, firmware or physical PLC proof follows from these bindings or local models. Genuine newly generated bare-product editor validation remains a separate stage. Full parity remains the target; the closed forms above are an implementation increment.
