# TM200CE40T native program structure

Research date: 2026-11-06. The next useful structural increment is **conditional leaf `SRn` calls with explicit Free POU identity and return context**. Periodic/event scheduling, UDF/UDFB instances and Grafcet require additional execution and serialization contracts. They remain part of [full parity](../PARITY.md), not features to infer from a shared editor enum.

This research used local primary manuals, static installed metadata and preserved authored projects. It operated no GUI, Wine, simulator, network or PLC and published no vendor method body or complete resource dump.

## Source identities and applicability

| Source | SHA256 and relevant scope |
|---|---|
| [M100/M200 Programming Guide EIO0000002019.06](https://www.se.com/ww/en/download/document/EIO0000002019/) | `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df`; pp.14, 21, 25–28, 52–53, 323–324. This supplies the M200 model link, task limits and embedded event sources. |
| [Generic Functions Library EIO0000003289.04](https://www.se.com/ww/en/download/document/EIO0000003289/) | `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595`; pp.60–61 and 65–66, END and SR semantics. |
| [Operating Guide EIO0000003281.04](https://www.se.com/ww/en/download/document/EIO0000003281/) | `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5`; pp.49–51, 54–70, 74–77, 86–92, 135–141. Its shared editor descriptions are used where the M200 guide explicitly refers to that guide/features; its M221 device list alone does not prove M200 eligibility. |
| Authentic CE40T baseline [fixture](../../tests/fixtures/official_tm200ce40t_memory.smbp) | `df5a293169d062d54b9d1f37909f15476cb7841d300c9b01a39c23ccd2924fbf`; exact saved/opened CE40T profile at `FunctLevelMan21_0`, with empty SR/UDF/UDFB/Grafcet collections. Capability fields are declarations, not execution proof. |
| Installed `SchneiderElectric.SoMachineBasic.Entities.dll` | `bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e`; entity, property, enum and default identities. |
| Installed `SchneiderElectric.SoMachineBasic.CommonCore.dll` | `9434b681932df39a57f9ee14d39e09b12bd5eb42c62d8aa814ef217821d0181a`; static minimum-level predicates. |
| Installed `SchneiderElectric.SoMachineBasic.PersistenceLayer.dll` | `c0a7c279d49584881fe4e7a0218220091633325f818c8366363b2ad2233270ea`; XML adapter member/field identities. |

All hashes above were freshly checked. Installed metadata belongs to Machine Expert Basic 1.4 build484. Human level mappings use the independently recorded enum/resource identities in [EDITOR-INTEROP-FACTS.json](EDITOR-INTEROP-FACTS.json), not the suffix of `FunctLevelMan…`.

## Calls and returns: native names matter

The documented Basic call instruction is **`SRn`**, executed only when the preceding Boolean result is true. Its target is a Free POU with subroutine number n. It returns to the caller; a Free POU is not automatically part of the master scan. Native SR calls cannot nest: an SR calling another SR is a documented compiler error. Calls inside Boolean parentheses, or between MPS and MPP, are invalid. A rung-terminal call is the first useful reversible subset. [Generic guide pp.65–66; Operating guide pp.49–51, 64–66.]

`END`, `ENDC` and `ENDCN` finish the **current execution level**. Within an SR/UDF/UDFB they return to its caller; within a task they finish that task. `ENDT` belongs to a Grafcet SFC transition. A subroutine can change the Boolean accumulator, so restoring the caller's old accumulator unconditionally would be wrong for general IL. Event context save/restore is a different contract from an ordinary SR call.

No standalone `CAL` or `RET` control opcode was established in these Basic sources or the 25 downloaded SMBP files inspected. `%RET0` is a UDF return-value object, with Word/Double/Float typing, not a return instruction. Installed `ProgramElementTypes.Return=12` is an editor identifier; it does not establish a `RET` opcode or SR Ladder geometry. Do not import similarly named instructions from another IEC toolchain.

The baseline declares `SubroutinesMax=64` and `LabelsMax=64`; the shared validation tables use subroutine numbers 0..63. `%SBR` is a shift-bit-register object, not the Free POU count. Section number, SR number and POU name must remain distinct identities.

## Tasks, preemption and events

The M200 guide explicitly documents the following, including the task table on p.28 checked against the rendered PDF:

| Task | Capacity and trigger | Ordering |
|---|---|---|
| Master | One; normal continuous scanning or periodic 1..150 ms | Lowest priority |
| Additional periodic | One; software period 1..255 ms; executes an assigned Free POU | Above master, below events |
| Embedded-input event | Four sources, I0.2..I0.5; rising/falling/both edges | Event priority |
| HSC threshold event | Four sources: two thresholds each for HSC0/HSC1 | Event priority |

Periodic-task configuration does not require converting the master to periodic mode. The master can remain normal while the additional periodic task executes. These are separate settings. The shared Operating Guide p.57 sets a 1 ms minimum only from human level 5.0; below that it gives 2 ms. The M200 guide refers to the Operating Guide for task configuration. This level boundary still needs an exact CE40T saved configuration before a new scheduling/export contract is claimed.

Input event use requires disabling filtering; latch and Run/Stop assignments also constrain eligibility. M200 pp.52–53 explicitly require distinct priorities 0..7, where the Operating Guide identifies 0 as highest. Events interrupt master and periodic execution. The shared event sequence saves context, runs the attached SR, updates embedded outputs, then restores context; only embedded controller I/O is permitted in an event SR. [Operating guide pp.88–90.]

The sources do not establish every interrupt boundary, higher-event interruption of an already running event, queue depth, repeated-source coalescing or overrun policy. Do not replace these with an unbounded host queue or execute every event only between complete master scans. M200 pp.323–324 describe S38 as queue-admission permission and S39 as lost-event indication. Operating Guide p.92 describes event processing and SW48's executed-event count; it distinguishes cold restart/application-load reset from warm restart retention. Queue admission and draining need separate proof rather than treating those descriptions as interchangeable.

The M200 guide also distinguishes application watchdogs from a system processing-capacity watchdog. The local VM instruction limit is not evidence for either controller watchdog or physical preemption latency.

## UDF/UDFB and Grafcet eligibility

The M200 guide lists UDF return/parameter/local objects and points explicitly to the Operating Guide for these features. Its p.25 gives up to 32 UDFB Boolean input/output pins from level 10.0, otherwise 8, and p.26 gives 48 combined PARAM/VAR objects. The exact CE40T baseline declares `UdfMax=64`, `UdfbInstanceMax=32`, `UdfObjectsMax=4096` and `GrafcetBitsMax=200`. The 4096 field's allocation unit/domain was not established here; its name alone must not become an allocator rule. The instance ceiling must not be reinterpreted as a proven UDFB-definition count.

| Feature | Documented/static editor gate | Remaining qualification |
|---|---|---|
| Grafcet SFC POUs | Human 4.0 / `FunctLevelMan7_0`; `SupportsGrafcetPous`, token `0x06000179`, minimum enum 16 | Does not imply SFC support at older levels or prove List/SFC serialization equivalence |
| UDF and UDFB | Human 6.0 / Man11; `SupportsUdfPous` / `SupportsUdfbPous`, tokens `0x06000192` / `193`, minimum enum 20 | Matches Operating Guide pp.67/74; actual CE40T definition/use bindings still missing |
| UDF object naming/parameter indexing; 32 pins; more than 96 Grafcet steps | Human 10.0 / Man14; predicates `0x0600019f`..`0x060001a2`, minimum enum 23 | Matches the level feature list; current baseline declares 200 step bits |
| Local function-block instances in UDFB | Human 11.0 in Operating Guide p.55 | Their global-instance allocation and complete XML mapping need capture |
| UDF/UDFB protection; UDFB pin-parameter configuration | Human 14.0 / Man21; predicates `0x060001b3`..`0x060001b5`, minimum enum 30 | Does not establish encrypted-definition import/export or password handling |

The minimum comparisons above were checked statically. They are editor predicates, not independent firmware/runtime tests. Unknown levels must continue to fail explicitly.

UDFs can be called from master, periodic, event and Free POUs. A UDF may call another UDF without direct/indirect recursion; it cannot call an SR, while an SR may call a UDF. Its RET/PARAM/VAR objects are scoped to that definition. UDFB interface variables and per-instance state must be distinguished from ordinary global MW/timer/edge objects, which the guide says remain shared. Local FB instances consume actual global indices after existing instances; they are not cost-free copies. Operating Guide p.76 also restricts UDFB programming in the IL editor despite nearby Ladder/IL-rung wording: obtain authentic definition/use forms before promising a universal IL-only UDFB export.

Grafcet List uses preprocessing, sequential steps and postprocessing, with separate initial/regular step and activation/deactivation operations. The p.136 instruction table was visually checked: `=*=`, `=*= POST`, `-*-`, `#`, `#x`, `#D x`, `Sx`, `Rx`. It is not just ordinary coils renamed as state variables. SFC POUs are master-task-only. SFC processing stages activation/deactivation for the next task cycle, visits active steps in ascending number, permits multiple active steps, and gives activation precedence over simultaneous deactivation. [Operating Guide pp.135–141.] Do not silently replace either form with a single-state enum or assume their transition timing is identical.

## XML evidence and precise missing forms

The local sample search found nonempty SR/periodic structures only in original **M221** projects:

| Original authored source | Observed structure, without model substitution |
|---|---|
| [didim99/TSTU](https://github.com/didim99/TSTU/blob/ea8c59ca97fc99d07cc979a2fcb78113c322cf2c/labwork/mps/Lab-07-M221-autoOperator.smbp), SHA256 `a4307729f0864133e414517ef49c37e6648f29d7403a8f9737e2f7367461a738` | TM221ME16R/G. `Subroutines/Subroutine` has Name, SectionNumber 4, Rungs, Number 0; main IL calls SR0. Call and callee rungs are IL-only, so no SR graph coordinates are established. |
| [brymon68/cs_8803_7](https://github.com/brymon68/cs_8803_7/blob/2cacf9fd8b059a0d87a0fe6105fbf9fa586b5c4f/Project%201/Project1_Part1B.smbp), SHA256 `836a371e610d37747fe23dbc8a35414f9273ef92dca6c4e7f70e94a2219c86c3` | TM221M16R/G. Subroutine has Number 0, SectionNumber 2, empty LinkedEvent and IsFastTask=true. `FastTask` contains Period 255 and `FastTaskSubroutine=Free POU_0`, a name rather than an SR number. |

No authored UDF/UDFB/Grafcet structure was found in those 25 files, and no nonempty authentic CE40T SR/task structure was established. The CE40R Modbus project is not evidence for CE40T calls or scheduling.

Installed static names narrow future capture work:

- Entities contains `MastTaskConfiguration`, `FastTaskConfiguration`, `Subroutine`, `UserFunctionPou`, `UserFunctionBlockPou`, `GrafcetPou`, step and transition entities. Inheritance/property names do not supply complete XML schemas.
- Persistence adapters name MastTask fields `UsePeriodScanMode` / `PeriodScan`, FastTask fields `Period` / `FastTaskSubroutine`, and SR linkage fields `LinkedEvent`, `IsFastTask`, `IsMastTask`. These are candidates to compare against real CE40T saves.
- Discrete-input adapters name `Deactivation`, `Priority`, `SubroutineNumber`, `DIFiltering`, `DILatch`; HSC threshold adapters name `ThresholdType`, `Priority`, `SubroutineNumber`. Shared `TriggerEventTypeEnum` has `NotUsed=0`, `FallingEdge=1`, `RisingEdge=2`, `BothEdges=3`. No active CE40T event XML was captured.
- UDF/UDFB adapters expose definition/object/pin collections, optional protection and local-FB fields; complete default omission, typed objects, instance identity and expression forms remain unproved. Grafcet adapters name Elements, StepNumber and transition Id/Row/Column/From/To plus nested POUs; this does not establish graph geometry or transition wiring.

## Current implementation and next closed increment

[Program](../../m200/model.py) has one flat rung stream, no native SR/task/UDF/Grafcet contexts. [Configuration](../../m200/config.py) rejects active SR/UDF/Grafcet collections and periodic FastTask assignment. The MastTask validation gap reproduced during this research is addressed by the separate false/100 profile guard and [its tests](../../tests/test_mast_task_profile.py); that guard rejects unimplemented periodic execution and other unverified profiles. It adds no scheduler. The authentic inactive profile parks 100 ms, while the M200 manual gives 10 ms as its default and the Operating Guide/installed constructor give 100 ms; do not silently rewrite that stored field to resolve the discrepancy.

The smallest execution increment should support one or more **leaf Free POUs numbered 0..63, called by rung-terminal conditional SRn in a normal master task**, initially with the already supported memory/Boolean/numeric operations. Preserve SectionNumber, SR number and name independently. Give callee END variants a return target distinct from the master output-commit epilogue. Include call effects in temporary lifetimes and shared-memory analysis; callee return must not commit staged outputs or reinitialize persistent state as though starting a new scan.

Before enabling that form, collect an exact CE40T editor-created SR0/main-call pair, save/reopen and its actual Ladder conversion; then repeat with SR63 and conditional callee END. Local tests should cover false/true calls, caller continuation, writes before/after return, accumulator behavior for any accepted IL continuation, skipped timer/edge execution, duplicate/missing targets, SR64, nested calls and ambiguous section/name mapping. Preserve source/destination bytes on rejection. Reject unsupported call contexts rather than flattening them silently.

Subsequent capture stages should isolate: one additional periodic SR versus periodic master configuration; one input event and one HSC event with priorities/context/output behavior; one Word UDF and two UDFB instances distinguishing local from global state; then separate two-step List and SFC programs with reset/freeze and competing transitions. Save/open evidence establishes bindings only. Scheduling, preemption, restart semantics and physical timing each require their own authorized runtime stage.
