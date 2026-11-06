#include <plc.hpp>

void scan() {
  plc::output(0, plc::input(0));
  bool original = plc::output_state(0);
  plc::output(1, !original);
  plc::output(0, plc::input(1));
  plc::output(2, original && plc::output_state(0));
}
