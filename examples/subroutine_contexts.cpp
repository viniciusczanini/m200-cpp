#include <plc.hpp>

// G06 usage contract. Unvalidated; batch editor/simulator acceptance pending.
plc::WordMemory image{64};
plc::Ton elapsed{4, 100, 2};
plc::Counter events{3, 5};

void accumulate() {
    plc::write_word(7, plc::add_i16(plc::read_word(7), 1));
    bool ready = elapsed.update(plc::input(2));
    bool reached = events.update(false, false, plc::input(3), false);
    plc::output(2, ready);
    plc::output(3, reached);
    if (plc::input(4)) { return; }
    for (plc::i16 i = 0; i < 3; i = plc::add_i16(i, 1)) {
        plc::write_word(1, i);
        plc::write_word_indexed(16, 1, plc::mul_i16(i, 7));
    }
    plc::write_word(10, 1);
}

void snapshot() {
    plc::write_word(8, plc::read_word(7));
    // The timer and counter above remain the same native instances here.
    plc::write_word(11, events.value());
    plc::output(4, elapsed.done());
}

plc::Subroutine increment{0, accumulate, "accumulate shared state", 2};
plc::Subroutine capture{63, snapshot, "capture shared state", 42};

void scan() {
    plc::write_word(7, 0);
    plc::write_word(8, 0);
    plc::write_word(10, 0);
    increment.call(plc::input(0));
    increment.call(plc::input(0));
    capture.call(plc::input(1));
    plc::write_word(9, 30);
    plc::output(0, plc::read_word(7) == 2);
    plc::output(1, plc::read_word(8) == 2);
}
