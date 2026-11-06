# Inactive pulse-alias integration results

The change based on `8ce9264c74dfe360736a45fb3c3b591293a6ce2f` passed
**469 combined tests in157.670s**, adding seven tests to the462-test checkpoint.
The full log SHA256 is
`4a710a13b5359698b0637c90c04323af45027caaa9aa7a88892b1e00edf23985`.
Exact patch-source, fixture, unchanged-gate and log hashes are recorded in the
[manifest](INACTIVE-PULSE-ALIAS-RESULTS.json). All seven pinned patch/gate inputs
still match at evidence capture.

This accepts two exact **inactive** display aliases per index0/1:
`%PLS{i}/%PWM{i}/%PTO{i}` and the same string with `/%FREQGEN{i}`.
Index/GlobalIndex agreement, default preset1, three scalar NotUsed axis inputs,
duplicate checks and unknown-field rejection remain unchanged. This does not
enable an active PTO, PWM, PLS or frequency generator.

The87336-byte official saved fixture has SHA256
`35a9d891711ff3eb74d745f30c14cbb3574b7cd61b0cec876320263e28a1fbd6`.
Its legacy inactive configuration now validates without mutation. The complete
retained-timer project remains rejected by the unchanged timer-option gate;
the saved true retention flag is not proof of execution at functional level3.2.
Ordinary program export preserves the inactive hardware profile.

The implementation's seven focused tests passed in0.255s. Independent review
repeated seven tests in0.263s and found no actionable defect after five valid
configuration probes, 108 rejected mutations, four hardware/source-preserving
exports and three existing-destination preservation checks. These are review
activities, not extra unit tests or scan frames to add to469. See the
[independent review](INACTIVE-PULSE-ALIAS-REVIEW.md).

Fresh scoped Ruff check/format-check and `git diff --check` passed. Earlier
historical integration reports and stress/public totals were preserved.
The separate read-only Modbus research and unsettled timer GUI profiles are
not included in this result. No native runtime, physical I/O, precise timing
or complete library parity is established by this increment.
