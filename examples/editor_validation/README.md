# Complex editor/simulator candidates

These are deterministic test programs, not hardware-ready applications. The
local runner checks SDK and VM results, explicit word values, actual exported
XML, reconstructed C++, recompilation and a second XML project:

```sh
python3 tests/editor_validation/run.py --output output/editor-validation/complex-next
```

The output directory must not already exist. Originals are preserved. Each
candidate has `program.smbp`, `program.audit.cpp`, `recompiled.smbp`, `trace.json`,
`expected.json` and `result.json`. The top-level `results.json` lists exact hashes,
stable phase observations and the input sequence. Native harness binaries stay
under the ignored output directory.

Each program has an I/O version and a `_memory.cpp` version. The latter uses
commands `%M800..%M802`, indicators `%M704..%M719`, and the same explicit words;
it uses no source-level physical I/O. This permits logic tests independently of
the unresolved editor I/O resource-claim issue. Inspect the actual generated IL
before calling a candidate memory-only, since compiler-generated constants can
also introduce references.

Only the local runner has been exercised here. Opening, compiling, saving,
reopening and running each exact candidate in the official editor/simulator are
separate pending checks. No physical PLC operation is performed by the runner.

## State, loops and computed arrays

`state_arrays.cpp` combines two bounded loops, a persistent four-element i32
array, computed indexing, native input edges and arithmetic. Start with commands
off. Pulse I0.0 (or M800), releasing between pulses. Holding it on counts only
once; a fourth pulse is ignored. I0.1 (M801) resets and takes priority.

| Accepted pulses | MD100 checksum | MW102 batches | MD104 first balance | MD106 last balance |
|---|---:|---:|---:|---:|
| 0 | 22000 | 0 | 1000 | 4000 |
| 1 | 29500 | 1 | 1250 | 5000 |
| 2 | 37000 | 2 | 1500 | 6000 |
| 3 | 44500 | 3 | 1750 | 7000 |

Q0.0..3 (M704..707) identify the checksum, Q0.4..7 (M708..711) identify the
batch count, and Q0.8..15 (M712..719) show checksum/250 as an eight-bit value.

## Timer, counter, edges and a latch

`timed_counter.cpp` uses TON0 at100ms/preset5, Counter0/preset3, input edges and
a persistent latch. First pulse reset I0.2 (M802), with the other commands off,
to establish a known counter state. Enable I0.1 (M801) and wait at least2s.
Then pulse I0.0 (M800), releasing between pulses. A pulse before the timer is
ready is consumed and is not counted later merely because the input stays on.

| Settled phase | MW120 count | MW121 timer value | MW124 latch |
|---|---:|---:|---:|
| Reset | 0 | 0 | 0 |
| Enabled, no fresh pulse | 0 | 5 | 0 |
| Three qualified pulses | 3 | 5 | 1 |
| Fourth qualified pulse | 4 | 5 | 1 |

MW122/123 show presets5/3. Q0.0 (M704) is ready, Q0.3 (M707) is counter DONE,
Q0.4 (M708) is the latch, and Q0.8..11 (M712..715) show the count. Exact timer
phase/timing is a separate question; the local trace uses100ms steps. These
values are a local-model expectation, pending official-simulator observation.

## Numeric/BCD diagnostics

`numeric_diagnostics.cpp` combines BTI/ITB16/32, CONCATW/LW/HW, the published
23241+21853 overflow/saturation example, explicit S18 reset, rotate/shift carry
snapshots and aliased MW/MD observations. All sixteen Q indicators (or
M704..719) should stay true in both I0.0/M800 modes.

| Field | Command off | Command on |
|---|---:|---:|
| MW140 raw sum | -20442 | -20442 |
| MW141 clamped sum | 32767 | 32767 |
| MW142 packed BCD word | 9296 | -26215 |
| MW143 decoded word | 2450 | 9999 |
| MD146 packed BCD dword | -2128394905 | -1717986919 |
| MD148 decoded dword | 81234567 | 99999999 |
| MD150/MD160 concatenation | 305407056 | 305437081 |

Negative packed BCD carriers are intentional. This program avoids the unresolved
negative DWORD-widening hypothesis and invalid arithmetic-result domains.
