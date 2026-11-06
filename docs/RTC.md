# RTC, calendar and schedules

Local calendar, staged-write, schedule and project/reverse results are in the
[integration evidence](validation/NATAL-INTEGRATION-PROGRESS.md). This does not
establish native boundary/lifecycle behavior, physical retention or the still
missing RTC_EXEC graphical binding.

`plc::Clock` remains an elapsed timer oscillator. It is not the RTC. The native
calendar source is never the host's wall clock. See `examples/rtc_calendar.cpp`
for the complete documented S/SW route: calendar snapshot, date/time conditions,
inclusive start/exclusive end, overnight OR, and BCD set transaction. This route
uses ordinary native operations/contacts/coils and does not need an RTC FB graph.

## Public API

- `i16 read_system_word(int index)`, `void write_system_word(int index,i16)`.
  This lane owns reads SW18/19,49..60,114,118, and writes18/19,50..53,59/60,114.
  SW49..53 are weekday,00SS,HHMM,MMDD,CCYY BCD. SW54..57 describe last STOP,
  SW58 its cause. Raw words are signed16-bit bit patterns.
- `bool system(int index)` additionally reads S50/51/52/59.
  `void write_system(int index,bool)` writes S50/51/59. S52 is read-only.
- `void rtc_snapshot(int first_word)` writes five words in MW, starting with
  weekday. Range0..7995 (or configured word-image size minus5). Frontend reserves
  all five cells before allocating private memory. This is five scalar reads;
  local scan-image coherence is **not** a native atomicity guarantee.
- `i32 absolute_counter_100ms()` uses `SW19*32768+SW18`, treating SW19 as unsigned.
  Frontend emits a native high/low/high retry loop to detect carry, not unrolled
  states. Wrap is31bits. SW18 writes are restricted to0..32767; SW19 preserves
  all16bits. The write-limit policy needs native boundary observations.
- `Rtc{index,day,month,year,hours,minutes,seconds}`, explicit index0/1.
  `update(enable,read,write)`, `done/error`, `day_of_week/error_id`, and
  `day/month/year/hours/minutes/seconds` getters and corresponding `set_*` setters.
- `Schedule{index,bank,output,sd,sm,sh,sn,ed,em,eh,en,dow}`. Index0..15, bank0=M,
  bank1=Q0; output range follows the real bank. Get/set methods `start_day`,
  `start_month`, `start_hour`, `start_min`, `end_day`, `end_month`, `end_hour`,
  `end_min`, `dow`. DOW bits0..6 are Monday..Sunday, established by installed
  vendor `ConversionHelper.ScheduleBlockDaysOfTheWeekMaskBuilder` CIL.

Program/JSON adds `rtcs` and `schedules` canonical decimal-key maps, serialized
from `RtcConfig` and `ScheduleConfig` respectively. Missing maps remain empty,
so existing v1/v2 JSON stays accepted. Configuration lives in real program data,
not source comments. Reverse reconstructs the actual operands/instructions and
configuration, including sparse block identities. RTC_EXEC is an explicitly
internal terminal IR instruction (`LD enable; RTC_EXEC %RTCn read write`). CLI
IL output warns when it is present. It is never passed to native project export.

## Local execution and calendar boundaries

`Machine(program,rtc=RtcClock(2028,2,29,23,59,59,valid=True))` injects an explicit
clock. Omitted clock is present but invalid (S51=1); no read is reported successful
on missing/invalid RTC. Elapsed counter and battery calendar advance independently.
`machine.rtc.reset(cold=True)` restores configured RTC/schedule members, enables
all schedules, and resets the absolute counter while preserving battery time and
SW60 correction. `reset(cold=False)` preserves member/request state, but resets
staging/adjust controls and S52. This API resets this family only. `rtc.stop(cause)`
captures STOP words; it does not stop the whole Machine/task engine. Corresponding
host SDK hooks are `detail::rtc_seed`, `detail::rtc_reset`, `detail::rtc_stop`.
They are host harness controls, not admitted PLC C++ calls.

S50 freezes the image; falling S50 validates BCD/ranges/Gregorian combination and
commits all four fields atomically. Failure leaves battery time unchanged and
sets S52. Weekday is recomputed. Writes outside the staging gate fail explicitly
in the host model; actual unprotected-write behavior is not claimed. S51 is a
validity bit; physical correction-constant storage on its falling edge is pending.
Year2000..32767 is allowed in RTC configuration per installed metadata; local host
calendar supports through9999. Attempting to execute outside this representation
fails as a model gap, not as a claim that the PLC rejects that year.

RTC read updates fields continuously; write consumes WR rising; disabled clears
outputs, request history and DayOfWeek. RD+WR gives256; S50 conflict257; invalid
components1/2/3/5/6/7, invalid combination8, unavailable/internal9. Error priority,
first-enable edge treatment, invalid-read policy and retained status after a held
WR are explicit local policies requiring official observations.

Schedules run at MAST entry; same-output blocks OR, including sparse identities.
Field and SW114 changes affect the next MAST. Cold reset restores configuration.
Local policy combines an annual date window with a daily time window; each can
wrap. End minute is inclusive; equal endpoints select that date/minute. Invalid
runtime fields deactivate that block. These choices are **not** promoted to native
facts. The manual does not disambiguate wrap, equality, end-minute and invalid-field
behavior. The algorithmic raw S/SW route lets C++ choose its own explicit policy.

For adjustment, the target M200 programming guide says to sample SW59 on S59 rising.
That policy is implemented. Generic Functions instead describes rising component
bits while S59 is enabled; the source conflict remains an acceptance case. Local
seconds/minutes/hours/day adjustments carry; months/years clamp to last valid day.
SW60 accepts direction bit7 and magnitude0..30 and corrects once on Sunday00:00:30;
physical persistence, calibration/drift and exact correction/tick phase are pending.
SW118 stays an independent controller-status word; absence of RTC is not fabricated
as a whole-controller error bitmap.

## Native bindings and acceptance boundary

`rtc_xml.py` reads/writes RTC parameters and ScheduleBlocks using exact names
extracted statically from installed vendor adapters. Schedule dates use the
adapter's `XmlConvert` unspecified timestamp form, with reference year2012;
code generation reads only month/day/HH:mm. Native configured schedules require
capacity16; dynamic SCH members require functional level6.0, RTC blocks5.0.
Existing management tokens are interpreted using the existing ordinal map.
No template level or CPU is rewritten. `SchsMemoryAllocation` uses the observed
empty editor default; nondefault allocation behavior needs official acceptance.

No native RTC IL pin/graph binding has been established. Export of RTC_EXEC fails
with a compiler-gap diagnostic directing users to S50/SW services. Import of a real
native RTC update block remains pending. RTC config/property-only serialization
and ScheduleBlocks are unvalidated adapter-based candidates, not editor proof.
No invented Ladder enum or vendor instruction is emitted to bypass this gap.

Integration with G02 must union system-word dispatch/permitted words (including
G02's SW17) in SDK/frontend/numeric/VM/reverse. Do not overwrite either family's
word service with the other. No global capability gate/evidence was changed.
