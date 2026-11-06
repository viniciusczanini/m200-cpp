# Official-editor Modbus binding observations

Date: 2026-11-06. Root personally observed **No error**, save and a fresh reopen
after another project for seven basic binding projects and three full-pin
conversions in Machine Expert Basic 1.4 build 484. All target TM200CE40T at exact
`FunctLevelMan21_0`, using an explicitly configured SL1 master. These are local
editor binding/persistence observations while not connected to a controller.

Saved-byte readback independently preserves each candidate's normalized IL,
hardware and typed function-block parameters. This comparison is against each
supplied candidate; it does not mean SL1 master configuration was added by the
editor or was present in the original slave-role memory baseline. All hashes,
parameters, graph entities, source-record identities and PNG-copy checks are in
the [observation manifest](MODBUS-OFFICIAL-BINDING-OBSERVATIONS.json).

## Basic bindings

These projects have Execute-only graphs. Function codes below describe the
documented object mapping; no transaction was performed.

| Case | Binding | Quantity and local MW buffer | Saved graph entities | Fresh reopen |
|---|---|---|---:|---|
| 01 | READ MW / WRITE MW, FC3/16 | Read 2 at MW200; write 3 at MW240 | 3 + 4 | [Capture](editor-evidence/modbus-bindings/01_reopen.png) |
| 02 | READ I, FC2 | 17 bits at MW200..201 | 3 | [Capture](editor-evidence/modbus-bindings/02_reopen.png) |
| 03 | READ Q, FC1 | 17 bits at MW220..221 | 3 | [Capture](editor-evidence/modbus-bindings/03_reopen.png) |
| 04 | WRITE Q, FC15 | 17 bits at MW240..241 | 4 | [Capture](editor-evidence/modbus-bindings/04_reopen.png) |
| 05 | WRITE SINGLE_COIL, FC5 | 1 object, source MW260 | 4 | [Capture](editor-evidence/modbus-bindings/05_reopen.png) |
| 06 | WRITE SINGLE_REG, FC6 | 1 object, source MW280 | 4 | [Capture](editor-evidence/modbus-bindings/06_reopen.png) |
| 07 | WRITE_READ MW, FC23 | Write 2 at MW300; read 3 at MW400 | 2 | [Capture](editor-evidence/modbus-bindings/07_reopen.png) |

Case 07 began with IL and no graph. The actual editor save selected Ladder and
created a `%M12` contact at row 0/column 0 plus `WriteReadVarBasic` at row 0/column
1, with block `ChosenConnection=Left`. Its final saved identity is
`6a7edd820fcaee97cc4c1c783005f0a88a0409c98934e7b6964fbce1004bb52e`
(89,601 bytes). This is authentic Execute-only WR binding evidence, separate
from full-pin support or product implementation.

## Full-pin conversions

Root converted the actual IL to Ladder, saved it, opened a different project and
freshly reopened the saved result. Each file has one 15-instruction rung and
**27 native graph entities**: two contacts, one block, twenty lines and four
coils. Parameters and hardware remain semantically equal to their input.

| Block / object | Saved bytes | SHA-256 prefix | Conversion view | Fresh reopen |
|---|---:|---|---|---|
| READ_VAR / I | 97,080 | `8154e130ce73b6a1` | [Diagram](editor-evidence/modbus-bindings/modbus_full_pin_read_editor_saved.png) | [Capture](editor-evidence/modbus-bindings/modbus_full_pin_read_reopen.png) |
| WRITE_VAR / Q | 97,089 | `ae6ffad294a36e79` | [Diagram](editor-evidence/modbus-bindings/modbus_full_pin_write_editor_saved.png) | [Capture](editor-evidence/modbus-bindings/modbus_full_pin_write_reopen.png) |
| WRITE_READ_VAR / MW | 98,503 | `9e7a3359a99c433b` | [Diagram](editor-evidence/modbus-bindings/modbus_full_pin_write_read_editor_saved.png) | [Capture](editor-evidence/modbus-bindings/modbus_full_pin_write_read_reopen.png) |

All three saved graphs establish these exact row rules:

| Element | Row | Column | ChosenConnection |
|---|---:|---:|---|
| Execute contact `%M10` | 0 | 0 | Left, Right |
| Abort contact `%M13` | 1 | 0 | Left, Right |
| Function block | 0 | 1 | Left, Right |
| DONE coil `%M14` | 0 | 10 | Left |
| BUSY coil `%M15` | 1 | 10 | Left |
| ABORTED coil `%M16` | 2 | 10 | Left |
| ERROR coil `%M17` | 3 | 10 | Left |
| Twenty line entities | 0..3 | 5..9 | Left, Right |

These coordinates come from saved native `LadderEntity` fields, not enum flag
values or a conceptual pin drawing. IL order is Execute, Abort, OUT_BLK, then
DONE/BUSY/ABORTED/ERROR loads stored to the corresponding coils.

## Persistence and excluded early copy

The readbacks record structural software-field differences without changes to
normalized executable IL or typed FB/hardware semantics. Cases 01–06 each have
four allocation-default serialization differences. Case 07 has twenty recorded
field differences: four allocation defaults, two IL-spacing changes, one view
selection and thirteen graph fields. Each full-pin save has 155 recorded field
differences: eleven IL-spacing changes, one view selection and 143 graph fields.

Conversion/parameter captures illustrate the graph or values; they can show an
unsaved-title asterisk. Final saved-file hashes/readback and the separate clean
fresh-reopen captures establish persistence. Case 01 has only its reopen capture
in the retained readback. Nineteen PNGs were copied byte for byte; their source
and destination identities are listed in the manifest.

The 86,046-byte `modbus_full_pin_write_before_save_completed.smbp`, SHA-256
`a6bbb7b609b24b5a9b9b3b0ccdd13c94812d8bc291f2140543d8110e4e4f575e`,
contains zero graph entities. Its lab record is preserved and **excluded** from
final official graph/persistence evidence. Only the later 97,089-byte WRITE file
identified above is the completed saved result.

## Product scope and limits

The current product supports the established READ_VAR MW/I/Q/IW and WRITE_VAR
MW/Q XML subset. Single-write XML, WRITE_READ_VAR XML and Abort/connected-status
graph implementation remain pending despite this new binding evidence. This
report changes no product gates, code, tests or fixtures.

No program exchange, native compile, official Modbus transaction, simulator
communication, physical-controller compatibility or minimum-level support is
proved here. Only the exact Man21 cases were observed. Root's ongoing GUI checks
of actual CLI-generated product exports are separate and are not included in
this record.
