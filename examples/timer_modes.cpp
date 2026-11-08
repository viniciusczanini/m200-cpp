#include <plc.hpp>

// %TM9: retain elapsed ticks when paused; apply new preset on next timer tick.
// Local example. SMBP export waits for functional-level mapping.
plc::Ton accumulated{9, 100, 5, true, true};

void scan() {
    if (plc::input(1)) { accumulated.set_preset(2); }
    bool done = accumulated.update(plc::input(0));
    plc::output(0, done);
    plc::output(1, accumulated.value() > 0);
    plc::output(2, accumulated.preset() == 2);
}
