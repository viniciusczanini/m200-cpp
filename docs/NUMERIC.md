# Numeric operations and shared memory

Use explicit types/functions from [plc.hpp](../sdk/plc.hpp) and
[scalar_numeric.hpp](../sdk/scalar_numeric.hpp). Clang checks C++ types; the
frontend also enforces the supported grammar, literal identities, resource
bounds and native instruction shapes. Ordinary C++ promotions/arithmetic are
restricted.

## Operations and errors

| Purpose | API | Behavior |
|---|---|---|
| Typed arithmetic | `add_i16`, `sub_i16`, `mul_i16`, `div_i16`, `rem_i16`, `sqrt_i16`, corresponding i32 functions | Explicit signed widths; observable flags prevent unsafe constant folding |
| Increment/decrement | `inc_i16`, `dec_i16`, `inc_i32`, `dec_i32`; `inc_word`, `dec_word`, `inc_dword`, `dec_dword` | Destination operations use native INC/DEC |
| Recoverable destination | `div_word`, `rem_word`, `sqrt_word`; corresponding `*_dword` forms | Destination index first, then operands; an invalid integer result sets S18 and marks its bits unknown |
| Storage copy | `copy_word(dest,source)`, `copy_dword`, `copy_real` | Copies storage and unknown masks, snapshotting overlapping ranges |
| Flags | `system(17)`, `system(18)`, `clear_shift_carry`, `clear_arithmetic_error` | Last shifted-out carry and sticky arithmetic error have separate ownership |
| Floating status | `floating_status`, `clear_floating_status`; system word17 | One shared SW17 provider; clearing this status and clearing S18 are separate operations |

`WordMemory{count}` declares 1..8000 ordinary cells for indexed access. MW uses
one cell; MD/MF use two consecutive cells in the same underlying storage.
Bit access aliases these cells and their known/unknown masks. Static bounds,
resource overlaps and private allocation are checked during compilation.

After an invalid destination operation, test S18 and overwrite the result with
an independent known value before comparing it. Clearing the error flag alone
does not repair unknown data. Partial word/bit writes repair only their region.
Use explicit copy operations to preserve unknown masks before independent repair.

The VM can carry unknown values through primitive expressions; ordinary C++
SDK primitives cannot represent poison. Reading an incompletely repaired word
into a primitive can trap earlier in the SDK. This remains a visible gap,
rather than a usable zero. Destination/copy APIs provide the supported route.

S18 remains set until explicitly cleared; valid operations and later scans do
not clear it. S17 changes to the last original bit shifted out by SHL/SHR/ROL/ROR;
unrelated operations preserve it. Signed overflow retains low destination bits
under the documented local modular policy. The manual's word-add example does
not independently qualify every firmware overflow bit pattern. S/ST/STN writes
to clear-only flags are rejected; R is preserved through reverse and projects.

## Constants

All constant forms share **512 native 16-bit cells**, not separate KW/KD/KF
storage images:

- `ConstantMemory{count}` declares 1..512 cells for indexed access.
- `ConstantWord{index,i16}` uses one cell.
- `ConstantDword{index,i32}` and `ConstantReal{index,f32}` use two cells.
- Overlapping initializers must agree bit for bit. Nonfinite real initializers
  and out-of-range or lossy typed initializers are rejected.
- `read_constant_word`, `read_constant_dword`, `read_constant_real` use literal
  identities. Their `*_indexed(base,index_word)` variants use the signed value
  of an ordinary MW as the cell offset.
- Indexed access requires both `WordMemory` and `ConstantMemory`. An offset
  outside the declared range sets S20 and uses the base identity; invalid static
  base/index-word identities are compilation errors.

Constants survive JSON, native configuration and actual-program reverse.
They do not need a scan-by-scan initialization loop. Boolean KW bit reads use
this same image.

## Floating and conversion boundaries

The local binary32 model retains infinities/NaNs and distinguishes SW17
invalid/NaN (1), division-by-zero (4) and overflow/infinity (8) statuses.
Arithmetic errors set S18; raw copies preserve payload bits and existing flags.
Finite tests use independent values/tolerances. These local rules are not full
firmware or physical timing qualification.

Valid real-to-integer conversion retains the established ties-to-even policy.
Out-of-range/nonfinite conversion sets S18 and refuses its undefined local
result before writing the destination, leaving S17/SW17 unchanged. The SDK sets
the flag before trapping, but invalid trap-state observation remains pending.
Invalid BCD recovery and broader conversion/ASCII work are deferred. Unsupported
opcodes, type/arity errors and invalid literal widths remain errors.

Primary references: Generic Functions EIO0000003289.04 pp28,54–57,68–72 and
M100/M200 Programming Guide EIO0000002019.06 pp322–323. Exact candidate tests,
SDK gaps and native gates are in the
[integration record](validation/NATAL-INTEGRATION-PROGRESS.md).
