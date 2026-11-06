#include <plc.hpp>

plc::ReadVar remote{0, plc::Link::Serial1, 1, 100,
                    plc::Object::DiscreteInputs, 17, 17, 200};

void scan() {
  remote.update(plc::input(0), plc::input(1));
  plc::output(0, plc::input(0));
  plc::output(1, plc::input(1));
  plc::output(2, plc::read_word(200) == -32767 && plc::read_word(201) == 1);
}
