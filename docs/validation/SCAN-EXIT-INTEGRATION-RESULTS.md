# Scan-exit integration results

The combined END/return and Modbus-recovery working tree passed the final
formatted **441-test suite in 140.079 seconds** on 2026-11-06. The baseline is
`95fefd85cb558ea94420508529588511e7172f32`; the count includes 18 scan-exit
tests and six new transport-recovery tests above the 417-test baseline.
The earlier preformat run also passed 441 tests and is a repetition, not
another set of distinct tests.

The final source/input pin covers 126 files: compiler modules, SDK, Python and
native test sources, fixtures, input JSON and C++ examples. Its digest is
`b08541f42f195f4f3011004feb8269de29290eba53dbca6732cc24461417513a`.
Root-owned documentation and generated artifacts are excluded. Exact individual
hashes, captured logs and scope are recorded in
[the integration manifest](SCAN-EXIT-INTEGRATION-RESULTS.json).

`make examples` completed successfully with 15 compile commands and 15
successful differential checks. Fresh non-mutating Ruff checks passed for
`m200 tests`; the format check reported 88 files. The root agent's broader
89-file pass is recorded separately so the scopes are not conflated.

Three fresh stress runs passed: control flow (12 cases/3,072 positions), native
logic (10/5,120), and digital I/O (49/12,800). The first two reports retain the
preformat Modbus hash; the digital-I/O report matches the final source hashes.
The final formatted regression suite passed separately. These 20,992 stress
position evaluations repeat existing recipe domains and are not added as new
distinct frames to the cached historical evidence: 15 stress scripts,
270,196 stress frames plus 18,176 public frames, totaling 288,372. Historical
reports remain preserved.

The dedicated local scan-exit candidate has 114 distinct trace positions. The
separate sequence-timer I/O and memory candidates have 4,834 total positions.
Their comparison stages and repeated runs do not multiply those counts. The
2,417-position official-save sequence readback compares an existing I/O trace;
it does not add new candidate frames.

The root agent recorded **11 official scan-exit simulator phases**, all matching
the expected Q indicators for the exact candidate hash
`6a5329a46799ff1f4c23a351175f3093d92115cf138324a2e4698f2a0d1e49a4`.
These include earlier output commits, retained later outputs, skipped-edge
behavior, fresh pulses and reset priority. MW220 was inferred through the
count1/count2 indicators; it was not directly watched. The sequence editor-save
readback preserved parsed semantics, hardware and typed graphics; the root
also recorded a fresh reopen with No error. A subsequent RUN after that reopen
requires its own separately recorded observation.

These are bounded local and simulator results. Native graphical END/EndCn XML
binding remains unverified; C++ return uses the supported Jump epilogue.
Physical PLC operation, electrical I/O, precise hardware timing and complete
library parity remain pending.
