# Independent asynchronous Modbus SDK validation

The `PLC_NATIVE` SDK now executes Modbus requests through its own bounded PDU
codec and scan-driven state machine. Its explicit transport supplies raw bytes,
pending/error events and cancellation tokens; it does not supply function-block
statuses or write the PLC memory image. The restricted-C++ frontend and native
Ladder exporter retain their existing public APIs and native profiles.

## Focused local results

- Both original G11 cases passed on VM and SDK: **four test executions**. Their
  literal expectations and the original VM provider remained byte-identical.
- Six new test methods covered **43 distinct SDK stimulus vectors**, including
  FC1/2/3/4/5/6/15/16/23, active-request and destination snapshots, outgoing data
  lifetime, next-request reconfiguration, token zero and captured callbacks.
- Malformed replies preserve the entire destination. Abort, late bytes,
  timeout, disabled timeout, link contention/release, separate links, broadcast
  acknowledgement and missing/partial transport paths were exercised.
- Valid READ/FC23 stores clear only overwritten indeterminate-word masks;
  unrelated memory and S17/S18/SW17 remain unchanged. An indeterminate WRITE
  source traps before the transport is called.
- Eight existing compatibility methods passed. The legacy callback case passed
  ten frames on two SDK routes; the unchanged default-error Modbus program
  passed ten frames on seven local routes. Its emitted native IL, configuration
  and graph matched the pinned baseline exactly.

One initial test-harness identifier collision prevented a channel test from
compiling. Only the harness names were corrected, and only that method was
repeated. The initial failure is retained; no product fix or expectation change
was needed. The focused checks kept all **74 compiler/SDK pins** intact.

Exact evidence is preserved in the [focused-vector bundle](g11-sdk-async-2026-11-06/focused/README.md)
and [compatibility record](g11-sdk-async-2026-11-06/compatibility/RESULTS.md),
including the initial harness failure and its affected-method follow-up.

The [SDK API and transport contract](../MODBUS.md#plc_native-raw-asynchronous-pdu-transport)
documents callback lifetimes, bounded buffers, captured configuration, ownership,
error mappings and the local edge policy. The permanent tests are
[`test_modbus_sdk_async.py`](../../tests/test_modbus_sdk_async.py) and
[`g11_sdk_host.py`](../../tests/parallel_semantics/g11_sdk_host.py).

## Evidence boundary

The [single final combined run](g11-sdk-async-2026-11-06/full-gate/RESULTS.md)
recorded 1,045 tests: 1,038 PASS, seven FAIL, zero ERROR/SKIP. Six are unchanged
native-oracle gaps. The seventh was an omitted pinned public fixture; restoring
its verified bytes and rerunning only that method gave one PASS. The original
full log remains exit 2. All 74 source pins were unchanged; no full retry ran.

These results exercise the real C++ SDK with literal raw-PDU stimuli. They do not
qualify native PLC transactions, wire framing, physical serial/TCP peers, timing
or every lifecycle policy. The official simulator's separate READ error-path
observation is recorded in the [Natal delivery](NATAL-DELIVERY.md); its observed
COMMERROR=6 is not assigned a guessed cause or substituted with the SDK's default
255/15 result. Full-controller parity and physical acceptance remain unfinished.

The final combined regression and exact public evidence are linked from the
[delivery report](NATAL-DELIVERY.md). All execution is local; GitHub Actions stays
disabled.
