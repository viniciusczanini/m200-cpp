# Subroutine compiler checkpoint

2026-11-06. The C++/SDK, typed contexts, VM, reverse conversion, source maps and native export are integrated for the [documented subroutine profile](../SUBROUTINES.md). The full copied regression passed **684 tests in 224.974 s, zero skips**; all 727 pinned inputs matched before/after. The separate 56-method subroutine run is included in that total. Focused independent review found no blocking issue. Validation was local; no CI ran.

The genuine [C++ example](../../examples/editor_validation/cpp_subroutine_implicit.cpp) was compiled through the CLI using the authentic ordinary CE40T template. Source IR, actual exported XML and reconstructed/recompiled C++ matched four literal local positions: I0 off gives MW0/1/2=30/0/10 and Q0..3=0010; I0 on gives 30/1/20 and 1110. Native reference checks covered the output bits. Input 1 does not affect this example.

| Artifact | Bytes | SHA256 |
|---|---:|---|
| C++ source | 468 | `0bc464f7dc379e5356ef559ddd976da8cb16c7ab3e3de814de8185b400e77125` |
| CLI-generated SMBP | 176597 | `8b69d70a73702e9660a4c774c6213b9e2826fb2025bb89d3baa329ace5fe79bd` |
| Official editor save | 182326 | `3ca0a94ac5a87c67b7cce91a0f8cd9e9d338bf20262c3c8df8243bd7bebe9f8f` |

The exact generated project opened with Programming **No error**. Master and leaf Ladder were inspected; Ctrl+S and a fresh saved-clone reopen also showed No error. These stages were personally observed by the lab operator in Machine Expert Basic under Wine. Saved readback preserves Master IL and each callee's number/name/section/body. Native container order may change, so comparisons use execution context rather than one global XML instruction sequence.

Master normalization captures call predicates and reserves scratch across every context; it preserves independent leaf bodies and current-level returns. A deliberate Master-only scratch-reservation fault was caught by the local oracle. Export rejects active-SR templates, unrequested staged callees and unsupported profiles before replacing the destination.

The exact generated candidate then ran in the official local simulator: input 0 went 0→1→0 and Q0..3 showed **0010→1110→0010**, with No error / Online / Run. These are three sampled software phases, not a scan count. Official MW watch values were not observed; the word values above are local oracle results. Cleanup returned No error / Not Connected, removed the panel and left neither the trial simulator process nor its TCP502 listener. Physical CE40T validation remains separate. The [compact manifest](SUBROUTINE-COMPILER-RESULTS.json) pins the three panels and fresh-reopen capture. Historical diagnostics and the earlier 628-test foundation remain distinct; the full parity objective is unchanged.

Local evidence: `output/diagnostics/subroutine-end-to-end-prototype-2026-11-06/{genuine-export-candidate,full-regression-overlay}`. Full regression log SHA256: `16d682d6b949ba4475971a5a78e80a756aeaf177d31a1ced9716d332f8301089`.
