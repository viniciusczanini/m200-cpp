# Native Modbus full-pin profiles

2026-11-06. **568 tests passed in 205.314 seconds**, with zero skips and all 149 source/input pins unchanged. The increment adds 24 regression methods to the published 544-test checkpoint. The focused communication/allocation/copy-fusion cohort passed 106 tests in 24.648 seconds; Ruff check/format passed for 102 Python files. Independent review found no outstanding findings and verified the terminal full-run log and every pin without repeating the full suite. Historical result reports remain unchanged.

## Admitted native binding

The new [communication_graph.py](../../m200/communication_graph.py) checks the original fifteen-line full-pin body and its complete 27-entity graph **before normalization**. Narrow [project.py](../../m200/project.py) adapters import it as the established six-line Execute/Abort update followed by four qualified status-store rungs, ordered DONE, BUSY, ABORTED, ERROR. Export regroups only that complete, adjacent, same-key sequence. The update may carry a label; the four interior status rungs cannot carry labels or separate control-flow entries. The caller's Program and metadata are not mutated.

The first profile uses actual XML **`FunctLevelMan21_0` (human 14.0), SL1 master**, normal direct M contacts and ordinary ST M coils:

| Kind/object | Function | Exact captured buffers |
|---|---:|---|
| READ_VAR I | FC2 | Remote17/count17 → MW200–201 |
| WRITE_VAR Q | FC15 | MW240–241 → remote73/count17 |
| WRITE_READ_VAR MW | FC23 | MW300–301 → remote17/count2; remote41/count3 → MW400–402 |

Existing typed parameter validation and complete buffer extents remain authoritative; admission does not dispatch on fixture hashes or fixed parameter values. Actual template fields, IL, graphics and allocations control acceptance. Other full-pin profile contexts remain explicit tool gaps, not controller impossibilities.

The observed graph has normal contacts at (row0,column0)/(row1,column0), a matching native block at (0,1), twenty horizontal lines at rows0–3/columns5–9 and four coils at column10/rows0–3. The block has **Left,Right**, unlike the existing Execute-only Left binding. A dedicated checker validates that distinction, exact geometry, descriptors, wires, unknown fields and original graph/IL mixed tails. The generic graph checker was not broadened.

## Authentic saves

All three exact root-operated conversion/Ctrl+S saves and fresh reopens No error are preserved byte-for-byte, including native CRLF. Adjacent provenance files retain original candidate identities, six capture hashes, readbacks and procedure. Existing `modbus*.smbp -text` coverage was verified. Each fixture has three blank password fields.

| Fixture | Bytes | SHA256 |
|---|---:|---|
| [READ I](../../tests/fixtures/official_tm200ce40t_modbus_full_pin_read.smbp) | 97080 | `8154e130ce73b6a1b6e90f5876264437ec36778207fc38c3a3661152059f9e50` |
| [WRITE Q](../../tests/fixtures/official_tm200ce40t_modbus_full_pin_write.smbp) | 97089 | `ae6ffad294a36e79656f36845f2a0bebf19df6f3e60b8aa7b82597b867b79af3` |
| [WRITE_READ MW](../../tests/fixtures/official_tm200ce40t_modbus_full_pin_write_read.smbp) | 98503 | `9e7a3359a99c433bdebe7eaca21235960de806fdfb8151a678e39345e4b3588f` |

The completed WRITE save is used; the nearby intermediate `before_save_completed` file is excluded. Each captured project has one raw rung/fifteen IL lines/27 entities, normalized to five rungs/fourteen instructions. Source instruction counts are reported separately from canonical counts. See [official binding observations](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md) and the [implementation plan](../capabilities/MODBUS-FULL-PIN-IMPLEMENTATION-PLAN.md).

## Ordering, origins and verification

Both inputs are sampled before the update and before any status stores. DONE feeding Execute affects the next invocation. Repeated output destinations retain ordered last-write semantics, including BUSY and ABORTED sharing the Abort memory bit. Tests cover initial-TRUE suppression, Busy/completion, Abort, timeout, simultaneous edges, absent transport, jumps around the block, conditional END, a following timer, C++ loops/OR composition, reverse/recompile and complete-group export/reimport. Literal FC2/FC15 17-bit packets and asymmetric FC23 buffers verify request count, neighbors and complete memory extents. A malformed response sets Error without a partial local inbound commit; it does not establish rollback of an already applied remote write.

The existing source-map sidecar remains unchanged. `native_full_pin_groups` retains native origin/comment details, and a reserved suffix in the existing MainComment field carries all five grouped canonical origins so they can be recovered from SMBP alone:

```text
\nM200_CPP_FULL_PIN_ORIGINS=<JSON array of exactly five origins>
```

Here `\n` denotes an actual newline. The suffix is limited to 65536 UTF-8 bytes, rejects duplicate keys/markers and malformed data, and allows only the existing file/line/column/generated origin fields and types. The human comment prefix is preserved verbatim and reexport does not accumulate suffixes. This payload is audit metadata: it cannot select IL, graph grouping, labels, configuration, profile or allocation. Valid forged provenance leaves execution unchanged; malformed audit metadata produces a controlled failure.

TDD first exposed the missing native-body binding. Additional RED cases exposed human-comment replacement, an unbounded audit suffix and original source locations being replaced during general Ladder normalization. The authorized change in [ladder_lowering.py](../../m200/ladder_lowering.py) copies already validated existing origins and retains its generated fallback when absent. Tests cover before/group/after locations, one-to-many expanded origins, complex-tail normalization and identical generated IL with and without origin metadata. No control-flow or allocator behavior was changed.

Independent review checked all three classes and six authentic captures, nine graph negatives, nine actual-profile negatives, 21 unsafe grouping cases with both destination states, 26 further structural/coherent import negatives, twelve forged-template atomic cases, eight provenance controls, literal status/wire oracles, native/VM/reverse paths, aliases and source-origin sentinels. No old negative test rows were removed: bare Abort, partial/extra output graphs and direct fifteen-line Program writer bodies remain refused. Existing four-line Execute-only updates followed by separate status rungs still export normally. `parse_block` remains four/six-line; codecs, frontend, reverse, SDK, IL/VM and protocol/runtime code are byte-unchanged.

## Genuine CLI products and remaining proof

Three public-CLI products are frozen under ignored `output/diagnostics/modbus-generated-full-pin-candidates-2026-11-06/` and its P: mirror. All 36 hashed files were verified in both locations. No XML was hand-edited. Writable GUI working copies are:

| P: filename | Original SHA256 |
|---|---|
| `modbus_generated_full_pin_read.smbp` | `afa4c24d14329fdc2f58a2fdba5c5be7a2249a916975cd6666c5138780723fa5` |
| `modbus_generated_full_pin_write.smbp` | `4535d3f02aea9855c04294ce548b697bf53953b22788415a0aba8a9ba33cc07f` |
| `modbus_generated_full_pin_write_read.smbp` | `57c8f1739fafb8341049dc472f0727591876168e5354fa80d400a350bbc3297f` |

Each has three raw rungs/nineteen instructions, versus seven canonical rungs/eighteen instructions: M10/M13 snapshots into M500/M501, then the complete native block and M14–17 status coils. Hardware, configuration and grouped origins are preserved. Exact generated-product official acceptance was pending at preparation and must be recorded as a separate root-operated stage.

Exact hashes, source pins, local logs and independent evidence are in [MODBUS-FULL-PIN-PROFILE-RESULTS.json](MODBUS-FULL-PIN-PROFILE-RESULTS.json). The optional authentic Register CONFIG test ran here with its two exact ignored inputs pinned; its previously documented public-checkout skip remains applicable. No official transaction, native instruction timing, serial delivery, firmware or physical PLC proof follows from local models or binding persistence. Bare/partial native pin layouts, further contact/coil forms and profile contexts, dynamic properties and full port/task interactions remain work toward the unchanged full-parity objective.
