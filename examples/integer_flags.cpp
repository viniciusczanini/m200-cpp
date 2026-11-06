#include <plc.hpp>

plc::i16 total = 32767;

void scan() {
    if (plc::input(0)) { plc::clear_arithmetic_error(); }
    if (plc::input(1)) { total = plc::add_i16(total, 1); }
    bool overflow = plc::system(18);
    if (overflow) { total = 32767; }
    plc::i16 shifted = plc::shr_i16(total, 1);
    bool last_bit = plc::system(17);
    plc::output(0, overflow);
    plc::output(1, last_bit);
    plc::output(2, shifted > 0);
}
