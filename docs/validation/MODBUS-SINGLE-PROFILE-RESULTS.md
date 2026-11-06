# Native Modbus single-write XML profiles

2026-11-06. **516 tests passed in 200.776 seconds**, with all 134 source/input pins unchanged across the full run. Ruff check/format passed for 97 Python files. This adds ten regression methods to the published 506-test checkpoint; historical result reports are unchanged.

[communication_xml.py](../../m200/communication_xml.py) now recognizes WRITE_VAR `SINGLE_COIL=4` / FC5 and `SINGLE_REG=5` / FC6. Full project admission remains closed to **actual `FunctLevelMan21_0` (human14.0), SL1 and the established serial-master configuration**. Actual template/XML fields are authoritative over Program metadata. Below human5.0, the diagnostic states the documented minimum; other known levels/links are explicitly unverified tool profiles. Those refusals do not classify the controller feature as impossible.

The [Generic Functions Library](https://www.se.com/ww/en/download/document/EIO0000003289/) p.180 documents the minimum5.0, a local MW source and ignored Quantity for these single writes. Existing ModbusConfig bounds and one-word/one-remote-address semantics are retained, including preservation of unused Quantity values. This does not claim that every such Quantity has been accepted by the official editor; the exact captured cases use1.

## Authentic binding evidence

The exact root-operated editor saves and fresh reopens are preserved as byte-identical CRLF fixtures. Both retain the frozen candidate's raw IL, hardware and typed function-block fields. They use the already established Execute-only WriteVarBasic graph: block row0/column3, Left connection; memory contact at column1. No new graph implementation was added.

| Exact saved fixture | Bytes | SHA256 |
|---|---:|---|
| [Single coil](../../tests/fixtures/official_tm200ce40t_modbus_single_coil.smbp) | 88741 | `4b72a0380555290934a4eea0492e3f9c0491b08f0741bd9f7ded49666845ef8f` |
| [Single register](../../tests/fixtures/official_tm200ce40t_modbus_single_reg.smbp) | 88736 | `d24a3b572bc565d9d1cb9d4111ffd231d28422384e7b08bd977c85198b995ed8` |

Adjacent provenance files pin the original candidates, exact saved bytes, actual Ctrl+S/clone/fresh-reopen procedure, parameter images and fresh-reopen images. Parameter images illustrate fields; saved-byte identity and the separate fresh reopen establish persistence. The existing `modbus*.smbp -text` rule preserves native line endings. See [official binding observations](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.md) for the operator evidence and its limits.

## Verification and closed boundaries

The initial exact-fixture import test was RED for both missing enum strings. All ten new methods then passed in1.072s; the 51-test focused communication cohort passed in3.554s before the full run. Tests cover public constructors, reverse/import/export, the last local word and remote address, ignored Quantity0/17/65535, literal FC5 bit0/FC6 values, local peer behavior, malformed wrappers/fields/indexes, invalid READ direction, actual level/link authority and unchanged files on rejection.

Independent review found no outstanding findings after 100 actual level/link cases, eight ignored-Quantity endpoints, 24 malformed/bounds/direction cases, 16 metadata/atomic export cases, four literal PDU checks, two local MemoryTransport cases and two native/VM/reverse cases without a transport. Those last cases confirm that no success is fabricated when transport is absent. The reviewer also verified the 516-test log and all 134 pins without repeating the full suite.

Only obsolete SINGLE negative rows were removed from the two existing communication test files with explicit coordination. Genuine wrong-direction/unknown-field checks and WRITE_READ_VAR, Abort and connected-output graph refusals remain. Project.py, SDK, VM and protocol/runtime code were not changed. Typed codecs recognize the values; the full project APIs apply the actual profile gate.

## Exact generated products and remaining proof

Two public-CLI products are frozen with source, program JSON/IL, reverse C++, template, report and hashes under ignored `output/diagnostics/modbus-generated-single-candidates-2026-11-06/`, mirrored into the P: shared bundle. Each has two rungs/six raw instructions: a memory Execute snapshot to M500 followed by the existing WRITE_VAR0 block, with no I/Q operands or connected status pins. Original CLI bytes were copied to descriptive filenames without XML edits.

| Prepared product | Original SHA256 |
|---|---|
| `modbus_generated_single_coil.smbp` | `6d9e10277a9b8311afd6ac61d7e309eba1ba35d1b535c53c75aa9434645002b6` |
| `modbus_generated_single_reg.smbp` | `4cb9b48c207d2ceef3d5b1d295cbfcbc9b3e9355c2926523e1a2ad7da638d9c5` |

Their official GUI status was pending at preparation and must be established separately for those exact products. Exact source/log/review/product hashes and the pinned code snapshot are in [MODBUS-SINGLE-PROFILE-RESULTS.json](MODBUS-SINGLE-PROFILE-RESULTS.json).

WRITE_READ_VAR, connected Abort/status graphs, other functional levels and other links remain tool gaps. No native compilation, official Modbus transaction, serial delivery, firmware or physical PLC proof is inferred from saving/opening a binding. Full Modbus parity remains active work.
