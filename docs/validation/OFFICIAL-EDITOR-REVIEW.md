# Official editor interoperability review

Review date: 2026-11-06. The reviewed changes against `77c55ae` preserve the full
[TM200CE40T parity goal](../PARITY.md). No actionable defect was found in the
inactive-profile validation, POU section handling, or communication level gate.
The saved memory candidate retains its actual instructions and hardware profile.
This review does not establish general editor or physical PLC compatibility.

## Code review and local tests

Reviewed `m200/config.py`, `m200/project.py`, `m200/levels.py`,
`m200/communication_xml.py`, the associated tests, authentic fixture/provenance,
and [editor metadata facts](../capabilities/EDITOR-INTEROP-FACTS.md).

```sh
python3 -m unittest tests.test_official_profile tests.test_communication_xml -v
```

Result: **28 tests passed locally**, including the exact editor-saved fixture
identity and normalized-profile readback regressions. The accepted inactive PTO
descriptors and default input filtering/latch values remain closed to active or unknown fields,
nested scalar content, duplicate singleton fields and duplicate axis identities.
Additional duplicate-field probes rejected PTO inputs, input filtering,
technical metadata and POU section duplicates. Unknown communication-level
tokens fail when the communication gate is required; observed internal ordinals
are mapped to displayed levels before applying the 10.1 instance limit.

The subsequent constant-false regression first failed on unwanted `%I0.0`
operands in memory-only and numeric-loop programs. Both tests passed after
switching initialization to a self-canceling private M contact, including dirty
scratch bits and multi-scan SDK/VM comparison. The focused toolchain,
allocation, copy-fusion and profile run passed **79 tests locally**. General
optimized resource counts can change, as measured for the audit derivative below.

The authentic fixture matches its provenance hash and size, contains only blank
password fields, and records a lab path. No local workflow directory was present.
This review did not inspect or change remote Actions settings.

## Exact memory candidate readback

The GUI operator reported that the generated candidate opened with **No error**
and displayed Ladder, then reached **Online / identical / RUN** in the official
local simulator. After changing the rung comment, the operator saved a separate
copy and reopened it with **No error**, targeting TM200CE40T. Those observations
belong to Machine Expert Basic 1.4 build 484 under the existing macOS Wine lab;
the separate GUI evidence record supplies the screenshots and session details.
The reviewer independently inspected the two local files below without operating
the GUI or simulator.

| Local artifact | Bytes | SHA-256 |
|---|---:|---|
| `output/editor-memory/program.smbp` | 84039 | `7128749796a0ca788898ed077f82ff4e8275a413ec2116fd0fb9f761c3653116` |
| `tests/fixtures/official_tm200ce40t_memory_editor_saved.smbp` (exact editor-saved copy) | 86197 | `4b6120f1151f840ae234e6f79135c51ec78e0fd3df21736c542894d52402a6bc` |

Both import as one rung: `LD %M0`, then `ST %M1`, with no timers, counters,
communication instances or application symbols. The complete hardware subtree,
including child order, is equal after ignoring XML indentation and attribute
order. Ladder elements and all remaining configuration retain their values.
`ManagementLevel` remains `FunctLevelMan21_0`.

The editor save changes project name/path, the requested rung comment, IL
spacing, software child order, and POU `SectionNumber` from `0` to `1`. It also
removes explicit `Allocation=Automatic` children for bits/timers and adds an
empty `MemoryWordsMemoryAllocation` element. These allocation observations apply
to this simple memory program; they do not resolve indexed-memory bound semantics.

## Reverse conversion and execution

`decompile_file` read the saved file and produced C++ plus a byte-exact SMBP
configuration sidecar in a temporary directory. The recovered C++ SHA-256 was
`e98ab2cb5f77c9cc7e0ef33f5575f33add8f7809a3aee6bb343f39cffe49034d`.
Recompiling it retains the memory-copy rung and adds two initialization rungs:
`LD %M501; ANDN %M501; ST %M501`, then `LD %M501; ST %M500`. The self-canceling
private contact establishes false regardless of its previous value, without a
physical input dependency. The derivative has three rungs, seven instructions
and two private bits. Compared with the previous compiler's synthetic-input
initialization, conservative allocation retains one extra copy rung, two extra
instructions and one extra private bit. No general count-preservation claim is
made. The original candidate remains unchanged; recompilation is not an
identical IL listing.

For eight scans with M0 values `01101001`, both the saved program and the
recompiled program produced M1 values `01101001` in the local VM. An Apple Clang
C++17 native harness executed the exact recovered C++ against the SDK and
observed the same M1 sequence. Reexport using the saved configuration sidecar
also passed local import. The original and editor-saved source files were
unchanged by these checks.

The local probes validate this memory-copy readback only. Simulator RUN does
not establish a forced-memory truth table, timer behavior, communication,
electrical I/O, firmware support or physical-controller behavior. Those remain
separate acceptance work; the reexported derivative was not opened in the
official editor during this review. No remote CI, PLC transfer, firmware update
or load actuation was performed.
