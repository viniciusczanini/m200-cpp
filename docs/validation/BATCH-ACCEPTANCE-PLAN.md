# Integrated batch acceptance plan

**Status:** prepared, not executed. No new test, Clang build, project generation,
Wine, Schneider editor, simulator, publication or Git action has run for this
preparation. The existing frozen **799-test PASS** remains historical regression
evidence; this work does not rerun or replace it.

**Goal:** produce one finite, inspectable acceptance batch for the priority version,
using genuine C++ algorithms, compatible resource profiles and independent
literal observations. Keep all **250 catalogue IDs** visible.

**Architecture:** a shared supervisor combines ordinary MAST resources. Separate
sources/templates isolate native profiles that cannot yet be safely combined.
The generator freezes sources, templates, cases and compiler hashes; the runner
later checks every admitted route against the same hand-derived observations.

**Spec:** the current root/user instructions, repository `AGENTS.md`,
`docs/capabilities/COMPLETION-MATRIX.json`, and the explicitly integrated lane
contracts under `output/parallel-implementation-2026-11-06/lanes/G*/`.

## Version scope and honest classification

Active work packages are **G01, G02, G06, G07, G08, G09 and G11**. RTC/calendar
and schedules remain active. G03/G04/G05/G10/G12..G20 are **DEFERRED_VERSION**;
their IDs remain in the manifest and can never acquire PASS from this version's
batch. New `float.*` acceptance is likewise deferred within G02's narrowed
integer/flag scope. Existing conversion/float/control regressions are preserved. Ordinary
C++ loops used by light algorithms do not promote exact native IF/FOR opcodes.

The authored static classification is
`tests/batch_acceptance/coverage_plan.json`: **250 rows**, including 29 prepared
source subsets, six prepared no-transport controls, 51 priority IDs awaiting
additional cases/contracts, and 164 deferred IDs. These are preparation states,
not test results, completed feature counts or a completion percentage.

Local, editor, official simulator and physical gates are separate. A successful
negative communication control is not a successful transaction. An unavailable
API, native binding, transport, template or observation never becomes zero or
PASS. Full-parity acceptance remains incomplete.

## Sources and controls prepared now

| Profile | Source | Resource scope |
|---|---|---|
| Supervisor | `examples/batch_acceptance/supervisor.cpp` | Ordinary MAST I/Q image, five underlying timers, light Clock, C0, FIFO R0/LIFO R1, public integer words |
| Subroutine | `examples/batch_acceptance/subroutine.cpp` | Existing stateless SR0/section2 profile, kept separate until broader contexts are integrated |
| Modbus | `examples/batch_acceptance/modbus.cpp` | SL1 master, READ_VAR0/WRITE_VAR0/WRITE_READ_VAR0 selected one at a time; no injected transport |

The supervisor selects a scenario from **I20..I23** while I19 is false, or from
**MW0** while I19 is true. Word-based selection makes all 24 input ports
observable without consuming the selector bits. I0 is reset for stateful cases;
I1 is enable/store/advance, I2 retrieve/down/STOP, I3 value/loop selector, I4 output
sentinel. Scenario-specific meanings are explicit in the literal case labels.

Q0..Q15 carry the complete result mask, mirrored as signed i16 in MW1. MW10+
carry public diagnostic values. Numeric scenario5 takes operands in MW20/MW21
and a nonnegative square-root operand in MW22. No private allocated M/MW address
is part of an oracle.

| Selector | Scenario | Independent observations |
|---|---|---|
| 0 | Ordinary I/O ports | First/last low ports, all16 output bits, upper eight inputs, releases |
| 1 | Boolean edges and toggle sequence | Fresh/held/released controls, rising/falling events, reset |
| 2 | TON30ms/TOF20ms/TP20ms | Literal virtual scan-start timeline and simultaneous timer state |
| 3 | FIFO/LIFO | Store11/22, held button, simultaneous no-op, order, empty sentinel retention |
| 4 | Counter and sequence/loop | Edge-driven step modulo3, CU/CD held controls, sums1..3=6 and1..5=15 |
| 5 | Integer words and S18 | Positive/negative arithmetic, signed overflow and explicit recovery |
| 7 | Alternating light Clock | Two phases, enable, held STOP, release and restart |
| mixed | Resource composition | Switch between queues, counter, edge latch and I/O without cross-resource leakage |

The current Clock scenario is a periodic helper, **not RTC/calendar**. RTC has
its own pending G09 profile and must receive explicit injected calendar inputs;
the host wall clock will not be substituted. The G09 draft identifies unresolved
native RTC block/XML bindings, so local RTC_EXEC support alone cannot count as a
generated SMBP. Final delivery/integration determines which RTC paths are native
products and which remain precisely gated.

The Modbus variant exercises the explicit default error255/15 after a fresh
Execute, held TRUE, release and selection across the three blocks. Positive
transport, Busy relocation, timeout, ASCII messages and EXCH need the integrated
G11 contract and a reviewed local observation adapter. No remote endpoint is
created or contacted by this preparation.

## Generator, runner and finite manifest

`tests/batch_acceptance/batch.py` has two explicit actions. Neither action has
been invoked during preparation.

```sh
# Only after root authorizes preparation of the final frozen batch:
python3 tests/batch_acceptance/batch.py prepare --output output/natal-final-batch

# Only after implementations are integrated and root freezes their hashes:
python3 tests/batch_acceptance/batch.py run --batch output/natal-final-batch
```

`prepare` writes source copies, bounded literal cases, source/template/oracle
hashes and a manifest containing all 250 IDs. It invokes no compiler. It refuses
existing destinations and unknown/duplicate IDs, missing expectations, malformed
stimuli, resource-profile/case mismatches and unconfirmed integration descriptors.

`run` compiles real source, writes/reimports SMBP, reverses the **actual generated
project**, recompiles/rebuilds it, and compares seven routes per case:

1. compiled IL Machine;
2. JSON round-trip Machine;
3. generated SMBP readback Machine;
4. recompiled actual-project reverse Machine;
5. rebuilt SMBP readback Machine;
6. original C++ native SDK execution;
7. actual-project reverse C++ native SDK execution.

Every route compares with literal masks/word values from `cases.json`, never
with another route as its sole oracle. The native bridge supplies input levels
and public word writes before each scan, observes public outputs/words, and uses
the same documented virtual scan-start convention. It neither patches production
classes nor supplies fabricated network success. Timed traces establish local
semantics only; GUI held states do not measure scan counts or physical timing.

A missing API/export or mismatched observation is a failure. Remaining priority
IDs cause default exit2 even if prepared cases pass. An explicit
`--allow-incomplete` permits a scoped run to return0 while preserving every
pending/deferred ID and the incomplete full-parity state in the report.
`native-batch.json` lists exact project hashes and labels only locally passing
products ready for root's **final** Schneider batch. It performs no GUI action.

## Integrating delivered priority APIs

CONTRACT.md/DELIVERY.md are evidence to read, not automatic main integration.
Do not activate an isolated lane because it says implemented. After root confirms
integration, add a reviewed JSON descriptor under
`tests/batch_acceptance/integrations/` with this interface:

```json
{
  "work_package": "G09",
  "main_integration": {
    "status": "confirmed",
    "notice": "Exact root integration notice/revision",
    "compiler_pins": {"m200/owner_module.py": "exact sha256"}
  },
  "variant": {
    "id": "rtc-calendar",
    "source": "examples/batch_acceptance/rtc_calendar.cpp",
    "template": "tests/fixtures/authentic_admitted_profile.smbp",
    "purpose": "Exact bounded integrated API scope",
    "exclusive_ownership": ["declared resources and pins"],
    "physical_execution": "pending",
    "local_transport": "none",
    "scenarios": ["rtc-literal-calendar"]
  },
  "cases": "examples/batch_acceptance/rtc_calendar_cases.json"
}
```

The example descriptor is a schema illustration, not an active descriptor or an
invented API/template. Explicit RTC calendar/lifecycle adapters and communication
transports require extending the test observation bridge to their delivered
contracts before activation. The current bridge refuses undeclared transports;
it cannot silently replace an RTC or message result with a local default.

Priority follow-ups are word/bit-bank and stack composition (G01), integer carry
and destination-error recovery (G02), broader useful SR contexts (G06), skipped/
repeated timer calls and options (G07), SBR/SC/DR (G08), actual RTC/agendas (G09),
and dynamic/message/transaction controls (G11). Finite resource variants must
reserve exclusive physical channels; fast I/O/PTO/analog modes remain deferred.
Drum cams and schedules must use reserved M outputs for composition, or a
separate variant with exclusive Q ownership. The supervisor's complete Q image
must never overwrite a hardware block's output and then call that block tested.

## Freeze and final acceptance checklist

- [ ] Root confirms priority implementations integrated into the main checkout.
- [ ] Test agents attach independent cases to each delivered priority contract.
- [ ] Root freezes source/template/oracle/compiler inputs; prepare one new batch.
- [ ] Test agents execute the authorized local batch and report failures by case.
- [ ] Preserve the 799 existing regression tests and run them only at root's gate.
- [ ] Root runs Schneider only in the final exact-artifact native batch.
- [ ] Record editor save/reopen separately from official runtime observations.
- [ ] Keep physical PLC, RF/load, wiring and timing qualification separate.

The first supervisor is a prepared composition candidate. It has not been
compiled, exported or validated. Its pending cases and deferred250-row audit are
visible rather than described as full parity.
