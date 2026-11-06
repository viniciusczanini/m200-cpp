# Three timer sequence review

Review date: 2026-11-06, compiler revision `95fefd8`. No actionable algorithm or
local-oracle defect was found in the reviewed sequence examples and runner.
An initial diagnostic derivative crashed while launching the simulator. The GUI
operator subsequently reported a completed RUN cycle from the original program
with a GUI-added watch table. These are separate artifact observations; the
diagnostic derivative's crash cause remains unresolved.

Reviewed both `examples/editor_validation/sequence_timers*.cpp` variants,
`tests/editor_validation/sequence_timers.py`, the
[local result manifest](SEQUENCE-TIMERS-LOCAL-RESULTS.json), and the
[button-test instructions](../../examples/editor_validation/SEQUENCE_TIMERS.md).
No source, existing result manifest, GUI or remote state was changed by this
review.

## Local algorithm and oracle checks

All 15 recorded source/artifact hashes and the package digest match. A fresh
focused rerun passed **2,417 frames per variant**, or **4,834 distinct
candidate/frame positions**, across all eight recorded comparison stages:
original IL, JSON, normalized IL, original native SDK, actual XML, recovered
native SDK, recompiled IL and recompiled XML. All three mutations per variant
were rejected: shortened TON with its preset diagnostic masked, level-triggered
START, and STOP incorrectly overriding RESET. Temporary outputs were discarded.

The elapsed-time oracle does not call the implementation's timer helpers. Its
14 literal settled checkpoints pass. The reviewer also checked seven exact
timer boundaries per variant against hand-derived values: warmup at 10 seconds,
TP expiry at 20 seconds and TOF expiry/completion at 30 seconds after an accepted
start, with the immediately preceding scans still in their former stages.
These checks use the documented local 100 ms scan model.

All 16 simultaneous START/permission/STOP/RESET combinations were probed during
TP for each variant. RESET clears application counters/milestones and dominates
the other controls; STOP or permission loss masks stage outputs and increments
the abort count once. Held START creates no new edge. A fresh disallowed START
increments rejection; when combined with an abort, its later diagnostic write
can leave reason 5 while the abort count still increments.

Timer order is consistent: TON can advance the phase and start TP in the same
scan; TP expiry starts the TOF interval in that scan. Abort/RESET does not cancel
the underlying TP. A separate probe reset immediately after TP started,
rejected a fresh edge at TP expiry while TOF still had 100 ms to drain, rejected
an automatic retry from held START, and accepted a later fresh edge after both
timers drained. Raw timer indications and application stage outputs remain
distinct.

SDK, VM and conversion stages share intended semantics and implementation
modules. This agreement, including the independently expressed oracle, is not
Schneider simulator or physical-controller proof.

## Simulator failure and allocation comparison

The GUI operator reported **No error** when opening the original I/O candidate,
SHA-256 `ddc2150a010e99b988a0ffc21807fce229190cf88e25d8d731c45afd10ad920b`.
A WatchLists-only diagnostic derivative, SHA-256
`83b73ea98fee422e230bf9d23f1164696e4e2de361d512916ebcd88abde5da67`,
crashed while launching the simulator before RUN. The reviewer read the local
`compiler-editor-culture-test-actual.log`: after the recorded
`2026-11-06 02:31:42.7282` launch request, it contains
`System.AccessViolationException` at `ProcessMbitsEdges()` / `MastTask(Void*)`
and a native page fault. The exact original and derivative were preserved.
Removing WatchLists makes their full XML trees equal after ignoring formatting
and attribute order, including the actual IL and hardware configuration.

| Artifact | Referenced M bits | Unique declared M symbols | Bit allocation | Word allocation |
|---|---|---:|---|---:|
| Sequence I/O | M500..M526 | 27 | Automatic, no ForcedCount | Manual 4007 |
| Previously running state arrays | M500..M517 | 18 | Automatic, no ForcedCount | Manual 4016 |
| Previously running timed counter | M500..M520 | 21 | Automatic, no ForcedCount | Manual 4001 |

All three have the same complete hardware subtree and execution settings and
exactly one edge instruction, `LDR %I0.0`. The profile declares 1,024 M bits,
8,000 MW words and 255 timers. Sequence references are I0.0..3, Q0.0..15 and
TM0..2, with no jump labels or duplicate M metadata. Its timer descriptors are
TON0, TP1 and TOF2, each non-retentive, static preset 10 and base OneSecond.

The original template's Manual bit count was 512; both previously running
controls also reference addresses above 511. Thus crossing that boundary or
omitting an explicit Automatic count alone does not distinguish this failure.
The actual native allocation and failure cause remain unobserved. No conclusion
attributes the crash to Wine, WatchLists, timer types, or compiler allocation.
Subsequently, the GUI operator reported that the original sequence completed
TON, TP and TOF in RUN, with a watch table added through the official GUI. After
START remained held for several minutes, the reported settled words were phase
4, accepted/completed 1/1, aborted/rejected 0/0, timer values 0/0/10, busy 0 and
reason 6. The separate official evidence record must bind any saved GUI-watch
derivative to its own hash. This positive control does not explain the earlier
programmatically constructed WatchLists derivative's crash. Further button
cases, timing measurements and runtime isolation remain separate work; local
model passes cannot close the crash finding.
