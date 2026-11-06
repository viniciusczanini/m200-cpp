#include <plc.hpp>

// Native instances; this example is an unvalidated API handoff, not a fixture.
plc::ShiftBitRegister shift{0};
plc::StepCounter step{1};
plc::Drum drum{2, 3,
    plc::DrumCam{0,plc::DrumOutput::Memory,10,2},
    plc::DrumCam{1,plc::DrumOutput::Memory,11,4}};

void scan() {
    // Native partial CU-only form from Generic Functions p155. Endpoints and
    // collisions require separate qualification; the local VM stops on ambiguity.
    if (plc::input(0)) shift.set_bit(8,true);
    shift.update_pins(2,false,plc::system(6),false);
    step.update(false,plc::input(1),false);
    if (plc::input(2)) drum.set_step(2);
    drum.update(false,plc::input(3));
    plc::output(0,shift.bit(15));
    plc::output(1,step.bit(3));
    plc::output(2,drum.full());
}
