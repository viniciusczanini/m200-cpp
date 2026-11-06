# Active implementation and validation queue

The full TM200CE40T parity goal remains active. Work is pulled from this queue whenever its prerequisites are available. Only the GUI lane operates the official editor/simulator. All builds and tests are local; GitHub Actions remains disabled.

| Priority | Task | Lane / owner | State | Next proof |
|---|---|---|---|---|
| P0 | Diagnose three-timer simulator crash in ProcessMbitsEdges | GUI operator + separate Wine runtime chat | Unresolved; controlled probes ready | Crash preserved; exact original reached Online/identical/RUN; compare bounded candidates before changes |
| P1 | Exercise TON/TP/TOF sequence, held/repeated buttons, STOP/RESET/permissive interactions | Official GUI operator | Completion, held/fresh START, TON abort and RESET passed; further cases queued | Observe TP abort/drain, permission loss and rejected busy edges with direct words |
| P1 | Save/reopen I/O and complex projects; validate normal launcher persistence | Official GUI operator | Sequence save/readback/reopen passed; other projects and launcher restart queued | Preserve original bytes; compare editor-saved IL/configuration and reverse C++ |
| P1 | Publish validated increments with English documentation | Main agent | Validated integration checkpoint | Next combined 462 tests passed; Actions disabled; publish reviewed source and evidence |
| P2 | Native END/ENDC/ENDCN and C++ early-scan exit parity | Compiler lane | Native graph import implemented; combined 462 tests passed; Jump export retained | Publish reviewed native graph bindings; extend actual runtime controls separately |
| P2 | Reconcile timer bases, retentive/dynamic modes and functional-level gates | Capability/schema lane | 10 ms binding implemented and saved/reopened; option/level matrix running | Real editor-created configuration plus exact generated candidate validation; no enum-only promotion |
| P2 | Complete local Modbus coverage with official configured projects | Protocol/runtime lane | Transport fix and independent review passed; official profiles queued | READ/WRITE/WRITE_READ and transport/status edge cases; separate local protocol, editor, simulator and hardware evidence |
| P3 | Native program structure: subroutines, tasks/events, UDF/UDFB and Grafcet | Compiler lane | Queued | Closed parser/lowering/reverse/runtime support and negative tests |
| P3 | Numeric gaps: native expressions, constant tables, float/system flags and error recovery | Compiler lane | Queued | Supported domains and flags from sources, independent oracles, real editor/simulator tests |
| P3 | Remaining native blocks: registers, drum/SBR/SC, RTC/schedule and PID | Library lane | Queued | Complete operands/configuration semantics, roundtrip and runtime checks |
| P3 | Hardware functions: FC/HSC, PWM/PLS/PTO/motion, expansion I/O and lifecycle | Hardware-profile lane | Queued | Authentic configurations, resource conflicts and diagnostics; physical tests remain pending access |

## Prepared GUI cases

- 15 timer-profile candidates: 10 ms, retentive TON/TOF across FL3.2/3.3/4.0, dynamic across FL11/12, TP-retentive negative, and TM5/TM6 at 1 ms. Man6 remains a documented conflict, not presumed acceptance.
- 3 IL-only native END-family candidates for authentic graphical binding discovery; the first ENDC candidate opened with No error and was converted to Ladder by the official editor. Binding implementation remains queued. No invented graphs or disabled validation.
- 5 bounded sequence-crash controls: Manual1024 variants and minimal TON/TP/TOF, TP and TOF programs.

## Completed evidence

- 441 combined regression tests passed in the current formatted integration. The earlier baseline had 417 regression tests and all 15 stress recipe scripts passed locally; 288,372 distinct public/stress frames.
- Six combined candidates passed 276 distinct local candidate frames.
- Three-timer I/O/memory candidates passed 4,834 distinct local candidate frames, eight comparison stages each and deliberate behavior mutations.
- Early scan exit passed 114 local candidate frames and 11 official simulator input/output phases.
- Official simulator: memory 0/1/0, digital I/O 0/1/0, state/array loops with held buttons/reset, TON+counter/latch and numeric diagnostics were observed.
- Culture-only runtime correction eliminated false I/O reservation errors on identical bytes; invalid Q0.16 remains rejected.
- Three-timer original and watch-only derivative open with No error. The derivative simulator startup crashed before RUN; that runtime test is not counted as a pass. The unchanged original subsequently completed TON/TP/TOF in RUN; GUI-created watch showed held-start 1/1, fresh-start 2/2, STOP abort once and RESET dominance.

See [official artifact evidence](docs/validation/OFFICIAL-EDITOR-RESULTS.json), [local baseline](docs/validation/OFFICIAL-EDITOR-LOCAL-RESULTS.json), and [parity contract](docs/PARITY.md). A missing feature is unfinished toolchain work, not evidence that the PLC cannot perform it.
