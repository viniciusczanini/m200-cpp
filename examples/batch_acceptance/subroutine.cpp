#include <plc.hpp>

void leaf() {
    plc::write_word(10, 20);
    plc::write_word(11, 1);
    plc::output(1, true);
}

plc::Subroutine subroutine{0, leaf, "BATCH_SR0_LEAF", 2};

void scan() {
    plc::write_word(10, 10);
    plc::write_word(11, 0);
    plc::output(1, false);
    subroutine.call(plc::input(1));
    plc::write_word(12, plc::read_word(10));
    plc::write_word(10, 30);
    plc::output(0, plc::input(1));
    plc::output(2, true);
}
