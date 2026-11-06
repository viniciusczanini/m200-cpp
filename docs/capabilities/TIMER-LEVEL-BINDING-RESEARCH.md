# Low level timer flag preservation research

Date: 2026-11-06. Matrix case 03 preserves `IsRetentive=true` at application
level 3.2 when saved by the official editor. **This proves persistence, not
retentive execution at that level.** Static inspection finds a separate installed
UI availability threshold at level 4.0, an ungated stored property, and a managed
compiler bridge that forwards the stored flag. Native compilation/runtime
treatment is still unresolved. No GUI, Wine process, socket or vendor runtime
was operated for this research; only this document was written.

## Exact files and semantic changes

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Lab `diagnostics/timer-profile-candidates/timer_profile_03_ret_ton_fl3_2.smbp` | 87451 | `f54bffa66cc80e7f0e781079821c1de2e3c77885c6b502849179c119c27b53fa` |
| Repository `output/editor-validation/timer-profiles/timer_profile_03_ret_ton_fl3_2_editor_saved.smbp` | 87336 | `35a9d891711ff3eb74d745f30c14cbb3574b7cd61b0cec876320263e28a1fbd6` |

Both identify TM200CE40T and `FunctLevelMan5_0`, mapped by the installed resources
to human level 3.2. Both retain TM0, preset 5, base `OneHundredMilliSeconds` and
`IsRetentive=true`. Actual IL and Ladder values/order are unchanged.

Ignoring indentation, attribute order and singleton-field ordering, there are
**31 semantic differences**: 27 technical-capability scalars, two pulse-output
address aliases and two omitted timer defaults. Every changed capability is
listed below; names in the first five rows are under
`Cpu/TechnicalConfiguration/PtoConfiguration`.

| Fields | Original | Editor-saved | Count |
|---|---:|---:|---:|
| McPowerPtoMax, McHomePtoMax, McSetPosPtoMax | 86 | 2 | 3 |
| McMoveVelPtoMax, McMoveRelPtoMax, McMoveAbsPtoMax, McStopPtoMax, McHaltPtoMax | 86 | 16 | 5 |
| McReadActVelPtoMax, McReadActPosPtoMax, McReadParPtoMax, McWriteParPtoMax | 40 | 4 | 4 |
| McReadStsPtoMax, McReadMotionStatePtoMax, McReadAxisErrorPtoMax, McResetPtoMax, McTouchProbePtoMax, McAbortTriggerPtoMax | 40 | 2 | 6 |
| McMotionTaskPtoMax | 2 | 0 | 1 |
| ComConfiguration/ReadVarBasicMax, WriteVarBasicMax, WriteReadVarBasicMax | 32 | 16 | 3 |
| ComConfiguration/SendRecvSmsMax | 1 | 0 | 1 |
| GrafcetBitsMax | 200 | 96 | 1 |
| UdfbInstanceMax | 32 | 0 | 1 |
| UdfMax | 64 | 0 | 1 |
| UdfObjectsMax | 4096 | 0 | 1 |

The remaining hardware changes are the two `PulseTrainOutput/Address` values:
`%PLS0/%PWM0/%PTO0/%FREQGEN0` becomes `%PLS0/%PWM0/%PTO0`, and the analogous
index-1 value loses `/%FREQGEN1`. Both retain index/global index 0 or 1, preset
1 and `RefInput`, `ZPhaseInput`, `ProbeInput` all `NotUsed`. No observed active
axis configuration was introduced. The installed `SupportsFrequencyGenerator`
predicate has the same level-4.0 threshold as the retentive UI predicate.
**Inference:** the capability and alias changes are consistent with rebuilding
the lower-level profile, rather than operator activation/deactivation of an axis.
The files alone do not prove the exact editor event that performed that rebuild.

The two software changes omit explicit `Type=TON` and
`IsDynamicPreset=false`; these are defaults already handled by the importer.
The retention flag, level, address, preset and base remain unchanged. This is
not a silent promotion to a higher application level.

## Current parser classification

The unmodified input reaches `timer-mode functional-level mapping is unverified
for SMBP`. The exact editor-saved copy fails earlier with `unsupported pulse
output defaults`: `inactive_pulse_outputs` currently accepts only the longer
alias containing FREQGEN.

A read-only, in-memory classification restored only those two aliases in a
copy of the parsed tree; its complete `configuration()` validation then passed.
Thus all 27 normalized capability values are already accepted metadata, while
the shorter inactive aliases constitute a separate importer gap. This experiment
did not alter either file or authorize dropping the timer-option gate.

Any future compatibility change should preserve these exact lower-level aliases
and retain the existing checks for address/index identity, duplicate fields,
preset 1, absent active modes and all three `NotUsed` inputs. It should not
rewrite the file into a higher-level profile to make import pass.

## Installed metadata and IL findings

The inspection recorded member identities and behavioral facts only. No vendor
binary, method body, disassembly or complete resource extraction is published.

| Inspected assembly | SHA-256 |
|---|---|
| CommonCore | `9434b681932df39a57f9ee14d39e09b12bd5eb42c62d8aa814ef217821d0181a` |
| Entities | `bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e` |
| Business | `2dc6a38e45ee6fa6d39b2fe63d67826214f3f6230413974516b30567ba3a16a8` |
| PersistenceLayer | `c0a7c279d49584881fe4e7a0218220091633325f818c8366363b2ad2233270ea` |
| CodeGeneratorService | `a25ee4fce2c3d3dd619108496842d1656a66e6f461b664b840c19fd864a4dc4d` |
| CLIWrapper | `d9c027872730d922e2b59cdefbee8270cd7af6403bf50773ed19d77fdb755c90` |

Assembly filenames use prefix `SchneiderElectric.SoMachineBasic.` and suffix
`.dll`, except `CLIWrapper.dll`.

1. `CommonCore` method `ManagementLevel.Supports.SupportsTimerRetentive`
   (`0x0600017a`) tests a minimum enum value of 16: `FunctLevelMan7_0`, human
   **4.0**. `SupportsNewPresetTimerMode` (`0x060001b0`) uses 27: Man18,
   **12.0**. `SupportsFrequencyGenerator` (`0x0600017c`) uses 16.
2. Business `TimerViewModel.get_IsRetentiveAvailable` (`0x06002cef`) consults
   the support predicate and excludes TP; the installed timer enum is TON=0,
   TOF=1, TP=2. `get_IsDynamicPresetAvailable` (`0x06002cf0`) consults the dynamic
   predicate. **Static consequence:** the retention availability predicate is
   false for a TON at Man5. Actual checkbox appearance was not observed here.
3. Entities `TimerTM.set_IsRetentive` (`0x0600141e`) stores the value and raises
   a property notification; no level check is present in that setter.
   `TimerBlockAdapter.ReadXml` (`0x06000158`) reads the supplied boolean.
   `WriteXml` (`0x06000159`) preserves a true flag without calling the timer
   support predicate. The writer also consults project-version serialization
   services; it is not correct to describe the entire serializer as level-blind.
4. Business `ProgramWorkspaceController.BuildSoftwareConfigurationReportMessages`
   (`0x06002426`), called by `BuildReportMessages`, has a separate level-change
   reporting path using `SupportsTimerRetentive` and resource identifier
   `WarningTimerRetentiveChange`. Its associated downgrade action iterates
   timers and clears the retention flag. An analogous dynamic-mode path exists.
   **This path's existence does not show it ran during this import/save.**
5. CodeGeneratorService `CodeGeneratorHelper.SetTimer` (`0x06000512`) reads the
   stored retention and dynamic flags and forwards them to the binary-generator
   `SetTimer` call. There is no support-predicate call or conditional level branch
   in that managed helper. This rules out silently stripping the flag in that
   helper, but does not establish how the downstream native generator uses it.

The installed UI threshold agrees with the Operating Guide's level-4.0 feature
list, while the Generic Functions configuration table still states 3.3. See
[the primary-source audit](TIMER-PARITY-AUDIT.md) and
[token/resource identities](EDITOR-INTEROP-FACTS.json). These implementation
facts narrow the discrepancy; they do not override documented PLC features or
prove the minimum effective firmware/runtime level.

## Evidence needed next

- Preserve the original, editor-saved and **post-compilation saved** bytes as
  separate artifacts. Record whether the flag, level, warnings or generated
  configuration change at compilation, commissioning/STOP, or reopening.
- Compare explicit GUI level changes from a valid retentive project against
  opening an already-low-level file. Capture any downgrade warning and resulting
  flag separately; those are different code paths.
- Test one retentive TON/TOF at each disputed boundary with a partial interval,
  disabled pause, resume and completion. Pair with options-off controls. A flag
  that persists but behaves as an ordinary TON is not successful retention.
- Keep application level, simulator firmware and physical-controller firmware
  distinct. No error on open, a saved checkbox, native compile success and actual
  pause/resume behavior are separate results.

The read-only evidence does **not** decide whether the native generator ignores,
honors or rejects the below-threshold flag. The current retentive/dynamic mode
gates should remain unchanged until those separate acceptance results exist.
