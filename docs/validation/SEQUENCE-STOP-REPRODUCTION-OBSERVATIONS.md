# Sequence STOP-only reproduction observations

**Result: `NOT_REPRODUCED_IN_THIS_SESSION_AND_INTERVAL`.** One launch of the original watch-table derivative reached **No error / Online / STOP**, with “PC and controller applications are identical” visible in two timestamped captures. This bounded observation leaves the earlier access violation unexplained. It establishes no fix or broader compatibility result.

The trial used the existing editor host process **24358**, without restarting the editor or launcher. Raw original S was opened offline and allowed to finish validation before the final A load. Opening S does not establish that the editor's internal state was reset. A used the historical logical path `P:\compiler-validation-2026-11-06\sequence_timers_watch.smbp` and exact original bytes. The planned B/A2 comparison was not started because A1 did not reproduce the failure.

| Role | Artifact | Bytes | SHA256 |
|---|---|---:|---|
| S | `control-sequence_timers.smbp` | 760861 | `ddc2150a010e99b988a0ffc21807fce229190cf88e25d8d731c45afd10ad920b` |
| A | `sequence_timers_watch.smbp` | 762859 | `83b73ea98fee422e230bf9d23f1164696e4e2de361d512916ebcd88abde5da67` |
| B, not started | `sequence_timers_watch_mbits1024.smbp` | 762894 | `9bb6db83edf956a6b1bf0ec36dc30af600cddd6003838017b1efe59ec66e4a0a` |

The [initial S capture](editor-evidence/sequence-stop-reproduction/S-offline-open.png) shows **Validating program 68%, Not Connected**. A premature attribution of completed validation was corrected; S was repeated/stabilized before final A. The [later S capture](editor-evidence/sequence-stop-reproduction/S-stabilized.png) and [A before launch](editor-evidence/sequence-stop-reproduction/A1-validation-completed.png) show **No error, Not Connected**. These exact images were independently inspected. No simulator launch had occurred during this preparation, according to the root operator's preserved record.

The first [STOP observation](editor-evidence/sequence-stop-reproduction/A1-observation-1.png) was **36.659541 s** after the launch-click request began; the second [STOP observation](editor-evidence/sequence-stop-reproduction/A1-observation-2.png) was **119.114885 s** after that request. They were **82.455344 s apart**. These intervals were recomputed from the journal request timestamp and the original capture filenames. They are not scan times or durations measured from simulator readiness. The two PNG files are byte-identical, preserved under their separate observation names and independently timestamped journal entries. They are two sampled observations, without a continuous-monitoring claim.

The preserved log segment for the current launch contains one launch request and no matching `AccessViolationException` / `ProcessMbitsEdges` / `MastTask` / native page-fault signature. The full same-session log still contains the earlier failure after the `2026-11-06 02:31:42.7282` launch. The [historical review](SEQUENCE-TIMERS-REVIEW.md) remains unchanged; neither the absence of a matching new log entry nor this STOP-only trial identifies its cause.

Root used **Stop simulator**. A [fresh cleanup capture](editor-evidence/sequence-stop-reproduction/A1-cleanup-completed.png) shows **No error, Not Connected**. The preserved manifest attributes exact simulator PID **96890** absence and TCP502 listener absence to root's `ps`/`lsof` checks, both exit1. The reviewer independently inspected the image and journal inventory and did not repeat those process/network checks.

No RUN, simulated input changes, external TCP client or memory collector was used; no operator Save/XML rewrite or physical hardware operation occurred. S/A/B hashes remained unchanged after cleanup and were independently read back. This is a disk-byte boundary: editor processing in memory is not asserted unchanged. No new unittest/scan count, native sequence execution, cold-start stability, allocation/WatchLists causal result or physical-controller proof is claimed. [Machine-readable evidence](SEQUENCE-STOP-REPRODUCTION-OBSERVATIONS.json) pins the six exact PNG copies, source manifest, eight-record action-journal subset and log snapshots.
