# Timer and Modbus bit integration

The local `make check` suite passed **496 tests in 202.294 seconds**. All 124 source, SDK, test and fixture inputs stayed byte-identical during the run. The [manifest](TIMER-BIT-INTEGRATION-RESULTS.json) pins the complete input set and log; 15 timer tests and 10 bit-binding tests extend the previous 471-test checkpoint. Focused/review repetitions are not added to that count or to historical distinct-frame totals.

The project importer/exporter now admits separate retentive TON/TOF and dynamic TON only at a one-second base and actual `FunctLevelMan21_0` profile. [Paired official controls](TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.md) established those separate behaviors; [policy evidence](TIMER-OPTION-POLICY-RESULTS.md) records context closure, real-template authority and destination preservation.

READ_VAR discrete-input/coil bits and WRITE_VAR coil bits now use exact official-editor saved/reopened CE40T bindings. Tests cover 17-bit packing, direction, complete local/remote extents, neighboring data, actual constructor/reverse/export paths, malformed fields and existing-output preservation. [Independent review](TIMER-MODBUS-INDEPENDENT-REVIEW.md) found no outstanding defect in this increment.

Other timer contexts, single writes, WRITE_READ_VAR and connected communication Abort/output graphs remain product gaps. Further official binding discovery and actual compiler-generated GUI checks are separate records; this checkpoint does not claim an exchange or physical-controller execution. Program/task scheduling is unfinished, and a newly found pre-existing MastTask validation gap is the immediate next fix. The full parity goal remains active.
