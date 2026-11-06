#include <plc.hpp>

plc::ShiftBitRegister shift{0};
plc::StepCounter step{1};
plc::Drum drum{2, 3,
    plc::DrumCam{0, plc::DrumOutput::Memory, 40, 2},
    plc::DrumCam{1, plc::DrumOutput::Memory, 41, 4},
    plc::DrumCam{2, plc::DrumOutput::Memory, 42, 1}};

void scan() {
    if (plc::input(3)) { shift.set_bit(8, true); }
    shift.update(plc::input(0), plc::input(1), plc::input(2));
    step.update(plc::input(0), plc::input(1), plc::input(2));
    plc::write_word(12, drum.step());
    if (plc::input(4)) { drum.set_step(2); }
    drum.update(plc::input(0), plc::input(1));
    plc::i16 limit = 3;
    if (step.bit(2)) { limit = 5; }
    plc::i16 sum = 0;
    for (plc::i16 n = 1; n <= limit; n = plc::add_i16(n, 1)) {
        sum = plc::add_i16(sum, n);
    }
    plc::output(0, shift.bit(8));
    plc::output(1, shift.bit(9));
    plc::output(2, shift.bit(10));
    plc::output(3, step.bit(0));
    plc::output(4, step.bit(1));
    plc::output(5, step.bit(2));
    plc::output(6, plc::read_m(40));
    plc::output(7, plc::read_m(41));
    plc::output(8, plc::read_m(42));
    plc::output(9, drum.full());
    plc::output(10, sum == 6);
    plc::output(11, sum == 15);
    plc::write_word(10, drum.step());
    plc::write_word(13, drum.step());
    plc::write_word(14, sum);
}
