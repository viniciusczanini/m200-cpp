.PHONY: check examples
check:
	python3 -m unittest discover -s tests -v
examples:
	python3 -m m200 compile examples/blink.cpp -o output/blink
	python3 -m m200 check examples/latch.cpp --trace examples/trace.json
