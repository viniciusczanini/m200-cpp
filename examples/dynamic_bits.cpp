#include <plc.hpp>

// Local example. SMBP export is gated until FL10.0 mapping is proven.
bool channels[4] = {true};

void scan() {
    for (plc::i16 i = 0; i < 4; i = plc::add_i16(i, 1)) {
        if (plc::input(0)) { channels[i] = !channels[i]; }
    }
    plc::i16 selected = 0;
    if (plc::input(1)) { selected = 3; }
    plc::output(0, channels[selected]);
    plc::output(1, !plc::system(20));
}
