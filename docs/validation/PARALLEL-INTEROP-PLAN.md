# Parallel interop corpus — preparation only

The user narrowed this release to the Christmas requirements on 2026-11-06:
G01/G02/G06/G07/G08/G09/G11 remain active, including RTC. The new corpus is in
`tests/parallel_interop/`. No test, build, syntax check, GUI, Wine, network access,
commit or push was performed while preparing it. It does not modify the compiler,
SDK, existing tests or completion matrix.

## Active cases

- Literal Modbus FC1/2/3/4/5/6/15/16/23 request bytes, endianness, packed bits,
  signed word patterns, exact response lengths, exception codes and padding.
- Last valid/first invalid quantities, complete local MW spans and remote ranges.
- MBAP transaction/unit/protocol/length refusal, using memory-only byte strings.
- Independent scripted responses: first-held Execute, Busy/terminal behavior,
  active configuration and destination snapshots, no implicit retry, atomic
  protocol-error handling, timeout/Abort and same-port arbitration/release.
- C++ → JSON → VM/native SDK → native SMBP/config/graph → actual-program reverse
  → rebuilt C++/VM/native SDK for the existing sparse communication profile and
  signed mixed Register resources. Literal traces are checked on every route;
  route agreement alone is not the oracle. The no-transport communication case
  explicitly expects refusal 255/15 and proves no successful transaction.
- Forged native graph identity/pins, unknown/duplicate executable configuration,
  target/level limits, sparse resource allocations, caller immutability and
  preservation of destination/template on export refusal.
- Prepared G11 adapters for dynamic properties, SEND_RECV_MSG byte limits,
  EXCH/FB sharing, native Link codes and actual native serialization. Missing
  integrated APIs/transports/native bindings remain named pending records.

The scripted transport does not import the implementation's Modbus peer and
does not open sockets. Response/request oracles are literal protocol fixtures.
Lifecycle collision policies explicitly retain their local-policy qualification.

## Freeze and execution

Only the coordinator integrates lane source. A lane `CONTRACT.md` describes the
expected API; its `DELIVERY.md` is necessary before new-lane cases run, but neither
means that source was integrated or validated. Execute only after the coordinator
supplies the relevant integration freeze identifier. Individual local package
checks may then proceed; official editor/simulator acceptance waits for the final
integrated batch.

Prepared commands, **not executed**:

```sh
python3 tests/parallel_interop/run.py --list
python3 tests/parallel_interop/run.py --run --freeze-id COORDINATOR_FREEZE \
  --select 'G11.*' --output output/parallel-interop/G11-results.json
python3 tests/parallel_interop/run.py --run --freeze-id COORDINATOR_FREEZE \
  --select 'INTEROP.*' --output output/parallel-interop/project-results.json
```

The runner writes PASS/FAIL/ERROR/PENDING per case and hashes source, SDK,
fixtures and lane deliveries before/after execution. Exit0 requires all selected
cases to pass, exit1 means failure/error, exit2 means pending, and exit3 means
source changed during execution. Missing features are never unittest skips or
green results. Saved repro/evidence directories accompany JSON results. No CI or
remote runner is created or used.

## Adapter contract

`bindings.json` maps a lane to a local `module:function`. The adapter receives
`identity`, `lane`, `scenario` and required evidence stages, **without the expected
answer**. It calls public APIs in the integrated root and returns `observed` plus
paths to actual stage evidence. The harness compares observations against its
literal oracle and hashes the evidence. Adapters must not echo expectations,
import lane/source as the implementation, infer success from a delivery note,
or substitute round trip agreement for behavior/configuration checks.

`adapter_cpp.py` binds the declared C++ constructors, JSON, actual-IL reverse and
native project route. Model-only scenarios deliberately remain pending until the
final integrated runtime interface can be bound. A native export gate remains
pending rather than being counted as a successfully generated project.

## DEFERRED_VERSION

G12–G20 requests were already prepared when the user narrowed the scope. They
are retained as `DEFERRED_VERSION.json` and dormant data in `future_corpus.py`.
Their bindings are null and the default runner excludes them. `--include-deferred`
only lists them; combining it with `--run` is refused. No further peripheral,
motion, task, drive or SD expansion/testing is authorized in this release. RTC is
explicitly retained in the active packages; this deferral does not remove it.

Future data includes UDF/UDFB/SFC identity and state, pin conflicts/fallback,
analog injection, mapping/scanner ownership, retention boundary events, watchdog
and task rules, drive/PID capacities and honest unresolved protocol eligibility.
These are proposals for later adapter work, not passing tests or completed parity.

Local corpus evidence never proves official editor acceptance, physical I/O,
RF/electrical safety, flash/SD endurance, drive/homing behavior or PLC timing.
