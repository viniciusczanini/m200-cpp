#include <plc.hpp>

plc::WordMemory image{64};

void scan() {
    plc::clear_index_error();
    for (plc::i16 i = 0; i < 4; i = plc::add_i16(i, 1)) {
        plc::write_word(1, i); // MW1 stores the changing table offset.
        plc::write_word_indexed(16, 1, plc::mul_i16(i, 7));
    }
    plc::write_word(0, 1);
    if (plc::input(0)) { plc::write_word(0, 3); }
    plc::i16 value = plc::read_word_indexed(16, 0);
    plc::output(0, value == 21);
    plc::output(1, value == 7);
    plc::output(2, !plc::system(20));
}
