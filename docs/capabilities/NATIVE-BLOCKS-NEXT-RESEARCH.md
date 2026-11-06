# Next native block increment for TM200CE40T

**Recommend native `%R` FIFO/LIFO next**, followed by `%SBR`. Registers have a
small fixed domain and an explicit documented rule for simultaneous store/retrieve
edges. This is a read-only research result, not an implementation or editor/runtime
acceptance claim. The current compiler still rejects all families below.

## Primary evidence and target eligibility

The cached Schneider [M100/M200 Programming Guide](https://www.se.com/ww/en/download/document/EIO0000002019/)
EIO0000002019.06 explicitly lists these families on p21 and their maxima on p25.
Thus eligibility comes from the M200 guide, not from an M221 example. The authentic
CE40T baseline's CPU TechnicalConfiguration independently contains the same R,
DR, SBR, SC, SCH and PID maxima. That serialized capacity metadata is not an
execution test.

| Family / native index | CE40T maximum | Domain, state and controls | Configuration and remaining evidence |
|---|---:|---|---|
| `%R0..3` | 4 | FIFO or LIFO; fixed capacity 16 words of 16 bits. RW input/output words `.I/.O`; BOOL `.E` empty and `.F` full. `R` resets; `I/O` request storage/retrieval on rising edges. | Explicit mode, identity and allocation; Generic pp141–146. Full push and empty pop do nothing; empty pop preserves `.O`. Both new I/O edges in one call do neither. Exact active XML/graph and reset/edge collisions still need captures. |
| `%SBR0..7` | 8 | Sixteen bits `.0..15`, readable/writable. `CU` shifts left, `CD` right on rising edges, losing the end bit; `R` clears. | No configurable length or mode documented; Generic pp152–155. Missing simultaneous CU/CD and reset-collision rules prevent an invented host ordering. |
| `%SC0..7` | 8 | One active step among 256 addressable BOOLs `.0..255`, readable/writable. `CU/CD` edges move one step; `R` selects step 0. | Identity/symbols; Generic pp155–158. Endpoint behavior, simultaneous directions and writes that try to set multiple steps need native evidence. No public numeric current-step operand is established by this section. |
| `%DR0..7` | 8 | 1–8 steps, 16 configured cams mapped to `%M` or `%Q` bits. `.S` is a RW step word 0–7 with decimal-immediate writes applied on the next call; `.F` indicates the configured last step. `R/U` reset/advance. | Step count, cam matrix and output bindings; Generic pp146–152. Last-step advance wraps to 0. Cams update on a step change or warm/cold restart, not on every scan; skipped calls retain outputs. Exact graph/config is missing. |
| `%RTC0..1` | 2 | Enable/RD/WR, date/time fields; Done/Error BOOLs, DayOfWeek0–7 and ErrorId. | Generic pp163–166 says FL ≥ 5.0; M200 eligibility is independently on p21/p25. Simultaneous RD/WR gives 256; S50 update conflict 257. Date/time operand serialization/width and the native graph are unbound. Hardware clock validity/battery are separate requirements. |
| `%SCH0..15` | 16 | Calendar/time periods drive configured `%M`/`%Q`; SW114 enables each instance. Multiple schedules assigned to one output are ORed. | Configuration objects, not rung-inserted FBs. Generic pp158–162; dynamic `.STARTDAY`/month/hour/minute, end fields and `.DOW` require FL ≥ 6.0 and apply next MAST scan. Configured date/time/weekday fields and valid RTC required; exact property encoding is unbound. |
| `PID 0..13` | 14 | PID, AT+PID, AT or word-selected mode; mode word 0 disables, 1 PID, 2 AT+PID, 3 AT, 4 PI. Readonly state word includes inactive 0x0000, regulating 0x2000, setpoint reached 0x4000 and documented error codes. | M200 pp294–321 covers configuration, algorithms and states. `[PID n]` enables a loop, not a BLK-style FB. Periodic MAST scan is required (p315); all parameter/scaling/sample-period bindings and numerical behavior remain unimplemented. |

No minimum feature level is inferred for R/DR/SBR/SC from the absence of a note.
The table separates documented behavior from open cases; it does not authorize
all values in the installed UI merely because an entity class exists.

## Existing authored project and installed metadata

The installed official example
`Examples/Material Handling_Zero Pressure Accumulation_Hardwired_M200.smbe`
is plain XML, targets **TM200CE24R**, and has SHA256
`e77749df0080c3b7122f9ca7a8b278c09ce404f38293d8e2237c08949533ea9d`
(3905323 bytes). It contains default configuration rows for all four registers,
eight drums, eight SBRs, eight SCs, 16 schedules and 14 PIDs. It has **no active
references to these families in its executable Ladder**, and no ManagementLevel
field. It establishes old M200 default persistence only. Do not retarget it or
treat it as a CE40T active-graph/runtime fixture.

Observed first-entry structure:

| Collection | Entry | Fields actually present |
|---|---|---|
| Registers | Register | Address `%R0`, Index 0; Type omitted |
| Drums | Drum | Address/Index; Bits with 16 BitForDrum entries, each with eight empty Step children |
| ShiftBitRegisters | ShiftBitRegister | Address/Index, `LastWritenBit=0`,16 BitSymbols entries |
| StepCounters | StepCounter | Address/Index,256 StepSymbols entries |
| ScheduleBlocks | ScheduleBlock | Address/Index, StartDate/EndDate `2012-01-01T00:00:00` |
| Pids | Pid | Address/Index, CorrectorDynamic `CorrectorDynamicFast` |

The matching allocation elements are empty. These are observed defaults, not an
allowlist for active configuration; child repetition, nil symbols, field omissions
and defaults need explicit handling when each family is implemented.

Read-only ECMA metadata inspection of installed
`SchneiderElectric.SoMachineBasic.Entities.dll` (1104024 bytes, SHA256
`bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e`)
found types under
`SchneiderElectric.Automation.SoMachineBasic.Entities.PLCObjects.FunctionBlocks`:
Register TypeDef 492, ShiftBitRegister 494 and StepCounter 495. RegisterTypeEnum
TypeDef 550 defines `Lifo=0`, `Fifo=1`. Register Input/Output properties are
`Nullable<Int16>`, Empty/Full `Nullable<Boolean>`; SBR Value is
`Nullable<UInt16>`. These match the intended 16-bit domains. SC CurrentStep uses
`Nullable<Int32>` internally, which does not establish a PLC numeric operand.

**An enum's zero value does not prove the default of an omitted XML Type.**
A subsequent static check separately established the installed Register default
as **Fifo**: its constructor sets Type to 1, its default-configuration predicate
compares with 1, and the Type property has DefaultValueAttribute for enum value 1.
That explains the authored default omission without inferring Lifo from zero.
Explicit FIFO/LIFO active saves still need editor evidence. No installed method
body or assembly is published or executed by this research.

## Current compiler gaps and smallest closed path

`Program` has timer/counter/communication maps but no register-family state or
configuration schema. `config.EMPTY` still rejects nonempty Registers, Drums,
ShiftBitRegisters, StepCounters, ScheduleBlocks and Pids. The operand parsers do
not bind `%R` words/status bits or `%SBR/%SC` bits, and native BLK parsing,
VM/SDK state, reverse C++, allocation and graph consistency are absent. Existing
ordinary shifts/arrays can express application logic but do not expose these
native resources or their persisted instance identities.

The next increment should stay on R only:

1. Obtain two authentic CE40T/Man21 saves: explicit FIFO and explicit LIFO, with
   I/O data-word operations, all R/I/O input ports and E/F output bindings. Freshly
   reopen both. Record actual mode spelling/default omissions, allocation fields,
   ports, geometry and IL/graph agreement before adding XML support.
2. Settle reset with store/retrieve edges, whether ignored simultaneous requests
   consume edges, held inputs, skipped/repeated calls, `.O` writes/reset behavior,
   and cold/warm/STOP separately. The guide specifies queue-content retention on
   warm/STOP and initialization on cold/INIT; it does not settle every interaction.
3. Implement one closed Register collection: IDs0–3, explicit FIFO/LIFO, fixed 16
   signed 16-bit words, RW `.I/.O`, readonly `.E/.F`, block R/I/O, typed C++ accessors
   and independent VM/SDK/reverse behavior. Proposed API names `Fifo/Lifo`,
   `set_input/input`, `set_output/output`, `update(reset,store,retrieve)` and
   `empty/full` are provisional. Keep trigger names distinct from data words.
4. Use literal mode-order oracles, sixteen-item capacity plus ignored seventeenth
   push, empty pop retaining `.O`, held/released controls, simultaneous new edges,
   all 16-bit patterns, sparse R3 and invalid R4/duplicate identities. Compare native
   C++, VM, actual XML import and reverse/recompile. Reject unknown fields/ports,
   unsupported raw actions and invalid destinations without replacing user files.
5. Root then validates the exact normal CLI output in the official editor and
   simulator. No graph geometry, omitted default, collision ordering or lifecycle
   policy should be inferred from a successful local round trip.

SBR follows once bidirectional/reset interaction is observed; SC adds step-end
and writable-one-hot questions; DR adds persistent cam-output ownership. RTC/SCH
need a clock/calendar model. PID follows parameter/task binding and independent
numerical/sample-time evidence. These are tool gaps, not PLC impossibilities.

## Source identities and limits

Manual PDF hashes: EIO0000002019.06
`fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`;
[Generic Functions](https://www.se.com/ww/en/download/document/EIO0000003289/)
EIO0000003289.04
`d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`;
[Operating Guide](https://www.se.com/ww/en/download/document/EIO0000003281/)
EIO0000003281.04
`2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5`.
All were read from the existing local cache; no download was performed here.

The cached M200 guide contains a full PID chapter; this supersedes the older
audit's narrower observation that Generic Functions only delegates to the M221
Advanced guide. The reused embedded-analog wording on M200 p295 does not add
an analog input to CE40T: p24 explicitly says M100/M200 have none embedded.

Reproducible compact facts and the proposed capture plan are in ignored
`output/diagnostics/native-blocks-research-2026-11-06/` (`facts.json` SHA256
`90095f157fe6bc52fd1c96c82c85030ca5e5aa4b887e954e3c07347da05d49fa`);
`register-default-proof.json` SHA256
`6b06a05f24250e6e15a75387f89f6813095b203e98d04e91e30b79a8d2145e31`
records the later default check without method-body contents.
No core, test, fixture or SDK was edited; no GUI, Wine, network, CI or physical
operation was performed. This document promotes no block capability.
