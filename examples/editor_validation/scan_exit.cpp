#include <plc.hpp>

void scan() {
    plc::output(0, plc::input(0));
    if (plc::system(13) || plc::input(2)) {
        plc::write_word(220, 0);
        plc::output(2, false);
        plc::output(3, false);
        plc::output(4, false);
        return;
    }
    if (plc::input(1)) { return; }
    plc::output(2, plc::input(0));
    if (plc::input_rising(0)) {
        plc::write_word(220, plc::add_i16(plc::read_word(220), 1));
    }
    plc::output(3, plc::read_word(220) == 1);
    plc::output(4, plc::read_word(220) == 2);
}
