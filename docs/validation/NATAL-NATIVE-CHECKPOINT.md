# Natal native acceptance checkpoint

2026-11-06. **The finite editor/simulator campaign is closed with explicit limits.**
This is an experimental software checkpoint, not a complete-controller or physical
PLC qualification. The release scope remains [Natal da Liberdade](../GOAL.md).

The fixed batch contains eleven composed project profiles and three sequence
observation probes. The selected official saves reopened with **No error**.
Ladder was visibly checked, and generated and official-saved byte hashes were
recorded separately. The [machine-readable checkpoint](native-campaign-2026-11-06/checkpoint.json)
retains the original failures, selected revisions and pending runtime states.

## Two defects found by the official editor and saved-file checks

1. **Negative schedule-enable masks.** The public API exposes signed `i16`, but
   native `%SW114` rejects a decimal `-1`: “out of authorized bounds (0...65535)”.
   The compiler now writes the same word pattern as `16#FFFF`. Comparisons and
   arithmetic use an ordinary signed MW carrier, preserving C++ signed ordering.
   Both original C++ programs were regenerated unchanged, opened, saved and
   freshly reopened with **No error**. The [before](native-campaign-2026-11-06/g09-schedule-memory-before-errors.png)
   and [after](native-campaign-2026-11-06/g09-schedule-memory-after-reopen.png)
   captures show the actual editor result. This rule is scoped to the observed
   SW114 domain; it does not guess unsigned ranges for other system words.
2. **Omitted native defaults on save.** Schneider keeps the actual SBR/SC
   instructions while omitting their fixed default configuration rows. The
   importer now resolves only referenced, bounded SBR/SC default instances,
   including references inside subroutines. It preserves explicit configuration
   and continues to reject invalid operands, malformed rows and missing
   meaningful Drum configuration. Three formerly refused official saves now
   pass actual-program import, reverse C++, recompilation and rebuilt import.
   One old malformed-project test was corrected: it now removes meaningful
   Drum configuration instead of rejecting a legitimate default SC omission.
   The affected method passed; the original failure remains in the
   [historical log](native-campaign-2026-11-06/default-focused-tests-historical.log),
   with the [successful follow-up](native-campaign-2026-11-06/default-contract-followup.log)
   and [fixed-save result](native-campaign-2026-11-06/fixed-schedule-readback-summary.json)
   recorded separately.

The focused checks include signed mask boundaries, comparisons in both operand
positions, dynamic words, sticky flags, real vendor-derived default omissions,
malformed configuration, model limits and reverse conversion. The unchanged
schedule examples also passed their three original traces: **19 positions across
seven routes, 133 matching observations**. These focused results supplement the
earlier [1,017-test regression record](NATAL-INTEGRATION-PROGRESS.md); they do not
replace its eight explicit oracle/SDK-adapter failures with a full-suite PASS.

## Runtime observed so far

The official local TM200CE40T simulator showed identical PC/controller
applications and RUN for the saved composed supervisor. Observed controls:

- I/O 0, 7, 8 and 15: high and released output masks matched.
- TON/TOF: held enable produced mask 3; released enable returned to 0.
- FIFO/LIFO: storing 11 then 22 produced first-pop mask 144, then 101;
  held requests did not repeat, and reset returned to empty mask 5.
- Light enable/inhibit: enabled mask 6, inhibit 8, release 6, disabled 0.

The bounded light captures observed one phase only. Alternation and period
remain unqualified; the 20 ms TP pulse was not measured. A strict screenshot
decoder refused the green Q4 glyph; the original captures were visually checked
without relaxing its threshold. The [runtime summary](native-campaign-2026-11-06/supervisor-runtime-summary.json)
keeps these distinctions. The simulator was stopped through the official UI;
its process and TCP 502 listener exited before the next project was opened.

## Subsequent finite campaign results

The [first bounded session](native-campaign-2026-11-06/RUNTIME-RESULTS.md) added
36 matching output checks across six profiles: subroutines, repeated stateful
calls, interior sequences, direct Drum outputs, calendar and schedule controls.
Its four unexecuted timebox records remain historical evidence.

The [four-profile follow-up](native-campaign-2026-11-06/runtime-remaining-4/SUMMARY.md)
added 40 matching output checks. DR/RTC light phases and inhibit controls were
observed; schedule reservation Q controls matched. Existing native READ diagnostic
rungs showed COMMERROR=6/OPERERROR=0, without a predeclared numeric expectation or
established cause. This is an observed error path, not a successful transaction.
All eleven composed profiles now have some runtime evidence; that does not
qualify every behavior or timing. The three unknown-outcome sequence probes,
reservation live M0/M1 values and other stated limits remain pending.

The [independent asynchronous SDK backend](G11-SDK-ASYNC-RESULTS.md) subsequently
passed local raw-PDU snapshot/cancellation/codec checks. Its SDK result is
separate from the official simulator observations. The exact native Modbus
emission stayed identical to its pinned baseline.

See the [Natal handoff](NATAL-DELIVERY.md) for the current scope and final local
regression evidence. Already implemented extra capabilities are retained;
deferred full-controller work does not block this experimental delivery.

Windows transfer, physical ports/loads, hardware timing, retention and real
communication peers remain later external gates. All checks run locally;
GitHub Actions remains disabled.
