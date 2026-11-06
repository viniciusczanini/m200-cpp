#include <plc.hpp>

void scan() {
  plc::i16 sum = 0;
  plc::i16 index = 0;
  plc::i16 limit = 3;
  if (plc::input(0)) { limit = 5; }
  while (index < limit) {
    sum = plc::add_i16(sum, index);
    index = plc::add_i16(index, 1);
  }
  plc::write_word(10, sum);
  plc::output(0, sum == 3);
  plc::output(1, sum == 10);
}
