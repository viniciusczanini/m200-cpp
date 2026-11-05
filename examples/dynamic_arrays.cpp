#include <plc.hpp>

plc::i32 counters[4] = {};

void scan() {
    plc::clear_index_error();
    for (plc::i16 i = 0; i < 4; i = plc::add_i16(i, 1)) {
        if (plc::input(0)) { counters[i] = plc::add_i32(counters[i], 1); }
    }
    plc::i16 selected = 0;
    if (plc::input(1)) { selected = 3; }
    plc::output(0, counters[selected] > 0);
    plc::output(1, counters[0] == counters[3]);
    plc::output(2, !plc::system(20));
}
