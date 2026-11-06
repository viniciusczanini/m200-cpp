# Timer-property stress: 10 ms runner repair

2026-11-06. Independent review found no actionable defects in the stress-runner repair. The supplied full regression log records **471 tests passing in 184.227 seconds**. Its 471 test entries, final OK and source pins were independently checked; the full suite was not rerun during review.

The exact snapshot is commit `6bf242c15c784203a14506b897bfdd66f3054530` plus these two files:

| File | SHA256 |
|---|---|
| [timer_properties.py](../../tests/stress/timer_properties.py) | `8d1353d38757664145ea233273d629faa623b04e946e33598ca65b9590085f65` |
| [test_timer_property_stress.py](../../tests/test_timer_property_stress.py) | `33c85057f20ddd3d1d619a413db8ef2630feee3d584d2e60a9c583dd29c6eabd` |

All 73 source pins match: 71 files from that commit and the two reviewed files above. Later timer-policy changes are outside this snapshot. Full source/log hashes and review details are preserved in [TIMER-PROPERTY-10MS-RESULTS.json](TIMER-PROPERTY-10MS-RESULTS.json); raw logs are ignored local artifacts under `output/diagnostics/timer-property-stress-10ms-2026-11-06/`.

## What changed and what ran

The runner still expected 10 ms XML export to fail after that binding had become available. It now exercises original and reverse XML import/VM checks for every base, and accepts `--output` for a fresh diagnostic report. Product timer implementation and policy gates were not changed by this repair.

The supplied RED run failed both new CLI tests. The supplied GREEN run passed both in 31.387 seconds. A separate fresh stress invocation passed 16 cases: TON/TOF/TP at 1, 10, 100, 1000 and 60000 ms, plus one isolated indexed timer-preset assignment from the pinned original project.

**8,192 frame evaluations repeat the existing seeded workload; they are not additional distinct frames.** Each case has 512 frames. Reruns and the six comparison stages must not be added to a distinct-frame total. The six stages compare IL VM, native C++, reverse C++, recompiled IL VM, original XML/import/VM and reverse XML/import/VM against expected results. The three 10 ms cases now execute both XML stages rather than reporting a serialization gate.

The original indexed source remains TM221ME16R/G, SHA256 `a4307729f0864133e414517ef49c37e6648f29d7403a8f9737e2f7367461a738`. Only its assignment and TM1 configuration are isolated; the whole foreign project is not imported or relabelled.

## Independent checks

- The two focused CLI tests passed again in **32.168 seconds**, including an actual fresh report and rejection of an existing report without replacement.
- Hand-derived 10 ms traces checked a two-tick preset at elapsed 9/10/19/20 ms through all six stages: seven TON frames, seven TOF frames and six TP frames. The TP trace drops its input before expiry and retains the pulse. Expected Q, wired output, value bits and preset bits were supplied manually, without using the runner's event oracle.
- A spy observed both actual XML writes for each kind: all six serialized `TenMilliSeconds`. Changing only that XML base to `OneHundredMilliSeconds` was detected at frame 3 independently in the original XML stage and the reverse XML stage. These are executable serialization checks, beyond examining result metadata.
- A file created after the initial destination check survived the final exclusive open unchanged. An existing directory was rejected before stress execution and retained its contents. Expensive execution was stubbed only for this filesystem race check; the actual XML paths were exercised separately above.

VM, native harness and oracle all evaluate the current scan before adding that frame's `dt_ms`; the review found no time-order change. Existing-output preservation follows exclusive creation. This does not claim that writing a fresh report is a transactional operation under every I/O failure. The legacy default destination remains unchanged, so fresh evidence must use `--output`.

## Historical evidence and limits

The original reports remain byte-for-byte unchanged, verified before and after independent checks:

| Historical report | SHA256 |
|---|---|
| `TIMER-PROPERTY-STRESS-RESULTS.json` | `190531e18e869974dbff6b2827041a290e2a2481fe915bd69eb0eb5ef984d526` |
| `TIMER-MODE-STRESS-RESULTS.json` | `2422e4df23cfe7c1d4c844b34e651490bb444c1862805f6c79b3ccd093b0d00d` |

The source-pin file hash is `34043a74e0cce8b3b72f0d9922dc1d3066e638424eb15a5bb61c9799fa8ffedc`; the full regression log hash is `94de485315c8ec045bfce6e71d32e28fcb02503c9a79479b3e5fac838f01cda2`; the fresh stress-result hash is `958f7b76e58fea026f68a9075254d2974795dae48ca036eed176a0392a99ba9b`.

These results cover the local synthetic-profile, nondynamic, nonretentive workload. They add no official editor/simulator execution or physical timing proof, and do not expand retentive/dynamic timer support.
