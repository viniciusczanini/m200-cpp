#include <plc.hpp>

plc::Fifo r{0};

void scan() {
    r.set_input(11);
    if (plc::input(0)) {
        r.update(true, false, false);
    } else {
        r.update(false, false, false);
        r.update(false, plc::input(1), plc::input(2));
    }
    plc::output(0, r.empty());
    plc::output(1, r.full());
    plc::output(2, r.output() == 11);
}
