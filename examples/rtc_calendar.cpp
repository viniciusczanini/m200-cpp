#include <plc.hpp>

// Native documented S/SW route: no RTC FB graph or schedule configuration needed.
// BCD HHMM/MMDD sort chronologically within a day/year. End time is exclusive.
void scan() {
    plc::rtc_snapshot(100); // MW100=weekday,101=seconds,102=HHMM,103=MMDD,104=CCYY.
    plc::i16 hhmm = plc::read_word(102);
    plc::i16 mmdd = plc::read_word(103);
    bool valid = !plc::system(51);
    bool season = mmdd >= 0x1101 && mmdd <= 0x1231;
    bool evening = hhmm >= 0x1800 && hhmm < 0x2300;
    bool overnight = hhmm >= 0x2300 || hhmm < 0x0200;
    plc::output(0, valid && season && evening);
    plc::output(1, valid && season && overnight);
    plc::write_dword(110, plc::absolute_counter_100ms());
    if (plc::input_rising(0)) {
        // 2026-11-06 17:59:58; S50 protects staging, falling edge commits.
        plc::write_system(50, true);
        plc::write_system_word(50, 0x0058);
        plc::write_system_word(51, 0x1759);
        plc::write_system_word(52, 0x1106);
        plc::write_system_word(53, 0x2026);
        plc::write_system(50, false);
    }
    // Inspect S52 on a later scan when checking an external native RTC write.
    plc::output(2, plc::system(52));
}
