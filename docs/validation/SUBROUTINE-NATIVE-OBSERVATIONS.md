# Native subroutine observations

2026-11-06. Two hand-built **TM200CE40T SR0/SR63** diagnostics completed official IL-to-Ladder conversion, Ctrl+S, fresh saved-clone Programming reopens **No error**, and ten settled local simulator phases across eight project/control combinations (four per project). Root operated the editor; an independent reviewer checked the exact saved bytes, XML readbacks, journals and PNGs. This is bounded native evidence, with no compiler SR support or new unit-test count claimed.

## Exact SR0 artifact and binding

The [actual editor-saved project](../../tests/fixtures/official_tm200ce40t_subroutine_sr0.smbp) is **137327 bytes**, SHA256 `49438bcbed59cde889547869d8c033f377dfb7e60153136a57cb48e135b0e21a`; its adjacent [provenance](../../tests/fixtures/official_tm200ce40t_subroutine_sr0.provenance.json) preserves the static binding procedure. Its hash still matches the preserved shared copy after the runtime and cleanup sequence. The watch-only input to conversion is 88891 bytes, SHA256 `6f408a96222793918c4548e82949e4b9b336ae886a30f6a7de38318af95f307c`.

The project contains ten master rungs/28 lexical IL lines and three callee rungs/nine lines: **13 rungs/37 lines total**. The master remains SectionNumber0; the Free POU is Name `LAB_SR0_LEAF`, Number0, SectionNumber2. These are separate identities, not a general number-to-section mapping.

The native call is `LD %I0.0; SR0`. Its saved graph uses a normal contact at row0/column0, horizontal lines at columns1–9 and a **Jump descriptor `SR0`** at column10/Left. The three callee rungs end implicitly, without a fabricated CAL or RET instruction. The editor generated every Ladder graph from the prepared IL; no graph was hand-drawn into the candidate.

Whole-tree readback permits only the recorded Name/FullName identity changes, IL whitespace, native graphs and IL-to-Ladder selection. Lexical IL, hardware, all thirteen allocation nodes, task/CPU-behavior settings, watches, rung names/labels and comments remain equal. The [clean save](editor-evidence/subroutine-native/sr0-save.png), [callee IL](editor-evidence/subroutine-native/sr0-callee-il.png), [native callee](editor-evidence/subroutine-native/sr0-callee-native-ladder.png) and [fresh reopen](editor-evidence/subroutine-native/sr0-reopen.png) retain exact captures. Historical `unaccepted`/`proof pending` preparation comments remain in the saved source; this dated record supplies the later observations without rewriting those comments.

## Settled SR0 runtime observations

Each scan initializes MW0 to10, clears MW1 and the diagnostic LEDs, and conditionally calls SR0 using I0.0. The callee writes MW0=20, MW1=1 and Q1=true. After returning, the caller snapshots MW0 into MW2, writes MW0=30 and sets Q2. I0.1 only supplies the diagnostic tautology/contradiction rungs in this leaf case. Every post-call operation starts a fresh Boolean load; caller accumulator preservation is not tested.

Watch order is MW0/MW1/MW2; output strings list Q0 through Q3 from left to right.

| Settled phase | I0 / I1 | MW0 / MW1 / MW2 | Q0–Q3 | Exact captures |
|---|---|---|---|---|
| Baseline | false / false | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr0-phase-0-watch.png), [panel](editor-evidence/subroutine-native/sr0-phase-0-panel.png) |
| Call enabled | true / false | 30 / 1 / 20 | `1110` | [watch](editor-evidence/subroutine-native/sr0-phase-1-watch.png), [panel](editor-evidence/subroutine-native/sr0-phase-1-panel.png) |
| Call held; I1 true | true / true | 30 / 1 / 20 | `1110` | [watch](editor-evidence/subroutine-native/sr0-phase-2-watch.png), [panel](editor-evidence/subroutine-native/sr0-phase-2-panel.png) |
| Call disabled; I1 true | false / true | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr0-phase-3-watch.png), [panel](editor-evidence/subroutine-native/sr0-phase-3-panel.png) |
| Both released | false / false | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr0-phase-4-watch.png), [panel](editor-evidence/subroutine-native/sr0-phase-4-panel.png) |

These values support conditional leaf entry, implicit return and subsequent caller operations for this exact diagnostic. Disabled calls leave no settled callee marker after the master's explicit initialization. They are five sampled phases, **not five scans or a timing trace**; no exact scan count, execution latency or refresh timing is inferred.

## SR63 conditional and explicit return

The [SR63 editor-saved project](../../tests/fixtures/official_tm200ce40t_subroutine_sr63.smbp) is **157411 bytes**, SHA256 `ff05369c686e8bc1887612afdbfcfd57d24e0e4e1e51d8d2b2b443824a2fa652`; its [provenance](../../tests/fixtures/official_tm200ce40t_subroutine_sr63.provenance.json) links the [clean save](editor-evidence/subroutine-native/sr63-save.png) and [fresh reopen](editor-evidence/subroutine-native/sr63-reopen.png). The saved and preserved shared bytes remain equal after runtime/cleanup. The watch-only conversion input is 91531 bytes, SHA256 `e0ba01812ca868ad1ffc75e0eb3fb5c12b49c1419cd3a584ec5e13bea3756408`.

It contains ten master rungs/28 lexical IL lines and eight callee rungs/21 lines: **18 rungs/49 lines total**. The Free POU is `LAB_SR63_CONDITIONAL_RETURN`, Number63, SectionNumber2; the master still uses SectionNumber0. Readback independently preserves every other typed field outside the same identity/native-graph/view changes as SR0, including all allocations, tasks, hardware, watches and comments. Its literal call graph ends in Jump descriptor `SR63`.

The [callee IL](editor-evidence/subroutine-native/sr63-callee-il.png) first sets MW0=20, MW1=1 and Q1. `LD %I0.1; ENDC` conditionally returns at that point. Otherwise the callee sets MW0=25, MW1=2 and Q3, then uses `END`. The caller's subsequent fresh-load rungs snapshot the returned word into MW2, set MW0=30 and Q2. [Native Ladder conversion](editor-evidence/subroutine-native/sr63-callee-native-ladder.png) is preserved separately.

| Settled phase | I0 / I1 | MW0 / MW1 / MW2 | Q0–Q3 | Exact captures |
|---|---|---|---|---|
| Baseline | false / false | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr63-phase-0-watch.png), [panel](editor-evidence/subroutine-native/sr63-phase-0-panel.png) |
| Call enabled; END path | true / false | 30 / 2 / 25 | `1111` | [watch](editor-evidence/subroutine-native/sr63-phase-1-watch.png), [panel](editor-evidence/subroutine-native/sr63-phase-1-panel.png) |
| Call held; ENDC path | true / true | 30 / 1 / 20 | `1110` | [watch](editor-evidence/subroutine-native/sr63-phase-2-watch.png), [panel](editor-evidence/subroutine-native/sr63-phase-2-panel.png) |
| Call disabled; I1 true | false / true | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr63-phase-3-watch.png), [panel](editor-evidence/subroutine-native/sr63-phase-3-panel.png) |
| Both released | false / false | 30 / 0 / 10 | `0010` | [watch](editor-evidence/subroutine-native/sr63-phase-4-watch.png), [panel](editor-evidence/subroutine-native/sr63-phase-4-panel.png) |

These samples support current-level END/ENDC return and caller continuation in this exact diagnostic. They do not establish ENDCN, same-rung accumulator preservation, repeated/skip history or stateful callee behavior. The two five-phase tables total **ten sampled phases/eight project-control combinations**, not scans; the four raw input combinations are reused across two different programs.

## Runtime state and cleanup

Both runtime sets show **Online / Run with “Program advisory(s) detected”**. [SR0 commissioning](editor-evidence/subroutine-native/sr0-commissioning-run-advisories.png) and [SR63 commissioning](editor-evidence/subroutine-native/sr63-commissioning-run-advisories.png) report identical PC/controller applications, “No protocol is enabled,” and inactive application protection. The existing **Untrusted DLL detected** banner is visible before and during execution; this report does not attribute or resolve it. The offline save/reopen's “No error” is not substituted for the runtime status.

Root used the official Stop simulator action for each project. The fresh completed [SR0 cleanup](editor-evidence/subroutine-native/sr0-cleanup.png) and [SR63 cleanup](editor-evidence/subroutine-native/sr63-cleanup.png) show **Not Connected / Program advisory(s) detected**, no simulator panel and Launch simulator available. Root's frozen records report the exact host simulator PIDs 9006 and 17448 absent (`ps` exit 1), respectively, and no TCP 502 listener (`lsof` exit 1) at each cleanup. Those are historical cleanup results, not new probes or claims about any later session.

The frozen action journals contain **23 SR0 and 21 SR63 completed entries with their full arguments**. All **38 promoted PNGs** (20 SR0, 18 SR63) match the original bytes and were independently viewed. Both root records, journals, complete static readbacks and hashes are pinned in [SUBROUTINE-NATIVE-OBSERVATIONS.json](SUBROUTINE-NATIVE-OBSERVATIONS.json).

## Remaining evidence

These diagnostics do not establish ENDCN, same-rung accumulator continuation, nested or dynamic calls, SR1–62, multiple calls per scan, stateful blocks inside callees, call-history/lifecycle semantics, events/tasks/preemption, physical controller behavior, or general subroutine compiler support. Standalone codec foundation tests and their combined suite are a separate implementation record, not a compiler/runtime claim supplied by these observations. The earlier simulator-crash investigation remains separate. No physical PLC, external communication, firmware change, remote pipeline or new local regression run was part of this observation review. The full parity goal remains unchanged.
