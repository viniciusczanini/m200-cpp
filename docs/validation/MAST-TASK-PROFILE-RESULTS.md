# MastTask profile guard

2026-11-06. **506 tests passed in 199.031 seconds**, with all 108 source/input pins unchanged across the full local run. Ruff check and format checks passed for all 96 Python files. This checkpoint adds ten regression methods to the published 496-test base, commit `8a80a7c8b3e82b7da11bd5a565a305ea651dc990`; its historical results remain unchanged.

The importer/exporter previously accepted periodic-master settings and malformed MastTask scalars while the execution model retained no scheduling context. [config.py](../../m200/config.py) now requires one explicit MastTask containing canonical `UsePeriodScanMode=false` and `PeriodScan=100`, the exact inactive profile observed in the authentic CE40T and synthetic templates. Both fields are required. Active periodic mode, malformed values, missing/duplicate fields, unknown fields/attributes and nested scalars are rejected. Actual template fields remain authoritative over opaque Program metadata.

Other canonical inactive periods are reported as an **unverified tool profile**, without implying a PLC limitation. The [M200 guide](https://www.se.com/ww/en/download/document/EIO0000002019/) pp.26–28 documents a 1..150 ms master period and prints a 10 ms default. The [Operating Guide](https://www.se.com/ww/en/download/document/EIO0000003281/) pp.56–57 and installed constructor use 100 ms; the saved inactive profile also retains 100. The guard preserves that observed setting rather than silently rewriting it. It adds no periodic scheduler or claim of 1 ms timing at any functional level.

The promoted TDD run exercised ten methods and reproduced 35 failing negative subcases, with no errors. The guard made all ten pass in 0.437 seconds. Tests cover valid profile preservation, canonical values, missing/duplicate/malformed structure, template authority, and unchanged existing destinations or absent destinations on rejection. The final full command was `make check`, expanding to `python3 -m unittest discover -s tests -v`.

Independent review found no new guard defect. It passed 333 configuration cases, including the complete 300-case matrix of false/true × periods 1..150, eight complete export authority/atomicity cases, and the ten focused tests. The reviewer independently checked the 506-test log and all 108 pins without repeating the full suite.

A **pre-existing generic parser limitation** remains separate: non-whitespace XML child-tail text can be accepted after a valid mode field. The actual interpreted mode/period stay false/100; no scheduling authorization or field override was found. This result therefore does not claim complete rejection of all mixed XML content. No broader parser change was included in this snapshot.

| Changed source | SHA256 |
|---|---|
| `m200/config.py` | `5411e6a28bd67da9a45c1660f1c62673443b249ac76948ede80b57c6e322f73e` |
| `tests/test_mast_task_profile.py` | `6bcbc398b4a2048c44a92433dc9d1f03755b5186814c0136fea4cdde04125d93` |

Exact log, source-pin and independent-review hashes are recorded in [MAST-TASK-PROFILE-RESULTS.json](MAST-TASK-PROFILE-RESULTS.json). Raw local evidence is under `output/diagnostics/mast-task-profile-2026-11-06/` and `output/reports/mast-task-independent-review-2026-11-06/`.

Full parity still requires periodic tasks, events, priorities/preemption and native SR/UDF/UDFB/Grafcet contexts. See [native program structure research](../capabilities/NATIVE-PROGRAM-STRUCTURE-RESEARCH.md). No GUI, simulator, serial/network exchange, PLC operation or physical timing proof was added by this validation fix.
