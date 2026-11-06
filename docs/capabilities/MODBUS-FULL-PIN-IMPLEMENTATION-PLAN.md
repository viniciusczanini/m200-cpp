# Closed native Modbus full-pin implementation plan

2026-11-06. This is a read-only preparation note. No product code, tests, fixtures, gates, GUI or communication endpoints were changed. The next useful increment is **exact full-pin import plus export of its canonical update/status sequence**, using the three authentic saves already recorded in [official binding observations](../validation/MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md). The final parity objective remains broader than these first admitted forms.

## Evidence and first scope

All three exact saves target TM200CE40T, actual `FunctLevelMan21_0`/SL1 master. Each contains one rung, fifteen InstructionLine elements and 27 Ladder entities. Root observed official conversion/save and fresh reopen No error; no exchange was attempted. The completed WRITE save below is authoritative; the nearby `before_save_completed` artifact is not a substitute.

| File under lab `diagnostics/modbus-next-bindings-20261106/full-pin-candidates/editor-saved/` | Bytes | SHA256 |
|---|---:|---|
| `modbus_full_pin_read_editor_saved.smbp` | 97080 | `8154e130ce73b6a1b6e90f5876264437ec36778207fc38c3a3661152059f9e50` |
| `modbus_full_pin_write_editor_saved.smbp` | 97089 | `ae6ffad294a36e79656f36845f2a0bebf19df6f3e60b8aa7b82597b867b79af3` |
| `modbus_full_pin_write_read_editor_saved.smbp` | 98503 | `9e7a3359a99c433bdebe7eaca21235960de806fdfb8151a678e39345e4b3588f` |

The actual configurations are READ I/FC2, first17/count17/MW200; WRITE Q/FC15, first73/count17/MW240; WR MW/FC23, write17/count2/MW300 and read41/count3/MW400. All have ID1/timeout100. Their static configuration codecs are already admitted by the preceding increments. The first full-pin profile should use these actual contexts, normal memory contacts and ordinary memory coils; other contexts remain follow-up acceptance cases rather than controller impossibilities.

For each key, the literal native body is:

```text
BLK <key>
LD %M10
EXECUTE
LD %M13
ABORT
OUT_BLK
LD DONE
ST %M14
LD BUSY
ST %M15
LD ABORTED
ST %M16
LD ERROR
ST %M17
END_BLK
```

Its graph is exactly two normal contacts at (row0,column0)/(row1,column0); the matching ReadVarBasic, WriteVarBasic or WriteReadVarBasic at (0,1); twenty horizontal lines at rows0–3/columns5–9; four ordinary coils at column10/rows0–3. Contacts, block and lines have Left,Right; coils have Left. This block connection differs from the current Execute-only Left connection. Do not change the global connection table to admit both indiscriminately.

## Implementation seams

1. **Add a dedicated full-body parser and graph checker.** Keep [communication.parse_block](../../m200/communication.py) closed to its current four/six-line contract. A new parser should return key, Execute, Abort and all four ordered output destinations; returning only the first three values for a fifteen-line body would silently lose coils in existing consumers. Require the exact OUT_BLK/status order and ST actions, valid writable destinations, complete terminators and known fields. A dedicated graph path should compare all 27 expected entities, coordinates, descriptors and connections against the original parsed IL, rejecting omissions, duplicates and extras. The generic [project.check_graph](../../m200/project.py) currently rejects mixed rows and rows2/3; weakening that generic rule would admit unrelated unverified graphs.
2. **Normalize import before whole-program validation, after checking the original body/graph.** Produce the existing six-line update followed immediately by four rungs `LD <key>.<status>; ST <target>` in DONE/BUSY/ABORTED/ERROR order. Qualify each status with its own key. Retain an original rung label on the update, preserve source order and map all five canonical rungs to the original origin. Then run the existing complete IL/resource/allocation validation. Other rungs must still undergo their ordinary graph checks. One native rung/fifteen raw instructions becomes five canonical rungs/fourteen instructions; report both counts. This expansion requires no new scratch memory or protocol operation.
3. **Export only a complete, safe canonical group.** After the existing [Ladder normalization](../../m200/ladder_lowering.py), recognize one six-line communication update followed by exactly the four ordered two-line status-store rungs for that key. Require ordinary ST memory coils and the proved input predicates. No interior rung may have a label or a separate control-flow entry. Emit one native fifteen-line body and its literal 27-entity graph without mutating the caller's Program. Preserve the first label/origin and retain a mapping for the four grouped origins. Nonmatching bare Abort/partial-output forms should retain an explicit missing-binding refusal; do not fabricate unused coils to force a match. Existing Execute-only export remains unchanged.
4. **Reuse runtime and reverse support.** [IL validation/VM](../../m200/il.py), [reverse C++](../../m200/reverse.py) and the public frontend already handle the normalized six-line update plus qualified status reads/stores. No new SDK, transport or FC is required for this path. The exporter must recognize compiled C++ as well as imported IR. Start with `update(read_m(execute), read_m(abort))` followed by four explicit `write_m` calls. Avoid a new public API until tests demonstrate a need.

## Semantics and independent oracles

Both inputs must be evaluated before the update and before any output coil writes. Keep the update at its original program position, followed by ordered status writes. Outputs that alias an input affect the next invocation, not the already sampled current inputs. Repeated destination aliases must either preserve last-write order or remain explicitly outside the initial profile; never deduplicate/reorder outputs. Status reads before the block must retain prior-state behavior. Labels, END/conditional END, jumps around the block and other FB calls must not cause an extra exchange or bypassed-output write.

Use literal expectations instead of comparing a reader to its own writer:

- Exact fixture hashes, fifteen normalized source lines and the complete 27-tuple graph for all three classes. Assert the five-rung normalized IR and all complete packed/word buffers independently.
- An independent trace table for DONE/BUSY/ABORTED/ERROR: initial TRUE edge suppression, FALSE→TRUE Execute, Busy, completion, Abort, timeout/fault and simultaneous Execute/Abort. Compare all four coils, neighbors, request count and input/response words. Existing local priority/timing rules are model evidence; native runtime confirmation remains separate.
- Literal FC2/FC15 packed 17-bit buffers and FC23 asymmetric request/response bytes. Confirm one request per update edge, outbound snapshot, valid-response completion commit and no partial inbound write on malformed response. Cancellation/failure does not prove remote rollback.
- Coherent negative mutations: swapped status names and coils, wrong class/key/index, mismatched IL/graph predicates, missing OUT_BLK/END_BLK, duplicate/unknown pins, S/R/STN output actions, nonwritable destinations, missing/duplicate lines, wrong block Left-only connection, shifted rows/columns, extra contacts/coils, attributes/nested/mixed content. Preserve templates and existing or absent destinations on every rejection, including a late failure after a valid earlier block.
- Canonical grouping negatives: another-key status, a missing/interleaved store, a label or jump target inside the quartet, reversed output order and partial layouts. Check import→reverse→recompile→export→import, source/template authority and preserved hardware. Include full-pin groups beside OR/branch/loop/timer logic so general normalization cannot accidentally break recognition.

Read-only probes of the current frozen code verified that all three native saves currently fail with `unsupported native communication block layout`, while the proposed five-rung IR already validates and reverses. In these exact probes reverse/recompile produced nine rungs/23 instructions, including existing private initialization/input snapshots, with the four status stores still adjacent. Adding an OR tail also preserved their adjacency after current general normalization. These observations establish feasibility, not a guarantee for every control-flow shape; add focused regression cases before relying on that property. Probe results and all inspected module hashes are pinned in ignored `output/diagnostics/modbus-full-pin-plan-2026-11-06/research.json`, SHA256 `a2fbbc11264691d7add5605188f1ad2d9db0f1d23532d78cc42ab07f9cd82241`.

## Completion gates and next forms

Implement only after the preceding 544-test checkpoint is isolated. Promote the three exact saves with provenance/byte-preservation, establish meaningful RED tests, implement the parser/checker/import and complete-group export, obtain independent review, then run one frozen combined local regression. Generate genuine CLI full-pin products for root-only official open/save/fresh reopen. Record raw/native versus canonical counts and any actual compiler overhead. No local round trip or GUI persistence result supplies official transaction, port scheduling or physical PLC proof.

Next forms remain explicit work: bare Abort without all four outputs; subsets/reordered outputs; negated/edge/comparison inputs; other coil actions and output address categories; other levels/links/object configurations; writable dynamic properties and complete native port/task interactions. The exact full-pin path is a first usable increment toward those forms, not a permanent boundary on parity.
