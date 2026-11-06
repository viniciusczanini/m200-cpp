#include <plc.hpp>

void scan() {
  plc::i16 sample = -1;
  if (plc::input(1)) { sample = 4; }
  if (plc::input(2)) { sample = 12; }
  plc::output(0, false);
  if (plc::input(0)) {
    if (sample >= 0) {
      if (sample < 10) { plc::output(0, true); }
    }
  }
  plc::write_word(10, sample);
}
