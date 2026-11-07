# G11 independent SDK raw-PDU validation

**Scoped PASS:** the two unchanged original G11 cases passed VM+SDK (4 methods,1.171 s). The new six-method module covers43 distinct SDK stimulus vectors. Five complete methods passed initially; the affected channel/timeout method then passed in2.853 s after a test-only C++ identifier collision was corrected. No expected values changed.

Coverage: all FC1/2/3/4/5/6/15/16/23 wire literals; request/data snapshots and next-request reconfiguration; token0, request-pointer lifetime and captured callbacks; strict malformed response/exception/echo/padding/size atomicity; timeout, cancellation, link contention/release, broadcast and default-error behavior. READ/FC23 clear only destination poison; malformed/abort preserve data+poison; S18/S17/SW17 remain sticky; an outgoing poisoned word traps before any raw start callback.

The transport supplies bytes/pending/broadcast/error only. It contains no Modbus codec, FB status model, response word stores or status-returning legacy hook. VM delegation and the original oracle source files remain byte-identical. Root registry has not been edited.

## Exact three-file handoff

| Repository path | SHA256 |
| --- | --- |
| `tests/test_modbus_sdk_async.py` | `50891659cf915ea5968f349359d84f6f131aa14256d2adfd9b85bdfac66ae810` |
| `tests/parallel_semantics/g11_sdk_host.py` | `16f14b80797cc87154bea326415aa67b1d23e34ffa6c1ce4a9e8c83de95fea8b` |
| `tests/parallel_semantics/adapters.json` | `f0b3175743ce2ba049bccdf76820650e9a965266a83674312b7b2c6753509ef2` |

Copy from `final/`; `FINAL.json` records exact paths and all74 core/SDK hashes. All74 private pins and root core bytes remained unchanged. Of301 private inputs, only the documented context-name correction changed `g11_sdk_host.py` after the initial snapshot.

Historical failure: generated Script contexts and FBs were both named first/second. `raw-vectors.log`, the failed host source/compile output and `harness-revision.json` are preserved. The fix renamed only test context variables; no implementation/oracle was changed. No replay of the five green methods or four original inventory methods.

Commands/results: `priority-results.json`, `raw-vector-command.json`, `focused-channel-command.json`, `raw-vector-inventory.json`, `summary.json`, before/after input pins and retained per-vector C++/compiler/runtime output.

No GUI, physical/network peer, CI, fullsuite or root source/test/registry mutation. The six native-oracle pending failures are untouched; this is not official PLC compatibility.
