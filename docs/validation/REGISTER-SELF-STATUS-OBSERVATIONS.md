# Native FIFO self-status observations

Two independently reset FIFO trials produced the same **first-call latch: E=0, F=0, I=11, O=42, valid=1**. Later while the store input remained held, the current state became **E=1, F=0, I=11, O=11**. The exact native editor-saved diagnostic ran locally, was stopped through the official simulator control, and freshly reopened in Programming with **No error** after another project. This is a hand-built diagnostic, not supported compiler output or Register SDK support.

The exact executed save is 162108 bytes, SHA256 `73a5c1f24318494b69149f01caac5a9a7ebd69b03264fa7dffbdff8f8f8b94b3`. It preserves the TM200CE40T, actual Man21, default FIFO R0, all 13 allocation trees and task configuration. Its 20 rungs/52 lexical IL lines are unchanged from the IL-only diagnostic; the official conversion supplies 212 graph entities. Root used Ctrl+S on the disposable shared file, waited for completion, cloned the actual bytes through the filesystem and reopened the saved clone. No Save As operation is claimed.

The one Register call is:

```text
BLK %R0
LD %I0.0
R
LD %I0.1
I
LD %I0.1
ANDN %R0.E
O
END_BLK
```

R0.I is always 11. Each trial uses exclusive reset with I1 false, releases reset, assigns output sentinel 42 with I4, releases I4, then presses and holds I1. A preceding `LDR I1` captures the first call's post-block flags/words into persistent M/MW samples. Q2/Q3 show captured E/F; Q4 marks validity; MW10 is case marker 1, MW11 captured O and MW12 captured I. Reset clears validity while leaving words stale, so the old B-before words are not a new sample.

| Watch record | Current I/O/E/F | MW10/11/12 | Meaning |
|---|---|---|---|
| Initial | 11/0/1/0 | 0/0/0 | Empty, no sample |
| A before | 11/42/1/0 | 0/0/0 | Sentinel set, sample invalid |
| A held / released | 11/11/1/0 | 1/42/11 | First-call O42 retained in sample |
| B before | 11/42/1/0 | 1/42/11 | Previous words stale; Q4=0 |
| B held / released | 11/11/1/0 | 1/42/11 | New trial repeats first-call sample |

Separately viewed panels establish captured E/F/valid=0/0/1 after the first call and current E=1; B's held panel also shows I1 active. The seven watch records comprise **five distinct PNG byte sets**; six selected panel records comprise **three**. All 31 journal actions completed successfully. These are capture/journal records, not scan counts. Identical A/B images remain recorded without inflating unique observations. The watch refresh is 5 s, and panel/table snapshots are separate refreshes.

The repeated trace supports input expressions seeing pre-call E in this observed FIFO profile. It does not distinguish every possible internal evaluation/request-history mechanism, establish a universal input-evaluation rule or settle other self-status/reset/full expressions, collisions, skipped/repeated calls or lifecycle behavior. The [latched watch](editor-evidence/register-self-status/self-A-held.png) and [released panel](editor-evidence/register-self-status/panel-A_released.png) preserve the relevant values.

Independent readback closes every real XML change: two project identity fields, 48 IL formatting text fields, 20 Ladder-selection fields, 212 native graph entities and two E/F watch display tokens (`Decimal`→`BoolNumeric`). Restoring precisely those reported differences makes the complete typed tree equal to the watch derivative. Hardware, all allocations, tasks, Register configuration and watch address order are unchanged. The earlier derivative changes only WatchLists. All original, derivative and saved bytes are preserved; [machine-readable results](REGISTER-SELF-STATUS-OBSERVATIONS.json) include exact source hashes, full differences, lexical IL, native graph, journal lineage and every copied PNG hash.

[Official Stop cleanup](editor-evidence/register-self-status/simulator-stopped.png) shows Not Connected/No error with the panel absent. Root's exact PID 74958 and listener 502 checks returned no match. The [fresh saved-clone reopen](editor-evidence/register-self-status/reopen.png) after the bare-WR project shows Programming/No error, with saved SHA unchanged. The existing Untrusted DLL detected banner is preserved in the captures; no integrity setting was changed.

This adds native diagnostic evidence only. LIFO self-status, other expressions, first-call-TRUE/skip/repeated-call/lifecycle behavior, full Register compiler/SDK/IR/VM integration and physical PLC validation remain pending. Frozen preparation guides, hypotheses and “LAB unaccepted” comments are historical records and remain unchanged. No full suite or new unit-test count is attributed to this stage.
