# Native Register implementation plan

The crucial active-binding finding is that **a used FIFO R0 saves with an empty
`Registers` collection**. Default FIFO configuration must therefore be resolved
from valid resource references; a reader requiring an explicit row would reject
authentic native code. LIFO saves one explicit Type Lifo row. Neither capability
is implemented by this research; reopening/runtime observations remain root-owned.

## Evidence and closed scope

The cached [Generic Functions Guide](https://www.se.com/ww/en/download/document/EIO0000003289/)
EIO0000003289.04 pp141–146 defines FIFO/LIFO, fixed capacity 16 words of 16 bits,
RW I/O words, E/F flags, reset and rising-edge store/retrieve. M100/M200
[EIO0000002019.06 pp21/25](https://www.se.com/ww/en/download/document/EIO0000002019/)
permits four registers on this family, including CE40T. Counts, primary hashes and
installed metadata evidence are in [NATIVE-BLOCKS-NEXT-RESEARCH.md](NATIVE-BLOCKS-NEXT-RESEARCH.md).

Root's actual editor saves under
`output/editor-validation/native-register-shared-request/editor-saved/`:

| Artifact | Bytes | SHA256 | Register configuration |
|---|---:|---|---|
| `register_fifo_editor_saved.smbp` | 106489 | `85219725709cbe90641e25bedddd6bfa4f13011a55e01be4ba087f8f42b09189` | `<Registers/>`, despite active `%R0` |
| `register_lifo_editor_saved.smbp` | 106627 | `8d04a2bc22bc2466a928ea185d41641f53c5493e26a2a19d690ef8e55822c1ab` | Register Address `%R0`, Index 0, Type `Lifo` |

Both were independently read without edits. FIFO root reports No error, global
IL→Ladder conversion and save; LIFO's typed save is likewise available. They contain
six selected-Ladder rungs and 20 IL lines; entity counts are 10/10/10/10/11/11.
The branch-rich Register rung is actually ElementType `Register`, row 0/column 2,
Left, with its input contacts/lines/VerticalLine across rows 0–4. Do not transplant
Counter port-row offsets: this real geometry includes the two OR request branches.
The original candidate remains separate from both saved derivatives.

The installed entity independently defaults Type to **Fifo=1**, established by its
constructor, default-configuration predicate and Type DefaultValueAttribute.
Enum-zero Lifo=0 is not the omitted default. Entity Input/Output are nullable Int16,
Empty/Full nullable BOOL; these are UI/configuration facts, not CPU reset semantics.
No runtime rule is taken from managed UI ResetRuntimeValues methods.

## Behavior known from the primary guide

| Domain | Documentary rule | Still unresolved by this lane |
|---|---|---|
| Store I | Fresh rising edge stores the input word unless full; changing `.I` while I stays high is not another edge | History consumption when a request is refused by full/reset, first-call TRUE and repeated calls |
| Retrieve O | Fresh rising edge selects oldest FIFO/newest LIFO word; empty retrieval retains the output word | History consumption on empty/reset and same-resource multiple calls |
| New I and O edges together | Neither operation occurs in that FB call | Whether and how ignored edges are recorded under subsequently held inputs |
| Reset R | Level 1 initializes queue contents and makes E true | Priority against I/O edges, output-word value, input edge-history reset/update |
| Data words/status | `.I/.O` readable and writable 16-bit words; `.E/.F` represent empty/full | Exact initial/reset O value and first-call/lifecycle details; a public depth operand is not documented |
| Lifecycle | Cold/INIT initializes contents/E; warm/STOP retain register contents/status | Full event sequencing and operator-visible data-word preservation need native observations |

C++ arguments are evaluated before a member call. A raw native block can put
`R0.E` in a later input expression, as the manual's example does. Establish whether
such a contact sees old state or an earlier action's state before canonicalizing
raw blocks into one host update. This is separate from simultaneous pure-input
requests, and from output status reads after the block.

## Collision and edge-history capture plan

Do not try to create simultaneous edges with sequential GUI clicks. The existing
I0.5 common request proves both I/O conditions can change in one call. New separate
IL-only candidates add I0.6=R+I, I0.7=R+O, I0.8=R+I+O. A single input drives each
combination. Before the block, one LDR per driver produces an event; after the call,
that event latches E/F and I/O word samples. This preserves the first-call result
while held Reset may change the state on subsequent scans.

| Priority | Preparation and control | Observation/question |
|---|---|---|
| 1 | Exclusive reset, write `.O=42`, release sentinel writer, empty retrieve | Known empty-pop O retention; determine reset O independently |
| 1 | Two stored values 11/22; common I/O pulse | Neither request changes queue; then drain FIFO 11/22 or LIFO 22/11 |
| 1 | Empty/two-item/full queue, fresh I6 | First-call Reset+store precedence; compare latched result with held current state |
| 1 | Two-item/full queue with O sentinel, fresh I7 | Reset+retrieve precedence and whether an output value escaped before clear |
| 1 | Two-item/full queue, fresh I8 | Reset precedence against documented simultaneous-request no-op |
| 2 | Hold I6; assert I1 while already held; release only I6 | Reset drops while Store remains high: was Store history cleared or consumed? No precise two-click timing needed |
| 2 | Empty pop edge then hold O; pulse a new store | Does unsuccessful retrieval retain a pending edge or consume it? |
| 2 | Full store edge then hold I; pulse a new retrieve | Does an ignored full store reappear when capacity becomes free? |
| 2 | Sixteen fresh stores, ignored seventeenth, sixteen retrievals | E/F transitions, no overwrite, exact order and final O retention |
| 3 | Separate variant with I=button and O=button AND NOT R0.E | Old/new self-status input evaluation point, captured at the first call |
| 3 | Separate skip variant: last called I=false, raise/hold I while skipped, resume | Per-call versus scan-global request history |
| 3 | Skip variant: last I=true, fall/rise while skipped, resume high | Unseen input transitions versus retained call state |
| 3 | Separate two-call variant, computed I=false then I=true in one cycle | Native legality and edge scope; do not advertise a hardware one-call limit |

The ignored package `output/editor-validation/native-register-collision-latches/`
contains 26-rung/73-line candidates, no graph entities, a detailed case table and
GUIDE. Q0/Q1 are current E/F; Q2/Q3 are first-edge samples; Q4 is sample-valid.
MW10 is case 6/7/8, MW11 sampled O and MW12 sampled I. Exclusive I0 clears validity;
stale words are deliberately retained and must be ignored while Q4 is false.
Only R configuration/rungs change; the baseline's 512 bits/2000 words already cover
these diagnostics. Previous candidates, actual saves and authentic baseline bytes
remain untouched. Both new candidates are **unaccepted**, with no runtime result.

An 11-position injected-observation probe passed for the latch design: it removed
the R block, injected post-call observations into the existing ordinary IL VM and
checked sample retention while later current state changed. This tests observation
mechanics only; it is not a Register model, native proof or new unit-test total.

## Minimal API, state, IR and project integration

1. **Model/configuration.** Add one bounded Register configuration family keyed
   by canonical IDs 0–3 and exact FIFO/LIFO modes. Fifo/Lifo share the same four-slot
   pool, not separate pools. Add a config-only JSON map, never queue runtime state.
   Resolve known default FIFO for referenced valid instances whose XML row is
   omitted; do not create all four unused instances. Preserve explicit Lifo and
   reject unknown/duplicate fields, IDs and modes. Do not infer runtime O from a
   default-value attribute.
2. **Word and bit operands.** Bind `.I/.O` through the existing i16 word semantics,
   `.E/.F` as readonly BOOLs. Data words are not `%MW` addresses and the internal
   sixteen-item queue must not silently consume ordinary MW cells. Check aliases
   and ordering for application MW/MD/MF sources separately. Match `%R<id>` exactly:
   a broad `%R` prefix would collide with READ_VAR and RTC families.
3. **C++ surface.** Start with explicit `plc::Fifo r{0}` / `plc::Lifo r{0}` identity;
   propose `set_input/input`, `set_output/output`, void
   `update(reset,store,retrieve)`, and `empty/full`. Output-word writes change the
   output word, not the queue. No invented Done/count/depth result is exposed.
   Literal identity/range/duplicate and typed-argument errors happen before output
   replacement. Any initial one-update restriction is a tool gap pending multiple
   call evidence, not a claimed PLC limit or the final parity objective.
4. **Local state model and SDK.** Fixed sixteen-word storage, input/output words,
   count/order and per-resource request history; no heap or host clock. FIFO and
   LIFO differ only in retrieval order. Consume the newly captured priority/history
   evidence before defining reset, first-call and ignored-edge transitions. Keep
   event/lifecycle policies visibly pending until proven; do not make two identical
   implementations the only oracle.
5. **IL and reverse.** One authoritative parser for Register R/I/O blocks plus
   typed data-word operations/status references. Preserve source order of data-word
   writes, input expression evaluation and post-call status reads. Reconstruct the
   native resource/mode in C++, not a software queue spread over MW cells. Raw
   direct I/O/R instructions and unusual control flow need explicit semantics;
   reject unknown forms rather than silently flattening them.
6. **XML and graphics.** Replace only the Registers EMPTY gate with a typed parser;
   add only Register repetition to singleton validation. Accept the proven default
   omission and Lifo row while preserving hardware/allocations. Numeric Operation
   and ordinary E/F contact graphics also need the new operand types. For the native
   block, implement a dedicated closed port/connectivity checker using the actual
   saved topology; do not guess every branch/row or reuse Counter coordinates.
   Writer output should follow proved native forms and canonical reimport checks.
7. **Validation and official acceptance.** TDD literal FIFO/LIFO order, sixteen/full/
   empty boundaries, held/fresh/ignored controls, data-word writes, newly observed
   collision priorities, sparse R3 and property-only references where established.
   Compare independent expectations against SDK, VM, actual XML and reverse/
   recompile; then independent review and one frozen full local suite. Normal CLI
   output gets its own root-operated open/save/reopen/runtime result. No fixture
   hash dispatch, retargeting, hidden mode fallback or invented compatibility claim.

Required negatives include R4, leading-zero/negative IDs, duplicate IDs across
Fifo/Lifo, invalid mode, unknown/nested/duplicate config fields, wrong Address/Index,
non-integer or incompatible data values, writes to E/F, missing-resource graph
references, mismatched block descriptor/mode, forged ports/lines/connections,
truncated actions and rejected-destination byte preservation. Existing timers,
counters, communication R-prefixed addresses and all broader unsupported blocks
must keep their current behavior.

Research only: no product/SDK/test/fixture changes, network/GUI operation, CI or
full-suite execution was performed by this lane. Root exclusively owns native
observations and later publication decisions.
