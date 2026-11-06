#include <plc.hpp>

void leaf() {
    plc::write_word(0, 20);
    plc::write_word(1, 1);
    plc::output(1, true);
}

plc::Subroutine subroutine{0, leaf, "CPP_SR0_LEAF", 2};

void scan() {
    plc::write_word(0, 10);
    plc::write_word(1, 0);
    plc::output(1, false);
    plc::output(3, false);
    subroutine.call(plc::input(0));
    plc::write_word(2, plc::read_word(0));
    plc::write_word(0, 30);
    plc::output(0, plc::input(0));
    plc::output(2, true);
}
