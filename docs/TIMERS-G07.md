# Timers and composition

The [integration record](validation/NATAL-INTEGRATION-PROGRESS.md) includes local
SDK/VM, native project/reverse, mode/level and boundary tests. Exact expanded
editor/simulator acceptance and physical timing remain separate gates.

All five documented bases (1/10/100/1000/60000 ms), TON/TOF/TP, P/V/Q and
existing constructors remain. IDs are 0..254, 1 ms only at 0..5, P is 0..9999.
`execute(bool)` updates IN without reading Q or fabricating a wired coil.
`update(bool)` returns Q. Both permit conditional calls and repeated static
sites. Skipping a call preserves the previous IN; it does not pass false.
Elapsed timing continues across skipped calls. Conditional calls use native
control flow; loops remain loops, and existing CFG allocation reuses scratch.

The configured JSON fields remain `kind`, `milliseconds`, `base_ms`,
`retentive`, `dynamic_preset`. Reverse conversion uses actual timer identities,
configuration and native IN/property accesses. It emits `execute()` for IN so
an input-only block does not acquire an extra Q test in the reverse path.

SMBP admission now follows actual management levels: retention TON/TOF at
>=4.0 conservatively (the Generic Functions guide says3.3, the Operating Guide
and installed metadata say4.0); dynamic TON/TOF/TP at >=12.0. Combined flags are
represented for TON/TOF at >=12.0 on every allowed base. TP retention remains
unavailable. Observed historical `OPTION_CONTEXTS` is evidence only. New
admission does not promote editor/simulator/physical evidence.

Timer configuration and port checking are isolated in `timer_xml.py`,
`timer_il.py`, `timer_graph.py`. Native BLK input-only and output sections are
parsed, local Q is qualified, Boolean branches/stacks and output ST/STN/S/R are
lowered in instruction order. Raw direct-IN timer-only graphs can contain up
to five distinct Timer blocks, checked with IN/Q ports, directed connectivity
and bounded Boolean algebra; multiple blocks in a raw rung require actual
FL>=10.1. Export may split complex logic into equivalent series rungs. No
claim of official acceptance is attached to the added layouts. Mixed-class raw
graphs, indexed/raw numeric side effects, wider native grids, and repeated
identity in one raw graphical rung remain explicit unsupported import cases.
They can still be expressed as ordered C++ operations using separate rungs.

Timer-only host lifecycle hooks are `Machine.timer_event(event)`,
`Machine.advance_time(dt_ms)`, and `Machine.step(..., timer_event=event)`.
CLI/native trace frames accept optional `timer_event` before the scan; dt is
still elapsed AFTER that frame's output. Events: `stop`, `run`, `power_off`,
`warm_restart`, `cold_restart`. STOP suppresses scans but timers advance;
power_off freezes their state until restart; warm_restart excludes outage
time and preserves state; cold_restart clears timer V/Q and restores initial
configured P. SDK host equivalents are `plc::detail::TimerEvent`,
`timer_event`, `timer_advance_time`, and `timer_running`. These are timer hooks,
not a full controller restart/output-fallback model. They are not accepted as
user program operations or emitted as fabricated PLC opcodes. Other memory,
startup flags, tasks/events and persistence orchestration are deferred.

Local timing keeps the prior activation/resume-relative tick policy. Retentive
IN pauses retain whole ticks; the warm power-outage hook retains fractional
phase too. Dynamic changes take effect on the next base tick, and a completed
activation is latched until its documented IN restart. Native tick phase,
fraction handling, after-completion P changes, runtime invalid P effects,
lifecycle Q/edge preservation and physical accuracy require native tests.
Runtime P outside0..9999 still fails explicitly rather than inventing a native
clamp, wrap, flag or recovery behavior.

Sources read locally: EIO0000003289.04 pp103–104,107–119; EIO0000003281.04
pp49–50,55; EIO0000002019.06 pp24–26; existing level map and pinned timer
fixtures/research. `examples/timer_composition.cpp` is source-only usage.
No test, build, validator, compiler, generator, editor or simulator was run.
