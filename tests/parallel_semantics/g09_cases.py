"""Independent G09 literals, with native rules separated from local policies.

Primary cached sources: EIO0000003289.04 pp160,164-165,207-211;
EIO0000002019.06 pp322-324,329-331,334. No production date/BCD helpers
generate these expectations. Calendar vectors include Gregorian century rules.
"""
from .contracts import Case


CASES = []
SCAN = {"scan": {}}
PROBE = {"probe": True}


def add(name, source, clock, observe, events, expected, basis, **extra):
    request = {"source": "#include <plc.hpp>\n" + source, "clock": clock,
               "observe": observe, "events": events, **extra}
    CASES.append(Case("G09_frozen_" + name, ("G09",), ("HW.RTC",), "G09_frozen",
                      basis, request, expected))


CAL = {"calendar": True}
BCD = {"calendar": True, "system_words": [49, 50, 51, 52, 53]}

# Explicit before/after dates and ISO weekday literals. SDK's ordinal calculation
# and Python's datetime implementation are both subjects, not this oracle.
vectors = [
    ([2000, 2, 28, 23, 59, 59], [2000, 2, 29, 0, 0, 0], [2, 0, 0, 0x0229, 0x2000]),
    ([2000, 2, 29, 23, 59, 59], [2000, 3, 1, 0, 0, 0], [3, 0, 0, 0x0301, 0x2000]),
    ([2100, 2, 28, 23, 59, 59], [2100, 3, 1, 0, 0, 0], [1, 0, 0, 0x0301, 0x2100]),
    ([2028, 2, 28, 23, 59, 59], [2028, 2, 29, 0, 0, 0], [2, 0, 0, 0x0229, 0x2028]),
    ([2028, 2, 29, 23, 59, 59], [2028, 3, 1, 0, 0, 0], [3, 0, 0, 0x0301, 0x2028]),
    ([2026, 4, 30, 23, 59, 59], [2026, 5, 1, 0, 0, 0], [5, 0, 0, 0x0501, 0x2026]),
    ([2026, 12, 31, 23, 59, 59], [2027, 1, 1, 0, 0, 0], [5, 0, 0, 0x0101, 0x2027]),
    ([2026, 11, 8, 23, 59, 59], [2026, 11, 9, 0, 0, 0], [1, 0, 0, 0x1109, 0x2026]),
]
events, expected = [], []
for before, after, bcd in vectors:
    events += [{"seed": before}, {"advance_ms": 1000}, SCAN]
    expected.append({"calendar": after, "system_words": bcd})
add("Gregorian_calendar_rollovers", "void scan(){}", vectors[0][0], BCD, events, expected,
    "Gregorian literal leap/century/month/year/weekday boundaries; BCD layout from M200 p330.")

add("snapshot_five_cells_and_canaries", r'''
void scan(){plc::write_word(9,1234);plc::write_word(15,4321);plc::rtc_snapshot(10);}
''', [2028, 2, 29, 23, 58, 57], {"words": list(range(9, 16))}, [SCAN],
    [{"words": [1234, 2, 0x0057, 0x2358, 0x0229, 0x2028, 4321]}],
    "M200 p330 BCD image; exactly five writes, preserving both adjacent cells. Local scan coherence does not prove native atomic snapshot.")

stage_source = r'''
void scan(){
 if(plc::input(0)){plc::write_system(50,true);plc::write_system_word(50,0x0009);plc::write_system_word(51,0x0708);plc::write_system_word(52,0x0231);plc::write_system_word(53,0x2026);}
 if(plc::input(1)){plc::write_system(50,false);}
 if(plc::input(2)){plc::write_system(50,true);plc::write_system_word(50,0x0058);plc::write_system_word(51,0x2359);plc::write_system_word(52,0x0229);plc::write_system_word(53,0x2028);}
}
'''
add("S50_atomic_invalid_combination_then_valid_clears_S52", stage_source,
    [2026, 1, 31, 23, 59, 59], {**BCD, "system_bits": [50, 51, 52]},
    [{"scan": {0: 1}}, {"advance_ms": 2000}, SCAN, {"scan": {1: 1}}, {"scan": {2: 1}}, {"scan": {1: 1}}],
    [
      {"calendar": [2026, 1, 31, 23, 59, 59], "system_words": [6, 9, 0x0708, 0x0231, 0x2026], "system_bits": [1, 0, 0]},
      {"calendar": [2026, 2, 1, 0, 0, 1], "system_words": [6, 9, 0x0708, 0x0231, 0x2026], "system_bits": [1, 0, 0]},
      {"calendar": [2026, 2, 1, 0, 0, 1], "system_words": [7, 1, 0, 0x0201, 0x2026], "system_bits": [0, 0, 1]},
      {"calendar": [2026, 2, 1, 0, 0, 1], "system_words": [7, 0x58, 0x2359, 0x0229, 0x2028], "system_bits": [1, 0, 1]},
      {"calendar": [2028, 2, 29, 23, 59, 58], "system_words": [2, 0x58, 0x2359, 0x0229, 0x2028], "system_bits": [0, 0, 0]},
    ], "M200 pp322-323 S50 frozen image/falling commit and S52 failed/successful request; invalid update must not partially alter battery time.")

for word, bad in [(50, 0x006A), (51, 0x1A00), (52, 0x0A01), (53, 0x20A8)]:
    add("invalid_BCD_nibble_SW" + str(word),
        "void scan(){if(plc::input(0)){plc::write_system(50,true);plc::write_system_word(" + str(word) + "," + str(bad) + ");}if(plc::input(1)){plc::write_system(50,false);}}",
        [2028, 2, 29, 12, 34, 56], {"calendar": True, "system_bits": [50, 52]},
        [{"scan": {0: 1}}, {"scan": {1: 1}}],
        [{"calendar": [2028, 2, 29, 12, 34, 56], "system_bits": [1, 0]}, {"calendar": [2028, 2, 29, 12, 34, 56], "system_bits": [0, 1]}],
        "M200 pp322-323 invalid BCD transaction rejected atomically. Bad nibble is isolated in one independently staged word.")

read_source = r'''
plc::Rtc rtc{1,1,1,2026,0,0,0};
void scan(){rtc.update(true,true,false);plc::write_word(0,rtc.error_id());plc::write_word(1,rtc.day_of_week());plc::write_word(2,rtc.day());plc::output(0,rtc.done());plc::output(1,rtc.error());}
'''
add("invalid_clock_never_fabricates_success", read_source, [2028, 2, 29, 12, 0, 0],
    {"words": [0, 1, 2], "bits": [0, 1], "system_bits": [51]},
    [SCAN, {"write_bit": [51, False]}, SCAN],
    [{"words": [9, 0, 1], "bits": [0, 1], "system_bits": [1]}, {"words": [0, 2, 29], "bits": [1, 0], "system_bits": [0]}],
    "M200 S51 invalidity; local FB invalid-read maps to internal error9, not a vendor-certified unavailable-clock rule.", valid=False)
add("unavailable_clock_read_error9", read_source, [2028, 2, 29, 12, 0, 0],
    {"words": [0, 1, 2], "bits": [0, 1], "system_bits": [51]}, [SCAN],
    [{"words": [9, 0, 1], "bits": [0, 1], "system_bits": [1]}],
    "Explicit local absent peripheral policy; no host wall clock or successful read is substituted.", available=False)

writer_source = r'''
plc::Rtc rtc{0,29,2,2028,12,0,0};
void scan(){if(plc::input(3)){rtc.set_seconds(10);}rtc.update(!plc::input(2),plc::input(1),plc::input(0));
 plc::write_word(0,rtc.error_id());plc::write_word(1,rtc.day_of_week());plc::output(0,rtc.done());plc::output(1,rtc.error());}
'''
add("write_request_history_held_fresh_disabled_and_collisions", writer_source,
    [2026, 1, 1, 0, 0, 0], {"calendar": True, "words": [0, 1], "bits": [0, 1]},
    [{"scan": {0: 1}}, {"scan": {0: 1, 3: 1}}, SCAN, {"scan": {0: 1}}, {"scan": {0: 1, 2: 1}},
     {"scan": {0: 1}}, {"scan": {0: 1, 1: 1}}, {"write_bit": [50, True]}, {"scan": {1: 1}},
     {"write_bit": [50, False]}, {"scan": {1: 1}}],
    [
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [0, 2], "bits": [1, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [0, 2], "bits": [1, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [0, 2], "bits": [0, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [0, 2], "bits": [1, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [0, 0], "bits": [0, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [0, 2], "bits": [1, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [256, 2], "bits": [0, 1]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [257, 2], "bits": [0, 1]},
      {"calendar": [2028, 2, 29, 12, 0, 10], "words": [0, 2], "bits": [1, 0]},
    ], "Generic pp164-165 continuous RD, rising WR, disabled outputs, errors256/257. Held status, first WR and disabled history clearing are explicit local lifecycle policy.")

for field, value, code in [("year", 1999, 1), ("month", 13, 2), ("day", 0, 3), ("hours", 24, 5), ("minutes", 60, 6), ("seconds", 60, 7), ("day", 30, 8)]:
    add("FB_component_error_" + str(code),
        "plc::Rtc rtc{0,29,2,2028,12,0,0};void scan(){rtc.set_" + field + "(" + str(value) + ");rtc.update(true,false,true);plc::write_word(0,rtc.error_id());plc::output(0,rtc.done());plc::output(1,rtc.error());}",
        [2026, 1, 1, 0, 0, 0], {"calendar": True, "words": [0], "bits": [0, 1]}, [SCAN],
        [{"calendar": [2026, 1, 1, 0, 0, 0], "words": [code], "bits": [0, 1]}],
        "Generic p165 error table; invalid field/combination changes no battery components. No error4/week input exists in the admitted API.")

add("M200_SW59_S59_edges_and_month_year_clamp", r'''
void scan(){plc::write_system_word(59,2);if(plc::input(1)){plc::write_system_word(59,4);}if(plc::input(2)){plc::write_system_word(59,512);}if(plc::input(3)){plc::write_system_word(59,32);}if(plc::input(4)){plc::write_system_word(59,64);}plc::write_system(59,plc::input(0));}
''', [2028, 1, 31, 23, 59, 59], CAL,
    [{"scan": {0: 1}}, {"scan": {0: 1, 1: 1}}, SCAN, {"scan": {0: 1, 2: 1}}, SCAN, {"scan": {0: 1, 3: 1}}, SCAN, {"scan": {0: 1, 4: 1}}],
    [{"calendar": c} for c in [[2028, 2, 1, 0, 0, 0], [2028, 2, 1, 0, 0, 0], [2028, 2, 1, 0, 0, 0], [2028, 1, 31, 23, 59, 59], [2028, 1, 31, 23, 59, 59], [2028, 2, 29, 23, 59, 59], [2028, 2, 29, 23, 59, 59], [2029, 2, 28, 23, 59, 59]]],
    "M200 p331 samples SW59 on S59 rising (conflicts with Generic component-edge wording); carry/clamp outcomes are documented local policy.")

for correction, first, second in [(3, 33, 35), (130, 28, 30)]:
    add("Sunday_SW60_correction_" + str(correction), "void scan(){}", [2026, 11, 8, 0, 0, 29],
        {"calendar": True, "system_words": [60]},
        [{"write_sw": [60, correction]}, {"advance_ms": 1000}, SCAN, {"advance_ms": 2000}, SCAN],
        [{"calendar": [2026, 11, 8, 0, 0, first], "system_words": [correction]}, {"calendar": [2026, 11, 8, 0, 0, second], "system_words": [correction]}],
        "M200 p331 Sunday00:00:30 correction; direction bit7 and magnitude0..30. Negative correction must not retrigger crossing the same point.")

add("absolute_counter_carry_unsigned_high_wrap_and_SW17_independence", r'''
void scan(){if(plc::input(0)){plc::write_system_word(17,5);plc::write_system_word(18,32767);plc::write_system_word(19,0);}
 if(plc::input(1)){plc::write_system_word(18,32767);plc::write_system_word(19,-1);}plc::write_dword(0,plc::absolute_counter_100ms());}
''', [2028, 2, 29, 12, 0, 0], {"calendar": True, "words": [0, 1], "system_words": [17, 18, 19]},
    [{"scan": {0: 1}}, {"advance_ms": 100}, SCAN, {"scan": {1: 1}}, {"advance_ms": 100}, SCAN, {"reset": "cold"}, SCAN],
    [
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [32767, 0], "system_words": [5, 32767, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [32768, 0], "system_words": [5, 0, 1]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [65535, 32767], "system_words": [5, 32767, 65535]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [0, 0], "system_words": [5, 0, 0]},
      {"calendar": [2028, 2, 29, 12, 0, 0], "words": [0, 0], "system_words": [5, 0, 0]},
    ], "M200 p329 low radix32768 and unsigned high, reset on cold. 31-bit wrap and family-only SW17 preservation are explicit host contract.")

add("RTC_continues_across_timer_only_STOP_and_off", "void scan(){plc::inc_word(0);}",
    [2026, 12, 31, 23, 59, 59], {"calendar": True, "words": [0], "system_words": [18, 19]},
    [SCAN, {"timer_event": "stop"}, {"advance_ms": 1000}, {"timer_event": "run"}, SCAN,
     {"timer_event": "power_off"}, {"advance_ms": 2000}, {"timer_event": "warm_restart"}, SCAN],
    [{"calendar": [2026, 12, 31, 23, 59, 59], "words": [1], "system_words": [0, 0]},
     {"calendar": [2027, 1, 1, 0, 0, 0], "words": [2], "system_words": [10, 0]},
     {"calendar": [2027, 1, 1, 0, 0, 2], "words": [3], "system_words": [30, 0]}],
    "Explicit integrated family-only hooks: battery RTC and absolute counter continue while timer STOP/off suppresses CPU calls. No physical power-retention claim.")

add("family_warm_preserves_WR_history_cold_restores_config", r'''
plc::Rtc rtc{0,29,2,2028,12,0,0};
void scan(){if(plc::input(0)){rtc.set_day(28);}if(plc::input(2)){rtc.set_day(29);}rtc.update(true,false,plc::input(1));
 plc::write_word(0,rtc.day());plc::write_word(1,rtc.day_of_week());plc::output(0,rtc.done());}
''', [2026, 1, 1, 0, 0, 0], {"calendar": True, "words": [0, 1], "bits": [0]},
    [{"scan": {0: 1, 1: 1}}, {"scan": {1: 1, 2: 1}}, {"reset": "warm"}, {"scan": {1: 1}},
     {"reset": "cold"}, {"scan": {1: 1}}],
    [{"calendar": c, "words": w, "bits": [1]} for c, w in [
      ([2028, 2, 28, 12, 0, 0], [28, 1]), ([2028, 2, 28, 12, 0, 0], [29, 1]),
      ([2028, 2, 28, 12, 0, 0], [29, 1]), ([2028, 2, 29, 12, 0, 0], [29, 2])]],
    "Explicit family-only local reset policy: warm preserves members/request history; cold restores configured members and clears WR history while retaining battery clock. Not a CPU-wide retention claim.")

add("last_STOP_snapshot_survives_calendar_rollover", "void scan(){}",
    [2026, 12, 31, 23, 59, 59], {"calendar": True, "system_words": [54, 55, 56, 57, 58]},
    [{"stop": 3}, {"advance_ms": 1000}, SCAN, {"stop": 4}, SCAN],
    [{"calendar": [2027, 1, 1, 0, 0, 0], "system_words": [0x59, 0x2359, 0x1231, 0x2026, 3]},
     {"calendar": [2027, 1, 1, 0, 0, 0], "system_words": [0, 0, 0x0101, 0x2027, 4]}],
    "M200 p330 last STOP words are a separate four-word BCD snapshot plus cause. Explicit family stop hook records data without simulating a complete controller STOP.")


def schedule(output="%Q0.0", **overrides):
    return dict(output=output, start_day=1, start_month=1, start_hour=12, start_min=0,
                end_day=31, end_month=12, end_hour=13, end_min=0, dow=127, **overrides)


def sched(name, configs, clock, events, expected, basis, observe=None):
    add(name, "void scan(){}", clock, observe or {"bits": [0]}, events, expected, basis,
        mode="schedule_source", schedules=configs)


base_sched = schedule()
mon = {**base_sched, "dow": 1}
tue = {**base_sched, "dow": 2}
sched("schedule_all_seven_weekday_bits_are_distinct", {str(i): {**base_sched, "output": "%Q0." + str(i), "dow": 1 << i} for i in range(7)},
      [2026, 11, 9, 12, 30, 0],
      [event for day in range(9, 16) for event in [{"seed": [2026, 11, day, 12, 30, 0]}, SCAN]],
      [{"bits": row} for row in [[1, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0, 0],
                               [0, 0, 0, 1, 0, 0, 0], [0, 0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 0, 1]]],
      "Vendor static ConversionHelper DOW encoding Monday bit0 through Sunday bit6; known Monday2026-11-09 starts a literal seven-day one-hot trace.",
      {"bits": list(range(7))})
sched("schedule_sparse_OR_weekday_mask_and_next_MAST", {"0": mon, "15": tue},
      [2026, 11, 9, 12, 30, 0],
      [SCAN, {"seed": [2026, 11, 10, 12, 30, 0]}, SCAN, {"seed": [2026, 11, 11, 12, 30, 0]}, SCAN,
       {"seed": [2026, 11, 10, 12, 30, 0]}, SCAN, {"write_sw": [114, 32767]}, PROBE, SCAN,
       {"reset": "cold"}, SCAN],
      [{"bits": [v], "system_words": [mask]} for v, mask in [(1, 65535), (1, 65535), (0, 65535), (1, 65535), (1, 32767), (0, 32767), (1, 65535)]],
      "Generic p160 OR, next MAST and cold SW114=FFFF; DOW Monday bit0..Sunday bit6 from vendor static CIL. Real source pipeline uses corrected Schedule declaration on 2b; native project acceptance remains pending.",
      {"bits": [0], "system_words": [114]})

sched("schedule_end_minute_equality_and_dynamic_restore", {"15": {**base_sched, "dow": 1}},
      [2026, 11, 9, 11, 59, 59],
      [SCAN, {"advance_ms": 1000}, SCAN, {"seed": [2026, 11, 9, 13, 0, 59]}, SCAN,
       {"advance_ms": 1000}, SCAN, {"seed": [2026, 11, 9, 12, 30, 0]}, SCAN,
       {"schedule_set": [15, "ENDHOUR", 12]}, {"schedule_set": [15, "ENDMIN", 0]}, PROBE, SCAN,
       {"reset": "warm"}, SCAN, {"reset": "cold"}, SCAN,
       {"schedule_set": [15, "STARTMONTH", 13]}, SCAN, {"reset": "cold"}, SCAN],
      [{"bits": [v]} for v in [0, 1, 1, 0, 1, 1, 0, 0, 1, 0, 1]],
      "Generic p160 next-MAST and cold configuration restore; inclusive end minute, equality and invalid-field deactivation are explicit local policies, not certified native semantics.")

sched("schedule_annual_and_daily_wrap_local_policy", {"0": {**base_sched, "start_month": 11, "start_day": 1, "end_month": 2, "end_day": 28, "start_hour": 22, "end_hour": 2}},
      [2026, 12, 31, 23, 0, 0],
      [SCAN, {"seed": [2027, 1, 1, 1, 59, 59]}, SCAN, {"seed": [2027, 1, 1, 2, 0, 59]}, SCAN,
       {"seed": [2027, 1, 1, 2, 1, 0]}, SCAN, {"seed": [2027, 6, 1, 23, 0, 0]}, SCAN,
       {"seed": [2027, 2, 28, 22, 0, 0]}, SCAN, {"seed": [2027, 3, 1, 1, 0, 0]}, SCAN],
      [{"bits": [v]} for v in [1, 1, 1, 0, 0, 1, 0]],
      "Explicit annual-window AND daily-window local policy; wrapping windows use OR and final minute is inclusive. These ambiguities remain official acceptance cases.")

sched("schedule_equal_date_and_minute_select_single_window", {"0": {**base_sched, "start_month": 2, "start_day": 29, "end_month": 2, "end_day": 29, "start_hour": 12, "end_hour": 12, "start_min": 34, "end_min": 34}},
      [2028, 2, 29, 12, 34, 0],
      [SCAN, {"advance_ms": 59000}, SCAN, {"advance_ms": 1000}, SCAN, {"seed": [2028, 3, 1, 12, 34, 0]}, SCAN],
      [{"bits": [v]} for v in [1, 1, 0, 0]],
      "Explicit local equality policy selects one recurring date and one complete minute; no universal native equivalence is asserted.")

sched("schedule_invalid_unavailable_clock_is_inactive", {"0": base_sched},
      [2026, 11, 9, 12, 30, 0],
      [SCAN, {"seed": [2026, 11, 9, 12, 30, 0], "valid": False}, SCAN,
       {"seed": [2026, 11, 9, 12, 30, 0], "available": False}, SCAN,
       {"seed": [2026, 11, 9, 12, 30, 0]}, SCAN],
      [{"bits": [v]} for v in [1, 0, 0, 1]],
      "Explicit local invalid/unavailable RTC policy prevents fabricated scheduled output.")

add("schedule_compiled_dynamic_member_and_memory_output", r'''
plc::Schedule schedule{15,0,100,1,1,12,0,31,12,13,0,1};
void scan(){if(plc::input(0)){schedule.set_dow(0);}plc::output(0,plc::read_m(100));}
''', [2026, 11, 9, 12, 30, 0], {"bits": [0], "memory": [100]},
    [SCAN, {"scan": {0: 1}}, SCAN, {"reset": "cold"}, SCAN],
    [{"bits": [v], "memory": [v]} for v in [1, 1, 0, 1]],
    "Generic p160 dynamic fields apply at next MAST and cold restores configuration. Source constructor/setter/read_m traverse real frontend; M100 must remain reserved from compiler scratch.")
