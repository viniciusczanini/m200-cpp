# Teste 2 — semantic oracles and bounded stress

Prepared on 2026-11-06; **nothing in this suite has been executed**. No test,
build, compiler, project generator, GUI, Wine, CI, commit or push was run while
preparing it. The historical 799 regressions are separate evidence and were not
changed or rerun. Implementation remains with the owning lanes/coordinator.

## Current scope

The user's release priority supersedes the initial G01..G10 assignment. Active:
G01 Boolean/I/O/edges, G02 integer/flag semantics, G06 useful SR composition,
G07 timers, G08 counters/Register/SBR/SC/DR, G09 RTC/calendar/schedules and G11
local Modbus. Previously prepared G03/G04/G05/G10 cases and two new floating
G02 cases remain **DEFERRED_VERSION**. They are inventoried but not collected,
skipped, counted as PASS or credited as current feature coverage.

Static preparation inventory: 54 scenarios, including 36 priority scenarios and
18 deferred ones. The priority inventory comprises 25 C++ source scenarios and
11 host/provider/oracle scenarios. Both SDK and VM are selected by default;
unbound engines/oracles stay explicit failures. These are preparation counts,
not executed test totals, passing assertions or complete matrix coverage.

## Files and execution boundary

New code lives only in `tests/parallel_semantics/`:

- `source_cases.py`, `contract_cases.py`, `priority_cases.py`: literal snapshots,
  source programs, host requests and pending-oracle scenarios.
- `contracts.py`: test-owned Case/adapter protocol. An adapter receives only
  request data, never expected output, oracle code or the whole Case object.
- `adapters.py`: independent execution paths for source→compiler/VM and
  source→PLC_NATIVE SDK. Each result is checked against the literal/reference
  expectation, never merely against the other implementation's result.
- `host_adapters.py`: explicit timer-only VM/SDK event hooks and raw-byte
  scripted transport into the real Python CommunicationEngine. No real network,
  serial or hardware is opened, and no SDK async state machine is fabricated.
- `adapters.json`: exact bound and pending providers, engines and delivery paths.
- `scope.json`, `catalog.py`: priority/deferred disposition and finite inventory.
- `test_semantics.py`, `run.py`: unittest collection and optional narrow runner.

Do not run any command below before root explicitly releases an integrated
source/API freeze. After that release, commands are local only:

```sh
python3 tests/parallel_semantics/run.py --inventory
python3 tests/parallel_semantics/run.py --groups G02 --engines vm,sdk
python3 tests/parallel_semantics/run.py --groups G01,G06,G07,G08,G09,G11 --engines vm,sdk
```

`--case NAME` can select an exact scenario during a concrete repair; `--repo`
selects the coordinator's integrated checkout. No lane copy is implicitly
treated as merged support. Normal unittest discovery also collects the active
suite through `load_tests`. Empty selections fail. Pending APIs/oracles raise
`PendingAdapterError`/`PendingOracleError`, never `skipTest` or a successful stub.
The complete active suite cannot be called green while those gates remain.

## Independent expectations

- G01: duplicate native edge reads share one scan event; expression edges
  consume per call; skipped expressions keep history; short-circuit arithmetic
  preserves flags; stack snapshots survive source writes; SW114 bit/word aliases
  share one image and S/R with false enable has no effect.
- G02: literal overflow/carry snapshots and explicit recovery order; signed
  division/remainder; MW/MD low/high alias snapshots; direct/typed INC/DEC at
  i16/i32 boundaries. A separate 256-frame reference uses integer mathematics
  and raw bit extraction, seeded `0x20061106`, with eight fixed boundary pairs.
  It imports no production ALU or SDK helper to calculate expectations.
- G06: two stateful leaves share Counter instances and exact call order;
  repeated calls advance only on the supplied pin transitions; early local
  return from a loop still resumes the caller's suffix.
- G07: simultaneous independent TONs, TP/TOF composition, retained versus
  dynamic preset, void execute with skipped call, explicit power outage/warm
  resume and cold configured-preset restore. STOP is a separate positive case:
  Generic pp109/113/117 says STOP does not freeze timer progress. Timer-only host
  hooks do not prove whole-controller RAM/edge/fallback lifecycle.
- G08: FIFO/LIFO order with aliased MW source overwritten before update;
  counter circular boundaries and repeated pulses; SBR safe shifts where vacant
  endpoints already equal zero; SC middle steps and exclusive reset; DR cam
  ownership, skipped calls, step writes and wrap. Counter/queue local policies
  are labelled and are not promoted to universal native semantics.
- G09: RTC simultaneous RD/WR error256; literal Gregorian leap/century/year
  rollovers and staged invalid-date atomicity; SW18/19 absolute 100ms counter
  rolls its low word at32768, not65536. Schedules remain explicitly represented
  by a pending DOW/OR/enable-mask scenario instead of disappearing from scope.
- G11: first TRUE is not an Execute edge; absent transport gives255/15 and no
  successful buffer write; explicit literal PDU/response checks cover Busy
  configuration snapshot and Abort versus a late response. The scripted
  transport only supplies bytes. Production owns status, decoding, request
  configuration and buffer mutation.

Snapshots observe raw u16 MW cells, explicit Q bits and selected flags at actual
source positions. Timestamp/dt is applied after each scan. Float/ASCII future
cases retain their own literal identities but are deferred; they are not part
of the priority success gate. The published ASCII vectors were preserved without
resolving the manual's byte-order prose conflict by assumption.

## Explicit pending bindings and semantic gaps

1. G01 external word-image callback binding and native cold/warm/STOP edge policy.
2. G08 documentary ambiguities: SBR endpoint fill/direction collisions, SC
   endpoints/one-hot writes, DR pending-write/request collisions. Runtime refusal
   is a guard result, not implemented semantic coverage. Independent observations
   or an explicitly reviewed local contract must supply the missing oracle.
3. G09 exact injectable RtcClock/SDK host names and native DOW encoding. The
   calendar/staging cases already contain literal outcomes; no host wall clock
   or fabricated battery-backed success is substituted.
4. G11 SDK async arbitration/state is owned by the existing callback. Returning
   scripted status from that callback would test the stub, so async SDK parity
   remains unbound instead. Python raw-byte engine cases are concretely bound.

Root must review final `lanes/G*/DELIVERY.md` before replacing any pending entry.
The G01/G02/G06/G07/G11 deliveries were read for current names and narrowed scope;
G08/G09 still use their CONTRACT.md handoffs where final delivery is absent.
Compiler/SDK/VM errors after freeze are failures to investigate; an adapter
signature mismatch is reported as a binding problem, never repaired by weakening
the literal expectation to whatever production returned.

## Primary/reference authority

Pinned local manuals: Generic EIO0000003289.04, M100/M200 EIO0000002019.06 and
Operating EIO0000003281.04 under `research/downloads/manuals/`. Existing source
hashes are retained in the capability research records. Relevant pages include
Generic27-30,49-60,82-83,107-123,141-158,163-165,171-187,204-205 and the M200
system-word SW18/SW19 table. Existing explicit local policies are documented in
COUNTERS.md, TIMER-MODES.md and REGISTER implementation/observation records.

SBR research for implementers remains at
`output/research/native-sbr-next-2026-11-06/README.md`, including unaccepted
IL-only candidates and first-event capture probes. This test preparation did
not modify that research, installed tools or any production source.

No source case, local oracle, SDK/VM agreement or synthetic round trip establishes
new official editor/simulator/physical compatibility. GUI acceptance remains
with root after implementation and integration, as the user requested.
