#include <plc.hpp>

// Explicit %TM7: 100ms time base, initial preset 3 ticks.
plc::Ton delay{7, 100, 3};

void scan() {
    if (plc::input(1)) { delay.set_preset(1); }
    bool reached = delay.update(plc::input(0));
    plc::output(0, reached);
    plc::output(1, delay.preset() == 1);
    plc::output(2, delay.value() >= 1);
    plc::output(3, delay.done());
}
