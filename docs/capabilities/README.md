# Capability coverage and completion matrix

The target is [functional equivalence with the official TM200CE40T profile](../PARITY.md): every algorithm accepted for that profile must have an equivalent supported C++ expression and native project. Current compiler gaps remain work toward that goal.

[COMPLETION-MATRIX.json](COMPLETION-MATRIX.json) is the implementation and evidence index. It retains all **161 instruction records and 89 hardware records** from [instructions.json](instructions.json) and [hardware.json](hardware.json). These 250 IDs overlap and include documented absences; they are not 250 independent features or a completion percentage. [HARDWARE-AUDIT.md](HARDWARE-AUDIT.md) records the primary-source conflicts.

## Reading the matrix

Each ID keeps its source domain and canonical source-record hash. The pinned catalogues retain its original operands, modes, limits, constraints, model applicability and primary-source/page references. Its `profile` resolves the exact supported subset, phase states, code/tests/evidence and the next concrete test. Its `work_package` assigns the remaining work to [release Tasks 4 or 5](../superpowers/plans/2026-11-06-compiler-finish.md); unresolved model eligibility returns to Task 3.

The eight phases are C++/SDK, IL/VM, SMBP/graphics, reverse conversion, local oracle, official editor, official simulator and physical controller. They distinguish source-equivalent lowering from exact native-opcode import, isolated serialization components from complete compiler integration, and handbuilt diagnostics from generated products. No current profile claims completion of its whole catalogue family.

The catalogue API in `m200/capabilities.py` still supplies conservative documentary `missing`/`pending` defaults. Those defaults do not describe current implementation progress. The matrix supplies the separate scoped overlay; source research alone cannot promote an implementation phase. Existing historical reports remain tied to their recorded artifacts and versions.

## Current profiles and next gaps

| Area | Implemented scope | Remaining work |
|---|---|---|
| Boolean and digital I/O | 24 embedded inputs and 16 outputs process images, M memory, allowlisted system bits, word-bit and packed groups, native I/M edge contacts, expression-edge expansion, stack/parenthesis normalization | Remaining operand banks, system permissions, edge lifecycle, active filters/latches/alarm/fallback and immediate I/O |
| Numeric and control flow | Explicit i16/i32/f32 operations, comparisons, shared MW/MD/MF, conversions, fixed arrays/indexing, loops, labels/jumps and early returns | Remaining operations/banks, numeric flags and error recovery, ASCII/strings/native table operations and native construct import |
| Subroutines | C++ descriptors, separate contexts/origins, shared scan image/clock, local returns and reverse. Native export: actual Man21, Master section 0 and one stateless leaf section 2 with admitted call/series graphs | Wider native layouts, stateful/control-flow leaves, nested calls and remaining leaf graph forms. See [SDK profile](../SUBROUTINES.md) and [generated-product results](../validation/SUBROUTINE-COMPILER-RESULTS.md) |
| Timers | TON/TOF/TP and properties; **10 ms XML is admitted**, backed by exact Man21 false-option TON/TOF/TP save/fresh-reopen evidence. True-option export admits only 1000 ms at Man21 retentive TON, retentive TOF and nonretentive dynamic TON | Other true-option contexts, graph/property combinations and lifecycle cases. See [10 ms binding](../validation/NATIVE-END-TIMER-10MS-RESULTS.md) and [generated timer observations](../validation/TIMER-GENERATED-PROJECT-RESULTS.md) |
| Counters and Register foundation | Counter API/configuration/local state/reverse and bounded native graphs; isolated FIFO/LIFO configuration and canonical graph codecs | Counter collision/lifecycle questions; **Register C++/IR/VM/reverse/project integration**; drum/shift/step, RTC/schedule and PID |
| Modbus | READ/WRITE/WRITE_READ APIs, local asynchronous protocol models and native static profiles, including bit/single objects and bare/full-pin Execute/Abort/status graphs | Dynamic properties, remaining native channel/pin/configuration profiles and native transactions. [Generated bare products](../validation/MODBUS-BARE-ABORT-GENERATED-PROJECT-RESULTS.md) passed save/fresh reopen |
| Scheduling and hardware | Strict isolated normal MAST profile, inactive/default hardware preservation and explicit unsupported-active refusal | Periodic/event tasks, priorities/watchdog, lifecycle/retention, FC/HSC/pulse/PTO/motion, expansion/cartridges, drive blocks and service configuration |
| Projects and reverse | Authentic CE40T baseline, strict IL/graph/config checks, template preservation, actual-program reverse and exact generated-product editor/simulator observations | Remaining native profiles, final interoperability corpus and the future physical acceptance checklist |

The official Machine Expert Basic editor and simulator are available in the existing Mac/Wine lab and provide the recorded practical acceptance evidence. Actual controller firmware, Windows/USB transfer and physical I/O/communication checks remain separate release gates; they do not prevent the remaining software work.

## Keeping the inventory finite

For each named gap, implement its API/configuration/state, native instruction and graphics, reverse path, independent boundary/error tests and the exact editor/simulator case. Unknown active configurations remain explicit errors. Optional improvements do not reopen a passed gate without changed inputs or a concrete counterexample.

[The consistency tests](../../tests/test_completion_matrix.py) require exact 250-ID closure, valid phase states, existing scoped evidence, pinned catalogues/observations and finite next-test assignments. They reject dropped/extra IDs, stale source hashes, source-only implementation claims and unproved whole-family completion.

Primary documents: [M100/M200 programming](https://www.se.com/id/en/download/document/EIO0000002019/), [hardware](https://www.se.com/ph/en/download/document/EIO0000002023/), [generic functions](https://www.se.com/us/en/download/document/EIO0000003289/) and [operation](https://www.se.com/us/en/download/document/EIO0000003281/). The catalogues retain the audited editions and hashes.
