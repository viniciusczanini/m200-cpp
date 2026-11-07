# G11 SDK raw-PDU acceptance evidence

This bundle preserves the completed local validation; packaging ran **no tests or builds**. Two unchanged priority cases passed VM/SDK. The added six-method module covers **43 distinct SDK stimuli**, including all nine documented function codes, asynchronous state, strict atomic decoding and poison/flag preservation. It does not qualify an official PLC, network peer or physical interface.

- `sources/`: the exact three reviewed test/binding/registry files. The main repository supplies the SDK headers, pinned in `sdk-pins.json`.
- `vectors.json`:43 unique stimuli, each selecting its final observed attempt and relative request, actual, C++ host, compile and run references.
- `attempts.json`:**all50 attempts**, including48 native compilations, two VM executions, repeated timeout controls and the failed initial harness compilation. Nothing is silently discarded.
- `objects/`: content-addressed, deduplicated JSON and C++ text. Identical requests/actuals share objects; no executables are included. Raw word images and poison masks are separate observations.
- `historical/`: the initial binding and failed attempt. Its transport names `first/second` collided with FB names; the corrected binding uses `natal_raw_primary/natal_raw_alternate`. No expected values changed.
- `evidence/` and `logs/`: recorded results, hashes, commands, revisions and diagnostics. **`evidence/DELIVERY.md` is the historical private handoff**, not current bundle navigation. Its `final/` means today's `sources/`; bare result filenames are now under `evidence/`, and logs under `logs/`.

All published paths are relative. In normalized command metadata, `repo/` means an operator-supplied repository and `work/` means scratch output. Original artifact hashes are retained. Source data/expected values were not rewritten; JSON key ordering is canonicalized for deduplication. Diagnostic path locations are normalized. `logical-path-aliases.json` maps historical attempt locations.

## Reproduce a selected SDK stimulus

Use the pinned SDK headers and a vector's `cpp_ref` from the repository root:

```sh
mkdir -p output
clang++ -std=c++17 -O0 -I sdk path/to/bundle/objects/HOST_HASH.cpp -o output/g11-host
output/g11-host
```

The complete C++ source contains the recorded stimuli and byte-only transport. Compare its JSON with `actual_ref` and inspect `run_ref`; no test generator or private lab path is required. One vector intentionally terminates on an unknown outgoing word: its actual is the recorded process exit, with no `RAW_START`, rather than invented PLC statuses. The known historical compile failure is excluded from the43 final selections but remains fully available separately.

`manifest.json` identifies the package and references `file-inventory.json` for content verification. The six unrelated native-oracle pending cases remain outside this local evidence.
