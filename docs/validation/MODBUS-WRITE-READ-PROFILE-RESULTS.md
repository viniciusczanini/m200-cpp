# Native WRITE_READ_VAR XML profile

2026-11-06. **544 tests passed in 187.332 seconds**, with zero skips and all 141 source/input pins unchanged. Ruff check/format passed for 100 Python files. The combined run adds ten WRITE_READ_VAR regression methods and eighteen standalone Register CONFIG codec methods to the published 516-test checkpoint. The Register codec remains a separate foundation: it is not integrated into the compiler or whole-project admission. Seventeen of its methods always run; its authentic-lab method ran here with both exact optional inputs pinned and skips when those ignored inputs are absent. Historical result reports remain unchanged.

[communication_xml.py](../../m200/communication_xml.py) now reads and writes the ten-field static MW WRITE_READ_VAR configuration. Complete project admission uses the **actual XML `FunctLevelMan21_0` (human 14.0), SL1 and existing serial-master configuration**. Program metadata cannot promote an unsupported template. Other levels and links remain explicitly unverified tool profiles; this closure does not establish a PLC limitation or invent a minimum functional level.

## Exact binding and graph

The [exact official save](../../tests/fixtures/official_tm200ce40t_modbus_write_read.smbp) is 89601 bytes, SHA256 `6a7edd820fcaee97cc4c1c783005f0a88a0409c98934e7b6964fbce1004bb52e`. Its [provenance](../../tests/fixtures/official_tm200ce40t_modbus_write_read.provenance.json) records the root-operated editor conversion, Ctrl+S on a writable disposable P: copy, preservation of the saved bytes, and No error after opening another project and freshly reopening the saved-byte clone. Native CRLF bytes are preserved by the existing `modbus*.smbp -text` rule. Hardware and typed block fields match the frozen input; IL whitespace was normalized by the official conversion.

The configuration is deliberately asymmetric:

| XML field | IR field | Captured value |
|---|---|---|
| Link | link | SerialLine1 / SL1 |
| RemoteDeviceId | id | 1 |
| Timeout | timeout_100ms | 100 |
| ObjType | obj_type | MW / 0 |
| FirstWriteObj | first_obj | 17 |
| WriteQuantity | quantity | 2 |
| IndexDataOut | index_data | 300 |
| FirstReadObj | first_read_obj | 41 |
| ReadQuantity | read_quantity | 3 |
| IndexDataIn | index_data_in | 400 |

The native body is `BLK; LD %M12; EXECUTE; END_BLK`. Its two entities are a NormalContact at row 0/column 0 with Left,Right and WriteReadVarBasic at row 0/column 1 with Left. Three narrow adapters in [project.py](../../m200/project.py) recognize that class, position and connection. Present WR graphics and graph export require a normal `LD` resource contact. Negated/constant contact graphs, connected Abort/status forms and the fifteen-line full-pin body remain rejected.

Existing **IL-only imports** retain the shared four/six-line parser, including Abort, LDN and constant predicates when graphics are absent and Ladder is unselected. This is a deliberate preserved boundary: those forms do not establish native graphic support, and their graph exports fail atomically. The full-pin fifteen-line body still fails import. See the [implementation plan](../capabilities/MODBUS-WRITE-READ-IMPLEMENTATION-PLAN.md) and [official binding observations](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md).

## Local verification

The exact-fixture test first failed because the WR class was not admitted. The complete new file was RED for the same missing binding, then all ten methods passed in 0.805 seconds. The focused communication/Register cohort passed 79 tests in 4.459 seconds before the full run.

Tests independently assert all ten wrappers and the exact two-entity graph, public C++ construction, reverse/recompile, both complete memory extents, write121/read125 maxima, local and remote endpoints, allocation rejection, actual level/link authority, unknown/duplicate/wrong-kind fields and unchanged templates/destinations after failure. Only obsolete WR-negative rows in three existing test files were replaced with real class/address mismatches and late-failure atomicity checks. Existing Abort and connected-output negatives remain. SDK, VM and protocol/runtime code are unchanged.

The FC23 oracle uses one request `17 0029 0003 0011 0002 04 1234 abcd` and response `17 06 8001 ffff 1234`. Local peer/VM checks cover write-before-read overlap, outbound snapshot while Busy and completion-time inbound commit. Malformed/exception responses cannot partially overwrite local input words. A failed response does not imply rollback of a write already applied at the peer.

Independent review found no outstanding findings after 50 actual level/link cases, 82 malformed XML/range cases, eighteen graph negatives, three complete two-buffer endpoints, three instance31 cases, ten metadata/atomic exports, a distinct non-fixture ten-field literal, and FC23/MBAP/local-peer/native/VM/reverse checks. The reviewer separately confirmed the IL-only boundary, the terminal 544-test log and all 141 pins without repeating the full suite.

## Generated product and remaining proof

A genuine public-CLI product is frozen under ignored `output/diagnostics/modbus-generated-write-read-candidates-2026-11-06/` and its shared P: mirror. Fourteen bundled files were hash-verified in both locations. The writable root-GUI candidate is `P:\modbus_generated_write_read.smbp`, SHA256 `24ac6d6efb7dc88d541969c8cf15985366571f0e59d17a24500ef783cf28ab1e`. It has two rungs/six raw instructions: M12 is snapshotted into M500 before WR0 executes. Its asymmetric configuration and template hardware are preserved; no XML was hand-edited. Official acceptance of that exact generated product was pending at preparation and must be recorded separately.

Exact source, fixture, log, independent-review and product hashes are in [MODBUS-WRITE-READ-PROFILE-RESULTS.json](MODBUS-WRITE-READ-PROFILE-RESULTS.json). Full-pin/Abort graphics, other profile contexts, dynamic properties and port/task interactions remain work toward full Modbus parity. No native compilation, official communication transaction, firmware, serial delivery or physical PLC proof is inferred from local tests or a clean save/reopen.
