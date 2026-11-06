# Local Modbus TCP transport recovery — 2026-11-06

The loopback reference client previously treated any response with another Transaction Identifier as a malformed reply to the active request. A stale/unrelated ADU arriving before the correct response terminated that request, including when both ADUs arrived in one TCP stream write.

The primary contract is [Modbus TCP Implementation Guide V1.0b, §4.4.1.3, printed p.24](https://www.modbus.org/file/secure/messagingimplementationguide.pdf): discard a response that has no pending transaction; parse and confirm responses belonging to a pending transaction. This work changes the local transport's stream handling to follow that distinction. It does not change the pure single-ADU `decode_tcp` validator.

## Change and finite bounds

`m200/modbus.py` now reads exactly one MBAP header and its bounded body, so a coalesced next ADU stays in the socket for a later poll. A complete ADU with an unmatched TID is discarded without completing the request or modifying its destination. The original request remains pending under its existing timeout.

- One pending exchange and one receive call per poll; no automatic request retry.
- At most 260 buffered bytes, determined by a validated MBAP length.
- Up to 16 unmatched complete responses may be discarded per exchange; a seventeenth produces local malformed-response error `(CommError=0, OperError=2)` and closes that exchange. This finite budget is a local resource policy, not a claimed Schneider controller rule.
- The active transaction still requires protocol ID0, valid length, the configured Unit ID and a valid PDU. Wrong Unit ID is not reinterpreted as success.
- Timeout/exception/truncation/resource-limit cleanup allows the same engine and transport to open a fresh connection on a later explicit Execute edge. Held Execute does not automatically retry.

## Reproduction and verification

Before the change, the new real-socket tests failed in three cases: stale ADU before the active reply, coalesced stale/current ADUs, and stale-only data that should leave the request pending until timeout. The existing malformed-response test also needed its unknown-TID-plus-EOF expectation corrected: after discarding the unrelated ADU, EOF without the requested response is a channel failure `(255,6)`, not a malformed matching reply.

Six new tests use a scripted server bound only to `127.0.0.1` on an OS-selected ephemeral port. Responses use independently constructed MBAP/PDU bytes. Events, socket timeouts, test deadlines and thread joins bound the fixture; no simulator or network device is involved. Cases cover:

1. Discard stale data without changing sentinel memory, then accept a fragmented active reply.
2. Independently frame a maximum-length unmatched ADU and the active reply sent together.
3. Leave stale-only input pending, expire at the configured scan-clock timeout, then reconnect on a new edge.
4. Accept the active reply after 16 unmatched ADUs, including with timeout disabled.
5. Stop a 17-ADU unmatched flood and recover on a new connection without changing destination memory on failure.
6. Recover on the same engine/transport after a matching bad Unit ID, Modbus exception and truncated response.

Focused command:

```sh
python3 -m unittest tests.test_modbus tests.test_modbus_transport_recovery tests.test_communication_compiler tests.test_communication_xml tests.test_communication_project
```

Observed result: **85 tests passed in 2.203s**. This includes protocol/state/transport regressions and the existing dedicated compiler/XML/project communication integration tests. The full repository suite was not rerun in this subtask; concurrent compiler work owns integration verification. No CI was created or run.

Changed implementation/test files: `m200/modbus.py`, `tests/test_modbus.py`, `tests/test_modbus_transport_recovery.py`. The parity audit was translated to English and its transport/test inventory updated. No frontend, IL executor, reverse compiler, project writer, SDK, vendor binary or runtime setting changed in this subtask. Nothing was staged or committed.

## Evidence limits

These are local Python client/server and compiler-integration results. They do not establish official editor acceptance, M2xxBasicSIM Modbus behavior, RS485, controller scheduling or physical TM200CE40T interoperability. No port502, GUI, Wine, simulator, external Modbus endpoint or physical PLC was accessed. The primary protocol guide was consulted as documentation. The experimental external `getsockopt` guard remains unapplied and is unrelated to this change.
