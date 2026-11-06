# Three-timer sequence and button tests

[`sequence_timers.cpp`](sequence_timers.cpp) combines TON0, TP1 and TOF2, each
with a one-second base and preset 10. The sequence warms up, runs a pulse, then
holds an off-delay before completing. Persistent diagnostics expose accepted
starts, completions, aborts, rejected edges and each timer's current value.
[`sequence_timers_memory.cpp`](sequence_timers_memory.cpp) uses the same logic
with memory commands and indicators.

These are test programs. Their local and official observations are separate:
[local result manifest](../../docs/validation/SEQUENCE-TIMERS-LOCAL-RESULTS.json),
[official artifact evidence](../../docs/validation/OFFICIAL-EDITOR-RESULTS.json).
No physical-controller validation is implied.

## Reproduce locally

```sh
python3 tests/editor_validation/sequence_timers.py \
  --output output/editor-validation/sequence-timers-next
```

Use a new output directory. The runner compares the original SDK, emitted IL,
serialized JSON, normalized IL, actual SMBP, recovered C++, recompilation and
a second SMBP against expected outputs and words. Its two variants cover
4,834 distinct candidate/trace-position frames. Comparison stages and repeated
runs are excluded from that number. Deliberately shortened timing, level-based
starts and reversed RESET priority must fail; the timing mutation is checked
with its preset diagnostic masked so behavior must reveal the error.

## Commands and observations

| Command | I/O version | Memory version |
|---|---|---|
| START | `%I0.0` | `%M800` |
| Permission | `%I0.1` | `%M801` |
| STOP | `%I0.2` | `%M802` |
| RESET | `%I0.3` | `%M803` |

| Words | Meaning |
|---|---|
| `%MW180` | Phase: 0 idle, 1 TON, 2 TP, 3 TOF, 4 complete |
| `%MW181..184` | Accepted, completed, aborted, rejected edge counters |
| `%MW185..187` | TON, TP, TOF values |
| `%MW188` | TP or TOF remains active |
| `%MW189` | Reason: 0 accepted, 2 STOP, 3 permission loss, 4 RESET, 5 rejected, 6 complete |
| `%MW190..192` | Presets, all 10 |

Q0.0 identifies idle; Q0.1..3 identify the active stages. Q0.4..7 retain
completion, warmup, pulse and off-delay milestones until RESET. Q0.8/9 retain
abort/rejection observations. Q0.10..13 mirror permission, STOP, RESET and
START; Q0.14/15 expose the underlying TP/TOF states. The memory variant maps
these sixteen indicators to M704..719 in the same order.

## Manual simulator checks

1. Start with all commands off. Assert RESET, then release it.
2. Enable permission. Press START and keep it pressed for at least 35 seconds.
   The settled result is phase 4, accepted/completed 1/1, aborted/rejected 0/0,
   busy 0 and reason 6. Q0.4..7 stay on. Keeping START pressed does not restart.
3. Release START and press it again. After another completed cycle,
   accepted/completed become 2/2.
4. During an active stage, assert STOP or remove permission. Application stage
   outputs turn off, phase becomes idle, and the abort counter increments once.
   Restoring permission or releasing STOP while START remains held does not
   create a fresh start edge.
5. Assert RESET while active, including simultaneously with STOP. RESET clears
   counters and retained milestones and has priority; reason becomes 4.
6. Release START before requesting another cycle. A rising edge while a prior
   TP/TOF remains active is rejected. After it becomes idle, another fresh edge
   is required.

A native TP is not internally cancelled by this program. Abort/RESET masks the
application stage outputs, while the raw timer diagnostics may remain active
until expiry. The busy guard intentionally prevents overlapping starts.
GUI observations establish settled states and order; they do not measure timer
accuracy at millisecond resolution or prove physical PLC timing.
