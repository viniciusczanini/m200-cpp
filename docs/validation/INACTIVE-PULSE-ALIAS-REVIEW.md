# Independent inactive pulse-alias review

**No actionable defect found** in the inactive-PTO alias change on baseline
`8ce9264c74dfe360736a45fb3c3b591293a6ce2f`. This review inspected the change
read-only, reran the seven focused tests, and performed independent validation
and destination-preservation probes. It did not run the full suite, operate
the GUI or touch a physical controller.

## Scope of the change

The only implementation change replaces one exact address comparison with a
two-string allowlist for each existing index0/1:

- `%PLS{i}/%PWM{i}/%PTO{i}`
- `%PLS{i}/%PWM{i}/%PTO{i}/%FREQGEN{i}`

There is no suffix stripping, prefix match, case folding or generic resource
parser. Index must still be exactly0 or1, GlobalIndex must match it, duplicates
remain forbidden, Preset must be exactly1, and all three PtoObject inputs must
be scalar `NotUsed`. Unknown fields, attributes and duplicate singletons remain
subject to the existing closed validation. The new spelling does not enable
an active axis or another hardware-resource identity.

The exact official save used as preservation evidence is
`tests/fixtures/official_tm200ce40t_timer_ret_ton_fl3_2.smbp`, 87,336bytes,
SHA256 `35a9d891711ff3eb74d745f30c14cbb3574b7cd61b0cec876320263e28a1fbd6`.
Its two disabled channels use the shorter aliases. Configuration validation
now accepts those inactive defaults without modifying the tree or file.
Loading the whole project still fails the unchanged
`timer-mode functional-level mapping is unverified for SMBP` gate. The fixture
is not evidence that its retained-timer option executes at functional level3.2.

## Independent verification

`python3 -m unittest tests.test_inactive_pulse_aliases -v` passed seven tests
in0.263s. Additional probes checked:

- Five valid configurations: all four per-index combinations of short/long
  aliases and the exact legacy saved configuration. Validation was read-only.
- 108 rejected mutations across both indices and both forms: crossed resource
  identities, unknown suffixes, whitespace/case changes, noncanonical indices,
  mismatched GlobalIndex, nondefault presets, active/missing axis inputs,
  unknown fields/attributes, duplicate resources/fields and nested scalars.
- Four ordinary exports preserved the typed hardware tree and template bytes,
  including mixed per-index aliases.
- Three invalid-template exports preserved existing destination bytes and
  their input templates.
- The legacy project continued to reach the separate timer-option rejection.

No implementation or fixture file was changed by the review. The reviewed
`m200/config.py` SHA256 is
`a77c79f392515338169aeccb033801997b924d58c211e866335379df5da21d75`.
Probe details and selected input hashes are recorded in
`output/editor-validation/inactive-pulse-alias-review/independent-probes.json`,
SHA256 `16fb3d2040580e3b46ea22c7e7f3a222ab18ef0270078371ce7c96ba4221e357`.
The focused output is preserved beside it as `focused-tests.log`.

This result is limited to preserving the two observed inactive descriptor
forms. Active PTO/PLS/PWM/FREQGEN behavior, timer-option support, native
compilation/execution, physical I/O and complete controller parity are separate
work. Historical reports and source manifests were left intact.
