#include <plc.hpp>

plc::WriteReadVar remote{0, plc::Link::Serial1, 1, 100,
                         17, 2, 300, 41, 3, 400};
plc::Ton gate{4, 10, 2};

void scan() {
  gate.update(plc::input(3));
  if (plc::system(13)) {
    plc::write_word(399, 30583);
    plc::write_word(400, 9320);
    plc::write_word(401, 4951);
    plc::write_word(402, 13980);
    plc::write_word(403, -30584);
  }
  if (plc::input(2)) {
    plc::write_word(300, 17185);
    plc::write_word(301, 4369);
  } else {
    plc::write_word(300, 4660);
    plc::write_word(301, -21555);
  }
  remote.update(plc::input(0) && gate.done() && !plc::input(4),
                plc::input(1) || plc::input(5));
  // Status observations remain ordinary rungs, deliberately BUSY before DONE.
  plc::output(0, remote.busy());
  plc::output(1, remote.done());
  plc::output(2, remote.aborted());
  plc::output(3, remote.error());
  plc::output(4, gate.done());
  plc::output(5, plc::read_word(400) == -32767 &&
                 plc::read_word(401) == -1 && plc::read_word(402) == 4660);
  plc::output(6, plc::input(4));
  plc::output(7, plc::input(5));
  plc::output(8, plc::input(2));
  plc::write_word(20, gate.value());
}
