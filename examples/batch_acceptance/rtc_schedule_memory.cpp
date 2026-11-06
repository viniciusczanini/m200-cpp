#include <plc.hpp>

plc::Schedule evening{0, 0, 60, 1, 11, 18, 0, 31, 12, 23, 0, 127};
plc::Schedule overlap{15, 0, 61, 1, 11, 19, 0, 31, 12, 20, 0, 127};

void scan() {
    if (plc::input(0)) { evening.set_end_hour(22); }
    if (plc::input(2)) { evening.set_end_hour(23); }
    if (plc::input(1)) { plc::write_system_word(114, 0); }
    if (plc::input(3)) { plc::write_system_word(114, -1); }
    plc::output(0, plc::read_m(60) && !plc::input(4));
    plc::output(1, plc::read_m(61) && !plc::input(4));
    plc::output(2, !plc::system(51));
    plc::output(3, plc::read_system_word(114) == -1);
    plc::write_word(10, evening.end_hour());
    plc::write_word(11, plc::read_system_word(114));
}
