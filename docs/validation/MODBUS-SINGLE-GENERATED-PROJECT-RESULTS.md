# CLI-generated FC5/FC6 projects in the official editor

2026-11-06. Root personally viewed **Programming No error** and the actual
parameters of both public-CLI products, completed Ctrl+S saves, and freshly
reopened each exact saved-byte clone after opening a different project. Both
target TM200CE40T at actual `FunctLevelMan21_0`, with the existing SL1 master
configuration, in Machine Expert Basic 1.4 build 484 in the local Mac Wine lab.
Neither program was run or given an Execute request.

This records the generated-product GUI stage separately from the
[single-write implementation checkpoint](MODBUS-SINGLE-PROFILE-RESULTS.md) and
[earlier native binding observations](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md).
Each original product and editor save contains **two rungs / six IL lines**.
Normalized IL, template hardware, typed FB parameters/wrappers and graph geometry
are preserved.

| Product | Original SHA-256 prefix | Editor-save prefix | Saved bytes | Save-stage / fresh reopen |
|---|---|---|---:|---|
| Single coil / FC5 | `6d9e10277a9b8311` | `a07db925c8b84ccc` | 92,537 | [View](editor-evidence/modbus-single-generated/single_coil-save.png) / [Reopen](editor-evidence/modbus-single-generated/single_coil-reopen.png) |
| Single register / FC6 | `4cb9b48c207d2cee` | `3ccfb61c5351f7d9` | 92,532 | [View](editor-evidence/modbus-single-generated/single_reg-save.png) / [Reopen](editor-evidence/modbus-single-generated/single_reg-reopen.png) |

The editor's six reported software-field changes per product comprise four
allocation-default fields and two graph Symbol fields (`TEMPORARY_500`). The
word allocations remain 261 and 281 respectively. Each graph retains eleven
entities in the Execute-snapshot rung and four in the existing WRITE_VAR rung.
No executable wiring changed. Four actual PNGs were copied byte for byte;
source/copy hashes and complete artifact identities are in the
[result manifest](MODBUS-SINGLE-GENERATED-PROJECT-RESULTS.json).

## Exact public CLI inputs

These commands describe the frozen generation, not a rebuild for this report.
The JSON preserves the original argv, including the Xcode Python executable and
working directory.

```sh
python3 -m m200 compile \
  output/diagnostics/modbus-generated-single-candidates-2026-11-06/sources/modbus_generated_single_coil.cpp \
  --template output/diagnostics/modbus-generated-single-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_single_coil.smbp \
  -o output/diagnostics/modbus-generated-single-candidates-2026-11-06/builds/modbus_generated_single_coil

python3 -m m200 compile \
  output/diagnostics/modbus-generated-single-candidates-2026-11-06/sources/modbus_generated_single_reg.cpp \
  --template output/diagnostics/modbus-generated-single-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_single_reg.smbp \
  -o output/diagnostics/modbus-generated-single-candidates-2026-11-06/builds/modbus_generated_single_reg
```

The two separate sources include `<plc.hpp>` and use these exact constructors:

```cpp
// Separate FC5 source:
plc::WriteVar remote{0, plc::Link::Serial1, 1, 100,
    plc::Object::SingleCoil, 107, 1, 260};

// Separate FC6 source:
plc::WriteVar remote{0, plc::Link::Serial1, 1, 100,
    plc::Object::SingleRegister, 131, 1, 280};
```

FC5 reads Execute from `%M11`, uses `%MW260` and remote coil 107. FC6 reads
Execute from `%M12`, uses `%MW280` and remote holding register 131. Both pass
`false` for Abort and serialize Quantity 1. The compiler snapshots the Execute
memory bit to `%M500` before the block call, producing six IL instructions:
`LD %M11` (or `%M12`), `ST %M500`, `BLK %WRITE_VAR0`, `LD %M500`, `EXECUTE`,
`END_BLK`. The source does not write the Execute bit. There are no I/Q operands,
status outputs or connected native status/Abort pins.

The generated `program.smbp` bytes were copied unchanged to descriptive filenames
and then writable P: working files. Root saved those working files through the
official editor, copied completed save bytes through the filesystem, opened a
different project and freshly reopened the saved clones. No hand-edited XML was
used in generation.

## Frozen provenance and limits

All **25** entries in the frozen bundle's `SHA256SUMS` were verified, including
sources, exact templates/provenance, CLI logs, program JSON/IL, reverse C++,
reports and the preparation script/manifest. Their identities and the generation
compiler source hashes are retained in the result JSON. The preparation manifest
and historical implementation report retain their earlier GUI-pending fields;
this separate record supplies the completed later stage without rewriting them.

This is offline editor acceptance/save/reopen evidence for two exact generated
products. Structural readback is not runtime communication. No program RUN,
simulator session, asserted/forced Execute, transaction, serial/network delivery,
external TCP/port 502, hardware operation, CI or GitHub Actions occurred in this
stage. The report author only read existing files and copied evidence.
Physical PLC/firmware behavior, other links/functional levels, editor acceptance
of ignored Quantity values other than 1, and connected native Abort/status graphs
remain outside this result. No full suite was rerun for this document, and the
historical 516-test checkpoint is unchanged.
