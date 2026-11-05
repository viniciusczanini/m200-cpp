.PHONY: check examples stress public-fetch public-check public-flow-fetch public-flow-check
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
stress:
	python3 tests/stress/run.py
	python3 tests/stress/control_flow.py
public-fetch:
	python3 tests/public/fetch.py
public-check:
	python3 tests/public/run.py
public-flow-fetch:
	python3 tests/public/fetch.py --manifest tests/public/control-flow-manifest.json
public-flow-check:
	python3 tests/public/control_flow.py
