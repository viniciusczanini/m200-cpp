# Final bounded simulator observations

The session ended after 591.142 seconds from the bounded focus recovery to cleanup.
**36 output-mask observations passed in six additional profiles.** Together with the prior supervisor controls, seven of eleven composed profiles have some native runtime evidence. This is not complete qualification of those profiles or of the controller.

| Profile | Observed output-mask trace | Remaining limits |
|---|---|---|
| subroutine | `{}:4; {1}:7; held:7; {}:4` | MW12 not inspected; no full SR lifecycle qualification |
| subroutine-stateful | `{}:7; {5}:7; {1,5}:114; held:114; {1,3,5}:114; {1,3,4,5}:114` | Only output composition verified. MW7..16/MW20 not inspected; the unchanged Q114 alone does not qualify early-return diagnostic words. No MW20=5 injection or one-scan snapshot claim. Shared TON timing not measured. |
| g08-sequences-memory | `{0}:1288; {}:1288; {3}:1289; {}:1289; {1}:1106; held:1106; {}:1106; {1}:2724` | MW diagnostic words not inspected. Interior forward composition only; endpoints/collisions/lifecycle remain pending. |
| g08-drum-direct-outputs | `prime {1}:2; {}:2; {0}:1; {}:1; {1}:2; held:2; {}:2; {1}:260; {}:260; {1}:1` | MW10 not inspected. No constructor/reset collision, writable-step ordering, skip or broad lifecycle claim. |
| g09-calendar-lights | `{}:13; {2}:12; {}:13` | Only current valid November evening gate and inhibit observed. S50 staged/atomic invalid/recovery, calendar boundaries, leap/day rollover and MW100..104 not exercised. |
| g09-schedule-memory | `{3}:13; {}:13; {1}:4; {}:4; {3}:13` | Only steady Schedule0 evening output/SW114 disable and reenable observed. Schedule15 is outside its 19:00..20:00 interval. M60/M61 and MW10/MW11 not directly watched. No one-MAST latency, programmable-end-hour or interval-boundary qualification. |
| g08-drum-clock-lights | `NOT_EXECUTED_TIMEBOX` | Bounded remaining GUI campaign ended; next profile refused before Open because less than 60s remained. Prior admission is not runtime evidence. |
| g09-rtc-clock-lights | `NOT_EXECUTED_TIMEBOX` | Bounded remaining GUI campaign ended; next profile refused before Open because less than 60s remained. Prior admission is not runtime evidence. |
| g09-schedule-reservation | `NOT_EXECUTED_TIMEBOX` | Bounded remaining GUI campaign ended; next profile refused before Open because less than 60s remained. Prior admission is not runtime evidence. |
| modbus-no-transport | `NOT_EXECUTED_TIMEBOX` | Bounded remaining GUI campaign ended; next profile refused before Open because less than 60s remained. Prior admission is not runtime evidence. |

Input sets in braces identify high inputs; the other inputs are low. `held` is another observation without a new input edge. Masks are decimal Q0..15. The [structured record](runtime-summary.json) links the original, hashed panel captures for all 36 points. Seven points retained a strict decoder refusal for the green Q4 glyph and were read visually; its threshold was not relaxed.

RTC Management displayed 06 November 2026 at 21:17:05 for the calendar and 21:18:48 for the schedule. Schedule0 was active; Schedule15 was outside its 19:00–20:00 window. The schedule trace therefore expects mask13, not the mask15 of the earlier 19:30 setup plan. No clock, date, MW or WatchLists injection was performed. Calendar writes, invalid/recovery cases, boundaries, diagnostic words, scan timing and broad lifecycle remain unqualified.

The three SBR/SC/Drum observation probes remain excluded and pending. Their unknown results were not replaced with hypotheses. Native Modbus, an external TCP/serial peer and physical PLC I/O were not executed.

The simulator was stopped through the official UI. The [cleanup record](runtime-cleanup.json) shows no simulator window/process or TCP502 listener; the coordinator independently confirmed process/listener absence. All 33 shared SMBP hashes stayed unchanged. Source and SDK remain frozen at `77bba32`; no new feature work was performed during this session.
