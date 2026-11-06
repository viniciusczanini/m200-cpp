# Bare Execute/Abort native Modbus binding observations

All three controlled hand-built candidates completed official IL-to-Ladder conversion, Ctrl+S and a fresh saved-clone Programming reopen after another project, with **No error** personally viewed by root. Independent readback and six exact captures agree. This is native binding evidence, not compiler-generated product or runtime communication proof.

| Form | Execute / Abort | Native saved bytes | SHA256 |
|---|---|---:|---|
| READ_VAR I / FC2 | M20 / M21 | 88863 | `222de155bd4061649a017859f8775322974c3e06b3a85204ff85ae015e35b3e4` |
| WRITE_VAR Q / FC15 | M22 / M23 | 88872 | `1489ad6bdcdde1101708088d37ee2eacb326ee23a3c6ac8c0d91cbe25f51fb7d` |
| WRITE_READ_VAR MW / FC23 | M24 / M25 | 90288 | `ce46d988bcdaf5e9f0add2d17daff51deb0074240a937ca5f85aeed933ea8890` |

Each saved project retains **one rung/six lexical IL lines**:

```text
BLK %<KIND>0
LD %M<EXECUTE>
EXECUTE
LD %M<ABORT>
ABORT
END_BLK
```

The actual native drawing contains exactly **three entities**: ordinary Execute and Abort contacts at `(row0,column0)` and `(row1,column0)`, both Left,Right; the matching ReadVarBasic, WriteVarBasic or WriteReadVarBasic at `(row0,column1)`, **Left**. Each class was inspected in its own saved artifact. The editor adds no OUT_BLK, output stores, connected status coils or synthetic filler lines. This differs from the earlier complete full-pin 27-entity Left,Right binding.

Typed parameters are unchanged: READ I remote17/count17→MW200; WRITE Q MW240→remote73/count17; WR MW300/write17/count2 and remote41/readcount3→MW400. Actual TM200CE40T/Man21 (human 14.0), SL1 master, all allocations, tasks, .NET parameter wrappers, rung names/labels/human comments, program symbols and watch trees are preserved.

For every project the complete typed-tree comparison closes exactly nine real changes: two root identity fields, three IL formatting text fields, one IL→Ladder selection field and three native graph entities. No executable IL or hardware/configuration change is hidden. Restoring only those reported fields reproduces the original candidate tree. All 18 files in the frozen initial package remain byte-identical; only later observed copies are added. Inherited Generated C++/full_pin/UNPROVEN comments remain as historical parent/preparation metadata and do not turn these hand-built derivatives into product output.

Root saved writable P: copies with Ctrl+S, waited for the clean title, cloned actual saved bytes through the filesystem, opened a different project and freshly reopened each exact clone. Saved hashes remain unchanged after reopening. This is not a Save As claim. The [READ reopen](editor-evidence/modbus-bare-abort/read-reopen.png), [WRITE reopen](editor-evidence/modbus-bare-abort/write-reopen.png) and [WR reopen](editor-evidence/modbus-bare-abort/write_read-reopen.png) preserve the final Programming views. [Machine-readable observations](MODBUS-BARE-ABORT-NATIVE-OBSERVATIONS.json) contain all six copied PNG hashes, exact source/saved identities, raw graph fields, typed parameters, full XML deltas and independent readback pins.

No program was RUN, no Execute/Abort was asserted, and no exchange, network client or physical PLC was used. Other predicates, functional/link/object profiles, dynamic fields and runtime cancellation remain unproven. Product graph admission and tests are tracked as a separate implementation stage; this report changes no compiler gate and claims no full-suite or new-test count.
