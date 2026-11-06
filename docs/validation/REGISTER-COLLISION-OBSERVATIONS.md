# Native FIFO Register collision observations

2026-11-06. Root opened the hand-built TM200CE40T FIFO R0 diagnostic in the
official local Machine Expert Basic editor, converted its IL to Ladder, saved it,
and freshly reopened the exact saved-byte clone after another project. The editor
showed **No error**. Root then ran the bounded cases below in its local simulator.
An independent reviewer checked all 21 recorded seven-value checkpoints against
the exact PNGs, plus 28 selected simulator panels, without operating the GUI.

This is native-editor and simulator evidence for a **disposable FIFO diagnostic**.
It is not compiler-generated output or implemented Register C++/IR/SDK/VM/graph
support. No physical PLC was operated. The environment is Machine Expert Basic
1.4 build 484 in the Mac Wine lab, at actual `FunctLevelMan21_0`. The
[manifest](REGISTER-COLLISION-OBSERVATIONS.json) pins artifacts, input records,
independent readings and exact public PNG copies.

## Exact editor artifact

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| IL-only FIFO collision candidate | 94,849 | `e4d668085e47677d1ef2d59e3560319e8f3cc6ff3e04412d6f191bbcd26d6b1f` |
| Candidate with seven animation rows | 96,430 | `6f3e15d9caec3f295ae4439d6adc76c2f89733f473739e862365ed5cf4b7ca5b` |
| Exact editor save used for execution | 192,588 | `f845b2ba9920aecc25be7c9fde40fc4fd75fd6d26c9da6f424d906c2d9b3e51b` |

The source derives from authentic CE40T memory baseline `df5a2931…2924fbf`.
Independent readback confirms the saved hardware tree and all 73 lexical IL lines
match the watch candidate. There are 26 selected-Ladder rungs; native conversion
produced 28 entities in the branch-rich Register rung. FIFO R0 saves as its known
default-empty `Registers` collection. These files remain lab artifacts, not newly
promoted product fixtures.

[Save](editor-evidence/register-collisions/fifo-save.png),
[fresh Programming reopen](editor-evidence/register-collisions/fifo-reopen.png)
and [reopened CE40T target](editor-evidence/register-collisions/fifo-reopen-configuration.png)
are separate acceptance stages. Earlier preparation comments and the readback's
historical `runtime: pending` field are preserved; the later observations below
complete only this bounded simulator stage.

## Controls and first-call capture

| Simulated input | Program effect |
|---|---|
| I0 | Exclusive reset; also clear snapshot flags/valid |
| I1 / I2 | Store / retrieve request |
| I3 | Input data 22 instead of 11, assigned before the Register call |
| I4 | Write output-word sentinel 42 before the call |
| I5 | Shared Store+Retrieve request |
| I6 / I7 / I8 | Shared Reset+Store / Reset+Retrieve / Reset+Store+Retrieve |

One rising-edge instruction per I6/I7/I8 runs before the Register call. Its event
captures E/F and the I/O data words after that call, retaining the sample while
the driver stays held. Q0/Q1 show current E/F; Q2/Q3 show captured E/F; Q4 is
snapshot-valid. MW10 is case6/7/8, MW11 captured O and MW12 captured I. The seven
watch rows are **R0.I, R0.O, R0.E, R0.F, MW10, MW11, MW12**. The suffixes I/O in
these watch rows are data words, distinct from the block's request inputs.

Reset deliberately leaves old sample words present when Q4 is false. For example,
the [C7 preparation](editor-evidence/register-collisions/fifo-C7-two-sentinel-off.png)
shows stale MW10=6 with invalid snapshot. A case word alone is not a valid sample.

## Recorded collisions and held requests

All collision snapshots below show **captured I=0/O=0/E=1/F=0, valid=1**, with
their respective case number. Current held values also read I0/O0/E1/F0. Direct
panels show Q2/Q3/Q4=1/0/1. This records the observed traces; it does not define a
universal reset-output or priority rule.

| Shared driver and preparation | Exact captured evidence |
|---|---|
| C6 Reset+Store, empty with O42 | [Words](editor-evidence/register-collisions/fifo-C6-empty-held.png), [panel](editor-evidence/register-collisions/panel-fifo-C6-empty-held.png) |
| C6 Reset+Store, two stored values and O42 | [Words](editor-evidence/register-collisions/fifo-C6-two-held.png), [panel](editor-evidence/register-collisions/panel-fifo-C6-two-held.png) |
| C7 Reset+Retrieve, two stored values and O42 | [Words](editor-evidence/register-collisions/fifo-C7-two-held.png), [panel](editor-evidence/register-collisions/panel-fifo-C7-two-held.png) |
| C8 Reset+Store+Retrieve, two stored values and O42 | [Words](editor-evidence/register-collisions/fifo-C8-two-held.png), [panel](editor-evidence/register-collisions/panel-fifo-C8-two-held.png) |
| C6 Reset+Store, full with O42 | [Before](editor-evidence/register-collisions/fifo-C6-full-sentinel-off.png), [captured words](editor-evidence/register-collisions/fifo-C6-full-held.png), [panel](editor-evidence/register-collisions/panel-fifo-C6-full-held.png) |

Three additional held-request sequences were observed:

1. While I6 remained high, I1 was asserted. Releasing only I6 left Store high:
   [panel I1+I6](editor-evidence/register-collisions/panel-fifo-E-reset-store-I1-held.png)
   becomes [I1 alone](editor-evidence/register-collisions/panel-fifo-E-reset-store-reset-falls.png),
   with [I11/O0/E0](editor-evidence/register-collisions/fifo-E-reset-store-reset-falls.png).
   After releasing and freshly asserting Store, two fresh retrievals returned
   [11/E0](editor-evidence/register-collisions/fifo-E-reset-store-drain-1-off.png)
   then [11/E1](editor-evidence/register-collisions/fifo-E-reset-store-drain-2-off.png).
   An [extra empty retrieval](editor-evidence/register-collisions/fifo-E-reset-store-drain-3-off.png)
   retained 11. The two pops support two queued values in this trace; no native
   depth operand was read.
2. After the C7 Reset driver dropped, Retrieve remained high. A fresh Store22
   pulse with Retrieve held produced
   [I22/O0/E0](editor-evidence/register-collisions/fifo-E-empty-pop-store-off.png);
   the [panel](editor-evidence/register-collisions/panel-fifo-E-empty-pop-store-off.png)
   still shows I2 high. No automatic retrieval was visible during those held
   observations. Releasing and freshly asserting Retrieve returned
   [22/E1](editor-evidence/register-collisions/fifo-E-empty-pop-retrieve-new-off.png).
3. Sixteen Store22 pulses produced
   [Full=1](editor-evidence/register-collisions/fifo-full-history-store-16-off.png).
   An attempted seventeenth Store of 11 was held with
   [Full still1](editor-evidence/register-collisions/fifo-E-full-ignored-store-held.png).
   A fresh Retrieve while Store stayed high returned 22 and left
   [Full=0 after Retrieve release](editor-evidence/register-collisions/fifo-E-full-retrieve-off.png),
   with [Store visibly held](editor-evidence/register-collisions/panel-fifo-E-full-retrieve-off.png).
   Releasing and freshly asserting Store restored
   [Full=1](editor-evidence/register-collisions/fifo-E-full-new-store-off.png).

These results constrain a future edge-history model for the observed paths.
They do not reveal its internal previous-pin/reset algorithm. In particular, an
inference about consumed, cleared or pending edges must remain distinct from the
displayed flags, data words, input levels and later drain results.

## Evidence limits and cleanup

The 21 runtime records have 17 distinct exact main-window PNG hashes. Repeated
images are retained under their action labels, not counted as additional unique
states or controller scans. The 28 panel records establish selected held/release
input conditions. Watch refresh is five seconds; the native latch preserves its
event sample, while GUI timestamps do not establish fine timing or physical
same-scan coherence. The 53 exact PNG copies total 11,043,975 bytes.

The journal contains 109 action records. Only its final 13 entries, beginning with
`fifo-E-full-select11`, include original command arguments; 96 earlier entries
have labels/timestamps/captures only. Those earlier transitions rely on the
listed panels, source IL and root's direct observations, not a complete
replayable command history. No new unit tests, full suite, CI or GitHub Actions
were run for this report; historical regression evidence is unchanged.

Root used official Stop simulator and recorded the panel absent, specific host
PID 31667 absent and no TCP 502 listener afterward. The
[fresh completion capture](editor-evidence/register-collisions/fifo-collision-simulator-stopped.png)
shows No error / Not Connected, Launch simulator available and Stop simulator
disabled. The earlier stop-action capture can precede asynchronous completion
and is not used as the final cleanup proof. Process/listener absence is attributed
to root's completed cleanup record; this reviewer did not rerun state probes or
infer that no listener existed during RUN.

LIFO collision/history repeats, C7/C8 with a full FIFO, first-call TRUE,
self-status input evaluation, skipped/repeated calls and cold/warm/STOP lifecycle
remain pending.
Physical controller, firmware and load behavior remain unverified. The isolated
[Register configuration codec](REGISTER-CONFIG-FOUNDATION-RESULTS.md) remains a
separate foundation; active Register compilation and execution support is still
gated. The exact Wine captures retain their existing Untrusted DLL detected
banner. No validation or integrity check was bypassed by this reporting work.
