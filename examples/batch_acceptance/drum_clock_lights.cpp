#include <plc.hpp>

plc::Clock clock{20};
plc::Drum drum{0, 3,
    plc::DrumCam{0, plc::DrumOutput::Memory, 40, 1},
    plc::DrumCam{1, plc::DrumOutput::Memory, 41, 2},
    plc::DrumCam{2, plc::DrumOutput::Memory, 42, 4}};

void scan() {
    bool enabled = plc::input(1) && !plc::input(0) && !plc::input(2);
    bool phase = clock.update(enabled);
    drum.update(plc::input(0), phase);
    plc::i16 checksum = 0;
    for (plc::i16 n = 1; n <= 3; n = plc::add_i16(n, 1)) {
        checksum = plc::add_i16(checksum, n);
    }
    plc::output(0, enabled && plc::read_m(40));
    plc::output(1, enabled && plc::read_m(41));
    plc::output(2, enabled && plc::read_m(42));
    plc::output(3, enabled);
    plc::output(4, plc::input(2));
    plc::output(5, phase);
    plc::output(6, checksum == 6);
    plc::write_word(10, drum.step());
    plc::write_word(11, checksum);
}
