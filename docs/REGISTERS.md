# FIFO and LIFO Registers

Declare global `plc::Fifo fifo{0};` or `plc::Lifo lifo{1};` with an explicit
literal ID in 0..3. Both modes share these four native `%R` resources; duplicate
IDs are rejected. Each Register holds sixteen signed 16-bit words internally,
without reserving sixteen ordinary `%MW` cells.

`set_input(plc::i16)` / `input()` read and write `%Rn.I`.
`set_output(plc::i16)` / `output()` read and write `%Rn.O`; writing O does not
change queued data. `empty()` and `full()` expose readonly BOOL flags `%Rn.E`
and `%Rn.F`. `update(bool reset, bool store, bool retrieve)` returns `void`.
Fresh Store and Retrieve requests insert and remove one word; held requests do
not repeat. FIFO retrieves the oldest word, LIFO the newest. An empty retrieval
retains O, a full Register refuses a store, and simultaneous fresh Store/Retrieve
requests do neither operation.

The local execution model captures all three arguments before each C++ call.
Repeated calls are permitted, and skipped calls retain the last called request
history. Reset clears the queue and I/O words, sets Empty and clears request
history in this local policy. The observed FIFO Reset+Store and self-status
traces constrain that policy; broader LIFO collisions, first-call TRUE,
repeated/skipped calls and cold/warm/STOP lifecycle remain pending native
confirmation. See the [native](validation/REGISTER-NATIVE-OBSERVATIONS.md),
[collision](validation/REGISTER-COLLISION-OBSERVATIONS.md) and
[self-status](validation/REGISTER-SELF-STATUS-OBSERVATIONS.md) records.

The current SMBP profile is TM200CE40T at actual Man21 (`FunctLevelMan21_0`),
with canonical three-input Register blocks driven by ordinary direct I/M
contacts. Complex source predicates are captured in compiler memory before
the block. The reader admits referenced default FIFO resources when the native
Registers collection omits their configuration, and explicit Lifo configuration.
Unknown configuration, operands and unproved graph forms fail explicitly.

The [dual example](../examples/register_queue.cpp) uses I0 for Reset, I1 for
Store, I2 for Retrieve, I3 to select 22 instead of 11, and I4 to write O=42.
Q0/Q1 are FIFO Empty/Full, Q2/Q3 LIFO Empty/Full, Q4/Q5 FIFO O=11/22,
Q6/Q7 LIFO O=11/22, and Q8/Q9 FIFO/LIFO O=42. Its twenty-frame trace covers
held buttons, simultaneous requests, retrieval order and empty output retention.

```sh
./m200c compile examples/register_queue.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp -o output/register-queue
./m200c check examples/register_queue.cpp --trace examples/register_queue_trace.json
```

The [integrated checkpoint](validation/REGISTER-INTEGRATION-RESULTS.md) records
799 passing local tests, exact dual generated output saved/freshly reopened with
No error, and separate repeated-call FIFO simulator Full/Empty observations.
The dual runtime controls and broader lifecycle/call contexts remain pending
the final batch. No physical controller,
firmware, scan timing, wiring or connected load is qualified by these checks.
