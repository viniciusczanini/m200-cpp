# Standalone Register graph foundation

2026-11-06. **587 tests passed in 234.067 seconds**, with zero skips and all 156 frozen source/input pins unchanged. This adds nineteen portable graph tests to the 568-test checkpoint. The graph/configuration cohort passed 37 methods in 0.221 seconds. Independent review found no actionable defects and separately verified the terminal log and 156 hashes without repeating the full suite.

The new [register_graph.py](../../m200/register_graph.py) is a **standalone component**. It is not connected to configuration/project import, Program, frontend, reverse, SDK or VM. Both complete Register fixture projects still fail current whole-project admission. This increment supplies no C++ Register API, FIFO/LIFO execution, edges, collision priority, self-status timing or physical PLC proof. The existing [Register configuration foundation](REGISTER-CONFIG-FOUNDATION-RESULTS.md) remains separate.

## Exact portable sources

Root opened, officially saved and freshly reopened both exact saved-byte clones with No error in Programming. Their original diagnostic names/comments remain unchanged, including older pending-proof text; the separate operator evidence establishes the observed save/reopen stage. Each file has six rungs/eighteen normalized instructions and graph sizes 10/10/10/**4**/11/11. The four-entity Register rung is the only graph form admitted by this component.

| Exact fixture | Bytes | SHA256 |
|---|---:|---|
| [FIFO, default mode omitted](../../tests/fixtures/official_tm200ce40t_register_fifo_three_ld.smbp) | 105416 | `f6198b7054f1f1b6dbd016f6df756ef2ebd150a99d26bc59e86069944d000fa4` |
| [LIFO, explicit Lifo configuration](../../tests/fixtures/official_tm200ce40t_register_lifo_three_ld.smbp) | 105554 | `a82e4dd97f37c469dae5d30f68b12cf3d11f55f0131f171d7e6b0a3b5c37cf0a` |

Adjacent provenance sidecars record exact bytes, snapshotted root observations and four save/reopen capture hashes. A narrow `official_tm200ce40t_register_*.smbp -text whitespace=cr-at-eol` rule preserves native CRLF; existing attributes/hooks are untouched. All nineteen new tests use these public fixtures, with no optional lab-file dependency. The older configuration test's optional authentic-lab method remains unchanged and ran in this local full suite.

Both bare bodies are:

```text
BLK %R0
LD %I0.0
R
LD %I0.1
I
LD %I0.2
O
END_BLK
```

| Entity | Descriptor | Row | Column | Connection |
|---|---|---:|---:|---|
| NormalContact | %I0.0 | 0 | 0 | Left, Right |
| NormalContact | %I0.1 | 1 | 0 | Left, Right |
| NormalContact | %I0.2 | 2 | 0 | Left, Right |
| Register | %R0 | 0 | 1 | Left |

The graph is mode-independent in these two saves. Mode is obtained separately through `register_xml.read_registers`; the graph does not infer mode or execute any pin.

## Component contract and tests

`RegisterInputs` holds a canonical native index 0–3 and Reset/Store/Retrieve pin addresses. `parse_block` accepts only the eight-line plain-LD R/I/O body; `graphics` returns its literal geometry; `read_graph` validates the complete original body/graph without mutation. Contact parameters are limited to canonical direct `%I0.0..%I0.23`. This is a bounded codec parameter domain, not evidence that every combination was opened in the editor or that a particular hardware assignment is available.

`write_graph` changes only an absent/empty LadderElements collection after checking that caller and stored IL agree. It stages the complete graph before replacement, preserves unrelated rung fields, instruction comments, selection state and the old collection tail, and retains existing valid graphs/UI annotations unchanged. It refuses malformed, partial or mismatched data instead of repairing it by discarding information. Unknown/duplicate/namespaced nodes, attributes, nested scalars, significant text/tails, noncanonical identities, forged coordinates/connections and unsupported actions fail explicitly. The other five fixture rungs are not mistaken for this bare Register body. Production code never dispatches on fixture hashes.

TDD first observed the absent module fail one test, then all nineteen new methods fail for that same missing component. The initial GREEN run passed nineteen in 0.193 seconds; the final graph/configuration cohort passed all 37. Independent local probes checked 55,296 parameter combinations, 96 XML writes, 24 graph permutations, 374 malformed owned-XML cases with atomic read/write refusal, 190 IL negatives, seven typed negatives and five annotation positives. Exact fixture/lab/provenance/CRLF/capture hashes and whole-project refusals were checked independently. The reviewer's separate nineteen-method run passed in 0.185 seconds as tool-session evidence; no persisted focused log is claimed for that run. Probe script/output and review hashes are pinned in the [JSON record](REGISTER-GRAPH-FOUNDATION-RESULTS.json).

## Frozen verification scope

The single unit run used the recorded 156-pin snapshot. Ruff check/format passed explicitly for its **104 pinned Python files**. A separate root-owned `tests/stress/modbus_full_pin.py` appeared during the run; it is not a discovered unittest file and was not retroactively added to this source pin. Post-run current-tree Ruff also passed **105 files**. That script's own Modbus stress evidence is separate; this report makes no all-current-tree or extra-full-suite claim.

Whole Register integration and remaining native forms are still work toward the unchanged full-parity objective. Other contact domains, negated/edge/status/compound inputs, labels, wired outputs and standalone Register actions outside this BLK form need their own contracts/evidence. A clean saved binding and a strict component codec do not establish Register runtime behavior or controller compatibility.
