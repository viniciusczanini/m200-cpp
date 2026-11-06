# natal-batch-final-1 — final integrated composition

**PASS of the prepared local subset:** 11 isolated profiles, **24 cases / 201 literal positions × 7 routes = 1,407 observations**, no failures (21.646 s). Preparation and execution each ran exactly once with explicit `--allow-incomplete`.

The seven routes were compiler/Machine, JSON/Machine, generated SMBP/readback/Machine, actual-project reverse/recompile/Machine, rebuilt SMBP/readback/Machine, original C++ PLC_NATIVE SDK, and actual-project reverse C++ PLC_NATIVE SDK. Each route used the same frozen literal case inputs/expectations; all FB identities/configurations and expected resource shapes survived. The complete finite250 inventory retains **45 IDs with passed literal subsets, 41 pending and 164 DEFERRED_VERSION**. Full parity remains **incomplete**.

`make optimization-stress` ran once: **10 budgets / 44 positions PASS**, 7.147 s. Every frozen maximum passed; exact maxima and headroom are recorded in `resource-budgets.json` along with compiled resources/native XML sizes for every batch project.

| Budget | Rungs | IL | M | MW | MW allocation |
| --- | ---: | ---: | ---: | ---: | ---: |
| wire | 1 | 2 | 0 | 0 | 0 |
| packed_io | 2 | 4 | 0 | 1 | 1 |
| same_scan_q | 5 | 11 | 1 | 0 | 0 |
| conditional_write | 6 | 14 | 2 | 0 | 0 |
| nested_numeric_guards | 8 | 18 | 1 | 2 | 11 |
| bool_chain | 6 | 15 | 2 | 0 | 0 |
| bounded_loop | 13 | 28 | 1 | 4 | 11 |
| early_return | 5 | 11 | 1 | 0 | 0 |
| word_alias | 4 | 8 | 0 | 2 | 22 |
| stateless_sr | 10 | 21 | 2 | 2 | 12 |

The unchanged Revoada check ran once: **PASS sampled-clock contract**, 22.482 s, 9,845 phase positions plus14 controls. Source SHA256 remains `37e2386fe336e4ef411ad3eb7ee468c4800083708049b5d22c6b93bf1b17cb7d`. Resulting project:46 rungs /103 IL, M5 unique/span5, MW7 unique/span181, zero timers. First quantum500..600 ms depends on START/clock phase; later600 ms requires all clock levels sampled. This does not establish absolute START-phase or missed-edge recovery.

`native-final-batch.json` is the finite handoff: exact hashes/paths for all11 generated and rebuilt projects, original/reverse C++, case files, resource ownership and selected frames, plus the unchanged Revoada diagnostic artifact. Native editor/simulator/physical phases are **NOT_RUN/PENDING**. Nine preserved native question categories include the original immediate-CD/reset SC history case. Host RTC seeds and virtual scan intervals do not establish an official-native injection route or scan count from held GUI inputs.

All **72 compiler/SDK pins, 294 test/example input pins and 98 batch manifest pins** remain unchanged. The seven integration descriptor comparisons confirm only `main_integration.notice/compiler_pins` differ from frozen7; variants/case selections/oracles are unchanged (`descriptor-confirmations.json`). No core/root/source/test/oracle edits, GUI, Wine or CI occurred. Fullunit and `make examples` were not repeated.

Artifacts: `summary.json`, `batch/manifest.json` (250 classifications), `batch/results.json` (seven-route observations), `native-final-batch.json` (exact project handoff), `resource-budgets.json` (costs/maxima), and one command JSON/log per requested execution. Revoada and generic budget products remain at their exact paths recorded there under the frozen source's ignored `output/` directory.
