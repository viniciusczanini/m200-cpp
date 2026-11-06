# Subroutines

Declare a named `void()` leaf and a global descriptor, then call it synchronously:

```cpp
#include <plc.hpp>

void leaf() { plc::write_word(0, 20); }
plc::Subroutine sr{0, leaf, "application_leaf", 2};
void scan() { sr.call(plc::input(0)); }
```

The four arguments are the native number, function, native name and independent section number. Numbers are literal integers in 0..63; names must be nonblank XML-safe literal strings; sections are nonnegative Int32 literals. IDs, names and sections must be unique. `Subroutine{number, leaf}` defaults to the function name and section 2 plus declaration order; this is a tool metadata policy, not a mapping from native SR number.

A false call skips the leaf. An enabled call shares the current scan's inputs, output image, global memory and clock. Falling off the body or executing `return;` resumes the caller. A Master `return;` still ends its scan after committing earlier output writes. Source maps, JSONv2 and IL artifacts retain separate Master/callee contexts and origins. Normalization reserves memory across all contexts and preserves leaf return scope.

## Current native export profile

TM200CE40T at actual Man21 (`FunctLevelMan21_0`), one Master section 0 and **one stateless leaf section 2**, using an ordinary supported template without active subroutines. Canonical normal `%M` call contacts (0..1023) and the observed I0.0 predicate are bound; complex source conditions are materialized into memory before the call. Leaf code must have supported direct series graphs. Implicit return, sole END and ENDC are supported; raw leaf ENDCN, constant-contact IL and compound graph shapes are refused.

Local typed contexts can represent multiple independent IDs 0..63 and different section metadata. Those broader layouts do not establish native export support. Nested calls, leaf loops/labels/indexed accesses and combining SR programs with timer/counter/communication blocks remain refused. These are current compiler gaps.

The [genuine example](../examples/editor_validation/cpp_subroutine_implicit.cpp) and [compiler results](validation/SUBROUTINE-COMPILER-RESULTS.md) show the bounded implemented path. To reconstruct a supported native project, use `m200c decompile`; compile the resulting C++ with an ordinary admitted CE40T template. The active native configuration sidecar is preserved for inspection and is currently refused as an export template.

```sh
./m200c compile examples/editor_validation/cpp_subroutine_implicit.cpp \
  --template tests/fixtures/official_tm200ce40t_memory.smbp -o output/subroutine
```
