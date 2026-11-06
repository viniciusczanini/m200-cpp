# CLI-generated timer projects in the official editor and simulator

Date: 2026-11-06. Root personally viewed **No error**, saved and freshly
reopened both actual public-CLI products after opening a different project.
Root then ran only the exact editor-saved **watch product**, SHA-256
`7e0dbae16113baf5738f5bf79d8b892a830f570712cd3fc729583aad71519564`, in the
official local simulator. The plain product was never run.

Both products target TM200CE40T at `FunctLevelMan21_0`, using Machine Expert
Basic 1.4 build 484 in the local Mac Wine lab. They contain **105 rungs / 227 IL
lines**. Each editor save preserves normalized IL, typed timer configuration
and its exact template hardware. Default TON Type and false option fields may
be omitted by the editor serializer; raw timer-subtree identity is not claimed.
The watch product also preserves its six Decimal watch rows, `%MW200..205`.

| Product | Original SHA-256 prefix | Editor-save prefix | Saved bytes | Save-stage / fresh reopen |
|---|---|---|---:|---|
| Plain | `5f8594912d882a3f` | `0373d6f41d99e77b` | 468,779 | [View](editor-evidence/timer-generated/plain-save.png) / [Reopen](editor-evidence/timer-generated/plain-reopen.png) |
| Watch | `1653292a94ce9b4e` | `7e0dbae16113baf5` | 470,226 | [View](editor-evidence/timer-generated/watch-save.png) / [Reopen](editor-evidence/timer-generated/watch-reopen.png) |

Root saved writable P: clones with Ctrl+S, copied the completed editor saves
through the filesystem and freshly reopened those saved clones. The original
CLI products remain unchanged. Full identities, original/copy PNG hashes,
source records and host timestamps are in the
[result manifest](TIMER-GENERATED-PROJECT-RESULTS.json).

## Generation and diagnostics

Both builds use the same 1,764-byte C++ input, SHA-256
`7a6819152ed649e9413807c382d4b6e1d8c5f11256111a5add579540c73d39c0`, and
the normal public CLI. The plain command is recorded in its frozen preparation
manifest; the watch build uses the authentic editor-saved timer/watch template.
There were no manual XML option edits in these generated products.

```sh
python3 -m m200 compile \
  output/editor-validation/timer-options-generated/timer_options_behavior.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp \
  -o output/editor-validation/timer-options-generated/build

python3 -m m200 compile \
  output/editor-validation/timer-options-generated/timer_options_behavior.cpp \
  --template tests/fixtures/official_tm200ce40t_timer_options_behavior.smbp \
  -o output/editor-validation/timer-options-generated-watch/build
```

The exact template hashes are `df5a293169d062d5…` for plain and
`5358e5334696e183…` for watch. The source's historical diagnostic/gating comment
was retained to preserve its bytes; it predates admission of these three exact
option contexts and does not describe a manual patch in this stage.

```cpp
plc::Ton retained_on{0, 1000, 20, true, false};
plc::Tof retained_off{1, 1000, 20, true, false};
plc::Ton dynamic_on{2, 1000, 20, false, true};
```

These are three separate instances, each at a one-second base and initial
preset 20. Retention and dynamic mode are not combined. Inputs `%I0.0`,
`%I0.1` and `%I0.2` control TON, TOF and dynamic TON. `%I0.3` calls
`dynamic_on.set_preset(5)`; `%I0.4` restores 20 and has explicit priority if both
preset inputs are held. The source calls `update()` once per timer per scan.

| Diagnostic | Address |
|---|---|
| TON V / P | `%MW200` / `%MW201` |
| TOF V / P | `%MW202` / `%MW203` |
| Dynamic TON V / P | `%MW204` / `%MW205` |
| TON / TOF / dynamic TON Q | `%Q0.0` / `%Q0.1` / `%Q0.2` |
| Five input mirrors | `%Q0.3..7` |
| TON V ≥ 5 / TOF V ≥ 5 / dynamic V ≥ 6 | `%Q0.8` / `%Q0.9` / `%Q0.10` |
| Dynamic P = 5 / P = 20 | `%Q0.11` / `%Q0.12` |
| TON / TOF / dynamic V > 0 | `%Q0.13` / `%Q0.14` / `%Q0.15` |

## Observed official simulator behavior

Root verified Online / applications identical / STOP before official RUN. The
later [RUN target view](editor-evidence/timer-generated/runtime-target-run.png)
shows the watch-save title, No error, Online, RUN, TM200CE40T and simulator
firmware label 1.14.1.0. It also shows the lab's **Untrusted DLL detected**
banner. That environment status is retained in the evidence; neither validation
nor integrity checks were changed for this report. The firmware label is a
simulator report, not evidence from a physical controller.

| Case | Root's settled observations | Actual captures |
|---|---|---|
| Baseline | V/P words `0/20, 0/20, 0/20` | [Baseline](editor-evidence/timer-generated/baseline.png) |
| Retentive TON | V advanced to 1; paused at V4/P20 with IN false and held across captures ≥15.15 seconds apart. After resuming, V20/Q0 on; disabling after completion cleared V0. | [Counting](editor-evidence/timer-generated/ton-counting.png), [pause](editor-evidence/timer-generated/ton-paused.png), [held](editor-evidence/timer-generated/ton-paused-later.png), [V20](editor-evidence/timer-generated/ton-completed.png), [Q0](editor-evidence/timer-generated/ton-completed-panel.png), [cleared](editor-evidence/timer-generated/ton-cleared-tof-held.png) |
| Retentive TOF | Paused at V11/P20 with IN true and held across captures ≥19.85 seconds apart. Resuming reached V20/Q1 off; rearming IN true gave V0/Q1 on. | [Pause](editor-evidence/timer-generated/tof-paused.png), [held](editor-evidence/timer-generated/tof-paused-later.png), [completed words](editor-evidence/timer-generated/dynamic-before.png), [completed Q1](editor-evidence/timer-generated/dynamic-done-panel.png), [rearmed](editor-evidence/timer-generated/final-rearmed.png) |
| Dynamic TON | Before preset change, V1/P20. After setting P5, the table showed V5/P5 and a separate panel showed Q2 on and Q10 (V ≥ 6) on. Disabling cleared V0/P5; restore returned V0/P20. | [Before](editor-evidence/timer-generated/dynamic-before.png), [P5 words](editor-evidence/timer-generated/dynamic-after-preset.png), [Q2 panel](editor-evidence/timer-generated/dynamic-done-panel.png), [clear](editor-evidence/timer-generated/dynamic-cleared.png), [restore](editor-evidence/timer-generated/dynamic-restored.png) |

The GUI refreshes every five seconds. The dynamic panel and word-table captures
are separate samples, approximately 1.17 seconds apart; their V/Q values are
not asserted to belong to one controller scan. Both were captured less than
10.1 seconds after the enable action started, earlier than the original
20-second preset. This establishes active dynamic-preset completion in the
observed run, without establishing clamping, next-tick behavior or precise
enable-to-completion latency. The hold durations are host capture separations,
not precise controller timing. Fifteen observation labels use thirteen unique
PNG hashes: repeated held-value captures can be byte-identical and are not
counted as unique controller scans.

Root stopped simulation through official Commissioning. The
[cleanup view](editor-evidence/timer-generated/simulator-stopped.png) and root's
readback record report the simulator panel absent, the specific simulator host
PID absent and no local TCP 502 listener after cleanup. No external TCP client
or forced memory was used. The report author performed only read-only local
verification and exact file copying.

## Local cross-check and scope

The existing 26-position literal oracle in
[`test_timer_option_bindings.py`](../../tests/test_timer_option_bindings.py)
matched outputs and `%MW200..205` across six VM paths: C++ source, both original
products, both editor saves and the reverse/recompiled product. Native C++
outputs also matched for the source and a reverse of the saved watch product.
These reuse existing oracle positions; they are not additional distinct test
frames or official runtime observations. The reverse/recompiled product has
expanded IL, so raw IL identity is not claimed, and it was not GUI-tested.

All nineteen frozen preparation artifacts were hash-verified. Its earlier GUI
`pending` fields remain unchanged; this separate report supplies the later
observations. Earlier hand-built diagnostics and paired false-option controls
remain in their [separate record](TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.md).
No generated false-option control run is claimed here.

Twenty-one exact PNG copies total 7,800,038 bytes. No full regression suite was
run for this GUI stage; no CI or GitHub Actions was used. This result covers the
three separate modes at the one-second base and actual Man21 profile. It does
not establish other bases, levels, timer kinds, combined options, physical I/O,
output loads or physical controller firmware behavior. Plain-product official
runtime remains pending.
