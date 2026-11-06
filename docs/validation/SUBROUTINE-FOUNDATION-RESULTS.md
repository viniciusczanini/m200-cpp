# Standalone subroutine wrapper and call-graph foundation

**628 tests passed in 217.783 seconds, with zero skips and all 172 frozen input hashes unchanged.** This adds 26 required, portable methods to the earlier 602-test checkpoint. The focused methods passed in 0.099 seconds. Independent review found no actionable defects; its 1,257 main checkpoints and 1,559 supplementary checks are separate local probes, not extra unittest or native-execution counts.

The new [wrapper codec](../../m200/subroutine_xml.py) and [call-graph codec](../../m200/subroutine_graph.py) are isolated components. **They do not enable subroutines in C++, Program/JSON, SDK, VM, reverse or whole-project import/export.** Active whole-project Subroutines remains explicitly rejected. A separately developed ignored prototype is excluded from this source snapshot and these test counts.

## Exact portable evidence

Both handbuilt native diagnostics were converted to Ladder in the official editor, including every master and callee rung, saved with Ctrl+S, filesystem-cloned and freshly reopened after another project. Root and the codec author viewed Programming **No error** at save and fresh reopen. These are genuine saved bindings rather than compiler-generated SR products.

| Fixture | Bytes | SHA256 |
|---|---:|---|
| [SR0, implicit-return leaf](../../tests/fixtures/official_tm200ce40t_subroutine_sr0.smbp) | 137327 | `49438bcbed59cde889547869d8c033f377dfb7e60153136a57cb48e135b0e21a` |
| [SR63, ENDC and END leaf](../../tests/fixtures/official_tm200ce40t_subroutine_sr63.smbp) | 157411 | `ff05369c686e8bc1887612afdbfcfd57d24e0e4e1e51d8d2b2b443824a2fa652` |

Adjacent provenance records the original handbuilt inputs, exact saved bytes, conversion/save/clone/reopen procedure and four [static capture](editor-evidence/subroutine-native/sr0-save.png) hashes. All three password fields in each fixture are blank; native CRLF is preserved with a narrow `official_tm200ce40t_subroutine_*.smbp -text whitespace=cr-at-eol` rule. All 26 new methods require public fixtures and have no lab-file fallback or optional skip. The older Register-configuration test's optional pinned-lab method remains unchanged; it was present in this local zero-skip run.

Typed readback verifies all 37 SR0 and 49 SR63 IL lines, hardware, all 13 allocations, task settings, watch rows and comments. Outside the separately measured added graphs and Ladder-selection changes, only root Name/FullName changed. Number 0 and Number 63 both retain SectionNumber 2, with distinct POU names. Section identity is independent of SR number.

## Closed component contract

The wrapper accepts only Name, SectionNumber, Rungs and Number. IDs use canonical decimal 0..63, with at most 64 entries. SectionNumber is preserved independently as a canonical nonnegative Int32 identity. Unknown or duplicate fields, ambiguous duplicate IDs/names/sections, active task/Grafcet/linkage additions, invalid XML characters, attributes, nesting and significant text/tails fail explicitly. Reader and writer clone rung XML; a complete staged replacement precedes mutation of the owned collection.

Rung bodies have closed XML surfaces and known opcode syntax. **The wrapper does not validate callee operand addresses/resources or complete IL/graph semantics.** Those checks remain mandatory before future execution admission. The independent reviewer deliberately checked this structural boundary and the unchanged whole-project refusal; a successfully decoded wrapper must not be presented as an executable validated program.

The observed call is exactly:

```text
LD %I0.0
SRn
```

Its eleven-entity graph is one NormalContact at row 0/column 0 Left/Right, nine Lines at columns 1..9 Left/Right, and a Jump at column 10 Left with descriptor `SRn`. The descriptor has no percent sign and is distinct from `%Ln` jumps. The identity domain 0..63 follows primary documentation; exact target saves prove endpoints 0/63. M contacts, other inputs, negation, labels, arbitrary expressions and invented CAL/RET forms are not admitted. Local parameterization does not claim that 64 native projects were opened.

The graph writer fills only an absent/empty LadderElements collection after validating the stored IL and caller body. It retains existing valid graphs and scalar annotations verbatim. Missing/extra/forged entities, coordinates, connections, descriptors, namespaces, duplicate fields and mixed content fail without changing the target. Whole-project scheduling and unrelated hardware/configuration gates remain unchanged.

## Verification scope

TDD preserved initial missing-module RED, meaningful malformed-value boundary RED and the final GREEN run. The single full command was `python3 -m unittest discover -s tests -v`; its terminal log reports 628 tests/217.783s/OK. Runner wall time was 217.914 seconds. All 172 inputs, before/after maps and exact retained source copies match. Ruff check/format passed for 110 Python files and diff checking passed before and after the suite.

Independent review exercised all 64 identities, 128 absent/empty graph fills, 704 rotations, wrapper-field orderings, deep-copy and malformed/atomic controls, instruction-budget boundaries and actual project refusal. A 10,000-instruction guard is a local tool budget, not measured PLC capacity. The source snapshot includes the separately owned stress script, but unittest discovery does not execute that standalone stress run. Historical 602-test and earlier reports remain unchanged.

The [machine-readable record](SUBROUTINE-FOUNDATION-RESULTS.json) pins exact sources, fixtures, logs and independent review. Separate [native observations](SUBROUTINE-NATIVE-OBSERVATIONS.md) cover the handbuilt diagnostics. This foundation makes no compiler SR, native transaction, generalized accumulator/return-context, scheduler, physical PLC or certification claim. Full SR integration remains required by the unchanged parity goal.
