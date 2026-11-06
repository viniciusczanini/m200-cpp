# Boolean logic, images and edges

Current scope is ordinary Boolean/I/O, edges, memory/constants and compact native
output. Local compilation, execution and project/reverse checks are recorded in
the [integration evidence](validation/NATAL-INTEGRATION-PROGRESS.md). Expanded
native layouts and restart history still need exact official observations.

`plc::BooleanContext{true,true}` selects native `RISINGn/FALLINGn` output while
keeping the existing isolated-MAST input-image contract. Default `{true,false}`
retains expansion. Native series output preserves per-instruction histories
without a persistent `%M` per history. Template limits: FL>=6;32 identities per
kind before10.1,255 from10.1. FallingEdgeBlock series layout remains an inference
from the observed rising shape plus the installed falling token; official batch
save/reopen/execution is pending.

`BooleanContext{false,false}` materializes input reads at evaluation points and
disables moving/coalescing/dead-store cleanup. It does not configure events,
preemption, immediate physical IO or a scheduler. Owning task integration must
choose the context explicitly and guarantee task-private memory ownership.

`plc::BooleanStack` is local to scan: `push(bool)`, `peek()`, `pop()`, depth<=32,
value snapshots and compile-time balancing across branch/loop/control contexts.
Only used slots go through liveness allocation. Actual MPS/MRD/MPP still use the
existing normalizer/reverse snapshots. G82's32 storage values and O49–51's>11
MPS reversibility error are not a claim that hardware executes32 nested pushes.

`read_bit("%M100")`, `write_bit("%MW100:X15",bool)`, `set_bit(address,enable)`
and `reset_bit(address,enable)` expose closed canonical operand identities.
S/R false preserves the target. MW bits alias numeric MW and stay on the existing
Machine/SDK word-bit path, preserving G02 indeterminate masks after integration.
Native block properties retain their existing typed APIs.

Constants are owned exclusively by G02: `ConstantWord/Dword/Real`,
`Program.constants`, `Machine.constants`, JSON/XML and SDK512 shared cells.
G01 `%KW:X` consumes that image via `Machine.constants` and G02's
`read_constant_word`, and preserves the same map during normalization. No
BooleanConstant or BooleanConfig.constant_words exists. Integrate G02's SDK
scalar_numeric.hpp before plc_boolean.hpp. Missing G02 fails explicitly.
SW17:X likewise consumes ArithmeticState.float_status / read_system_word(17)
and write_system_word(17); numeric flags and Boolean bits have one identity.

`Program.boolean` is optional `BooleanConfig`: input_image_stable,
native_expression_edges, word_objects. Old programs retain their previous
behavior. `BooleanWord{"%IW1.0"}` declares an image identity without hardware.
Active analog module SMBP binding remains gated. Other system/IO state/effects
require adapter callback `(action,address,value)` through
`Machine(...,boolean_runtime=callback)`; read_bit/write_bit/read_word/write_word,
reads bool/unsigned16. SDK hooks boolean_bit_hook/boolean_word_hook receive
(address,write,value), word address without :Xk. No adapter=>error/trap.
Grafcet X and unbound native block banks remain pending.

VM `begin_master_cycle(inputs)` samples native I/M history independently of body
execution. Subsequent `step(inputs,dt_ms=0,master_cycle=False)` uses that sample;
default step still samples once per scan. SDK: detail::begin_master_cycle().
Expression history updates per executed site, including false accumulators;
skipping preserves history. Initial false history is the prior local policy.
Warm/cold/STOP/RUN lifecycle and exact physical image phase remain unproved.

Reverse uses actual opcodes/addresses/configuration, never an embedded C++ copy.
Sources: local G=EIO0000003289.04 pp20,27,37–48,82–83;
P=EIO0000002019.06 pp22–26,321–340; O=EIO0000003281.04 pp49–51.
NATIVE-EDGES-RESEARCH.md fixes a public RisingEdgeBlock descriptor/index layout.
Static strings of the installed Entities.dll exposed exact RisingEdgeBlock and
FallingEdgeBlock tokens. No assemblies were loaded or executed. Existing gates,
validation evidence and documentary capability catalogues were not promoted.


## Integration candidate G01 with G02/G06/G07/G09/G11 (unexecuted)

Program retains constants, rtcs, schedules and boolean together. Scalar SW17
and RTC-owned SW18/19/49..60/114/118 word-bit access uses the same read/write
providers as numeric access, including read-only and RTC staging/range rules.
There is no external adapter requirement or duplicate image for those objects.
RTC system bits S50/S51/S52/S59 likewise use the existing RTC state. Other
unowned system/extra hardware operands retain explicit adapters.

Machine accepts both rtc and boolean_runtime. step retains timer_event and adds
the keyword-only master_cycle. Timer lifecycle/advance_time hooks are retained.
Only a master boundary calls RTC.begin_scan, before native I/M sampling;
non-master calls require dt_ms=0 and do not reapply schedule outputs or history.
The SDK scalar header remains before plc_boolean.hpp. Native expression-mode
inference includes Master and SR IL. No test/build/import/editor execution was
performed while resolving this candidate.
