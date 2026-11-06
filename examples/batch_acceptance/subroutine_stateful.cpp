#include <plc.hpp>

plc::Ton shared_timer{4, 10, 2};

void accumulate() {
    plc::i16 total = 0;
    for (plc::i16 term = 1; term <= 3; term = plc::add_i16(term, 1)) {
        if (term == 2) { continue; }
        total = plc::add_i16(total, term);
    }
    plc::write_word(7, plc::add_i16(plc::read_word(7), total));
    bool q = shared_timer.update(plc::input(2));
    plc::write_m(200, q);
    plc::write_word(20, 99);
    if (plc::input(3)) {
        plc::write_word(8, plc::add_i16(plc::read_word(8), 1));
        return;
    }
    plc::write_word(8, plc::add_i16(plc::read_word(8), 10));
}

void snapshot() {
    plc::write_word(9, plc::read_word(7));
    plc::write_word(10, plc::read_word(8));
    plc::write_word(11, shared_timer.value());
    if (plc::input(4)) { return; }
    plc::write_word(15, 77);
}

plc::Subroutine add_twice{0, accumulate, "BATCH_SR0_ACCUMULATE", 2};
plc::Subroutine read_after{63, snapshot, "BATCH_SR63_SNAPSHOT", 42};

void scan() {
    plc::i16 original = plc::read_word(20);
    plc::i16 held = plc::add_i16(original, 7);
    plc::write_word(7, 0);
    plc::write_word(8, 0);
    plc::write_word(9, -1);
    plc::write_word(10, -1);
    plc::write_word(11, -1);
    plc::write_word(15, -1);
    add_twice.call(plc::input(1));
    add_twice.call(plc::input(1));
    read_after.call(plc::input(5));
    plc::write_word(12, held);
    plc::write_word(13, original);
    plc::i16 result = plc::add_i16(held, plc::read_word(7));
    plc::write_word(14, result);
    if (shared_timer.done()) { result = plc::add_i16(result, 256); }
    if (plc::read_m(200)) { plc::write_word(16, 1); }
    else { plc::write_word(16, 0); }
    plc::write_word(1, result);
    plc::write_output_bits_i16(0, 16, result);
}
