# Code generation budgets

Run `python3 tests/stress/optimization.py` locally. Ten frozen C++ programs cover direct and packed I/O, output-image ordering, conditional writes, nested numeric guards, boolean chains, a bounded loop, early return, word aliases and a stateless SR.

`cases.json` stores manually derived output/word expectations and explicit upper bounds for rungs, IL, distinct M/MW cells and required word extent. The runner checks compiled IL, exported/reimported SMBP, reconstructed C++ and original/reconstructed native SDK execution. Native checks observe outputs; the three VM routes also inspect the named words. Forty-four distinct trace positions are shared across those routes, not multiplied into a larger scan total.

The source hashes prevent an application rewrite from silently improving compiler measurements. When a deliberate benchmark change is necessary, review its oracle and budgets explicitly. These small local cases are regression gates; they do not prove global optimality, official editor acceptance or physical timing.
