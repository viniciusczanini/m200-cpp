#include <plc.hpp>
// Text only. I7 EXEC, I0 R, I1 U, I3 write2, I4 write1, I6 skip block.
// I3 and I4 are mutually exclusive in the plan. No aliasing of cam destinations.
plc::Drum dr{0,3,
    plc::DrumCam{0,plc::DrumOutput::Memory,100,1},
    plc::DrumCam{1,plc::DrumOutput::Memory,101,2},
    plc::DrumCam{2,plc::DrumOutput::Memory,102,4}};
void scan() {
    if (plc::system(13)) {
        plc::write_m(900,false);
        plc::write_m(901,false);
        plc::write_word(15,0);
    }
    if (!plc::input(7)) plc::write_m(900,false);
    if (plc::input(7) && !plc::read_m(900)) {
        plc::write_m(900,true);
        plc::write_word(0,dr.step());
        plc::write_word(3,0);
        plc::write_word_bit(3,0,plc::read_m(100));
        plc::write_word_bit(3,1,plc::read_m(101));
        plc::write_word_bit(3,2,plc::read_m(102));
        plc::write_word(6,0);
        plc::write_word_bit(6,0,dr.full());
        if (plc::input(3)) dr.set_step(2);
        else if (plc::input(4)) dr.set_step(1);
        plc::write_word(1,dr.step());
        plc::write_word(4,0);
        plc::write_word_bit(4,0,plc::read_m(100));
        plc::write_word_bit(4,1,plc::read_m(101));
        plc::write_word_bit(4,2,plc::read_m(102));
        plc::write_word(7,0);
        plc::write_word_bit(7,0,dr.full());
        if (!plc::input(6)) dr.update(plc::input(0),plc::input(1));
        plc::write_word(2,dr.step());
        plc::write_word(5,0);
        plc::write_word_bit(5,0,plc::read_m(100));
        plc::write_word_bit(5,1,plc::read_m(101));
        plc::write_word_bit(5,2,plc::read_m(102));
        plc::write_word(8,0);
        plc::write_word_bit(8,0,dr.full());
        plc::write_word(10,0);
        plc::write_word_bit(10,0,plc::input(0));
        plc::write_word_bit(10,1,plc::input(1));
        plc::write_word_bit(10,3,plc::input(3));
        plc::write_word_bit(10,4,plc::input(4));
        plc::write_word_bit(10,6,plc::input(6));
        plc::inc_word(15);
        plc::write_m(901,true);
    }
    plc::output(0,plc::read_m(100));
    plc::output(1,plc::read_m(101));
    plc::output(2,plc::read_m(102));
    plc::output(3,dr.full());
    plc::output(14,plc::read_m(900));
    plc::output(15,plc::read_m(901));
}
