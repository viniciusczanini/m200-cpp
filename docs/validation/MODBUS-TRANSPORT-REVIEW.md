# Modbus transport publication review

Review date: 2026-11-06. **No actionable defect found** in the formatted
transport recovery diff, its six new tests and the corrected existing malformed
response test. Only this review document was written; implementation and test
files were unchanged.

| Reviewed file | SHA-256 |
|---|---|
| `m200/modbus.py` | `a391ce5ff71520cea4f6b74d9ae984ba6cb4d6fff36b9d44fe05396e68c2e32b` |
| `tests/test_modbus_transport_recovery.py` | `564d4d062d98871885cd3a62d773bdf3617117e86ded0b551a0cd3bbdc6deb9a` |
| `tests/test_modbus.py` | `6a5d5b4e04363514b44b199793593e2d887a4d6dbbbd69937f34d91eb42b7546` |

## Framing, ownership and finite work

The client preserves the pending request when a complete response belongs to
another transaction. This matches the transaction-selection rule in the
[Modbus TCP Implementation Guide V1.0b, section 4.4.1.3, p.24](https://www.modbus.org/file/secure/messagingimplementationguide.pdf).
It reads one header/body boundary at a time, leaving adjacent ADUs for later
polls. The pure `decode_tcp` single-ADU validator remains strict.

There is one pending socket, at most one receive per poll and at most 260 bytes
in the application's response buffer. Protocol and length are validated before
using the body length. Sixteen complete unmatched ADUs may be discarded; the
seventeenth closes the exchange with a local protocol error. No discard loop,
request retry or growing response queue was introduced.

Matching transactions still require the configured Unit ID and a valid
function, response shape and payload before destination words change. A bad
matching response is terminal; a later valid frame cannot overwrite that
failure. Malformed MBAP framing also fails closed. EOF after discarding an
unmatched response is correctly a missing-response channel failure, rather
than a malformed matching response.

The original scan-clock deadline remains in force across discarded frames.
**Timeout zero intentionally allows an indefinite wait for a silent or partial
peer**; it does not promise finite transaction duration. Per-poll work, storage
and complete-frame discard counts remain bounded, and explicit Abort/close
remain available. Deadlines depend on the caller advancing the engine clock.

## Focused verification

```sh
python3 -m unittest tests.test_modbus_transport_recovery tests.test_modbus.ModbusLoopbackTests -v
```

Result: **15 tests passed**. The full repository suite was not rerun by this
reviewer.

Twenty additional independent real-socket cases passed: all twelve split
positions in the valid reply after a stale ADU; bytewise framing with TID wrap
to zero; unrelated PDU/Unit ID discard; a trailing duplicate; a bad matching
function followed by valid data; malformed protocol/length; and partial-header
timeout/Abort. Tracing actual socket calls confirmed one receive per update,
bounded receive sizes, and no destination writes on failure. Unknown token
poll/cancel did not disturb the owned exchange. Terminal paths released the
socket and engine link; held Execute did not retry. The regression suite also
verified fresh-edge reconnection after timeout, flood, exception and truncation.

All real sockets used numeric IPv4 loopback and OS-selected ephemeral ports,
with deadlines and joined peer threads. No GUI, Wine, simulator, port 502,
external Modbus endpoint or physical PLC was accessed. These results validate
the local client and its resource policy, not Schneider runtime interoperability.
