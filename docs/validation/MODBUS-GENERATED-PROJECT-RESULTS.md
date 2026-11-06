# CLI-generated Modbus projects in the official editor

Date: 2026-11-06. Root personally viewed **No error**, saved with Ctrl+S and
freshly reopened each of the three actual public-CLI products after a different
project. All are TM200CE40T at `FunctLevelMan21_0`, viewed offline in Machine
Expert Basic 1.4 build 484. This is a generated-artifact stage, separate from
[binding discovery](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md).

Each original product and its editor save contains **18 rungs / 38 IL lines**.
Normalized IL, typed FB configuration, template hardware and diagram geometry
are preserved. The editor's thirty reported software-field changes per case
are four allocation-default fields, twenty-two graph Symbol fields and four
Comment fields. Symbols/comments changed; executable wiring did not.

| Product | Original SHA-256 prefix | Editor-save prefix | Saved bytes | Save-stage / fresh reopen |
|---|---|---|---:|---|
| READ I / FC2 | `59e938fc98c8cc41` | `11e7a6e83fbde01c` | 151,441 | [View](editor-evidence/modbus-generated/read_i-save.png) / [Reopen](editor-evidence/modbus-generated/read_i-reopen.png) |
| READ Q / FC1 | `887cb7353accaf8b` | `cca857167dd967b7` | 151,441 | [View](editor-evidence/modbus-generated/read_q-save.png) / [Reopen](editor-evidence/modbus-generated/read_q-reopen.png) |
| WRITE Q / FC15 | `b69b6b4f937127ca` | `68537c1b488ebfd1` | 151,722 | [View](editor-evidence/modbus-generated/write_q-save.png) / [Reopen](editor-evidence/modbus-generated/write_q-reopen.png) |

Root used writable P: byte clones of the generated files, copied completed
editor saves through the filesystem, opened a different project and then freshly
reopened the saved clones. The original CLI products remain unchanged. Six
actual PNGs were copied byte for byte; full identities and source/copy hashes
are in the [result manifest](MODBUS-GENERATED-PROJECT-RESULTS.json).

## Recorded CLI and C++ inputs

The public command was `python3 -m m200 compile SOURCE --template TEMPLATE -o
OUTPUT`. These are the recorded commands in repository-relative spelling; they
were not re-executed for this report. The JSON retains the exact original argv,
including its Xcode Python executable and working directory.

```sh
python3 -m m200 compile \
  output/diagnostics/modbus-generated-bit-candidates-2026-11-06/sources/modbus_generated_read_i.cpp \
  --template output/diagnostics/modbus-generated-bit-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_read_i.smbp \
  -o output/diagnostics/modbus-generated-bit-candidates-2026-11-06/builds/modbus_generated_read_i

python3 -m m200 compile \
  output/diagnostics/modbus-generated-bit-candidates-2026-11-06/sources/modbus_generated_read_q.cpp \
  --template output/diagnostics/modbus-generated-bit-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_read_q.smbp \
  -o output/diagnostics/modbus-generated-bit-candidates-2026-11-06/builds/modbus_generated_read_q

python3 -m m200 compile \
  output/diagnostics/modbus-generated-bit-candidates-2026-11-06/sources/modbus_generated_write_q.cpp \
  --template output/diagnostics/modbus-generated-bit-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_write_q.smbp \
  -o output/diagnostics/modbus-generated-bit-candidates-2026-11-06/builds/modbus_generated_write_q
```

Each separate source includes `<plc.hpp>` and uses the exact SDK constructor
below. The two-word buffers hold seventeen packed bits.

```cpp
// Separate READ I source:
plc::ReadVar remote{0, plc::Link::Serial1, 1, 100,
    plc::Object::DiscreteInputs, 17, 17, 200};

// Separate READ Q source:
plc::ReadVar remote{0, plc::Link::Serial1, 1, 100,
    plc::Object::Coils, 41, 17, 220};

// Separate WRITE Q source:
plc::WriteVar remote{0, plc::Link::Serial1, 1, 100,
    plc::Object::Coils, 73, 17, 240};
```

| Source | Execute memory | DONE / BUSY / ABORTED / ERROR outputs |
|---|---|---|
| READ I | `%M10` | `%Q0.0` / `%Q0.1` / `%Q0.2` / `%Q0.3` |
| READ Q | `%M11` | `%Q0.4` / `%Q0.5` / `%Q0.6` / `%Q0.7` |
| WRITE Q | `%M12` | `%Q0.8` / `%Q0.9` / `%Q0.10` / `%Q0.11` |

The call is `remote.update(plc::read_m(n), false)`. DONE is taken from that call;
the other outputs use `busy()`, `aborted()` and `error()`. Generated IL reads
the status properties in separate rungs and copies them to the outputs. It does
not use the separate native full-pin/Abort graph form. The inspection procedure
did not assert or force Execute, start simulation or trigger an exchange.

## Frozen provenance and limits

The generation bundle retains its C++ sources, exact templates, CLI logs,
program/IL/JSON/source-map reports and reverse C++. All 36 entries in its
`SHA256SUMS` were verified. The public result records the immutable manifest,
checksum-file and per-artifact hashes, including compiler source hashes at
generation. The preparation manifest's earlier GUI fields remain `pending`;
this later observation record supplies the completed GUI stage without
rewriting that historical preparation snapshot.

Hardware is retained from the exact SL1 master templates. The result establishes
offline editor acceptance/save/reopen for these exact generated products, not
runtime communication. Local readback is not native simulation or PLC proof.
There was no program exchange, forcing, native simulator communication, serial
transaction, hardware operation, external TCP/port 502, CI or GitHub Actions.
Other object/kind combinations, connected-status/Abort graphs, physical I/O,
controller firmware and minimum functional levels remain outside this result.
Historical regression reports were not rewritten or rerun for this document.
