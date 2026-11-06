#include <plc.hpp>

void scan() {
    if (plc::input_rising(0)) {
        plc::write_system(50, true);
        plc::write_system_word(50, plc::read_word(20));
        plc::write_system_word(51, plc::read_word(21));
        plc::write_system_word(52, plc::read_word(22));
        plc::write_system_word(53, plc::read_word(23));
        plc::write_system(50, false);
    }
    if (plc::input_rising(1)) {
        plc::write_system_word(18, 0);
        plc::write_system_word(19, 0);
    }
    plc::rtc_snapshot(100);
    plc::i16 hhmm = plc::read_word(102);
    plc::i16 mmdd = plc::read_word(103);
    bool valid = !plc::system(51);
    bool season = mmdd >= 0x1101 && mmdd <= 0x1231;
    bool evening = hhmm >= 0x1800 && hhmm < 0x2300;
    bool overnight = hhmm >= 0x2300 || hhmm < 0x0200;
    bool allowed = valid && season && !plc::input(2);
    plc::output(0, allowed && evening);
    plc::output(1, allowed && overnight);
    plc::output(2, valid);
    plc::output(3, season);
    plc::output(4, plc::system(52));
    plc::output(5, plc::system(50));
    plc::write_dword(110, plc::absolute_counter_100ms());
}
