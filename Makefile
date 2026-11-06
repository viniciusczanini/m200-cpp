.PHONY: check examples stress digital-io-stress expression-edge-stress counter-stress public-fetch public-check public-flow-fetch public-flow-check public-indexed-fetch public-counter-fetch
check:
	python3 -m unittest discover -s tests -v
examples:
	python3 -m m200 compile examples/blink.cpp -o output/blink
	python3 -m m200 check examples/latch.cpp --trace examples/trace.json
	python3 -m m200 compile examples/numeric_control.cpp -o output/numeric-control
	python3 -m m200 check examples/numeric_control.cpp --trace examples/trace.json
	python3 -m m200 compile examples/modbus_read.cpp -o output/modbus-read
	python3 -m m200 check examples/modbus_read.cpp --trace examples/trace.json
	python3 -m m200 compile examples/loops.cpp -o output/loops
	python3 -m m200 check examples/loops.cpp --trace examples/trace.json
	python3 -m m200 compile examples/indexed_words.cpp -o output/indexed-words
	python3 -m m200 check examples/indexed_words.cpp --trace examples/trace.json
	python3 -m m200 compile examples/dynamic_arrays.cpp -o output/dynamic-arrays
	python3 -m m200 check examples/dynamic_arrays.cpp --trace examples/trace.json
	python3 -m m200 compile examples/dynamic_bits.cpp -o output/dynamic-bits
	python3 -m m200 check examples/dynamic_bits.cpp --trace examples/trace.json
	python3 -m m200 compile examples/timer_properties.cpp -o output/timer-properties
	python3 -m m200 check examples/timer_properties.cpp --trace examples/trace.json
	python3 -m m200 compile examples/timer_modes.cpp -o output/timer-modes
	python3 -m m200 check examples/timer_modes.cpp --trace examples/trace.json
	python3 -m m200 compile examples/bit_objects.cpp -o output/bit-objects
	python3 -m m200 check examples/bit_objects.cpp --trace examples/trace.json
	python3 -m m200 compile examples/native_edges.cpp -o output/native-edges
	python3 -m m200 check examples/native_edges.cpp --trace examples/trace.json
	python3 -m m200 compile examples/expression_edges.cpp -o output/expression-edges
	python3 -m m200 check examples/expression_edges.cpp --trace examples/trace.json
	python3 -m m200 compile examples/counter.cpp -o output/counter
	python3 -m m200 check examples/counter.cpp --trace examples/trace.json
stress:
	python3 tests/stress/run.py
	python3 tests/stress/control_flow.py
	python3 tests/stress/indexed.py
	python3 tests/stress/dynamic_arrays.py
	python3 tests/stress/timer_properties.py
	python3 tests/stress/timer_modes.py
	python3 tests/stress/native_logic.py
	python3 tests/stress/bit_objects.py
	python3 tests/stress/digital_io.py
	python3 tests/stress/native_edges.py
	python3 tests/stress/expression_edges.py
	python3 tests/stress/counters.py
counter-stress:
	python3 tests/stress/counters.py
expression-edge-stress:
	python3 tests/stress/expression_edges.py
digital-io-stress:
	python3 tests/stress/digital_io.py
public-fetch:
	python3 tests/public/fetch.py
public-check:
	python3 tests/public/run.py
public-flow-fetch:
	python3 tests/public/fetch.py --manifest tests/public/control-flow-manifest.json
public-flow-check:
	python3 tests/public/control_flow.py
public-indexed-fetch:
	python3 tests/public/fetch.py --manifest docs/capabilities/INDEXED-SOURCES.json --corpus research/downloads/indexed-sources
public-counter-fetch:
	python3 tests/public/fetch.py --manifest docs/capabilities/COUNTER-SOURCES.json --corpus research/downloads/counter-sources
