# CLI-generated WRITE_READ_VAR project in the official editor

2026-11-06. Root personally viewed **Programming No error** and confirmed all
ten WRITE_READ_VAR parameters in the genuine public-CLI product. Root completed
Ctrl+S, copied the saved bytes through the filesystem, opened the FIFO watch
project and freshly reopened the exact saved clone in Programming with **No
error**. The project targets TM200CE40T at actual `FunctLevelMan21_0`, with the
template's SL1 master configuration, in Machine Expert Basic 1.4 build 484 in the
local Mac Wine lab. There was no RUN or transaction.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Original CLI product | 91,107 | `24ac6d6efb7dc88d541969c8cf15985366571f0e59d17a24500ef783cf28ab1e` |
| Exact editor save | 93,388 | `e4111934d8cf42c7b4d514075e8ac9bf7032da7ce6242f87f0414671cfb926a2` |

Actual [save-stage view](editor-evidence/modbus-write-read-generated/save.png)
and [fresh reopen](editor-evidence/modbus-write-read-generated/reopen.png) are
copied byte for byte. Their source/copy hashes, root observations, robust local
readback and full frozen inventory are in the
[result manifest](MODBUS-WRITE-READ-GENERATED-PROJECT-RESULTS.json).

The frozen public command, not rerun for this report, was:

```sh
python3 -m m200 compile \
  output/diagnostics/modbus-generated-write-read-candidates-2026-11-06/sources/modbus_generated_write_read.cpp \
  --template output/diagnostics/modbus-generated-write-read-candidates-2026-11-06/inputs/official_tm200ce40t_modbus_write_read.smbp \
  -o output/diagnostics/modbus-generated-write-read-candidates-2026-11-06/builds/modbus_generated_write_read
```

The C++ source includes `<plc.hpp>` and uses:

```cpp
plc::WriteReadVar remote{0, plc::Link::Serial1, 1, 100,
    17, 2, 300, 41, 3, 400};
```

The block is `%WRITE_READ_VAR0`, with Link `SerialLine1`, RemoteDeviceId 1,
Timeout 100 and ObjType `MW`. The asymmetric fields remain distinct:

| Side | First object | Quantity | Local MW start |
|---|---:|---:|---:|
| Write | 17 | 2 | 300 |
| Read | 41 | 3 | 400 |

The call is `remote.update(plc::read_m(12), false)`. Two rungs/six IL lines
snapshot `%M12` into `%M500`, then execute the four-line WR block. There are no
I/Q operands, status outputs or connected Abort/status pins. The graph contains
eleven entities in the snapshot rung and two in the Execute-only WR rung.

Normalized/typed IL, FB parameters and exact wrappers, template hardware,
effective allocations and graph geometry are preserved through the editor save.
The closed whole-XML comparison identifies six real field changes: project
Name/FullName reflect the working filename/path, two Automatic allocation
children are omitted, and two existing empty `%M500` graph Symbol texts become
`TEMPORARY_500`. All remaining typed XML matches after IL spacing and named-field
order normalization; rung/instruction sequences remain ordered.

All fourteen entries listed in the frozen generation `SHA256SUMS` were verified,
including the source, exact template/provenance, program/IL/JSON, reverse C++,
reports and CLI log. No hand-edited XML was used. Earlier generation and
[implementation-checkpoint](MODBUS-WRITE-READ-PROFILE-RESULTS.md) pending fields
remain historical; this separate record supplies the later editor stage.

This establishes offline save/fresh-reopen acceptance for the exact generated
artifact. It does not establish native compilation, simulator behavior, an FC23
request/response, serial/network delivery, physical PLC/firmware behavior or
full-pin/Abort graph support. Execute was not asserted or forced. No full suite,
CI or GitHub Actions was run for this GUI stage; the report author performed
only read-only file verification and evidence copying.
