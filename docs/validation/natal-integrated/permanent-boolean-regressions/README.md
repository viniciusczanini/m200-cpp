# Permanent Boolean regressions

`tests/test_natal_boolean.py`:8 portable unittest methods,8PASS in one execution on a private full copy of natal-combined-6. Only the new module ran. All72 compiler/SDK pins match before/after; the original frozen tree and root/tested module bytes are unchanged.

Module SHA-256: `84d78c9c5d200ce854bd167eb90e1a4199eb1d91a409dd7f889d325d5daf0c1d`.

Command: `python3 -B tests/test_natal_boolean.py -v`, with cwd recorded in `command.json`. Logs are `stdout.log`/`stderr.log`; `results.json` and pin snapshots fix provenance. Root received only the new test module. No full suite, GUI/CI, other test/core edits, commit or push.
