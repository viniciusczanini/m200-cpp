#include <plc.hpp>

plc::Schedule zero{0, 0, 0, 1, 11, 18, 0, 31, 12, 23, 0, 127};
plc::Schedule one{15, 0, 1, 1, 11, 19, 0, 31, 12, 20, 0, 127};

void scan() {
    bool ab = plc::input(0) && plc::input(1);
    bool cd = plc::input(2) || plc::input(3);
    bool different = ab != cd;
    plc::output(0, different);
    plc::output(1, ab && !plc::input(4));
    plc::output(2, cd || plc::input(5));
    plc::output(3, (different && plc::input(6)) || plc::input(7));
    if (plc::input(4)) { plc::write_system_word(114, 0); }
    if (plc::input(5)) { plc::write_system_word(114, -1); }
}
