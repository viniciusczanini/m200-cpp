#include <plc.hpp>

plc::WriteVar remote{0, plc::Link::Serial1, 1, 100,
                     plc::Object::Coils, 73, 17, 240};

void scan() {
  if (plc::input(2)) {
    plc::write_word(240, 2);
    plc::write_word(241, 0);
  } else {
    plc::write_word(240, -32767);
    plc::write_word(241, 1);
  }
  remote.update(plc::input(0), plc::input(1));
  // Deliberately partial/reordered: BUSY overwrites ERROR on the shared bit.
  plc::write_m(30, remote.error());
  plc::write_m(30, remote.busy());
  plc::write_m(31, remote.done());
  plc::output(0, plc::read_m(30));
  plc::output(1, plc::read_m(31));
  plc::output(2, remote.aborted());
  plc::output(3, plc::input(2));
}
