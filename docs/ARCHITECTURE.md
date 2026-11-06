# Architecture and semantics

m200-cpp targets **TM200CE40T**, with the actual firmware, functional level, editor version, and hardware configuration forming part of the acceptance profile. The final contract is [functional parity](PARITY.md), not permanent restriction to today's implementation.

This guide describes the current local model and its boundaries. The detailed capability and validation records linked below retain source pages, hashes, conflicts, and historical decisions; many are in Portuguese.

## Compiler and reverse path

| Stage | Responsibility | Main implementation |
|---|---|---|
| C++ frontend | Invoke Clang, inspect its AST, accept a closed language/SDK subset | `m200/frontend.py`, `sdk/plc.hpp` |
| Lowering | Preserve evaluation order, state, short-circuit effects, and same-scan control flow | `m200/lower.py`, feature modules |
| Allocation | Map private virtual cells into physical M/MW space while reserving explicit addresses | `m200/allocation.py` |
| Instruction validation/execution | Check supported IL and execute the local scan model | `m200/il.py` |
| Ladder normalization | Expand supported complex logic into the known graphical subset | `m200/ladder_lowering.py` |
| Project reader/writer | Preserve recognized configuration and reconcile IL with Ladder | `m200/project.py`, XML feature modules |
| Reverse compiler | Reconstruct C++ from real instructions and block configuration | `m200/reverse.py` |
| Native reference | Compile and run original/reconstructed C++ against the SDK model | `m200/native.py` |

The frontend does not translate source by text substitution. Unknown AST nodes and declarations outside the supported SDK boundary fail explicitly. The project reader likewise does not use comments or cached C++ as program logic.

`compile` exports the actual instruction model, a readable IL listing, reconstructed audit C++, source maps, and a resource/hash report. An SMBP candidate additionally requires a supported target template. `decompile` accepts supported SMBP or program JSON, not the standalone `.il` listing.

`check` compares original C++, IL execution, and reversed C++ on the same 16-output trace. It executes native local code and is not a sandbox. The SDK and executor share modeling assumptions; specialized suites add independent expected values and inspect more internal state. Finite tests do not prove equivalence for every program or official compatibility.

## Source language and scan order

Supported source constructs include boolean variables, initialization, sequential assignment, `if/else`, `!`, `&&`, `||`, boolean XOR/equality, compatible typed numeric comparisons, fixed-capacity arrays, and same-scan control flow.

A bare `return;` exits `scan()` through the output-commit epilogue, preserving earlier writes and retained outputs. It works inside supported loops and conditional/goto paths. Imported operand-free END/ENDC/ENDCN use their native accumulator condition and export through supported Jump graphics; native END graphical entities remain unverified. See [scan-exit semantics](capabilities/SCAN-EXIT.md).

Boolean helper functions may have one return expression, with no recursion or explicit state writes. Numeric intrinsics inside an expanded expression retain their S17/S18 side effects. This is not support for arbitrary C++ functions or classes.

The local execution contract is:

- A single master `scan()` runs once per frame.
- Used inputs are captured for the scan. The logical output image observes prior writes in that same scan; physical output writes are consolidated at the end.
- Common globals and used outputs receive generated first-RUN initialization. Globals then persist between scans. Configurable physical retention is not implemented by this rule.
- Local declarations initialize when executed, including on repeated visits inside a loop.
- Expression snapshots and real branches preserve sequencing and short-circuit evaluation, including flags and indexed accesses with side effects.

The direct embedded API uses literal indices: `input(0..23)`, `output(0..15, bool)`, and `output_state(0..15)`.

The current frontend rejects ordinary application arithmetic with implicit C++ promotions, unsigned application types, multidimensional arrays, arbitrary pointers/references, application classes, exceptions, threads, external functions, unsupported header declarations, and unknown AST constructs. Use explicit `plc::*` alternatives where provided. Native algorithms without a supported alternative remain coverage gaps.

The complete PLC profile still requires work on tasks/events and priorities, subroutines/UDF/UDFB, Grafcet, immediate I/O, retention and lifecycle, expansions, strings/tables, RTC/PID, HSC, PWM/PLS/PTO/motion, and remaining system objects and communications. `read_m`, `write_m`, and `system` also serve the audit path; system-object access is an allowlisted subset, including clocks/first-scan and implemented error flags, not a full S/SW map.

## Resource allocation and limits

| Resource | Current target/model range | Allocation rule or qualification |
|---|---|---|
| M bits | 1,024, addresses `0..1023` | Globals, instance state, explicit reservations, and private temporaries share the bank |
| MW words | 8,000, addresses `0..7999` | Shared with MD/MF; complete communication buffers and explicit images are reserved |
| MD / MF | Starts `0..7998` | Each occupies two adjacent MW cells; these are not separate 8,000-element banks |
| Timers | `TM0..TM254` | 1 ms timers are restricted to `TM0..TM5`; a `Clock` uses two timers |
| Counters | `C0..C254` in the local model | Native preset range `0..9999`; exact profile/lifecycle still needs confirmation |
| Jump labels | 64 native IDs | Compiler-generated labels also consume this documented budget |
| Communication instances | Up to 32 per kind in the local model | Template functional level can restrict export to 16 before 10.1 |

The allocator considers the control-flow graph, loops, liveness between scans, and instruction order within a rung. It reuses private cells only when their values do not coexist. Globals and instance state retain unique cells; explicit addresses, raw memory images, and entire communication buffers remain reserved. The preferred starts M500/MW4000 are placement preferences, not half-bank limits.

MW/MD/MF aliases overlap physically, including odd starts. Typed 32-bit array elements use a stride of two words. Partial writes must preserve live neighboring data. Reused cells have `compiler_reused_*` symbols; those names do not represent independent persistent variables. `metadata.allocation` records virtual/physical counts and reservations.

Allocation is conservative and not proven optimal. Compiler expansion and a second translation of audit C++ can exhaust memory or the **local 10,000-instruction program cap** even if a smaller native implementation exists. That instruction cap is a tool guard, not a demonstrated PLC capacity limit. Lowering and graph analysis also have local complexity guards.

Diagnostics and documentation must distinguish an identified controller limit, unsupported source syntax, a compiler/exporter gap, and unverified behavior. None of these categories should silently become another.

See [allocation review](validation/ALLOCATION-REVIEW.md), [memory allocation results](validation/MEMORY-ALLOCATION-RESULTS.json), and [copy/expansion costs](capabilities/COPY-FUSION.md).

## Numbers, flags, and conversions

The application numeric types are `plc::i16`, `plc::i32`, and `plc::f32`. Use explicit intrinsics such as `add_i16`, `add_i32`, or `add_f32` to select representation and width. Ordinary `+ - * /` on application values are rejected. REAL literals use an `f` suffix. Comparisons `== != < <= > >=` require compatible types.

The 53-intrinsic subset covers arithmetic, remainder, word logic, shifts/rotations, square root, selected REAL functions, and explicit conversions. `./m200c capabilities` lists the current APIs; documentary catalogue entries are not implementation claims.

Invalid literals, impossible addresses, and invalid shift counts fail. Integer S17/S18 behavior is explicit in the local model:

- `system(17)` reads the last bit ejected by a shift/rotation; `clear_shift_carry()` clears it.
- `system(18)` reads sticky arithmetic error/overflow; `clear_arithmetic_error()` clears it.
- ADD/SUB/MUL/ABS and minimum-value divided/remainder by `-1` use modular result bits with S18. Apart from documented corroborating cases, the exact overflow results remain a local policy awaiting physical tests.
- Literal operations are still emitted when necessary to preserve flag effects. Guards, snapshots, and loops preserve when an operation executes.
- Integer division by zero and negative square root set S18 and stop the local model instead of inventing undefined result bits. General recovery from indeterminate results, REAL `%SW17`, and remaining arithmetic errors are incomplete.

Stopping the local model is not a claim that the controller stops the same way. Native algorithms that handle these errors remain part of the parity goal. EXPT and DEG/RAD remain refused pending adequate semantic evidence.

The conversion subset includes native BTI/ITB (`bcd_to_int`, `bcd_to_dint`, `int_to_bcd`, `dint_to_bcd`), CONCATW (`concat_words`), and DWORD (`int_to_dint`). BCD represents four/eight unsigned decimal digits in signed carriers: a high nibble of 8 or 9 does not make the packed decimal negative. Valid conversions preserve prior S17/S18. Invalid BCD sets S18 and stops before writing a fabricated result. CONCATW receives the low word first, then the high word. DWORD uses sign extension locally; negative operands still need physical confirmation.

See [integer flags](capabilities/INTEGER-FLAGS.md), [conversions](capabilities/CONVERSIONS.md), and examples [numeric control](../examples/numeric_control.cpp), [flags](../examples/integer_flags.cpp), and [conversions](../examples/conversions.cpp).

## Arrays and indexed memory

Fixed-capacity arrays of `bool`, `i16`, `i32`, and `f32` accept literal or computed `bool`/`i16`/`i32` indices. Computed arrays occupy contiguous regions. Partial initializers and `{}` zero the remainder; uninitialized local arrays are refused. Globals initialize on first RUN and persist; locals reinitialize each time their declaration executes.

Out-of-range literal indices fail compilation. For computed out-of-range indices, the experimental model sets sticky S20 and uses the first element as fallback after overflow-safe index validation. This is a tool policy; out-of-range `[]` is undefined in desktop C++, so differential tests do not run the original C++ in that domain. The reverse path recovers real operands and addresses, not necessarily array syntax.

Native indexed word APIs use an explicit global image:

```cpp
#include <plc.hpp>

plc::WordMemory image{64};  // Reserve MW0..63 for application data.

void scan() {
    plc::write_word(0, 3);
    plc::write_word_indexed(16, 0, 42);  // MW16 + contents of MW0 -> MW19.
    plc::i16 value = plc::read_word_indexed(16, 0);
    plc::output(0, value == 42);
}
```

The second argument is the literal **address of the index MW**, not the offset itself. Dword/REAL variants also measure offsets in words, and validate both occupied cells. Negative offsets may be valid when the final address remains in range. An error does not modify the original index. S20 remains set until `clear_index_error()`; direct S/ST writes to it are rejected. On error, native indexed access falls back to its base address.

Guards preserve the logical `WordMemory` extent even when compiler temporaries occupy higher addresses. The entire image is reserved. The local native model uses the highest directly referenced word as its bound; interactions with manual over-allocation, omitted/default XML allocation, and isolated symbols are not externally resolved. Ambiguous imported indexed profiles are refused.

Raw native AND/OR contacts with indexed comparisons are blocked until their access/error order is established. C++ `&&`/`||` remain supported by emitting a snapshot/branch before the access. Indexed Operation/Comparison serialization is experimental and needs editor/PLC evidence.

Computed boolean arrays and raw `read_m_indexed` / `write_m_indexed` work in C++/IL/VM/reverse. Raw access declares global `BitMemory` and `WordMemory` images, with the MW contents interpreted as a bit offset. **Indexed-bit SMBP import/export remains blocked** pending the documented FL10.0 mapping and target-profile evidence.

See [dynamic arrays](capabilities/DYNAMIC-ARRAYS.md), [indexed semantics](capabilities/INDEXED-SEMANTICS.md), [format research](capabilities/INDEXED-ORIGINALS.md), and examples [arrays](../examples/dynamic_arrays.cpp), [indexed words](../examples/indexed_words.cpp), and [indexed bits](../examples/dynamic_bits.cpp).

## Same-scan control flow

`while`, `for`, `do/while`, `break`, `continue`, labels, and `goto` lower to native jumps. All visited iterations execute within the same scan; the compiler does not silently spread a loop over several scans. Use explicit typed increments, for example `i = plc::add_i16(i, 1)`. The reverse compiler reconstructs labels and `goto` from actual IL.

The local VM defaults to 100,000 executed instructions per scan. The Python API accepts `Machine(program, instruction_limit=...)` within its local supported range. Exceeding the guard raises an error; it is neither successful early loop completion nor an emulation of the physical watchdog.

The exporter emits the observed `Jump/JMPC` graphical form after lowering. Direct native `JMP/JMPCN` graphics and additional official control structures still have evidence/implementation gaps. See [control-flow research](capabilities/CONTROL-FLOW-RESEARCH.md) and [loops example](../examples/loops.cpp).

## Timers and clocks

Global `Ton`, `Tof`, `Pulse`, `Clock`, `RisingEdge`, and `FallingEdge` instances are locally implemented. The current frontend allows one static `update` occurrence per instance; an entirely unused declaration is allowed but may reserve resources. Loops/jumps can visit that occurrence zero or multiple times in a scan, updating state on every visit. Some predicated branch forms remain rejected; enable/disable is an explicit argument.

`Clock{milliseconds}` is a nonblocking local clock made from two timers and state. It starts off; disabled update resets its timers and phase. Its intervals include quantization and scan latency.

`clock_ms(10|100|1000|60000)` reads global `%S4..%S7` bases instead. Their controller phase is global, not reset per instance. The local model starts their phase at zero for reproducible tests. Hardware measurements are still required, including bases the official simulator does not reproduce.

TON/TOF/TP expose `preset()` (%TM.P), `value()` (%TM.V), `done()` (%TM.Q), and `set_preset(i16)`. `Ton{42, 100, 3}` fixes native TM42, a 100 ms base, and a three-tick preset; the reverse path preserves these parameters. Writes to P use the native object, not a shadow MW. V and Q are read-only. With Dynamic Preset false, a new P is visible immediately but affects the next activation. Skipping the block lets its internal state progress without rewriting its linked output.

The five-argument constructor `{index, base, preset, retentive, dynamic_preset}` accepts literal flags. Locally, retentive TON/TOF pause/resume before completion; retentive TP is refused. Dynamic preset is modeled for TON/TOF/TP and applies on the next base update. Reducing P below V completes while retaining V; with both options, reducing P below V while paused resets V. These boundaries, native tick phase, fractional timing, RUN/STOP, and restart behavior remain provisional.

**SMBP with either timer option true remains blocked**, pending functional-level 3.3/12.0 mapping. The 10 ms timer base is also blocked because its XML enum has not been established from a verified original. Other emitted bases still require official acceptance.

See [timer properties](capabilities/TIMER-PROPERTIES.md), [timer modes](capabilities/TIMER-MODES.md), and the corresponding [properties](../examples/timer_properties.cpp) / [modes](../examples/timer_modes.cpp) examples.

## Bits and edges

`read_word_bit(word, bit)` / `write_word_bit(word, bit, bool)` access MW bits while preserving neighbors and MD/MF aliases. Packed `read_m/input/output_bits_i16/i32` and `write_m/output_bits_i16/i32` transfer byte-aligned groups of `1..32` bits within the carrier/bank, first bit in the LSB. Reads zero higher carrier bits; writes preserve neighbors. `copy_m_bits(dest, source, count)` snapshots before writing and permits overlap. Output reads observe earlier writes within the scan.

Native edge contacts LDR/LDF, ANDR/ANDF, ORR/ORF, and XORR/XORF work in IL and reverse conversion. `input_rising/falling(index)` and `m_rising/falling(index)` read events sampled at scan start. Repeated contacts do not consume the event; skipped contacts do not accumulate stale edges. An M write is observed at the next scan's edge sample; a pulse that rises and falls within a scan is not sampled. The `RisingEdge`/`FallingEdge` classes instead detect transitions at their call sites.

`rising(id, expression)` / `falling(id, expression)` detect an expression edge at execution. Each kind has distinct static IDs `0..254`; skipped calls retain history, and loops revisit the same point. Conditional/short-circuit evaluation follows C++ order. SMBP export expands these functions into private M bits and known Ladder gates, rather than unproved raw edge-block enums. The generated-project resource report includes that cost.

Startup/resume, input phase, and physical edge behavior need external confirmation. See [bit objects](capabilities/BIT-OBJECTS.md), [native edge contacts](capabilities/NATIVE-EDGE-CONTACTS.md), [expression edges](capabilities/EXPRESSION-EDGES.md), and their examples.

## Native counters

`Counter{id, preset}` represents a native %C block, not a counter synthesized in M/MW. Actions are `reset`, `set`, `count_up`, and `count_down`; getters expose `preset`, `value`, `done`, `empty`, and `full`. `set_preset(i16)` writes P. `update(r, s, cu, cd)` executes those four actions in that order and returns D. Instances can occur at multiple call sites and in loops.

Flags, input interaction, histories, and lifecycle remain a provisional local model, including a documented source conflict about E. Pure raw Counter branch/output graphs are imported only after proving port connectivity and exact boolean execution order, including shared prefixes/coils. Comparisons and numeric side effects inside those raw graphs remain gated. Export normalizes to separate rungs and reports the allocation extent.

See [counters](capabilities/COUNTERS.md), [counter graphs](capabilities/COUNTER-GRAPHS.md), and the [counter example](../examples/counter.cpp).

## Communications

Global `ReadVar`, `WriteVar`, and `WriteReadVar` instances model native communication blocks. Configuration is static and explicit. The implementation includes FC1/2/3/4/5/6/15/16/23, bit packing, MBAP validation, status/error codes, timeout, abort, and per-link exclusion.

Each used instance has one unconditional `update(execute, abort)` per scan. Getters before or after update retain that order. Execute requires a false-to-true transition; true in the first RUN scan is not an edge in the local model. Abort cannot undo a write already processed by a remote device.

Ethernet `Id` selects a configured remote-server index, not the TCP MBAP UnitId. Serial1 selects embedded RS485; exported serial profiles require explicit RTU/master configuration. Full local buffers are checked and reserved before temporary allocation. Reverse constructors preserve sparse native block indices.

No transport is selected automatically. `Machine(..., communication_transport=...)` accepts an explicit memory or loopback TCP transport. The TCP test transport accepts only `127.0.0.1` without DNS and opens a socket when a transaction starts. Without a transport, an attempted exchange reports channel-not-configured error 255/15. The native SDK defaults to that error path and offers an explicit test callback. There are no success stubs or implicit remote retries.

The local engine bounds queues/receive data and rejects mismatched responses. Arbitration, simultaneous Abort/Execute, and code-clearing details remain conservative local policies where physical behavior lacks evidence. Physical serial RTU/ASCII/CRC is not implemented by the host model; in an exported project it belongs to the official PLC runtime.

SMBP export covers proved READ_VAR/WRITE_VAR word profiles and known port enums only. WRITE_READ_VAR XML, bit/single-object enums, certain port parameters, dynamic communication properties, and graphical ABORT remain gaps. Local protocol support does not establish project-format support, serial electrical behavior, or physical Ethernet compatibility.

See [Modbus API and limits](MODBUS.md), [serialization research](capabilities/MODBUS-FORMAT-RESEARCH.md), and the [read example](../examples/modbus_read.cpp).

## Project format and export gates

SMBP serialization is based on inspected originals and primary documentation. A sufficient public vendor schema has not been established. Observed XML nodes/enums are evidence for the implemented subset, not a stable official format contract.

The reader requires recognized model/configuration and coherent IL/graphics. Unknown active tasks/objects, execution settings, ambiguous duplicates, and unrecognized constructs fail. Input produced by the official editor may still be outside this conservative subset. The tool does not relabel a foreign CPU to manufacture a target template. The included authentic CE40T memory baseline and its provenance record establish a concrete editor-created profile fixture; the synthetic fixture remains a parser-only input.

Supported native boolean forms include STN/N, MPS/MRD/MPP, parenthesized AND/OR groups, compound timer inputs, ST/STN/S/R timer outputs, and terminal `IN %TMn` or `IN` before another load. Saved intermediate values are snapshots. Complex logic lowers to known series contacts/coils/timer blocks; short-circuit numeric comparisons use jumps. MPS stack-depth source conflicts, further modifiers, raw graphical forms, and general parallel/Grafcet/task import remain open.

Important current export gates include:

| Feature available locally | Why project support remains gated |
|---|---|
| 10 ms timer base | Unproved XML enumeration |
| Retentive / dynamic-preset timer modes | Functional-level serialization and profile mapping unresolved |
| Indexed bits | FL10.0 mapping and CE40T profile evidence unresolved |
| Several Modbus variants | Unproved object/port enums or graphical ABORT / WRITE_READ form |
| Arbitrary native project graphs | Importer only handles explicitly reconciled subsets |

`write_project` rereads the generated candidate and validates it locally before replacing the destination. Source maps and hashes make outputs inspectable. They do not prove the editor will open, compile, or retain the same program.

Decompilation reads the real instructions/configuration, preserves explicit addresses and block identities, and writes an exact configuration sidecar for SMBP input. It is not a general decompiler for every file accepted by the vendor editor. Retained regions and external project startup semantics must be assessed against their real configuration; the local model does not simulate physical power loss/resume.

See [format evidence](FORMAT.md), [native logic](capabilities/NATIVE-LOGIC.md), and the [official acceptance plan](validation/WINDOWS.md).

## Evidence and remaining acceptance work

The capability catalogue contains 161 language/block records and 89 hardware/configuration records, with overlap, optional/absent features, and unresolved source conflicts. Its research stages begin conservatively as missing/pending. The CLI's separate `library` section describes local implementation; no percentage or record count is treated as complete feature coverage.

The dated [local validation history](validation/LOCAL-RESULTS.md) and result manifests bind claims to actual tested files. Public projects are fetched from pinned commits with size and hash checks. Selected instructions may be tested in explicit harnesses without claiming a foreign project imports in full or targets CE40T.

The remaining official evidence must identify target/firmware/functional level, open and compile exact output bytes, inspect Ladder/configuration, save/reopen, compare actual instructions, and exercise official simulation and physical hardware where needed. A Wine-hosted editor result must retain that environment qualification. Windows drivers, real PLC timing, retention, watchdog, RUN/STOP, physical serial/Ethernet, and electrical output behavior require their own evidence.

All validation runs locally. Do not create or enable GitHub Actions, remote CI, automatic PLC transfer, firmware changes, or load actuation as part of the toolchain's build process.
