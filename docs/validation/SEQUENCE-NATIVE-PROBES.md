# G08 — finite official observation batch, plan1

**Three authored C++ probe texts; no project was generated or executed. Every
native question below is PENDING.** Root may batch these after its local gate
and source freeze. This plan does not authorize physical-controller operation.
Use the local official simulator only. Do not drive connected loads.

## Evidence boundary and prerequisite

Read: final isolated G08 DELIVERY; current root docs/NATIVE-SEQUENCES.md;
`tests/parallel_semantics/g0108_cases.py`; combined-3/test-batch SUMMARY/summary,
combined-3b/test-batch SUMMARY/summary/minimal reproduction and
combined-3c/test-interop/summary. These existing records say:

- combined-3:23 cases/185 positions passed seven local routes; deterministic
  DR.S assignment was blocked in allocation, without an ambiguous native input.
- combined-3b: the corrected deterministic SBR/SC/DR case passed16 positions in
  seven routes, plus the minimal set_step2 local reproduction.
- combined-3c: focused DR.S/packed-width/timer checks passed; its summary retains
  the earlier full-suite result of123 failures,4 errors and1 skip. This is NOT a
  global green gate and is not official editor/simulator acceptance.
- Native endpoints, collisions, request history and lifecycle remain pending.

No tests/imports/compiler/generator/GUI/Wine/simulator were run here. The sources
use existing SDK routes only: named native instances, literal bit access,
update/update_pins, decimal literal set_step, native loops, raw M/MW/Q observers.
They have NOT themselves been compiled or validated. Record any source/compiler
or native-admission failure separately; it supplies no endpoint oracle.

Use existing authentic `tests/fixtures/official_tm200ce40t_memory.smbp` as the
future template: TM200CE40T/Man21 with eight native DR/SBR/SC resources. Its
identity/hash and the manuals are pinned in manifest.json. No hardware/config
clone was written here. Existing authored default rows/static metadata establish
names/limits, not acceptance of the new active graphs. Root must open, compile,
inspect Ladder/config, save and reopen each exact generated project first.
Record byte hashes before/after official saves, tool version, target and level.
Keep the CE40T hardware/config; do not retarget the CE24R example. If active XML
or graphs need correction, preserve the refused bytes and report the defect;
do not substitute IL-only output and call it a completed compiler project.

## One deliberate transaction per EXEC assertion

All three programs use I0.7=EXEC, M900=accepted EXEC latch, M901=capture valid,
MW15=transaction number, Q0.14=EXEC acknowledgement and Q0.15=capture valid.
Only the EXEC transaction calls the native block (except the explicitly marked
SC PRIME255 preparation). Held EXEC skips further calls. Results remain latched
for a slow animation-table refresh; a GUI refresh is not a scan clock.

For **every numbered transaction T{input indices}**, use this exact order:

1. Set I0.7=0; wait until Q0.14=0. Do not STOP/RUN between transactions.
2. With EXEC low, set every listed control input to1 and every other control
   input to0, including all seed/mode/skip inputs. Inputs not in the table stay0.
3. Set I0.7=1. Wait for MW15 to increase by exactly1, Q0.14=1 and Q0.15=1.
   Capture all listed MW/M/native fields, then verify the same MW15/results on
   another refresh while EXEC remains held. If the count keeps increasing, the
   observer/harness failed; do not infer native repeated-request behavior.
4. Set I0.7=0 and wait for Q0.14=0 before changing controls. Releasing EXEC does
   NOT call the native block and does NOT release its CU/CD/U history. A neutral
   transaction T{} explicitly calls the full pin group with all pins false.

At fresh startup set every I0 input0 before RUN and wait for normal first scan;
MW15=0/M901=0 identify initialization, not a valid sample. Use Decimal for signed
MW, Hex if available; raw16 8001/C000 are -32767/-16384 in signed i16. Every
transaction latches its input controls too. Capture valid alone can be stale;
associate data with the observed MW15 and input echo.

The common **PREP0** is three actual transactions: **T{}; T{0}; T{}**.
These call neutral, exclusive reset, then neutral. This removes a prior direction
request before reset and releases R by an actual call. Do not replace this by
merely clicking controls while EXEC is low. For the documented exclusive-reset
control, require the family to reach0. If it does not, preserve observations and
leave subsequent questions pending for failed setup.

## Project1 — sbr_observe.cpp / SBR0 only

Inputs: I0=R, I1=CU, I2=CD, I3=set bit0, I4=set bit15,
I5=set bit14, I8=R-only partial block. No seed repeats while EXEC is held.
When I8=1, I1/I2 are omitted native pins, regardless of their UI levels.

Observe MW0=latched full16-bit mask built from all16 documented BOOL operands;
MW1=input echo (bits0..5 correspond I0..5; bit8=I8); MW15. Q0..3 show live
bits0/1/14/15. MW0 is ordinary observer memory, not a numeric whole-SBR operand.

| Question / sequence | Ordered transactions after PREP0 | Documented control / discriminating result |
|---|---|---|
| SBR_LEFT_FILL | T{3,4}; T{1}; T{1} | Seed must sample8001 (-32767). Fresh CU may sample0002 (vacated bit0 cleared) or0003 (bit0 retained); these are hypotheses, expected=null. Second T{1} is a held CU call: record it separately; never re-seed. |
| SBR_RIGHT_FILL | PREP0; T{3,4}; T{2}; T{2} | Seed8001. Fresh CD may sample4000 (16384, bit15 cleared) orC000 (-16384, bit15 retained). Other masks are retained as observations, not forced into these two hypotheses. |
| SBR_PARTIAL_HISTORY (optional, same project) | PREP0; T{5}; T{1}; T{8}; T{1} | Verify seed4000 then safe CU8000 (-32768). T{8} calls only R=false. Final full CU=true distinguishes retained active CU history (8000 if no extra shift) from omitted pin clearing history (0000 after fresh CU). Infer history only if the intermediate partial sample remained8000; otherwise record the new case without choosing an ordering. |

The first two are essential for any circulating single-bit show pattern that
injects a1 at the vacated end. The optional third matters because update_pins is
the reverse path for valid partial native blocks; skip it if the frozen batch
contains no partial blocks. It does not require another project.

The manual establishes exclusive reset clears bits and shifts lose the outgoing
end bit. It does not settle these seeded-vacated-end values. The current local
VM/PLC_NATIVE deliberately stops at those ambiguous first shifts/omitted-active
histories. Native IL emission is still supported; local refusal is not native
rejection. No S17/carry expectation is borrowed from numeric SHL/SHR.

## Project2 — sc_observe.cpp / SC0 only

Inputs: I0=R, I1=CU, I2=CD, I3=PRIME255. PRIME must not be combined with other
control pins. Observe MW1=before landmarks; MW0=after landmarks; MW2=input echo;
MW3=255 only if PRIME code reached its completion marker; MW15. Landmark mask:
bit0=SC0.0, bit1=SC0.1, bit2=SC0.254, bit3=SC0.255, bit4=SC0.2.
Q0..4 mirror these same five live landmarks. This is not a numeric SC step
operand. Mask0 means outside these five landmarks, not proof of no active step.

| Question / sequence | Exact ordered transactions | Control and pending discrimination |
|---|---|---|
| SC_ZERO_CD | PREP0; T{2}; T{2} | PREP0 must give mask1 (step0). First CD: mask8 is compatible with wrap255; mask1 with staying0; other/multi-landmark masks are recorded without calling them invalid. Second T{2} records held-request endpoint history separately. |
| SC_MAX_CU | PREP0; T{3}; T{1}; T{1} | PRIME is a native bounded loop of255 neutral/CU=true pairs plus final neutral. Before testing the boundary require MW3=255, MW0=8, SC0.255=1 and SC0.0/1/2/254=0. Then fresh CU: mask1 suggests wrap0; mask8 suggests stay255. Second held CU records history. No guessed outcome if setup fails. |
| SC_RESET_RELEASE_HISTORY | PREP0; T{1}; T{1}; T{0}; T{1} | Verify first/held CU give step1(mask2). T{0} is exclusive R with CU=false after a prior true CU; documented reset control should reach step0(mask1). Without a neutral call afterward, R=false/CU=true may give step1 if reset sampled false CU/cleared history, or step0 if old true CU history persisted through reset. Outcomes remain pending. |
| SC_RESET_NEW_CU_COLLISION | PREP0; T{1}; T{}; T{0,1}; T{1} | Precondition step1 and called CU=false. On simultaneous R/new CU: mask1/2/16 discriminate reset-final, reset-then-CU-like, or CU-from-old-step-like outcomes; these are behavioral hypotheses, not asserted internal execution order. Final R release while CU stays high records history. |

PRIME255 is an optional fast **setup technique**, not an assumption about
watchdog timing or same-instance call acceptance. It contains no256th increment,
no writable-step shortcut and no unrolling of states. Its admission and observed
step255 are prerequisites. If its loop/native repeated calls/watchdog prevent
completion, preserve the failed setup; SC_MAX_CU remains PENDING_SETUP. Do not
change watchdog settings to hide failure. The lower-bound/reset questions can
still be observed after normal PREP0 in an admitted project. If the project
itself is refused because of the loop, these questions are blocked at project
admission too; do not report them as native semantic failures.

Local VM/SDK accepts documentary interior moves but stops on CD at0, CU at255,
reset with prior active history and reset/direction collisions. Those stops are
intentional local gaps. No outcome vector is supplied for these unknown domains.

## Project3 — drum_observe.cpp / DR0,3 steps, unique cams

Inputs: I0=R, I1=U, I3=write literal2, I4=write literal1,
I6=skip block. I3 and I4 must never both be1. I2/I5/I8 and others stay0.
For this project, replace PREP0 in every Drum row below by **DR_PREP0**:
**T{}; T{4}; T{}; T{0}; T{}**. Require the literal1 call to show
step1/cam2/F0, then the reset call and final neutral to show step0/cam1/F0.
This forces an actual step change before testing cams and does not depend on
assuming that a plain RUN entry applied a cold-start cam image. If either
control fails, the Drum questions remain pending setup.

Slots0/1/2 bind distinct M100/M101/M102, masks1/2/4 respectively. No aliased cam,
RTC, schedule, Counter or other native family is configured in this project.

Observe these latched words (and MW15/input echo MW10):

| Stage | Step `.S` | Cam mask M100/101/102 | F in bit0 |
|---|---|---|---|
| Before optional assignment | MW0 | MW3 | MW6 |
| After assignment, before call/skip | MW1 | MW4 | MW7 |
| After call or skip | MW2 | MW5 | MW8 |

Cam masks1/2/4 correspond to steps0/1/2; F is true at configured last step2.
Q0..2 mirror the live cams; Q3 mirrors F. The snapshot after a skip is explicitly
not after an executed block. Record all three stages; live DR.S alone loses
visibility of the assignment/call boundary.

| Question / sequence | Exact ordered transactions | Control and discriminating observations |
|---|---|---|
| DR_STEP_VISIBILITY | PREP0; T{3} | Verify PREP0 gives step0/cam1/F0. With no reset/U, literal2 must take effect at the next executed block according to the manual: final step2/cam4/F1 is the documentary control. MW1/MW4/MW7 expose whether the public properties/cams change before that call; those intermediate values are pending, not inferred from local success. |
| DR_SKIP_PENDING | PREP0; T{3,6}; T{6}; T{} | First write2 skips block. Second transaction skips without another write and latches persistent pre-call visibility. Cam1 should be retained while no step execution occurs (documentary control); record any contrary native result. Final neutral execution applies pending step2: final step2/cam4/F1 is the documentary next-call control. Intermediate step/F visibility remains pending. |
| DR_WRITE_NEW_U | PREP0; T{3,1}; T{1} | DR_PREP0 explicitly restores step0 and includes called U=false throughout. Write2+fresh U may finish at0 (write then wrap-like),1 (advance-only-like),2 (write-final-like), or another result. Finishing2 alone does not prove whether U ran before assignment or was suppressed. Repeat U=true without write: unchanged or wrap0 distinguishes whether U history was consumed under the write. |
| DR_RESET_NEW_U | PREP0; T{4}; T{}; T{0,1}; T{1} | Establish step1/cam2/F0 with a literal1 control and called U=false. R+fresh U may finish0 (reset-final-like),1 (reset then advance-like),2 (advance-priority-like), or other. Final R=false with held U tests history; classify it conditional on the collision result. |
| DR_WRITE_RESET | PREP0; T{4}; T{}; T{3,0}; T{} | Establish step1/U=false. Write2+R may finish0(reset-final-like) or2(write-final-like), among other outcomes. Following neutral call shows whether a suppressed write remains pending. Preserve both stage snapshots and never infer a hidden queue from one sample. |

DR_PREP0 and the two U=true transactions are finite and stay within3 steps;
they separate a fresh edge from an already-held direction. No
single-step F/reset ambiguity or cam aliasing is smuggled into these probes.
Those unrelated pending questions remain outside this bounded show batch.

The local runtime supports the no-collision next-call step2 control (existing
combined-3b/3c evidence) but intentionally refuses pending-write/request and
reset/advance collisions. These sources remain native-emission probes, not
requested success traces through ambiguous local runtime paths.

## What root records, and what may close a question

For every project: source hash, pre/post-save SMBP hashes, editor version,
TM200CE40T/Man21 config, actual active native collection/graph, compile/open/save/
reopen outcomes. For every transaction: question ID, local transaction ordinal,
input-set and echo, MW15, all staged observations, native bit/step UI if present,
and screenshots/time references. The optional UI numeric current-step display
is only a display; never invent a PLC numeric SC/SBR operand to observe it.

Keep known controls separate from unknown hypotheses in the final record.
`manifest.json` expands the exact ordered input sets (including each setup)
and has expected=null/status=PENDING_NATIVE_OBSERVATION for every
question and no prefilled actual result. A hypothesis list is nonexhaustive.
Only actual observations of the exact saved bytes may replace pending; if two
hypotheses give the same trace, report that equivalence instead of choosing an
internal order. If sparse SC landmarks are inconclusive, identify the native
active step using the official UI/bit list; otherwise keep the answer pending.
Do not claim a finite capture settles all first-call, skipped/repeated-call,
cold/warm/INIT/STOP variants or physical hardware behavior.

No new simulator classes or compiler fixes are included. Root can keep local
checks for the documentary controls and preserve intentional ambiguous-domain
VM errors while running the official batch. Tool refusal, failed setup, native
project refusal, and observed native behavior are distinct result categories.
