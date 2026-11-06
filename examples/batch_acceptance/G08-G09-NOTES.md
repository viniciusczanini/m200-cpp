# Prepared G08/G09 batch variants

`pending_g08_g09_profiles.json` is a registry of seven concrete source/configuration
profiles and thirteen literal cases (95 positions). It is **not** an active
integration descriptor. Read lane contracts as API proposals; activate a variant
only after root supplies an immutable integrated freeze and its compiler hashes.

| Package | Variant | Literal cases / positions | Output ownership |
|---|---|---|---|
| G08 | sequences-memory | 1 / 16 | SBR0, SC1, DR2; cams M40..42; Q are observations |
| G08 | drum-clock-lights | 1 / 17 | DR0, two Clock timers; M cams gate three Q lamps |
| G08 | drum-direct-outputs | 1 / 10 | DR7 exclusively owns Q0..2; diagnostic uses Q8 |
| G09 | calendar-lights | 6 / 23 | Native S/SW route, snapshot MW100..104, elapsed MD110 |
| G09 | rtc-clock-lights | 1 / 10 | Calendar window gates an elapsed Clock and lamp pair |
| G09 | schedule-memory | 2 / 13 | Sparse SCH0/SCH15 own separate M60/M61; Q lamps only read them |
| G09 | schedule-reservation | 1 / 6 | Schedules own M0/M1 without application reads; harness observes allocation safety |

G08 is prepared and has not been executed. The vectors use interior SC moves,
zero vacated SBR endpoints, separate reset/direction edges and distinct DR cams.
They intentionally avoid unresolved endpoint fills, active-step rewrites and
collisions. Those cases remain `PENDING_NATIVE` in the registry. Loop sums,
held/released buttons, Clock phase edges, STOP and restart are observable through
lamp outputs and explicit public words. DR Q cams have a separate profile so
ordinary packed output writes cannot hide or overwrite their effects.

RTC cases use explicit `rtc_seed` dictionaries. `native_probe.py` seeds the SDK
host calendar; the VM receives `RtcClock(**rtc_seed)`. Neither reads the Mac clock.
The source uses documented S50/SW50..53 transactions and ordinary native S/SW
operands. The light algorithm explicitly chooses inclusive start/exclusive end;
native Schedule endpoint semantics are a separate, pending evidence question.
Schedule cases use interior times, distinct M outputs and next-MAST property/
enable-mask behavior. Native RTC_EXEC block/graph export remains gated and is
not used as a shortcut.

In the first authorized G09 freeze (`natal-combined-2`), calendar/Clock cases
passed 33 positions in seven local routes. Schedule cases were blocked by the
production constructor-arity mismatch (12 real arguments versus 13 in the
non-native SDK/frontend declarations). Its original failure and pin checks are
preserved under `output/parallel-implementation-2026-11-06/integration/combined-2/test-batch/`.
This historical result does not qualify another freeze or official software.
After the constructor/reservation fix, `natal-combined-2b` passed both Schedule
cases and the M0/M1 reservation control: 19 positions in seven routes. The earlier
seven RTC cases were not repeated. That scoped report is preserved in the
corresponding `integration/combined-2b/test-batch/` directory.

Activation creates reviewed `tests/batch_acceptance/integrations/*.json` files
from selected registry entries, adds `main_integration.status="confirmed"`, an
exact root notice and the freeze's compiler hashes. `case_ids` selects the entry's
cases from its bundle. Unactivated G08 entries must not enter a G09-only run.
For example, after that explicit activation:

```sh
python3 tests/batch_acceptance/batch.py prepare --output output/rtc-frozen-batch \
  --variant g09-calendar-lights --variant g09-rtc-clock-lights \
  --variant g09-schedule-memory
python3 tests/batch_acceptance/batch.py run --batch output/rtc-frozen-batch \
  --allow-incomplete
```

The finite manifest keeps all 250 IDs. Pending and `DEFERRED_VERSION` rows remain
visible and cannot become PASS from source preparation or a scoped local run.
Editor, official simulator and physical qualification are separate gates.
