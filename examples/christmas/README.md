# Algorithmic Revoada20

The preferred `revoada20_clock_10.cpp` uses real phase/reflection arithmetic, a bounded SHL loop and one 16-bit packed output write. There is no frame table and no TON. Q0.0–Q0.9 are the ten groups; Q0.10–Q0.15 remain off. MW180 exposes phase 0–19.

I0.0 START needs a rising edge. I0.1 STOP and I0.2 RESET dominate START, switch all outputs off and reset the sequence. A held START does not rearm. S5/`clock_ms(100)` is captured once per scan and its history is updated even while stopped; six sampled rises advance a unit. In the local clock model the first unit is 500–600 ms depending on START/S5 phase; later units are 600 ms when both clock levels are sampled. The initial position holds two units, so the first visible hold can be 1100–1200 ms. A scan gap below 50 ms suffices for the model's 50% duty; the S5 clock is asynchronous to scans. This design cannot detect missed full periods or infer monotonic elapsed time. It does not claim millisecond phase parity to the original renderer.

`revoada20_compact_10.cpp` is the alternative using two TONs with a 1 ms base: no frame table, same real shift loop, sampled elapsed carry. Its local oracle matches original time boundaries exactly; saturation fails dark and RESET clears it. This alternative needs service within 1999 ms and is not a physical timing qualification. MW180/181 expose cycle elapsed ms/mask.

```sh
./m200c compile examples/christmas/revoada20_clock_10.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp \
  -o output/christmas/revoada20_clock_10
python3 tests/christmas/check_clock_revoada.py
python3 tests/christmas/check_movement.py
```

Tests use frozen vectors from the original Natal renderer and work without the Natal checkout. Optional `--source-root /path/to/Natal` compiles/rechecks the original directly; `check_movement.py --source-root /path/to/Natal --regenerate-vectors` explicitly refreshes its oracle data. Source hashes are in `tests/christmas/oracle_vectors.json`.

Scope: Revoada20/10 only as the current algorithmic implementation. Old baked experiments are preserved under ignored `output/christmas/` as history, not final implementations. No Natal/core changes, SR dependency, CI, physical-PLC or load qualification is claimed. Official GUI/simulator acceptance is a separate root-operated stage.

The current unchanged clock source emits 48 rungs/108 IL lines. Its exact project passed official save/fresh reopen and bounded RUN/movement/STOP observations. The editor warns about the real loop's backward jump. The [bound check](../../docs/validation/REVOADA-LOOP-BOUND-RESULTS.json) exercises every signed-i16 phase value: position remains 0..9 and the loop performs at most nine shifts. The advisory is retained; local instruction budgets do not measure physical watchdog margin.
