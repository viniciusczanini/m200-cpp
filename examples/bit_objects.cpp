#include <plc.hpp>

void scan() {
    plc::i16 buttons = plc::read_input_bits_i16(0, 8);
    plc::write_m_bits_i16(64, 8, buttons);
    plc::write_word(100, buttons);
    plc::write_word_bit(100, 15, plc::input(8));
    plc::copy_m_bits(72, 64, 8);
    plc::write_output_bits_i16(0, 8, plc::read_m_bits_i16(72, 8));
    plc::output(8, plc::read_word_bit(100, 15));
    plc::output(9, plc::read_output_bits_i16(0, 8) == buttons);
}
