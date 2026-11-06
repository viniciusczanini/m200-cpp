#include <plc.hpp>

void leaf() {
  plc::write_word(10, 20);
  plc::output(1, true);
}
plc::Subroutine action{0, leaf, "benchmark_leaf", 2};
void scan() {
  plc::write_word(10, 10);
  plc::output(1, false);
  action.call(plc::input(0));
  plc::write_word(11, plc::read_word(10));
  plc::output(0, true);
}
