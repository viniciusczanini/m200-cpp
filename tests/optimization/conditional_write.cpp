#include <plc.hpp>

void scan() {
  if (plc::input(0)) { plc::output(0, plc::input(1)); }
  plc::output(1, plc::output_state(0));
}
