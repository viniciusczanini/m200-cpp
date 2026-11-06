#include <plc.hpp>
// Text only. I7 EXEC; I0 R, I1 CU, I2 CD, I3 PRIME255.
// PRIME255 requires observed step0 and an already-called neutral input group.
// It delivers255 released/rising CU pairs in a real native loop, never unrolled.
// Watchdog/admission of this preparation is a separate prerequisite, not assumed.
plc::StepCounter sc{0};
void scan() {
    if (plc::system(13)) {
        plc::write_m(900,false);
        plc::write_m(901,false);
        plc::write_word(15,0);
    }
    if (!plc::input(7)) plc::write_m(900,false);
    if (plc::input(7) && !plc::read_m(900)) {
        plc::write_m(900,true);
        plc::write_word(1,0);
        plc::write_word_bit(1,0,sc.bit(0));
        plc::write_word_bit(1,1,sc.bit(1));
        plc::write_word_bit(1,2,sc.bit(254));
        plc::write_word_bit(1,3,sc.bit(255));
        plc::write_word_bit(1,4,sc.bit(2));
        if (plc::input(3)) {
            plc::i16 i=0;
            while (i<255) {
                sc.update(false,false,false);
                sc.update(false,true,false);
                i=plc::add_i16(i,1);
            }
            sc.update(false,false,false);
            plc::write_word(3,255); // requested positive CU calls, NOT step value
        } else {
            sc.update(plc::input(0),plc::input(1),plc::input(2));
            plc::write_word(3,0);
        }
        // Five landmarks only; mask0 does NOT prove that no other step is active.
        plc::write_word(0,0);
        plc::write_word_bit(0,0,sc.bit(0));
        plc::write_word_bit(0,1,sc.bit(1));
        plc::write_word_bit(0,2,sc.bit(254));
        plc::write_word_bit(0,3,sc.bit(255));
        plc::write_word_bit(0,4,sc.bit(2));
        plc::write_word(2,0);
        plc::write_word_bit(2,0,plc::input(0));
        plc::write_word_bit(2,1,plc::input(1));
        plc::write_word_bit(2,2,plc::input(2));
        plc::write_word_bit(2,3,plc::input(3));
        plc::inc_word(15);
        plc::write_m(901,true);
    }
    plc::output(0,sc.bit(0));
    plc::output(1,sc.bit(1));
    plc::output(2,sc.bit(254));
    plc::output(3,sc.bit(255));
    plc::output(4,sc.bit(2));
    plc::output(14,plc::read_m(900));
    plc::output(15,plc::read_m(901));
}
