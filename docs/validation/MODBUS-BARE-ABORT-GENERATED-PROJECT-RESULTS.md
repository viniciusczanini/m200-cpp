# Genuine bare Execute/Abort Modbus products

2026-11-06. All three genuine CLI products completed official Programming **No error**, Ctrl+S and fresh saved-clone Programming reopens **No error** after another project. Root operated the editor; independent review verified six exact captures, full typed readbacks and saved-file C++ round-trips. This static stage used no simulator, RUN or communication transaction.

## Reusable public sources

The three public examples are byte-exact copies of the originally tested C++ sources:

- [modbus_bare_abort_read.cpp](../../examples/editor_validation/modbus_bare_abort_read.cpp): READ I/FC2 without status getters, remote17/count17 into MW200–201.
- [modbus_bare_abort_write_aliases.cpp](../../examples/editor_validation/modbus_bare_abort_write_aliases.cpp): WRITE Q/FC15, MW240–241 to remote73/count17; partial/reordered status stores share M30 so later BUSY overwrites ERROR.
- [modbus_bare_abort_write_read_timer.cpp](../../examples/editor_validation/modbus_bare_abort_write_read_timer.cpp): asymmetric MW/FC23 buffers, a 10 ms-base TON4 with preset2, composite Execute/Abort and separate status rungs.

Run from a public repository clone using the included authentic Man21/SL1 templates:

```sh
./m200c compile examples/editor_validation/modbus_bare_abort_read.cpp \
  --template tests/fixtures/official_tm200ce40t_modbus_full_pin_read.smbp \
  -o output/modbus-bare-read
./m200c compile examples/editor_validation/modbus_bare_abort_write_aliases.cpp \
  --template tests/fixtures/official_tm200ce40t_modbus_full_pin_write.smbp \
  -o output/modbus-bare-write
./m200c compile examples/editor_validation/modbus_bare_abort_write_read_timer.cpp \
  --template tests/fixtures/official_tm200ce40t_modbus_full_pin_write_read.smbp \
  -o output/modbus-bare-write-read
```

Local CLI help confirms `--template` and `-o`/`--output`. Each public copy was compiled once into fresh ignored output. Canonical IL, communication/timer/counter configuration and symbols match its frozen original exactly. Only metadata.source and 8/16/37 source-origin filenames change; line/column/generated origins remain equal. The public-path rebuilds therefore have their own hashes and are not relabelled as the exact GUI-tested original bundles. All 172 earlier pinned inputs plus the three examples and CLI launcher remained unchanged (176 pins); the 628-test suite was not repeated for identical source copies.

## Exact products and static editor stage

Root opened writable P: copies of genuine CLI outputs, viewed Programming No error, used Ctrl+S and preserved the actual saved bytes as filesystem clones. Another project was opened before each fresh saved-clone reopen. [READ save](editor-evidence/modbus-bare-generated/read-save.png)/[reopen](editor-evidence/modbus-bare-generated/read-reopen.png), [WRITE save](editor-evidence/modbus-bare-generated/write-save.png)/[reopen](editor-evidence/modbus-bare-generated/write-reopen.png) and [WR save](editor-evidence/modbus-bare-generated/write-read-save.png)/[reopen](editor-evidence/modbus-bare-generated/write-read-reopen.png) show the six settled No error views. The frozen static journal has twelve completed full-argument entries. No XML repair or GUI Save As is claimed.

| Product | Frozen original bytes / SHA256 |
|---|---|
| READ, no statuses | 151097 / `3481058f61b536d06a88b158e1b0cec45cf2f2750e7589c7dfb6b858b3f2bdc6` |
| WRITE, aliases | 192845 / `225bc26220b731b1bcedbae6e2d4c5b81321873285346c881da78164a620ad55` |
| WRITE_READ + timer | 341577 / `7eceb1dec3c44d8c0d150c4db4a91b58822746b920eefaa7da00df4b7b9c858e` |

| Product | Actual editor-saved bytes / SHA256 |
|---|---|
| READ, no statuses | 155988 / `5a5bc2034e39d1f7bdd9a8e97c9c18c78b0e5e9d30548b683c769932525ea640` |
| WRITE, aliases | 199029 / `3d9c7d0f43197e550394ad5cd19295b3a5195ede368c597a51633aca98f51334` |
| WRITE_READ + timer | 353702 / `55ce5db272eda93b9e52ad8d43ac0b915f47d8f4d1cc604edd770e4ef3859b8b` |

All three keep one native six-line/three-entity communication graph. Surrounding logic remains ordinary rungs; the saved projects retain 19/44, 31/66 and 72/161 rungs/instructions respectively. The originals, source/template files and all 238 frozen bundle records remain byte-identical. The existing Untrusted DLL banner remains visible; no cause or resolution is inferred.

## Complete readback and honest normalizations

Independent whole-tree comparison and the actual product reader preserve every executable lexical IL token, rung order, communication wrapper/value, hardware field, task/CPU-behavior setting, watch tree, instruction comment, rung Name/MainComment/Label and software symbol. Graph types, positions, descriptors, connections and entity counts are unchanged. The complete differences are:

| Case | Root identity | Bit/timer allocation omissions | Graph field changes | Timer defaults omitted |
|---|---:|---:|---|---:|
| READ | 2 | 2 | 30 Symbol, 3 Comment, 2 comparison spacing | 0 |
| WRITE | 2 | 2 | 38 Symbol, 4 Comment, 4 operation spacing | 0 |
| WRITE_READ | 2 | 2 | 109 Symbol, 10 Comment, 10 operation spacing, 3 comparison spacing | 3 |

For each file the editor removes a sole explicit `<Allocation>Automatic</Allocation>` child from MemoryBitsMemoryAllocation and TimersMemoryAllocation, leaving the containers empty. All other allocation nodes, including Manual word extents, are equal. This is not blanket raw-allocation equality or permission to ignore unknown differences.

For active TM4 only, the WR save also omits Type=TON, IsRetentive=false and IsDynamicPreset=false. Address, Index4, Preset2 and Base=TenMilliSeconds remain exact; the actual reader still yields the same TON4, nominal 20 ms, base 10 ms, false-option object. These exact default-child omissions are recorded independently; no active option change or wider timer profile is inferred. Initial reviewer assumptions of raw allocation/timer-tree equality failed on those differences; the initial logs remain retained and the final comparison permits only these observed literal omissions.

## Reverse C++ and local evidence

Each actual saved file was decompiled with the public CLI, recompiled using that saved template and reimported. Configurations and timers remain equal. Audit lowering has conservative extra scratch/copy cost:

| Case | Original/saved rungs / IL | Audit derivative rungs / IL | Added rungs / IL |
|---|---|---|---|
| READ | 19 / 44 | 36 / 80 | 17 / 36 |
| WRITE | 31 / 66 | 50 / 105 | 19 / 39 |
| WRITE_READ | 72 / 161 | 120 / 260 | 48 / 99 |

The frozen original local validation contains **51 positions/10 starts** (14 READ, 14 WRITE, 23 WR; seven completions/three cancellations), passed in 7.392 seconds. Saved IR, audit C++ IR and audit SMBP replay those same literal callback and absent-transport cases; audit native SDK C++ passes its separate absent-transport expectations. These are repeated representations, not new distinct frames or unit tests, and the local callback engine does not prove native/vendor communication.

## Separate WR STOP-only simulator preparation

After the static stage, root launched the official local simulator with the exact editor-saved WR file (`55ce5db2…`, 353702 bytes). Two settled observations showed **No error / Online / Stop** and identical PC/controller applications: [observation 1](editor-evidence/modbus-bare-generated/write-read-stop-observation-1.png) and [observation 2](editor-evidence/modbus-bare-generated/write-read-stop-observation-2.png). They were captured 58.901 and 195.777 seconds after the launch request, 136.876 seconds apart. They are **two sampled observations with one unique PNG hash**, not two distinct image states, scans or continuous observation. Root and the independent reviewer viewed both exact files.

Root used the official Stop simulator control. A [fresh cleanup capture](editor-evidence/modbus-bare-generated/write-read-stop-cleanup.png) shows **No error / Not Connected** and no simulator panel. Root's cleanup record reports exact host PID34875 absent (`ps` exit1) and no TCP502 listener (`lsof` exit1); the reviewer read that record without issuing process or network commands. The saved file and its shared clone remain byte-exact. The six-entry STOP journal retains complete arguments and successful completion for commissioning, launch, both observations, official stop and fresh cleanup.

The commissioning view retained the no-protocol and inactive-application-protection notices and existing Untrusted DLL banner. No RUN, input change, communication command, external client or physical PLC was used in this stage. It demonstrates bounded preparation in STOP for this exact file; it does not demonstrate native Modbus execution, serial timing or physical interoperability, and **does not resolve the historical P0 simulator failure**. This stage is recorded separately from the three static save/reopen results.

Exact sources, rebuilds, normalizations, local replays and evidence hashes are in [MODBUS-BARE-ABORT-GENERATED-PROJECT-RESULTS.json](MODBUS-BARE-ABORT-GENERATED-PROJECT-RESULTS.json). No product/test/gate changes or full regression rerun are part of this report. Complete functional parity remains the goal.
