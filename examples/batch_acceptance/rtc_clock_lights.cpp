#include <plc.hpp>

plc::Clock light_clock{20};

void scan() {
    plc::i16 hhmm = plc::read_system_word(51);
    plc::i16 mmdd = plc::read_system_word(52);
    bool valid = !plc::system(51);
    bool window = mmdd >= 0x1101 && mmdd <= 0x1231 &&
                  hhmm >= 0x1800 && hhmm < 0x2300;
    bool enabled = valid && window && plc::input(1) &&
                   !plc::input(0) && !plc::input(2);
    bool phase = light_clock.update(enabled);
    plc::output(0, enabled && phase);
    plc::output(1, enabled && !phase);
    plc::output(2, enabled);
    plc::output(3, valid);
    plc::output(4, plc::input(2));
}
