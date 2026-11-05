#include <plc.hpp>

plc::RisingEdge pulse;
plc::i16 count = 0;

void scan() {
    bool event = pulse.update(plc::input(0));
    if (event) {
        count = plc::add_i16(count, 1);
    }
    if (count >= 50 || plc::input(1)) {
        count = 0;
    }
    plc::f32 fraction = plc::div_f32(plc::int_to_real(count), 50.0f);
    plc::write_word(0, count);
    plc::write_real(2, fraction);
    plc::output(0, fraction >= 0.5f);
}
