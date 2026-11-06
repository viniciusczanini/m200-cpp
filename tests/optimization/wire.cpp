#include <plc.hpp>

void scan() {
  plc::output(0, plc::input(0));
}
