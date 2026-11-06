# Subroutines

Declare a named `void()` body and a global descriptor, then call it synchronously:

```cpp
#include <plc.hpp>

void leaf() { plc::write_word(0, 20); }
plc::Subroutine sr{0, leaf, "application_leaf", 2};
void scan() { sr.call(plc::input(0)); }
```

The four arguments are the native number, function, native name and independent section number. Numbers are literal integers in 0..63; names must be nonblank XML-safe literal strings; sections are nonnegative Int32 literals. IDs, names and sections must be unique. `Subroutine{number, leaf}` defaults to the function name and section 2 plus declaration order; this is a tool metadata policy, not a mapping from native SR number.

A false call skips the body. An enabled call shares the current scan's inputs, output image, global memory, arithmetic flags, function-block instances and clock. Falling off the body or executing `return;` resumes the caller. Calls may repeat: each enabled call executes the same body with the same state. They do not start a new scan, refresh input images, clone a timer, or reset local persistent state. A Master `return;` still ends its scan after earlier output writes. Source maps, JSONv2 and IL artifacts retain separate Master/callee contexts and origins.

Bodies support the ordinary implemented source expressions, local variables, `if`, native-jump lowering of `while`/`for`/`do`, `break`/`continue`, labels/goto and early returns. Timer, Counter, Register and communication APIs retain their established configuration and instruction restrictions. One Timer/communication update source location may be invoked repeatedly through its SR; duplicate update locations retain the existing diagnostic. Properties may be observed from other contexts. Private scratch uses call/return CFG liveness; persistent storage stays unique and explicit addresses stay reserved. No SR body is inlined or unrolled to implement calls.

Native label identities remain unique across the application (%L0..63), and each jump must resolve in its own execution context. Labels, compiler comparison guards and Master exit anchors share that real capacity. Indexed-word accesses use the complete shared word image, including direct addresses in every context.

## Implemented native export path — G06 unvalidated extension

TM200CE40T at actual Man21 (`FunctLevelMan21_0`), one Master section 0 and up to 64 independent SR wrappers with distinct names and sections. A native SR section cannot collide with Master section 0. Existing canonical normal `%M` call contacts (0..1023) and the observed I0.0 predicate are retained; other source predicates are materialized into memory before the call. Supported stateful graphs use the existing Timer/Counter/Register/communication serializers in each body. Compound and wide predicates are lowered to coherent series rungs. `END`/`ENDC`/`ENDCN` in an SR remain local returns; Master END lowering is not applied to them.

An active supported SR template can supply configuration, but all its executable Master/SR bodies are replaced by the requested Program; unused inherited SRs are removed. Unknown configuration and task/event fields still fail. The reverse path reconstructs one global instance per configured resource and one body/descriptor per actual native SR. SR origin payloads in comments carry provenance only; InstructionLines remain authoritative for code. Full communication origin groups stay scoped to their body.

Native SR-to-SR nesting is prohibited by Schneider, including guarded or unused bodies. Calls in Boolean parentheses/MPS ranges or before a same-rung continuation remain refused; rung-terminal calls resume at the next caller rung, which performs a fresh load. This avoids claiming an unspecified accumulator restore. Indexed-bit native export, additional task/event execution, UDF/UDFB calls and native structured IF/FOR metadata remain separate gaps. No watchdog timing guarantee is inferred from the local VM instruction limit.

The [genuine example](../examples/editor_validation/cpp_subroutine_implicit.cpp) and [historical compiler results](validation/SUBROUTINE-COMPILER-RESULTS.md) establish only the earlier one-stateless-leaf profile. The new [multiple/stateful/loop example](../examples/subroutine_contexts.cpp) is a usage contract, not an executed test. G06 ran no tests, builds, generators, editor or simulator. Wider layouts and their composition await the integrated local checks and final exact-artifact editor/simulator campaign; physical PLC validation remains separate.

Sources: local primary manuals `research/downloads/manuals/EIO0000003289.txt`, printed pp60–62 and 65–66 (current-level END, jumps and terminal SR call, no nesting); `EIO0000003281.txt`, pp49–51 and 64–65 (reversibility, labels, Free POU identities); `EIO0000002019.txt`, pp24–28 (M200 resources/tasks). Wrapper fields and call geometry reuse the exact CE40T SR0/SR63 fixtures and their existing provenance, not newly observed editor acceptance.

```sh
./m200c compile examples/editor_validation/cpp_subroutine_implicit.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp -o output/subroutine
```
