# Closed WRITE_READ_VAR implementation path

The smallest useful increment is **static MW WRITE_READ_VAR configuration plus
Execute-only native graphics**, using the exact official 07 save. C++ construction,
IL/VM execution, reverse C++, shared-word allocation and the local FC23 protocol
already exist. The full-pin save provides the next authentic binding, but importing
its inline outputs requires more than adding an XML enum. This research changes
no product code and does not claim an official communication transaction.

## Exact official evidence

Both artifacts target TM200CE40T at `FunctLevelMan21_0`, were saved/freshly reopened
No error by root, and remain byte-identical. The public
[observation record](../validation/MODBUS-OFFICIAL-BINDING-OBSERVATIONS.json)
separates those steps from runtime, which was not attempted.

| Saved artifact under the lab `diagnostics/modbus-next-bindings-20261106/` | Bytes | SHA256 |
|---|---:|---|
| `editor-saved/07_write_read_mw_fc23_il_only_editor_saved.smbp` | 89601 | `6a7edd820fcaee97cc4c1c783005f0a88a0409c98934e7b6964fbce1004bb52e` |
| `full-pin-candidates/editor-saved/modbus_full_pin_write_read_editor_saved.smbp` | 98503 | `9e7a3359a99c433bdebe7eaca21235960de806fdfb8151a678e39345e4b3588f` |

Their block configurations are equal. The block class is
`...FunctionBlocks.Com.WriteReadVarBasic`, with the exact assembly-qualified
Entities Type used by the observation record. Address is `%WRITE_READ_VAR0`,
Index 0. Each field is required in the first closed binding:

| XML field/value | Existing IR field | Wrapper |
|---|---|---|
| Link `SerialLine1` | link=`SL1` | Existing FBComLinkParameterEnums enum wrapper |
| RemoteDeviceId 1 | id=1 | Int32 range wrapper |
| Timeout 100 | timeout_100ms=100 | Int32 range wrapper |
| ObjType `MW` | obj_type=0 | Existing FBComObjTypeParameterEnums enum wrapper |
| FirstWriteObj 17 | first_obj=17 | Int32 range wrapper |
| WriteQuantity 2 | quantity=2 | Int32 range wrapper |
| IndexDataOut 300 | index_data=300 | Int32 range wrapper |
| FirstReadObj 41 | first_read_obj=41 | Int32 range wrapper |
| ReadQuantity 3 | read_quantity=3 | Int32 range wrapper |
| IndexDataIn 400 | index_data_in=400 | Int32 range wrapper |

The observed binding context is SL1/Man21. Keep existing actual-template channel
and level checks; other links/levels need their own generated-project acceptance,
not a minimum guessed from an enum suffix. No template settings are synthesized.

The wrappers and `Value/int` or `Value/<enum>` paths match the exact saved bytes;
retain the existing exact assembly/version/public-key tokens. CommError/OperError
are not serialized configuration children in either artifact. Asymmetric sizes,
addresses and buffers must remain literal regression expectations: a reader and
writer sharing the same swap bug can pass their own round trip.

Official07 has four IL lines: BLK, LD `%M12`, EXECUTE, END_BLK. Its graph has exactly
two entities: NormalContact M12 at row0/column 0/Left,Right and WriteReadVarBasic at
row0/column 1/Left. No line is needed between adjacent entities.

The full-pin save has fifteen IL lines: Execute M10, Abort M13, OUT_BLK then
DONE→M14, BUSY→M15, ABORTED→M16, ERROR→M17 in order. Its 27 entities are two normal
contacts at (0,0)/(1,0), block at (0,1) with Left,Right, twenty horizontal lines in
rows 0–3/columns 5–9, and four Left coils at column 10/rows 0–3. These are observed
bindings, not permission to invent every partial pin layout.

## Current architecture and precise gaps

| Layer | Already present | Needed for this path |
|---|---|---|
| `ModbusConfig`/JSON | WRITE_READ_VAR; write fields plus independent read fields; MW-only, 121/125 limits and full local/remote extents | No new configuration schema or function code needed |
| C++ frontend | `WriteReadVar` with 9 constructor values or 10 with explicit native index; both local buffer extents reserved; one unconditional update per instance per scan | No new API for static Execute-only use. Dynamic native properties remain a separate gap |
| IL/VM/reverse | Closed 4/6-line blocks; Execute/Abort, status getters, completion writes to index_data_in | Full-pin 15-line IL is currently rejected; it needs validated lowering or a complete shared parser/runtime implementation |
| SDK | Config/constructor/getters and explicit communication test callback | No implicit client. Without callback, an execution edge yields 255/15. A callback supplies states; it does not independently prove the Python asynchronous model |
| Numeric/allocation | `memory_words_used` and frontend reservations include both complete buffers and MW/MD/MF aliases | Regression-check both extents; do not reserve only outbound words or confuse MW indices with DWORD indices |
| XML | READ/WRITE shared wrapper guards, staged replacement and actual template channel/level checks | Per-kind parameter maps, WR class and its ten fields; never broaden all kinds to accept a union of every field |
| Graphs | Execute-only READ/WRITE; Abort and WR gates explicit | Add exact WR Execute-only class/column/Left connection. Full-pin requires its own closed multirow checker; generic checker currently rejects rows 2/3 and mixed rows |

The IR's `first_obj/quantity/index_data` are deliberately the **write** side for WR.
Do not rename them globally or map WR through READ_VAR's parameter names.
`allowed_attribute` may recognize the union of established wrapper tags, but
`read_blocks` must still require and allow only the exact fields for the matched
class/address kind. Wrong class, unknown/duplicate field and wrapper failures
must remain explicit. The other active lane owns FC5/6; coordinate a single writer
for `communication_xml.py` and do not mix the two increments accidentally.

## Prioritized implementation and test gates

1. **Freeze fixtures and independent expectations.** Promote exact07 and full-pin
   saves/provenance only in the authorized implementation lane. Keep their hashes,
   typed hardware, actual serial master settings and separate No error/save/reopen
   evidence. Do not rewrite historical result manifests.
2. **RED→GREEN Execute-only binding.** Add WR's block Type and per-kind field map;
   reuse existing `ModbusConfig` validation. Add WriteReadVarBasic to the appropriate
   Execute-only Left connection handling and exact column 1 shape. Import07;
   compile the matching explicit C++ constructor; export/reimport and reverse/
   recompile; independently assert all six asymmetric data fields and allocations.
   Keep unimplemented Abort/full-pin forms rejected at this stage. This is a useful
   increment, not completion of every native WR surface.
3. **Full-pin import without semantic loss.** Prefer a dedicated closed native-body
   parser/checker and lower this exact shape to the existing 6-line update followed
   by four ordered `LD %WRITE_READ_VAR0.<status>; ST <target>` rungs. Check the
   original graph against the original IL before discarding its representation;
   validate the complete canonical program afterward. Preserve input snapshots,
   output order, labels/origins and legitimate destination alias effects. Do not
   return only Execute/Abort from a 15-line parser and silently drop its coils.
4. **Full-pin export/Abort is a separate explicit step.** A bare 6-line Abort block
   has not been observed as a saved graph. Do not remove the gate by drawing half
   of the 27-entity shape. Use a proved grouping/normalization path for all four
   native outputs, or collect the missing partial layouts. Any added scratch bits
   need allocation/budget proof and canonical reimport comparison. Existing source
   status reads before update must keep their prior-state ordering.
5. **Verify on the frozen combined tree.** Run focused XML/compiler/VM/protocol/
   reverse/graph negatives, independent review and one full local regression.
   Then normal CLI generation → root-only official open/save/fresh reopen, followed
   by a separately authorized real transaction with request/response and memory
   evidence. Clean binding evidence does not supply that final exchange proof.

Required negative controls include class/address mismatch; missing/duplicate/wrong
wrapper fields; old FirstObj/Quantity/IndexData tags inside WR; simultaneous old
and WR tag sets; noncanonical integers and unsupported attributes; ObjType other
than MW; write 0/122, read 0/126; remote start 65535 with count 2; local MW 7999 with
count 2; SL1 Id 0; undefined ETH remote; unknown/low actual level with forged metadata;
instance 31 below FL 10.1; invalid readonly status destinations; swapped/duplicated
ports/status rows, incomplete lines, forged descriptor/connection/geometry and
silent full-pin output omission. Rejected import/export must preserve originals
and any pre-existing destination.

## Task, resource and memory semantics

Generic p171 permits only one active communication FB/EXCH on a port during a
master-task cycle. The current engine arbitrates one exchange per modeled link;
occupied-link 255/11 and simultaneous Execute/Abort priority remain explicit local
policies, not observed PLC scheduling. No automatic retry/queue should be added by
this XML increment. Native `%MSGx.D` is ready/done when TRUE (Generic p129), not a
busy-TRUE flag. EXCH/MSG interoperation is still outside the implemented subset.

The first RUN task cycle seeing TRUE does not count as an Execute/Abort rising
edge; a FALSE observation must precede it (Generic p183). Execute edges while Busy
are ignored. Never turn one source update into two port requests or move the
update relative to application memory/status statements. Index budgets remain
16 per kind below human FL 10.1 and 32 at/above it, using the actual template token
mapping. Serial slave address, Ethernet remote-server index and MBAP Unit ID are
three different identities. Existing template ports/remotes must be preserved.

Outbound words are snapshotted into the current local request at Execute; valid
response words commit to the inbound range only on completion. Local overlap,
source edits while Busy and MW/MD/MF aliases therefore need explicit oracles.
Current local behavior is tested, but its exact native buffer timing remains
pending. Malformed/exception responses must not partially overwrite local input
words. Timeout or Abort does **not** establish that a remote write was rolled back:
a peer may have applied the write before a response was lost or cancelled.

## FC23 literal oracle and research probes

[Generic Functions pp182–186](https://www.se.com/ww/en/download/document/EIO0000003289/)
defines one transaction with a write followed by a read, MW only, write 1–121/read1–125.
[Modbus Application Protocol V1.1b3, section 6.17](https://www.modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf)
is the protocol-layout reference. The M200 guide's Modbus tables identify
**decimal 23 = hexadecimal 17**; Generic
p185's ambiguous “Fct17” wording must not become decimal FC17. This must remain
one FC23 PDU, not separate FC16 then FC3 transactions.

Independent literals for the exact07 configuration, outbound 1234/ABCD and inbound
8001/FFFF/1234:

- Request PDU: `17 0029 0003 0011 0002 04 1234 abcd`.
- Response PDU: `17 06 8001 ffff 1234`.
- TCP request prefix with TID 1234 and Unit 11 hex: `1234 0000 000f 11`.
- TCP response prefix: `1234 0000 0009 11`.
- Overlapping remote read at 18 after writing 17–18 returns `abcd 8001 ffff`,
  proving write-before-read in the independent local peer check.

At the documented maxima, FC23 request and response PDUs are 252 bytes each
(259-byte TCP ADUs), despite the general 253-byte PDU ceiling. Requests order the
read address/count before write address/count/data. Response byte count is twice
**read** quantity and has no echoed write address. Counts/ranges are checked before
peer mutation; read-range errors produce exception 9702, malformed quantity 9703.

Ignored `output/diagnostics/write-read-plan-2026-11-06/` contains the standalone
literal oracle/probe and `results.json`. It checked both source hashes/configs,
PDU/MBAP literals, remote write/read overlap, invalid read-range/no peer mutation,
six malformed responses, fourteen invalid configurations, 121/125 maxima and local
snapshot/overlap behavior. Result SHA256 is
`1c7319bed07b13150ad4817c12fc3c8978bdadac317b78bca0c7ca057e14df31`.
No socket/serial call, GUI, Wine, full suite or product
edit occurred. These are research probes, not new unit-test totals or official
runtime observations. The result pins the exact source snapshot it inspected.

Manual identities and installed type/factory evidence are in
[MODBUS-NEXT-BINDINGS-RESEARCH.md](MODBUS-NEXT-BINDINGS-RESEARCH.md). The new actual
saves close its earlier binding-evidence gap; they do not close dynamic writable
properties, all pin layouts, port/task interactions or physical/official protocol
runtime parity. Those remain required parts of the final project objective.
