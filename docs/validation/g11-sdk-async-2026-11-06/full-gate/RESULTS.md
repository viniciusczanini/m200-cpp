# Final local G11 gate

One `make check`: **1,045 tests — 1,038 PASS, 7 FAIL, 0 ERROR, 0 SKIP**. Raw make exit **2**, wall time **334.358 s**. The raw log is preserved unchanged.

Six failures are the known native PendingOracle cases (VM + SDK for each): G01 cold/warm/STOP/RUN edge lifecycle; G08 SC reset with active CD history; G08 unresolved SBR/SC/DR endpoint/collision domains. Discovery fails explicitly before adapter invocation. These are not PASS.

The seventh failure is a test-input packaging gap. `test_timer_property_stress.TimerPropertyStressTests.test_all_bases_complete_and_write_only_the_explicit_new_report` completed its 15 generated Ton/Tof/Pulse controls, then could not read the untracked I1 corpus omitted by the authorized tracked-only snapshot. The local original matches the pinned manifest: 114,221 bytes, SHA256 `a4307729f0864133e414517ef49c37e6648f29d7403a8f9737e2f7367461a738`, Git blob `425372b07a34946b6363b78bd15a5fbf8727cc98`.

Root authorized one addendum: copy only that verified corpus and execute only the affected method once. **Follow-up: 1 PASS, exit 0, 35.063 s.** No source, test, expected value, or native oracle changed. No full-gate retry was performed. The raw full result remains 1,038/7; it was not rewritten as green.

Full snapshot: 1,076 inputs, 114,506,706 bytes; **74 core/SDK pins unchanged**. All selected execution inputs were unchanged through the full run. The follow-up has 1,077 inputs after the single documented corpus addition, with zero further input/core drift. Excluded G01 helper and panel-decoder files are absent. All runtime outputs are outside the snapshot.

Root changes during the full run were `docs/PARITY.md`, `docs/ROADMAP.md`, and a `.gitattributes` rule preserving raw publication logs. Exact drift is recorded; the tested snapshot was unaffected.

No newly observed compiler/SDK defect remains from this gate. Six native oracle gaps remain. This local result does not establish full parity or physical PLC runtime equivalence.

Publication proposal contains only logs, commands, classifications, provenance, pins and audits. It excludes the source snapshot, corpus bytes, binaries, temporary files, and generated runtime artifacts.
