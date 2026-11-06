# Compiler optimization

The compiler reduces Ladder overhead automatically while preserving source order and observable scan behavior. The comparison below uses the **same C++ file**, SHA256 `37e2386fe336e4ef411ad3eb7ee468c4800083708049b5d22c6b93bf1b17cb7d`, compiled by baseline `1bfd233` and the validated compiler. Its reflection/shift algorithm and real loops are unchanged.

| Resource | Before | After |
|---|---:|---:|
| Rungs | 122 | 55 |
| IL instructions | 261 | 126 |
| Distinct M cells | 22 | 7 |
| Distinct MW cells | 7 | 7 |
| Required MW extent: highest index +1 | 4006 | 181 |

The seven used words include the diagnostic at MW180, which imposes extent 181. This is address coverage, not 181 used words or a reduction of the controller's 8000-word capacity.

Three generic changes produce the reduction:

- Ordinary inputs use the PLC input image. Scalar/packed output writes update its output image in source order; `output_state` and packed reads see the latest writes. Physical output update follows the admitted isolated Master scan. S13 initialization remains for used channels when required, including conditional writes and read-before-write; unused channels are preserved.
- CFG liveness removes dead, pure, complete private-bit stores before copy fusion. Timers, edges, numeric/indexed reads, explicit writes, partial/group writes and labels remain protected. This DSE pass skips subroutine programs until it has contextual liveness summaries.
- Storage uses the lowest available cells with the same reservations, widths, interference and contiguous-group rules. Explicit addresses, whole memory images and communication buffers remain reserved. Compiler-private physical addresses are not an ABI.

**703 tests passed in 222.366 s, zero skips**, with 746 pinned inputs unchanged. An initial run exposed three stale private-address assertions; their reviewed corrections passed targeted checks before the final run. Independent focused reviews and `make examples` passed. The [compact results](validation/OPTIMIZATION-RESULTS.json) pin the evidence.

The exact 55/126 candidate opened with Programming No error and was saved. The simulator reached Online/Run; START showed Q0 on and the user confirmed motion. Fresh reopen and a quantitative complete cycle were not performed for this optimized candidate; physical PLC validation remains separate. The officially saved project passed local reverse/recompile/native checks over 2461 sequence positions and 14 control positions. Its reconstructed 72/165 project has not been opened in the editor.

The [example's](../examples/christmas/revoada20_clock_10.cpp) sampled-S5 clock contract remains unchanged: first quantum depends on phase; missed complete periods are not inferred. Static instruction counts do not establish physical timing or broader task/immediate-I/O behavior.
