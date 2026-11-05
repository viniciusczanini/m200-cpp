.PHONY: check examples stress
check:
	python3 -m unittest discover -s tests -v
examples:
	python3 -m m200 compile examples/blink.cpp -o output/blink
	python3 -m m200 check examples/latch.cpp --trace examples/trace.json
	python3 -m m200 compile examples/numeric_control.cpp -o output/numeric-control
	python3 -m m200 check examples/numeric_control.cpp --trace examples/trace.json
stress:
	python3 tests/stress/run.py
