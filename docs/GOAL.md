# Current goal: Natal da Liberdade release

User scope revision: 2026-11-06. This release goal supersedes the earlier
requirement to finish whole-controller parity in the current delivery.
The [full parity contract](PARITY.md) remains a future-version objective.

Deliver a practical restricted-C++ compiler/SDK for the Schneider TM200CE40T
covering the Natal da Liberdade show. Prioritize correctness, compact Ladder
and controller memory limits. Use algorithms, loops, clocks, comparisons and
native blocks rather than expanded tables of application states.

## Included

- G01/G02: Boolean/digital I/O and edges; integer/bitwise/comparison logic,
  flags, useful constants and memory handling.
- G06/G07: useful subroutines; TON/TOF/TP, clocks, multiple timers and properties.
- G08: counters and FIFO/LIFO/shift/step/drum sequences needed for the show.
- G09: RTC/calendar/schedules, explicitly retained by the user.
- G11: Modbus READ/WRITE/WRITE_READ configuration, properties, states and errors.

Each included capability needs a supported C++/SDK expression, typed execution,
resource/conflict diagnostics, coherent native Ladder/SMBP and reconstruction
of equivalent C++ from the actual program/configuration.

## Delivery and acceptance

1. Finish and integrate the seven priority packages. Preserve partial work from
   the thirteen stopped packages; do not restart them automatically.
2. Three dedicated test agents execute local semantic, boundary, interoperability
   and composed-program checks. Implementation agents do not execute tests.
   Preserve the existing regression coverage and enforce code-size/memory budgets.
3. Exercise inputs/outputs, held/released buttons, reset, conditionals, loops,
   sequences, multiple timers, RTC scheduling and Modbus. Record independent
   expected results and forward/reverse comparisons; absence is not a pass.
4. After the priority implementation is complete, run one planned official
   editor/simulator campaign over the finite generated batch. Open/check/display
   Ladder/save/reopen exact artifacts and compare supported runtime scenarios.
5. Publish validated source, examples, hashes/results and professional English
   documentation in the personal public Git repository. All tests/builds stay
   local; GitHub Actions remains disabled.

Completion means the Natal scope is integrated and passes its local and supported
official-editor/simulator acceptance cases. A defect that prevents those show
programs from working remains required work. Other profile families stay in the
future inventory and do not block this version.

Windows/USB transfer, the physical TM200CE40T, electrical ports/loads, physical
timing/communication and retention need the future access described by the user.
Record these external gates explicitly without claiming they were tested.
Neither this release nor its simulator results establish full PLC parity.

See [roadmap](ROADMAP.md), [execution policy](PARALLEL-DELIVERY.md) and
[capability inventory](capabilities/COMPLETION-MATRIX.json).
