#include <plc.hpp>

plc::Ton ready{0, 100, 5};
plc::Counter accepted{0, 3};
bool latched = false;

void scan() {
    bool qualified = ready.update(plc::input(1) && !plc::input(2));
    bool pulse = plc::input_rising(0);
    bool complete = accepted.update(plc::input(2), false, pulse && qualified, false);
    if (plc::input(2)) { latched = false; }
    if (complete) { latched = true; }
    plc::i16 latch_word = 0;
    if (latched) { latch_word = 1; }
    plc::write_word(120, accepted.value());
    plc::write_word(121, ready.value());
    plc::write_word(122, ready.preset());
    plc::write_word(123, accepted.preset());
    plc::write_word(124, latch_word);
    plc::output(0, qualified);
    plc::output(1, accepted.value() == 1);
    plc::output(2, accepted.value() == 2);
    plc::output(3, complete);
    plc::output(4, latched);
    plc::output(5, accepted.value() == 0);
    plc::output(6, plc::input(1));
    plc::output(7, plc::input(2));
    plc::write_output_bits_i16(8, 4, accepted.value());
    plc::output(12, ready.value() > 0);
    plc::output(13, accepted.preset() == 3);
    plc::output(14, ready.preset() == 5);
    plc::output(15, !plc::system(18) && !plc::system(20));
}
