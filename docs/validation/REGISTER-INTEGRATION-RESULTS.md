# Integrated FIFO/LIFO checkpoint

The four native Register identities are now connected through restricted C++,
SDK execution, typed JSON/operands, IL/VM, native configuration/Ladder and actual
reverse C++. Each FIFO/LIFO holds sixteen signed words in its native storage.
The [API guide](../REGISTERS.md) and [working example](../../examples/register_queue.cpp)
describe the supported Man21 profile.

## Local evidence

The frozen implementation passed **799 tests in 220.444 seconds, zero skips**.
All 330 pinned inputs stayed unchanged. The 95 Register-focused tests, examples,
ten optimization budgets and independent integration/capacity reviews also
passed. These are recorded runs; they were not repeated to write this report.

The unchanged dual example improved from 34 rungs/80 IL, 3 M/1 MW to
**22 rungs/56 IL, 1 M/0 MW**. Direct stable input pins avoid unnecessary captures;
a tightly constrained adjacent Register-word comparison avoids a scratch word.
Both rules correct demonstrated full-bank capacity failures. Native queues use
32 internal words separately from ordinary MW memory.

Actual officially saved dual and repeated-call programs passed literal expected
traces through six local forward/reverse routes: 20 dual frames and 41 repeated
frames. Their reverse rebuilds have 37/86 and 41/103 respectively; those rebuilds
have not been opened in the official editor.

## Official observations

- The exact 22/56 dual generated project opened, was saved and freshly reopened
  with **No error**. Its saved instructions/configuration matched the generated
  program. Its ordered FIFO/LIFO runtime controls remain pending the final batch.
- A separate exact 20/61 repeated-call FIFO product was accepted, saved and ran
  in the local simulator. Held Store reached Full; exclusive Reset showed Empty;
  another held Store reached Full; releasing Store and holding Retrieve showed
  Empty with O=11. The captures do not measure the number of scans to each state.
- The immediate post-RUN panel does not establish cold-start state. Generic
  guide EIO0000003289.04 p143 distinguishes cold/INIT from warm/STOP; plain RUN
  entry is not assumed to be cold initialization.

The initial Stop click only focused its button. Opening the next project then
ended the simulator connection; its specific PID and TCP502 listener were
verified absent afterwards. The evidence does not claim the first click stopped it.

[The machine-readable report](REGISTER-INTEGRATION-RESULTS.json) pins the source,
trace, generated/saved project bytes, captures, original suite log/input manifest,
compiler manifest and saved-reverse results. Evidence files are preserved under
[register-generated](editor-evidence/register-generated/).

## Remaining gates

The user deferred official editor/simulator work to a final batch while the
priority implementation continues. Dual runtime controls and broader first-call,
repeated/skipped LIFO, lifecycle and graph contexts remain open. Windows/USB
transfer, physical TM200CE40T ports, communication, timing and retention remain
separate hardware acceptance cases. This checkpoint does not complete the full
Register family or the whole controller profile.
