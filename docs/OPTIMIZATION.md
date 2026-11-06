# Compiler optimization

The compiler reduces Ladder overhead automatically while preserving source order and observable scan behavior. The comparison below uses the **same C++ file**, SHA256 `37e2386fe336e4ef411ad3eb7ee468c4800083708049b5d22c6b93bf1b17cb7d`, compiled by baseline `1bfd233` and the 703-test checkpoint `13cfb9e`. Its reflection/shift algorithm and real loops are unchanged.

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

## Adjacent guard checkpoint

The next compiler change removes repeated captured guards, preserving the comparison once in its original position. It only rewrites adjacent, unlabelled rungs with a private scalar guard and a private result that is dead after its consumer. Flags, shared/partial guards, live values and label entries remain protected. Final operand validation still applies after virtual addresses are allocated.

The same application now uses **51 rungs / 114 IL**, compared with 55/126 at `13cfb9e` and 122/261 at the original baseline. The nine new regression methods and independent review cover false guards, flags, virtual numeric operands, aliasing, values live into the next scan and existing indexed-contact refusals. **712 unit/regression tests passed in 214.046 s**, with 740 inputs unchanged during that run. `make examples` also passed.

Ten [frozen generic benchmarks](../tests/optimization/README.md) now enforce explicit upper bounds on rungs, IL and memory. Their 44 literal trace positions pass through IL, exported/reimported SMBP, recovered C++ and original/recovered native SDK execution. Nested numeric guards improve from 13/31 to 10/23; the other nine cases keep their costs. Run `make optimization-stress` locally. The runner also rejected a deliberately impossible zero-rung wire budget.

The sampled-clock application passes 9845 positions across four START phases plus 14 button-control positions. Its recovered-C++ rebuild is now 60/133 and passes 2461 sequence positions plus 14 controls through local VM/native checks. Overlapping traces are not added into one larger total.

The exact 51-rung CLI artifact opened as Ladder with **No error**, was officially saved with identical 51/114 instructions, then freshly reopened after another project with No error. Its saved bytes reached Online/Run in the official simulator: START lit Q0, observed outputs advanced, STOP turned them off, and held START did not rearm after STOP release. Official cleanup removed the simulator process and TCP502 listener. Reverse conversion of the official save produces exactly the already tested audit-C++ bytes.

A 75-frame read-only capture decoded 67 one-hot frames; eight were refused by the unchanged font decoder's Q4 glyph threshold. These are sampled movement/button observations, not a complete automated visual-cycle or physical timing pass. The existing untrusted-DLL banner remains unchanged. See the [new results](validation/GUARD-FUSION-RESULTS.json) and the optimization-first [completion plan](superpowers/plans/2026-11-06-compiler-finish.md).

## Private emission cleanup

The next frozen checkpoint emits **48 rungs / 108 IL lines** for the same C++: one coalesced private i16 self-copy is removed, followed by two unread label scratch stores. Labels attach to the following real statement while keeping that statement's source origin. Public stores, float copies, live scratch values, terminal/consecutive labels and unknown contexts remain protected. Indexed/shared views and SR contexts keep their earlier emission. Native M-edge contacts retain anchors because their history belongs to physical cells across scans; input-edge contacts remain eligible.

Twelve focused regression methods cover dirty storage, flags, NaN, indexed-image limits, label entry and source origins. Independent review exposed the M-edge history counterexample; its new test failed before the guard was added and passed afterwards. The final suite passed **724 tests in 214.974 s**, with 763 pinned inputs unchanged. The final examples and ten generic budget cases also passed. See the [exact result manifest](validation/EMISSION-CLEANUP-RESULTS.json).

The genuine 48/108 CLI artifact opened, was saved, and freshly reopened with No error. The saved project reached official simulator RUN, displayed Q0 and later Q5, and passed STOP plus held-START no-rearm observations; official cleanup removed its process/listener. The saved-file reverse rebuild is 55/123 and passes 2461 sequence positions plus 14 controls locally. Physical timing remains pending.

The editor's backward-jump advisory on `%L0` remains visible. [Exhaustive local checks](validation/REVOADA-LOOP-BOUND-RESULTS.json) of all 65536 signed-i16 phase values find at most nine actual cursor increments/shifts, with maxima at phases 10/11. The reflection limits position to 0..9 and cursor starts at zero. All cases pass a 190-instruction local VM budget; that count is not a physical watchdog or execution-time guarantee. Invalid phase injections prove termination under the test conditions, not an application recovery policy.

## Native literal contacts

The compiler now uses the installed editor's native `LD 1`/`LD 0` forms for ordinary series rungs, represented as `Short`/`Open` Ladder elements. This eliminates the two materialized constant bits and their initialization rungs. The unchanged clock example emits **46 rungs / 103 IL lines / five M cells**; its seven MW cells still require extent 181. The capacity regression `BitMemory{1024}` plus `write_word(0,1)` now compiles without any private M cell.

The native test exposed an operand restriction: `LDN 0/1` and `ANDN 0/1` are rejected by the installed editor. Export canonicalizes them to positive `LD`/`AND` with the inverse digit before the series fast path, retaining every preceding evaluation. Actual native saves bind start-column and subsequent-column `Short`/`Open`, including clearing coils. Forged types, descriptors, coordinates and connections are rejected.

Block pins and native SR contexts retain their separately qualified memory-contact profiles. A direct-IR Timer with a literal pin is normalized to that profile. This change does not infer additional block, subroutine or native END graph bindings. Ten new tests cover capacity, dirty retained outputs, packed-output initialization, both literal values, negation, native saved graphs, reverse/native execution and Timer profile isolation. An independent review also checked SR, indexed S20 effects, NaN short-circuiting and original-IL audit hashes.

Communication rungs retain their original pins even when another expression forces whole-program normalization. A mixed-path regression keeps unbound raw digit Execute/Abort predicates refused while a normal M-contact control still exports. This prevents constant materialization from widening native Modbus admission.

The frozen release passed **741 tests in 205.817 s, zero skips**, with 286 pinned inputs unchanged. Examples and the ten portable size budgets passed. The exact 46/103 file opened with No error, was saved and freshly reopened, then reached Online/Run with Q0→Q9 movement, STOP and held-START no-rearm. Its actual saved reverse rebuild is 51/113 and passes 2461 sequence positions plus 14 controls locally. All 65536 injected i16 phases terminate within nine shifts under a 185-instruction local VM budget. [Exact artifacts and observations](validation/NATIVE-LITERAL-CONTACT-RESULTS.json) retain the advisory and all scoped limits.

## Native Register capacity

Register calls use stable native I0 pins directly in the isolated MAST profile; mutable expressions remain captured before the update. Adjacent unconditional private i16 snapshots of a Register I/O word can feed a single immediate literal comparison directly. This narrow fusion requires exactly two references and excludes labels, SRs, indexing and word-bit shared views.

Both changes correct real capacity failures: a full 1024-bit user image can still call a Register with native I0 pins, and a full 8000-word image can still compare a Register word without a scratch MW. Captured values that survive a later Register mutation remain stored. The unchanged dual FIFO/LIFO example drops from 34 rungs/80 IL, 3 M/1 MW to **22 rungs/56 IL, 1 M/0 MW**. Its two native sixteen-word queues are separate controller resources.
