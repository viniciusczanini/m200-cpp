#include <plc.hpp>

void scan() {
  plc::write_dword(20, 65538);
  if (plc::input(0)) { plc::write_word(21, 3); }
  plc::output(0, plc::read_word(20) == 2);
  plc::output(1, plc::read_dword(20) == 196610);
}
