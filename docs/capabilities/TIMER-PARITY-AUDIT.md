# TM200CE40T timer parity audit

Audit date: 2026-11-06, compiler revision `95fefd8`. TON, TOF and TP, all five
documented bases, retentive TON/TOF and dynamic presets remain part of the full
[parity contract](../PARITY.md). The local implementation covers their principal
state paths, but editor bindings, feature boundaries and lifecycle behavior are
incomplete. **Keep the timer-option SMBP gates until their behavior evidence is closed.** The 10 ms binding was subsequently established by an exact editor-saved/reopened CE40T fixture. No compiler, editor, simulator or controller was changed for this
audit. Only this document was written.

## Primary sources and identity

Official download pages were checked on the audit date. The preserved PDFs in
`research/downloads/manuals/` match these SHA-256 values:

| Source | Pages used | SHA-256 |
|---|---|---|
| [M100/M200 Programming Guide, EIO0000002019.06](https://www.se.com/id/en/download/document/EIO0000002019/) | 21, 24-25 | `fb4f684e7efbb46e3e38e61ed532d99bf623bedffe447b5c379dd3dd6c4434df` |
| [Basic Generic Functions, EIO0000003289.04](https://www.se.com/us/en/download/document/EIO0000003289/) | 107-118 | `d2c8af0598276e7a0bb4f30770e4529282962bc6ee3944dee0645cb9a3186595` |
| [Basic Operating Guide, EIO0000003281.04](https://www.se.com/us/en/download/document/EIO0000003281/) | 54-55 | `2fb60e335bbe92342760471777abf256da7a434c61b98b464ae234aaa82c45e5` |

The M100/M200 guide explicitly delegates `%TM` behavior to the Generic Functions
guide and specifies 255 timers. This connects the generic timer documentation
to the target family; it does not identify a physical CE40T firmware revision.
The official pages currently advertise revisions 06, 04 and 04 respectively.
Parameter and timing-diagram pages 108, 112, 116 and 118 and the functional-level
page 55 were also rendered and visually inspected.

The installed portable editor's `Help/en-GB` CHMs were read without launching
vendor code. No extracted vendor HTML or implementation is published here.

| Installed source | SHA-256 |
|---|---|
| `sombgflg.chm` | `b4e4ec3ba4e8770f6ec0e459e15ace5ade9cb811f5a7b68d13c3c17e5759272c` |
| `sombopgd.chm` | `7b6b39fe891c8a2d24f8fae964879ece4ac39ce79af29284a6217aa967a21c36` |
| Timer configuration topic `/sombgflg_D-SE-0033418.htm` | `89bb6cf3b2c7ef4c06c4013299cc613fe6664bdc6f539062fc012b42268881d9` |
| Behavior topic `/sombopgd_D-SE-0027939.htm` | `a640d1ea42817838ddda4355c84ea9570778324d64579780c51c419cdd8382c1` |

Installed TON/TOF/TP topics are `/sombgflg_D-SE-0027156.htm`, `...27157.htm`
and `...27158.htm`. Their contracts agree with the inspected PDF sections.
The [Schneider retentive-timer FAQ](https://www.se.com/us/en/faqs/FA369738/)
also distinguishes TON/TOF from TP, but explicitly concerns M221; it is
corroboration, not independent CE40T proof. Machine Expert/CODESYS emulation
library pages are not substitutes for the Basic `%TM` contract.

## Documented timer contract

The family has `%TM0..%TM254`. Bases are 1 ms, 10 ms, 100 ms, 1 second and
1 minute; 1 ms is restricted to TM0..5. Presets span **0..9999**, with 9999
and a minute base as editor defaults. `%TMn.P` is program-readable/writable;
V is program-readable and Q is a readable bit. Changing V through an animation
table is a separate operator capability, not permission for a program write.

| Mode | Principal contract | Retentive option | Dynamic preset |
|---|---|---|---|
| TON | Counts while enabled; completion asserts Q; disabling normally clears elapsed value/Q | Pauses unfinished elapsed value while disabled; resumes on enable; disabling after completion clears it | Documented |
| TOF | Enable asserts Q; disable starts the delay; completion clears Q; enable normally resets elapsed value | Enable pauses an unfinished off-delay; disable resumes it | Documented |
| TP | A rising edge starts a pulse; retriggers during that pulse do not restart it; falling IN does not cancel it | Not established for TP; the supplied diagrams cover retention only for TON/TOF | Documented |

Without dynamic mode, a P write affects a later activation. With it, a new
threshold applies to the active timer. Although the parameter table describes
immediate effect, diagrams on pp. 111, 112, 115, 116 and 118 explicitly place a
decreased threshold's completion at the next base update. The drawn V may remain
above the new P; clamping V to the smaller preset would lose this distinction.
With both options, reducing P below a paused V clears V: TON is paused at IN=0,
TOF at IN=1. The documented comparison is strict; equality needs its own test.

The special-case tables also describe cold restart resetting V/Q and restoring
configured P, warm restart preserving V/P without counting through the outage,
and controller STOP allowing a running timer to progress. Skipping a block does
not stop its internal timer, but does not rewrite the directly wired output.
These are distinct from retentive pause/resume at IN. The tables advise one
program test of Q; the actual acceptance/meaning of repeated property reads
still needs verification rather than an invented restriction.

Online editor parameter edits have a reset footnote. They must be tested
separately from program instructions writing P; conflating the two would hide
dynamic-mode or reset behavior. Sources: Generic Functions pp. 108-118 and the
installed configuration/TON/TOF/TP topics above.

## Functional levels and binding evidence

There is a **primary-source conflict for retentive mode**: Generic Functions
p. 108 and the installed timer configuration specify minimum FL3.3, while
Operating Guide p. 55 and the installed Behavior topic introduce retentive timers
at FL4.0. Both sources consistently place dynamic presets at FL12.0. A selected
application level must also fit the real controller firmware's supported level
(Operating Guide p. 54); an editor label alone cannot establish that support.

The installed enum/resource mapping in [editor facts](EDITOR-INTEROP-FACTS.json)
now supplies candidate boundary tokens:

| Human level | Actual token | Audit use |
|---|---|---|
| 3.2 | `FunctLevelMan5_0` | Below both documented retentive thresholds |
| 3.3 | `FunctLevelMan6_0` | Disputed retentive boundary |
| 4.0 | `FunctLevelMan7_0` | Operating Guide retentive boundary |
| 11.0 | `FunctLevelMan17_0` | Below dynamic threshold |
| 12.0 | `FunctLevelMan18_0` | Dynamic threshold |

This supersedes the older assumption that no token-to-label map exists. It does
**not** resolve the conflicting boundary, serialize every setting correctly, or
justify replacing `validate_timer_profile` with a level comparison today.

| Feature | XML evidence | Current implementation | Actual official evidence |
|---|---|---|---|
| Non-retentive TON/TOF/TP | `TimerTM`, Type, Preset, Base and false option fields are emitted and locally reread | Frontend, IL/VM, SDK and reverse path | TON0/100 ms/preset 5 has the exact case below; operator also reports a completed 1 s-base three-timer sequence; no general matrix |
| Bases 1 ms / 100 ms / 1 s | Current names `OneMilliSeconds`, `OneHundredMilliSeconds`, `OneSecond` | Import/export allowed, with 1 ms index restriction | 100 ms TON covered; 1 s sequence completion reported; 1 ms acceptance and other combinations remain separate |
| 1 minute | Existing public M200 files omit Base and use the default | Import/export uses omitted Base | No exact CE40T timer acceptance case established here |
| 10 ms | Exact CE40T editor save preserves `TenMilliSeconds` for TON/TOF/TP | Local model and SMBP import/export supported | Saved/reopened fixture SHA `934affc43bd7e3d918b529b5cbfaee5aabd6bc062006edcd5c3cacf0d7f2bc45`; runtime timing remains separate |
| Retentive TON/TOF | `IsRetentive=true` exists in a pinned foreign M200 project | Local modes/JSON/reverse supported; SMBP true is refused | No CE40T option/boundary acceptance |
| Dynamic preset | `IsDynamicPreset` is recognized; false is emitted | Local mode supported; SMBP true is refused | No editor-created true-mode CE40T fixture or runtime proof |

The public [TM200CE24R project](https://github.com/GabriWar/ubec/blob/cd7f4b009b53c19a9952173efbbcf29decc12087/PROJETOS/UBEC/correto.smbp)
has SHA-256 `1c6d07b606c595dc5a9e80590e2c589a948b55102887f6e12f4b3d8279c7d2b9`:
TM3, base OneSecond, preset 2, `IsRetentive=true`, token `FunctLevelMan13_0`
(human 6.2). It cannot distinguish the 3.3/4.0 thresholds, and does not establish
CE40T execution. The installed Entities assembly's timer-base identifiers are
bound to hash `bf7b33a79356dbfd9839891b00e61695b5af3b5ee7ce121def37e3e973a9455e`
in the editor facts. Names and numeric enum values are not serialization tests.

## Current implementation and remaining behavior gaps

`m200/timers.py` and `sdk/plc.hpp` implement activation/resume-relative ticks,
integer elapsed-value retention, dynamic threshold updates, and internal timer
progress when a block is skipped. The frontend permits one static update site
per instance; control flow may visit that site multiple times in a scan. Tests
in `test_timer_properties.py` and `test_timer_modes.py` inspect P/V/Q, preset
writes, pauses, jumps, strict flags, inverse conversion and protected XML refusal.
This audit inspected those tests; it did not rerun timer runtime suites.

Remaining local policies need external comparison: fractional ticks lost on
pause/resume, ordering of elapsed ticks versus a same-instant P write, and
whether a completed dynamic timer can resume when P grows. Invalid runtime P
currently raises an error; a native clamp/wrap/status effect is not established.
The VM has no complete STOP/RUN, warm/cold restart or power-loss model, and its
system-bit allowlist does not expose S0/S1. None of these gaps reduces the PLC
parity target.

The exact `timed_counter` artifact SHA-256
`abf6cb87d043840b5fa4065b4ad69144a6454b34573404edcb02d594d9345581`
contains TON0, 100 ms base, preset 5, both options false. The
[official evidence record](../validation/OFFICIAL-EDITOR-RESULTS.json) records
Online/identical/RUN and ready/edge/counter/reset states; it expressly limits
timing to settled observations. Subsequently, the GUI operator reported a
completed TON/TP/TOF sequence with a one-second base/preset 10, and held START
without automatic restart: phase 4, accepted/completed 1/1, aborted/rejected
0/0, V=0/0/10, busy 0, reason 6. The
[sequence review](../validation/SEQUENCE-TIMERS-REVIEW.md) separates that positive
original-program/GUI-watch observation from the earlier WatchLists derivative's
unresolved launch access violation. Its saved GUI-watch identity and further
button cases belong to the official evidence record. No cause is attributed to
Wine or timer modes. Fine-resolution, options and physical timing remain
unverified by this audit.

## Next tasks and precise controls

1. Resolve the simulator launch failure with preserved exact original,
   WatchLists-only, TON-only, TP-only, TOF-only and three-timer candidates. Record
   actual native allocations and every artifact hash; local VM success cannot
   replace this step.
2. Create/save/reopen CE40T timer fixtures in the official editor for every base
   and type, inspecting real IL, hardware and timer fields. Include TM0/TM5
   positive 1 ms cases and TM6 negative 1 ms case, and TM254 positive/TM255
   negative identity cases. Confirm a 10 ms saved binding before lifting its gate.
3. Isolate retentive gates at FL3.2, 3.3 and 4.0 and dynamic gates at FL11.0 and
   12.0, using the actual tokens above. Pair each rejection with the valid
   neighboring request. Preserve controller/firmware identity; do not change
   firmware to manufacture acceptance. Test combined options and TP's unavailable
   retentive selection separately.
4. Preserve negative import/export controls for unknown/noncanonical level
   tokens, unknown Base/Type, malformed/duplicate timer fields, non-boolean flags,
   duplicate indexes, V/Q writes and P=-1/10000. Require explicit failure before
   destination replacement, then verify a valid ordinary timer still succeeds.
   P=0 and P=9999 are valid boundary requests, not rejection cases.
5. Compare preset increase/decrease/equality while counting, paused and completed;
   write P before/after update and around a base boundary. Include overlapping
   IN edges, held/retriggered TP, skipped blocks and repeated visits. Observe Q
   and wired output separately, including a repeated-Q-read comparison. Keep
   editor online edits distinct from program P writes and animation V writes.
6. Establish STOP/RUN and warm/cold restart contracts, then implement missing
   lifecycle expressions/model support. Physical tick phase, jitter, power-loss
   behavior and electrical timing require a separately authorized controller
   test; editor or simulator acceptance alone cannot settle them.

## Official artifact metadata cross-check

All seven referenced SMBP files in the official evidence record exist and match
their recorded SHA-256 and byte sizes. Counts below are from `load_project` and
raw XML; the two counting methods agree. These are artifact counts, not an
estimate from the original frontend program.

| Candidate/artifact | Actual rungs / instructions | Recorded counts | Hash prefix |
|---|---:|---:|---|
| Compiler memory original | 1 / 2 | Not separately listed | `7128749796a0` |
| Memory editor-saved | 1 / 2 | Not separately listed | `4b6120f1151f` |
| Memory animation table | 1 / 2 | Not separately listed | `6af5bd3ade58` |
| Compiler I/O original | 4 / 8 | Not separately listed | `1bd2d9e1ff43` |
| State arrays | 141 / 298 | 141 / 298 | `d3644371358f` |
| Timed counter | **102 / 221** | **102 / 221, corrected** | `abf6cb87d043` |
| Numeric diagnostics | 113 / 231 | 113 / 231 | `af42029357b2` |

The stale timed-counter numbers exactly match current `compile_source` frontend
IL. `normalize` expands it to 102/221, matching both the actual SMBP's
`RungEntity`/`InstructionLine` counts and `load_project`. State arrays and numeric
diagnostics have equal frontend/normalized counts. The GUI operator corrected the timed-counter metadata before publication; this audit itself did not edit the official evidence manifest.

The subsequent [END/timer integration](../validation/NATIVE-END-TIMER-10MS-RESULTS.md) records the 10 ms fixture and 462-test checkpoint. [Timer level research](TIMER-LEVEL-BINDING-RESEARCH.md) distinguishes stored flags from UI availability and downstream execution.


## Subsequent scoped implementation

A later increment admits only separate retentive TON/TOF and dynamic TON at base1000ms and actual `FunctLevelMan21_0`, following [paired official controls](../validation/TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.md). [Profile-policy results](../validation/TIMER-OPTION-POLICY-RESULTS.md) distinguish this narrow admission from the remaining mode/base/level/lifecycle gaps. Earlier audit statements about a blanket option gate describe the state when this audit was written.
