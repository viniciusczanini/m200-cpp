# Permanent G06/G08 regressions

Created only `tests/test_natal_subroutines.py`: six portable methods using repository fixtures and the existing native probe helper. Covers all four literal conditional SR returns through native project/reverse/recompile, the byte-identical original SC and composed SBR/SC/Drum repros, labelled/unlabelled Drum F, seven forged graph/config variants with atomic staged-write refusal, and retention of typed Program configurations during mixed leaf normalization.

Executed in a private clone of **natal-combined-7**, never in the closed freeze. One complete module execution: **five PASS**, plus one test-selector failure before checking SC geometry. The initial selector matched an auxiliary contact outside `%SC0`; it now selects the actual `BLK %SC0` rung. Literal row1, source/frames/expected values stayed unchanged. The corrected method alone then **PASS** (1.562 s); the other five were not replayed.

Final module SHA256: `82521a18c4c8fcd6534ef87fb3c5b4bb71608503de50dbaa1fdc39cadb5440dc`. All72 private and closed-freeze compiler/SDK pins remain unchanged. Of295 private test/example inputs, the sole change after the initial snapshot is the documented selector in this new module. Root/private module bytes match; original SC/composed repro source bytes match their verified freeze5 inputs.

Exact commands, initial/focused logs, old/new module hashes and before/after input pins are preserved here. No other root files, compiler/SDK, fullsuite, GUI, Wine or CI were changed/run. Local regression preservation only; no new capability or native qualification.
