# Native M-contact binding observations

2026-11-06. Two hand-built TM200CE40T diagnostics completed official IL-to-Ladder conversion, Ctrl+S and fresh saved-clone Programming reopens with **No error / Not Connected**. Root operated Machine Expert Basic1.4 build484; independent review viewed the four exact captures and compared the complete saved XML trees with the frozen candidates and authentic parent files. These are static binding observations, not compiler-generated products or runtime tests.

## Exact artifacts and procedure

Each candidate modifies one contiguous RungEntity byte span in an authentic saved parent. The SR0 derivative inserts `LD %I0.0; ST %M20` before `LD %M20; SR0`. The FIFO derivative inserts three ordinary I→M snapshots before its existing R/I/O body, replacing only the three block predicates with M20/M21/M22. The changed rungs initially have empty graphics and IL selected; the rest of each parent file remains byte-exact. Independent byte-prefix/suffix and restoration checks confirm those bounds.

| Case | Authentic parent bytes / SHA256 |
|---|---|
| FIFO | 105416 / `f6198b7054f1f1b6dbd016f6df756ef2ebd150a99d26bc59e86069944d000fa4` |
| SR0 | 137327 / `49438bcbed59cde889547869d8c033f377dfb7e60153136a57cb48e135b0e21a` |

| Case | Frozen IL-only candidate bytes / SHA256 |
|---|---|
| FIFO | 105454 / `45668bb3d0120b8d409d5eb315e363e909dffa8b2edeffb30747226f3e112e54` |
| SR0 | 134651 / `33bc2a5e4fa48c72761271f4333fa0158da0af651dba1aa7e6182bad3c1f8c72` |

| Case | Actual editor-saved bytes / SHA256 |
|---|---|
| FIFO | 117097 / `e05bf55077084557c9cc11a5237cdb677611c9cedff3cf22f921f19716932639` |
| SR0 | 141240 / `b850091e79c974dec8be14de36694428091d5a82ad6257a6ddfe5f1d882cc692` |

Root opened writable P: copies, converted the master rungs in the official editor and used Ctrl+S. Actual saved bytes were preserved as filesystem clones; no GUI Save As is claimed. Root opened the FIFO candidate before freshly reopening the SR0 saved clone, then opened the FIFO saved clone after that SR0 project. Both fresh Programming views showed No error / Not Connected. The frozen journal contains eleven recorded static actions with complete arguments and successful completion; its historical `runtime-actions` filename does not mean a simulator was used.

The independently viewed evidence is [FIFO full saved graph](editor-evidence/native-m-contact/fifo-m-contacts-saved-graph.png), [FIFO fresh reopen](editor-evidence/native-m-contact/fifo-m-contacts-reopen.png), [SR0 full saved graph](editor-evidence/native-m-contact/sr0-m20-saved-graph.png) and [SR0 fresh reopen](editor-evidence/native-m-contact/sr0-m20-reopen.png). All four public PNGs are exact filesystem copies. The existing Untrusted DLL banner remains visible; no cause or resolution is inferred.

## Observed graphs and complete readback

The FIFO block retains the ordered eight-line body `BLK %R0; LD %M20; R; LD %M21; I; LD %M22; O; END_BLK`. Its four entities are three NormalContacts at column0, rows0/1/2, each connected Left, Right, and Register `%R0` at row0/column1, connected Left. The native view displays Type FIFO; the serialized Registers container remains empty exactly as in the authentic parent. No new mode token is inferred or invented.

The SR0 call retains `LD %M20; SR0`. Its graph contains a NormalContact `%M20` at row0/column0, nine Line entities at columns1–9, and Jump `SR0` at column10. Contact and lines connect Left, Right; the Jump connects Left.

| Candidate → actual save | FIFO | SR0 |
|---|---:|---:|
| Project rungs / IL | 9 / 24 | 14 / 39 |
| Added Ladder entities | 37: 11+11+11+4 | 22: 11+11 |
| IsLadderSelected false→true | 4 rungs | 2 rungs |
| Token-identical LD/ST alignment changes | 6 lines | 2 lines |
| Root Name/FullName changes | 2 | 2 |
| Indentation-only text/tail differences on existing nodes | 92 | 34 |

Those are the complete differences. A literal expected transformation, built from the fixed operands, geometry, working-file identities and exact opcode spacing, matches the entire saved typed tree after normalizing only whitespace indentation. The JSON retains every added subtree and every content or indentation delta. All existing unowned rungs and their graphs are exact. Every lexical IL token, rung order, instruction comment and rung Name/MainComment/Label value is preserved. SR0 has eleven master rungs/30 instructions plus three unchanged callee rungs/nine instructions; all fourteen rungs have Ladder selected.

Every SoftwareConfiguration child other than the transformed master Pous is exact. HardwareConfiguration, WatchLists, Registers, FunctionBlocks, FastTask, MastTask, CpuBehavior, Subroutines and CustomSymbols additionally compare byte-for-byte as raw subtrees. **All thirteen allocation subtrees are byte-identical**, including Manual memory bits512 and words2000; the other eleven allocation containers stay empty. There are no allocation omissions or unclassified configuration differences in these saves. The six parent/candidate/saved XML files retain their UTF8 BOM, CRLF and identical declaration.

## Metadata and limits

The editor updates root Name/FullName to the writable candidate filename. Preserving the actual save under another clone basename does not rewrite those embedded fields. Historical rung comments such as “acceptance pending” remain unchanged author text; they neither override the observed static result nor establish runtime behavior. A reviewer helper initially required identical indentation tails on changed rung metadata; that assumption was corrected after confirming equal scalar values, and the initial failure and exact whitespace deltas remain retained. A separate raw-format check was corrected to require the preserved UTF8 BOM. Neither identifies a product defect.

No simulator launch, RUN, input changes, scans, repeated calls, accumulator/stack behavior, FIFO lifecycle/edge/priority semantics or physical PLC execution is newly tested. At this checkpoint the isolated codecs and whole-project compiler gates have not been expanded by this observation lane. Other indices, levels, contact domains and negated/edge/composite forms need their own evidence. Full functional parity remains the goal; these are specific implementation follow-up inputs, not PLC limitations.

All172 existing source/fixture pins remain unchanged. No source, test, fixture, codec, README or TASK_QUEUE edits or unit-suite rerun are part of this report. Exact hashes, graph fields, thirteen-allocation proofs, metadata and complete differences are in [NATIVE-M-CONTACT-BINDING-OBSERVATIONS.json](NATIVE-M-CONTACT-BINDING-OBSERVATIONS.json). Earlier [Register graph foundation](REGISTER-GRAPH-FOUNDATION-RESULTS.md) and [native subroutine observations](SUBROUTINE-NATIVE-OBSERVATIONS.md) retain their separate scopes.
