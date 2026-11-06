#include <plc.hpp>

void scan() {
  if (plc::input(0)) { return; }
  plc::output(0, plc::input(1));
  plc::output(1, true);
}
