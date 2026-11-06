#include <plc.hpp>

void scan() {
  bool enabled = plc::input(0);
  bool allowed = enabled && !plc::input(1);
  bool selected = allowed || plc::input(2);
  bool result = selected && enabled;
  plc::output(0, result);
  plc::output(1, selected);
}
