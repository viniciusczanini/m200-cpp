# Local editor interoperability facts

The JSON alongside this note records identifiers and enum/resource values read
from the user's installed Machine Expert Basic 1.4 build484 assemblies. It
includes the exact assembly hashes. The existing binary-refinery tools performed
metadata-only inspection; no vendor binary, decompiled source, method body or
complete resource dump is published here. Original binaries were not modified.

`ManagementLevel` is an internal ordinal. Its suffix is not the displayed
functional level: `FunctLevelMan11_0` means6.0, `FunctLevelMan14_0` means10.0,
and `FunctLevelMan15_0` means10.1. The complete21-row table is source-backed in
the JSON. The communication instance gate must therefore permit IDs16..31 from
human level10.1 (`FunctLevelMan15_0`), not from a lexical comparison against a
fictional `FunctLevelMan10_1`. Unknown tokens remain unverified and are refused
where the gate is required. The map does not prove controller firmware supports
every represented level or optional feature.

The timer enum contains `TenMilliSeconds=1`. This supplies a concrete candidate
for the10ms XML value; it does not yet prove the serialization binding or timer
execution/timing. An editor-created/saved Timer project and an acceptance test
must establish that binding before lifting the exporter gate.

The Ladder enum contains `End=37`, `EndCn=38`, `Stop=13` and `Return=12`. These
are identifiers only: instruction binding, layout and a complete END-family
round trip still need editor evidence. Do not infer the graphical representation
of END/ENDC merely from similar names.

The authentic inactive TM200CE40T template has first POU `SectionNumber=0`.
The parser also preserves the earlier observed contiguous1-based variant, and
the writer retains the chosen template's base. Default4ms filtering/no latch,
two inactive pulse-output descriptors and capability scalars are preserved;
unknown/active modes are still rejected. This is independent of physical PLC
validation, which remains pending.

## Diagnostic watch values

The installed Entities `ValueRepresentationTypeEnum` identifies `Decimal=0` for numeric animation-table values and `BoolNumeric=6` for discrete values. MW values use signed Int16; MD values use signed Int32. The sequence diagnostic copy adds only explicit Decimal watch rows; its executable IL and hardware configuration are compared with the original before opening. Enum identifiers alone do not establish runtime acceptance; exact GUI observations are recorded separately.
