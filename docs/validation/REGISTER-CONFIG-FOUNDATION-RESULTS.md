# Register configuration foundation

The new [`register_xml.py`](../../m200/register_xml.py) is a standalone typed
configuration codec. **It is not integrated into the compiler, project reader,
Program model or SDK. Register programs remain gated and cannot be authored in
C++ through this foundation.** No Register queue/state implementation was added.

`read_registers` preserves explicit Fifo/Lifo modes and supplies the established
FIFO default only for referenced valid IDs 0–3. `write_registers` stages a typed
mapping before replacing only Registers; malformed existing/new data is rejected
without deleting unknown content or changing siblings. Modes use the small
RegisterMode enum; strings and integers are not silently coerced.

The focused local run passed **18 methods in 0.038 s, with zero skips** after an
observed RED run of 18 failures for the initially missing module. Ruff and syntax
checks passed. Seventeen methods always run against independent literal trees,
mode expectations, invalid forms and atomicity cases. One additional method reads
the two exact unpromoted local editor saves when present; it skips if those local
inputs are absent, and fails on a hash mismatch. No public fixture was promoted.

The authenticated inputs are FIFO save 85219725…b09189 (106489 bytes, omitted
Register row) and LIFO save 8d04a2bc…22c1ab (106627 bytes, explicit Lifo). The tests
also verify that the existing whole-project loader still refuses both projects.
These are configuration/readback tests, not new editor acceptance or Register
runtime, reset, edge, capacity or lifecycle evidence.

Source SHA256 pins:

- Codec: `8cccf50926e13978df2389afb48cf37409b451e8b4b80be86e1f3299dd292f71`.
- Tests: `07ebf1a24864e75551c561e6a5ce9ea049d2212568c19ef9d4a008952a577de3`.

The [JSON record](REGISTER-CONFIG-FOUNDATION-RESULTS.json) pins full source/input/log
hashes and the exact test command. [The implementation plan](../capabilities/REGISTER-IMPLEMENTATION-PLAN.md)
keeps the remaining operand, IR, SDK, graph, execution and integration work visible.

Independent read-only review found no actionable code defect: five literal
positives, 20 malformed-owned cases, four mapping-atomicity cases, five invalid
reference cases and both exact saved modes passed. Its 18-method repeat passed
in 0.044 s with zero skips. Simulating absent private inputs produced the expected
single explicit skip, without failures.

The final combined local suite passed **544 methods in 187.332 s, zero skips**,
with all 141 pinned inputs unchanged after the run and at report verification.
That total already includes the 18 foundation methods and 10 separate WRITE_READ_VAR
profile methods. Both optional lab input files were pinned and present. The full
log SHA256 is
`2d618087e5a01d38640151acfee5116f29b14e06532df676d39068af94351851`.

The WRITE_READ_VAR lane/root owned that single combined run; this lane did not
repeat the full suite. Focused/reviewer repetitions and negative subcases are not
added as extra tests or native runtime frames. Passing these gates does not wire
the Register codec into C++ or enable native Register projects.
