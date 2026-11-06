#include <plc.hpp>

plc::Drum drum{7, 3,
    plc::DrumCam{0, plc::DrumOutput::Output, 0, 1},
    plc::DrumCam{1, plc::DrumOutput::Output, 1, 2},
    plc::DrumCam{2, plc::DrumOutput::Output, 2, 4}};

void scan() {
    drum.update(plc::input(0), plc::input(1));
    plc::output(8, drum.full());
    plc::write_word(10, drum.step());
}
