#include <plc.hpp>

void scan() {
  plc::write_output_bits_i16(0, 16, plc::read_input_bits_i16(0, 16));
}
