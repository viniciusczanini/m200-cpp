# Functional parity with the Schneider TM200CE40T profile

The user reinforced this requirement on 2026-11-05: every algorithm that can be
programmed and accepted by the official software for their TM200CE40T must be
expressible in C++ with this project's library, producing an equivalent project.

This is the final coverage criterion. The subset implemented today is a
development milestone, not an authorized reduction of that objective.

## Contract

For every valid native program within the identified model, firmware, functional
level, editor version and hardware configuration profile, there must be a
supported way to write it in C++ with the library. The compiler must generate a
project that the editor accepts and that preserves observable behavior.

This requires instructions, types, addresses, configuration and execution to be
covered together. A function declared in a header, an implemented Modbus PDU or
one passing example does not complete coverage of a feature.

The user does not require full desktop C++. A restricted source language is
acceptable provided it can express every algorithm available within the
controller's official profile. Heap allocation, an operating system and desktop
libraries are not required by this contract; arrays, control flow and blocks
that correspond to native resources cannot be excluded from the objective.

## Equivalence that must be preserved

- Operation order within a scan, reads before/after writes and address/type
  aliasing, including communication buffers.
- Numeric width, signedness, representation, conversions, flags and error
  handling. Native algorithms that inspect and handle flags must also be
  expressible; the current policy of stopping simulation does not replace
  that functionality in the final library.
- Loops, jumps, conditions, subroutines, functions, user-defined blocks and
  state/Grafcet sequences permitted by the official profile. A loop within a
  scan must not be silently distributed across scans.
- Every permitted task, including its events, priorities, preemption and memory
  access rules. The current single master `scan()` is a provisional limitation.
- The I/O image and immediate access when requested by the program; retention,
  startup, reset, STOP/RUN, resumption and fallback according to configuration.
- Blocks, system objects and dynamic properties: timers, counters, registers,
  tables, strings, RTC, PID, HSC, pulses, motion and all other resources actually
  permitted by the target.
- Communication and its states/errors, including Modbus, channel configuration,
  mappings, properties writable at runtime and contention for a port.
- Peripheral and expansion configuration compatible with the profile. Supporting
  an option does not mean asserting that it is physically connected.

Resources from other models do not automatically enter the contract. The target
remains TM200CE40T, with identified options and functional levels.

## Capacity and diagnostics

The former fixed temporary reservations (%M500..1023 and words starting at 4000)
were replaced by allocation across the entire bank and CFG liveness analysis.
The final implementation still needs sufficient allocation, reuse and emission
to represent native programs that fit the profile, accounting for the compiler's
own memory overhead. Direct access to native resources may complement the
high-level API; it must not require the user to write Ladder or IL manually.

Diagnostics must distinguish:

1. A resource incompatible with the controller's actual profile.
2. A program exceeding a real profile limit, identifying that limit.
3. A C++ construct outside the source language, identifying the supported way
   to express the same native feature when one exists.
4. A gap in the compiler, library, decompiler or exporter. An officially accepted
   feature that has not yet been implemented is pending work, not an algorithm
   that is impossible for the PLC.
5. Behavior or compatibility that has not yet been externally demonstrated.

The contract does not assume that termination or worst-case execution time can
be proved statically for every algorithm. Preserving native execution/watchdog
rules and recording what has not been demonstrated are mandatory; uncertainty
must not be replaced with a timing guarantee.

## Project output and reverse conversion

The deliverable remains a project opened by the official software, with coherent
visualization and symbols, and program transfer performed through that software.
The original request for Ladder visualization remains a backend requirement.
Native cases without direct reversibility to Ladder require an explicit,
validated solution; they must not be omitted or treated as covered by a file
containing only IL text for manual assembly.

Reverse conversion must recover equivalent C++ from the actual program,
preserving the addresses/identities and configuration required by its semantics.
It does not need to recover the original C++ syntax or exact names. Embedding a
copy of the source in metadata or retaining opaque logic without translating it
does not demonstrate this reverse path.

## Completion criteria

- Identify the exact official profile and inventory every feature, mode,
  operand, configuration and restriction actually available within it.
- For each one, provide its C++ expression, internal representation, native
  generation, configuration, visualization and reverse conversion.
- Exercise feature composition, limits, errors and lifecycle using independent
  references and official/real programs. A list of isolated examples does not
  replace that coverage.
- Open, compile, visualize, save and reopen the exact artifacts in the editor;
  compare execution with the official simulator and with hardware where needed.
- Bind results to the tested bytes and versions. A finite test suite is evidence,
  not a mathematical proof of correctness for every program.
- Keep gaps visible until they are closed. The library must not be declared
  complete while any native algorithm/feature in the profile lacks a supported
  equivalent expression.

The implementation remains experimental and partial. Local regression evidence,
including [LOCAL-RESULTS.md](validation/LOCAL-RESULTS.md), and the
[capability inventory and pending work](capabilities/README.md) record progress.
Official editor validation/save/reopen, official simulator execution, Windows/driver
integration and physical-controller verification are separate evidence stages.
Selected exact projects now have [official editor/simulator observations](validation/OFFICIAL-EDITOR-RESULTS.json)
in the authorized Wine lab, including [bounded timer behavior observations](validation/TIMER-OPTIONS-OFFICIAL-OBSERVATIONS.md).
Those results apply only to the identified artifacts, configurations and phases;
they do not establish complete profile compatibility. Windows/driver and physical
TM200CE40T validation remain pending. This does not remove the remaining local
work on the language, blocks, allocation and backend.
