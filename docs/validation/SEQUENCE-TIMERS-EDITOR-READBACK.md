# Sequence timers: official-save readback

Readback performed on 2026-11-06 for TM200CE40T. No compiler, source program,
original project or saved project was changed during this investigation.
The official GUI provenance and the addition of MW180–189 animation rows were
provided by the root agent; this task performed local file inspection and
execution, without GUI or physical PLC operations.

## Result

**No substantive program or hardware drift was detected in the supported
domain.** Both projects load successfully. They contain the same 191 rungs,
440 instruction lines, three timer configurations and 2,043 Ladder entities.
Their parsed instruction semantics and typed graph semantics/geometry are
exactly equal. The failing equality assertion is `original.rungs == saved.rungs`:
numeric expression formatting remains different in 55 loaded rungs.
The hardware comparison passes.

| Preserved artifact | Bytes | SHA256 |
|---|---:|---|
| `output/editor-validation/sequence-timers-official/original.smbp` | 760861 | `ddc2150a010e99b988a0ffc21807fce229190cf88e25d8d731c45afd10ad920b` |
| `output/editor-validation/sequence-timers-official/editor-saved.smbp` | 794739 | `8f34c6b4e5cf44440b444048d3bdc3a1337fc3f380d7b620a8d93832e61aa767` |

## Instruction and graph comparison

The comparison did not remove all whitespace and assume equivalence. Each rung
was split into its actual label and decoded instructions. Numeric operations
were compared through `instruction_operation`; comparisons were compared
through `comparison`. Operator, target, typed operands, addresses and order all
match. Other decoded operator/operand pairs match directly.

Of 440 raw XML instruction texts, 431 changed formatting. Existing loading
already collapses padding between tokens. The remaining 55 differences are:

| Parsed instruction category | Changed expressions | Parsed meaning |
|---|---:|---|
| Numeric operations | 41 | Equal target, operation and typed arguments |
| LD comparisons | 10 | Equal typed operands and comparison operator |
| AND comparisons | 4 | Equal typed operands and comparison operator |

For example, `[%MW4000:=0]` became `[ %MW4000 := 0 ]`.
Neither artifact contains labels or jump instructions. In particular, there
was no JMPC-to-other-opcode transformation to explain this difference.

All 2,043 graphical entities retain their type, bound descriptor or parsed
numeric expression, row, column, connection and sequence. No graphical fields
were added or removed. The editor populated 331 graph Symbol values from the
existing symbol bindings and 28 S13 contact comments; those S13 contacts now
use `SB_FIRSTRUN`. It formatted 41 OperationExpression and 14
ComparisonExpression values consistently with the IL changes. These graph
annotations explain why every raw LadderElements subtree differs despite
equal typed graphics. Rung names, MainComment, Label and IsLadderSelected
values are unchanged.

## Configuration and metadata changes

HardwareConfiguration is equal when comparing element names, attributes,
scalar values and child order, disregarding indentation. ProjectVersion,
ManagementLevel, CurrentCultureName, GlobalProperties, report configuration
and user-label display configuration are also unchanged. The same software
collection tags remain present; their serialization order changed.

These are the five changed software collections after matching by tag:

| Collection | Original | Saved |
|---|---|---|
| Pous | Generated instruction/graph text | Formatting and graph annotations described above |
| Timers | Explicit TON type and false mode flags | TM0 Type omitted; false IsRetentive/IsDynamicPreset omitted for all three |
| MemoryBitsMemoryAllocation | Allocation=Automatic | Empty element |
| TimersMemoryAllocation | Allocation=Automatic | Allocation omitted; ForcedCount=3 |
| WatchLists | Empty | One animation table containing MW180 through MW189 |

The parsed timer configurations are exactly equal: TM0=TON, TM1=TP and TM2=TOF,
each with a 1,000ms base, preset10, 10,000ms duration, non-retentive state and
static preset. The existing reader already handles the omitted TON/false
defaults; no validation was relaxed for this file. The allocation serialization
change is recorded explicitly rather than calling the whole software
configuration byte-identical. The referenced timer extent is three. This
readback does not resolve unrelated indexed-memory allocation boundary cases.

The animation items use Decimal representation with IsTraced=false. No stored
write/force value was added to these items. Every other software collection is
unchanged under the same XML-tree comparison.

The project Name changed from `m200-cpp EXPERIMENTAL` to `sequence_timers`;
FullName changed from `program.smbp` to its P-drive Save As path. Parsed symbols,
counters and communications remain equal. The only difference in the loaded
Program metadata is the expected `project_sha256` identifying different files.

## Independent oracle and reverse execution

The exact saved artifact passed the existing independent elapsed-time/event
oracle for all **2,417 trace positions**, including 14 hand-computed settled
checkpoints, all 16 outputs and MW180–192 at every position. Checks covered:

- Original XML VM and official-saved XML VM.
- Official-saved normalized VM.
- C++ reconstructed from the saved XML, compiled and run through the native SDK.
- Recompiled reconstructed C++ in the VM, then a second exported/reloaded XML.

The original and saved artifacts reconstruct to **byte-identical C++**:
SHA256 `94142016582de609bd6be5f70a0b6362c0d1e51b7039007f435ad1365565fa9c`.
The independent oracle covers held starts, missing permission, normal
completion, fresh restart, STOP/reset priority, aborts in TON/TP/TOF and native
TP/TOF draining before another accepted start.

There are 4,834 direct original/saved file-version frame evaluations here, but
they compare the same previously recorded I/O trace. They are not additional
distinct candidate frames and are not added to the earlier 4,834 I/O-plus-memory
candidate total. The memory variant was not officially saved in this pair.

Reproduction/evidence script:
`output/editor-validation/sequence-timers-official/readback/verify.py`.
Its derived C++, XML, trace, expected values and machine-readable results are
in that same disposable directory. The results file records exact input,
runner, compiler-module, SDK and derived-artifact hashes:
`output/editor-validation/sequence-timers-official/readback/results.json`,
SHA256 `46b5d135052c9e742fb9d777aeb224a75f099a8ab829e34e4727b5515f3ab3e8`.

The compiler hashes describe the loaded readback snapshot. The independently
owned `m200/modbus.py` changed again after that capture; its recorded hash is
therefore historical, not a claim that the final combined tree still matches.
The seven scan-exit compiler paths and all preserved/readback artifacts still
match their captured hashes. The root agent validates the combined tree
separately. This program has no configured communication blocks.

No compiler fix was required. Literal IL-string equality is unsuitable as the
sole semantic readback assertion for this editor save. These results establish
equivalence within the parsed domain and this independent local trace. They
do not establish physical timing, every possible input sequence, hardware
operation or complete library parity; the root agent records official GUI
observations separately.
