# Official timer-option observations

These are bounded observations of a **hand-built laboratory diagnostic** in
the official local simulator. They are not a record of the supported exporter
generating true-option projects. At this observation checkpoint, the product
still rejected those projects through its timer-option gate; any later narrow
admission is separate work.

The root operator observed No error, Online/identical and RUN, used simulated
input buttons, and watched MW200–205 directly without Force or an external TCP
client. The environment is the authorized Wine/.NET lab with its existing
Untrusted DLL detected banner. No physical controller was involved.

## Exact configuration and artifacts

All three timers use `FunctLevelMan21_0`, a one-second base and initial preset20.
TM0 is TON with retention true; TM1 is TOF with retention true; TM2 is TON with
dynamic preset true. The other option is false for each. **No instance combines
retention and dynamic preset.** I0.0/1/2 enable the respective timers. I0.3
writes TM2.P=5; I0.4 restores20 and takes priority when both are set.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| Hand-built candidate | 452549 | `72590cd249739a1bdc4f7387f8508f918d0a7c6b85ad0e15240fdcb9bb5b23ec` |
| Official-editor saved file | 471237 | `5358e5334696e1838e8b34b9efaa84fafb2a7bd97802d2d2ee32ae94a7f52214` |
| Ordinary-false watch control | 471240 | `ff8d737a4bb38725de268ef22908bea685ac0b3dc5b20412d69a7688bf2a7aa6` |

The control is the saved file with exactly three true option fields replaced
by false. A byte-level reconstruction matches it exactly. Hardware, executable
IL, graphics and the six-word watch remain unchanged.

## Observed behavior and control

| Separate configuration | True-option diagnostic | Ordinary-false control |
|---|---|---|
| TON retention | V18/P20 paused and remained18 through a hold of at least52.7s; resuming reached20 with Q0.0 on. Disabling after completion cleared V/Q. | Q0.13 indicated V>0 while counting; disabling cleared that indicator and the subsequent direct word value was0. |
| TOF retention | V4/P20 remained4 through an approximately286.6s pause. Resuming showed18 then20; Q0.1 cleared on completion. Reasserting IN cleared V and asserted Q again. | Q0.14 indicated V>0 during off-delay. Reasserting IN cleared it, and the subsequent direct word value was0. |
| TON dynamic preset | A sample showed V2/P20. After requesting P5 while enabled, the captured state was V6/P5 with Q0.2 on, within10s of enable according to root's wall-clock observations. | V6/P5 and V18/P5 still had Q0.2 off; V20/P5 had Q0.2 on. |

Both dynamic experiments were cleared to V0 and restored to P20. The captured
V6 above new P5 is preserved as observed; it is not replaced by an assumed
clamped value5.

Representative evidence: [TON pause](editor-evidence/timer-options/ton-paused.png),
[TOF held](editor-evidence/timer-options/tof-held.png),
[dynamic true V6/P5](editor-evidence/timer-options/dynamic-changed-completed.png)
and [Q on](editor-evidence/timer-options/dynamic-changed-completed-panel.png),
versus ordinary control [V18/P5](editor-evidence/timer-options/false-dynamic-p5-later-still-counting.png)
and [Q off](editor-evidence/timer-options/false-dynamic-v18-p5-qoff-panel.png).
The [JSON record](TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.json) pins all29 unchanged
public PNGs: 12 true-option word samples, three panels, six control word
samples, seven control panels and one fresh-reopen capture.

The animation table displayed a5s time-base setting; its readings and separate
panel captures are not synchronized. During a rapid ordinary-TOF transition,
the word table still showed0 while the panel indicated V>0. Accordingly, the
transient nonzero control observation is **panel-only**, with no exact nonzero
word value claimed. Pause durations are root's wall-clock observations, not
measurements encoded in identical paused/held PNGs.

## Save/readback and limits

Independent parsing found105 rungs and227 executable lines in both original
and saved files. Typed numeric/comparison instruction semantics, timer flags
with editor defaults, graph bindings/geometry and hardware are equal. Raw
spacing and omitted default TON/false fields account for serialization
differences; this comparison did not simply delete whitespace. The typed IL
signature SHA256 is
`8eff612556795b417ffb642d57474ea20da017e87eb7d64f31f9b9a61fec7656`.

The exact saved file was [freshly reopened with No error](editor-evidence/timer-options/fresh-reopen.png)
after another project was loaded. This proves a reopen, not another runtime
run of the saved bytes. Root stopped the simulator after the control; the
panel disappeared and a local TCP502 listener check returned exit1/no output
at that cleanup event.

These results support the selected separate-mode differences at Man21/base1s.
They do not establish minimum/lower functional levels, combined modes, TP
retention, STOP/RUN or power-loss behavior, exact scan/tick ordering,
fractional-tick policy, physical timing, complete SDK/VM equivalence or full
library parity. The preparation GUIDE/manifest predate these GUI observations;
their no-official-runtime wording is preserved as historical preparation
context rather than silently rewritten.
