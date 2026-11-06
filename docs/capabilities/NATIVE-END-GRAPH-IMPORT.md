# Native END-family graphical import

The three saved fixtures below establish concrete END-family IL-to-Ladder
bindings for TM200CE40T in EcoStruxure Machine Expert Basic 1.4 build484.
The root agent converted each diagnostic from IL to Ladder, observed No error
with validation enabled, and saved it. No native-END simulator RUN or physical
PLC result is claimed here.

## Exact preserved evidence

All three files are exact native CRLF saves. Their `.provenance.json` companions
record source paths, identity, editor context and observation scope.
`.gitattributes` disables text conversion for these fixtures.

| Fixture under tests/fixtures | Bytes | SHA256 |
|---|---:|---|
| `official_tm200ce40t_end.smbp` | 86370 | `11b4772aab31b5759ebf5a0315125cd4f1f0005dd0bad943c64de9af9eb2ea31` |
| `official_tm200ce40t_endc.smbp` | 86629 | `10d49746b54f4b8ef14dee3a51e8f08607aabebc5e142ade76f3643a1369451f` |
| `official_tm200ce40t_endcn.smbp` | 86644 | `5c76b1dabede9dc85c2c155f01c00d981262d804c150ccb7a7efbc07ba0496dc` |

| Actual IL | Predicate/power rail | Terminal |
|---|---|---|
| `END` alone | Line cells0–9 | End |
| `LD %M0; ENDC` | NormalContact M0 at column0, Line cells1–9 | End |
| `LD %M0; ENDCN` | NormalContact M0 at column0, Line cells1–9 | EndCn |

Every observed entity is on row0. Terminals are at column10, have empty
Descriptor and ChosenConnection=Left. Contacts and wire cells use
ChosenConnection=Left, Right. END and ENDC share the End enum, so the terminal
name alone cannot determine whether execution is unconditional. In particular,
`LD %M0; END` must not silently match the observed conditional contact graph.

## Closed consistency checks

The importer compares the graph against the actual IL, including predicate
polarity/address, terminal kind, empty terminal descriptor, complete wires,
column positions, row and connections. Duplicate, missing, disconnected,
unknown or contradictory elements remain errors. Setting IsLadderSelected=false
does not bypass validation when a nonempty graph is present. Existing IL-only
import remains available with an empty graph and Ladder unselected.

Conditional terminals can compose with the already supported series-contact
and comparison layouts. That composition is checked locally using the existing
component rules; it is not a claim that every such combination was separately
saved in the official editor. Inline unconditional END after a predicate,
nonseries predicates, literal-contact graphics and translated END rows remain
outside this observed import profile. Those are toolchain evidence boundaries,
not newly asserted controller limits.

The existing native END/ENDC/ENDCN VM and reverse semantics are unchanged.
The file exporter continues to normalize exits to a shared Jump destination.
This work does not switch output to newly generated native End/EndCn entities,
invent bindings from enum names, or add project metadata as a substitute for
actual instructions.

## Local validation

```sh
python3 -m unittest tests.test_native_end_graphs tests.test_scan_exit -v
```

The focused tests verify fixture hashes/newlines and typed hardware retention;
import all three authentic saves; reject forged opcode, polarity, descriptor,
geometry, wire, connection, field and attribute combinations; and preserve
IL-only handling. The earlier blanket-unknown-graph test is narrowed to its
still-malformed missing-wire examples.

Derived local programs surround an untouched authentic END rung with ordinary
input/output actions and word increments. Hand-set expected outputs and
MW200/MW201 values verify effects before exit, skipped later writes, retained
outputs and subsequent scans. The checks cover imported and normalized IL,
native reconstructed C++, recompiled C++, and exported/reloaded XML. A native
observer exposes the small word counters after the returning function, so word
effects are checked as well as Q outputs. These programs are local test
compositions, not additional official-editor accepted projects.

The three official-save fixtures provide import-binding evidence. Local model
agreement does not establish native runtime behavior, physical timing,
electrical I/O, arbitrary graphical layouts or complete library parity.

## Verification snapshot

The focused command passed 35 tests in8.580s: 17 new native-graph tests plus
18 existing scan-exit tests. The final combined graph-import and separate
10ms timer-XML changes passed the full 462-test regression in154.393s.
Ruff check passed and its format check reported91 files already formatted.
`git diff --check` passed. No remote CI was created or executed.

Logs and the selected source/test/fixture pin are preserved under
`output/editor-validation/native-end/import-validation/`. All109 pinned files
matched before and after the full regression. The pin file SHA256 is
`658e9cbfef4a623e47bca2788b26f0b6ed2ebb02a7154f5f6374637ad9ae4799`;
the complete regression log SHA256 is
`b7a2f159616b285c12aefe2f77f7a68588166a94855396edfe725a9bd881d143`.
