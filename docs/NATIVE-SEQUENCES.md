# Native SBR, SC and Drum resources

This provisional pipeline has local compilation, execution and project/reverse
evidence in the [integration record](validation/NATAL-INTEGRATION-PROGRESS.md).
Unknown endpoint/collision/lifecycle domains remain explicitly gated; exact
native acceptance belongs to the final official batch. [The goal](GOAL.md)
defines the current priority release; [parity](PARITY.md) is the future contract.

Declare native resources globally with explicit literal identities0..7:

```cpp
plc::ShiftBitRegister shift{0};
plc::StepCounter step{1};
plc::Drum drum{2, 3,
    plc::DrumCam{0,plc::DrumOutput::Memory,10,2},
    plc::DrumCam{1,plc::DrumOutput::Output,2,4}};
```

SBR and SC expose `bit(literal)` and `set_bit(literal,bool)`. SBR bit indices are
0..15; SC step bits are0..255. `update(reset,up,down)` emits native R/CU/CD groups.
Each family has its own eight-instance pool. Objects cannot be copied. There is
no invented numeric whole-SBR value or numeric SC current-step PLC operand.

`Drum` takes its identity, step count1..8 and zero to sixteen `DrumCam` values.
Each cam gives a unique slot0..15, a Memory/Output bank, an M index0..1023 or Q0
index0..15, and an eight-bit step mask0..255. Mask bit0 controls step0. Unselected
slots have no associated output. Dormant mask bits beyond configured steps are
retained as configuration, not emitted as scan instructions. `update(reset,up)`
emits R/U; `step()` reads the i16 `.S` operand; `full()` reads `.F`.
`set_step(literal0..7)` emits the documented decimal-immediate assignment. It
schedules the local step change for the next block execution. Numeric expressions,
word writes, INC and arithmetic assignments to `.S` are refused.

`update_pins(mask,...)` preserves native partial blocks in the reverse path.
SBR/SC mask bits0/1/2 select R/CU/CD; Drum bits0/1 select R/U. The BOOL argument
count remains three/two and mask is a literal nonzero subset. Absent pins are
omitted in emitted IL, never silently converted into false inputs. All source
arguments are evaluated in order and mutable predicates are captured before the
block. Conditional calls skip the actual native block; repeated calls retain
one shared native resource identity. Native operations are not unrolled into
ordinary M/MW state machines.

`Program` adds `shift_bit_registers`, `step_counters` and `drums` mappings. JSON
keys are canonical decimal strings. SBR config has `bit_symbols` (16 nullable
strings), `last_writen_bit` (only observed0 accepted); SC has `step_symbols`
(256 nullable strings); Drum has `steps` and `cams`, where each cam stores
`slot`, native `output` address and `mask`. Only configuration is serialized;
request history and current values belong to runtime state. Defaults may be
omitted from JSON fields but referenced native resources must have explicit
configuration in project XML until omitted-default evidence is available.

The native persistence codec owns Drums/ShiftBitRegisters/StepCounters only,
rejects duplicate identities/fields, unknown fields/attributes and malformed
symbol arrays, and retains dormant cam masks. Native names (`StepsNumber`,
`BitForDrum`, `Steps`, `Step`, `Used`, `Available`, `Outputs`, `LastWritenBit`)
come from authored default XML and installed static metadata. Generic allocation
counts are checked against maxID+1 and capacity8. Automatic allocation is emitted;
no unestablished Allocation enum is added. Cam M addresses participate in memory
extent accounting and are reserved before temporary allocation. Compiler RUN
initialization does not automatically erase configured cam Q outputs.

Graphs use metadata-defined enum names and dimensions: ShiftBitRegister and
StepCounter2x3, Drum2x2. Input rows follow the documented native pin order. A
canonical block has normal direct I0/M contacts at column0 and its body at
column1; present pins occupy their own native rows. Drum F can wire one plain
ST/S/R coil at column10, with ordinary wire cells after the two-column body.
Complex predicates/output expressions normalize through shared temporary bits.
The graph checker compares full port/descriptor/coordinate tuples with actual
stored IL. Names and dimensions are statically sourced; acceptance of these new
active layouts remains pending. Unknown branched raw graph forms are refused.

Integration note: the candidate composes with the existing shared-resource SR
contexts (including their labels, loops, timers and communication admission).
The initial lane's narrow leaf-only restrictions below describe its baseline;
they are not reintroduced as blanket gates by this integration. Existing
per-feature native/profile and lifecycle gates remain in force.

The existing Register storage algorithm is unchanged. Full R/I/O blocks can now
have an OUT_BLK E/F output section. The canonical output profile admits ordered
E/F tests and ST/S/R coils; labels are checked against real IL. The observed bare
four-entity graph remains unchanged. Its wired output extension needs a native
save/reopen observation. Counter/Register/sequence configuration can be shared
with the existing bounded leaf-SR contexts; timer/communication closure and the
existing SR topology gates are unchanged.

The reverse converter reads real native instructions and typed configuration.
It reconstructs explicit native identities, cam configuration and pin-presence
masks. It does not depend on embedded source text. UI bit-symbol arrays are kept
in Program/XML, but the reverse C++ API currently reconstructs behavior without
those labels. Nonzero SBR LastWritenBit, unknown inherited configuration fields,
raw standalone SBR/SC/DR action instructions, partial Register input sets and
multiple native blocks in one rung remain compiler gaps.

The Python VM and PLC_NATIVE SDK intentionally stop on unresolved native paths:

- Simultaneous SBR/SC fresh direction edges; reset plus an active direction;
  reset with an active request history; omission of a previously active pin.
- SBR left shift when bit0 is set, or right shift when bit15 is set: the cached
  figure does not settle whether the vacated endpoint is cleared or retained.
  The native instruction is still emitted for such programs.
- SC step0 decrement, step255 increment, or assignment that changes the active
  step (including clearing it). Idempotent BOOL writes remain evaluable.
- Drum pending step outside the configured count, pending-write plus reset/new
  advance, reset plus advance, reset on a single-step Drum, omitted active pins,
  and aliased cam-output ownership.

Runtime construction models cold initialization, including Drum cams before
any call. Direction histories start false as an explicit local policy. Held
requests do not repeat; skipped calls retain history; known interior movements
use constant-size native state. First-call true, repeated/skipped-call history,
plain RUN entry, INIT, warm restart, STOP, pending-step read visibility and reset
collisions need independent native observations. No S17 effects are inferred
from integer SHL/SHR. These runtime restrictions are simulator/tool gaps, not
claims that the native PLC algorithms are invalid.

Primary sources: Generic Functions EIO0000003289.04 pp103–104,141–158;
M100/M200 Programming Guide EIO0000002019.06 pp21,25. Installed authored M200
example and Entities.dll metadata facts/hashes are recorded in the lane's
`SOURCES.json`. `examples/native_sequences.cpp` is an API illustration, not a
validated fixture or any application-specific effect.
