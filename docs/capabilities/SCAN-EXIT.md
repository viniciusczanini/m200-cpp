# Scan exit: C++ return and native END instructions

`return;` now ends the current `scan()` execution. Statements already executed
keep their effects; later statements are skipped. The next scan can execute
normally. This feature does not stop the controller.

The documented native instructions are `END` (unconditional), `ENDC` (exit when
the current Boolean accumulator is true) and `ENDCN` (exit when it is false).
END finishes the current execution level: in a master/periodic/event task it
finishes that task execution; in a subroutine, UDF or UDFB it returns to its
caller. Normal scanning updates outputs and proceeds to the next scan; periodic
scanning retains its period. See the official
[Generic Functions Library Guide, EIO0000003289.04, pp.60–61](https://www.se.com/us/en/download/document/EIO0000003289/).

## Implemented domain

The current toolchain models the supported master-task program. It accepts a
bare C++ return, including inside nested conditionals, loops and supported
label/goto paths. A return exits the scan, rather than just the innermost loop.
An expression such as `return plc::output(0,true);` remains outside the subset;
write the call followed by `return;` instead. Existing pure Boolean helpers
retain their separate expression-return rules.

The IL reader, JSON round trip, VM and reverse translator support operand-free
END/ENDC/ENDCN. Conditional exits use the accumulator at that exact instruction.
An unconditional END can occupy its own rung and ignores a preceding false
accumulator. The VM completes its normal scan bookkeeping after an exit;
skipped operations are not counted against the local execution budget. That
budget is a local protection, not a model of physical watchdog timing.

C++ output calls write a compiler output image. Early returns therefore jump
to a shared epilogue that commits the image. This preserves output writes made
before return and retains outputs whose writes were skipped. Native C++ SDK
execution uses ordinary language return; no new public SDK function is needed.

Native input-edge sampling still advances at scan entry, even when a later
early exit skips the contact. Stateful expression-edge history advances when
that expression actually executes. A skipped timer block is not given an
invented update by the exit implementation.

## Ladder export and remaining evidence gates

The native graphical END/EndCn XML binding is **unverified**. An enum name does
not establish instruction binding, descriptors or a complete saved graph.
The importer continues to reject graphical END-family rungs explicitly, while
accepting supported IL-only rungs with Ladder unselected.

An initial ENDC diagnostic has now opened with No error, been converted to
Ladder and saved by the official editor. It uses an `End` action after its
contact. This single observed fixture is recorded in the
[official evidence](../validation/OFFICIAL-EDITOR-RESULTS.json); implementing
and validating every END-family binding remains the next task. The gate is
still active.

Export instead lowers native END-family instructions to the existing supported
conditional Jump graph and one shared final scan-exit anchor. This is a derived
control-flow translation. It is not evidence that the native End graph is
accepted by the official editor. C++ returns similarly use a shared jump to
the output-commit epilogue. Each path may need a spare label and private anchor
storage; exhausting those resources is reported as compiler overhead, not as
proof that the PLC cannot express the algorithm.

Executable instructions after an unconditional END in the same rung are
rejected, as required by the official
[Operating Guide, EIO0000003281.04, pp.49–51](https://www.se.com/ca/en/download/document/EIO0000003281/).
The current reversible subset also rejects an END-family instruction inside
open Boolean parentheses or an unclosed MPS/MPP region. These are toolchain
domain boundaries, not a newly claimed controller limit. ENDT requires Grafcet
transition context; STOP, subroutine/UDF/UDFB execution and native task
scheduling remain separate parity work.

## Local checks and disposable acceptance candidate

Run the independent expected-output and memory-history checks with:

```sh
python3 -m unittest tests.test_scan_exit -v
```

They compare original IL, JSON, normalization, native C++, reconstructed C++,
recompilation and actual exported XML. They cover conditional polarity, writes
before/after exits, retained outputs, next-scan behavior, nested loops/goto,
timer and edge history, malformed instructions, unverified native graphs and
label overhead with destination preservation. Local agreement does not certify
Schneider editor, simulator or physical PLC behavior.

The disposable source/project under `output/editor-validation/scan-exit` uses
I0.0 as payload/pulse, I0.1 as the early-exit gate and I0.2 as reset. Q0.0 is
written before both returns. Q0.2, MW220 increments and Q0.3/4 count indicators
are updated after the early-exit return. The exact trace, independent oracle,
hashes and manual observations are recorded alongside that candidate.

That manifest describes a captured local source snapshot. Its source hashes
remain historical when another module changes. A later combined validation of
the current working tree is separate evidence; the candidate's exact project
hash still identifies the file to open in the official editor.
